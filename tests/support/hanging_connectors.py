"""동기화의 돌아오지 않는 호출 시험이 entry point로 가리키는 커넥터(source-sync 티켓 07).

커넥터가 폴더 이름(`config["folder"]`)으로 시험이 세워 둔 `Plan`을 찾는다. 계획이 `list()`나
`fetch`를 붙잡아 두고(`hold`), 시험이 `release()`로 푼다. 호출이 불린 횟수를 세어 시험이 "커넥터를
부르지 않았다"를 본다. `in_thread`면 끊긴 공유 폴더의 읽기처럼 이벤트 루프 밖의 daemon 스레드가
풀릴 때까지 막힌다(서버 경로 커넥터가 파일 시스템을 부르는 모양이다). 모듈 최상위에서 부수 효과를
내지 않는다. 계획은 시험이 `World`로 세우고 끝나면 모두 풀어 비운다.
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

from tests.support.holding_connectors import EndlessConnector

from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    FetchedItem,
    ListedItem,
)
from rag_engine.domain.entities import JsonValue

PLANS: dict[str, "Plan"] = {}
SETTLE_SECONDS = 0.05


def _resolve(future: asyncio.Future[None]) -> None:
    if not future.done():
        future.set_result(None)


class Plan:
    """폴더 하나가 하는 일. `hang_list`면 `list()`가 첫 항목 전에 붙잡히고, `fetch_ok`가 있으면
    그 횟수까지의 `fetch`만 바로 돌려주고 그 뒤는 붙잡힌다. `list_delay`는 `list()`가 돌려주기
    전에 기다리는 초다(한도 안에 끝나는 느린 호출)."""

    def __init__(
        self,
        files: Mapping[str, bytes],
        *,
        hang_list: bool = False,
        fetch_ok: int | None = None,
        list_delay: float = 0.0,
        in_thread: bool = False,
        endless_cap: int | None = None,
    ) -> None:
        self.files = dict(files)
        # 주면 `list()`가 파일 대신 항목을 끝없이 낸다(`EndlessConnector`). `cap`개를 넘기면 오류다.
        self.endless_cap = endless_cap
        self.marker = "m1"
        self.hang_list = hang_list
        self.fetch_ok = fetch_ok
        self.list_delay = list_delay
        self.in_thread = in_thread
        # 첫 `fetch`가 시작될 때 한 번 부르는 걸이. 다른 자리의 호출을 끼워 넣는 데 쓴다.
        self.on_fetch: Callable[[], Awaitable[None]] | None = None
        self.list_calls = 0
        self.fetch_calls = 0
        self._gate = asyncio.Event()
        self._thread_gate = threading.Event()

    def release(self) -> None:
        self._gate.set()
        self._thread_gate.set()

    async def hold(self) -> None:
        """풀어 줄 때까지 돌아가지 않는다."""
        if not self.in_thread:
            await self._gate.wait()
            return
        loop = asyncio.get_running_loop()
        done: asyncio.Future[None] = loop.create_future()

        def wait_in_thread() -> None:
            self._thread_gate.wait()
            try:
                loop.call_soon_threadsafe(_resolve, done)
            except RuntimeError:
                return  # 이벤트 루프가 이미 닫혔다

        threading.Thread(target=wait_in_thread, daemon=True, name="hanging-call").start()
        await done


class PlannedConnector:
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    @property
    def interface_version(self) -> str:
        return CONNECTOR_INTERFACE_VERSION

    async def list(self) -> AsyncIterator[ListedItem]:
        plan = self._plan
        plan.list_calls += 1
        if plan.list_delay:
            await asyncio.sleep(plan.list_delay)
        if plan.hang_list:
            await plan.hold()
        if plan.endless_cap is not None:
            async for item in EndlessConnector(cap=plan.endless_cap).list():
                yield item
        for key, data in plan.files.items():
            yield ListedItem(key=key, change_marker=plan.marker, size_bytes=len(data))

    async def fetch(self, key: str) -> FetchedItem:
        plan = self._plan
        plan.fetch_calls += 1
        if plan.on_fetch is not None and plan.fetch_calls == 1:
            await plan.on_fetch()
        if plan.fetch_ok is not None and plan.fetch_calls > plan.fetch_ok:
            await plan.hold()
        return FetchedItem(data=plan.files[key], mime=None, updated_at=None, metadata={})

    async def check(self) -> None:
        return None


def create_planned(config: Mapping[str, JsonValue]) -> PlannedConnector:
    return PlannedConnector(PLANS[str(config["folder"])])


class World:
    """시험이 세운 계획의 모음. 끝날 때 붙잡힌 호출을 모두 풀고 한 번 쉬어 그 호출들이 끝나게
    한다."""

    def plan(
        self,
        folder: str,
        files: Mapping[str, bytes] | None = None,
        *,
        hang_list: bool = False,
        fetch_ok: int | None = None,
        list_delay: float = 0.0,
        in_thread: bool = False,
        endless_cap: int | None = None,
    ) -> Plan:
        made = Plan(
            files or {},
            hang_list=hang_list,
            fetch_ok=fetch_ok,
            list_delay=list_delay,
            in_thread=in_thread,
            endless_cap=endless_cap,
        )
        PLANS[folder] = made
        return made

    def release_all(self) -> None:
        for each in PLANS.values():
            each.release()

    async def close(self) -> None:
        self.release_all()
        await asyncio.sleep(SETTLE_SECONDS)
        PLANS.clear()
