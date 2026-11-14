"""평가의 LLM 판정 유스케이스(티켓 search-eval 12, 명세 "LLM 관련성 판정").

판정 쌍 고르기, 보고서의 `llm` 숫자(분모가 어디인지), 판정 실행(동시 호출 넷, 일시 실패 재시도 셋,
영구 실패는 그 쌍만 건너뛰고 연이어 나면 멈춤)을 가짜 판정기로 본다. 판정 파일의 줄과 끝점은 이
시험의 일이 아니다.
"""

import asyncio
from collections.abc import Iterable, Sequence
from datetime import date

import pytest
from tests.support.fake_judge import FakeRelevanceJudge

from rag_engine.app.eval_judgments import (
    JUDGE_CONCURRENCY,
    JUDGE_RETRIES,
    PERMANENT_STREAK_LIMIT,
    JudgeOutcome,
    JudgeRunError,
    Judgment,
    JudgmentPair,
    LlmNumbers,
    LlmUnavailable,
    MissingCandidate,
    estimate_dollars,
    judge_pairs,
    llm_summary,
    pending_pairs,
)
from rag_engine.app.eval_run import QueryOutcome, Stage, TopPassage, sha256_text
from rag_engine.domain.errors import ErrorCode, PermanentFailure, TransientFailure
from rag_engine.domain.ports import RelevanceJudge

MODEL = "claude-test"
VERSION = "1"
TODAY = date(2026, 11, 14)


def _passage(
    query: str, text: str, *, document: str = "a.docx", ordinal: int = 0, reached: bool = False
) -> TopPassage:
    return TopPassage(
        document=document,
        ordinal=ordinal,
        reached=reached,
        query_sha256=sha256_text(query),
        text_sha256=sha256_text(text),
        query=query,
        text=text,
    )


def _outcome(
    evidence_id: str, top: Sequence[TopPassage], *, query_list: str = "human"
) -> QueryOutcome:
    return QueryOutcome(
        query_list=query_list,
        evidence_id=evidence_id,
        expected=1,
        reach={Stage.FUSED: ()},
        top=tuple(top),
    )


def _judgment(
    passage: TopPassage, *, relevant: bool, model: str = MODEL, version: str = VERSION
) -> Judgment:
    return Judgment(
        query_sha256=passage.query_sha256,
        text_sha256=passage.text_sha256,
        relevant=relevant,
        model=model,
        prompt_version=version,
        judged_at=TODAY,
    )


def _two_outcomes() -> tuple[list[QueryOutcome], list[TopPassage]]:
    """질의 둘의 상위 조각 넷. 앞의 둘은 q1(`a1`이 기대 근거에 닿음), 뒤의 둘은 q2(`b2`가 닿음)."""
    a1 = _passage("질의1", "글 a", document="a.docx", ordinal=0, reached=True)
    b1 = _passage("질의1", "글 b", document="b.docx", ordinal=0)
    a2 = _passage("질의2", "글 a", document="a.docx", ordinal=0)
    b2 = _passage("질의2", "글 b", document="b.docx", ordinal=0, reached=True)
    return [_outcome("q1", [a1, b1]), _outcome("q2", [b2, a2])], [a1, b1, a2, b2]


def test_판정_쌍은_판정_파일에_없는_것만_첫_등장_순으로_중복_없이_고른다() -> None:
    outcomes, (a1, b1, a2, b2) = _two_outcomes()
    # 같은 질의 글과 조각 글이 다른 질의 목록에서 또 나온다. 같은 쌍이라 한 번만 부른다.
    again = _outcome("q1", [a1], query_list="keyword")

    pairs = pending_pairs(
        [*outcomes, again],
        [_judgment(b1, relevant=True)],
        model=MODEL,
        prompt_version=VERSION,
    )

    assert [(pair.query, pair.text) for pair in pairs] == [
        ("질의1", "글 a"),
        ("질의2", "글 b"),
        ("질의2", "글 a"),
    ]
    assert pairs[0] == JudgmentPair(a1.query_sha256, a1.text_sha256, "질의1", "글 a")
    del a2, b2


@pytest.mark.parametrize(
    "stale",
    [{"model": "다른-모델"}, {"version": "2"}],
    ids=["다른 모델", "다른 지시문 판"],
)
def test_모델이나_지시문_판이_다른_옛_판정은_판정_없음으로_센다(stale: dict[str, str]) -> None:
    outcomes, (a1, *_) = _two_outcomes()

    pairs = pending_pairs(
        outcomes, [_judgment(a1, relevant=True, **stale)], model=MODEL, prompt_version=VERSION
    )

    assert len(pairs) == 4


def test_판정_쌍의_repr에는_질의와_조각의_글이_없다() -> None:
    outcomes, _ = _two_outcomes()

    (pair, *_) = pending_pairs(outcomes, [], model=MODEL, prompt_version=VERSION)

    assert "질의1" not in repr(pair)
    assert "글 a" not in repr(pair)


def test_llm_숫자의_분모는_판정이_있는_조합이고_판정_없음은_전체가_분모다() -> None:
    """넷 가운데 셋만 판정했다. 판정된 셋은 a1(닿음, 관련), b1(관련 없음), b2(닿음, 관련 없음)다.
    관련 비율은 1/3, 닿은 조각의 일치 비율은 닿은 둘(a1, b2) 가운데 a1만 관련이라 1/2이다. 판정
    없음의 비율은 전체 넷 가운데 하나(a2)라 1/4이다."""
    outcomes, (a1, b1, a2, b2) = _two_outcomes()
    judgments = [
        _judgment(a1, relevant=True),
        _judgment(b1, relevant=False),
        _judgment(b2, relevant=False),
    ]

    summary = llm_summary(outcomes, judgments, model=MODEL, prompt_version=VERSION)

    assert isinstance(summary, LlmNumbers)
    assert (summary.pairs, summary.judged) == (4, 3)
    assert summary.relevant_rate == pytest.approx(1 / 3)
    assert summary.agreement_rate == pytest.approx(1 / 2)
    assert summary.unjudged_rate == pytest.approx(1 / 4)
    assert summary.missing_candidates == ()
    del a2


def test_기대_근거에_닿지_않았는데_관련_있다고_본_조각이_빠진_정답_후보다() -> None:
    outcomes, (a1, b1, a2, b2) = _two_outcomes()
    judgments = [_judgment(piece, relevant=piece.text == "글 a") for piece in (a1, b1, a2, b2)]

    summary = llm_summary(outcomes, judgments, model=MODEL, prompt_version=VERSION)

    assert isinstance(summary, LlmNumbers)
    assert summary.missing_candidates == (
        MissingCandidate(query_list="human", evidence_id="q2", document="a.docx", ordinal=0),
    )


def test_같은_조각이_같은_기대_근거에_두_번_나와도_빠진_정답_후보는_한_번이다() -> None:
    first = _passage("질의1", "글 a")
    second = _passage("질의1 다른 표현", "글 a")
    outcomes = [_outcome("q1", [first]), _outcome("q1", [second])]
    judgments = [_judgment(first, relevant=True), _judgment(second, relevant=True)]

    summary = llm_summary(outcomes, judgments, model=MODEL, prompt_version=VERSION)

    assert isinstance(summary, LlmNumbers)
    assert len(summary.missing_candidates) == 1


def test_판정이_있는_조합에_닿은_조각이_없으면_일치_비율은_없다() -> None:
    outcomes, (a1, b1, *_) = _two_outcomes()

    summary = llm_summary(
        outcomes, [_judgment(b1, relevant=True)], model=MODEL, prompt_version=VERSION
    )

    assert isinstance(summary, LlmNumbers)
    assert summary.judged == 1
    assert summary.agreement_rate is None
    assert summary.relevant_rate == 1.0
    del a1


def test_판정_파일이_없으면_까닭과_함께_쓸_수_없다고_낸다() -> None:
    outcomes, _ = _two_outcomes()

    summary = llm_summary(outcomes, None, model=MODEL, prompt_version=VERSION)

    assert isinstance(summary, LlmUnavailable)
    assert "judgments.jsonl" in summary.reason


def test_맞는_줄이_하나도_없으면_까닭과_함께_쓸_수_없다고_낸다() -> None:
    outcomes, (a1, *_) = _two_outcomes()
    stale = [_judgment(a1, relevant=True, version="0")]

    summary = llm_summary(outcomes, stale, model=MODEL, prompt_version=VERSION)

    assert isinstance(summary, LlmUnavailable)
    assert "judge_model" in summary.reason
    assert "judge_prompt_version" in summary.reason


def test_비용_어림은_ADR_0019의_삼천_건_스물여섯_달러에_건수를_비례시킨_값이다() -> None:
    assert estimate_dollars(3000) == pytest.approx(26.0)
    assert estimate_dollars(0) == 0.0
    assert estimate_dollars(300) == pytest.approx(2.6)


def _pairs(count: int) -> list[JudgmentPair]:
    return [_pair(f"질의{number}", f"글{number}") for number in range(count)]


def _pair(query: str, text: str) -> JudgmentPair:
    return JudgmentPair(sha256_text(query), sha256_text(text), query, text)


async def _run(
    judge: RelevanceJudge, pairs: Sequence[JudgmentPair], recorded: list[Judgment]
) -> JudgeOutcome:
    return await judge_pairs(
        judge,
        pairs,
        model=MODEL,
        prompt_version=VERSION,
        today=TODAY,
        record=recorded.append,
        retry_delay_seconds=0.0,
    )


class _SlowJudge:
    """동시에 진행 중인 호출의 최대 수를 센다."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0

    async def judge(self, query: str, text: str) -> bool:
        del query, text
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        return True


class _FlakyJudge:
    """앞의 몇 번은 주어진 예외를 올리고 그 뒤로는 참을 낸다."""

    def __init__(self, failures: Sequence[Exception]) -> None:
        self._failures = list(failures)
        self.calls = 0

    async def judge(self, query: str, text: str) -> bool:
        del query, text
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        return True


async def test_판정은_쌍마다_하나씩_받는_대로_기록하고_모델과_판과_날짜를_붙인다() -> None:
    recorded: list[Judgment] = []
    judge = FakeRelevanceJudge({"글1": True})

    outcome = await _run(judge, _pairs(3), recorded)

    assert (outcome.received, outcome.skipped) == (3, 0)
    assert sorted(judge.calls) == [("질의0", "글0"), ("질의1", "글1"), ("질의2", "글2")]
    assert {(item.model, item.prompt_version, item.judged_at) for item in recorded} == {
        (MODEL, VERSION, TODAY)
    }
    assert {item.text_sha256: item.relevant for item in recorded} == {
        sha256_text("글0"): False,
        sha256_text("글1"): True,
        sha256_text("글2"): False,
    }


async def test_동시_호출은_넷을_넘지_않는다() -> None:
    judge = _SlowJudge()

    await _run(judge, _pairs(20), [])

    assert JUDGE_CONCURRENCY == 4
    assert judge.max_in_flight == 4


async def test_일시_실패는_다시_해서_받는다() -> None:
    recorded: list[Judgment] = []
    judge = _FlakyJudge([TransientFailure(ErrorCode.JUDGE_UNAVAILABLE, "불통")] * 2)

    assert (await _run(judge, _pairs(1), recorded)).received == 1

    assert judge.calls == 3
    assert len(recorded) == 1


async def test_일시_실패가_재시도_셋_뒤에도_이어지면_멈추고_이미_받은_것은_남긴다() -> None:
    recorded: list[Judgment] = []
    always = [TransientFailure(ErrorCode.JUDGE_UNAVAILABLE, "불통")] * 100
    judge = _FlakyJudge(always)

    with pytest.raises(JudgeRunError, match="불통"):
        await _run(judge, _pairs(1), recorded)

    assert JUDGE_RETRIES == 3
    assert judge.calls == 4
    assert recorded == []


class _PickyJudge:
    """주어진 글의 쌍은 영구 실패로 거절하고 나머지는 참을 낸다. 거절의 까닭은 글마다 다르다."""

    def __init__(self, rejected: Iterable[str]) -> None:
        self._rejected = set(rejected)
        self.calls = 0

    async def judge(self, query: str, text: str) -> bool:
        del query
        self.calls += 1
        if text in self._rejected:
            raise PermanentFailure(ErrorCode.JUDGE_REJECTED, "거절" if self.calls % 2 else "잘림")
        return True


async def test_영구_실패는_다시_하지_않고_그_쌍만_건너뛰고_나머지를_판정한다() -> None:
    recorded: list[Judgment] = []
    judge = _PickyJudge(["글3"])

    outcome = await _run(judge, _pairs(20), recorded)

    assert judge.calls == 20
    assert (outcome.received, outcome.skipped) == (19, 1)
    assert sha256_text("글3") not in {item.text_sha256 for item in recorded}
    assert len(recorded) == 19


async def test_건너뛴_까닭은_이_저장소가_쓴_글을_중복_없이_모은다() -> None:
    judge = _PickyJudge(["글0", "글1", "글2"])

    outcome = await _run(judge, _pairs(10), [])

    assert outcome.skipped == 3
    assert sorted(outcome.skip_reasons) == ["거절", "잘림"]


async def test_영구_실패가_이어져도_사이에_판정을_받으면_연속이_끊겨_멈추지_않는다() -> None:
    limit = PERMANENT_STREAK_LIMIT
    rejected = [f"글{number}" for number in (*range(limit - 1), *range(limit, 2 * limit - 1))]
    judge = _PickyJudge(rejected)

    outcome = await _run(judge, _pairs(30), [])

    assert (outcome.received, outcome.skipped) == (30 - len(rejected), len(rejected))


async def test_영구_실패가_연이어_한계에_닿으면_멈추고_남은_쌍을_더_부르지_않는다() -> None:
    judge = _PickyJudge(f"글{number}" for number in range(50))

    with pytest.raises(JudgeRunError, match="연이어"):
        await _run(judge, _pairs(50), [])

    assert PERMANENT_STREAK_LIMIT == 5
    assert judge.calls == PERMANENT_STREAK_LIMIT


async def test_영구_실패에서_멈출_때도_이미_받은_판정은_남는다() -> None:
    recorded: list[Judgment] = []
    judge = _PickyJudge(f"글{number}" for number in range(2, 50))

    with pytest.raises(JudgeRunError):
        await _run(judge, _pairs(50), recorded)

    assert len(recorded) == 2
