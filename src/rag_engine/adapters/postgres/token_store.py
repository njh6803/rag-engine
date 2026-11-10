"""`TokenStore` 어댑터(명세 "포트 열셋과 그 값"). 다른 표와 한 트랜잭션에 들 일이 없어 작업 단위
밖에서 부른다. 한 호출이 연결 하나를 열어 커밋까지 끝낸다."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from rag_engine.adapters.postgres import tables
from rag_engine.domain.entities import Token, TokenRole


def _token(row: sa.RowMapping) -> Token:
    return Token(
        id=row["id"],
        name=row["name"],
        token_hash=row["token_hash"],
        role=TokenRole(row["role"]),
        knowledge_base_ids=tuple(row["knowledge_base_ids"]),
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        created_at=row["created_at"],
    )


class PostgresTokenStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(self, token: Token) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sa.insert(tables.tokens).values(
                    id=token.id,
                    name=token.name,
                    token_hash=token.token_hash,
                    role=token.role.value,
                    knowledge_base_ids=list(token.knowledge_base_ids),
                    expires_at=token.expires_at,
                    revoked_at=token.revoked_at,
                    created_at=token.created_at,
                )
            )

    async def get(self, token_id: UUID) -> Token | None:
        return await self._get_where(tables.tokens.c.id == token_id)

    async def get_by_hash(self, token_hash: str) -> Token | None:
        return await self._get_where(tables.tokens.c.token_hash == token_hash)

    async def _get_where(self, condition: sa.ColumnElement[bool]) -> Token | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(sa.select(tables.tokens).where(condition))
            row = result.mappings().one_or_none()
        return None if row is None else _token(row)

    async def list_tokens(self) -> list[Token]:
        # UUIDv7은 시간순이라 id 순이 만든 순서다.
        async with self._engine.connect() as connection:
            result = await connection.execute(sa.select(tables.tokens).order_by(tables.tokens.c.id))
            return [_token(row) for row in result.mappings()]

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sa.update(tables.tokens)
                .where(tables.tokens.c.id == token_id, tables.tokens.c.revoked_at.is_(None))
                .values(revoked_at=revoked_at)
            )

    async def has_live_admin(self, now: datetime) -> bool:
        live_admin = (
            sa.select(sa.literal(1))
            .select_from(tables.tokens)
            .where(
                tables.tokens.c.role == TokenRole.ADMIN.value,
                tables.tokens.c.revoked_at.is_(None),
                sa.or_(tables.tokens.c.expires_at.is_(None), tables.tokens.c.expires_at > now),
            )
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(sa.select(sa.exists(live_admin)))
            return bool(result.scalar_one())
