"""읽기 도구의 계약(티켓 09, 스토리 21, 22, 23, 27, 42): 도구 목록, `get_document`,
`list_knowledge_bases`.

서버는 실제 uvicorn이고 도구는 공식 MCP SDK의 클라이언트로 HTTP 접속해 부른다
(`.claude/rules/tests.md`). 문서를 지운 갈래는 `test_delete_restore.py`가 시험한다.
"""

import json
from collections.abc import Callable, Iterator
from uuid import uuid4

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Tool
from tests.harness import RunningServer
from tests.support.docx_files import docx_outline
from tests.support.round_trip import (
    RoundTrip,
    document_output,
    error_body,
    knowledge_bases_output,
    output,
    wire_stubs,
)

from rag_engine.server.tool_models import (
    FORMAT_VERSION,
    DocumentOutput,
    KnowledgeBasesOutput,
    SearchOutput,
)

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.", "미사용 휴가는 소멸한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")
# 제목 블록의 글은 `#`을 달고, 블록 글은 빈 줄로 이어진다(명세 "MCP 도구").
휴가_전문 = "# 제1조 휴가\n\n연차휴가는 입사 일 년 뒤부터 발생한다.\n\n미사용 휴가는 소멸한다."
_SMALL_LIMIT = 40
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _tools(round_trip: RoundTrip) -> dict[str, Tool]:
    async with httpx2.AsyncClient(headers=round_trip.auth()) as http:
        async with Client(
            streamable_http_client(round_trip.server.mcp_url, http_client=http)
        ) as client:
            listed = await client.list_tools()
    return {tool.name: tool for tool in listed.tools}


async def _document_id(round_trip: RoundTrip, *paragraphs: str, **fields: str) -> str:
    response = await round_trip.ingest(*paragraphs, filename="규정.docx", fields=fields or None)
    assert response.status_code == 202
    await round_trip.work()
    document_id: str = response.json()["document_id"]
    return document_id


async def test_도구_목록은_셋이고_모두_읽기_전용_표지와_판이_든_출력_스키마가_있다(
    round_trip: RoundTrip,
) -> None:
    tools = await _tools(round_trip)

    assert set(tools) == {"search", "get_document", "list_knowledge_bases"}
    models = {
        "search": SearchOutput,
        "get_document": DocumentOutput,
        "list_knowledge_bases": KnowledgeBasesOutput,
    }
    for name, tool in tools.items():
        annotations = tool.annotations
        assert annotations is not None
        assert (
            annotations.read_only_hint,
            annotations.destructive_hint,
            annotations.idempotent_hint,
            annotations.open_world_hint,
        ) == (True, False, True, False), name
        schema = tool.output_schema
        assert schema is not None
        assert "format_version" in schema["required"], name
        assert schema["properties"].keys() == models[name].model_json_schema()["properties"].keys()


async def test_세_도구의_결과가_스키마와_형식의_판_1_0_0에_맞는다(round_trip: RoundTrip) -> None:
    document_id = await _document_id(round_trip, *휴가)

    searched = output(await round_trip.search("연차휴가"))
    document = document_output(await round_trip.get_document(document_id, include_text=True))
    listed = knowledge_bases_output(await round_trip.list_knowledge_bases())

    assert [searched.format_version, document.format_version, listed.format_version] == [
        FORMAT_VERSION
    ] * 3
    assert FORMAT_VERSION == "1.0.0"


async def test_get_document는_문서_정보와_조각_수를_싣고_글은_요청할_때만_싣는다(
    round_trip: RoundTrip,
) -> None:
    document_id = await _document_id(
        round_trip,
        *휴가,
        metadata=json.dumps({"부서": "인사"}, ensure_ascii=False),
        updated_at="2026-03-01T09:00:00+09:00",
    )
    searched = output(await round_trip.search("연차휴가")).results

    without_text = document_output(await round_trip.get_document(document_id))
    with_text = document_output(await round_trip.get_document(document_id, include_text=True))

    assert str(without_text.document_id) == document_id
    assert (without_text.source, without_text.key, without_text.group) == (
        "default",
        "규정.docx",
        "default",
    )
    # 제목은 수집에서 정한다(파일 이름의 이름 부분). 본문의 첫 제목이 아니다.
    assert (without_text.title, without_text.mime) == ("규정", _DOCX_MIME)
    assert without_text.size_bytes > 0
    assert without_text.metadata == {"부서": "인사"}
    assert without_text.updated_at.isoformat() == "2026-03-01T00:00:00+00:00"
    assert without_text.chunk_counts == {"default": len(searched)}
    assert (without_text.text, without_text.next_offset) == (None, None)
    assert without_text.text_length == len(휴가_전문)
    assert (with_text.text, with_text.next_offset) == (휴가_전문, None)
    assert with_text.text_length == len(휴가_전문)


async def test_수정한_내용을_아직_파싱하지_않았으면_길이와_글과_next_offset이_모두_null이다(
    round_trip: RoundTrip,
) -> None:
    document_id = await _document_id(round_trip, *휴가)
    changed = await round_trip.ingest(*출장, filename="규정.docx")
    assert changed.json()["document_id"] == document_id

    stale = document_output(await round_trip.get_document(document_id, include_text=True))
    await round_trip.work()
    fresh = document_output(await round_trip.get_document(document_id, include_text=True))

    assert (stale.text_length, stale.text, stale.next_offset) == (None, None, None)
    assert fresh.text == "# 제2조 출장\n\n출장비는 실비로 정산한다."


@pytest.fixture
def small_window(run_server: Callable[..., RunningServer]) -> Iterator[RoundTrip]:
    """전문 창의 상한이 40자인 서버의 왕복 도우미. 서버는 동기 픽스처에서만 띄운다."""
    with wire_stubs(run_server(document_text_max_chars=_SMALL_LIMIT)) as round_trip:
        yield round_trip


async def _windows(round_trip: RoundTrip, document_id: str) -> list[DocumentOutput]:
    """`next_offset`을 그대로 되돌려 주며 전문을 끝까지 읽은 창들."""
    windows: list[DocumentOutput] = []
    offset: int | None = 0
    while offset is not None:
        window = document_output(
            await round_trip.get_document(document_id, include_text=True, offset=offset)
        )
        windows.append(window)
        offset = window.next_offset
        assert len(windows) < 100, "next_offset이 앞으로 나아가지 않는다"
    return windows


async def test_창을_next_offset으로_이어_읽으면_전문과_같고_창마다_상한_안이다(
    small_window: RoundTrip,
) -> None:
    긴_문단 = "가나다라마바사아자차" * 7  # 70자. 상한 40자보다 길다.
    paragraphs = ("첫째 문단이다.", 긴_문단, "끝 문단")
    document_id = await _document_id(small_window, "제목", *paragraphs)
    full = "# 제목\n\n" + "\n\n".join(paragraphs)

    windows = await _windows(small_window, document_id)

    texts = [window.text or "" for window in windows]
    assert "".join(texts) == full
    assert all(len(text) <= _SMALL_LIMIT for text in texts)
    assert len(windows) > 2
    assert {window.text_length for window in windows} == {len(full)}
    # 블록 경계에서 자른 창의 다음 창은 그 빈 줄로 시작하고, 긴 블록은 상한에서 잘린다.
    assert texts[0] == "# 제목\n\n첫째 문단이다."
    assert texts[1].startswith("\n\n")
    assert len(texts[1]) == _SMALL_LIMIT


async def test_max_chars를_주면_설정의_상한_안에서_그_크기로_자른다(
    small_window: RoundTrip,
) -> None:
    document_id = await _document_id(small_window, "제목", "가" * 30)

    default = document_output(
        await small_window.get_document(document_id, include_text=True, offset=7)
    )
    narrow = document_output(
        await small_window.get_document(document_id, include_text=True, offset=7, max_chars=10)
    )

    # 전문은 "# 제목\n\n" 여섯 글자 뒤에 가 서른 개라, offset 7부터 남은 글은 스물아홉 글자다.
    assert (default.text, default.next_offset) == ("가" * 29, None)
    assert (narrow.text, narrow.next_offset) == ("가" * 10, 17)


async def test_offset이_길이와_같으면_빈_글이고_넘으면_잘못된_인자다(round_trip: RoundTrip) -> None:
    document_id = await _document_id(round_trip, *휴가)

    at_end = document_output(
        await round_trip.get_document(document_id, include_text=True, offset=len(휴가_전문))
    )
    beyond = error_body(
        await round_trip.get_document(document_id, include_text=True, offset=len(휴가_전문) + 1)
    )
    ignored = document_output(await round_trip.get_document(document_id, offset=10**9))

    assert (at_end.text, at_end.next_offset) == ("", None)
    assert (beyond["code"], beyond["status"]) == ("invalid_argument", 422)
    assert (ignored.text, ignored.next_offset) == (None, None)


async def test_max_chars와_offset의_범위_위반은_문서와_상관없이_잘못된_인자다(
    small_window: RoundTrip,
) -> None:
    results = [
        await small_window.get_document(uuid4(), max_chars=0),
        await small_window.get_document(uuid4(), max_chars=_SMALL_LIMIT + 1),
        await small_window.get_document(uuid4(), offset=-1),
        await small_window.get_document(uuid4(), include_text=True, max_chars=0),
        await small_window.get_document(uuid4(), include_text=True, offset=-1),
    ]

    bodies = [error_body(result) for result in results]
    assert [(body["code"], body["status"]) for body in bodies] == [("invalid_argument", 422)] * 5


async def test_볼_수_없는_문서는_offset이_길이를_넘어도_없는_문서와_같은_오류다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_knowledge_base("격리")
    document_id = await _document_id(round_trip, *휴가)
    isolated = await round_trip.issue_reader("격리")

    hidden = error_body(
        await round_trip.get_document(document_id, token=isolated, include_text=True, offset=10**9)
    )
    missing = error_body(
        await round_trip.get_document(uuid4(), token=isolated, include_text=True, offset=10**9)
    )

    assert hidden["code"] == missing["code"] == "document_not_found"


async def test_창_사이에_같은_키로_다시_수집하면_새_내용이_파싱되기_전의_창은_null_셋이다(
    round_trip: RoundTrip,
) -> None:
    document_id = await _document_id(round_trip, *휴가)
    first = document_output(
        await round_trip.get_document(document_id, include_text=True, max_chars=14)
    )
    assert first.next_offset is not None
    await round_trip.ingest(*출장, filename="규정.docx")

    middle = document_output(
        await round_trip.get_document(document_id, include_text=True, offset=first.next_offset)
    )
    await round_trip.work()
    after = document_output(
        await round_trip.get_document(document_id, include_text=True, offset=first.next_offset)
    )

    assert (middle.text_length, middle.text, middle.next_offset) == (None, None, None)
    # 파싱이 끝나면 같은 `offset`이 새 전문의 창을 가리킨다. 갱신일은 호출자가 넘긴 값이라 신호가
    # 아니다(명세 "MCP 도구"). 받는 쪽이 아는 것은 `text_length`가 새 전문의 것이라는 점뿐이다.
    new_full = "# 제2조 출장\n\n출장비는 실비로 정산한다."
    assert after.text_length == len(new_full)
    assert after.text == new_full[first.next_offset :]


async def test_하위_제목은_수준만큼_샵을_단_전문에_든다(round_trip: RoundTrip) -> None:
    response = await round_trip.ingest_bytes(
        docx_outline((1, "규정"), (2, "제1조"), "본문입니다."), "구조.docx"
    )
    await round_trip.work()
    document_id: str = response.json()["document_id"]

    document = document_output(await round_trip.get_document(document_id, include_text=True))

    assert document.text == "# 규정\n\n## 제1조\n\n본문입니다."


async def test_없는_문서와_UUID가_아닌_식별자는_오류_결과다(round_trip: RoundTrip) -> None:
    missing = error_body(await round_trip.get_document(uuid4()))
    malformed = error_body(await round_trip.get_document("not-a-uuid"))

    assert (missing["code"], missing["status"]) == ("document_not_found", 404)
    assert (malformed["code"], malformed["status"]) == ("invalid_argument", 422)
    assert "not-a-uuid" not in json.dumps(malformed)


async def test_범위_밖_지식베이스는_chunk_counts와_목록에_이름도_없다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_knowledge_base("추가")
    round_trip.link_group("default", "추가")
    round_trip.add_knowledge_base("격리")
    document_id = await _document_id(round_trip, *휴가)
    everything = await round_trip.issue_reader()
    only_default = await round_trip.issue_reader("default")
    only_extra = await round_trip.issue_reader("추가")
    only_isolated = await round_trip.issue_reader("격리")

    async def counts(token: str) -> dict[str, int]:
        return document_output(await round_trip.get_document(document_id, token=token)).chunk_counts

    async def names(token: str) -> list[str]:
        listed = knowledge_bases_output(await round_trip.list_knowledge_bases(token=token))
        return sorted(item.name for item in listed.knowledge_bases)

    assert sorted(await counts(everything)) == ["default", "추가"]
    assert list(await counts(only_default)) == ["default"]
    assert await counts(only_extra) == {"추가": 0}
    assert await names(everything) == ["default", "격리", "추가"]
    assert await names(only_default) == ["default"]
    assert await names(only_isolated) == ["격리"]


async def test_문서가_든_그룹을_가진_지식베이스가_모두_범위_밖이면_없는_문서와_같은_오류다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_knowledge_base("격리")
    document_id = await _document_id(round_trip, *휴가)
    isolated = await round_trip.issue_reader("격리")

    hidden = error_body(await round_trip.get_document(document_id, token=isolated))
    missing = error_body(await round_trip.get_document(uuid4(), token=isolated))

    assert hidden["code"] == missing["code"] == "document_not_found"
    assert (hidden["status"], hidden["title"]) == (missing["status"], missing["title"])
    assert set(hidden) == {"type", "title", "status", "code", "request_id"}


async def test_list_knowledge_bases는_문서_수와_기본_표시를_싣고_색인_상태와_상관없다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_knowledge_base("비어있음")
    await round_trip.ingest(*휴가, filename="휴가.docx")
    await round_trip.ingest(*출장, filename="출장.docx")

    before_work = knowledge_bases_output(await round_trip.list_knowledge_bases())
    await round_trip.work()
    after_work = knowledge_bases_output(await round_trip.list_knowledge_bases())

    for listed in (before_work, after_work):
        assert {
            item.name: (item.document_count, item.is_default) for item in listed.knowledge_bases
        } == {"default": (2, True), "비어있음": (0, False)}
    default = next(item for item in after_work.knowledge_bases if item.name == "default")
    assert default.description == ""
