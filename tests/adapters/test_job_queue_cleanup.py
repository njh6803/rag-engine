"""`JobQueue` 어댑터의 정리 작업(source-sync 명세 "정리 작업"과 "작업 대기열").

정리 작업은 원천도 문서도 가리키지 않는다. 대기 중이거나 실행 중인 정리 작업은 하나뿐이어야 하고(빈
값끼리 같은 값으로 보는 부분 유일 색인), 일정 확인이 쓰는 "이 시각 뒤에 넣은 적이 없으면 넣는다"는
한 문장이다. 꺼낼 때는 문서 색인 작업보다 먼저 나온다.
"""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import JobKind, JobStatus
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome

LEASE_SECONDS = 600.0
REPEATS = 20
LONG_AGO = NOW - timedelta(days=30)


async def test_한_연결에서_스무_번_넣어도_정리_작업은_하나만_들어간다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)

    async with unit_of_work.begin() as transaction:
        answers = [
            await transaction.jobs.enqueue_cleanup(LONG_AGO, new_id(), NOW) for _ in range(REPEATS)
        ]

    first = answers[0]
    assert first is not None
    assert (first.kind, first.source_id, first.document_id) == (JobKind.CLEANUP, None, None)
    assert answers[1:] == [None] * (REPEATS - 1)


async def test_실행_중인_정리_작업이_있어도_넣지_않는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue_cleanup(LONG_AGO, new_id(), LONG_AGO)
        await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)

    async with unit_of_work.begin() as transaction:
        while_running = await transaction.jobs.enqueue_cleanup(
            NOW + timedelta(days=1), new_id(), NOW
        )

    assert while_running is None


async def test_기준_시각_뒤에_넣은_정리_작업이_있으면_끝났어도_넣지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    async with unit_of_work.begin() as transaction:
        queued = await transaction.jobs.enqueue_cleanup(LONG_AGO, new_id(), NOW)
        assert queued is not None
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
        assert claimed is not None
        await transaction.jobs.finish(claimed, JobOutcome(JobStatus.SUCCEEDED, None), NOW)

    async with unit_of_work.begin() as transaction:
        recent = await transaction.jobs.enqueue_cleanup(NOW, new_id(), NOW)
        older = await transaction.jobs.enqueue_cleanup(NOW + timedelta(seconds=1), new_id(), NOW)

    assert recent is None
    assert older is not None


async def test_정리_작업은_먼저_들어온_문서_색인_작업보다_먼저_나온다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    document = make_document(source, group, key="규정.pdf")
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(document)
        indexing = await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        cleanup = await transaction.jobs.enqueue_cleanup(LONG_AGO, new_id(), NOW)

    async with unit_of_work.begin() as transaction:
        first = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
        second = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)

    assert cleanup is not None
    assert first is not None
    assert second is not None
    assert (first.id, second.id) == (cleanup.id, indexing.id)


async def test_원천의_가장_나중_작업을_종류로_읽는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    async with unit_of_work.begin() as transaction:
        before = await transaction.jobs.latest_source_job(source.id, JobKind.RESTORE_SOURCE)
        older = await transaction.jobs.enqueue_source_job(
            JobKind.RESTORE_SOURCE, source.id, {}, new_id(), NOW
        )
        assert older is not None
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
        assert claimed is not None
        await transaction.jobs.finish(claimed, JobOutcome(JobStatus.FAILED, None), NOW)
        newer = await transaction.jobs.enqueue_source_job(
            JobKind.RESTORE_SOURCE, source.id, {}, new_id(), NOW
        )
        other_kind = await transaction.jobs.latest_source_job(source.id, JobKind.SYNC_SOURCE)
        latest = await transaction.jobs.latest_source_job(source.id, JobKind.RESTORE_SOURCE)

    assert newer is not None
    assert before is None
    assert other_kind is None
    assert latest is not None
    assert latest.id == newer.id
