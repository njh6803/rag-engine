"""수집의 갱신 갈래(명세 "수집 API"의 그룹 변경과 `requeued`, 티켓 10).

실제 테스트 PostgreSQL, 실제 DOCX 파서 자식 프로세스, 실제 청커와 Kiwi 위에서 돈다. 임베딩 서버만
`TeiStub`이다. 둘째 그룹과 지식베이스(첫 판 포함)는 `Catalog` 어댑터로 만든다.
"""

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
import sqlalchemy as sa
from tests.records import NOW, make_index_version
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import Pipeline

from rag_engine.app import ingest as ingest_module
from rag_engine.app.index_document import index_document
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    IngestAction,
)
from rag_engine.domain.errors import ErrorCode

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")


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


async def _save_state(pipeline: Pipeline, state: IndexState) -> None:
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.index.save_state(state)


def _failed(document: Document, version: IndexVersion) -> IndexState:
    return IndexState(
        document_id=document.id,
        index_version_id=version.id,
        status=IndexStateStatus.FAILED,
        chunk_count=0,
        built_content_hash=None,
        error_code=ErrorCode.EMBEDDING_UNAVAILABLE,
        updated_at=NOW,
    )


async def _chunk_groups(pipeline: Pipeline, document_id: UUID) -> list[tuple[UUID, UUID]]:
    """조각마다 (색인 판, 복사 칸의 그룹)."""
    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                "SELECT DISTINCT index_version_id, group_id FROM chunks WHERE document_id = :id"
                " ORDER BY index_version_id"
            ),
            {"id": document_id},
        )
        return [(row[0], row[1]) for row in rows]


def _blobs(root: Path) -> list[Path]:
    return sorted(path for path in (root / "blobs").rglob("*") if path.is_file())


async def test_그룹을_바꾸면_빠지는_지식베이스의_조각과_색인_상태를_그_커밋으로_지운다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    moved = await pipeline.add_group("팀B")
    _, other = await pipeline.add_knowledge_base("b", moved)

    result = await pipeline.ingest(휴가, group="팀B")

    assert result.action is IngestAction.UPDATED
    assert result.document_id == ingested.document_id
    assert result.job_id is not None
    document = await _document(pipeline, ingested.document_id)
    assert (document.group_id, document.generation) == (moved.id, 3)
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await _state(pipeline, ingested.document_id, pipeline.version) is None
    assert await _state(pipeline, ingested.document_id, other) is None


async def test_그룹이_바뀌어도_두_그룹이_모두_든_지식베이스의_조각은_남고_복사_칸만_새_그룹이_된다(
    pipeline: Pipeline,
) -> None:
    moved = await pipeline.add_group("팀B")
    _, shared = await pipeline.add_knowledge_base("공용", pipeline.group, moved)
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    assert {version for version, _ in await _chunk_groups(pipeline, ingested.document_id)} == {
        pipeline.version.id,
        shared.id,
    }

    await pipeline.ingest(휴가, group="팀B")

    assert await _chunk_groups(pipeline, ingested.document_id) == [(shared.id, moved.id)]
    state = await _state(pipeline, ingested.document_id, shared)
    assert state is not None and state.status is IndexStateStatus.INDEXED


async def test_그룹이_바뀌면_물러난_판의_조각도_복사_칸을_새_그룹으로_고친다(
    pipeline: Pipeline,
) -> None:
    moved = await pipeline.add_group("팀B")
    _, shared = await pipeline.add_knowledge_base("공용", pipeline.group, moved)
    retired = replace(
        make_index_version(pipeline.knowledge_base, IndexVersionStatus.RETIRED),
        embedding_dimensions=pipeline.version.embedding_dimensions,
    )
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.add_index_version(retired)
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text(
                "INSERT INTO chunks (id, document_id, index_version_id, ordinal, text,"
                " token_count, location, embedding, keywords, source_content_hash, group_id,"
                " updated_at) SELECT gen_random_uuid(), document_id, :retired, ordinal, text,"
                " token_count, location, embedding, keywords, source_content_hash, group_id,"
                " updated_at FROM chunks WHERE document_id = :id AND index_version_id = :shared"
            ),
            {"retired": retired.id, "id": ingested.document_id, "shared": shared.id},
        )

    await pipeline.ingest(휴가, group="팀B")

    groups = await _chunk_groups(pipeline, ingested.document_id)
    assert {group for _, group in groups} == {moved.id}
    assert retired.id in {version for version, _ in groups}


async def test_빠지는_지식베이스에_건설_중인_판이_있으면_그_판도_지우고_전환_검사를_부른다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    building = await pipeline.add_building_version()
    document = await _document(pipeline, ingested.document_id)
    await _save_state(
        pipeline,
        replace(_failed(document, building), status=IndexStateStatus.PENDING, error_code=None),
    )
    await pipeline.add_group("팀B")
    checked: list[IndexVersion] = []

    async def record_check(_transaction: object, version: IndexVersion) -> None:
        checked.append(version)

    monkeypatch.setattr(ingest_module, "check_version_switch", record_check)

    await pipeline.ingest(휴가, group="팀B")

    assert await _state(pipeline, ingested.document_id, building) is None
    assert [version.id for version in checked] == [building.id]


async def test_그룹을_바꿔도_들어오는_지식베이스의_건설_중인_판에는_전환_검사를_부르지_않는다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    moved = await pipeline.add_group("팀B")
    entering, _ = await pipeline.add_knowledge_base("b", moved)
    async with pipeline.unit_of_work.begin() as transaction:
        building = replace(
            make_index_version(entering, IndexVersionStatus.BUILDING),
            embedding_dimensions=pipeline.version.embedding_dimensions,
        )
        await transaction.catalog.add_index_version(building)
    checked: list[IndexVersion] = []

    async def record_check(_transaction: object, version: IndexVersion) -> None:
        checked.append(version)

    monkeypatch.setattr(ingest_module, "check_version_switch", record_check)

    await pipeline.ingest(휴가, group="팀B")

    assert checked == []
    assert await _state(pipeline, ingested.document_id, building) is None


async def test_그룹과_내용을_함께_바꾸면_새_원본을_가리키고_옛_원본을_지운다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    moved = await pipeline.add_group("팀B")
    await pipeline.add_knowledge_base("b", moved)

    result = await pipeline.ingest(출장, group="팀B")

    assert result.action is IngestAction.UPDATED
    document = await _document(pipeline, ingested.document_id)
    assert (document.group_id, document.status) == (moved.id, DocumentStatus.RECEIVED)
    (blob,) = _blobs(tmp_path)
    assert document.blob_path == f"blobs/{document.id}/{blob.name}"
    assert blob.read_bytes() == 출장


async def test_그룹만_바뀐_갱신은_새_원본을_지우고_문서_행은_옛_원본을_가리킨다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    ingested = await pipeline.ingest(휴가)
    before = await _document(pipeline, ingested.document_id)
    moved = await pipeline.add_group("팀B")
    await pipeline.add_knowledge_base("b", moved)

    result = await pipeline.ingest(휴가, group="팀B")

    assert result.action is IngestAction.UPDATED
    document = await _document(pipeline, ingested.document_id)
    assert document.blob_path == before.blob_path
    (blob,) = _blobs(tmp_path)
    assert document.blob_path == f"blobs/{document.id}/{blob.name}"


async def test_그룹만_바뀐_갱신은_파싱을_건너뛰고_새_지식베이스에_조각을_쓴다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    moved = await pipeline.add_group("팀B")
    _, other = await pipeline.add_knowledge_base("b", moved)
    await pipeline.ingest(휴가, group="팀B")

    await _work(pipeline)

    assert await pipeline.chunk_texts(ingested.document_id, other) != []
    assert await pipeline.chunk_texts(ingested.document_id) == []
    document = await _document(pipeline, ingested.document_id)
    assert (document.status, document.group_id) == (DocumentStatus.PARSED, moved.id)


async def test_그룹을_바꾸는_수집은_빠지는_지식베이스_행의_공유_잠금이_풀리길_기다린다(
    pipeline: Pipeline, empty_database_url: str
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    moved = await pipeline.add_group("팀B")
    await pipeline.add_knowledge_base("b", moved)

    with psycopg.connect(empty_database_url) as other:
        other.execute(
            "SELECT 1 FROM knowledge_bases WHERE id = %s FOR SHARE", [pipeline.knowledge_base.id]
        )
        task = asyncio.ensure_future(pipeline.ingest(휴가, group="팀B"))
        done, _ = await asyncio.wait({task}, timeout=1.0)
        assert not done
        other.rollback()
        result = await asyncio.wait_for(task, timeout=30)

    assert result.document_id == ingested.document_id


async def test_내용과_그룹이_같아도_문서가_failed이면_requeued로_세대를_올리고_작업을_넣는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(ingested.document_id)
        assert document is not None
        await transaction.documents.update(
            replace(
                document,
                status=DocumentStatus.FAILED,
                error_code=ErrorCode.ENCRYPTED_DOCUMENT,
                generation=4,
            )
        )
    await pipeline.claim()

    result = await pipeline.ingest(휴가)

    assert result.action is IngestAction.REQUEUED
    assert result.document_id == ingested.document_id
    assert result.job_id is not None and result.job_id != ingested.job_id
    document = await _document(pipeline, ingested.document_id)
    assert (document.generation, document.status, document.error_code) == (
        5,
        DocumentStatus.FAILED,
        ErrorCode.ENCRYPTED_DOCUMENT,
    )


async def test_살아_있는_판의_색인_상태가_failed이면_requeued이고_작업이_다시_색인한다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    document = await _document(pipeline, ingested.document_id)
    await _save_state(pipeline, _failed(document, pipeline.version))

    result = await pipeline.ingest(휴가)
    await _work(pipeline)

    assert result.action is IngestAction.REQUEUED and result.job_id is not None
    state = await _state(pipeline, ingested.document_id, pipeline.version)
    assert state is not None and state.status is IndexStateStatus.INDEXED
    assert any("연차휴가" in text for text in await pipeline.chunk_texts(ingested.document_id))


async def test_물러난_판의_실패한_색인_상태는_requeued로_세지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    document = await _document(pipeline, ingested.document_id)
    retired = replace(
        make_index_version(pipeline.knowledge_base, IndexVersionStatus.RETIRED),
        embedding_dimensions=pipeline.version.embedding_dimensions,
    )
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.add_index_version(retired)
    await _save_state(pipeline, _failed(document, retired))

    result = await pipeline.ingest(휴가)

    assert result.action is IngestAction.UNCHANGED and result.job_id is None


async def test_requeued는_새_원본을_지우고_메타데이터와_갱신일을_문서_행에_반영한다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    document = await _document(pipeline, ingested.document_id)
    await _save_state(pipeline, _failed(document, pipeline.version))
    newer = NOW.replace(year=2027)

    result = await pipeline.ingest(휴가, updated_at=newer)

    assert result.action is IngestAction.REQUEUED
    refreshed = await _document(pipeline, ingested.document_id)
    assert (refreshed.blob_path, refreshed.updated_at) == (document.blob_path, newer)
    (blob,) = _blobs(tmp_path)
    assert refreshed.blob_path == f"blobs/{refreshed.id}/{blob.name}"
