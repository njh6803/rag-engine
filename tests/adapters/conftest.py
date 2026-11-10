"""어댑터 시험의 픽스처. 시험마다 빈 데이터베이스를 하나 만들고 끝나면 지운다.

테스트 서버 하나를 워크트리와 세션이 함께 쓰므로(core 01) 이름에 무작위 토막을 붙인다. 템플릿
데이터베이스로 복제하는 세션 픽스처는 core 03이 만든다.
"""

from collections.abc import Iterator
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql


def _replace_database(url: str, name: str) -> str:
    return urlsplit(url)._replace(path=f"/{name}").geturl()


@pytest.fixture
def empty_database_url(database_url: str) -> Iterator[str]:
    name = f"rag_empty_{uuid4().hex}"
    with psycopg.connect(database_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield _replace_database(database_url, name)
    finally:
        with psycopg.connect(database_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
