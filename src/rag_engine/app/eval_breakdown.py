"""유형 표지와 필터 질의의 지표, 놓친 질의의 수, 사람 판정의 수(티켓 search-eval 06, 명세 "지표"와
"놓친 까닭").

질의 하나의 결과(`QueryOutcome`)에서 보고서의 `by_tag`, `filtered`, `misses`, `miss_counts`,
`human_causes` 값을 만든다. 지표는 마지막 단계(빠른 실행은 합친 뒤, 전체 실행은 리랭크 뒤)에
대해서만 내고, 질의 수가 0인 줄은 만들지 않는다. 질의의 글과 조각의 글은 다루지 않고 식별자만
다룬다(원칙 V).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from rag_engine.app.eval_metrics import StageMetrics, aggregate, score_query
from rag_engine.app.eval_misses import MissCause
from rag_engine.app.eval_run import QueryOutcome
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.eval_set import MISS_CAUSES, EvalSet


@dataclass(frozen=True, slots=True)
class TagRow:
    """질의 목록과 유형 표지 하나의 마지막 단계 지표."""

    query_list: str
    tag: str
    stage: Stage
    metrics: StageMetrics


@dataclass(frozen=True, slots=True)
class FilteredRow:
    """질의 목록 하나에서 필터가 붙은 질의만의 마지막 단계 지표와, HNSW 계획의 벡터 후보가 모자란
    질의의 수다."""

    query_list: str
    stage: Stage
    metrics: StageMetrics
    vector_short: int

    @property
    def vector_short_rate(self) -> float:
        return self.vector_short / self.metrics.queries


@dataclass(frozen=True, slots=True)
class MissRow:
    """놓친 질의 하나. 낱말 겹침은 값이 없으면 `None`이다."""

    query_list: str
    evidence_id: str
    cause: MissCause
    word_overlap: float | None


@dataclass(frozen=True, slots=True)
class MissCounts:
    """놓친 질의의 수. `causes`는 탈락 지점마다의 수(일어나지 않은 지점은 0)이고, `zero_overlap`은
    낱말 겹침이 0인 놓친 질의의 수다. 겹침이 없는(`None`) 질의는 넣지 않는다."""

    missed: int
    causes: dict[MissCause, int]
    zero_overlap: int


def _metrics(outcomes: Sequence[QueryOutcome], stage: Stage) -> StageMetrics | None:
    return aggregate(
        [score_query(outcome.reach[stage], expected=outcome.expected) for outcome in outcomes]
    )


def tag_rows(eval_set: EvalSet, outcomes: Sequence[QueryOutcome], stage: Stage) -> list[TagRow]:
    """질의 목록마다, 표지 이름순으로 줄을 낸다. 표지가 없는 질문과 질의가 없는 표지는 줄이 없다."""
    tags = {item.id: item.tags for item in eval_set.evidence}
    names = sorted({tag for item in eval_set.evidence for tag in item.tags})
    rows: list[TagRow] = []
    for query_list in eval_set.query_lists:
        in_list = [outcome for outcome in outcomes if outcome.query_list == query_list.name]
        for tag in names:
            metrics = _metrics([o for o in in_list if tag in tags.get(o.evidence_id, ())], stage)
            if metrics is not None:
                rows.append(TagRow(query_list.name, tag, stage, metrics))
    return rows


def filtered_rows(outcomes: Sequence[QueryOutcome], stage: Stage) -> list[FilteredRow]:
    """질의 목록마다 필터가 붙은 질의(`filter_probe`가 있는 질의)만의 줄을 낸다."""
    rows: list[FilteredRow] = []
    for name in dict.fromkeys(outcome.query_list for outcome in outcomes):
        filtered = [o for o in outcomes if o.query_list == name and o.filter_probe is not None]
        metrics = _metrics(filtered, stage)
        if metrics is not None:
            short = sum(1 for o in filtered if o.filter_probe is not None and o.filter_probe.short)
            rows.append(FilteredRow(name, stage, metrics, short))
    return rows


def miss_rows(outcomes: Sequence[QueryOutcome]) -> list[MissRow]:
    return [
        MissRow(
            outcome.query_list, outcome.evidence_id, outcome.miss.cause, outcome.miss.word_overlap
        )
        for outcome in outcomes
        if outcome.miss is not None
    ]


def miss_counts(outcomes: Sequence[QueryOutcome]) -> MissCounts:
    misses = [outcome.miss for outcome in outcomes if outcome.miss is not None]
    return MissCounts(
        missed=len(misses),
        causes={cause: sum(1 for miss in misses if miss.cause is cause) for cause in MissCause},
        zero_overlap=sum(1 for miss in misses if miss.word_overlap == 0.0),
    )


def human_cause_counts(eval_set: EvalSet) -> dict[str, int]:
    """`miss-review.jsonl`에서 `confirmed`가 참인 줄만 까닭마다 센다. 다섯 까닭을 모두 싣는다."""
    confirmed = [review.cause for review in eval_set.miss_reviews if review.confirmed]
    return {cause: confirmed.count(cause) for cause in sorted(MISS_CAUSES)}
