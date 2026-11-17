"""후보 수 50의 실험 보고서가 커밋된 기준 보고서와 같은 칸을 내는지 본다(티켓 search-eval 17).

실험 환경(사본의 묶음, GPU 리랭크 기록)이 저장소의 기준을 그대로 다시 만드는지 점검하는 일이다.
빠른 실행 보고서(`report-fused-50.json`)는 `baseline-fast.json`의 `rows`, `by_tag`, `filtered`와,
전체 실행 보고서(`report-rerank-50.json`)는 `baseline-full.json`의 `rows`, `by_tag`, `filtered`,
`misses`, `miss_counts`, `score_distribution`과 비교한다. 칸마다 같으면 "같다", 아니면 "다르다"를
찍고, 하나라도 다르면 종료 코드 1로 끝난다. `meta`는 실행 시각 같은 값이라 비교하지 않는다.

    uv run python -X utf8 -I compare_with_baseline.py <저장소 루트>

표준 라이브러리만 쓴다.
"""

import json
import sys
from pathlib import Path

FAST_FIELDS = ("rows", "by_tag", "filtered")
FULL_FIELDS = ("rows", "by_tag", "filtered", "misses", "miss_counts", "score_distribution")


def load(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit(f"{path}: 최상위가 객체가 아니다")
    return loaded


def compare(label: str, experiment: Path, baseline: Path, fields: tuple[str, ...]) -> bool:
    left = load(experiment)
    right = load(baseline)
    same = True
    for field in fields:
        if field not in left or field not in right:
            print(f"{label} {field}: 칸이 없다(실험 {field in left}, 기준 {field in right})")
            same = False
            continue
        equal = left[field] == right[field]
        print(f"{label} {field}: {'같다' if equal else '다르다'}")
        same = same and equal
    return same


def main(argv: list[str]) -> int:
    root = Path(argv[0])
    here = Path(__file__).resolve().parent
    data = root / "evals" / "public-docs"
    fast = compare("fast", here / "report-fused-50.json", data / "baseline-fast.json", FAST_FIELDS)
    full = compare("full", here / "report-rerank-50.json", data / "baseline-full.json", FULL_FIELDS)
    return 0 if fast and full else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
