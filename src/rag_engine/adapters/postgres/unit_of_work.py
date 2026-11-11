"""PostgreSQL 작업 단위(명세 "포트 열셋과 그 값").

`begin()`이 연결 하나와 트랜잭션을 열고, 그 안에서 얻는 어댑터 넷(`catalog`, `documents`, `index`,
`jobs`)이 그 연결을 공유한다. 블록을 예외 없이 나가면 커밋이고 예외로 나가면 롤백이다. 명시적
`commit()`은 없다.

연결을 여는 일부터 커밋까지 올라오는 데이터베이스의 일시 오류는 일시 실패 `database_unavailable`로
바꿔 올린다(`error_translation`). 나머지 드라이버 오류는 그대로 올라간다.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from rag_engine.adapters.postgres.catalog import PostgresCatalog
from rag_engine.adapters.postgres.document_store import PostgresDocumentStore
from rag_engine.adapters.postgres.error_translation import translate
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
        try:
            async with self._engine.connect() as connection, connection.begin():
                yield PostgresTransaction(connection)
        except DBAPIError as error:
            transient = translate(error)
            if transient is None:
                raise
            raise transient from None
