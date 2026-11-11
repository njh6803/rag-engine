"""도구 오류와 로그(티켓 09, 스토리 26, 37): 오류 코드마다 한 사례, 로그에 남지 않는 것.

서버는 실제 uvicorn이고 도구는 공식 MCP SDK의 클라이언트로 HTTP 접속해 부른다.
"""

import psycopg
from tests.harness import LogCapture
from tests.support.round_trip import RoundTrip, error_body

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
_PROBLEM_FIELDS = {"type", "title", "status", "code", "request_id"}


async def test_도구_오류는_코드마다_JSON_글_하나이고_detail이_없다(round_trip: RoundTrip) -> None:
    await round_trip.ingest(*휴가)
    await round_trip.work()
    round_trip.reranker_stub.fail("/rerank", 500)
    not_found = await round_trip.search("연차휴가", knowledge_base="없는지식베이스")
    no_document = await round_trip.get_document("00000000-0000-7000-8000-000000000000")
    invalid = await round_trip.search("")
    unavailable = await round_trip.search("연차휴가")
    with psycopg.connect(round_trip.server.settings.database_url, autocommit=True) as connection:
        connection.execute("ALTER TABLE chunks RENAME TO chunks_removed")
    internal = await round_trip.search("연차휴가")

    cases = {
        "knowledge_base_not_found": (not_found, 404),
        "document_not_found": (no_document, 404),
        "invalid_argument": (invalid, 422),
        "search_unavailable": (unavailable, 503),
        "internal_error": (internal, 500),
    }
    for code, (result, status) in cases.items():
        body = error_body(result)
        assert (body["code"], body["status"]) == (code, status), code
        assert set(body) == _PROBLEM_FIELDS, code
        assert len(result.content) == 1, code


async def test_로그에는_질의와_문서의_글_키_제목과_토큰_원문이_없다(
    round_trip: RoundTrip, log_capture: LogCapture
) -> None:
    reader = await round_trip.issue_reader("default")
    ingested = await round_trip.ingest(*휴가, filename="비밀규정.docx")
    await round_trip.work()

    await round_trip.search("연차휴가", token=reader)
    await round_trip.get_document(ingested.json()["document_id"], include_text=True, token=reader)
    await round_trip.list_knowledge_bases(token=reader)
    await round_trip.search("연차휴가", token=reader, knowledge_base="없는지식베이스")
    round_trip.reranker_stub.fail("/rerank", 500)
    await round_trip.search("연차휴가", token=reader)

    # 지연을 남기는 `search` 이벤트는 끝난 검색에만 있다. 없는 지식베이스와 리랭커 실패의 검색은
    # 결과가 없어 남기지 않는다.
    assert len(log_capture.events("search", count=1)) == 1
    text = log_capture.text()
    secrets = [
        "연차휴가",
        "입사 일 년",
        "제1조 휴가",
        "비밀규정.docx",
        "없는지식베이스",
        reader,
        round_trip.server.admin_token,
    ]
    for secret in secrets:
        assert secret not in text, secret
