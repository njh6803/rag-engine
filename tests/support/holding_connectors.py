"""커넥터 호출 장치 시험이 쓰는 가짜 커넥터 둘(source-sync 티켓 05).

`HoldingConnector`는 풀어 줄 때까지 호출을 붙잡아 둔다. 호출이 불린 횟수와 끝난 횟수와 취소된 횟수를
세어, 시험이 "커넥터를 부르지 않았다", "한도를 넘긴 호출이 살아 있다", "호출을 취소하지 않았다"를
본다. `EndlessConnector`는 항목 사이에 기다리는 일 없이 항목을 끝없이 낸다(프로브
`.scratch/source-sync/probes/endless-list/`의 `endless`가 이 꼴이다).
"""

import asyncio
from collections.abc import AsyncIterator, Sequence

from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    FetchedItem,
    ListedItem,
)

FETCHED = FetchedItem(data=b"abc", mime=None, updated_at=None, metadata={})


class HoldingConnector:
    """`release()`를 부르기 전까지 호출마다 붙잡아 두는 커넥터. `hold=False`면 붙잡지 않는다.

    `list()`는 `hold_list_at`번째 항목(0부터)을 내기 전에 붙잡는다. 고르지 않으면 항목마다 붙잡는다.
    """

    def __init__(
        self,
        *,
        hold: bool = True,
        items: Sequence[ListedItem] = (),
        hold_list_at: int | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.finished = 0
        self.cancelled = 0
        self._items = items
        self._hold_list_at = hold_list_at
        self._gate = asyncio.Event()
        if not hold:
            self._gate.set()

    @property
    def interface_version(self) -> str:
        return CONNECTOR_INTERFACE_VERSION

    def release(self) -> None:
        self._gate.set()

    async def _hold(self, kind: str) -> None:
        self.calls.append(kind)
        try:
            await self._gate.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        self.finished += 1

    async def list(self) -> AsyncIterator[ListedItem]:
        for index, item in enumerate(self._items):
            if self._hold_list_at is None or index == self._hold_list_at:
                await self._hold("list")
            else:
                self.calls.append("list")
            yield item

    async def fetch(self, key: str) -> FetchedItem:
        await self._hold("fetch")
        return FETCHED

    async def check(self) -> None:
        await self._hold("check")


class EndlessConnector:
    """기다리는 일 없이 항목을 끝없이 내는 커넥터. 받는 쪽이 항목 사이에 이벤트 루프로 돌아가지
    않으면 시험이 영원히 돌지 않으므로, `cap`개를 넘기면 오류를 올려 빨갛게 끝낸다."""

    def __init__(self, *, cap: int) -> None:
        self.emitted = 0
        self._cap = cap

    @property
    def interface_version(self) -> str:
        return CONNECTOR_INTERFACE_VERSION

    async def list(self) -> AsyncIterator[ListedItem]:
        while True:
            if self.emitted >= self._cap:
                raise AssertionError("받는 쪽이 항목 사이에 이벤트 루프로 돌아가지 않았다")
            yield ListedItem(
                key=f"규정집/문서_{self.emitted:09d}.pdf", change_marker="1", size_bytes=1
            )
            self.emitted += 1

    async def fetch(self, key: str) -> FetchedItem:
        return FETCHED

    async def check(self) -> None:
        return None
