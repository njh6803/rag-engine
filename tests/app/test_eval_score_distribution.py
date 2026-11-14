"""리랭크 점수의 분포(티켓 search-eval 05, 명세 "최소 점수").

질의마다 합친 뒤의 후보 전부를 리랭크한 점수 순으로 늘어선 `(점수, 기대 근거에 닿았는가)`를 받아,
0.05 폭 구간마다 닿은 조각과 닿지 않은 조각을 세고 문턱 0.05부터 0.95까지 0.05 간격마다 상위 5
적중률, 상위 10 적중률, 결과가 빈 질의의 비율, 질의마다 남는 조각 수의 평균을 낸다. 문턱은 그 값
이상인 조각을 남긴다(검색의 `min_score`가 그 값보다 낮은 조각을 빼는 것과 같다). 기대 값은 손으로
계산했다.
"""

import pytest

from rag_engine.app.eval_run import QueryOutcome, ScoredCandidate
from rag_engine.app.eval_score_distribution import ScoreDistribution, build_score_distribution
from rag_engine.app.eval_stages import Stage


def _outcome(*scored: tuple[float, bool]) -> QueryOutcome:
    return QueryOutcome(
        query_list="human",
        evidence_id="q",
        expected=1,
        reach={stage: () for stage in Stage},
        scored=tuple(ScoredCandidate(score, reached) for score, reached in scored),
    )


def _distribution(*outcomes: QueryOutcome) -> ScoreDistribution:
    distribution = build_score_distribution(outcomes)
    assert distribution is not None
    return distribution


def _counts(distribution: ScoreDistribution) -> dict[int, tuple[int, int]]:
    """닿은 조각과 닿지 않은 조각이 하나라도 있는 구간의 번호(0부터)와 그 수."""
    return {
        number: (bin_.reached, bin_.not_reached)
        for number, bin_ in enumerate(distribution.bins)
        if bin_.reached or bin_.not_reached
    }


def _row(distribution: ScoreDistribution, min_score: float) -> tuple[float, float, float, float]:
    (row,) = [row for row in distribution.thresholds if row.min_score == min_score]
    return row.hit_at_5, row.hit_at_10, row.empty_rate, row.mean_kept


def test_구간은_0_05_폭으로_스물이고_문턱은_0_05부터_0_95까지_열아홉이다() -> None:
    distribution = _distribution(_outcome((0.5, True)))

    assert len(distribution.bins) == 20
    assert (distribution.bins[0].lower, distribution.bins[0].upper) == (0.0, 0.05)
    assert (distribution.bins[19].lower, distribution.bins[19].upper) == (0.95, 1.0)
    assert [row.min_score for row in distribution.thresholds] == [
        number / 20 for number in range(1, 20)
    ]


def test_점수를_닿은_조각과_닿지_않은_조각으로_갈라_구간마다_센다() -> None:
    """q1 점수 0.9(닿음) 0.5 0.5 0.1(닿음), q2 점수 0.8 0.3(닿음). 구간의 아래 끝은 그 구간에
    든다."""
    distribution = _distribution(
        _outcome((0.9, True), (0.5, False), (0.5, False), (0.1, True)),
        _outcome((0.8, False), (0.3, True)),
    )

    assert _counts(distribution) == {
        2: (1, 0),  # 0.10 이상 0.15 미만: 0.1
        6: (1, 0),  # 0.30 이상: 0.3
        10: (0, 2),  # 0.50 이상: 0.5 둘
        16: (0, 1),  # 0.80 이상: 0.8
        18: (1, 0),  # 0.90 이상: 0.9
    }


def test_점수가_0과_1이어도_첫_구간과_마지막_구간에_센다() -> None:
    distribution = _distribution(_outcome((1.0, False), (0.05, True), (0.0, False)))

    assert _counts(distribution) == {0: (0, 1), 1: (1, 0), 19: (0, 1)}


def test_문턱마다_상위_적중률과_빈_질의의_비율과_남는_조각_수의_평균을_낸다() -> None:
    """세 질의: q1 [0.9 닿음, 0.5, 0.5, 0.1 닿음], q2 [0.8, 0.3 닿음], q3 후보 없음."""
    distribution = _distribution(
        _outcome((0.9, True), (0.5, False), (0.5, False), (0.1, True)),
        _outcome((0.8, False), (0.3, True)),
        _outcome(),
    )

    # (적중률 5, 적중률 10, 빈 질의의 비율, 평균 남는 수)
    assert _row(distribution, 0.05) == pytest.approx((2 / 3, 2 / 3, 1 / 3, 2.0))
    assert _row(distribution, 0.15) == pytest.approx((2 / 3, 2 / 3, 1 / 3, 5 / 3))
    assert _row(distribution, 0.35) == pytest.approx((1 / 3, 1 / 3, 1 / 3, 4 / 3))
    assert _row(distribution, 0.55) == pytest.approx((1 / 3, 1 / 3, 1 / 3, 2 / 3))
    assert _row(distribution, 0.85) == pytest.approx((1 / 3, 1 / 3, 2 / 3, 1 / 3))
    assert _row(distribution, 0.95) == pytest.approx((0.0, 0.0, 1.0, 0.0))


def test_문턱은_그_값_이상인_조각을_남긴다() -> None:
    """점수 0.05인 조각은 문턱 0.05에서 남고 0.1에서 빠진다."""
    distribution = _distribution(_outcome((1.0, False), (0.05, True)))

    assert _row(distribution, 0.05) == pytest.approx((1.0, 1.0, 0.0, 2.0))
    assert _row(distribution, 0.1) == pytest.approx((0.0, 0.0, 0.0, 1.0))


def test_상위_5와_상위_10은_남은_조각의_순위로_센다() -> None:
    """닿은 조각이 점수 순 여섯째이면 상위 10에는 들고 상위 5에는 들지 못한다. 문턱은 점수가 낮은
    조각만 걷어내므로 앞의 순위는 그대로이고, 문턱이 그 조각의 점수를 넘으면 그 조각이 빠져 적중이
    없어진다."""
    distribution = _distribution(
        _outcome(
            (0.95, False), (0.9, False), (0.85, False), (0.8, False), (0.75, False), (0.7, True)
        )
    )

    assert _row(distribution, 0.05) == pytest.approx((0.0, 1.0, 0.0, 6.0))
    assert _row(distribution, 0.7) == pytest.approx((0.0, 1.0, 0.0, 6.0))
    assert _row(distribution, 0.75) == pytest.approx((0.0, 0.0, 0.0, 5.0))


def test_질의가_하나도_없으면_분포가_없다() -> None:
    assert build_score_distribution(()) is None


def test_점수가_없는_질의는_후보가_없는_질의로_세지_않고_오류로_끝낸다() -> None:
    """빠른 실행의 질의(`scored`가 `None`)와 후보가 없었던 전체 실행의 질의(빈 튜플)는 다르다. 앞의
    것을 분포에 넣으면 점수를 재지 않은 질의가 빈 질의의 비율을 올린다."""
    fast = QueryOutcome(
        query_list="human", evidence_id="q", expected=1, reach={stage: () for stage in Stage}
    )

    with pytest.raises(ValueError, match="점수"):
        build_score_distribution([fast])
