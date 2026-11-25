"""작업자의 일정 확인 반복(source-sync 명세 "일정과 일정 확인", ADR 0022).

일정 확인은 작업을 처리하는 슬롯과 따로 돈다. 슬롯이 모두 오래 걸리는 작업에 잡혀 있어도 일정이
밀리지 않게 하려는 것이다. `poll_seconds`마다 `check_schedules`를 한 번 부르고, 종료 신호가 오면
기다리던 중이라도 바로 나간다. 확인이 실패하면(데이터베이스에 닿지 못했거나 예기치 않은 예외) 로그만
남기고 다음 주기에 다시 한다. 시각이 지난 원천은 다음 확인에서 그대로 시각이 지난 채로 남아 있다.

같은 확인이 하루에 한 번 정리 작업도 넣는다(`check_cleanup`). 로그는 동기화 작업을 넣었거나 앞
동기화와 겹쳐 넣지 못했을 때, 정리 작업을 넣었을 때만 한 줄씩 남긴다. 아무 일도 없는 주기는
조용하다. 원천 이름과 기록·요청 ID만 싣고 설정 값은 싣지 않는다(원칙 V).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from rag_engine.adapters.log_format import log_event
from rag_engine.app.schedule_check import ScheduledSync, check_cleanup, check_schedules
from rag_engine.domain.errors import ErrorCode, TransientFailure
from rag_engine.domain.ports import ScheduleCalculator, UnitOfWork

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduleDeps:
    """일정 확인에 필요한 것. 슬롯의 작업 단위를 세어 보는 시험이 있어서, 일정 확인은 자기 작업
    단위를 따로 받는다. `now`는 "지금 시각"이다."""

    unit_of_work: UnitOfWork
    calculator: ScheduleCalculator
    now: Callable[[], datetime]


async def run_schedule_loop(
    schedules: ScheduleDeps, stop: asyncio.Event, *, poll_seconds: float
) -> None:
    """`stop`이 설 때까지 `poll_seconds`마다 일정을 한 번 확인한다."""
    while not stop.is_set():
        await check_once(schedules)
        try:
            async with asyncio.timeout(poll_seconds):
                await stop.wait()
        except TimeoutError:
            pass


async def check_once(schedules: ScheduleDeps) -> None:
    """일정 확인 한 번(원천의 동기화 일정, 그리고 정리 작업)과 그 로그. 실패는 밖으로 내지 않고
    로그로만 남긴다. 한쪽이 실패해도 다른 쪽을 돌린다."""
    await _guarded("sources", _check_sources, schedules)
    await _guarded("cleanup", _check_cleanup, schedules)


async def _check_sources(schedules: ScheduleDeps) -> None:
    handled = await check_schedules(
        schedules.unit_of_work, schedules.calculator, now=schedules.now()
    )
    for item in handled:
        _log_handled(item)


async def _check_cleanup(schedules: ScheduleDeps) -> None:
    job = await check_cleanup(schedules.unit_of_work, schedules.calculator, now=schedules.now())
    if job is not None:
        log_event(
            logger, "schedule_cleanup_enqueued", request_id=job.request_id, job_id=str(job.id)
        )


async def _guarded(
    name: str, check: Callable[[ScheduleDeps], Awaitable[None]], schedules: ScheduleDeps
) -> None:
    """`name`은 어느 확인(`sources`, `cleanup`)이 실패했는지 로그에 남기려는 이름이다."""
    try:
        await check(schedules)
    except TransientFailure as failure:
        log_event(
            logger,
            "schedule_check_failed",
            level=logging.WARNING,
            check=name,
            error_code=failure.code.value,
        )
    except Exception as error:
        # 일정 확인이 죽으면 일정이 모두 선다. 예외의 종류는 가리지 않고 알린 뒤 다음 주기에 다시
        # 한다.
        log_event(logger, "schedule_check_failed", level=logging.ERROR, check=name, exception=error)


def _log_handled(item: ScheduledSync) -> None:
    if item.started:
        log_event(
            logger,
            "schedule_sync_enqueued",
            request_id=item.request_id,
            source=item.source,
            sync_record_id=str(item.sync_record_id),
            job_id=str(item.job_id),
        )
        return
    log_event(
        logger,
        "schedule_sync_skipped",
        request_id=item.request_id,
        source=item.source,
        sync_record_id=str(item.sync_record_id),
        reason=ErrorCode.SYNC_IN_PROGRESS.value,
    )
