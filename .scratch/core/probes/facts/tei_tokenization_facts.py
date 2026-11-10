"""TEI v1.9.4 의 토크나이즈 소스(`core/src/tokenization.rs`)에서 입력 길이 검증의 자리를 뽑는다.

근거로 드는 곳은 명세의 청킹 절이다. PR #3 봇 회차(CodeRabbit)가 "조각 글만 상한 안이어도 임베딩이
거부될 수 있다"고 짚어, 임베딩 요청의 길이 검증이 특수 토큰을 포함하는지와 `/tokenize` 의
`add_special_tokens` 가 그 검증과 어떻게 다른지를 원문으로 본다. 보는 것 셋. `tokenize` 가 빈 입력을
거부하는 줄, `tokenize_input` 이 받는 `add_special_tokens` 인자와 글자 수 상한, `encode_input` 이
`tokenize_input` 에 `true` 를 넘긴 뒤 `seq_len > max_input_length` 로 거부하는 줄이다.

실행(저장소 루트에서. GitHub raw 의 태그 고정 소스 하나만 받는다. 표준 라이브러리만):
    uv run python -I -X utf8 .scratch/core/probes/facts/tei_tokenization_facts.py <폴더>
`<폴더>` 는 저장소 밖(세션 스크래치패드)이다. 받은 파일은 읽기만 한다.
출력은 `tei_tokenization_facts_out.txt` 로 남겼다(2026-11-10). 패턴 적중 줄 뒤에 CONTEXT 의 줄
범위를 통째로 찍어, 적중 줄 하나만으로는 대 볼 수 없던 함수 본문을 남긴다.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

TAG = "v1.9.4"
URL = (
    "https://raw.githubusercontent.com/huggingface/text-embeddings-inference/"
    f"{TAG}/core/src/tokenization.rs"
)
PATTERNS = [
    r"fn tokenize\b|fn tokenize_input\b|fn encode_input\b",
    r"cannot be empty",
    r"add_special_tokens",
    r"max_input_length",
    r"must have less than",
]
# (시작 줄, 끝 줄). 1부터 세는 소스 줄 번호다. `tokenize` 의 빈 입력 검사, `tokenize_input` 의
# 머리와 글자 수 상한, `encode_input` 의 본문(특수 토큰을 붙여 센 길이를 상한과 비교한다)이다.
CONTEXT = [(104, 118), (286, 310), (368, 405)]


def fetch(dest: Path) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"tei-tokenization-{TAG}.rs"
    if not target.exists():
        with urllib.request.urlopen(URL, timeout=60) as resp:
            target.write_bytes(resp.read())
    return target.read_text(encoding="utf-8")


def main() -> None:
    text = fetch(Path(sys.argv[1]))
    lines = text.splitlines()
    print("source", URL, "lines", len(lines))
    for pat in PATTERNS:
        rx = re.compile(pat)
        hits = [(i + 1, line) for i, line in enumerate(lines) if rx.search(line)]
        print(f"--- /{pat}/ hits={len(hits)}")
        for no, line in hits[:20]:
            print(f"  {no}: {line.strip()[:160]}")
    for start, end in CONTEXT:
        print(f"=== lines {start}-{end}")
        for no in range(start, end + 1):
            print(f"  {no}: {lines[no - 1].rstrip()[:160]}")


if __name__ == "__main__":
    main()
