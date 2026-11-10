"""alembic 환경. 비동기 엔진으로 마이그레이션을 돈다(ADR 0011).

접속 주소는 `Config.attributes["url"]`로 받는다(`migrate.upgrade_to_head`가 둔다). ini 파일의 값을
쓰지 않는 까닭은 비밀번호의 `%`가 설정 보간에 걸리기 때문이다. 오프라인(SQL만 내는) 모드는 쓰지
않는다.

엔진은 `hide_parameters=True`로 만든다. 마이그레이션이 바인딩 값을 싣는 일은 없지만 이 저장소의 모든
엔진이 같은 규칙을 따른다(ADR 0011).
"""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from rag_engine.adapters.postgres.tables import metadata


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await engine.dispose()


def _run_online() -> None:
    url: object = context.config.attributes.get("url")
    if not isinstance(url, str):
        raise RuntimeError("접속 주소가 없다. `migrate.upgrade_to_head`로 돌린다")
    # psycopg 비동기는 Windows의 기본 ProactorEventLoop과 맞지 않아 Selector 루프를 쓴다(ADR 0011).
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(_run_async_migrations(url))


if context.is_offline_mode():
    raise RuntimeError("오프라인 모드는 쓰지 않는다")
_run_online()
