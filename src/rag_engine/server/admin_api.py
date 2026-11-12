"""작업·문서 조회의 관리 API(명세 "관리 API", 스토리 7, 8). 모두 `admin` 토큰의 몫이다(인증
미들웨어가 `reader`의 REST를 막는다).

목록은 최근 순이고 커서는 마지막으로 본 ID다(UUIDv7이 시간순이라 ID 비교로 한다). 없는 그룹 이름으로
거른 문서 목록은 오류가 아니라 빈 목록이다.
"""

from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Query

from rag_engine.app.admin_queries import (
    get_document_report,
    get_job_report,
    list_document_reports,
    list_jobs,
)
from rag_engine.domain.entities import DocumentState, JobStatus
from rag_engine.domain.ports import UnitOfWork
from rag_engine.server.admin_models import (
    DocumentListResponse,
    DocumentResponse,
    JobDetailResponse,
    JobListResponse,
    JobResponse,
)
from rag_engine.server.problems import ProblemDetails

DEFAULT_LIMIT: Final = 50
MAX_LIMIT: Final = 200

type Limit = Annotated[
    int, Query(ge=1, le=MAX_LIMIT, description=f"한 번에 낼 개수(기본 {DEFAULT_LIMIT})")
]
type After = Annotated[UUID | None, Query(description="마지막으로 본 항목의 ID. 그 다음부터 낸다")]

_JOB_NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 ID의 작업이 없다(`job_not_found`)"},
}
_DOCUMENT_NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 ID의 문서가 없다(`document_not_found`)"},
}


def build_admin_query_router(unit_of_work: UnitOfWork) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin")

    @router.get("/jobs/{job_id}", responses=_JOB_NOT_FOUND)
    async def job(job_id: UUID) -> JobDetailResponse:
        return JobDetailResponse.of(await get_job_report(unit_of_work, job_id))

    @router.get("/jobs")
    async def jobs(
        status: Annotated[JobStatus | None, Query(description="이 상태의 작업만")] = None,
        limit: Limit = DEFAULT_LIMIT,
        after: After = None,
    ) -> JobListResponse:
        found = await list_jobs(unit_of_work, status=status, limit=limit, after=after)
        return JobListResponse(jobs=[JobResponse.of(item) for item in found])

    @router.get("/documents/{document_id}", responses=_DOCUMENT_NOT_FOUND)
    async def document(document_id: UUID) -> DocumentResponse:
        return DocumentResponse.of(await get_document_report(unit_of_work, document_id))

    @router.get("/documents")
    async def documents(
        status: Annotated[DocumentState | None, Query(description="이 상태의 문서만")] = None,
        group: Annotated[str | None, Query(description="이 그룹 이름의 문서만")] = None,
        key: Annotated[str | None, Query(description="그 키의 문서 하나를 찾는다")] = None,
        limit: Limit = DEFAULT_LIMIT,
        after: After = None,
    ) -> DocumentListResponse:
        found = await list_document_reports(
            unit_of_work, state=status, group=group, key=key, limit=limit, after=after
        )
        return DocumentListResponse(documents=[DocumentResponse.of(item) for item in found])

    return router
