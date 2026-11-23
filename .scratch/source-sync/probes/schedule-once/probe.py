"""작업자 여럿이 같은 순간에 일정을 확인해도 동기화 작업이 원천마다 한 번만 들어가는지를
PostgreSQL 18 에서 잰다(ADR 0022 "시작시키는 쪽"과 "지키는 것", source-sync 명세).

ADR 0022 는 작업자가 대기열을 살피는 주기에 다음 실행 시각이 지난 원천을 찾아 동기화 작업을 넣게
했고, 작업자를 여럿 띄워도 한 번만 시작되게 하는 장치를 원천 행의 잠금으로 적었다. 명세가 그 장치의
모양과 겹침 방지의 구조, 작업을 꺼내는 순서를 정하기 전에 여섯 가지를 본다.
A. 원천 행을 `FOR UPDATE SKIP LOCKED` 로 잡고 같은 트랜잭션에서 작업을 넣고 다음 실행 시각을 옮기면
   연결 여덟이 동시에 돌아도 원천마다 작업이 하나인지. A 는 원천을 하나씩 잡아 원천마다 커밋하고,
   A2 는 명세가 적은 모양대로 시각이 지난 원천을 트랜잭션 하나에서 모두 잡아 한 번에 커밋한다.
B. 대조. 행을 잠그지 않고 읽어서 넣으면 같은 원천에 작업이 둘 이상 들어가는지(이 프로브가 중복을
   볼 수 있는지를 함께 확인한다).
C. 행을 잠그지 않고 `UPDATE … WHERE next_run_at = <읽은 값> RETURNING` 이 돌려준 쪽만 넣는 방법.
D. 원천마다 종류마다 대기·실행 중 작업을 하나로 묶는 부분 유일 색인. 연결 여덟이 같은 원천에 동시에
   넣을 때 하나만 들어가는지, 앞 작업이 실행 중이면 막고 끝나면 다시 받는지, `ON CONFLICT` 의 술어를
   리터럴로 적을 때와 바인드 값으로 적을 때 같은 문장을 스무 번 돌리면 어떻게 되는지.
E. 문서도 원천도 가리키지 않는 작업(정리 작업) 둘이 유일 색인에 걸리는지. 널은 서로 다른 값으로
   보므로 걸리지 않을 것이고, `NULLS NOT DISTINCT` 로 묶이는지를 함께 본다.
F. 색인 작업 10만 건이 대기 중일 때, 동기화 작업을 먼저 꺼내도록 종류로 가른 순서의 질의가 지금의
   순서(예약 시각, 식별자)의 질의보다 얼마나 걸리는지. 색인 작업이 아닌 것만 먼저 묻는 질의를 부분
   색인과 함께 따로 두는 방법도 함께 잰다.

표는 지금의 `jobs`(`src/rag_engine/adapters/postgres/tables.py`)에서 이 물음에 닿는 칸만 옮기고
원천 참조 칸을 더한 것이다. 문서 표가 없어 문서 참조의 외래 키는 두지 않는다. A~C 는 넣기 직전에
`pg_sleep` 으로 틈을 벌린 것과 벌리지 않은 것을 둘 다 돈다.

실행(저장소 루트에서. 테스트와 같은 버전의 이미지를 따로 띄운다):
    docker run -d --rm --name rag-probe-sync-pg -p 127.0.0.1:55441:5432 \
        -e POSTGRES_PASSWORD=probe pgvector/pgvector:0.8.7-pg18-trixie
    uv run --with "psycopg[binary]==3.3.8" python -I -X utf8 \
        .scratch/source-sync/probes/schedule-once/probe.py \
        postgresql://postgres:probe@127.0.0.1:55441/postgres
출력은 `probe_out.txt` 다. 스키마 `probe_schedule_once` 를 만들고 끝에 지운다.
"""

from __future__ import annotations

import statistics
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import psycopg

DSN = sys.argv[1]
SCHEMA = "probe_schedule_once"
WORKERS = 8
SOURCES = 40
ROUNDS = 25
RACE_ROUNDS = 50
REPEATS = 20
QUEUED_INDEX_JOBS = 100_000
TIMED_RUNS = 15
ACTIVE = "status IN ('queued', 'running')"

PICK = (
    "SELECT id, next_run_at FROM sources WHERE next_run_at <= %s AND NOT paused"
    " ORDER BY next_run_at, id LIMIT 1"
)
PICK_ALL = (
    "SELECT id FROM sources WHERE next_run_at <= %s AND NOT paused"
    " ORDER BY next_run_at, id FOR UPDATE SKIP LOCKED"
)
INSERT_SYNC = (
    "INSERT INTO jobs (id, kind, source_id, status, run_after, created_at, round)"
    " VALUES (%s, 'sync_source', %s, 'queued', %s, %s, %s)"
)
ENQUEUE_SYNC = (
    "INSERT INTO jobs (id, kind, source_id, status, run_after, created_at)"
    " VALUES (%s, 'sync_source', %s, 'queued', %s, %s)"
    f" ON CONFLICT (source_id, kind) WHERE {ACTIVE} DO NOTHING RETURNING id"
)
ENQUEUE_SYNC_BOUND = (
    "INSERT INTO jobs (id, kind, source_id, status, run_after, created_at)"
    " VALUES (%s, 'sync_source', %s, 'queued', %s, %s)"
    " ON CONFLICT (source_id, kind) WHERE status IN (%s, %s) DO NOTHING RETURNING id"
)
CLAIM_FILTER = (
    "FROM jobs WHERE (status = 'queued' AND run_after <= %s)"
    " OR (status = 'running' AND leased_until <= %s)"
)
CLAIM_NOW = f"SELECT kind {CLAIM_FILTER} ORDER BY run_after, id LIMIT 1 FOR UPDATE SKIP LOCKED"
CLAIM_KIND_FIRST = (
    f"SELECT kind {CLAIM_FILTER} ORDER BY (kind = 'index_document'), run_after, id"
    " LIMIT 1 FOR UPDATE SKIP LOCKED"
)
OTHER_KINDS = f"kind <> 'index_document' AND {ACTIVE}"
CLAIM_OTHER_KINDS = (
    f"SELECT kind FROM jobs WHERE {OTHER_KINDS} AND ((status = 'queued' AND run_after <= %s)"
    " OR (status = 'running' AND leased_until <= %s))"
    " ORDER BY run_after, id LIMIT 1 FOR UPDATE SKIP LOCKED"
)


def connect() -> psycopg.Connection:
    return psycopg.connect(DSN, autocommit=True, options=f"-c search_path={SCHEMA},public")


def setup() -> None:
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        c.execute(f"CREATE SCHEMA {SCHEMA}")
        print("server:", c.execute("SHOW server_version").fetchone())
        print("psycopg:", psycopg.__version__, "/ libpq 구현:", psycopg.pq.__impl__)
    with connect() as c:
        print("prepare_threshold:", c.prepare_threshold)
        c.execute(
            "CREATE TABLE sources (id uuid PRIMARY KEY, name text NOT NULL UNIQUE,"
            " next_run_at timestamptz, paused boolean NOT NULL DEFAULT false)"
        )
        c.execute(
            "CREATE TABLE jobs (id uuid PRIMARY KEY, kind text NOT NULL, document_id uuid,"
            " source_id uuid REFERENCES sources (id), status text NOT NULL,"
            " attempts integer NOT NULL DEFAULT 0, run_after timestamptz NOT NULL,"
            " leased_until timestamptz, worker_id text, created_at timestamptz NOT NULL,"
            " round integer)"
        )
        c.execute(
            "CREATE UNIQUE INDEX uq_jobs_document_id_queued ON jobs (document_id)"
            " WHERE status = 'queued'"
        )
        c.execute(f"CREATE INDEX ix_jobs_document_id_active ON jobs (document_id) WHERE {ACTIVE}")
        for number in range(SOURCES):
            c.execute(
                "INSERT INTO sources (id, name) VALUES (%s, %s)",
                (uuid.uuid4(), f"source-{number:02d}"),
            )


def tick(
    c: psycopg.Connection,
    mode: str,
    now: datetime,
    following: datetime,
    round_no: int,
    gap: float,
) -> None:
    """일정 확인 한 번. 시각이 지난 원천을 하나씩 골라 작업을 넣고 다음 실행 시각을 옮긴다."""
    pick = PICK + (" FOR UPDATE SKIP LOCKED" if mode == "locked" else "")
    while True:
        with c.transaction():
            row = c.execute(pick, (now,)).fetchone()
            if row is None:
                return
            source_id, seen = row
            if gap:
                c.execute("SELECT pg_sleep(%s)", (gap,))
            if mode == "conditional":
                won = c.execute(
                    "UPDATE sources SET next_run_at = %s WHERE id = %s AND next_run_at = %s"
                    " RETURNING id",
                    (following, source_id, seen),
                ).fetchone()
                if won is None:
                    continue
            else:
                c.execute(
                    "UPDATE sources SET next_run_at = %s WHERE id = %s", (following, source_id)
                )
            c.execute(INSERT_SYNC, (uuid.uuid4(), source_id, now, now, round_no))


def tick_all(
    c: psycopg.Connection,
    now: datetime,
    following: datetime,
    round_no: int,
    gap: float,
) -> None:
    """일정 확인 한 번을 트랜잭션 하나로 한다(명세의 모양). 시각이 지난 원천을 모두 잡아 원천마다
    작업을 넣고 다음 실행 시각을 옮긴 뒤 한 번에 커밋한다."""
    with c.transaction():
        for (source_id,) in c.execute(PICK_ALL, (now,)).fetchall():
            if gap:
                c.execute("SELECT pg_sleep(%s)", (gap,))
            c.execute("UPDATE sources SET next_run_at = %s WHERE id = %s", (following, source_id))
            c.execute(INSERT_SYNC, (uuid.uuid4(), source_id, now, now, round_no))


def check_schedule(
    barrier: threading.Barrier,
    mode: str,
    now: datetime,
    round_no: int,
    gap: float,
) -> None:
    """연결 하나를 열어, 다른 연결들과 같은 순간에 일정 확인을 한 번 한다."""
    following = now + timedelta(hours=1)
    with connect() as c:
        barrier.wait()
        if mode == "locked_all":
            tick_all(c, now, following, round_no, gap)
        else:
            tick(c, mode, now, following, round_no, gap)


def worker(
    barrier: threading.Barrier,
    errors: list[str],
    mode: str,
    now: datetime,
    round_no: int,
    gap: float,
) -> None:
    try:
        check_schedule(barrier, mode, now, round_no, gap)
    except psycopg.Error as error:
        errors.append(f"{type(error).__name__} {error.sqlstate}")


def run_variant(mode: str, gap: float) -> str:
    """원천 40개가 모두 시각이 지난 채로 연결 여덟이 동시에 일정을 확인하는 일을 25회차 돈다."""
    total = extra = missing = 0
    errors: list[str] = []
    started = time.monotonic()
    with connect() as admin:
        admin.execute("TRUNCATE jobs")
        for round_no in range(ROUNDS):
            now = datetime.now(UTC)
            admin.execute("UPDATE sources SET next_run_at = %s", (now - timedelta(seconds=1),))
            barrier = threading.Barrier(WORKERS)
            threads = [
                threading.Thread(target=worker, args=(barrier, errors, mode, now, round_no, gap))
                for _ in range(WORKERS)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            counts = admin.execute(
                "SELECT count(j.id) FROM sources s LEFT JOIN jobs j"
                " ON j.source_id = s.id AND j.round = %s GROUP BY s.id",
                (round_no,),
            ).fetchall()
            for (count,) in counts:
                total += count
                extra += max(count - 1, 0)
                missing += count == 0
    elapsed = time.monotonic() - started
    return (
        f"넣은 작업 {total}건(기대 {SOURCES * ROUNDS}건), 한 원천에 더 들어간 작업 {extra}건,"
        f" 작업이 없는 원천 {missing}곳, 오류 {errors or '없음'}, {elapsed:.1f}초"
    )


def parts_abc() -> None:
    labels = {
        "locked": "A. 원천 행 잠금(FOR UPDATE SKIP LOCKED), 원천 하나씩 커밋",
        "locked_all": "A2. 원천 행 잠금, 시각이 지난 원천을 트랜잭션 하나에서 모두(명세의 모양)",
        "unlocked": "B. 대조: 잠금 없이 읽고 넣기",
        "conditional": "C. 조건부 UPDATE 가 돌려준 쪽만 넣기",
    }
    for mode, label in labels.items():
        for gap in (0.0, 0.002):
            print(f"{label}, 틈 {gap * 1000:.0f}ms: {run_variant(mode, gap)}")


def racer(barrier: threading.Barrier, wins: list[bool], source_id: uuid.UUID) -> None:
    with connect() as c:
        barrier.wait()
        now = datetime.now(UTC)
        row = c.execute(ENQUEUE_SYNC, (uuid.uuid4(), source_id, now, now)).fetchone()
        wins.append(row is not None)


def repeat(statement: str, source_ids: list[uuid.UUID], tail: tuple[str, ...]) -> str:
    """같은 연결에서 같은 문장을 스무 번 돌린다. 원천을 바꿔 가며 넣으므로 매번 새 행이 든다."""
    with connect() as c:
        for number in range(1, REPEATS + 1):
            now = datetime.now(UTC)
            try:
                c.execute(statement, (uuid.uuid4(), source_ids[number], now, now, *tail))
            except psycopg.Error as error:
                return f"{number}번째 실행에서 {type(error).__name__} {error.sqlstate}"
    return f"{REPEATS}번 모두 통과"


def part_d() -> None:
    with connect() as admin:
        admin.execute("TRUNCATE jobs")
        admin.execute(
            f"CREATE UNIQUE INDEX uq_jobs_source_kind_active ON jobs (source_id, kind)"
            f" WHERE {ACTIVE}"
        )
        source_ids = [row[0] for row in admin.execute("SELECT id FROM sources ORDER BY name")]
        target = source_ids[0]
        spread: Counter[int] = Counter()
        short_rounds = 0
        for _ in range(RACE_ROUNDS):
            admin.execute("UPDATE jobs SET status = 'succeeded' WHERE source_id = %s", (target,))
            barrier = threading.Barrier(WORKERS)
            wins: list[bool] = []
            threads = [
                threading.Thread(target=racer, args=(barrier, wins, target)) for _ in range(WORKERS)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            spread[sum(wins)] += 1
            # 연결이 예외로 끝나면 답을 남기지 못한다. 그런 회차가 분포에 조용히 섞이지 않게 센다.
            short_rounds += len(wins) != WORKERS
        print(
            f"D1. 연결 {WORKERS}개가 같은 원천에 동시에 넣기 {RACE_ROUNDS}회차,"
            f" 회차마다 들어간 작업 수의 분포: {dict(spread)},"
            f" 연결 {WORKERS}개가 모두 답하지 않은 회차 {short_rounds}"
        )
        now = datetime.now(UTC)
        admin.execute("UPDATE jobs SET status = 'running' WHERE status = 'queued'")
        running = admin.execute(ENQUEUE_SYNC, (uuid.uuid4(), target, now, now)).fetchone()
        print("D2. 앞 작업이 실행 중일 때 넣기:", "들어갔다" if running else "들어가지 않았다")
        admin.execute("UPDATE jobs SET status = 'succeeded' WHERE status = 'running'")
        finished = admin.execute(ENQUEUE_SYNC, (uuid.uuid4(), target, now, now)).fetchone()
        print("D2. 앞 작업이 끝난 뒤 넣기:", "들어갔다" if finished else "들어가지 않았다")
        admin.execute("TRUNCATE jobs")
        print("D3. 술어를 리터럴로 적은 문장:", repeat(ENQUEUE_SYNC, source_ids, ()))
        admin.execute("TRUNCATE jobs")
        bound = repeat(ENQUEUE_SYNC_BOUND, source_ids, ("queued", "running"))
        print("D3. 술어를 바인드 값으로 적은 문장:", bound)


def insert_cleanup(c: psycopg.Connection, suffix: str = "") -> str:
    now = datetime.now(UTC)
    try:
        row = c.execute(
            "INSERT INTO jobs (id, kind, status, run_after, created_at)"
            f" VALUES (%s, 'cleanup', 'queued', %s, %s){suffix} RETURNING id",
            (uuid.uuid4(), now, now),
        ).fetchone()
    except psycopg.Error as error:
        return f"{type(error).__name__} {error.sqlstate}"
    return "들어갔다" if row else "들어가지 않았다(오류 없음)"


def part_e() -> None:
    with connect() as c:
        c.execute("TRUNCATE jobs")
        print(
            "E1. D 의 유일 색인(빈 값을 서로 다른 값으로 본다)이 있을 때 정리 작업 둘:",
            insert_cleanup(c),
            "/",
            insert_cleanup(c),
        )
        c.execute("TRUNCATE jobs")
        c.execute("DROP INDEX uq_jobs_source_kind_active")
        scope = f"document_id IS NULL AND {ACTIVE}"
        c.execute(
            "CREATE UNIQUE INDEX uq_jobs_source_kind_active ON jobs (source_id, kind)"
            f" NULLS NOT DISTINCT WHERE {scope}"
        )
        print(
            "E2. NULLS NOT DISTINCT 색인에서 정리 작업 둘:",
            insert_cleanup(c),
            "/",
            insert_cleanup(c),
        )
        conflict = f" ON CONFLICT (source_id, kind) WHERE {scope} DO NOTHING"
        print("E2. 같은 색인에 ON CONFLICT DO NOTHING 으로 셋째:", insert_cleanup(c, conflict))
        source_id = c.execute("SELECT id FROM sources ORDER BY name LIMIT 1").fetchone()
        now = datetime.now(UTC)
        outcomes: list[str] = []
        for _ in range(2):
            row = c.execute(
                "INSERT INTO jobs (id, kind, source_id, status, run_after, created_at)"
                f" VALUES (%s, 'sync_source', %s, 'queued', %s, %s){conflict} RETURNING id",
                (uuid.uuid4(), source_id[0] if source_id else None, now, now),
            ).fetchone()
            outcomes.append("들어갔다" if row else "들어가지 않았다")
        print("E2. 같은 색인에서 같은 원천의 동기화 작업 둘:", " / ".join(outcomes))
        documents: list[str] = []
        for _ in range(2):
            c.execute(
                "INSERT INTO jobs (id, kind, document_id, status, run_after, created_at)"
                " VALUES (%s, 'index_document', %s, 'running', %s, %s)",
                (uuid.uuid4(), uuid.uuid4(), now, now),
            )
            documents.append("들어갔다")
        print("E2. 같은 색인에서 서로 다른 문서의 색인 작업 둘:", " / ".join(documents))


def timed(c: psycopg.Connection, statement: str, now: datetime) -> str:
    picked: set[str] = set()
    samples: list[float] = []
    for _ in range(TIMED_RUNS):
        with c.transaction(force_rollback=True):
            started = time.perf_counter()
            row = c.execute(statement, (now, now)).fetchone()
            samples.append((time.perf_counter() - started) * 1000)
            picked.add(str(row[0]) if row else "없음")
    return (
        f"꺼낸 종류 {sorted(picked)}, 가운데값 {statistics.median(samples):.1f}ms,"
        f" 가장 긴 것 {max(samples):.1f}ms({TIMED_RUNS}번)"
    )


def part_f() -> None:
    with connect() as c:
        c.execute("TRUNCATE jobs")
        now = datetime.now(UTC)
        for status in ("queued", "succeeded"):
            c.execute(
                "INSERT INTO jobs (id, kind, document_id, status, run_after, created_at)"
                " SELECT gen_random_uuid(), 'index_document', gen_random_uuid(), %s,"
                " %s - random() * interval '6 hours', %s FROM generate_series(1, %s)",
                (status, now, now, QUEUED_INDEX_JOBS),
            )
        source_id = c.execute("SELECT id FROM sources ORDER BY name LIMIT 1").fetchone()
        c.execute(
            "INSERT INTO jobs (id, kind, source_id, status, run_after, created_at)"
            " VALUES (%s, 'sync_source', %s, 'queued', %s, %s)",
            (uuid.uuid4(), source_id[0] if source_id else None, now, now),
        )
        c.execute("ANALYZE jobs")
        print(
            f"F. 대기 중인 색인 작업 {QUEUED_INDEX_JOBS}건, 끝난 색인 작업 {QUEUED_INDEX_JOBS}건,"
            " 가장 늦게 들어온 동기화 작업 1건"
        )
        print("F. 지금의 순서(예약 시각, 식별자):", timed(c, CLAIM_NOW, now))
        print("F. 종류로 가른 순서(색인 작업을 뒤로):", timed(c, CLAIM_KIND_FIRST, now))
        c.execute(f"CREATE INDEX ix_jobs_other_kinds ON jobs (run_after, id) WHERE {OTHER_KINDS}")
        c.execute("ANALYZE jobs")
        print("F. 색인 작업이 아닌 것만 먼저 묻기(부분 색인):", timed(c, CLAIM_OTHER_KINDS, now))
        plans = (
            ("지금 순서", CLAIM_NOW),
            ("종류로 가른 순서", CLAIM_KIND_FIRST),
            ("색인 작업이 아닌 것만 묻는 질의", CLAIM_OTHER_KINDS),
        )
        for label, statement in plans:
            plan = c.execute(
                f"EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF, SUMMARY OFF) {statement}", (now, now)
            ).fetchall()
            print(f"F. {label}의 계획:")
            for (line,) in plan:
                print("   ", line)


def main() -> None:
    setup()
    parts_abc()
    part_d()
    part_e()
    part_f()
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(f"DROP SCHEMA {SCHEMA} CASCADE")


if __name__ == "__main__":
    main()
