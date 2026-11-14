"""`run --through fused|rerank <묶음 폴더> --out <폴더>`의 조립(티켓 search-eval 04와 05, 명세
"자리와 층").

평가 전용 데이터베이스에 색인된 묶음을 평가해 `report.json`과 `report.md`를 쓴다. 합친 뒤까지의
빠른 실행(`fused`)과 리랭크 뒤까지의 전체 실행(`rerank`)이 같은 순서를 지난다. 아래를 하나라도
어기면 질의를 임베딩하지 않고 보고서를 쓰지 않은 채 1을 낸다(3과 4는 데이터베이스를 읽어 판정한다).

1. 평가 전용 환경(`read_eval_environment`. 접속하지 않고 이름의 규칙까지 본다). 전체 실행은 리랭커
   끝점 `RAG_EVAL_RERANKER_URL`도 있어야 하고, 없으면 빠진 이름을 알린다.
2. 묶음을 읽고 목록(`check_eval_set`)과 문서 파일(`check_bundle_files`)을 판정한다.
3. 스키마가 올라 있는지, 그리고 데이터베이스가 이 묶음의 것인지(`check_database`. `index`가 시작할
   때 지나는 판정과 같다). 현재 판의 모델과 차원이 `config.json`과 다른 것도 거기서 걸린다.
4. 묶음의 문서가 모두 현재 판에 지금 내용으로 색인되어 있는지(`check_documents_indexed`).

평가가 끝난 뒤에만 보고서를 쓴다. 평가 도중 판이 바뀌거나 임베딩이나 리랭크가 실패하면 보고서를
쓰지 않는다. 질의를 임베딩하는 끝점은 판에 적힌 것이 아니라 환경의 `RAG_EVAL_EMBEDDING_URL`이고,
리랭커의 모델은 지식베이스가 아니라 `config.json`의 `reranker_model`이다. 오류 문장은 연결
문자열이 아니라 오류의 종류만 싣는다(원칙 V).
"""

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx
from sqlalchemy.exc import SQLAlchemyError

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.adapters.eval_bundle_files import check_bundle_files
from rag_engine.adapters.eval_bundle_hash import bundle_content_hash
from rag_engine.adapters.eval_database import SchemaState, check_database, read_schema_state
from rag_engine.adapters.eval_environment import (
    EvalEnvironment,
    EvalEnvironmentError,
    eval_settings,
    read_eval_environment,
    require_reranker_url,
)
from rag_engine.adapters.eval_set_reader import EvalSetFormatError, read_eval_set
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.postgres.engine import create_engine, run_in_selector_loop
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.adapters.tei import TeiEmbedderPool, TeiReranker
from rag_engine.app.check_eval_database import DATABASE_SUBJECT
from rag_engine.app.check_eval_set import check_eval_set
from rag_engine.app.check_indexed_documents import check_documents_indexed
from rag_engine.app.eval_report import build_report, report_json, report_markdown
from rag_engine.app.eval_run import (
    FAST_STAGES,
    FULL_STAGES,
    EvalRunDeps,
    EvalRunError,
    EvalRunResult,
    Stage,
    run_fast_evaluation,
    run_full_evaluation,
)
from rag_engine.domain.errors import ConfigurationError, RagEngineError
from rag_engine.domain.eval_set import EvalProblem, EvalSet

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
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
    folder: Path, out: Path, environ: Mapping[str, str], *, through: Stage, commit: str | None
) -> int:
    """평가의 종료 코드를 낸다. `through`는 마지막으로 잴 단계로 `Stage.FUSED`(빠른 실행)나
    `Stage.RERANK`(전체 실행)이다. 이벤트 루프를 스스로 열므로 실행 중인 루프 안에서는 부를 수
    없다."""
    if not folder.is_dir():
        print(f"묶음 폴더가 없다: {folder}", file=sys.stderr)
        return EXIT_FAILED
    try:
        environment = read_eval_environment(environ)
        reranker_url = require_reranker_url(environment) if through is Stage.RERANK else None
        paths = BundlePaths(folder)
        eval_set = read_eval_set(paths)
    except EvalEnvironmentError as error:
        print(error, file=sys.stderr)
        return EXIT_FAILED
    except EvalSetFormatError as error:
        return _report_problems(error.problems)
    problems = (*check_eval_set(eval_set), *check_bundle_files(paths, eval_set))
    if problems:
        return _report_problems(problems)
    try:
        content_hash = bundle_content_hash(paths, eval_set)
        settings = eval_settings(environment, eval_set.config)
        problems = run_in_selector_loop(_check_ready(environment.database_url, eval_set))
        if problems:
            return _report_problems(problems)
        result = run_in_selector_loop(
            _evaluate(environment, settings, eval_set, reranker_url=reranker_url)
        )
    except EvalRunError as error:
        print(f"평가를 끝내지 못했다: {error}", file=sys.stderr)
        return EXIT_FAILED
    except (EvalEnvironmentError, ConfigurationError) as error:
        print(f"설정 오류: {error}", file=sys.stderr)
        return EXIT_FAILED
    except (OSError, BundlePathError, SQLAlchemyError, RagEngineError) as error:
        # 접속 실패의 메시지와 스택은 호스트와 사용자 이름을 싣는다(원칙 V). 오류의 종류만 알린다.
        print(f"평가하지 못했다({type(error).__name__})", file=sys.stderr)
        return EXIT_FAILED
    report = build_report(
        eval_set,
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


def _write_reports(out: Path, json_text: str, markdown_text: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / REPORT_JSON).write_bytes(json_text.encode())
    (out / REPORT_MARKDOWN).write_bytes(markdown_text.encode())


def _report_problems(problems: tuple[EvalProblem, ...]) -> int:
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"묶음의 오류 {len(problems)}건. 평가하지 않았고 보고서를 쓰지 않았다", file=sys.stderr)
    return EXIT_FAILED


async def _check_ready(database_url: str, eval_set: EvalSet) -> tuple[EvalProblem, ...]:
    """`index`와 같은 판정(`check_database`)에 스키마가 올라 있는지와 묶음의 문서가 모두 색인되어
    있는지를 더한다. `check_database`는 스키마를 올리기 전에 부르도록 빈 데이터베이스를 지나가게
    두지만, 평가는 색인된 데이터베이스가 있어야 한다. 문서의 색인은 질의를 임베딩하기 전에
    본다. 색인이 끝나지 않은 문서는 조각이 0개로 세어져 질의가 모두 놓친 것이 된다."""
    engine = create_engine(database_url)
    try:
        state = await read_schema_state(engine)
    finally:
        await engine.dispose()
    if state is SchemaState.EMPTY:
        return (
            EvalProblem(DATABASE_SUBJECT, "스키마가 올라 있지 않다. 먼저 index로 묶음을 색인한다"),
        )
    problems = await check_database(database_url, eval_set)
    if problems:
        return problems
    engine = create_engine(database_url)
    try:
        return await check_documents_indexed(PostgresUnitOfWork(engine), eval_set)
    finally:
        await engine.dispose()


async def _evaluate(
    environment: EvalEnvironment,
    settings: Settings,
    eval_set: EvalSet,
    *,
    reranker_url: str | None,
) -> EvalRunResult:
    """`reranker_url`이 없으면 합친 뒤까지, 있으면 그 끝점의 리랭커로 리랭크 뒤까지 평가한다."""
    engine = create_engine(environment.database_url)
    pool = TeiEmbedderPool(
        lambda endpoint: httpx.AsyncClient(base_url=endpoint, timeout=settings.tei_timeout_seconds),
        batch_size=settings.tei_batch_size,
    )
    reranker_client = (
        None
        if reranker_url is None
        else httpx.AsyncClient(base_url=reranker_url, timeout=settings.tei_timeout_seconds)
    )

    try:
        deps = EvalRunDeps(
            unit_of_work=PostgresUnitOfWork(engine),
            embedder_for=lambda version: pool(
                replace(version, embedding_endpoint=environment.embedding_url)
            ),
            tokenize_keywords=tokenize_keywords,
        )
        candidates = eval_set.config.search_candidates
        if reranker_client is None:
            return await run_fast_evaluation(deps, eval_set, candidates=candidates)
        reranker = TeiReranker(
            reranker_client,
            model=eval_set.config.reranker_model,
            batch_size=settings.tei_batch_size,
            max_chunk_tokens=eval_set.config.chunking.max_tokens,
        )
        return await run_full_evaluation(deps, reranker, eval_set, candidates=candidates)
    finally:
        if reranker_client is not None:
            await reranker_client.aclose()
        await pool.aclose()
        await engine.dispose()
