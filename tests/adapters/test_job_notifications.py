"""작업 알림 듣기(`LISTEN rag_jobs`, 명세 "수집 파이프라인과 작업"의 작업자 항목, 티켓 13).

실제 테스트 PostgreSQL에서 작업을 넣는 작업 단위가 커밋될 때 보내는 `NOTIFY`를 듣는지, 연결이
끊기면 다시 붙어 끊긴 사이를 메우려 한 번 깨우는지 본다.
"""

import asyncio
from collections.abc import AsyncIterator, Callable

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.notifications import JobNotificationListener
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.identifiers import new_id

WAIT_SECONDS = 10.0


class _Listening:
    """듣는 작업을 띄워 두고 깨움을 센다."""

    def __init__(self, database_url: str) -> None:
        self.pokes = 0
        self.ready = asyncio.Event()
        self._listener = JobNotificationListener(database_url, retry_seconds=0.05)
        self._task = asyncio.create_task(self._listener.run(self._poke, self.ready))

    def _poke(self) -> None:
        self.pokes += 1

    async def wait_for_pokes(self, count: int) -> None:
        async with asyncio.timeout(WAIT_SECONDS):
            while self.pokes < count:
                await asyncio.sleep(0.01)

    async def stop(self) -> None:
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)


@pytest.fixture
async def listening(empty_database_url: str) -> AsyncIterator[_Listening]:
    started = _Listening(empty_database_url)
    try:
        async with asyncio.timeout(WAIT_SECONDS):
            await started.ready.wait()
        yield started
    finally:
        await started.stop()


async def _enqueue(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    document = make_document(source, group, key=f"규정{new_id()}.pdf")
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(document)
        await transaction.jobs.enqueue(document.id, new_id(), NOW)


async def test_작업을_넣은_작업_단위가_커밋되면_깨운다(
    engine: AsyncEngine, listening: _Listening
) -> None:
    await _enqueue(engine)

    await listening.wait_for_pokes(1)

    assert listening.pokes >= 1


async def test_연결이_끊기면_다시_붙어_끊긴_사이를_메우려_한_번_깨우고_계속_듣는다(
    engine: AsyncEngine,
    listening: _Listening,
    empty_database_url: str,
    terminate_listener: Callable[[str], None],
) -> None:
    before = listening.pokes

    terminate_listener(empty_database_url)
    await listening.wait_for_pokes(before + 1)
    after_reconnect = listening.pokes
    await _enqueue(engine)

    await listening.wait_for_pokes(after_reconnect + 1)
    assert listening.pokes > after_reconnect


@pytest.fixture
def terminate_listener() -> Callable[[str], None]:
    """듣는 연결(`LISTEN`을 마지막으로 친 백엔드)을 서버에서 끊는 도우미."""

    def terminate(database_url: str) -> None:
        with psycopg.connect(database_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                " WHERE datname = current_database() AND query LIKE 'LISTEN%'"
                " AND pid <> pg_backend_pid()"
            )

    return terminate
