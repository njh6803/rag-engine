"""문서 되살리기의 관리 API(source-sync 명세 "문서 되살리기", 스토리 33). `admin` 토큰의 몫이다.

`POST /documents/{document_id}/restore`는 밀어 넣는 원천의 지운 문서 하나를 되살려 200으로 답한다.
응답은 되살린 문서와, 되돌릴 조각이 없는 색인 판이 있어 넣은 색인 작업의 식별자(없으면 null)다.
없는 문서와 삭제 기록은 404 `document_not_found`, 지워지지 않은 문서는 409 `document_not_deleted`,
가져오는 원천의 문서는 409 `wrong_source_kind`, 지운 원천의 문서는 409 `source_deleted`다. 보관
기간이 지났는지는 보지 않는다. 가져오는 원천의 문서는 API로 되살리지 않고, 원천 폴더에 파일을 되돌려
놓으면 다음 동기화가 되살린다.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request

from rag_engine.app.admin_queries import get_document_report
from rag_engine.app.restore_document import restore_document
from rag_engine.domain.ports import UnitOfWork
from rag_engine.server.admin_models import DocumentResponse, DocumentRestoredResponse
from rag_engine.server.api_version import API_VERSION
from rag_engine.server.problems import ProblemDetails
from rag_engine.server.request_context import request_id_of

_RESTORE_PROBLEMS: dict[int | str, dict[str, object]] = {
    404: {"model": ProblemDetails, "description": "그 ID의 문서가 없다(`document_not_found`)"},
    409: {
        "model": ProblemDetails,
        "description": (
            "지워지지 않은 문서다(`document_not_deleted`)거나 가져오는 원천의 문서다"
            "(`wrong_source_kind`)거나 지운 원천의 문서다(`source_deleted`)"
        ),
    },
}


def build_admin_document_router(unit_of_work: UnitOfWork) -> APIRouter:
    router = APIRouter(prefix=f"/api/{API_VERSION}/admin")

    @router.post("/documents/{document_id}/restore", responses=_RESTORE_PROBLEMS)
    async def restore(document_id: UUID, request: Request) -> DocumentRestoredResponse:
        restored = await restore_document(
            unit_of_work,
            document_id,
            request_id=request_id_of(request.scope),
            now=datetime.now(UTC),
        )
        # 되살린 작업 단위가 끝난 뒤 읽는다. 그 사이 다른 요청이 문서를 다시 지우면 응답의 문서가
        # 이미 다시 지워진 모양(`deleted_at`이 찬 것)일 수 있다. 되살리기는 그 전에 끝나 있다.
        report = await get_document_report(unit_of_work, restored.document_id)
        return DocumentRestoredResponse(
            document=DocumentResponse.of(report), job_id=restored.job_id
        )

    return router
