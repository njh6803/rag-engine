"""평가를 도는 하위 명령(`run`, `inspect`)이 함께 지나는 준비와 조립(티켓 search-eval 04, 05, 06,
명세 "자리와 층").

준비(`prepare_evaluation`)는 평가 전용 환경, 묶음, 구성 파일, 목록과 문서 파일의 판정을 지난다.
하나라도 어기면 오류를 표준 오류에 적고 `None`을 낸다. 그다음 데이터베이스를 읽는
판정(`check_ready`)은 스키마가 올라 있고, 이 묶음의 데이터베이스이고, 묶음의 문서가 모두 현재 판에
지금 내용으로 색인되어 있는지를 본다. 조립(`evaluation_deps`)은 평가 끝점으로 질의를 임베딩하는
의존성과, 전체 실행이면 리랭커를 지어 건네고 끝나면 연결을 닫는다. 오류 문장은 연결 문자열이 아니라
오류의 종류만 싣는다(원칙 V).

추론 기록(`--records`, 티켓 search-eval 07)은 준비가 `RecordsRun`으로 열어 `PreparedEvaluation`에
싣고, 조립이 질의의 임베딩과 리랭크를 그 기록기로 감싼다. 기록을 끈(`off`) 실행은 기록기가 없어
감싸지 않는다. `inspect`는 기록을 쓰지 않아 `off`다.
"""

import sys
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx
from sqlalchemy.exc import SQLAlchemyError

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.adapters.eval_bundle_files import check_bundle_files
from rag_engine.adapters.eval_database import SchemaState, check_database, read_schema_state
from rag_engine.adapters.eval_environment import (
    EvalEnvironment,
    EvalEnvironmentError,
    eval_embedder_for,
    eval_embedder_pool,
    eval_settings,
    read_eval_environment,
    require_reranker_url,
)
from rag_engine.adapters.eval_set_reader import EvalSetFormatError, read_eval_set
from rag_engine.adapters.inference_record_files import (
    RecordKind,
    RecordsFormatError,
    failure_reason,
)
from rag_engine.adapters.inference_records import RecordMode, RecordsOptions, RecordsRun
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.tei import TeiReranker
from rag_engine.app.check_eval_database import DATABASE_SUBJECT
from rag_engine.app.check_eval_set import check_eval_set
from rag_engine.app.check_indexed_documents import check_documents_indexed
from rag_engine.app.eval_run import EvalRunDeps, EvalRunError
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.errors import ConfigurationError, RagEngineError
from rag_engine.domain.eval_set import EvalProblem, EvalSet
from rag_engine.domain.ports import Reranker

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
_RECORDS_OFF: Final = RecordsOptions(RecordMode.OFF)


@dataclass(frozen=True, slots=True)
class PreparedEvaluation:
    """준비를 지난 평가의 입력. `reranker_url`은 전체 실행(`Stage.RERANK`)에서만 있고, 추론 기록을
    쓰는 전체 실행은 끝점이 없어도 된다. `records_run`은 이 실행의 추론 기록이다."""

    environment: EvalEnvironment
    reranker_url: str | None
    paths: BundlePaths
    eval_set: EvalSet
    records_run: RecordsRun


def report_problems(problems: tuple[EvalProblem, ...]) -> None:
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"묶음의 오류 {len(problems)}건. 평가하지 않았고 파일을 쓰지 않았다", file=sys.stderr)


def prepare_evaluation(
    folder: Path,
    environ: Mapping[str, str],
    *,
    through: Stage,
    config_file: Path | None,
    records: RecordsOptions = _RECORDS_OFF,
) -> PreparedEvaluation | None:
    """평가 전용 환경(`read_eval_environment`. 접속하지 않고 이름의 규칙까지 본다)과 묶음을 읽고
    목록(`check_eval_set`)과 문서 파일(`check_bundle_files`)을 판정하고, 추론 기록을 읽을 수
    있는지(`RecordsRun`) 본다. 추론 기록을 쓰지 않는(`records`가 `off`) 전체 실행은 리랭커 끝점
    `RAG_EVAL_RERANKER_URL`도 있어야 하고, 기록을 쓰는 전체 실행은 끝점이 없어도 기록에 있는 쌍으로
    돈다. 구성은 `config_file`이 있으면 그 파일이고 없으면 묶음의 `config.json`이다. 어기면 이유를
    표준 오류에 적고 `None`이다."""
    if not folder.is_dir():
        print(f"묶음 폴더가 없다: {folder}", file=sys.stderr)
        return None
    try:
        environment = read_eval_environment(environ)
        reranker_url = _reranker_url(environment, through=through, records=records)
        paths = BundlePaths(folder)
        eval_set = read_eval_set(paths, config_file=config_file)
    except EvalEnvironmentError as error:
        print(error, file=sys.stderr)
        return None
    except EvalSetFormatError as error:
        report_problems(error.problems)
        return None
    problems = (*check_eval_set(eval_set), *check_bundle_files(paths, eval_set))
    if problems:
        report_problems(problems)
        return None
    owned = (RecordKind.QUERY_EMBEDDINGS,)
    try:
        records_run = RecordsRun(
            paths,
            eval_set.config,
            records,
            owned=(*owned, RecordKind.RERANK) if through is Stage.RERANK else owned,
        )
    except (BundlePathError, RecordsFormatError, OSError) as error:
        print(f"추론 기록을 읽지 못했다: {failure_reason(error)}. 평가하지 않았다", file=sys.stderr)
        return None
    return PreparedEvaluation(environment, reranker_url, paths, eval_set, records_run)


def _reranker_url(
    environment: EvalEnvironment, *, through: Stage, records: RecordsOptions
) -> str | None:
    """리랭크에 쓸 끝점. 빠른 실행은 리랭크하지 않아 없다. 기록을 끈 전체 실행은 끝점이 반드시
    있어야 하고(없으면 빠진 이름을 알린다), 기록을 쓰는 전체 실행은 끝점이 없어도 된다."""
    if through is not Stage.RERANK:
        return None
    if records.mode is RecordMode.OFF:
        return require_reranker_url(environment)
    return environment.reranker_url


def guarded[T](work: Callable[[], T], records_run: RecordsRun | None = None) -> T | None:
    """데이터베이스를 읽고 평가하는 일을 돌려 실패를 종류만 적고 `None`으로 낸다. 접속 실패의
    메시지와 스택은 호스트와 사용자 이름을 싣는다(원칙 V). 평가가 끝나지 못했을 때 `records_run`이
    계산을 멈춘 기록이 있으면 어느 명령을 다시 돌리는지도 알린다."""
    try:
        return work()
    except EvalRunError as error:
        print(f"평가를 끝내지 못했다: {error}", file=sys.stderr)
        if records_run is not None:
            for notice in records_run.notices():
                print(notice, file=sys.stderr)
    except (EvalEnvironmentError, ConfigurationError) as error:
        print(f"설정 오류: {error}", file=sys.stderr)
    except (OSError, BundlePathError, SQLAlchemyError, RagEngineError) as error:
        print(f"평가하지 못했다({type(error).__name__})", file=sys.stderr)
    return None


async def check_ready(database_url: str, eval_set: EvalSet) -> tuple[EvalProblem, ...]:
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


@asynccontextmanager
async def evaluation_deps(
    prepared: PreparedEvaluation,
) -> AsyncGenerator[tuple[EvalRunDeps, Reranker | None]]:
    """질의를 환경의 `RAG_EVAL_EMBEDDING_URL`로 임베딩하는 의존성을 짓는다. 판에 적힌 끝점이 아니라
    환경의 끝점을 쓴다. `reranker_url`이 있으면 그 끝점의 리랭커도 짓는다. 리랭커의 모델은
    지식베이스가 아니라 구성의 `reranker_model`이다. 질의의 임베딩과 리랭크는 추론 기록기
    (`prepared.records_run`)를 거치고, 리랭크 기록기가 있는 전체 실행은 끝점이 없어도 기록에 있는
    쌍으로만 도는 리랭커를 낸다. 나올 때 연결을 닫는다."""
    environment, eval_set = prepared.environment, prepared.eval_set
    records_run = prepared.records_run
    settings = eval_settings(environment, eval_set.config)
    engine = create_engine(environment.database_url)
    pool = eval_embedder_pool(settings)
    reranker_client = (
        None
        if prepared.reranker_url is None
        else httpx.AsyncClient(base_url=prepared.reranker_url, timeout=settings.tei_timeout_seconds)
    )
    try:
        embedder_for = eval_embedder_for(pool, environment)
        query_recorder = records_run.embedding(RecordKind.QUERY_EMBEDDINGS)
        deps = EvalRunDeps(
            unit_of_work=PostgresUnitOfWork(engine),
            embedder_for=(
                embedder_for
                if query_recorder is None
                else query_recorder.wrap_factory(embedder_for)
            ),
            tokenize_keywords=tokenize_keywords,
        )
        inner = (
            None
            if reranker_client is None
            else TeiReranker(
                reranker_client,
                model=eval_set.config.reranker_model,
                batch_size=settings.tei_batch_size,
                max_chunk_tokens=eval_set.config.chunking.max_tokens,
            )
        )
        rerank_recorder = records_run.rerank
        reranker: Reranker | None = (
            inner if rerank_recorder is None else rerank_recorder.wrap(inner)
        )
        yield deps, reranker
    finally:
        if reranker_client is not None:
            await reranker_client.aclose()
        await pool.aclose()
        await engine.dispose()
