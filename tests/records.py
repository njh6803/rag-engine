"""시험이 함께 쓰는 도메인 레코드 빌더. 값은 시험이 덮어쓰고, 식별자는 UUIDv7으로 새로 만든다."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import psycopg

from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.domain.entities import (
    ChunkingConfig,
    Document,
    DocumentStatus,
    Group,
    IndexVersion,
    IndexVersionStatus,
    KnowledgeBase,
    Source,
    SourceKind,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.media_types import PDF_MIME
from rag_engine.domain.ports import UnitOfWork

NOW: Final = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
CHUNKING: Final = ChunkingConfig(strategy="structure_first", max_tokens=512, overlap_tokens=64)


def make_knowledge_base(name: str = "kb", *, is_default: bool = False) -> KnowledgeBase:
    return KnowledgeBase(
        id=new_id(),
        name=name,
        description="",
        embedding_endpoint="http://tei:80",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        reranker_endpoint=None,
        reranker_model=None,
        chunking=CHUNKING,
        current_index_version_id=None,
        is_default=is_default,
    )


def make_index_version(knowledge_base: KnowledgeBase, status: IndexVersionStatus) -> IndexVersion:
    elements = compute_index_elements(
        knowledge_base.embedding_model, knowledge_base.embedding_dimensions, CHUNKING
    )
    return IndexVersion(
        id=new_id(),
        knowledge_base_id=knowledge_base.id,
        schema_version=elements.schema_version,
        embedding_endpoint=knowledge_base.embedding_endpoint,
        embedding_model=elements.embedding_model,
        embedding_dimensions=elements.embedding_dimensions,
        chunking=CHUNKING,
        chunking_hash=elements.chunking_hash,
        tokenizer_version=elements.tokenizer_version,
        status=status,
        created_at=NOW,
        retired_at=None,
    )


def insert_chunk(
    database_url: str, document_id: UUID, index_version_id: UUID, group_id: UUID
) -> None:
    """조각 행 하나를 SQL로 직접 넣는다. 조각을 쓰는 어댑터(`replace_chunks`)는 아직 없다(07)."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO chunks (id, document_id, index_version_id, ordinal, text,"
            " token_count, location, embedding, keywords, source_content_hash, group_id,"
            " updated_at) VALUES (%s, %s, %s, 0, '글', 1, '{}', '[1,2,3]',"
            " to_tsvector('simple', '글'), 'h', %s, %s)",
            [new_id(), document_id, index_version_id, group_id, NOW],
        )


def make_document(
    source: Source, group: Group, key: str = "규정.pdf", **overrides: object
) -> Document:
    """받은 직후(`received`)의 새 문서. `overrides`는 칸 이름과 값이다."""
    document = Document(
        id=new_id(),
        source_id=source.id,
        key=key,
        group_id=group.id,
        title="규정",
        mime=PDF_MIME,
        size_bytes=10,
        content_hash="a" * 64,
        blob_path="blobs/doc/blob",
        metadata={"부서": "기획팀"},
        updated_at=NOW,
        effective_date=None,
        access_groups=(),
        status=DocumentStatus.RECEIVED,
        error_code=None,
        generation=1,
        deleted_at=None,
        purged_at=None,
        created_at=NOW,
        modified_at=NOW,
    )
    return replace(document, **overrides)


async def seed_source_and_group(
    unit_of_work: UnitOfWork, group_name: str = "default"
) -> tuple[Source, Group]:
    """원천 `default`와 그룹 하나를 만들어 낸다."""
    source = Source(new_id(), "default", SourceKind.PUSH)
    group = Group(new_id(), group_name, "")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_source(source)
        await transaction.catalog.add_group(group)
    return source, group
