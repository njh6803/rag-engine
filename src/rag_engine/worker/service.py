"""상시로 도는 작업자(명세 "수집 파이프라인과 작업"의 작업자 항목, ADR 0009, 티켓 13).

작업자는 `LISTEN rag_jobs`로 깨어나고 `poll_seconds`마다 폴링하며, `concurrency`개의 슬롯이 작업을
비동기로 함께 처리한다. 슬롯은 작업을 하나 꺼내 처리하고, 꺼낼 작업이 없으면 알림이나 폴링 시각이나
종료 신호를 기다린다. 알림을 놓치지 않으려고 깨움을 순번으로 센다. 슬롯이 꺼내기를 시작하기 전의
순번을 기억해 두고, 꺼낼 작업이 없었는데 그사이 순번이 바뀌었으면 기다리지 않고 바로 다시 꺼낸다.

종료 신호(`stop`)를 받으면 새 작업을 꺼내지 않고, 진행 중인 작업은 끝낸 뒤 나간다. 데이터베이스에
잠시 닿지 못해 꺼내기나 처리가 일시 실패로 끝나면(`TransientFailure`) 로그를 남기고 다음 반복으로
넘어간다. 처리 중이던 작업은 임대가 끝난 뒤 다른 작업자(또는 이 작업자)가 가져간다.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from rag_engine.adapters.log_format import log_event
from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.domain.errors import TransientFailure
from rag_engine.worker.processing import process_job

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    worker_id: str
    lease_seconds: float
    concurrency: int
    poll_seconds: float


class JobListener(Protocol):
    async def run(self, on_notify: Callable[[], None], ready: asyncio.Event) -> None:
        """작업 알림을 들으며 알림마다 `on_notify`를 부른다. 듣기가 시작되면 `ready`를 세우고,
        취소될 때까지 돈다."""
        ...


class _Wakeups:
    """깨움 순번. 알림이 오거나 종료 신호가 오면 순번이 오르고 기다리는 슬롯이 깨어난다."""

    def __init__(self) -> None:
        self.sequence = 0
        self._waiters: list[asyncio.Future[None]] = []

    def poke(self) -> None:
        self.sequence += 1
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(None)
        self._waiters.clear()

    async def wait(self, seen: int, timeout: float) -> None:
        """`seen` 뒤에 깨움이 있었으면 바로, 아니면 깨움이나 `timeout`초를 기다린다."""
        if self.sequence != seen:
            return
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            async with asyncio.timeout(timeout):
                await waiter
        except TimeoutError:
            pass
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)


async def serve(
    deps: IndexDocumentDeps, config: WorkerConfig, *, stop: asyncio.Event, listener: JobListener
) -> None:
    """`stop`이 서고 진행 중인 작업이 모두 끝날 때까지 작업을 꺼내 처리한다. 먼저 작업 알림 듣기를
    시작한 뒤 꺼내기를 시작해 그 사이에 온 알림을 놓치지 않는다. 데이터베이스가 내려가 듣기가 서지
    않으면 `poll_seconds`만 기다리고 폴링으로 시작하며, 그 사이에 종료 신호가 오면 기다리지 않고
    나간다."""
    wakeups = _Wakeups()
    ready = asyncio.Event()
    listening = asyncio.create_task(listener.run(wakeups.poke, ready))
    listening.add_done_callback(_log_listener_failure)
    stopping = asyncio.create_task(_poke_on_stop(stop, wakeups))
    try:
        try:
            async with asyncio.timeout(config.poll_seconds):
                await _until_any(ready, stop)
        except TimeoutError:
            pass
        log_event(
            logger,
            "worker_started",
            worker_id=config.worker_id,
            concurrency=config.concurrency,
            poll_seconds=config.poll_seconds,
            lease_seconds=config.lease_seconds,
            listening=ready.is_set(),
        )
        async with asyncio.TaskGroup() as slots:
            for _ in range(config.concurrency):
                slots.create_task(_slot(deps, config, stop, wakeups))
        log_event(logger, "worker_stopped", worker_id=config.worker_id)
    finally:
        listening.cancel()
        stopping.cancel()
        await asyncio.gather(listening, stopping, return_exceptions=True)


async def _until_any(first: asyncio.Event, second: asyncio.Event) -> None:
    """두 표지 가운데 하나라도 설 때까지 기다린다."""
    waiting = [asyncio.create_task(each.wait()) for each in (first, second)]
    try:
        await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for each in waiting:
            each.cancel()
        await asyncio.gather(*waiting, return_exceptions=True)


def _log_listener_failure(task: asyncio.Task[None]) -> None:
    """듣기가 연결 오류가 아닌 예외로 죽으면 알린다. 작업자는 폴링으로 계속 돈다. 예외의 메시지는
    싣지 않는다(원칙 V, `log_event`가 종류와 프레임만 싣는다)."""
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        log_event(logger, "job_listener_failed", level=logging.ERROR, exception=error)


async def _poke_on_stop(stop: asyncio.Event, wakeups: _Wakeups) -> None:
    await stop.wait()
    wakeups.poke()


async def _slot(
    deps: IndexDocumentDeps, config: WorkerConfig, stop: asyncio.Event, wakeups: _Wakeups
) -> None:
    while not stop.is_set():
        seen = wakeups.sequence
        try:
            async with deps.unit_of_work.begin() as transaction:
                job = await transaction.jobs.claim(
                    config.worker_id, deps.now(), config.lease_seconds
                )
            if job is not None:
                await process_job(deps, job, lease_seconds=config.lease_seconds)
                continue
        except TransientFailure as failure:
            log_event(
                logger,
                "worker_database_unavailable",
                level=logging.WARNING,
                worker_id=config.worker_id,
                error_code=failure.code.value,
            )
        await wakeups.wait(seen, config.poll_seconds)
