"""pgvector의 `hnsw.ef_search`가 받는 범위를 잰다(core 07 `RAG_SEARCH_CANDIDATES`의 상한 근거).

확장을 로드하기 전의 연결에서는 `hnsw.` 변수가 자리표시자라 어떤 값이든 받는다. 벡터 연산을 한 번
쓴 뒤에야 범위를 검사한다. 두 경우를 값마다 찍는다. 확장 생성은 트랜잭션 안에서 하고 되돌려
데이터베이스에 남기지 않는다.

실행: RAG_TEST_DATABASE_URL=<테스트 PostgreSQL 주소> uv run python \
    .scratch/core/probes/vector-store/probe_ef_search_range.py
"""

import os

import psycopg

VALUES = ("0", "1", "40", "1000", "1001")


def try_set(connection: psycopg.Connection, value: str) -> str:
    connection.execute("SAVEPOINT s")
    try:
        connection.execute("SELECT set_config('hnsw.ef_search', %s, true)", (value,))
    except psycopg.Error as error:
        connection.execute("ROLLBACK TO SAVEPOINT s")
        return f"거부: {str(error).splitlines()[0]}"
    return "받음"


def main() -> None:
    with psycopg.connect(os.environ["RAG_TEST_DATABASE_URL"]) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        print("pgvector", version)
        print("[확장을 쓰기 전]")
        for value in VALUES:
            print(f"  {value}: {try_set(connection, value)}")
        connection.execute("SELECT '[1,2]'::vector")
        print("[벡터 연산을 쓴 뒤]")
        for value in VALUES:
            print(f"  {value}: {try_set(connection, value)}")
        connection.rollback()


main()
