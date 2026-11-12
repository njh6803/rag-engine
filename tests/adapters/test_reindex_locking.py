"""재색인 시작의 잠금과 판 전환의 직렬화(명세 "수집 파이프라인과 작업", ADR 0009, 티켓 14).

연결 둘로 한쪽 작업 단위(재색인 시작)를 커밋 직전에 열어 둔 채 다른 쪽을 돌린다. 실제 테스트
PostgreSQL 위에서 지식베이스 행을 기다리는 것을 데이터베이스에서 보고, 교착 없이 끝나는지 본다.
"""

import asyncio

import pytest
import sqlalchemy as sa
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FailingRunner, FlakyUnitOfWork
from tests.support.pipeline import BACKOFF_BASE_SECONDS, LEASE_SECONDS, Pipeline
from tests.support.reindex import (
    MOMENT_SECONDS,
    building_version,
    current_version,
    held_knowledge_base_lock,
    index_exists,
    ingest_and_index,
    job_row_is_free,
    paused_reindex,
    set_chunk_tokens,
    start,
    state_status,
    version_of,
    versions_of,
    wait_for_lock_waiter,
)

from rag_engine.adapters.postgres.vector_index import version_index_name
from rag_engine.app.index_document import index_document
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.entities import IndexStateStatus, IndexVersion, IndexVersionStatus
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.worker.processing import process_job

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
ONE_ATTEMPT = RetryPolicy(max_attempts=1, backoff_base_seconds=BACKOFF_BASE_SECONDS)


async def test_재색인_중_삭제는_지식베이스_행에서_기다리고_새_판의_상태를_남기지_않는다(
    pipeline: Pipeline,
) -> None:
    document_id = await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)

    async with paused_reindex(pipeline):
        deleting = asyncio.create_task(pipeline.delete())
        await wait_for_lock_waiter(pipeline, deleting)

    await asyncio.wait_for(deleting, timeout=MOMENT_SECONDS)
    new = await current_version(pipeline)
    assert new.id != pipeline.version.id
    assert await state_status(pipeline, document_id, new) is None
    assert await version_of(pipeline, IndexVersionStatus.BUILDING) is None


async def test_재색인_중_수집은_지식베이스_행에서_기다리고_새_판에_pending을_남긴다(
    pipeline: Pipeline,
) -> None:
    document_id = await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)

    async with paused_reindex(pipeline):
        updating = asyncio.create_task(pipeline.ingest(출장))
        await wait_for_lock_waiter(pipeline, updating)

    ingested = await asyncio.wait_for(updating, timeout=MOMENT_SECONDS)
    assert ingested.document_id == document_id
    building = await building_version(pipeline)
    assert await state_status(pipeline, document_id, building) is IndexStateStatus.PENDING
    assert (await pipeline.job_statuses(document_id))[-1] == "queued"


async def test_재색인_중_소진은_지식베이스_행에서_기다리고_pending을_failed로_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    running = await pipeline.claim()
    await set_chunk_tokens(pipeline)

    async with paused_reindex(pipeline):
        flaky = FlakyUnitOfWork(pipeline.unit_of_work)
        exhausting = asyncio.create_task(
            process_job(pipeline.deps(unit_of_work=flaky, retry=ONE_ATTEMPT), running)
        )
        await wait_for_lock_waiter(pipeline, exhausting)

    await asyncio.wait_for(exhausting, timeout=MOMENT_SECONDS)
    building = await building_version(pipeline)
    # 재색인이 넣은 작업이 문서를 처음부터 맡으므로 소진한 옛 작업은 새 판 쪽을 쓰지 않는다.
    assert await state_status(pipeline, ingested.document_id, building) is IndexStateStatus.PENDING
    assert await pipeline.job_statuses(ingested.document_id) == ["failed", "queued"]


async def test_재색인_시작이_잠근_대기_작업은_작업자가_꺼내지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await set_chunk_tokens(pipeline)

    async with paused_reindex(pipeline):
        async with pipeline.unit_of_work.begin() as transaction:
            skipped = await transaction.jobs.claim("worker-2", NOW, LEASE_SECONDS)

    assert skipped is None
    claimed = await pipeline.claim("worker-2")
    assert claimed.document_id == ingested.document_id


async def test_마지막_두_문서를_동시에_끝내도_판은_한_번만_전환된다(pipeline: Pipeline) -> None:
    first = await ingest_and_index(pipeline, 휴가, "휴가.docx")
    second = await ingest_and_index(pipeline, 출장, "출장.docx")
    await set_chunk_tokens(pipeline)
    started = await start(pipeline)
    assert started.jobs_enqueued == 2
    jobs = [await pipeline.claim("worker-1"), await pipeline.claim("worker-2")]

    await asyncio.wait_for(
        asyncio.gather(*(index_document(pipeline.deps(), job) for job in jobs)),
        timeout=MOMENT_SECONDS,
    )

    versions = await versions_of(pipeline)
    assert sorted(version.status.value for version in versions) == ["current", "retired"]
    current = await current_version(pipeline)
    assert current.id == started.index_version_id
    for document_id in (first, second):
        assert await state_status(pipeline, document_id, current) is IndexStateStatus.INDEXED


async def test_전환_검사는_지식베이스_행을_잠그고_다른_연결이_쥔_동안_기다린다(
    pipeline: Pipeline,
) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    building = await building_version(pipeline)

    async with held_knowledge_base_lock(pipeline):
        checking = asyncio.create_task(_check(pipeline, building))
        await wait_for_lock_waiter(pipeline, checking)

    await asyncio.wait_for(checking, timeout=MOMENT_SECONDS)


async def test_색인_작업은_작업_행을_쥐기_전에_지식베이스_행을_잠그고_기다린다(
    pipeline: Pipeline,
) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    job = await pipeline.claim()

    async with held_knowledge_base_lock(pipeline):
        indexing = asyncio.create_task(index_document(pipeline.deps(), job))
        await wait_for_lock_waiter(pipeline, indexing)
        free = await job_row_is_free(pipeline, job.id)
        assert free, f"잠금을 기다리는 동안 작업 행을 쥐고 있다(작업 행이 비었나: {free})"

    await asyncio.wait_for(indexing, timeout=MOMENT_SECONDS)
    assert (await current_version(pipeline)).id != pipeline.version.id


async def test_영구_실패_기록은_건설_중인_판이_있으면_작업_행을_쥐기_전에_지식베이스_행을_기다린다(
    pipeline: Pipeline,
) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    job = await pipeline.claim()

    async with held_knowledge_base_lock(pipeline):
        failing = asyncio.create_task(
            index_document(pipeline.deps(parse_runner=FailingRunner(ErrorCode.PARSE_FAILED)), job)
        )
        await wait_for_lock_waiter(pipeline, failing)
        free = await job_row_is_free(pipeline, job.id)
        assert free, f"잠금을 기다리는 동안 작업 행을 쥐고 있다(작업 행이 비었나: {free})"

    with pytest.raises(PermanentFailure):
        await asyncio.wait_for(failing, timeout=MOMENT_SECONDS)
    building = await version_of(pipeline, IndexVersionStatus.CURRENT)
    assert building is not None and building.id != pipeline.version.id


async def test_영구_실패_기록은_건설_중인_판이_없으면_지식베이스_행을_기다리지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()

    async with held_knowledge_base_lock(pipeline):
        with pytest.raises(PermanentFailure):
            await asyncio.wait_for(
                index_document(
                    pipeline.deps(parse_runner=FailingRunner(ErrorCode.PARSE_FAILED)), job
                ),
                timeout=MOMENT_SECONDS,
            )

    assert await state_status(pipeline, ingested.document_id, pipeline.version) is (
        IndexStateStatus.FAILED
    )


async def _check(pipeline: Pipeline, version: IndexVersion) -> None:
    async with pipeline.unit_of_work.begin() as transaction:
        await check_version_switch(transaction, version)


async def test_색인_판마다_HNSW_부분_색인이_있고_물러난_판의_색인은_없다(
    pipeline: Pipeline,
) -> None:
    await ingest_and_index(pipeline, 휴가)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    building = await building_version(pipeline)

    assert await index_exists(pipeline, pipeline.version)
    assert await index_exists(pipeline, building)
    async with pipeline.engine.connect() as connection:
        definition = (
            await connection.execute(
                sa.text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
                {"name": version_index_name(building.id)},
            )
        ).scalar_one()
    assert "hnsw" in definition and f"index_version_id = '{building.id}'" in definition
    assert "vector(16)" in definition
