"""관리 조회가 쓰는 목록 질의(티켓 15): 작업 목록, 문서에 남은 작업, 문서 목록.

목록은 최근 순(UUIDv7 ID의 내림차순)이고 커서는 마지막으로 본 ID다. 문서의 상태 필터는 지운 문서를
네 번째 상태로 가른다.
"""

from dataclasses import replace
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import (
    Document,
    DocumentQuery,
    DocumentState,
    DocumentStatus,
    Group,
    Job,
    JobStatus,
    Source,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome


async def _add_documents(
    unit_of_work: PostgresUnitOfWork, source: Source, group: Group, *keys: str
) -> list[Document]:
    documents = [make_document(source, group, key) for key in keys]
    async with unit_of_work.begin() as transaction:
        for document in documents:
            await transaction.documents.add(document)
    return documents


async def _enqueue(unit_of_work: PostgresUnitOfWork, document: Document) -> Job:
    async with unit_of_work.begin() as transaction:
        return await transaction.jobs.enqueue(document.id, new_id(), NOW)


async def _finish(unit_of_work: PostgresUnitOfWork, job: Job, status: JobStatus) -> None:
    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자", NOW, 60.0)
        assert claimed is not None and claimed.id == job.id
        await transaction.jobs.finish(claimed, JobOutcome(status, None), NOW)


def _query(**overrides: object) -> DocumentQuery:
    return replace(
        DocumentQuery(state=None, group_id=None, key=None, limit=50, after=None), **overrides
    )


async def test_작업_목록은_최근_순이고_커서는_마지막으로_본_ID_다음부터다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    documents = await _add_documents(unit_of_work, source, group, "하나", "둘", "셋")
    jobs = [await _enqueue(unit_of_work, document) for document in documents]

    async with unit_of_work.begin() as transaction:
        first = await transaction.jobs.list_jobs(None, 2, None)
        second = await transaction.jobs.list_jobs(None, 2, first[-1].id)

    assert [job.id for job in first] == [jobs[2].id, jobs[1].id]
    assert [job.id for job in second] == [jobs[0].id]


async def test_작업_목록은_상태로_거른다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    done, waiting = await _add_documents(unit_of_work, source, group, "끝남", "대기")
    done_job = await _enqueue(unit_of_work, done)
    await _finish(unit_of_work, done_job, JobStatus.SUCCEEDED)
    waiting_job = await _enqueue(unit_of_work, waiting)

    async with unit_of_work.begin() as transaction:
        succeeded = await transaction.jobs.list_jobs(JobStatus.SUCCEEDED, 10, None)
        queued = await transaction.jobs.list_jobs(JobStatus.QUEUED, 10, None)

    assert [job.id for job in succeeded] == [done_job.id]
    assert [job.id for job in queued] == [waiting_job.id]


async def test_문서에_대기나_실행_중인_작업이_있을_때만_남았다고_한다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    untouched, finished, waiting = await _add_documents(
        unit_of_work, source, group, "작업 없음", "끝남", "대기"
    )
    await _finish(unit_of_work, await _enqueue(unit_of_work, finished), JobStatus.FAILED)
    await _enqueue(unit_of_work, waiting)

    async with unit_of_work.begin() as transaction:
        remaining = [
            await transaction.jobs.has_active_job(document.id)
            for document in (untouched, finished, waiting)
        ]

    assert remaining == [False, False, True]


async def test_실행_중인_작업도_남은_작업으로_센다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    (document,) = await _add_documents(unit_of_work, source, group, "실행")
    await _enqueue(unit_of_work, document)
    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자", NOW, 60.0)
        assert claimed is not None and claimed.status is JobStatus.RUNNING

    async with unit_of_work.begin() as transaction:
        assert await transaction.jobs.has_active_job(document.id)


async def test_문서_목록은_최근_순이고_커서_다음부터_한도만큼_낸다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    documents = await _add_documents(unit_of_work, source, group, "하나", "둘", "셋")

    async with unit_of_work.begin() as transaction:
        first = await transaction.documents.list_documents(_query(limit=2))
        second = await transaction.documents.list_documents(_query(limit=2, after=first[-1].id))

    assert [document.id for document in first] == [documents[2].id, documents[1].id]
    assert [document.id for document in second] == [documents[0].id]


async def test_문서_목록은_상태_그룹_키로_거르고_지운_문서는_지움_상태다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    other = Group(new_id(), "다른 그룹", "")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(other)
    received = make_document(source, group, "받음")
    parsed = make_document(source, group, "파싱됨", status=DocumentStatus.PARSED)
    failed = make_document(source, group, "실패", status=DocumentStatus.FAILED)
    deleted = make_document(
        source, group, "지움", status=DocumentStatus.PARSED, deleted_at=NOW + timedelta(hours=1)
    )
    elsewhere = make_document(source, other, "다른 곳")
    async with unit_of_work.begin() as transaction:
        for document in (received, parsed, failed, deleted, elsewhere):
            await transaction.documents.add(document)

    async with unit_of_work.begin() as transaction:
        listing = transaction.documents
        by_state = {
            state: [d.key for d in await listing.list_documents(_query(state=state))]
            for state in DocumentState
        }
        in_other = await listing.list_documents(_query(group_id=other.id))
        by_key = await listing.list_documents(_query(key="파싱됨"))

    assert by_state[DocumentState.RECEIVED] == ["다른 곳", "받음"]
    assert by_state[DocumentState.PARSED] == ["파싱됨"]
    assert by_state[DocumentState.FAILED] == ["실패"]
    assert by_state[DocumentState.DELETED] == ["지움"]
    assert [d.key for d in in_other] == ["다른 곳"]
    assert [d.id for d in by_key] == [parsed.id]
