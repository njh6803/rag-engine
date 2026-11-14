"""평가 보고서의 값과 Markdown(티켓 search-eval 04, 명세 "보고서").

`report.json`이 원천이고 `report.md`는 같은 값을 사람이 읽는 표로 옮긴 것이다. 보고서에는 질의의
글과 조각의 글을 싣지 않고 식별자(질의 목록 이름, 기대 근거의 `id`)로만 가리킨다. 이 유스케이스를
관리자 페이지가 설치처의 평가에 다시 쓸 때 질문과 문서 내용이 보고서 파일로 번지지 않게 하기
위해서다(원칙 V).

이 판(`"1.0.0"`)의 칸은 `format_version`, `eval_set`, `config`, `index`, `stages`, `rows`, `meta`와,
전체 실행(`stages`가 리랭크 뒤로 끝난다)에서만 `score_distribution`이다. 빠른 실행의 보고서에는
`score_distribution` 칸이 없다. 유형 표지와 필터의 지표, 놓친 질의, 사람 판정, LLM 숫자, 추론 기록은
그 칸을 받는 티켓이 같은 판에서 더한다(칸을 더하는 것은 판을 올리지 않는다).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from rag_engine.app.eval_metrics import StageMetrics, aggregate, score_query
from rag_engine.app.eval_run import EvalRunResult, IndexSummary, Stage
from rag_engine.app.eval_score_distribution import ScoreDistribution, build_score_distribution
from rag_engine.domain.entities import JsonValue
from rag_engine.domain.eval_set import EvalConfig, EvalSet

REPORT_FORMAT_VERSION: Final = "1.0.0"
_METRIC_DIGITS: Final = 3


@dataclass(frozen=True, slots=True)
class ReportRow:
    """질의 목록과 단계 하나의 줄."""

    query_list: str
    stage: Stage
    metrics: StageMetrics


@dataclass(frozen=True, slots=True)
class EvalReport:
    set_name: str
    set_format_version: str
    content_hash: str
    documents: int
    questions: int
    queries: int
    config: EvalConfig
    index: IndexSummary
    stages: tuple[Stage, ...]
    rows: tuple[ReportRow, ...]
    run_at: datetime
    commit: str | None
    score_distribution: ScoreDistribution | None = None


def config_values(config: EvalConfig, *, with_judge: bool) -> dict[str, JsonValue]:
    """구성의 칸. 묶음의 내용 해시는 판정 칸(`judge_model`, `judge_prompt_version`)을 뺀 값을
    쓴다. 두 칸은 검색의 숫자에 닿지 않는 참고 숫자의 열쇠이기 때문이다."""
    values: dict[str, JsonValue] = {
        "embedding_model": config.embedding_model,
        "embedding_dimensions": config.embedding_dimensions,
        "reranker_model": config.reranker_model,
        "chunking": {
            "strategy": config.chunking.strategy,
            "max_tokens": config.chunking.max_tokens,
            "overlap_tokens": config.chunking.overlap_tokens,
        },
        "search_candidates": config.search_candidates,
        "tei_version": config.tei_version,
    }
    if with_judge:
        values["judge_model"] = config.judge_model
        values["judge_prompt_version"] = config.judge_prompt_version
    return values


def build_report(
    eval_set: EvalSet,
    result: EvalRunResult,
    *,
    content_hash: str,
    stages: Sequence[Stage],
    run_at: datetime,
    commit: str | None,
) -> EvalReport:
    rows: list[ReportRow] = []
    for query_list in eval_set.query_lists:
        for stage in stages:
            scores = [
                score_query(outcome.reach[stage], expected=outcome.expected)
                for outcome in result.outcomes
                if outcome.query_list == query_list.name
            ]
            metrics = aggregate(scores)
            if metrics is not None:
                rows.append(ReportRow(query_list.name, stage, metrics))
    return EvalReport(
        set_name=eval_set.name,
        set_format_version=eval_set.format_version,
        content_hash=content_hash,
        documents=len(eval_set.documents),
        questions=len(eval_set.evidence),
        queries=sum(len(query_list.queries) for query_list in eval_set.query_lists),
        config=eval_set.config,
        index=result.index,
        stages=tuple(stages),
        rows=tuple(rows),
        run_at=run_at,
        commit=commit,
        score_distribution=(
            build_score_distribution(result.outcomes) if Stage.RERANK in stages else None
        ),
    )


def report_json(report: EvalReport) -> dict[str, JsonValue]:
    values = _report_values(report)
    if report.score_distribution is not None:
        values["score_distribution"] = _distribution_json(report.score_distribution)
    return values


def _distribution_json(distribution: ScoreDistribution) -> dict[str, JsonValue]:
    return {
        "queries": distribution.queries,
        "bins": [
            {
                "lower": bin_.lower,
                "upper": bin_.upper,
                "reached": bin_.reached,
                "not_reached": bin_.not_reached,
            }
            for bin_ in distribution.bins
        ],
        "thresholds": [
            {
                "min_score": row.min_score,
                "hit_at_5": row.hit_at_5,
                "hit_at_10": row.hit_at_10,
                "empty_rate": row.empty_rate,
                "mean_kept": row.mean_kept,
            }
            for row in distribution.thresholds
        ],
    }


def _report_values(report: EvalReport) -> dict[str, JsonValue]:
    elements = report.index.elements
    return {
        "format_version": REPORT_FORMAT_VERSION,
        "eval_set": {
            "name": report.set_name,
            "format_version": report.set_format_version,
            "content_hash": report.content_hash,
            "documents": report.documents,
            "questions": report.questions,
            "queries": report.queries,
        },
        "config": config_values(report.config, with_judge=True),
        "index": {
            "schema_version": elements.schema_version,
            "embedding_model": elements.embedding_model,
            "embedding_dimensions": elements.embedding_dimensions,
            "chunking_hash": elements.chunking_hash,
            "tokenizer_version": elements.tokenizer_version,
            "chunks": report.index.chunks,
        },
        "stages": [stage.value for stage in report.stages],
        "rows": [_row_json(row) for row in report.rows],
        "meta": {"run_at": report.run_at.isoformat(), "commit": report.commit},
    }


def _row_json(row: ReportRow) -> dict[str, JsonValue]:
    metrics = row.metrics
    return {
        "query_list": row.query_list,
        "stage": row.stage.value,
        "queries": metrics.queries,
        "hit_at_1": metrics.hit_at_1,
        "hit_at_3": metrics.hit_at_3,
        "hit_at_5": metrics.hit_at_5,
        "hit_at_10": metrics.hit_at_10,
        "mrr": metrics.mrr,
        "recall": metrics.recall,
        "ndcg_at_10": metrics.ndcg_at_10,
        "ndcg_truncated": metrics.ndcg_truncated,
    }


def report_markdown(report: EvalReport) -> str:
    """`report_json`과 같은 값을 표로 옮긴다."""
    lines = [
        f"# 검색 평가 보고서: {report.set_name}",
        "",
        f"- 보고서 판: {REPORT_FORMAT_VERSION}",
        f"- 묶음 판: {report.set_format_version}, 내용 해시: `{report.content_hash}`",
        f"- 문서 {report.documents}개, 질문 {report.questions}개, 질의 {report.queries}개",
        f"- 실행 시각: {report.run_at.isoformat()}, 커밋: {report.commit or '없음'}",
        f"- 잰 단계: {', '.join(stage.value for stage in report.stages)}",
        "",
        "## 구성",
        "",
        *_table(
            ("칸", "값"),
            [
                (name, _cell(value))
                for name, value in config_values(report.config, with_judge=True).items()
            ],
        ),
        "",
        "## 색인",
        "",
        *_table(("칸", "값"), _index_rows(report)),
    ]
    for name in dict.fromkeys(row.query_list for row in report.rows):
        lines += ["", f"## 질의 목록 `{name}`", ""]
        lines += _table(
            (
                "단계",
                "질의",
                "적중률@1",
                "@3",
                "@5",
                "@10",
                "MRR",
                "재현율",
                "nDCG@10",
                "nDCG 잘림",
            ),
            [_metric_cells(row) for row in report.rows if row.query_list == name],
        )
    if report.score_distribution is not None:
        lines += _distribution_markdown(report.score_distribution)
    return "\n".join(lines) + "\n"


def _distribution_markdown(distribution: ScoreDistribution) -> list[str]:
    """점수 분포의 두 표. 구간별 조각 수와 문턱별 지표다."""
    return [
        "",
        f"## 리랭크 점수 분포 (질의 {distribution.queries}개)",
        "",
        "구간별 조각 수: 합친 뒤의 후보 전부를 기대 근거에 닿았는지로 가른다.",
        "",
        *_table(
            ("구간", "닿음", "닿지 않음"),
            [
                (
                    f"{_number(bin_.lower)}~{_number(bin_.upper)}",
                    str(bin_.reached),
                    str(bin_.not_reached),
                )
                for bin_ in distribution.bins
            ],
        ),
        "",
        "문턱별 지표: 문턱 이상의 점수를 가진 조각만 남긴다.",
        "",
        *_table(
            ("문턱", "적중률@5", "적중률@10", "빈 질의의 비율", "남는 조각 수의 평균"),
            [
                (
                    _number(row.min_score),
                    _number(row.hit_at_5),
                    _number(row.hit_at_10),
                    _number(row.empty_rate),
                    _number(row.mean_kept),
                )
                for row in distribution.thresholds
            ],
        ),
    ]


def _index_rows(report: EvalReport) -> list[tuple[str, str]]:
    elements = report.index.elements
    return [
        ("schema_version", str(elements.schema_version)),
        ("embedding_model", elements.embedding_model),
        ("embedding_dimensions", str(elements.embedding_dimensions)),
        ("chunking_hash", elements.chunking_hash),
        ("tokenizer_version", elements.tokenizer_version),
        ("chunks", str(report.index.chunks)),
    ]


def _metric_cells(row: ReportRow) -> tuple[str, ...]:
    metrics = row.metrics
    return (
        row.stage.value,
        str(metrics.queries),
        *(
            _number(value)
            for value in (
                metrics.hit_at_1,
                metrics.hit_at_3,
                metrics.hit_at_5,
                metrics.hit_at_10,
                metrics.mrr,
                metrics.recall,
                metrics.ndcg_at_10,
            )
        ),
        str(metrics.ndcg_truncated),
    )


def _number(value: float) -> str:
    return f"{value:.{_METRIC_DIGITS}f}"


def _cell(value: JsonValue) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={_cell(item)}" for key, item in value.items())
    return str(value)


def _table(header: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
        *("| " + " | ".join(cells) + " |" for cells in rows),
    ]
