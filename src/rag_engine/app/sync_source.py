"""`sync_source` 작업의 유스케이스(source-sync 명세 "동기화의 차례", "수집 정책", "동기화 기록").

가져오는 원천 하나의 문서를 원천의 목록에 맞춘다. 순서는 다음과 같다.

1. 동기화 기록과 원천을 읽는다. 원천에 지움 표시가 서 있으면 `source_deleted`로 끝낸다. 커넥터를
   만들지 못하면 `connector_unavailable`로 끝낸다. 만들었으면 기록을 `running`으로 쓴다.
2. 목록을 끝까지 받는다. 받는 도중의 예외는 아무것도 넣지 않은 채 실패로 끝난다.
3. 받은 목록에 수집 정책(제외 패턴, 형식, 크기)을 적용해 후보를 만든다. 걸린 파일은 사유별 개수로만
   남는다.
4. 후보마다 같은 (원천, 키)의 문서와 대 본다. 변경 확인값이 같으면 읽지 않고, 아니면 읽어서 내용
   해시를 비교한다. "모두 다시 읽기"를 켠 동기화는 확인값이 같아도 읽는다. 새 문서와 내용이 바뀐
   문서는 수집 유스케이스로 넣고, 내용이 같은 문서는 변경 확인값만 새 값으로 적는다. 내용이 같은
   문서 가운데 색인이 실패했거나 건너뛴 것은 색인 작업을 다시 넣는다. 보통 동기화는 일시 실패와
   `worker_lost`, `source_changed`로 실패한 문서만 다시 넣고, "모두 다시 읽기"는 영구 실패와 건너뜀
   문서도 다시 넣는다. 읽다가 `too_large`가 나온 파일은 후보에서 빠진다.
5. 삭제를 반영한다. 먼저 빈 목록 판정을 한다. 읽다가 후보에서 빠진 파일까지 뺀 뒤에도 후보가 0건이고
   그 원천에 지워지지 않은 문서가 있으면 아무것도 지우지 않고 실패로 끝난다. 지나면 그 원천의
   지워지지 않은 문서 가운데 후보에 키가 없는 것을 문서마다 작업 단위 하나에서 임시 삭제한다. 넣은
   문서의 색인이 끝나기를 기다리지 않는다.
6. 기록을 끝낸 상태로 쓴다. 실패로 끝나도 그때까지 센 개수를 남긴다.

문서를 넣거나 지우는 작업 단위마다 맨 먼저 원천 행을 공유 잠금으로 잡고 지움 표시를 다시 본다.
표시가 서 있으면 그 자리에서 `source_deleted`로 끝나고 그때까지 센 개수를 남긴다. 목록을 받는 중이나
파일 하나를 읽는 중에는 이 자리에 닿지 못하므로, 작업자가 작업 담당 기록의 기한을 늘릴 때도 표시를
본다. 거기서 본 동기화는 처리를 취소하고 `close_after_source_deleted`로 기록을 `failed`와
`source_deleted`로 닫는다. 작업자가 센 개수의 그릇(`SyncCounts`)을 `sync_source`와
`close_after_source_deleted`에 함께 넘기므로 이 길도 취소하기 전까지 센 개수를 남긴다.

문서를 쓰는 작업 단위마다 마지막에 작업 행 조건을 본다. 어긋나면 `AttemptLostError`가 그대로
올라가 그 시도를 버린다. 원천 쪽의 까닭으로 실패한 동기화는 이 모듈이 기록과 결과를 정해 돌려주고
(재시도 없이 끝난다), 데이터베이스가 끊긴 것 같은 일시 실패는 `TransientFailure`로 올라가 작업자가
색인 작업과 같은 규칙으로 다시 예약한다. 로그 줄은 `SyncDeps.log`로 작업자에게 넘기고(이 층은
어댑터를 import하지 않는다), 줄과 기록에는 닫힌 코드와 개수만 싣는다. 문서의 키, 파일 이름, 커넥터
설정, 예외의 글은 싣지 않는다(원칙 V).
"""

import asyncio
import hashlib
import time
import unicodedata
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Final
from uuid import UUID

from rag_engine.app.delete_document import (
    delete_locked_document,
    detach_from_source_deletion,
    holds_source_deletion_mark,
)
from rag_engine.app.document_outcome import index_failure_code
from rag_engine.app.ingest import (
    IngestResult,
    PulledDocument,
    ingest_pulled_document,
    requeue_locked_document,
)
from rag_engine.app.ingest_policy import RejectReason, reject_reason
from rag_engine.app.job_attempt import hold_attempt
from rag_engine.domain.connectors import (
    ConnectorBrokenError,
    ConnectorCallBlockedError,
    ConnectorCallTimedOutError,
    ConnectorError,
    ConnectorFailureReason,
    ConnectorUnavailableError,
    FetchedItem,
    ListedItem,
    SourceReader,
)
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IngestAction,
    Job,
    JobStatus,
    JsonValue,
    SkipReason,
    Source,
    SyncRecord,
    SyncRecordStatus,
)
from rag_engine.domain.errors import TRANSIENT_FAILURE_CODES, ErrorCode, RequestError
from rag_engine.domain.media_types import SUPPORTED_EXTENSIONS
from rag_engine.domain.ports import ConnectorRegistry, JobOutcome, Transaction, UnitOfWork

_MS_PER_SECOND: Final = 1000.0

# 보통 동기화가 색인 작업을 다시 넣는 실패의 코드(명세 "가져오는 원천의 문서 색인"). 일시 실패의
# 코드에, 작업자가 죽어 끝난 `worker_lost`와 목록을 받은 뒤 원천이 바뀐 `source_changed`를 더했다.
# 이 집합에 없는 실패(`parse_failed` 같은 것)는 같은 파일로 다시 해도 같은 결과가 나오기 쉬워
# "모두 다시 읽기"만 다시 넣는다. `source_changed`는 영구 실패 코드이지만 원천이 되돌아오면 풀리므로
# 여기 든다.
_RETRIED_CODES: Final = TRANSIENT_FAILURE_CODES | {ErrorCode.WORKER_LOST, ErrorCode.SOURCE_CHANGED}

type LogValue = str | int | float | bool | None


class SyncLogLevel(StrEnum):
    """동기화가 내는 로그 줄의 수준. 닫힌 값이고 작업자가 로그 수준으로 옮긴다."""

    INFO = "info"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class SyncLogLine:
    """작업자가 로그로 옮길 한 줄."""

    event: str
    request_id: UUID
    level: SyncLogLevel
    duration_ms: float | None
    fields: Mapping[str, LogValue]


@dataclass(frozen=True, slots=True)
class SyncDeps:
    """동기화가 부르는 포트와 값. `max_upload_bytes`는 수집 API와 같은 파일 크기 상한이다."""

    unit_of_work: UnitOfWork
    connectors: ConnectorRegistry
    source_read_timeout_seconds: float
    max_upload_bytes: int
    now: Callable[[], datetime]
    log: Callable[[SyncLogLine], None]


class SyncFailure(Exception):
    """동기화가 원천 쪽의 까닭으로 실패했다. 닫힌 코드만 든다(예외의 글을 담지 않는다)."""

    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(slots=True)
class SyncCounts:
    """동기화가 파일과 문서를 본 순간의 분류. 기록의 개수 칸이 된다."""

    listed: int | None = None
    added: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    skipped: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    not_accepted: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    failed: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    # 후보였다가 읽는 도중 수집 정책에 걸려(`too_large`) 후보에서 빠진 키. 삭제 반영이 이 키의
    # 문서도 지운다.
    withdrawn: set[str] = field(default_factory=lambda: set[str]())

    def reject(self, reason: RejectReason) -> None:
        self.not_accepted[reason.value] = self.not_accepted.get(reason.value, 0) + 1

    def reject_on_read(self, key: str) -> None:
        """읽다가 크기 상한에 걸린 파일을 정책에 걸린 파일로 세고 후보에서 뺀다."""
        self.reject(RejectReason.TOO_LARGE)
        self.withdrawn.add(key)

    def fail(self, code: ErrorCode) -> None:
        self.failed[code.value] = self.failed.get(code.value, 0) + 1

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def as_log_fields(self) -> dict[str, LogValue]:
        """로그 칸. 사유별 개수는 `사유=개수`를 쉼표로 이은 글이다."""
        return {
            "listed": self.listed,
            "added": self.added,
            "updated": self.updated,
            "deleted": self.deleted,
            "unchanged": self.unchanged,
            "skipped": _flatten(self.skipped),
            "not_accepted": _flatten(self.not_accepted),
            "failed": _flatten(self.failed),
        }


def _flatten(counts: Mapping[str, int]) -> str:
    return ",".join(f"{reason}={number}" for reason, number in sorted(counts.items()))


async def sync_source(deps: SyncDeps, job: Job, counts: SyncCounts | None = None) -> JobOutcome:
    """동기화 작업 하나를 끝까지 돌린다. 원천 쪽의 실패는 기록을 `failed`로 닫고 그 코드의 실패로,
    아니면 기록을 `succeeded`로 닫고 성공으로 낸다. `counts`는 작업자가 처리를 취소하고 기록을 닫을
    때(`close_after_source_deleted`) 그때까지 센 개수를 읽으려고 넘기는 그릇이다."""
    started = time.perf_counter()
    async with deps.unit_of_work.begin() as transaction:
        record = await transaction.sync_records.get_by_job(job.id)
        source = await transaction.catalog.get_source_by_id(job.target_source_id)
    if record is None or source is None:
        raise RuntimeError("동기화 작업이 가리키는 기록이나 원천이 없다")
    deps.log(
        SyncLogLine(
            event="sync_started",
            request_id=job.request_id,
            level=SyncLogLevel.INFO,
            duration_ms=None,
            fields={
                "source": source.name,
                "sync_record_id": str(record.id),
                "trigger": record.trigger.value,
            },
        )
    )
    counts = SyncCounts() if counts is None else counts
    code: ErrorCode | None = None
    try:
        await _sync(deps, job, source, counts)
    except SyncFailure as failure:
        code = failure.code
    await _close(deps, job, counts, code)
    deps.log(
        SyncLogLine(
            event="sync_finished",
            request_id=job.request_id,
            level=SyncLogLevel.INFO if code is None else SyncLogLevel.WARNING,
            duration_ms=(time.perf_counter() - started) * _MS_PER_SECOND,
            fields={
                "source": source.name,
                "sync_record_id": str(record.id),
                "result": "succeeded" if code is None else "failed",
                "failure_code": None if code is None else code.value,
                **counts.as_log_fields(),
            },
        )
    )
    if code is None:
        return JobOutcome(JobStatus.SUCCEEDED, None)
    return JobOutcome(JobStatus.FAILED, code)


async def _hold_live_source(transaction: Transaction, job: Job) -> None:
    """문서를 넣거나 지우는 작업 단위가 맨 먼저 부른다. 원천 행을 공유 잠금으로 잡고 지움 표시를
    다시 본다. 표시가 서 있으면 `source_deleted`로 끝난다(재시도 없음)."""
    source = await transaction.catalog.lock_source_shared(job.target_source_id)
    if source is None or source.deleted_at is not None:
        raise SyncFailure(ErrorCode.SOURCE_DELETED)


async def close_after_source_deleted(deps: SyncDeps, job: Job, counts: SyncCounts) -> JobOutcome:
    """작업 담당 기록의 기한을 늘리는 쪽이 지움 표시를 봐서 처리를 멈춘 동기화를 마무리한다. 그
    시도를 버리지 않고 기록을 `failed`와 `source_deleted`로 닫고, 취소하기 전까지 센
    개수(`counts`)를 남긴다. 그때까지 넣은 문서와 지운 문서는 그대로 두고 남은 삭제는 반영하지
    않는다."""
    await _close(deps, job, counts, ErrorCode.SOURCE_DELETED)
    return JobOutcome(JobStatus.FAILED, ErrorCode.SOURCE_DELETED)


async def _sync(deps: SyncDeps, job: Job, source: Source, counts: SyncCounts) -> None:
    if source.deleted_at is not None:
        raise SyncFailure(ErrorCode.SOURCE_DELETED)
    reader = _open(deps, source)
    await _mark_running(deps, job)
    items = await _list(reader)
    counts.listed = len(items)
    candidates = _candidates(deps, source, items, counts)
    for item in candidates.values():
        await _reconcile(deps, job, source, reader, item, counts)
    kept = candidates.keys() - counts.withdrawn
    await _guard_empty_list(deps, job, source, counts, kept)
    await _apply_deletions(deps, job, source, kept, counts)


def _open(deps: SyncDeps, source: Source) -> SourceReader:
    """원천의 커넥터를 만들어 읽는 길을 연다. 만들지 못하면(설치되지 않았다, 버전이 맞지 않는다,
    저장해 둔 설정을 받지 않는다) `connector_unavailable`이다."""
    if source.connector is None or source.config is None:
        raise RuntimeError("가져오는 원천이 아니다")
    try:
        return deps.connectors.open_reader(
            source.connector,
            source.config,
            source=source.name,
            timeout_seconds=deps.source_read_timeout_seconds,
        )
    except (ConnectorUnavailableError, ConnectorError):
        raise SyncFailure(ErrorCode.CONNECTOR_UNAVAILABLE) from None


async def _mark_running(deps: SyncDeps, job: Job) -> None:
    """기록을 `running`으로 쓰고 개수를 비운다. 작업자가 죽어 다른 작업자가 처음부터 다시 돌 때도
    개수는 마지막 시도가 본 것이다."""
    async with deps.unit_of_work.begin() as transaction:
        await _hold_live_source(transaction, job)
        record = await _record_of(transaction, job)
        await transaction.sync_records.update(
            replace(
                record,
                status=SyncRecordStatus.RUNNING,
                failure_code=None,
                started_at=deps.now(),
                finished_at=None,
                listed=None,
                added=0,
                updated=0,
                deleted=0,
                unchanged=0,
                skipped={},
                not_accepted={},
                failed={},
            )
        )
        await hold_attempt(transaction, job)


async def _record_of(transaction: Transaction, job: Job) -> SyncRecord:
    record = await transaction.sync_records.get_by_job(job.id)
    if record is None:
        raise RuntimeError("동기화 작업의 기록이 없다")
    return record


def _failure_of(error: Exception) -> SyncFailure:
    """커넥터를 부르다 난 예외를 동기화의 실패 코드로 옮긴다. 예외의 글은 쓰지 않는다."""
    if isinstance(error, ConnectorError):
        if error.reason is ConnectorFailureReason.UNREADABLE:
            return SyncFailure(ErrorCode.SOURCE_UNREADABLE)
        if error.reason is ConnectorFailureReason.REJECTED:
            return SyncFailure(ErrorCode.SOURCE_PATH_REJECTED)
        return SyncFailure(ErrorCode.CONNECTOR_ERROR)
    if isinstance(error, ConnectorCallTimedOutError | ConnectorCallBlockedError):
        return SyncFailure(ErrorCode.SOURCE_UNREADABLE)
    return SyncFailure(ErrorCode.CONNECTOR_ERROR)


_READER_ERRORS: Final = (
    ConnectorError,
    ConnectorCallTimedOutError,
    ConnectorCallBlockedError,
    ConnectorBrokenError,
)


async def _list(reader: SourceReader) -> dict[str, ListedItem]:
    """목록을 끝까지 받는다. 같은 키를 두 번 내면 `connector_error`다."""
    items: dict[str, ListedItem] = {}
    try:
        async for item in reader.list():
            if item.key in items:
                raise SyncFailure(ErrorCode.CONNECTOR_ERROR)
            items[item.key] = item
    except _READER_ERRORS as error:
        raise _failure_of(error) from None
    return items


def _candidates(
    deps: SyncDeps, source: Source, items: Mapping[str, ListedItem], counts: SyncCounts
) -> dict[str, ListedItem]:
    """수집 정책에 걸리지 않은 항목을 키로 묶어 낸다. 걸린 파일은 처음 걸린 사유 하나로 센다."""
    candidates: dict[str, ListedItem] = {}
    for item in items.values():
        reason = reject_reason(
            item.key,
            item.size_bytes,
            exclude_patterns=source.exclude_patterns,
            max_bytes=deps.max_upload_bytes,
        )
        if reason is None:
            candidates[item.key] = item
        else:
            counts.reject(reason)
    return candidates


async def _guard_empty_list(
    deps: SyncDeps, job: Job, source: Source, counts: SyncCounts, kept: Collection[str]
) -> None:
    """후보가 하나도 남지 않았는데 그 원천에 지워지지 않은 문서가 있으면 삭제를 반영하지 않고
    동기화를 실패로 끝낸다(명세 "동기화의 차례"의 빈 목록 판정). 폴더가 안 붙은 자리를 빈 폴더로
    읽어 문서를 모두 지우는 사고를 막는다. 커넥터가 낸 항목이 0건이면 `source_unreadable`이고 항목은
    있는데 모두 걸렸으면 `nothing_accepted`다. "빈 목록도 반영"을 켠 동기화는 목록을 끝까지 받은
    뒤이므로(받는 도중의 실패는 이 자리에 닿기 전에 끝난다) 지나간다."""
    if kept or _applies_empty(job):
        return
    async with deps.unit_of_work.begin() as transaction:
        if not await transaction.documents.has_documents_held_by_source(source.id):
            return
    raise SyncFailure(
        ErrorCode.SOURCE_UNREADABLE if counts.listed == 0 else ErrorCode.NOTHING_ACCEPTED
    )


def _applies_empty(job: Job) -> bool:
    """지금 동기화가 "빈 목록도 반영"을 켠 요청인가."""
    return job.options.get("apply_empty") is True


async def _held_keys(deps: SyncDeps, source: Source) -> dict[str, UUID]:
    """그 원천의, 지워지지 않은 문서와 원천과 함께 지워졌다는 표시가 남은 문서(원천 복구
    작업이 아직 복구하지 않았다)의 키마다 문서 ID."""
    async with deps.unit_of_work.begin() as transaction:
        return await transaction.documents.list_held_keys_of_source(source.id)


async def _apply_deletions(
    deps: SyncDeps, job: Job, source: Source, kept: Collection[str], counts: SyncCounts
) -> None:
    """후보에 키가 없는 문서를 문서마다 작업 단위 하나에서 임시 삭제한다. 읽지 못해 실패로 센
    파일은 후보에 있으므로 지우지 않고, 읽다가 `too_large`가 난 파일은 후보에서 빠졌으므로 그 키의
    문서를 지운다. 복구한 원천의 문서를 복구하는 작업이 아직 끝나지 않았으면 표시가 남은 문서도
    대상이다. 원천 폴더에 파일이 없는 그 문서는 복구하지 않고 따로 지운 문서로 만든다. 넣은 문서의
    색인이 끝나기를 기다리지 않는다."""
    for key, document_id in (await _held_keys(deps, source)).items():
        if key not in kept:
            await _delete_one(deps, job, document_id, counts)


async def _delete_one(deps: SyncDeps, job: Job, document_id: UUID, counts: SyncCounts) -> None:
    """문서 하나를 지운다. 잠그고 보니 이미 지워졌으면 아무것도 하지 않고 세지도 않는다. 원천과
    함께 지워졌다는 표시가 남은 문서는 표시를 걷어 따로 지운 문서로 만들고 지운 것으로 센다. 잠금
    순서는 문서 행, 지식베이스 행, 작업 행이다."""
    async with deps.unit_of_work.begin() as transaction:
        await _hold_live_source(transaction, job)
        document = await transaction.documents.lock(document_id)
        if document is not None and _is_live(document):
            await delete_locked_document(transaction, document, deps.now())
            counts.deleted += 1
        elif document is not None and holds_source_deletion_mark(document):
            await detach_from_source_deletion(transaction, document, deps.now())
            counts.deleted += 1
        await hold_attempt(transaction, job)


def _rereads(job: Job) -> bool:
    """지금 동기화가 "모두 다시 읽기"를 켠 요청인가."""
    return job.options.get("reread") is True


async def _reconcile(
    deps: SyncDeps,
    job: Job,
    source: Source,
    reader: SourceReader,
    item: ListedItem,
    counts: SyncCounts,
) -> None:
    """후보 하나를 문서와 대 보고 맞춘다. 변경 확인값이 같으면 파일을 읽지 않는다. 다만 "모두 다시
    읽기"를 켠 동기화는 확인값이 같아도 읽어 내용 해시를 비교한다. 내용이 그대로인 문서는 색인이
    실패했거나 건너뛴 것을 골라 색인 작업을 다시 넣는다(`_settle_unchanged`)."""
    reread = _rereads(job)
    async with deps.unit_of_work.begin() as transaction:
        await _hold_live_source(transaction, job)
        existing = await transaction.documents.get_by_key(source.id, item.key)
        if (
            not reread
            and existing is not None
            and _is_live(existing)
            and existing.change_marker == item.change_marker
        ):
            if await _settle_unchanged(deps, job, transaction, existing, counts):
                await hold_attempt(transaction, job)
            return
    fetched = await _fetch(reader, item, counts)
    if fetched is None:
        return
    if len(fetched.data) > deps.max_upload_bytes:
        counts.reject_on_read(item.key)
        return
    content_hash = await asyncio.to_thread(lambda: hashlib.sha256(fetched.data).hexdigest())
    if existing is not None and _is_live(existing) and existing.content_hash == content_hash:
        await _refresh_marker(deps, job, existing, item, counts)
        return
    try:
        result = await ingest_pulled_document(
            deps.unit_of_work,
            PulledDocument(
                source=source,
                key=item.key,
                data=fetched.data,
                content_hash=content_hash,
                mime=SUPPORTED_EXTENSIONS[PurePosixPath(item.key).suffix.lower()],
                title=_title(item.key, fetched.metadata),
                metadata=fetched.metadata,
                updated_at=fetched.updated_at,
                change_marker=item.change_marker,
            ),
            request_id=job.request_id,
            now=deps.now(),
            holding=job,
        )
    except RequestError as error:
        if error.code is ErrorCode.SOURCE_DELETED:
            raise SyncFailure(ErrorCode.SOURCE_DELETED) from None
        raise
    _count_ingested(result, counts)


def _is_live(document: Document) -> bool:
    return document.deleted_at is None and document.purged_at is None


async def _fetch(reader: SourceReader, item: ListedItem, counts: SyncCounts) -> FetchedItem | None:
    """파일을 읽는다. 읽지 못한 파일은 실패로 세고 `None`을 낸다. 커넥터가 `too_large`로 알리면
    수집 정책에 걸린 파일로 세고 후보에서 뺀다. 한도를 넘기거나 막히면 동기화를
    `source_unreadable`로 끝낸다(남은 파일을 하나씩 실패로 세지 않는다)."""
    try:
        return await reader.fetch(item.key)
    except ConnectorError as error:
        if error.reason is ConnectorFailureReason.TOO_LARGE:
            counts.reject_on_read(item.key)
        elif error.reason is ConnectorFailureReason.REJECTED:
            counts.fail(ErrorCode.SOURCE_PATH_REJECTED)
        elif error.reason is ConnectorFailureReason.INVALID_CONFIG:
            counts.fail(ErrorCode.CONNECTOR_ERROR)
        else:
            counts.fail(ErrorCode.SOURCE_UNREADABLE)
        return None
    except ConnectorBrokenError:
        counts.fail(ErrorCode.CONNECTOR_ERROR)
        return None
    except (ConnectorCallTimedOutError, ConnectorCallBlockedError):
        raise SyncFailure(ErrorCode.SOURCE_UNREADABLE) from None


@dataclass(frozen=True, slots=True)
class _Standing:
    """내용이 그대로인 문서가 지금 놓인 상태. 건너뜀이면 그 사유, 문서나 색인이 실패로 남아 있으면
    그 오류 코드를 든다. 둘 다 비면 색인된(또는 색인을 기다리는) 문서다."""

    skip_reason: SkipReason | None
    failure: ErrorCode | None

    def retried_by_sync(self) -> bool:
        """보통 동기화가 색인 작업을 다시 넣을 상태인가. 건너뜀이 아니고, 실패 코드가 일시 실패나
        `worker_lost`나 `source_changed`(`_RETRIED_CODES`)인 문서다."""
        if self.skip_reason is not None or self.failure is None:
            return False
        return self.failure in _RETRIED_CODES

    def retried_by_reread(self) -> bool:
        """모두 다시 읽기가 색인 작업을 다시 넣을 상태인가. 건너뛰었거나 실패로 남은 문서는 사유와
        코드가 무엇이든 모두 다시 넣는다."""
        return self.skip_reason is not None or self.failure is not None

    def count(self, counts: SyncCounts) -> None:
        """건너뜀이면 사유별 `skipped`, 실패로 남아 있으면 오류 코드별 `failed`, 그 밖이면
        `unchanged`로 센다."""
        if self.skip_reason is not None:
            counts.skip(self.skip_reason.value)
        elif self.failure is not None:
            counts.fail(self.failure)
        else:
            counts.unchanged += 1


async def _standing_of(transaction: Transaction, document: Document) -> _Standing:
    if document.status is DocumentStatus.SKIPPED and document.skip_reason is not None:
        return _Standing(document.skip_reason, None)
    return _Standing(None, await index_failure_code(transaction, document))


def _is_requeued(standing: _Standing, job: Job) -> bool:
    """이 동기화가 그 상태의 문서에 색인 작업을 다시 넣는가. "모두 다시 읽기"를 켠 동기화와 보통
    동기화가 다시 넣는 상태가 다르다."""
    if _rereads(job):
        return standing.retried_by_reread()
    return standing.retried_by_sync()


async def _settle_unchanged(
    deps: SyncDeps,
    job: Job,
    transaction: Transaction,
    document: Document,
    counts: SyncCounts,
) -> bool:
    """내용이 그대로인 파일을 그 문서의 지금 상태로 세고, 다시 시도시킬 상태면 그 문서의 색인 작업을
    다시 넣는다. 다시 넣었으면 참을 낸다. 부른 쪽이 그 작업 단위의 끝에서 작업 행 조건을 본다. 다시
    넣기 전에 문서 행을 잠그고 상태를 다시 읽는다(그사이 색인이 끝났거나 문서가 지워졌을 수 있다).
    개수는 다시 넣기 전의 상태로 센다."""
    standing = await _standing_of(transaction, document)
    if not _is_requeued(standing, job):
        standing.count(counts)
        return False
    locked = await transaction.documents.lock(document.id)
    if locked is None or not _is_live(locked):
        counts.unchanged += 1
        return False
    standing = await _standing_of(transaction, locked)
    standing.count(counts)
    if not _is_requeued(standing, job):
        return False
    await requeue_locked_document(transaction, locked, request_id=job.request_id, now=deps.now())
    return True


def _title(key: str, metadata: Mapping[str, JsonValue]) -> str:
    """제목은 메타데이터의 `title`이 문자열이면 그것이고, 아니면 키의 마지막 토막에서 확장자를 뗀
    것을 NFC로 맞춘 것이다."""
    title = metadata.get("title")
    if isinstance(title, str):
        return title
    return unicodedata.normalize("NFC", PurePosixPath(key).stem)


def _count_ingested(result: IngestResult, counts: SyncCounts) -> None:
    if result.action in (IngestAction.CREATED, IngestAction.RESTORED):
        counts.added += 1
    elif result.action is IngestAction.UPDATED:
        counts.updated += 1
    else:
        counts.unchanged += 1


async def _refresh_marker(
    deps: SyncDeps,
    job: Job,
    document: Document,
    item: ListedItem,
    counts: SyncCounts,
) -> None:
    """읽어 보니 내용이 같은 문서다. 변경 확인값만 새 값으로 적고 다른 칸은 고치지 않는다(갱신일을
    고치면 조각의 복사 칸까지 다시 써야 한다). 값이 이미 같으면(모두 다시 읽기) 쓰지 않는다. 그 뒤
    색인이 실패했거나 건너뛴 문서는 색인 작업을 다시 넣는다(`_settle_unchanged`)."""
    async with deps.unit_of_work.begin() as transaction:
        await _hold_live_source(transaction, job)
        locked = await transaction.documents.lock(document.id)
        if locked is not None and _is_live(locked):
            marked = replace(locked, change_marker=item.change_marker)
            if marked != locked:
                await transaction.documents.update(marked)
            await _settle_unchanged(deps, job, transaction, marked, counts)
        else:
            counts.unchanged += 1
        await hold_attempt(transaction, job)


async def fail_record(transaction: Transaction, job: Job, code: ErrorCode, now: datetime) -> None:
    """작업이 재시도를 다 쓰거나 일시 실패로 끝났을 때 아직 끝나지 않은 동기화 기록을 그 코드의
    실패로 닫는다. 이미 끝난 기록은 건드리지 않는다."""
    record = await transaction.sync_records.get_by_job(job.id)
    if record is None or record.status not in (SyncRecordStatus.QUEUED, SyncRecordStatus.RUNNING):
        return
    await transaction.sync_records.update(
        replace(record, status=SyncRecordStatus.FAILED, failure_code=code.value, finished_at=now)
    )


async def _close(deps: SyncDeps, job: Job, counts: SyncCounts, code: ErrorCode | None) -> None:
    """기록을 끝낸 상태로 쓴다. 실패로 끝나도 그때까지 센 개수를 남긴다."""
    async with deps.unit_of_work.begin() as transaction:
        record = await _record_of(transaction, job)
        await transaction.sync_records.update(
            replace(
                record,
                status=SyncRecordStatus.SUCCEEDED if code is None else SyncRecordStatus.FAILED,
                failure_code=None if code is None else code.value,
                finished_at=deps.now(),
                listed=counts.listed,
                added=counts.added,
                updated=counts.updated,
                deleted=counts.deleted,
                unchanged=counts.unchanged,
                skipped=dict(counts.skipped),
                not_accepted=dict(counts.not_accepted),
                failed=dict(counts.failed),
            )
        )
        await hold_attempt(transaction, job)
