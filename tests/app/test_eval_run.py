"""평가의 단계별 순위(티켓 search-eval 04, 명세 "진단용 검색과 단계").

`stage_ranking`은 한 번의 진단용 검색이 돌려준 줄(합집합)에서 단계의 순위 순으로 줄을 만든다. 진단용
검색은 합집합을 자르지 않아 한 줄의 `fused_rank`가 후보 수를 넘을 수 있고, 합친 뒤 단계는 그
줄을 순위 밖으로 둔다.
"""

from datetime import UTC, datetime
from uuid import uuid4

from rag_engine.app.eval_run import Stage, stage_ranking
from rag_engine.domain.entities import BlockKind, ChunkLocation, DiagnosedHit, SearchHit


def _hit(
    name: str, *, vector_rank: int | None, keyword_rank: int | None, fused_rank: int
) -> DiagnosedHit:
    return DiagnosedHit(
        hit=SearchHit(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source="기본",
            key=name,
            title=name,
            text=name,
            location=ChunkLocation(
                page=None, section=(), block_kind=BlockKind.PARAGRAPH, block_range=(0, 0)
            ),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            effective_date=None,
            access_groups=(),
            metadata={},
            rrf_score=0.0,
        ),
        ordinal=0,
        vector_rank=vector_rank,
        keyword_rank=keyword_rank,
        fused_rank=fused_rank,
    )


HITS = [
    _hit("c", vector_rank=3, keyword_rank=None, fused_rank=3),
    _hit("a", vector_rank=1, keyword_rank=2, fused_rank=1),
    _hit("d", vector_rank=None, keyword_rank=1, fused_rank=2),
]


def _keys(hits: list[DiagnosedHit]) -> list[str]:
    return [hit.hit.key for hit in hits]


def test_벡터만은_벡터_순위_순이고_벡터_후보에_들지_못한_줄은_뺀다() -> None:
    ranked = stage_ranking(HITS, Stage.VECTOR, ["낱말"], 50)

    assert _keys(ranked) == ["a", "c"]


def test_키워드만은_키워드_순위_순이고_키워드_후보에_들지_못한_줄은_뺀다() -> None:
    ranked = stage_ranking(HITS, Stage.KEYWORD, ["낱말"], 50)

    assert _keys(ranked) == ["d", "a"]


def test_키워드_토큰이_없으면_키워드만은_비어_있다() -> None:
    assert stage_ranking(HITS, Stage.KEYWORD, [], 50) == []


def test_합친_뒤는_합친_순위_순이다() -> None:
    ranked = stage_ranking(HITS, Stage.FUSED, ["낱말"], 50)

    assert _keys(ranked) == ["a", "d", "c"]


def test_합친_뒤는_합친_순위가_후보_수_밖인_줄을_뺀다() -> None:
    ranked = stage_ranking(HITS, Stage.FUSED, ["낱말"], 2)

    assert _keys(ranked) == ["a", "d"]
