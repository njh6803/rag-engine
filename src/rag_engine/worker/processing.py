"""작업자의 작업 처리와 한 번 돌기 입구(명세 "수집 파이프라인과 작업", 티켓 07, 13).

`run_once`는 지금 꺼낼 수 있는 작업을 더는 없을 때까지 하나씩 꺼내 처리하고 돌아온다. 테스트와 첫
왕복이 쓰는 입구다. 상시로 도는 작업자(`LISTEN`, 폴링, 동시 처리, 종료 신호)는 `service.py`다.

`lease_seconds`를 주면 처리하는 동안 그 삼분의 일마다 임대를 늘린다. 연장이 작업 행 조건에 걸리면
임대가 끝나 다른 작업자가 가져간 것이라 처리를 멈추고 그 시도를 버린다. 시도 횟수를 이미 다 쓴
작업을 임대 인수로 꺼냈으면 다시 돌리지 않고 `worker_lost`로 끝낸다. 동기 CPU 호출(청킹의 문장
분리와 키워드 토큰화)은 이벤트 루프 안에서 부르므로 아주 큰 문서에서는 연장이 늦을 수 있다. 그래도
임대를 잃은 시도는 작업 행 조건에 걸려 문서에도 작업 행에도 쓰지 못하므로 데이터는 어긋나지 않는다.
다만 인수마다 시도 횟수가 오르므로, 임대보다 오래 루프를 막는 문서는 인수가 되풀이되다
`worker_lost`로 끝날 수 있다.

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

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, auto
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
# 임대 기간 안에서 연장하는 횟수. 간격은 앞 연장이 끝난 뒤부터 센다. 연장 한 번이 임대 기간의
# 삼분의 일 안에 실패로 돌아오면 임대가 끝나기 전에 한 번 더 시도한다.
_EXTENSIONS_PER_LEASE: Final = 3

type _Settle = Callable[[IndexDocumentDeps, Job, ErrorCode], Awaitable[JobOutcome]]


class _JobRow(Enum):
    """작업 행을 누가 쓰는가. 다시 예약하기와 재시도 소진은 잠금 순서 안에서 자기 작업 단위가 이미
    쓰고(`WRITTEN`), 나머지는 `process_job`이 이어서 끝낸다(`PENDING`)."""

    PENDING = auto()
    WRITTEN = auto()


@dataclass(frozen=True, slots=True)
class _Settled:
    """시도가 끝난 모양. `outcome`이 `None`이면 임대를 잃은 시도다."""

    outcome: JobOutcome | None
    timings: IndexTimings
    job_row: _JobRow = _JobRow.PENDING


async def run_once(deps: IndexDocumentDeps, *, worker_id: str, lease_seconds: float) -> int:
    """꺼낼 수 있는 작업을 모두 처리하고 처리한 수를 낸다."""
    processed = 0
    while True:
        async with deps.unit_of_work.begin() as transaction:
            job = await transaction.jobs.claim(worker_id, deps.now(), lease_seconds)
        if job is None:
            return processed
        await process_job(deps, job, lease_seconds=lease_seconds)
        processed += 1


async def process_job(
    deps: IndexDocumentDeps, job: Job, *, lease_seconds: float | None = None
) -> None:
    """꺼낸 작업 하나를 처리한다. `lease_seconds`가 `None`이면 임대를 늘리지 않는다(한 번에 끝나는
    시험용이다. 작업자는 항상 임대 기간을 준다)."""
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
    settled = await _run(deps, job, lease_seconds)
    outcome, timings = settled.outcome, settled.timings
    if outcome is not None and settled.job_row is _JobRow.PENDING:
        outcome = await _finish(deps, job, outcome)
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


async def _finish(deps: IndexDocumentDeps, job: Job, outcome: JobOutcome) -> JobOutcome | None:
    """작업 행을 끝낸 상태로 쓴다. 끝내기 직전에 임대를 잃었으면 작업 행은 새 작업자의 것이라 쓰지
    못하고 `None`을 낸다."""
    try:
        async with deps.unit_of_work.begin() as transaction:
            await transaction.jobs.finish(job, outcome, deps.now())
    except AttemptLostError:
        return None
    return outcome


async def _run(deps: IndexDocumentDeps, job: Job, lease_seconds: float | None) -> _Settled:
    """유스케이스를 돌려 끝난 모양을 낸다. 임대를 잃은 시도는 끝낼 작업 행이 이미 남의 것이라 끝난
    모양이 `None`이다. 일시 실패는 다시 예약하거나 재시도 소진으로, 어느 갈래에도 들지 않는
    예외는 `internal_error`로 재시도 소진과 같이 끝낸다. 시도를 이미 다 쓴 작업을 임대 인수로 꺼낸
    시도는 유스케이스를 돌리지 않고 `worker_lost`로 재시도 소진과 같이 끝낸다. 실패한 시도도
    그때까지의 지연을 싣는다."""
    timer = IndexTimer()
    if deps.retry.is_overrun(job.attempts):
        return await _settle(deps, job, timer, ErrorCode.WORKER_LOST, exhaust)
    try:
        result: IndexResult = await _index(deps, job, timer, lease_seconds)
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


async def _index(
    deps: IndexDocumentDeps, job: Job, timer: IndexTimer, lease_seconds: float | None
) -> IndexResult:
    """유스케이스를 돌리면서 임대를 늘린다. 연장이 임대를 잃었다고 알리면 유스케이스를 취소하고
    `AttemptLostError`를 올린다. 유스케이스가 끝나거나 실패하면 연장을 멈춘다."""
    if lease_seconds is None:
        return await index_document(deps, job, timer)
    work = asyncio.create_task(index_document(deps, job, timer))
    keeper = asyncio.create_task(_keep_lease(deps, job, lease_seconds))
    try:
        await asyncio.wait({work, keeper}, return_when=asyncio.FIRST_COMPLETED)
        if work.done():
            return work.result()
        keeper.result()
        raise AttemptLostError
    finally:
        work.cancel()
        keeper.cancel()
        await asyncio.gather(work, keeper, return_exceptions=True)


def extension_interval_seconds(lease_seconds: float) -> float:
    """임대를 늘리는 간격. 임대 기간의 삼분의 일이다."""
    return lease_seconds / _EXTENSIONS_PER_LEASE


async def _keep_lease(deps: IndexDocumentDeps, job: Job, lease_seconds: float) -> None:
    """임대 기간의 삼분의 일마다 임대를 늘린다. 연장이 작업 행 조건에 걸려 임대를 잃은 것이 드러나면
    돌아온다. 그 밖의 이유로 연장하지 못한 것(일시 실패, 잠금 대기 시간 초과 같은 예기치 않은
    오류)은 알리고 다음 간격에 다시 한다. 연장이 죽어 건강한 작업이 같이 실패하는 것보다, 계속
    실패해 임대가 끝나고 다른 작업자가 인수하는 쪽이 안전하다."""
    while True:
        await asyncio.sleep(extension_interval_seconds(lease_seconds))
        try:
            async with deps.unit_of_work.begin() as transaction:
                await transaction.jobs.extend_lease(
                    job, deps.now() + timedelta(seconds=lease_seconds)
                )
        except AttemptLostError:
            return
        except TransientFailure:
            log_event(
                logger,
                "lease_extension_failed",
                level=logging.WARNING,
                request_id=job.request_id,
                job_id=str(job.id),
            )
        except Exception as error:  # 연장의 예기치 않은 오류가 처리 중인 작업을 죽이지 않게 한다
            log_event(
                logger,
                "lease_extension_failed",
                level=logging.ERROR,
                request_id=job.request_id,
                job_id=str(job.id),
                exception=error,
            )


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
    return _Settled(outcome, timer.timings(), _JobRow.WRITTEN)
