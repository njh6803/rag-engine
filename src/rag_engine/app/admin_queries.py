"""관리 조회의 유스케이스(명세 "관리 API"의 작업 조회와 문서 조회, 스토리 7, 8).

작업의 상태는 그 작업이 끝난 모양이지 문서의 색인 결과가 아니다(수집 파이프라인의 넷째 단계). 그래서
작업 조회는 작업 행에 그 문서의 결과(문서 조회와 같은 상태, 오류 코드, 지식베이스마다의 색인 상태)와
같은 문서에 대기·실행 중인 작업이 남았는지를 더해 낸다. 세대 대조에 걸려 `succeeded`로 끝난 작업도
뒤 작업이 남았으면 남았다고 낸다.

문서의 색인 상태는 문서의 그룹이 든 지식베이스마다 살아 있는 판(현재 판과 건설 중인 판)별로 낸다.
지운 문서는 색인 상태 행이 모두 지워지므로 색인 상태를 내지 않는다. 이 조회는 토큰의 지식베이스
범위를 보지 않는다. 관리 API는 `admin` 토큰의 몫이다.
"""

from dataclasses import dataclass
from uuid import UUID

from rag_engine.domain.entities import (
    Document,
    DocumentQuery,
    DocumentState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    Job,
    JobStatus,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import Transaction, UnitOfWork


@dataclass(frozen=True, slots=True)
class IndexReport:
    """지식베이스 하나의 살아 있는 판 하나에 대한 문서의 색인 상태. `state`가 `None`이면 그 판에
    색인 상태 행이 없다. `chunk_count`는 그 판의 조각 수다."""

    knowledge_base: str
    version: IndexVersionStatus
    state: IndexStateStatus | None
    chunk_count: int
    error_code: ErrorCode | None


@dataclass(frozen=True, slots=True)
class DocumentReport:
    document: Document
    source: str
    group: str
    indexes: tuple[IndexReport, ...]


@dataclass(frozen=True, slots=True)
class JobReport:
    """작업 행과 그 문서의 결과. `active_jobs_remain`은 그 문서에 대기·실행 중인 작업이 있는지다
    (이 작업 자신이 아직 그렇다면 참이다)."""

    job: Job
    document: DocumentReport
    active_jobs_remain: bool


async def get_job_report(unit_of_work: UnitOfWork, job_id: UUID) -> JobReport:
    async with unit_of_work.begin() as transaction:
        job = await transaction.jobs.get(job_id)
        if job is None:
            raise RequestError(ErrorCode.JOB_NOT_FOUND, "작업을 찾을 수 없다")
        document = await transaction.documents.get(job.document_id)
        if document is None:
            raise RuntimeError("작업이 가리키는 문서가 없다")
        return JobReport(
            job=job,
            document=await _report(transaction, document),
            active_jobs_remain=await transaction.jobs.has_active_job(document.id),
        )


async def list_jobs(
    unit_of_work: UnitOfWork, *, status: JobStatus | None, limit: int, after: UUID | None
) -> list[Job]:
    async with unit_of_work.begin() as transaction:
        return await transaction.jobs.list_jobs(status, limit, after)


async def get_document_report(unit_of_work: UnitOfWork, document_id: UUID) -> DocumentReport:
    async with unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
        if document is None:
            raise RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "문서를 찾을 수 없다")
        return await _report(transaction, document)


async def list_document_reports(
    unit_of_work: UnitOfWork,
    *,
    state: DocumentState | None,
    group: str | None,
    key: str | None,
    limit: int,
    after: UUID | None,
) -> list[DocumentReport]:
    """없는 그룹 이름은 오류가 아니라 맞는 문서가 없는 것이다(검색의 그룹 필터와 같다)."""
    async with unit_of_work.begin() as transaction:
        group_id: UUID | None = None
        if group is not None:
            found = await transaction.catalog.get_group(group)
            if found is None:
                return []
            group_id = found.id
        documents = await transaction.documents.list_documents(
            DocumentQuery(state=state, group_id=group_id, key=key, limit=limit, after=after)
        )
        return [await _report(transaction, document) for document in documents]


async def _report(transaction: Transaction, document: Document) -> DocumentReport:
    source = await transaction.catalog.get_source_by_id(document.source_id)
    group = await transaction.catalog.get_group_by_id(document.group_id)
    if source is None or group is None:
        raise RuntimeError("문서가 가리키는 원천이나 그룹이 없다")
    indexes = () if document.deleted_at is not None else await _indexes(transaction, document)
    return DocumentReport(document=document, source=source.name, group=group.name, indexes=indexes)


def _building_last(version: IndexVersion) -> bool:
    return version.status is not IndexVersionStatus.CURRENT


async def _indexes(transaction: Transaction, document: Document) -> tuple[IndexReport, ...]:
    """지식베이스 이름 순으로, 한 지식베이스 안에서는 현재 판이 건설 중인 판보다 앞이다."""
    reports: list[IndexReport] = []
    knowledge_bases = await transaction.catalog.list_knowledge_bases_of_group(document.group_id)
    for knowledge_base in sorted(knowledge_bases, key=lambda found: found.name):
        versions = await transaction.catalog.list_live_index_versions(knowledge_base.id)
        for version in sorted(versions, key=_building_last):
            state = await transaction.index.get_state(document.id, version.id)
            reports.append(
                IndexReport(
                    knowledge_base=knowledge_base.name,
                    version=version.status,
                    state=None if state is None else state.status,
                    chunk_count=await transaction.index.count_chunks(document.id, version.id),
                    error_code=None if state is None else state.error_code,
                )
            )
    return tuple(reports)
