"""유형 표지와 필터 질의의 지표, 놓친 질의의 수, 사람 판정의 수(티켓 search-eval 06, 명세 "지표"와
"놓친 까닭").

질의 하나의 결과(`QueryOutcome`)를 손으로 지어 넣고 값을 견준다. 지표는 마지막 단계에 대해서만
낸다. 질의 수가 0인 줄은 만들지 않는다.
"""

from rag_engine.app.eval_breakdown import (
    FilteredRow,
    MissRow,
    filtered_rows,
    human_cause_counts,
    miss_counts,
    miss_rows,
    tag_rows,
)
from rag_engine.app.eval_misses import MissCause
from rag_engine.app.eval_run import FilterScanProbe, QueryMiss, QueryOutcome
from rag_engine.app.eval_stages import FAST_STAGES, Stage
from rag_engine.domain.eval_set import (
    ChunkingConfig,
    EvalConfig,
    EvalSet,
    EvidenceItem,
    MissReview,
    PassageEvidence,
    QueryList,
    QueryStyle,
)

CONFIG = EvalConfig(
    embedding_model="m",
    embedding_dimensions=16,
    reranker_model="r",
    chunking=ChunkingConfig(strategy="structure_first", max_tokens=512, overlap_tokens=64),
    search_candidates=10,
    tei_version="1.9",
    judge_model="j",
    judge_prompt_version="1",
)


def _item(identifier: str, *tags: str) -> EvidenceItem:
    return EvidenceItem(
        id=identifier, evidence=(PassageEvidence(document="a.docx", passage="글귀"),), tags=tags
    )


def _eval_set(items: tuple[EvidenceItem, ...], reviews: tuple[MissReview, ...] = ()) -> EvalSet:
    return EvalSet(
        format_version="1.0.0",
        name="세트",
        config=CONFIG,
        documents=(),
        evidence=items,
        query_lists=(
            QueryList(name="human", style=QueryStyle.QUESTION, queries=()),
            QueryList(name="keyword", style=QueryStyle.KEYWORD, queries=()),
        ),
        miss_reviews=reviews,
    )


def _outcome(
    identifier: str,
    *,
    query_list: str = "human",
    first_rank: int | None,
    miss: QueryMiss | None = None,
    probe: FilterScanProbe | None = None,
) -> QueryOutcome:
    """마지막 단계(합친 뒤)의 순위 `first_rank`에서 기대 근거 하나에 닿은 질의."""
    ranks = () if first_rank is None else (*[frozenset[int]()] * (first_rank - 1), frozenset({0}))
    return QueryOutcome(
        query_list=query_list,
        evidence_id=identifier,
        expected=1,
        reach={stage: ranks for stage in FAST_STAGES},
        miss=miss,
        filter_probe=probe,
    )


def test_유형_표지마다_질의_목록별로_마지막_단계의_지표를_낸다() -> None:
    """table 질문 둘(하나는 1위에 닿고 하나는 놓침)과 figure 질문 하나(놓침)."""
    eval_set = _eval_set((_item("q1", "table"), _item("q2", "table", "figure"), _item("q3")))
    outcomes = [
        _outcome("q1", first_rank=1),
        _outcome("q2", first_rank=None),
        _outcome("q3", first_rank=1),
    ]

    rows = tag_rows(eval_set, outcomes, Stage.FUSED)

    assert [(row.query_list, row.tag, row.stage, row.metrics.queries) for row in rows] == [
        ("human", "figure", Stage.FUSED, 1),
        ("human", "table", Stage.FUSED, 2),
    ]
    assert rows[0].metrics.hit_at_1 == 0.0
    assert rows[1].metrics.hit_at_1 == 0.5


def test_유형_표지가_없는_질문과_질의가_없는_표지는_줄을_만들지_않는다() -> None:
    eval_set = _eval_set((_item("q1"), _item("q2", "table")))

    rows = tag_rows(eval_set, [_outcome("q1", first_rank=1)], Stage.FUSED)

    assert rows == []


def test_유형_표지의_줄은_질의_목록마다_따로_센다() -> None:
    eval_set = _eval_set((_item("q1", "table"),))
    outcomes = [
        _outcome("q1", query_list="human", first_rank=1),
        _outcome("q1", query_list="keyword", first_rank=None),
    ]

    rows = tag_rows(eval_set, outcomes, Stage.FUSED)

    assert [(row.query_list, row.metrics.hit_at_1) for row in rows] == [
        ("human", 1.0),
        ("keyword", 0.0),
    ]


def test_필터_질의만의_지표와_벡터_후보가_모자란_질의의_수를_낸다() -> None:
    """필터 질의 셋 가운데 하나(q2)만 HNSW가 정확 스캔보다 벡터 후보를 적게 냈다. 필터 없는 질의
    q4는 세지 않는다."""
    outcomes = [
        _outcome("q1", first_rank=1, probe=FilterScanProbe(expected_vectors=5, index_vectors=5)),
        _outcome("q2", first_rank=None, probe=FilterScanProbe(expected_vectors=5, index_vectors=3)),
        _outcome("q3", first_rank=2, probe=FilterScanProbe(expected_vectors=0, index_vectors=0)),
        _outcome("q4", first_rank=1),
    ]

    rows = filtered_rows(outcomes, Stage.FUSED)

    assert rows == [
        FilteredRow(query_list="human", stage=Stage.FUSED, metrics=rows[0].metrics, vector_short=1)
    ]
    assert rows[0].metrics.queries == 3
    assert rows[0].metrics.hit_at_1 == 1 / 3
    assert rows[0].vector_short_rate == 1 / 3


def test_필터_질의가_없는_질의_목록은_필터_줄이_없다() -> None:
    assert filtered_rows([_outcome("q1", first_rank=1)], Stage.FUSED) == []


def test_정확_스캔도_후보를_채우지_못한_질의는_모자란_것으로_세지_않는다() -> None:
    """필터를 지나는 조각이 둘뿐이라 정확 스캔의 벡터 후보가 둘이고, 색인 계획도 둘을 냈다."""
    probe = FilterScanProbe(expected_vectors=2, index_vectors=2)

    assert probe.short is False


def test_놓친_질의는_질의_목록_이름과_기대_근거_id와_탈락_지점과_낱말_겹침으로_싣는다() -> None:
    outcomes = [
        _outcome("q1", first_rank=1),
        _outcome("q2", first_rank=None, miss=QueryMiss(MissCause.LOST_IN_FUSION, 0.5)),
        _outcome(
            "q3",
            query_list="keyword",
            first_rank=None,
            miss=QueryMiss(MissCause.NO_MATCHING_CHUNK, None),
        ),
    ]

    assert miss_rows(outcomes) == [
        MissRow("human", "q2", MissCause.LOST_IN_FUSION, 0.5),
        MissRow("keyword", "q3", MissCause.NO_MATCHING_CHUNK, None),
    ]


def test_놓친_질의의_수는_탈락_지점마다_세고_일어나지_않은_지점도_0으로_싣는다() -> None:
    outcomes = [
        _outcome("q1", first_rank=None, miss=QueryMiss(MissCause.LOST_IN_FUSION, 0.5)),
        _outcome("q2", first_rank=None, miss=QueryMiss(MissCause.LOST_IN_FUSION, 0.25)),
        _outcome("q3", first_rank=None, miss=QueryMiss(MissCause.NOT_IN_CANDIDATES, 1.0)),
        _outcome("q4", first_rank=1),
    ]

    counts = miss_counts(outcomes)

    assert counts.missed == 3
    assert counts.causes == {
        MissCause.NO_MATCHING_CHUNK: 0,
        MissCause.NOT_IN_CANDIDATES: 1,
        MissCause.LOST_IN_FUSION: 2,
        MissCause.LOST_IN_RERANK: 0,
    }


def test_낱말_겹침이_값이_없는_놓친_질의는_겹침이_0인_수에_넣지_않는다() -> None:
    """겹침 0.0은 센다. `None`(키워드 토큰이 없거나 쪽으로 적은 기대 근거)은 세지 않는다."""
    outcomes = [
        _outcome("q1", first_rank=None, miss=QueryMiss(MissCause.NOT_IN_CANDIDATES, 0.0)),
        _outcome("q2", first_rank=None, miss=QueryMiss(MissCause.NOT_IN_CANDIDATES, None)),
        _outcome("q3", first_rank=None, miss=QueryMiss(MissCause.LOST_IN_FUSION, 0.5)),
    ]

    counts = miss_counts(outcomes)

    assert counts.missed == 3
    assert counts.zero_overlap == 1


def test_사람_판정은_확인된_줄만_까닭마다_센다() -> None:
    reviews = (
        MissReview("human", "q1", "vocabulary", confirmed=True),
        MissReview("human", "q2", "vocabulary", confirmed=True),
        MissReview("keyword", "q2", "no_context", confirmed=True),
        MissReview("human", "q3", "table_or_figure", confirmed=False),
    )

    counts = human_cause_counts(_eval_set((), reviews))

    assert counts == {
        "no_context": 1,
        "table_or_figure": 0,
        "vocabulary": 2,
        "multi_document": 0,
        "other": 0,
    }


def test_사람_판정이_없으면_다섯_까닭이_모두_0이다() -> None:
    assert set(human_cause_counts(_eval_set(())).values()) == {0}
    assert len(human_cause_counts(_eval_set(()))) == 5
