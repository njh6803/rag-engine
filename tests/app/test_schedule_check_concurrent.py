"""연결 여럿이 같은 시각에 일정을 확인해도 동기화 작업이 원천마다 하나만 들어간다(source-sync 티켓
10, 명세 "일정과 일정 확인", 프로브 `schedule-once`의 A2를 옮겼다).

프로브는 연결 여덟이 원천 40개의 일정을 25회차 동안 동시에 확인했고, 시각이 지난 원천을 트랜잭션
하나에서 모두 잡는 이 모양이 넣은 작업 1000건(기대 1000건)에 한 원천에 더 들어간 작업 0건이었다.
여기서는 회차를 줄여 같은 모양을 본다. 연결마다 작업 단위 하나를 열므로 연결 여덟은 실제로 동시에
일한다. 행 잠금이 없으면(프로브의 대조군) 같은 시험이 중복 작업이나 `not_started` 기록으로 빨개진다.
"""

import asyncio
from collections import Counter
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.support.schedule_sources import (
    CHECK_TIME,
    SEOUL_CALCULATOR,
    add_scheduled_source,
    set_sync_job_status,
    sync_jobs,
)

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.schedule_check import ScheduledSync, check_schedules

CONNECTIONS = 8
SOURCES = 20
ROUNDS = 5


async def _make_every_source_due(engine: AsyncEngine, round_number: int) -> None:
    """앞 회차의 동기화를 끝난 것으로 돌리고 모든 원천의 다음 실행 시각을 지난 시각으로 되돌린다."""
    await set_sync_job_status(engine, "succeeded")
    async with engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE sources SET next_run_at = :due"),
            {"due": CHECK_TIME - timedelta(minutes=1 + round_number)},
        )


async def test_연결_여덟이_같은_시각에_동시에_확인해도_원천마다_동기화_작업이_하나만_들어간다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    sources = [
        await add_scheduled_source(unit_of_work, f"source-{number:02d}", next_run_at=CHECK_TIME)
        for number in range(SOURCES)
    ]

    for round_number in range(ROUNDS):
        await _make_every_source_due(engine, round_number)
        before = len(await sync_jobs(engine))

        results: list[list[ScheduledSync]] = await asyncio.gather(
            *(
                check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)
                for _ in range(CONNECTIONS)
            )
        )

        started = [item for result in results for item in result]
        assert len(started) == SOURCES
        assert all(item.started for item in started)
        assert sorted(item.source for item in started) == sorted(source.name for source in sources)
        new_jobs = (await sync_jobs(engine))[before:]
        assert Counter(job.source_id for job in new_jobs) == {source.id: 1 for source in sources}
        assert {job.status for job in new_jobs} == {"queued"}

    async with engine.connect() as connection:
        not_started = await connection.scalar(
            sa.text("SELECT count(*) FROM sync_records WHERE status = 'not_started'")
        )
        recorded = await connection.scalar(sa.text("SELECT count(*) FROM sync_records"))
    assert not_started == 0
    assert recorded == SOURCES * ROUNDS
