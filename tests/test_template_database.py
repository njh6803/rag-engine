"""세션 픽스처가 템플릿 데이터베이스에 alembic 과 기본 레코드 보장을 한 번 돌리고, 시험마다 그
템플릿에서 복제한 데이터베이스를 준다(명세 "테스트 데이터베이스와 이미지 판")."""

from collections.abc import Callable

import psycopg


def test_복제한_데이터베이스에는_기본_레코드가_이미_들어_있다(seeded_database_url: str) -> None:
    with psycopg.connect(seeded_database_url, autocommit=True) as connection:
        knowledge_bases = connection.execute(
            "SELECT k.name, v.status FROM knowledge_bases k"
            " JOIN index_versions v ON v.id = k.current_index_version_id"
        ).fetchall()
        versions = connection.execute("SELECT count(*) FROM alembic_version").fetchall()

    assert knowledge_bases == [("default", "current")]
    assert versions == [(1,)]


def test_한_복제본에_쓴_행은_다른_복제본에_보이지_않는다(
    make_seeded_database: Callable[[], str],
) -> None:
    first, second = make_seeded_database(), make_seeded_database()

    with psycopg.connect(first, autocommit=True) as connection:
        connection.execute("INSERT INTO groups (id, name) VALUES (gen_random_uuid(), 'marker')")
    with psycopg.connect(second, autocommit=True) as connection:
        names = connection.execute("SELECT name FROM groups").fetchall()

    assert first != second
    assert names == [("default",)]
