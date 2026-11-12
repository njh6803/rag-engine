"""삭제, 되살림, 묘비(명세 "삭제, 되살림, 묘비", 티켓 11).

실제 테스트 PostgreSQL, 실제 DOCX 파서 자식 프로세스, 실제 청커와 Kiwi 위에서 돈다. 임베딩 서버만
`TeiStub`이다. 정리 작업은 core에 없어 묘비 행은 시험이 데이터베이스에 직접 만든다.
"""

from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import Pipeline

from rag_engine.app import delete_document as delete_module
from rag_engine.app import ingest as ingest_module
from rag_engine.app.index_document import index_document
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IngestAction,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import Transaction

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
EMBEDDINGS = "/v1/embeddings"


async def _work(pipeline: Pipeline) -> None:
    await index_document(pipeline.deps(), await pipeline.claim())


async def _document(pipeline: Pipeline, document_id: UUID) -> Document:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
    assert document is not None
    return document


async def _state(pipeline: Pipeline, document_id: UUID, version: IndexVersion) -> IndexState | None:
    async with pipeline.unit_of_work.begin() as transaction:
        return await transaction.index.get_state(document_id, version.id)


def _blobs(root: Path) -> list[Path]:
    return sorted(path for path in (root / "blobs").rglob("*") if path.is_file())


async def test_삭제하면_조각이_보관_표로_옮겨지고_색인_상태와_대기_작업이_사라진다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    indexed = await pipeline.chunk_texts(ingested.document_id)
    assert indexed != []
    await pipeline.ingest(출장)
    before = await _document(pipeline, ingested.document_id)
    assert "queued" in await pipeline.job_statuses(ingested.document_id)
    pipeline.clock[0] = NOW + timedelta(days=1)

    await pipeline.delete()

    after = await _document(pipeline, ingested.document_id)
    assert (after.deleted_at, after.generation) == (NOW + timedelta(days=1), before.generation + 1)
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.archived_texts(ingested.document_id) == indexed
    assert await _state(pipeline, ingested.document_id, pipeline.version) is None
    assert "queued" not in await pipeline.job_statuses(ingested.document_id)


async def test_삭제는_건설_중인_판의_색인_상태를_지우고_그_판의_전환_검사를_부른다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    building = await pipeline.add_building_version()
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.index.save_state(
            IndexState(
                document_id=ingested.document_id,
                index_version_id=building.id,
                status=IndexStateStatus.PENDING,
                chunk_count=0,
                built_content_hash=None,
                error_code=None,
                updated_at=NOW,
            )
        )
    checked: list[IndexVersion] = []

    async def record(transaction: Transaction, version: IndexVersion) -> None:
        checked.append(version)

    monkeypatch.setattr(delete_module, "check_version_switch", record)

    await pipeline.delete()

    assert await _state(pipeline, ingested.document_id, building) is None
    assert [version.id for version in checked] == [building.id]


async def test_이미_지운_문서를_다시_지워도_문서를_바꾸지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await pipeline.delete()
    deleted = await _document(pipeline, ingested.document_id)
    pipeline.clock[0] = NOW + timedelta(days=1)

    await pipeline.delete()

    assert await _document(pipeline, ingested.document_id) == deleted


async def test_없는_키와_묘비_행의_키를_지우면_document_not_found다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await pipeline.make_tombstone(ingested.document_id)

    for key in ("없는.docx", "규정.docx"):
        with pytest.raises(RequestError) as caught:
            await pipeline.delete(key)
        assert caught.value.code is ErrorCode.DOCUMENT_NOT_FOUND


async def test_같은_내용을_되살리면_보관_조각이_돌아와_임베딩과_작업_없이_바로_검색된다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    indexed = await pipeline.chunk_texts(ingested.document_id)
    await pipeline.delete()
    deleted = await _document(pipeline, ingested.document_id)
    embeddings = pipeline.stub.count(EMBEDDINGS)

    restored = await pipeline.ingest(휴가)

    assert (restored.action, restored.document_id) == (IngestAction.RESTORED, ingested.document_id)
    assert restored.job_id is None
    document = await _document(pipeline, ingested.document_id)
    assert (document.deleted_at, document.generation) == (None, deleted.generation + 1)
    assert await pipeline.chunk_texts(ingested.document_id) == indexed
    assert await pipeline.archived_texts(ingested.document_id) == []
    state = await _state(pipeline, ingested.document_id, pipeline.version)
    assert state is not None and state.status is IndexStateStatus.INDEXED
    assert (state.chunk_count, state.built_content_hash) == (len(indexed), document.content_hash)
    assert pipeline.stub.count(EMBEDDINGS) == embeddings
    assert "queued" not in await pipeline.job_statuses(ingested.document_id)
    assert len(_blobs(tmp_path)) == 1


async def test_다른_그룹으로_되살리면_대상이_아닌_판의_보관_조각을_지우고_새_판에_pending을_쓴다(
    pipeline: Pipeline,
) -> None:
    moved = await pipeline.add_group("팀B")
    _, other = await pipeline.add_knowledge_base("b", moved)
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    await pipeline.delete()

    restored = await pipeline.ingest(휴가, group="팀B")

    assert (restored.action, restored.document_id) == (IngestAction.RESTORED, ingested.document_id)
    assert restored.job_id is not None
    document = await _document(pipeline, ingested.document_id)
    assert (document.group_id, document.deleted_at) == (moved.id, None)
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.archived_texts(ingested.document_id) == []
    assert await _state(pipeline, ingested.document_id, pipeline.version) is None
    pending = await _state(pipeline, ingested.document_id, other)
    assert pending is not None and pending.status is IndexStateStatus.PENDING
    await _work(pipeline)
    assert await pipeline.chunk_texts(ingested.document_id, other) != []


async def test_되돌릴_조각이_없는_판이_건설_중이면_작업만_넣고_pending을_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    building = await pipeline.add_building_version()
    await pipeline.keep_pending(building)
    await pipeline.delete()

    restored = await pipeline.ingest(휴가)

    assert restored.action is IngestAction.RESTORED and restored.job_id is not None
    assert await _state(pipeline, ingested.document_id, building) is None
    current = await _state(pipeline, ingested.document_id, pipeline.version)
    assert current is not None and current.status is IndexStateStatus.INDEXED
    assert await pipeline.chunk_texts(ingested.document_id) != []


async def test_건설_중인_판에_보관_조각이_돌아오면_indexed를_쓰고_전환_검사는_부르지_않는다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    building = await pipeline.add_building_version()
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    await pipeline.delete()
    checked: list[IndexVersion] = []

    async def record(transaction: Transaction, version: IndexVersion) -> None:
        checked.append(version)

    monkeypatch.setattr(ingest_module, "check_version_switch", record)

    restored = await pipeline.ingest(휴가)

    assert restored.action is IngestAction.RESTORED and restored.job_id is None
    state = await _state(pipeline, ingested.document_id, building)
    assert state is not None and state.status is IndexStateStatus.INDEXED
    assert checked == []


async def test_내용이_다른_수집으로_되살리면_보관_조각을_지우고_갱신으로_색인한다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    (old_blob,) = _blobs(tmp_path)
    await pipeline.delete()

    restored = await pipeline.ingest(출장)

    assert (restored.action, restored.document_id) == (IngestAction.RESTORED, ingested.document_id)
    assert restored.job_id is not None
    document = await _document(pipeline, ingested.document_id)
    assert (document.deleted_at, document.status) == (None, DocumentStatus.RECEIVED)
    assert await pipeline.archived_texts(ingested.document_id) == []
    assert await pipeline.chunk_texts(ingested.document_id) == []
    (new_blob,) = _blobs(tmp_path)
    assert new_blob != old_blob and document.blob_path.endswith(new_blob.name)
    await _work(pipeline)
    texts = await pipeline.chunk_texts(ingested.document_id)
    assert any("출장비" in text for text in texts)


async def test_색인되기_전에_지운_갱신_내용을_같은_내용으로_되살리면_옛_글은_돌아오지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    await pipeline.ingest(출장)
    await pipeline.delete()

    restored = await pipeline.ingest(출장)

    assert restored.action is IngestAction.RESTORED and restored.job_id is not None
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.archived_texts(ingested.document_id) == []
    pending = await _state(pipeline, ingested.document_id, pipeline.version)
    assert pending is not None and pending.status is IndexStateStatus.PENDING
    await _work(pipeline)
    texts = await pipeline.chunk_texts(ingested.document_id)
    assert any("출장비" in text for text in texts)
    assert not any("연차휴가" in text for text in texts)


async def test_색인_전에_지운_문서를_옛_내용으로_되살려_조각이_돌아오면_문서_상태도_parsed다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    await pipeline.ingest(출장)
    await pipeline.ingest(휴가)
    assert (await _document(pipeline, ingested.document_id)).status is DocumentStatus.RECEIVED
    await pipeline.delete()

    restored = await pipeline.ingest(휴가)

    assert restored.action is IngestAction.RESTORED and restored.job_id is None
    assert await pipeline.chunk_texts(ingested.document_id) != []
    document = await _document(pipeline, ingested.document_id)
    assert document.status is DocumentStatus.PARSED


async def test_묘비_행과_같은_키가_오면_그_행을_다시_써_UUID와_세대를_잇고_created를_낸다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    await pipeline.make_tombstone(ingested.document_id)
    tombstone = await _document(pipeline, ingested.document_id)
    assert tombstone.purged_at is not None
    pipeline.clock[0] = NOW + timedelta(days=60)

    created = await pipeline.ingest(출장)

    assert (created.action, created.document_id) == (IngestAction.CREATED, ingested.document_id)
    assert created.job_id is not None
    document = await _document(pipeline, ingested.document_id)
    assert (document.deleted_at, document.purged_at) == (None, None)
    assert (document.generation, document.status) == (
        tombstone.generation + 1,
        DocumentStatus.RECEIVED,
    )
    assert (document.created_at, document.modified_at) == (tombstone.created_at, pipeline.clock[0])
    assert document.blob_path != tombstone.blob_path
    assert _blobs(tmp_path) == [tmp_path / document.blob_path]
    await _work(pipeline)
    assert any("출장비" in text for text in await pipeline.chunk_texts(ingested.document_id))
