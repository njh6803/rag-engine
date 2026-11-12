"""상시로 도는 작업자 반복(`serve`, 명세 "수집 파이프라인과 작업"의 작업자 항목, 티켓 13).

실제 테스트 PostgreSQL과 실제 알림 듣기(`LISTEN rag_jobs`) 위에서 돌린다. `NOTIFY`로 깨어나는 시험은
폴링 간격을 단언의 기한보다 길게 두어 폴링으로 지나가지 않게 한다. 동시 처리와 종료 시점은
임베딩 직전에 끼어드는 훅으로 정한다.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import (
    FlakyUnitOfWork,
    WatchedUnitOfWork,
    interrupting_embedder_for,
)
from tests.support.pipeline import LEASE_SECONDS, Pipeline

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.adapters.postgres.notifications import JobNotificationListener
from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.worker.service import JobListener, WorkerConfig, serve

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
WAIT_SECONDS = 60.0
# 알림으로 깨어나는 시험이 폴링으로 지나가지 않도록 대기 기한보다 훨씬 길게 둔다.
LONG_POLL_SECONDS = 5 * WAIT_SECONDS


class _ObservedListener:
    """실제 듣기에 위임하며 듣기가 시작된 것을 시험이 볼 수 있게 한다."""

    def __init__(self, database_url: str) -> None:
        self._inner = JobNotificationListener(database_url, retry_seconds=0.05)
        self.ready = asyncio.Event()

    async def run(self, on_notify: Callable[[], None], ready: asyncio.Event) -> None:
        async def mirror() -> None:
            await ready.wait()
            self.ready.set()

        mirroring = asyncio.create_task(mirror())
        try:
            await self._inner.run(on_notify, ready)
        finally:
            mirroring.cancel()


class _NeverReadyListener:
    """듣기가 서지 않은 채 취소될 때까지 도는 듣기(데이터베이스가 내려가 접속하지 못하는 상황)."""

    async def run(self, on_notify: Callable[[], None], ready: asyncio.Event) -> None:
        await asyncio.Event().wait()


class _SilentListener:
    """듣기는 서지만 알림은 한 번도 보내지 않는 듣기."""

    async def run(self, on_notify: Callable[[], None], ready: asyncio.Event) -> None:
        ready.set()
        await asyncio.Event().wait()


class _BrokenListener:
    """연결 오류가 아닌 예외로 죽는 듣기."""

    async def run(self, on_notify: Callable[[], None], ready: asyncio.Event) -> None:
        raise RuntimeError("시험용 예외")


class _Running:
    """띄운 작업자. 시험이 멈추게 하거나 끝나기를 기다린다."""

    def __init__(self, task: asyncio.Task[None], stop: asyncio.Event, listener: _ObservedListener):
        self.task = task
        self.stop = stop
        self.listener = listener

    async def wait_until_listening(self) -> None:
        async with asyncio.timeout(WAIT_SECONDS):
            await self.listener.ready.wait()

    async def finish(self) -> None:
        self.stop.set()
        async with asyncio.timeout(WAIT_SECONDS):
            await self.task


@pytest.fixture
async def start_worker(
    pipeline: Pipeline, empty_database_url: str
) -> AsyncIterator[Callable[..., _Running]]:
    running: list[_Running] = []

    def start(
        deps: IndexDocumentDeps | None = None,
        *,
        concurrency: int = 1,
        poll_seconds: float = LONG_POLL_SECONDS,
    ) -> _Running:
        listener = _ObservedListener(empty_database_url)
        stop = asyncio.Event()
        config = WorkerConfig(
            worker_id="worker-test",
            lease_seconds=LEASE_SECONDS,
            concurrency=concurrency,
            poll_seconds=poll_seconds,
        )
        task = asyncio.create_task(
            serve(deps or pipeline.deps(), config, stop=stop, listener=listener)
        )
        started = _Running(task, stop, listener)
        running.append(started)
        return started

    yield start
    for started in running:
        started.stop.set()
        await asyncio.gather(started.task, return_exceptions=True)


async def _wait_for_statuses(
    pipeline: Pipeline, document_id: UUID, wanted: list[str], timeout: float = WAIT_SECONDS
) -> None:
    async with asyncio.timeout(timeout):
        while await pipeline.job_statuses(document_id) != wanted:
            await asyncio.sleep(0.05)


def _serve_with(
    pipeline: Pipeline, listener: JobListener, poll_seconds: float
) -> tuple[asyncio.Task[None], asyncio.Event]:
    stop = asyncio.Event()
    config = WorkerConfig(
        worker_id="worker-test",
        lease_seconds=LEASE_SECONDS,
        concurrency=1,
        poll_seconds=poll_seconds,
    )
    task = asyncio.create_task(serve(pipeline.deps(), config, stop=stop, listener=listener))
    return task, stop


def _events(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [json.loads(JsonLinesFormatter().format(record))["event"] for record in caplog.records]


async def test_알림이_오면_폴링을_기다리지_않고_깨어나_작업을_처리한다(
    pipeline: Pipeline, start_worker: Callable[..., _Running]
) -> None:
    watched = WatchedUnitOfWork(pipeline.unit_of_work)
    worker = start_worker(pipeline.deps(unit_of_work=watched))
    await worker.wait_until_listening()
    # 첫 꺼내기가 수집 뒤에 시작하면 알림이 고장 나도 그 꺼내기가 작업을 가져가 시험이 통과한다.
    # 첫 꺼내기가 빈손으로 끝난 뒤에 수집해야 폴링이 아니라 알림으로 깨어난 것을 가려낸다.
    async with asyncio.timeout(WAIT_SECONDS):
        await watched.ended.wait()

    ingested = await pipeline.ingest(휴가)
    await _wait_for_statuses(pipeline, ingested.document_id, ["succeeded"])
    await worker.finish()

    assert len(await pipeline.chunk_texts(ingested.document_id)) > 0


async def test_시작할_때_이미_쌓인_작업을_바로_처리한다(
    pipeline: Pipeline, start_worker: Callable[..., _Running]
) -> None:
    ingested = await pipeline.ingest(휴가)

    worker = start_worker()
    await _wait_for_statuses(pipeline, ingested.document_id, ["succeeded"])
    await worker.finish()


async def test_동시_처리_수만큼_작업을_함께_처리한다(
    pipeline: Pipeline, start_worker: Callable[..., _Running]
) -> None:
    first = await pipeline.ingest(휴가)
    second = await pipeline.ingest(출장, "출장.docx")
    arrived = 0
    both_arrived = asyncio.Event()

    async def wait_for_the_other_job() -> None:
        nonlocal arrived
        arrived += 1
        if arrived >= 2:
            both_arrived.set()
        async with asyncio.timeout(20):
            await both_arrived.wait()

    deps = pipeline.deps(
        embedder_for=interrupting_embedder_for(pipeline.pool, wait_for_the_other_job)
    )

    worker = start_worker(deps, concurrency=2)
    await _wait_for_statuses(pipeline, first.document_id, ["succeeded"])
    await _wait_for_statuses(pipeline, second.document_id, ["succeeded"])
    await worker.finish()


async def test_쉬는_작업자는_종료_신호에_폴링을_기다리지_않고_나간다(
    pipeline: Pipeline, start_worker: Callable[..., _Running]
) -> None:
    watched = WatchedUnitOfWork(pipeline.unit_of_work)
    worker = start_worker(pipeline.deps(unit_of_work=watched))
    await worker.wait_until_listening()
    # 듣기가 서자마자 종료를 걸면 슬롯이 쉬는 자리에 들기 전에 반복을 마쳐, 종료 신호가 쉬는 슬롯을
    # 깨우는지 가려내지 못한다. 첫 꺼내기가 끝나면 슬롯은 쉬고 있다.
    async with asyncio.timeout(WAIT_SECONDS):
        await watched.ended.wait()

    await worker.finish()


async def test_종료_신호를_받으면_진행_중인_작업은_끝내고_새_작업은_꺼내지_않는다(
    pipeline: Pipeline, start_worker: Callable[..., _Running]
) -> None:
    first = await pipeline.ingest(휴가)
    second = await pipeline.ingest(출장, "출장.docx")
    holder: list[_Running] = []

    async def stop_while_processing() -> None:
        holder[0].stop.set()
        await asyncio.sleep(0.2)

    deps = pipeline.deps(
        embedder_for=interrupting_embedder_for(pipeline.pool, stop_while_processing)
    )

    holder.append(start_worker(deps))
    async with asyncio.timeout(WAIT_SECONDS):
        await holder[0].task

    assert await pipeline.job_statuses(first.document_id) == ["succeeded"]
    assert len(await pipeline.chunk_texts(first.document_id)) > 0
    assert await pipeline.job_statuses(second.document_id) == ["queued"]


async def test_데이터베이스에_닿지_못해도_멈추지_않고_다음_반복에_이어서_처리한다(
    pipeline: Pipeline,
    start_worker: Callable[..., _Running],
    caplog: pytest.LogCaptureFixture,
) -> None:
    ingested = await pipeline.ingest(휴가)
    flaky = FlakyUnitOfWork(pipeline.unit_of_work, failures=2)

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.service"):
        worker = start_worker(pipeline.deps(unit_of_work=flaky), poll_seconds=0.05)
        await _wait_for_statuses(pipeline, ingested.document_id, ["succeeded"])
        await worker.finish()

    assert _events(caplog).count("worker_database_unavailable") == 2


async def test_듣기가_서기_전에_종료_신호를_받으면_폴링_간격을_기다리지_않고_나간다(
    pipeline: Pipeline,
) -> None:
    task, stop = _serve_with(pipeline, _NeverReadyListener(), poll_seconds=LONG_POLL_SECONDS)

    await asyncio.sleep(0.2)
    stop.set()

    async with asyncio.timeout(5):
        await task


async def test_알림이_없어도_폴링_간격마다_다시_꺼내_작업을_처리한다(pipeline: Pipeline) -> None:
    task, stop = _serve_with(pipeline, _SilentListener(), poll_seconds=0.1)
    try:
        await asyncio.sleep(0.4)
        ingested = await pipeline.ingest(휴가)
        await _wait_for_statuses(pipeline, ingested.document_id, ["succeeded"], timeout=10)
    finally:
        stop.set()
        await task


async def test_듣기가_예기치_않은_예외로_죽어도_폴링으로_계속_처리하고_알린다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    ingested = await pipeline.ingest(휴가)

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.service"):
        task, stop = _serve_with(pipeline, _BrokenListener(), poll_seconds=0.05)
        try:
            await _wait_for_statuses(pipeline, ingested.document_id, ["succeeded"], timeout=10)
        finally:
            stop.set()
            await task

    assert _events(caplog).count("job_listener_failed") == 1
