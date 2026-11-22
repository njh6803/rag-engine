"""원천 관리 API(source-sync 명세 "관리 API", 스토리 1). 모두 `admin` 토큰의 몫이다(인증 미들웨어가
`reader`의 REST를 막는다).

`POST /sources`는 밀어 넣는 원천을 만들어 201로 답한다. 이름이 규칙에 어긋나면 422, 이미 있으면(지운
원천 포함) 409 `source_already_exists`다. `GET /sources`와 `GET /sources/{name}`은 같은 모양의
원천을 낸다. 없는 이름은 404 `source_not_found`다.
"""

from datetime import UTC, datetime

from fastapi import APIRouter

from rag_engine.app.admin_sources import create_push_source, get_source_report, list_source_reports
from rag_engine.domain.ports import UnitOfWork
from rag_engine.server.admin_source_models import (
    CreateSourceRequest,
    SourceListResponse,
    SourceResponse,
)
from rag_engine.server.api_version import API_VERSION
from rag_engine.server.problems import ProblemDetails

_NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 이름의 원천이 없다(`source_not_found`)"},
}
_CREATE_PROBLEMS: dict[int | str, dict[str, object]] = {
    409: {
        "model": ProblemDetails,
        "description": "같은 이름의 원천이 이미 있다(`source_already_exists`)",
    },
}


def build_admin_source_router(unit_of_work: UnitOfWork) -> APIRouter:
    router = APIRouter(prefix=f"/api/{API_VERSION}/admin")

    @router.post("/sources", status_code=201, responses=_CREATE_PROBLEMS)
    async def create(body: CreateSourceRequest) -> SourceResponse:
        report = await create_push_source(unit_of_work, body.name, now=datetime.now(UTC))
        return SourceResponse.of(report)

    @router.get("/sources")
    async def sources() -> SourceListResponse:
        found = await list_source_reports(unit_of_work)
        return SourceListResponse(sources=[SourceResponse.of(report) for report in found])

    @router.get("/sources/{name}", responses=_NOT_FOUND)
    async def source(name: str) -> SourceResponse:
        return SourceResponse.of(await get_source_report(unit_of_work, name))

    return router
