"""`ingest --wait`가 쓰는 기다림(명세 "관리 명령", 스토리 9, 티켓 15).

문서마다 대기·실행 중인 작업이 없어질 때까지 폴링하고, 그때 색인이 실패한 문서를 낸다. 넣은 작업의
상태가 아니라 문서의 결과로 판정한다. 폴링 사이의 잠을 시험이 건네므로 그 자리에서 작업자를 돌리거나
다른 수집을 끼워 넣는다. 실제 테스트 PostgreSQL과 실제 DOCX 파서 위에서 돌고 임베딩 서버만 스텁이다.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FailingRunner, rejecting_embedder_for
from tests.support.pipeline import Pipeline

from rag_engine.app.await_documents import WaitStatus, wait_for_documents
from rag_engine.app.ingest import IngestResult
from rag_engine.domain.entities import JobStatus
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import run_once

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
POLL_SECONDS = 1.0


class _Clock:
    """잠을 자면 시계가 그만큼 가는 가짜 시계. 잠이 불린 길이를 남긴다."""

    def __init__(self, on_sleep: Callable[[], Awaitable[None]] | None = None) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []
        self._on_sleep = on_sleep

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        if self._on_sleep is not None:
            await self._on_sleep()


async def _wait(
    pipeline: Pipeline, *results: IngestResult, clock: _Clock, timeout_seconds: float = 0.0
) -> tuple[WaitStatus, list[tuple[UUID, ErrorCode]]]:
    outcome = await wait_for_documents(
        pipeline.unit_of_work,
        [result.document_id for result in results],
        poll_seconds=POLL_SECONDS,
        timeout_seconds=timeout_seconds,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    return outcome.status, [(failed.document_id, failed.error_code) for failed in outcome.failed]


def _worker(pipeline: Pipeline, *, parse_failing: bool = False) -> Callable[[], Awaitable[None]]:
    async def work() -> None:
        deps = (
            pipeline.deps(parse_runner=FailingRunner(ErrorCode.PARSE_FAILED))
            if parse_failing
            else pipeline.deps()
        )
        await run_once(deps, worker_id="작업자", lease_seconds=600.0)

    return work


async def test_작업이_끝나_색인되면_실패_없이_돌아온다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    clock = _Clock(_worker(pipeline))

    status, failed = await _wait(pipeline, ingested, clock=clock)

    assert (status, failed) == (WaitStatus.FINISHED, [])
    assert clock.sleeps == [POLL_SECONDS]


async def test_이미_끝난_문서는_잠들지_않고_돌아온다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await _worker(pipeline)()
    clock = _Clock()

    status, failed = await _wait(pipeline, ingested, clock=clock)

    assert (status, failed) == (WaitStatus.FINISHED, [])
    assert clock.sleeps == []


async def test_앞서_넣은_작업이_도는_문서를_다시_넣어_unchanged여도_그_작업을_기다린다(
    pipeline: Pipeline,
) -> None:
    first = await pipeline.ingest(휴가)
    again = await pipeline.ingest(휴가)
    assert again.job_id is None
    clock = _Clock(_worker(pipeline))

    status, failed = await _wait(pipeline, again, clock=clock)

    assert (status, failed) == (WaitStatus.FINISHED, [])
    assert clock.sleeps == [POLL_SECONDS]
    assert first.document_id == again.document_id


async def test_파싱이_영구_실패한_문서는_오류_코드와_함께_실패로_낸다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    clock = _Clock(_worker(pipeline, parse_failing=True))

    status, failed = await _wait(pipeline, ingested, clock=clock)

    assert status is WaitStatus.FINISHED
    assert failed == [(ingested.document_id, ErrorCode.PARSE_FAILED)]


async def test_파싱은_됐고_판의_임베딩만_거부당한_문서도_실패로_낸다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    rejecting = rejecting_embedder_for(
        pipeline.pool, {pipeline.version.id}, ErrorCode.EMBEDDING_REJECTED
    )

    async def work() -> None:
        await run_once(
            pipeline.deps(embedder_for=rejecting), worker_id="작업자", lease_seconds=600.0
        )

    status, failed = await _wait(pipeline, ingested, clock=_Clock(work))

    assert status is WaitStatus.FINISHED
    assert failed == [(ingested.document_id, ErrorCode.EMBEDDING_REJECTED)]


async def test_넣은_작업이_succeeded로_끝나도_같은_문서의_뒤_작업이_실패하면_실패다(
    pipeline: Pipeline,
) -> None:
    first = await pipeline.ingest(휴가)
    await _worker(pipeline)()
    second = await pipeline.ingest(출장)
    assert second.job_id is not None and second.job_id != first.job_id
    clock = _Clock(_worker(pipeline, parse_failing=True))

    status, failed = await _wait(pipeline, first, clock=clock)

    assert status is WaitStatus.FINISHED
    assert failed == [(first.document_id, ErrorCode.PARSE_FAILED)]


async def test_넣은_작업이_failed로_끝나도_뒤_작업이_색인하면_실패가_아니다(
    pipeline: Pipeline,
) -> None:
    first = await pipeline.ingest(휴가)
    await _worker(pipeline, parse_failing=True)()
    await pipeline.ingest(출장)
    clock = _Clock(_worker(pipeline))

    status, failed = await _wait(pipeline, first, clock=clock)

    assert (status, failed) == (WaitStatus.FINISHED, [])


async def test_기다리는_사이_지워진_문서는_실패로_세지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)

    async def delete() -> None:
        await pipeline.delete()

    status, failed = await _wait(pipeline, ingested, clock=_Clock(delete))

    assert (status, failed) == (WaitStatus.FINISHED, [])


async def test_지운_문서에_실행_중인_작업이_남아도_기다리지_않고_끝난_것으로_본다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    async with pipeline.unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim(
            "작업자", datetime.now(UTC) + timedelta(days=1), 60.0
        )
        assert claimed is not None and claimed.status is JobStatus.RUNNING
    await pipeline.delete()

    status, failed = await _wait(pipeline, ingested, clock=_Clock(), timeout_seconds=5.0)

    assert (status, failed) == (WaitStatus.FINISHED, [])


async def test_실패한_뒤_지워진_문서도_실패로_세지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await _worker(pipeline, parse_failing=True)()
    await pipeline.delete()

    status, failed = await _wait(pipeline, ingested, clock=_Clock())

    assert (status, failed) == (WaitStatus.FINISHED, [])


async def test_시간이_지나면_남은_잠을_줄여_자고_시간_초과로_돌아온다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    clock = _Clock()

    status, failed = await _wait(pipeline, ingested, clock=clock, timeout_seconds=2.5)

    assert (status, failed) == (WaitStatus.TIMED_OUT, [])
    assert clock.sleeps == [1.0, 1.0, 0.5]


async def test_시간_초과여도_그때까지_끝난_문서의_실패는_낸다(pipeline: Pipeline) -> None:
    failing = await pipeline.ingest(휴가, "실패.docx")
    await _worker(pipeline, parse_failing=True)()
    waiting = await pipeline.ingest(출장, "대기.docx")

    status, failed = await _wait(pipeline, failing, waiting, clock=_Clock(), timeout_seconds=1.0)

    assert status is WaitStatus.TIMED_OUT
    assert failed == [(failing.document_id, ErrorCode.PARSE_FAILED)]


async def test_없는_문서는_끝난_것으로_보고_실패로_세지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    outcome = await wait_for_documents(
        pipeline.unit_of_work,
        [new_id()],
        poll_seconds=POLL_SECONDS,
        timeout_seconds=0.0,
        sleep=_Clock().sleep,
        monotonic=_Clock().monotonic,
    )

    assert (outcome.status, outcome.failed) == (WaitStatus.FINISHED, ())
    assert ingested.document_id is not None
