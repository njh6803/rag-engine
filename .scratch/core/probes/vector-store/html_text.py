"""HTML 원문에서 태그를 벗기고 키워드 주변 글을 뽑는다.

실행: uv run --no-project python -I -X utf8 .scratch/core/probes/vector-store/html_text.py \\
    <file> <keyword> [<keyword> ...] [--span N] [--count M]
(표준 라이브러리만 쓴다. <file>은 fetch_raw*.py 가 받은 HTML 원문.)

2026-11-09에 내려받은 문서 페이지를 읽는 데 썼다. 출력 파일은 남기지 않았다(읽은 자리는 비교 문서의
"읽음" 표기).
"""

import html
import pathlib
import re
import sys

args = [a for a in sys.argv[1:]]
span, count = 700, 2
if "--span" in args:
    i = args.index("--span")
    span = int(args[i + 1])
    del args[i : i + 2]
if "--count" in args:
    i = args.index("--count")
    count = int(args[i + 1])
    del args[i : i + 2]
path, kws = args[0], args[1:]
t = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
t = re.sub(r"<(script|style).*?</\1>", " ", t, flags=re.S)
t = re.sub(r"<[^>]+>", " ", t)
t = html.unescape(t)
t = re.sub(r"\s+", " ", t)
print(f"# {path} ({len(t)} chars)")
for kw in kws:
    hits = [m.start() for m in re.finditer(re.escape(kw), t)]
    print(f"\n## '{kw}' x{len(hits)}")
    for h in hits[:count]:
        print("  ..." + t[max(0, h - span // 4) : h + span] + "...")
