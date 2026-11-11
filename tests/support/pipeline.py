"""수집에서 색인까지 이어 보는 시험 세계(티켓 07).

실제 테스트 PostgreSQL 위에 원천, 그룹, 지식베이스(현재 판 하나)를 세우고, 실제 `ingest_document`로
DOCX를 넣고, 실제 파서 자식 프로세스와 실제 청커·Kiwi로 `index_document`를 돌린다. 임베딩 서버만
`TeiStub`이다(명세 Testing Decisions). 시험은 이 세계에 끼어들 곳(임베딩 직전)만 바꿔 끼운다.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import httpx
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_index_version, make_knowledge_base, seed_source_and_group
from tests.support.tei_stub import TeiStub

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.chunking import chunker_for
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.parsers.registry import ParserRegistry, discover_parser_specs
from rag_engine.adapters.parsers.runner import SubprocessParseRunner
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.tei import TeiEmbedderPool
from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.app.ingest import IngestRequest, IngestResult, ingest_document
from rag_engine.domain.entities import (
    Group,
    IndexVersion,
    IndexVersionStatus,
    Job,
    KnowledgeBase,
    Source,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.parsing import ParseRunner
from rag_engine.domain.ports import EmbedderFor

DIMENSIONS = 16
LEASE_SECONDS = 600.0
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


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
    ) -> IndexDocumentDeps:
        return IndexDocumentDeps(
            unit_of_work=self.unit_of_work,
            blob_store=self.blob_store,
            parse_runner=parse_runner or self.parse_runner,
            embedder_for=embedder_for or self.pool,
            chunker_for=chunker_for,
            tokenize_keywords=tokenize_keywords,
            now=lambda: self.clock[0],
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

    async def claim(self, worker_id: str = "worker-1", *, later: float = 0.0) -> Job:
        """작업 하나를 꺼낸다. `later`초 뒤의 시각에서 꺼내면 임대가 끝난 작업도 꺼낸다."""
        when = self.clock[0] + timedelta(seconds=later)
        async with self.unit_of_work.begin() as transaction:
            job = await transaction.jobs.claim(worker_id, when, LEASE_SECONDS)
        assert job is not None
        return job

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
