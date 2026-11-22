"""돌아오지 않는 커넥터 호출이 동기화와 작업자를 붙잡지 않는 길(source-sync 티켓 07, 명세
"Testing Decisions"의 열둘 가운데 작업자의 것).

가짜 레지스트리가 아니라 실제 `EntryPointConnectorRegistry`와 그 호출 장치(`ConnectorCallGuard`)를
쓰고, entry point가 `tests/support/hanging_connectors.py`의 돌아오지 않는 커넥터를 가리킨다. 한도는
0.3초처럼 짧게 준다. 작업자는 `run_once`(작업 하나씩)와 실제 작업자 반복(`serve`, 자리 여럿)을
쓴다. 붙잡힌 호출은 시험이 끝날 때 `World`가 모두 푼다.
"""

import asyncio
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from importlib.metadata import EntryPoint

import pytest
import sqlalchemy as sa
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.hanging_connectors import Plan, World
from tests.support.pipeline import Pipeline

from rag_engine.adapters.connectors.guard import ConnectorCallGuard
from rag_engine.adapters.connectors.registry import (
    CONNECTOR_ENTRY_POINT_GROUP,
    EntryPointConnectorRegistry,
)
from rag_engine.app.sync_requests import SyncRequested, request_sync
from rag_engine.domain.connectors import ConnectorCallKind, ConnectorCallTimedOutError
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    Source,
    SourceKind,
    SyncRecord,
    SyncRecordStatus,
)
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import process_job, run_once
from rag_engine.worker.service import WorkerConfig, serve

ENTRY = EntryPoint(
    name="planned",
    value="tests.support.hanging_connectors:create_planned",
    group=CONNECTOR_ENTRY_POINT_GROUP,
)
# 읽기 한도. 시험이 돌아오지 않는 호출을 이 시간 안에 기다리고 나온다.
LIMIT_SECONDS = 0.3
# 시험이 기다리는 기한. 정상이면 한도의 몇 배 안에 끝나고, 어긋나면 영원히 돌지 않고 빨갛게 끝난다.
DEADLINE_SECONDS = 60.0
LEASE_SECONDS = 600.0
POLL_SECONDS = 0.05
CHECK_PAUSE_SECONDS = 0.05


@pytest.fixture
async def world() -> AsyncIterator[World]:
    built = World()
    try:
        yield built
    finally:
        await built.close()


def _docx(title: str = "규정") -> bytes:
    return docx_bytes(title, "본문이다.")


def _registry(guard: ConnectorCallGuard | None = None) -> EntryPointConnectorRegistry:
    return EntryPointConnectorRegistry(lambda: [ENTRY], guard=guard)


async def _make_source(
    pipeline: Pipeline, folder: str, *, name: str | None = None, rev: int = 1
) -> Source:
    source = Source(
        new_id(),
        name or folder,
        SourceKind.PULL,
        NOW,
        connector="planned",
        config={"folder": folder, "rev": rev},
        group_id=pipeline.group.id,
        exclude_patterns=(),
    )
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(source)
    return source


async def _request(pipeline: Pipeline, source: Source) -> SyncRequested:
    return await request_sync(
        pipeline.unit_of_work,
        source.name,
        apply_empty=False,
        reread=False,
        request_id=new_id(),
        now=pipeline.clock[0],
    )


async def _drain(
    pipeline: Pipeline,
    registry: EntryPointConnectorRegistry,
    *,
    limit: float = LIMIT_SECONDS,
    lease: float = LEASE_SECONDS,
) -> int:
    """꺼낼 수 있는 작업을 모두 처리한다. 돌아오지 않는 호출이 작업자를 붙잡으면 기한에서 빨갛게
    끝난다."""
    async with asyncio.timeout(DEADLINE_SECONDS):
        return await run_once(
            pipeline.deps(connectors=registry, source_read_timeout_seconds=limit),
            worker_id="worker-hung",
            lease_seconds=lease,
        )


async def _record(pipeline: Pipeline, requested: SyncRequested) -> SyncRecord:
    async with pipeline.unit_of_work.begin() as transaction:
        record = await transaction.sync_records.get(requested.sync_record_id)
    assert record is not None
    return record


async def _latest(pipeline: Pipeline, source: Source) -> SyncRecord | None:
    async with pipeline.unit_of_work.begin() as transaction:
        return await transaction.sync_records.latest_for_source(source.id)


async def _sync(
    pipeline: Pipeline, source: Source, registry: EntryPointConnectorRegistry
) -> SyncRecord:
    requested = await _request(pipeline, source)
    await _drain(pipeline, registry)
    return await _record(pipeline, requested)


async def _sync_job_rows(pipeline: Pipeline, source: Source) -> list[tuple[str, str | None, int]]:
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                "SELECT status, last_error_code, attempts FROM jobs"
                " WHERE source_id = :source AND kind = 'sync_source' ORDER BY id"
            ),
            {"source": source.id},
        )
        return [(row[0], row[1], row[2]) for row in rows]


async def _document(pipeline: Pipeline, source: Source, key: str) -> Document | None:
    async with pipeline.unit_of_work.begin() as transaction:
        return await transaction.documents.get_by_key(source.id, key)


async def _wait_until(check: Callable[[], Awaitable[bool]]) -> None:
    async with asyncio.timeout(DEADLINE_SECONDS):
        while not await check():
            await asyncio.sleep(CHECK_PAUSE_SECONDS)


async def _is_finished(pipeline: Pipeline, source: Source) -> bool:
    record = await _latest(pipeline, source)
    return record is not None and record.status in (
        SyncRecordStatus.SUCCEEDED,
        SyncRecordStatus.FAILED,
    )


async def _is_parsed(pipeline: Pipeline, source: Source, key: str) -> bool:
    document = await _document(pipeline, source, key)
    return document is not None and document.status is DocumentStatus.PARSED


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
        async with asyncio.timeout(DEADLINE_SECONDS):
            await self.task


def _serve(
    pipeline: Pipeline,
    registry: EntryPointConnectorRegistry,
    *,
    concurrency: int,
    limit: float,
) -> _Serving:
    stop = asyncio.Event()
    config = WorkerConfig(
        worker_id="worker-serve",
        lease_seconds=LEASE_SECONDS,
        concurrency=concurrency,
        poll_seconds=POLL_SECONDS,
    )
    deps = pipeline.deps(connectors=registry, source_read_timeout_seconds=limit)
    task = asyncio.create_task(serve(deps, config, stop=stop, listener=_PollOnly()))
    return _Serving(task, stop)


async def _stuck_index_fetch(
    pipeline: Pipeline, world: World
) -> tuple[Plan, Source, EntryPointConnectorRegistry, Document]:
    """동기화가 파일을 한 번 읽어 문서를 넣은 뒤, 색인 작업의 읽기(둘째 `fetch`)가 돌아오지 않아
    한도를 넘긴 호출이 남은 세계."""
    plan = world.plan("공유", {"규정.docx": _docx()}, fetch_ok=1)
    source = await _make_source(pipeline, "공유")
    registry = _registry()
    await _sync(pipeline, source, registry)
    document = await _document(pipeline, source, "규정.docx")
    assert document is not None
    return plan, source, registry, document


async def test_list가_돌아오지_않으면_한도에서_source_unreadable로_끝나고_다시_시도되지_않는다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("끊김", hang_list=True)
    source = await _make_source(pipeline, "끊김")
    registry = _registry()

    record = await _sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert record.listed is None
    assert await _sync_job_rows(pipeline, source) == [("failed", "source_unreadable", 1)]
    assert await _drain(pipeline, registry) == 0
    assert plan.list_calls == 1


async def test_끊긴_원천_하나가_자리를_잡아도_자리가_남으면_다른_원천의_동기화와_색인이_끝난다(
    pipeline: Pipeline, world: World
) -> None:
    stuck_plan = world.plan("끊김", hang_list=True)
    world.plan("멀쩡", {"규정.docx": _docx()})
    stuck = await _make_source(pipeline, "끊김")
    healthy = await _make_source(pipeline, "멀쩡")
    await _request(pipeline, stuck)
    await _request(pipeline, healthy)
    # 한도를 길게 주어, 끊긴 원천의 동기화가 이 시험 내내 자리 하나를 쥐게 한다.
    serving = _serve(pipeline, _registry(), concurrency=2, limit=DEADLINE_SECONDS)
    try:
        await _wait_until(lambda: _is_parsed(pipeline, healthy, "규정.docx"))

        stuck_record = await _latest(pipeline, stuck)
        healthy_record = await _latest(pipeline, healthy)
        assert stuck_plan.list_calls == 1
        assert stuck_record is not None
        assert stuck_record.status is SyncRecordStatus.RUNNING
        assert healthy_record is not None
        assert (healthy_record.status, healthy_record.added) == (SyncRecordStatus.SUCCEEDED, 1)
    finally:
        world.release_all()
        await serving.finish()


async def test_fetch가_돌아오지_않는_문서의_색인_작업은_자리를_잡지_않고_일시_실패로_다시_예약된다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("공유", {"규정.docx": _docx()}, fetch_ok=1)
    source = await _make_source(pipeline, "공유")

    record = await _sync(pipeline, source, _registry())

    document = await _document(pipeline, source, "규정.docx")
    assert document is not None
    assert (record.status, record.added) == (SyncRecordStatus.SUCCEEDED, 1)
    assert plan.fetch_calls == 2
    assert document.status is DocumentStatus.RECEIVED
    (row,) = await pipeline.job_rows(document.id)
    assert (row.status, row.last_error_code, row.attempts) == ("queued", "source_unreadable", 1)
    assert row.run_after > pipeline.clock[0]


async def test_호출이_남아_있는_동안_같은_설정의_다음_동기화는_커넥터를_부르지_않고_끝난다(
    pipeline: Pipeline, world: World
) -> None:
    plan, source, registry, _document_row = await _stuck_index_fetch(pipeline, world)

    record = await _sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert (plan.list_calls, plan.fetch_calls) == (1, 2)


async def test_설정을_고친_뒤의_동기화는_남은_호출과_상관없이_커넥터를_부른다(
    pipeline: Pipeline, world: World
) -> None:
    plan, source, registry, _document_row = await _stuck_index_fetch(pipeline, world)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.update_pull_source(
            source.id, config={"folder": "공유", "rev": 2}, exclude_patterns=None
        )

    record = await _sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.listed, record.unchanged) == (1, 1)
    assert plan.list_calls == 2


async def test_같은_커넥터와_설정을_쓰는_다른_원천의_동기화도_커넥터를_부르지_않고_끝난다(
    pipeline: Pipeline, world: World
) -> None:
    plan, _source, registry, _document_row = await _stuck_index_fetch(pipeline, world)
    other = await _make_source(pipeline, "공유", name="다른원천")

    record = await _sync(pipeline, other, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert plan.list_calls == 1


async def test_다른_자리의_호출이_한도를_넘겨_막히면_도는_동기화는_남은_파일을_세지_않고_끝난다(
    pipeline: Pipeline, world: World
) -> None:
    guard = ConnectorCallGuard()
    files = {f"규정{number}.docx": _docx(f"제{number}조") for number in (1, 2, 3)}
    plan = world.plan("폴더", files)
    source = await _make_source(pipeline, "폴더")

    async def another_slot_overruns() -> None:
        # 같은 설정을 다른 자리가 부르다 한도를 넘긴다. 이 동기화의 둘째 파일부터 막힌다.
        with pytest.raises(ConnectorCallTimedOutError):
            await guard.call(
                connector="planned",
                config={"folder": "폴더", "rev": 1},
                kind=ConnectorCallKind.FETCH,
                start=plan.hold,
                timeout_seconds=0.05,
            )

    plan.on_fetch = another_slot_overruns

    record = await _sync(pipeline, source, _registry(guard))

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert (record.listed, record.added) == (3, 1)
    assert record.failed == {}
    assert plan.fetch_calls == 1


async def test_막힌_설정이_자리_수보다_많아도_저마다_한도를_넘긴_뒤에는_멀쩡한_원천의_작업이_끝난다(
    pipeline: Pipeline, world: World
) -> None:
    guard = ConnectorCallGuard()
    names = [f"끊김{number}" for number in range(3)]
    plans = [world.plan(name, hang_list=True) for name in names]
    world.plan("멀쩡", {"규정.docx": _docx()})
    stuck = [await _make_source(pipeline, name) for name in names]
    healthy = await _make_source(pipeline, "멀쩡")
    for source in (*stuck, healthy):
        await _request(pipeline, source)
    serving = _serve(pipeline, _registry(guard), concurrency=2, limit=LIMIT_SECONDS)
    try:

        async def all_done() -> bool:
            finished = [await _is_finished(pipeline, source) for source in (*stuck, healthy)]
            return all(finished) and await _is_parsed(pipeline, healthy, "규정.docx")

        await _wait_until(all_done)

        records = [await _latest(pipeline, source) for source in stuck]
        healthy_record = await _latest(pipeline, healthy)
        assert [(r.status, r.failure_code) for r in records if r is not None] == [
            (SyncRecordStatus.FAILED, ErrorCode.SOURCE_UNREADABLE.value)
        ] * 3
        assert [plan.list_calls for plan in plans] == [1, 1, 1]
        assert healthy_record is not None
        assert (healthy_record.status, healthy_record.added) == (SyncRecordStatus.SUCCEEDED, 1)
        assert guard.outstanding_calls == 3
    finally:
        world.release_all()
        await serving.finish()


async def test_붙잡아_둔_호출을_풀어_준_뒤의_동기화는_성공한다(
    pipeline: Pipeline, world: World
) -> None:
    guard = ConnectorCallGuard()
    registry = _registry(guard)
    plan = world.plan("끊김", {"규정.docx": _docx()}, hang_list=True)
    source = await _make_source(pipeline, "끊김")
    blocked = await _sync(pipeline, source, registry)
    assert blocked.status is SyncRecordStatus.FAILED
    assert guard.outstanding_calls == 1

    plan.release()
    await _wait_until(lambda: _no_calls_left(guard))
    record = await _sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.listed, record.added) == (1, 1)
    assert plan.list_calls == 2
    assert await _is_parsed(pipeline, source, "규정.docx")


async def _no_calls_left(guard: ConnectorCallGuard) -> bool:
    return guard.outstanding_calls == 0


async def _run_clock(pipeline: Pipeline) -> None:
    """시험의 시계를 실제로 흐르는 시간에 맞춰 앞으로 보낸다. 작업 담당 기록의 기한은 이 시계로
    정해지므로, 시계가 흘러야 기한이 지나는지를 볼 수 있다."""
    start = time.monotonic()
    while True:
        pipeline.clock[0] = NOW + timedelta(seconds=time.monotonic() - start)
        await asyncio.sleep(0.02)


async def test_한도_안에_끝나는_느린_호출을_기다리는_동안_작업_담당_기록의_기한이_지나지_않는다(
    pipeline: Pipeline, world: World
) -> None:
    lease = 1.2
    plan = world.plan("느림", list_delay=3 * lease)
    source = await _make_source(pipeline, "느림")
    clock = asyncio.create_task(_run_clock(pipeline))
    worker: asyncio.Task[int] | None = None
    probes = 0
    try:
        requested = await _request(pipeline, source)
        # 읽기 한도는 호출이 걸리는 시간보다 길고, 작업 담당 기록의 기한은 그보다 짧다.
        worker = asyncio.create_task(
            _drain(pipeline, _registry(), limit=DEADLINE_SECONDS / 2, lease=lease)
        )

        async def running() -> bool:
            rows = await _sync_job_rows(pipeline, source)
            return [status for status, _code, _attempts in rows] == ["running"]

        await _wait_until(running)
        while not worker.done():
            async with pipeline.unit_of_work.begin() as transaction:
                taken = await transaction.jobs.claim("작업자-다른", pipeline.clock[0], lease)
            assert taken is None
            probes += 1
            await asyncio.sleep(0.2)
        assert await worker == 1
    finally:
        if worker is not None and not worker.done():
            worker.cancel()
        clock.cancel()
        await asyncio.gather(clock, return_exceptions=True)

    record = await _record(pipeline, requested)
    assert record.status is SyncRecordStatus.SUCCEEDED
    assert await _sync_job_rows(pipeline, source) == [("succeeded", None, 1)]
    assert plan.list_calls == 1
    assert probes >= 2 * 3


async def test_거두어진_시도의_호출이_한도_안에_돌아오면_다음_시도가_커넥터를_부른다(
    pipeline: Pipeline, world: World
) -> None:
    guard = ConnectorCallGuard()
    plan = world.plan("끊김", hang_list=True)
    source = await _make_source(pipeline, "끊김")
    requested = await _request(pipeline, source)
    deps = pipeline.deps(
        connectors=_registry(guard), source_read_timeout_seconds=DEADLINE_SECONDS / 2
    )
    async with pipeline.unit_of_work.begin() as transaction:
        first = await transaction.jobs.claim("작업자-1", pipeline.clock[0], 0.3)
    assert first is not None
    attempt = asyncio.create_task(process_job(deps, first, lease_seconds=0.3))

    async def listing_started() -> bool:
        return plan.list_calls == 1

    await _wait_until(listing_started)
    # 기한이 끝난 것으로 보이는 시각에 다른 작업자가 작업을 가져가고, 첫 시도는 기한을 늘리다 잃은
    # 것을 안다.
    second = await pipeline.claim("작업자-2", later=1000.0)
    async with asyncio.timeout(DEADLINE_SECONDS):
        await attempt
    assert (second.id, second.attempts) == (first.id, 2)
    assert guard.outstanding_calls == 0

    plan.release()
    await asyncio.sleep(CHECK_PAUSE_SECONDS)
    await process_job(deps, second, lease_seconds=LEASE_SECONDS)

    record = await _record(pipeline, requested)
    assert record.status is SyncRecordStatus.SUCCEEDED
    assert plan.list_calls == 2


async def test_한도를_넘긴_호출이_남은_채_종료_신호를_받은_작업자는_스스로_내려간다(
    pipeline: Pipeline, world: World
) -> None:
    guard = ConnectorCallGuard()
    world.plan("끊김", hang_list=True, in_thread=True)
    source = await _make_source(pipeline, "끊김")
    await _request(pipeline, source)
    baseline = set(threading.enumerate())
    serving = _serve(pipeline, _registry(guard), concurrency=1, limit=LIMIT_SECONDS)
    try:
        await _wait_until(lambda: _is_finished(pipeline, source))
        assert guard.outstanding_calls == 1

        await serving.finish()

        # 끊긴 읽기는 daemon 스레드에서 막힌 채이고, 프로세스가 내려가는 것을 붙잡는 스레드는 없다.
        stuck = [thread for thread in threading.enumerate() if thread.name == "hanging-call"]
        leftover = [
            thread
            for thread in threading.enumerate()
            if thread not in baseline and not thread.daemon
        ]
        assert len(stuck) == 1
        assert stuck[0].daemon
        assert stuck[0].is_alive()
        assert leftover == []
        assert guard.outstanding_calls == 1
    finally:
        world.release_all()
        serving.stop.set()
        await asyncio.gather(serving.task, return_exceptions=True)
