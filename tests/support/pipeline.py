"""수집에서 색인까지 이어 보는 시험 세계(티켓 07).

실제 테스트 PostgreSQL 위에 원천, 그룹, 지식베이스(현재 판 하나)를 세우고, 실제 `ingest_document`로
DOCX를 넣고, 실제 파서 자식 프로세스와 실제 청커·Kiwi로 `index_document`를 돌린다. 임베딩 서버만
`TeiStub`이다(명세 Testing Decisions). 시험은 이 세계에 끼어들 곳(임베딩 직전)만 바꿔 끼운다.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import httpx
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_index_version, make_knowledge_base, seed_source_and_group
from tests.support.docx_files import docx_bytes
from tests.support.tei_stub import TeiStub

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.chunking import chunker_for
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.parsers.registry import ParserRegistry, discover_parser_specs
from rag_engine.adapters.parsers.runner import SubprocessParseRunner
from rag_engine.adapters.postgres.index_maintenance import PostgresIndexMaintenance
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.tei import TeiEmbedderPool
from rag_engine.app.delete_document import delete_document
from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.app.ingest import IngestRequest, IngestResult, ingest_document
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.domain.entities import (
    Group,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    Job,
    KnowledgeBase,
    Source,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.parsing import ParseRunner
from rag_engine.domain.ports import EmbedderFor, UnitOfWork

DIMENSIONS = 16
LEASE_SECONDS = 600.0
CLAIM_RETRY_SECONDS = 5.0
CLAIM_RETRY_PAUSE_SECONDS = 0.02
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
BACKOFF_BASE_SECONDS = 30.0
DEFAULT_RETRY = RetryPolicy(max_attempts=6, backoff_base_seconds=BACKOFF_BASE_SECONDS)


@dataclass(frozen=True, slots=True)
class JobRow:
    """작업 행에서 시험이 보는 칸."""

    status: str
    last_error_code: str | None
    attempts: int
    run_after: datetime


@dataclass(slots=True)
class Pipeline:
    unit_of_work: PostgresUnitOfWork
    engine: AsyncEngine
    blob_store: LocalBlobStore
    stub: TeiStub
    pool: TeiEmbedderPool
    parse_runner: SubprocessParseRunner
    source: Source
    group: Group
    knowledge_base: KnowledgeBase
    version: IndexVersion
    clock: list[datetime] = field(default_factory=lambda: [NOW])

    def deps(
        self,
        *,
        embedder_for: EmbedderFor | None = None,
        parse_runner: ParseRunner | None = None,
        unit_of_work: UnitOfWork | None = None,
        retry: RetryPolicy = DEFAULT_RETRY,
    ) -> IndexDocumentDeps:
        return IndexDocumentDeps(
            retry=retry,
            unit_of_work=unit_of_work or self.unit_of_work,
            blob_store=self.blob_store,
            parse_runner=parse_runner or self.parse_runner,
            embedder_for=embedder_for or self.pool,
            chunker_for=chunker_for,
            tokenize_keywords=tokenize_keywords,
            now=lambda: self.clock[0],
            maintenance=PostgresIndexMaintenance(self.engine),
        )

    async def ingest(
        self,
        data: bytes,
        key: str = "규정.docx",
        *,
        group: str | None = None,
        updated_at: datetime | None = None,
    ) -> IngestResult:
        return await ingest_document(
            self.unit_of_work,
            self.blob_store,
            IngestRequest(
                filename=key, data=data, key=None, group=group, metadata={}, updated_at=updated_at
            ),
            request_id=new_id(),
            now=self.clock[0],
            max_upload_bytes=MAX_UPLOAD_BYTES,
        )

    async def delete(self, key: str = "규정.docx") -> None:
        await delete_document(self.unit_of_work, key, now=self.clock[0])

    async def archived_texts(self, document_id: UUID) -> list[str]:
        """보관 표에 있는 그 문서의 조각 글(순번 순)."""
        async with self.engine.connect() as connection:
            rows = await connection.execute(
                sa.text(
                    "SELECT text FROM archived_chunks WHERE document_id = :document"
                    " ORDER BY index_version_id, ordinal"
                ),
                {"document": document_id},
            )
            return [row[0] for row in rows]

    async def job_rows(self, document_id: UUID) -> list[JobRow]:
        """그 문서의 작업 행을 만든 순서로 낸다."""
        async with self.engine.connect() as connection:
            rows = await connection.execute(
                sa.text(
                    "SELECT status, last_error_code, attempts, run_after FROM jobs"
                    " WHERE document_id = :document ORDER BY id"
                ),
                {"document": document_id},
            )
            return [JobRow(row[0], row[1], row[2], row[3]) for row in rows]

    async def states(self, document_id: UUID) -> dict[UUID, IndexState]:
        """그 문서의 색인 상태를 판 ID로 묶어 낸다. 물러난 판도 든다. 건설 중인 판에 `pending`이
        없으면 작업이 끝나는 순간 그 판이 현재 판이 되어 옛 판이 물러나기 때문이다."""
        found: dict[UUID, IndexState] = {}
        async with self.unit_of_work.begin() as transaction:
            for version in await transaction.catalog.list_index_versions(self.knowledge_base.id):
                state = await transaction.index.get_state(document_id, version.id)
                if state is not None:
                    found[version.id] = state
        return found

    async def job_statuses(self, document_id: UUID) -> list[str]:
        async with self.engine.connect() as connection:
            rows = await connection.execute(
                sa.text("SELECT status FROM jobs WHERE document_id = :document ORDER BY id"),
                {"document": document_id},
            )
            return [row[0] for row in rows]

    async def make_tombstone(self, document_id: UUID) -> None:
        """정리 작업이 물리 삭제한 모양을 만든다. 문서 행만 남고 조각, 보관 조각, 색인 상태, 작업,
        파싱 결과가 없으며 `deleted_at`과 `purged_at`이 있다. core에는 정리 작업이 없어 시험이
        데이터베이스에 직접 만든다."""
        async with self.engine.begin() as connection:
            for table in ("chunks", "archived_chunks", "document_index_states", "jobs"):
                await connection.execute(
                    sa.text(f"DELETE FROM {table} WHERE document_id = :document"),
                    {"document": document_id},
                )
            await connection.execute(
                sa.text("DELETE FROM document_contents WHERE document_id = :document"),
                {"document": document_id},
            )
            await connection.execute(
                sa.text(
                    "UPDATE documents SET deleted_at = :now, purged_at = :now WHERE id = :document"
                ),
                {"now": self.clock[0], "document": document_id},
            )

    async def claim(self, worker_id: str = "worker-1", *, later: float = 0.0) -> Job:
        """작업 하나를 꺼낸다. `later`초 뒤의 시각에서 꺼내면 임대가 끝난 작업도 꺼낸다.

        꺼내기는 `FOR UPDATE SKIP LOCKED`라서, 처리 중인 작업의 임대 연장 트랜잭션이 그 행을 잠근
        순간에 부르면 행을 건너뛰어 아무것도 꺼내지 못한다. 그 순간은 짧으므로 기한 안에서 다시
        시도한다. 꺼낼 작업이 정말 없으면 기한이 지나 실패한다."""
        when = self.clock[0] + timedelta(seconds=later)
        deadline = time.monotonic() + CLAIM_RETRY_SECONDS
        while True:
            async with self.unit_of_work.begin() as transaction:
                job = await transaction.jobs.claim(worker_id, when, LEASE_SECONDS)
            if job is not None:
                return job
            assert time.monotonic() < deadline, f"{CLAIM_RETRY_SECONDS}초 안에 꺼낼 작업이 없었다"
            await asyncio.sleep(CLAIM_RETRY_PAUSE_SECONDS)

    async def add_building_version(self) -> IndexVersion:
        """같은 지식베이스의 건설 중인 판 하나를 더한다."""
        version = replace(
            make_index_version(self.knowledge_base, IndexVersionStatus.BUILDING),
            embedding_dimensions=DIMENSIONS,
        )
        async with self.unit_of_work.begin() as transaction:
            await transaction.catalog.add_index_version(version)
            await transaction.index.create_version_index(version)
        return version

    async def keep_pending(self, version: IndexVersion) -> None:
        """자리 표시 문서 하나를 이 판에서 계속 `pending`으로 둔다. 건설 중인 판은 `pending`이
        없으면 전환 검사가 도는 첫 순간(색인, 삭제 등)에 현재 판이 되므로, 전환하지 않는 건설 중인
        판이 필요한 시험이 쓴다. 자리 표시 문서의 작업은 지워 아무도 그 문서를 색인하지 않는다."""
        held = await self.ingest(docx_bytes("자리 표시", "전환을 막는 문서다."), "자리표시.docx")
        async with self.unit_of_work.begin() as transaction:
            await transaction.jobs.delete_queued(held.document_id)
            await transaction.index.save_state(
                IndexState(
                    document_id=held.document_id,
                    index_version_id=version.id,
                    status=IndexStateStatus.PENDING,
                    chunk_count=0,
                    built_content_hash=None,
                    error_code=None,
                    updated_at=self.clock[0],
                )
            )

    async def add_group(self, name: str) -> Group:
        """그룹을 더한다. 어느 지식베이스에도 들지 않은 채다."""
        group = Group(new_id(), name, "")
        async with self.unit_of_work.begin() as transaction:
            await transaction.catalog.add_group(group)
        return group

    async def add_knowledge_base(
        self, name: str, *groups: Group
    ) -> tuple[KnowledgeBase, IndexVersion]:
        """첫 현재 판이 있는 지식베이스를 `Catalog`로 만들고 그룹을 넣는다. 끝점은 이 세계의
        스텁이다."""
        knowledge_base = replace(make_knowledge_base(name), embedding_dimensions=DIMENSIONS)
        version = replace(
            make_index_version(knowledge_base, IndexVersionStatus.CURRENT),
            embedding_dimensions=DIMENSIONS,
        )
        async with self.unit_of_work.begin() as transaction:
            await transaction.catalog.add_knowledge_base(knowledge_base)
            for group in groups:
                await transaction.catalog.add_group_to_knowledge_base(knowledge_base.id, group.id)
            await transaction.catalog.add_index_version(version)
            await transaction.index.create_version_index(version)
            await transaction.catalog.switch_current_version(knowledge_base.id, version.id)
        return knowledge_base, version

    async def chunk_texts(
        self, document_id: UUID, version: IndexVersion | None = None
    ) -> list[str]:
        target = (version or self.version).id
        async with self.engine.connect() as connection:
            rows = await connection.execute(
                sa.text(
                    "SELECT text FROM chunks WHERE document_id = :document AND"
                    " index_version_id = :version ORDER BY ordinal"
                ),
                {"document": document_id, "version": target},
            )
            return [row[0] for row in rows]


def stub_client_for(stub: TeiStub) -> Callable[[str], httpx.AsyncClient]:
    def make(_endpoint: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
        )

    return make


async def build_pipeline(engine: AsyncEngine, data_dir: Path) -> Pipeline:
    # 실제 Kiwi의 첫 호출은 모델을 읽느라 이 PC에서 2.6~5.3초(부하에 따라) 걸리고 그동안 이벤트
    # 루프가 멈춘다.
    # 시험이 `process_job`을 직접 부르면 이 적재가 시험의 시간 단언 안으로 들어가, 상한 5초를
    # 단독 실행 열 번 가운데 한 번 넘겼다. 시험이 재기 전에 여기서 적재해 둔다(프로세스마다 한 번).
    tokenize_keywords("준비")
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    knowledge_base = replace(
        make_knowledge_base("default", is_default=True), embedding_dimensions=DIMENSIONS
    )
    version = replace(
        make_index_version(knowledge_base, IndexVersionStatus.CURRENT),
        embedding_dimensions=DIMENSIONS,
    )
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_knowledge_base(knowledge_base)
        await transaction.catalog.add_group_to_knowledge_base(knowledge_base.id, group.id)
        await transaction.catalog.add_index_version(version)
        await transaction.index.create_version_index(version)
        await transaction.catalog.switch_current_version(knowledge_base.id, version.id)
    stub = TeiStub(dimensions=DIMENSIONS)
    return Pipeline(
        unit_of_work=unit_of_work,
        engine=engine,
        blob_store=LocalBlobStore(data_dir),
        stub=stub,
        pool=TeiEmbedderPool(stub_client_for(stub), batch_size=32),
        parse_runner=SubprocessParseRunner(
            ParserRegistry(discover_parser_specs()),
            timeout_seconds=60,
            memory_mb=2048,
            max_pages=1000,
            max_text_mb=64,
            max_unzipped_mb=512,
            max_compression_ratio=100,
        ),
        source=source,
        group=group,
        knowledge_base=knowledge_base,
        version=version,
    )
