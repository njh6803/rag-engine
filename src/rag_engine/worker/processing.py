"""작업자의 작업 처리와 한 번 돌기 입구(명세 "수집 파이프라인과 작업", 티켓 07).

`run_once`는 지금 꺼낼 수 있는 작업을 더는 없을 때까지 하나씩 꺼내 처리하고 돌아온다. 테스트와 첫
왕복이 쓰는 입구다. 상시로 도는 작업자(`LISTEN`, 폴링, 동시 처리, 임대 연장, 종료 신호)는 13이다.

작업 하나는 `job_started`와 `job_finished` 이벤트를 남긴다. 요청 ID는 작업 행이 든 수집 요청의 ID다.
싣는 칸은 작업 ID, 종류, 문서 ID, 시도 횟수, 결과, 오류 코드, 파싱·임베딩·쓰기 지연이고 문서의 키와
제목은 싣지 않는다(원칙 V). 어느 갈래에도 들지 않는 예외는 `job_crashed`를 남기고 `internal_error`로
끝낸다. 파싱의 영구
실패는 08이 문서와 색인에 적고 이 모듈이 작업을 재시도 없이 `failed`와 그 코드로 끝낸다. 일시
실패의 재시도와 소진, 오류의 번역은 12가 채운다.
"""

import logging
import time
from typing import Final

from rag_engine.adapters.log_format import log_event
from rag_engine.app.index_document import (
    IndexDocumentDeps,
    IndexResult,
    IndexTimings,
    index_document,
)
from rag_engine.domain.entities import Job, JobStatus
from rag_engine.domain.errors import AttemptLostError, ErrorCode, RagEngineError
from rag_engine.domain.ports import JobOutcome

logger = logging.getLogger(__name__)

_MS_PER_SECOND: Final = 1000.0
_NO_TIMINGS: Final = IndexTimings(parse_ms=0.0, embedding_ms=0.0, write_ms=0.0)


async def run_once(deps: IndexDocumentDeps, *, worker_id: str, lease_seconds: float) -> int:
    """꺼낼 수 있는 작업을 모두 처리하고 처리한 수를 낸다."""
    processed = 0
    while True:
        async with deps.unit_of_work.begin() as transaction:
            job = await transaction.jobs.claim(worker_id, deps.now(), lease_seconds)
        if job is None:
            return processed
        await process_job(deps, job)
        processed += 1


async def process_job(deps: IndexDocumentDeps, job: Job) -> None:
    started = time.perf_counter()
    log_event(
        logger,
        "job_started",
        request_id=job.request_id,
        job_id=str(job.id),
        kind=job.kind.value,
        document_id=str(job.document_id),
        attempts=job.attempts,
    )
    outcome, timings = await _run(deps, job)
    if outcome is not None:
        async with deps.unit_of_work.begin() as transaction:
            await transaction.jobs.finish(job, outcome, deps.now())
    log_event(
        logger,
        "job_finished",
        level=logging.INFO if outcome is None or outcome.error_code is None else logging.WARNING,
        request_id=job.request_id,
        duration_ms=(time.perf_counter() - started) * _MS_PER_SECOND,
        job_id=str(job.id),
        kind=job.kind.value,
        document_id=str(job.document_id),
        attempts=job.attempts,
        result="lost" if outcome is None else outcome.status.value,
        error_code=None
        if outcome is None or outcome.error_code is None
        else outcome.error_code.value,
        parse_ms=timings.parse_ms,
        embedding_ms=timings.embedding_ms,
        write_ms=timings.write_ms,
    )


async def _run(deps: IndexDocumentDeps, job: Job) -> tuple[JobOutcome | None, IndexTimings]:
    """유스케이스를 돌려 끝난 모양을 낸다. 임대를 잃은 시도는 끝낼 작업 행이 이미 남의 것이라
    `None`이다."""
    try:
        result: IndexResult = await index_document(deps, job)
    except AttemptLostError:
        return None, _NO_TIMINGS
    except RagEngineError as error:
        return JobOutcome(JobStatus.FAILED, error.code), _NO_TIMINGS
    except Exception as error:  # 어느 갈래에도 들지 않는 예외는 `internal_error`다
        log_event(
            logger,
            "job_crashed",
            level=logging.ERROR,
            request_id=job.request_id,
            exception=error,
        )
        return JobOutcome(JobStatus.FAILED, ErrorCode.INTERNAL_ERROR), _NO_TIMINGS
    return result.outcome, result.timings
