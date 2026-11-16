"""답 없는 질의의 리랭크 점수와 답 있는 질의의 점수를 같은 문턱 표로 견준다(search-eval 18).

티켓 18의 첫 측정(보고서 `score_distribution`)은 답 있는 질의의 후보만 갈랐다. 이 프로브는 색인에
답이 없는 질의 20개(`questions.jsonl`)를 같은 길(`Evaluator.rank`, 후보 50개, 리랭크)로 돌려
문턱마다 "결과가 비는 질의의 비율"을 견준다. 답 있는 질의 310개도 같은 길로 다시 돌려(리랭크는
기록에서 읽는다) 문턱마다 "기대 근거를 잃는 질의의 비율"(기대 근거에 닿은 후보의 최고 점수가
문턱보다 낮거나 닿은 후보가 아예 없는 질의)을 낸다.

필요한 것: 이 묶음이 색인된 평가 전용 데이터베이스(`compose.eval.yml`의 postgres와 `index`),
임베딩 TEI(`RAG_EVAL_EMBEDDING_URL`, 청킹이 아니라 질의 임베딩용이고 기록에 없는 질의 20개만
계산한다), 리랭커 TEI(`RAG_EVAL_RERANKER_URL`, 기록에 없는 쌍만 계산한다. 답 없는 질의 20개의 쌍 약
1,000개와, 데이터베이스에 따라 답 있는 질의의 쌍 일부). 기록은 `--records read`와 같이 읽기만 하고
쓰지 않는다.

    export RAG_EVAL_DATABASE_URL=... RAG_EVAL_DATA_DIR=... RAG_EVAL_EMBEDDING_URL=...
    export RAG_EVAL_RERANKER_URL=...
    uv run python .scratch/search-eval/probes/no-answer-scores/probe_no_answer.py evals/public-docs

출력은 숫자와 질문 이름표(`noans-NN`)뿐이다. 조각의 글은 찍지 않는다(원칙 V).
"""

import json
import os
import sys
from pathlib import Path

from rag_engine.adapters.eval_assembly import (
    PreparedEvaluation,
    check_ready,
    evaluation_deps,
    guarded,
    prepare_evaluation,
    report_problems,
)
from rag_engine.adapters.inference_records import RecordMode, RecordsOptions
from rag_engine.adapters.postgres.engine import run_in_selector_loop
from rag_engine.app.eval_run import chunk_reach, find_evidence, open_evaluator
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.eval_set import EvalQuery

THRESHOLDS = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95)
QUESTIONS = Path(__file__).with_name("questions.jsonl")


type NoAnswer = tuple[str, str, tuple[float, ...]]
type Answerable = tuple[str, float | None, float]


async def _measure(prepared: PreparedEvaluation) -> tuple[list[NoAnswer], list[Answerable]]:
    """답 없는 질의는 (이름표, 종류, 리랭크 점수들)이고 답 있는 질의는 (목록/이름표, 기대 근거에
    닿은 후보의 최고 점수, 1등 점수)다."""
    eval_set = prepared.eval_set
    async with evaluation_deps(prepared) as (deps, reranker):
        evaluator = await open_evaluator(
            deps, eval_set, candidates=eval_set.config.search_candidates, reranker=reranker
        )
        noans: list[NoAnswer] = []
        for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            ranked = await evaluator.rank(EvalQuery(row["id"], row["query"], None))
            noans.append((row["id"], row["kind"], ranked.scores or ()))
        answerable: list[Answerable] = []
        for listed in eval_set.query_lists:
            for query in listed.queries:
                ranked = await evaluator.rank(query)
                item = find_evidence(eval_set, query.evidence_id)
                scores = ranked.scores or ()
                reached = [
                    score
                    for hit, score in zip(ranked.rankings[Stage.RERANK], scores, strict=True)
                    if chunk_reach(item, hit, evaluator.index.pages)
                ]
                answerable.append(
                    (
                        f"{listed.name}/{query.evidence_id}",
                        max(reached) if reached else None,
                        scores[0] if scores else 0.0,
                    )
                )
    return noans, answerable


def main() -> int:
    folder = Path(sys.argv[1])
    prepared = prepare_evaluation(
        folder,
        os.environ,
        through=Stage.RERANK,
        config_file=None,
        records=RecordsOptions(RecordMode.READ),
    )
    if prepared is None:
        return 1
    problems = run_in_selector_loop(
        check_ready(prepared.environment.database_url, prepared.eval_set)
    )
    if problems:
        report_problems(problems)
        return 1
    result = guarded(lambda: run_in_selector_loop(_measure(prepared)), prepared.records_run)
    if result is None:
        return 1
    noans, answerable = result
    rerank = prepared.records_run.rerank
    print(
        f"리랭크 기록에서 읽은 쌍 {rerank.read_count if rerank else '-'}개, "
        f"끝점으로 새로 계산한 쌍 {rerank.computed_count if rerank else '-'}개"
    )
    print(f"\n## 답 없는 질의 {len(noans)}개의 1등 점수(리랭크 뒤)")
    for noans_id, kind, scores in noans:
        top = f"{scores[0]:.3f}" if scores else "-"
        print(f"{noans_id} {kind:11s} 1등 {top} 후보 {len(scores)}개")
    tops = sorted(s[0] for _, _, s in noans if s)
    print(f"1등 점수 정렬: {', '.join(f'{t:.3f}' for t in tops)}")
    print(f"\n## 문턱표 (답 있는 질의 {len(answerable)}개, 답 없는 질의 {len(noans)}개)")
    print(
        "문턱 | 답 없는 질의 빈 결과 비율 | 소재가 먼 10개 | 소재가 가까운 10개 | "
        "답 있는 질의 기대 근거를 잃는 비율 | 답 있는 질의 빈 결과 비율"
    )
    for threshold in THRESHOLDS:
        empty = [(kind, not any(s >= threshold for s in scores)) for _, kind, scores in noans]
        total = sum(flag for _, flag in empty) / len(empty)
        far = [flag for kind, flag in empty if kind == "off_domain"]
        near = [flag for kind, flag in empty if kind == "near_domain"]
        lost = sum(best is None or best < threshold for _, best, _ in answerable) / len(answerable)
        empty_answerable = sum(top < threshold for _, _, top in answerable) / len(answerable)
        print(
            f"{threshold:.2f} | {total:.2f} | {sum(far) / len(far):.2f} | "
            f"{sum(near) / len(near):.2f} | {lost:.3f} | {empty_answerable:.3f}"
        )
    print("\n## 답 있는 질의의 1등 점수 분위(리랭크 뒤 1등의 점수)")
    ordered = sorted(top for _, _, top in answerable)
    for quantile in (0.05, 0.10, 0.25, 0.50, 0.75, 0.90):
        print(f"{quantile:.2f} 분위 {ordered[int(quantile * (len(ordered) - 1))]:.3f}")
    reached_only = sorted(best for _, best, _ in answerable if best is not None)
    print(f"\n기대 근거에 닿은 후보가 후보 50개 안에 있는 질의 {len(reached_only)}개")
    for quantile in (0.05, 0.10, 0.25, 0.50, 0.75):
        value = reached_only[int(quantile * (len(reached_only) - 1))]
        print(f"닿은 후보의 최고 점수 {quantile:.2f} 분위 {value:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
