"""수집과 작업이 엇갈릴 때 결과가 새 상태로 모이는지 본다(명세 Testing Decisions의 동시성 교차,
티켓 10).

실제 테스트 PostgreSQL 위에서 끼어들 순간을 정한다. 작업이 임베딩이나 파싱을 하는 동안 다른
수집이나 같은 문서의 다른 작업이 끝까지 돈다.
"""

from uuid import UUID

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FailingRunner, interrupting_embedder_for
from tests.support.pipeline import Pipeline

from rag_engine.app.index_document import index_document
from rag_engine.domain.entities import DocumentStatus, IndexStateStatus, JobStatus
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.ports import JobOutcome

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
SUCCEEDED = JobOutcome(JobStatus.SUCCEEDED, None)


async def _document_state(
    pipeline: Pipeline, document_id: UUID
) -> tuple[DocumentStatus, ErrorCode | None]:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
    assert document is not None
    return document.status, document.error_code


async def test_내용이_바뀐_뒤_셋째_단계에_든_작업은_옛_조각을_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)

    async def change_content() -> None:
        await pipeline.ingest(출장)

    first = await index_document(
        pipeline.deps(embedder_for=interrupting_embedder_for(pipeline.pool, change_content)),
        await pipeline.claim(),
    )

    assert first.outcome == SUCCEEDED
    assert await pipeline.chunk_texts(ingested.document_id) == []
    async with pipeline.unit_of_work.begin() as transaction:
        assert await transaction.index.get_state(ingested.document_id, pipeline.version.id) is None
    await index_document(pipeline.deps(), await pipeline.claim("worker-2"))
    texts = await pipeline.chunk_texts(ingested.document_id)
    assert any("출장비" in text for text in texts)
    assert not any("연차휴가" in text for text in texts)


async def test_그룹이_바뀐_뒤_셋째_단계에_든_작업은_옛_조각을_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    moved = await pipeline.add_group("팀B")
    _, other = await pipeline.add_knowledge_base("b", moved)
    ingested = await pipeline.ingest(휴가)

    async def change_group() -> None:
        await pipeline.ingest(휴가, group="팀B")

    first = await index_document(
        pipeline.deps(embedder_for=interrupting_embedder_for(pipeline.pool, change_group)),
        await pipeline.claim(),
    )

    assert first.outcome == SUCCEEDED
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.chunk_texts(ingested.document_id, other) == []
    await index_document(pipeline.deps(), await pipeline.claim("worker-2"))
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.chunk_texts(ingested.document_id, other) != []


async def test_먼저_시작한_작업이_늦게_영구_실패해도_늦게_시작한_작업의_결과가_남는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    early = await pipeline.claim("worker-1")

    async def later_job_finishes() -> None:
        await pipeline.ingest(출장)
        await index_document(pipeline.deps(), await pipeline.claim("worker-2"))

    with pytest.raises(PermanentFailure):
        await index_document(
            pipeline.deps(parse_runner=FailingRunner(before_failing=later_job_finishes)), early
        )

    assert await _document_state(pipeline, ingested.document_id) == (DocumentStatus.PARSED, None)
    texts = await pipeline.chunk_texts(ingested.document_id)
    assert any("출장비" in text for text in texts)
    assert not any("연차휴가" in text for text in texts)
    async with pipeline.unit_of_work.begin() as transaction:
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert state is not None and state.status is IndexStateStatus.INDEXED
