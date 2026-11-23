"""원천 삭제와 동기화(source-sync 티켓 11, 명세 "원천 삭제와 되살리기"와 "동기화의 차례").

실제 테스트 PostgreSQL과 실제 작업자 루프를 쓴다. 원천의 폴더는
`tests/support/hanging_connectors.py`의 계획이 움직이는 커넥터이고, 실제 레지스트리와 호출 장치를
거친다. 시험이 보는 것은 동기화가 지움 표시를 어느 자리에서 보고 어떻게 끝나는가, 그리고 원천 삭제
작업이 문서를 50건씩 옮기는가다.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from importlib.metadata import EntryPoint

import pytest
import sqlalchemy as sa
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.hanging_connectors import World
from tests.support.pipeline import MAX_UPLOAD_BYTES, Pipeline

from rag_engine.adapters.connectors.registry import (
    CONNECTOR_ENTRY_POINT_GROUP,
    EntryPointConnectorRegistry,
)
from rag_engine.app.delete_source import BATCH_SIZE, request_source_deletion
from rag_engine.app.ingest import IngestRequest, ingest_document
from rag_engine.app.source_lookup import lock_live_source
from rag_engine.app.sync_requests import SyncRequested, request_sync
from rag_engine.domain.entities import (
    JobKind,
    Source,
    SourceKind,
    SyncRecord,
    SyncRecordStatus,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import run_once

ENTRY = EntryPoint(
    name="planned",
    value="tests.support.hanging_connectors:create_planned",
    group=CONNECTOR_ENTRY_POINT_GROUP,
)
DEADLINE_SECONDS = 60.0
LEASE_SECONDS = 600.0
# 기한을 늘리는 간격이 삼분의 일이라 이 값이면 0.2초마다 지움 표시를 본다.
SHORT_LEASE_SECONDS = 0.6
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


def _registry() -> EntryPointConnectorRegistry:
    return EntryPointConnectorRegistry(lambda: [ENTRY])


async def _make_source(pipeline: Pipeline, folder: str) -> Source:
    source = Source(
        new_id(),
        folder,
        SourceKind.PULL,
        NOW,
        connector="planned",
        config={"folder": folder},
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


async def _delete(pipeline: Pipeline, source: Source) -> None:
    await request_source_deletion(
        pipeline.unit_of_work, source.name, request_id=new_id(), now=pipeline.clock[0]
    )


async def _drain(pipeline: Pipeline, *, lease: float = LEASE_SECONDS) -> int:
    async with asyncio.timeout(DEADLINE_SECONDS):
        return await run_once(
            pipeline.deps(connectors=_registry(), source_read_timeout_seconds=DEADLINE_SECONDS / 2),
            worker_id="worker-delete",
            lease_seconds=lease,
        )


async def _record(pipeline: Pipeline, requested: SyncRequested) -> SyncRecord:
    async with pipeline.unit_of_work.begin() as transaction:
        record = await transaction.sync_records.get(requested.sync_record_id)
    assert record is not None
    return record


async def _sync_jobs(pipeline: Pipeline, source: Source) -> list[tuple[str, str | None, int]]:
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                "SELECT status, last_error_code, attempts FROM jobs"
                " WHERE source_id = :source AND kind = 'sync_source' ORDER BY id"
            ),
            {"source": source.id},
        )
        return [(row[0], row[1], row[2]) for row in rows]


async def _document_keys(pipeline: Pipeline, source: Source) -> list[str]:
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text("SELECT key FROM documents WHERE source_id = :source ORDER BY key"),
            {"source": source.id},
        )
        return [row[0] for row in rows]


async def _wait_until(check: Callable[[], Awaitable[bool]]) -> None:
    async with asyncio.timeout(DEADLINE_SECONDS):
        while not await check():
            await asyncio.sleep(CHECK_PAUSE_SECONDS)


async def _run_and_delete_when(
    pipeline: Pipeline, source: Source, started: Callable[[], Awaitable[bool]]
) -> None:
    """짧은 기한으로 작업자를 돌리다가 `started`가 참이 되면 원천을 지우고, 작업자가 끝나기를
    기다린다. 끝나지 않으면 기한에서 빨갛게 끝난다."""
    worker = asyncio.create_task(_drain(pipeline, lease=SHORT_LEASE_SECONDS))
    try:
        await _wait_until(started)
        await _delete(pipeline, source)
        async with asyncio.timeout(DEADLINE_SECONDS):
            await worker
    finally:
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


async def test_지운_원천의_동기화는_커넥터를_부르지_않고_source_deleted로_끝난다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("공유", {"규정.docx": _docx()})
    source = await _make_source(pipeline, "공유")
    requested = await _request(pipeline, source)
    # 요청은 받은 뒤이고 작업자가 꺼내기 전에 지움 표시가 선 경우다(표시만 쓰고 대기 작업은 둔다).
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.mark_source_deleted(source.id, NOW)

    await _drain(pipeline)

    record = await _record(pipeline, requested)
    assert (record.status, record.failure_code) == (SyncRecordStatus.FAILED, "source_deleted")
    assert await _sync_jobs(pipeline, source) == [("failed", "source_deleted", 1)]
    assert (plan.list_calls, plan.fetch_calls) == (0, 0)
    assert await _document_keys(pipeline, source) == []


async def test_대기_중인_동기화는_원천을_지울_때_작업이_지워지고_기록이_닫힌다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("공유", {"규정.docx": _docx()})
    source = await _make_source(pipeline, "공유")
    requested = await _request(pipeline, source)

    await _delete(pipeline, source)

    record = await _record(pipeline, requested)
    assert (record.status, record.failure_code) == (SyncRecordStatus.FAILED, "source_deleted")
    assert record.job_id is None
    assert await _sync_jobs(pipeline, source) == []
    await _drain(pipeline)
    assert plan.list_calls == 0


async def test_파일을_읽는_중에_원천을_지우면_그_문서를_넣지_않고_source_deleted로_끝난다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("공유", {"가.docx": _docx("가"), "나.docx": _docx("나")})
    source = await _make_source(pipeline, "공유")

    async def delete_source_now() -> None:
        await _delete(pipeline, source)

    plan.on_fetch = delete_source_now
    requested = await _request(pipeline, source)

    await _drain(pipeline)

    record = await _record(pipeline, requested)
    assert (record.status, record.failure_code) == (SyncRecordStatus.FAILED, "source_deleted")
    assert await _sync_jobs(pipeline, source) == [("failed", "source_deleted", 1)]
    assert plan.fetch_calls == 1
    assert await _document_keys(pipeline, source) == []


async def test_끝없이_항목을_내는_목록도_원천을_지우면_기한을_늘릴_때_멈춘다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("끝없음", endless_cap=1_000_000)
    source = await _make_source(pipeline, "끝없음")
    requested = await _request(pipeline, source)

    async def listing() -> bool:
        return plan.list_calls == 1

    await _run_and_delete_when(pipeline, source, listing)

    record = await _record(pipeline, requested)
    assert (record.status, record.failure_code) == (SyncRecordStatus.FAILED, "source_deleted")
    # 그 시도를 버리지 않고 닫았다. 재시도 없이 한 번 돌고 `failed`다.
    assert await _sync_jobs(pipeline, source) == [("failed", "source_deleted", 1)]


async def test_파일_하나를_읽다가_멈춘_동기화도_원천을_지우면_기한을_늘릴_때_멈춘다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("멈춤", {"가.docx": _docx()}, fetch_ok=0)
    source = await _make_source(pipeline, "멈춤")
    requested = await _request(pipeline, source)

    async def reading() -> bool:
        return plan.fetch_calls == 1

    await _run_and_delete_when(pipeline, source, reading)

    record = await _record(pipeline, requested)
    assert (record.status, record.failure_code) == (SyncRecordStatus.FAILED, "source_deleted")
    assert await _sync_jobs(pipeline, source) == [("failed", "source_deleted", 1)]
    assert await _document_keys(pipeline, source) == []


async def test_원천을_지우면_다음_실행_시각이_비워진다(pipeline: Pipeline, world: World) -> None:
    world.plan("일정", {})
    source = await _make_source(pipeline, "일정")
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE sources SET next_run_at = :now WHERE id = :source"),
            {"now": NOW, "source": source.id},
        )

    await _delete(pipeline, source)

    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text("SELECT next_run_at FROM sources WHERE id = :source"), {"source": source.id}
        )
        assert rows.scalar_one() is None


async def _push_source(pipeline: Pipeline, name: str) -> Source:
    source = Source(new_id(), name, SourceKind.PUSH, NOW)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(source)
    return source


async def _ingest_into(pipeline: Pipeline, source: Source, key: str) -> None:
    await ingest_document(
        pipeline.unit_of_work,
        pipeline.blob_store,
        IngestRequest(
            filename=key,
            data=_docx(key),
            key=None,
            group=None,
            metadata={},
            updated_at=None,
            source=source.name,
        ),
        request_id=new_id(),
        now=pipeline.clock[0],
        max_upload_bytes=MAX_UPLOAD_BYTES,
    )


async def _deleted_counts(pipeline: Pipeline, source: Source) -> tuple[int, int, int]:
    """(문서 수, 지운 문서 수, 원천과 함께 지웠다는 표시가 선 문서 수)."""
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                "SELECT count(*), count(deleted_at), count(*) FILTER (WHERE deleted_with_source)"
                " FROM documents WHERE source_id = :source"
            ),
            {"source": source.id},
        )
        total, deleted, with_source = rows.one()
    return total, deleted, with_source


async def test_원천_삭제_작업은_묶음_크기를_넘는_문서도_모두_삭제_보관함으로_옮긴다(
    pipeline: Pipeline,
) -> None:
    source = await _push_source(pipeline, "묶음")
    total = BATCH_SIZE + 5
    for number in range(total):
        await _ingest_into(pipeline, source, f"문서{number}.docx")
    await _delete(pipeline, source)

    await _drain(pipeline)

    assert await _deleted_counts(pipeline, source) == (total, total, total)


async def test_지움_표시가_걷힌_원천에_직접_넣은_삭제_작업은_문서를_지우지_않고_성공으로_끝난다(
    pipeline: Pipeline,
) -> None:
    source = await _push_source(pipeline, "되살림")
    await _ingest_into(pipeline, source, "규정.docx")
    async with pipeline.unit_of_work.begin() as transaction:
        queued = await transaction.jobs.enqueue_source_job(
            JobKind.DELETE_SOURCE, source.id, {}, new_id(), NOW
        )
    assert queued is not None

    await _drain(pipeline)

    assert await _deleted_counts(pipeline, source) == (1, 0, 0)
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text("SELECT status FROM jobs WHERE id = :job"), {"job": queued.id}
        )
        assert rows.scalar_one() == "succeeded"


async def test_삭제_요청이_먼저_잡은_원천에_수집이_겹치면_수집은_기다렸다_409로_끝난다(
    pipeline: Pipeline,
) -> None:
    source = await _push_source(pipeline, "겹침")
    async with pipeline.unit_of_work.begin() as transaction:
        locked = await transaction.catalog.lock_source(source.id)
        assert locked is not None
        await transaction.catalog.mark_source_deleted(source.id, NOW)
        # 삭제 요청의 작업 단위가 아직 커밋하지 않았다. 이때 온 수집은 원천 행을 기다린다.
        crossing = asyncio.create_task(_ingest_into(pipeline, source, "늦은.docx"))
        await asyncio.sleep(0.3)
        assert not crossing.done()

    async with asyncio.timeout(DEADLINE_SECONDS):
        with pytest.raises(RequestError) as refused:
            await crossing
    assert refused.value.code is ErrorCode.SOURCE_DELETED
    assert await _deleted_counts(pipeline, source) == (0, 0, 0)


async def test_수집이_먼저_잡은_원천에_삭제_요청이_겹치면_요청은_기다렸다_수집_뒤에_끝난다(
    pipeline: Pipeline,
) -> None:
    source = await _push_source(pipeline, "겹침")
    async with pipeline.unit_of_work.begin() as transaction:
        await lock_live_source(transaction, source.id)
        # 수집의 작업 단위가 아직 커밋하지 않았다. 이때 온 삭제 요청은 원천 행을 기다린다.
        crossing = asyncio.create_task(_delete(pipeline, source))
        await asyncio.sleep(0.3)
        assert not crossing.done()

    async with asyncio.timeout(DEADLINE_SECONDS):
        await crossing
    await _drain(pipeline)
    # 지움 표시가 선 뒤에는 수집이 409이고, 지운 원천에 살아 있는 문서가 남지 않는다.
    with pytest.raises(RequestError) as refused:
        await _ingest_into(pipeline, source, "늦은.docx")
    assert refused.value.code is ErrorCode.SOURCE_DELETED
    assert await _deleted_counts(pipeline, source) == (0, 0, 0)
