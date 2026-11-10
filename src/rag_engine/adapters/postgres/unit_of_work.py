"""PostgreSQL 작업 단위(명세 "포트 열셋과 그 값").

`begin()`이 연결 하나와 트랜잭션을 열고, 그 안에서 얻는 어댑터 넷(`catalog`, `documents`, `index`,
`jobs`)이 그 연결을 공유한다. 블록을 예외 없이 나가면 커밋이고 예외로 나가면 롤백이다. 명시적
`commit()`은 없다.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from rag_engine.adapters.postgres.catalog import PostgresCatalog
from rag_engine.adapters.postgres.document_store import PostgresDocumentStore
from rag_engine.adapters.postgres.job_queue import PostgresJobQueue
from rag_engine.adapters.postgres.vector_index import PostgresVectorIndex


class PostgresTransaction:
    def __init__(self, connection: AsyncConnection) -> None:
        self.catalog = PostgresCatalog(connection)
        self.documents = PostgresDocumentStore(connection)
        self.index = PostgresVectorIndex(connection)
        self.jobs = PostgresJobQueue(connection)


class PostgresUnitOfWork:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[PostgresTransaction]:
        async with self._engine.connect() as connection, connection.begin():
            yield PostgresTransaction(connection)
