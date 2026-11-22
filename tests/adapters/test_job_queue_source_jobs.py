"""`JobQueue` 어댑터의 원천 단위 작업(source-sync 명세 "동기화의 차례", ADR 0009).

같은 원천의 같은 종류 작업은 대기 중이거나 실행 중인 것이 하나뿐이고, 꺼낼 때는 원천 단위 작업이
문서 색인 작업보다 먼저 나온다.
"""

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import JobKind, JobStatus
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome

LEASE_SECONDS = 600.0
REPEATS = 20


async def test_같은_원천의_같은_종류_작업은_대기나_실행_중이면_넣지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    async with unit_of_work.begin() as transaction:
        first = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
        )
    async with unit_of_work.begin() as transaction:
        while_queued = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
        )
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
    async with unit_of_work.begin() as transaction:
        while_running = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
        )

    assert first is not None
    assert while_queued is None
    assert claimed is not None
    assert claimed.id == first.id
    assert while_running is None


async def test_끝난_작업은_다음_같은_종류_작업을_막지_않는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue_source_job(JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
        assert claimed is not None
        await transaction.jobs.finish(claimed, JobOutcome(JobStatus.SUCCEEDED, None), NOW)

    async with unit_of_work.begin() as transaction:
        again = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
        )

    assert again is not None


async def test_같은_원천이라도_다른_종류_작업은_함께_들어간다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    async with unit_of_work.begin() as transaction:
        sync = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
        )
        delete = await transaction.jobs.enqueue_source_job(
            JobKind.DELETE_SOURCE, source.id, {}, new_id(), NOW
        )

    assert sync is not None
    assert delete is not None


async def test_한_연결에서_스무_번_넣어도_하나만_들어가고_나머지는_없음으로_답한다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)

    async with unit_of_work.begin() as transaction:
        answers = [
            await transaction.jobs.enqueue_source_job(
                JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
            )
            for _ in range(REPEATS)
        ]

    assert answers[0] is not None
    assert answers[1:] == [None] * (REPEATS - 1)


async def test_원천_단위_작업은_먼저_들어온_문서_색인_작업보다_먼저_나온다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    document = make_document(source, group, key="규정.pdf")
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(document)
        indexing = await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        sync = await transaction.jobs.enqueue_source_job(
            JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW
        )

    async with unit_of_work.begin() as transaction:
        first = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
        second = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)

    assert sync is not None
    assert first is not None
    assert second is not None
    assert (first.id, second.id) == (sync.id, indexing.id)
