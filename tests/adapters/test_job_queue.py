"""`JobQueue` 어댑터의 작업 넣기(명세 "수집 파이프라인과 작업", ADR 0009).

같은 문서의 대기 작업은 부분 유일 색인으로 하나라서 넣는 쪽이 있는 행을 다시 쓴다. 알림(`NOTIFY
rag_jobs`)은 커밋 때 간다.
"""

import asyncio
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import Document, JobKind, JobStatus
from rag_engine.domain.identifiers import new_id


async def _seed_document(unit_of_work: PostgresUnitOfWork) -> Document:
    source, group = await seed_source_and_group(unit_of_work)
    document = make_document(source, group)
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(document)
    return document


def _rows(database_url: str, document_id: UUID) -> list[tuple[str, str, int]]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        return connection.execute(
            "SELECT id::text, status, attempts FROM jobs WHERE document_id = %s ORDER BY id",
            [document_id],
        ).fetchall()


async def test_작업을_넣으면_대기_상태로_지금_돌_수_있게_들어간다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    document = await _seed_document(unit_of_work)
    request_id = new_id()

    async with unit_of_work.begin() as transaction:
        job = await transaction.jobs.enqueue(document.id, request_id, NOW)

    assert (job.kind, job.status, job.attempts) == (JobKind.INDEX_DOCUMENT, JobStatus.QUEUED, 0)
    assert (job.document_id, job.request_id) == (document.id, request_id)
    assert (job.run_after, job.created_at) == (NOW, NOW)
    assert (job.leased_until, job.worker_id, job.raised_generation) == (None, None, None)
    assert (job.last_error_code, job.started_at, job.finished_at) == (None, None, None)


async def test_같은_연결로_열다섯_번_넘게_넣어도_준비된_문장이_부분_색인을_찾는다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    document = await _seed_document(unit_of_work)

    for _ in range(15):
        async with unit_of_work.begin() as transaction:
            await transaction.jobs.enqueue(document.id, new_id(), NOW)

    assert len(_rows(empty_database_url, document.id)) == 1


async def test_대기_작업이_있는_문서에_다시_넣으면_새_행_없이_그_행을_다시_쓴다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    document = await _seed_document(unit_of_work)
    async with unit_of_work.begin() as transaction:
        first = await transaction.jobs.enqueue(document.id, new_id(), NOW)
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        connection.execute("UPDATE jobs SET attempts = 3 WHERE id = %s", [first.id])
    second_request = new_id()
    later = NOW + timedelta(minutes=5)

    async with unit_of_work.begin() as transaction:
        second = await transaction.jobs.enqueue(document.id, second_request, later)

    assert second.id == first.id
    assert (second.run_after, second.request_id) == (later, second_request)
    assert (second.attempts, second.created_at) == (3, NOW)
    assert _rows(empty_database_url, document.id) == [(str(first.id), "queued", 3)]


async def test_실행_중인_작업이_있어도_새_대기_작업은_들어간다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    document = await _seed_document(unit_of_work)
    async with unit_of_work.begin() as transaction:
        running = await transaction.jobs.enqueue(document.id, new_id(), NOW)
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        connection.execute("UPDATE jobs SET status = 'running' WHERE id = %s", [running.id])

    async with unit_of_work.begin() as transaction:
        queued = await transaction.jobs.enqueue(document.id, new_id(), NOW)

    assert queued.id != running.id
    assert sorted(status for _, status, _ in _rows(empty_database_url, document.id)) == [
        "queued",
        "running",
    ]


async def test_같은_문서에_동시에_넣어도_대기_작업은_하나다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    document = await _seed_document(unit_of_work)

    async def enqueue() -> UUID:
        async with unit_of_work.begin() as transaction:
            return (await transaction.jobs.enqueue(document.id, new_id(), NOW)).id

    first, second = await asyncio.gather(enqueue(), enqueue())

    assert first == second
    assert len(_rows(empty_database_url, document.id)) == 1


async def test_알림은_커밋_때_가고_롤백하면_가지_않는다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    document = await _seed_document(unit_of_work)

    class Abort(Exception):
        pass

    async with await psycopg.AsyncConnection.connect(
        empty_database_url, autocommit=True
    ) as listener:
        await listener.execute("LISTEN rag_jobs")

        with pytest.raises(Abort):
            async with unit_of_work.begin() as transaction:
                await transaction.jobs.enqueue(document.id, new_id(), NOW)
                raise Abort
        assert [note async for note in listener.notifies(timeout=0.5)] == []

        async with unit_of_work.begin() as transaction:
            await transaction.jobs.enqueue(document.id, new_id(), NOW)
            assert [note async for note in listener.notifies(timeout=0.5)] == []
        notes = [note async for note in listener.notifies(timeout=2.0, stop_after=1)]

    assert [note.channel for note in notes] == ["rag_jobs"]
