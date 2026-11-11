"""수집 API의 요청·응답 모델. 경로의 `v1`이 판이다(원칙 VII, 명세 "수집 API").

칸을 더하는 것은 같은 판이고 칸을 지우거나 뜻을 바꾸면 `v2`다. 요청은 multipart이고 파일 `file`은
경로 처리기가 받는다. 아래 `IngestFields`는 나머지 폼 칸이다.
"""

import math
from typing import Annotated, Final
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from rag_engine.domain.entities import IngestAction

_METADATA: Final = TypeAdapter(dict[str, JsonValue])
_NUL: Final = "\x00"


def _is_finite(value: JsonValue) -> bool:
    """pydantic의 JSON 파서는 `NaN`과 `Infinity`를 받지만 JSON이 아니고 jsonb 열도 거부한다."""
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_finite(item) for item in value)
    if isinstance(value, dict):
        return all(_is_finite(item) for item in value.values())
    return True


def _has_nul(value: JsonValue) -> bool:
    """PostgreSQL의 글 칸과 jsonb는 NUL 문자를 받지 않는다. 값과 객체의 키를 모두 본다."""
    if isinstance(value, str):
        return _NUL in value
    if isinstance(value, list):
        return any(_has_nul(item) for item in value)
    if isinstance(value, dict):
        return any(_NUL in key or _has_nul(item) for key, item in value.items())
    return False


def _reject_nul(value: str) -> str:
    if _NUL in value:
        raise ValueError("NUL 문자(\\u0000)를 담을 수 없다")
    return value


# 삭제 요청의 키(쿼리 매개변수). 키는 text 칸에 들어가므로 비어 있거나 NUL을 담으면 422다.
DocumentKey = Annotated[
    str,
    Field(min_length=1, description="지울 문서의 키. URL 인코딩한 쿼리 매개변수다"),
    AfterValidator(_reject_nul),
]


class IngestFields(BaseModel):
    """`POST /api/v1/ingest/documents`의 폼 칸(파일 제외)."""

    model_config = ConfigDict(frozen=True)

    key: str | None = Field(default=None, description="원천 안의 문서 키. 없으면 파일 이름이다")
    group: str | None = Field(default=None, description="그룹 이름. 없으면 기본 그룹이다")
    metadata: dict[str, JsonValue] = Field(
        default_factory=dict, description="문서의 메타데이터(JSON 객체 문자열로 받는다)"
    )
    updated_at: AwareDatetime | None = Field(
        default=None, description="문서의 갱신일(ISO 8601, 오프셋 포함). 없으면 수집 시각이다"
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def _parse_metadata(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            return _METADATA.validate_json(value)
        except ValidationError as error:
            raise ValueError("metadata는 JSON 객체 문자열이어야 한다") from error

    @field_validator("metadata")
    @classmethod
    def _metadata_is_storable(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not _is_finite(value):
            raise ValueError("metadata는 NaN이나 무한대를 담을 수 없다")
        if _has_nul(value):
            raise ValueError("metadata는 NUL 문자(\\u0000)를 담을 수 없다")
        return value

    @field_validator("key", "group")
    @classmethod
    def _text_has_no_nul(cls, value: str | None) -> str | None:
        if value is not None and _NUL in value:
            raise ValueError("NUL 문자(\\u0000)를 담을 수 없다")
        return value


class IngestResponse(BaseModel):
    """수집 응답. `job_id`는 작업이 없으면 null이다.

    작업이 없는 경우는 `unchanged`와, 보관 조각이 대상 판을 모두 채운 `restored`다.
    """

    model_config = ConfigDict(frozen=True)

    action: IngestAction = Field(description="수집이 문서에 한 일")
    document_id: UUID = Field(description="문서의 식별자(UUIDv7)")
    job_id: UUID | None = Field(description="넣은 작업의 식별자. 작업이 없으면 null")
