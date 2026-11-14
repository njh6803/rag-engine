"""리랭크 점수의 분포(티켓 search-eval 05, 명세 "최소 점수").

전체 실행의 보고서 `score_distribution`의 값이다. 검색 도구에 `min_score`를 둘지와 그 값을 정할
근거로, 합친 뒤의 후보 전부의 리랭크 점수를 기대 근거에 닿은 조각과 닿지 않은 조각으로 갈라 센다.

- 구간은 0.05 폭 스물이다. 구간의 아래 끝은 그 구간에 들고(`[0.10, 0.15)`), 마지막 구간은 1.0을
  든다. 0보다 낮거나 1 이상인 점수는 첫 구간과 마지막 구간에 센다.
- 문턱은 0.05부터 0.95까지 0.05 간격 열아홉이다. 문턱 이상의 점수를 가진 조각이 남는다(검색의
  `min_score`가 그 값보다 낮은 조각을 빼는 것과 같다). 남은 조각은 리랭크 뒤 순위 그대로이므로
  상위 5와 상위 10은 남은 조각의 앞에서 센다. 결과가 빈 질의는 남은 조각이 없는 질의다.
- 분모는 질의 목록과 상관없이 평가한 모든 질의다. `min_score`는 질의 목록이 아니라 지식베이스의
  설정이기 때문이다.

경계의 값은 `number / 20`이다. 0.05 같은 소수를 곱하거나 나누어 구간을 찾으면 `0.15 / 0.05`가
`2.9999999999999996`이라 아래 끝의 점수가 앞 구간으로 샌다. `number / 20`은 같은 소수 글자(`0.15`)와
같은 실수라 점수와 문턱을 같은 값으로 견준다.
"""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from rag_engine.app.eval_run import QueryOutcome, ScoredCandidate

BIN_COUNT: Final = 20
_TOP_FIVE: Final = 5
_TOP_TEN: Final = 10
_LOWER_EDGES: Final = tuple(number / BIN_COUNT for number in range(BIN_COUNT))


@dataclass(frozen=True, slots=True)
class ScoreBin:
    """점수 구간 하나. `lower`는 그 구간에 들고 `upper`는 마지막 구간만 든다."""

    lower: float
    upper: float
    reached: int
    not_reached: int


@dataclass(frozen=True, slots=True)
class ThresholdRow:
    """문턱 하나에서 남는 조각만 본 지표."""

    min_score: float
    hit_at_5: float
    hit_at_10: float
    empty_rate: float
    mean_kept: float


@dataclass(frozen=True, slots=True)
class ScoreDistribution:
    queries: int
    bins: tuple[ScoreBin, ...]
    thresholds: tuple[ThresholdRow, ...]


def build_score_distribution(outcomes: Sequence[QueryOutcome]) -> ScoreDistribution | None:
    """질의가 하나도 없으면 `None`이다. 후보가 없었던 전체 실행의 질의(`scored`가 빈 튜플)는 후보가
    없는 질의로 세고, 점수를 재지 않은 질의(`scored`가 `None`, 빠른 실행)가 들어오면
    `ValueError`다."""
    if not outcomes:
        return None
    scored = [_scored(outcome) for outcome in outcomes]
    reached = [0] * BIN_COUNT
    not_reached = [0] * BIN_COUNT
    for candidates in scored:
        for candidate in candidates:
            counts = reached if candidate.reached else not_reached
            counts[_bin_number(candidate.score)] += 1
    upper_edges = (*_LOWER_EDGES[1:], 1.0)
    return ScoreDistribution(
        queries=len(outcomes),
        bins=tuple(
            ScoreBin(lower, upper, reached[number], not_reached[number])
            for number, (lower, upper) in enumerate(zip(_LOWER_EDGES, upper_edges, strict=True))
        ),
        thresholds=tuple(_threshold_row(scored, edge) for edge in _LOWER_EDGES[1:]),
    )


def _scored(outcome: QueryOutcome) -> tuple[ScoredCandidate, ...]:
    if outcome.scored is None:
        raise ValueError(f"질의 {outcome.query_list}/{outcome.evidence_id}에 리랭크 점수가 없다")
    return outcome.scored


def _bin_number(score: float) -> int:
    return max(0, bisect_right(_LOWER_EDGES, score) - 1)


def _threshold_row(scored: Sequence[Sequence[ScoredCandidate]], min_score: float) -> ThresholdRow:
    count = len(scored)
    kept = [[c for c in candidates if c.score >= min_score] for candidates in scored]
    return ThresholdRow(
        min_score=min_score,
        hit_at_5=sum(_any_reached(row[:_TOP_FIVE]) for row in kept) / count,
        hit_at_10=sum(_any_reached(row[:_TOP_TEN]) for row in kept) / count,
        empty_rate=sum(1 for row in kept if not row) / count,
        mean_kept=sum(len(row) for row in kept) / count,
    )


def _any_reached(top: Sequence[ScoredCandidate]) -> bool:
    return any(candidate.reached for candidate in top)
