"""일정 확인 한 번(source-sync 티켓 10, 명세 "일정과 일정 확인", Testing Decisions의 장면 표).

시계를 기다리지 않고 "지금 시각"을 넣어 일정 확인을 한 번 돌린다. 실제 테스트 PostgreSQL 위에서
동기화 작업, 동기화 기록, 원천의 다음 실행 시각을 읽어 판정한다.
"""

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.support.schedule_sources import (
    CHECK_TIME,
    EVERY_HOUR,
    SEOUL_CALCULATOR,
    add_scheduled_source,
    mark_deleted,
    records_of,
    set_sync_job_status,
    source_named,
    sync_jobs,
)

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.schedule_check import check_schedules
from rag_engine.app.sync_requests import request_sync
from rag_engine.domain.entities import SyncRecordStatus, SyncTrigger
from rag_engine.domain.errors import InvalidScheduleError
from rag_engine.domain.identifiers import new_id

PAST = CHECK_TIME - timedelta(minutes=5)
NEXT_HOUR = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)


async def test_일정이_지난_원천에_동기화_작업과_일정_기록을_넣고_다음_시각을_지금_다음으로_옮긴다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(unit_of_work, "wiki", next_run_at=PAST)

    started = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    jobs = await sync_jobs(engine)
    assert [(job.source_id, job.status, job.options) for job in jobs] == [(source.id, "queued", {})]
    [record] = await records_of(unit_of_work, source)
    assert (record.trigger, record.status, record.job_id) == (
        SyncTrigger.SCHEDULE,
        SyncRecordStatus.QUEUED,
        jobs[0].id,
    )
    assert (record.options, record.failure_code, record.started_at, record.finished_at) == (
        {},
        None,
        None,
        None,
    )
    assert record.created_at == CHECK_TIME
    assert [(item.source, item.sync_record_id, item.job_id) for item in started] == [
        ("wiki", record.id, jobs[0].id)
    ]
    assert (await source_named(unit_of_work, "wiki")).next_run_at == NEXT_HOUR


async def test_같은_시각으로_한_번_더_돌려도_동기화_작업이_하나다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(unit_of_work, "wiki", next_run_at=PAST)

    first = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)
    second = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert len(first) == 1
    assert second == []
    assert len(await sync_jobs(engine)) == 1
    assert len(await records_of(unit_of_work, source)) == 1


async def test_놓친_회차가_여럿이어도_한_번만_넣고_지금_다음의_시각으로_옮긴다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(
        unit_of_work, "wiki", next_run_at=CHECK_TIME - timedelta(days=3)
    )

    await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert len(await sync_jobs(engine)) == 1
    assert len(await records_of(unit_of_work, source)) == 1
    assert (await source_named(unit_of_work, "wiki")).next_run_at == NEXT_HOUR


async def test_다음_시각이_아직_오지_않았거나_정각이면_시각이_지났는지는_이하로_가른다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    await add_scheduled_source(unit_of_work, "later", next_run_at=CHECK_TIME + timedelta(seconds=1))
    await add_scheduled_source(unit_of_work, "exact", next_run_at=CHECK_TIME)

    started = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert [item.source for item in started] == ["exact"]
    assert len(await sync_jobs(engine)) == 1


async def test_일시_중지한_원천과_지운_원천에는_동기화_작업이_생기지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    paused = await add_scheduled_source(unit_of_work, "paused", next_run_at=PAST, paused=True)
    deleted = await add_scheduled_source(unit_of_work, "deleted", next_run_at=PAST)
    await mark_deleted(engine, deleted)

    started = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert started == []
    assert await sync_jobs(engine) == []
    assert await records_of(unit_of_work, paused) == []
    assert await records_of(unit_of_work, deleted) == []


async def test_앞_동기화가_대기_중이면_작업은_넣지_않고_not_started_기록만_남긴다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(unit_of_work, "wiki", next_run_at=PAST)
    manual = await request_sync(
        unit_of_work, "wiki", apply_empty=False, reread=False, request_id=new_id(), now=PAST
    )

    started = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert [job.id for job in await sync_jobs(engine)] == [manual.job_id]
    first, second = await records_of(unit_of_work, source)
    assert first.id == manual.sync_record_id
    assert (second.trigger, second.status, second.failure_code) == (
        SyncTrigger.SCHEDULE,
        SyncRecordStatus.NOT_STARTED,
        "sync_in_progress",
    )
    assert second.job_id is None
    assert second.started_at is None
    assert second.finished_at == second.created_at == CHECK_TIME
    assert [(item.sync_record_id, item.job_id) for item in started] == [(second.id, None)]
    assert (await source_named(unit_of_work, "wiki")).next_run_at == NEXT_HOUR


async def test_앞_동기화가_실행_중이어도_not_started_기록만_남긴다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(unit_of_work, "wiki", next_run_at=PAST)
    await request_sync(
        unit_of_work, "wiki", apply_empty=False, reread=False, request_id=new_id(), now=PAST
    )
    await set_sync_job_status(engine, "running")

    await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert len(await sync_jobs(engine)) == 1
    statuses = [record.status for record in await records_of(unit_of_work, source)]
    assert statuses == [SyncRecordStatus.QUEUED, SyncRecordStatus.NOT_STARTED]


async def test_앞_동기화가_끝났으면_다음_회차는_다시_작업을_넣는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source = await add_scheduled_source(unit_of_work, "wiki", next_run_at=PAST)
    await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)
    await set_sync_job_status(engine, "succeeded")

    await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=NEXT_HOUR)

    assert [job.status for job in await sync_jobs(engine)] == ["succeeded", "queued"]
    statuses = [record.status for record in await records_of(unit_of_work, source)]
    assert statuses == [SyncRecordStatus.QUEUED, SyncRecordStatus.QUEUED]


async def test_시각이_지난_원천_여럿은_원천마다_작업_하나와_다른_요청_ID를_받는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    for name in ("a", "b", "c"):
        await add_scheduled_source(unit_of_work, name, next_run_at=PAST)

    started = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    jobs = await sync_jobs(engine)
    assert len({job.source_id for job in jobs}) == len(jobs) == 3
    assert len({job.request_id for job in jobs}) == 3
    assert sorted(item.source for item in started) == ["a", "b", "c"]


async def test_일정_없이_다음_시각만_남은_원천은_작업을_넣지_않고_시각을_비운다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    await add_scheduled_source(unit_of_work, "wiki", schedule=None, next_run_at=PAST)

    started = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert started == []
    assert await sync_jobs(engine) == []
    stored = await source_named(unit_of_work, "wiki")
    assert (stored.schedule, stored.next_run_at) == (None, None)


async def test_일정_확인은_원천을_고치는_요청이_잡은_행을_기다리지_않고_건너뛴다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    locked = await add_scheduled_source(unit_of_work, "locked", next_run_at=PAST)
    await add_scheduled_source(unit_of_work, "free", next_run_at=PAST)
    async with unit_of_work.begin() as holding:
        await holding.catalog.lock_source(locked.id)

        started = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert [item.source for item in started] == ["free"]
    again = await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)
    assert [item.source for item in again] == ["locked"]


async def test_일정_확인이_실패하면_아무것도_남기지_않는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    await add_scheduled_source(unit_of_work, "a", next_run_at=PAST)
    await add_scheduled_source(unit_of_work, "b", next_run_at=PAST, schedule=EVERY_HOUR)
    async with engine.begin() as connection:
        # 저장된 표현식이 계산기가 받지 않는 글이 된 경우를 흉내 낸다.
        await connection.execute(sa.text("UPDATE sources SET schedule = 'x y z' WHERE name = 'b'"))

    with pytest.raises(InvalidScheduleError):
        await check_schedules(unit_of_work, SEOUL_CALCULATOR, now=CHECK_TIME)

    assert await sync_jobs(engine) == []
    assert (await source_named(unit_of_work, "a")).next_run_at == PAST
