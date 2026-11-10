"""MCP 도구 셋(`search`, `get_document`, `list_knowledge_bases`)의 출력 모델과 `format_version`.

출력 스키마는 이 pydantic 모델에서 나오고 MCP 도구 목록의 outputSchema로 공개된다. 판은 결과 객체의
`format_version` 칸(semver 문자열)이고, 칸을 더하면 minor, 칸을 지우거나 뜻을 바꾸면 major다(원칙
VII, ADR 0015). 도구는 결과를 만들 때 `FORMAT_VERSION`을 직접 넣는다. 칸에 기본값이 없어
outputSchema의 `required`에 들고, 클라이언트는 이 칸이 늘 있다고 읽는다. 스키마와 판은
`tests/server/test_tool_models.py`가 보고, 도구가 이 모델로 답하는지는 도구를 구현하는 티켓이
`tests/contract/`에 더한다. 도구 이름은 고정이다.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Final, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from rag_engine.domain.entities import BlockKind

FORMAT_VERSION: Final = "1.0.0"


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# 오프셋이 있는 시각을 받아 UTC로 맞춘다. JSON에는 `Z`로 나간다.
type UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]

_VERSION_DESCRIPTION: Final = (
    "이 결과 형식의 판(semver). 칸을 더하면 minor, 지우거나 뜻을 바꾸면 major다"
)


class SearchLocation(BaseModel):
    """조각의 근거 위치. 조각이 덮는 블록들에서 만든다."""

    model_config = ConfigDict(frozen=True)

    page: int | None = Field(ge=1, description="첫 블록의 쪽 번호(1부터). 쪽이 없는 형식이면 null")
    section: list[str] = Field(
        description="절 경로의 제목 글을 바깥에서 안쪽 순으로 담는다. 절이 없으면 빈 배열"
    )
    block_kind: BlockKind = Field(description="첫 블록의 종류")
    block_range: tuple[int, int] = Field(
        description="조각이 덮은 블록 순번의 [처음, 끝]. 0부터이고 양 끝을 포함한다"
    )

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Self:
        first, last = self.block_range
        if first < 0 or last < first:
            raise ValueError("block_range는 0 이상의 [처음, 끝]이고 처음이 끝보다 클 수 없다")
        return self


class SearchResult(BaseModel):
    """검색 결과 하나. 같은 문서의 조각 여럿이 나와도 합치지 않는다."""

    model_config = ConfigDict(frozen=True)

    chunk_id: UUID = Field(description="조각의 식별자")
    document_id: UUID = Field(description="문서의 식별자")
    source: str = Field(description="원천의 이름")
    key: str = Field(description="원천 안의 문서 키")
    title: str = Field(description="문서의 제목")
    text: str = Field(description="조각 글. 절 경로는 포함하지 않고 `location.section`에 싣는다")
    location: SearchLocation = Field(description="근거 위치")
    updated_at: UtcDatetime = Field(description="문서의 갱신일(UTC)")
    effective_date: date | None = Field(description="시행일. 지금은 늘 null이다")
    access_groups: list[str] = Field(description="접근 그룹. 지금은 늘 빈 배열이다")
    metadata: dict[str, JsonValue] = Field(description="문서의 메타데이터")
    score: float = Field(
        allow_inf_nan=False, description="리랭커가 있으면 리랭크 점수, 없으면 RRF 점수"
    )
    rank: int = Field(ge=1, description="순위. 1부터")


class SearchOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    format_version: str = Field(description=_VERSION_DESCRIPTION)
    knowledge_base: str = Field(description="검색에 쓴 지식베이스의 이름")
    results: list[SearchResult] = Field(description="점수 순의 결과. 현재 판이 없으면 빈 배열")


class DocumentOutput(BaseModel):
    """`get_document`의 결과. 토큰 범위 밖 지식베이스는 `chunk_counts`에 이름도 내지 않는다."""

    model_config = ConfigDict(frozen=True)

    format_version: str = Field(description=_VERSION_DESCRIPTION)
    document_id: UUID = Field(description="문서의 식별자")
    source: str = Field(description="원천의 이름")
    key: str = Field(description="원천 안의 문서 키")
    title: str = Field(description="문서의 제목")
    group: str = Field(description="문서가 속한 그룹의 이름")
    mime: str = Field(description="문서의 MIME 형식")
    size_bytes: int = Field(description="원본의 바이트 수")
    updated_at: UtcDatetime = Field(description="문서의 갱신일(UTC)")
    metadata: dict[str, JsonValue] = Field(description="문서의 메타데이터")
    chunk_counts: dict[str, int] = Field(description="토큰 범위 안의 지식베이스 이름마다 조각 수")
    text: str | None = Field(
        default=None,
        description=(
            "`include_text`가 참일 때 파싱 결과의 블록 글을 빈 줄로 이은 글. 파싱 결과가 없거나 "
            "문서의 지금 내용과 맞지 않으면 null이다"
        ),
    )


class KnowledgeBaseSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(description="지식베이스의 이름")
    description: str = Field(description="지식베이스의 설명")
    document_count: int = Field(
        description="그 지식베이스의 그룹 집합에 드는 그룹의, 지워지지 않은 문서 수"
    )
    is_default: bool = Field(description="기본 지식베이스인지")


class KnowledgeBasesOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    format_version: str = Field(description=_VERSION_DESCRIPTION)
    knowledge_bases: list[KnowledgeBaseSummary] = Field(
        description="토큰 범위 안의 지식베이스. 범위 밖은 목록에서 뺀다"
    )
