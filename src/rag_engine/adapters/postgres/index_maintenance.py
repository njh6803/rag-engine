"""`IndexMaintenance` 어댑터. 물러난 판의 정리를 작업 단위 밖에서 한다(명세 "데이터 모델과 스키마",
"수집 파이프라인과 작업"의 판 전환 항목).

색인은 자동 커밋 연결에서 `DROP INDEX CONCURRENTLY IF EXISTS`로 지운다. 이 문장은 트랜잭션 안에서
부를 수 없고(`25001`), 일반 `DROP INDEX`와 달리 줄을 서도 그 뒤에 온 `SELECT`를 막지 않는다. 조각은
묶음마다 별도 트랜잭션에서 지운다. 묶음은 `FOR UPDATE SKIP LOCKED`로 고르므로 정리를 겹쳐 돌려도
서로 기다리지 않는다. 지울 색인의 이름은 UUID에서 지은 것이고 묶음 크기는 바인딩하므로 SQL 문자열에
바깥 글이 끼지 않는다.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from rag_engine.adapters.postgres import tables
from rag_engine.adapters.postgres.catalog import index_version_of
from rag_engine.adapters.postgres.error_translation import translate
from rag_engine.adapters.postgres.vector_index import version_index_name
from rag_engine.domain.entities import IndexVersion, IndexVersionStatus


class PostgresIndexMaintenance:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def list_versions_to_clean(
        self, knowledge_base_id: UUID | None = None
    ) -> list[IndexVersion]:
        versions = tables.index_versions
        retired = sa.select(versions).where(versions.c.status == IndexVersionStatus.RETIRED.value)
        if knowledge_base_id is not None:
            retired = retired.where(versions.c.knowledge_base_id == knowledge_base_id)
        found: list[IndexVersion] = []
        async with self._translated(), self._engine.connect() as connection:
            for row in (await connection.execute(retired.order_by(versions.c.id))).mappings():
                version = index_version_of(row)
                if await self._has_leftover(connection, version):
                    found.append(version)
        return found

    async def drop_version_index(self, index_version_id: UUID) -> None:
        async with self._translated(), self._engine.connect() as connection:
            autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
            name = version_index_name(index_version_id)
            await autocommit.execute(sa.text(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"'))

    async def delete_version_chunks(self, index_version_id: UUID, limit: int) -> int:
        chunks = tables.chunks
        batch = (
            sa.select(chunks.c.id)
            .where(chunks.c.index_version_id == index_version_id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        async with self._translated(), self._engine.begin() as connection:
            result = await connection.execute(sa.delete(chunks).where(chunks.c.id.in_(batch)))
            return result.rowcount

    @staticmethod
    async def _has_leftover(connection: AsyncConnection, version: IndexVersion) -> bool:
        chunks = tables.chunks
        has_chunks = sa.select(chunks.c.id).where(chunks.c.index_version_id == version.id).exists()
        if await connection.scalar(sa.select(has_chunks)):
            return True
        return bool(
            await connection.scalar(
                sa.select(sa.func.to_regclass(version_index_name(version.id)).is_not(None))
            )
        )

    @staticmethod
    @asynccontextmanager
    async def _translated() -> AsyncGenerator[None]:
        """데이터베이스의 일시 오류를 일시 실패 `database_unavailable`로 바꿔 올린다."""
        try:
            yield
        except DBAPIError as error:
            transient = translate(error)
            if transient is None:
                raise
            raise transient from None
