"""SQLAlchemy 비동기 엔진과 그것을 돌리는 이벤트 루프(ADR 0011).

엔진은 `hide_parameters=True`로 만든다. SQLAlchemy의 `StatementError`는 메시지에 SQL과 바인딩 값을
붙이고 그 값에는 조각 본문과 검색 질의가 들어서다(ADR 0015, 원칙 V).

psycopg 비동기는 Windows의 기본 ProactorEventLoop과 맞지 않아 Selector 루프를 쓴다.
"""

import asyncio
from collections.abc import Coroutine

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rag_engine.adapters.postgres.migrate import async_database_url


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(async_database_url(database_url), hide_parameters=True)


def run_in_selector_loop[T](coroutine: Coroutine[object, object, T]) -> T:
    """동기 코드(관리 명령, 세션 픽스처)에서 코루틴 하나를 Selector 이벤트 루프로 돌려 결과를
    낸다."""
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(coroutine)
