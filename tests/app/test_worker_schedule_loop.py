"""작업자의 일정 확인 반복(source-sync 티켓 10, 명세 "일정과 일정 확인"과 "로그").

일정 확인은 작업을 처리하는 슬롯과 따로 `poll_seconds`마다 돈다. 실제 테스트 PostgreSQL 위에서
`serve`를 띄우고, 일정이 지난 원천을 만들어 동기화 작업이 들어가는지 본다. "지금 시각"은 시험이
정한 값이다.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FlakyUnitOfWork, interrupting_embedder_for
from tests.support.pipeline import LEASE_SECONDS, Pipeline
from tests.support.schedule_sources import (
    CHECK_TIME,
    SEOUL_CALCULATOR,
    add_scheduled_source,
    records_of,
    source_named,
    sync_jobs,
)

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.app.sync_requests import request_sync
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import UnitOfWork
from rag_engine.worker.schedule_loop import ScheduleDeps
from rag_engine.worker.service import WorkerConfig, serve

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
WAIT_SECONDS = 60.0
POLL_SECONDS = 0.05
PAST = CHECK_TIME - timedelta(minutes=5)
LOGGER = "rag_engine.worker.schedule_loop"


class _PollOnly:
    """알림 없이 폴링으로만 도는 작업자 반복의 듣기."""

    async def run(self, on_notify: Callable[[], None], ready: asyncio.Event) -> None:
        ready.set()
        await asyncio.Event().wait()


@dataclass(frozen=True, slots=True)
class _Serving:
    task: asyncio.Task[None]
    stop: asyncio.Event

    async def finish(self) -> None:
        self.stop.set()
        async with asyncio.timeout(WAIT_SECONDS):
            await self.task


def _serve(
    deps: IndexDocumentDeps, unit_of_work: UnitOfWork, *, poll_seconds: float = POLL_SECONDS
) -> _Serving:
    stop = asyncio.Event()
    config = WorkerConfig(
        worker_id="worker-schedule",
        lease_seconds=LEASE_SECONDS,
        concurrency=1,
        poll_seconds=poll_seconds,
    )
    schedules = ScheduleDeps(unit_of_work, SEOUL_CALCULATOR, lambda: CHECK_TIME)
    task = asyncio.create_task(
        serve(deps, config, stop=stop, listener=_PollOnly(), schedules=schedules)
    )
    return _Serving(task, stop)


async def _until(condition: Callable[[], Awaitable[bool]]) -> None:
    async with asyncio.timeout(WAIT_SECONDS):
        while not await condition():
            await asyncio.sleep(0.02)


def _events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    """원천의 일정 로그. 정리 작업을 넣는 로그(첫 확인이 한 번 남긴다)는 따로 본다
    (`test_schedule_check_cleanup.py`)."""
    parsed = [
        json.loads(JsonLinesFormatter().format(record))
        for record in caplog.records
        if record.name == LOGGER
    ]
    return [event for event in parsed if event["event"] != "schedule_cleanup_enqueued"]


def _names(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [str(event["event"]) for event in _events(caplog)]


async def test_자리가_모두_긴_작업에_잡혀_있어도_일정_확인이_주기마다_돌아_동기화_작업을_넣는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    busy = asyncio.Event()
    release = asyncio.Event()

    async def hold_the_only_slot() -> None:
        busy.set()
        async with asyncio.timeout(WAIT_SECONDS):
            await release.wait()

    deps = pipeline.deps(embedder_for=interrupting_embedder_for(pipeline.pool, hold_the_only_slot))
    serving = _serve(deps, pipeline.unit_of_work)
    try:
        async with asyncio.timeout(WAIT_SECONDS):
            await busy.wait()
        source = await add_scheduled_source(pipeline.unit_of_work, "wiki", next_run_at=PAST)

        async def enqueued() -> bool:
            return len(await sync_jobs(pipeline.engine, source)) == 1

        await _until(enqueued)

        assert await pipeline.job_statuses(ingested.document_id) == ["running"]
        assert [job.status for job in await sync_jobs(pipeline.engine, source)] == ["queued"]
    finally:
        serving.stop.set()
        release.set()
        await serving.task


async def test_일정_확인은_같은_시각으로_주기마다_돌아도_작업을_한_번만_넣는다(
    pipeline: Pipeline,
) -> None:
    source = await add_scheduled_source(pipeline.unit_of_work, "wiki", next_run_at=PAST)
    serving = _serve(pipeline.deps(), pipeline.unit_of_work)
    try:

        async def moved_on() -> bool:
            found = await source_named(pipeline.unit_of_work, "wiki")
            return found.next_run_at is not None and found.next_run_at > CHECK_TIME

        await _until(moved_on)
        await asyncio.sleep(10 * POLL_SECONDS)
    finally:
        await serving.finish()

    assert len(await sync_jobs(pipeline.engine, source)) == 1
    assert len(await records_of(pipeline.unit_of_work, source)) == 1


async def test_일정이_작업을_넣거나_겹쳐서_못_넣었을_때만_한_줄씩_남긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await add_scheduled_source(pipeline.unit_of_work, "later", next_run_at=PAST + timedelta(days=1))
    started = await add_scheduled_source(pipeline.unit_of_work, "started", next_run_at=PAST)
    overlapped = await add_scheduled_source(pipeline.unit_of_work, "overlapped", next_run_at=PAST)
    await request_sync(
        pipeline.unit_of_work,
        "overlapped",
        apply_empty=False,
        reread=False,
        request_id=new_id(),
        now=PAST,
    )

    with caplog.at_level(logging.INFO, logger=LOGGER):
        serving = _serve(pipeline.deps(), pipeline.unit_of_work)
        try:

            async def logged() -> bool:
                return len(_events(caplog)) >= 2

            await _until(logged)
            await asyncio.sleep(10 * POLL_SECONDS)
        finally:
            await serving.finish()

    events = {str(event["source"]): event for event in _events(caplog)}
    assert sorted(_names(caplog)) == ["schedule_sync_enqueued", "schedule_sync_skipped"]
    assert events["started"]["event"] == "schedule_sync_enqueued"
    assert events["overlapped"]["event"] == "schedule_sync_skipped"
    assert events["overlapped"]["reason"] == "sync_in_progress"
    [started_record] = await records_of(pipeline.unit_of_work, started)
    assert events["started"]["sync_record_id"] == str(started_record.id)
    [started_job] = await sync_jobs(pipeline.engine, started)
    assert events["started"]["request_id"] == str(started_job.request_id)
    assert len(await records_of(pipeline.unit_of_work, overlapped)) == 2


async def test_시각이_지난_원천이_없으면_로그를_남기지_않는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await add_scheduled_source(
        pipeline.unit_of_work, "later", next_run_at=CHECK_TIME + timedelta(hours=1)
    )

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        serving = _serve(pipeline.deps(), pipeline.unit_of_work)
        await asyncio.sleep(20 * POLL_SECONDS)
        await serving.finish()

    assert _events(caplog) == []


@pytest.mark.parametrize("error", [None, RuntimeError("시험용 예기치 않은 예외")])
async def test_일정_확인이_실패하면_알리고_다음_주기에_다시_해서_작업을_넣는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture, error: Exception | None
) -> None:
    source = await add_scheduled_source(pipeline.unit_of_work, "wiki", next_run_at=PAST)
    flaky = FlakyUnitOfWork(pipeline.unit_of_work, failures=0)
    flaky.fail_next(2, error=error)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        serving = _serve(pipeline.deps(), flaky)
        try:

            async def enqueued() -> bool:
                return len(await sync_jobs(pipeline.engine, source)) == 1

            await _until(enqueued)
        finally:
            await serving.finish()

    assert _names(caplog).count("schedule_check_failed") == 2
    assert _names(caplog).count("schedule_sync_enqueued") == 1
    assert len(await sync_jobs(pipeline.engine, source)) == 1


async def test_종료_신호를_받으면_긴_폴링_간격을_기다리지_않고_일정_확인도_나간다(
    pipeline: Pipeline,
) -> None:
    serving = _serve(pipeline.deps(), pipeline.unit_of_work, poll_seconds=WAIT_SECONDS * 5)

    await asyncio.sleep(0.3)
    serving.stop.set()

    async with asyncio.timeout(5):
        await serving.task
