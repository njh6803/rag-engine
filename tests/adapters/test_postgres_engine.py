"""엔진의 연결 풀 크기(티켓 13).

작업자는 슬롯마다 작업 단위와 임대 연장이 연결을 둘까지 동시에 쥔다. 동시 처리 수가 크면 기본 풀
상한(15)을 넘으므로 `at_least_connections`로 상한을 넓힐 수 있어야 한다.
"""

import asyncio
from contextlib import AsyncExitStack

from rag_engine.adapters.postgres.engine import create_engine

CONNECTIONS = 20


async def test_연결_상한을_넓히면_기본_상한을_넘어_동시에_연결을_쥘_수_있다(
    empty_database_url: str,
) -> None:
    engine = create_engine(empty_database_url, at_least_connections=CONNECTIONS)
    try:
        async with asyncio.timeout(10), AsyncExitStack() as held:
            for _ in range(CONNECTIONS):
                await held.enter_async_context(engine.connect())
    finally:
        await engine.dispose()
