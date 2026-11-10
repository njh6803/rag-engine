"""물러난 판의 색인을 `DROP INDEX CONCURRENTLY` 로 지우면 새 SELECT 를 막지 않는지, 그 문장을
트랜잭션 안에서 부르면 어떻게 되는지를 PostgreSQL 18 에서 잰다.

근거로 드는 곳은 명세(`.scratch/core/spec.md`)의 판 전환(물러난 판의 색인 삭제)이다. 2026-11-10 티켓
세션의 spec-reviewer 가 세션 스크래치패드에서 돌린 임시 스크립트의 G 부분을 옮겼다(독스트링과 서식만
고쳤다. 같은 스크립트의 H 부분은 `uuid/probe_sqlalchemy.py`). 보는 것 둘.
G1. 열린 읽기 트랜잭션 뒤에 줄 선 `DROP INDEX CONCURRENTLY` 가 새 SELECT 를 막는지(`ddl_locks.py` 의
    D 와 같은 자리에서 일반 `DROP INDEX` 는 막았다).
G2. 트랜잭션 안의 `DROP INDEX CONCURRENTLY` 가 내는 예외.

실행(저장소 루트에서. `ddl_locks.py` 가 `chunks` 표를 만든 같은 데이터베이스에 이어서 돈다):
    uv run --with "psycopg[binary]==3.3.8" python -I -X utf8 \
        .scratch/core/probes/pg-ddl/drop_concurrently.py postgresql://postgres:probe@127.0.0.1:55432/postgres
출력은 `drop_concurrently_out.txt`(2026-11-10)다.
"""

import sys
import threading
import time

import psycopg

DSN = sys.argv[1]


def blocked(sql: str) -> str:
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("SET statement_timeout = 1500")
        t = time.monotonic()
        try:
            c.execute(sql)
            return f"ran in {time.monotonic() - t:.2f}s"
        except psycopg.errors.QueryCanceled:
            return "blocked"


def part_g() -> None:
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("CREATE INDEX idx_g ON chunks (document_id)")
    reader = psycopg.connect(DSN, autocommit=False)
    reader.execute("SELECT 1 FROM chunks LIMIT 1")
    out: list[str] = []

    def dropper() -> None:
        with psycopg.connect(DSN, autocommit=True) as c:
            t = time.monotonic()
            c.execute("DROP INDEX CONCURRENTLY idx_g")
            out.append(f"{time.monotonic() - t:.2f}s")

    th = threading.Thread(target=dropper)
    th.start()
    time.sleep(0.5)
    select = "SELECT count(*) FROM (SELECT 1 FROM chunks LIMIT 5) s"
    print("G1: new SELECT behind DROP INDEX CONCURRENTLY ->", blocked(select))
    time.sleep(1.0)
    reader.commit()
    reader.close()
    th.join(10)
    print("G1: DROP INDEX CONCURRENTLY finished after", out)
    with psycopg.connect(DSN, autocommit=False) as c:
        try:
            c.execute("DROP INDEX CONCURRENTLY IF EXISTS nope")
            print("G2: inside tx -> accepted")
        except psycopg.errors.ActiveSqlTransaction as e:
            print("G2: inside tx ->", type(e).__name__, e.sqlstate)


if __name__ == "__main__":
    print("psycopg", psycopg.__version__)
    part_g()
