"""오류 코드와 이 저장소의 예외 계층. 코드의 이름은 이 파일 한 자리에서만 정의한다.

작업 코드 열넷(`internal_error` 포함)과 HTTP·도구 코드 전부가 `ErrorCode` 하나에 든다. 뒤의 티켓은
이 자리의 이름만 쓰고 문자열을 새로 짓지 않는다(명세 "수집 파이프라인과 작업", "관리 API", "MCP
도구").

예외의 메시지는 이 저장소가 쓴 글만 담는다. 서드파티 예외의 메시지는 옮기지 않는다. 질의, 문서 내용,
연결 정보가 들 수 있어서다(원칙 V, ADR 0015).
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    # 작업 코드. 문서 상태·색인 상태·작업 행의 오류 코드 칸에 쓴다.
    PARSE_TIMEOUT = "parse_timeout"
    PARSE_MEMORY_EXCEEDED = "parse_memory_exceeded"
    PARSE_FAILED = "parse_failed"
    TOO_MANY_PAGES = "too_many_pages"
    DOCUMENT_TOO_LARGE = "document_too_large"
    COMPRESSED_TOO_LARGE = "compressed_too_large"
    ENCRYPTED_DOCUMENT = "encrypted_document"
    EMBEDDING_REJECTED = "embedding_rejected"
    EMBEDDING_DIMENSION_MISMATCH = "embedding_dimension_mismatch"
    EMBEDDING_UNAVAILABLE = "embedding_unavailable"
    DATABASE_UNAVAILABLE = "database_unavailable"
    BLOB_STORE_ERROR = "blob_store_error"
    INTERNAL_ERROR = "internal_error"
    WORKER_LOST = "worker_lost"
    # HTTP 와 도구의 코드. `internal_error` 는 위 작업 코드와 같은 값이다.
    UNAUTHENTICATED = "unauthenticated"
    TOKEN_EXPIRED = "token_expired"
    FORBIDDEN = "forbidden"
    VALIDATION_ERROR = "validation_error"
    DOCUMENT_NOT_FOUND = "document_not_found"
    KNOWLEDGE_BASE_NOT_FOUND = "knowledge_base_not_found"
    GROUP_NOT_FOUND = "group_not_found"
    JOB_NOT_FOUND = "job_not_found"
    TOKEN_NOT_FOUND = "token_not_found"
    UPLOAD_TOO_LARGE = "upload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    REINDEX_IN_PROGRESS = "reindex_in_progress"
    SEARCH_UNAVAILABLE = "search_unavailable"
    INVALID_ARGUMENT = "invalid_argument"


# 영구 실패의 코드. 다시 시도하지 않고 작업이 `failed`로 끝난다.
PERMANENT_FAILURE_CODES = frozenset(
    {
        ErrorCode.PARSE_TIMEOUT,
        ErrorCode.PARSE_MEMORY_EXCEEDED,
        ErrorCode.PARSE_FAILED,
        ErrorCode.TOO_MANY_PAGES,
        ErrorCode.DOCUMENT_TOO_LARGE,
        ErrorCode.COMPRESSED_TOO_LARGE,
        ErrorCode.ENCRYPTED_DOCUMENT,
        ErrorCode.EMBEDDING_REJECTED,
        ErrorCode.EMBEDDING_DIMENSION_MISMATCH,
    }
)

# 일시 실패의 코드. 백오프로 다시 예약하고 시도를 다 쓰면 재시도 소진으로 끝난다.
TRANSIENT_FAILURE_CODES = frozenset(
    {
        ErrorCode.EMBEDDING_UNAVAILABLE,
        ErrorCode.DATABASE_UNAVAILABLE,
        ErrorCode.BLOB_STORE_ERROR,
    }
)

# 작업 행과 문서·색인 상태의 오류 코드 칸에 들어갈 수 있는 값 열넷.
JOB_ERROR_CODES = (
    PERMANENT_FAILURE_CODES
    | TRANSIENT_FAILURE_CODES
    | frozenset({ErrorCode.INTERNAL_ERROR, ErrorCode.WORKER_LOST})
)

# 도구 오류(`isError`가 참인 결과)의 `code`로 낼 수 있는 값 다섯.
TOOL_ERROR_CODES = frozenset(
    {
        ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
        ErrorCode.DOCUMENT_NOT_FOUND,
        ErrorCode.INVALID_ARGUMENT,
        ErrorCode.SEARCH_UNAVAILABLE,
        ErrorCode.INTERNAL_ERROR,
    }
)

# Problem Details 의 `code`로 낼 수 있는 값 열넷.
PROBLEM_ERROR_CODES = frozenset(
    {
        ErrorCode.UNAUTHENTICATED,
        ErrorCode.TOKEN_EXPIRED,
        ErrorCode.FORBIDDEN,
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.DOCUMENT_NOT_FOUND,
        ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
        ErrorCode.GROUP_NOT_FOUND,
        ErrorCode.JOB_NOT_FOUND,
        ErrorCode.TOKEN_NOT_FOUND,
        ErrorCode.UPLOAD_TOO_LARGE,
        ErrorCode.UNSUPPORTED_MEDIA_TYPE,
        ErrorCode.REINDEX_IN_PROGRESS,
        ErrorCode.SEARCH_UNAVAILABLE,
        ErrorCode.INTERNAL_ERROR,
    }
)


class ConfigurationError(Exception):
    """운영자가 고칠 설정의 오류. 관리 명령이 메시지를 찍고 종료 코드 1로 끝난다. 설정 값은 메시지에
    싣지 않는다(비밀번호가 들 수 있다. 원칙 V). 작업 오류 코드나 HTTP 응답으로 나가는 오류가
    아니라서 오류 코드를 드는 `RagEngineError` 밖에 둔다."""


class DocumentAlreadyExistsError(Exception):
    """같은 (원천, 키)의 문서가 이미 있다. `DocumentStore.add`가 유일 제약의 위반을 이 예외로
    바꿔 올린다. 같은 키를 동시에 넣은 수집이 진 쪽에서 받고, 이긴 문서로 갱신을 다시 한다. 응답으로
    나가는 오류가 아니라서 오류 코드를 드는 `RagEngineError` 밖에 둔다."""


class AttemptLostError(Exception):
    """임대가 끝나 다른 작업자가 가져간 작업의 시도. 작업 행 조건(`JobQueue.hold_attempt`)이 알린다.
    그 시도는 문서에도 작업 행에도 쓰지 않고 버린다. 오류 코드를 드는 `RagEngineError` 밖에 둔다.
    응답이나 작업 결과로 나가는 오류가 아니라 시도를 멈추는 신호다."""


class RagEngineError(Exception):
    """이 저장소가 올리는 예외의 뿌리. 오류 코드를 든다."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class PermanentFailure(RagEngineError):
    """영구 실패. 같은 입력으로 다시 해도 같은 결과라 재시도하지 않는다."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        if code not in PERMANENT_FAILURE_CODES:
            raise ValueError(f"영구 실패의 코드가 아니다: {code}")
        super().__init__(code, message)


class TransientFailure(RagEngineError):
    """일시 실패. 시간이 지나면 풀릴 수 있어 백오프로 다시 예약한다."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        if code not in TRANSIENT_FAILURE_CODES:
            raise ValueError(f"일시 실패의 코드가 아니다: {code}")
        super().__init__(code, message)


class RequestError(RagEngineError):
    """요청을 거절하는 오류. HTTP 응답(Problem Details)과 도구 오류의 `code`가 된다."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        if code not in PROBLEM_ERROR_CODES | TOOL_ERROR_CODES:
            raise ValueError(f"요청 오류의 코드가 아니다: {code}")
        super().__init__(code, message)


class InvalidInput(RequestError):
    """입력 값 하나가 규칙에 어긋난다. 응답은 422 `validation_error`이고 `loc`이 어느 입력인지
    가리킨다(`loc`은 입력 칸의 이름이고 요청의 어느 자리인지는 바깥 층이 붙인다)."""

    def __init__(self, loc: tuple[str | int, ...], kind: str, message: str) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message)
        self.loc = loc
        self.kind = kind
