"""작업 알림 듣기(`LISTEN rag_jobs`, ADR 0009, 명세 "수집 파이프라인과 작업"의 작업자 항목).

수집이 작업을 넣는 작업 단위를 커밋하면 PostgreSQL이 `NOTIFY rag_jobs`를 보낸다(`job_queue.py`).
작업자는 풀과 따로 연결 하나를 열어 그 채널을 듣고, 알림이 올 때마다 부른 쪽이 준 함수를 부른다.
알림 내용은 읽지 않는다. 깨어난 작업자는 작업 표에서 꺼내므로 알림은 "지금 꺼내 보라"는 신호일
뿐이다.

연결이 끊기면 잠시 뒤 다시 붙는다. 끊긴 사이에 온 알림은 잃으므로 다시 붙은 직후 한 번 깨워 그사이
들어온 작업을 꺼내게 한다. 폴링이 어차피 받쳐 주므로 알림을 잃는 것은 지연일 뿐 누락이 아니다.
연결 오류는 메시지에 접속 정보가 들 수 있어 로그에 싣지 않는다(원칙 V).
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Final

import psycopg
from psycopg import sql

from rag_engine.adapters.log_format import log_event
from rag_engine.adapters.postgres.job_queue import NOTIFY_CHANNEL

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_SECONDS: Final = 1.0


class JobNotificationListener:
    def __init__(self, database_url: str, *, retry_seconds: float = _DEFAULT_RETRY_SECONDS) -> None:
        self._database_url = database_url
        self._retry_seconds = retry_seconds

    async def run(self, on_notify: Callable[[], None], ready: asyncio.Event) -> None:
        """듣기를 시작해 `ready`를 세우고, 알림마다 `on_notify`를 부른다. 취소될 때까지 돈다. 연결이
        끊기면 `ready`를 내리고 다시 붙는다."""
        reconnecting = False
        while True:
            try:
                await self._listen_once(on_notify, ready, wake_on_start=reconnecting)
            except (psycopg.OperationalError, psycopg.InterfaceError):
                pass
            ready.clear()
            reconnecting = True
            log_event(logger, "job_listener_disconnected", level=logging.WARNING)
            await asyncio.sleep(self._retry_seconds)

    async def _listen_once(
        self, on_notify: Callable[[], None], ready: asyncio.Event, *, wake_on_start: bool
    ) -> None:
        """연결 하나로 듣는다. 연결이 닫히면 돌아오거나 연결 오류를 올린다."""
        async with await psycopg.AsyncConnection.connect(
            self._database_url, autocommit=True
        ) as connection:
            await connection.execute(sql.SQL("LISTEN {}").format(sql.Identifier(NOTIFY_CHANNEL)))
            ready.set()
            if wake_on_start:
                on_notify()
            async for _ in connection.notifies():
                on_notify()
