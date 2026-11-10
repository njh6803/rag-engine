"""`JobQueue` 어댑터. 작업 표의 대기열이다(명세 "수집 파이프라인과 작업", ADR 0009).

같은 문서의 대기(`queued`) 작업은 부분 유일 색인으로 하나라서, 넣는 쪽은 `INSERT … ON CONFLICT … DO
UPDATE` 한 문장으로 있는 행을 다시 쓴다. 있는지 보는 일과 넣는 일이 한 문장이어야 같은 문서에 동시에
넣어도 대기 작업이 둘이 되지 않는다. 알림(`NOTIFY rag_jobs`)은 PostgreSQL이 커밋 때 보낸다.

꺼내기, 끝내기, 다시 예약하기, 임대 연장은 이 어댑터에 아직 없다.
"""

from datetime import datetime
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

    async def get(self, job_id: UUID) -> Job | None:
        raise NotImplementedError(_NOT_YET)

    async def claim(self, worker_id: str, now: datetime, lease_seconds: float) -> Job | None:
        raise NotImplementedError(_NOT_YET)

    async def finish(self, job: Job, outcome: JobOutcome, now: datetime) -> None:
        raise NotImplementedError(_NOT_YET)

    async def reschedule(self, job: Job, run_after: datetime, error_code: ErrorCode) -> None:
        raise NotImplementedError(_NOT_YET)

    async def extend_lease(self, job: Job, leased_until: datetime) -> None:
        raise NotImplementedError(_NOT_YET)
