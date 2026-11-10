"""PostgreSQL 작업 단위와 `Catalog`·`VectorIndex` 어댑터(명세 "포트 열셋과 그 값").

블록을 예외 없이 나가면 커밋이고 예외로 나가면 롤백이다. `catalog` 와 `index` 는 한 연결의 한
트랜잭션을 공유한다. 이 시험은 `migrate` 를 거치지 않은 빈 데이터베이스에 스키마만 올려 쓴다.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import LiteralString

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.migrate import upgrade_to_head
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.postgres.vector_index import version_index_name
from rag_engine.domain.entities import (
    ChunkingConfig,
    Group,
    IndexVersion,
    IndexVersionStatus,
    KnowledgeBase,
    Source,
    SourceKind,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import LockMode

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
CHUNKING = ChunkingConfig(strategy="structure_first", max_tokens=512, overlap_tokens=64)


@pytest.fixture
async def engine(empty_database_url: str) -> AsyncIterator[AsyncEngine]:
    await asyncio.to_thread(upgrade_to_head, empty_database_url)
    created = create_engine(empty_database_url)
    try:
        yield created
    finally:
        await created.dispose()


def _knowledge_base(name: str = "kb", *, is_default: bool = False) -> KnowledgeBase:
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


def _version(knowledge_base: KnowledgeBase, status: IndexVersionStatus) -> IndexVersion:
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


def _names(database_url: str, query: LiteralString) -> set[str]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        return {name for (name,) in connection.execute(query).fetchall()}


class _Abort(Exception):
    pass


async def test_블록을_예외_없이_나가면_커밋한다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)

    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(Group(new_id(), "기획팀", ""))

    async with unit_of_work.begin() as transaction:
        assert await transaction.catalog.get_group("기획팀") is not None


async def test_블록을_예외로_나가면_롤백한다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)

    with pytest.raises(_Abort):
        async with unit_of_work.begin() as transaction:
            await transaction.catalog.add_group(Group(new_id(), "기획팀", ""))
            raise _Abort

    async with unit_of_work.begin() as transaction:
        assert await transaction.catalog.get_group("기획팀") is None


async def test_catalog와_index는_한_트랜잭션에_들어_함께_롤백된다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    knowledge_base = _knowledge_base()
    version = _version(knowledge_base, IndexVersionStatus.BUILDING)

    with pytest.raises(_Abort):
        async with unit_of_work.begin() as transaction:
            await transaction.catalog.add_knowledge_base(knowledge_base)
            await transaction.catalog.add_index_version(version)
            await transaction.index.create_version_index(version)
            raise _Abort

    assert _names(empty_database_url, "SELECT name FROM knowledge_bases") == set()
    assert _names(empty_database_url, "SELECT indexname FROM pg_indexes") >= {"ix_chunks_keywords"}
    assert version_index_name(version.id) not in _names(
        empty_database_url, "SELECT indexname FROM pg_indexes"
    )


async def test_판의_HNSW_부분_색인은_판마다_코사인_거리로_만들어져_카탈로그에_있다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    knowledge_base = _knowledge_base()
    version = _version(knowledge_base, IndexVersionStatus.BUILDING)

    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_knowledge_base(knowledge_base)
        await transaction.catalog.add_index_version(version)
        await transaction.index.create_version_index(version)

    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s",
            [version_index_name(version.id)],
        ).fetchall()
    assert len(rows) == 1
    definition: str = rows[0][0]
    assert "USING hnsw" in definition
    assert "(embedding)::vector(1024)" in definition
    assert "vector_cosine_ops" in definition
    assert str(version.id) in definition


async def test_카탈로그는_원천과_그룹과_지식베이스를_이름으로_찾는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    knowledge_base = _knowledge_base("default", is_default=True)
    group = Group(new_id(), "default", "")

    async with unit_of_work.begin() as transaction:
        catalog = transaction.catalog
        await catalog.add_source(Source(new_id(), "default", SourceKind.PUSH))
        await catalog.add_group(group)
        await catalog.add_knowledge_base(knowledge_base)
        await catalog.add_group_to_knowledge_base(knowledge_base.id, group.id)

    async with unit_of_work.begin() as transaction:
        catalog = transaction.catalog
        source = await catalog.get_source("default")
        assert source is not None
        assert source.kind is SourceKind.PUSH
        assert await catalog.get_source("없는 원천") is None
        assert await catalog.get_group("default") == group
        assert await catalog.get_knowledge_base("default") == knowledge_base
        assert await catalog.list_knowledge_bases() == [knowledge_base]
        assert await catalog.list_knowledge_bases_of_group(group.id) == [knowledge_base]


async def test_같은_이름을_다시_더해도_먼저_있던_행이_남는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    first = Group(new_id(), "default", "처음")

    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(first)
        await transaction.catalog.add_group(Group(new_id(), "default", "나중"))

    async with unit_of_work.begin() as transaction:
        assert await transaction.catalog.get_group("default") == first


async def test_지식베이스_행을_잠그면_잠근_뒤의_행을_ID_순으로_낸다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    first, second = _knowledge_base("a"), _knowledge_base("b")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_knowledge_base(second)
        await transaction.catalog.add_knowledge_base(first)

    async with unit_of_work.begin() as transaction:
        locked_for_share = await transaction.catalog.lock_knowledge_bases(
            [second.id, first.id], LockMode.SHARE
        )
        locked_for_update = await transaction.catalog.lock_knowledge_bases(
            [second.id, first.id], LockMode.UPDATE
        )

    assert [row.id for row in locked_for_update] == sorted([first.id, second.id])
    assert locked_for_share == locked_for_update


async def test_첫_판으로_바꾸면_현재_판_참조와_상태가_함께_바뀐다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    knowledge_base = _knowledge_base()
    version = _version(knowledge_base, IndexVersionStatus.BUILDING)

    async with unit_of_work.begin() as transaction:
        catalog = transaction.catalog
        await catalog.add_knowledge_base(knowledge_base)
        await catalog.add_index_version(version)
        assert await catalog.list_live_index_versions(knowledge_base.id) == [version]
        await catalog.switch_current_version(knowledge_base.id, version.id)

    async with unit_of_work.begin() as transaction:
        reloaded = await transaction.catalog.get_knowledge_base("kb")
        live = await transaction.catalog.list_live_index_versions(knowledge_base.id)
    assert reloaded == replace(knowledge_base, current_index_version_id=version.id)
    assert live == [replace(version, status=IndexVersionStatus.CURRENT)]
