"""평가 지표와 글귀 적중 판정(티켓 search-eval 04, 명세 "적중의 단위"와 "지표").

순수 함수라 손으로 계산한 값과 견준다. `reach`는 순위 순으로 그 조각이 닿은 기대 근거의 번호
집합이다.
"""

import math
import unicodedata

import pytest

from rag_engine.app.eval_metrics import (
    BlockPages,
    QueryScore,
    StageMetrics,
    aggregate,
    passage_reaches,
    reaches,
    score_query,
)
from rag_engine.domain.eval_set import PageEvidence, PassageEvidence

NONE: frozenset[int] = frozenset()
FIRST: frozenset[int] = frozenset({0})
SECOND: frozenset[int] = frozenset({1})
BOTH: frozenset[int] = frozenset({0, 1})


def _gain(rank: int) -> float:
    return 1 / math.log2(rank + 1)


def test_첫_적중이_1위이면_모든_지표가_1이다() -> None:
    score = score_query([FIRST, NONE, NONE], expected=1)

    assert score == QueryScore(first_rank=1, reached=1, expected=1, ndcg=1.0, ndcg_truncated=False)


def test_첫_적중이_3위이면_MRR의_근거_순위가_3이고_nDCG는_순위의_할인을_받는다() -> None:
    score = score_query([NONE, NONE, FIRST], expected=1)

    assert score.first_rank == 3
    assert score.ndcg == pytest.approx(_gain(3))
    assert score.ndcg == pytest.approx(0.5)


def test_상위_10_밖의_적중은_놓친_것으로_센다() -> None:
    reach = [NONE] * 10 + [FIRST]

    score = score_query(reach, expected=1)

    assert score == QueryScore(
        first_rank=None, reached=0, expected=1, ndcg=0.0, ndcg_truncated=False
    )


def test_기대_근거_둘_가운데_하나만_닿으면_재현율의_분자가_1이고_nDCG는_이상적_순위에_견준다() -> (
    None
):
    score = score_query([FIRST, NONE], expected=2)

    assert score.reached == 1
    assert score.ndcg == pytest.approx(1 / (1 + _gain(2)))


def test_기대_근거_둘이_1위와_3위에_닿으면_nDCG가_손으로_계산한_값이다() -> None:
    score = score_query([FIRST, NONE, SECOND], expected=2)

    assert score.reached == 2
    assert score.ndcg == pytest.approx((1 + _gain(3)) / (1 + _gain(2)))
    assert not score.ndcg_truncated


def test_같은_기대_근거에_다시_닿는_조각은_이득을_더하지_않는다() -> None:
    """겹침 때문에 같은 자리를 담은 조각이 여럿 나와도 이득은 한 번이다."""
    score = score_query([FIRST, FIRST, FIRST], expected=1)

    assert score.ndcg == 1.0
    assert score.reached == 1
    # 이득이 겹쳐 더해지면 1을 넘어 1에서 잘린 것으로 센다. 값 1.0만으로는 그 차이가 가려진다.
    assert not score.ndcg_truncated


def test_조각_하나가_기대_근거_둘에_닿으면_nDCG가_1에서_잘리고_잘린_질의로_센다() -> None:
    score = score_query([BOTH], expected=2)

    assert score.reached == 2
    assert score.ndcg == 1.0
    assert score.ndcg_truncated is True


def test_이상적인_순위는_기대_근거가_열_개를_넘어도_열에서_끊는다() -> None:
    """기대 근거가 12개이고 상위 10이 모두 새 기대 근거에 닿으면 이상적인 순위와 같아 1이다."""
    reach = [frozenset({rank}) for rank in range(10)]

    score = score_query(reach, expected=12)

    assert score.ndcg == pytest.approx(1.0)
    assert score.reached == 10
    assert not score.ndcg_truncated


def test_집계는_질의_수와_적중률과_MRR과_재현율과_nDCG와_잘린_수를_낸다() -> None:
    scores = [
        score_query([FIRST], expected=1),  # 1위 적중
        score_query([NONE, NONE, FIRST], expected=1),  # 3위 적중
        score_query([NONE] * 4 + [FIRST], expected=1),  # 5위 적중
        score_query([NONE], expected=1),  # 놓침
        score_query([BOTH], expected=2),  # 1위, nDCG가 잘린다
    ]

    metrics = aggregate(scores)

    assert metrics == StageMetrics(
        queries=5,
        hit_at_1=2 / 5,
        hit_at_3=3 / 5,
        hit_at_5=4 / 5,
        hit_at_10=4 / 5,
        mrr=(1 + 1 / 3 + 1 / 5 + 0 + 1) / 5,
        recall=(1 + 1 + 1 + 0 + 1) / 5,
        ndcg_at_10=(1 + _gain(3) + _gain(5) + 0 + 1) / 5,
        ndcg_truncated=1,
    )


def test_질의가_없으면_집계하지_않는다() -> None:
    assert aggregate([]) is None


def test_글귀는_조각_글의_부분_문자열이면_닿는다() -> None:
    assert passage_reaches("연차휴가는 입사 일 년 뒤부터", "연차휴가는 입사 일 년 뒤부터 발생한다.")


def test_공백과_줄바꿈과_NFC가_달라도_닿는다() -> None:
    chunk = "연차휴가는\n입사 일 년\t뒤부터 발생한다."
    decomposed = unicodedata.normalize("NFD", "연차휴가는 입사 일 년 뒤부터")

    assert passage_reaches(decomposed, chunk)


def test_글귀가_조각의_경계에서_갈리면_닿지_않는다() -> None:
    assert not passage_reaches("연차휴가는 입사 일 년 뒤부터 발생한다", "연차휴가는 입사 일 년")
    assert not passage_reaches("연차휴가는 입사 일 년 뒤부터 발생한다", "뒤부터 발생한다")


# 문서 `a.pdf`의 블록 순번(0부터)과 그 블록이 놓인 쪽이다. 블록 2는 쪽이 없다.
PAGES: BlockPages = {"a.pdf": {0: 1, 1: 1, 2: None, 3: 2, 4: 3}}


def test_쪽으로_적은_기대_근거는_덮은_블록의_쪽_번호에_기대한_쪽이_있으면_닿는다() -> None:
    assert reaches(PageEvidence(document="a.pdf", page=2), "a.pdf", "조각 글", (3, 3), PAGES)


def test_두_쪽에_걸친_조각은_첫_블록이_아닌_쪽의_기대_근거에도_닿는다() -> None:
    """근거 위치에 실린 쪽은 첫 블록의 것(1쪽)뿐이지만, 블록 1~3을 덮으므로 2쪽에도 닿는다."""
    assert reaches(PageEvidence(document="a.pdf", page=2), "a.pdf", "조각 글", (1, 3), PAGES)


def test_덮은_블록의_쪽에_기대한_쪽이_없으면_닿지_않는다() -> None:
    assert not reaches(PageEvidence(document="a.pdf", page=3), "a.pdf", "조각 글", (0, 3), PAGES)


def test_쪽이_없는_블록만_덮은_조각은_쪽으로_적은_기대_근거에_닿지_않는다() -> None:
    assert not reaches(PageEvidence(document="a.pdf", page=1), "a.pdf", "글", (2, 2), PAGES)


def test_쪽으로_적은_기대_근거는_다른_문서의_조각에_닿지_않는다() -> None:
    assert not reaches(PageEvidence(document="a.pdf", page=2), "b.pdf", "글", (3, 3), PAGES)


def test_글귀로_적은_기대_근거는_문서가_같고_글귀가_조각_글에_들_때만_닿는다() -> None:
    expectation = PassageEvidence(document="a.pdf", passage="연차 발생")

    assert reaches(expectation, "a.pdf", "연차 발생 시기", (0, 0), PAGES)
    assert not reaches(expectation, "b.pdf", "연차 발생 시기", (0, 0), PAGES)
    assert not reaches(expectation, "a.pdf", "출장비 정산", (0, 0), PAGES)
