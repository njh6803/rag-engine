"""`VectorIndex`와 `DocumentStore`의 07 몫(명세 "데이터 모델과 스키마", "검색 흐름").

조각 쓰기는 그 (문서, 판)의 옛 조각을 지우고 새 조각을 넣는다. 색인 상태와 파싱 결과는 덮어쓴다.
검색 질의는 벡터와 키워드 후보를 SQL 하나로 모아 RRF(`1/(60+순위)`의 합)로 합치고, 벡터 질의는 03이
만든 판의 HNSW 부분 색인을 탄다(같은 캐스트 `embedding::vector(D)`).

끝의 진단용 검색 시험은 search-eval 01 몫이다(명세 "진단용 검색과 단계"). 진단용 검색은 같은 SQL
뼈대에서 합친 뒤의 자르기만 빼고 단계마다의 순위를 싣는다. 계획을 고르는 `CandidateScan.EXACT`는
HNSW 색인을 쓰지 않는 계획으로 돌고, 그 설정은 호출 밖으로 새지 않는다.
"""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
import sqlalchemy as sa
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
from rag_engine.adapters.postgres.vector_index import PostgresVectorIndex
from rag_engine.domain.entities import (
    Block,
    BlockKind,
    CandidateScan,
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


async def _with_building_version(world: _World) -> IndexVersion:
    building = replace(world.version, id=new_id(), status=IndexVersionStatus.BUILDING)
    async with world.unit_of_work.begin() as transaction:
        await transaction.catalog.add_index_version(building)
        await transaction.index.create_version_index(building)
    return building


def _archived(database_url: str, document_id: UUID) -> list[tuple[str, object]]:
    """보관 표의 (글, 보관 시각)."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        return connection.execute(
            "SELECT text, archived_at FROM archived_chunks WHERE document_id = %s ORDER BY text",
            [document_id],
        ).fetchall()


async def test_조각을_보관하면_모든_판의_조각이_검색_표에서_보관_표로_옮겨진다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    world = await _world(engine)
    building = await _with_building_version(world)
    document = await world.document()
    other = await world.document("다른.docx")
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
        await transaction.index.replace_chunks(
            other.id, world.version.id, [world.chunk(other, 0, "남는 글", (0.0, 0.0, 1.0), "남는")]
        )

    later = NOW + timedelta(hours=1)
    async with world.unit_of_work.begin() as transaction:
        await transaction.index.archive_chunks(document.id, later)

    assert _count(empty_database_url, document.id) == 0
    assert _archived(empty_database_url, document.id) == [("건설 글", later), ("현재 글", later)]
    assert _count(empty_database_url, other.id) == 1
    assert _archived(empty_database_url, other.id) == []
    async with world.unit_of_work.begin() as transaction:
        hits = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ()))
    assert [hit.text for hit in hits.hits] == ["남는 글"]


async def test_보관_조각을_되돌리면_대상_판의_같은_내용_조각만_문서의_지금_복사_칸으로_돌아온다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    world = await _world(engine)
    building = await _with_building_version(world)
    document = await world.document()
    stale = replace(
        world.chunk(document, 1, "옛 내용 글", (0.0, 1.0, 0.0), "옛"), source_content_hash="b" * 64
    )
    async with world.unit_of_work.begin() as transaction:
        await transaction.index.replace_chunks(
            document.id,
            world.version.id,
            [world.chunk(document, 0, "되돌릴 글", (1.0, 0.0, 0.0), "되돌릴"), stale],
        )
        await transaction.index.replace_chunks(
            document.id,
            building.id,
            [world.chunk(document, 0, "건설 글", (0.0, 0.0, 1.0), "건설", version=building)],
        )
        await transaction.index.archive_chunks(document.id, NOW)
    revived = replace(
        document, updated_at=NOW + timedelta(days=3), access_groups=("교육팀",), deleted_at=None
    )

    async with world.unit_of_work.begin() as transaction:
        restored = await transaction.index.restore_archived_chunks(revived, [world.version.id])

    assert restored == {world.version.id: 1}
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT text, index_version_id, group_id, updated_at, access_groups FROM chunks"
            " WHERE document_id = %s",
            [document.id],
        ).fetchall()
    assert rows == [
        ("되돌릴 글", world.version.id, world.group.id, NOW + timedelta(days=3), ["교육팀"])
    ]
    async with world.unit_of_work.begin() as transaction:
        hits = await transaction.index.search_candidates(world.query((1.0, 0.0, 0.0), ()))
    assert [hit.text for hit in hits.hits] == ["되돌릴 글"]


async def test_보관_조각을_지우면_그_문서의_보관_조각만_사라진다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    world = await _world(engine)
    document = await world.document()
    other = await world.document("다른.docx")
    async with world.unit_of_work.begin() as transaction:
        for target, text in ((document, "지울 글"), (other, "남는 글")):
            await transaction.index.replace_chunks(
                target.id, world.version.id, [world.chunk(target, 0, text, (1.0, 0.0, 0.0), text)]
            )
            await transaction.index.archive_chunks(target.id, NOW)

    async with world.unit_of_work.begin() as transaction:
        await transaction.index.delete_archived_chunks(document.id)

    assert _archived(empty_database_url, document.id) == []
    assert _archived(empty_database_url, other.id) == [("남는 글", NOW)]


async def test_색인_상태를_모두_지우면_판과_상관없이_그_문서의_상태_행이_사라진다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    world = await _world(engine)
    building = await _with_building_version(world)
    document = await world.document()
    other = await world.document("다른.docx")
    async with world.unit_of_work.begin() as transaction:
        for target in (document, other):
            for version in (world.version, building):
                await transaction.index.save_state(
                    IndexState(
                        document_id=target.id,
                        index_version_id=version.id,
                        status=IndexStateStatus.PENDING,
                        chunk_count=0,
                        built_content_hash=None,
                        error_code=None,
                        updated_at=NOW,
                    )
                )

    async with world.unit_of_work.begin() as transaction:
        await transaction.index.delete_states(document.id)

    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT document_id FROM document_index_states ORDER BY index_version_id"
        ).fetchall()
    assert rows == [(other.id,), (other.id,)]


async def _spread_world(engine: AsyncEngine) -> _World:
    """그룹 둘에 걸친 조각 여덟 개. 벡터는 질의 (1, 0, 0)에서 거리가 서로 다르고 키워드는 짝수
    조각만 든다. 후보 수를 3으로 주면 벡터와 키워드 후보가 일부만 겹친다."""
    world = await _world(engine)
    personnel = await _other_group(world, "인사")
    for group, key in ((world.group, "기본.docx"), (personnel, "인사.docx")):
        document = await _document_in(world, group, key)
        tilt = 0.1 if group is world.group else 0.15
        await world.write(
            document,
            *[
                world.chunk(
                    document,
                    n,
                    f"{key} 글 {n}",
                    (1.0, 0.2 * (n + 1), tilt * (4 - n)),
                    "찾는말" if n % 2 == 0 else "무관",
                )
                for n in range(4)
            ],
        )
    return world


@pytest.mark.parametrize("keywords", [("찾는말",), ()], ids=["키워드_있음", "키워드_빈_질의"])
@pytest.mark.parametrize("filter_kind", ["없음", "그룹"], ids=["필터_없음", "그룹_필터"])
async def test_진단용_검색의_합친_순위가_후보_수_이하인_줄은_검색의_후보와_순서와_점수까지_같다(
    engine: AsyncEngine, keywords: tuple[str, ...], filter_kind: str
) -> None:
    world = await _spread_world(engine)
    query = replace(world.query((1.0, 0.0, 0.0), keywords), candidates=3)
    if filter_kind == "그룹":
        query = replace(query, filter=SearchFilter(group_ids=(world.group.id,)))

    async with world.unit_of_work.begin() as transaction:
        searched = await transaction.index.search_candidates(query)
        diagnosed = await transaction.index.diagnose_candidates(query, scan=CandidateScan.INDEX)

    head = [line for line in diagnosed.hits if line.fused_rank <= query.candidates]
    assert [(hit.chunk_id, hit.text, hit.rrf_score) for hit in searched.hits] == [
        (line.hit.chunk_id, line.hit.text, line.hit.rrf_score) for line in head
    ]
    assert len(head) == len(searched.hits) > 0
    assert diagnosed.is_current is searched.is_current is True


async def test_진단용_검색은_벡터와_키워드_후보의_합집합_전부를_단계마다의_순위와_함께_낸다(
    engine: AsyncEngine,
) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        world.chunk(document, 0, "벡터 쪽", (1.0, 0.0, 0.0), "무관"),
        world.chunk(document, 1, "키워드 쪽", (0.0, 1.0, 0.0), "찾는말"),
        world.chunk(document, 2, "어디에도 없음", (0.0, 0.0, 1.0), "무관"),
    )
    query = replace(world.query((1.0, 0.0, 0.0), ("찾는말",)), candidates=1)

    async with world.unit_of_work.begin() as transaction:
        diagnosed = await transaction.index.diagnose_candidates(query, scan=CandidateScan.INDEX)

    # 후보 수가 1이라 벡터 후보는 "벡터 쪽"뿐이고 키워드 후보는 "키워드 쪽"뿐이다. 합집합은 둘이고
    # 점수가 같아 조각 ID 순으로 끊는다(`search_candidates`와 같은 규칙).
    by_text = {line.hit.text: line for line in diagnosed.hits}
    assert set(by_text) == {"벡터 쪽", "키워드 쪽"}
    vector_side, keyword_side = by_text["벡터 쪽"], by_text["키워드 쪽"]
    assert (vector_side.vector_rank, vector_side.keyword_rank) == (1, None)
    assert (keyword_side.vector_rank, keyword_side.keyword_rank) == (None, 1)
    assert (vector_side.ordinal, keyword_side.ordinal) == (0, 1)
    assert [line.fused_rank for line in diagnosed.hits] == [1, 2]
    assert diagnosed.hits[0].hit.chunk_id == min(
        vector_side.hit.chunk_id, keyword_side.hit.chunk_id
    )


async def test_진단용_검색에서_키워드_토큰이_없으면_키워드_순위는_모두_없다(
    engine: AsyncEngine,
) -> None:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        world.chunk(document, 0, "가", (1.0, 0.0, 0.0), "가"),
        world.chunk(document, 1, "나", (0.0, 1.0, 0.0), "나"),
    )

    async with world.unit_of_work.begin() as transaction:
        diagnosed = await transaction.index.diagnose_candidates(
            world.query((1.0, 0.0, 0.0), ()), scan=CandidateScan.INDEX
        )

    assert [
        (line.hit.text, line.vector_rank, line.keyword_rank, line.fused_rank)
        for line in diagnosed.hits
    ] == [("가", 1, None, 1), ("나", 2, None, 2)]


async def test_진단용_검색은_검색과_같은_규칙으로_ef_search와_반복_스캔을_건다(
    engine: AsyncEngine,
) -> None:
    world = await _world(engine)
    seen: list[str] = []

    def capture(
        connection: Connection, cursor: object, statement: str, parameters: object, *rest: object
    ) -> None:
        if "set_config" in statement:
            seen.append(repr(parameters))

    async def settings_for(search_filter: SearchFilter) -> list[str]:
        seen.clear()
        query = replace(world.query((1.0, 0.0, 0.0), ()), candidates=7, filter=search_filter)
        async with world.unit_of_work.begin() as transaction:
            await transaction.index.diagnose_candidates(query, scan=CandidateScan.INDEX)
        return list(seen)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        unfiltered = await settings_for(SearchFilter())
        filtered = await settings_for(SearchFilter(updated_after=NOW))
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    assert any("hnsw.ef_search" in text and "'7'" in text for text in unfiltered)
    assert not any("iterative_scan" in text for text in unfiltered)
    assert any("iterative_scan" in text and "relaxed_order" in text for text in filtered)


async def test_진단용_검색은_정확_스캔일_때만_색인_스캔을_끄고_호출_끝에_되돌린다(
    engine: AsyncEngine,
) -> None:
    # 계획 시험(EXPLAIN)은 시험용 메서드만 본다. 실제 호출이 `scan`을 따르는지는 호출이 거는
    # 설정으로 본다.
    world = await _world(engine)
    seen: list[str] = []

    def capture(
        connection: Connection, cursor: object, statement: str, parameters: object, *rest: object
    ) -> None:
        if "set_config" in statement and "enable_indexscan" in repr(parameters):
            seen.append(repr(parameters))

    async def settings_for(scan: CandidateScan) -> list[str]:
        seen.clear()
        async with world.unit_of_work.begin() as transaction:
            await transaction.index.diagnose_candidates(world.query((1.0, 0.0, 0.0), ()), scan=scan)
        return list(seen)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        indexed = await settings_for(CandidateScan.INDEX)
        exact = await settings_for(CandidateScan.EXACT)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    assert indexed == []
    assert ["'off'" in text for text in exact] == [True, False]
    assert "'on'" in exact[1]


async def _twenty_chunks(engine: AsyncEngine) -> _World:
    world = await _world(engine)
    document = await world.document()
    await world.write(
        document,
        *[world.chunk(document, n, f"글 {n}", (1.0, float(n), 0.0), "공통") for n in range(20)],
    )
    return world


async def test_정확_스캔의_계획에는_판의_HNSW_부분_색인이_없고_색인_스캔의_계획에는_있다(
    engine: AsyncEngine,
) -> None:
    world = await _twenty_chunks(engine)
    query = world.query((1.0, 0.0, 0.0), ("공통",))
    index_name = f"ix_chunks_hnsw_{world.version.id.hex}"

    async with world.unit_of_work.begin() as transaction:
        exact = await transaction.index.explain_diagnosis(query, scan=CandidateScan.EXACT)
    async with world.unit_of_work.begin() as transaction:
        indexed = await transaction.index.explain_diagnosis(query, scan=CandidateScan.INDEX)

    assert index_name not in exact
    assert index_name in indexed


async def test_정확_스캔_호출_뒤에도_같은_트랜잭션의_색인_스캔과_검색은_HNSW_색인을_쓴다(
    engine: AsyncEngine,
) -> None:
    world = await _twenty_chunks(engine)
    query = world.query((1.0, 0.0, 0.0), ("공통",))
    index_name = f"ix_chunks_hnsw_{world.version.id.hex}"

    async with world.unit_of_work.begin() as transaction:
        before = await transaction.index.explain_diagnosis(query, scan=CandidateScan.EXACT)
        await transaction.index.diagnose_candidates(query, scan=CandidateScan.EXACT)
        diagnosed = await transaction.index.explain_diagnosis(query, scan=CandidateScan.INDEX)
        searched = await transaction.index.explain_search(query)

    assert index_name not in before
    assert index_name in diagnosed
    assert index_name in searched


async def test_정확_스캔의_벡터_순위는_거리_순과_같다(engine: AsyncEngine) -> None:
    world = await _twenty_chunks(engine)
    query = world.query((1.0, 0.0, 0.0), ())

    async with world.unit_of_work.begin() as transaction:
        diagnosed = await transaction.index.diagnose_candidates(query, scan=CandidateScan.EXACT)

    ranked = sorted(
        (line for line in diagnosed.hits if line.vector_rank is not None),
        key=lambda line: line.vector_rank or 0,
    )
    # 질의 (1, 0, 0)과의 코사인 거리는 (1, n, 0)의 n이 클수록 멀다. 후보 수 10만큼이 든다.
    assert [line.hit.text for line in ranked] == [f"글 {n}" for n in range(10)]
    assert [line.vector_rank for line in ranked] == list(range(1, 11))


async def test_진단용_검색도_질의한_판이_전환되면_is_current가_거짓이다(
    engine: AsyncEngine,
) -> None:
    world = await _world(engine)
    other = await _with_building_version(world)

    async with world.unit_of_work.begin() as transaction:
        before = await transaction.index.diagnose_candidates(
            world.query((1.0, 0.0, 0.0), ()), scan=CandidateScan.EXACT
        )
        await transaction.catalog.switch_current_version(world.version.knowledge_base_id, other.id)
    async with world.unit_of_work.begin() as transaction:
        after = await transaction.index.diagnose_candidates(
            world.query((1.0, 0.0, 0.0), ()), scan=CandidateScan.EXACT
        )

    assert (before.is_current, after.is_current) == (True, False)


def _index_scans(database_url: str, version: IndexVersion) -> int:
    """판의 HNSW 부분 색인이 지금까지 스캔된 횟수(통계 보기)."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        row = connection.execute(
            "SELECT idx_scan FROM pg_stat_user_indexes WHERE indexrelname = %s",
            [f"ix_chunks_hnsw_{version.id.hex}"],
        ).fetchone()
    assert row is not None
    return row[0]


async def test_같은_연결에서_두_계획을_열_번_넘게_번갈아_불러도_정확_스캔만_색인을_타지_않는다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    # psycopg는 같은 문장을 다섯 번 돌리면 서버에 준비시키고 서버는 그 뒤 일반 계획을 쓴다. 일반
    # 계획은 `enable_indexscan` 설정이 바뀌어도 다시 짜지 않으므로, 두 계획이 같은 문장 글을 쓰면
    # 한쪽 계획이 다른 쪽 호출에 눌러앉는다.
    world = await _twenty_chunks(engine)
    query = world.query((1.0, 0.0, 0.0), ())
    before = _index_scans(empty_database_url, world.version)
    rounds = 8

    async with engine.connect() as connection, connection.begin():
        index = PostgresVectorIndex(connection)
        for _ in range(rounds):
            await index.diagnose_candidates(query, scan=CandidateScan.INDEX)
            await index.diagnose_candidates(query, scan=CandidateScan.EXACT)
        await connection.execute(sa.text("SELECT pg_stat_force_next_flush()"))

    # 색인을 탄 것은 `INDEX` 호출뿐이어야 한다.
    scans = _index_scans(empty_database_url, world.version) - before
    assert scans == rounds, f"색인 스캔 {scans}회, 기대 {rounds}회"
