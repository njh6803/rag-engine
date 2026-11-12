"""재색인 시험이 함께 쓰는 도우미(티켓 14). `Pipeline` 세계 위에서 재색인을 시작하고 판의 상태를
읽는다."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from tests.records import NOW
from tests.support.interleaving import PausingUnitOfWork
from tests.support.pipeline import Pipeline

from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.adapters.postgres.index_maintenance import PostgresIndexMaintenance
from rag_engine.adapters.postgres.vector_index import version_index_name
from rag_engine.app.index_document import index_document
from rag_engine.app.reindex import ReindexStarted, start_reindex
from rag_engine.domain.entities import IndexStateStatus, IndexVersion, IndexVersionStatus
from rag_engine.domain.identifiers import new_id

NEW_CHUNK_TOKENS = 64
MOMENT_SECONDS = 60
POLL_SECONDS = 0.05
POLL_LIMIT = 400


async def set_chunk_tokens(pipeline: Pipeline, chunk_tokens: int = NEW_CHUNK_TOKENS) -> None:
    """지식베이스 설정의 청킹 크기를 고쳐 "재색인 필요"를 만든다."""
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE knowledge_bases SET chunk_tokens = :tokens, chunk_overlap_tokens = 8"),
            {"tokens": chunk_tokens},
        )


async def start(pipeline: Pipeline) -> ReindexStarted:
    return await start_reindex(
        pipeline.unit_of_work,
        PostgresIndexMaintenance(pipeline.engine),
        compute_index_elements,
        pipeline.knowledge_base.name,
        request_id=new_id(),
        now=NOW,
    )


async def versions_of(pipeline: Pipeline) -> list[IndexVersion]:
    async with pipeline.unit_of_work.begin() as transaction:
        return await transaction.catalog.list_index_versions(pipeline.knowledge_base.id)


async def version_of(pipeline: Pipeline, status: IndexVersionStatus) -> IndexVersion | None:
    found = [v for v in await versions_of(pipeline) if v.status is status]
    assert len(found) <= 1
    return found[0] if found else None


async def current_version(pipeline: Pipeline) -> IndexVersion:
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None
    return current


async def building_version(pipeline: Pipeline) -> IndexVersion:
    building = await version_of(pipeline, IndexVersionStatus.BUILDING)
    assert building is not None
    return building


async def index_all_queued(pipeline: Pipeline) -> None:
    """대기 중인 작업을 모두 꺼내 색인한다."""
    async with pipeline.engine.connect() as connection:
        queued = (
            await connection.execute(sa.text("SELECT count(*) FROM jobs WHERE status = 'queued'"))
        ).scalar_one()
    for _ in range(queued):
        await index_document(pipeline.deps(), await pipeline.claim())


async def ingest_and_index(pipeline: Pipeline, data: bytes, key: str = "규정.docx") -> UUID:
    ingested = await pipeline.ingest(data, key)
    await index_document(pipeline.deps(), await pipeline.claim())
    return ingested.document_id


async def state_status(
    pipeline: Pipeline, document_id: UUID, version: IndexVersion
) -> IndexStateStatus | None:
    async with pipeline.unit_of_work.begin() as transaction:
        state = await transaction.index.get_state(document_id, version.id)
    return None if state is None else state.status


async def keywords_of(pipeline: Pipeline, document_id: UUID, version: IndexVersion) -> list[str]:
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                "SELECT keywords::text FROM chunks WHERE document_id = :document"
                " AND index_version_id = :version ORDER BY ordinal"
            ),
            {"document": document_id, "version": version.id},
        )
        return [row[0] for row in rows]


async def index_exists(pipeline: Pipeline, version: IndexVersion) -> bool:
    async with pipeline.engine.connect() as connection:
        found = await connection.execute(
            sa.text("SELECT to_regclass(:name)"), {"name": version_index_name(version.id)}
        )
        return found.scalar_one() is not None


async def chunk_count(pipeline: Pipeline, version: IndexVersion) -> int:
    async with pipeline.engine.connect() as connection:
        found = await connection.execute(
            sa.text("SELECT count(*) FROM chunks WHERE index_version_id = :version"),
            {"version": version.id},
        )
        return found.scalar_one()


@asynccontextmanager
async def paused_reindex(pipeline: Pipeline) -> AsyncGenerator[None]:
    """재색인 시작의 작업 단위를 모든 쓰기를 마친 뒤 커밋 직전에 멈춰 둔다(둘째 작업 단위가
    지식베이스 행을 잠그고 판과 작업을 쓰는 쪽이다). 블록을 나가면 풀어 주고 재색인이 끝나기를
    기다린다."""
    pausing = PausingUnitOfWork(pipeline.unit_of_work, pause_on=2)
    reindex = asyncio.create_task(
        start_reindex(
            pausing,
            PostgresIndexMaintenance(pipeline.engine),
            compute_index_elements,
            pipeline.knowledge_base.name,
            request_id=new_id(),
            now=NOW,
        )
    )
    reached = asyncio.create_task(pausing.paused.wait())
    done, _ = await asyncio.wait(
        {reindex, reached}, timeout=MOMENT_SECONDS, return_when=asyncio.FIRST_COMPLETED
    )
    assert reached in done, "재색인 시작이 멈춤 지점에 닿지 못했다"
    try:
        yield
    finally:
        pausing.release.set()
        await asyncio.wait_for(reindex, timeout=MOMENT_SECONDS)


async def lock_waiters(pipeline: Pipeline) -> int:
    """이 데이터베이스에서 행 잠금을 기다리는 백엔드의 수."""
    async with pipeline.engine.connect() as connection:
        found = await connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_stat_activity"
                " WHERE datname = current_database() AND wait_event_type = 'Lock'"
            )
        )
        return found.scalar_one()


async def wait_for_lock_waiter(pipeline: Pipeline, task: "asyncio.Task[object]") -> None:
    """`task`가 끝나지 않은 채 데이터베이스의 행 잠금을 기다리는 것을 본다."""
    for _ in range(POLL_LIMIT):
        if task.done() or await lock_waiters(pipeline) > 0:
            break
        await asyncio.sleep(POLL_SECONDS)
    assert not task.done(), "잠금을 기다리지 않고 끝났다"
    assert await lock_waiters(pipeline) > 0


@asynccontextmanager
async def held_knowledge_base_lock(pipeline: Pipeline) -> AsyncGenerator[None]:
    """다른 연결이 지식베이스 행을 `FOR UPDATE`로 잡은 채 블록을 돈다. 블록을 나가면 커밋해 푼다."""
    async with pipeline.engine.begin() as connection:
        await connection.execute(sa.text("SELECT id FROM knowledge_bases FOR UPDATE"))
        yield


async def job_row_is_free(pipeline: Pipeline, job_id: UUID) -> bool:
    """다른 연결이 작업 행을 기다리지 않고 잠글 수 있으면 참. 작업 행을 쥔 쪽이 있으면 거짓."""
    try:
        async with pipeline.engine.begin() as connection:
            await connection.execute(
                sa.text("SELECT id FROM jobs WHERE id = :id FOR UPDATE NOWAIT"), {"id": job_id}
            )
    except DBAPIError:
        return False
    return True
