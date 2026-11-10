"""MCP 도구 셋의 출력 모델과 `format_version`(명세 "MCP 도구", 원칙 VII)."""

from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import BaseModel

from rag_engine.domain.entities import BlockKind
from rag_engine.server.tool_models import (
    FORMAT_VERSION,
    DocumentOutput,
    KnowledgeBasesOutput,
    KnowledgeBaseSummary,
    SearchLocation,
    SearchOutput,
    SearchResult,
)

_ID = UUID("0198f4a0-0000-7000-8000-000000000001")
_NOW = datetime(2026, 11, 10, 9, 30, tzinfo=UTC)


def _result() -> SearchResult:
    return SearchResult(
        chunk_id=_ID,
        document_id=_ID,
        source="default",
        key="규정/휴가.pdf",
        title="휴가 규정",
        text="연차는 15일이다.",
        location=SearchLocation(
            page=3, section=["제2장", "제5조"], block_kind=BlockKind.PARAGRAPH, block_range=(4, 6)
        ),
        updated_at=_NOW,
        effective_date=None,
        access_groups=[],
        metadata={"부서": "인사"},
        score=0.5,
        rank=1,
    )


def test_첫_판의_format_version은_1_0_0이다() -> None:
    assert FORMAT_VERSION == "1.0.0"


@pytest.mark.parametrize("model", [SearchOutput, DocumentOutput, KnowledgeBasesOutput])
def test_세_도구의_출력_스키마는_format_version을_필수로_공개한다(model: type[BaseModel]) -> None:
    for mode in ("validation", "serialization"):
        schema = model.model_json_schema(mode=mode)

        assert "format_version" in schema["required"]


def test_검색_출력은_판과_쓴_지식베이스와_결과를_담는다() -> None:
    output = SearchOutput(
        format_version=FORMAT_VERSION, knowledge_base="default", results=[_result()]
    )

    dumped = output.model_dump(mode="json")

    assert dumped["format_version"] == "1.0.0"
    assert dumped["knowledge_base"] == "default"
    assert set(dumped["results"][0]) == {
        "chunk_id",
        "document_id",
        "source",
        "key",
        "title",
        "text",
        "location",
        "updated_at",
        "effective_date",
        "access_groups",
        "metadata",
        "score",
        "rank",
    }
    assert set(dumped["results"][0]["location"]) == {"page", "section", "block_kind", "block_range"}


def test_시각은_UTC_Z로_나온다() -> None:
    dumped = _result().model_dump(mode="json")

    assert dumped["updated_at"] == "2026-11-10T09:30:00Z"


def test_다른_오프셋의_시각도_UTC_Z로_나온다() -> None:
    result = _result().model_dump()
    result["updated_at"] = datetime(2026, 11, 10, 18, 30, tzinfo=timezone(timedelta(hours=9)))

    dumped = SearchResult.model_validate(result).model_dump(mode="json")

    assert dumped["updated_at"] == "2026-11-10T09:30:00Z"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
def test_점수에_NaN이나_무한대가_있으면_거부한다(score: float) -> None:
    result = _result().model_dump()
    result["score"] = score

    with pytest.raises(ValueError, match="finite"):
        SearchResult.model_validate(result)


def test_위치의_쪽_번호와_블록_범위는_모양이_맞아야_한다() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        SearchLocation(page=0, section=[], block_kind=BlockKind.PARAGRAPH, block_range=(0, 0))
    with pytest.raises(ValueError, match="처음이 끝보다 클 수 없다"):
        SearchLocation(page=1, section=[], block_kind=BlockKind.PARAGRAPH, block_range=(5, 2))
    with pytest.raises(ValueError, match="0 이상의"):
        SearchLocation(page=1, section=[], block_kind=BlockKind.PARAGRAPH, block_range=(-1, 2))


def test_오프셋이_없는_시각은_거부한다() -> None:
    result = _result().model_dump()
    result["updated_at"] = datetime(2026, 11, 10, 9, 30)  # noqa: DTZ001

    with pytest.raises(ValueError, match="timezone"):
        SearchResult.model_validate(result)


def test_쪽이_없는_조각의_위치는_page가_null이고_절이_없으면_section이_빈_배열이다() -> None:
    location = SearchLocation(
        page=None, section=[], block_kind=BlockKind.TABLE, block_range=(0, 0)
    ).model_dump(mode="json")

    assert location == {"page": None, "section": [], "block_kind": "table", "block_range": [0, 0]}


def test_순위는_1부터다() -> None:
    result = _result().model_dump()
    result["rank"] = 0

    with pytest.raises(ValueError, match="greater than or equal to 1"):
        SearchResult.model_validate(result)


def test_시행일은_날짜이고_지금은_비어_있다() -> None:
    assert _result().effective_date is None
    filled = _result().model_copy(update={"effective_date": date(2026, 1, 1)})

    assert filled.model_dump(mode="json")["effective_date"] == "2026-01-01"


def test_문서_조회의_text는_기본이_null이다() -> None:
    output = DocumentOutput(
        format_version=FORMAT_VERSION,
        document_id=_ID,
        source="default",
        key="k",
        title="t",
        group="default",
        mime="application/pdf",
        size_bytes=10,
        updated_at=_NOW,
        metadata={},
        chunk_counts={"default": 3},
    )

    assert output.text is None
    assert output.model_dump(mode="json")["chunk_counts"] == {"default": 3}


def test_지식베이스_목록은_이름_설명_문서_수_기본_여부를_담는다() -> None:
    output = KnowledgeBasesOutput(
        format_version=FORMAT_VERSION,
        knowledge_bases=[
            KnowledgeBaseSummary(name="default", description="", document_count=2, is_default=True)
        ],
    )

    assert output.model_dump(mode="json")["knowledge_bases"] == [
        {"name": "default", "description": "", "document_count": 2, "is_default": True}
    ]


def test_location의_뜻이_스키마_설명에_든다() -> None:
    properties = SearchLocation.model_json_schema()["properties"]

    assert "쪽 번호(1부터)" in properties["page"]["description"]
    assert "바깥에서 안쪽 순" in properties["section"]["description"]
    assert "양 끝을 포함" in properties["block_range"]["description"]
