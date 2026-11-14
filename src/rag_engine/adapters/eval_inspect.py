"""`inspect <묶음 폴더> <질의 목록 이름> <기대 근거 id>`의 조립(티켓 search-eval 06, 명세 "보고서"의
`inspect` 항목).

질의 하나를 `run`과 같은 길로 돌려 그 질의의 글, 기대 근거, 단계마다의 상위 조각의 글을 표준 출력에
찍는다. 질의와 조각의 글이 실리는 유일한 자리라서 파일은 쓰지 않는다(원칙 V). `run`과 같은 준비
(`prepare_evaluation`)와 데이터베이스 판정(`check_ready`)을 지난다. `through`가 `Stage.RERANK`이면
리랭크 뒤 순위와 점수도 찍고, 그때는 리랭커 끝점 `RAG_EVAL_RERANKER_URL`이 있어야 한다.
"""

from collections.abc import Mapping
from pathlib import Path

from rag_engine.adapters.eval_assembly import (
    EXIT_FAILED,
    EXIT_OK,
    PreparedEvaluation,
    check_ready,
    evaluation_deps,
    guarded,
    prepare_evaluation,
    report_problems,
)
from rag_engine.adapters.postgres.engine import run_in_selector_loop
from rag_engine.app.eval_inspect import Inspection, inspect_query, inspection_text
from rag_engine.app.eval_stages import Stage


def inspect_evaluation(
    folder: Path,
    query_list: str,
    evidence_id: str,
    environ: Mapping[str, str],
    *,
    through: Stage,
    config_file: Path | None = None,
) -> int:
    """종료 코드를 낸다. 글은 표준 출력에만 쓴다. 이벤트 루프를 스스로 열므로 실행 중인 루프
    안에서는 부를 수 없다."""
    prepared = prepare_evaluation(folder, environ, through=through, config_file=config_file)
    if prepared is None:
        return EXIT_FAILED
    inspection = guarded(lambda: _check_and_inspect(prepared, query_list, evidence_id))
    if inspection is None:
        return EXIT_FAILED
    print(inspection_text(inspection), end="")
    return EXIT_OK


def _check_and_inspect(
    prepared: PreparedEvaluation, query_list: str, evidence_id: str
) -> Inspection | None:
    problems = run_in_selector_loop(
        check_ready(prepared.environment.database_url, prepared.eval_set)
    )
    if problems:
        report_problems(problems)
        return None
    return run_in_selector_loop(_inspect(prepared, query_list, evidence_id))


async def _inspect(prepared: PreparedEvaluation, query_list: str, evidence_id: str) -> Inspection:
    async with evaluation_deps(prepared) as (deps, reranker):
        return await inspect_query(
            deps,
            reranker,
            prepared.eval_set,
            query_list=query_list,
            evidence_id=evidence_id,
            candidates=prepared.eval_set.config.search_candidates,
        )
