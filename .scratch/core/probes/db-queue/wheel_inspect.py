"""내려받은 휠에서 라이선스 파일 원문의 머리와 SQL 잠금 키워드를 찾는다.

사용: uv run python -I .scratch/core/probes/db-queue/wheel_inspect.py <다운로드 디렉터리>
(저장소 루트에서. 표준 라이브러리만 쓴다. <다운로드 디렉터리>는 pypi_meta.py 가 휠을 받은 곳.)

2026-11-09에 pypi_meta.py 가 받은 휠에 돌려 표준 출력을 같은 폴더의 `report_wheels.txt`로
남겼다(휠 이름에 판이 있다. 예: sqlalchemy 2.1.8, alembic 1.20.1, psycopg 3.3.8, asyncpg 0.32.0,
uuid6 2025.0.1, uuid-utils 1.2.0). 휠은 옮기지 않았다. 같은 이름의 `parsers/wheel_inspect.py`는 다른
스크립트다.

키워드 판정은 처음에 `k.lower() in text.lower()`라 `LISTEN`이 `listener`에, `NOTIFY`가
`notify`에 걸려 alembic·fastapi·celery 행에 PostgreSQL과 무관한 적중이 실렸다(PR #2의
CodeRabbit 지적). SQL 키워드 셋은 원문 대소문자 그대로 단어 경계로, 함수 이름 접두 둘은 앞 경계만
두고(뒤에 `_lock`이 이어진다), 나머지 셋은 전처럼 대소문자 무시 부분 일치로 좁힌 뒤 휠을 다시
받아 `report_wheels.txt`를 다시 만들었다(같은 날).

다시 받은 휠은 서른하나다. 처음 보고에 없던 pg0-embedded·pgbox·pgembed 셋이 들었고, pgqueuer는
그 사이 올라온 2.0.0이다(2026-11-09 08:35 UTC 업로드. `report_q3.txt`와 ADR 0009가 본 판은
1.6.0이고, ADR 0009가 거부 사유로 든 pydantic-settings·typer 의존은 2.0.0의 requires_dist에도
있다. 재실행한 pypi_meta.py의 출력에서 손으로 봤고 그 출력은 옮기지 않았다).
"""

import re
import sys
import zipfile
from pathlib import Path

LICENSE_HINTS = [
    ("LGPL-3.0", "GNU LESSER GENERAL PUBLIC LICENSE\n                       Version 3"),
    ("LGPL-3.0", "GNU LESSER GENERAL PUBLIC LICENSE"),
    ("GPL-3.0", "GNU GENERAL PUBLIC LICENSE"),
    ("Apache-2.0", "Apache License"),
    ("MIT", "Permission is hereby granted, free of charge"),
    ("BSD", "Redistribution and use in source and binary forms"),
    ("PostgreSQL", "PostgreSQL License"),
]

KEYWORDS = [
    "SKIP LOCKED",
    "pg_advisory",
    "pg_try_advisory",
    "LISTEN",
    "NOTIFY",
    "queueing_lock",
    "dedupe",
    "heartbeat",
]
# SQL 키워드는 원문 대소문자 그대로 단어 경계로, 함수 접두는 앞 경계만(뒤에 `_lock`이 온다).
SQL_WORDS = {"SKIP LOCKED", "LISTEN", "NOTIFY"}
SQL_PREFIXES = {"pg_advisory", "pg_try_advisory"}
PATTERNS = {
    k: (
        re.compile(rf"\b{re.escape(k)}\b")
        if k in SQL_WORDS
        else re.compile(rf"\b{re.escape(k)}")
        if k in SQL_PREFIXES
        else re.compile(re.escape(k), re.I)
    )
    for k in KEYWORDS
}


def classify(text: str) -> str:
    found = []
    for name, hint in LICENSE_HINTS:
        if hint in text and name not in found:
            found.append(name)
    return ",".join(found) or "?"


def main() -> None:
    d = Path(sys.argv[1])
    for whl in sorted(d.glob("*.whl")):
        print("=" * 78)
        print(f"[{whl.name}]")
        with zipfile.ZipFile(whl) as zf:
            names = zf.namelist()
            lic_names = [
                n
                for n in names
                if ".dist-info/" in n
                and re.search(r"(LICENSE|LICENCE|COPYING|NOTICE)", n, re.I)
                and not n.endswith("/")
            ]
            if not lic_names:
                print("  라이선스 파일: 휠에 없음")
            for n in lic_names:
                text = zf.read(n).decode("utf-8", errors="replace")
                head = " | ".join(line.strip() for line in text.splitlines()[:6] if line.strip())
                print(f"  라이선스 파일: {n} ({len(text)}자) -> 판정 {classify(text)}")
                print(f"    머리: {head[:300]}")
                # LGPL 판에서 4절 제목 확인
                if "LESSER" in text:
                    m = re.search(r"Version (\d)", text)
                    print(f"    LGPL 판: {m.group(0) if m else '?'}")
            # SQL/파이썬 소스 속 잠금 키워드
            hits: dict[str, list[str]] = {k: [] for k in KEYWORDS}
            for n in names:
                if not n.endswith((".sql", ".py", ".pyi", ".txt", ".md", ".rst")):
                    continue
                try:
                    text = zf.read(n).decode("utf-8", errors="replace")
                except Exception:
                    continue
                for k, pattern in PATTERNS.items():
                    if pattern.search(text):
                        hits[k].append(n.split("/", 1)[-1])
            shown = {k: sorted(set(v))[:6] for k, v in hits.items() if v}
            if shown:
                print(f"  키워드 적중: {shown}")
            pyi = [n for n in names if n.endswith(".pyi")]
            if pyi:
                print(f"  .pyi: {pyi[:10]}")


if __name__ == "__main__":
    main()
