"""`run --through fused|rerank <묶음 폴더> --out <폴더>`의 조립(티켓 search-eval 04, 05, 06, 명세
"자리와 층").

평가 전용 데이터베이스에 색인된 묶음을 평가해 `report.json`과 `report.md`를 쓴다. 합친 뒤까지의
빠른 실행(`fused`)과 리랭크 뒤까지의 전체 실행(`rerank`)이 같은 순서를 지난다. 아래를 하나라도
어기면 질의를 임베딩하지 않고 보고서를 쓰지 않은 채 1을 낸다(3과 4는 데이터베이스를 읽어 판정한다).

1. 평가 전용 환경(`read_eval_environment`. 접속하지 않고 이름의 규칙까지 본다). 전체 실행은 리랭커
   끝점 `RAG_EVAL_RERANKER_URL`도 있어야 하고, 없으면 빠진 이름을 알린다.
2. 묶음을 읽고 목록(`check_eval_set`)과 문서 파일(`check_bundle_files`)을 판정한다. 구성은
   `config_file`(`--config`)을 주면 그 파일이고 주지 않으면 묶음의 `config.json`이다.
3. 스키마가 올라 있는지, 그리고 데이터베이스가 이 묶음의 것인지(`check_database`. `index`가 시작할
   때 지나는 판정과 같다). 현재 판의 모델과 차원이 구성과 다른 것도 거기서 걸린다.
4. 묶음의 문서가 모두 현재 판에 지금 내용으로 색인되어 있는지(`check_documents_indexed`).

1과 2는 `eval_assembly.prepare_evaluation`, 3과 4는 `eval_assembly.check_ready`가 한다. 평가가 끝난
뒤에만 보고서를 쓴다. 평가 도중 판이 바뀌거나 임베딩이나 리랭크가 실패하면 보고서를 쓰지 않는다.
보고서의 `config`와 내용 해시는 쓴 구성(`config_file`이 있으면 그 파일)으로 계산한다. 질의를
임베딩하는 끝점은 판에 적힌 것이 아니라 환경의 `RAG_EVAL_EMBEDDING_URL`이고, 리랭커의 모델은
지식베이스가 아니라 구성의 `reranker_model`이다. 오류 문장은 연결 문자열이 아니라 오류의 종류만
싣는다(원칙 V).
"""

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

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
from rag_engine.adapters.eval_bundle_hash import bundle_content_hash
from rag_engine.adapters.postgres.engine import run_in_selector_loop
from rag_engine.app.eval_report import build_report, report_json, report_markdown
from rag_engine.app.eval_run import EvalRunResult, run_fast_evaluation, run_full_evaluation
from rag_engine.app.eval_stages import FAST_STAGES, FULL_STAGES, Stage

REPORT_JSON: Final = "report.json"
REPORT_MARKDOWN: Final = "report.md"
_GIT_TIMEOUT_SECONDS: Final = 10
_COMMIT_LENGTH: Final = 40
# git이 읽을 저장소를 고르는 환경 변수. `tools/run_hooks.py`의 `REPO_LOCATION_VARS`와 같은 목록이다
# (`adapters`는 `tools`를 import하지 못해 따로 적는다).
_GIT_LOCATION_VARIABLES: Final = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_PREFIX",
    }
)


def current_commit(repository: Path) -> str | None:
    """저장소의 `HEAD` 커밋. git이 없거나 저장소가 아니면 `None`이다. 저장소를 고르는 환경 변수는
    벗긴다. `git -C`를 줘도 `GIT_DIR`이 있으면 git이 그 저장소를 읽어, 훅 같은 다른 도구의 환경이
    남은 셸에서는 보고서에 다른 저장소의 커밋이 적힌다."""
    environment = {
        name: value for name, value in os.environ.items() if name not in _GIT_LOCATION_VARIABLES
    }
    try:
        done = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = done.stdout.strip()
    return commit if done.returncode == 0 and len(commit) == _COMMIT_LENGTH else None


def run_evaluation(
    folder: Path,
    out: Path,
    environ: Mapping[str, str],
    *,
    through: Stage,
    commit: str | None,
    config_file: Path | None = None,
) -> int:
    """평가의 종료 코드를 낸다. `through`는 마지막으로 잴 단계로 `Stage.FUSED`(빠른 실행)나
    `Stage.RERANK`(전체 실행)이다. `config_file`은 `--config`로 준 구성 파일이다. 이벤트 루프를
    스스로 열므로 실행 중인 루프 안에서는 부를 수 없다."""
    prepared = prepare_evaluation(folder, environ, through=through, config_file=config_file)
    if prepared is None:
        return EXIT_FAILED
    evaluated = guarded(lambda: _check_and_evaluate(prepared))
    if evaluated is None:
        return EXIT_FAILED
    content_hash, result = evaluated
    report = build_report(
        prepared.eval_set,
        result,
        content_hash=content_hash,
        stages=FULL_STAGES if through is Stage.RERANK else FAST_STAGES,
        run_at=datetime.now(UTC),
        commit=commit,
    )
    json_text = json.dumps(report_json(report), ensure_ascii=False, indent=2) + "\n"
    try:
        _write_reports(out, json_text, report_markdown(report))
    except OSError as error:
        print(f"보고서를 쓰지 못했다({type(error).__name__})", file=sys.stderr)
        return EXIT_FAILED
    print(f"보고서를 썼다: {out / REPORT_JSON}, {out / REPORT_MARKDOWN}")
    return EXIT_OK


def _check_and_evaluate(prepared: PreparedEvaluation) -> tuple[str, EvalRunResult] | None:
    """데이터베이스를 읽는 판정(3과 4)을 지난 뒤 묶음의 내용 해시와 평가 결과를 낸다. 판정에
    걸리면 이유를 적고 `None`이다."""
    content_hash = bundle_content_hash(prepared.paths, prepared.eval_set)
    problems = run_in_selector_loop(
        check_ready(prepared.environment.database_url, prepared.eval_set)
    )
    if problems:
        report_problems(problems)
        return None
    return content_hash, run_in_selector_loop(_evaluate(prepared))


def _write_reports(out: Path, json_text: str, markdown_text: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / REPORT_JSON).write_bytes(json_text.encode())
    (out / REPORT_MARKDOWN).write_bytes(markdown_text.encode())


async def _evaluate(prepared: PreparedEvaluation) -> EvalRunResult:
    """리랭커가 없으면 합친 뒤까지, 있으면 그 끝점의 리랭커로 리랭크 뒤까지 평가한다."""
    candidates = prepared.eval_set.config.search_candidates
    async with evaluation_deps(prepared) as (deps, reranker):
        if reranker is None:
            return await run_fast_evaluation(deps, prepared.eval_set, candidates=candidates)
        return await run_full_evaluation(deps, reranker, prepared.eval_set, candidates=candidates)
