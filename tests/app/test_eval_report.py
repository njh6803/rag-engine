"""평가 보고서의 새 칸(티켓 search-eval 06, 명세 "보고서").

`by_tag`, `filtered`, `misses`, `miss_counts`, `human_causes`는 마지막 단계에 대한 값이고, 칸을
더해도 보고서의 판은 그대로다. 보고서는 질의의 글과 조각의 글을 싣지 않고 식별자만 싣는다.
"""

import json
from datetime import UTC, datetime

from rag_engine.app.eval_misses import MissCause
from rag_engine.app.eval_report import (
    REPORT_FORMAT_VERSION,
    build_report,
    report_json,
    report_markdown,
)
from rag_engine.app.eval_run import (
    EvalRunResult,
    FilterScanProbe,
    IndexSummary,
    QueryMiss,
    QueryOutcome,
)
from rag_engine.app.eval_stages import FAST_STAGES, FULL_STAGES, Stage
from rag_engine.domain.entities import IndexElements, JsonValue
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
RUN_AT = datetime(2026, 11, 14, tzinfo=UTC)
ELEMENTS = IndexElements(
    schema_version=1,
    embedding_model="m",
    embedding_dimensions=16,
    chunking_hash="h",
    tokenizer_version="t",
)


def _eval_set() -> EvalSet:
    return EvalSet(
        format_version="1.0.0",
        name="세트",
        config=CONFIG,
        documents=(),
        evidence=tuple(
            EvidenceItem(
                id=identifier,
                evidence=(PassageEvidence(document="a.docx", passage="글귀"),),
                tags=tags,
            )
            for identifier, tags in (("q1", ("table",)), ("q2", ()), ("q3", ("table",)))
        ),
        query_lists=(QueryList(name="human", style=QueryStyle.QUESTION, queries=()),),
        miss_reviews=(
            MissReview("human", "q2", "vocabulary", confirmed=True),
            MissReview("human", "q3", "other", confirmed=False),
        ),
    )


def _outcome(
    identifier: str,
    *,
    last: Stage,
    hit: bool,
    miss: QueryMiss | None = None,
    probe: FilterScanProbe | None = None,
) -> QueryOutcome:
    """`last` 단계에서만 `hit`이면 1위에 닿고, 앞 단계는 모두 놓친다."""
    stages = FULL_STAGES if last is Stage.RERANK else FAST_STAGES
    return QueryOutcome(
        query_list="human",
        evidence_id=identifier,
        expected=1,
        reach={stage: ((frozenset({0}),) if hit and stage is last else ()) for stage in stages},
        scored=() if last is Stage.RERANK else None,
        miss=miss,
        filter_probe=probe,
    )


def _result(*outcomes: QueryOutcome) -> EvalRunResult:
    return EvalRunResult(index=IndexSummary(elements=ELEMENTS, chunks=7), outcomes=outcomes)


def _fast_report_values() -> dict[str, JsonValue]:
    result = _result(
        _outcome("q1", last=Stage.FUSED, hit=True),
        _outcome(
            "q2",
            last=Stage.FUSED,
            hit=False,
            miss=QueryMiss(MissCause.NOT_IN_CANDIDATES, None),
            probe=FilterScanProbe(expected_vectors=5, index_vectors=3),
        ),
        _outcome(
            "q3",
            last=Stage.FUSED,
            hit=False,
            miss=QueryMiss(MissCause.LOST_IN_FUSION, 0.0),
        ),
    )
    report = build_report(
        _eval_set(),
        result,
        content_hash="해시",
        stages=FAST_STAGES,
        run_at=RUN_AT,
        commit=None,
    )
    return report_json(report)


def test_새_칸을_더해도_보고서의_판은_그대로다() -> None:
    values = _fast_report_values()

    assert values["format_version"] == REPORT_FORMAT_VERSION == "1.0.0"
    for name in ("by_tag", "filtered", "misses", "miss_counts", "human_causes"):
        assert name in values


def test_놓친_질의는_식별자와_탈락_지점과_낱말_겹침으로_싣고_값이_없으면_null이다() -> None:
    values = _fast_report_values()

    assert values["misses"] == [
        {
            "query_list": "human",
            "evidence_id": "q2",
            "cause": "not_in_candidates",
            "word_overlap": None,
        },
        {
            "query_list": "human",
            "evidence_id": "q3",
            "cause": "lost_in_fusion",
            "word_overlap": 0.0,
        },
    ]


def test_놓친_질의의_수는_탈락_지점마다_싣고_겹침이_0인_수에_null은_들지_않는다() -> None:
    values = _fast_report_values()

    assert values["miss_counts"] == {
        "missed": 2,
        "causes": {
            "no_matching_chunk": 0,
            "not_in_candidates": 1,
            "lost_in_fusion": 1,
            "lost_in_rerank": 0,
        },
        "zero_overlap": 1,
    }


def test_유형_표지의_지표는_마지막_단계에_대해_낸다() -> None:
    values = _fast_report_values()

    by_tag = values["by_tag"]
    assert isinstance(by_tag, list)
    (row,) = by_tag
    assert isinstance(row, dict)
    assert (row["query_list"], row["tag"], row["stage"], row["queries"]) == (
        "human",
        "table",
        "fused",
        2,
    )
    assert row["hit_at_1"] == 0.5


def test_필터_질의의_숫자는_유형_표지의_숫자와_따로_나온다() -> None:
    values = _fast_report_values()

    filtered = values["filtered"]
    assert isinstance(filtered, list)
    (row,) = filtered
    assert isinstance(row, dict)
    assert (row["query_list"], row["stage"], row["queries"]) == ("human", "fused", 1)
    assert (row["vector_short"], row["vector_short_rate"]) == (1, 1.0)
    assert row["hit_at_1"] == 0.0


def test_사람_판정은_확인된_줄만_다섯_까닭마다_센다() -> None:
    values = _fast_report_values()

    assert values["human_causes"] == {
        "multi_document": 0,
        "no_context": 0,
        "other": 0,
        "table_or_figure": 0,
        "vocabulary": 1,
    }


def test_전체_실행의_지표는_리랭크_뒤_단계에_대해_낸다() -> None:
    result = _result(
        _outcome("q1", last=Stage.RERANK, hit=True, probe=FilterScanProbe(3, 3)),
        _outcome("q2", last=Stage.RERANK, hit=False, miss=QueryMiss(MissCause.LOST_IN_RERANK, 0.5)),
    )
    report = build_report(
        _eval_set(),
        result,
        content_hash="해시",
        stages=FULL_STAGES,
        run_at=RUN_AT,
        commit=None,
    )

    values = report_json(report)

    by_tag = values["by_tag"]
    filtered = values["filtered"]
    assert isinstance(by_tag, list) and isinstance(filtered, list)
    assert [row["stage"] for row in by_tag if isinstance(row, dict)] == ["rerank"]
    assert [row["stage"] for row in filtered if isinstance(row, dict)] == ["rerank"]


def test_보고서는_json으로_직렬화되고_마크다운은_같은_값을_표로_싣는다() -> None:
    result = _result(
        _outcome("q1", last=Stage.FUSED, hit=True),
        _outcome(
            "q2",
            last=Stage.FUSED,
            hit=False,
            miss=QueryMiss(MissCause.NOT_IN_CANDIDATES, None),
            probe=FilterScanProbe(expected_vectors=5, index_vectors=3),
        ),
    )
    report = build_report(
        _eval_set(),
        result,
        content_hash="해시",
        stages=FAST_STAGES,
        run_at=RUN_AT,
        commit=None,
    )

    json.dumps(report_json(report), ensure_ascii=False)
    markdown = report_markdown(report)

    assert "## 유형 표지별 지표" in markdown
    assert "## 필터가 붙은 질의" in markdown
    assert "## 놓친 질의" in markdown
    assert "not_in_candidates" in markdown
    assert "## 사람 판정" in markdown
    assert "vocabulary" in markdown
