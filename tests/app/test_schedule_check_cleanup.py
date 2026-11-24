"""일정 확인이 정리 작업을 넣는 때(source-sync 티켓 14, 명세 "정리 작업").

일정 시간대(`RAG_SCHEDULE_TIMEZONE`)로 가장 최근의 새벽 3시보다 뒤에 넣은 정리 작업이 없으면 하나
넣는다. 정리 작업을 넣은 적이 없는 설치에서는 첫 확인이 넣고, 이미 대기 중이거나 실행 중이면 넣지
않는다. 시험의 서울 시각 새벽 3시는 UTC로 전날 18시다.
"""

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from tests.records import NOW
from tests.support.pipeline import Pipeline
from tests.support.schedule_sources import SEOUL_CALCULATOR

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.app.schedule_check import check_cleanup
from rag_engine.domain.entities import Job, JobKind
from rag_engine.worker.schedule_loop import check_once

LOGGER = "rag_engine.worker.schedule_loop"
# 서울 시각 2026-11-12 03:00이다. 시험의 `NOW`(서울 시각 11-11 18:00)보다 아홉 시간 뒤다.
NEXT_THREE = datetime(2026, 11, 11, 18, 0, tzinfo=UTC)


async def _check(pipeline: Pipeline, now: datetime) -> Job | None:
    return await check_cleanup(pipeline.unit_of_work, SEOUL_CALCULATOR, now=now)


async def _cleanup_rows(pipeline: Pipeline) -> list[tuple[str, object, object]]:
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text("SELECT status, source_id, document_id FROM jobs WHERE kind = 'cleanup'")
        )
        return [(row.status, row.source_id, row.document_id) for row in rows]


async def _finish_all(pipeline: Pipeline) -> None:
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE jobs SET status = 'succeeded' WHERE kind = 'cleanup'")
        )


async def test_정리_작업을_넣은_적이_없는_설치에서는_첫_확인이_넣는다(pipeline: Pipeline) -> None:
    job = await _check(pipeline, NOW)

    assert job is not None
    assert (job.kind, job.source_id, job.document_id) == (JobKind.CLEANUP, None, None)
    assert await _cleanup_rows(pipeline) == [("queued", None, None)]


async def test_대기_중이거나_실행_중인_정리_작업이_있으면_넣지_않는다(pipeline: Pipeline) -> None:
    await _check(pipeline, NOW)
    # 새벽 3시가 지나 새로 넣을 때가 됐어도 앞 작업이 대기 중이면 넣지 않는다.
    waiting = await _check(pipeline, NEXT_THREE)
    await pipeline.claim("worker-1", later=0.0)
    running = await _check(pipeline, NEXT_THREE)

    assert waiting is None
    assert running is None
    assert await _cleanup_rows(pipeline) == [("running", None, None)]


async def test_다음_새벽_3시_전의_확인은_넣지_않고_3시_뒤의_첫_확인은_넣는다(
    pipeline: Pipeline,
) -> None:
    await _check(pipeline, NOW)
    await _finish_all(pipeline)

    before = await _check(pipeline, NEXT_THREE - timedelta(minutes=1))
    at = await _check(pipeline, NEXT_THREE)

    assert before is None
    assert at is not None


async def test_작업자가_며칠_꺼져_있었으면_다시_켜진_뒤의_첫_확인이_한_번만_넣는다(
    pipeline: Pipeline,
) -> None:
    await _check(pipeline, NOW)
    await _finish_all(pipeline)
    later = NOW + timedelta(days=5)

    first = await _check(pipeline, later)
    await _finish_all(pipeline)
    second = await _check(pipeline, later + timedelta(minutes=1))

    assert first is not None
    assert second is None


async def test_새벽_3시가_지난_첫_확인이_정리_작업을_넣고_한_줄을_남긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    pipeline.clock[0] = NOW
    with caplog.at_level(logging.INFO, logger=LOGGER):
        await check_once(pipeline.schedules())
        await check_once(pipeline.schedules())

    events = [
        json.loads(JsonLinesFormatter().format(record))
        for record in caplog.records
        if record.name == LOGGER
    ]
    [row] = await _cleanup_rows(pipeline)
    [line] = events
    assert row[0] == "queued"
    assert line["event"] == "schedule_cleanup_enqueued"
    assert set(line) >= {"request_id", "job_id"}
