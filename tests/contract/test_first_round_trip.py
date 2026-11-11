"""첫 왕복(티켓 07): 수집 API로 DOCX를 넣고 작업자가 한 번 돌면 MCP `search`가 근거 위치가 붙은
조각을 낸다(스토리 12~16, 18, 19, 24, 25, 38).

서버는 실제 uvicorn이고 검색은 공식 MCP SDK의 클라이언트로 HTTP 접속해 부른다. 작업자는 같은
설정으로 한 번 돈다. 임베딩 서버만 스텁이다.
"""

from tests.harness import LogCapture
from tests.support.round_trip import RoundTrip, output

from rag_engine.server.tool_models import FORMAT_VERSION

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")


async def test_수집한_DOCX가_작업자_한_번_뒤_근거_위치와_함께_검색된다(
    round_trip: RoundTrip,
) -> None:
    # 리랭크 점수는 `test_search_complete.py`가 본다. 여기는 RRF 점수가 양수인 첫 왕복이다.
    round_trip.drop_reranker()
    ingested = await round_trip.ingest(*휴가)
    assert ingested.status_code == 202
    assert await round_trip.work() == 1

    found = output(await round_trip.search("연차휴가"))

    assert (found.format_version, found.knowledge_base) == (FORMAT_VERSION, "default")
    first = found.results[0]
    assert "연차휴가" in first.text
    assert (first.key, first.source, first.rank) == ("규정.docx", "default", 1)
    assert str(first.document_id) == ingested.json()["document_id"]
    assert first.location.section == ["제1조 휴가"]
    assert first.location.page is None
    assert first.location.block_range[0] <= first.location.block_range[1]
    assert first.score > 0
    assert first.updated_at.tzinfo is not None


async def test_작업자가_돌기_전에는_결과가_없다(round_trip: RoundTrip) -> None:
    await round_trip.ingest(*휴가)

    found = output(await round_trip.search("연차휴가"))

    assert found.results == []


async def test_수집이_도는_동안_검색은_옛_조각만_내고_작업_뒤에는_새_조각만_낸다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.ingest(*휴가)
    await round_trip.work()
    await round_trip.ingest(*출장)

    before = output(await round_trip.search("연차휴가 출장비"))
    await round_trip.work()
    after = output(await round_trip.search("연차휴가 출장비"))

    assert [("연차휴가" in item.text, "출장비" in item.text) for item in before.results] == [
        (True, False)
    ]
    assert [("연차휴가" in item.text, "출장비" in item.text) for item in after.results] == [
        (False, True)
    ]


async def test_조사가_달라도_한국어_질의가_형태소로_키워드_검색된다(round_trip: RoundTrip) -> None:
    await round_trip.ingest(*휴가, filename="휴가.docx")
    await round_trip.ingest(*출장, filename="출장.docx")
    await round_trip.work()

    found = output(await round_trip.search("연차휴가가 며칠이나 발생하는지"))

    assert "연차휴가" in found.results[0].text
    assert found.results[0].key == "휴가.docx"


async def test_개수를_주면_그만큼만_낸다(round_trip: RoundTrip) -> None:
    await round_trip.ingest(*휴가, filename="휴가.docx")
    await round_trip.ingest(*출장, filename="출장.docx")
    await round_trip.work()

    found = output(await round_trip.search("규정", top_k=1))

    assert [item.rank for item in found.results] == [1]


async def test_지식베이스를_이름으로_고르고_안_고르면_기본_지식베이스를_쓴다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.ingest(*휴가)
    await round_trip.work()

    by_default = output(await round_trip.search("연차휴가"))
    by_name = output(await round_trip.search("연차휴가", knowledge_base="default"))

    assert by_default.knowledge_base == by_name.knowledge_base == "default"
    assert [item.chunk_id for item in by_default.results] == [
        item.chunk_id for item in by_name.results
    ]


async def test_수집_요청_ID가_작업자_로그의_요청_ID로_이어진다(
    round_trip: RoundTrip, log_capture: LogCapture
) -> None:
    ingested = await round_trip.ingest(*휴가)
    request_id = ingested.headers["X-Request-Id"]

    await round_trip.work()

    (started,) = log_capture.events("job_started", count=1)
    (finished,) = log_capture.events("job_finished", count=1)
    assert [started["request_id"], finished["request_id"]] == [request_id, request_id]
    assert finished["job_id"] == ingested.json()["job_id"]
    assert finished["document_id"] == ingested.json()["document_id"]
    assert (finished["kind"], finished["attempts"]) == ("index_document", 1)
    assert (finished["result"], finished["error_code"]) == ("succeeded", None)
    for field in ("duration_ms", "parse_ms", "embedding_ms", "write_ms"):
        elapsed = finished[field]
        assert isinstance(elapsed, float) and elapsed > 0


async def test_로그에는_문서의_키와_제목과_질의가_없고_검색은_지연만_남는다(
    round_trip: RoundTrip, log_capture: LogCapture
) -> None:
    await round_trip.ingest(*휴가)
    await round_trip.work()

    await round_trip.search("연차휴가")

    (searched,) = log_capture.events("search", count=1)
    assert {"embedding_ms", "sql_ms", "duration_ms"} <= set(searched)
    text = log_capture.text()
    for secret in ("규정.docx", "제1조 휴가", "연차휴가"):
        assert secret not in text
