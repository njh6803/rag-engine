"""인증 토큰 유스케이스(명세 "인증과 권한", ADR 0014).

원문은 `rag_` 접두와 32바이트 난수의 URL 안전 base64이고, 저장은 sha256 해시뿐이다. 원문은 발급
응답에 한 번만 나온다.
"""

import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from rag_engine.domain.entities import Token, TokenRole
from rag_engine.domain.errors import ErrorCode, InvalidInput, RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import TokenStore, UnitOfWork

TOKEN_PREFIX: Final = "rag_"
_RANDOM_BYTES: Final = 32


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """발급 결과. `raw`는 이 값 말고는 어디에도 남지 않는 토큰 원문이다."""

    token: Token
    raw: str


@dataclass(frozen=True, slots=True)
class TokenView:
    """목록에 낼 토큰. 지식베이스 범위는 id가 아니라 이름이다."""

    token: Token
    knowledge_base_names: tuple[str, ...]


def new_token_text() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(_RANDOM_BYTES)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _require_valid_scope_and_expiry(
    role: TokenRole,
    knowledge_base_names: Sequence[str],
    expires_at: datetime | None,
    now: datetime,
) -> None:
    if role is TokenRole.ADMIN and knowledge_base_names:
        raise InvalidInput(
            ("knowledge_bases",),
            "value_error",
            "admin 토큰에는 지식베이스 범위를 줄 수 없다",
        )
    if expires_at is not None and expires_at <= now:
        raise InvalidInput(("expires_at",), "value_error", "만료 시각이 이미 지났다")


async def _resolve_knowledge_base_ids(
    unit_of_work: UnitOfWork, names: Sequence[str]
) -> tuple[UUID, ...]:
    ids: list[UUID] = []
    async with unit_of_work.begin() as transaction:
        for name in dict.fromkeys(names):
            knowledge_base = await transaction.catalog.get_knowledge_base(name)
            if knowledge_base is None:
                raise RequestError(
                    ErrorCode.KNOWLEDGE_BASE_NOT_FOUND, "범위에 준 지식베이스가 없다"
                )
            ids.append(knowledge_base.id)
    return tuple(ids)


def _new_token(
    name: str,
    role: TokenRole,
    knowledge_base_ids: tuple[UUID, ...],
    expires_at: datetime | None,
    now: datetime,
) -> IssuedToken:
    """새 원문을 지어 해시만 든 토큰 레코드와 묶는다. 저장은 부르는 쪽이 한다."""
    raw = new_token_text()
    token = Token(
        id=new_id(),
        name=name,
        token_hash=hash_token(raw),
        role=role,
        knowledge_base_ids=knowledge_base_ids,
        expires_at=expires_at,
        revoked_at=None,
        created_at=now,
    )
    return IssuedToken(token=token, raw=raw)


async def issue_token(
    store: TokenStore,
    unit_of_work: UnitOfWork,
    *,
    name: str,
    role: TokenRole,
    knowledge_base_names: Sequence[str],
    expires_at: datetime | None,
    now: datetime,
) -> IssuedToken:
    _require_valid_scope_and_expiry(role, knowledge_base_names, expires_at, now)
    knowledge_base_ids = await _resolve_knowledge_base_ids(unit_of_work, knowledge_base_names)
    issued = _new_token(name, role, knowledge_base_ids, expires_at, now)
    await store.add(issued.token)
    return issued


async def authenticate(store: TokenStore, raw: str | None, now: datetime) -> Token:
    """토큰 원문으로 살아 있는 토큰 레코드를 찾는다. 없음·모름·회수는 `unauthenticated`(회수 사실을
    드러내지 않는다)이고 만료는 `token_expired`다."""
    token = await store.get_by_hash(hash_token(raw)) if raw else None
    if token is None or token.revoked_at is not None:
        raise RequestError(ErrorCode.UNAUTHENTICATED, "토큰이 없거나 맞지 않다")
    if token.expires_at is not None and token.expires_at <= now:
        raise RequestError(ErrorCode.TOKEN_EXPIRED, "토큰이 만료되었다")
    return token


async def list_tokens(store: TokenStore, unit_of_work: UnitOfWork) -> list[TokenView]:
    tokens = await store.list_tokens()
    async with unit_of_work.begin() as transaction:
        names_by_id = {kb.id: kb.name for kb in await transaction.catalog.list_knowledge_bases()}
    return [
        TokenView(
            token=token,
            knowledge_base_names=tuple(
                names_by_id[kb_id] for kb_id in token.knowledge_base_ids if kb_id in names_by_id
            ),
        )
        for token in tokens
    ]


async def revoke_token(store: TokenStore, token_id: UUID, now: datetime) -> None:
    if await store.get(token_id) is None:
        raise RequestError(ErrorCode.TOKEN_NOT_FOUND, "그 토큰이 없다")
    await store.revoke(token_id, now)


async def bootstrap_admin_token(store: TokenStore, name: str, now: datetime) -> IssuedToken | None:
    """살아 있는 `admin` 토큰이 하나도 없을 때만 발급한다. 있으면 `None`이다."""
    if await store.has_live_admin(now):
        return None
    issued = _new_token(name, TokenRole.ADMIN, (), None, now)
    await store.add(issued.token)
    return issued
