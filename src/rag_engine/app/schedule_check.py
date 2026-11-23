"""일정 확인 한 번(source-sync 명세 "일정과 일정 확인", 스토리 10, 11, 12, 13, 21, 22).

일정 확인 한 번은 작업 단위 하나다. 다음 실행 시각이 지났고 일시 중지도 지움 표시도 없는 원천의 행을
`FOR NO KEY UPDATE SKIP LOCKED`로 잠근다. 다른 연결이 잡은 행은 기다리지 않고 건너뛰므로 작업자를
여럿 띄워도 같은 일정이 한 번만 시작된다(프로브 `schedule-once`의 A2). `FOR UPDATE`가 아니라 키를
건드리지 않는 잠금인 까닭은, 지금 동기화가 작업 행을 넣을 때 외래 키 확인이 거는 `FOR KEY SHARE`를
막지 않아 두 요청이 서로를 기다리는 교착을 피하기 위해서다. 잡은 원천마다 동기화
기록(`trigger`가 `schedule`)과 동기화 작업을 넣고 다음 실행 시각을 지금 다음의 시각으로 옮긴 뒤 한
번에 커밋한다. 놓친 회차가 여럿이어도 한 번만 넣는다.

같은 원천의 동기화가 대기 중이거나 실행 중이면 작업을 넣지 않고 기록을 `not_started`로 남긴다(실패
사유 `sync_in_progress`, 시작 시각은 비우고 끝 시각은 만든 시각과 같다). 일정이 넣은 작업에는 새
요청 ID를 붙이고, 일정이 시작한 동기화에는 "빈 목록도 반영"과 "모두 다시 읽기"가 없다. 어느 원천의
일정이 계산하지 못하는 글이면(저장할 때 확인한 글이라 일어나지 않는 일이다) 이 작업 단위 전체를
되돌린다. 로그와 다시 하기는 부르는 쪽(작업자)의 몫이다.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rag_engine.domain.entities import (
    JobKind,
    Source,
    SyncRecord,
    SyncRecordStatus,
    SyncTrigger,
)
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import ScheduleCalculator, Transaction, UnitOfWork


@dataclass(frozen=True, slots=True)
class ScheduledSync:
    """일정 확인이 한 원천에서 한 일. `job_id`가 없으면 앞 동기화가 돌고 있어 시작하지 않은
    회차다."""

    source: str
    sync_record_id: UUID
    job_id: UUID | None
    request_id: UUID

    @property
    def started(self) -> bool:
        return self.job_id is not None


async def check_schedules(
    unit_of_work: UnitOfWork, calculator: ScheduleCalculator, *, now: datetime
) -> list[ScheduledSync]:
    """`now`에 시각이 지난 원천마다 동기화를 한 번 시작시키고, 한 일을 원천 순서대로 낸다."""
    async with unit_of_work.begin() as transaction:
        handled: list[ScheduledSync] = []
        for source in await transaction.catalog.lock_due_sources(now):
            result = await _start(transaction, calculator, source, now)
            if result is not None:
                handled.append(result)
        return handled


async def _start(
    transaction: Transaction, calculator: ScheduleCalculator, source: Source, now: datetime
) -> ScheduledSync | None:
    if source.schedule is None:
        # 일정이 없는데 시각만 남은 원천이다. 일정을 없앨 때 시각도 함께 비우므로 보통은 없다.
        await transaction.catalog.set_next_run_at(source.id, None)
        return None
    following = calculator.next_run(source.schedule, now)
    request_id = new_id()
    job = await transaction.jobs.enqueue_source_job(
        JobKind.SYNC_SOURCE, source.id, {}, request_id, now
    )
    record = SyncRecord(
        id=new_id(),
        source_id=source.id,
        job_id=None if job is None else job.id,
        trigger=SyncTrigger.SCHEDULE,
        options={},
        status=SyncRecordStatus.NOT_STARTED if job is None else SyncRecordStatus.QUEUED,
        failure_code=ErrorCode.SYNC_IN_PROGRESS.value if job is None else None,
        created_at=now,
        started_at=None,
        finished_at=now if job is None else None,
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
    await transaction.catalog.set_next_run_at(source.id, following)
    return ScheduledSync(source.name, record.id, record.job_id, request_id)
