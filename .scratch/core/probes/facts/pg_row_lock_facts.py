"""PostgreSQL 18 의 행 잠금 모드 충돌, 외래 키 검사가 거는 잠금, 기본 격리 수준을 원문으로 뽑는다.

근거로 드는 곳은 명세의 수집 파이프라인 절이다. PR #3 봇 2회차(CodeRabbit)가 재색인 시작과 동시
수집의 직렬화를 짚어, 재색인 시작이 지식베이스 행을 잠근 채 문서마다 색인 상태와 작업 행을 넣을
때(외래 키 검사가 문서 행에 잠금을 건다) 문서 행을 먼저 잠그고 지식베이스 행을 기다리는 수집·삭제와
교착하는지, 재색인 시작이 잠근 대기 작업을 작업자가 건너뛰는지를 본다. 보는 것 다섯. 첫째, 행 잠금
모드 절에서 `FOR UPDATE` 가 `SELECT FOR KEY SHARE` 를 막고 `FOR NO KEY UPDATE` 는 막지 않는다는
문장. 둘째, 같은 절에서 키 열을 바꾸지 않는 `UPDATE` 가 `FOR NO KEY UPDATE` 를 건다는 문장과 그 키
열(외래 키에 쓸 수 있는 유일 색인의 열)의 정의. 셋째, `ri_triggers.c` 의 `RI_FKey_check` 가 참조하는
행을 `FOR KEY SHARE OF x` 로 읽는 질의. 넷째, 격리 수준 절에서 Read Committed 가 기본이고 질의는 그
질의가 시작되기 전에 커밋된 것을 본다는 문장. 다섯째, SELECT 절에서 `SKIP LOCKED` 가 바로 잠글 수
없는 행을 건너뛴다는 문장과, 행 잠금 절에서 행 잠금이 트랜잭션 끝에 풀린다는 문장이다.

실행(저장소 루트에서. 판 고정 문서 세 쪽과 GitHub raw 의 브랜치 고정 소스 하나를 받는다. 표준
라이브러리만):
    uv run python -I -X utf8 .scratch/core/probes/facts/pg_row_lock_facts.py <폴더>
`<폴더>` 는 저장소 밖(세션 스크래치패드)이다. 받은 파일은 읽기만 한다.
출력은 `pg_row_lock_facts_out.txt` 로 남겼다(2026-11-10). 소스는 패턴 적중 줄과, `RI_FKey_check`
안에서 `FOR KEY SHARE OF x` 를 붙이는 줄과 그 앞 30줄(질의를 조립하는 부분)을 찍는다.
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request
from pathlib import Path

DOCS = {
    "explicit-locking-18.html": "https://www.postgresql.org/docs/18/explicit-locking.html",
    "transaction-iso-18.html": "https://www.postgresql.org/docs/18/transaction-iso.html",
    "sql-select-18.html": "https://www.postgresql.org/docs/18/sql-select.html",
}
BRANCH = "REL_18_STABLE"
SOURCE = (
    "https://raw.githubusercontent.com/postgres/postgres/"
    f"{BRANCH}/src/backend/utils/adt/ri_triggers.c"
)
# 문서에서 찍을 문장. 행 잠금 모드 셋의 충돌, Read Committed 의 스냅숏, SKIP LOCKED 와 행 잠금의
# 수명이다.
DOC_PATTERNS = [
    r"SELECT FOR KEY SHARE of these rows will be blocked",
    r"will not block SELECT FOR KEY SHARE",
    r"SELECT FOR UPDATE is blocked, but not SELECT FOR NO KEY UPDATE",
    r"also acquired by any UPDATE that does not acquire a FOR UPDATE lock",
    r"UPDATE that modifies the values of certain columns",
    r"set of columns considered for the UPDATE case",
    r"Read Committed is the default isolation level",
    r"sees only data committed before the query began",
    r"sees a snapshot as of the start of the query",
    r"SKIP LOCKED ?, any selected rows that cannot be immediately locked are skipped",
    r"Row-level locks are released at transaction end",
]
SOURCE_PATTERNS = [r"^RI_FKey_check\(", r"FOR KEY SHARE"]


def fetch(dest: Path, name: str, url: str) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / name
    for attempt in range(3):
        if target.exists():
            break
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                target.write_bytes(resp.read())
        except OSError as exc:
            print(f"fetch {name} attempt {attempt + 1} failed: {exc}")
            if attempt < 2:
                time.sleep(2)
    return target.read_text(encoding="utf-8")


def sentences(page: str) -> list[str]:
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = " ".join(text.split())
    return re.split(r"(?<=[.;:])\s+", text)


def main() -> None:
    dest = Path(sys.argv[1])
    for name, url in DOCS.items():
        found = sentences(fetch(dest, name, url))
        print("doc", url, "sentences", len(found))
        for pat in DOC_PATTERNS:
            hits = [s for s in found if re.search(pat, s)]
            if hits:
                print(f"--- /{pat}/ hits={len(hits)}")
                for s in hits[:3]:
                    print(f"  {s[:400]}")
    lines = fetch(dest, f"ri_triggers-{BRANCH}.c", SOURCE).splitlines()
    print("source", SOURCE, "lines", len(lines))
    for pat in SOURCE_PATTERNS:
        rx = re.compile(pat)
        hits = [(i + 1, line) for i, line in enumerate(lines) if rx.search(line)]
        print(f"--- /{pat}/ hits={len(hits)}")
        for no, line in hits[:10]:
            print(f"  {no}: {line.strip()[:160]}")
    start = next(i for i, line in enumerate(lines) if line.startswith("RI_FKey_check("))
    end = next(i for i in range(start, len(lines)) if 'FOR KEY SHARE OF x");' in lines[i])
    first = max(start, end - 30)
    print(f"=== RI_FKey_check starts at line {start + 1}; query build lines {first + 1}-{end + 1}")
    for no in range(first, end + 1):
        print(f"  {no + 1}: {lines[no].rstrip()[:160]}")


if __name__ == "__main__":
    main()
