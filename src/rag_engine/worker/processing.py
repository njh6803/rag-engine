"""작업자의 작업 처리와 한 번 돌기 입구(명세 "수집 파이프라인과 작업", 티켓 07).

`run_once`는 지금 꺼낼 수 있는 작업을 더는 없을 때까지 하나씩 꺼내 처리하고 돌아온다. 테스트와 첫
왕복이 쓰는 입구다. 상시로 도는 작업자(`LISTEN`, 폴링, 동시 처리, 임대 연장, 종료 신호)는 13이다.

작업 하나는 `job_started`와 `job_finished` 이벤트를 남긴다. 요청 ID는 작업 행이 든 수집 요청의 ID다.
싣는 칸은 작업 ID, 종류, 문서 ID, 시도 횟수, 결과, 오류 코드, 파싱·임베딩·쓰기 지연이고 문서의 키와
제목은 싣지 않는다(원칙 V). 결과는 작업이 시도 뒤에 놓인 상태다. 성공은 `succeeded`, 영구 실패는
`failed`, 다시 예약한 일시 실패는 `queued`, 임대를 잃은 시도는 `lost`이고, 오류 코드는 실패한 시도의
것이다. 실패한 시도도 그때까지의 지연을 싣는다.

파싱의 영구 실패는 08이 문서와 색인에 적고 이 모듈이 작업을 재시도 없이 `failed`와 그 코드로
끝낸다. 일시 실패는 시도가 남아 있으면 백오프 뒤로 다시 예약하고 다 썼으면 재시도 소진으로 끝낸다.
어느 갈래에도 들지 않는 예외는 `job_crashed`를 남기고 `internal_error`로 다시 예약하지 않고
재시도 소진과 같이 끝낸다(`app/job_failure.py`).
"""

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from rag_engine.adapters.log_format import log_event
from rag_engine.app.index_document import (
    IndexDocumentDeps,
    IndexResult,
    IndexTimer,
    IndexTimings,
    index_document,
)
from rag_engine.app.job_failure import exhaust, settle_transient_failure
from rag_engine.domain.entities import Job, JobStatus
from rag_engine.domain.errors import AttemptLostError, ErrorCode, RagEngineError, TransientFailure
from rag_engine.domain.ports import JobOutcome

logger = logging.getLogger(__name__)

_MS_PER_SECOND: Final = 1000.0

type _Settle = Callable[[IndexDocumentDeps, Job, ErrorCode], Awaitable[JobOutcome]]


@dataclass(frozen=True, slots=True)
class _Settled:
    """시도가 끝난 모양. `outcome`이 `None`이면 임대를 잃은 시도다. `recorded`는 작업 행을 이미
    썼다는 뜻이다(다시 예약하기와 재시도 소진이 잠금 순서 안에서 쓴다)."""

    outcome: JobOutcome | None
    timings: IndexTimings
    recorded: bool = False


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
    settled = await _run(deps, job)
    outcome, timings = settled.outcome, settled.timings
    if outcome is not None and not settled.recorded:
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


async def _run(deps: IndexDocumentDeps, job: Job) -> _Settled:
    """유스케이스를 돌려 끝난 모양을 낸다. 임대를 잃은 시도는 끝낼 작업 행이 이미 남의 것이라 끝난
    모양이 `None`이다. 일시 실패는 다시 예약하거나 재시도 소진으로, 어느 갈래에도 들지 않는
    예외는 `internal_error`로 재시도 소진과 같이 끝낸다. 실패한 시도도 그때까지의 지연을 싣는다."""
    timer = IndexTimer()
    try:
        result: IndexResult = await index_document(deps, job, timer)
    except AttemptLostError:
        return _Settled(None, timer.timings())
    except TransientFailure as failure:
        return await _settle(deps, job, timer, failure.code, settle_transient_failure)
    except RagEngineError as error:
        return _Settled(JobOutcome(JobStatus.FAILED, error.code), timer.timings())
    except Exception as error:  # 어느 갈래에도 들지 않는 예외는 `internal_error`다
        log_event(
            logger,
            "job_crashed",
            level=logging.ERROR,
            request_id=job.request_id,
            exception=error,
        )
        return await _settle(deps, job, timer, ErrorCode.INTERNAL_ERROR, exhaust)
    return _Settled(result.outcome, result.timings)


async def _settle(
    deps: IndexDocumentDeps, job: Job, timer: IndexTimer, code: ErrorCode, settle: _Settle
) -> _Settled:
    """실패한 시도를 `settle`로 마무리한다. 일시 실패는 시도가 남았으면 다시 예약하는
    `settle_transient_failure`, 어느 갈래에도 들지 않는 예외는 바로 끝내는 `exhaust`를 받는다.
    작업 행은 `settle` 안에서 이미 썼다."""
    try:
        outcome = await settle(deps, job, code)
    except AttemptLostError:
        return _Settled(None, timer.timings())
    return _Settled(outcome, timer.timings(), recorded=True)
