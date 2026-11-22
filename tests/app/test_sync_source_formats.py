"""가져오는 원천의 동기화가 세 형식을 검색까지 보내는 주 이음매(source-sync 티켓 07).

폴더에 PDF, DOCX, HWPX를 하나씩 두고 동기화한 뒤 작업자를 돌리면 세 문서가 검색에 나온다. 암호가
걸린 PDF와 글자가 없는 PDF는 `skipped`로 세어지고, 파싱에 실패하는 PDF는 `failed`로 세어진다. 실제
파서 자식 프로세스와 청커, Kiwi가 돌고 임베딩 서버만 스텁이다.
"""

from tests.support.docx_files import docx_bytes
from tests.support.hwpx_files import HwpxHeading, HwpxParagraph, hwpx_bytes
from tests.support.pdf_files import PdfPage, blank_pages_pdf, pdf_bytes, text_block
from tests.support.pipeline import Pipeline
from tests.support.scripted_connectors import ScriptedFolder, ScriptedRegistry
from tests.support.sync_world import make_pull_source, run_sync

from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.app.admin_sources import get_source_report
from rag_engine.app.search import SearchDeps, SearchRequest, search_documents
from rag_engine.domain.entities import DocumentStatus, SkipReason, SyncRecordStatus
from rag_engine.domain.errors import ErrorCode

_REQUEST = SearchRequest(query="휴가", top_k=8, knowledge_base=None, allowed_knowledge_base_ids=())


def _search_deps(pipeline: Pipeline) -> SearchDeps:
    return SearchDeps(
        unit_of_work=pipeline.unit_of_work,
        embedder_for=pipeline.pool,
        reranker_for=lambda _knowledge_base: None,
        tokenize_keywords=tokenize_keywords,
        candidates=20,
        max_top_k=8,
        timeout_seconds=30.0,
    )


def _three_formats(folder: ScriptedFolder) -> None:
    pages = [PdfPage(text_block("제1조 휴가", "연차휴가는 발생한다."))]
    folder.put("규정.pdf", pdf_bytes(pages), "m1")
    folder.put("지침.docx", docx_bytes("제2조 휴가", "휴가 신청은 사흘 전에 한다."), "m1")
    folder.put(
        "안내.hwpx",
        hwpx_bytes(HwpxHeading("제3조 휴가", 1), HwpxParagraph("휴가 일수는 연 열다섯 날이다.")),
        "m1",
    )


async def test_세_형식의_파일을_동기화하면_세_문서가_검색에_나온다(pipeline: Pipeline) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    _three_formats(folder)

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert (record.listed, record.added, record.updated, record.unchanged) == (3, 3, 0, 0)
    results = await search_documents(_search_deps(pipeline), _REQUEST)
    assert {hit.key for hit in results.hits} == {"규정.pdf", "지침.docx", "안내.hwpx"}
    assert {hit.source for hit in results.hits} == {source.name}


async def test_암호가_걸린_PDF와_글자가_없는_PDF는_건너뜀이고_다음_동기화와_원천_보기에_세어진다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put("암호.pdf", pdf_bytes([PdfPage(text_block("제1조"))], user_password="secret"), "m1")
    folder.put("스캔본.pdf", blank_pages_pdf(1), "m1")
    registry = ScriptedRegistry(folder)
    first = await run_sync(pipeline, source, registry)

    second = await run_sync(pipeline, source, registry)

    assert first.status is SyncRecordStatus.SUCCEEDED
    assert second.skipped == {SkipReason.ENCRYPTED.value: 1, SkipReason.NO_TEXT.value: 1}
    assert (second.added, second.unchanged, second.failed) == (0, 0, {})
    report = await get_source_report(pipeline.unit_of_work, source.name)
    assert (report.documents.total, report.documents.skipped) == (2, 2)
    assert report.last_sync is not None
    assert report.last_sync.id == second.id


async def test_파싱에_실패하는_PDF는_다음_동기화에서_failed로_세어지고_원천_보기에_실패로_든다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    _three_formats(folder)
    folder.put("깨짐.pdf", "%PDF-1.4 이것은 PDF가 아니다".encode(), "m1")
    registry = ScriptedRegistry(folder)
    first = await run_sync(pipeline, source, registry)

    second = await run_sync(pipeline, source, registry)

    assert first.added == 4
    assert second.failed == {ErrorCode.PARSE_FAILED.value: 1}
    assert second.unchanged == 3
    report = await get_source_report(pipeline.unit_of_work, source.name)
    assert (report.documents.total, report.documents.failed) == (4, 1)
    async with pipeline.unit_of_work.begin() as transaction:
        broken = await transaction.documents.get_by_key(source.id, "깨짐.pdf")
    assert broken is not None
    assert broken.status is DocumentStatus.FAILED


async def test_파일이_모두_정책에_걸려도_문서가_없는_원천의_동기화는_실패가_아니다(
    pipeline: Pipeline,
) -> None:
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.put(".숨김.pdf", b"x", "m1")
    folder.put("~$임시.docx", b"x", "m1")
    folder.put("메모.txt", b"x", "m1")
    folder.put("큰.pdf", b"x", "m1", size=10**12)

    record = await run_sync(pipeline, source, ScriptedRegistry(folder))

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert record.listed == 4
    assert record.not_accepted == {"excluded": 2, "unsupported_type": 1, "too_large": 1}
    assert (record.added, record.updated, record.unchanged) == (0, 0, 0)
