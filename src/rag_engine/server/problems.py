"""에러 봉투. RFC 9457 Problem Details에 우리 `code`를 더한 모양이다(ADR 0015).

REST의 오류 응답(`application/problem+json`)과 MCP 도구 오류가 같은 `code`를 쓴다. 어느 오류든
`detail`에 질의나 문서 내용을 넣지 않는다(원칙 V).
"""

from collections.abc import Mapping
from typing import Final, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import ErrorDetails

from rag_engine.domain.errors import PROBLEM_ERROR_CODES, TOOL_ERROR_CODES, ErrorCode

PROBLEM_MEDIA_TYPE: Final = "application/problem+json"

# 코드마다 내는 HTTP 상태. 도구 오류의 `status`도 같은 표를 쓴다. `invalid_argument`는 도구 입력의
# 검증 실패라 REST의 `validation_error`와 같은 422다.
ERROR_STATUS: Final[Mapping[ErrorCode, int]] = {
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.INVALID_ARGUMENT: 422,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.KNOWLEDGE_BASE_NOT_FOUND: 404,
    ErrorCode.GROUP_NOT_FOUND: 404,
    ErrorCode.JOB_NOT_FOUND: 404,
    ErrorCode.TOKEN_NOT_FOUND: 404,
    ErrorCode.SOURCE_NOT_FOUND: 404,
    ErrorCode.UPLOAD_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
    ErrorCode.REINDEX_IN_PROGRESS: 409,
    ErrorCode.SOURCE_ALREADY_EXISTS: 409,
    ErrorCode.WRONG_SOURCE_KIND: 409,
    ErrorCode.SOURCE_FOLDER_OVERLAP: 409,
    ErrorCode.SYNC_IN_PROGRESS: 409,
    ErrorCode.SYNC_RECORD_NOT_FOUND: 404,
    ErrorCode.SOURCE_DELETED: 409,
    ErrorCode.SOURCE_PROTECTED: 409,
    ErrorCode.SOURCE_NOT_DELETED: 409,
    ErrorCode.SOURCE_CHANGE_IN_PROGRESS: 409,
    ErrorCode.SOURCE_RETENTION_EXPIRED: 409,
    ErrorCode.DOCUMENT_NOT_DELETED: 409,
    ErrorCode.SEARCH_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


# 코드마다 사람이 읽는 짧은 제목. REST 오류 응답과 도구 오류가 같은 표를 쓴다.
ERROR_TITLE: Final[Mapping[ErrorCode, str]] = {
    ErrorCode.UNAUTHENTICATED: "인증이 필요하다",
    ErrorCode.TOKEN_EXPIRED: "토큰이 만료되었다",
    ErrorCode.FORBIDDEN: "권한이 없다",
    ErrorCode.VALIDATION_ERROR: "입력이 올바르지 않다",
    ErrorCode.INVALID_ARGUMENT: "입력이 올바르지 않다",
    ErrorCode.DOCUMENT_NOT_FOUND: "문서를 찾을 수 없다",
    ErrorCode.KNOWLEDGE_BASE_NOT_FOUND: "지식베이스를 찾을 수 없다",
    ErrorCode.GROUP_NOT_FOUND: "그룹을 찾을 수 없다",
    ErrorCode.JOB_NOT_FOUND: "작업을 찾을 수 없다",
    ErrorCode.TOKEN_NOT_FOUND: "토큰을 찾을 수 없다",
    ErrorCode.SOURCE_NOT_FOUND: "원천을 찾을 수 없다",
    ErrorCode.UPLOAD_TOO_LARGE: "업로드가 너무 크다",
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: "지원하지 않는 형식이다",
    ErrorCode.REINDEX_IN_PROGRESS: "재색인이 이미 진행 중이다",
    ErrorCode.SOURCE_ALREADY_EXISTS: "같은 이름의 원천이 이미 있다",
    ErrorCode.WRONG_SOURCE_KIND: "원천의 갈래가 맞지 않는다",
    ErrorCode.SOURCE_FOLDER_OVERLAP: "다른 원천의 폴더와 겹친다",
    ErrorCode.SYNC_IN_PROGRESS: "같은 원천의 동기화가 이미 진행 중이다",
    ErrorCode.SYNC_RECORD_NOT_FOUND: "동기화 기록을 찾을 수 없다",
    ErrorCode.SOURCE_DELETED: "지운 원천이다",
    ErrorCode.SOURCE_PROTECTED: "지울 수 없는 원천이다",
    ErrorCode.SOURCE_NOT_DELETED: "지워지지 않은 원천이다",
    ErrorCode.SOURCE_CHANGE_IN_PROGRESS: "원천을 지우거나 되살리는 작업이 끝나지 않았다",
    ErrorCode.SOURCE_RETENTION_EXPIRED: "보관 기간이 지나 되살릴 수 없다",
    ErrorCode.DOCUMENT_NOT_DELETED: "지워지지 않은 문서다",
    ErrorCode.SEARCH_UNAVAILABLE: "검색을 쓸 수 없다",
    ErrorCode.INTERNAL_ERROR: "서버 내부 오류",
}


class _ProblemBase(BaseModel):
    """세 오류 모델이 함께 쓰는 칸. 어느 코드를 받는지는 모델마다 다르다."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(default="about:blank", description="문제 유형. 지금은 늘 `about:blank`다.")
    title: str = Field(description="사람이 읽는 짧은 제목")
    status: int = Field(description="HTTP 상태 코드")
    code: ErrorCode = Field(description="기계가 읽는 오류 코드")
    request_id: UUID = Field(description="요청 ID(UUIDv7). 응답 헤더 `X-Request-Id`와 같다")
    detail: str | None = Field(default=None, description="자세한 설명(선택)")

    @model_validator(mode="after")
    def _status_matches_code(self) -> Self:
        expected = ERROR_STATUS[self.code]
        if self.status != expected:
            raise ValueError(f"`{self.code}`의 상태는 {expected}이다(받은 값 {self.status})")
        return self


class ProblemDetails(_ProblemBase):
    """REST 오류 응답의 본문. `detail`은 선택이고 질의나 문서 내용을 담지 않는다."""

    @field_validator("code")
    @classmethod
    def _code_is_listed(cls, code: ErrorCode) -> ErrorCode:
        if code not in PROBLEM_ERROR_CODES:
            raise ValueError(f"Problem Details의 코드가 아니다: {code}")
        return code


class ValidationIssue(BaseModel):
    """입력 검증 오류 하나. 입력 값(`input`)과 `ctx`는 싣지 않는다."""

    model_config = ConfigDict(frozen=True)

    loc: list[str | int] = Field(description="오류가 난 입력의 위치")
    type: str = Field(description="오류 유형")
    msg: str = Field(description="오류 메시지")


_UNION_TAG_ISSUES: Final = frozenset({"union_tag_not_found", "union_tag_invalid"})


def validation_issue_of(issue: ErrorDetails) -> ValidationIssue:
    """pydantic의 검증 오류 하나를 응답의 오류 하나로 옮긴다. 판별 유니온의 갈래 칸이 없거나
    틀린 오류는 위치가 `body`에서 끝난다. 그래서 위치 끝에 칸 이름을 더한다. 칸이 틀린 오류
    (`union_tag_invalid`)는 글이 클라이언트가 보낸 갈래 값을 되울리므로 그 값 대신 받을 수 있는
    값을 싣는다. 칸이 없는 오류(`union_tag_not_found`)의 글에는 보낸 값이 없어 그대로 둔다."""
    location = list(issue["loc"])
    message = issue["msg"]
    context = issue.get("ctx")
    if issue["type"] in _UNION_TAG_ISSUES and context is not None:
        # pydantic은 칸 이름과 받을 수 있는 값을 따옴표로 감싸 싣는다(`'kind'`, `'push', 'pull'`).
        location.append(str(context.get("discriminator", "")).strip("'"))
        if issue["type"] == "union_tag_invalid":
            expected = context.get("expected_tags", "")
            message = f"Input tag does not match any of the expected tags: {expected}"
    return ValidationIssue(loc=location, type=issue["type"], msg=message)


class ValidationProblem(_ProblemBase):
    """422 응답. `code`는 `validation_error`이고 `errors`가 더 붙는다."""

    errors: list[ValidationIssue] = Field(description="검증 오류 목록")

    @field_validator("code")
    @classmethod
    def _code_is_validation_error(cls, code: ErrorCode) -> ErrorCode:
        if code is not ErrorCode.VALIDATION_ERROR:
            raise ValueError("검증 오류의 코드는 validation_error 하나다")
        return code


class ToolError(_ProblemBase):
    """MCP 도구 오류. `isError`가 참인 결과의 글 내용 하나에 이 모양의 JSON 문자열이 든다.

    인증 실패는 도구에 닿기 전에 미들웨어가 401로 낸다(Problem Details).
    """

    @field_validator("code")
    @classmethod
    def _code_is_tool_code(cls, code: ErrorCode) -> ErrorCode:
        if code not in TOOL_ERROR_CODES:
            raise ValueError(f"도구 오류의 코드가 아니다: {code}")
        return code
