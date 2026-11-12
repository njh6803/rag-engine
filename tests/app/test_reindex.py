"""재색인 시작과 판 전환, 물러난 판의 정리, 토크나이저 판만 다른 재색인(명세 "수집 파이프라인과
작업", 티켓 14).

실제 테스트 PostgreSQL, 실제 파서 자식 프로세스, 실제 청커와 Kiwi 위에서 돈다. 임베딩 서버만
`TeiStub`이다. "재색인 필요"는 지식베이스 행의 청킹 설정을 직접 고치거나(청킹 해시가 달라진다)
키워드 규칙 판 상수를 바꿔(토크나이저 판만 달라진다) 만든다.
"""

import asyncio
from uuid import UUID

import pytest
import sqlalchemy as sa
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FailingRunner
from tests.support.pipeline import Pipeline
from tests.support.reindex import (
    NEW_CHUNK_TOKENS,
    chunk_count,
    index_all_queued,
    index_exists,
    ingest_and_index,
    keywords_of,
    set_chunk_tokens,
    start,
    state_status,
    version_of,
    versions_of,
)

from rag_engine.adapters import index_elements
from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.adapters.postgres.index_maintenance import PostgresIndexMaintenance
from rag_engine.app.admin_knowledge_bases import get_knowledge_base_detail
from rag_engine.app.index_document import index_document
from rag_engine.app.reindex import start_reindex
from rag_engine.app.retire_cleanup import clean_retired_versions
from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.entities import IndexStateStatus, IndexVersionStatus
from rag_engine.domain.errors import ErrorCode, PermanentFailure, RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import process_job

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
EMBEDDINGS = "/v1/embeddings"


async def _statuses(pipeline: Pipeline) -> dict[UUID, IndexVersionStatus]:
    return {version.id: version.status for version in await versions_of(pipeline)}


async def test_모르는_지식베이스는_재색인을_시작하지_못한다(pipeline: Pipeline) -> None:
    with pytest.raises(RequestError) as raised:
        await start_reindex(
            pipeline.unit_of_work,
            PostgresIndexMaintenance(pipeline.engine),
            compute_index_elements,
            "없는-지식베이스",
            request_id=new_id(),
            now=NOW,
        )

    assert raised.value.code is ErrorCode.KNOWLEDGE_BASE_NOT_FOUND


async def test_문서가_없으면_새_판을_만들자마자_전환하고_옛_판을_물린다(pipeline: Pipeline) -> None:
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)

    started = await start(pipeline)

    assert started.jobs_enqueued == 0
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id == started.index_version_id
    assert current.chunking.max_tokens == NEW_CHUNK_TOKENS
    retired = await version_of(pipeline, IndexVersionStatus.RETIRED)
    assert retired is not None and retired.id == pipeline.version.id
    assert await version_of(pipeline, IndexVersionStatus.BUILDING) is None


async def test_살아_있는_문서마다_pending과_작업을_넣고_지운_문서는_넣지_않는다(
    pipeline: Pipeline,
) -> None:
    kept = await ingest_and_index(pipeline, 휴가, "휴가.docx")
    deleted = await ingest_and_index(pipeline, 출장, "출장.docx")
    await pipeline.delete("출장.docx")
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)

    started = await start(pipeline)

    building = await version_of(pipeline, IndexVersionStatus.BUILDING)
    assert building is not None and building.id == started.index_version_id, (
        f"pending이 있는데 시작하자마자 전환했다: {await _statuses(pipeline)}"
    )
    assert started.jobs_enqueued == 1
    assert await state_status(pipeline, kept, building) is IndexStateStatus.PENDING
    assert await state_status(pipeline, deleted, building) is None
    assert (await pipeline.job_statuses(kept))[-1] == "queued"


async def test_대기_작업이_있는_문서에는_작업을_더_넣지_않고_그_작업이_새_판도_채운다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)

    started = await start(pipeline)

    assert started.jobs_enqueued == 0, (
        f"대기 작업이 있는데 작업을 {started.jobs_enqueued}개 더 넣었다"
    )
    assert await pipeline.job_statuses(ingested.document_id) == ["queued"]
    building = await version_of(pipeline, IndexVersionStatus.BUILDING)
    assert building is not None
    await index_document(pipeline.deps(), await pipeline.claim())
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id == building.id, (
        f"마지막 색인 뒤에도 현재 판이 옛 판이다: {await _statuses(pipeline)}"
    )
    assert await pipeline.chunk_texts(ingested.document_id, current) != []


async def test_건설_중인_판이_있으면_두_번째_재색인은_거절한다(pipeline: Pipeline) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)

    with pytest.raises(RequestError) as raised:
        await start(pipeline)

    assert raised.value.code is ErrorCode.REINDEX_IN_PROGRESS
    assert len(await versions_of(pipeline)) == 2


async def test_마지막_pending이_사라지면_새_판이_현재가_되고_옛_판은_물러난다(
    pipeline: Pipeline,
) -> None:
    first = await ingest_and_index(pipeline, 휴가, "휴가.docx")
    second = await ingest_and_index(pipeline, 출장, "출장.docx")
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    started = await start(pipeline)
    building = await version_of(pipeline, IndexVersionStatus.BUILDING)
    assert building is not None

    await index_document(pipeline.deps(), await pipeline.claim())

    assert await version_of(pipeline, IndexVersionStatus.BUILDING) is not None
    await index_document(pipeline.deps(), await pipeline.claim())

    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id == started.index_version_id
    retired = await version_of(pipeline, IndexVersionStatus.RETIRED)
    assert retired is not None and retired.id == pipeline.version.id
    for document_id in (first, second):
        assert await state_status(pipeline, document_id, current) is IndexStateStatus.INDEXED


async def test_전환한_뒤에_옛_상태로_전환_검사를_불러도_아무것도_바꾸지_않는다(
    pipeline: Pipeline,
) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)
    building = await version_of(pipeline, IndexVersionStatus.BUILDING)
    assert building is not None
    await index_all_queued(pipeline)
    # 두 번째 재색인까지 끝나면 처음 건설 중이던 판은 물러난 판이다. 옛 상태로 부른 검사가 그 판을
    # 현재 판으로 되살리지 않아야 한다.
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS * 2)
    await start(pipeline)
    await index_all_queued(pipeline)
    before = await _statuses(pipeline)
    assert before[building.id] is IndexVersionStatus.RETIRED

    async with pipeline.unit_of_work.begin() as transaction:
        await check_version_switch(transaction, building)

    assert await _statuses(pipeline) == before, (
        f"옛 상태의 검사가 판을 바꿨다: {await _statuses(pipeline)}"
    )


async def test_pending이_남아_있는_사이_전환_검사는_전환하지_않는다(pipeline: Pipeline) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)
    building = await version_of(pipeline, IndexVersionStatus.BUILDING)
    assert building is not None

    async with pipeline.unit_of_work.begin() as transaction:
        await check_version_switch(transaction, building)

    assert await version_of(pipeline, IndexVersionStatus.BUILDING) is not None
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id == pipeline.version.id


async def test_문서가_영구_실패해도_pending이_없으면_전환하고_failed는_그대로_남는다(
    pipeline: Pipeline,
) -> None:
    ingested = await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)

    with pytest.raises(PermanentFailure) as raised:
        await index_document(
            pipeline.deps(parse_runner=FailingRunner(ErrorCode.PARSE_FAILED)),
            await pipeline.claim(),
        )

    assert raised.value.code is ErrorCode.PARSE_FAILED, f"오류 코드가 {raised.value.code}로 나왔다"
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id != pipeline.version.id
    assert await state_status(pipeline, ingested, current) is IndexStateStatus.FAILED


async def test_물러난_판의_조각과_색인은_정리가_지우고_다시_불러도_아무것도_하지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await ingest_and_index(pipeline, 휴가, "휴가.docx")
    await ingest_and_index(pipeline, 출장, "출장.docx")
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)
    await index_all_queued(pipeline)
    maintenance = PostgresIndexMaintenance(pipeline.engine)
    old = pipeline.version
    stored = await chunk_count(pipeline, old)
    # 묶음 크기가 1이므로 조각이 둘 이상이어야 묶음을 되풀이해 지우는지 볼 수 있다.
    assert stored >= 2 and await index_exists(pipeline, old)

    cleaned = await clean_retired_versions(maintenance, batch_chunks=1)

    deleted = [(c.index_version_id, c.chunks_deleted) for c in cleaned]
    assert deleted == [(old.id, stored)], (
        f"묶음 정리가 지운 조각 {[count for _, count in deleted]}개, 저장된 조각 {stored}개"
    )
    left = await chunk_count(pipeline, old)
    assert left == 0, f"정리한 뒤에도 물러난 판에 조각 {left}개가 남았다"
    still = await index_exists(pipeline, old)
    assert not still, f"정리한 뒤에도 물러난 판의 HNSW 색인이 남았다: {still}"
    assert await clean_retired_versions(maintenance) == []
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and await pipeline.chunk_texts(ingested, current) != []
    assert await index_exists(pipeline, current)


async def test_작업자가_마지막_작업을_끝내면_물러난_판을_바로_정리한다(pipeline: Pipeline) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)

    await process_job(pipeline.deps(), await pipeline.claim())

    assert await chunk_count(pipeline, pipeline.version) == 0
    assert not await index_exists(pipeline, pipeline.version)


async def test_판마다_자기_청킹_설정으로_조각을_낸다(pipeline: Pipeline) -> None:
    paragraphs = [f"{n}번째 규정은 휴가를 신청하는 절차와 승인 기준을 설명한다." for n in range(40)]
    ingested = await ingest_and_index(pipeline, docx_bytes("제1조 휴가", *paragraphs))
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)

    await index_all_queued(pipeline)

    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id != pipeline.version.id
    old_count = len(await pipeline.chunk_texts(ingested, pipeline.version))
    new_count = len(await pipeline.chunk_texts(ingested, current))
    assert old_count >= 1 and new_count > old_count, (
        f"새 판의 조각이 더 많지 않다: 옛 판 {old_count}개, 새 판 {new_count}개"
    )


async def test_토크나이저_판만_다르면_조각과_임베딩을_복사하고_키워드만_다시_만든다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingested = await ingest_and_index(pipeline, 휴가)
    embedded_before = pipeline.stub.count(EMBEDDINGS)
    monkeypatch.setattr(index_elements, "KEYWORD_RULES_VERSION", "2")
    started = await start(pipeline)
    assert started.jobs_enqueued == 1
    building = await version_of(pipeline, IndexVersionStatus.BUILDING)
    assert building is not None
    assert building.chunking_hash == pipeline.version.chunking_hash
    assert building.tokenizer_version != pipeline.version.tokenizer_version

    await index_document(pipeline.deps(), await pipeline.claim())

    # 작업은 살아 있는 판마다 재료를 만들므로 현재 판은 평소대로 임베딩을 한 번 부른다.
    # 복사하는 건설 중인 판은 임베딩을 부르지 않는다.
    assert pipeline.stub.count(EMBEDDINGS) == embedded_before + 1
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id == building.id
    assert await pipeline.chunk_texts(ingested, current) == await pipeline.chunk_texts(
        ingested, pipeline.version
    )
    assert await keywords_of(pipeline, ingested, current) == await keywords_of(
        pipeline, ingested, pipeline.version
    )
    assert await state_status(pipeline, ingested, current) is IndexStateStatus.INDEXED


async def test_복사한_조각의_임베딩과_위치는_옛_판과_같다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingested = await ingest_and_index(pipeline, 휴가)
    monkeypatch.setattr(index_elements, "KEYWORD_RULES_VERSION", "2")
    await start(pipeline)
    await index_document(pipeline.deps(), await pipeline.claim())
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None

    async with pipeline.engine.connect() as connection:
        rows = (
            await connection.execute(
                sa.text(
                    "SELECT index_version_id, embedding::text AS embedding, location::text AS"
                    " location, token_count, source_content_hash FROM chunks WHERE document_id"
                    " = :document ORDER BY ordinal, index_version_id"
                ),
                {"document": ingested},
            )
        ).all()

    by_version = {
        version_id: [tuple(row)[1:] for row in rows if row[0] == version_id]
        for version_id in (pipeline.version.id, current.id)
    }
    assert by_version[current.id] == by_version[pipeline.version.id] != []


async def test_옛_판의_조각이_옛_내용이면_복사하지_않고_새로_청킹하고_임베딩한다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingested = await ingest_and_index(pipeline, 휴가)
    monkeypatch.setattr(index_elements, "KEYWORD_RULES_VERSION", "2")
    await start(pipeline)
    await pipeline.ingest(출장)
    embedded_before = pipeline.stub.count(EMBEDDINGS)

    await index_document(pipeline.deps(), await pipeline.claim())

    # 현재 판과 건설 중인 판이 각자 임베딩을 한 번씩 부른다.
    calls = pipeline.stub.count(EMBEDDINGS) - embedded_before
    assert calls == 2, f"임베딩 호출이 {calls}번 늘어 기대한 2번과 다르다"
    current = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert current is not None and current.id != pipeline.version.id
    texts = await pipeline.chunk_texts(ingested, current)
    assert any("출장비" in text for text in texts)


async def test_다음_재색인_시작이_물러난_판에_남은_조각을_먼저_정리한다(pipeline: Pipeline) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    await index_all_queued(pipeline)
    old = pipeline.version
    assert await chunk_count(pipeline, old) > 0 and await index_exists(pipeline, old)
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS * 2)

    await start(pipeline)

    left = await chunk_count(pipeline, old)
    assert left == 0, f"다시 시작한 뒤에도 물러난 판에 조각 {left}개가 남았다"
    assert not await index_exists(pipeline, old)


async def test_색인이_이미_없어도_남은_조각을_정리하고_색인_지우기는_두_번_불러도_된다(
    pipeline: Pipeline,
) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    await index_all_queued(pipeline)
    maintenance = PostgresIndexMaintenance(pipeline.engine)
    old = pipeline.version

    await maintenance.drop_version_index(old.id)
    await maintenance.drop_version_index(old.id)
    cleaned = await clean_retired_versions(maintenance)

    assert [c.index_version_id for c in cleaned] == [old.id]
    assert await chunk_count(pipeline, old) == 0


async def test_정리를_겹쳐_돌려도_오류_없이_조각을_한_번씩만_지운다(pipeline: Pipeline) -> None:
    await ingest_and_index(pipeline, 휴가, "휴가.docx")
    await ingest_and_index(pipeline, 출장, "출장.docx")
    await set_chunk_tokens(pipeline, NEW_CHUNK_TOKENS)
    await start(pipeline)
    await index_all_queued(pipeline)
    maintenance = PostgresIndexMaintenance(pipeline.engine)
    old = pipeline.version
    stored = await chunk_count(pipeline, old)
    assert stored >= 2

    first, second = await asyncio.gather(
        clean_retired_versions(maintenance, batch_chunks=1),
        clean_retired_versions(maintenance, batch_chunks=1),
    )

    deleted = sum(c.chunks_deleted for cleaned in (first, second) for c in cleaned)
    assert deleted == stored, f"두 정리가 지운 조각이 모두 {deleted}개, 저장된 조각은 {stored}개"
    assert await chunk_count(pipeline, old) == 0
    assert not await index_exists(pipeline, old)


async def test_건설_중인_판의_진행은_색인_상태를_상태마다_센다(pipeline: Pipeline) -> None:
    await ingest_and_index(pipeline, 휴가, "휴가.docx")
    await ingest_and_index(pipeline, 출장, "출장.docx")
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    with pytest.raises(PermanentFailure) as raised:
        await index_document(
            pipeline.deps(parse_runner=FailingRunner(ErrorCode.PARSE_FAILED)),
            await pipeline.claim(),
        )

    assert raised.value.code is ErrorCode.PARSE_FAILED, f"오류 코드가 {raised.value.code}로 나왔다"
    detail = await get_knowledge_base_detail(
        pipeline.unit_of_work, compute_index_elements, pipeline.knowledge_base.name
    )

    building = detail.report.building
    assert building is not None
    assert (building.pending, building.indexed, building.failed, building.total) == (1, 0, 1, 2)
    assert detail.report.reindex_needed is True
