"""원천 되살리기 작업과 동기화(source-sync 티켓 12, 명세 "원천 삭제와 되살리기"와 "동기화의 차례").

실제 테스트 PostgreSQL과 실제 작업자 루프를 쓴다. 가져오는 원천의 폴더는
`tests/support/hanging_connectors.py`의 계획이 움직이는 커넥터다. 시험이 보는 것은 원천 되살리기
작업이 문서를 50건씩 되살리는가, 지움 표시가 선 원천에는 아무것도 되살리지 않는가, 원천 삭제
작업이 실패로 끝난 원천에서 멈춘 문서가 다시 이어지는가, 되살린 원천의 동기화가 아직 되살리지
않은 문서를 어떻게 다루는가다.
"""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from importlib.metadata import EntryPoint
from uuid import UUID

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
from rag_engine.app.delete_source import request_source_deletion
from rag_engine.app.ingest import IngestRequest, ingest_document
from rag_engine.app.restore_source import BATCH_SIZE, request_source_restoration
from rag_engine.app.sync_requests import SyncRequested, request_sync
from rag_engine.domain.entities import (
    IndexStateStatus,
    JobKind,
    Source,
    SourceKind,
    SyncRecord,
    SyncRecordStatus,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import run_once

ENTRY = EntryPoint(
    name="planned",
    value="tests.support.hanging_connectors:create_planned",
    group=CONNECTOR_ENTRY_POINT_GROUP,
)
RETENTION_DAYS = 30


@pytest.fixture
async def world() -> AsyncIterator[World]:
    built = World()
    try:
        yield built
    finally:
        await built.close()


def _docx(title: str = "규정") -> bytes:
    return docx_bytes(title, "휴가는 연차로 쓴다.")


async def _drain_all(pipeline: Pipeline) -> None:
    """꺼낼 작업이 없을 때까지 작업자를 돌린다."""
    registry = EntryPointConnectorRegistry(lambda: [ENTRY])
    while (
        await run_once(
            pipeline.deps(connectors=registry), worker_id="worker-restore", lease_seconds=600.0
        )
        > 0
    ):
        pass


async def _drain_one(pipeline: Pipeline) -> None:
    registry = EntryPointConnectorRegistry(lambda: [ENTRY])
    await run_once(
        pipeline.deps(connectors=registry), worker_id="worker-restore", lease_seconds=600.0
    )


async def _push_source(pipeline: Pipeline, name: str) -> Source:
    source = Source(new_id(), name, SourceKind.PUSH, NOW)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(source)
    return source


async def _pull_source(pipeline: Pipeline, folder: str) -> Source:
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


async def _delete(pipeline: Pipeline, source: Source) -> None:
    await request_source_deletion(
        pipeline.unit_of_work, source.name, request_id=new_id(), now=pipeline.clock[0]
    )


async def _restore(pipeline: Pipeline, source: Source) -> UUID:
    requested = await request_source_restoration(
        pipeline.unit_of_work,
        source.name,
        request_id=new_id(),
        now=pipeline.clock[0],
        retention_days=RETENTION_DAYS,
    )
    return requested.job_id


async def _counts(pipeline: Pipeline, source: Source) -> tuple[int, int, int]:
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


async def _marks(pipeline: Pipeline, source: Source) -> dict[str, tuple[bool, bool]]:
    """키마다 (지웠는가, 원천과 함께 지웠다는 표시가 섰는가)."""
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                "SELECT key, deleted_at IS NOT NULL, deleted_with_source FROM documents"
                " WHERE source_id = :source"
            ),
            {"source": source.id},
        )
        return {row[0]: (row[1], row[2]) for row in rows}


async def _job_status(pipeline: Pipeline, job_id: UUID) -> str:
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text("SELECT status FROM jobs WHERE id = :job"), {"job": job_id}
        )
        status: str = rows.scalar_one()
        return status


async def _request_sync(pipeline: Pipeline, source: Source) -> SyncRequested:
    return await request_sync(
        pipeline.unit_of_work,
        source.name,
        apply_empty=False,
        reread=False,
        request_id=new_id(),
        now=pipeline.clock[0],
    )


async def _record(pipeline: Pipeline, requested: SyncRequested) -> SyncRecord:
    async with pipeline.unit_of_work.begin() as transaction:
        record = await transaction.sync_records.get(requested.sync_record_id)
    assert record is not None
    return record


async def _postpone_restore_job(pipeline: Pipeline) -> None:
    """원천 되살리기 작업을 뒤로 미룬다. 되살린 원천의 동기화를 그 작업보다 먼저 돌리게 한다."""
    await _set_restore_run_after(pipeline, NOW + timedelta(hours=1))


async def _release_restore_job(pipeline: Pipeline) -> None:
    await _set_restore_run_after(pipeline, NOW)


async def _set_restore_run_after(pipeline: Pipeline, moment: datetime) -> None:
    """작업자는 파이프라인의 시계(`NOW`)로 꺼내므로 실제 시각이 아니라 그 시계로 맞춘다."""
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE jobs SET run_after = :moment WHERE kind = 'restore_source'"),
            {"moment": moment},
        )


async def test_원천_되살리기_작업은_묶음_크기를_넘는_문서도_모두_되살린다(
    pipeline: Pipeline,
) -> None:
    source = await _push_source(pipeline, "묶음")
    total = BATCH_SIZE + 5
    for number in range(total):
        await _ingest_into(pipeline, source, f"문서{number}.docx")
    await _delete(pipeline, source)
    await _drain_one(pipeline)
    assert await _counts(pipeline, source) == (total, total, total)

    job_id = await _restore(pipeline, source)
    await _drain_one(pipeline)

    assert await _job_status(pipeline, job_id) == "succeeded"
    assert await _counts(pipeline, source) == (total, 0, 0)


async def test_지움_표시가_선_원천에_직접_넣은_되살리기_작업은_문서를_되살리지_않고_끝난다(
    pipeline: Pipeline,
) -> None:
    source = await _push_source(pipeline, "직접")
    await _ingest_into(pipeline, source, "규정.docx")
    await _delete(pipeline, source)
    await _drain_one(pipeline)
    async with pipeline.unit_of_work.begin() as transaction:
        queued = await transaction.jobs.enqueue_source_job(
            JobKind.RESTORE_SOURCE, source.id, {}, new_id(), NOW
        )
    assert queued is not None

    await _drain_one(pipeline)

    assert await _job_status(pipeline, queued.id) == "succeeded"
    assert await _counts(pipeline, source) == (1, 1, 1)


async def test_원천_삭제_작업이_실패로_끝난_원천을_되살리면_멈춘_문서가_색인되어_검색에_나온다(
    pipeline: Pipeline,
) -> None:
    source = await _push_source(pipeline, "멈춤")
    await _ingest_into(pipeline, source, "규정.docx")
    # 원천 삭제 작업이 재시도를 다 쓰고 실패로 끝난 원천이다. 지움 표시만 서 있고 문서는 그대로다.
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.mark_source_deleted(source.id, NOW)
    # 색인 작업이 지움 표시를 보고 아무것도 쓰지 않고 끝난다.
    await _drain_all(pipeline)
    async with pipeline.engine.connect() as connection:
        document_id = (
            await connection.execute(
                sa.text("SELECT id FROM documents WHERE source_id = :source"),
                {"source": source.id},
            )
        ).scalar_one()
    assert await pipeline.states(document_id) == {}

    await _restore(pipeline, source)
    await _drain_all(pipeline)

    states = await pipeline.states(document_id)
    assert [state.status for state in states.values()] == [IndexStateStatus.INDEXED]
    assert await _counts(pipeline, source) == (1, 0, 0)


async def test_되살린_원천의_동기화는_폴더에서_사라진_문서를_되살리지_않고_따로_지운_문서로_센다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("공유", {"가.docx": _docx("가"), "나.docx": _docx("나")})
    source = await _pull_source(pipeline, "공유")
    await _request_sync(pipeline, source)
    await _drain_all(pipeline)
    assert await _counts(pipeline, source) == (2, 0, 0)
    await _delete(pipeline, source)
    await _drain_one(pipeline)
    assert await _counts(pipeline, source) == (2, 2, 2)
    await _restore(pipeline, source)
    await _postpone_restore_job(pipeline)
    del plan.files["가.docx"]
    requested = await _request_sync(pipeline, source)

    await _drain_one(pipeline)

    record = await _record(pipeline, requested)
    assert (record.status, record.deleted) == (SyncRecordStatus.SUCCEEDED, 1)
    # 폴더에 남은 나.docx는 동기화가 읽으면서 코어의 되살림으로 되살리고 표시도 걷는다.
    assert await _marks(pipeline, source) == {"가.docx": (True, False), "나.docx": (False, False)}
    await _release_restore_job(pipeline)
    await _drain_one(pipeline)
    # 원천 되살리기 작업은 따로 지운 가.docx를 되살리지 않는다.
    assert await _marks(pipeline, source) == {"가.docx": (True, False), "나.docx": (False, False)}


async def test_폴더를_비운_되살린_원천의_동기화는_실패하고_표시가_남아_작업_뒤_문서가_돌아온다(
    pipeline: Pipeline, world: World
) -> None:
    plan = world.plan("비움", {"가.docx": _docx("가"), "나.docx": _docx("나")})
    source = await _pull_source(pipeline, "비움")
    await _request_sync(pipeline, source)
    await _drain_all(pipeline)
    await _delete(pipeline, source)
    await _drain_one(pipeline)
    await _restore(pipeline, source)
    await _postpone_restore_job(pipeline)
    plan.files.clear()
    requested = await _request_sync(pipeline, source)

    await _drain_one(pipeline)

    record = await _record(pipeline, requested)
    assert (record.status, record.failure_code) == (SyncRecordStatus.FAILED, "source_unreadable")
    assert await _marks(pipeline, source) == {"가.docx": (True, True), "나.docx": (True, True)}
    await _release_restore_job(pipeline)
    await _drain_one(pipeline)
    assert await _counts(pipeline, source) == (2, 0, 0)
