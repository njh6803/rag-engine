"""`run --through fused <묶음 폴더> --out <폴더>`의 조립(티켓 search-eval 04, 명세 "자리와 층").

평가 전용 데이터베이스에 색인된 묶음을 평가해 `report.json`과 `report.md`를 쓴다. 순서는 이렇다.
아래를 하나라도 어기면 질의를 임베딩하지 않고 보고서를 쓰지 않은 채 1을 낸다(3은 데이터베이스를
읽어 판정한다).

1. 평가 전용 환경(`read_eval_environment`. 접속하지 않고 이름의 규칙까지 본다).
2. 묶음을 읽고 목록(`check_eval_set`)과 문서 파일(`check_bundle_files`)을 판정한다.
3. 스키마가 올라 있는지, 그리고 데이터베이스가 이 묶음의 것인지(`check_database`. `index`가 시작할
   때 지나는 판정과 같다). 현재 판의 모델과 차원이 `config.json`과 다른 것도 거기서 걸린다.

평가가 끝난 뒤에만 보고서를 쓴다. 평가 도중 판이 바뀌거나 임베딩이 실패하면 보고서를 쓰지 않는다.
질의를 임베딩하는 끝점은 판에 적힌 것이 아니라 환경의 `RAG_EVAL_EMBEDDING_URL`이다. 오류 문장은
연결 문자열이 아니라 오류의 종류만 싣는다(원칙 V).
"""

import json
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
)
from rag_engine.adapters.eval_set_reader import EvalSetFormatError, read_eval_set
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.postgres.engine import create_engine, run_in_selector_loop
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.adapters.tei import TeiEmbedderPool
from rag_engine.app.check_eval_database import DATABASE_SUBJECT
from rag_engine.app.check_eval_set import check_eval_set
from rag_engine.app.eval_report import build_report, report_json, report_markdown
from rag_engine.app.eval_run import (
    EvalRunDeps,
    EvalRunError,
    EvalRunResult,
    Stage,
    run_fast_evaluation,
)
from rag_engine.domain.errors import ConfigurationError, RagEngineError
from rag_engine.domain.eval_set import EvalProblem, EvalSet

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
REPORT_JSON: Final = "report.json"
REPORT_MARKDOWN: Final = "report.md"
FAST_STAGES: Final = (Stage.VECTOR, Stage.KEYWORD, Stage.FUSED)
_GIT_TIMEOUT_SECONDS: Final = 10
_COMMIT_LENGTH: Final = 40


def current_commit(repository: Path) -> str | None:
    """저장소의 `HEAD` 커밋. git이 없거나 저장소가 아니면 `None`이다."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = done.stdout.strip()
    return commit if done.returncode == 0 and len(commit) == _COMMIT_LENGTH else None


def run_fast(folder: Path, out: Path, environ: Mapping[str, str], *, commit: str | None) -> int:
    """빠른 실행의 종료 코드를 낸다. 이벤트 루프를 스스로 열므로 실행 중인 루프 안에서는 부를 수
    없다."""
    if not folder.is_dir():
        print(f"묶음 폴더가 없다: {folder}", file=sys.stderr)
        return EXIT_FAILED
    try:
        environment = read_eval_environment(environ)
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
        result = run_in_selector_loop(_evaluate(environment, settings, eval_set))
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
        stages=FAST_STAGES,
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
    """`index`와 같은 판정(`check_database`)에 스키마가 올라 있는지를 더한다. `check_database`는
    스키마를 올리기 전에 부르도록 빈 데이터베이스를 지나가게 두지만, 평가는 색인된 데이터베이스가
    있어야 한다."""
    engine = create_engine(database_url)
    try:
        state = await read_schema_state(engine)
    finally:
        await engine.dispose()
    if state is SchemaState.EMPTY:
        return (
            EvalProblem(DATABASE_SUBJECT, "스키마가 올라 있지 않다. 먼저 index로 묶음을 색인한다"),
        )
    return await check_database(database_url, eval_set)


async def _evaluate(
    environment: EvalEnvironment, settings: Settings, eval_set: EvalSet
) -> EvalRunResult:
    engine = create_engine(environment.database_url)
    pool = TeiEmbedderPool(
        lambda endpoint: httpx.AsyncClient(base_url=endpoint, timeout=settings.tei_timeout_seconds),
        batch_size=settings.tei_batch_size,
    )

    try:
        deps = EvalRunDeps(
            unit_of_work=PostgresUnitOfWork(engine),
            embedder_for=lambda version: pool(
                replace(version, embedding_endpoint=environment.embedding_url)
            ),
            tokenize_keywords=tokenize_keywords,
        )
        return await run_fast_evaluation(
            deps, eval_set, candidates=eval_set.config.search_candidates
        )
    finally:
        await pool.aclose()
        await engine.dispose()
