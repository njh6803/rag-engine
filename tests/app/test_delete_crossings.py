"""삭제·되살림과 색인 작업이 엇갈릴 때 결과가 새 상태로 모이는지 본다(명세 Testing Decisions의
동시성 교차, 티켓 11).

실제 테스트 PostgreSQL 위에서 끼어들 순간을 정한다. 작업이 임베딩이나 파싱을 하는 동안 다른
수집이나 삭제가 끝까지 돈다. 재시도를 다 쓰는 갈래는 `test_job_retry.py`가 맡는다(티켓 12).
"""

import pytest
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FailingRunner, interrupting_embedder_for
from tests.support.pipeline import Pipeline

from rag_engine.app.index_document import index_document
from rag_engine.domain.entities import DocumentStatus, IndexStateStatus, JobStatus
from rag_engine.domain.errors import PermanentFailure
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
SUCCEEDED = JobOutcome(JobStatus.SUCCEEDED, None)


async def test_삭제가_커밋된_뒤_셋째_단계에_든_작업은_조각을_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)

    async def delete() -> None:
        await pipeline.delete()

    result = await index_document(
        pipeline.deps(embedder_for=interrupting_embedder_for(pipeline.pool, delete)),
        await pipeline.claim(),
    )

    assert result.outcome == SUCCEEDED
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.archived_texts(ingested.document_id) == []
    async with pipeline.unit_of_work.begin() as transaction:
        assert await transaction.index.get_state(ingested.document_id, pipeline.version.id) is None


async def test_삭제가_첫째_단계_앞에_커밋됐으면_작업은_세대를_올리지_않고_성공으로_끝난다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()
    await pipeline.delete()
    async with pipeline.unit_of_work.begin() as transaction:
        deleted = await transaction.documents.get(ingested.document_id)
    assert deleted is not None

    result = await index_document(pipeline.deps(), job)

    assert result.outcome == SUCCEEDED
    async with pipeline.unit_of_work.begin() as transaction:
        assert await transaction.documents.get(ingested.document_id) == deleted
    assert await pipeline.chunk_texts(ingested.document_id) == []


async def test_지운_뒤_되살린_사이에_옛_작업이_영구_실패해도_되살린_조각을_건드리지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await index_document(pipeline.deps(), await pipeline.claim())
    indexed = await pipeline.chunk_texts(ingested.document_id)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(ingested.document_id, new_id(), NOW)
    old = await pipeline.claim("worker-2")

    async def delete_then_restore() -> None:
        await pipeline.delete()
        await pipeline.ingest(휴가)

    with pytest.raises(PermanentFailure):
        await index_document(
            pipeline.deps(parse_runner=FailingRunner(before_failing=delete_then_restore)), old
        )

    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
        state = await transaction.index.get_state(ingested.document_id, pipeline.version.id)
    assert document is not None
    assert (document.status, document.error_code, document.deleted_at) == (
        DocumentStatus.PARSED,
        None,
        None,
    )
    assert await pipeline.chunk_texts(ingested.document_id) == indexed
    assert state is not None and state.status is IndexStateStatus.INDEXED
