"""작업 표의 `has_active_job` 질의가 0002의 부분 색인을 고르는지 EXPLAIN으로 본다.

임시 데이터베이스를 head까지 올려 같은 질의의 실행 계획을 0002 색인이 있을 때와 지운 뒤(0001만 있는
것과 같다)로 비교한다. `enable_seqscan = off`로 순차 읽기를 막아, 쓸 수 있는 색인이 있으면 그 색인이
계획에 드러나게 한다. 표가 비어 있어 행 수 추정은 의미가 없고 색인을 고르는지만 본다.

사용: `uv run python .scratch/core/probes/jobs_active_index_plan.py <관리자 접속 문자열>`
"""

import sys
from uuid import uuid4

import psycopg
from psycopg import sql

from rag_engine.adapters.postgres.migrate import upgrade_to_head

QUERY = "EXPLAIN SELECT id FROM jobs WHERE document_id = %s AND status IN ('queued', 'running')"


def plan(url: str) -> list[str]:
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute("SET enable_seqscan = off")
        rows = connection.execute(QUERY, [uuid4()]).fetchall()
    return [row[0] for row in rows]


def main(base_url: str) -> None:
    admin = psycopg.connect(base_url, autocommit=True)
    name = f"plan_probe_{uuid4().hex[:8]}"
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        url = base_url.rsplit("/", 1)[0] + "/" + name
        upgrade_to_head(url)
        print("head:")
        print("\n".join(plan(url)))
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute("DROP INDEX ix_jobs_document_id_active")
        print("0002 색인을 지운 뒤:")
        print("\n".join(plan(url)))
    finally:
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


main(sys.argv[1])
