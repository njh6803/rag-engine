"""같은 커밋의 빠른 게이트를 CI에서 여러 번 돌려 얻은 보고서(report.json)가 어느 칸에서 다른지 센다.

티켓 search-eval 11의 흔들림 측정이다. 보고서를 모든 칸(숫자와 문자열)으로 펼쳐 같은 경로의 값을
견주고, 값이 다른 칸만 찍는다. 질문 하나의 몫(상위 5 적중률 0.67%p) 안에서 흔들리는지는 다른 칸의
값을 눈으로 읽어 가른다. 이 스크립트는 다른 칸을 찾을 뿐 그 크기를 판정하지 않는다.

사용법(이 폴더에서):
    uv run python -X utf8 -I report_diff.py attempt-1.json attempt-2.json attempt-3.json

표준 라이브러리만 쓴다. 입력은 `gh run download <실행 번호> -n eval-fast-report-<시도 번호>`로 받은
산출물이고, 이 폴더의 attempt-1~3.json이 티켓에서 쓴 것이다(산출물은 30일 뒤 지워진다).
"""

import json
import sys
from pathlib import Path


def flatten(value: object, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            out.update(flatten(child, f"{prefix}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            out.update(flatten(child, f"{prefix}[{index}]"))
    else:
        out[prefix] = value
    return out


def main() -> int:
    paths = [Path(arg) for arg in sys.argv[1:]]
    flats = [flatten(json.loads(p.read_text(encoding="utf-8"))) for p in paths]
    keys: list[str] = sorted(set().union(*[set(f) for f in flats]))
    differing = 0
    for key in keys:
        values = [f.get(key, "<없음>") for f in flats]
        if len({json.dumps(v, ensure_ascii=False) for v in values}) > 1:
            differing += 1
            print(key, values)
    print(f"칸 {len(keys)}개, 다른 칸 {differing}개")
    return 0


raise SystemExit(main())
