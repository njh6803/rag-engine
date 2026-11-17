"""설정 실험(search-eval 16)의 보고서를 한 표로 모은다.

저장소 루트에서
`uv run python .scratch/search-eval/probes/experiments/chunking-candidates/summarize.py`로 돌린다.
이 폴더의 `reports/<구성 이름>/report.json`과 `timings.tsv`를 읽어 Markdown 표를 표준 출력에 찍는다
(표준 라이브러리만 쓴다). 판단용 숫자(키워드만 줄, 필터 질의의 적중률과 HNSW 계획의 벡터 후보
부족 비율)도 같은 표에 든다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

HERE = Path(__file__).parent
ORDER = ["c256-32", "c512-64", "c512-128", "c1024-128", "c512-64-k20", "c512-64-k100"]
LISTS = ("human", "keyword")


class Metrics(TypedDict, total=False):
    query_list: str
    stage: str
    queries: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    hit_at_10: float
    mrr: float
    recall: float
    ndcg_at_10: float
    vector_short: int
    vector_short_rate: float


class Causes(TypedDict):
    no_matching_chunk: int
    not_in_candidates: int
    lost_in_fusion: int
    lost_in_rerank: int


class MissCounts(TypedDict):
    missed: int
    causes: Causes
    zero_overlap: int


class IndexInfo(TypedDict):
    chunks: int


class Config(TypedDict):
    search_candidates: int


class Report(TypedDict):
    config: Config
    index: IndexInfo
    rows: list[Metrics]
    filtered: list[Metrics]
    miss_counts: MissCounts


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}"


def num(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def find(rows: list[Metrics], query_list: str, stage: str) -> Metrics:
    for candidate in rows:
        if candidate.get("query_list") == query_list and candidate.get("stage") == stage:
            return candidate
    return {}


def table(title: str, headers: list[str], body: list[list[str]]) -> None:
    print(f"\n## {title}\n")
    print("| " + " | ".join(headers) + " |")
    print("|" + "---|" * len(headers))
    for cells in body:
        print("| " + " | ".join(cells) + " |")


def read_timings() -> dict[tuple[str, str], int]:
    path = HERE / "timings.tsv"
    result: dict[tuple[str, str], int] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        cells = line.split("\t")
        if cells[5] == "0":
            result[(cells[0], cells[1])] = int(cells[4])
    return result


def main() -> int:
    reports: dict[str, Report] = {}
    for name in ORDER:
        path = HERE / "reports" / name / "report.json"
        if path.exists():
            reports[name] = json.loads(path.read_text(encoding="utf-8"))
    if not reports:
        print("보고서가 없다", file=sys.stderr)
        return 1

    fused: list[list[str]] = []
    stages: list[list[str]] = []
    keyword_only: list[list[str]] = []
    filtered: list[list[str]] = []
    misses: list[list[str]] = []
    times: list[list[str]] = []
    timings = read_timings()
    for name, report in reports.items():
        rows = report["rows"]
        human = find(rows, "human", "fused")
        keyword = find(rows, "keyword", "fused")
        fused.append(
            [
                name,
                str(report["index"]["chunks"]),
                str(report["config"]["search_candidates"]),
                pct(human.get("hit_at_5")),
                num(human.get("mrr")),
                pct(keyword.get("hit_at_5")),
                num(keyword.get("mrr")),
                pct(human.get("hit_at_10")),
                num(human.get("ndcg_at_10")),
                num(human.get("recall")),
            ]
        )
        stages.append(
            [name]
            + [
                pct(find(rows, query_list, stage).get("hit_at_5"))
                for query_list in LISTS
                for stage in ("vector", "keyword", "fused")
            ]
        )
        keyword_cells: list[str] = [name]
        filtered_cells: list[str] = [name]
        for query_list in LISTS:
            only = find(rows, query_list, "keyword")
            keyword_cells += [
                pct(only.get("hit_at_1")),
                pct(only.get("hit_at_5")),
                pct(only.get("hit_at_10")),
                num(only.get("mrr")),
            ]
            narrow = find(report["filtered"], query_list, "fused")
            filtered_cells += [
                str(narrow.get("queries", "-")),
                pct(narrow.get("hit_at_5")),
                str(narrow.get("vector_short", "-")),
                pct(narrow.get("vector_short_rate")),
            ]
        keyword_only.append(keyword_cells)
        filtered.append(filtered_cells)
        counts = report["miss_counts"]
        causes = counts["causes"]
        misses.append(
            [
                name,
                str(counts["missed"]),
                str(causes["no_matching_chunk"]),
                str(causes["not_in_candidates"]),
                str(causes["lost_in_fusion"]),
                str(counts["zero_overlap"]),
            ]
        )
        times.append(
            [
                name,
                str(timings.get((name, "index"), "-")),
                str(timings.get((name, "run"), "-")),
            ]
        )

    table(
        "합친 뒤(fused) 줄: 상위 5 적중률(%)과 MRR",
        ["구성", "조각 수", "후보 수", "사람 @5", "사람 MRR", "키워드형 @5", "키워드형 MRR"]
        + ["사람 @10", "사람 nDCG@10", "사람 재현율"],
        fused,
    )
    table(
        "단계별 상위 5 적중률(%): 벡터만 / 키워드만 / 합친 뒤",
        ["구성"] + [f"{q} {s}" for q in LISTS for s in ("벡터", "키워드만", "합친 뒤")],
        stages,
    )
    table(
        "키워드만 줄의 지표(스토리 10: ts_rank에 IDF가 없고 토큰을 OR로 잇는 동작)",
        ["구성"] + [f"{q} {m}" for q in LISTS for m in ("@1", "@5", "@10", "MRR")],
        keyword_only,
    )
    table(
        "필터가 붙은 질의(스토리 9): 합친 뒤 @5(%)와 HNSW 계획의 벡터 후보 부족",
        ["구성"] + [f"{q} {m}" for q in LISTS for m in ("질의 수", "@5", "부족 수", "부족 비율")],
        filtered,
    )
    table(
        "놓친 질의(합친 뒤 상위 10에 닿는 조각이 없는 질의)의 탈락 지점",
        ["구성", "놓친 수", "no_matching_chunk", "not_in_candidates", "lost_in_fusion"]
        + ["낱말 겹침 0"],
        misses,
    )
    table("걸린 시간(초)", ["구성", "index", "run"], times)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
