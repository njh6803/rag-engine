"""`index <묶음 폴더>`의 조립(티켓 search-eval 03, 명세 "자리와 층"의 `index` 항목).

제품과 같은 길로 묶음의 문서를 평가 전용 데이터베이스에 색인한다. 스키마와 기본 지식베이스는 제품의
`migrate`와 같은 코드(`migrate_database`)로 만들고, 문서는 수집 유스케이스(`ingest_document`)로
넣고, 작업은 호출하는 쪽이 건넨 처리 함수(작업자의 한 번 돌기 입구)로 끝까지 처리한다. 작업자는 이
층의 위에 있어 이 모듈이 직접 부르지 못하므로 `tools/search_eval.py`가 건넨다.

순서는 이렇다. 아래를 하나라도 어기면 아무것도 쓰지 않고 1을 낸다. 스키마를 올리기 전에 모두 본다.

1. 평가 전용 환경(`read_eval_environment`. 접속하지 않고 이름의 규칙까지 본다).
2. 묶음을 읽고(`read_eval_set`) 문서 파일을 판정한다(`check_bundle_files`. 경로, 문서 목록의 모든
   파일이 있고 해시가 맞는지, 목록에 없는 파일이 없는지). 수집에는 해시를 대 본 그 바이트를 넘긴다.
   판정과 수집 사이에 파일이 바뀌어도 넘기는 바이트는 해시가 맞는다.
3. 데이터베이스가 이 묶음의 것인지(`check_database`).

색인에 실패한 문서가 하나라도 있으면 1이다. 실패한 문서가 있어도 나머지는 색인한다.
"""

import asyncio
import hashlib
import sys
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Final
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.adapters.eval_bundle_files import DOCUMENTS_FOLDER, check_bundle_files
from rag_engine.adapters.eval_database import check_database
from rag_engine.adapters.eval_environment import (
    EvalEnvironmentError,
    eval_settings,
    read_eval_environment,
)
from rag_engine.adapters.eval_set_reader import EvalSetFormatError, read_eval_set
from rag_engine.adapters.log_format import request_id_var
from rag_engine.adapters.postgres.bootstrap import migrate_database
from rag_engine.adapters.postgres.engine import create_engine, run_in_selector_loop
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.app.await_documents import wait_for_documents
from rag_engine.app.ingest import IngestRequest, ingest_document
from rag_engine.domain.entities import JsonValue
from rag_engine.domain.errors import ConfigurationError, RequestError
from rag_engine.domain.eval_set import EvalDocument, EvalProblem
from rag_engine.domain.identifiers import new_id

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
POLL_SECONDS: Final = 1.0
_BYTES_PER_MB: Final = 1024 * 1024
_NO_METADATA: Final[dict[str, JsonValue]] = {}

# 작업자의 한 번 돌기 입구: 설정에 적힌 데이터베이스에서 꺼낼 수 있는 작업을 모두 처리하고 처리한
# 수를 낸다(`rag_engine.worker.assembly.run_once_with_settings`).
type ProcessJobs = Callable[[Settings], Awaitable[int]]


def index_bundle(
    folder: Path,
    environ: Mapping[str, str],
    process_jobs: ProcessJobs,
    *,
    config_file: Path | None = None,
) -> int:
    """종료 코드를 낸다. `config_file`(`--config`)을 주면 묶음의 `config.json` 대신 그 구성으로
    색인한다. 이벤트 루프를 스스로 열므로 실행 중인 루프 안에서는 부를 수 없다."""
    if not folder.is_dir():
        print(f"묶음 폴더가 없다: {folder}", file=sys.stderr)
        return EXIT_FAILED
    try:
        environment = read_eval_environment(environ)
        paths = BundlePaths(folder)
        eval_set = read_eval_set(paths, config_file=config_file)
    except EvalEnvironmentError as error:
        print(error, file=sys.stderr)
        return EXIT_FAILED
    except EvalSetFormatError as error:
        return _report(error.problems)
    problems = check_bundle_files(paths, eval_set)
    if problems:
        return _report(problems)
    documents, problems = _read_verified(paths, eval_set.documents)
    if problems:
        return _report(problems)
    try:
        settings = eval_settings(environment, eval_set.config)
        problems = run_in_selector_loop(check_database(environment.database_url, eval_set))
        if problems:
            return _report(problems)
        migrate_database(settings)
        return run_in_selector_loop(_ingest_and_process(settings, documents, process_jobs))
    except (EvalEnvironmentError, ConfigurationError) as error:
        print(f"설정 오류: {error}", file=sys.stderr)
        return EXIT_FAILED
    except (OSError, SQLAlchemyError) as error:
        # 접속 실패의 메시지와 스택은 호스트와 사용자 이름을 싣는다(원칙 V). 오류의 종류만 알린다.
        print(f"데이터베이스를 쓰지 못했다({type(error).__name__})", file=sys.stderr)
        return EXIT_FAILED


def _report(problems: tuple[EvalProblem, ...]) -> int:
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"묶음의 오류 {len(problems)}건. 아무것도 쓰지 않았다", file=sys.stderr)
    return EXIT_FAILED


def _read_verified(
    paths: BundlePaths, listed: tuple[EvalDocument, ...]
) -> tuple[list[tuple[EvalDocument, bytes]], tuple[EvalProblem, ...]]:
    """문서 파일의 바이트를 읽어 해시를 대 본다. 수집에는 이 바이트를 넘긴다."""
    verified: list[tuple[EvalDocument, bytes]] = []
    problems: list[EvalProblem] = []
    for document in listed:
        try:
            data = paths.resolve(document.key, under=DOCUMENTS_FOLDER).read_bytes()
        except (BundlePathError, OSError):
            problems.append(EvalProblem(document.key, "문서 파일을 읽지 못했다"))
            continue
        if hashlib.sha256(data).hexdigest() != document.sha256:
            problems.append(
                EvalProblem(document.key, "읽는 사이에 문서 파일이 바뀌었다(해시가 다르다)")
            )
            continue
        verified.append((document, data))
    return verified, tuple(problems)


async def _ingest_and_process(
    settings: Settings, documents: list[tuple[EvalDocument, bytes]], process_jobs: ProcessJobs
) -> int:
    request_id = new_id()
    reset = request_id_var.set(request_id)
    engine = create_engine(settings.database_url)
    try:
        unit_of_work = PostgresUnitOfWork(engine)
        blob_store = LocalBlobStore(settings.data_dir)
        labels: dict[UUID, str] = {}
        rejected = 0
        for document, data in documents:
            try:
                result = await ingest_document(
                    unit_of_work,
                    blob_store,
                    IngestRequest(
                        filename=PurePosixPath(document.key).name,
                        data=data,
                        key=document.key,
                        group=None,
                        metadata=_NO_METADATA,
                        updated_at=document.updated_at,
                    ),
                    request_id=request_id,
                    now=datetime.now(UTC),
                    max_upload_bytes=settings.max_upload_mb * _BYTES_PER_MB,
                )
            except RequestError as error:
                print(f"거부\t{document.key}\t{error.code.value}", file=sys.stderr)
                rejected += 1
                continue
            print(f"{result.action.value}\t{document.key}")
            labels[result.document_id] = document.key

        async def work_then_sleep(seconds: float) -> None:
            await process_jobs(settings)
            await asyncio.sleep(seconds)

        await process_jobs(settings)
        waited = await wait_for_documents(
            unit_of_work,
            list(labels),
            poll_seconds=POLL_SECONDS,
            timeout_seconds=0.0,
            sleep=work_then_sleep,
            monotonic=time.monotonic,
        )
    finally:
        await engine.dispose()
        request_id_var.reset(reset)
    for failed in waited.failed:
        print(f"실패\t{labels[failed.document_id]}\t{failed.error_code.value}", file=sys.stderr)
    return EXIT_FAILED if rejected or waited.failed else EXIT_OK
