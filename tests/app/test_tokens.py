"""토큰 유스케이스(명세 "인증과 권한"). 저장은 실제 테스트 PostgreSQL의 `TokenStore`다."""

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.token_store import PostgresTokenStore
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.tokens import (
    TOKEN_PREFIX,
    IssuedToken,
    authenticate,
    bootstrap_admin_token,
    hash_token,
    issue_token,
    list_tokens,
    new_token_text,
    revoke_token,
)
from rag_engine.domain.entities import TokenRole
from rag_engine.domain.errors import ErrorCode, InvalidInput, RequestError
from rag_engine.domain.identifiers import new_id

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


@pytest.fixture
async def store_and_unit_of_work(
    seeded_database_url: str,
) -> AsyncIterator[tuple[PostgresTokenStore, PostgresUnitOfWork]]:
    engine = create_engine(seeded_database_url)
    try:
        yield PostgresTokenStore(engine), PostgresUnitOfWork(engine)
    finally:
        await engine.dispose()


async def _issue(
    pair: tuple[PostgresTokenStore, PostgresUnitOfWork],
    *,
    role: TokenRole = TokenRole.ADMIN,
    knowledge_bases: tuple[str, ...] = (),
    expires_at: datetime | None = None,
) -> IssuedToken:
    store, unit_of_work = pair
    return await issue_token(
        store,
        unit_of_work,
        name="시험 토큰",
        role=role,
        knowledge_base_names=knowledge_bases,
        expires_at=expires_at,
        now=NOW,
    )


def test_토큰_원문은_rag_접두와_32바이트_난수의_URL_안전_base64다() -> None:
    text = new_token_text()

    assert TOKEN_PREFIX == "rag_"
    assert re.fullmatch(r"rag_[A-Za-z0-9_-]{43}", text)
    assert new_token_text() != text


def test_해시는_sha256_16진_64자이고_같은_원문은_같은_해시다() -> None:
    text = new_token_text()

    assert hash_token(text) == hash_token(text)
    assert re.fullmatch(r"[0-9a-f]{64}", hash_token(text))
    # 표준 시험 벡터(FIPS 180-2의 "abc")라, 해시 함수를 바꾸면 저장된 해시가 모두 어긋난다.
    assert hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


async def test_발급한_토큰은_원문과_해시로_저장되고_원문은_저장하지_않는다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, _ = store_and_unit_of_work

    issued = await _issue(store_and_unit_of_work)

    stored = await store.get_by_hash(hash_token(issued.raw))
    assert stored == issued.token
    assert issued.raw not in repr(stored)


async def test_지식베이스_이름의_범위는_id로_바뀌어_저장된다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    _, unit_of_work = store_and_unit_of_work
    async with unit_of_work.begin() as transaction:
        default = await transaction.catalog.get_knowledge_base("default")
    assert default is not None

    issued = await _issue(
        store_and_unit_of_work, role=TokenRole.READER, knowledge_bases=("default", "default")
    )

    assert issued.token.knowledge_base_ids == (default.id,)


async def test_admin_토큰에_범위를_주면_거부한다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    with pytest.raises(InvalidInput) as caught:
        await _issue(store_and_unit_of_work, knowledge_bases=("default",))

    assert caught.value.code is ErrorCode.VALIDATION_ERROR
    assert caught.value.loc == ("knowledge_bases",)


async def test_이미_지난_만료_시각은_거부한다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    with pytest.raises(InvalidInput) as caught:
        await _issue(store_and_unit_of_work, expires_at=NOW)

    assert caught.value.loc == ("expires_at",)


async def test_없는_지식베이스를_범위로_주면_지식베이스_없음이다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    with pytest.raises(RequestError) as caught:
        await _issue(store_and_unit_of_work, role=TokenRole.READER, knowledge_bases=("없음",))

    assert caught.value.code is ErrorCode.KNOWLEDGE_BASE_NOT_FOUND


async def test_인증은_살아_있는_토큰의_레코드를_낸다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, _ = store_and_unit_of_work
    issued = await _issue(store_and_unit_of_work)

    assert await authenticate(store, issued.raw, NOW) == issued.token


@pytest.mark.parametrize("raw", [None, "", "rag_모르는_토큰"])
async def test_토큰이_없거나_모르는_것이면_인증되지_않은_것이다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork], raw: str | None
) -> None:
    store, _ = store_and_unit_of_work

    with pytest.raises(RequestError) as caught:
        await authenticate(store, raw, NOW)

    assert caught.value.code is ErrorCode.UNAUTHENTICATED


async def test_회수된_토큰은_회수_사실을_드러내지_않고_인증되지_않은_것이다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, _ = store_and_unit_of_work
    issued = await _issue(store_and_unit_of_work, expires_at=NOW + timedelta(days=1))
    await revoke_token(store, issued.token.id, NOW)

    with pytest.raises(RequestError) as caught:
        await authenticate(store, issued.raw, NOW)

    assert caught.value.code is ErrorCode.UNAUTHENTICATED


async def test_만료된_토큰은_만료로_거부하고_만료_시각_전에는_받는다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, _ = store_and_unit_of_work
    issued = await _issue(store_and_unit_of_work, expires_at=NOW + timedelta(seconds=1))

    assert await authenticate(store, issued.raw, NOW) == issued.token
    with pytest.raises(RequestError) as caught:
        await authenticate(store, issued.raw, NOW + timedelta(seconds=1))

    assert caught.value.code is ErrorCode.TOKEN_EXPIRED


async def test_없는_토큰을_회수하면_토큰_없음이다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, _ = store_and_unit_of_work

    with pytest.raises(RequestError) as caught:
        await revoke_token(store, new_id(), NOW)

    assert caught.value.code is ErrorCode.TOKEN_NOT_FOUND


async def test_목록의_범위는_지식베이스_이름으로_나온다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, unit_of_work = store_and_unit_of_work
    await _issue(store_and_unit_of_work, role=TokenRole.READER, knowledge_bases=("default",))
    await _issue(store_and_unit_of_work)

    views = await list_tokens(store, unit_of_work)

    assert [(view.token.role, view.knowledge_base_names) for view in views] == [
        (TokenRole.READER, ("default",)),
        (TokenRole.ADMIN, ()),
    ]


async def test_첫_관리_토큰은_살아_있는_admin_토큰이_없을_때만_발급한다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, _ = store_and_unit_of_work

    first = await bootstrap_admin_token(store, "bootstrap", NOW)
    second = await bootstrap_admin_token(store, "bootstrap", NOW)

    assert first is not None
    assert (first.token.role, first.token.name) == (TokenRole.ADMIN, "bootstrap")
    assert second is None


async def test_살아_있는_admin_토큰이_회수되면_다시_발급한다(
    store_and_unit_of_work: tuple[PostgresTokenStore, PostgresUnitOfWork],
) -> None:
    store, _ = store_and_unit_of_work
    first = await bootstrap_admin_token(store, "bootstrap", NOW)
    assert first is not None
    await revoke_token(store, first.token.id, NOW)

    assert await bootstrap_admin_token(store, "bootstrap", NOW) is not None
