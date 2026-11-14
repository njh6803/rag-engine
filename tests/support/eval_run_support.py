"""`tools/search_eval.py`의 `run`과 `inspect` 표면 시험이 함께 쓰는 묶음, 보고서 모델, 도우미(티켓
search-eval 04, 05, 06).

보고서의 모델은 칸을 모두 이름으로 받는다(`extra="forbid"`). 모르는 칸이 있으면 검증이 실패해 칸의
목록을 고정한다. 묶음은 문서가 둘이고 조각이 하나씩이다(짧은 글).
"""

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from tests.support.docx_files import docx_bytes
from tests.support.eval_bundle import (
    HEADER,
    HEADER_QUERY_LISTS,
    INDEX_CONFIG,
    PASSAGE,
    PASSAGE_B,
    passage_evidence,
    write_indexable_bundle,
    write_json,
    write_jsonl,
)

from rag_engine.domain.entities import JsonValue
from tools import search_eval

DOCUMENT_A = docx_bytes("휴가", PASSAGE + ".")
DOCUMENT_B = docx_bytes("출장", PASSAGE_B + ".")
DOCUMENTS = {"a.docx": DOCUMENT_A, "sub/b.docx": DOCUMENT_B}
# 문서의 제목과 글을 그대로 옮긴 질의: 낱말 주머니가 그 문서의 조각과 같아 그 조각이 벡터 1위다.
QUERY_A = f"휴가 {PASSAGE}."
QUERY_B = f"출장 {PASSAGE_B}."
EVIDENCE = [
    passage_evidence("q1", "a.docx", PASSAGE),
    passage_evidence("q2", "sub/b.docx", PASSAGE_B),
]
HUMAN = [
    {"evidence_id": "q1", "query": QUERY_A},
    {"evidence_id": "q2", "query": QUERY_B},
]
EMBEDDINGS = "/v1/embeddings"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportEvalSet(Strict):
    name: str
    format_version: str
    content_hash: str
    documents: int
    questions: int
    queries: int


class ReportIndex(Strict):
    schema_version: int
    embedding_model: str
    embedding_dimensions: int
    chunking_hash: str
    tokenizer_version: str
    chunks: int


class ReportMetrics(Strict):
    queries: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    hit_at_10: float
    mrr: float
    recall: float
    ndcg_at_10: float
    ndcg_truncated: int


class ReportRow(ReportMetrics):
    query_list: str
    stage: str


class TagRow(ReportMetrics):
    query_list: str
    tag: str
    stage: str


class FilteredRow(ReportMetrics):
    query_list: str
    stage: str
    vector_short: int
    vector_short_rate: float


class MissRow(Strict):
    query_list: str
    evidence_id: str
    cause: str
    word_overlap: float | None


class MissCounts(Strict):
    missed: int
    causes: dict[str, int]
    zero_overlap: int


class ReportMeta(Strict):
    run_at: str
    commit: str | None


class ScoreBin(Strict):
    lower: float
    upper: float
    reached: int
    not_reached: int


class Threshold(Strict):
    min_score: float
    hit_at_5: float
    hit_at_10: float
    empty_rate: float
    mean_kept: float


class Distribution(Strict):
    queries: int
    bins: list[ScoreBin]
    thresholds: list[Threshold]

    def counts(self) -> dict[int, tuple[int, int]]:
        """닿은 조각과 닿지 않은 조각이 하나라도 있는 구간의 번호(0부터)와 그 수."""
        return {
            number: (bin_.reached, bin_.not_reached)
            for number, bin_ in enumerate(self.bins)
            if bin_.reached or bin_.not_reached
        }

    def row(self, min_score: float) -> Threshold:
        (found,) = [row for row in self.thresholds if row.min_score == min_score]
        return found


class Report(Strict):
    format_version: str
    eval_set: ReportEvalSet
    config: dict[str, JsonValue]
    index: ReportIndex
    stages: list[str]
    rows: list[ReportRow]
    by_tag: list[TagRow]
    filtered: list[FilteredRow]
    misses: list[MissRow]
    miss_counts: MissCounts
    human_causes: dict[str, int]
    meta: ReportMeta
    score_distribution: Distribution | None = None

    def row(self, query_list: str, stage: str) -> ReportRow:
        (found,) = [r for r in self.rows if r.query_list == query_list and r.stage == stage]
        return found

    def miss(self, query_list: str, evidence_id: str) -> MissRow:
        (found,) = [
            m for m in self.misses if m.query_list == query_list and m.evidence_id == evidence_id
        ]
        return found


def make_bundle(
    tmp_path: Path,
    name: str = "bundle",
    *,
    documents: dict[str, bytes] | None = None,
    evidence: Sequence[JsonValue] = EVIDENCE,
    human: Sequence[JsonValue] = HUMAN,
    keyword: Sequence[JsonValue] | None = None,
    config: dict[str, JsonValue] | None = None,
) -> Path:
    root = write_indexable_bundle(
        tmp_path / name,
        DOCUMENTS if documents is None else documents,
        evidence,
        config=INDEX_CONFIG if config is None else config,
    )
    write_jsonl(root / "queries-human.jsonl", human)
    if keyword is not None:
        write_json(root / "eval-set.json", {**HEADER, "query_lists": HEADER_QUERY_LISTS})
        write_jsonl(root / "queries-keyword.jsonl", keyword)
    return root


def run_index(bundle: Path, *extra: str) -> int:
    return search_eval.main(["index", str(bundle), *extra])


def run_fast(bundle: Path, out: Path, *extra: str) -> int:
    return search_eval.main(["run", str(bundle), "--through", "fused", "--out", str(out), *extra])


def run_full(bundle: Path, out: Path, *extra: str) -> int:
    return search_eval.main(["run", str(bundle), "--through", "rerank", "--out", str(out), *extra])


def read_report(out: Path) -> Report:
    return Report.model_validate_json((out / "report.json").read_text(encoding="utf-8"))


def read_raw_report(out: Path) -> dict[str, JsonValue]:
    raw: JsonValue = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def indexed_fast_report(bundle: Path, out: Path) -> Report:
    assert run_index(bundle) == 0
    assert run_fast(bundle, out) == 0
    return read_report(out)


def indexed_full_report(bundle: Path, out: Path) -> Report:
    assert run_index(bundle) == 0
    assert run_full(bundle, out) == 0
    return read_report(out)


def prefer_b(query: str, text: str) -> float:
    """리랭커 스텁의 점수. 질의와 상관없이 `b` 문서의 조각을 높이 친다."""
    del query
    return 0.9 if PASSAGE_B in text else 0.2
