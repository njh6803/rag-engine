"""일시 실패의 재시도와 재시도 소진(명세 "수집 파이프라인과 작업", 티켓 12).

실제 테스트 PostgreSQL, 실제 파서, 실제 청커 위에서 `process_job`을 돌린다. 임베딩 서버는
`TeiStub`이고 시험이 `fail`로 5xx를 낸다. 백오프는 기다리지 않고 `run_after`와 지금의 차로 본다.
"""

import asyncio
import json
import logging
from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest
import sqlalchemy as sa
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import (
    FailingRunner,
    FlakyUnitOfWork,
    TransientFailingRunner,
    interrupting_embedder_for,
    rejecting_embedder_for,
)
from tests.support.pipeline import BACKOFF_BASE_SECONDS, JobRow, Pipeline

from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.app import index_failure as index_failure_module
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.domain.entities import (
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IngestAction,
    JobStatus,
)
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import LockMode
from rag_engine.worker.processing import process_job

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
EMBEDDINGS = "/v1/embeddings"
FAR_FUTURE = 3 * 24 * 3600.0


def _policy(max_attempts: int) -> RetryPolicy:
    return RetryPolicy(max_attempts=max_attempts, backoff_base_seconds=BACKOFF_BASE_SECONDS)


async def _attempt(pipeline: Pipeline, retry: RetryPolicy) -> None:
    """꺼낼 수 있는 시각까지 시계를 건너뛰어 작업 하나를 꺼내 한 번 시도한다."""
    job = await pipeline.claim(later=FAR_FUTURE)
    await process_job(pipeline.deps(retry=retry), job)


async def _generation(pipeline: Pipeline, document_id: UUID) -> int:
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
    assert document is not None
    return document.generation


async def _index(pipeline: Pipeline, data: bytes, key: str = "규정.docx") -> UUID:
    """문서를 넣고 색인을 마친다."""
    ingested = await pipeline.ingest(data, key)
    job = await pipeline.claim()
    await process_job(pipeline.deps(), job)
    return ingested.document_id


async def test_일시_실패하면_백오프_뒤로_다시_예약하고_문서_쪽은_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    pipeline.stub.fail(EMBEDDINGS, 503)

    await _attempt(pipeline, _policy(6))

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code, row.attempts) == (
        "queued",
        "embedding_unavailable",
        1,
    )
    assert row.run_after == pipeline.clock[0] + timedelta(seconds=BACKOFF_BASE_SECONDS)
    assert await pipeline.states(ingested.document_id) == {}


async def test_백오프는_네_배씩_늘고_한_시간을_넘지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    pipeline.stub.fail(EMBEDDINGS, 503)
    delays: list[float] = []

    for _ in range(5):
        await _attempt(pipeline, _policy(6))
        (row,) = await pipeline.job_rows(ingested.document_id)
        delays.append((row.run_after - pipeline.clock[0]).total_seconds())

    assert delays == [30.0, 120.0, 480.0, 1920.0, 3600.0]


async def test_최대_시도를_다_쓰면_작업이_failed로_끝나고_옛_조각을_지우고_상태를_failed로_쓴다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline, 휴가)
    assert await pipeline.chunk_texts(document_id) != []
    changed = await pipeline.ingest(출장)
    pipeline.stub.fail(EMBEDDINGS, 503)

    for _ in range(3):
        await _attempt(pipeline, _policy(3))

    assert changed.document_id == document_id
    rows = await pipeline.job_rows(document_id)
    assert [(row.status, row.last_error_code, row.attempts) for row in rows[-1:]] == [
        ("failed", "embedding_unavailable", 3)
    ]
    assert await pipeline.chunk_texts(document_id) == []
    state = (await pipeline.states(document_id))[pipeline.version.id]
    assert (state.status, state.error_code, state.chunk_count) == (
        IndexStateStatus.FAILED,
        ErrorCode.EMBEDDING_UNAVAILABLE,
        0,
    )


async def test_최대_시도_뒤_같은_내용을_다시_넣으면_requeued로_작업이_다시_들어간다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    pipeline.stub.fail(EMBEDDINGS, 503)
    for _ in range(2):
        await _attempt(pipeline, _policy(2))

    again = await pipeline.ingest(휴가)

    assert again.action is IngestAction.REQUEUED
    assert again.document_id == ingested.document_id
    assert again.job_id is not None


async def test_지운_문서는_재시도를_다_써도_색인_상태_행을_만들지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    pipeline.stub.fail(EMBEDDINGS, 503)
    job = await pipeline.claim()

    async def delete_meanwhile() -> None:
        await pipeline.delete()

    deps = pipeline.deps(
        embedder_for=interrupting_embedder_for(pipeline.pool, delete_meanwhile),
        retry=_policy(1),
    )
    await process_job(deps, job)

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code) == ("failed", "embedding_unavailable")
    assert await pipeline.states(ingested.document_id) == {}


async def test_임베딩_끝점의_모델이_다르면_작업이_embedding_unavailable로_다시_예약된다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    pipeline.stub.model_id = "다른/모델"

    await _attempt(pipeline, _policy(6))

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code) == ("queued", "embedding_unavailable")


async def test_원본을_읽지_못하면_blob_store_error로_다시_예약된다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    async with pipeline.unit_of_work.begin() as transaction:
        document = await transaction.documents.get(ingested.document_id)
    assert document is not None
    await pipeline.blob_store.delete(document.blob_path)

    await _attempt(pipeline, _policy(6))

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code) == ("queued", "blob_store_error")


async def test_데이터베이스가_잠깐_끊기면_다시_예약하고_세대를_올리지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    before = await _generation(pipeline, ingested.document_id)
    job = await pipeline.claim()
    flaky = FlakyUnitOfWork(pipeline.unit_of_work)

    await process_job(pipeline.deps(unit_of_work=flaky, retry=_policy(6)), job)

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code) == ("queued", "database_unavailable")
    assert await _generation(pipeline, ingested.document_id) == before


async def test_어느_갈래에도_들지_않는_예외는_다시_예약하지_않고_색인_상태를_internal_error로_쓴다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    job = await pipeline.claim()
    failing = FailingRunner(before_failing=_crash)

    await process_job(pipeline.deps(parse_runner=failing, retry=_policy(6)), job)

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code, row.attempts) == ("failed", "internal_error", 1)
    state = (await pipeline.states(ingested.document_id))[pipeline.version.id]
    assert (state.status, state.error_code) == (IndexStateStatus.FAILED, ErrorCode.INTERNAL_ERROR)


async def _crash() -> None:
    raise RuntimeError("예기치 못한 오류")


async def test_다른_대기_작업이_있으면_다시_예약하지_않고_이번_코드로_끝내고_문서_쪽을_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    pipeline.stub.fail(EMBEDDINGS, 503)
    job = await pipeline.claim()
    async with pipeline.unit_of_work.begin() as transaction:
        waiting = await transaction.jobs.enqueue(ingested.document_id, new_id(), pipeline.clock[0])

    await process_job(pipeline.deps(retry=_policy(6)), job)

    rows = await pipeline.job_rows(ingested.document_id)
    assert {(row.status, row.last_error_code) for row in rows} == {
        ("failed", "embedding_unavailable"),
        ("queued", None),
    }
    assert waiting.status is JobStatus.QUEUED
    assert await pipeline.states(ingested.document_id) == {}


async def test_한_판의_임베딩_영구_실패_뒤에도_남은_대상_판을_처리하고_작업은_failed다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    building = await pipeline.add_building_version()
    job = await pipeline.claim()
    rejecting = rejecting_embedder_for(
        pipeline.pool, {pipeline.version.id}, ErrorCode.EMBEDDING_REJECTED
    )

    await process_job(pipeline.deps(embedder_for=rejecting, retry=_policy(6)), job)

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code, row.attempts) == ("failed", "embedding_rejected", 1)
    states = await pipeline.states(ingested.document_id)
    assert (states[pipeline.version.id].status, states[pipeline.version.id].error_code) == (
        IndexStateStatus.FAILED,
        ErrorCode.EMBEDDING_REJECTED,
    )
    assert states[building.id].status is IndexStateStatus.INDEXED
    assert await pipeline.chunk_texts(ingested.document_id) == []
    assert await pipeline.chunk_texts(ingested.document_id, building) != []


async def test_영구_실패한_판은_옛_조각을_지운다(pipeline: Pipeline) -> None:
    document_id = await _index(pipeline, 휴가)
    await pipeline.ingest(출장)
    job = await pipeline.claim()
    rejecting = rejecting_embedder_for(
        pipeline.pool, {pipeline.version.id}, ErrorCode.EMBEDDING_DIMENSION_MISMATCH
    )

    await process_job(pipeline.deps(embedder_for=rejecting), job)

    assert await pipeline.chunk_texts(document_id) == []
    state = (await pipeline.states(document_id))[pipeline.version.id]
    assert state.error_code is ErrorCode.EMBEDDING_DIMENSION_MISMATCH


async def test_남은_판에서_일시_실패가_나면_그_시도는_일시_실패로_다룬다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    building = await pipeline.add_building_version()
    job = await pipeline.claim()
    rejecting = rejecting_embedder_for(
        pipeline.pool, {pipeline.version.id}, ErrorCode.EMBEDDING_REJECTED
    )
    pipeline.stub.fail(EMBEDDINGS, 503)

    await process_job(pipeline.deps(embedder_for=rejecting, retry=_policy(6)), job)

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code) == ("queued", "embedding_unavailable")
    assert await pipeline.states(ingested.document_id) == {}
    assert await pipeline.chunk_texts(ingested.document_id, building) == []


async def _save_pending(pipeline: Pipeline, document_id: UUID, version_id: UUID) -> None:
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.index.save_state(
            IndexState(
                document_id=document_id,
                index_version_id=version_id,
                status=IndexStateStatus.PENDING,
                chunk_count=0,
                built_content_hash=None,
                error_code=None,
                updated_at=pipeline.clock[0],
            )
        )


async def test_첫째_단계_전에_재시도를_다_써도_맡을_다른_작업이_없으면_pending을_failed로_쓴다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    building = await pipeline.add_building_version()
    await _save_pending(pipeline, ingested.document_id, building.id)
    job = await pipeline.claim()
    flaky = FlakyUnitOfWork(pipeline.unit_of_work)

    await process_job(pipeline.deps(unit_of_work=flaky, retry=_policy(1)), job)

    states = await pipeline.states(ingested.document_id)
    assert {
        version_id: (state.status, state.error_code) for version_id, state in states.items()
    } == {
        building.id: (IndexStateStatus.FAILED, ErrorCode.DATABASE_UNAVAILABLE),
        pipeline.version.id: (IndexStateStatus.FAILED, ErrorCode.DATABASE_UNAVAILABLE),
    }


async def test_옛_작업이_실행_중이어도_늦게_시작한_작업이_재시도를_다_쓰면_pending을_failed로_쓴다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    building = await pipeline.add_building_version()
    await _save_pending(pipeline, ingested.document_id, building.id)
    older = await pipeline.claim("worker-1")
    generation = await _generation(pipeline, ingested.document_id)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.record_raised_generation(older, generation)
        await transaction.jobs.enqueue(ingested.document_id, new_id(), pipeline.clock[0])
    later = await pipeline.claim("worker-2")
    flaky = FlakyUnitOfWork(pipeline.unit_of_work)

    await process_job(pipeline.deps(unit_of_work=flaky, retry=_policy(1)), later)

    states = await pipeline.states(ingested.document_id)
    assert states[building.id].status is IndexStateStatus.FAILED


async def test_맡을_다른_작업이_있으면_재시도를_다_써도_문서_쪽을_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    building = await pipeline.add_building_version()
    await _save_pending(pipeline, ingested.document_id, building.id)
    last = await pipeline.claim("worker-1")
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(ingested.document_id, new_id(), pipeline.clock[0])
    flaky = FlakyUnitOfWork(pipeline.unit_of_work)

    await process_job(pipeline.deps(unit_of_work=flaky, retry=_policy(1)), last)

    states = await pipeline.states(ingested.document_id)
    assert {version_id: state.status for version_id, state in states.items()} == {
        building.id: IndexStateStatus.PENDING
    }


async def test_세대가_다르고_다른_작업이_없으면_재시도_소진이_문서_쪽을_건드리지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    pipeline.stub.fail(EMBEDDINGS, 503)
    job = await pipeline.claim()

    async def raise_generation() -> None:
        async with pipeline.unit_of_work.begin() as transaction:
            document = await transaction.documents.lock(ingested.document_id)
            assert document is not None
            await transaction.documents.update(
                replace(document, generation=document.generation + 1)
            )

    deps = pipeline.deps(
        embedder_for=interrupting_embedder_for(pipeline.pool, raise_generation),
        retry=_policy(1),
    )
    await process_job(deps, job)

    (row,) = await pipeline.job_rows(ingested.document_id)
    assert (row.status, row.last_error_code) == ("failed", "embedding_unavailable")
    assert await pipeline.states(ingested.document_id) == {}


async def test_재시도_소진은_지금_내용으로_색인된_판의_조각과_상태를_건드리지_않는다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline, 휴가)
    indexed_chunks = await pipeline.chunk_texts(document_id)
    building = await pipeline.add_building_version()
    await _save_pending(pipeline, document_id, building.id)
    # 건설 중인 판에 pending이 이 문서 하나뿐이면 소진이 failed를 쓰는 순간 판이 전환되고 옛 판의
    # 조각이 정리된다. 소진 자체가 조각을 건드리지 않는지 보려고 pending을 하나 더 남긴다.
    other = (await pipeline.ingest(출장, "출장.docx")).document_id
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.delete_queued(other)
    await _save_pending(pipeline, other, building.id)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document_id, new_id(), pipeline.clock[0])
    job = await pipeline.claim()
    flaky = FlakyUnitOfWork(pipeline.unit_of_work)

    await process_job(pipeline.deps(unit_of_work=flaky, retry=_policy(1)), job)

    states = await pipeline.states(document_id)
    assert {version_id: state.status for version_id, state in states.items()} == {
        pipeline.version.id: IndexStateStatus.INDEXED,
        building.id: IndexStateStatus.FAILED,
    }
    assert await pipeline.chunk_texts(document_id) == indexed_chunks


async def test_지운_문서는_첫째_단계_전에_재시도를_다_써도_건설_중인_판의_상태를_쓰지_않는다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    building = await pipeline.add_building_version()
    await _save_pending(pipeline, ingested.document_id, building.id)
    job = await pipeline.claim()
    await pipeline.delete()
    flaky = FlakyUnitOfWork(pipeline.unit_of_work)

    await process_job(pipeline.deps(unit_of_work=flaky, retry=_policy(1)), job)

    assert await pipeline.states(ingested.document_id) == {}


async def test_재시도_소진이_건설_중인_판을_failed로_쓰면_그_판만_전환_검사를_부른다(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingested = await pipeline.ingest(휴가)
    building = await pipeline.add_building_version()
    await _save_pending(pipeline, ingested.document_id, building.id)
    job = await pipeline.claim()
    checked: list[IndexVersion] = []

    async def record_check(_transaction: object, version: IndexVersion) -> None:
        checked.append(version)

    monkeypatch.setattr(index_failure_module, "check_version_switch", record_check)

    await process_job(
        pipeline.deps(unit_of_work=FlakyUnitOfWork(pipeline.unit_of_work), retry=_policy(1)), job
    )

    assert [version.id for version in checked] == [building.id]


async def test_지웠다_되살린_사이에_옛_작업이_재시도를_다_써도_되살린_조각과_상태를_건드리지_않는다(
    pipeline: Pipeline,
) -> None:
    document_id = await _index(pipeline, 휴가)
    restored_chunks = await pipeline.chunk_texts(document_id)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document_id, new_id(), pipeline.clock[0])
    job = await pipeline.claim()
    pipeline.stub.fail(EMBEDDINGS, 503)

    async def delete_and_restore() -> None:
        await pipeline.delete()
        restored = await pipeline.ingest(휴가)
        assert restored.action is IngestAction.RESTORED

    deps = pipeline.deps(
        embedder_for=interrupting_embedder_for(pipeline.pool, delete_and_restore),
        retry=_policy(1),
    )
    await process_job(deps, job)

    assert await pipeline.chunk_texts(document_id) == restored_chunks
    state = (await pipeline.states(document_id))[pipeline.version.id]
    assert state.status is IndexStateStatus.INDEXED
    rows = await pipeline.job_rows(document_id)
    assert rows[-1].status == "failed"


async def _lock_waiters(pipeline: Pipeline) -> int:
    """이 데이터베이스에서 행 잠금을 기다리는 백엔드의 수."""
    async with pipeline.engine.connect() as connection:
        found = await connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_stat_activity"
                " WHERE datname = current_database() AND wait_event_type = 'Lock'"
            )
        )
        return found.scalar_one()


async def _attempt_while_knowledge_base_is_locked(
    pipeline: Pipeline, retry: RetryPolicy, mode: LockMode, *, expect_wait: bool
) -> JobRow:
    """지식베이스 행을 `mode`로 잠가 둔 채 일시 실패하는 시도를 돌리고 그 작업 행을 낸다. 기다려야
    하면 시도가 잠금을 기다리는 것을 데이터베이스에서 보고서야 잠금을 풀고, 기다리지 않아야 하면
    잠금을 쥔 채 시도가 끝나기를 기다린다."""
    document_id = await _index(pipeline, 휴가)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document_id, new_id(), pipeline.clock[0])
    pipeline.stub.fail(EMBEDDINGS, 503)
    job = await pipeline.claim()
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.lock_knowledge_bases([pipeline.knowledge_base.id], mode)
        attempt = asyncio.create_task(process_job(pipeline.deps(retry=retry), job))
        if expect_wait:
            for _ in range(200):
                if await _lock_waiters(pipeline) > 0 or attempt.done():
                    break
                await asyncio.sleep(0.1)
            assert not attempt.done()
            assert await _lock_waiters(pipeline) > 0
        else:
            await asyncio.wait_for(attempt, timeout=60)
    await asyncio.wait_for(attempt, timeout=60)
    return (await pipeline.job_rows(document_id))[-1]


async def test_다시_예약은_지식베이스_행을_공유로_잠가_갱신_잠금이_풀리기를_기다린다(
    pipeline: Pipeline,
) -> None:
    row = await _attempt_while_knowledge_base_is_locked(
        pipeline, _policy(6), LockMode.UPDATE, expect_wait=True
    )

    assert (row.status, row.last_error_code) == ("queued", "embedding_unavailable")


async def test_다시_예약은_공유_잠금을_기다리지_않는다(pipeline: Pipeline) -> None:
    row = await _attempt_while_knowledge_base_is_locked(
        pipeline, _policy(6), LockMode.SHARE, expect_wait=False
    )

    assert row.status == "queued"


async def test_재시도_소진은_지식베이스_행을_갱신으로_잠가_공유_잠금도_기다린다(
    pipeline: Pipeline,
) -> None:
    row = await _attempt_while_knowledge_base_is_locked(
        pipeline, _policy(1), LockMode.SHARE, expect_wait=True
    )

    assert (row.status, row.last_error_code) == ("failed", "embedding_unavailable")


async def test_파싱이_영구_실패한_작업도_실제_파싱_지연을_싣는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await pipeline.ingest(휴가)
    job = await pipeline.claim()

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(pipeline.deps(parse_runner=FailingRunner()), job)

    finished = [
        payload
        for payload in (
            json.loads(JsonLinesFormatter().format(record)) for record in caplog.records
        )
        if payload["event"] == "job_finished"
    ]
    assert [(item["result"], item["error_code"]) for item in finished] == [
        ("failed", "encrypted_document")
    ]
    assert finished[0]["parse_ms"] > 0


async def test_파싱이_일시_실패해_다시_예약된_시도도_실제_파싱_지연을_싣는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await pipeline.ingest(휴가)
    job = await pipeline.claim()

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(
            pipeline.deps(parse_runner=TransientFailingRunner(), retry=_policy(6)), job
        )

    finished = [
        payload
        for payload in (
            json.loads(JsonLinesFormatter().format(record)) for record in caplog.records
        )
        if payload["event"] == "job_finished"
    ]
    assert [(item["result"], item["error_code"]) for item in finished] == [
        ("queued", "database_unavailable")
    ]
    assert finished[0]["parse_ms"] > 0


async def test_임베딩이_일시_실패해_다시_예약된_시도도_실제_임베딩_지연을_싣는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    await pipeline.ingest(휴가)
    pipeline.stub.fail(EMBEDDINGS, 503)
    job = await pipeline.claim()

    with caplog.at_level(logging.INFO, logger="rag_engine.worker.processing"):
        await process_job(pipeline.deps(retry=_policy(6)), job)

    finished = [
        payload
        for payload in (
            json.loads(JsonLinesFormatter().format(record)) for record in caplog.records
        )
        if payload["event"] == "job_finished"
    ]
    assert [(item["result"], item["error_code"]) for item in finished] == [
        ("queued", "embedding_unavailable")
    ]
    assert finished[0]["embedding_ms"] > 0


def test_시도_횟수가_아무리_커도_백오프는_한_시간에서_멈추고_넘치지_않는다() -> None:
    assert _policy(10_000).backoff(10_000) == timedelta(hours=1)
