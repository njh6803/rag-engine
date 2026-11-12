"""재색인 시작과 색인 작업, 재시도 소진이 엇갈릴 때 결과가 새 상태로 모이는지 본다(명세 Testing
Decisions의 동시성 교차, 티켓 14).

실제 테스트 PostgreSQL 위에서 `tests/support/interleaving.py`의 끼어들기 훅으로 순간을 정한다.
끼어들기 훅은 임베더마다(살아 있는 판마다) 한 번씩 불리므로, 여기서는 한 번만 도는 보호 장치를 둔다.
"""

from tests.support.docx_files import docx_bytes
from tests.support.interleaving import (
    FlakyUnitOfWork,
    Interloper,
    interrupting_embedder_for,
    rejecting_embedder_for,
)
from tests.support.pipeline import BACKOFF_BASE_SECONDS, Pipeline
from tests.support.reindex import (
    building_version,
    current_version,
    ingest_and_index,
    set_chunk_tokens,
    start,
    state_status,
    version_of,
)

from rag_engine.app.index_document import index_document
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.domain.entities import IndexStateStatus, IndexVersionStatus, IngestAction, Job
from rag_engine.domain.errors import ErrorCode
from rag_engine.worker.processing import process_job

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
복지 = docx_bytes("제3조 복지", "복지 포인트는 매년 연초에 지급한다.")
EMBEDDINGS = "/v1/embeddings"
ONE_ATTEMPT = RetryPolicy(max_attempts=1, backoff_base_seconds=BACKOFF_BASE_SECONDS)


def _once(interloper: Interloper) -> Interloper:
    done: list[bool] = []

    async def wrapped() -> None:
        if not done:
            done.append(True)
            await interloper()

    return wrapped


async def _exhaust_before_first_stage(pipeline: Pipeline, job: Job) -> None:
    """첫째 단계 전에 데이터베이스가 끊겨 최대 시도를 다 쓴 시도를 돌린다."""
    flaky = FlakyUnitOfWork(pipeline.unit_of_work)
    await process_job(pipeline.deps(unit_of_work=flaky, retry=ONE_ATTEMPT), job)


async def test_재색인이_넣은_작업이_소진되면_마지막_pending이_failed가_되어_전환된다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    first = await pipeline.claim()

    async def reindex() -> None:
        await set_chunk_tokens(pipeline)
        started = await start(pipeline)
        assert started.jobs_enqueued == 1

    await index_document(
        pipeline.deps(embedder_for=interrupting_embedder_for(pipeline.pool, _once(reindex))), first
    )
    # 첫 작업은 재색인이 시작되기 전에 읽은 판(옛 현재 판)에만 썼으므로 새 판은 아직 pending이다.
    building = await building_version(pipeline)
    assert await state_status(pipeline, ingested.document_id, building) is IndexStateStatus.PENDING

    await _exhaust_before_first_stage(pipeline, await pipeline.claim("worker-2"))

    current = await current_version(pipeline)
    assert current.id == building.id
    assert await state_status(pipeline, ingested.document_id, current) is IndexStateStatus.FAILED
    assert await pipeline.chunk_texts(ingested.document_id, current) == []
    again = await pipeline.ingest(휴가)
    assert again.action is IngestAction.REQUEUED


async def test_먼저_읽은_작업은_판이_먼저_전환돼도_새_현재_판에_색인한다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    first = await pipeline.claim()
    await set_chunk_tokens(pipeline)
    started = await start(pipeline)
    assert started.jobs_enqueued == 1
    building = await building_version(pipeline)

    async def exhaust_reindex_job() -> None:
        await _exhaust_before_first_stage(pipeline, await pipeline.claim("worker-2"))
        # 재색인이 넣은 작업이 소진되어 마지막 pending이 failed가 되자 판이 먼저 전환됐다.
        switched = await current_version(pipeline)
        assert switched.id == building.id
        assert (
            await state_status(pipeline, ingested.document_id, switched) is IndexStateStatus.FAILED
        )

    await index_document(
        pipeline.deps(
            embedder_for=interrupting_embedder_for(pipeline.pool, _once(exhaust_reindex_job))
        ),
        first,
    )

    current = await current_version(pipeline)
    assert current.id == building.id
    assert await state_status(pipeline, ingested.document_id, current) is IndexStateStatus.INDEXED
    assert await pipeline.chunk_texts(ingested.document_id, current) != []
    assert await version_of(pipeline, IndexVersionStatus.BUILDING) is None


async def test_현재_판의_모델이_거부해도_건설_중인_판에_쓰고_그_판을_막지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    building = await building_version(pipeline)
    rejecting = rejecting_embedder_for(
        pipeline.pool, {pipeline.version.id}, ErrorCode.EMBEDDING_REJECTED
    )

    await process_job(pipeline.deps(embedder_for=rejecting), await pipeline.claim())

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code) == ("failed", "embedding_rejected")
    current = await current_version(pipeline)
    assert current.id == building.id
    assert await state_status(pipeline, ingested.document_id, current) is IndexStateStatus.INDEXED
    assert (
        await state_status(pipeline, ingested.document_id, pipeline.version)
        is IndexStateStatus.FAILED
    )


async def test_재색인_중_들어온_문서가_소진되면_전환_뒤에도_requeued다(
    pipeline: Pipeline,
) -> None:
    kept = await pipeline.ingest(휴가, "휴가.docx")
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    building = await building_version(pipeline)
    late = await pipeline.ingest(출장, "출장.docx")
    assert late.action is IngestAction.CREATED

    # 재색인 중 들어온 문서는 색인 상태 행이 없어 판 전환을 막지 않는다.
    assert await state_status(pipeline, late.document_id, building) is None
    kept_job = await pipeline.claim()
    assert kept_job.document_id == kept.document_id

    await _exhaust_before_first_stage(pipeline, await pipeline.claim("worker-2"))

    # 소진은 건설 중인 판에도 failed를 남긴다. 먼저 꺼낸 작업이 아직 pending이라 전환은 아직이다.
    assert await state_status(pipeline, late.document_id, building) is IndexStateStatus.FAILED
    assert await version_of(pipeline, IndexVersionStatus.BUILDING) is not None
    await index_document(pipeline.deps(), kept_job)
    current = await current_version(pipeline)
    assert current.id == building.id
    assert await state_status(pipeline, late.document_id, current) is IndexStateStatus.FAILED
    again = await pipeline.ingest(출장, "출장.docx")
    assert again.action is IngestAction.REQUEUED


async def test_재색인_중_들어온_새_문서는_작업이_끝나면_새_현재_판에_든다(
    pipeline: Pipeline,
) -> None:
    await ingest_and_index(pipeline, 휴가, "휴가.docx")
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    late = await pipeline.ingest(복지, "복지.docx")

    for _ in range(2):
        await index_document(pipeline.deps(), await pipeline.claim())

    current = await current_version(pipeline)
    assert current.id != pipeline.version.id
    assert await state_status(pipeline, late.document_id, current) is IndexStateStatus.INDEXED
    assert await pipeline.chunk_texts(late.document_id, current) != []


async def test_재색인_중_작업은_판마다_그_판의_청킹_설정으로_청킹한다(pipeline: Pipeline) -> None:
    paragraphs = [f"{n}번째 규정은 휴가를 신청하는 절차와 승인 기준을 설명한다." for n in range(40)]
    long = docx_bytes("제1조 휴가", *paragraphs)
    ingested = await pipeline.ingest(long)
    await set_chunk_tokens(pipeline)
    await start(pipeline)
    building = await building_version(pipeline)

    await index_document(pipeline.deps(), await pipeline.claim())

    old_count = len(await pipeline.chunk_texts(ingested.document_id, pipeline.version))
    new_count = len(await pipeline.chunk_texts(ingested.document_id, building))
    assert old_count >= 1 and new_count > old_count
