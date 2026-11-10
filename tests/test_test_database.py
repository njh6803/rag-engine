"""테스트 데이터베이스가 core 시험이 기댈 만하게 서 있는지(core 01).

세션 픽스처 `database_url` 이 판정한다. 값이 없거나 서버가 답하지 않으면 skip 이 아니라 실패하고,
메시지가 띄우는 길을 알린다(원칙 I, `tests/conftest.py`).
"""

import psycopg


def test_테스트_서버에_vector_확장이_있고_역할이_데이터베이스를_만들_수_있다(
    database_url: str,
) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        extension = connection.execute(
            "SELECT default_version FROM pg_available_extensions WHERE name = 'vector'"
        ).fetchone()
        role = connection.execute(
            "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname = current_user"
        ).fetchone()

    assert extension is not None, "pgvector 이미지가 아니다"
    assert extension[0].startswith("0.8."), extension[0]
    assert role == (True,)
