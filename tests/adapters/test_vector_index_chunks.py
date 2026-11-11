"""`VectorIndex`와 `DocumentStore`의 07 몫(명세 "데이터 모델과 스키마", "검색 흐름").

조각 쓰기는 그 (문서, 판)의 옛 조각을 지우고 새 조각을 넣는다. 색인 상태와 파싱 결과는 덮어쓴다.
검색 질의는 벡터와 키워드 후보를 SQL 하나로 모아 RRF(`1/(60+순위)`의 합)로 합치고, 벡터 질의는 03이
만든 판의 HNSW 부분 색인을 탄다(같은 캐스트 `embedding::vector(D)`).
"""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
from sqlalchemy import Connection, event
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
    Block,
    BlockKind,
    Chunk,
    ChunkLocation,
    Document,
    DocumentContent,
    Group,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    SearchFilter,
    SearchQuery,
    Source,
)
from rag_engine.domain.identifiers import new_id

DIMENSIONS = 3


class _World:
    def __init__(
        self,
        unit_of_work: PostgresUnitOfWork,
        source: Source,
        group: Group,
        version: IndexVersion,
    ) -> None:
        self.unit_of_work = unit_of_work
        self.source = source
        self.group = group
        self.version = version

    async def document(self, key: str = "규정.docx", **overrides: object) -> Document:
        document = make_document(self.source, self.group, key=key, **overrides)
        async with self.unit_of_work.begin() as transaction:
            await transaction.documents.add(document)
        return document

    def chunk(
        self,
        document: Document,
        ordinal: int,
        text: str,
        vector: tuple[float, ...],
        keywords: str,
        *,
        version: IndexVersion | None = None,
    ) -> Chunk:
        return Chunk(
            id=new_id(),
            document_id=document.id,
            index_version_id=(version or self.version).id,
            ordinal=ordinal,
            text=text,
            token_count=3,
            location=ChunkLocation(
                page=None, section=("제1조",), block_kind=BlockKind.PARAGRAPH, block_range=(0, 0)
            ),
            embedding=vector,
            keyword_text=keywords,
            source_content_hash=document.content_hash,
            group_id=document.group_id,
            updated_at=document.updated_at,
            effective_date=None,
            access_groups=(),
        )

    async def write(self, document: Document, *chunks: Chunk) -> None:
        async with self.unit_of_work.begin() as transaction:
            await transaction.index.replace_chunks(document.id, self.version.id, chunks)

    def query(self, vector: tuple[float, ...], keywords: tuple[str, ...]) -> SearchQuery:
        return SearchQuery(
            knowledge_base_id=self.version.knowledge_base_id,
            index_version_id=self.version.id,
            dimensions=DIMENSIONS,
            vector=vector,
            keywords=keywords,
            candidates=10,
        )


async def _world(engine: AsyncEngine) -> _World:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    knowledge_base = replace(make_knowledge_base(), embedding_dimensions=DIMENSIONS)
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
    return _World(unit_of_work, source, group, version)


def _count(database_url: str, document_id: UUID) -> int:
    with psycopg.connect(database_url, autocommit=True) as connection:
        row = connection.execute(
            "SELECT count(*) FROM chunks WHERE document_id = %s", [document_id]
        ).fetchone()
    assert row is not None
    return row[0]


async def test_조각을_쓰면_옛_조각이_지워지고_새_조각만_남는다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        world.chunk(document, 0, "옛 글", (1.0, 0.0, 0.0), "옛"),
        world.chunk(document, 1, "옛 글 둘", (0.0, 1.0, 0.0), "옛"),
    )

    await world.write(document, world.chunk(document, 0, "새 글", (0.0, 0.0, 1.0), "새"))

    assert _count(empty_database_url, document.id) == 1
    async with world.unit_of_work.begin() as transaction:
        hits = await transaction.index.search_candidates(world.query((0.0, 0.0, 1.0), ()))
    assert [hit.text for hit in hits.hits] == ["새 글"]


async def test_판을_정해_지우면_그_판의_조각만_지우고_정하지_않으면_모든_판의_조각을_지운다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    world = await _world(engine)
    building = replace(world.version, id=new_id(), status=IndexVersionStatus.BUILDING)
    async with world.unit_of_work.begin() as transaction:
        await transaction.catalog.add_index_version(building)
        await transaction.index.create_version_index(building)
    document = await world.document()
    async with world.unit_of_work.begin() as transaction:
        await transaction.index.replace_chunks(
            document.id,
            world.version.id,
            [world.chunk(document, 0, "현재 글", (1.0, 0.0, 0.0), "현재")],
        )
        await transaction.index.replace_chunks(
            document.id,
            building.id,
            [world.chunk(document, 0, "건설 글", (0.0, 1.0, 0.0), "건설", version=building)],
        )

    async with world.unit_of_work.begin() as transaction:
        await transaction.index.delete_chunks(document.id, building.id)
    after_one_version = _count(empty_database_url, document.id)
    async with world.unit_of_work.begin() as transaction:
        await transaction.index.delete_chunks(document.id, None)

    assert [after_one_version, _count(empty_database_url, document.id)] == [1, 0]


async def test_다른_문서의_조각은_건드리지_않는다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    world = await _world(engine)
    first = await world.document("가.docx")
    second = await world.document("나.docx")
    await world.write(first, world.chunk(first, 0, "가 글", (1.0, 0.0, 0.0), "가"))

    await world.write(second, world.chunk(second, 0, "나 글", (0.0, 1.0, 0.0), "나"))

    assert (_count(empty_database_url, first.id), _count(empty_database_url, second.id)) == (1, 1)


async def test_조각은_복사_칸과_근거_위치와_만든_내용_해시를_싣고_검색_결과로_읽힌다(
    engine: AsyncEngine,
) -> None:
    world = await _world(engine)
    document = await world.document(title="인사 규정", metadata={"부서": "기획팀"})
    await world.write(document, world.chunk(document, 0, "연차 글", (1.0, 0.0, 0.0), "연차"))

    async with world.unit_of_work.begin() as transaction:
        found = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ("연차",)))

    (hit,) = found.hits
    assert (hit.source, hit.key, hit.title, hit.document_id) == (
        "default",
        "규정.docx",
        "인사 규정",
        document.id,
    )
    assert hit.metadata == {"부서": "기획팀"}
    assert hit.updated_at == NOW
    assert hit.location == ChunkLocation(
        page=None, section=("제1조",), block_kind=BlockKind.PARAGRAPH, block_range=(0, 0)
    )
    assert (hit.effective_date, hit.access_groups) == (None, ())


async def test_벡터에만_걸린_후보도_키워드에만_걸린_후보도_합쳐_나온다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        world.chunk(document, 0, "벡터 쪽", (0.9, 0.1, 0.0), "무관"),
        world.chunk(document, 1, "키워드 쪽", (0.0, 1.0, 0.0), "찾는말"),
        world.chunk(document, 2, "둘 다", (1.0, 0.0, 0.0), "찾는말"),
    )

    async with world.unit_of_work.begin() as transaction:
        found = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ("찾는말",)))

    texts = [hit.text for hit in found.hits]
    assert set(texts) == {"벡터 쪽", "키워드 쪽", "둘 다"}
    # 벡터 1위이면서 키워드 2위인 "둘 다"가 가장 먼저다(키워드 점수가 같으면 조각 ID 순이다).
    assert texts[0] == "둘 다"
    assert found.hits[0].rrf_score == pytest.approx(1 / 61 + 1 / 62)


async def test_RRF_점수는_순위의_역수_합이고_점수_순으로_나온다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        world.chunk(document, 0, "가", (1.0, 0.0, 0.0), "가"),
        world.chunk(document, 1, "나", (0.0, 1.0, 0.0), "나"),
    )

    async with world.unit_of_work.begin() as transaction:
        found = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ()))

    assert [(hit.text, hit.rrf_score) for hit in found.hits] == [
        ("가", pytest.approx(1 / 61)),
        ("나", pytest.approx(1 / 62)),
    ]


async def test_키워드_토큰이_없으면_벡터_후보만_모은다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(document, world.chunk(document, 0, "가", (1.0, 0.0, 0.0), "가"))

    async with world.unit_of_work.begin() as transaction:
        found = await transaction.index.search_candidates(world.query((0.0, 1.0, 0.0), ()))

    assert [hit.text for hit in found.hits] == ["가"]


async def test_검색은_트랜잭션_안에서_ef_search를_후보_수로_올린다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    seen: list[str] = []

    def capture(
        connection: Connection, cursor: object, statement: str, parameters: object, *rest: object
    ) -> None:
        if "set_config" in statement:
            seen.append(repr(parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        async with world.unit_of_work.begin() as transaction:
            await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ()))
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    assert [("hnsw.ef_search" in text, "'10'" in text) for text in seen] == [(True, True)]


async def test_후보_수만큼만_모은다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        *[world.chunk(document, n, f"글 {n}", (1.0, float(n), 0.0), "공통") for n in range(5)],
    )

    async with world.unit_of_work.begin() as transaction:
        found = await transaction.index.search_candidates(
            replace(world.query((1.0, 0.0, 0.0), ("공통",)), candidates=2)
        )

    assert len(found.hits) == 2


async def test_다른_판의_조각은_후보에_들지_않는다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    other = replace(world.version, id=new_id(), status=IndexVersionStatus.BUILDING)
    async with world.unit_of_work.begin() as transaction:
        await transaction.catalog.add_index_version(other)
        await transaction.index.create_version_index(other)
        await transaction.index.replace_chunks(
            document.id,
            other.id,
            [world.chunk(document, 0, "건설 중", (1.0, 0.0, 0.0), "건설", version=other)],
        )

    async with world.unit_of_work.begin() as transaction:
        found = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ("건설",)))

    assert found.hits == ()


async def test_질의한_판이_현재_판이면_is_current가_참이고_전환되면_거짓이다(
    engine: AsyncEngine,
) -> None:
    world = await _world(engine)
    other = replace(world.version, id=new_id(), status=IndexVersionStatus.BUILDING)
    async with world.unit_of_work.begin() as transaction:
        await transaction.catalog.add_index_version(other)
        await transaction.index.create_version_index(other)

    async with world.unit_of_work.begin() as transaction:
        before = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ()))
        await transaction.catalog.switch_current_version(world.version.knowledge_base_id, other.id)
    async with world.unit_of_work.begin() as transaction:
        after = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ()))

    assert (before.is_current, after.is_current) == (True, False)


async def test_바인딩_매개변수_상한을_넘는_수의_조각도_한_번에_바꾼다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    # 조각 하나가 바인딩 값을 열넷쯤 쓰고 한 문장은 65535개까지만 받는다. 그 수를 넘는 조각이다.
    world = await _world(engine)
    document = await world.document()
    chunks = [
        world.chunk(document, n, f"글 {n}", (1.0, float(n % 7), 0.0), "공통") for n in range(5000)
    ]

    await world.write(document, *chunks)

    assert _count(empty_database_url, document.id) == 5000


async def test_벡터_질의는_판의_HNSW_부분_색인을_탄다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        *[world.chunk(document, n, f"글 {n}", (1.0, float(n), 0.0), "공통") for n in range(20)],
    )

    async with world.unit_of_work.begin() as transaction:
        plan = await transaction.index.explain_search(world.query((1.0, 0.0, 0.0), ("공통",)))

    assert f"ix_chunks_hnsw_{world.version.id.hex}" in plan


async def test_일반_계획으로도_판의_HNSW_부분_색인을_쓴다(engine: AsyncEngine) -> None:
    # psycopg는 같은 문장을 다섯 번 넘게 돌리면 서버에 준비시키고, 서버는 그때 일반 계획을 고를 수
    # 있다. 일반 계획을 강제해 그 계획이 부분 색인을 타는지 본다.
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        *[world.chunk(document, n, f"글 {n}", (1.0, float(n), 0.0), "공통") for n in range(20)],
    )

    async with world.unit_of_work.begin() as transaction:
        plan = await transaction.index.explain_search_generic(
            world.query((1.0, 0.0, 0.0), ("공통",))
        )

    assert f"ix_chunks_hnsw_{world.version.id.hex}" in plan


async def test_색인_상태를_쓰면_다시_읽히고_다시_쓰면_덮는다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    pending = IndexState(
        document.id, world.version.id, IndexStateStatus.PENDING, 0, None, None, NOW
    )
    indexed = replace(
        pending,
        status=IndexStateStatus.INDEXED,
        chunk_count=2,
        built_content_hash=document.content_hash,
        updated_at=NOW + timedelta(seconds=5),
    )

    async with world.unit_of_work.begin() as transaction:
        await transaction.index.save_state(pending)
        first = await transaction.index.get_state(document.id, world.version.id)
        await transaction.index.save_state(indexed)
        second = await transaction.index.get_state(document.id, world.version.id)
        missing = await transaction.index.get_state(document.id, new_id())

    assert (first, second, missing) == (pending, indexed, None)


async def test_파싱_결과를_저장하면_다시_읽히고_다시_저장하면_덮는다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    content = DocumentContent(
        document_id=document.id,
        parser_name="docx",
        parser_interface_version="1.0.0",
        parser_library_version="1.2.0",
        blocks=(
            Block(BlockKind.HEADING, "제1조", level=1, page=None, ordinal=0),
            Block(BlockKind.PARAGRAPH, "본문", level=None, page=3, ordinal=1),
        ),
        parsed_content_hash="b" * 64,
        text_hash="c" * 64,
        parsed_at=NOW,
    )
    newer = replace(content, blocks=content.blocks[:1], text_hash="d" * 64)

    async with world.unit_of_work.begin() as transaction:
        before = await transaction.documents.get_content(document.id)
        await transaction.documents.save_content(content)
        first = await transaction.documents.get_content(document.id)
        await transaction.documents.save_content(newer)
        second = await transaction.documents.get_content(document.id)

    assert (before, first, second) == (None, content, newer)


async def _document_in(world: _World, group: Group, key: str, **overrides: object) -> Document:
    document = make_document(world.source, group, key=key, **overrides)
    async with world.unit_of_work.begin() as transaction:
        await transaction.documents.add(document)
    return document


async def _other_group(world: _World, name: str) -> Group:
    """지식베이스의 그룹 집합에 드는 그룹 하나를 더한다."""
    group = Group(new_id(), name, "")
    async with world.unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(group)
        await transaction.catalog.add_group_to_knowledge_base(
            world.version.knowledge_base_id, group.id
        )
    return group


async def _texts_found(world: _World, search_filter: SearchFilter) -> set[str]:
    query = replace(world.query((1.0, 0.0, 0.0), ("찾는말",)), filter=search_filter)
    async with world.unit_of_work.begin() as transaction:
        found = await transaction.index.search_candidates(query)
    return {hit.text for hit in found.hits}


async def test_그룹_필터는_벡터와_키워드_두_쪽_모두에서_그_그룹의_조각만_남긴다(
    engine: AsyncEngine,
) -> None:
    world = await _world(engine)
    personnel = await _other_group(world, "인사")
    base_document = await world.document("기본.docx")
    personnel_document = await _document_in(world, personnel, "인사.docx")
    await world.write(
        base_document,
        world.chunk(base_document, 0, "기본 벡터", (1.0, 0.0, 0.0), "무관"),
        world.chunk(base_document, 1, "기본 키워드", (0.0, 0.0, 1.0), "찾는말"),
    )
    await world.write(
        personnel_document,
        world.chunk(personnel_document, 0, "인사 벡터", (0.9, 0.1, 0.0), "무관"),
        world.chunk(personnel_document, 1, "인사 키워드", (0.0, 0.0, 1.0), "찾는말"),
    )

    only_personnel = await _texts_found(world, SearchFilter(group_ids=(personnel.id,)))
    only_base = await _texts_found(world, SearchFilter(group_ids=(world.group.id,)))
    both = await _texts_found(world, SearchFilter(group_ids=(personnel.id, world.group.id)))

    assert only_personnel == {"인사 벡터", "인사 키워드"}
    assert only_base == {"기본 벡터", "기본 키워드"}
    assert len(both) == 4


async def test_그룹_집합이_빈_필터는_아무_조각도_내지_않는다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(document, world.chunk(document, 0, "글", (1.0, 0.0, 0.0), "찾는말"))

    assert await _texts_found(world, SearchFilter(group_ids=())) == set()


async def test_갱신일_기간은_시작을_포함하고_끝을_제외한다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    for days_ago, key in ((2, "이틀.docx"), (1, "하루.docx"), (0, "오늘.docx")):
        document = await world.document(key, updated_at=NOW - timedelta(days=days_ago))
        await world.write(document, world.chunk(document, 0, key, (1.0, 0.0, 0.0), "찾는말"))
    yesterday = NOW - timedelta(days=1)

    period = SearchFilter(updated_after=yesterday, updated_before=NOW)
    from_yesterday = SearchFilter(updated_after=yesterday)
    before_today = SearchFilter(updated_before=NOW)

    assert await _texts_found(world, period) == {"하루.docx"}
    assert await _texts_found(world, from_yesterday) == {"하루.docx", "오늘.docx"}
    assert await _texts_found(world, before_today) == {"이틀.docx", "하루.docx"}


async def test_필터가_있을_때만_반복_스캔을_완화된_순서로_켠다(engine: AsyncEngine) -> None:
    world = await _world(engine)
    seen: list[str] = []

    def capture(
        connection: Connection, cursor: object, statement: str, parameters: object, *rest: object
    ) -> None:
        if "set_config" in statement:
            seen.append(repr(parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        await _texts_found(world, SearchFilter())
        unfiltered = list(seen)
        seen.clear()
        await _texts_found(world, SearchFilter(updated_after=NOW))
        filtered = list(seen)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    assert [
        any("iterative_scan" in text for text in group) for group in (unfiltered, filtered)
    ] == [
        False,
        True,
    ]
    assert any("relaxed_order" in text for text in filtered)
