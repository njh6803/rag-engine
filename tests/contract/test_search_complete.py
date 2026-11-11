"""검색의 완성(티켓 09): 필터, 리랭크, 시간 제한, 설정 불일치(스토리 4, 17, 20).

서버는 실제 uvicorn이고 도구는 공식 MCP SDK의 클라이언트로 HTTP 접속해 부른다. 임베딩 서버와
리랭커만 스텁이다(`tests/support/round_trip.py`).
"""

import json
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from tests.harness import LogCapture, RunningServer
from tests.support.docx_files import docx_bytes
from tests.support.round_trip import RoundTrip, error_body, output, wire_stubs
from tests.support.tei_stub import SECRET_MESSAGE

from rag_engine.server.tool_models import SearchOutput

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")
_PROBLEM_FIELDS = {"type", "title", "status", "code", "request_id"}
_WARM_UP_TRIES = 5


def _keys(found: SearchOutput) -> list[str]:
    return [item.key for item in found.results]


async def _index_both(round_trip: RoundTrip, **fields_by_name: dict[str, str]) -> None:
    """휴가와 출장을 `휴가.docx`와 `출장.docx`로 수집하고 작업자를 돌린다. 문서마다 폼 칸을
    `휴가=`, `출장=`으로 줄 수 있다."""
    await round_trip.ingest(*휴가, filename="휴가.docx", fields=fields_by_name.get("휴가"))
    await round_trip.ingest(*출장, filename="출장.docx", fields=fields_by_name.get("출장"))
    await round_trip.work()


async def test_메타데이터와_갱신일이_결과에_실리고_바꾼_값이_unchanged_수집_뒤_검색에_나온다(
    round_trip: RoundTrip,
) -> None:
    data = docx_bytes(*휴가)
    first = await round_trip.ingest_bytes(
        data,
        fields={
            "metadata": json.dumps({"부서": "인사"}, ensure_ascii=False),
            "updated_at": "2026-03-01T09:00:00+09:00",
        },
    )
    assert first.status_code == 202
    await round_trip.work()

    before = output(await round_trip.search("연차휴가")).results[0]
    again = await round_trip.ingest_bytes(
        data,
        fields={
            "metadata": json.dumps({"부서": "총무", "개정": 2}, ensure_ascii=False),
            "updated_at": "2026-04-01T00:00:00Z",
        },
    )
    after = output(await round_trip.search("연차휴가")).results[0]

    assert (before.metadata, before.updated_at) == (
        {"부서": "인사"},
        datetime(2026, 3, 1, 0, 0, tzinfo=UTC),
    )
    assert again.status_code == 200
    assert (again.json()["action"], again.json()["job_id"]) == ("unchanged", None)
    assert (after.metadata, after.updated_at) == (
        {"부서": "총무", "개정": 2},
        datetime(2026, 4, 1, 0, 0, tzinfo=UTC),
    )
    assert after.document_id == before.document_id


async def test_그룹_필터는_그_그룹의_문서만_내고_없는_그룹_이름은_빈_결과다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_group("인사", "default")
    await _index_both(round_trip, 휴가={"group": "인사"})

    async def keys(*groups: str) -> list[str]:
        found = output(await round_trip.search("규정", filter={"groups": list(groups)}))
        return sorted(_keys(found))

    assert await keys("인사") == ["휴가.docx"]
    assert await keys("default") == ["출장.docx"]
    assert await keys("인사", "default") == ["출장.docx", "휴가.docx"]
    assert await keys("없는그룹") == []
    assert await keys("없는그룹", "인사") == ["휴가.docx"]


async def test_갱신일_기간은_이후를_포함하고_이전을_포함하지_않는다(round_trip: RoundTrip) -> None:
    await _index_both(
        round_trip,
        휴가={"updated_at": "2026-01-01T00:00:00Z"},
        출장={"updated_at": "2026-06-01T00:00:00Z"},
    )

    async def keys(**window: str) -> list[str]:
        return _keys(output(await round_trip.search("규정", filter=window)))

    assert await keys(updated_after="2026-06-01T00:00:00Z") == ["출장.docx"]
    assert await keys(updated_after="2026-06-01T09:00:00+09:00") == ["출장.docx"]
    assert await keys(updated_after="2026-06-01T00:00:01Z") == []
    assert await keys(updated_before="2026-06-01T00:00:00Z") == ["휴가.docx"]
    assert await keys(updated_before="2026-01-01T00:00:00Z") == []
    assert await keys(
        updated_after="2026-01-01T00:00:00Z", updated_before="2026-06-01T00:00:00Z"
    ) == ["휴가.docx"]


@pytest.mark.parametrize("instant", ["2026-06-01", "2026-06-01T00:00:00", "어제", ""])
async def test_오프셋이_없거나_읽을_수_없는_시각은_invalid_argument다(
    round_trip: RoundTrip, instant: str
) -> None:
    after = error_body(await round_trip.search("규정", filter={"updated_after": instant}))
    before = error_body(await round_trip.search("규정", filter={"updated_before": instant}))

    assert (after["code"], before["code"]) == ("invalid_argument", "invalid_argument")
    # `detail`이 없어 잘못된 입력 값이 오류에 되풀이되지 않는다.
    assert set(after) == set(before) == _PROBLEM_FIELDS


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": ""},
        {"query": "  \n"},
        {"query": "규정", "top_k": 0},
        {"query": "규정", "top_k": -1},
    ],
)
async def test_빈_질의와_범위_밖_top_k는_invalid_argument다(
    round_trip: RoundTrip, arguments: dict[str, object]
) -> None:
    body = error_body(await round_trip.call("search", arguments))

    assert body["code"] == "invalid_argument"


async def test_상한을_넘는_top_k는_invalid_argument이고_상한은_통과한다(
    round_trip: RoundTrip,
) -> None:
    await _index_both(round_trip)
    limit = round_trip.server.settings.search_max_top_k

    over = error_body(await round_trip.search("규정", top_k=limit + 1))
    at_limit = output(await round_trip.search("규정", top_k=limit))

    assert over["code"] == "invalid_argument"
    assert len(at_limit.results) == 2


async def test_리랭커가_순서를_바꾸고_점수는_리랭크_점수다(round_trip: RoundTrip) -> None:
    await _index_both(round_trip)
    reranker = round_trip.reranker_stub
    # 점수가 모두 같으면 RRF 순서가 그대로 남는다(안정 정렬). 그 순서가 기준이다.
    reranker.score_with = lambda query, text: 0.0
    baseline = output(await round_trip.search("규정"))
    assert [item.score for item in baseline.results] == [0.0, 0.0]
    favored = baseline.results[-1]
    reranker.score_with = lambda query, text: 1.0 if favored.text in text else 0.0

    reranked = output(await round_trip.search("규정"))

    assert [item.chunk_id for item in reranked.results] == [
        item.chunk_id for item in reversed(baseline.results)
    ]
    assert [(item.rank, item.score) for item in reranked.results] == [(1, 1.0), (2, 0.0)]
    sent = reranker.bodies("/rerank")[-1]
    assert sent["query"] == "규정"
    assert isinstance(sent["texts"], list) and len(sent["texts"]) == 2


async def test_리랭커가_없으면_RRF_점수로_나가고_리랭커를_부르지_않는다(
    round_trip: RoundTrip,
) -> None:
    await _index_both(round_trip)
    round_trip.drop_reranker()

    found = output(await round_trip.search("규정"))

    assert len(found.results) == 2
    assert all(item.score > 0 for item in found.results)
    assert round_trip.reranker_stub.count("/rerank") == 0


async def test_리랭커가_실패하면_RRF로_대신하지_않고_search_unavailable이다(
    round_trip: RoundTrip,
) -> None:
    await _index_both(round_trip)
    round_trip.reranker_stub.fail("/rerank", 500)

    result = await round_trip.search("규정")

    body = error_body(result)
    assert body["code"] == "search_unavailable"
    assert SECRET_MESSAGE not in json.dumps(body)


async def test_리랭커의_모델이_지식베이스_설정과_다르면_search_unavailable이다(
    round_trip: RoundTrip,
) -> None:
    await _index_both(round_trip)
    round_trip.reranker_stub.model_id = "다른/리랭커"

    body = error_body(await round_trip.search("규정"))

    assert body["code"] == "search_unavailable"
    assert round_trip.reranker_stub.count("/rerank") == 0


async def test_임베딩_끝점의_모델이_판에_적힌_모델과_다르면_search_unavailable이다(
    round_trip: RoundTrip,
) -> None:
    await _index_both(round_trip)
    round_trip.stub.model_id = "다른/임베딩"

    body = error_body(await round_trip.search("규정"))

    assert body["code"] == "search_unavailable"
    assert round_trip.reranker_stub.count("/rerank") == 0


@pytest.fixture
def one_second_limit(run_server: Callable[..., RunningServer]) -> Iterator[RoundTrip]:
    """검색 시간 제한이 1초(설정의 최솟값)인 서버의 왕복 도우미. 서버는 동기 픽스처에서만 띄운다."""
    with wire_stubs(run_server(search_timeout_seconds=1)) as round_trip:
        yield round_trip


async def test_시간_제한을_넘기면_search_unavailable이다(one_second_limit: RoundTrip) -> None:
    round_trip = one_second_limit
    await _index_both(round_trip)
    # 준비: 처음 몇 번은 형태소 모델을 올리느라 1초를 넘길 수 있다. 늦지 않은 검색이 제한 안에
    # 끝나는 것을 확인한 뒤에 답을 늦춘다.
    for _ in range(_WARM_UP_TRIES):
        if (await round_trip.search("규정")).is_error is not True:
            break
    else:
        pytest.fail(f"검색이 {_WARM_UP_TRIES}번 모두 1초 제한 안에 끝나지 않았다")
    round_trip.reranker_stub.rerank_delay_seconds = 3.0

    started = time.monotonic()
    body = error_body(await round_trip.search("규정"))
    elapsed = time.monotonic() - started

    assert body["code"] == "search_unavailable"
    # 리랭커의 답(3초)을 기다리지 않고 제한(1초)에서 끊는다.
    assert elapsed < 3.0


async def test_search_로그_이벤트는_단계별_지연만_싣는다(
    round_trip: RoundTrip, log_capture: LogCapture
) -> None:
    await _index_both(round_trip)

    await round_trip.search("연차휴가", top_k=1, knowledge_base="default")

    (searched,) = log_capture.events("search", count=1)
    standard = {"time", "level", "logger", "event", "request_id"}
    assert set(searched) - standard == {"duration_ms", "embedding_ms", "sql_ms", "rerank_ms"}
    latencies = [searched[name] for name in ("duration_ms", "embedding_ms", "sql_ms", "rerank_ms")]
    assert all(isinstance(value, float) and value > 0 for value in latencies)
    duration, embedding, sql, rerank = latencies
    assert isinstance(duration, float)
    assert isinstance(embedding, float) and isinstance(sql, float) and isinstance(rerank, float)
    assert duration >= embedding + sql + rerank
