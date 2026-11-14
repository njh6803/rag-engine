"""평가의 글귀 적중 판정과 지표(티켓 search-eval 04, 명세 "적중의 단위"와 "지표").

순수 함수다. 질의 하나의 결과는 단계의 순위 순으로 늘어선 `reach`다. `reach[i]`는 순위 `i + 1`의
조각이 닿은 기대 근거의 번호(기대 근거 안의 자리) 집합이고, 아무것에도 닿지 않으면 비어 있다. 지표는
상위 `TOP_K`개만 본다.

nDCG에서 기대 근거 하나는 처음 닿은 순위에서 한 번만 이득 1을 준다. 그래서 한 순위의 이득은 그
조각이 처음으로 닿은 기대 근거의 수이고, 이상적인 순위는 기대 근거의 수만큼(많아야 `TOP_K`) 맨
위부터 이득 1로 채운 것이다. 조각 하나가 기대 근거 둘에 처음 닿으면 값이 1을 넘을 수 있어 1에서
자르고, 잘린 질의는 `ndcg_truncated`로 센다. 분모를 조각 하나가 주는 여러 이득까지 넣어 다시 정하지
않는 것은 청킹을 바꾼 실행끼리 값을 견줄 수 있게 하기 위해서다.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from rag_engine.app.eval_passages import normalize_text

TOP_K: Final = 10
HIT_CUTOFFS: Final = (1, 3, 5, 10)
# 부동소수점 오차로 1을 아주 조금 넘는 값을 잘린 것으로 세지 않는다.
_TRUNCATION_TOLERANCE: Final = 1e-9


def passage_reaches(passage: str, chunk_text: str) -> bool:
    """글귀가 조각 글에 들어 있으면 닿은 것이다. 양쪽을 NFC로 정규화하고 공백류를 지운 뒤 부분
    문자열로 본다(`normalize_text`). 조각 글은 절 경로 줄을 뺀 `text`다. 글귀가 조각의 경계에서
    갈리면 닿지 않는다."""
    return normalize_text(passage) in normalize_text(chunk_text)


@dataclass(frozen=True, slots=True)
class QueryScore:
    """질의 하나의 단계 점수. `first_rank`는 상위 `TOP_K` 안에서 처음 닿은 순위이고 없으면
    `None`이다. `reached`는 상위 `TOP_K`가 닿은 서로 다른 기대 근거의 수다."""

    first_rank: int | None
    reached: int
    expected: int
    ndcg: float
    ndcg_truncated: bool


@dataclass(frozen=True, slots=True)
class StageMetrics:
    """질의 목록과 단계 하나의 지표. 질의 수가 0인 줄은 만들지 않는다(`aggregate`가 `None`)."""

    queries: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    hit_at_10: float
    mrr: float
    recall: float
    ndcg_at_10: float
    ndcg_truncated: int


def score_query(reach: Sequence[frozenset[int]], *, expected: int) -> QueryScore:
    """`expected`는 그 질문의 기대 근거 수다."""
    top = reach[:TOP_K]
    seen: set[int] = set()
    first_rank: int | None = None
    discounted = 0.0
    for position, reached_here in enumerate(top, start=1):
        if reached_here and first_rank is None:
            first_rank = position
        gain = len(reached_here - seen)
        seen |= reached_here
        discounted += gain / math.log2(position + 1)
    ideal = sum(1 / math.log2(position + 1) for position in range(1, min(expected, TOP_K) + 1))
    raw = discounted / ideal if ideal else 0.0
    return QueryScore(
        first_rank=first_rank,
        reached=len(seen),
        expected=expected,
        ndcg=min(raw, 1.0),
        ndcg_truncated=raw > 1.0 + _TRUNCATION_TOLERANCE,
    )


def aggregate(scores: Sequence[QueryScore]) -> StageMetrics | None:
    """질의마다의 점수를 평균한다. 질의가 없으면 `None`이다."""
    if not scores:
        return None
    count = len(scores)

    def hit_rate(cutoff: int) -> float:
        return sum(1 for s in scores if s.first_rank is not None and s.first_rank <= cutoff) / count

    return StageMetrics(
        queries=count,
        hit_at_1=hit_rate(1),
        hit_at_3=hit_rate(3),
        hit_at_5=hit_rate(5),
        hit_at_10=hit_rate(10),
        mrr=sum(0.0 if s.first_rank is None else 1 / s.first_rank for s in scores) / count,
        recall=sum(s.reached / s.expected if s.expected else 0.0 for s in scores) / count,
        ndcg_at_10=sum(s.ndcg for s in scores) / count,
        ndcg_truncated=sum(1 for s in scores if s.ndcg_truncated),
    )
