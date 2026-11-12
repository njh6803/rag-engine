"""지식베이스 관리 API의 응답 모델(명세 "관리 API"). 경로의 `v1`이 판이다(원칙 VII).

칸을 더하는 것은 같은 판이고 칸을 지우거나 뜻을 바꾸면 `v2`다. 시각은 UTC `Z`로 낸다(ADR 0015).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rag_engine.app.admin_knowledge_bases import (
    BuildProgress,
    KnowledgeBaseDetail,
    KnowledgeBaseReport,
)
from rag_engine.app.reindex import ReindexStarted
from rag_engine.domain.entities import IndexVersion, IndexVersionStatus
from rag_engine.server.admin_models import UtcTime


class ChunkingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: str
    max_tokens: int
    overlap_tokens: int


class IndexVersionResponse(BaseModel):
    """색인 판. 요소 넷은 스키마 판, 임베딩 모델과 차원, 청킹 설정 해시, 토크나이저 판이다."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    status: IndexVersionStatus
    schema_version: int
    embedding_endpoint: str
    embedding_model: str
    embedding_dimensions: int
    chunking: ChunkingResponse
    chunking_hash: str
    tokenizer_version: str
    created_at: UtcTime
    retired_at: UtcTime | None

    @staticmethod
    def of(version: IndexVersion) -> "IndexVersionResponse":
        return IndexVersionResponse(
            id=version.id,
            status=version.status,
            schema_version=version.schema_version,
            embedding_endpoint=version.embedding_endpoint,
            embedding_model=version.embedding_model,
            embedding_dimensions=version.embedding_dimensions,
            chunking=ChunkingResponse(
                strategy=version.chunking.strategy,
                max_tokens=version.chunking.max_tokens,
                overlap_tokens=version.chunking.overlap_tokens,
            ),
            chunking_hash=version.chunking_hash,
            tokenizer_version=version.tokenizer_version,
            created_at=version.created_at,
            retired_at=version.retired_at,
        )


class BuildProgressResponse(BaseModel):
    """건설 중인 판의 진행. 색인 상태 행을 상태마다 센 값이다. 재색인을 시작한 뒤에 지식베이스에 든
    문서는 건설 중인 판에 색인 상태가 없어 세지 않는다."""

    model_config = ConfigDict(frozen=True)

    index_version_id: UUID
    total: int
    pending: int
    indexed: int
    failed: int

    @staticmethod
    def of(progress: BuildProgress) -> "BuildProgressResponse":
        return BuildProgressResponse(
            index_version_id=progress.version.id,
            total=progress.total,
            pending=progress.pending,
            indexed=progress.indexed,
            failed=progress.failed,
        )


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    document_count: int = Field(description="그룹 집합에 드는 그룹의, 지워지지 않은 문서 수")
    current_index_version: IndexVersionResponse | None = Field(
        description="현재 색인 판. 아직 없으면 null"
    )
    reindex_needed: bool = Field(
        description="지식베이스의 지금 설정에서 계산한 판 요소가 현재 판과 다르면 참"
    )
    building: BuildProgressResponse | None = Field(
        description="건설 중인 판의 진행. 재색인 중이 아니면 null"
    )

    @staticmethod
    def of(report: KnowledgeBaseReport) -> "KnowledgeBaseResponse":
        return KnowledgeBaseResponse(
            name=report.knowledge_base.name,
            description=report.knowledge_base.description,
            document_count=report.document_count,
            current_index_version=None
            if report.current is None
            else IndexVersionResponse.of(report.current),
            reindex_needed=report.reindex_needed,
            building=None if report.building is None else BuildProgressResponse.of(report.building),
        )


class KnowledgeBaseListResponse(BaseModel):
    knowledge_bases: list[KnowledgeBaseResponse]


class KnowledgeBaseSettingsResponse(BaseModel):
    """지식베이스의 지금 설정. 다음 재색인이 새 판에 적는 값이다."""

    model_config = ConfigDict(frozen=True)

    embedding_endpoint: str
    embedding_model: str
    embedding_dimensions: int
    reranker_endpoint: str | None
    reranker_model: str | None
    chunking: ChunkingResponse


class KnowledgeBaseDetailResponse(KnowledgeBaseResponse):
    settings: KnowledgeBaseSettingsResponse
    index_versions: list[IndexVersionResponse] = Field(
        description="물러난 판까지 모든 색인 판. 최근 순"
    )

    @staticmethod
    def detail_of(detail: KnowledgeBaseDetail) -> "KnowledgeBaseDetailResponse":
        base = KnowledgeBaseResponse.of(detail.report)
        knowledge_base = detail.report.knowledge_base
        return KnowledgeBaseDetailResponse(
            **base.model_dump(),
            settings=KnowledgeBaseSettingsResponse(
                embedding_endpoint=knowledge_base.embedding_endpoint,
                embedding_model=knowledge_base.embedding_model,
                embedding_dimensions=knowledge_base.embedding_dimensions,
                reranker_endpoint=knowledge_base.reranker_endpoint,
                reranker_model=knowledge_base.reranker_model,
                chunking=ChunkingResponse(
                    strategy=knowledge_base.chunking.strategy,
                    max_tokens=knowledge_base.chunking.max_tokens,
                    overlap_tokens=knowledge_base.chunking.overlap_tokens,
                ),
            ),
            index_versions=[IndexVersionResponse.of(version) for version in detail.versions],
        )


class ReindexResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_version_id: UUID = Field(description="새로 만든 건설 중인 색인 판의 ID")
    jobs_enqueued: int = Field(
        description="새로 넣은 작업 수. 대기 작업이 이미 있던 문서는 그 작업이 맡아 세지 않는다"
    )

    @staticmethod
    def of(started: ReindexStarted) -> "ReindexResponse":
        return ReindexResponse(
            index_version_id=started.index_version_id, jobs_enqueued=started.jobs_enqueued
        )
