"""처리 중의 임대 연장과 임대 인수(명세 "수집 파이프라인과 작업"의 작업자 항목, 티켓 13).

실제 테스트 PostgreSQL 위에서 `process_job`을 돌린다. 임대 연장은 `lease_seconds`의 삼분의 일마다
돌므로 시험은 임대를 0.3초로 주어 0.1초 간격으로 지켜본다. 임대가 끝나 다른 작업자가 가져가는 일은
시계를 건너뛴 두 번째 꺼내기로 만들고, 끼어들 곳은 임베딩 직전이다(`interrupting_embedder_for`).
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import (
    FailingRunner,
    FlakyUnitOfWork,
    Interloper,
    interrupting_embedder_for,
)
from tests.support.pipeline import BACKOFF_BASE_SECONDS, LEASE_SECONDS, Pipeline

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.domain.entities import IndexStateStatus, Job
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.parsing import ParsedDocument, ParserVersion
from rag_engine.worker.processing import extension_interval_seconds, process_job

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
SHORT_LEASE_SECONDS = 0.3


def _policy(max_attempts: int) -> RetryPolicy:
    return RetryPolicy(max_attempts=max_attempts, backoff_base_seconds=BACKOFF_BASE_SECONDS)


async def _leased_until(pipeline: Pipeline, job_id: UUID) -> datetime | None:
    async with pipeline.unit_of_work.begin() as transaction:
        job = await transaction.jobs.get(job_id)
    assert job is not None
    return job.leased_until


def _finished_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    payloads = (json.loads(JsonLinesFormatter().format(record)) for record in caplog.records)
    return [payload for payload in payloads if payload["event"] == "job_finished"]


class _RaisingRunner:
    """파싱 자리에서 먼저 끼어들 일을 하고 `RagEngineError`를 던진다. 유스케이스가 작업 행을 쓰기
    전에 올라오는 오류라 `process_job`이 바로 작업을 끝내려는 길을 만든다."""

    def __init__(self, before_raising: Interloper | None = None) -> None:
        self._before_raising = before_raising

    def current_version(self, mime: str) -> ParserVersion | None:
        return None

    async def parse(self, data: bytes, mime: str) -> ParsedDocument:
        if self._before_raising is not None:
            await self._before_raising()
        raise RequestError(ErrorCode.INTERNAL_ERROR, "시험용 오류")


async def test_처리하는_동안_임대_기간의_삼분의_일마다_임대를_늘린다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()
    assert await _leased_until(pipeline, job.id) == NOW + timedelta(seconds=LEASE_SECONDS)
    observed: list[datetime | None] = []

    async def wait_while_lease_extends() -> None:
        pipeline.clock[0] = NOW + timedelta(hours=1)
        await asyncio.sleep(0.5)
        observed.append(await _leased_until(pipeline, job.id))

    deps = pipeline.deps(
        embedder_for=interrupting_embedder_for(pipeline.pool, wait_while_lease_extends)
    )

    await process_job(deps, job, lease_seconds=SHORT_LEASE_SECONDS)

    assert observed == [NOW + timedelta(hours=1, seconds=SHORT_LEASE_SECONDS)]
    assert len(await pipeline.chunk_texts(ingested.document_id)) > 0


def test_임대를_늘리는_간격은_임대_기간의_삼분의_일이다() -> None:
    assert extension_interval_seconds(900.0) == pytest.approx(300.0)


async def test_임대_연장이_일시_실패해도_다음_간격에_다시_늘린다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await pipeline.ingest(휴가)
    job = await pipeline.claim()
    flaky = FlakyUnitOfWork(pipeline.unit_of_work, failures=0)
    observed: list[datetime | None] = []

    async def fail_one_extension_then_wait() -> None:
        pipeline.clock[0] = NOW + timedelta(hours=1)
        flaky.fail_next()
        await asyncio.sleep(0.5)
        observed.append(await _leased_until(pipeline, job.id))

    deps = pipeline.deps(
        unit_of_work=flaky,
        embedder_for=interrupting_embedder_for(pipeline.pool, fail_one_extension_then_wait),
    )

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(deps, job, lease_seconds=SHORT_LEASE_SECONDS)

    events = [json.loads(JsonLinesFormatter().format(record))["event"] for record in caplog.records]
    assert events.count("lease_extension_failed") == 1
    assert observed == [NOW + timedelta(hours=1, seconds=SHORT_LEASE_SECONDS)]
    assert [item["result"] for item in _finished_events(caplog)] == ["succeeded"]


async def test_임대_연장이_예기치_않게_실패해도_작업을_실패로_끝내지_않고_다음_간격에_다시_늘린다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await pipeline.ingest(휴가)
    job = await pipeline.claim()
    flaky = FlakyUnitOfWork(pipeline.unit_of_work, failures=0)
    observed: list[datetime | None] = []

    async def crash_one_extension_then_wait() -> None:
        pipeline.clock[0] = NOW + timedelta(hours=1)
        flaky.fail_next(error=ValueError("시험용 예기치 않은 예외"))
        await asyncio.sleep(0.5)
        observed.append(await _leased_until(pipeline, job.id))

    deps = pipeline.deps(
        unit_of_work=flaky,
        embedder_for=interrupting_embedder_for(pipeline.pool, crash_one_extension_then_wait),
    )

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(deps, job, lease_seconds=SHORT_LEASE_SECONDS)

    events = [json.loads(JsonLinesFormatter().format(record))["event"] for record in caplog.records]
    assert events.count("lease_extension_failed") == 1
    assert observed == [NOW + timedelta(hours=1, seconds=SHORT_LEASE_SECONDS)]
    assert [item["result"] for item in _finished_events(caplog)] == ["succeeded"]


async def test_임대를_늘리지_않는_처리는_꺼낼_때_둔_임대_그대로다(pipeline: Pipeline) -> None:
    await pipeline.ingest(휴가)
    job = await pipeline.claim()
    observed: list[datetime | None] = []

    async def wait() -> None:
        pipeline.clock[0] = NOW + timedelta(hours=1)
        await asyncio.sleep(0.4)
        observed.append(await _leased_until(pipeline, job.id))

    deps = pipeline.deps(embedder_for=interrupting_embedder_for(pipeline.pool, wait))

    await process_job(deps, job)

    assert observed == [NOW + timedelta(seconds=LEASE_SECONDS)]


async def test_임대를_잃은_것이_드러나면_처리를_멈추고_문서에도_작업_행에도_쓰지_않는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    ingested = await pipeline.ingest(휴가)
    lost = await pipeline.claim("worker-1")
    reached_after_takeover: list[str] = []

    async def lose_lease_and_keep_waiting() -> None:
        await pipeline.claim("worker-2", later=LEASE_SECONDS + 1)
        await asyncio.sleep(10)
        reached_after_takeover.append("취소되지 않고 기다림이 끝났다")

    deps = pipeline.deps(
        embedder_for=interrupting_embedder_for(pipeline.pool, lose_lease_and_keep_waiting)
    )
    started = time.monotonic()

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(deps, lost, lease_seconds=SHORT_LEASE_SECONDS)

    assert time.monotonic() - started < 5
    assert reached_after_takeover == []
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert [
        (row.status, row.attempts) for row in await pipeline.job_rows(ingested.document_id)
    ] == [("running", 2)]
    assert [(item["result"], item["error_code"]) for item in _finished_events(caplog)] == [
        ("lost", None)
    ]


async def test_연장하지_못한_채_다른_작업자가_가져가도_처음_작업자는_쓰지_않고_가져간_쪽이_끝낸다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    first = await pipeline.claim("worker-1")
    taken_jobs: list[Job] = []

    async def lose_lease() -> None:
        taken_jobs.append(await pipeline.claim("worker-2", later=LEASE_SECONDS + 1))

    losing = pipeline.deps(embedder_for=interrupting_embedder_for(pipeline.pool, lose_lease))

    await process_job(losing, first)

    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.states(ingested.document_id) == {}
    assert [
        (row.status, row.attempts) for row in await pipeline.job_rows(ingested.document_id)
    ] == [("running", 2)]

    await process_job(pipeline.deps(), taken_jobs[0])

    assert [row.status for row in await pipeline.job_rows(ingested.document_id)] == ["succeeded"]
    assert len(await pipeline.chunk_texts(ingested.document_id)) > 0


async def test_끝내려는_시점에_임대를_잃었으면_성공이_아니라_잃었다고_남긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    ingested = await pipeline.ingest(휴가)
    lost = await pipeline.claim("worker-1")

    async def lose_lease() -> None:
        await pipeline.claim("worker-2", later=LEASE_SECONDS + 1)

    runner = _RaisingRunner(before_raising=lose_lease)

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(pipeline.deps(parse_runner=runner), lost)

    rows = await pipeline.job_rows(ingested.document_id)
    assert [(row.status, row.last_error_code, row.attempts) for row in rows] == [
        ("running", None, 2)
    ]
    assert [(item["result"], item["error_code"]) for item in _finished_events(caplog)] == [
        ("lost", None)
    ]


async def test_끝낼_수_있으면_갱신_여부와_상관없이_기존_결과를_남긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(pipeline.deps(parse_runner=_RaisingRunner()), job)

    rows = await pipeline.job_rows(ingested.document_id)
    assert [(row.status, row.last_error_code) for row in rows] == [("failed", "internal_error")]
    assert [(item["result"], item["error_code"]) for item in _finished_events(caplog)] == [
        ("failed", "internal_error")
    ]


async def test_횟수를_다_쓴_작업을_임대_인수로_꺼내면_다시_돌리지_않고_worker_lost로_끝낸다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    retry = _policy(2)
    await pipeline.claim("worker-1")
    await pipeline.claim("worker-1", later=LEASE_SECONDS + 1)
    # 시도 둘을 다 쓴 작업이다. 이 파서가 불리면 오류 코드가 `parse_failed`가 되어 드러난다.
    taken = await pipeline.claim("worker-2", later=2 * (LEASE_SECONDS + 1))
    assert taken.attempts == 3

    await process_job(
        pipeline.deps(retry=retry, parse_runner=FailingRunner(ErrorCode.PARSE_FAILED)), taken
    )

    rows = await pipeline.job_rows(ingested.document_id)
    assert [(row.status, row.last_error_code, row.attempts) for row in rows] == [
        ("failed", "worker_lost", 3)
    ]
    state = (await pipeline.states(ingested.document_id))[pipeline.version.id]
    assert (state.status, state.error_code) == (IndexStateStatus.FAILED, ErrorCode.WORKER_LOST)
    assert await pipeline.chunk_texts(ingested.document_id) == []


async def test_마지막_시도를_임대_인수로_꺼낸_것은_다시_돌린다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    retry = _policy(2)
    await pipeline.claim("worker-1")
    taken = await pipeline.claim("worker-2", later=LEASE_SECONDS + 1)
    assert taken.attempts == 2

    await process_job(pipeline.deps(retry=retry), taken)

    rows = await pipeline.job_rows(ingested.document_id)
    assert [(row.status, row.last_error_code) for row in rows] == [("succeeded", None)]
    assert len(await pipeline.chunk_texts(ingested.document_id)) > 0


async def test_늦은_시도와_같은_프로세스가_횟수를_다_쓴_작업을_꺼내도_늦은_시도는_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    retry = _policy(2)
    late = await pipeline.claim("worker-1")
    retaken = await pipeline.claim("worker-1", later=LEASE_SECONDS + 1)
    taken = await pipeline.claim("worker-1", later=2 * (LEASE_SECONDS + 1))
    await process_job(pipeline.deps(retry=retry), taken)
    before = await pipeline.job_rows(ingested.document_id)

    await process_job(pipeline.deps(retry=retry), late)
    await process_job(pipeline.deps(retry=retry), retaken)

    after = await pipeline.job_rows(ingested.document_id)
    assert [(row.status, row.last_error_code, row.attempts) for row in after] == [
        ("failed", "worker_lost", 3)
    ]
    assert after == before
    assert await pipeline.chunk_texts(ingested.document_id) == []
