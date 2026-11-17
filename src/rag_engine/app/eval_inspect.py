"""`inspect`의 값과 글(티켓 search-eval 06, 명세 "보고서"의 `inspect` 항목).

질의 하나를 평가와 같은 길(`Evaluator`)로 돌려, 그 질의의 글, 기대 근거, 단계마다의 상위 조각의 글을
사람이 읽는 글로 낸다. 질의와 조각의 글이 실리는 유일한 자리라서, 이 글은 표준 출력에만 가고
보고서나 파일로 쓰지 않는다(원칙 V). 단계마다 상위 `INSPECT_TOP`개만 본다.
"""

from dataclasses import dataclass
from typing import Final

from rag_engine.app.eval_run import (
    EvalRunDeps,
    EvalRunError,
    QueryMiss,
    RankedQuery,
    chunk_reach,
    find_evidence,
    open_evaluator,
)
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.eval_set import (
    EvalFilter,
    EvalSet,
    Expectation,
    PageEvidence,
)
from rag_engine.domain.ports import Reranker

INSPECT_TOP: Final = 5
_NUMBER_DIGITS: Final = 3


@dataclass(frozen=True, slots=True)
class InspectedChunk:
    """단계의 순위 `rank`인 조각. `score`는 리랭크 뒤 순위에서만 있다."""

    rank: int
    key: str
    ordinal: int
    section: tuple[str, ...]
    text: str
    reached: bool
    score: float | None


@dataclass(frozen=True, slots=True)
class StageView:
    stage: Stage
    chunks: tuple[InspectedChunk, ...]


@dataclass(frozen=True, slots=True)
class Inspection:
    """질의 하나의 글과 기대 근거와 단계마다의 상위 조각. `miss`는 마지막 단계에서 놓친 질의에만
    있다."""

    query_list: str
    evidence_id: str
    query: str
    filter: EvalFilter | None
    tags: tuple[str, ...]
    expectations: tuple[Expectation, ...]
    stages: tuple[StageView, ...]
    miss: QueryMiss | None


async def inspect_query(
    deps: EvalRunDeps,
    reranker: Reranker | None,
    eval_set: EvalSet,
    *,
    query_list: str,
    evidence_id: str,
    candidates: int,
) -> Inspection:
    """질의 목록과 기대 근거의 `id`로 질의 하나를 찾아 평가와 같은 길로 돌린다. 찾지 못하면
    `EvalRunError`다."""
    query = next(
        (
            query
            for listed in eval_set.query_lists
            if listed.name == query_list
            for query in listed.queries
            if query.evidence_id == evidence_id
        ),
        None,
    )
    if query is None:
        raise EvalRunError(f"질의 목록 {query_list}에 기대 근거 {evidence_id}의 질의가 없다")
    item = find_evidence(eval_set, evidence_id)
    evaluator = await open_evaluator(deps, eval_set, candidates=candidates, reranker=reranker)
    ranked = await evaluator.rank(query)
    outcome = await evaluator.outcome(query_list, item, ranked)
    return Inspection(
        query_list=query_list,
        evidence_id=evidence_id,
        query=query.query,
        filter=query.filter,
        tags=item.tags,
        expectations=item.evidence,
        stages=tuple(
            StageView(
                stage,
                tuple(
                    InspectedChunk(
                        rank=rank,
                        key=hit.hit.key,
                        ordinal=hit.ordinal,
                        section=hit.hit.location.section,
                        text=hit.hit.text,
                        reached=bool(chunk_reach(item, hit, evaluator.index.pages)),
                        score=_score(ranked, stage, rank),
                    )
                    for rank, hit in enumerate(ranking[:INSPECT_TOP], start=1)
                ),
            )
            for stage, ranking in ranked.rankings.items()
        ),
        miss=outcome.miss,
    )


def _score(ranked: RankedQuery, stage: Stage, rank: int) -> float | None:
    if stage is not Stage.RERANK or ranked.scores is None:
        return None
    return ranked.scores[rank - 1]


def inspection_text(inspection: Inspection) -> str:
    lines = [
        f"질의 목록: {inspection.query_list}",
        f"기대 근거 id: {inspection.evidence_id}",
        f"표지: {', '.join(inspection.tags) or '없음'}",
        f"필터: {_filter_text(inspection.filter)}",
        f"질의: {inspection.query}",
        "",
        "기대 근거:",
        *(f"  - {_expectation_text(expectation)}" for expectation in inspection.expectations),
        "",
        _miss_text(inspection.miss),
    ]
    for view in inspection.stages:
        lines += ["", f"## {view.stage.value} (상위 {INSPECT_TOP}개)"]
        if not view.chunks:
            lines.append("  (결과 없음)")
        for chunk in view.chunks:
            lines += _chunk_lines(chunk)
    return "\n".join(lines) + "\n"


def _filter_text(value: EvalFilter | None) -> str:
    if value is None:
        return "없음"
    parts: list[str] = []
    if value.groups is not None:
        parts.append(f"그룹 {', '.join(value.groups)}")
    if value.updated_after is not None:
        parts.append(f"updated_after {value.updated_after.isoformat()}")
    if value.updated_before is not None:
        parts.append(f"updated_before {value.updated_before.isoformat()}")
    return ", ".join(parts) or "없음"


def _expectation_text(expectation: Expectation) -> str:
    if isinstance(expectation, PageEvidence):
        return f"{expectation.document} {expectation.page}쪽"
    return f"{expectation.document} 글귀: {expectation.passage}"


def _miss_text(miss: QueryMiss | None) -> str:
    if miss is None:
        return "마지막 단계에서 닿았다"
    overlap = "없음" if miss.word_overlap is None else f"{miss.word_overlap:.{_NUMBER_DIGITS}f}"
    return f"놓친 까닭: {miss.cause.value}, 낱말 겹침: {overlap}"


def _chunk_lines(chunk: InspectedChunk) -> list[str]:
    mark = "닿음" if chunk.reached else "닿지 않음"
    score = "" if chunk.score is None else f" 점수 {chunk.score:.{_NUMBER_DIGITS}f}"
    where = f"{chunk.key}#{chunk.ordinal}"
    section = f" [{' > '.join(chunk.section)}]" if chunk.section else ""
    return [f"{chunk.rank}. {mark}{score} {where}{section}", f"     {chunk.text}"]
