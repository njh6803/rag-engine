"""동기화의 삭제 반영과 빈 목록 보호(source-sync 티켓 08, 명세 "동기화의 차례"와 "수집 정책").

실제 테스트 PostgreSQL과 실제 작업자 루프를 쓰고 원천의 폴더만 대본대로 움직이는 가짜
(`tests/support/scripted_connectors.py`)로 둔다. 문서가 검색에서 빠졌는지는 삭제 표시와 조각 표로
본다(검색 도구로 보는 왕복은 `tests/server/test_sync_deletes_round_trip.py`가 맡는다).
"""

from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import Pipeline
from tests.support.scripted_connectors import ScriptedFile, ScriptedFolder, ScriptedRegistry
from tests.support.sync_world import make_pull_source, run_sync

from rag_engine.adapters.postgres.document_store import PostgresDocumentStore
from rag_engine.adapters.postgres.unit_of_work import PostgresTransaction, PostgresUnitOfWork
from rag_engine.app.delete_document import delete_locked_document
from rag_engine.domain.connectors import ConnectorError, ConnectorFailureReason
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    Source,
    SyncRecord,
    SyncRecordStatus,
)
from rag_engine.domain.errors import ErrorCode


async def _document(pipeline: Pipeline, source: Source, key: str) -> Document:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get_by_key(source.id, key)
    assert document is not None
    return document


def _docx(title: str) -> bytes:
    return docx_bytes(title, f"{title}의 본문이다.")


def _folder_with(*keys: str) -> ScriptedFolder:
    folder = ScriptedFolder()
    for key in keys:
        folder.put(key, _docx(key), "m1")
    return folder


def _counts(record: SyncRecord) -> Mapping[str, object]:
    return {
        "listed": record.listed,
        "added": record.added,
        "updated": record.updated,
        "deleted": record.deleted,
        "unchanged": record.unchanged,
        "not_accepted": dict(record.not_accepted),
        "failed": dict(record.failed),
    }


async def _seed(pipeline: Pipeline, *keys: str) -> tuple[Source, ScriptedFolder, ScriptedRegistry]:
    """원천을 만들고 그 폴더의 파일을 모두 색인한 상태로 둔다."""
    source = await make_pull_source(pipeline)
    folder = _folder_with(*keys)
    registry = ScriptedRegistry(folder)
    first = await run_sync(pipeline, source, registry)
    assert first.status is SyncRecordStatus.SUCCEEDED
    return source, folder, registry


async def _is_searchable(pipeline: Pipeline, source: Source, key: str) -> bool:
    """문서가 지워지지 않았고 현재 판에 조각이 있으면 검색에 나온다."""
    document = await _document(pipeline, source, key)
    return document.deleted_at is None and bool(await pipeline.chunk_texts(document.id))


async def test_폴더에서_지운_파일의_문서는_다음_동기화_뒤_검색에서_빠진다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    removed = await _document(pipeline, source, "규정.docx")
    del folder.files["규정.docx"]

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert _counts(record) == {
        "listed": 1,
        "added": 0,
        "updated": 0,
        "deleted": 1,
        "unchanged": 1,
        "not_accepted": {},
        "failed": {},
    }
    after = await _document(pipeline, source, "규정.docx")
    assert after.deleted_at is not None
    assert after.generation == removed.generation + 1
    assert await pipeline.chunk_texts(after.id) == []
    assert await pipeline.archived_texts(after.id)
    assert await _is_searchable(pipeline, source, "지침.docx")


async def test_삭제_반영은_임베딩_서버가_답하지_않아도_같은_동기화가_넣은_문서를_기다리지_않는다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    pipeline.stub.fail("/v1/embeddings", 503)
    del folder.files["규정.docx"]
    folder.put("새.docx", _docx("새"), "m1")

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.added, record.deleted) == (1, 1)
    assert (await _document(pipeline, source, "규정.docx")).deleted_at is not None
    added = await _document(pipeline, source, "새.docx")
    assert added.deleted_at is None
    assert await pipeline.chunk_texts(added.id) == []


async def test_지운_파일이_다시_생기면_다음_동기화가_그_문서를_되살린다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    kept = folder.files["규정.docx"]
    del folder.files["규정.docx"]
    await run_sync(pipeline, source, registry)
    folder.files["규정.docx"] = kept

    record = await run_sync(pipeline, source, registry)

    assert (record.added, record.deleted) == (1, 0)
    assert await _is_searchable(pipeline, source, "규정.docx")


async def test_이미_지운_문서는_다시_지우지도_세지도_않는다(pipeline: Pipeline) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    del folder.files["규정.docx"]
    await run_sync(pipeline, source, registry)
    before = await _document(pipeline, source, "규정.docx")

    record = await run_sync(pipeline, source, registry)

    assert record.deleted == 0
    after = await _document(pipeline, source, "규정.docx")
    assert (after.generation, after.deleted_at) == (before.generation, before.deleted_at)


async def _nothing() -> None:
    return None


class _InterruptedDocumentStore(PostgresDocumentStore):
    """지워지지 않은 문서의 키를 읽어 낸 직후, 한 번만 다른 작업이 끼어들게 한다."""

    def __init__(
        self, connection: AsyncConnection, interloper: Callable[[], Awaitable[None]]
    ) -> None:
        super().__init__(connection)
        self._interloper = interloper

    async def list_held_keys_of_source(self, source_id: UUID) -> dict[str, UUID]:
        keys = await super().list_held_keys_of_source(source_id)
        interloper, self._interloper = self._interloper, _nothing
        await interloper()
        return keys


class _InterruptedUnitOfWork(PostgresUnitOfWork):
    def __init__(self, pipeline: Pipeline, interloper: Callable[[], Awaitable[None]]) -> None:
        super().__init__(pipeline.engine)
        self._interloper = interloper

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[PostgresTransaction]:
        async with self._engine.connect() as connection, connection.begin():
            transaction = PostgresTransaction(connection)
            transaction.documents = _InterruptedDocumentStore(connection, self._interloper)
            yield transaction


async def test_지울_문서를_잠그기_전에_다른_작업이_먼저_지웠으면_다시_지우지도_세지도_않는다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    removed = await _document(pipeline, source, "규정.docx")
    del folder.files["규정.docx"]

    async def delete_first() -> None:
        async with pipeline.unit_of_work.begin() as transaction:
            locked = await transaction.documents.lock(removed.id)
            assert locked is not None
            await delete_locked_document(transaction, locked, pipeline.clock[0])

    record = await run_sync(
        pipeline, source, registry, unit_of_work=_InterruptedUnitOfWork(pipeline, delete_first)
    )

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert record.deleted == 0
    after = await _document(pipeline, source, "규정.docx")
    assert after.deleted_at is not None
    assert after.generation == removed.generation + 1


async def test_제외_패턴을_더하면_그_패턴에_맞는_문서가_검색에서_빠지고_나머지는_남는다(
    pipeline: Pipeline,
) -> None:
    source, _, registry = await _seed(pipeline, "초안/메모.docx", "규정.docx")
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.update_pull_source(
            source.id, config=None, exclude_patterns=["초안"]
        )

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.deleted, record.unchanged) == (1, 1)
    assert record.not_accepted == {"excluded": 1}
    assert (await _document(pipeline, source, "초안/메모.docx")).deleted_at is not None
    assert await _is_searchable(pipeline, source, "규정.docx")


async def test_읽지_못해_실패로_센_파일의_문서는_지우지_않는다(pipeline: Pipeline) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    folder.put("지침.docx", _docx("지침 고침"), "m2")
    folder.fetch_errors["지침.docx"] = ConnectorError(ConnectorFailureReason.UNREADABLE)

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.deleted, record.failed) == (0, {ErrorCode.SOURCE_UNREADABLE.value: 1})
    assert await _is_searchable(pipeline, source, "지침.docx")


async def test_읽다가_너무_크다고_알린_파일의_문서는_지우고_정책에_걸린_것으로_센다(
    pipeline: Pipeline,
) -> None:
    """목록은 크기를 비워 내고 읽을 때 `too_large`를 낸다. 읽지 못해 문서를 그대로 두는 파일이
    아니라 수집 정책에 걸린 파일이다(명세 "수집 정책")."""
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    folder.files["지침.docx"] = ScriptedFile(_docx("지침"), "m2", None)
    folder.fetch_errors["지침.docx"] = ConnectorError(ConnectorFailureReason.TOO_LARGE)

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert _counts(record) == {
        "listed": 2,
        "added": 0,
        "updated": 0,
        "deleted": 1,
        "unchanged": 1,
        "not_accepted": {"too_large": 1},
        "failed": {},
    }
    assert (await _document(pipeline, source, "지침.docx")).deleted_at is not None
    assert await _is_searchable(pipeline, source, "규정.docx")


async def test_읽은_바이트가_상한을_넘는_파일의_문서도_지운다(pipeline: Pipeline) -> None:
    """목록은 작다고 했는데 읽어 보니 상한을 넘는다. 커넥터가 상한을 지키지 않은 경우다."""
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    kept = folder.files["규정.docx"].data
    folder.files["지침.docx"] = ScriptedFile(kept + b"\0" * 5000, "m2", 1)

    record = await run_sync(pipeline, source, registry, max_upload_bytes=len(kept) + 1)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.deleted, record.unchanged, record.not_accepted) == (1, 1, {"too_large": 1})
    assert (await _document(pipeline, source, "지침.docx")).deleted_at is not None
    assert await _is_searchable(pipeline, source, "규정.docx")


async def test_문서가_하나뿐인_원천에서_그_파일이_읽을_때_너무_크면_실패하고_문서는_그대로다(
    pipeline: Pipeline,
) -> None:
    """삭제 반영을 시작하기 직전의 판정이 잡는 장면이다. 후보가 읽다가 모두 빠졌다."""
    source, folder, registry = await _seed(pipeline, "규정.docx")
    folder.files["규정.docx"] = ScriptedFile(_docx("규정"), "m2", None)
    folder.fetch_errors["규정.docx"] = ConnectorError(ConnectorFailureReason.TOO_LARGE)

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.NOTHING_ACCEPTED.value
    assert (record.listed, record.deleted, record.not_accepted) == (1, 0, {"too_large": 1})
    assert await _is_searchable(pipeline, source, "규정.docx")


async def test_폴더가_비면_아무것도_지우지_않고_source_unreadable로_실패한다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    folder.files.clear()

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert (record.listed, record.deleted) == (0, 0)
    assert await _is_searchable(pipeline, source, "규정.docx")
    assert await _is_searchable(pipeline, source, "지침.docx")


async def test_폴더를_읽지_못하면_목록_건수가_비고_문서는_그대로다(pipeline: Pipeline) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx")
    folder.list_error = ConnectorError(ConnectorFailureReason.UNREADABLE)

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert record.listed is None
    assert await _is_searchable(pipeline, source, "규정.docx")


async def test_빈_목록도_반영을_켜면_빈_폴더의_문서를_모두_지우고_성공으로_끝난다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    folder.files.clear()

    record = await run_sync(pipeline, source, registry, apply_empty=True)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.listed, record.deleted) == (0, 2)
    assert (await _document(pipeline, source, "규정.docx")).deleted_at is not None
    assert (await _document(pipeline, source, "지침.docx")).deleted_at is not None
    assert record.options == {"apply_empty": True}


async def test_빈_목록도_반영을_켜도_폴더를_읽지_못하면_실패하고_문서는_그대로다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx")
    folder.list_error = ConnectorError(ConnectorFailureReason.UNREADABLE)

    record = await run_sync(pipeline, source, registry, apply_empty=True)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.SOURCE_UNREADABLE.value
    assert await _is_searchable(pipeline, source, "규정.docx")


async def test_문서_파일을_모두_치우고_걸릴_파일만_두면_nothing_accepted로_실패한다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    folder.files.clear()
    folder.put(".숨김.docx", _docx("숨김"), "m1")
    folder.put("메모.txt", b"text", "m1")

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.NOTHING_ACCEPTED.value
    assert _counts(record) == {
        "listed": 2,
        "added": 0,
        "updated": 0,
        "deleted": 0,
        "unchanged": 0,
        "not_accepted": {"excluded": 1, "unsupported_type": 1},
        "failed": {},
    }
    assert await _is_searchable(pipeline, source, "규정.docx")
    assert await _is_searchable(pipeline, source, "지침.docx")


async def test_빈_목록도_반영을_켜면_걸릴_파일만_남은_원천의_문서가_빠지고_다음은_실패가_아니다(
    pipeline: Pipeline,
) -> None:
    source, folder, registry = await _seed(pipeline, "규정.docx", "지침.docx")
    folder.files.clear()
    folder.put(".숨김.docx", _docx("숨김"), "m1")
    folder.put("메모.txt", b"text", "m1")

    forced = await run_sync(pipeline, source, registry, apply_empty=True)
    later = await run_sync(pipeline, source, registry)

    assert forced.status is SyncRecordStatus.SUCCEEDED
    assert (forced.deleted, forced.not_accepted) == (
        2,
        {"excluded": 1, "unsupported_type": 1},
    )
    assert (await _document(pipeline, source, "규정.docx")).deleted_at is not None
    assert later.status is SyncRecordStatus.SUCCEEDED
    assert later.deleted == 0


async def test_문서가_하나도_없는_원천은_모든_파일이_걸려도_실패하지_않는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put(".숨김.docx", _docx("숨김"), "m1")
    folder.put("메모.txt", b"text", "m1")

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert record.not_accepted == {"excluded": 1, "unsupported_type": 1}


async def test_문서도_파일도_없는_원천의_동기화는_성공이다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)

    record = await run_sync(pipeline, source, ScriptedRegistry(ScriptedFolder()))

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.listed, record.deleted) == (0, 0)


async def test_이미_지워진_문서만_남은_원천은_폴더가_비어도_실패하지_않는다(
    pipeline: Pipeline,
) -> None:
    """지워지지 않은 문서가 없으면 지울 것도 보호할 것도 없다."""
    source, folder, registry = await _seed(pipeline, "규정.docx")
    folder.files.clear()
    forced = await run_sync(pipeline, source, registry, apply_empty=True)
    assert forced.status is SyncRecordStatus.SUCCEEDED
    assert (await _document(pipeline, source, "규정.docx")).deleted_at is not None

    record = await run_sync(pipeline, source, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.listed, record.deleted) == (0, 0)


async def test_원천과_함께_지워졌다는_표시가_남은_문서도_있는_문서로_세어_빈_폴더를_실패로_닫는다(
    pipeline: Pipeline,
) -> None:
    """원천을 되살린 뒤 원천 되살리기 작업이 아직 되살리지 않은 문서는 지워진 채 표시만 남는다."""
    source, folder, registry = await _seed(pipeline, "규정.docx")
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text(
                "UPDATE documents SET deleted_at = now(), deleted_with_source = true"
                " WHERE source_id = :source_id"
            ),
            {"source_id": source.id},
        )
    folder.files.clear()

    record = await run_sync(pipeline, source, registry)

    assert (record.status, record.failure_code) == (SyncRecordStatus.FAILED, "source_unreadable")
    assert record.deleted == 0


async def test_색인_전에_파일이_지워져_source_changed로_실패한_문서는_다음_동기화가_지운다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = _folder_with("규정.docx", "지침.docx")
    seen: set[str] = set()

    def remove_before_index(key: str) -> None:
        # 동기화가 읽을 때(첫 읽기)는 그대로 두고 색인 작업이 읽는 순간에 파일을 지운다.
        if key == "규정.docx" and key in seen:
            folder.files.pop(key, None)
        seen.add(key)

    folder.on_fetch = remove_before_index
    registry = ScriptedRegistry(folder)
    first = await run_sync(pipeline, source, registry)
    broken = await _document(pipeline, source, "규정.docx")
    assert first.status is SyncRecordStatus.SUCCEEDED
    assert (broken.status, broken.error_code) == (DocumentStatus.FAILED, ErrorCode.SOURCE_CHANGED)

    second = await run_sync(pipeline, source, registry)

    assert second.deleted == 1
    assert (await _document(pipeline, source, "규정.docx")).deleted_at is not None
    assert await _is_searchable(pipeline, source, "지침.docx")
