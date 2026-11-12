"""`JobQueue` 어댑터. 작업 표의 대기열이다(명세 "수집 파이프라인과 작업", ADR 0009).

같은 문서의 대기(`queued`) 작업은 부분 유일 색인으로 하나라서, 넣는 쪽은 `INSERT … ON CONFLICT … DO
UPDATE` 한 문장으로 있는 행을 다시 쓴다. 있는지 보는 일과 넣는 일이 한 문장이어야 같은 문서에 동시에
넣어도 대기 작업이 둘이 되지 않는다. 알림(`NOTIFY rag_jobs`)은 PostgreSQL이 커밋 때 보낸다.

임대 연장(13)은 이 어댑터에 아직 없다.
"""

from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from rag_engine.adapters.postgres import tables
from rag_engine.domain.entities import Job, JobKind, JobStatus
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome

NOTIFY_CHANNEL: Final = "rag_jobs"
_NOT_YET: Final = "이 어댑터에 아직 없다"
# `ON CONFLICT`의 색인 추론 술어는 부분 색인의 술어와 글자가 같아야 한다. 값을 바인드 파라미터로
# 보내면 psycopg가 같은 문장을 다섯 번 돌린 뒤 서버에 준비시키고, 일반 계획은 파라미터를 상수로
# 접지 못해 색인을 찾지 못한다(`42P10`). 그래서 리터럴로 렌더링한다.
_QUEUED: Final[sa.ColumnClause[str]] = sa.literal_column(
    f"'{JobStatus.QUEUED.value}'", type_=sa.String()
)


def _job(row: sa.RowMapping) -> Job:
    error_code: str | None = row["last_error_code"]
    return Job(
        id=row["id"],
        kind=JobKind(row["kind"]),
        document_id=row["document_id"],
        status=JobStatus(row["status"]),
        attempts=row["attempts"],
        run_after=row["run_after"],
        leased_until=row["leased_until"],
        worker_id=row["worker_id"],
        raised_generation=row["raised_generation"],
        last_error_code=None if error_code is None else ErrorCode(error_code),
        request_id=row["request_id"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _attempt_of(job: Job) -> list[sa.ColumnElement[bool]]:
    """이 시도가 쓴 작업 행만 고르는 조건. 임대가 끝나 다른 작업자가 가져간 작업(작업자 ID나 시도
    횟수가 다르다)은 고르지 않는다. 지식베이스 행을 잠금 순서에 맞게 작업 행 앞에서 잠그는 것은
    부르는 쪽의 몫이다(다시 예약하기와 재시도 소진은 `app/job_failure.py`가 잠근다. 색인 작업 자신의
    작업 단위가 잠그는 일은 14가 한다)."""
    return [
        tables.jobs.c.id == job.id,
        tables.jobs.c.worker_id == job.worker_id,
        tables.jobs.c.attempts == job.attempts,
    ]


class PostgresJobQueue:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def enqueue(self, document_id: UUID, request_id: UUID, now: datetime) -> Job:
        insertion = insert(tables.jobs).values(
            id=new_id(),
            kind=JobKind.INDEX_DOCUMENT.value,
            document_id=document_id,
            status=JobStatus.QUEUED.value,
            run_after=now,
            request_id=request_id,
            created_at=now,
        )
        statement = insertion.on_conflict_do_update(
            index_elements=[tables.jobs.c.document_id],
            index_where=tables.jobs.c.status == _QUEUED,
            set_={"run_after": insertion.excluded.run_after, "request_id": request_id},
        ).returning(tables.jobs)
        row = (await self._connection.execute(statement)).mappings().one()
        await self._connection.execute(sa.select(sa.func.pg_notify(NOTIFY_CHANNEL, "")))
        return _job(row)

    async def delete_queued(self, document_id: UUID) -> None:
        await self._connection.execute(
            sa.delete(tables.jobs).where(
                tables.jobs.c.document_id == document_id,
                tables.jobs.c.status == JobStatus.QUEUED.value,
            )
        )

    async def get(self, job_id: UUID) -> Job | None:
        row = (
            (
                await self._connection.execute(
                    sa.select(tables.jobs).where(tables.jobs.c.id == job_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _job(row)

    async def list_jobs(
        self, status: JobStatus | None, limit: int, after: UUID | None
    ) -> list[Job]:
        query = sa.select(tables.jobs).order_by(tables.jobs.c.id.desc()).limit(limit)
        if status is not None:
            query = query.where(tables.jobs.c.status == status.value)
        if after is not None:
            query = query.where(tables.jobs.c.id < after)
        rows = (await self._connection.execute(query)).mappings().all()
        return [_job(row) for row in rows]

    async def has_active_job(self, document_id: UUID) -> bool:
        active = sa.select(tables.jobs.c.id).where(
            tables.jobs.c.document_id == document_id,
            tables.jobs.c.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
        return bool(await self._connection.scalar(sa.select(active.exists())))

    async def claim(self, worker_id: str, now: datetime, lease_seconds: float) -> Job | None:
        jobs = tables.jobs
        picked = (
            sa.select(jobs.c.id)
            .where(
                sa.or_(
                    sa.and_(jobs.c.status == JobStatus.QUEUED.value, jobs.c.run_after <= now),
                    sa.and_(jobs.c.status == JobStatus.RUNNING.value, jobs.c.leased_until <= now),
                )
            )
            .order_by(jobs.c.run_after, jobs.c.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .cte("picked")
        )
        statement = (
            sa.update(jobs)
            .where(jobs.c.id == picked.c.id)
            .values(
                status=JobStatus.RUNNING.value,
                attempts=jobs.c.attempts + 1,
                raised_generation=None,
                worker_id=worker_id,
                leased_until=now + timedelta(seconds=lease_seconds),
                started_at=sa.func.coalesce(jobs.c.started_at, now),
            )
            .returning(jobs)
        )
        row = (await self._connection.execute(statement)).mappings().one_or_none()
        return None if row is None else _job(row)

    async def hold_attempt(self, job: Job) -> bool:
        held = await self._connection.execute(
            sa.select(tables.jobs.c.id).where(*_attempt_of(job)).with_for_update()
        )
        return held.first() is not None

    async def record_raised_generation(self, job: Job, generation: int) -> None:
        await self._connection.execute(
            sa.update(tables.jobs).where(*_attempt_of(job)).values(raised_generation=generation)
        )

    async def finish(self, job: Job, outcome: JobOutcome, now: datetime) -> None:
        await self._connection.execute(
            sa.update(tables.jobs)
            .where(*_attempt_of(job))
            .values(
                status=outcome.status.value,
                last_error_code=None if outcome.error_code is None else outcome.error_code.value,
                finished_at=now,
                leased_until=None,
            )
        )

    async def reschedule(self, job: Job, run_after: datetime, error_code: ErrorCode) -> bool:
        jobs = tables.jobs
        other = jobs.alias("other")
        no_other_queued = ~sa.exists().where(
            other.c.document_id == jobs.c.document_id,
            other.c.status == JobStatus.QUEUED.value,
            other.c.id != jobs.c.id,
        )
        rescheduled = await self._connection.execute(
            sa.update(jobs)
            .where(*_attempt_of(job), no_other_queued)
            .values(
                status=JobStatus.QUEUED.value,
                run_after=run_after,
                last_error_code=error_code.value,
                leased_until=None,
                worker_id=None,
                raised_generation=None,
            )
            .returning(jobs.c.id)
        )
        return rescheduled.first() is not None

    async def has_other_job_from_start(self, document_id: UUID, excluding_job_id: UUID) -> bool:
        jobs = tables.jobs
        found = await self._connection.execute(
            sa.select(jobs.c.id)
            .where(
                jobs.c.document_id == document_id,
                jobs.c.id != excluding_job_id,
                sa.or_(
                    jobs.c.status == JobStatus.QUEUED.value,
                    sa.and_(
                        jobs.c.status == JobStatus.RUNNING.value,
                        jobs.c.raised_generation.is_(None),
                    ),
                ),
            )
            .limit(1)
        )
        return found.first() is not None

    async def extend_lease(self, job: Job, leased_until: datetime) -> None:
        raise NotImplementedError(_NOT_YET)
