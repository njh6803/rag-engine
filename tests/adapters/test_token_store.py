"""PostgreSQL `TokenStore` 어댑터(명세 "포트 열셋과 그 값", "데이터 모델과 스키마").

토큰 표는 작업 단위 밖에서 다룬다. 한 호출이 연결 하나를 열어 커밋까지 끝낸다.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.token_store import PostgresTokenStore
from rag_engine.app.tokens import hash_token
from rag_engine.domain.entities import Token, TokenRole
from rag_engine.domain.identifiers import new_id

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


@pytest.fixture
async def store(seeded_database_url: str) -> AsyncIterator[PostgresTokenStore]:
    engine = create_engine(seeded_database_url)
    try:
        yield PostgresTokenStore(engine)
    finally:
        await engine.dispose()


def _token(
    name: str = "토큰",
    *,
    role: TokenRole = TokenRole.ADMIN,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> Token:
    return Token(
        id=new_id(),
        name=name,
        token_hash=hash_token(f"rag_{name}-{new_id()}"),
        role=role,
        knowledge_base_ids=(),
        expires_at=expires_at,
        revoked_at=revoked_at,
        created_at=NOW,
    )


async def test_넣은_토큰을_해시로_찾으면_같은_값이_나온다(store: PostgresTokenStore) -> None:
    scoped = Token(
        id=new_id(),
        name="범위가 있는 토큰",
        token_hash=hash_token("rag_scoped"),
        role=TokenRole.READER,
        knowledge_base_ids=(new_id(), new_id()),
        expires_at=NOW + timedelta(days=1),
        revoked_at=None,
        created_at=NOW,
    )

    await store.add(scoped)

    assert await store.get_by_hash(scoped.token_hash) == scoped


async def test_모르는_해시는_None이다(store: PostgresTokenStore) -> None:
    assert await store.get_by_hash(hash_token("rag_없는_토큰")) is None


async def test_id로_토큰을_찾는다(store: PostgresTokenStore) -> None:
    token = _token()
    await store.add(token)

    assert await store.get(token.id) == token
    assert await store.get(new_id()) is None


async def test_목록은_만든_순서이고_회수된_토큰도_든다(store: PostgresTokenStore) -> None:
    first, second = _token("첫째"), _token("둘째")
    await store.add(first)
    await store.add(second)
    await store.revoke(first.id, NOW + timedelta(minutes=1))

    listed = await store.list_tokens()

    assert [(token.name, token.revoked_at) for token in listed] == [
        ("첫째", NOW + timedelta(minutes=1)),
        ("둘째", None),
    ]


async def test_회수는_처음_시각을_남기고_다시_회수해도_바뀌지_않는다(
    store: PostgresTokenStore,
) -> None:
    token = _token()
    await store.add(token)

    await store.revoke(token.id, NOW + timedelta(minutes=1))
    await store.revoke(token.id, NOW + timedelta(minutes=2))

    reloaded = await store.get(token.id)
    assert reloaded is not None
    assert reloaded.revoked_at == NOW + timedelta(minutes=1)


async def test_살아_있는_admin_토큰이_있는지_본다(store: PostgresTokenStore) -> None:
    assert await store.has_live_admin(NOW) is False

    await store.add(_token("읽기", role=TokenRole.READER))
    assert await store.has_live_admin(NOW) is False

    await store.add(_token("회수됨", revoked_at=NOW - timedelta(hours=1)))
    await store.add(_token("만료됨", expires_at=NOW - timedelta(seconds=1)))
    assert await store.has_live_admin(NOW) is False

    await store.add(_token("살아 있음", expires_at=NOW + timedelta(seconds=1)))
    assert await store.has_live_admin(NOW) is True


async def test_만료_시각이_없는_admin_토큰은_살아_있다(store: PostgresTokenStore) -> None:
    await store.add(_token())

    assert await store.has_live_admin(NOW) is True
