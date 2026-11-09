"""pgvector v0.8.7 README 원문에서 명세가 기대는 색인·질의 문장을 뽑는다(ADR 0006, 명세).

보는 것: 차원이 없는 `vector` 열에 캐스트 표현식으로 HNSW 색인을 거는
문장(`(embedding::vector(3))`), 부분 색인(`WHERE`)과 필터 문단, 반복 스캔
설정(`hnsw.iterative_scan`, `hnsw.max_scan_tuples`, `hnsw.scan_mem_multiplier`), `hnsw.ef_search`,
연산자 클래스(`vector_cosine_ops`), 거리 연산자(`<=>`). 지식베이스마다 임베딩 차원이 다를 수 있어
조각 표의 벡터 열을 어떻게 선언하고 색인하는지를 명세가 정하는 데 썼다.

실행(저장소 루트에서. GitHub raw 하나만 받는다. 표준 라이브러리만):
    uv run python -I -X utf8 .scratch/core/probes/facts/pgvector_readme_facts.py <저장소 밖 폴더>
출력은 `pgvector_readme_facts_out.txt` 로 남겼다(2026-11-10). 패턴 적중 줄 뒤에 CONTEXT 의 줄 범위
(차원이 다른 벡터 절과 `ef_search` 문단)를 통째로 찍어, 적중 줄 하나만으로는 대 볼 수 없던 문맥을
남긴다.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

TAG = "v0.8.7"
URL = f"https://raw.githubusercontent.com/pgvector/pgvector/{TAG}/README.md"
PATTERNS = [
    r"::vector\(",
    r"iterative_scan",
    r"max_scan_tuples",
    r"scan_mem_multiplier",
    r"ef_search",
    r"vector_cosine_ops",
    r"CREATE INDEX .* WHERE",
    r"partial index",
    r"does not have dimensions|without dimensions|untyped",
    r"Filtering",
]
# (시작 줄, 끝 줄). 1부터 세는 README 줄 번호다. 차원이 다른 벡터를 한 열에 두는 절과 결과 수가
# ef_search 로 잘리는 문단이다.
CONTEXT = [(836, 850), (930, 937)]


def fetch(dest: Path) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"pgvector-README-{TAG}.md"
    if not target.exists():
        with urllib.request.urlopen(URL, timeout=60) as resp:
            target.write_bytes(resp.read())
    return target.read_text(encoding="utf-8")


def main() -> None:
    text = fetch(Path(sys.argv[1]))
    lines = text.splitlines()
    print("source", URL, "lines", len(lines))
    for pat in PATTERNS:
        rx = re.compile(pat, re.IGNORECASE)
        hits = [(i + 1, line) for i, line in enumerate(lines) if rx.search(line)]
        print(f"--- /{pat}/ hits={len(hits)}")
        for no, line in hits[:12]:
            print(f"  {no}: {line.strip()[:160]}")
    for start, end in CONTEXT:
        print(f"--- context {start}-{end}")
        for no in range(start, end + 1):
            print(f"  {no}: {lines[no - 1].rstrip()[:200]}")


if __name__ == "__main__":
    main()
