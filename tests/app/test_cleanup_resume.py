"""정리 작업의 다섯째 단계와 로그, 되살리기와의 겹침(source-sync 티켓 14, 명세 "정리 작업").

다섯째 단계는 재시도를 다 쓰고 멈춘 원천 삭제 작업과 원천 되살리기 작업을 다시 넣는다. 시험은
작업 행을 `failed`로 직접 써서 멈춘 모양을 만들고, 정리 작업을 한 번 돌린 뒤 작업자를 돌려 문서가
모두 옮겨지거나 되살아나는지 본다. 정리 작업이 끝에 남기는 한 줄의 로그와, 정리 작업이 원천을
지우는 도중에 끼어든 문서 되살리기가 500이 아니라 404로 끝나는 것도 여기서 본다.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
from uuid import UUID

import pytest
import sqlalchemy as sa
from tests.app.test_cleanup import (
    RETENTION_DAYS,
    claim_cleanup,
    cleanup_deps,
    delete_source_and_drain,
    drain,
    ingest_into,
    push_source,
    run_cleanup_at,
    scalar,
)
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import Pipeline

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.app.cleanup import run_cleanup
from rag_engine.app.delete_source import request_source_deletion
from rag_engine.app.restore_document import restore_document
from rag_engine.app.restore_source import request_source_restoration
from rag_engine.domain.entities import JobKind, JobStatus, Source
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome, Transaction, UnitOfWork
from rag_engine.worker.processing import run_once

PROCESSING_LOGGER = "rag_engine.worker.processing"
DEADLINE_SECONDS = 60.0


async def _fail(pipeline: Pipeline, job_id: UUID) -> None:
    """재시도를 다 쓰고 실패로 끝난 작업의 모양으로 쓴다."""
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text(
                "UPDATE jobs SET status = 'failed', last_error_code = 'worker_lost',"
                " finished_at = :now, leased_until = NULL WHERE id = :id"
            ),
            {"now": pipeline.clock[0], "id": job_id},
        )


async def _job_statuses(pipeline: Pipeline, kind: JobKind) -> list[str]:
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text("SELECT status FROM jobs WHERE kind = :kind ORDER BY id"), {"kind": kind.value}
        )
        return [row.status for row in rows]


async def _documents(pipeline: Pipeline, source: Source) -> tuple[int, int, int]:
    """(문서 수, 지운 문서 수, 원천과 함께 지웠다는 표시가 선 문서 수)."""
    async with pipeline.engine.connect() as connection:
        row = (
            await connection.execute(
                sa.text(
                    "SELECT count(*) AS total, count(deleted_at) AS deleted,"
                    " count(*) FILTER (WHERE deleted_with_source) AS marked"
                    " FROM documents WHERE source_id = :id"
                ),
                {"id": source.id},
            )
        ).one()
    return row.total, row.deleted, row.marked


async def _seed(pipeline: Pipeline, name: str = "위키") -> Source:
    source = await push_source(pipeline, name)
    for key in ("가.docx", "나.docx", "다.docx"):
        await ingest_into(pipeline, source, key)
    await drain(pipeline)
    return source


async def test_재시도를_다_쓰고_멈춘_원천_삭제_작업을_다시_넣어_문서를_모두_옮긴다(
    pipeline: Pipeline,
) -> None:
    source = await _seed(pipeline)
    requested = await request_source_deletion(
        pipeline.unit_of_work, source.name, request_id=new_id(), now=pipeline.clock[0]
    )
    await _fail(pipeline, requested.job_id)

    first = await run_cleanup_at(pipeline)

    assert first.jobs_requeued == 1
    assert await _job_statuses(pipeline, JobKind.DELETE_SOURCE) == ["failed", "queued"]
    # 다시 넣은 작업이 대기 중이므로 다음 정리 작업은 또 넣지 않는다.
    assert (await run_cleanup_at(pipeline)).jobs_requeued == 0
    await drain(pipeline)
    assert await _documents(pipeline, source) == (3, 3, 3)
    assert (await run_cleanup_at(pipeline)).jobs_requeued == 0


async def test_재시도를_다_쓰고_멈춘_원천_되살리기_작업을_다시_넣어_문서를_모두_되살린다(
    pipeline: Pipeline,
) -> None:
    source = await _seed(pipeline)
    await delete_source_and_drain(pipeline, source)
    restored = await request_source_restoration(
        pipeline.unit_of_work,
        source.name,
        request_id=new_id(),
        now=pipeline.clock[0],
        retention_days=RETENTION_DAYS,
    )
    # 표시를 걷은 뒤 되살리기 작업이 문서를 되살리지 못한 채 재시도를 다 썼다.
    await _fail(pipeline, restored.job_id)
    assert await _documents(pipeline, source) == (3, 3, 3)

    counts = await run_cleanup_at(pipeline)

    assert counts.jobs_requeued == 1
    assert await _job_statuses(pipeline, JobKind.RESTORE_SOURCE) == ["failed", "queued"]
    await drain(pipeline)
    assert await _documents(pipeline, source) == (3, 0, 0)
    assert (await run_cleanup_at(pipeline)).jobs_requeued == 0


async def test_문서를_모두_되살린_뒤_실패로_끝난_되살리기_작업도_다시_넣는다(
    pipeline: Pipeline,
) -> None:
    source = await _seed(pipeline)
    await delete_source_and_drain(pipeline, source)
    restored = await request_source_restoration(
        pipeline.unit_of_work,
        source.name,
        request_id=new_id(),
        now=pipeline.clock[0],
        retention_days=RETENTION_DAYS,
    )
    await drain(pipeline)
    # 문서는 모두 되살았는데 색인이 멈춘 문서를 잇는 단계에서 실패로 끝난 작업이다.
    await _fail(pipeline, restored.job_id)
    assert await _documents(pipeline, source) == (3, 0, 0)

    counts = await run_cleanup_at(pipeline)

    assert counts.jobs_requeued == 1
    await drain(pipeline)
    assert await _job_statuses(pipeline, JobKind.RESTORE_SOURCE) == ["failed", "succeeded"]
    assert (await run_cleanup_at(pipeline)).jobs_requeued == 0


async def test_멈추지_않은_원천에는_작업을_넣지_않는다(pipeline: Pipeline) -> None:
    await _seed(pipeline, "그대로")
    done = await _seed(pipeline, "끝남")
    await delete_source_and_drain(pipeline, done)

    counts = await run_cleanup_at(pipeline)

    assert counts.jobs_requeued == 0
    assert await _job_statuses(pipeline, JobKind.DELETE_SOURCE) == ["succeeded"]
    assert await _job_statuses(pipeline, JobKind.RESTORE_SOURCE) == []


async def test_원천_삭제_작업이_실행_중이면_다시_넣지_않는다(pipeline: Pipeline) -> None:
    source = await _seed(pipeline)
    await request_source_deletion(
        pipeline.unit_of_work, source.name, request_id=new_id(), now=pipeline.clock[0]
    )
    # 작업자가 꺼내 돌고 있다. 문서는 아직 그대로다.
    running = await pipeline.claim("worker-other")

    counts = await run_cleanup_at(pipeline)

    assert running.kind is JobKind.DELETE_SOURCE
    assert counts.jobs_requeued == 0
    assert await _job_statuses(pipeline, JobKind.DELETE_SOURCE) == ["running"]


def _events(caplog: pytest.LogCaptureFixture, name: str) -> list[dict[str, object]]:
    parsed = [
        json.loads(JsonLinesFormatter().format(record))
        for record in caplog.records
        if record.name == PROCESSING_LOGGER
    ]
    return [event for event in parsed if event["event"] == name]


async def test_정리_작업은_끝에_종류별_개수를_한_줄로_남긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await pipeline.ingest(docx_bytes("지움", "지울 문서다."), "지움.docx")
    await pipeline.delete("지움.docx")
    stalled = await _seed(pipeline)
    # 원천은 하루 늦게 지워 정리 작업이 도는 날에는 보관 기간이 하루 남는다.
    pipeline.clock[0] = NOW + timedelta(days=1)
    requested = await request_source_deletion(
        pipeline.unit_of_work, stalled.name, request_id=new_id(), now=pipeline.clock[0]
    )
    await _fail(pipeline, requested.job_id)
    pipeline.clock[0] = NOW + timedelta(days=RETENTION_DAYS)
    async with pipeline.unit_of_work.begin() as transaction:
        queued = await transaction.jobs.enqueue_cleanup(
            pipeline.clock[0] + timedelta(days=1), new_id(), pipeline.clock[0]
        )
    assert queued is not None

    with caplog.at_level(logging.INFO, logger=PROCESSING_LOGGER):
        await run_once(pipeline.deps(), worker_id="worker-log", lease_seconds=600.0)

    [line] = _events(caplog, "cleanup_finished")
    assert line["request_id"] == str(queued.request_id)
    assert {
        key: line[key]
        for key in (
            "documents_purged",
            "sources_purged",
            "blobs_removed",
            "sync_records_deleted",
            "jobs_requeued",
        )
    } == {
        "documents_purged": 1,
        "sources_purged": 0,
        "blobs_removed": 0,
        "sync_records_deleted": 0,
        "jobs_requeued": 1,
    }
    # 문서의 키와 제목, 원천의 이름은 싣지 않는다(원칙 V).
    assert "지움" not in json.dumps(line, ensure_ascii=False)
    assert "위키" not in json.dumps(line, ensure_ascii=False)


class PauseWhenSourceGone:
    """원천 행을 지운 작업 단위를 커밋하기 직전에 멈춘다. 그 작업 단위는 원천 행을 지운 채 잠금을
    쥐고 `release`가 서기를 기다리므로, 연결 둘로 "지우는 도중에 끼어드는 요청"을 만들 수 있다. 어느
    번째 작업 단위인지 세지 않고, 작업 단위 안에서 원천 행이 안 보이는지로 가른다."""

    def __init__(self, inner: UnitOfWork, source_id: UUID) -> None:
        self._inner = inner
        self._source_id = source_id
        self.paused = asyncio.Event()
        self.release = asyncio.Event()

    def begin(self) -> AbstractAsyncContextManager[Transaction]:
        return self._begin()

    @asynccontextmanager
    async def _begin(self) -> AsyncGenerator[Transaction]:
        async with self._inner.begin() as transaction:
            yield transaction
            if await transaction.catalog.get_source_by_id(self._source_id) is None:
                self.paused.set()
                await self.release.wait()


async def _purge_source_with_crossing_request(
    pipeline: Pipeline, refused: Callable[[Pipeline, UUID], Coroutine[object, object, ErrorCode]]
) -> ErrorCode:
    """원천 하나를 지우는 정리 작업이 원천 행을 지운 채 커밋을 기다릴 때 요청 하나(`refused`, 문서
    ID를 받는다)를 끼워 넣고, 그 요청이 거절된 오류 코드를 낸다."""
    source = await push_source(pipeline, "위키")
    document_id = await ingest_into(pipeline, source, "규정.docx")
    await drain(pipeline)
    await delete_source_and_drain(pipeline, source)
    pipeline.clock[0] = NOW + timedelta(days=RETENTION_DAYS)
    job = await claim_cleanup(pipeline)
    pausing = PauseWhenSourceGone(pipeline.unit_of_work, source.id)
    cleaning = asyncio.create_task(run_cleanup(cleanup_deps(pipeline, unit_of_work=pausing), job))

    crossing: asyncio.Task[ErrorCode] | None = None
    try:
        async with asyncio.timeout(DEADLINE_SECONDS):
            await pausing.paused.wait()
        # 정리 작업이 원천 행을 지운 채 커밋을 기다린다. 이때 온 요청은 문서나 원천을 읽은 뒤
        # 원천 행을 기다린다.
        crossing = asyncio.create_task(refused(pipeline, document_id))
        await asyncio.sleep(0.3)
        assert not crossing.done()
        pausing.release.set()

        async with asyncio.timeout(DEADLINE_SECONDS):
            await cleaning
            code = await crossing
    finally:
        # 중간 단언이 실패해도 정리 작업이 커밋 직전에 잠금과 연결을 쥔 채 남지 않게 한다.
        pausing.release.set()
        cleaning.cancel()
        await asyncio.gather(cleaning, return_exceptions=True)
        if crossing is not None:
            crossing.cancel()
            await asyncio.gather(crossing, return_exceptions=True)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.finish(job, JobOutcome(JobStatus.SUCCEEDED, None), pipeline.clock[0])
    assert await scalar(pipeline, "SELECT count(*) FROM sources WHERE name = '위키'") == 0
    return code


async def test_원천을_지우는_도중에_끼어든_문서_되살리기는_500이_아니라_404로_끝난다(
    pipeline: Pipeline,
) -> None:
    code = await _purge_source_with_crossing_request(pipeline, _document_refused)

    assert code is ErrorCode.DOCUMENT_NOT_FOUND


async def test_원천을_지우는_도중에_끼어든_원천_되살리기는_500이_아니라_404로_끝난다(
    pipeline: Pipeline,
) -> None:
    code = await _purge_source_with_crossing_request(pipeline, _source_refused)

    assert code is ErrorCode.SOURCE_NOT_FOUND


async def _document_refused(pipeline: Pipeline, document_id: UUID) -> ErrorCode:
    with pytest.raises(RequestError) as refused:
        await restore_document(
            pipeline.unit_of_work, document_id, request_id=new_id(), now=pipeline.clock[0]
        )
    return refused.value.code


async def _source_refused(pipeline: Pipeline, _document_id: UUID) -> ErrorCode:
    with pytest.raises(RequestError) as refused:
        await request_source_restoration(
            pipeline.unit_of_work,
            "위키",
            request_id=new_id(),
            now=pipeline.clock[0],
            retention_days=RETENTION_DAYS,
        )
    return refused.value.code
