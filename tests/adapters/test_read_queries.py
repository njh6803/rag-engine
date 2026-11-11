"""읽기 도구가 쓰는 조회(티켓 09): 지식베이스의 문서 수, 문서의 판별 조각 수, 원천과 그룹의
식별자 조회."""

from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import (
    NOW,
    make_document,
    make_index_version,
    make_knowledge_base,
    seed_source_and_group,
)

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import (
    BlockKind,
    Chunk,
    ChunkLocation,
    Document,
    DocumentStatus,
    Group,
    IndexVersion,
    IndexVersionStatus,
    KnowledgeBase,
    Source,
)
from rag_engine.domain.identifiers import new_id

DIMENSIONS = 3


async def _knowledge_base(
    unit_of_work: PostgresUnitOfWork, name: str, *groups: Group
) -> tuple[KnowledgeBase, IndexVersion]:
    knowledge_base = replace(make_knowledge_base(name), embedding_dimensions=DIMENSIONS)
    version = replace(
        make_index_version(knowledge_base, IndexVersionStatus.CURRENT),
        embedding_dimensions=DIMENSIONS,
    )
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_knowledge_base(knowledge_base)
        for group in groups:
            await transaction.catalog.add_group_to_knowledge_base(knowledge_base.id, group.id)
        await transaction.catalog.add_index_version(version)
        await transaction.index.create_version_index(version)
    return knowledge_base, version


async def _add(
    unit_of_work: PostgresUnitOfWork, source: Source, group: Group, key: str, **overrides: object
) -> Document:
    document = make_document(source, group, key=key, **overrides)
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(document)
    return document


async def test_지식베이스의_문서_수는_그_그룹_집합의_지워지지_않은_문서만_센다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    other = Group(new_id(), "다른", "")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(other)
    knowledge_base, _ = await _knowledge_base(unit_of_work, "한쪽", group)
    empty, _ = await _knowledge_base(unit_of_work, "빈", other)
    await _add(unit_of_work, source, group, "하나.docx")
    await _add(unit_of_work, source, group, "둘.docx", status=DocumentStatus.PARSED)
    await _add(unit_of_work, source, group, "지움.docx", deleted_at=NOW)
    await _add(unit_of_work, source, other, "다른.docx")

    async with unit_of_work.begin() as transaction:
        counts = [
            await transaction.documents.count_live_documents(knowledge_base.id),
            await transaction.documents.count_live_documents(empty.id),
        ]

    assert counts == [2, 1]


async def test_문서의_조각_수는_판마다_센다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    _, first = await _knowledge_base(unit_of_work, "첫째", group)
    _, second = await _knowledge_base(unit_of_work, "둘째", group)
    document = await _add(unit_of_work, source, group, "규정.docx")

    def chunk(version: IndexVersion, ordinal: int) -> Chunk:
        return Chunk(
            id=new_id(),
            document_id=document.id,
            index_version_id=version.id,
            ordinal=ordinal,
            text="글",
            token_count=1,
            location=ChunkLocation(None, (), BlockKind.PARAGRAPH, (0, 0)),
            embedding=(1.0, 0.0, 0.0),
            keyword_text="글",
            source_content_hash=document.content_hash,
            group_id=group.id,
            updated_at=NOW,
            effective_date=None,
            access_groups=(),
        )

    async with unit_of_work.begin() as transaction:
        await transaction.index.replace_chunks(
            document.id, first.id, [chunk(first, 0), chunk(first, 1), chunk(first, 2)]
        )
        await transaction.index.replace_chunks(document.id, second.id, [chunk(second, 0)])

    async with unit_of_work.begin() as transaction:
        counts = [
            await transaction.index.count_chunks(document.id, first.id),
            await transaction.index.count_chunks(document.id, second.id),
            await transaction.index.count_chunks(document.id, new_id()),
        ]

    assert counts == [3, 1, 0]


async def test_원천과_그룹을_식별자로_찾고_없으면_None이다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work, "인사")

    async with unit_of_work.begin() as transaction:
        found = (
            await transaction.catalog.get_source_by_id(source.id),
            await transaction.catalog.get_group_by_id(group.id),
        )
        missing = (
            await transaction.catalog.get_source_by_id(new_id()),
            await transaction.catalog.get_group_by_id(new_id()),
        )

    assert (found, missing) == ((source, group), (None, None))
