"""`Catalog` 어댑터. 원천, 그룹, 지식베이스(그룹과의 다대다 포함), 색인 판 레코드를 맡는다(명세
"포트 열셋과 그 값"). 작업 단위가 연 연결 위에서 돈다."""

from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from rag_engine.adapters.postgres import tables
from rag_engine.domain.entities import (
    ChunkingConfig,
    Group,
    IndexVersion,
    IndexVersionStatus,
    KnowledgeBase,
    Source,
    SourceKind,
)
from rag_engine.domain.ports import LockMode

_LIVE_STATUSES: Final = (IndexVersionStatus.CURRENT.value, IndexVersionStatus.BUILDING.value)


def _knowledge_base(row: sa.RowMapping) -> KnowledgeBase:
    return KnowledgeBase(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        embedding_endpoint=row["embedding_endpoint"],
        embedding_model=row["embedding_model"],
        embedding_dimensions=row["embedding_dimensions"],
        reranker_endpoint=row["reranker_endpoint"],
        reranker_model=row["reranker_model"],
        chunking=ChunkingConfig(
            strategy=row["chunking_strategy"],
            max_tokens=row["chunk_tokens"],
            overlap_tokens=row["chunk_overlap_tokens"],
        ),
        current_index_version_id=row["current_index_version_id"],
        is_default=row["is_default"],
    )


def _knowledge_base_values(knowledge_base: KnowledgeBase) -> dict[str, object]:
    """이름과 현재 판 참조를 뺀 칸. 이름은 바꾸지 않고, 현재 판 참조는 판 전환이 쓴다."""
    return {
        "description": knowledge_base.description,
        "embedding_endpoint": knowledge_base.embedding_endpoint,
        "embedding_model": knowledge_base.embedding_model,
        "embedding_dimensions": knowledge_base.embedding_dimensions,
        "reranker_endpoint": knowledge_base.reranker_endpoint,
        "reranker_model": knowledge_base.reranker_model,
        "chunking_strategy": knowledge_base.chunking.strategy,
        "chunk_tokens": knowledge_base.chunking.max_tokens,
        "chunk_overlap_tokens": knowledge_base.chunking.overlap_tokens,
        "is_default": knowledge_base.is_default,
    }


def _chunking_config(chunking: ChunkingConfig) -> dict[str, object]:
    return {
        "strategy": chunking.strategy,
        "max_tokens": chunking.max_tokens,
        "overlap_tokens": chunking.overlap_tokens,
    }


def _index_version(row: sa.RowMapping) -> IndexVersion:
    config: Mapping[str, object] = row["chunking_config"]
    strategy, max_tokens, overlap_tokens = (
        config["strategy"],
        config["max_tokens"],
        config["overlap_tokens"],
    )
    if (
        not isinstance(strategy, str)
        or not isinstance(max_tokens, int)
        or not isinstance(overlap_tokens, int)
    ):
        raise RuntimeError("색인 판의 청킹 설정 모양이 어긋난다")
    return IndexVersion(
        id=row["id"],
        knowledge_base_id=row["knowledge_base_id"],
        schema_version=row["schema_version"],
        embedding_endpoint=row["embedding_endpoint"],
        embedding_model=row["embedding_model"],
        embedding_dimensions=row["embedding_dimensions"],
        chunking=ChunkingConfig(strategy, max_tokens, overlap_tokens),
        chunking_hash=row["chunking_hash"],
        tokenizer_version=row["tokenizer_version"],
        status=IndexVersionStatus(row["status"]),
        created_at=row["created_at"],
        retired_at=row["retired_at"],
    )


class PostgresCatalog:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add_source(self, source: Source) -> None:
        await self._connection.execute(
            insert(tables.sources)
            .values(id=source.id, name=source.name, kind=source.kind.value)
            .on_conflict_do_nothing(index_elements=["name"])
        )

    async def get_source(self, name: str) -> Source | None:
        result = await self._connection.execute(
            sa.select(tables.sources).where(tables.sources.c.name == name)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return Source(id=row["id"], name=row["name"], kind=SourceKind(row["kind"]))

    async def add_group(self, group: Group) -> None:
        await self._connection.execute(
            insert(tables.groups)
            .values(id=group.id, name=group.name, description=group.description)
            .on_conflict_do_nothing(index_elements=["name"])
        )

    async def get_group(self, name: str) -> Group | None:
        return await self._group_where(tables.groups.c.name == name)

    async def get_source_by_id(self, source_id: UUID) -> Source | None:
        result = await self._connection.execute(
            sa.select(tables.sources).where(tables.sources.c.id == source_id)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return Source(id=row["id"], name=row["name"], kind=SourceKind(row["kind"]))

    async def get_group_by_id(self, group_id: UUID) -> Group | None:
        return await self._group_where(tables.groups.c.id == group_id)

    async def _group_where(self, condition: sa.ColumnElement[bool]) -> Group | None:
        result = await self._connection.execute(sa.select(tables.groups).where(condition))
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return Group(id=row["id"], name=row["name"], description=row["description"])

    async def add_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        await self._connection.execute(
            insert(tables.knowledge_bases)
            .values(
                id=knowledge_base.id,
                name=knowledge_base.name,
                **_knowledge_base_values(knowledge_base),
            )
            .on_conflict_do_nothing(index_elements=["name"])
        )

    async def update_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        await self._connection.execute(
            sa.update(tables.knowledge_bases)
            .where(tables.knowledge_bases.c.id == knowledge_base.id)
            .values(**_knowledge_base_values(knowledge_base))
        )

    async def add_group_to_knowledge_base(self, knowledge_base_id: UUID, group_id: UUID) -> None:
        await self._connection.execute(
            insert(tables.knowledge_base_groups)
            .values(knowledge_base_id=knowledge_base_id, group_id=group_id)
            .on_conflict_do_nothing()
        )

    async def get_knowledge_base(self, name: str) -> KnowledgeBase | None:
        result = await self._connection.execute(
            sa.select(tables.knowledge_bases).where(tables.knowledge_bases.c.name == name)
        )
        row = result.mappings().one_or_none()
        return None if row is None else _knowledge_base(row)

    async def list_knowledge_bases(self) -> list[KnowledgeBase]:
        result = await self._connection.execute(
            sa.select(tables.knowledge_bases).order_by(tables.knowledge_bases.c.name)
        )
        return [_knowledge_base(row) for row in result.mappings()]

    async def list_knowledge_bases_of_group(self, group_id: UUID) -> list[KnowledgeBase]:
        result = await self._connection.execute(
            sa.select(tables.knowledge_bases)
            .join(
                tables.knowledge_base_groups,
                tables.knowledge_base_groups.c.knowledge_base_id == tables.knowledge_bases.c.id,
            )
            .where(tables.knowledge_base_groups.c.group_id == group_id)
            .order_by(tables.knowledge_bases.c.name)
        )
        return [_knowledge_base(row) for row in result.mappings()]

    async def lock_knowledge_bases(
        self, knowledge_base_ids: Sequence[UUID], mode: LockMode
    ) -> list[KnowledgeBase]:
        result = await self._connection.execute(
            sa.select(tables.knowledge_bases)
            .where(tables.knowledge_bases.c.id.in_(knowledge_base_ids))
            .order_by(tables.knowledge_bases.c.id)
            .with_for_update(read=mode is LockMode.SHARE)
        )
        return [_knowledge_base(row) for row in result.mappings()]

    async def list_live_index_versions(self, knowledge_base_id: UUID) -> list[IndexVersion]:
        result = await self._connection.execute(
            sa.select(tables.index_versions)
            .where(
                tables.index_versions.c.knowledge_base_id == knowledge_base_id,
                tables.index_versions.c.status.in_(_LIVE_STATUSES),
            )
            .order_by(tables.index_versions.c.id)
        )
        return [_index_version(row) for row in result.mappings()]

    async def add_index_version(self, version: IndexVersion) -> None:
        await self._connection.execute(
            sa.insert(tables.index_versions).values(
                id=version.id,
                knowledge_base_id=version.knowledge_base_id,
                schema_version=version.schema_version,
                embedding_endpoint=version.embedding_endpoint,
                embedding_model=version.embedding_model,
                embedding_dimensions=version.embedding_dimensions,
                chunking_config=_chunking_config(version.chunking),
                chunking_hash=version.chunking_hash,
                tokenizer_version=version.tokenizer_version,
                status=version.status.value,
                created_at=version.created_at,
                retired_at=version.retired_at,
            )
        )

    async def update_index_version_endpoint(self, version_id: UUID, endpoint: str) -> None:
        await self._connection.execute(
            sa.update(tables.index_versions)
            .where(tables.index_versions.c.id == version_id)
            .values(embedding_endpoint=endpoint)
        )

    async def switch_current_version(self, knowledge_base_id: UUID, new_version_id: UUID) -> None:
        old = await self._connection.scalar(
            sa.select(tables.knowledge_bases.c.current_index_version_id).where(
                tables.knowledge_bases.c.id == knowledge_base_id
            )
        )
        if old is not None and old != new_version_id:
            await self._connection.execute(
                sa.update(tables.index_versions)
                .where(tables.index_versions.c.id == old)
                .values(status=IndexVersionStatus.RETIRED.value, retired_at=sa.func.now())
            )
        await self._connection.execute(
            sa.update(tables.index_versions)
            .where(tables.index_versions.c.id == new_version_id)
            .values(status=IndexVersionStatus.CURRENT.value)
        )
        await self._connection.execute(
            sa.update(tables.knowledge_bases)
            .where(tables.knowledge_bases.c.id == knowledge_base_id)
            .values(current_index_version_id=new_version_id)
        )
