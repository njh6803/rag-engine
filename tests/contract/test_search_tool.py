"""MCP `search` 도구의 계약(명세 "MCP 도구", 티켓 07).

도구 목록에서의 표지와 출력 스키마, 결과의 `format_version`, 범위 밖 지식베이스의 오류를 공식 SDK
클라이언트로 HTTP 접속해 본다(`.claude/rules/tests.md`).
"""

import httpx2
import psycopg
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from tests.support.round_trip import RoundTrip, error_body, output

from rag_engine.server.tool_models import FORMAT_VERSION, SearchOutput


async def _tools(round_trip: RoundTrip) -> dict[str, object]:
    async with httpx2.AsyncClient(headers=round_trip.auth()) as http:
        async with Client(
            streamable_http_client(round_trip.server.mcp_url, http_client=http)
        ) as client:
            listed = await client.list_tools()
    return {tool.name: tool for tool in listed.tools}


async def test_search_도구는_읽기_전용_표지와_출력_스키마를_공개한다(round_trip: RoundTrip) -> None:
    tools = await _tools(round_trip)

    tool = tools["search"]
    assert getattr(tool, "annotations") is not None  # noqa: B009
    annotations = getattr(tool, "annotations")  # noqa: B009
    assert (
        annotations.read_only_hint,
        annotations.destructive_hint,
        annotations.idempotent_hint,
        annotations.open_world_hint,
    ) == (True, False, True, False)
    schema = getattr(tool, "output_schema")  # noqa: B009
    assert schema["properties"].keys() == SearchOutput.model_json_schema()["properties"].keys()
    assert "format_version" in schema["required"]


async def test_결과는_출력_스키마와_형식의_판_1_0_0에_맞는다(round_trip: RoundTrip) -> None:
    await round_trip.ingest("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
    await round_trip.work()

    found = output(await round_trip.search("연차휴가"))

    assert found.format_version == FORMAT_VERSION == "1.0.0"
    assert found.results != []


async def test_현재_판이_없는_지식베이스는_빈_결과를_낸다(round_trip: RoundTrip) -> None:
    with psycopg.connect(round_trip.server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE knowledge_bases SET current_index_version_id = NULL")

    found = output(await round_trip.search("연차휴가"))

    assert (found.knowledge_base, found.results) == ("default", [])


async def test_토큰_범위_밖_지식베이스는_없는_지식베이스와_같은_오류를_낸다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_knowledge_base("비공개")
    reader = await round_trip.issue_reader("default")

    hidden = error_body(await round_trip.search("연차휴가", token=reader, knowledge_base="비공개"))
    missing = error_body(await round_trip.search("연차휴가", token=reader, knowledge_base="없음"))

    assert hidden["code"] == missing["code"] == "knowledge_base_not_found"
    assert (hidden["status"], hidden["title"]) == (missing["status"], missing["title"])
    assert set(hidden) == {"type", "title", "status", "code", "request_id"}


async def test_이름을_안_주면_범위_밖인_기본_지식베이스도_찾을_수_없다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_knowledge_base("비공개")
    reader = await round_trip.issue_reader("비공개")

    body = error_body(await round_trip.search("연차휴가", token=reader))

    assert body["code"] == "knowledge_base_not_found"
