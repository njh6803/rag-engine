"""작업자의 작업 하나 처리(`process_job`, `run_once`, 티켓 07).

유스케이스가 어떻게 끝나든 작업 행이 그 모양으로 끝나는지, 임대를 잃은 시도는 남의 작업 행을
건드리지 않는지 본다. 실패를 가르는 끝냄과 재시도는 08과 12의 몫이라 여기서는 07의 단순한 끝냄만
잰다.
"""

import json
import logging
from uuid import UUID

import pytest
import sqlalchemy as sa
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import LEASE_SECONDS, Pipeline

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.parsing import ParsedDocument, ParserVersion
from rag_engine.worker.processing import process_job, run_once

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")


class _FailingRunner:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def current_version(self, mime: str) -> ParserVersion | None:
        return None

    async def parse(self, data: bytes, mime: str) -> ParsedDocument:
        raise self._error


async def _job_row(pipeline: Pipeline, document_id: UUID) -> tuple[str, str | None, int]:
    async with pipeline.engine.connect() as connection:
        row = (
            await connection.execute(
                sa.text(
                    "SELECT status, last_error_code, attempts FROM jobs WHERE document_id = :id"
                ),
                {"id": document_id},
            )
        ).one()
    return row[0], row[1], row[2]


async def test_유스케이스가_성공하면_작업이_성공으로_끝난다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()

    await process_job(pipeline.deps(), job)

    assert await _job_row(pipeline, ingested.document_id) == ("succeeded", None, 1)


async def test_오류_코드가_있는_실패는_그_코드로_작업을_끝낸다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()
    failing = _FailingRunner(PermanentFailure(ErrorCode.PARSE_FAILED, "깨진 파일"))

    await process_job(pipeline.deps(parse_runner=failing), job)

    assert await _job_row(pipeline, ingested.document_id) == ("failed", "parse_failed", 1)


async def test_어느_갈래에도_들지_않는_예외는_internal_error로_끝난다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()
    failing = _FailingRunner(RuntimeError("예기치 못한 오류"))

    await process_job(pipeline.deps(parse_runner=failing), job)

    assert await _job_row(pipeline, ingested.document_id) == ("failed", "internal_error", 1)


async def test_임대를_잃은_시도는_남의_작업_행을_끝내지_않고_잃었다고_남긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    ingested = await pipeline.ingest(휴가)
    lost = await pipeline.claim("worker-1")
    taken = await pipeline.claim("worker-2", later=LEASE_SECONDS + 1)

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(pipeline.deps(), lost)

    assert await _job_row(pipeline, ingested.document_id) == ("running", None, taken.attempts)
    finished = [
        payload
        for payload in (
            json.loads(JsonLinesFormatter().format(record)) for record in caplog.records
        )
        if payload["event"] == "job_finished"
    ]
    assert [(item["result"], item["error_code"]) for item in finished] == [("lost", None)]


async def test_한_번_돌면_꺼낼_작업을_모두_처리하고_수를_낸다(pipeline: Pipeline) -> None:
    first = await pipeline.ingest(휴가)
    출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
    second = await pipeline.ingest(출장, "출장.docx")

    processed = await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)

    assert processed == 2
    assert [
        (await _job_row(pipeline, ingested.document_id))[0] for ingested in (first, second)
    ] == ["succeeded", "succeeded"]
    assert await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS) == 0
