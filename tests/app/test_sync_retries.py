"""가져오는 원천의 동기화가 실패한 문서를 다시 시도시키고, "모두 다시 읽기"가 파일을 모두 읽는 길
(source-sync 티켓 09).

실제 테스트 PostgreSQL과 실제 작업자 루프(`run_once`)를 쓰고, 원천의 폴더만 대본대로 움직이는
가짜(`tests/support/scripted_connectors.py`)로 둔다. 임베딩 서버는 `TeiStub`이고 시험이 꺼 둔다.
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection
from tests.support.docx_files import docx_bytes
from tests.support.pdf_files import PdfPage, blank_pages_pdf, pdf_bytes, text_block
from tests.support.pipeline import BACKOFF_BASE_SECONDS, Pipeline
from tests.support.scripted_connectors import ScriptedFolder, ScriptedRegistry
from tests.support.sync_world import make_pull_source, run_sync

from rag_engine.adapters.parsers.runner import SubprocessParseRunner
from rag_engine.adapters.postgres.document_store import PostgresDocumentStore
from rag_engine.adapters.postgres.unit_of_work import PostgresTransaction, PostgresUnitOfWork
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IndexStateStatus,
    SkipReason,
    Source,
    SyncRecord,
)
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.parsing import ParsedDocument, ParserVersion

_ONE_ATTEMPT = RetryPolicy(max_attempts=1, backoff_base_seconds=BACKOFF_BASE_SECONDS)
_SUCCEEDED = "succeeded"
_FAILED = "failed"

# 일시 실패와 같게 다시 시도하는 코드(명세 "가져오는 원천의 문서 색인").
_RETRYABLE = [
    ErrorCode.EMBEDDING_UNAVAILABLE,
    ErrorCode.DATABASE_UNAVAILABLE,
    ErrorCode.BLOB_STORE_ERROR,
    ErrorCode.SOURCE_UNREADABLE,
    ErrorCode.WORKER_LOST,
    ErrorCode.SOURCE_CHANGED,
]
# 다시 넣는 집합 밖의 실패 코드. 보통 동기화는 다시 넣지 않고 "모두 다시 읽기"만 다시 넣는다.
_PERMANENT = [
    ErrorCode.PARSE_FAILED,
    ErrorCode.EMBEDDING_REJECTED,
    ErrorCode.DOCUMENT_TOO_LARGE,
    ErrorCode.INTERNAL_ERROR,
]


class _CountingRunner:
    """실제 실행기를 감싸 파싱 횟수를 센다."""

    def __init__(self, inner: SubprocessParseRunner) -> None:
        self._inner = inner
        self.parse_calls = 0

    def current_version(self, mime: str) -> ParserVersion | None:
        return self._inner.current_version(mime)

    async def parse(self, data: bytes, mime: str) -> ParsedDocument:
        self.parse_calls += 1
        return await self._inner.parse(data, mime)


async def _nothing() -> None:
    return None


class _InterruptedDocumentStore(PostgresDocumentStore):
    """문서 행을 잠그기 직전에, 한 번만 다른 작업자가 끼어들게 한다."""

    def __init__(
        self, connection: AsyncConnection, interloper: Callable[[], Awaitable[None]]
    ) -> None:
        super().__init__(connection)
        self._interloper = interloper

    async def lock(self, document_id: UUID) -> Document | None:
        interloper, self._interloper = self._interloper, _nothing
        await interloper()
        return await super().lock(document_id)


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


async def _document(pipeline: Pipeline, source: Source, key: str) -> Document:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get_by_key(source.id, key)
    assert document is not None
    return document


async def _jobs(pipeline: Pipeline, document: Document) -> list[str]:
    return await pipeline.job_statuses(document.id)


async def _force_failure(pipeline: Pipeline, document_id: UUID, code: ErrorCode) -> None:
    """색인이 이 코드로 실패해 끝난 모양을 문서 행에 직접 만든다."""
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE documents SET status = 'failed', error_code = :code WHERE id = :id"),
            {"code": code.value, "id": document_id},
        )


def _counts(record: SyncRecord) -> dict[str, object]:
    return {
        "added": record.added,
        "updated": record.updated,
        "unchanged": record.unchanged,
        "skipped": dict(record.skipped),
        "failed": dict(record.failed),
    }


async def test_재시도를_다_쓰고_실패한_문서는_다음_동기화가_읽지_않고_색인_작업을_다시_넣는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", docx_bytes("규정", "연차휴가는 입사 일 년 뒤에 생긴다."), "m1")
    registry = ScriptedRegistry(folder)
    pipeline.stub.fail("/v1/embeddings", 503)
    pipeline.stub.fail("/tokenize", 503)
    await run_sync(pipeline, source, registry, retry=_ONE_ATTEMPT)
    broken = await _document(pipeline, source, "규정.docx")
    states = (await pipeline.states(broken.id)).values()
    assert [(state.status, state.error_code) for state in states] == [
        (IndexStateStatus.FAILED, ErrorCode.EMBEDDING_UNAVAILABLE)
    ]
    pipeline.stub.forced_statuses.clear()
    folder.fetches.clear()

    record = await run_sync(pipeline, source, registry)

    assert folder.fetches == []
    assert record.failed == {ErrorCode.EMBEDDING_UNAVAILABLE.value: 1}
    fixed = await _document(pipeline, source, "규정.docx")
    assert fixed.status is DocumentStatus.PARSED
    # 다시 넣기가 한 번, 색인 작업이 시작하며 한 번 세대를 올린다.
    assert fixed.generation == broken.generation + 2
    assert await pipeline.chunk_texts(fixed.id)
    assert await _jobs(pipeline, fixed) == [_FAILED, _SUCCEEDED]


@pytest.mark.parametrize("code", _RETRYABLE, ids=lambda code: code.value)
async def test_일시_실패와_worker_lost와_source_changed로_실패한_문서는_보통_동기화가_다시_넣는다(
    pipeline: Pipeline, code: ErrorCode
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", docx_bytes("규정"), "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    indexed = await _document(pipeline, source, "규정.docx")
    await _force_failure(pipeline, indexed.id, code)
    folder.fetches.clear()

    record = await run_sync(pipeline, source, registry)

    assert folder.fetches == []
    assert record.failed == {code.value: 1}
    assert await _jobs(pipeline, indexed) == [_SUCCEEDED, _SUCCEEDED]
    assert (await _document(pipeline, source, "규정.docx")).status is DocumentStatus.PARSED


@pytest.mark.parametrize("code", _PERMANENT, ids=lambda code: code.value)
async def test_영구_실패로_남은_문서는_보통_동기화가_다시_넣지_않고_모두_다시_읽기는_다시_넣는다(
    pipeline: Pipeline, code: ErrorCode
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", docx_bytes("규정"), "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    indexed = await _document(pipeline, source, "규정.docx")
    await _force_failure(pipeline, indexed.id, code)
    folder.fetches.clear()

    plain = await run_sync(pipeline, source, registry)

    assert (plain.failed, await _jobs(pipeline, indexed)) == (
        {code.value: 1},
        [_SUCCEEDED],
    )
    assert folder.fetches == []

    again = await run_sync(pipeline, source, registry, reread=True)

    assert folder.fetches == ["규정.docx"]
    assert again.failed == {code.value: 1}
    assert await _jobs(pipeline, indexed) == [_SUCCEEDED, _SUCCEEDED]
    assert (await _document(pipeline, source, "규정.docx")).status is DocumentStatus.PARSED


async def test_수정_시각이_그대로인_채_내용만_바뀐_파일은_모두_다시_읽기가_바뀐_문서로_넣는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", docx_bytes("규정", "처음 내용이다."), "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    folder.put("규정.docx", docx_bytes("규정", "고친 내용이다."), "m1")
    folder.fetches.clear()

    plain = await run_sync(pipeline, source, registry)

    assert (_counts(plain)["updated"], _counts(plain)["unchanged"]) == (0, 1)
    assert folder.fetches == []

    reread = await run_sync(pipeline, source, registry, reread=True)

    assert (_counts(reread)["updated"], _counts(reread)["unchanged"]) == (1, 0)
    document = await _document(pipeline, source, "규정.docx")
    assert any("고친 내용" in text for text in await pipeline.chunk_texts(document.id))


async def test_모두_다시_읽기는_내용이_그대로이고_색인된_문서를_건드리지_않는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", docx_bytes("규정"), "m1")
    folder.put("지침.docx", docx_bytes("지침"), "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    before = [await _document(pipeline, source, key) for key in ("규정.docx", "지침.docx")]
    folder.fetches.clear()

    record = await run_sync(pipeline, source, registry, reread=True)

    assert sorted(folder.fetches) == ["규정.docx", "지침.docx"]
    assert _counts(record) == {
        "added": 0,
        "updated": 0,
        "unchanged": 2,
        "skipped": {},
        "failed": {},
    }
    after = [await _document(pipeline, source, key) for key in ("규정.docx", "지침.docx")]
    assert after == before
    for document in after:
        assert await _jobs(pipeline, document) == [_SUCCEEDED]


async def test_다시_읽어_내용이_같으면_확인값만_새_값으로_적고_색인된_문서는_작업을_만들지_않는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    data = docx_bytes("규정")
    folder.put("규정.docx", data, "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    before = await _document(pipeline, source, "규정.docx")
    folder.put("규정.docx", data, "m2")

    await run_sync(pipeline, source, registry, reread=True)

    after = await _document(pipeline, source, "규정.docx")
    assert after == replace(before, change_marker="m2")
    assert await _jobs(pipeline, after) == [_SUCCEEDED]


async def test_색인_전에_바뀌었다_되돌아온_파일은_다음_동기화가_색인_작업을_다시_넣는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    original = docx_bytes("규정", "처음 내용이다.")
    folder.put("규정.docx", original, "m1")
    registry = ScriptedRegistry(folder)
    reads: list[str] = []

    def swap_after_sync_read(key: str) -> None:
        # 동기화가 읽은 직후(첫 읽기)는 그대로 두고, 색인 작업의 읽기에서 파일을 바꾼다.
        if reads:
            folder.put(key, docx_bytes("규정", "그사이 바뀐 내용이다."), "m2")
        reads.append(key)

    folder.on_fetch = swap_after_sync_read
    await run_sync(pipeline, source, registry)
    broken = await _document(pipeline, source, "규정.docx")
    assert (broken.status, broken.error_code) == (DocumentStatus.FAILED, ErrorCode.SOURCE_CHANGED)
    assert broken.change_marker is None
    folder.on_fetch = None
    folder.put("규정.docx", original, "m3")

    record = await run_sync(pipeline, source, registry)

    assert (_counts(record)["updated"], record.failed) == (0, {ErrorCode.SOURCE_CHANGED.value: 1})
    fixed = await _document(pipeline, source, "규정.docx")
    assert fixed.status is DocumentStatus.PARSED
    assert fixed.change_marker == "m3"
    assert fixed.content_hash == broken.content_hash
    assert await _jobs(pipeline, fixed) == [_FAILED, _SUCCEEDED]
    assert any("처음 내용" in text for text in await pipeline.chunk_texts(fixed.id))


async def test_글자가_없어_건너뛴_문서는_모두_다시_읽기가_작업을_넣되_다시_파싱하지_않는다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("스캔본.pdf", blank_pages_pdf(1), "m1")
    registry = ScriptedRegistry(folder)
    runner = _CountingRunner(pipeline.parse_runner)
    await run_sync(pipeline, source, registry, parse_runner=runner)
    skipped = await _document(pipeline, source, "스캔본.pdf")
    assert (skipped.status, skipped.skip_reason) == (DocumentStatus.SKIPPED, SkipReason.NO_TEXT)
    folder.fetches.clear()

    plain = await run_sync(pipeline, source, registry, parse_runner=runner)

    assert (plain.skipped, folder.fetches) == ({SkipReason.NO_TEXT.value: 1}, [])
    assert await _jobs(pipeline, skipped) == [_SUCCEEDED]

    reread = await run_sync(pipeline, source, registry, parse_runner=runner, reread=True)

    assert reread.skipped == {SkipReason.NO_TEXT.value: 1}
    assert folder.fetches == ["스캔본.pdf"]
    assert await _jobs(pipeline, skipped) == [_SUCCEEDED, _SUCCEEDED]
    assert runner.parse_calls == 1
    after = await _document(pipeline, source, "스캔본.pdf")
    assert (after.status, after.skip_reason) == (DocumentStatus.SKIPPED, SkipReason.NO_TEXT)


async def test_암호가_걸려_건너뛴_문서는_모두_다시_읽기가_작업을_다시_넣고_다시_파싱한다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("암호.pdf", pdf_bytes([PdfPage(text_block("제1조"))], user_password="secret"), "m1")
    registry = ScriptedRegistry(folder)
    runner = _CountingRunner(pipeline.parse_runner)
    await run_sync(pipeline, source, registry, parse_runner=runner)
    skipped = await _document(pipeline, source, "암호.pdf")
    assert skipped.skip_reason is SkipReason.ENCRYPTED

    plain = await run_sync(pipeline, source, registry, parse_runner=runner)

    assert plain.skipped == {SkipReason.ENCRYPTED.value: 1}
    assert (runner.parse_calls, await _jobs(pipeline, skipped)) == (1, [_SUCCEEDED])

    await run_sync(pipeline, source, registry, parse_runner=runner, reread=True)

    assert (runner.parse_calls, await _jobs(pipeline, skipped)) == (2, [_SUCCEEDED, _SUCCEEDED])


@pytest.mark.parametrize("reread", [False, True], ids=["읽지_않는_길", "모두_다시_읽기의_읽는_길"])
async def test_다시_넣는_사이_작업을_다른_작업자에게_뺏기면_다시_넣기도_함께_버려진다(
    pipeline: Pipeline, *, reread: bool
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("규정.docx", docx_bytes("규정"), "m1")
    registry = ScriptedRegistry(folder)
    await run_sync(pipeline, source, registry)
    indexed = await _document(pipeline, source, "규정.docx")
    await _force_failure(pipeline, indexed.id, ErrorCode.EMBEDDING_UNAVAILABLE)

    async def steal_the_job() -> None:
        await pipeline.claim("worker-b", later=3 * 24 * 3600.0)

    await run_sync(
        pipeline,
        source,
        registry,
        reread=reread,
        unit_of_work=_InterruptedUnitOfWork(pipeline, steal_the_job),
    )

    after = await _document(pipeline, source, "규정.docx")
    assert after.generation == indexed.generation
    assert await _jobs(pipeline, indexed) == [_SUCCEEDED]
