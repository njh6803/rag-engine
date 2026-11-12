"""작업·문서 조회의 응답 모델(명세 "관리 API"). 경로의 `v1`이 판이다(원칙 VII).

칸을 더하는 것은 같은 판이고 칸을 지우거나 뜻을 바꾸면 `v2`다. 시각은 UTC `Z`로 낸다(ADR 0015).
`status`는 문서에서는 `received`, `parsed`, `failed`, `deleted` 넷이고, 색인 상태에서는 `pending`,
`indexed`, `failed`이거나 그 판에 색인 상태 행이 없으면 null이다.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue

from rag_engine.app.admin_queries import DocumentReport, IndexReport, JobReport
from rag_engine.domain.entities import (
    DocumentState,
    IndexStateStatus,
    IndexVersionStatus,
    Job,
    JobKind,
    JobStatus,
)
from rag_engine.domain.errors import ErrorCode
from rag_engine.server.tool_support import METADATA


def _utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC)


type UtcTime = Annotated[datetime, AfterValidator(_utc)]


class IndexStatusResponse(BaseModel):
    """문서가 지식베이스 하나의 살아 있는 판 하나에 반영된 모양."""

    model_config = ConfigDict(frozen=True)

    knowledge_base: str = Field(description="지식베이스 이름")
    index_version: IndexVersionStatus = Field(
        description="`current`(현재 판)나 `building`(건설 중인 판)"
    )
    status: IndexStateStatus | None = Field(description="그 판에 색인 상태 행이 없으면 null")
    chunk_count: int = Field(description="그 판에 든 그 문서의 조각 수")
    error_code: ErrorCode | None = Field(description="색인이 실패했을 때의 오류 코드")

    @staticmethod
    def of(report: IndexReport) -> "IndexStatusResponse":
        return IndexStatusResponse(
            knowledge_base=report.knowledge_base,
            index_version=report.version,
            status=report.state,
            chunk_count=report.chunk_count,
            error_code=report.error_code,
        )


class DocumentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    key: str
    title: str
    source: str
    group: str
    mime: str
    size_bytes: int
    status: DocumentState = Field(description="지운 문서는 `deleted`다")
    error_code: ErrorCode | None = Field(description="파싱이 영구 실패한 문서의 오류 코드")
    metadata: dict[str, JsonValue]
    updated_at: UtcTime
    created_at: UtcTime
    deleted_at: UtcTime | None
    indexes: list[IndexStatusResponse] = Field(
        description="지식베이스 이름 순이고 한 지식베이스 안에서는 현재 판이 먼저다."
        " 지운 문서는 비어 있다"
    )

    @staticmethod
    def of(report: DocumentReport) -> "DocumentResponse":
        document = report.document
        return DocumentResponse(
            id=document.id,
            key=document.key,
            title=document.title,
            source=report.source,
            group=report.group,
            mime=document.mime,
            size_bytes=document.size_bytes,
            status=document.state,
            error_code=document.error_code,
            metadata=METADATA.validate_python(document.metadata),
            updated_at=document.updated_at,
            created_at=document.created_at,
            deleted_at=document.deleted_at,
            indexes=[IndexStatusResponse.of(index) for index in report.indexes],
        )


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class JobResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    kind: JobKind
    document_id: UUID
    status: JobStatus = Field(description="그 작업이 끝난 모양이다. 문서의 결과가 아니다")
    attempts: int
    run_after: UtcTime
    leased_until: UtcTime | None
    worker_id: str | None
    last_error_code: ErrorCode | None
    request_id: UUID
    created_at: UtcTime
    started_at: UtcTime | None
    finished_at: UtcTime | None

    @staticmethod
    def of(job: Job) -> "JobResponse":
        return JobResponse(
            id=job.id,
            kind=job.kind,
            document_id=job.document_id,
            status=job.status,
            attempts=job.attempts,
            run_after=job.run_after,
            leased_until=job.leased_until,
            worker_id=job.worker_id,
            last_error_code=job.last_error_code,
            request_id=job.request_id,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class JobListResponse(BaseModel):
    jobs: list[JobResponse]


class JobDetailResponse(BaseModel):
    """작업 행과 그 문서의 결과. 수집이 끝났는지는 작업의 상태가 아니라 문서의 상태와 색인 상태,
    그리고 `active_jobs_remain`으로 본다."""

    model_config = ConfigDict(frozen=True)

    job: JobResponse
    document: DocumentResponse
    active_jobs_remain: bool = Field(
        description="같은 문서에 대기·실행 중인 작업이 남았는지(이 작업 자신이 그렇다면 참)"
    )

    @staticmethod
    def of(report: JobReport) -> "JobDetailResponse":
        return JobDetailResponse(
            job=JobResponse.of(report.job),
            document=DocumentResponse.of(report.document),
            active_jobs_remain=report.active_jobs_remain,
        )
