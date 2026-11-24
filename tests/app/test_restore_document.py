"""문서 되살리기(source-sync 티켓 13, 명세 "문서 되살리기").

실제 테스트 PostgreSQL, 실제 DOCX 파서 자식 프로세스, 실제 청커와 Kiwi 위에서 돈다. 임베딩 서버만
`TeiStub`이다. 되살림 한 건이 작업 단위 하나에서 조각을 돌려놓는지, 되돌릴 조각이 없는 판에만 작업을
넣는지, 건너뜀 문서는 색인 상태만 다시 쓰는지, 거절하는 넷과 잠금 순서를 본다.
"""

import asyncio
from dataclasses import replace
from uuid import UUID

import pytest
import sqlalchemy as sa
from tests.records import NOW, make_document
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import Pipeline

from rag_engine.app.index_document import index_document
from rag_engine.app.restore_document import DocumentRestored, restore_document
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IndexStateStatus,
    IngestAction,
    Source,
    SourceKind,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
EMBEDDINGS = "/v1/embeddings"
DEADLINE_SECONDS = 60.0


async def _restore(pipeline: Pipeline, document_id: UUID) -> DocumentRestored:
    return await restore_document(
        pipeline.unit_of_work, document_id, request_id=new_id(), now=pipeline.clock[0]
    )


async def _refused(pipeline: Pipeline, document_id: UUID) -> ErrorCode:
    with pytest.raises(RequestError) as refused:
        await _restore(pipeline, document_id)
    return refused.value.code


async def _document(pipeline: Pipeline, document_id: UUID) -> Document:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
    assert document is not None
    return document


async def _indexed_and_deleted(pipeline: Pipeline, data: bytes = 휴가) -> UUID:
    """색인까지 끝낸 문서를 지운다."""
    ingested = await pipeline.ingest(data)
    await index_document(pipeline.deps(), await pipeline.claim())
    await pipeline.delete()
    return ingested.document_id


async def _make_skipped(pipeline: Pipeline, document_id: UUID) -> None:
    """색인한 문서를 건너뜀 문서의 모양으로 바꾼다. 조각이 없고 색인 상태는 조각 0개인 `indexed`다.
    지운 문서라 조각은 삭제 보관함에 있으므로 거기서 지운다."""
    async with pipeline.engine.begin() as connection:
        parameters = {"document": document_id}
        await connection.execute(
            sa.text("DELETE FROM archived_chunks WHERE document_id = :document"), parameters
        )
        await connection.execute(
            sa.text("UPDATE document_index_states SET chunk_count = 0 WHERE document_id = :d"),
            {"d": document_id},
        )
        await connection.execute(
            sa.text(
                "UPDATE documents SET status = 'skipped', skip_reason = 'no_text'"
                " WHERE id = :document"
            ),
            parameters,
        )


async def _live_states(pipeline: Pipeline, document_id: UUID) -> dict[UUID, tuple[str, int]]:
    """판마다 (색인 상태, 조각 수)."""
    states = await pipeline.states(document_id)
    return {version: (state.status.value, state.chunk_count) for version, state in states.items()}


async def test_같은_내용이고_판이_그대로면_조각이_돌아오고_작업도_임베딩도_없다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    embeddings = pipeline.stub.count(EMBEDDINGS)
    before = await _document(pipeline, document_id)
    assert await pipeline.chunk_texts(document_id) == []

    restored = await _restore(pipeline, document_id)

    assert restored == DocumentRestored(document_id, None)
    after = await _document(pipeline, document_id)
    assert (after.deleted_at, after.generation) == (None, before.generation + 1)
    assert after.status is DocumentStatus.PARSED
    assert await pipeline.chunk_texts(document_id) != []
    assert await pipeline.archived_texts(document_id) == []
    states = await pipeline.states(document_id)
    assert {state.status for state in states.values()} == {IndexStateStatus.INDEXED}
    assert "queued" not in await pipeline.job_statuses(document_id)
    assert pipeline.stub.count(EMBEDDINGS) == embeddings


async def test_그룹_제목_메타데이터는_문서_행의_것_그대로다(pipeline: Pipeline) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    before = await _document(pipeline, document_id)

    await _restore(pipeline, document_id)

    after = await _document(pipeline, document_id)
    assert (after.group_id, after.title, after.metadata, after.content_hash, after.blob_path) == (
        before.group_id,
        before.title,
        before.metadata,
        before.content_hash,
        before.blob_path,
    )


async def test_지운_뒤에_생긴_판에는_되돌릴_조각이_없어_작업이_들어가고_pending은_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    building = await pipeline.add_building_version()

    restored = await _restore(pipeline, document_id)

    assert restored.job_id is not None
    states = await pipeline.states(document_id)
    assert states[pipeline.version.id].status is IndexStateStatus.INDEXED
    assert building.id not in states
    assert await pipeline.job_statuses(document_id) == ["running", "queued"]
    assert await pipeline.chunk_texts(document_id) != []


async def test_내용이_색인되기_전에_지운_문서는_현재_판에도_pending이_들어가고_작업이_색인한다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await pipeline.delete()

    restored = await _restore(pipeline, ingested.document_id)

    assert restored.job_id is not None
    states = await pipeline.states(ingested.document_id)
    assert {state.status for state in states.values()} == {IndexStateStatus.PENDING}
    assert await pipeline.chunk_texts(ingested.document_id) == []
    await index_document(pipeline.deps(), await pipeline.claim())
    assert await pipeline.chunk_texts(ingested.document_id) != []


async def test_건너뜀_문서는_조각이_없어_대상_판마다_색인_상태만_다시_쓰고_작업을_넣지_않는다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    await _make_skipped(pipeline, document_id)
    building = await pipeline.add_building_version()
    embeddings = pipeline.stub.count(EMBEDDINGS)

    restored = await _restore(pipeline, document_id)

    assert restored.job_id is None
    after = await _document(pipeline, document_id)
    assert (after.status, after.skip_reason is not None, after.deleted_at) == (
        DocumentStatus.SKIPPED,
        True,
        None,
    )
    assert await _live_states(pipeline, document_id) == {
        pipeline.version.id: ("indexed", 0),
        building.id: ("indexed", 0),
    }
    assert "queued" not in await pipeline.job_statuses(document_id)
    assert pipeline.stub.count(EMBEDDINGS) == embeddings


async def test_수집_API가_같은_키로_되살려도_건너뜀_문서는_작업을_넣지_않는다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    await _make_skipped(pipeline, document_id)

    result = await pipeline.ingest(휴가)

    assert (result.action, result.job_id) == (IngestAction.RESTORED, None)
    assert "queued" not in await pipeline.job_statuses(document_id)


async def test_원천과_함께_지워졌다는_표시가_남은_문서는_그_표시도_지운다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE documents SET deleted_with_source = true WHERE id = :document"),
            {"document": document_id},
        )

    await _restore(pipeline, document_id)

    after = await _document(pipeline, document_id)
    assert (after.deleted_at, after.deleted_with_source) == (None, False)


async def test_없는_문서와_삭제_기록은_404_document_not_found다(pipeline: Pipeline) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    await pipeline.make_tombstone(document_id)

    assert await _refused(pipeline, new_id()) is ErrorCode.DOCUMENT_NOT_FOUND
    assert await _refused(pipeline, document_id) is ErrorCode.DOCUMENT_NOT_FOUND


async def test_지워지지_않은_문서는_409_document_not_deleted다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)

    assert await _refused(pipeline, ingested.document_id) is ErrorCode.DOCUMENT_NOT_DELETED
    assert (await _document(pipeline, ingested.document_id)).deleted_at is None


async def test_두_번째_되살리기는_409_document_not_deleted다(pipeline: Pipeline) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    await _restore(pipeline, document_id)

    assert await _refused(pipeline, document_id) is ErrorCode.DOCUMENT_NOT_DELETED


async def test_가져오는_원천의_문서는_409_wrong_source_kind다(pipeline: Pipeline) -> None:
    pulled = Source(
        new_id(),
        "가져옴",
        SourceKind.PULL,
        NOW,
        connector="server_path",
        config={"folder": "x"},
        group_id=pipeline.group.id,
        exclude_patterns=(),
    )
    document = make_document(pulled, pipeline.group, "a.pdf", deleted_at=NOW)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(pulled)
        await transaction.documents.add(document)

    assert await _refused(pipeline, document.id) is ErrorCode.WRONG_SOURCE_KIND
    assert (await _document(pipeline, document.id)).deleted_at == NOW


async def test_지운_원천의_문서는_409_source_deleted다(pipeline: Pipeline) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.lock_source(pipeline.source.id)
        await transaction.catalog.mark_source_deleted(pipeline.source.id, NOW)

    assert await _refused(pipeline, document_id) is ErrorCode.SOURCE_DELETED
    assert (await _document(pipeline, document_id)).deleted_at is not None


async def test_보관_기간이_지났어도_정리_작업이_아직_지우지_않았으면_되살린다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE documents SET deleted_at = :long_ago WHERE id = :document"),
            {"long_ago": NOW.replace(year=NOW.year - 1), "document": document_id},
        )

    restored = await _restore(pipeline, document_id)

    assert restored.document_id == document_id
    assert (await _document(pipeline, document_id)).deleted_at is None


async def test_원천을_지우는_요청이_먼저_잡은_원천이면_되살리기는_기다렸다_source_deleted로_끝난다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.lock_source(pipeline.source.id)
        await transaction.catalog.mark_source_deleted(pipeline.source.id, NOW)
        # 삭제 요청의 작업 단위가 아직 커밋하지 않았다. 이때 온 되살리기는 원천 행을 기다린다.
        crossing = asyncio.create_task(_refused(pipeline, document_id))
        await asyncio.sleep(0.3)
        assert not crossing.done()

    async with asyncio.timeout(DEADLINE_SECONDS):
        assert await crossing is ErrorCode.SOURCE_DELETED
    assert (await _document(pipeline, document_id)).deleted_at is not None


async def test_문서_행을_잡은_작업이_문서를_정리하면_기다린_되살리기는_404로_끝난다(
    pipeline: Pipeline,
) -> None:
    document_id = await _indexed_and_deleted(pipeline)
    async with pipeline.unit_of_work.begin() as transaction:
        locked = await transaction.documents.lock(document_id)
        assert locked is not None
        # 정리 작업이 문서 행을 잡은 채 완전히 지우는 중이다. 이때 온 되살리기는 문서 행을 기다린다.
        crossing = asyncio.create_task(_refused(pipeline, document_id))
        await asyncio.sleep(0.3)
        assert not crossing.done()
        await transaction.documents.update(replace(locked, purged_at=NOW))

    async with asyncio.timeout(DEADLINE_SECONDS):
        assert await crossing is ErrorCode.DOCUMENT_NOT_FOUND
    assert (await _document(pipeline, document_id)).deleted_at is not None
