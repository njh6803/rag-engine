"""임베딩 모델 카드(HTML)에서 자원·설정 낱말(GB, OOM, batch_size, max_length, fp16, 3070, A800, GiB)
주변 글을 뽑는다. 태그를 벗기고 공백을 접은 뒤 낱말 앞뒤 220자를 찍는다(같은 머리 60자는 한 번만).

실행: uv run python -I .scratch/core/probes/embedding/disc_extract.py <모델 카드 HTML 파일>
(저장소 루트에서. 표준 라이브러리만 쓴다. 입력은 Hugging Face 모델 카드 페이지를 내려받은 HTML
이다.)

2026-11-09에 임베딩 후보 모델 카드의 토론·설정 글을 읽는 데 썼다(ADR 0010 의 모델 메모리·차원 메모).
내려받은 원문(스크래치패드 `embedding/dl/`)과 출력은 남기지 않았다.
"""

import html
import re
import sys

t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
t = html.unescape(re.sub(r"<[^>]+>", " ", t))
t = re.sub(r"\s+", " ", t)
seen: set[str] = set()
for m in re.finditer(r".{0,220}(GB|OOM|batch_size|max_length|fp16|3070|A800|GiB).{0,220}", t):
    s = m.group(0).strip()
    if s[:60] in seen:
        continue
    seen.add(s[:60])
    print("-", s)
