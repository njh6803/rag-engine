"""PDF·HWPX 수집이 작업자를 거쳐 색인되는 왕복과 파싱 실패의 종결(티켓 08, 스토리 10·36).

실제 테스트 PostgreSQL과 실제 파서 자식 프로세스를 쓴다. 임베딩 서버만 `TeiStub`이다.
"""

from uuid import UUID

import sqlalchemy as sa
from tests.support.docx_files import docx_bytes
from tests.support.hwpx_files import HwpxHeading, HwpxParagraph, hwpx_bytes
from tests.support.pdf_files import PdfPage, blank_pages_pdf, pdf_bytes, text_block
from tests.support.pipeline import LEASE_SECONDS, Pipeline
from tests.support.zip_files import zip_bytes

from rag_engine.adapters.parsers.registry import ParserRegistry, discover_parser_specs
from rag_engine.adapters.parsers.runner import SubprocessParseRunner
from rag_engine.domain.entities import DocumentStatus, IndexStateStatus
from rag_engine.domain.errors import ErrorCode
from rag_engine.worker.processing import process_job, run_once

MIB = 1024 * 1024
휴가 = "연차휴가는 입사 일 년 뒤부터 발생한다."


async def _page_and_section(pipeline: Pipeline, document_id: UUID) -> tuple[str | None, str | None]:
    """첫 조각의 `location`에서 쪽 번호와 절 경로(JSON 글)를 읽는다."""
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                "SELECT location->>'page', location->>'section' FROM chunks"
                " WHERE document_id = :id ORDER BY ordinal LIMIT 1"
            ),
            {"id": document_id},
        )
        page, section = rows.one()
    return page, section


async def _job_and_document(
    pipeline: Pipeline, document_id: UUID
) -> tuple[tuple[str, str | None], tuple[DocumentStatus, ErrorCode | None]]:
    async with pipeline.engine.connect() as connection:
        job = (
            await connection.execute(
                sa.text("SELECT status, last_error_code FROM jobs WHERE document_id = :id"),
                {"id": document_id},
            )
        ).one()
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
    assert document is not None
    return (job[0], job[1]), (document.status, document.error_code)


async def test_PDF를_수집하면_쪽_번호가_붙은_조각으로_색인된다(pipeline: Pipeline) -> None:
    data = pdf_bytes([PdfPage(text_block("제1조 휴가")), PdfPage(text_block(휴가))])
    ingested = await pipeline.ingest(data, "규정.pdf")

    await process_job(pipeline.deps(), await pipeline.claim())

    texts = await pipeline.chunk_texts(ingested.document_id)
    assert any("연차휴가" in text for text in texts)
    assert await _page_and_section(pipeline, ingested.document_id) == ("1", "[]")
    assert await _job_and_document(pipeline, ingested.document_id) == (
        ("succeeded", None),
        (DocumentStatus.PARSED, None),
    )


async def test_HWPX를_수집하면_제목_경로가_붙은_조각으로_색인된다(pipeline: Pipeline) -> None:
    data = hwpx_bytes(HwpxHeading("제1조 휴가", level=1), HwpxParagraph(휴가))
    ingested = await pipeline.ingest(data, "규정.hwpx")

    await process_job(pipeline.deps(), await pipeline.claim())

    assert any("연차휴가" in text for text in await pipeline.chunk_texts(ingested.document_id))
    assert await _page_and_section(pipeline, ingested.document_id) == (None, '["제1조 휴가"]')


async def test_글이_없는_HWPX는_조각_없이_parsed로_끝난다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(hwpx_bytes(), "빈.hwpx")

    await process_job(pipeline.deps(), await pipeline.claim())

    assert [
        await _job_and_document(pipeline, ingested.document_id),
        await pipeline.chunk_texts(ingested.document_id),
    ] == [(("succeeded", None), (DocumentStatus.PARSED, None)), []]


async def test_암호가_걸린_PDF는_작업과_문서에_encrypted_document를_남긴다(
    pipeline: Pipeline,
) -> None:
    data = pdf_bytes([PdfPage(text_block("제1조 휴가"))], user_password="secret")
    ingested = await pipeline.ingest(data, "규정.pdf")

    await process_job(pipeline.deps(), await pipeline.claim())

    assert await _job_and_document(pipeline, ingested.document_id) == (
        ("failed", "encrypted_document"),
        (DocumentStatus.FAILED, ErrorCode.ENCRYPTED_DOCUMENT),
    )
    async with pipeline.unit_of_work.begin() as transaction:
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert state is not None and state.status is IndexStateStatus.FAILED
    assert state.error_code is ErrorCode.ENCRYPTED_DOCUMENT


async def test_압축_폭탄과_쪽이_많은_PDF가_있어도_작업자는_다음_문서를_계속_처리한다(
    pipeline: Pipeline,
) -> None:
    runner = SubprocessParseRunner(
        ParserRegistry(discover_parser_specs()),
        timeout_seconds=60,
        memory_mb=2048,
        max_pages=1000,
        max_text_mb=64,
        max_unzipped_mb=1,
        max_compression_ratio=100,
    )
    bomb = await pipeline.ingest(zip_bytes({"a.bin": bytes(2 * MIB)}), "폭탄.docx")
    pages = await pipeline.ingest(blank_pages_pdf(1500), "쪽.pdf")
    good = await pipeline.ingest(docx_bytes("제1조 휴가", 휴가), "정상.docx")

    processed = await run_once(
        pipeline.deps(parse_runner=runner), worker_id="worker-1", lease_seconds=LEASE_SECONDS
    )

    assert processed == 3
    assert await _job_and_document(pipeline, bomb.document_id) == (
        ("failed", "compressed_too_large"),
        (DocumentStatus.FAILED, ErrorCode.COMPRESSED_TOO_LARGE),
    )
    assert await _job_and_document(pipeline, pages.document_id) == (
        ("failed", "too_many_pages"),
        (DocumentStatus.FAILED, ErrorCode.TOO_MANY_PAGES),
    )
    assert await _job_and_document(pipeline, good.document_id) == (
        ("succeeded", None),
        (DocumentStatus.PARSED, None),
    )
    assert any("연차휴가" in text for text in await pipeline.chunk_texts(good.document_id))
