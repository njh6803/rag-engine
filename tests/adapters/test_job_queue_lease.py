"""`JobQueue` 어댑터의 임대 연장과 인수(명세 "수집 파이프라인과 작업"의 작업자 항목, 티켓 13).

임대 연장과 끝내기도 작업 행 조건(작업자 ID와 시도 횟수가 꺼낼 때 값 그대로)을 지나고, 임대를 잃은
시도면 작업 행을 바꾸지 않고 `AttemptLostError`를 올려 임대를 잃은 시도가 끝낸 것으로 오해하지 않게
한다. 인수 시험은 `RAG_JOB_LEASE_SECONDS=1`의 실제 시간으로 임대가 끝나기를 기다린다.
"""

import asyncio
from datetime import UTC, datetime, timedelta

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


async def test_임대를_연장하면_임대_만료가_새_시각이_된다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
    assert claimed is not None

    extended_until = NOW + timedelta(seconds=LEASE_SECONDS * 2)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.extend_lease(claimed, extended_until)
    async with unit_of_work.begin() as transaction:
        reread = await transaction.jobs.get(claimed.id)

    assert reread is not None
    assert (reread.status, reread.worker_id, reread.attempts, reread.leased_until) == (
        JobStatus.RUNNING,
        "작업자-1",
        1,
        extended_until,
    )


async def test_임대를_잃은_시도의_연장은_작업_행을_바꾸지_않고_임대를_잃었다고_알린다(
    engine: AsyncEngine,
) -> None:
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
            await transaction.jobs.extend_lease(lost, later + timedelta(days=1))
    async with unit_of_work.begin() as transaction:
        reread = await transaction.jobs.get(taken.id)

    assert reread is not None
    assert (reread.worker_id, reread.attempts, reread.leased_until) == (
        "작업자-2",
        2,
        taken.leased_until,
    )


async def test_같은_작업자가_다시_꺼낸_뒤에도_이전_시도의_연장은_임대를_잃었다고_알린다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
    async with unit_of_work.begin() as transaction:
        late = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
    assert late is not None
    later = NOW + timedelta(seconds=LEASE_SECONDS + 1)
    async with unit_of_work.begin() as transaction:
        retaken = await transaction.jobs.claim("작업자-1", later, LEASE_SECONDS)
    assert retaken is not None

    extended_until = later + timedelta(days=1)
    with pytest.raises(AttemptLostError):
        async with unit_of_work.begin() as transaction:
            await transaction.jobs.extend_lease(late, extended_until)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.extend_lease(retaken, extended_until)
    async with unit_of_work.begin() as transaction:
        reread = await transaction.jobs.get(retaken.id)

    assert reread is not None
    assert reread.leased_until == extended_until


async def test_끝내기는_이_시도의_작업_행만_쓰고_잃은_시도는_임대를_잃었다고_알린다(
    engine: AsyncEngine,
) -> None:
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
        before = await transaction.jobs.get(taken.id)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.finish(
            taken, JobOutcome(JobStatus.FAILED, ErrorCode.PARSE_FAILED), later
        )
    async with unit_of_work.begin() as transaction:
        after = await transaction.jobs.get(taken.id)

    assert before is not None
    assert after is not None
    assert before.status is JobStatus.RUNNING
    assert (after.status, after.last_error_code) == (JobStatus.FAILED, ErrorCode.PARSE_FAILED)


async def test_두_작업자가_동시에_꺼내도_모든_작업이_한_번씩만_나간다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    documents = await _seed_documents(unit_of_work, count=6)
    async with unit_of_work.begin() as transaction:
        for document in documents:
            await transaction.jobs.enqueue(document.id, new_id(), NOW)

    async def drain(worker_id: str) -> list[str]:
        taken: list[str] = []
        while True:
            async with unit_of_work.begin() as transaction:
                job = await transaction.jobs.claim(worker_id, NOW, LEASE_SECONDS)
            if job is None:
                return taken
            taken.append(str(job.id))

    first, second = await asyncio.gather(drain("작업자-1"), drain("작업자-2"))

    assert len(first) + len(second) == 6
    assert set(first).isdisjoint(second)


async def test_임대가_1초인_작업은_1초가_지나면_다른_작업자가_가져가고_시도_횟수가_는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed_documents(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), datetime.now(UTC))
    async with unit_of_work.begin() as transaction:
        first = await transaction.jobs.claim("작업자-1", datetime.now(UTC), 1.0)
    assert first is not None
    async with unit_of_work.begin() as transaction:
        during_lease = await transaction.jobs.claim("작업자-2", datetime.now(UTC), 1.0)

    await asyncio.sleep(1.2)
    async with unit_of_work.begin() as transaction:
        taken = await transaction.jobs.claim("작업자-2", datetime.now(UTC), 1.0)

    assert during_lease is None
    assert taken is not None
    assert (taken.id, taken.worker_id, taken.attempts) == (first.id, "작업자-2", 2)
