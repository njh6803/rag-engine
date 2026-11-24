"""원천 관리 API(source-sync 명세 "관리 API", 스토리 1, 6, 8, 9, 24). 모두 `admin` 토큰의
몫이다(인증 미들웨어가 `reader`의 REST를 막는다).

`POST /sources`는 밀어 넣는 원천이나 가져오는 원천을 만들어 201로 답한다. 이름이 규칙에 어긋나거나
가져오는 원천의 폴더와 설정이 틀리면 422, 이름이 이미 있으면(지운 원천 포함) 409
`source_already_exists`, 다른 원천의 폴더와 겹치면 409 `source_folder_overlap`이다.
`GET /sources`와 `GET /sources/{name}`은 같은 모양의 원천을 낸다. 없는 이름은 404
`source_not_found`다. 목록은 `include_deleted=true`를 적어야 지운 원천도 낸다.

`DELETE /sources/{name}`은 지움 표시를 쓰고 원천 삭제 작업을 넣어 202와 그 작업의 식별자로
답한다. 문서를 옮기는 일은 작업자가 뒤에서 한다. `default`와 `upload`는 409 `source_protected`다.
원천 삭제나 되살리기 작업이 끝나지 않았으면 409 `source_change_in_progress`다. 지운 원천은 보기,
되살리기, 동기화 기록 보기만 받고, 고치기, 지우기, 연결 확인, 지금 동기화, 일시 중지, 다시 시작은
409 `source_deleted`다.

`POST /sources/{name}/restore`는 보관 기간(`RAG_DELETED_RETENTION_DAYS`) 안의 지운 원천을 되살린다.
지움 표시를 걷고 원천 되살리기 작업을 넣어 202와 그 작업의 식별자로 답한다. 가져오는 원천은
되살린 직후의 연결 확인(`connection_check`)도 함께 낸다. 지운 원천이 아니면 409
`source_not_deleted`, 보관 기간이 지났으면 409 `source_retention_expired`, 원천 삭제나 되살리기
작업이 끝나지 않았으면 409 `source_change_in_progress`, 서버 경로 원천의 폴더가 그사이 다른
원천과 겹치게 됐으면 409 `source_folder_overlap`이다.

`PATCH /sources/{name}`, `POST /sources/{name}/check`, `/sync`, `/pause`, `/resume`은 가져오는
원천에만 통한다. 밀어 넣는 원천에는 409 `wrong_source_kind`다. 연결 확인은 원천을 읽지 못해도
200이다.

만들기와 고치기는 `schedule`(다섯 칸 cron 표현식)을 받는다. 받지 않는 글(칸 수가 다섯이 아니거나
값이 틀리거나 오지 않는 날짜. 일과 요일을 둘 다 적으면 하나만 맞아도 도는 표현식이라 받는다)은 422
`validation_error`이고 `loc`의 끝이 `schedule`이다. 고칠 때 `null`은 일정을 없애고 칸을 적지 않으면
그대로 둔다. 응답의 `next_run_at`은 일정을 적거나 고칠 때, 일시 중지에서 다시 시작할 때 지금 다음의
시각으로 채우고, 일정을 없애거나 일시 중지하면 비운다.

`POST /sources/{name}/sync`는 동기화 작업과 동기화 기록(`queued`)을 한 작업 단위에서 만들어 202와 두
식별자로 답한다. 같은 원천의 동기화가 대기 중이거나 실행 중이면 409 `sync_in_progress`다.
`GET /sources/{name}/sync-records`는 기록을 최근 것부터 `limit`와 `after`로 내고,
`/sync-records/{record_id}`는 그 원천의 기록 하나를 낸다. 없는 기록은 404 `sync_record_not_found`다.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request

from rag_engine.app.admin_sources import (
    create_push_source,
    get_source_report,
    list_source_reports,
)
from rag_engine.app.delete_source import request_source_deletion
from rag_engine.app.pull_sources import PullSources, ScheduleChange
from rag_engine.app.restore_source import request_source_restoration, source_kind_of
from rag_engine.app.sync_requests import get_sync_record, list_sync_records, request_sync
from rag_engine.domain.entities import SourceKind
from rag_engine.domain.ports import UnitOfWork
from rag_engine.server.admin_api import DEFAULT_LIMIT, After, Limit
from rag_engine.server.admin_source_models import (
    ConnectionCheckResponse,
    CreatePullSourceRequest,
    CreateSourceRequest,
    SourceDeletionResponse,
    SourceListResponse,
    SourceResponse,
    SourceRestorationResponse,
    UpdateSourceRequest,
)
from rag_engine.server.admin_sync_models import (
    SyncRecordListResponse,
    SyncRecordResponse,
    SyncRequest,
    SyncRequestedResponse,
)
from rag_engine.server.api_version import API_VERSION
from rag_engine.server.problems import ProblemDetails
from rag_engine.server.request_context import request_id_of

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
            "밀어 넣는 원천이다(`wrong_source_kind`)거나 지운 원천이다(`source_deleted`). 설정을 "
            "고칠 때는 다른 원천의 폴더와 겹치는 것(`source_folder_overlap`)도 409다"
        ),
    },
}
_SYNC_PROBLEMS: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 이름의 원천이 없다(`source_not_found`)"},
    409: {
        "model": ProblemDetails,
        "description": (
            "밀어 넣는 원천이다(`wrong_source_kind`)거나 지운 원천이다(`source_deleted`)거나 그 "
            "원천의 동기화가 대기 중이거나 실행 중이다(`sync_in_progress`)"
        ),
    },
}
_DELETE_PROBLEMS: dict[int | str, dict[str, object]] = {
    **_NOT_FOUND,
    409: {
        "model": ProblemDetails,
        "description": (
            "`default`와 `upload`는 지울 수 없다(`source_protected`). 이미 지운 원천이다"
            "(`source_deleted`). 원천을 지우거나 되살리는 작업이 아직 끝나지 않았다"
            "(`source_change_in_progress`)"
        ),
    },
}
_RESTORE_PROBLEMS: dict[int | str, dict[str, object]] = {
    **_NOT_FOUND,
    409: {
        "model": ProblemDetails,
        "description": (
            "지운 원천이 아니다(`source_not_deleted`)거나 보관 기간이 지났다"
            "(`source_retention_expired`)거나 원천을 지우거나 되살리는 작업이 아직 끝나지 않았다"
            "(`source_change_in_progress`)거나 폴더가 다른 원천과 겹친다(`source_folder_overlap`)"
        ),
    },
}
_RECORD_NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {
        "model": ProblemDetails,
        "description": (
            "그 이름의 원천이 없거나(`source_not_found`) 그 원천에 그 식별자의 동기화 기록이 "
            "없다(`sync_record_not_found`)"
        ),
    },
}


def build_admin_source_router(
    unit_of_work: UnitOfWork, pull_sources: PullSources, retention_days: int
) -> APIRouter:
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
                schedule=body.schedule,
                now=now,
            )
        else:
            report = await create_push_source(unit_of_work, body.name, now=now)
        return SourceResponse.of(report)

    @router.get("/sources")
    async def sources(*, include_deleted: bool = False) -> SourceListResponse:
        found = await list_source_reports(unit_of_work, include_deleted=include_deleted)
        return SourceListResponse(sources=[SourceResponse.of(report) for report in found])

    @router.get("/sources/{name}", responses=_NOT_FOUND)
    async def source(name: str) -> SourceResponse:
        return SourceResponse.of(await get_source_report(unit_of_work, name))

    @router.delete("/sources/{name}", status_code=202, responses=_DELETE_PROBLEMS)
    async def delete(name: str, request: Request) -> SourceDeletionResponse:
        requested = await request_source_deletion(
            unit_of_work, name, request_id=request_id_of(request.scope), now=datetime.now(UTC)
        )
        return SourceDeletionResponse.of(requested)

    @router.post("/sources/{name}/restore", status_code=202, responses=_RESTORE_PROBLEMS)
    async def restore(name: str, request: Request) -> SourceRestorationResponse:
        request_id = request_id_of(request.scope)
        now = datetime.now(UTC)
        if await source_kind_of(unit_of_work, name) is SourceKind.PULL:
            restored = await pull_sources.restore(
                name, request_id=request_id, now=now, retention_days=retention_days
            )
            return SourceRestorationResponse.of_pull(restored)
        requested = await request_source_restoration(
            unit_of_work, name, request_id=request_id, now=now, retention_days=retention_days
        )
        return SourceRestorationResponse.of_push(requested)

    @router.patch("/sources/{name}", responses=_PULL_ONLY_PROBLEMS)
    async def update(name: str, body: UpdateSourceRequest) -> SourceResponse:
        report = await pull_sources.update(
            name,
            config=body.config,
            exclude_patterns=body.exclude_patterns,
            schedule=ScheduleChange(body.schedule) if body.schedule_given else None,
            now=datetime.now(UTC),
        )
        return SourceResponse.of(report)

    @router.post("/sources/{name}/check", responses=_PULL_ONLY_PROBLEMS)
    async def check(name: str) -> ConnectionCheckResponse:
        return ConnectionCheckResponse.of(await pull_sources.check(name))

    @router.post("/sources/{name}/sync", status_code=202, responses=_SYNC_PROBLEMS)
    async def sync(
        name: str, request: Request, body: SyncRequest | None = None
    ) -> SyncRequestedResponse:
        options = SyncRequest() if body is None else body
        requested = await request_sync(
            unit_of_work,
            name,
            apply_empty=options.apply_empty,
            reread=options.reread,
            request_id=request_id_of(request.scope),
            now=datetime.now(UTC),
        )
        return SyncRequestedResponse.of(requested)

    @router.get("/sources/{name}/sync-records", responses=_NOT_FOUND)
    async def sync_records(
        name: str, limit: Limit = DEFAULT_LIMIT, after: After = None
    ) -> SyncRecordListResponse:
        found = await list_sync_records(unit_of_work, name, limit=limit, after=after)
        return SyncRecordListResponse(
            sync_records=[SyncRecordResponse.of(record, name) for record in found]
        )

    @router.get("/sources/{name}/sync-records/{record_id}", responses=_RECORD_NOT_FOUND)
    async def sync_record(name: str, record_id: UUID) -> SyncRecordResponse:
        record = await get_sync_record(unit_of_work, name, record_id)
        return SyncRecordResponse.of(record, name)

    @router.post("/sources/{name}/pause", responses=_PULL_ONLY_PROBLEMS)
    async def pause(name: str) -> SourceResponse:
        report = await pull_sources.set_paused(name, paused=True, now=datetime.now(UTC))
        return SourceResponse.of(report)

    @router.post("/sources/{name}/resume", responses=_PULL_ONLY_PROBLEMS)
    async def resume(name: str) -> SourceResponse:
        report = await pull_sources.set_paused(name, paused=False, now=datetime.now(UTC))
        return SourceResponse.of(report)

    return router
