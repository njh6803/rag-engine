"""리랭커 켬·끔 실험의 보고서들을 읽어 질의 목록마다 합친 뒤 줄과 리랭크 뒤 줄의 차를 표로 낸다
(티켓 search-eval 17).

    uv run python -X utf8 -I summarize.py <이름>=<fused 보고서> <이름>=<rerank 보고서> ...

인자의 이름은 `20`, `50`, `100`처럼 리랭크를 넣은 후보 수다. 같은 이름의 fused 보고서와 rerank
보고서를 묶어 표를 만든다. 보고서에 없는 것은 읽지 않는다. 새로 재지 않고 보고서의 숫자를 옮길
뿐이다.
"""

import json
import sys
from pathlib import Path

METRICS = ("hit_at_1", "hit_at_3", "hit_at_5", "hit_at_10", "mrr", "recall", "ndcg_at_10")
HEADS = ("적중@1", "적중@3", "적중@5", "적중@10", "MRR", "재현율", "nDCG@10")


def _load(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _row(report: dict[str, object], query_list: str, stage: str) -> dict[str, float]:
    rows = report["rows"]
    assert isinstance(rows, list)
    for row in rows:
        if row["query_list"] == query_list and row["stage"] == stage:
            return row
    raise SystemExit(f"{query_list} {stage} 줄이 없다")


def _tag_rows(report: dict[str, object], stage: str) -> dict[tuple[str, str], dict[str, float]]:
    by_tag = report["by_tag"]
    assert isinstance(by_tag, list)
    return {(r["query_list"], r["tag"]): r for r in by_tag if r["stage"] == stage}


def main(argv: list[str]) -> int:
    pairs: dict[str, list[str]] = {}
    for arg in argv:
        name, _, path = arg.partition("=")
        pairs.setdefault(name, []).append(path)
    for name, paths in pairs.items():
        reports = [_load(p) for p in paths]
        fused_report = next(r for r in reports if "rerank" not in r["stages"])
        full_report = next(r for r in reports if "rerank" in r["stages"])
        print(f"\n## 후보 수 {name}\n")
        print("| 질의 목록 | 줄 | " + " | ".join(HEADS) + " |")
        print("|---|---|" + "---|" * len(HEADS))
        for query_list in ("human", "keyword"):
            fused = _row(fused_report, query_list, "fused")
            rerank = _row(full_report, query_list, "rerank")
            print(
                f"| {query_list} | 합친 뒤(리랭커 끔) | "
                + " | ".join(f"{fused[m]:.3f}" for m in METRICS)
                + " |"
            )
            print(
                f"| {query_list} | 리랭크 뒤(리랭커 켬) | "
                + " | ".join(f"{rerank[m]:.3f}" for m in METRICS)
                + " |"
            )
            print(
                f"| {query_list} | 차 | "
                + " | ".join(f"{rerank[m] - fused[m]:+.3f}" for m in METRICS)
                + " |"
            )
        fused_tags = _tag_rows(fused_report, "fused")
        rerank_tags = _tag_rows(full_report, "rerank")
        print("\n| 질의 목록 | 유형 | 질의 수 | 적중@1 끔→켬 | 적중@5 끔→켬 | MRR 끔→켬 |", end="")
        print(" nDCG@10 끔→켬 |")
        print("|---|---|---|---|---|---|---|")
        for key in sorted(fused_tags):
            f, r = fused_tags[key], rerank_tags[key]
            cells = " | ".join(
                f"{f[m]:.3f}→{r[m]:.3f}" for m in ("hit_at_1", "hit_at_5", "mrr", "ndcg_at_10")
            )
            print(f"| {key[0]} | {key[1]} | {f['queries']} | {cells} |")
        print(f"\n놓친 근거(리랭크 뒤): {full_report['miss_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
