"""오류 응답을 짓는다. 본문은 Problem Details(`application/problem+json`)이고 요청 ID를 싣는다
(ADR 0015). 미들웨어(FastAPI 앱 바깥)와 예외 처리기가 같은 길을 쓴다."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from starlette.responses import JSONResponse

from rag_engine.domain.errors import ErrorCode
from rag_engine.server.problems import (
    ERROR_STATUS,
    ERROR_TITLE,
    PROBLEM_MEDIA_TYPE,
    ProblemDetails,
    ValidationIssue,
    ValidationProblem,
)


def problem_response(
    code: ErrorCode,
    request_id: UUID,
    *,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    problem = ProblemDetails(
        title=ERROR_TITLE[code],
        status=ERROR_STATUS[code],
        code=code,
        request_id=request_id,
        detail=detail,
    )
    return JSONResponse(
        problem.model_dump(mode="json", exclude_none=True),
        status_code=problem.status,
        headers=headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )


def validation_response(request_id: UUID, issues: Sequence[ValidationIssue]) -> JSONResponse:
    problem = ValidationProblem(
        title=ERROR_TITLE[ErrorCode.VALIDATION_ERROR],
        status=ERROR_STATUS[ErrorCode.VALIDATION_ERROR],
        code=ErrorCode.VALIDATION_ERROR,
        request_id=request_id,
        errors=list(issues),
    )
    return JSONResponse(
        problem.model_dump(mode="json", exclude_none=True),
        status_code=problem.status,
        media_type=PROBLEM_MEDIA_TYPE,
    )
