"""지식베이스 관리 API(명세 "관리 API", 스토리 33). 모두 `admin` 토큰의 몫이다(인증 미들웨어가
`reader`의 REST를 막는다).

`GET /knowledge-bases`와 `GET /knowledge-bases/{name}`은 "재색인 필요"와 건설 중인 판의 진행을 낸다.
`POST /knowledge-bases/{name}/reindex`는 새 판을 만들고 문서마다 작업을 넣어 202로 답한다. 이미
건설 중인 판이 있으면 409 `reindex_in_progress`다.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from rag_engine.app.admin_knowledge_bases import (
    get_knowledge_base_detail,
    list_knowledge_base_reports,
)
from rag_engine.app.reindex import start_reindex
from rag_engine.domain.ports import ComputeIndexElements, IndexMaintenance, UnitOfWork
from rag_engine.server.admin_knowledge_base_models import (
    KnowledgeBaseDetailResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    ReindexResponse,
)
from rag_engine.server.problems import ProblemDetails
from rag_engine.server.request_context import request_id_of

_NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {
        "model": ProblemDetails,
        "description": "그 이름의 지식베이스가 없다(`knowledge_base_not_found`)",
    },
}
_REINDEX_RESPONSES: dict[int | str, dict[str, object]] = {
    **_NOT_FOUND,
    409: {
        "model": ProblemDetails,
        "description": "건설 중인 색인 판이 이미 있다(`reindex_in_progress`)",
    },
}


def build_admin_knowledge_base_router(
    unit_of_work: UnitOfWork, maintenance: IndexMaintenance, compute_elements: ComputeIndexElements
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin")

    @router.get("/knowledge-bases")
    async def knowledge_bases() -> KnowledgeBaseListResponse:
        found = await list_knowledge_base_reports(unit_of_work, compute_elements)
        return KnowledgeBaseListResponse(
            knowledge_bases=[KnowledgeBaseResponse.of(report) for report in found]
        )

    @router.get("/knowledge-bases/{name}", responses=_NOT_FOUND)
    async def knowledge_base(name: str) -> KnowledgeBaseDetailResponse:
        detail = await get_knowledge_base_detail(unit_of_work, compute_elements, name)
        return KnowledgeBaseDetailResponse.detail_of(detail)

    @router.post("/knowledge-bases/{name}/reindex", status_code=202, responses=_REINDEX_RESPONSES)
    async def reindex(name: str, request: Request) -> ReindexResponse:
        started = await start_reindex(
            unit_of_work,
            maintenance,
            compute_elements,
            name,
            request_id=request_id_of(request.scope),
            now=datetime.now(UTC),
        )
        return ReindexResponse.of(started)

    return router
