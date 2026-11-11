"""수집 유스케이스(명세 "수집 API", "수집 파이프라인과 작업").

파일 하나를 받아 원본을 저장하고, 작업 단위 하나에서 문서 행을 만들거나 고치고 `index_document`
작업을 넣는다. 순서는 이렇다. 먼저 크기와 형식과 그룹을 거른다(셋 다 작업을 만들지 않는다). 원본은
작업 단위를 열기 전에 새 경로 `blobs/<문서 UUID>/<원본 UUID>`에 쓴다. 작업 단위가 롤백되면 그 요청이
쓴 새 원본만 지우고, 커밋된 뒤에는 문서 행이 더는 가리키지 않는 원본을 지운다. 내용이 바뀐 갱신은
옛 원본을, 묘비 행을 다시 쓰는 `created`는 묘비 행이 가리키던 원본을, 문서 행이 새 원본을 가리키지
않는 수집(`unchanged`, `requeued`, 그룹만 바뀐 `updated`, 내용이 같은 되살림)은 방금 쓴 새 원본을
지운다. 지우기는 최선 노력이다. 지우지 못한 원본은 고아로 남긴다.

같은 키를 동시에 넣은 두 요청은 (원천, 키) 유일 제약이 직렬화한다. 진 쪽은 원본을 이긴 문서의 UUID
아래 새 원본 경로로 옮긴 뒤 갱신으로 다시 처리한다.

지우지 않은 문서에 내용이 같은 수집은 셋으로 갈린다. 그룹이 바뀌었으면 `updated`이고, 앞선 색인이
실패했으면 `requeued`이며, 아니면 `unchanged`다. 그룹이 바뀌면 같은 작업 단위에서 조각의 복사 칸을
새 그룹으로 고치고 문서가 빠지는 지식베이스의 살아 있는 판에서 문서의 조각과 색인 상태를 지운다.

지운 문서(`deleted_at`은 있고 `purged_at`은 없다)가 같은 키로 돌아오면 되살림(`restored`)이다. 문서
UUID를 그대로 두고, 내용이 같으면 보관 조각을 검색 표로 되돌리며(되돌릴 조각이 없는 대상 판이 있을
때만 작업을 넣는다), 내용이 다르면 보관 조각을 지우고 갱신으로 간다. 정리 작업이 물리 삭제해 묘비
행만 남은 문서(`purged_at`)가 같은 키로 오면 그 행을 다시 써 UUID를 잇고 `created`다.
"""

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePath
from typing import Final
from uuid import UUID

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.app.live_versions import live_index_versions
from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    IngestAction,
    JsonValue,
    KnowledgeBase,
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


def _fresh_document(upload: _Upload, now: datetime, *, generation: int) -> Document:
    """요청이 만드는 문서 행. 시행일과 접근 그룹은 비운다. 묘비 행을 다시 쓸 때는 `update`가 만든
    시각을 그대로 두므로 `created_at`은 처음 만든 시각으로 남는다."""
    return Document(
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
        generation=generation,
        deleted_at=None,
        purged_at=None,
        created_at=now,
        modified_at=now,
    )


async def _create(
    transaction: Transaction, upload: _Upload, request_id: UUID, now: datetime
) -> _Recorded:
    document = _fresh_document(upload, now, generation=1)
    await transaction.documents.add(document)
    job_id = await _schedule(transaction, document, None, request_id, now)
    return _Recorded(IngestResult(IngestAction.CREATED, document.id, job_id), None)


async def _rewrite_tombstone(
    transaction: Transaction, tombstone: Document, upload: _Upload, request_id: UUID, now: datetime
) -> _Recorded:
    """정리 작업이 물리 삭제한 문서의 묘비 행을 다시 쓴다. UUID를 잇고 세대를 이어서 올린다. 묘비는
    "있었다"는 표시이지 새 문서를 막는 장치가 아니다. 묘비 행이 아직 가리키는 옛 원본은 정리 작업이
    이미 지웠을 수 있고, 지우기는 없는 원본에도 안전하므로 커밋 뒤에 한 번 더 지운다."""
    document = _fresh_document(upload, now, generation=tombstone.generation + 1)
    await transaction.documents.update(document)
    job_id = await _schedule(transaction, document, None, request_id, now)
    return _Recorded(IngestResult(IngestAction.CREATED, document.id, job_id), tombstone.blob_path)


async def _amend(
    transaction: Transaction,
    existing: Document,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
) -> _Recorded:
    if existing.purged_at is not None:
        return await _rewrite_tombstone(transaction, existing, upload, request_id, now)
    if existing.deleted_at is not None:
        return await _restore(transaction, existing, upload, request_id, now)
    if existing.content_hash != upload.content_hash:
        return await _update_content(transaction, existing, upload, request_id, now)
    refreshed = _refresh_metadata(existing, upload)
    if refreshed.group_id != existing.group_id:
        return await _update_group(transaction, existing, refreshed, upload, request_id, now)
    if await _index_failed(transaction, existing):
        return await _requeue(transaction, existing, refreshed, upload, request_id, now)
    if refreshed != existing:
        await transaction.documents.update(replace(refreshed, modified_at=now))
        if refreshed.updated_at != existing.updated_at:
            await transaction.index.update_chunk_copies(refreshed)
    return _Recorded(IngestResult(IngestAction.UNCHANGED, existing.id, None), upload.blob_key)


def _refresh_metadata(existing: Document, upload: _Upload) -> Document:
    """내용이 같은 수집이 문서 행에 반영하는 값이다. 제목, 메타데이터, 호출자가 준 갱신일, 요청의
    그룹을 쓴다. 호출자가 갱신일을 주지 않으면 갱신일은 그대로 둔다."""
    return replace(
        existing,
        group_id=upload.group_id,
        title=upload.title,
        metadata=upload.metadata,
        updated_at=existing.updated_at if upload.updated_at is None else upload.updated_at,
    )


async def _restore(
    transaction: Transaction,
    deleted: Document,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
) -> _Recorded:
    """지운 문서가 같은 키로 돌아왔다. 지운 문서는 조각이 보관 표에만 있고 색인 상태가 없어 어느
    지식베이스에서도 빠질 것이 없다. 그래서 되살린 문서를 처음부터 요청의 그룹에 든 것으로 두고
    지식베이스 행의 잠금과 조각의 복사 칸을 다룬다. 내용이 다르면 보관 조각을 지우고 갱신으로
    간다(`restored`에 작업 ID)."""
    revived = replace(deleted, deleted_at=None, group_id=upload.group_id)
    if deleted.content_hash != upload.content_hash:
        await transaction.index.delete_archived_chunks(deleted.id)
        return await _update_content(
            transaction, revived, upload, request_id, now, action=IngestAction.RESTORED
        )
    return await _restore_chunks(transaction, revived, upload, request_id, now)


async def _restore_chunks(
    transaction: Transaction,
    revived: Document,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
) -> _Recorded:
    """내용이 같은 되살림이다. 대상 판은 요청의 그룹이 든 지식베이스의 살아 있는 판이다. 만든 내용
    해시가 같은 보관 조각을 대상 판의 검색 표로 되돌리고 그 판에 `indexed`를 쓴다. 보관 조각은
    되돌렸든 아니든 모두 지운다. 되돌릴 조각이 없는 대상 판이 있으면 작업을 넣고, 그 판이 건설 중인
    판이 아니면 `pending`을 쓴다(건설 중인 판에 `pending`을 쓰면 그 문서의 작업이 끝날 때까지 판이
    전환되지 않을 수 있다. 명세 "재색인 시작" 항목). 건설 중인 판에 `indexed`를 써도 전환 검사를
    부르지 않는다. 그 판에 색인 상태가 없던 문서의 `indexed` 한 행은 전환 조건(모든 색인 상태가
    `indexed`나 `failed`)을 새로 채우지 못하고, 검사는 지식베이스 행을 `FOR UPDATE`로 올려 잠가야
    해서 같은 지식베이스의 되살림끼리 서로를 기다릴 수 있다. 조각이 하나라도 돌아오면 그 조각은 같은
    해시의 내용을 파싱해 만든 것이므로 문서 상태를 `parsed`로 쓴다(갱신이 `received`로 쓴 뒤 색인
    작업이 돌기 전에 지운 문서는 작업이 지워져 상태를 고칠 작업이 없다). 문서 행은 새 원본을
    가리키지 않아 새 원본은 커밋 뒤에 지운다."""
    document = replace(
        _refresh_metadata(revived, upload), generation=revived.generation + 1, modified_at=now
    )
    await _lock_knowledge_bases(transaction, document.group_id, document.group_id)
    versions = await live_index_versions(transaction, document.group_id)
    restored = await transaction.index.restore_archived_chunks(
        document, [version.id for version in versions]
    )
    if restored:
        document = replace(document, status=DocumentStatus.PARSED)
    await transaction.documents.update(document)
    await transaction.index.delete_archived_chunks(document.id)
    for version in versions:
        if version.id in restored:
            await transaction.index.save_state(
                _restored_state(document, version, restored[version.id], now)
            )
    unrestored = [version for version in versions if version.id not in restored]
    job_id: UUID | None = None
    if unrestored:
        for version in unrestored:
            if version.status is not IndexVersionStatus.BUILDING:
                await transaction.index.save_state(_pending_state(document, version, now))
        job_id = (await transaction.jobs.enqueue(document.id, request_id, now)).id
    return _Recorded(IngestResult(IngestAction.RESTORED, document.id, job_id), upload.blob_key)


def _restored_state(
    document: Document, version: IndexVersion, chunk_count: int, now: datetime
) -> IndexState:
    """보관 조각이 돌아온 판의 색인 상태다. 돌아온 조각이 만든 내용 해시는 문서의 것과 같다."""
    return IndexState(
        document_id=document.id,
        index_version_id=version.id,
        status=IndexStateStatus.INDEXED,
        chunk_count=chunk_count,
        built_content_hash=document.content_hash,
        error_code=None,
        updated_at=now,
    )


def _pending_state(document: Document, version: IndexVersion, now: datetime) -> IndexState:
    return IndexState(
        document_id=document.id,
        index_version_id=version.id,
        status=IndexStateStatus.PENDING,
        chunk_count=0,
        built_content_hash=None,
        error_code=None,
        updated_at=now,
    )


async def _update_content(
    transaction: Transaction,
    existing: Document,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
    *,
    action: IngestAction = IngestAction.UPDATED,
) -> _Recorded:
    """내용이 바뀐 갱신이다. 문서 행이 새 원본을 가리키고 옛 원본은 커밋 뒤에 지운다. `action`은
    지운 문서를 다른 내용으로 되살릴 때만 `restored`다."""
    document = replace(
        existing,
        group_id=upload.group_id,
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
    job_id = await _schedule(transaction, document, existing, request_id, now)
    return _Recorded(IngestResult(action, document.id, job_id), existing.blob_path)


async def _update_group(
    transaction: Transaction,
    existing: Document,
    refreshed: Document,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
) -> _Recorded:
    """내용은 같고 그룹만 바뀐 갱신이다. 파싱은 해시가 같아 건너뛰지만 대상 지식베이스가 바뀌므로
    작업을 넣는다. 문서 행은 새 원본을 가리키지 않아 새 원본은 커밋 뒤에 지운다."""
    document = replace(refreshed, generation=existing.generation + 1, modified_at=now)
    await transaction.documents.update(document)
    job_id = await _schedule(transaction, document, existing, request_id, now)
    return _Recorded(IngestResult(IngestAction.UPDATED, document.id, job_id), upload.blob_key)


async def _requeue(
    transaction: Transaction,
    existing: Document,
    refreshed: Document,
    upload: _Upload,
    request_id: UUID,
    now: datetime,
) -> _Recorded:
    """내용과 그룹이 같지만 앞선 색인이 실패한 문서를 다시 색인한다. 세대를 올리고 작업을 넣는다.
    문서 상태는 작업이 정한다. 문서 행은 새 원본을 가리키지 않아 새 원본은 커밋 뒤에 지운다."""
    document = replace(refreshed, generation=existing.generation + 1, modified_at=now)
    await transaction.documents.update(document)
    job_id = await _schedule(transaction, document, existing, request_id, now)
    return _Recorded(IngestResult(IngestAction.REQUEUED, document.id, job_id), upload.blob_key)


async def _index_failed(transaction: Transaction, document: Document) -> bool:
    """앞선 색인이 실패했는가. 문서 상태가 `failed`이거나, 문서가 드는 지식베이스의 살아 있는 판
    가운데 색인 상태가 `failed`인 판이 있다. 문서 행을 잠근 채라 작업 단위가 문서 행을 잠그고
    쓰는 색인 상태(작업의 결과)는 이 사이에 바뀌지 않는다."""
    if document.status is DocumentStatus.FAILED:
        return True
    for version in await live_index_versions(transaction, document.group_id):
        state = await transaction.index.get_state(document.id, version.id)
        if state is not None and state.status is IndexStateStatus.FAILED:
            return True
    return False


async def _schedule(
    transaction: Transaction,
    document: Document,
    previous: Document | None,
    request_id: UUID,
    now: datetime,
) -> UUID:
    """문서 행을 쓴 바로 뒤에 한다. 지식베이스 행을 잠근 다음(잠금 순서는 문서 행, 지식베이스 행,
    작업 행이다) 그룹이 바뀌어 문서가 빠지는 지식베이스에서 문서를 걷고, 그룹이나 갱신일이
    바뀌었으면 조각의 복사 칸을 고치고, 작업을 넣는다. `previous`는 고치기 전의 문서이고 새 문서면
    `None`이다."""
    previous_group_id = document.group_id if previous is None else previous.group_id
    departing = await _lock_knowledge_bases(transaction, previous_group_id, document.group_id)
    await _leave_knowledge_bases(transaction, document, departing)
    if previous is not None and (
        previous.group_id != document.group_id or previous.updated_at != document.updated_at
    ):
        await transaction.index.update_chunk_copies(document)
    job = await transaction.jobs.enqueue(document.id, request_id, now)
    return job.id


async def _lock_knowledge_bases(
    transaction: Transaction, previous_group_id: UUID, group_id: UUID
) -> list[KnowledgeBase]:
    """문서가 드는 지식베이스는 `FOR SHARE`로, 그룹이 바뀌어 문서가 빠지는 지식베이스는 `FOR
    UPDATE`로 잠그고 빠지는 지식베이스를 낸다. 둘을 합쳐 ID 순으로 하나씩 잠가 다른 수집과 교착하지
    않는다. 잠금이 풀리길 기다리는 일은 있다."""
    catalog = transaction.catalog
    containing = await catalog.list_knowledge_bases_of_group(group_id)
    departing: list[KnowledgeBase] = []
    if previous_group_id != group_id:
        staying = {knowledge_base.id for knowledge_base in containing}
        departing = [
            knowledge_base
            for knowledge_base in await catalog.list_knowledge_bases_of_group(previous_group_id)
            if knowledge_base.id not in staying
        ]
    modes = {knowledge_base.id: LockMode.SHARE for knowledge_base in containing}
    modes.update({knowledge_base.id: LockMode.UPDATE for knowledge_base in departing})
    for knowledge_base_id in sorted(modes):
        await catalog.lock_knowledge_bases([knowledge_base_id], modes[knowledge_base_id])
    return departing


async def _leave_knowledge_bases(
    transaction: Transaction, document: Document, departing: Sequence[KnowledgeBase]
) -> None:
    """빠지는 지식베이스의 살아 있는 판에서 문서의 조각과 색인 상태를 지운다. 건설 중인 판이면 그
    색인 상태가 사라져 판이 전환될 수 있으므로 전환 검사를 부른다."""
    for knowledge_base in departing:
        for version in await transaction.catalog.list_live_index_versions(knowledge_base.id):
            await transaction.index.delete_chunks(document.id, version.id)
            await transaction.index.delete_state(document.id, version.id)
            if version.status is IndexVersionStatus.BUILDING:
                await check_version_switch(transaction, version)


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
