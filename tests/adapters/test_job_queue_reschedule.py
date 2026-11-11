"""`JobQueue` 어댑터의 다시 예약하기와 처음부터 맡을 다른 작업 보기(명세 "수집 파이프라인과 작업",
티켓 12).

일시 실패한 시도는 작업 행을 `queued`로 되돌려 `run_after`를 뒤로 둔다. 같은 문서에 다른 대기 작업이
있으면 부분 유일 색인이 둘째 대기 작업을 막으므로 되돌리지 않는다.
"""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import Document, Job, JobStatus
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome

LEASE_SECONDS = 600.0
LATER = NOW + timedelta(minutes=2)


async def _seed(unit_of_work: PostgresUnitOfWork, count: int = 1) -> list[Document]:
    source, group = await seed_source_and_group(unit_of_work)
    documents = [make_document(source, group, key=f"규정{index}.pdf") for index in range(count)]
    async with unit_of_work.begin() as transaction:
        for document in documents:
            await transaction.documents.add(document)
    return documents


async def _claimed(unit_of_work: PostgresUnitOfWork, document: Document, worker: str) -> Job:
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue(document.id, new_id(), NOW)
        job = await transaction.jobs.claim(worker, NOW, LEASE_SECONDS)
    assert job is not None
    return job


async def test_다시_예약하면_대기로_돌아가고_다음_실행_시각과_오류_코드를_두며_시도_횟수는_둔다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed(unit_of_work)
    job = await _claimed(unit_of_work, document, "작업자-1")

    async with unit_of_work.begin() as transaction:
        rescheduled = await transaction.jobs.reschedule(job, LATER, ErrorCode.EMBEDDING_UNAVAILABLE)
        row = await transaction.jobs.get(job.id)

    assert rescheduled is True
    assert row is not None
    assert (row.status, row.attempts, row.run_after) == (JobStatus.QUEUED, 1, LATER)
    assert (row.last_error_code, row.leased_until, row.worker_id, row.raised_generation) == (
        ErrorCode.EMBEDDING_UNAVAILABLE,
        None,
        None,
        None,
    )


async def test_다시_예약한_작업은_다음_실행_시각_전에는_꺼내지_않고_뒤에는_시도_횟수를_올려_꺼낸다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed(unit_of_work)
    job = await _claimed(unit_of_work, document, "작업자-1")
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.reschedule(job, LATER, ErrorCode.DATABASE_UNAVAILABLE)

    async with unit_of_work.begin() as transaction:
        early = await transaction.jobs.claim("작업자-2", NOW + timedelta(minutes=1), LEASE_SECONDS)
        due = await transaction.jobs.claim("작업자-2", LATER, LEASE_SECONDS)

    assert early is None
    assert due is not None
    assert (due.id, due.attempts, due.status) == (job.id, 2, JobStatus.RUNNING)
    assert due.last_error_code is ErrorCode.DATABASE_UNAVAILABLE


async def test_같은_문서에_다른_대기_작업이_있으면_다시_예약하지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed(unit_of_work)
    job = await _claimed(unit_of_work, document, "작업자-1")
    async with unit_of_work.begin() as transaction:
        other = await transaction.jobs.enqueue(document.id, new_id(), NOW)

    async with unit_of_work.begin() as transaction:
        rescheduled = await transaction.jobs.reschedule(job, LATER, ErrorCode.BLOB_STORE_ERROR)
        row = await transaction.jobs.get(job.id)
        other_row = await transaction.jobs.get(other.id)

    assert rescheduled is False
    assert row is not None
    assert (row.status, row.run_after, row.last_error_code) == (JobStatus.RUNNING, NOW, None)
    assert other_row is not None
    assert other_row.status is JobStatus.QUEUED


async def test_임대를_잃은_시도는_다시_예약하지_못한다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed(unit_of_work)
    lost = await _claimed(unit_of_work, document, "작업자-1")
    async with unit_of_work.begin() as transaction:
        taken = await transaction.jobs.claim(
            "작업자-2", NOW + timedelta(seconds=LEASE_SECONDS + 1), LEASE_SECONDS
        )
    assert taken is not None

    async with unit_of_work.begin() as transaction:
        rescheduled = await transaction.jobs.reschedule(lost, LATER, ErrorCode.BLOB_STORE_ERROR)
        row = await transaction.jobs.get(lost.id)

    assert rescheduled is False
    assert row is not None
    assert (row.status, row.worker_id) == (JobStatus.RUNNING, "작업자-2")


async def test_처음부터_맡을_다른_작업은_대기_작업과_올린_세대가_빈_실행_중_작업이다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    (document,) = await _seed(unit_of_work)
    running = await _claimed(unit_of_work, document, "작업자-1")

    async with unit_of_work.begin() as transaction:
        alone = await transaction.jobs.has_other_job_from_start(document.id, running.id)
        queued = await transaction.jobs.enqueue(document.id, new_id(), NOW)
        with_queued = await transaction.jobs.has_other_job_from_start(document.id, running.id)
        from_queued = await transaction.jobs.has_other_job_from_start(document.id, queued.id)
        await transaction.jobs.delete_queued(document.id)
        await transaction.jobs.record_raised_generation(running, 2)
        raised_other = await transaction.jobs.has_other_job_from_start(document.id, new_id())

    assert alone is False
    assert with_queued is True
    # 실행 중 작업은 올린 세대가 비었을 때만 센다. 올린 세대가 채워진 작업은 세지 않는다.
    assert from_queued is True
    assert raised_other is False


async def test_끝난_작업과_다른_문서의_작업은_처음부터_맡을_다른_작업이_아니다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    first, second = await _seed(unit_of_work, 2)
    done = await _claimed(unit_of_work, first, "작업자-1")
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.finish(done, JobOutcome(JobStatus.SUCCEEDED, None), NOW)
        await transaction.jobs.enqueue(second.id, new_id(), NOW)

    async with unit_of_work.begin() as transaction:
        found = await transaction.jobs.has_other_job_from_start(first.id, new_id())

    assert found is False
