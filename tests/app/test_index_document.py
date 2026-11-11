"""`index_document` 유스케이스(명세 "수집 파이프라인과 작업"의 네 단계, 티켓 07).

실제 테스트 PostgreSQL, 실제 DOCX 파서 자식 프로세스, 실제 청커와 Kiwi 위에서 돈다. 임베딩 서버만
`TeiStub`이다. 끼어듦(임베딩 직전에 다른 요청이 세대를 올림)은 임베더를 바꿔 끼워 정한다.
"""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest
import sqlalchemy as sa
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FailingRunner, InterruptingEmbedder
from tests.support.pipeline import DIMENSIONS, LEASE_SECONDS, Pipeline

from rag_engine.adapters.parsers.runner import SubprocessParseRunner
from rag_engine.app import index_failure as index_failure_module
from rag_engine.app.index_document import index_document
from rag_engine.domain.entities import (
    DocumentStatus,
    IndexStateStatus,
    IndexVersion,
    IngestAction,
    JobStatus,
)
from rag_engine.domain.errors import AttemptLostError, ErrorCode, PermanentFailure
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.parsing import ParsedDocument, ParserVersion
from rag_engine.domain.ports import Embedder, JobOutcome

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
SUCCEEDED = JobOutcome(JobStatus.SUCCEEDED, None)


class _CountingRunner:
    """실제 실행기를 감싸 파싱 횟수를 센다. `library_version`을 주면 파서의 판이 바뀐 것으로
    본다."""

    def __init__(self, inner: SubprocessParseRunner, library_version: str | None = None) -> None:
        self._inner = inner
        self._library_version = library_version
        self.parse_calls = 0

    def current_version(self, mime: str) -> ParserVersion | None:
        version = self._inner.current_version(mime)
        if version is None or self._library_version is None:
            return version
        return replace(version, library_version=self._library_version)

    async def parse(self, data: bytes, mime: str) -> ParsedDocument:
        self.parse_calls += 1
        return await self._inner.parse(data, mime)


async def _generation(pipeline: Pipeline, document_id: UUID) -> int:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
    assert document is not None
    return document.generation


async def _requeue(pipeline: Pipeline, document_id: UUID) -> None:
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document_id, new_id(), NOW)


async def test_DOCX를_파싱해_조각과_색인_상태를_쓰고_성공으로_끝난다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    before = await _generation(pipeline, ingested.document_id)
    job = await pipeline.claim()

    result = await index_document(pipeline.deps(), job)

    assert result.outcome == SUCCEEDED
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
        content = await transaction.documents.get_content(ingested.document_id)
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
        saved_job = await transaction.jobs.get(job.id)
    assert document is not None
    assert (document.status, document.error_code, document.generation) == (
        DocumentStatus.PARSED,
        None,
        before + 1,
    )
    assert content is not None
    assert (content.parser_name, content.parsed_content_hash) == ("docx", document.content_hash)
    assert [block.text for block in content.blocks] == [
        "제1조 휴가",
        "연차휴가는 입사 일 년 뒤부터 발생한다.",
    ]
    texts = await pipeline.chunk_texts(ingested.document_id)
    assert texts != [] and "연차휴가" in texts[0]
    assert state is not None
    assert (state.status, state.chunk_count, state.built_content_hash) == (
        IndexStateStatus.INDEXED,
        len(texts),
        document.content_hash,
    )
    assert saved_job is not None and saved_job.raised_generation == before + 1


async def test_조각은_판의_차원_벡터와_키워드와_문서에서_복사한_칸을_싣는다(
    pipeline: Pipeline,
) -> None:
    updated_at = NOW - timedelta(days=30)
    ingested = await pipeline.ingest(휴가, updated_at=updated_at)

    await index_document(pipeline.deps(), await pipeline.claim())

    async with pipeline.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    sa.text(
                        "SELECT vector_dims(embedding) AS dims, keywords::text AS keywords,"
                        " group_id, source_content_hash, updated_at FROM chunks"
                        " WHERE document_id = :document"
                    ),
                    {"document": ingested.document_id},
                )
            )
            .mappings()
            .all()
        )
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
    assert document is not None
    assert [row["dims"] for row in rows] == [DIMENSIONS]
    assert "연차" in rows[0]["keywords"]
    assert (rows[0]["group_id"], rows[0]["source_content_hash"], rows[0]["updated_at"]) == (
        pipeline.group.id,
        document.content_hash,
        updated_at,
    )


async def test_지워진_문서는_아무것도_쓰지_않고_성공으로_끝난다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(ingested.document_id)
        assert document is not None
        await transaction.documents.update(replace(document, deleted_at=NOW))
    before = await _generation(pipeline, ingested.document_id)

    result = await index_document(pipeline.deps(), await pipeline.claim())

    assert result.outcome == SUCCEEDED
    assert [await _generation(pipeline, ingested.document_id)] == [before]
    assert await pipeline.chunk_texts(ingested.document_id) == []
    async with pipeline.unit_of_work.begin() as transaction:
        assert await transaction.documents.get_content(ingested.document_id) is None


async def test_임베딩하는_사이_세대가_올라가면_조각을_쓰지_않고_성공으로_끝난다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)

    async def bump_generation() -> None:
        async with pipeline.unit_of_work.begin() as transaction:
            document = await transaction.documents.lock(ingested.document_id)
            assert document is not None
            await transaction.documents.update(
                replace(document, generation=document.generation + 5)
            )

    def embedder_for(version: IndexVersion) -> Embedder:
        return InterruptingEmbedder(pipeline.pool(version), bump_generation)

    result = await index_document(pipeline.deps(embedder_for=embedder_for), await pipeline.claim())

    assert result.outcome == SUCCEEDED
    assert await pipeline.chunk_texts(ingested.document_id) == []
    async with pipeline.unit_of_work.begin() as transaction:
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert state is None


async def test_임대를_잃은_시도는_세대를_올리지_못하고_버려진다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    stale = await pipeline.claim("worker-1")
    await pipeline.claim("worker-2", later=LEASE_SECONDS + 1)
    before = await _generation(pipeline, ingested.document_id)

    with pytest.raises(AttemptLostError):
        await index_document(pipeline.deps(), stale)

    assert await _generation(pipeline, ingested.document_id) == before
    assert await pipeline.chunk_texts(ingested.document_id) == []


async def test_내용이_같고_파서의_판도_같으면_파싱을_건너뛴다(pipeline: Pipeline) -> None:
    runner = _CountingRunner(pipeline.parse_runner)
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())
    await _requeue(pipeline, ingested.document_id)

    second = await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())

    assert runner.parse_calls == 1
    assert second.timings.parse_ms == 0.0
    assert second.outcome == SUCCEEDED


async def test_내용이_바뀌면_다시_파싱하고_옛_조각을_새_조각으로_바꾼다(pipeline: Pipeline) -> None:
    runner = _CountingRunner(pipeline.parse_runner)
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())
    old = await pipeline.chunk_texts(ingested.document_id)

    await pipeline.ingest(출장)
    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())

    new = await pipeline.chunk_texts(ingested.document_id)
    assert [runner.parse_calls] == [2]
    assert any("연차휴가" in text for text in old)
    assert new != [] and all("연차휴가" not in text for text in new)
    assert any("출장비" in text for text in new)


async def test_파서의_판이_바뀌면_내용이_같아도_다시_파싱한다(pipeline: Pipeline) -> None:
    first = _CountingRunner(pipeline.parse_runner)
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(parse_runner=first), await pipeline.claim())
    await _requeue(pipeline, ingested.document_id)
    upgraded = _CountingRunner(pipeline.parse_runner, library_version="999.0.0")

    await index_document(pipeline.deps(parse_runner=upgraded), await pipeline.claim())

    assert (first.parse_calls, upgraded.parse_calls) == (1, 1)
    async with pipeline.unit_of_work.begin() as transaction:
        content = await transaction.documents.get_content(ingested.document_id)
    assert content is not None
    assert content.parser_library_version != "999.0.0"


async def test_살아_있는_판_둘에_각각_조각과_색인_상태를_쓴다(pipeline: Pipeline) -> None:
    building: IndexVersion = await pipeline.add_building_version()
    ingested = await pipeline.ingest(휴가)

    await index_document(pipeline.deps(), await pipeline.claim())

    assert await pipeline.chunk_texts(ingested.document_id, building) == await pipeline.chunk_texts(
        ingested.document_id
    )
    async with pipeline.unit_of_work.begin() as transaction:
        building_state = await transaction.index.get_state(ingested.document_id, building.id)
        current_state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert building_state is not None and current_state is not None
    assert (building_state.status, current_state.status) == (
        IndexStateStatus.INDEXED,
        IndexStateStatus.INDEXED,
    )


async def test_단계별_지연을_잰다(pipeline: Pipeline) -> None:
    await pipeline.ingest(휴가)

    result = await index_document(pipeline.deps(), await pipeline.claim())

    assert result.timings.parse_ms > 0
    assert result.timings.embedding_ms > 0
    assert result.timings.write_ms > 0


async def _fail_parsing(
    pipeline: Pipeline, runner: FailingRunner | None = None
) -> PermanentFailure:
    with pytest.raises(PermanentFailure) as raised:
        await index_document(
            pipeline.deps(parse_runner=runner or FailingRunner()), await pipeline.claim()
        )
    return raised.value


async def test_파싱이_영구_실패하면_문서와_색인_상태를_failed로_쓰고_옛_조각을_지운다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(), await pipeline.claim())
    await pipeline.ingest(출장)

    failure = await _fail_parsing(pipeline)

    assert failure.code is ErrorCode.ENCRYPTED_DOCUMENT
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert document is not None and state is not None
    assert (document.status, document.error_code) == (
        DocumentStatus.FAILED,
        ErrorCode.ENCRYPTED_DOCUMENT,
    )
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert (state.status, state.chunk_count, state.built_content_hash, state.error_code) == (
        IndexStateStatus.FAILED,
        0,
        None,
        ErrorCode.ENCRYPTED_DOCUMENT,
    )


async def test_영구_실패는_살아_있는_판_모두에_색인_상태를_쓰고_건설_중인_판은_전환_검사를_부른다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    building = await pipeline.add_building_version()
    ingested = await pipeline.ingest(휴가)
    checked: list[IndexVersion] = []

    async def record_check(_transaction: object, version: IndexVersion) -> None:
        checked.append(version)

    monkeypatch.setattr(index_failure_module, "check_version_switch", record_check)

    await _fail_parsing(pipeline, FailingRunner(ErrorCode.PARSE_FAILED))

    async with pipeline.unit_of_work.begin() as transaction:
        states = [
            await transaction.index.get_state(ingested.document_id, version.id)
            for version in (pipeline.version, building)
        ]
    assert [(state.status, state.error_code) for state in states if state is not None] == [
        (IndexStateStatus.FAILED, ErrorCode.PARSE_FAILED)
    ] * 2
    assert [version.id for version in checked] == [building.id]


async def test_파싱하는_사이_세대가_올라가면_문서도_조각도_건드리지_않고_실패만_올린다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(), await pipeline.claim())
    await pipeline.ingest(출장)

    async def bump_generation() -> None:
        async with pipeline.unit_of_work.begin() as transaction:
            document = await transaction.documents.lock(ingested.document_id)
            assert document is not None
            await transaction.documents.update(
                replace(document, generation=document.generation + 5)
            )

    failure = await _fail_parsing(pipeline, FailingRunner(before_failing=bump_generation))

    assert failure.code is ErrorCode.ENCRYPTED_DOCUMENT
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert document is not None and state is not None
    assert (document.status, document.error_code) == (DocumentStatus.RECEIVED, None)
    assert state.status is IndexStateStatus.INDEXED
    assert any("연차휴가" in text for text in await pipeline.chunk_texts(ingested.document_id))


async def test_고친_파일을_넣으면_received를_거쳐_parsed가_되고_같은_내용은_unchanged다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _fail_parsing(pipeline)

    fixed = await pipeline.ingest(출장)
    async with pipeline.unit_of_work.begin() as transaction:
        received = await transaction.documents.get(ingested.document_id)
    await index_document(pipeline.deps(), await pipeline.claim())
    again = await pipeline.ingest(출장)

    assert fixed.action is IngestAction.UPDATED
    assert received is not None
    assert (received.status, received.error_code) == (DocumentStatus.RECEIVED, None)
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert document is not None and state is not None
    assert (document.status, document.error_code) == (DocumentStatus.PARSED, None)
    assert state.status is IndexStateStatus.INDEXED
    assert again.action is IngestAction.UNCHANGED and again.job_id is None


async def test_내용을_바꿨다가_되돌리면_파싱을_건너뛰어도_parsed로_돌아온다(
    pipeline: Pipeline,
) -> None:
    runner = _CountingRunner(pipeline.parse_runner)
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())
    await pipeline.ingest(출장)
    await _fail_parsing(pipeline)

    await pipeline.ingest(휴가)
    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())

    assert runner.parse_calls == 1
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
    assert document is not None
    assert (document.status, document.error_code) == (DocumentStatus.PARSED, None)
    assert any("연차휴가" in text for text in await pipeline.chunk_texts(ingested.document_id))
