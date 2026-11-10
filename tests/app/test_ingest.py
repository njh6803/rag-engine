"""수집 유스케이스의 교차 시험(명세 "수집 API"의 동시 수집, "수집 파이프라인과 작업"의 원본 정리).

실제 테스트 PostgreSQL 위에서, 같은 키를 넣는 다른 요청이 지는 쪽의 사이에 끼어드는 순간을 정해 두고
돌린다. 끼어듦은 한 번이다. 진 쪽은 원본을 이긴 문서의 UUID 아래로 옮기고 갱신으로 다시 처리한다.
"""

import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from tests.records import (
    NOW,
    insert_chunk,
    make_index_version,
    make_knowledge_base,
    seed_source_and_group,
)

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.adapters.postgres.document_store import PostgresDocumentStore
from rag_engine.adapters.postgres.job_queue import PostgresJobQueue
from rag_engine.adapters.postgres.unit_of_work import PostgresTransaction, PostgresUnitOfWork
from rag_engine.app.ingest import IngestRequest, IngestResult, ingest_document
from rag_engine.domain.entities import Document, IndexVersionStatus, IngestAction, Job
from rag_engine.domain.errors import ErrorCode, InvalidInput, TransientFailure
from rag_engine.domain.identifiers import new_id

PDF = b"%PDF-1.7 first"
OTHER_PDF = b"%PDF-1.7 second"
MAX_UPLOAD_BYTES = 1024 * 1024
KEY = "규정.pdf"


async def _nothing() -> None:
    return None


def _blobs(root: Path) -> list[Path]:
    return sorted(path for path in (root / "blobs").rglob("*") if path.is_file())


def _request(
    data: bytes,
    *,
    filename: str | None = KEY,
    key: str | None = None,
    updated_at: datetime | None = None,
) -> IngestRequest:
    return IngestRequest(
        filename=filename, data=data, key=key, group=None, metadata={}, updated_at=updated_at
    )


async def _ingest_request(
    unit_of_work: PostgresUnitOfWork, blob_store: LocalBlobStore, request: IngestRequest
) -> IngestResult:
    return await ingest_document(
        unit_of_work,
        blob_store,
        request,
        request_id=new_id(),
        now=NOW,
        max_upload_bytes=MAX_UPLOAD_BYTES,
    )


async def _ingest(
    unit_of_work: PostgresUnitOfWork, blob_store: LocalBlobStore, data: bytes
) -> IngestResult:
    return await _ingest_request(unit_of_work, blob_store, _request(data))


class _CustomizedUnitOfWork(PostgresUnitOfWork):
    """시험이 어댑터 하나를 바꿔 끼울 수 있게 하는 작업 단위. 하위 클래스가 `customize`를 채운다."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine)
        self._test_engine = engine

    def customize(self, transaction: PostgresTransaction, connection: AsyncConnection) -> None:
        raise NotImplementedError

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[PostgresTransaction]:
        async with self._test_engine.connect() as connection, connection.begin():
            transaction = PostgresTransaction(connection)
            self.customize(transaction, connection)
            yield transaction


class _RacingDocumentStore(PostgresDocumentStore):
    """처음 `add`를 부르기 직전에 다른 수집이 끼어들어 먼저 커밋하게 한다."""

    def __init__(
        self, connection: AsyncConnection, interloper: Callable[[], Awaitable[None]]
    ) -> None:
        super().__init__(connection)
        self._interloper = interloper

    async def add(self, document: Document) -> None:
        interloper, self._interloper = self._interloper, _nothing
        await interloper()
        await super().add(document)


class _RacingUnitOfWork(_CustomizedUnitOfWork):
    def __init__(self, engine: AsyncEngine, interloper: Callable[[], Awaitable[None]]) -> None:
        super().__init__(engine)
        self._interloper = interloper

    def customize(self, transaction: PostgresTransaction, connection: AsyncConnection) -> None:
        transaction.documents = _RacingDocumentStore(connection, self._interloper)


class _RacingBlobStore(LocalBlobStore):
    """처음 쓰기가 끝난 직후에 다른 수집이 끼어들어 먼저 커밋하게 한다."""

    def __init__(self, root: Path, interloper: Callable[[], Awaitable[None]]) -> None:
        super().__init__(root)
        self._interloper = interloper

    async def write(self, key: str, data: bytes) -> None:
        await super().write(key, data)
        interloper, self._interloper = self._interloper, _nothing
        await interloper()


async def test_같은_키가_동시에_들어와_지면_이긴_문서로_갱신하고_원본을_그_문서_아래로_옮긴다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)
    store = LocalBlobStore(tmp_path)
    winner: list[IngestResult] = []

    async def winner_ingests() -> None:
        winner.append(await _ingest(plain, store, PDF))

    loser = await _ingest(_RacingUnitOfWork(engine, winner_ingests), store, OTHER_PDF)

    (won,) = winner
    assert won.action is IngestAction.CREATED
    assert loser.action is IngestAction.UPDATED
    assert loser.document_id == won.document_id
    assert loser.job_id == won.job_id
    (blob,) = _blobs(tmp_path)
    assert blob.parent.name == str(won.document_id)
    assert blob.read_bytes() == OTHER_PDF
    async with plain.begin() as transaction:
        document = await transaction.documents.get(won.document_id)
    assert document is not None
    assert document.generation == 2
    assert document.blob_path == f"blobs/{won.document_id}/{blob.name}"


async def test_같은_내용이_동시에_들어와_지면_건너뛰고_진_쪽의_원본은_남기지_않는다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)
    store = LocalBlobStore(tmp_path)
    winner: list[IngestResult] = []

    async def winner_ingests() -> None:
        winner.append(await _ingest(plain, store, PDF))

    loser = await _ingest(_RacingUnitOfWork(engine, winner_ingests), store, PDF)

    (won,) = winner
    assert (loser.action, loser.document_id, loser.job_id) == (
        IngestAction.UNCHANGED,
        won.document_id,
        None,
    )
    (blob,) = _blobs(tmp_path)
    assert blob.parent.name == str(won.document_id)
    assert blob.read_bytes() == PDF


async def test_원본을_쓴_뒤_같은_키의_문서가_먼저_커밋되면_원본을_그_문서_아래로_옮긴다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)
    winner: list[IngestResult] = []

    async def winner_ingests() -> None:
        winner.append(await _ingest(plain, LocalBlobStore(tmp_path), PDF))

    store = _RacingBlobStore(tmp_path, winner_ingests)

    loser = await _ingest(plain, store, OTHER_PDF)

    (won,) = winner
    assert loser.action is IngestAction.UPDATED
    assert loser.document_id == won.document_id
    (blob,) = _blobs(tmp_path)
    assert blob.parent.name == str(won.document_id)
    assert blob.read_bytes() == OTHER_PDF


class _FailingJobQueue(PostgresJobQueue):
    async def enqueue(self, document_id: UUID, request_id: UUID, now: datetime) -> Job:
        raise RuntimeError("작업을 넣다가 실패한다")


class _FailingJobUnitOfWork(_CustomizedUnitOfWork):
    def customize(self, transaction: PostgresTransaction, connection: AsyncConnection) -> None:
        transaction.jobs = _FailingJobQueue(connection)


async def test_작업_단위가_롤백되면_새로_쓴_원본을_지우고_문서도_남기지_않는다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)

    with pytest.raises(RuntimeError, match="작업을 넣다가"):
        await _ingest(_FailingJobUnitOfWork(engine), LocalBlobStore(tmp_path), PDF)

    assert _blobs(tmp_path) == []
    async with plain.begin() as transaction:
        source = await transaction.catalog.get_source("default")
        assert source is not None
        assert await transaction.documents.get_by_key(source.id, KEY) is None


class _CommitThenFailUnitOfWork(PostgresUnitOfWork):
    """두 번째 블록(쓰기)은 커밋한 뒤 나가며 예외를 낸다. 커밋 응답을 받지 못한 연결이다."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine)
        self._blocks = 0

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[PostgresTransaction]:
        self._blocks += 1
        async with super().begin() as transaction:
            yield transaction
        if self._blocks == 2:
            raise ConnectionError("커밋 응답을 받지 못했다")


async def test_커밋이_됐는지_모르는_실패_뒤에는_문서_행이_가리키는_원본을_지우지_않는다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)
    store = LocalBlobStore(tmp_path)

    with pytest.raises(ConnectionError, match="커밋 응답"):
        await _ingest(_CommitThenFailUnitOfWork(engine), store, PDF)

    (blob,) = _blobs(tmp_path)
    assert blob.read_bytes() == PDF
    retried = await _ingest(plain, store, PDF)
    assert retried.action is IngestAction.UNCHANGED
    (kept,) = _blobs(tmp_path)
    assert kept == blob


class _StubbornBlobStore(LocalBlobStore):
    """지우지 못하는 파일 저장소(Windows에서 열린 파일 등)."""

    async def delete(self, key: str) -> None:
        raise TransientFailure(ErrorCode.BLOB_STORE_ERROR, "원본을 지우지 못했다")


async def test_커밋_뒤_옛_원본을_지우지_못해도_수집은_성공하고_고아_원본을_로그에_남긴다(
    engine: AsyncEngine, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)
    store = _StubbornBlobStore(tmp_path)
    await _ingest(plain, store, PDF)

    with caplog.at_level(logging.WARNING, logger="rag_engine.app.ingest"):
        result = await _ingest(plain, store, OTHER_PDF)

    assert result.action is IngestAction.UPDATED
    assert len(_blobs(tmp_path)) == 2
    (record,) = caplog.records
    line = JsonLinesFormatter().format(record)
    payload = json.loads(line)
    assert payload["event"] == "orphan_blob_left"
    assert payload["exception"]["type"] == "rag_engine.domain.errors.TransientFailure"
    assert payload["exception"]["message"] == "원본을 지우지 못했다"
    assert "blobs/" not in line


class _SecondWriteFailsBlobStore(LocalBlobStore):
    """첫 쓰기는 하고 두 번째 쓰기부터 실패하는 파일 저장소."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self._writes = 0

    async def write(self, key: str, data: bytes) -> None:
        self._writes += 1
        if self._writes > 1:
            raise TransientFailure(ErrorCode.BLOB_STORE_ERROR, "다시 쓰지 못했다")
        await super().write(key, data)


async def test_이긴_문서_아래로_옮기다_쓰기가_실패하면_처음_쓴_원본을_지우고_오류를_올린다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)
    winner: list[IngestResult] = []

    async def winner_ingests() -> None:
        winner.append(await _ingest(plain, LocalBlobStore(tmp_path), PDF))

    loser_store = _SecondWriteFailsBlobStore(tmp_path)

    with pytest.raises(TransientFailure, match="다시 쓰지 못했다"):
        await _ingest(_RacingUnitOfWork(engine, winner_ingests), loser_store, OTHER_PDF)

    (won,) = winner
    (blob,) = _blobs(tmp_path)
    assert blob.parent.name == str(won.document_id)
    assert blob.read_bytes() == PDF


async def test_키도_파일_이름도_없으면_거부하고_원본도_작업도_남기지_않는다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)

    with pytest.raises(InvalidInput) as raised:
        await _ingest_request(plain, LocalBlobStore(tmp_path), _request(PDF, filename=None))

    assert raised.value.loc == ("key",)
    assert _blobs(tmp_path) == []


async def test_파일_이름에_NUL이_있으면_거부하고_원본도_작업도_남기지_않는다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    await seed_source_and_group(plain)

    with pytest.raises(InvalidInput) as raised:
        await _ingest_request(
            plain, LocalBlobStore(tmp_path), _request(PDF, filename="규정\x00.pdf", key="정책.pdf")
        )

    assert raised.value.loc == ("file",)
    assert _blobs(tmp_path) == []


async def test_파일_이름이_없어도_키가_있으면_키가_문서의_키이고_제목의_바탕이_된다(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    source, _ = await seed_source_and_group(plain)

    result = await _ingest_request(
        plain, LocalBlobStore(tmp_path), _request(PDF, filename=None, key="정책.pdf")
    )

    assert result.action is IngestAction.CREATED
    async with plain.begin() as transaction:
        document = await transaction.documents.get_by_key(source.id, "정책.pdf")
    assert document is not None
    assert (document.id, document.title) == (result.document_id, "정책")


async def test_같은_내용을_갱신일만_바꿔_넣으면_조각의_복사_칸의_갱신일이_따라간다(
    engine: AsyncEngine, empty_database_url: str, tmp_path: Path
) -> None:
    plain = PostgresUnitOfWork(engine)
    _, group = await seed_source_and_group(plain)
    store = LocalBlobStore(tmp_path)
    first = await _ingest(plain, store, PDF)
    knowledge_base = make_knowledge_base()
    version = make_index_version(knowledge_base, IndexVersionStatus.BUILDING)
    async with plain.begin() as transaction:
        await transaction.catalog.add_knowledge_base(knowledge_base)
        await transaction.catalog.add_index_version(version)
    insert_chunk(empty_database_url, first.document_id, version.id, group.id)
    newer = datetime(2026, 12, 1, tzinfo=UTC)

    result = await _ingest_request(plain, store, _request(PDF, updated_at=newer))

    assert result.action is IngestAction.UNCHANGED
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        ((updated_at,),) = connection.execute("SELECT updated_at FROM chunks").fetchall()
    assert updated_at.date().isoformat() == "2026-12-01"
