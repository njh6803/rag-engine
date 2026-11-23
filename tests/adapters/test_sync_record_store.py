"""`SyncRecordStore` 어댑터(source-sync 티켓 07, 명세 "동기화 기록").

기록 하나를 넣고 읽고 고치는 왕복, 작업으로 찾기, 원천마다 최근 것부터 나누어 읽기를 본다.
"""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import JobKind, SyncRecord, SyncRecordStatus, SyncTrigger
from rag_engine.domain.identifiers import new_id


def _queued(source_id: UUID, job_id: UUID | None = None) -> SyncRecord:
    return SyncRecord(
        id=new_id(),
        source_id=source_id,
        job_id=job_id,
        trigger=SyncTrigger.MANUAL,
        options={"reread": True},
        status=SyncRecordStatus.QUEUED,
        failure_code=None,
        created_at=NOW,
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


async def test_기록을_넣고_읽고_고치면_개수와_사유별_개수가_그대로_돌아온다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    record = _queued(source.id)
    async with unit_of_work.begin() as transaction:
        await transaction.sync_records.add(record)
    finished = replace(
        record,
        status=SyncRecordStatus.FAILED,
        failure_code="source_unreadable",
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=3),
        listed=7,
        added=2,
        updated=1,
        unchanged=1,
        skipped={"encrypted": 1},
        not_accepted={"excluded": 1, "too_large": 1},
        failed={"parse_failed": 1},
    )

    async with unit_of_work.begin() as transaction:
        before = await transaction.sync_records.get(record.id)
        await transaction.sync_records.update(finished)
    async with unit_of_work.begin() as transaction:
        after = await transaction.sync_records.get(record.id)

    assert before == record
    assert after == finished


async def test_없는_기록은_없음으로_답한다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)

    async with unit_of_work.begin() as transaction:
        found = await transaction.sync_records.get(new_id())

    assert found is None


async def test_동기화_작업으로_그_작업의_기록을_찾는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    async with unit_of_work.begin() as transaction:
        job = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
        )
        assert job is not None
        record = _queued(source.id, job.id)
        await transaction.sync_records.add(record)

    async with unit_of_work.begin() as transaction:
        found = await transaction.sync_records.get_by_job(job.id)
        missing = await transaction.sync_records.get_by_job(new_id())

    assert found == record
    assert missing is None


async def test_원천의_기록을_최근_것부터_나누어_읽고_가장_최근_것을_낸다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    records = [_queued(source.id) for _ in range(3)]
    async with unit_of_work.begin() as transaction:
        for record in records:
            await transaction.sync_records.add(record)
    newest_first = list(reversed(records))

    async with unit_of_work.begin() as transaction:
        first_page = await transaction.sync_records.list_for_source(source.id, 2, None)
        second_page = await transaction.sync_records.list_for_source(
            source.id, 2, first_page[-1].id
        )
        latest = await transaction.sync_records.latest_for_source(source.id)

    assert [record.id for record in first_page] == [record.id for record in newest_first[:2]]
    assert [record.id for record in second_page] == [newest_first[2].id]
    assert latest is not None
    assert latest.id == newest_first[0].id


async def test_기록이_없는_원천의_가장_최근_기록은_없음이다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)

    async with unit_of_work.begin() as transaction:
        latest = await transaction.sync_records.latest_for_source(source.id)

    assert latest is None
