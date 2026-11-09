"""PDF 텍스트를 뽑아 키워드 줄을 찍는다.

실행(저장소 루트에서):
    uv run --no-project --with pypdf python -I -X utf8 \\
        .scratch/core/probes/vector-store/pdf_text.py <pdf> <out.txt> <kw>...
(pypdf 를 임시로 얹는다. 판은 적어 두지 않았다.)

2026-11-09에 Elasticsearch 구독 등급표 PDF(fetch_list.py 가 받은 `elastic_subscriptions.pdf`)에
돌렸다. 표의 열이 텍스트 추출에서 사라져 등급을 대조하지 못했다(비교 문서 열린 사실 15). 출력 파일은
남기지 않았다.
"""

import pathlib
import re
import sys

from pypdf import PdfReader

r = PdfReader(sys.argv[1])
text = "\n".join((p.extract_text() or "") for p in r.pages)
pathlib.Path(sys.argv[2]).write_text(text, encoding="utf-8")
print(f"# pages={len(r.pages)} chars={len(text)}")
for kw in sys.argv[3:]:
    hits = [m.start() for m in re.finditer(re.escape(kw), text, re.I)][:4]
    print(f"\n## {kw!r} x{len(hits)}")
    for h in hits:
        print("  ..." + re.sub(r"\s+", " ", text[max(0, h - 120) : h + 180]) + "...")
