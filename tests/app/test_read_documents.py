"""읽기 도구 `get_document`와 `list_knowledge_bases`의 유스케이스(명세 "MCP 도구", 티켓 09).

실제 테스트 PostgreSQL과 실제 파서·청커 위에서 돈다. 토큰 범위 밖 지식베이스는 이름도 내지 않고,
지워진 문서와 범위 밖에만 든 문서는 `document_not_found`다. 전문의 창 계산 자체는
`test_document_text.py`가 데이터베이스 없이 본다.
"""

from dataclasses import replace
from uuid import UUID

import pytest
from tests.records import NOW, make_knowledge_base
from tests.support.docx_files import docx_bytes, docx_outline
from tests.support.pipeline import LEASE_SECONDS, Pipeline

from rag_engine.app.read_documents import DocumentView, get_document, list_knowledge_bases
from rag_engine.domain.entities import Group, KnowledgeBase
from rag_engine.domain.errors import ErrorCode, RagEngineError
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import run_once

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.", "미사용 휴가는 소멸한다.")
휴가_전문 = "# 제1조 휴가\n\n연차휴가는 입사 일 년 뒤부터 발생한다.\n\n미사용 휴가는 소멸한다."
_LIMIT = 20_000


async def _index(pipeline: Pipeline, data: bytes = 휴가, key: str = "규정.docx") -> UUID:
    """문서를 수집하고 작업자를 한 번 돌려 색인한 뒤 문서의 식별자를 낸다."""
    ingested = await pipeline.ingest(data, key)
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)
    return ingested.document_id


async def _get(
    pipeline: Pipeline,
    document_id: UUID,
    *,
    scope: tuple[UUID, ...] = (),
    include_text: bool = False,
    offset: int = 0,
    max_chars: int | None = None,
    limit: int = _LIMIT,
) -> DocumentView:
    return await get_document(
        pipeline.unit_of_work,
        document_id,
        allowed_knowledge_base_ids=scope,
        include_text=include_text,
        offset=offset,
        max_chars=max_chars,
        max_text_chars=limit,
    )


async def _error_code(
    pipeline: Pipeline,
    document_id: UUID,
    *,
    scope: tuple[UUID, ...] = (),
    include_text: bool = False,
    offset: int = 0,
    max_chars: int | None = None,
) -> ErrorCode:
    with pytest.raises(RagEngineError) as caught:
        await _get(
            pipeline,
            document_id,
            scope=scope,
            include_text=include_text,
            offset=offset,
            max_chars=max_chars,
        )
    return caught.value.code


async def _add_knowledge_base(pipeline: Pipeline, name: str, *groups: Group) -> KnowledgeBase:
    knowledge_base = replace(make_knowledge_base(name), embedding_dimensions=16)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.add_knowledge_base(knowledge_base)
        for group in groups:
            await transaction.catalog.add_group_to_knowledge_base(knowledge_base.id, group.id)
    return knowledge_base


async def test_문서_정보는_원천과_그룹의_이름과_현재_판의_조각_수를_싣는다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline)

    view = await _get(pipeline, document_id)

    assert (view.source, view.group, view.document.key) == ("default", "default", "규정.docx")
    assert view.chunk_counts == {"default": len(await pipeline.chunk_texts(document_id))}
    assert view.chunk_counts["default"] > 0


async def test_글을_요청하지_않아도_전문의_길이는_내고_글과_next_offset은_null이다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline)

    view = await _get(pipeline, document_id)

    assert (view.text_length, view.text, view.next_offset) == (len(휴가_전문), None, None)


async def test_글을_요청하면_제목은_샵_표시를_달고_블록의_글을_빈_줄로_이어_낸다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline)

    view = await _get(pipeline, document_id, include_text=True)

    assert (view.text_length, view.text, view.next_offset) == (len(휴가_전문), 휴가_전문, None)


async def test_하위_제목은_수준만큼_샵을_단다(pipeline: Pipeline) -> None:
    document_id = await _index(
        pipeline, docx_outline((1, "규정"), (2, "제1조"), "본문입니다.", (3, "제1항"))
    )

    view = await _get(pipeline, document_id, include_text=True)

    assert view.text == "# 규정\n\n## 제1조\n\n본문입니다.\n\n### 제1항"


async def test_창은_블록_경계에서_잘리고_next_offset을_이어_읽으면_전문과_같다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline)

    first = await _get(pipeline, document_id, include_text=True, max_chars=30)
    assert first.next_offset is not None
    second = await _get(
        pipeline, document_id, include_text=True, offset=first.next_offset, max_chars=_LIMIT
    )

    assert first.text == "# 제1조 휴가"
    assert first.next_offset == len("# 제1조 휴가")
    assert (first.text or "") + (second.text or "") == 휴가_전문
    assert (second.next_offset, second.text_length) == (None, len(휴가_전문))


async def test_글이_없는_문서의_전문은_길이_0의_빈_글이다(pipeline: Pipeline) -> None:
    document_id = await _index(pipeline, docx_outline())

    view = await _get(pipeline, document_id, include_text=True)

    assert (view.text_length, view.text, view.next_offset) == (0, "", None)


async def test_offset이_전문의_길이와_같으면_빈_글이고_넘으면_잘못된_인자다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline)
    length = len(휴가_전문)

    at_end = await _get(pipeline, document_id, include_text=True, offset=length)
    code = await _error_code(pipeline, document_id, include_text=True, offset=length + 1)

    assert (at_end.text, at_end.next_offset, at_end.text_length) == ("", None, length)
    assert code is ErrorCode.INVALID_ARGUMENT


async def test_글을_요청하지_않으면_길이를_넘는_offset도_오류가_아니다(pipeline: Pipeline) -> None:
    document_id = await _index(pipeline)

    view = await _get(pipeline, document_id, offset=10**9)

    assert (view.text, view.next_offset) == (None, None)


@pytest.mark.parametrize(
    ("offset", "max_chars", "include_text"),
    [(0, 0, False), (0, _LIMIT + 1, False), (-1, None, False), (0, 0, True), (-1, None, True)],
    ids=["0", "상한_초과", "음수_offset", "글을_요청해도_0", "글을_요청해도_음수_offset"],
)
async def test_max_chars와_offset의_범위_위반은_문서를_찾기_전에_잘못된_인자다(
    pipeline: Pipeline, *, offset: int, max_chars: int | None, include_text: bool
) -> None:
    # 없는 문서의 식별자로도 `document_not_found`가 아니라 `invalid_argument`다.
    code = await _error_code(
        pipeline, new_id(), include_text=include_text, offset=offset, max_chars=max_chars
    )

    assert code is ErrorCode.INVALID_ARGUMENT


async def test_max_chars는_1부터_상한까지_받는다(pipeline: Pipeline) -> None:
    document_id = await _index(pipeline)

    smallest = await _get(pipeline, document_id, include_text=True, max_chars=1)
    largest = await _get(pipeline, document_id, include_text=True, max_chars=_LIMIT)

    assert smallest.text == "#"
    assert largest.text == 휴가_전문


async def test_max_chars를_주지_않으면_설정의_상한이_창의_크기다(pipeline: Pipeline) -> None:
    document_id = await _index(pipeline)

    view = await _get(pipeline, document_id, include_text=True, limit=20)

    assert view.text == "# 제1조 휴가"
    assert view.next_offset == len("# 제1조 휴가")


async def test_내용이_바뀐_뒤_아직_파싱하지_않았으면_길이와_글과_next_offset이_모두_null이다(
    pipeline: Pipeline,
) -> None:
    await _index(pipeline)
    changed = await pipeline.ingest(docx_bytes("제2조 출장", "출장비는 실비다."), "규정.docx")

    for include_text in (True, False):
        view = await _get(pipeline, changed.document_id, include_text=include_text)
        assert (view.text_length, view.text, view.next_offset) == (None, None, None)

    # 길이를 모르면 offset이 아무리 커도 오류가 아니다.
    far = await _get(pipeline, changed.document_id, include_text=True, offset=10**9)
    assert (far.text_length, far.text, far.next_offset) == (None, None, None)


async def test_지워진_문서는_찾을_수_없다(pipeline: Pipeline) -> None:
    document_id = await _index(pipeline)
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(document_id)
        assert document is not None
        await transaction.documents.update(replace(document, deleted_at=NOW))

    assert await _error_code(pipeline, document_id) is ErrorCode.DOCUMENT_NOT_FOUND


async def test_없는_문서는_찾을_수_없다(pipeline: Pipeline) -> None:
    assert await _error_code(pipeline, new_id()) is ErrorCode.DOCUMENT_NOT_FOUND


async def test_범위_밖에만_든_문서는_찾을_수_없고_범위_안_지식베이스만_조각_수에_싣는다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline)
    extra = await _add_knowledge_base(pipeline, "추가", pipeline.group)
    elsewhere_group = Group(new_id(), "다른", "")
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(elsewhere_group)
    elsewhere = await _add_knowledge_base(pipeline, "다른곳", elsewhere_group)

    async def view_with(*scope: KnowledgeBase) -> list[str]:
        view = await _get(pipeline, document_id, scope=tuple(item.id for item in scope))
        return sorted(view.chunk_counts)

    assert await view_with() == ["default", "추가"]
    assert await view_with(pipeline.knowledge_base) == ["default"]
    assert await view_with(extra) == ["추가"]
    with pytest.raises(RagEngineError) as caught:
        await view_with(elsewhere)
    assert caught.value.code is ErrorCode.DOCUMENT_NOT_FOUND


async def test_볼_수_없는_문서는_offset이_길이를_넘어도_찾을_수_없다고만_알린다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline)
    elsewhere_group = Group(new_id(), "다른", "")
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(elsewhere_group)
    elsewhere = await _add_knowledge_base(pipeline, "다른곳", elsewhere_group)

    code = await _error_code(
        pipeline, document_id, scope=(elsewhere.id,), include_text=True, offset=10**9
    )

    # 길이를 넘는 offset의 `invalid_argument`는 문서를 볼 수 있을 때만 난다(문서의 길이가 드러난다).
    assert code is ErrorCode.DOCUMENT_NOT_FOUND


async def test_현재_판이_없는_지식베이스의_조각_수는_0이다(pipeline: Pipeline) -> None:
    document_id = await _index(pipeline)
    await _add_knowledge_base(pipeline, "추가", pipeline.group)

    view = await _get(pipeline, document_id)

    assert view.chunk_counts["추가"] == 0


async def test_지식베이스_목록은_문서_수와_기본_표시를_싣고_범위_밖은_뺀다(
    pipeline: Pipeline,
) -> None:
    await _index(pipeline, 휴가, "하나.docx")
    await _index(pipeline, docx_bytes("제2조 출장", "출장비는 실비다."), "둘.docx")
    empty_group = Group(new_id(), "빈그룹", "")
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(empty_group)
    empty = await _add_knowledge_base(pipeline, "비어있음", empty_group)

    everything = await list_knowledge_bases(pipeline.unit_of_work, allowed_knowledge_base_ids=())
    scoped = await list_knowledge_bases(
        pipeline.unit_of_work, allowed_knowledge_base_ids=(empty.id,)
    )

    # 목록의 순서는 데이터베이스의 이름 정렬이라 문자 종류가 다른 이름끼리는 순서를 가정하지 않는다.
    assert {
        view.knowledge_base.name: (view.document_count, view.knowledge_base.is_default)
        for view in everything
    } == {"default": (2, True), "비어있음": (0, False)}
    assert [view.knowledge_base.name for view in scoped] == ["비어있음"]
