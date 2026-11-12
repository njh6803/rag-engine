"""`JobQueue` 어댑터의 꺼내기와 끝내기(명세 "수집 파이프라인과 작업", ADR 0009).

작업자는 `FOR UPDATE SKIP LOCKED`로 `queued`이고 `run_after`가 지난 작업이나 임대가 끝난 `running`
작업 하나를 꺼내 `running`으로 바꾸고 시도 횟수를 올리고 올린 세대를 비운다. 임대 연장과 재시도
예약의 완성은 13과 12다.
"""

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import Document, JobStatus
from rag_engine.domain.errors import AttemptLostError, ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome

LEASE_SECONDS = 600.0


async def _seed_documents(unit_of_work: PostgresUnitOfWork, count: int = 1) -> list[Document]:
    source, group = await seed_source_and_group(unit_of_work)
    documents = [make_document(source, group, key=f"규정{index}.pdf") for index in range(count)]
    async with unit_of_work.begin() as transaction:
        for document in documents:
            await transaction.documents.add(document)
    return documents


async def test_지금_돌_수_있는_작업을_꺼내_실행_중으로_바꾸고_시도_횟수와_임대를_둔다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        queued = await transaction.jobs.enqueue(document.id, new_id(), NOW)

    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)

    assert claimed is not None
    assert claimed.id == queued.id
    assert (claimed.status, claimed.attempts, claimed.worker_id) == (
        JobStatus.RUNNING,
        1,
        "작업자-1",
    )
    assert claimed.leased_until == NOW + timedelta(seconds=LEASE_SECONDS)
    assert (claimed.raised_generation, claimed.started_at) == (None, NOW)


async def test_다음_실행_시각이_아직_오지_않은_작업은_꺼내지_않는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW + timedelta(minutes=5))

    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)

    assert [claimed] == [None]


async def test_두_작업자가_동시에_꺼내도_같은_작업을_잡지_않는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)

    async with unit_of_work.begin() as first, unit_of_work.begin() as second:
        first_job = await first.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
        second_job = await second.jobs.claim("작업자-2", NOW, LEASE_SECONDS)

    assert first_job is not None
    assert second_job is None


async def test_임대가_끝난_실행_중_작업은_다른_작업자가_가져가고_시도_횟수가_는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)

    async with unit_of_work.begin() as transaction:
        during_lease = await transaction.jobs.claim("작업자-2", NOW, LEASE_SECONDS)
    later = NOW + timedelta(seconds=LEASE_SECONDS + 1)
    async with unit_of_work.begin() as transaction:
        taken = await transaction.jobs.claim("작업자-2", later, LEASE_SECONDS)

    assert during_lease is None
    assert [None if taken is None else (taken.worker_id, taken.attempts, taken.status)] == [
        ("작업자-2", 2, JobStatus.RUNNING)
    ]


async def test_꺼낼_때_올린_세대를_비운다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
    assert claimed is not None
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.record_raised_generation(claimed, 7)

    later = NOW + timedelta(seconds=LEASE_SECONDS + 1)
    async with unit_of_work.begin() as transaction:
        retaken = await transaction.jobs.claim("작업자-2", later, LEASE_SECONDS)

    assert retaken is not None
    assert [retaken.raised_generation] == [None]


async def test_작업_행_조건은_작업자와_시도_횟수가_꺼낼_때_값_그대로일_때만_참이다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        first = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
    assert first is not None
    later = NOW + timedelta(seconds=LEASE_SECONDS + 1)
    async with unit_of_work.begin() as transaction:
        retaken = await transaction.jobs.claim("작업자-1", later, LEASE_SECONDS)
    assert retaken is not None

    async with unit_of_work.begin() as transaction:
        results = [
            await transaction.jobs.hold_attempt(retaken),
            await transaction.jobs.hold_attempt(first),
            await transaction.jobs.hold_attempt(replace(retaken, worker_id="작업자-9")),
        ]

    assert results == [True, False, False]


async def test_임대를_잃은_시도가_끝내려_해도_작업_행은_그대로다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        lost = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
    assert lost is not None
    later = NOW + timedelta(seconds=LEASE_SECONDS + 1)
    async with unit_of_work.begin() as transaction:
        taken = await transaction.jobs.claim("작업자-2", later, LEASE_SECONDS)
    assert taken is not None

    with pytest.raises(AttemptLostError):
        async with unit_of_work.begin() as transaction:
            await transaction.jobs.finish(lost, JobOutcome(JobStatus.SUCCEEDED, None), later)
    async with unit_of_work.begin() as transaction:
        reread = await transaction.jobs.get(taken.id)

    assert reread is not None
    assert (reread.status, reread.worker_id, reread.finished_at) == (
        JobStatus.RUNNING,
        "작업자-2",
        None,
    )


async def test_끝낸_작업은_상태와_끝난_시각과_오류_코드를_갖고_임대가_사라진다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
    assert claimed is not None

    finished_at = NOW + timedelta(seconds=3)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.finish(
            claimed, JobOutcome(JobStatus.FAILED, ErrorCode.PARSE_FAILED), finished_at
        )
    async with unit_of_work.begin() as transaction:
        reread = await transaction.jobs.get(claimed.id)

    assert reread is not None
    assert (reread.status, reread.last_error_code) == (JobStatus.FAILED, ErrorCode.PARSE_FAILED)
    assert (reread.finished_at, reread.leased_until) == (finished_at, None)


async def test_없는_작업을_조회하면_None이다(engine: AsyncEngine) -> None:
    async with PostgresUnitOfWork(engine).begin() as transaction:
        assert await transaction.jobs.get(new_id()) is None
