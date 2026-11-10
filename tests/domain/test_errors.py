"""오류 코드는 한 자리에서 정의되고, 예외는 자기 갈래의 코드만 받는다(명세 "수집 파이프라인과
작업")."""

import pytest

from rag_engine.domain.errors import (
    JOB_ERROR_CODES,
    PERMANENT_FAILURE_CODES,
    PROBLEM_ERROR_CODES,
    TOOL_ERROR_CODES,
    TRANSIENT_FAILURE_CODES,
    ErrorCode,
    InvalidInput,
    PermanentFailure,
    RequestError,
    TransientFailure,
)

# 명세가 적은 작업 코드 열넷. 명세의 문장에서 옮긴 것이라 코드와 따로 늘어나지 않는다.
SPEC_JOB_CODES = {
    "parse_timeout",
    "parse_memory_exceeded",
    "parse_failed",
    "too_many_pages",
    "document_too_large",
    "compressed_too_large",
    "encrypted_document",
    "embedding_rejected",
    "embedding_dimension_mismatch",
    "embedding_unavailable",
    "database_unavailable",
    "blob_store_error",
    "internal_error",
    "worker_lost",
}

# Problem Details 의 코드 목록(명세 "관리 API").
SPEC_PROBLEM_CODES = {
    "unauthenticated",
    "token_expired",
    "forbidden",
    "validation_error",
    "document_not_found",
    "knowledge_base_not_found",
    "group_not_found",
    "job_not_found",
    "token_not_found",
    "upload_too_large",
    "unsupported_media_type",
    "reindex_in_progress",
    "search_unavailable",
    "internal_error",
}

# 도구 오류의 코드(명세 "MCP 도구").
SPEC_TOOL_CODES = {
    "knowledge_base_not_found",
    "document_not_found",
    "invalid_argument",
    "search_unavailable",
    "internal_error",
}


def test_작업_코드_열넷이_모두_정의되어_있다() -> None:
    assert {code.value for code in JOB_ERROR_CODES} == SPEC_JOB_CODES


def test_HTTP_코드_열넷이_모두_정의되어_있다() -> None:
    assert {code.value for code in PROBLEM_ERROR_CODES} == SPEC_PROBLEM_CODES


def test_도구_오류_코드_다섯이_모두_정의되어_있다() -> None:
    assert {code.value for code in TOOL_ERROR_CODES} == SPEC_TOOL_CODES


def test_정의된_코드는_작업_코드와_HTTP_도구_코드의_합집합이다() -> None:
    expected = SPEC_JOB_CODES | SPEC_PROBLEM_CODES | SPEC_TOOL_CODES

    assert {code.value for code in ErrorCode} == expected


def test_영구_실패와_일시_실패의_코드는_겹치지_않는다() -> None:
    assert PERMANENT_FAILURE_CODES & TRANSIENT_FAILURE_CODES == frozenset()


@pytest.mark.parametrize("code", sorted(PERMANENT_FAILURE_CODES))
def test_영구_실패는_영구_코드를_받는다(code: ErrorCode) -> None:
    error = PermanentFailure(code, "메시지")

    assert error.code is code
    assert str(error) == "메시지"


@pytest.mark.parametrize("code", sorted(TRANSIENT_FAILURE_CODES))
def test_일시_실패는_일시_코드를_받는다(code: ErrorCode) -> None:
    assert TransientFailure(code, "메시지").code is code


def test_영구_실패에_일시_코드를_주면_거부한다() -> None:
    with pytest.raises(ValueError, match="영구 실패의 코드가 아니다"):
        PermanentFailure(ErrorCode.DATABASE_UNAVAILABLE, "메시지")


def test_일시_실패에_영구_코드를_주면_거부한다() -> None:
    with pytest.raises(ValueError, match="일시 실패의 코드가 아니다"):
        TransientFailure(ErrorCode.PARSE_FAILED, "메시지")


def test_internal_error와_worker_lost는_영구도_일시도_아니다() -> None:
    for code in (ErrorCode.INTERNAL_ERROR, ErrorCode.WORKER_LOST):
        assert code in JOB_ERROR_CODES
        assert code not in PERMANENT_FAILURE_CODES | TRANSIENT_FAILURE_CODES


def test_요청_오류는_HTTP_코드와_도구_코드를_받는다() -> None:
    assert RequestError(ErrorCode.GROUP_NOT_FOUND, "없는 그룹").code is ErrorCode.GROUP_NOT_FOUND
    assert (
        RequestError(ErrorCode.INVALID_ARGUMENT, "잘못된 인자").code is ErrorCode.INVALID_ARGUMENT
    )


def test_요청_오류에_작업_전용_코드를_주면_거부한다() -> None:
    with pytest.raises(ValueError, match="요청 오류의 코드가 아니다"):
        RequestError(ErrorCode.PARSE_FAILED, "메시지")


def test_입력_오류는_validation_error_코드와_입력_칸을_싣는다() -> None:
    error = InvalidInput(("name",), "string_too_short", "이름이 비어 있다")

    assert isinstance(error, RequestError)
    assert error.code is ErrorCode.VALIDATION_ERROR
    assert (error.loc, error.kind, str(error)) == (
        ("name",),
        "string_too_short",
        "이름이 비어 있다",
    )
