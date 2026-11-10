"""Problem Details와 도구 오류의 모양(명세 "관리 API", "MCP 도구", ADR 0015)."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from rag_engine.domain.errors import PROBLEM_ERROR_CODES, TOOL_ERROR_CODES, ErrorCode
from rag_engine.server.problems import (
    ERROR_STATUS,
    PROBLEM_MEDIA_TYPE,
    ProblemDetails,
    ToolError,
    ValidationIssue,
    ValidationProblem,
)

_REQUEST_ID = UUID("0198f4a0-0000-7000-8000-000000000002")


def test_미디어_타입은_application_problem_json이다() -> None:
    assert PROBLEM_MEDIA_TYPE == "application/problem+json"


def test_모든_HTTP_코드와_도구_코드에_상태가_있다() -> None:
    assert set(ERROR_STATUS) == PROBLEM_ERROR_CODES | TOOL_ERROR_CODES


def test_Problem_Details는_type_title_status_code_request_id를_담고_detail은_선택이다() -> None:
    problem = ProblemDetails(
        title="문서를 찾을 수 없다",
        status=404,
        code=ErrorCode.DOCUMENT_NOT_FOUND,
        request_id=_REQUEST_ID,
    )

    assert problem.model_dump(mode="json", exclude_none=True) == {
        "type": "about:blank",
        "title": "문서를 찾을 수 없다",
        "status": 404,
        "code": "document_not_found",
        "request_id": str(_REQUEST_ID),
    }


def test_Problem_Details에_작업_전용_코드를_주면_거부한다() -> None:
    with pytest.raises(ValidationError, match="Problem Details의 코드가 아니다"):
        ProblemDetails(title="t", status=500, code=ErrorCode.PARSE_FAILED, request_id=_REQUEST_ID)


def test_상태가_코드의_상태와_다르면_거부한다() -> None:
    with pytest.raises(ValidationError, match="상태는 404이다"):
        ProblemDetails(
            title="t", status=500, code=ErrorCode.DOCUMENT_NOT_FOUND, request_id=_REQUEST_ID
        )
    with pytest.raises(ValidationError, match="상태는 503이다"):
        ToolError(title="t", status=500, code=ErrorCode.SEARCH_UNAVAILABLE, request_id=_REQUEST_ID)


def test_422_본문은_validation_error_코드와_errors_배열을_담는다() -> None:
    problem = ValidationProblem(
        title="입력이 올바르지 않다",
        status=422,
        code=ErrorCode.VALIDATION_ERROR,
        request_id=_REQUEST_ID,
        errors=[ValidationIssue(loc=["body", "metadata"], type="value_error", msg="JSON 객체")],
    )

    dumped = problem.model_dump(mode="json", exclude_none=True)

    assert dumped["code"] == "validation_error"
    assert dumped["errors"] == [
        {"loc": ["body", "metadata"], "type": "value_error", "msg": "JSON 객체"}
    ]
    assert set(ValidationIssue.model_json_schema()["properties"]) == {"loc", "type", "msg"}


def test_422_본문의_코드가_validation_error가_아니면_거부한다() -> None:
    with pytest.raises(ValidationError, match="validation_error 하나다"):
        ValidationProblem(
            title="t", status=422, code=ErrorCode.FORBIDDEN, request_id=_REQUEST_ID, errors=[]
        )


@pytest.mark.parametrize("code", sorted(TOOL_ERROR_CODES))
def test_도구_오류는_도구_코드_다섯을_받는다(code: ErrorCode) -> None:
    error = ToolError(title="t", status=ERROR_STATUS[code], code=code, request_id=_REQUEST_ID)

    assert error.code is code


def test_도구_오류에_도구_밖의_코드를_주면_거부한다() -> None:
    with pytest.raises(ValidationError, match="도구 오류의 코드가 아니다"):
        ToolError(title="t", status=401, code=ErrorCode.UNAUTHENTICATED, request_id=_REQUEST_ID)


def test_도구_오류는_JSON_문자열로_직렬화되어_Problem_Details와_같은_칸을_낸다() -> None:
    error = ToolError(
        title="지식베이스를 찾을 수 없다",
        status=404,
        code=ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
        request_id=_REQUEST_ID,
    )

    restored = ToolError.model_validate_json(error.model_dump_json(exclude_none=True))

    assert restored == error
    assert set(error.model_dump(exclude_none=True)) == {
        "type",
        "title",
        "status",
        "code",
        "request_id",
    }
