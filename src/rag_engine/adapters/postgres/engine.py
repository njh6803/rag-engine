"""SQLAlchemy 비동기 엔진과 그것을 돌리는 이벤트 루프(ADR 0011).

엔진은 `hide_parameters=True`로 만든다. SQLAlchemy의 `StatementError`는 메시지에 SQL과 바인딩 값을
붙이고 그 값에는 조각 본문과 검색 질의가 들어서다(ADR 0015, 원칙 V).

psycopg 비동기는 Windows의 기본 ProactorEventLoop과 맞지 않아 Selector 루프를 쓴다.
"""

import asyncio
from collections.abc import Coroutine
from typing import Final

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rag_engine.adapters.postgres.migrate import async_database_url

# SQLAlchemy의 기본 풀 크기와 넘침 허용(합쳐 15). 기본 동작을 바꾸지 않으려고 값을 적어 둔다.
_POOL_SIZE: Final = 5
_MAX_OVERFLOW: Final = 10


def create_engine(database_url: str, *, at_least_connections: int = 0) -> AsyncEngine:
    """동시에 쥘 수 있는 연결의 상한은 기본 15이고, `at_least_connections`가 그보다 크면 그 값까지
    넓힌다. 동시 처리하는 작업자가 슬롯마다 연결을 둘까지 쥐는 것을 풀이 받쳐야 한다."""
    return create_async_engine(
        async_database_url(database_url),
        hide_parameters=True,
        pool_size=_POOL_SIZE,
        max_overflow=max(_MAX_OVERFLOW, at_least_connections - _POOL_SIZE),
    )


def run_in_selector_loop[T](coroutine: Coroutine[object, object, T]) -> T:
    """동기 코드(관리 명령, 세션 픽스처)에서 코루틴 하나를 Selector 이벤트 루프로 돌려 결과를
    낸다."""
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(coroutine)
