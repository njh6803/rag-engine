"""지금 동기화를 요청하고 동기화 기록을 보는 유스케이스(source-sync 명세 "관리 API", "동기화 기록").

요청은 한 작업 단위에서 동기화 작업을 대기열에 넣고 그 작업을 가리키는 동기화 기록(`queued`)을
만든다. 같은 원천의 동기화가 대기 중이거나 실행 중이면 작업이 들어가지 않으므로, 기록도 남기지 않고
409 `sync_in_progress`로 끝낸다(작업 단위가 롤백되어 아무것도 남지 않는다). 일시 중지한 원천도
받는다.

옵션은 켠 것만 작업과 기록의 옵션 칸에 남긴다. 둘의 뜻은 동기화를 짓는 쪽(작업자)이 붙인다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rag_engine.app.source_lookup import require_pull_source, require_source
from rag_engine.domain.entities import (
    JobKind,
    JsonValue,
    SyncRecord,
    SyncRecordStatus,
    SyncTrigger,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import UnitOfWork


@dataclass(frozen=True, slots=True)
class SyncRequested:
    """지금 동기화 요청의 결과. 기록과 작업의 식별자다."""

    sync_record_id: UUID
    job_id: UUID


def _enabled_options(*, apply_empty: bool, reread: bool) -> Mapping[str, JsonValue]:
    options: dict[str, JsonValue] = {}
    if apply_empty:
        options["apply_empty"] = True
    if reread:
        options["reread"] = True
    return options


async def request_sync(
    unit_of_work: UnitOfWork,
    source_name: str,
    *,
    apply_empty: bool,
    reread: bool,
    request_id: UUID,
    now: datetime,
) -> SyncRequested:
    options = _enabled_options(apply_empty=apply_empty, reread=reread)
    async with unit_of_work.begin() as transaction:
        source = await require_pull_source(transaction, source_name)
        job = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, options, request_id, now
        )
        if job is None:
            raise RequestError(ErrorCode.SYNC_IN_PROGRESS, "그 원천의 동기화가 이미 진행 중이다")
        record = SyncRecord(
            id=new_id(),
            source_id=source.id,
            job_id=job.id,
            trigger=SyncTrigger.MANUAL,
            options=options,
            status=SyncRecordStatus.QUEUED,
            failure_code=None,
            created_at=now,
            started_at=None,
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
        await transaction.sync_records.add(record)
        return SyncRequested(sync_record_id=record.id, job_id=job.id)


async def list_sync_records(
    unit_of_work: UnitOfWork, source_name: str, *, limit: int, after: UUID | None
) -> list[SyncRecord]:
    """그 원천의 동기화 기록을 최근 것부터 낸다. 지운 원천의 기록도 본다."""
    async with unit_of_work.begin() as transaction:
        source = await require_source(transaction, source_name)
        return await transaction.sync_records.list_for_source(source.id, limit, after)


async def get_sync_record(
    unit_of_work: UnitOfWork, source_name: str, record_id: UUID
) -> SyncRecord:
    """그 원천의 동기화 기록 하나. 없거나 다른 원천의 기록이면 404 `sync_record_not_found`다."""
    async with unit_of_work.begin() as transaction:
        source = await require_source(transaction, source_name)
        record = await transaction.sync_records.get(record_id)
        if record is None or record.source_id != source.id:
            raise RequestError(ErrorCode.SYNC_RECORD_NOT_FOUND, "그 동기화 기록이 없다")
        return record
