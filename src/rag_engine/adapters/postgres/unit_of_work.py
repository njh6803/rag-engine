"""PostgreSQL 작업 단위(명세 "포트 열셋과 그 값").

`begin()`이 연결 하나와 트랜잭션을 열고, 그 안에서 얻는 어댑터들이 그 연결을 공유한다. 블록을 예외
없이 나가면 커밋이고 예외로 나가면 롤백이다. 명시적 `commit()`은 없다.

`documents`와 `jobs`의 어댑터는 아직 없어 그 속성은 `NotImplementedError`를 올린다.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from rag_engine.adapters.postgres.catalog import PostgresCatalog
from rag_engine.adapters.postgres.vector_index import PostgresVectorIndex
from rag_engine.domain.ports import DocumentStore, JobQueue


class PostgresTransaction:
    def __init__(self, connection: AsyncConnection) -> None:
        self.catalog = PostgresCatalog(connection)
        self.index = PostgresVectorIndex(connection)

    @property
    def documents(self) -> DocumentStore:
        raise NotImplementedError("이 어댑터에 아직 없다")

    @property
    def jobs(self) -> JobQueue:
        raise NotImplementedError("이 어댑터에 아직 없다")


class PostgresUnitOfWork:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[PostgresTransaction]:
        async with self._engine.connect() as connection, connection.begin():
            yield PostgresTransaction(connection)
