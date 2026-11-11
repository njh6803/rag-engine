"""수집 API(명세 "수집 API"). `POST /api/v1/ingest/documents`와 같은 경로의 `DELETE`이고 `admin`
토큰의 몫이다(인증 미들웨어가 `reader`의 REST를 막는다). 삭제는 소프트 삭제로 204이고, 이미 지운
문서도 204, 없는 키는 404 `document_not_found`, 키가 없거나 비었거나 NUL 문자를 담으면 422다.

`POST`는 `unchanged`만 200이고 나머지는 202다. 크기 상한은 멀티파트 파서가 임시 파일로 받아 알게 된
업로드 크기(`file.size`)로, 본문을 메모리로 읽기 전에 먼저 본다. `Content-Length`를 미리 보지는
않으므로 상한을 넘는 업로드도 디스크는 쓴다. 이 검사가 없어도 유스케이스가 같은 상한을 다시 보지만
그때는 본문이 이미 메모리에 올라 있다.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile

from rag_engine.app.delete_document import delete_document
from rag_engine.app.ingest import (
    IngestRequest,
    ensure_within_upload_limit,
    ingest_document,
)
from rag_engine.domain.entities import IngestAction
from rag_engine.domain.ports import BlobStore, UnitOfWork
from rag_engine.server.ingest_models import DocumentKey, IngestFields, IngestResponse
from rag_engine.server.problems import ProblemDetails
from rag_engine.server.request_context import request_id_of

_PROBLEMS: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그룹이 없다(`group_not_found`)"},
    413: {"model": ProblemDetails, "description": "업로드가 크기 상한을 넘었다"},
    415: {"model": ProblemDetails, "description": "PDF, DOCX, HWPX가 아니다"},
}


_DELETE_PROBLEMS: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 키의 문서가 없다(`document_not_found`)"},
}


def build_ingest_router(
    unit_of_work: UnitOfWork, blob_store: BlobStore, max_upload_bytes: int
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/ingest")

    @router.post("/documents", status_code=202, responses=_PROBLEMS)
    async def ingest(
        request: Request,
        response: Response,
        file: Annotated[UploadFile, File(description="문서 파일(PDF, DOCX, HWPX)")],
        fields: Annotated[IngestFields, Form()],
    ) -> IngestResponse:
        if file.size is not None:
            ensure_within_upload_limit(file.size, max_upload_bytes)
        result = await ingest_document(
            unit_of_work,
            blob_store,
            IngestRequest(
                filename=file.filename,
                data=await file.read(),
                key=fields.key,
                group=fields.group,
                metadata=fields.metadata,
                updated_at=fields.updated_at,
            ),
            request_id=request_id_of(request.scope),
            now=datetime.now(UTC),
            max_upload_bytes=max_upload_bytes,
        )
        if result.action is IngestAction.UNCHANGED:
            response.status_code = 200
        return IngestResponse(
            action=result.action, document_id=result.document_id, job_id=result.job_id
        )

    @router.delete("/documents", status_code=204, responses=_DELETE_PROBLEMS)
    async def delete(key: Annotated[DocumentKey, Query()]) -> Response:
        await delete_document(unit_of_work, key, now=datetime.now(UTC))
        return Response(status_code=204)

    return router
