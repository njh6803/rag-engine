"""기본 레코드 보장(명세 "관리 명령"의 `migrate`). 마이그레이션 뒤 기본 원천·그룹·지식베이스와 첫
현재 색인 판이 설정값으로 있게 한다. 멱등이다.

지식베이스 행을 `FOR UPDATE`로 잠근 뒤(없으면 만든 뒤 잠근다) 쓴다. 겹쳐 돌아도 같은 결과로 모인다.
"""

from dataclasses import dataclass, replace
from datetime import datetime

from rag_engine.domain.entities import (
    MAX_EMBEDDING_DIMENSIONS,
    ChunkingConfig,
    Group,
    IndexVersion,
    IndexVersionStatus,
    KnowledgeBase,
    Source,
    SourceKind,
)
from rag_engine.domain.errors import ConfigurationError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import Catalog, ComputeIndexElements, LockMode, UnitOfWork

DEFAULT_NAME = "default"


@dataclass(frozen=True, slots=True)
class DefaultKnowledgeBaseSettings:
    """기본 지식베이스를 만드는 설정(`RAG_DEFAULT_*`). 리랭커가 없으면 끝점과 모델이 모두
    `None`이다."""

    embedding_url: str
    embedding_model: str
    embedding_dimensions: int
    reranker_url: str | None
    reranker_model: str | None
    chunking: ChunkingConfig


async def ensure_default_records(
    unit_of_work: UnitOfWork,
    settings: DefaultKnowledgeBaseSettings,
    compute_elements: ComputeIndexElements,
    now: datetime,
) -> None:
    if settings.embedding_dimensions > MAX_EMBEDDING_DIMENSIONS:
        raise ConfigurationError(
            f"임베딩 차원은 {MAX_EMBEDDING_DIMENSIONS} 이하여야 한다"
            f"(설정은 {settings.embedding_dimensions})"
        )
    elements = compute_elements(
        settings.embedding_model, settings.embedding_dimensions, settings.chunking
    )
    async with unit_of_work.begin() as transaction:
        catalog = transaction.catalog
        await catalog.add_source(Source(new_id(), DEFAULT_NAME, SourceKind.PUSH))
        await catalog.add_group(Group(new_id(), DEFAULT_NAME, ""))
        await catalog.add_knowledge_base(_new_knowledge_base(settings))
        knowledge_base = await _lock_default_knowledge_base(catalog)
        group = await catalog.get_group(DEFAULT_NAME)
        if group is None:
            raise RuntimeError("기본 그룹이 없다")

        wanted = _with_settings(knowledge_base, settings)
        if wanted != knowledge_base:
            await catalog.update_knowledge_base(wanted)
        await catalog.add_group_to_knowledge_base(knowledge_base.id, group.id)
        await _follow_moved_endpoint(catalog, knowledge_base, settings)
        if knowledge_base.current_index_version_id is None:
            version = IndexVersion(
                id=new_id(),
                knowledge_base_id=knowledge_base.id,
                schema_version=elements.schema_version,
                embedding_endpoint=settings.embedding_url,
                embedding_model=elements.embedding_model,
                embedding_dimensions=elements.embedding_dimensions,
                chunking=settings.chunking,
                chunking_hash=elements.chunking_hash,
                tokenizer_version=elements.tokenizer_version,
                status=IndexVersionStatus.BUILDING,
                created_at=now,
                retired_at=None,
            )
            await catalog.add_index_version(version)
            await catalog.switch_current_version(knowledge_base.id, version.id)
            # 판 행을 만드는 작업 단위가 조각 표에 쓸 것을 다 쓴 뒤 커밋 직전에 만든다.
            await transaction.index.create_version_index(version)


def _new_knowledge_base(settings: DefaultKnowledgeBaseSettings) -> KnowledgeBase:
    return KnowledgeBase(
        id=new_id(),
        name=DEFAULT_NAME,
        description="",
        embedding_endpoint=settings.embedding_url,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        reranker_endpoint=settings.reranker_url,
        reranker_model=settings.reranker_model,
        chunking=settings.chunking,
        current_index_version_id=None,
        is_default=True,
    )


def _with_settings(
    knowledge_base: KnowledgeBase, settings: DefaultKnowledgeBaseSettings
) -> KnowledgeBase:
    return replace(
        knowledge_base,
        embedding_endpoint=settings.embedding_url,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        reranker_endpoint=settings.reranker_url,
        reranker_model=settings.reranker_model,
        chunking=settings.chunking,
    )


async def _lock_default_knowledge_base(catalog: Catalog) -> KnowledgeBase:
    existing = await catalog.get_knowledge_base(DEFAULT_NAME)
    if existing is None:
        raise RuntimeError("기본 지식베이스가 없다")
    (locked,) = await catalog.lock_knowledge_bases([existing.id], LockMode.UPDATE)
    return locked


async def _follow_moved_endpoint(
    catalog: Catalog, knowledge_base: KnowledgeBase, settings: DefaultKnowledgeBaseSettings
) -> None:
    """임베딩 모델과 차원이 설정과 같고 끝점만 다른 살아 있는 판(건설 중인 판 포함)의 끝점을 고친다.
    같은 모델이 다른 주소로 옮긴 것이라 재색인이 아니다."""
    for version in await catalog.list_live_index_versions(knowledge_base.id):
        same_model = (
            version.embedding_model == settings.embedding_model
            and version.embedding_dimensions == settings.embedding_dimensions
        )
        if same_model and version.embedding_endpoint != settings.embedding_url:
            await catalog.update_index_version_endpoint(version.id, settings.embedding_url)
