"""수집 유스케이스(명세 "수집 API", "수집 파이프라인과 작업").

파일 하나를 받아 원본을 저장하고, 작업 단위 하나에서 문서 행을 만들거나 고치고 `index_document`
작업을 넣는다. 순서는 이렇다. 먼저 크기와 형식과 그룹을 거른다(셋 다 작업을 만들지 않는다). 원본은
작업 단위를 열기 전에 새 경로 `blobs/<문서 UUID>/<원본 UUID>`에 쓴다. 작업 단위가 롤백되면 그 요청이
쓴 새 원본만 지우고, 커밋된 뒤에는 문서 행이 더는 가리키지 않는 원본(옛 원본, 또는 `unchanged`가 쓴
새 원본)을 지운다. 지우기는 최선 노력이다. 지우지 못한 원본은 고아로 남긴다.

같은 키를 동시에 넣은 두 요청은 (원천, 키) 유일 제약이 직렬화한다. 진 쪽은 원본을 이긴 문서의 UUID
아래 새 원본 경로로 옮긴 뒤 갱신으로 다시 처리한다.

그룹이 바뀐 수집(10)과 지운 문서를 되살리는 수집(11)은 이 모듈이 아직 처리하지 않는다.
"""

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePath
from typing import Final
from uuid import UUID

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IngestAction,
    JsonValue,
)
from rag_engine.domain.errors import (
    DocumentAlreadyExistsError,
    ErrorCode,
    InvalidInput,
    RequestError,
    TransientFailure,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.media_types import detect_media_type
from rag_engine.domain.ports import BlobStore, LockMode, Transaction, UnitOfWork

logger = logging.getLogger(__name__)

# 같은 키를 동시에 넣은 요청이 진 쪽은 한 번만 이긴 문서로 다시 처리한다.
_MAX_ATTEMPTS: Final = 2


@dataclass(frozen=True, slots=True)
class IngestRequest:
    """수집 요청의 입력. `key`와 `group`을 주지 않으면 파일 이름과 기본 그룹이다."""

    filename: str | None
    data: bytes
    key: str | None
    group: str | None
    metadata: Mapping[str, JsonValue]
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class IngestResult:
    """수집이 문서에 한 일. 작업을 넣지 않았으면 `job_id`가 `None`이다."""

    action: IngestAction
    document_id: UUID
    job_id: UUID | None


@dataclass(frozen=True, slots=True)
class _Upload:
    """저장한 원본과, 문서 행에 쓸 요청의 값."""

    source_id: UUID
    group_id: UUID
    key: str
    title: str
    mime: str
    size_bytes: int
    content_hash: str
    metadata: Mapping[str, JsonValue]
    updated_at: datetime | None
    document_id: UUID
    blob_key: str


@dataclass(frozen=True, slots=True)
class _Recorded:
    """커밋한 결과와 뒷정리가 지울 원본. 지울 것이 없으면 `None`이다."""

    result: IngestResult
    stale_blob_key: str | None


def ensure_within_upload_limit(size_bytes: int, max_upload_bytes: int) -> None:
    if size_bytes > max_upload_bytes:
        raise RequestError(ErrorCode.UPLOAD_TOO_LARGE, "업로드가 크기 상한을 넘었다")


async def ingest_document(
    unit_of_work: UnitOfWork,
    blob_store: BlobStore,
    request: IngestRequest,
    *,
    request_id: UUID,
    now: datetime,
    max_upload_bytes: int,
) -> IngestResult:
    ensure_within_upload_limit(len(request.data), max_upload_bytes)
    _ensure_filename_storable(request.filename)
    key = _document_key(request)
    mime = detect_media_type(request.filename, request.data)
    if mime is None:
        raise RequestError(ErrorCode.UNSUPPORTED_MEDIA_TYPE, "PDF, DOCX, HWPX만 받는다")
    upload = await _locate(unit_of_work, request, key, mime)

    await blob_store.write(upload.blob_key, request.data)
    recorded = await _record_with_retry(unit_of_work, blob_store, request, upload, request_id, now)
    await _remove_quietly(blob_store, recorded.stale_blob_key)
    return recorded.result


def _ensure_filename_storable(filename: str | None) -> None:
    """파일 이름은 키나 제목이 되어 text 칸에 들어가는데, PostgreSQL은 NUL을 담지 못한다."""
    if filename is not None and "\x00" in filename:
        raise InvalidInput(("file",), "invalid", "파일 이름에 NUL 문자(\\u0000)를 담을 수 없다")


def _document_key(request: IngestRequest) -> str:
    key = request.key if request.key is not None else request.filename
    if not key:
        raise InvalidInput(("key",), "missing", "key나 파일 이름이 있어야 한다")
    return key


def _title(metadata: Mapping[str, JsonValue], name: str) -> str:
    """`metadata.title`이 문자열이면 그것, 아니면 확장자를 뗀 파일 이름이다."""
    title = metadata.get("title")
    return title if isinstance(title, str) else PurePath(name).stem


async def _locate(unit_of_work: UnitOfWork, request: IngestRequest, key: str, mime: str) -> _Upload:
    """원천과 그룹을 읽고 원본을 둘 경로를 정한다. 없는 그룹이면 원본을 쓰기 전에 거부한다."""
    async with unit_of_work.begin() as transaction:
        source = await transaction.catalog.get_source(DEFAULT_NAME)
        if source is None:
            raise RuntimeError("기본 원천이 없다. migrate를 돌려야 한다")
        group = await transaction.catalog.get_group(request.group or DEFAULT_NAME)
        if group is None:
            raise RequestError(ErrorCode.GROUP_NOT_FOUND, "그 이름의 그룹이 없다")
        existing = await transaction.documents.get_by_key(source.id, key)
    document_id = new_id() if existing is None else existing.id
    return _Upload(
        source_id=source.id,
        group_id=group.id,
        key=key,
        title=_title(request.metadata, request.filename or key),
        mime=mime,
        size_bytes=len(request.data),
        content_hash=hashlib.sha256(request.data).hexdigest(),
        metadata=request.metadata,
        updated_at=request.updated_at,
        document_id=document_id,
        blob_key=_blob_key(document_id),
    )


def _blob_key(document_id: UUID) -> str:
    return f"blobs/{document_id}/{new_id()}"


async def _record_with_retry(
    unit_of_work: UnitOfWork,
    blob_store: BlobStore,
    request: IngestRequest,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
) -> _Recorded:
    """문서 행과 작업을 쓴다. 같은 키의 문서를 다른 요청이 먼저 만들었으면 원본을 그 문서의 UUID
    아래로 옮기고 한 번 더 쓴다. 쓰지 못하고 끝나면 그 요청이 새로 저장한 원본을 지운다."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return await _record(unit_of_work, upload, request_id, now)
        except DocumentAlreadyExistsError:
            if attempt == _MAX_ATTEMPTS:
                await _remove_quietly(blob_store, upload.blob_key)
                raise
            upload = await _move_blob_to_winner(unit_of_work, blob_store, request, upload)
        except BaseException:
            await _discard_unless_recorded(unit_of_work, blob_store, upload)
            raise
    raise AssertionError("시도 횟수가 1 이상이라 도달하지 않는다")


async def _discard_unless_recorded(
    unit_of_work: UnitOfWork, blob_store: BlobStore, upload: _Upload
) -> None:
    """커밋이 됐는지 모르는 실패(커밋 응답을 받지 못한 연결, 취소) 뒤의 뒷정리다. 문서 행이 이
    원본을 가리키면 커밋된 것이라 지우지 않는다. 행을 읽지 못해 결과를 모르면 고아로 남긴다. 문서가
    가리키는 원본을 잃는 것보다 고아가 낫다."""
    try:
        async with unit_of_work.begin() as transaction:
            document = await transaction.documents.get(upload.document_id)
    except Exception:
        logger.warning("orphan_blob_left", exc_info=True)
        return
    if document is None or document.blob_path != upload.blob_key:
        await _remove_quietly(blob_store, upload.blob_key)


async def _move_blob_to_winner(
    unit_of_work: UnitOfWork, blob_store: BlobStore, request: IngestRequest, upload: _Upload
) -> _Upload:
    """이긴 문서의 UUID 아래 새 원본 경로에 다시 쓰고 진 쪽이 처음 쓴 원본을 지운다. 옮기지 못하면
    처음 쓴 원본을 지우고 오류를 올린다."""
    try:
        moved = await _write_under_winner(unit_of_work, blob_store, request, upload)
    except BaseException:
        await _remove_quietly(blob_store, upload.blob_key)
        raise
    await _remove_quietly(blob_store, upload.blob_key)
    return moved


async def _write_under_winner(
    unit_of_work: UnitOfWork, blob_store: BlobStore, request: IngestRequest, upload: _Upload
) -> _Upload:
    async with unit_of_work.begin() as transaction:
        winner = await transaction.documents.get_by_key(upload.source_id, upload.key)
    if winner is None:
        raise RuntimeError("같은 키의 문서가 있다고 했는데 읽히지 않는다")
    moved = replace(upload, document_id=winner.id, blob_key=_blob_key(winner.id))
    await blob_store.write(moved.blob_key, request.data)
    return moved


async def _record(
    unit_of_work: UnitOfWork, upload: _Upload, request_id: UUID, now: datetime
) -> _Recorded:
    async with unit_of_work.begin() as transaction:
        existing = await transaction.documents.get_by_key(upload.source_id, upload.key)
        if existing is None:
            return await _create(transaction, upload, request_id, now)
        if existing.id != upload.document_id:
            # 원본 경로를 정한 뒤에 같은 키의 문서가 생겼다. 원본은 그 문서의 UUID 아래에 있어야
            # 한다.
            raise DocumentAlreadyExistsError("원본 경로를 정한 뒤에 같은 키의 문서가 생겼다")
        locked = await transaction.documents.lock(existing.id)
        if locked is None:
            raise RuntimeError("문서 행이 잠그는 사이에 사라졌다")
        return await _amend(transaction, locked, upload, request_id, now)


async def _create(
    transaction: Transaction, upload: _Upload, request_id: UUID, now: datetime
) -> _Recorded:
    document = Document(
        id=upload.document_id,
        source_id=upload.source_id,
        key=upload.key,
        group_id=upload.group_id,
        title=upload.title,
        mime=upload.mime,
        size_bytes=upload.size_bytes,
        content_hash=upload.content_hash,
        blob_path=upload.blob_key,
        metadata=upload.metadata,
        updated_at=upload.updated_at or now,
        effective_date=None,
        access_groups=(),
        status=DocumentStatus.RECEIVED,
        error_code=None,
        generation=1,
        deleted_at=None,
        purged_at=None,
        created_at=now,
        modified_at=now,
    )
    await transaction.documents.add(document)
    job_id = await _enqueue(transaction, document, request_id, now)
    return _Recorded(IngestResult(IngestAction.CREATED, document.id, job_id), None)


async def _amend(
    transaction: Transaction,
    existing: Document,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
) -> _Recorded:
    if existing.deleted_at is not None:
        raise NotImplementedError("지운 문서를 되살리는 수집은 티켓 11이 처리한다")
    if existing.group_id != upload.group_id:
        raise NotImplementedError("그룹을 바꾸는 수집은 티켓 10이 처리한다")
    if existing.content_hash == upload.content_hash:
        await _refresh_unchanged(transaction, existing, upload, now)
        return _Recorded(IngestResult(IngestAction.UNCHANGED, existing.id, None), upload.blob_key)
    document = replace(
        existing,
        title=upload.title,
        mime=upload.mime,
        size_bytes=upload.size_bytes,
        content_hash=upload.content_hash,
        blob_path=upload.blob_key,
        metadata=upload.metadata,
        updated_at=upload.updated_at or now,
        status=DocumentStatus.RECEIVED,
        error_code=None,
        generation=existing.generation + 1,
        modified_at=now,
    )
    await transaction.documents.update(document)
    job_id = await _enqueue(transaction, document, request_id, now)
    return _Recorded(IngestResult(IngestAction.UPDATED, document.id, job_id), existing.blob_path)


async def _refresh_unchanged(
    transaction: Transaction, existing: Document, upload: _Upload, now: datetime
) -> None:
    """내용이 같아 건너뛰는 수집이 메타데이터, 제목, 호출자가 준 갱신일만 문서 행에 반영한다.
    갱신일이 바뀌면 조각의 복사 칸도 같은 트랜잭션에서 고친다. 호출자가 갱신일을 주지 않으면 그대로
    둔다."""
    refreshed = replace(
        existing,
        title=upload.title,
        metadata=upload.metadata,
        updated_at=existing.updated_at if upload.updated_at is None else upload.updated_at,
    )
    if refreshed == existing:
        return
    await transaction.documents.update(replace(refreshed, modified_at=now))
    if refreshed.updated_at != existing.updated_at:
        await transaction.index.update_chunk_copies(refreshed)


async def _enqueue(
    transaction: Transaction, document: Document, request_id: UUID, now: datetime
) -> UUID:
    """문서 행을 쓴 바로 뒤, 문서가 드는 지식베이스 행을 `FOR SHARE`로 잠그고 작업을 넣는다(잠금
    순서는 문서 행, 지식베이스 행, 작업 행이다)."""
    knowledge_bases = await transaction.catalog.list_knowledge_bases_of_group(document.group_id)
    await transaction.catalog.lock_knowledge_bases(
        [knowledge_base.id for knowledge_base in knowledge_bases], LockMode.SHARE
    )
    job = await transaction.jobs.enqueue(document.id, request_id, now)
    return job.id


async def _remove_quietly(blob_store: BlobStore, key: str | None) -> None:
    """원본 지우기는 최선 노력이다. 지우지 못하면 고아로 남긴다. 이유는 로그 포매터가 예외
    정보(타입, 프레임, 이 저장소가 정의한 예외의 메시지)로 싣는다. 원본 경로와 문서의 키는 싣지
    않는다."""
    if key is None:
        return
    try:
        await blob_store.delete(key)
    except TransientFailure as error:
        logger.warning("orphan_blob_left", exc_info=error)
