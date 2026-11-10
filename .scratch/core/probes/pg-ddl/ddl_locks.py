"""판마다의 부분 HNSW 색인을 만들고 지우는 DDL 이 조각 표의 읽기·쓰기를 막는지, NUL 글과 같은 문서의
대기 작업 부분 유일 색인이 어떤 예외로 오는지를 PostgreSQL 18 + pgvector 0.8.7 에서 잰다.

근거로 드는 곳은 명세(`.scratch/core/spec.md`)의 재색인 시작, 판 전환, 실패 분류, `jobs` 칸이다.
2026-11-10 티켓 세션의 spec-reviewer 가 세션 스크래치패드에서 돌린 임시 스크립트를 옮겨(독스트링과
서식만 고쳤다) 다시 돌렸다. 보는 것 여섯.
A. 조건이 0행에 맞는 부분 HNSW 색인 만들기의 시간(조각 표의 행 수는 둘째 인자).
B. 트랜잭션 안의 `CREATE INDEX` 가 같은 표의 INSERT 를 막고 SELECT 는 막지 않는지.
C. 트랜잭션 안의 `DROP INDEX` 가 같은 표의 SELECT 를 막는지.
D. 열린 읽기 트랜잭션 뒤에 줄 선 `DROP INDEX` 가 새 SELECT 까지 막는지(잠금 대기열).
E. 글 칸과 jsonb 의 NUL 이 어떤 예외로 오는지.
F. 같은 문서의 `queued` 부분 유일 색인에서 둘째 `queued` 를 넣거나 `running` 을 `queued` 로 되돌릴
때. 막혔는지는 `statement_timeout` 1.5초로 가린다(취소되면 막힌 것).

실행(저장소 루트에서. 테스트와 같은 판의 이미지를 띄운다):
    docker run -d --rm --name rag-probe-pg -p 55432:5432 -e POSTGRES_PASSWORD=probe \
        pgvector/pgvector:0.8.7-pg18-trixie
    uv run --with "psycopg[binary]==3.3.8" python -I -X utf8 \
        .scratch/core/probes/pg-ddl/ddl_locks.py \
        postgresql://postgres:probe@127.0.0.1:55432/postgres 200000
같은 데이터베이스에 이어서 `drop_concurrently.py` 를 돌리고 컨테이너를 내린다. 출력은
`ddl_locks_out.txt`(20만 행, 2026-11-10)다.
"""

import sys
import threading
import time
import uuid

import psycopg
from psycopg.types.json import Jsonb

DSN = sys.argv[1]
N = int(sys.argv[2])
A_VER = uuid.uuid4()
SELECT_A = (
    f"SELECT count(*) FROM (SELECT 1 FROM chunks WHERE index_version_id = '{A_VER}' LIMIT 5) s"
)


def conn(*, autocommit: bool = True) -> psycopg.Connection:
    return psycopg.connect(DSN, autocommit=autocommit)


def blocked(sql: str, ms: int = 1500) -> str:
    with conn() as c:
        c.execute(f"SET statement_timeout = {ms}")
        t = time.monotonic()
        try:
            c.execute(sql)
            return f"ran in {time.monotonic() - t:.2f}s"
        except psycopg.errors.QueryCanceled:
            return f"blocked (canceled after {time.monotonic() - t:.2f}s)"


def setup() -> None:
    with conn() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.execute("DROP TABLE IF EXISTS chunks")
        c.execute(
            "CREATE TABLE chunks (id bigserial PRIMARY KEY, index_version_id uuid NOT NULL,"
            " document_id uuid NOT NULL, text text NOT NULL, embedding vector NOT NULL)"
        )
        t = time.monotonic()
        c.execute(
            "WITH v AS (SELECT array_agg(random())::vector AS e FROM generate_series(1, 1024))"
            " INSERT INTO chunks (index_version_id, document_id, text, embedding)"
            " SELECT %s, gen_random_uuid(), repeat('가나다라마바사 ', 60), v.e"
            " FROM v, generate_series(1, %s)",
            (A_VER, N),
        )
        print(f"setup: inserted {N} rows in {time.monotonic() - t:.1f}s")
        c.execute("VACUUM ANALYZE chunks")
        row = c.execute(
            "SELECT pg_size_pretty(pg_relation_size('chunks')),"
            " pg_size_pretty(pg_total_relation_size('chunks'))"
        ).fetchone()
        print(f"setup: heap={row[0]} total={row[1]}" if row else "setup: no size")
        print(
            "pgvector:",
            c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone(),
        )
        print("server:", c.execute("SHOW server_version").fetchone())


def create_idx_sql(name: str, ver: uuid.UUID) -> str:
    return (
        f"CREATE INDEX {name} ON chunks USING hnsw ((embedding::vector(1024)) vector_cosine_ops)"
        f" WHERE index_version_id = '{ver}'"
    )


def part_a() -> None:
    with conn() as c:
        for i in range(2):
            t = time.monotonic()
            c.execute(create_idx_sql(f"idx_a{i}", uuid.uuid4()))
            print(f"A: CREATE INDEX (0 matching rows of {N}) took {time.monotonic() - t:.2f}s")


def part_b() -> None:
    holder = conn(autocommit=False)
    holder.execute(create_idx_sql("idx_b", uuid.uuid4()))
    ins = (
        f"INSERT INTO chunks (index_version_id, document_id, text, embedding)"
        f" SELECT '{uuid.uuid4()}', gen_random_uuid(), 'x', embedding FROM chunks LIMIT 1"
    )
    print("B: INSERT while CREATE INDEX tx open ->", blocked(ins))
    print(
        "B: SELECT while CREATE INDEX tx open ->",
        blocked(SELECT_A),
    )
    holder.rollback()
    holder.close()


def part_c() -> None:
    with conn() as c:
        c.execute(create_idx_sql("idx_c", uuid.uuid4()))
    holder = conn(autocommit=False)
    holder.execute("DROP INDEX idx_c")
    print(
        "C: SELECT while DROP INDEX tx open ->",
        blocked(SELECT_A),
    )
    holder.rollback()
    holder.close()


def part_d() -> None:
    reader = conn(autocommit=False)
    reader.execute("SELECT 1 FROM chunks LIMIT 1")  # 열린 읽기 트랜잭션(긴 검색이나 쓰기의 자리)
    done: list[str] = []

    def dropper() -> None:
        with conn() as c:
            t = time.monotonic()
            c.execute("DROP INDEX idx_a0")
            done.append(f"{time.monotonic() - t:.2f}s")

    th = threading.Thread(target=dropper)
    th.start()
    time.sleep(0.5)
    print(
        "D: new SELECT behind queued DROP INDEX ->",
        blocked(SELECT_A),
    )
    reader.commit()
    reader.close()
    th.join(10)
    print("D: DROP INDEX finished after", done)


def part_e() -> None:
    with conn() as c:
        c.execute("CREATE TEMP TABLE t (s text, j jsonb)")
        for label, sql, params in [
            ("text NUL", "INSERT INTO t (s) VALUES (%s)", ("a\x00b",)),
            ("jsonb NUL", "INSERT INTO t (j) VALUES (%s)", (Jsonb({"t": "a\x00b"}),)),
        ]:
            try:
                c.execute(sql, params)
                print(f"E: {label} -> accepted")
            except Exception as e:  # 프로브: 어떤 예외든 종류를 찍는다
                mro = [k.__name__ for k in type(e).__mro__[:4]]
                print(f"E: {label} -> {mro} sqlstate={getattr(e, 'sqlstate', None)}")


def part_f() -> None:
    with conn() as c:
        c.execute("CREATE TEMP TABLE jobs (id serial, document_id int, status text)")
        c.execute("CREATE UNIQUE INDEX one_queued ON jobs (document_id) WHERE status = 'queued'")
        c.execute("INSERT INTO jobs (document_id, status) VALUES (1, 'running'), (1, 'queued')")
        try:
            c.execute("UPDATE jobs SET status = 'queued' WHERE status = 'running'")
            print("F: running -> queued with another queued -> accepted")
        except psycopg.errors.UniqueViolation as e:
            print("F: running -> queued with another queued ->", type(e).__name__, e.sqlstate)
        try:
            c.execute("INSERT INTO jobs (document_id, status) VALUES (1, 'queued')")
            print("F: second queued insert -> accepted")
        except psycopg.errors.UniqueViolation as e:
            print("F: second queued insert ->", type(e).__name__, e.sqlstate)


if __name__ == "__main__":
    print("psycopg", psycopg.__version__)
    setup()
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    part_f()
