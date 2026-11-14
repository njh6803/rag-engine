"""놓친 질의의 탈락 지점과 낱말 겹침(티켓 search-eval 06, 명세 "놓친 까닭").

순수 함수라 진단용 검색이 돌려준 줄을 손으로 지어 넣고 값을 견준다. 닿는 조각은 문서의 키와 조각
순번 쌍으로 가리킨다.
"""

from datetime import UTC, datetime
from uuid import uuid4

from rag_engine.app.eval_misses import (
    ChunkRef,
    MissCause,
    classify_miss,
    reaching_chunks,
    word_overlap,
)
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.entities import BlockKind, ChunkLocation, DiagnosedHit, SearchHit
from rag_engine.domain.eval_set import EvidenceItem, PageEvidence, PassageEvidence

CANDIDATES = 5
PASSAGE = "연차휴가는 입사 일 년 뒤부터 발생한다"
ITEM = EvidenceItem(
    id="q1", evidence=(PassageEvidence(document="a.docx", passage=PASSAGE),), tags=()
)
# 문서 a의 조각 셋. 순번 1이 글귀를 온전히 담고 나머지는 담지 않는다.
CHUNKS = {
    "a.docx": [
        ChunkRef(ordinal=0, text="휴가 규정의 머리말", block_range=(0, 0)),
        ChunkRef(ordinal=1, text=f"{PASSAGE}. 그 밖의 말", block_range=(1, 2)),
        ChunkRef(ordinal=2, text="출장 규정", block_range=(3, 3)),
    ]
}
REACHING = frozenset({("a.docx", 1)})


def _hit(
    key: str, ordinal: int, *, vector: int | None, keyword: int | None, fused: int
) -> DiagnosedHit:
    return DiagnosedHit(
        hit=SearchHit(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source="기본",
            key=key,
            title=key,
            text="글",
            location=ChunkLocation(
                page=None, section=(), block_kind=BlockKind.PARAGRAPH, block_range=(0, 0)
            ),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            effective_date=None,
            access_groups=(),
            metadata={},
            rrf_score=0.0,
        ),
        ordinal=ordinal,
        vector_rank=vector,
        keyword_rank=keyword,
        fused_rank=fused,
    )


def test_닿는_조각을_문서의_키와_조각_순번_쌍으로_모은다() -> None:
    assert reaching_chunks(ITEM, CHUNKS, {}) == REACHING


def test_기대한_문서의_조각_가운데_닿는_것이_없으면_빈_집합이다() -> None:
    boundary = {
        "a.docx": [ChunkRef(0, "연차휴가는 입사 일 년", (0, 0)), ChunkRef(1, "발생한다", (1, 1))]
    }

    assert reaching_chunks(ITEM, boundary, {}) == frozenset()


def test_쪽으로_적은_기대_근거는_덮은_블록의_쪽이_기대한_쪽인_조각이_닿는다() -> None:
    item = EvidenceItem(id="q2", evidence=(PageEvidence(document="a.pdf", page=2),), tags=())
    chunks = {
        "a.pdf": [
            ChunkRef(ordinal=0, text="첫 쪽", block_range=(0, 0)),
            ChunkRef(ordinal=1, text="두 쪽에 걸친 조각", block_range=(1, 2)),
        ]
    }

    assert reaching_chunks(item, chunks, {"a.pdf": {0: 1, 1: 1, 2: 2}}) == {("a.pdf", 1)}


def test_닿는_조각이_색인에_없으면_no_matching_chunk다() -> None:
    cause = classify_miss(frozenset(), [], candidates=CANDIDATES, last_stage=Stage.FUSED)

    assert cause is MissCause.NO_MATCHING_CHUNK


def test_닿는_조각이_후보에_들지_못했으면_not_in_candidates다() -> None:
    hits = [_hit("a.docx", 0, vector=1, keyword=1, fused=1)]

    cause = classify_miss(REACHING, hits, candidates=CANDIDATES, last_stage=Stage.FUSED)

    assert cause is MissCause.NOT_IN_CANDIDATES


def test_후보에는_들었지만_합친_순위가_밀렸으면_빠른_실행에서_lost_in_fusion이다() -> None:
    hits = [_hit("a.docx", 1, vector=None, keyword=4, fused=7)]

    cause = classify_miss(REACHING, hits, candidates=CANDIDATES, last_stage=Stage.FUSED)

    assert cause is MissCause.LOST_IN_FUSION


def test_합친_순위가_후보_수_안이어도_빠른_실행이면_lost_in_fusion이다() -> None:
    hits = [_hit("a.docx", 1, vector=3, keyword=None, fused=3)]

    cause = classify_miss(REACHING, hits, candidates=CANDIDATES, last_stage=Stage.FUSED)

    assert cause is MissCause.LOST_IN_FUSION


def test_전체_실행에서_합친_순위가_후보_수_밖이면_lost_in_fusion이다() -> None:
    """후보 수 밖의 조각은 리랭커에 들어가지 못한다."""
    hits = [_hit("a.docx", 1, vector=None, keyword=4, fused=CANDIDATES + 1)]

    cause = classify_miss(REACHING, hits, candidates=CANDIDATES, last_stage=Stage.RERANK)

    assert cause is MissCause.LOST_IN_FUSION


def test_전체_실행에서_리랭커에_들어갔는데_못_닿았으면_lost_in_rerank다() -> None:
    hits = [_hit("a.docx", 1, vector=1, keyword=1, fused=CANDIDATES)]

    cause = classify_miss(REACHING, hits, candidates=CANDIDATES, last_stage=Stage.RERANK)

    assert cause is MissCause.LOST_IN_RERANK


def test_닿는_조각이_여럿이면_가장_멀리_간_조각을_기준으로_삼는다() -> None:
    """닿는 조각 둘 가운데 하나는 후보 밖이고 하나는 리랭커까지 들어갔다. 리랭크에서 밀렸다."""
    reaching = frozenset({("a.docx", 1), ("a.docx", 2)})
    hits = [
        _hit("a.docx", 1, vector=None, keyword=4, fused=CANDIDATES + 3),
        _hit("a.docx", 2, vector=2, keyword=None, fused=2),
    ]

    cause = classify_miss(reaching, hits, candidates=CANDIDATES, last_stage=Stage.RERANK)

    assert cause is MissCause.LOST_IN_RERANK


def test_다른_문서의_같은_순번_조각은_닿는_조각으로_세지_않는다() -> None:
    hits = [_hit("b.docx", 1, vector=1, keyword=1, fused=1)]

    cause = classify_miss(REACHING, hits, candidates=CANDIDATES, last_stage=Stage.FUSED)

    assert cause is MissCause.NOT_IN_CANDIDATES


def _tokenize(text: str) -> list[str]:
    return [word for word in text.replace(".", " ").split() if len(word) > 1]


def test_낱말_겹침은_질의의_키워드_토큰_가운데_글귀의_토큰에_든_것의_비율이다() -> None:
    item = EvidenceItem(
        id="q1",
        evidence=(PassageEvidence(document="a.docx", passage="연차휴가 입사 발생"),),
        tags=(),
    )

    overlap = word_overlap(item, "연차휴가 언제 발생 시기", _tokenize)

    assert overlap == 0.5


def test_질의의_토큰이_모두_글귀에_없으면_겹침은_0이다() -> None:
    item = EvidenceItem(
        id="q1", evidence=(PassageEvidence(document="a.docx", passage="연차휴가 입사"),), tags=()
    )

    assert word_overlap(item, "출장비 정산", _tokenize) == 0.0


def test_질의에서_키워드_토큰이_나오지_않으면_겹침은_없다() -> None:
    assert word_overlap(ITEM, "? !", _tokenize) is None


def test_쪽으로만_적은_기대_근거의_겹침은_없다() -> None:
    item = EvidenceItem(id="q2", evidence=(PageEvidence(document="a.pdf", page=2),), tags=())

    assert word_overlap(item, "연차휴가 발생", _tokenize) is None


def test_글귀가_여럿이면_글귀들의_토큰을_합쳐_견준다() -> None:
    item = EvidenceItem(
        id="q1",
        evidence=(
            PassageEvidence(document="a.docx", passage="연차휴가 입사"),
            PassageEvidence(document="b.docx", passage="출장비 정산"),
        ),
        tags=(),
    )

    assert word_overlap(item, "연차휴가 정산 규정 없음", _tokenize) == 0.5


def test_같은_토큰이_질의에_되풀이되어도_한_번으로_센다() -> None:
    item = EvidenceItem(
        id="q1", evidence=(PassageEvidence(document="a.docx", passage="연차휴가 입사"),), tags=()
    )

    assert word_overlap(item, "연차휴가 연차휴가 출장비", _tokenize) == 0.5
