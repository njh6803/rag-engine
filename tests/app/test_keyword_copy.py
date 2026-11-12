"""`copy_source_of`의 판정(명세 "수집 파이프라인과 작업"의 셋째 단계, 티켓 14).

건설 중인 판은 같은 지식베이스의 현재 판과 판 스키마, 임베딩 모델, 차원, 청킹 해시가 모두 같을
때만 조각을 복사해 온다. 토크나이저 판과 임베딩 끝점은 보지 않는다.
"""

from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

import pytest
from tests.records import make_index_version, make_knowledge_base
from tests.support.token_meters import CharMeter

from rag_engine.app.keyword_copy import copy_source_of, rebuild_keywords
from rag_engine.domain.entities import (
    BlockKind,
    ChunkingConfig,
    ChunkLocation,
    IndexVersion,
    IndexVersionStatus,
    StoredChunk,
)
from rag_engine.domain.identifiers import new_id

KNOWLEDGE_BASE = make_knowledge_base()
CURRENT = make_index_version(KNOWLEDGE_BASE, IndexVersionStatus.CURRENT)
BUILDING = replace(
    make_index_version(KNOWLEDGE_BASE, IndexVersionStatus.BUILDING),
    tokenizer_version="다른-토크나이저",
)


def _source(version: IndexVersion, live: list[IndexVersion]) -> UUID | None:
    found = copy_source_of(version, live)
    return None if found is None else found.id


def test_요소가_같고_토크나이저_판만_다르면_현재_판에서_복사한다() -> None:
    source = _source(BUILDING, [CURRENT, BUILDING])

    assert source == CURRENT.id, f"복사 원본이 {source}로 나왔다"


def test_임베딩_끝점이_달라도_현재_판에서_복사한다() -> None:
    moved = replace(BUILDING, embedding_endpoint="http://다른-서버:80")

    source = _source(moved, [CURRENT, moved])

    assert source == CURRENT.id, f"끝점만 달랐는데 복사 원본이 {source}로 나왔다"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", CURRENT.schema_version + 1),
        ("embedding_model", "다른/모델"),
        ("embedding_dimensions", CURRENT.embedding_dimensions + 1),
        ("chunking_hash", "다른해시"),
        ("knowledge_base_id", new_id()),
    ],
)
def test_복사_조건_하나라도_다르면_복사하지_않는다(field: str, value: str | int | UUID) -> None:
    changed = replace(BUILDING, **{field: value})

    source = _source(changed, [CURRENT, changed])

    assert source is None, f"{field}가 달라도 복사 원본이 {source}로 나왔다"


@pytest.mark.parametrize("status", [IndexVersionStatus.BUILDING, IndexVersionStatus.RETIRED])
def test_현재_판이_아닌_판에서는_복사하지_않는다(status: IndexVersionStatus) -> None:
    not_current = replace(CURRENT, status=status)

    source = _source(BUILDING, [not_current, BUILDING])

    assert source is None, f"{status.value} 판이 복사 원본 {source}로 나왔다"


@pytest.mark.parametrize("status", [IndexVersionStatus.CURRENT, IndexVersionStatus.RETIRED])
def test_건설_중인_판이_아니면_복사하지_않는다(status: IndexVersionStatus) -> None:
    not_building = replace(BUILDING, status=status)

    source = _source(not_building, [CURRENT, not_building])

    assert source is None, f"{status.value} 판이 복사 원본 {source}를 받았다"


class _CharEmbedder(CharMeter):
    """글자 하나가 토큰 하나인 가짜 임베더. `rebuild_keywords`는 토큰 수만 센다."""

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        raise AssertionError(f"복사 경로가 임베딩을 불렀다: {len(texts)}개")


def _stored(ordinal: int, section: tuple[str, ...], text: str) -> StoredChunk:
    return StoredChunk(
        ordinal=ordinal,
        text=text,
        token_count=len(text),
        location=ChunkLocation(
            page=None, section=section, block_kind=BlockKind.PARAGRAPH, block_range=(0, 0)
        ),
        embedding=(float(ordinal), 0.5),
        source_content_hash="해시",
    )


async def test_키워드를_되지을_때_절_경로를_상한_안으로_줄이고_임베딩은_그대로_둔다() -> None:
    # 조각 상한이 40토큰이라 절 경로 줄의 상한은 10토큰이고, 글자 하나가 토큰 하나다.
    version = replace(BUILDING, chunking=ChunkingConfig("structure_first", 40, 4))
    long_path = ("긴제목긴제목긴제목", "중간제목", "안쪽")
    short_path = ("짧은",)
    stored = [_stored(0, long_path, "본문"), _stored(1, short_path, "다른")]

    material = await rebuild_keywords(_CharEmbedder(), str.split, version, stored)

    assert material.keyword_texts == ["중간제목 > 안쪽 본문", "짧은 다른"], (
        f"되지은 키워드 글이 {material.keyword_texts}로 나왔다"
    )
    assert [draft.text for draft in material.drafts] == ["본문", "다른"]
    assert [draft.index_text for draft in material.drafts][0] == "중간제목 > 안쪽\n\n본문"
    assert material.embeddings == [chunk.embedding for chunk in stored]
