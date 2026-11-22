"""가져오는 원천의 동기화가 새 파일과 바뀐 파일을 넣는 길(source-sync 티켓 07).

실제 테스트 PostgreSQL과 실제 작업자 루프(`run_once`)를 쓰고, 원천의 폴더만 대본대로 움직이는
가짜(`tests/support/scripted_connectors.py`)로 둔다. 동기화 작업이 문서를 넣으면 그 색인 작업이
같은 루프에서 이어 돌아, 문서가 `parsed`가 되고 조각이 생기는 데까지 본다.
"""

from collections.abc import Callable, Mapping
from datetime import timedelta

import pytest
import sqlalchemy as sa
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import LEASE_SECONDS, Pipeline
from tests.support.scripted_connectors import ScriptedFolder, ScriptedRegistry
from tests.support.sync_world import make_pull_source, run_sync

from rag_engine.app.job_failure import exhaust
from rag_engine.app.sync_requests import request_sync
from rag_engine.domain.connectors import ConnectorError, ConnectorFailureReason
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    JobStatus,
    Source,
    SyncRecord,
    SyncRecordStatus,
)
from rag_engine.domain.errors import AttemptLostError, ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import run_once


async def _document(pipeline: Pipeline, source: Source, key: str) -> Document:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get_by_key(source.id, key)
    assert document is not None
    return document


def _docx(title: str, text: str = "본문이다.") -> bytes:
    return docx_bytes(title, text)


def _counts(record: SyncRecord) -> Mapping[str, object]:
    return {
        "listed": record.listed,
        "added": record.added,
        "updated": record.updated,
        "unchanged": record.unchanged,
        "not_accepted": dict(record.not_accepted),
        "failed": dict(record.failed),
    }


async def test_새_파일은_더해지고_정책에_걸린_파일은_사유별로_센다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline, exclude_patterns=("초안",))
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")
    folder.put("하위/지침.docx", _docx("지침"), "m1")
    folder.put(".숨김.docx", _docx("숨김"), "m1")
    folder.put("초안/메모.docx", _docx("메모"), "m1")
    folder.put("메모.txt", b"text", "m1")

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert _counts(record) == {
        "listed": 5,
        "added": 2,
        "updated": 0,
        "unchanged": 0,
        "not_accepted": {"excluded": 2, "unsupported_type": 1},
        "failed": {},
    }
    document = await _document(pipeline, source, "하위/지침.docx")
    assert document.status is DocumentStatus.PARSED
    assert document.title == "지침"
    assert document.blob_path is None
    assert document.change_marker == "m1"
    assert await pipeline.chunk_texts(document.id)


async def test_넣은_색인_작업은_동기화_작업의_요청_ID를_잇는다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")

    await run_sync(pipeline, source, ScriptedRegistry(folder))

    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(sa.text("SELECT kind, request_id FROM jobs ORDER BY kind"))
        request_ids = {row[0]: row[1] for row in rows}
    assert set(request_ids) == {"index_document", "sync_source"}
    assert request_ids["index_document"] == request_ids["sync_source"]


async def test_바뀌지_않은_파일은_읽지_않고_그대로로_센다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")
    folder.put("지침.docx", _docx("지침"), "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    folder.fetches.clear()

    record = await run_sync(pipeline, source, registry)

    assert _counts(record) == {
        "listed": 2,
        "added": 0,
        "updated": 0,
        "unchanged": 2,
        "not_accepted": {},
        "failed": {},
    }
    assert folder.fetches == []


async def test_내용이_바뀐_파일은_고쳐_넣고_새_색인_작업이_돈다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정", "처음 내용이다."), "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    before = await _document(pipeline, source, "규정.docx")
    folder.put("규정.docx", _docx("규정", "고친 내용이다."), "m2")

    record = await run_sync(pipeline, source, registry)

    assert _counts(record) == {
        "listed": 1,
        "added": 0,
        "updated": 1,
        "unchanged": 0,
        "not_accepted": {},
        "failed": {},
    }
    after = await _document(pipeline, source, "규정.docx")
    assert after.id == before.id
    assert after.content_hash != before.content_hash
    assert after.change_marker == "m2"
    assert after.status is DocumentStatus.PARSED
    assert any("고친 내용" in text for text in await pipeline.chunk_texts(after.id))
    assert await pipeline.job_statuses(after.id) == [JobStatus.SUCCEEDED.value] * 2


async def test_변경_확인값만_바뀌고_내용이_같으면_값만_갱신하고_작업을_만들지_않는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    # python-docx는 파일에 생성 시각(초 단위)을 넣는다. 같은 내용이라는 전제는 바이트를 한 번만
    # 만들어 지킨다.
    same_bytes = _docx("규정")
    folder.put("규정.docx", same_bytes, "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    before = await _document(pipeline, source, "규정.docx")
    folder.put("규정.docx", same_bytes, "m2")

    record = await run_sync(pipeline, source, registry)

    after = await _document(pipeline, source, "규정.docx")
    assert _counts(record)["unchanged"] == 1
    assert _counts(record)["updated"] == 0
    assert after.change_marker == "m2"
    assert after.content_hash == before.content_hash
    assert after.generation == before.generation
    assert await pipeline.job_statuses(after.id) == [JobStatus.SUCCEEDED.value]


async def test_작업_담당_기록을_잃은_시도가_재시도_소진으로_끝내려_해도_동기화_기록은_바뀌지_않는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    await request_sync(
        pipeline.unit_of_work,
        source.name,
        apply_empty=False,
        reread=False,
        request_id=new_id(),
        now=pipeline.clock[0],
    )
    lost = await pipeline.claim("worker-a")
    await pipeline.claim("worker-b", later=3 * 24 * 3600.0)

    with pytest.raises(AttemptLostError):
        await exhaust(pipeline.deps(), lost, ErrorCode.INTERNAL_ERROR)

    async with pipeline.unit_of_work.begin() as transaction:
        record = await transaction.sync_records.get_by_job(lost.id)
        job = await transaction.jobs.get(lost.id)
    assert record is not None
    assert (record.status, record.failure_code) == (SyncRecordStatus.QUEUED, None)
    assert job is not None
    assert (job.status, job.worker_id) == (JobStatus.RUNNING, "worker-b")


async def test_목록을_받다_읽을_수_없으면_아무것도_넣지_않고_실패로_닫는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")
    folder.list_error = ConnectorError(ConnectorFailureReason.UNREADABLE)

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert record.listed is None
    async with pipeline.unit_of_work.begin() as transaction:
        assert await transaction.documents.get_by_key(source.id, "규정.docx") is None


async def test_같은_키를_두_번_내는_커넥터는_connector_error로_닫는다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder(repeat_first_key=True)
    folder.put("규정.docx", _docx("규정"), "m1")

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.CONNECTOR_ERROR.value
    async with pipeline.unit_of_work.begin() as transaction:
        assert await transaction.documents.get_by_key(source.id, "규정.docx") is None


async def test_커넥터를_만들_수_없으면_connector_unavailable로_닫는다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    registry = ScriptedRegistry(ScriptedFolder(), unavailable=True)

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.CONNECTOR_UNAVAILABLE.value
    assert record.listed is None


async def test_저장된_설정을_커넥터가_받지_않으면_connector_unavailable로_닫는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    registry = ScriptedRegistry(ScriptedFolder(), invalid_config=True)

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.CONNECTOR_UNAVAILABLE.value
    assert record.listed is None


async def _sync_then_change_before_index(
    pipeline: Pipeline, change: Callable[[ScriptedFolder, str], None]
) -> Document:
    """동기화가 읽은 직후까지는 그대로 두고, 색인 작업이 읽는 순간 `change`가 폴더를 바꾸게 한 뒤
    그 문서를 낸다."""
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")
    reads: list[str] = []

    def change_on_second_read(key: str) -> None:
        if reads:
            change(folder, key)
        reads.append(key)

    folder.on_fetch = change_on_second_read
    await run_sync(pipeline, source, ScriptedRegistry(folder))
    return await _document(pipeline, source, "규정.docx")


async def test_색인_작업이_읽을_때_파일이_없어졌으면_source_changed로_실패하고_확인값을_비운다(
    pipeline: Pipeline,
) -> None:
    def remove(folder: ScriptedFolder, key: str) -> None:
        del folder.files[key]

    document = await _sync_then_change_before_index(pipeline, remove)

    assert document.status is DocumentStatus.FAILED
    assert document.error_code is ErrorCode.SOURCE_CHANGED
    assert document.change_marker is None


async def test_색인_작업이_읽을_때_커넥터가_너무_크다고_답하면_source_changed로_실패한다(
    pipeline: Pipeline,
) -> None:
    def too_large(folder: ScriptedFolder, key: str) -> None:
        folder.fetch_errors[key] = ConnectorError(ConnectorFailureReason.TOO_LARGE)

    document = await _sync_then_change_before_index(pipeline, too_large)

    assert document.status is DocumentStatus.FAILED
    assert document.error_code is ErrorCode.SOURCE_CHANGED
    assert document.change_marker is None


async def test_색인_작업이_읽을_때_상한이_동기화_때보다_낮아졌으면_source_changed로_실패한다(
    pipeline: Pipeline,
) -> None:
    """운영자가 상한을 낮춰 다시 띄운 사이에 색인 작업이 도는 장면이다. 커넥터가 상한을 따로 지키지
    않아도 서버가 크기를 본다."""
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")
    reads: list[str] = []

    def fail_the_index_read(key: str) -> None:
        if reads:
            folder.fetch_errors[key] = ConnectorError(ConnectorFailureReason.UNREADABLE)
        reads.append(key)

    folder.on_fetch = fail_the_index_read
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    waiting = await _document(pipeline, source, "규정.docx")
    assert waiting.status is DocumentStatus.RECEIVED, f"받은 상태: {waiting.status.value}"

    folder.fetch_errors.clear()
    folder.on_fetch = None
    pipeline.clock[0] += timedelta(hours=2)
    await run_once(
        pipeline.deps(connectors=registry, max_upload_bytes=10),
        worker_id="worker-lower-limit",
        lease_seconds=LEASE_SECONDS,
    )

    document = await _document(pipeline, source, "규정.docx")
    assert document.status is DocumentStatus.FAILED, f"받은 상태: {document.status.value}"
    assert document.error_code is ErrorCode.SOURCE_CHANGED
    assert document.change_marker is None


async def test_커넥터가_너무_크다고_답한_파일은_정책에_걸린_것으로_센다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")
    folder.put("큰.docx", _docx("큰"), "m1")
    folder.fetch_errors["큰.docx"] = ConnectorError(ConnectorFailureReason.TOO_LARGE)

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert _counts(record)["added"] == 1
    assert record.not_accepted == {"too_large": 1}


async def test_읽지_못한_파일_하나는_실패로_세고_나머지는_넣는다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정"), "m1")
    folder.put("지침.docx", _docx("지침"), "m1")
    folder.fetch_errors["지침.docx"] = ConnectorError(ConnectorFailureReason.UNREADABLE)

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert _counts(record)["added"] == 1
    assert record.failed == {ErrorCode.SOURCE_UNREADABLE.value: 1}


async def test_목록_뒤_색인_전에_바뀐_파일은_source_changed로_실패하고_다음_동기화가_다시_넣는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", _docx("규정", "처음 내용이다."), "m1")
    registry = ScriptedRegistry(folder)
    swapped: list[str] = []

    def swap_after_sync_read(key: str) -> None:
        # 동기화가 읽은 직후(첫 읽기)는 그대로 두고, 색인 작업의 읽기에서 파일을 바꾼다.
        if swapped:
            folder.put(key, _docx("규정", "그사이 바뀐 내용이다."), "m2")
        swapped.append(key)

    folder.on_fetch = swap_after_sync_read
    first = await run_sync(pipeline, source, registry)
    broken = await _document(pipeline, source, "규정.docx")
    assert first.status is SyncRecordStatus.SUCCEEDED
    assert broken.status is DocumentStatus.FAILED
    assert broken.error_code is ErrorCode.SOURCE_CHANGED
    assert broken.change_marker is None
    folder.on_fetch = None

    second = await run_sync(pipeline, source, registry)

    fixed = await _document(pipeline, source, "규정.docx")
    assert _counts(second)["updated"] == 1
    assert fixed.status is DocumentStatus.PARSED
    assert fixed.change_marker == "m2"
