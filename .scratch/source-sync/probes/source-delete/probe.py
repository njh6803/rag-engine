"""원천 하나의 문서를 모두 임시 삭제하거나 되살릴 때 걸리는 시간을 PostgreSQL 18 + pgvector 0.8.7
에서 잰다(ADR 0021 "원천을 지우면 그 원천의 문서도 함께 임시 삭제한다", source-sync 명세).

설계의 셀프 리뷰가 명세에 넘긴 물음이 "원천 삭제를 작업 단위 하나로 할지 대기열의 작업으로
할지(문서가 수만 건일 때)"다. 문서 하나를 지우는 지금의 유스케이스(`src/rag_engine/app/
delete_document.py`)가 하는 일(조각을 삭제 보관함으로 옮기고, 색인 상태를 지우고, 문서 행의 세대를
올리며 지운 시각을 적는다)을 원천의 모든 문서에 한다. 보는 것 넷.
A. 한 트랜잭션에서 한꺼번에 지울 때 문장마다의 시간과, 그 트랜잭션이 열려 있는 동안 다른 연결의
   읽기와 쓰기가 막히는지.
B. 문서를 묶음(셋째 인자, 기본 500건)으로 나눠 묶음마다 트랜잭션을 닫을 때의 전체 시간과 묶음 하나의
   시간.
C. 지운 원천을 한 트랜잭션에서 한꺼번에 되살릴 때. 보관 조각이 HNSW 색인과 GIN 색인이 있는 조각 표로
   돌아간다.
D. 되살리기를 묶음으로 나눠 할 때.

표는 지금의 표(`src/rag_engine/adapters/postgres/tables.py`)에서 조각과 삭제 보관함의 칸을 그대로
옮기고, 문서와 원천과 색인 상태는 이 물음에 닿는 칸만 둔다. 조각의 벡터는 행마다 다른 무작위
1024차원이고 글은 행마다 다른 낱말 40개다. 보지 못하는 것: 지식베이스 행의 잠금과 버전 전환 검사,
대기 작업 지우기, 검색과 색인이 함께 도는 부하. 디스크는 컨테이너의 쓰기 층이고 fsync 는 켠 채다.

실행(저장소 루트에서. 벡터 색인을 병렬로 지으려면 공유 메모리가 넉넉해야 한다):
    docker run -d --rm --name rag-probe-sync-pg -p 127.0.0.1:55441:5432 \
        -e POSTGRES_PASSWORD=probe --shm-size=1g pgvector/pgvector:0.8.7-pg18-trixie
    uv run --with "psycopg[binary]==3.3.8" python -I -X utf8 \
        .scratch/source-sync/probes/source-delete/probe.py \
        postgresql://postgres:probe@127.0.0.1:55441/postgres 10000 10 500
인자는 주소, 문서 수, 문서마다의 조각 수, 묶음의 문서 수다. 출력은 `probe_out.txt` 다. 스키마
`probe_source_delete` 를 만들고 끝에 지운다.
"""

from __future__ import annotations

import statistics
import sys
import time
import uuid
from datetime import UTC, datetime

import psycopg

DSN = sys.argv[1]
DOCUMENTS = int(sys.argv[2])
CHUNKS_PER_DOCUMENT = int(sys.argv[3])
BATCH = int(sys.argv[4])
SCHEMA = "probe_source_delete"
OTHER_DOCUMENTS = 200
DIMENSIONS = 1024
BLOCK_TIMEOUT_MS = 1500
VERSION = uuid.uuid4()
GROUP = uuid.uuid4()
TARGET = uuid.uuid4()
OTHER = uuid.uuid4()
COLUMNS = (
    "id, document_id, index_version_id, ordinal, text, token_count, location, embedding,"
    " keywords, source_content_hash, group_id, updated_at, effective_date, access_groups"
)
PREFIXED = ", ".join(f"c.{name.strip()}" for name in COLUMNS.split(","))


def connect() -> psycopg.Connection:
    return psycopg.connect(DSN, autocommit=True, options=f"-c search_path={SCHEMA},public")


def timed(
    c: psycopg.Connection, label: str, statement: str, parameters: tuple[object, ...]
) -> float:
    started = time.monotonic()
    affected = c.execute(statement, parameters).rowcount
    elapsed = time.monotonic() - started
    print(f"    {label}: {elapsed:.2f}초({affected}행)")
    return elapsed


def blocked(label: str, statement: str, parameters: tuple[object, ...]) -> None:
    with connect() as c:
        c.execute(f"SET statement_timeout = {BLOCK_TIMEOUT_MS}")
        started = time.monotonic()
        try:
            c.execute(statement, parameters)
        except psycopg.errors.QueryCanceled:
            print(f"    {label}: 막혔다({time.monotonic() - started:.2f}초 뒤에 거뒀다)")
        else:
            print(f"    {label}: 막히지 않았다({time.monotonic() - started:.2f}초)")


def fill(c: psycopg.Connection, source_id: uuid.UUID, documents: int) -> None:
    c.execute(
        "INSERT INTO documents (id, source_id, key, content_hash, generation, modified_at)"
        " SELECT gen_random_uuid(), %s, 'doc-' || i, md5(i::text), 1, now()"
        " FROM generate_series(1, %s) i",
        (source_id, documents),
    )
    c.execute(
        "INSERT INTO document_index_states (document_id, index_version_id, status, chunk_count)"
        " SELECT id, %s, 'indexed', %s FROM documents WHERE source_id = %s",
        (VERSION, CHUNKS_PER_DOCUMENT, source_id),
    )
    c.execute(
        f"INSERT INTO chunks ({COLUMNS})"
        " SELECT gen_random_uuid(), d.id, %s, o, t.text, 300, '{\"page\": 1}'::jsonb, t.embedding,"
        " to_tsvector('simple', t.text), d.content_hash, %s, now(), NULL, '{}'"
        " FROM documents d CROSS JOIN generate_series(1, %s) o CROSS JOIN LATERAL ("
        "   SELECT (SELECT string_agg(md5(random()::text), ' ') FROM generate_series(1, 40)"
        "           WHERE d.id IS NOT NULL AND o IS NOT NULL) AS text,"
        "          (SELECT array_agg(random())::vector FROM generate_series(1, %s)"
        "           WHERE d.id IS NOT NULL AND o IS NOT NULL) AS embedding) t"
        " WHERE d.source_id = %s",
        (VERSION, GROUP, CHUNKS_PER_DOCUMENT, DIMENSIONS, source_id),
    )


def setup() -> None:
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        c.execute(f"CREATE SCHEMA {SCHEMA}")
        print("server:", c.execute("SHOW server_version").fetchone())
        extension = c.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        print("pgvector:", extension.fetchone())
    with connect() as c:
        c.execute(
            "CREATE TABLE sources (id uuid PRIMARY KEY, name text NOT NULL UNIQUE,"
            " deleted_at timestamptz)"
        )
        c.execute(
            "CREATE TABLE documents (id uuid PRIMARY KEY,"
            " source_id uuid NOT NULL REFERENCES sources (id), key text NOT NULL,"
            " content_hash text NOT NULL, generation bigint NOT NULL, deleted_at timestamptz,"
            " deleted_with_source boolean NOT NULL DEFAULT false,"
            " modified_at timestamptz NOT NULL, UNIQUE (source_id, key))"
        )
        c.execute(
            "CREATE TABLE document_index_states ("
            " document_id uuid NOT NULL REFERENCES documents (id), index_version_id uuid NOT NULL,"
            " status text NOT NULL, chunk_count integer NOT NULL,"
            " PRIMARY KEY (document_id, index_version_id))"
        )
        c.execute(
            "CREATE TABLE chunks (id uuid PRIMARY KEY,"
            " document_id uuid NOT NULL REFERENCES documents (id), index_version_id uuid NOT NULL,"
            " ordinal integer NOT NULL, text text NOT NULL, token_count integer NOT NULL,"
            " location jsonb NOT NULL, embedding vector NOT NULL, keywords tsvector NOT NULL,"
            " source_content_hash text NOT NULL, group_id uuid NOT NULL,"
            " updated_at timestamptz NOT NULL, effective_date date,"
            " access_groups text[] NOT NULL DEFAULT '{}',"
            " UNIQUE (index_version_id, document_id, ordinal))"
        )
        c.execute("CREATE TABLE archived_chunks (LIKE chunks INCLUDING DEFAULTS)")
        c.execute(
            "ALTER TABLE archived_chunks ADD COLUMN archived_at timestamptz NOT NULL,"
            " ADD PRIMARY KEY (id), ADD FOREIGN KEY (document_id) REFERENCES documents (id)"
        )
        c.execute("CREATE INDEX ix_archived_chunks_document_id ON archived_chunks (document_id)")
        c.execute(
            "INSERT INTO sources (id, name) VALUES (%s, 'target'), (%s, 'other')", (TARGET, OTHER)
        )
        started = time.monotonic()
        fill(c, TARGET, DOCUMENTS)
        fill(c, OTHER, OTHER_DOCUMENTS)
        print(
            f"준비: 문서 {DOCUMENTS}건과 조각 {DOCUMENTS * CHUNKS_PER_DOCUMENT}개(다른 원천에 문서"
            f" {OTHER_DOCUMENTS}건)를 {time.monotonic() - started:.1f}초에 넣었다"
        )
        c.execute("CREATE INDEX ix_chunks_document_id ON chunks (document_id)")
        c.execute("CREATE INDEX ix_chunks_keywords ON chunks USING gin (keywords)")
        c.execute("SET maintenance_work_mem = '900MB'")
        c.execute("SET max_parallel_maintenance_workers = 4")
        started = time.monotonic()
        c.execute(
            f"CREATE INDEX ix_chunks_hnsw ON chunks USING hnsw"
            f" ((embedding::vector({DIMENSIONS})) vector_cosine_ops)"
            f" WHERE index_version_id = '{VERSION}'"
        )
        print(f"준비: HNSW 색인을 {time.monotonic() - started:.1f}초에 지었다")
        c.execute("VACUUM ANALYZE")
        sizes = c.execute(
            "SELECT pg_size_pretty(pg_relation_size('chunks')),"
            " pg_size_pretty(pg_total_relation_size('chunks'))"
        ).fetchone()
        print("준비: 조각 표의 크기(행만 / 색인과 TOAST 포함):", sizes)


def counts(c: psycopg.Connection, label: str) -> None:
    row = c.execute(
        "SELECT (SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id"
        "         WHERE d.source_id = %s),"
        " (SELECT count(*) FROM archived_chunks c JOIN documents d ON d.id = c.document_id"
        "   WHERE d.source_id = %s),"
        " (SELECT count(*) FROM documents WHERE source_id = %s AND deleted_at IS NULL),"
        " (SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id"
        "   WHERE d.source_id = %s)",
        (TARGET, TARGET, TARGET, OTHER),
    ).fetchone()
    print(f"    {label}: (조각, 보관 조각, 살아 있는 문서, 다른 원천의 조각) = {row}")


def delete_at_once(c: psycopg.Connection) -> None:
    print("A. 한 트랜잭션에서 원천의 문서를 모두 임시 삭제")
    now = datetime.now(UTC)
    live = "d.source_id = %s AND d.deleted_at IS NULL"
    other_document = c.execute(
        "SELECT id FROM documents WHERE source_id = %s LIMIT 1", (OTHER,)
    ).fetchone()
    target_document = c.execute(
        "SELECT id FROM documents WHERE source_id = %s LIMIT 1", (TARGET,)
    ).fetchone()
    if other_document is None or target_document is None:
        raise RuntimeError("문서가 없다")
    started = time.monotonic()
    with c.transaction():
        timed(
            c,
            "원천 행에 지운 시각",
            "UPDATE sources SET deleted_at = %s WHERE id = %s",
            (now, TARGET),
        )
        timed(
            c,
            "조각을 삭제 보관함으로 복사",
            f"INSERT INTO archived_chunks ({COLUMNS}, archived_at) SELECT {PREFIXED}, %s"
            f" FROM chunks c JOIN documents d ON d.id = c.document_id WHERE {live}",
            (now, TARGET),
        )
        timed(
            c,
            "조각 지우기",
            f"DELETE FROM chunks c USING documents d WHERE d.id = c.document_id AND {live}",
            (TARGET,),
        )
        timed(
            c,
            "색인 상태 지우기",
            "DELETE FROM document_index_states s USING documents d"
            f" WHERE d.id = s.document_id AND {live}",
            (TARGET,),
        )
        timed(
            c,
            "문서 행의 세대와 지운 시각",
            "UPDATE documents SET deleted_at = %s, generation = generation + 1,"
            " deleted_with_source = true, modified_at = %s"
            " WHERE source_id = %s AND deleted_at IS NULL",
            (now, now, TARGET),
        )
        print(
            f"    커밋 전까지 {time.monotonic() - started:.2f}초. 트랜잭션을 연 채로 다른 연결에서:"
        )
        blocked(
            "다른 원천의 조각 읽기",
            "SELECT count(*) FROM chunks WHERE document_id = %s",
            (other_document[0],),
        )
        blocked(
            "다른 원천의 문서에 조각 쓰기",
            f"INSERT INTO chunks ({COLUMNS}) SELECT gen_random_uuid(), document_id,"
            " index_version_id, 9000 + (random() * 100000)::integer, text, token_count, location,"
            " embedding, keywords, source_content_hash, group_id, updated_at, effective_date,"
            " access_groups FROM chunks WHERE document_id = %s LIMIT 1",
            (other_document[0],),
        )
        blocked(
            "지우는 원천의 조각 읽기(커밋 전이라 아직 보인다)",
            "SELECT count(*) FROM chunks WHERE document_id = %s",
            (target_document[0],),
        )
        blocked(
            "지우는 원천의 문서 행 잠그기(색인 작업과 수집이 하는 일)",
            "SELECT id FROM documents WHERE id = %s FOR UPDATE",
            (target_document[0],),
        )
        committing = time.monotonic()
    print(f"    커밋 {time.monotonic() - committing:.2f}초")
    counts(c, "지운 뒤")


def delete_in_batches(c: psycopg.Connection) -> None:
    print(f"B. 문서 {BATCH}건씩 묶어 임시 삭제(묶음마다 커밋)")
    now = datetime.now(UTC)
    samples: list[float] = []
    started = time.monotonic()
    while True:
        batch_started = time.monotonic()
        with c.transaction():
            ids = [
                row[0]
                for row in c.execute(
                    "SELECT id FROM documents WHERE source_id = %s AND deleted_at IS NULL"
                    " ORDER BY id LIMIT %s FOR UPDATE",
                    (TARGET, BATCH),
                )
            ]
            if not ids:
                break
            c.execute(
                f"INSERT INTO archived_chunks ({COLUMNS}, archived_at) SELECT {PREFIXED}, %s"
                " FROM chunks c WHERE c.document_id = ANY(%s)",
                (now, ids),
            )
            c.execute("DELETE FROM chunks WHERE document_id = ANY(%s)", (ids,))
            c.execute("DELETE FROM document_index_states WHERE document_id = ANY(%s)", (ids,))
            c.execute(
                "UPDATE documents SET deleted_at = %s, generation = generation + 1,"
                " deleted_with_source = true, modified_at = %s WHERE id = ANY(%s)",
                (now, now, ids),
            )
        samples.append(time.monotonic() - batch_started)
    report(started, samples)
    counts(c, "지운 뒤")


def restore_at_once(c: psycopg.Connection) -> None:
    print("C. 한 트랜잭션에서 원천의 문서를 모두 되살리기")
    now = datetime.now(UTC)
    gone = "d.source_id = %s AND d.deleted_with_source"
    started = time.monotonic()
    with c.transaction():
        timed(
            c,
            "원천 행의 지운 시각 비우기",
            "UPDATE sources SET deleted_at = NULL WHERE id = %s",
            (TARGET,),
        )
        timed(
            c,
            "보관 조각을 조각 표로 복사",
            f"INSERT INTO chunks ({COLUMNS}) SELECT {PREFIXED} FROM archived_chunks c"
            f" JOIN documents d ON d.id = c.document_id WHERE {gone}"
            " AND c.source_content_hash = d.content_hash",
            (TARGET,),
        )
        timed(
            c,
            "보관 조각 지우기",
            "DELETE FROM archived_chunks c USING documents d"
            f" WHERE d.id = c.document_id AND {gone}",
            (TARGET,),
        )
        timed(
            c,
            "색인 상태 다시 쓰기",
            "INSERT INTO document_index_states (document_id, index_version_id, status, chunk_count)"
            f" SELECT d.id, %s, 'indexed', %s FROM documents d WHERE {gone}",
            (VERSION, CHUNKS_PER_DOCUMENT, TARGET),
        )
        timed(
            c,
            "문서 행의 세대와 지운 시각",
            "UPDATE documents SET deleted_at = NULL, generation = generation + 1,"
            " deleted_with_source = false, modified_at = %s"
            " WHERE source_id = %s AND deleted_with_source",
            (now, TARGET),
        )
        print(f"    커밋 전까지 {time.monotonic() - started:.2f}초")
    counts(c, "되살린 뒤")


def restore_in_batches(c: psycopg.Connection) -> None:
    print(f"D. 문서 {BATCH}건씩 묶어 되살리기(묶음마다 커밋)")
    now = datetime.now(UTC)
    samples: list[float] = []
    started = time.monotonic()
    while True:
        batch_started = time.monotonic()
        with c.transaction():
            ids = [
                row[0]
                for row in c.execute(
                    "SELECT id FROM documents WHERE source_id = %s AND deleted_with_source"
                    " ORDER BY id LIMIT %s FOR UPDATE",
                    (TARGET, BATCH),
                )
            ]
            if not ids:
                break
            c.execute(
                f"INSERT INTO chunks ({COLUMNS}) SELECT {COLUMNS} FROM archived_chunks"
                " WHERE document_id = ANY(%s)",
                (ids,),
            )
            c.execute("DELETE FROM archived_chunks WHERE document_id = ANY(%s)", (ids,))
            c.execute(
                "INSERT INTO document_index_states"
                " (document_id, index_version_id, status, chunk_count)"
                " SELECT id, %s, 'indexed', %s FROM documents WHERE id = ANY(%s)",
                (VERSION, CHUNKS_PER_DOCUMENT, ids),
            )
            c.execute(
                "UPDATE documents SET deleted_at = NULL, generation = generation + 1,"
                " deleted_with_source = false, modified_at = %s WHERE id = ANY(%s)",
                (now, ids),
            )
        samples.append(time.monotonic() - batch_started)
    report(started, samples)
    counts(c, "되살린 뒤")


def report(started: float, samples: list[float]) -> None:
    print(
        f"    전체 {time.monotonic() - started:.2f}초, 묶음 {len(samples)}개,"
        f" 묶음 하나의 가운데값 {statistics.median(samples):.2f}초,"
        f" 가장 긴 묶음 {max(samples):.2f}초"
    )


def main() -> None:
    setup()
    with connect() as c:
        counts(c, "처음")
        delete_at_once(c)
        restore_at_once(c)
        c.execute("VACUUM ANALYZE")
        delete_in_batches(c)
        restore_in_batches(c)
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(f"DROP SCHEMA {SCHEMA} CASCADE")


if __name__ == "__main__":
    main()
