"""원천 관리 API(source-sync 명세 "관리 API", 스토리 1, 6, 8, 9, 24). 모두 `admin` 토큰의
몫이다(인증 미들웨어가 `reader`의 REST를 막는다).

`POST /sources`는 밀어 넣는 원천이나 가져오는 원천을 만들어 201로 답한다. 이름이 규칙에 어긋나거나
가져오는 원천의 폴더와 설정이 틀리면 422, 이름이 이미 있으면(지운 원천 포함) 409
`source_already_exists`, 다른 원천의 폴더와 겹치면 409 `source_folder_overlap`이다.
`GET /sources`와 `GET /sources/{name}`은 같은 모양의 원천을 낸다. 없는 이름은 404
`source_not_found`다.

`PATCH /sources/{name}`, `POST /sources/{name}/check`, `/pause`, `/resume`은 가져오는 원천에만
통한다. 밀어 넣는 원천에는 409 `wrong_source_kind`다. 연결 확인은 원천을 읽지 못해도 200이다.
"""

from datetime import UTC, datetime

from fastapi import APIRouter

from rag_engine.app.admin_sources import (
    create_push_source,
    get_source_report,
    list_source_reports,
)
from rag_engine.app.pull_sources import PullSources
from rag_engine.domain.ports import UnitOfWork
from rag_engine.server.admin_source_models import (
    ConnectionCheckResponse,
    CreatePullSourceRequest,
    CreateSourceRequest,
    SourceListResponse,
    SourceResponse,
    UpdateSourceRequest,
)
from rag_engine.server.api_version import API_VERSION
from rag_engine.server.problems import ProblemDetails

_NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 이름의 원천이 없다(`source_not_found`)"},
}
_CREATE_PROBLEMS: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 이름의 그룹이 없다(`group_not_found`)"},
    409: {
        "model": ProblemDetails,
        "description": (
            "같은 이름의 원천이 이미 있다(`source_already_exists`)거나 다른 원천의 폴더와 "
            "겹친다(`source_folder_overlap`)"
        ),
    },
}
_PULL_ONLY_PROBLEMS: dict[int | str, dict[str, object]] = {
    **_NOT_FOUND,
    409: {
        "model": ProblemDetails,
        "description": (
            "밀어 넣는 원천이다(`wrong_source_kind`). 설정을 고칠 때는 다른 원천의 폴더와 "
            "겹치는 것(`source_folder_overlap`)도 409다"
        ),
    },
}


def build_admin_source_router(unit_of_work: UnitOfWork, pull_sources: PullSources) -> APIRouter:
    router = APIRouter(prefix=f"/api/{API_VERSION}/admin")

    @router.post("/sources", status_code=201, responses=_CREATE_PROBLEMS)
    async def create(body: CreateSourceRequest) -> SourceResponse:
        now = datetime.now(UTC)
        if isinstance(body, CreatePullSourceRequest):
            report = await pull_sources.create(
                name=body.name,
                connector=body.connector,
                config=body.config,
                group=body.group,
                exclude_patterns=body.exclude_patterns,
                now=now,
            )
        else:
            report = await create_push_source(unit_of_work, body.name, now=now)
        return SourceResponse.of(report)

    @router.get("/sources")
    async def sources() -> SourceListResponse:
        found = await list_source_reports(unit_of_work)
        return SourceListResponse(sources=[SourceResponse.of(report) for report in found])

    @router.get("/sources/{name}", responses=_NOT_FOUND)
    async def source(name: str) -> SourceResponse:
        return SourceResponse.of(await get_source_report(unit_of_work, name))

    @router.patch("/sources/{name}", responses=_PULL_ONLY_PROBLEMS)
    async def update(name: str, body: UpdateSourceRequest) -> SourceResponse:
        report = await pull_sources.update(
            name, config=body.config, exclude_patterns=body.exclude_patterns
        )
        return SourceResponse.of(report)

    @router.post("/sources/{name}/check", responses=_PULL_ONLY_PROBLEMS)
    async def check(name: str) -> ConnectionCheckResponse:
        return ConnectionCheckResponse.of(await pull_sources.check(name))

    @router.post("/sources/{name}/pause", responses=_PULL_ONLY_PROBLEMS)
    async def pause(name: str) -> SourceResponse:
        return SourceResponse.of(await pull_sources.set_paused(name, paused=True))

    @router.post("/sources/{name}/resume", responses=_PULL_ONLY_PROBLEMS)
    async def resume(name: str) -> SourceResponse:
        return SourceResponse.of(await pull_sources.set_paused(name, paused=False))

    return router
