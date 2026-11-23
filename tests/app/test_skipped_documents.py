"""건너뜀(명세 "건너뜀", source-sync 티켓 02): 암호가 걸린 파일과 글자가 없는 파일이 실패가 아니라
`skipped`로 남는다.

실제 테스트 PostgreSQL, 실제 파서 자식 프로세스, 실제 청커와 Kiwi 위에서 돈다. 임베딩 서버만
`TeiStub`이다. 파서 버전이 바뀌는 장면과 공백만 있는 글은 정해 둔 글을 내는 실행기로 흉내 낸다.
"""

from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

import pytest
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.hwpx_files import hwpx_bytes
from tests.support.interleaving import FailingRunner
from tests.support.pdf_files import PdfPage, blank_pages_pdf, pdf_bytes, text_block
from tests.support.pipeline import Pipeline
from tests.support.reindex import current_version, state_status

from rag_engine.app.document_outcome import index_failure_code
from rag_engine.app.index_document import index_document
from rag_engine.domain.entities import (
    Block,
    BlockKind,
    Document,
    DocumentStatus,
    IndexState,
    IndexStateStatus,
    IngestAction,
    JobStatus,
    SkipReason,
)
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.parsing import ParsedDocument, ParserVersion
from rag_engine.domain.ports import JobOutcome

SUCCEEDED = JobOutcome(JobStatus.SUCCEEDED, None)
암호_PDF = pdf_bytes([PdfPage(text_block("제1조 휴가"))], user_password="secret")
스캔본_PDF = blank_pages_pdf(1)
휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")


class _FixedRunner:
    """정해 둔 글을 파싱 결과로 내는 실행기. `library_version`이 다르면 파서 버전이 바뀐 것으로
    본다. 파싱한 횟수를 센다."""

    def __init__(self, texts: Sequence[str], library_version: str = "1") -> None:
        self._texts = texts
        self._library_version = library_version
        self.parse_calls = 0

    def current_version(self, mime: str) -> ParserVersion | None:
        return ParserVersion("fixed", "1.0.0", self._library_version)

    async def parse(self, data: bytes, mime: str) -> ParsedDocument:
        self.parse_calls += 1
        blocks = tuple(
            Block(BlockKind.PARAGRAPH, text, None, None, ordinal)
            for ordinal, text in enumerate(self._texts)
        )
        return ParsedDocument("fixed", "1.0.0", self._library_version, blocks)


async def _document(pipeline: Pipeline, document_id: UUID) -> Document:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
    assert document is not None
    return document


async def _state(pipeline: Pipeline, document_id: UUID) -> IndexState:
    async with pipeline.unit_of_work.begin() as transaction:
        state = await transaction.index.get_state(document_id, pipeline.version.id)
    assert state is not None
    return state


async def _enqueue(pipeline: Pipeline, document_id: UUID) -> None:
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document_id, new_id(), NOW)


async def test_암호가_걸린_PDF는_건너뜀과_encrypted로_쓰고_성공으로_끝난다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(암호_PDF, "규정.pdf")

    result = await index_document(pipeline.deps(), await pipeline.claim())

    assert result.outcome == SUCCEEDED
    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.skip_reason, document.error_code) == (
        DocumentStatus.SKIPPED,
        SkipReason.ENCRYPTED,
        None,
    )


async def test_건너뜀_문서의_색인_상태는_조각_없이_indexed다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(암호_PDF, "규정.pdf")

    await index_document(pipeline.deps(), await pipeline.claim())

    document = await _document(pipeline, ingested.document_id)
    state = await _state(pipeline, ingested.document_id)
    assert (state.status, state.chunk_count, state.built_content_hash, state.error_code) == (
        IndexStateStatus.INDEXED,
        0,
        document.content_hash,
        None,
    )
    assert await pipeline.chunk_texts(ingested.document_id) == []


@pytest.mark.parametrize(
    ("data", "filename"), [(스캔본_PDF, "스캔.pdf"), (hwpx_bytes(), "빈.hwpx")], ids=["PDF", "HWPX"]
)
async def test_색인할_글이_하나도_나오지_않는_파일은_건너뜀과_no_text로_쓴다(
    pipeline: Pipeline, data: bytes, filename: str
) -> None:
    ingested = await pipeline.ingest(data, filename)

    result = await index_document(pipeline.deps(), await pipeline.claim())

    assert result.outcome == SUCCEEDED
    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.skip_reason, document.error_code) == (
        DocumentStatus.SKIPPED,
        SkipReason.NO_TEXT,
        None,
    )
    state = await _state(pipeline, ingested.document_id)
    assert (state.status, state.chunk_count) == (IndexStateStatus.INDEXED, 0)


async def test_공백만_있는_글도_no_text다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)

    await index_document(
        pipeline.deps(parse_runner=_FixedRunner(["  ", "\n\t", ""])), await pipeline.claim()
    )

    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.skip_reason) == (DocumentStatus.SKIPPED, SkipReason.NO_TEXT)


async def test_글이_있던_문서를_같은_키의_암호_PDF로_바꾸면_옛_조각이_사라진다(
    pipeline: Pipeline,
) -> None:
    first = await pipeline.ingest(휴가, "규정")
    await index_document(pipeline.deps(), await pipeline.claim())
    assert await pipeline.chunk_texts(first.document_id) != []

    changed = await pipeline.ingest(암호_PDF, "규정")
    await index_document(pipeline.deps(), await pipeline.claim())

    assert (changed.action, changed.document_id) == (IngestAction.UPDATED, first.document_id)
    document = await _document(pipeline, first.document_id)
    assert (document.status, document.skip_reason) == (DocumentStatus.SKIPPED, SkipReason.ENCRYPTED)
    assert await pipeline.chunk_texts(first.document_id) == []
    assert (await _state(pipeline, first.document_id)).status is IndexStateStatus.INDEXED


async def test_건너뜀을_쓴_작업이_건설_중인_판의_마지막_문서면_판이_전환된다(
    pipeline: Pipeline,
) -> None:
    building = await pipeline.add_building_version()
    ingested = await pipeline.ingest(스캔본_PDF, "스캔.pdf")

    await index_document(pipeline.deps(), await pipeline.claim())

    assert (await current_version(pipeline)).id == building.id
    assert await state_status(pipeline, ingested.document_id, building) is IndexStateStatus.INDEXED


async def test_건너뜀_문서는_살아_있는_판_모두에_indexed를_쓴다(pipeline: Pipeline) -> None:
    building = await pipeline.add_building_version()
    await pipeline.keep_pending(building)
    ingested = await pipeline.ingest(암호_PDF, "규정.pdf")

    await index_document(pipeline.deps(), await pipeline.claim())

    assert (
        await state_status(pipeline, ingested.document_id, pipeline.version),
        await state_status(pipeline, ingested.document_id, building),
    ) == (IndexStateStatus.INDEXED, IndexStateStatus.INDEXED)
    assert (await current_version(pipeline)).id == pipeline.version.id


async def test_글이_없어_건너뛴_문서는_파서_버전이_같으면_다시_파싱하지_않고_건너뜀으로_남는다(
    pipeline: Pipeline,
) -> None:
    runner = _FixedRunner([])
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())
    await _enqueue(pipeline, ingested.document_id)

    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())

    assert runner.parse_calls == 1
    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.skip_reason) == (DocumentStatus.SKIPPED, SkipReason.NO_TEXT)


async def test_글이_없어_건너뛴_문서는_파서_버전이_바뀌어_글이_나오면_색인된다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(스캔본_PDF, "스캔.pdf")
    await index_document(pipeline.deps(), await pipeline.claim())
    await _enqueue(pipeline, ingested.document_id)
    upgraded = _FixedRunner(["연차휴가는 입사 일 년 뒤부터 발생한다."], library_version="2")

    await index_document(pipeline.deps(parse_runner=upgraded), await pipeline.claim())

    assert upgraded.parse_calls == 1
    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.skip_reason) == (DocumentStatus.PARSED, None)
    assert any("연차휴가" in text for text in await pipeline.chunk_texts(ingested.document_id))


async def test_재색인_중_글이_없어_건너뛴_문서에서_글이_나오면_두_판_모두에_조각이_생긴다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(스캔본_PDF, "스캔.pdf")
    await index_document(pipeline.deps(), await pipeline.claim())
    building = await pipeline.add_building_version()
    await pipeline.keep_pending(building)
    await _enqueue(pipeline, ingested.document_id)
    upgraded = _FixedRunner(["연차휴가는 입사 일 년 뒤부터 발생한다."], library_version="2")

    await index_document(pipeline.deps(parse_runner=upgraded), await pipeline.claim())

    assert (await _document(pipeline, ingested.document_id)).status is DocumentStatus.PARSED
    for version in (pipeline.version, building):
        assert await state_status(pipeline, ingested.document_id, version) is (
            IndexStateStatus.INDEXED
        )
        assert any(
            "연차휴가" in text for text in await pipeline.chunk_texts(ingested.document_id, version)
        )


@pytest.mark.parametrize("data", [암호_PDF, 스캔본_PDF], ids=["encrypted", "no_text"])
async def test_건너뜀_문서와_내용이_같은_파일을_다시_넣으면_unchanged이고_작업이_들어가지_않는다(
    pipeline: Pipeline, data: bytes
) -> None:
    first = await pipeline.ingest(data, "규정.pdf")
    await index_document(pipeline.deps(), await pipeline.claim())

    again = await pipeline.ingest(data, "규정.pdf")

    assert (again.action, again.document_id, again.job_id) == (
        IngestAction.UNCHANGED,
        first.document_id,
        None,
    )
    assert len(await pipeline.job_rows(first.document_id)) == 1
    assert (await _document(pipeline, first.document_id)).status is DocumentStatus.SKIPPED


async def test_건너뜀_문서에_다른_내용을_넣으면_받음으로_돌아가고_사유가_사라진다(
    pipeline: Pipeline,
) -> None:
    first = await pipeline.ingest(암호_PDF, "규정")
    await index_document(pipeline.deps(), await pipeline.claim())

    changed = await pipeline.ingest(출장, "규정")

    assert (changed.action, changed.document_id) == (IngestAction.UPDATED, first.document_id)
    assert changed.job_id is not None
    document = await _document(pipeline, first.document_id)
    assert (document.status, document.skip_reason) == (DocumentStatus.RECEIVED, None)
    await index_document(pipeline.deps(), await pipeline.claim())
    parsed = await _document(pipeline, first.document_id)
    assert (parsed.status, parsed.skip_reason) == (DocumentStatus.PARSED, None)
    assert any("출장비" in text for text in await pipeline.chunk_texts(first.document_id))


async def test_건너뜀_문서는_색인_실패로_세지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(암호_PDF, "규정.pdf")
    await index_document(pipeline.deps(), await pipeline.claim())

    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
        assert document is not None
        failure = await index_failure_code(transaction, document)

    assert failure is None


async def test_건너뛴_문서를_다시_파싱하다_다른_영구_실패가_나면_실패로_바뀌고_사유가_사라진다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(암호_PDF, "규정.pdf")
    await index_document(pipeline.deps(), await pipeline.claim())
    await _enqueue(pipeline, ingested.document_id)

    with pytest.raises(PermanentFailure) as raised:
        await index_document(
            pipeline.deps(parse_runner=FailingRunner(ErrorCode.PARSE_FAILED)),
            await pipeline.claim(),
        )

    assert raised.value.code is ErrorCode.PARSE_FAILED
    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.error_code, document.skip_reason) == (
        DocumentStatus.FAILED,
        ErrorCode.PARSE_FAILED,
        None,
    )


async def test_건너뜀을_쓰기_전에_세대가_올라가면_문서도_조각도_색인_상태도_건드리지_않는다(
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

    runner = FailingRunner(ErrorCode.ENCRYPTED_DOCUMENT, before_failing=bump_generation)
    await index_document(pipeline.deps(parse_runner=runner), await pipeline.claim())

    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.skip_reason, document.error_code) == (
        DocumentStatus.RECEIVED,
        None,
        None,
    )
    assert (await _state(pipeline, ingested.document_id)).status is IndexStateStatus.INDEXED
    assert any("연차휴가" in text for text in await pipeline.chunk_texts(ingested.document_id))
