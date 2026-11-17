"""검색 도구의 `min_score`(스토리 34~38, ADR 0017, 티켓 search-eval 20).

서버는 실제 uvicorn이고 도구는 공식 MCP SDK의 클라이언트로 HTTP 접속해 부른다. 임베딩 서버와
리랭커만 스텁이다. 리랭커 스텁은 모든 조각에 같은 점수(0.4)를 매긴다.
"""

import httpx2
import psycopg
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from tests.support.round_trip import RoundTrip, error_body, output

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
_PROBLEM_FIELDS = {"type", "title", "status", "code", "request_id"}
_RERANK_SCORE = 0.4


async def _index(round_trip: RoundTrip) -> None:
    round_trip.reranker_stub.score_with = lambda query, text: _RERANK_SCORE
    await round_trip.ingest(*휴가)
    await round_trip.work()


def _set_default(round_trip: RoundTrip, min_score: float | None) -> None:
    with psycopg.connect(round_trip.server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE knowledge_bases SET min_score = %s", [min_score])


async def test_도구_목록의_inputSchema에_선택_인자_min_score가_있다(round_trip: RoundTrip) -> None:
    async with httpx2.AsyncClient(headers=round_trip.auth()) as http:
        async with Client(
            streamable_http_client(round_trip.server.mcp_url, http_client=http)
        ) as client:
            listed = await client.list_tools()

    (tool,) = [tool for tool in listed.tools if tool.name == "search"]
    schema = tool.input_schema
    assert "min_score" in schema["properties"]
    assert "min_score" not in schema["required"]
    description = tool.description or ""
    assert "min_score" in description
    assert "리랭커가 없는 지식베이스에 주면 invalid_argument로 거부한다" in description


async def test_리랭크_점수가_min_score보다_낮으면_빠지고_같으면_남는다(
    round_trip: RoundTrip,
) -> None:
    await _index(round_trip)

    kept = output(await round_trip.search("연차휴가", min_score=_RERANK_SCORE))
    dropped = output(await round_trip.search("연차휴가", min_score=0.5))
    unfiltered = output(await round_trip.search("연차휴가"))

    assert [len(kept.results), len(dropped.results), len(unfiltered.results)] == [1, 0, 1]
    assert kept.results[0].score == _RERANK_SCORE


async def test_남은_조각이_없으면_오류가_아니라_쓴_지식베이스를_밝힌_빈_결과다(
    round_trip: RoundTrip,
) -> None:
    await _index(round_trip)

    result = await round_trip.search("연차휴가", min_score=0.9)

    found = output(result)
    assert (found.knowledge_base, found.results, result.is_error) == ("default", [], False)


async def test_지식베이스의_기본값은_요청_인자가_없을_때_쓰이고_요청_인자가_이긴다(
    round_trip: RoundTrip,
) -> None:
    await _index(round_trip)
    _set_default(round_trip, 0.5)

    by_default = output(await round_trip.search("연차휴가"))
    overridden = output(await round_trip.search("연차휴가", min_score=0.0))

    assert [len(by_default.results), len(overridden.results)] == [0, 1]


async def test_범위_밖과_유한하지_않은_값은_invalid_argument이고_값을_싣지_않는다(
    round_trip: RoundTrip,
) -> None:
    await _index(round_trip)

    for value in (1.5, -0.1, "nan", "inf", "-inf"):
        body = error_body(await round_trip.search("연차휴가", min_score=value))

        assert (body["code"], body["status"]) == ("invalid_argument", 422), value
        assert set(body) == _PROBLEM_FIELDS, value
        assert str(value) not in str(body), value


async def test_숫자가_아닌_값은_유스케이스에_닿기_전에_SDK의_입력_검증이_거부한다(
    round_trip: RoundTrip,
) -> None:
    await _index(round_trip)

    result = await round_trip.search("연차휴가", min_score="abc")

    assert result.is_error is True
    assert result.structured_content is None


async def test_리랭커가_없는_지식베이스에_min_score를_주면_0도_invalid_argument다(
    round_trip: RoundTrip,
) -> None:
    await _index(round_trip)
    round_trip.drop_reranker()

    zero = error_body(await round_trip.search("연차휴가", min_score=0))
    half = error_body(await round_trip.search("연차휴가", min_score=0.5))
    without = output(await round_trip.search("연차휴가"))

    assert (zero["code"], half["code"]) == ("invalid_argument", "invalid_argument")
    assert len(without.results) == 1


async def test_리랭커가_빈_채_기본값이_있는_행은_요청_인자가_없으면_search_unavailable이다(
    round_trip: RoundTrip,
) -> None:
    await _index(round_trip)
    round_trip.drop_reranker()
    _set_default(round_trip, 0.5)

    unavailable = error_body(await round_trip.search("연차휴가"))
    both = error_body(await round_trip.search("연차휴가", min_score=0.5))

    assert (unavailable["code"], unavailable["status"]) == ("search_unavailable", 503)
    assert both["code"] == "invalid_argument"
