"""커넥터 호출 장치. 서버와 작업자가 커넥터를 부를 때 지나는 곳이다(ADR 0023, source-sync 명세
"동기화의 차례").

- 호출 하나(`list()`의 다음 항목 하나, `fetch` 한 번, `check()` 한 번, 폴더 확인 한 번)를 호출마다
  따로 띄운 일(asyncio의 Task)로 내보내고, 그 일을 취소하지 않은 채 한도까지 기다린다. 항목마다
  이벤트 루프로 돌아가므로, 기다리는 일 없이 항목을 끝없이 내는 목록을 받는 동안에도 같은 루프의
  다른 일(작업 담당 기록의 기한을 늘리는 일)이 돈다. 목록 전체의 시간이나 항목 수에는 상한이 없다.
- 한도를 넘긴 호출은 취소하지도 끝내지도 않고 둔다. 기다리던 쪽만 `ConnectorCallTimedOutError`로
  돌아온다. 프로세스는 그 호출을 커넥터의 이름과 설정(값으로 견준다)으로 기억하고, 그렇게 남은
  호출이 있는 동안 같은 이름과 설정의 새 호출은 커넥터를 부르지 않고 `ConnectorCallBlockedError`로
  막는다. 기억의 단위가 원천이 아니라서 같은 커넥터와 설정을 쓰는 다른 쪽의 호출도 막힌다. 남은
  호출이 모두 돌아오면 다시 부른다. 남는 호출의 수에는 상한이 없다. 기억은 이 객체 안에만 있어
  프로세스를 다시 띄우면 빈다.
- 부르는 쪽이 하던 일을 버려 기다리던 일이 취소되면(작업 담당 기록을 잃어 작업이 거두어졌다) 나가
  있던 호출은 바로 기억하지 않는다. 제 한도 안에 돌아오면 기억에 들지 않고, 한도까지 돌아오지
  않으면 그때 한도를 넘긴 호출로 기억한다.
- 한도를 넘겨 기다리기를 그만둘 때 로그 한 줄을 남긴다. 싣는 것은 원천 이름(없으면 비운다)과 호출의
  종류와 그 프로세스에 끝나지 않은 채 남은 호출의 수다. 문서의 키와 커넥터 설정은 싣지 않는다
  (원칙 V). 막혀서 커넥터를 부르지 않은 호출은 줄을 남기지 않는다.
- 커넥터가 낸 예외는 그대로 부르는 쪽에 넘긴다.

이벤트 루프 하나 안에서만 쓴다(스레드 사이에서 나눠 쓰지 않는다). 읽기를 스레드로 넘기는 일은
커넥터가 하고, 이 장치는 커넥터가 비동기 함수 안에서 그대로 막히는 경우를 풀지 못한다(ADR 0023
Consequences).
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from typing import Final

from rag_engine.adapters.log_format import log_event
from rag_engine.domain.connectors import (
    ConnectorCallBlockedError,
    ConnectorCallKind,
    ConnectorCallTimedOutError,
)
from rag_engine.domain.entities import JsonValue

logger = logging.getLogger(__name__)

_TIMED_OUT_EVENT: Final = "connector_call_timed_out"


def _canonical(value: JsonValue) -> JsonValue:
    # `JsonValue`는 `dict`와 `list`가 아닌 `Mapping`과 `Sequence`도 받으므로 `json`이 다룰 꼴로
    # 푼다.
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {key: _canonical(entry) for key, entry in value.items()}
    if isinstance(value, Sequence):
        return [_canonical(entry) for entry in value]
    return value


def _identity(connector: str, config: Mapping[str, JsonValue]) -> str:
    """커넥터 이름과 설정을 값으로 견주는 열쇠. 키 순서가 달라도 같은 설정은 같은 열쇠다. 견주는
    것은 JSON 글이라 `1`과 `1.0`과 `true`는 다른 값이다. 부르는 쪽이 같은 설정을 같은 꼴로
    넘긴다고 본다. 기억 표 안에서만 쓰고 로그나 예외에 싣지 않는다."""
    canonical = json.dumps(
        _canonical(config), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return f"{connector}\n{canonical}"


def _retrieve_outcome[T](future: asyncio.Future[T]) -> None:
    # 기다리는 쪽이 떠난 호출이 예외로 끝나도 "never retrieved" 경고가 뜨지 않게 읽어 둔다.
    if not future.cancelled():
        future.exception()


async def _advance[T](items: AsyncIterator[T]) -> T:
    return await anext(items)


class ConnectorCallGuard:
    """모듈 머리 설명의 규칙을 지키는 장치. 기억이 이 객체에 있으므로 서버와 작업자는 프로세스마다
    하나만 만들어 나눠 쓴다. 요청이나 작업마다 새로 만들면 기억이 갈려 막지 못한다."""

    def __init__(self) -> None:
        # 열쇠마다 끝나지 않은 채 남은 호출의 `done` 확인 함수. 막혔는지는 완료 콜백이 아니라 이
        # 함수를 그때그때 읽어 정해, 막 끝난 호출이 콜백이 돌기 전의 틈에 다음 호출을 막지 않게
        # 한다. 완료 콜백(`_release`)은 끝난 호출이 쥔 결과를 놓으려고 따로 둔다.
        self._stuck: dict[str, list[Callable[[], bool]]] = {}

    @property
    def outstanding_calls(self) -> int:
        """이 장치에 한도를 넘기고도 끝나지 않은 채 남은 호출의 수. 끝난 호출은 세기 전에 비운다."""
        for key in tuple(self._stuck):
            self._live(key)
        return sum(len(entries) for entries in self._stuck.values())

    def _live(self, key: str) -> int:
        """그 열쇠로 남은 호출 가운데 끝난 것을 비우고 아직 끝나지 않은 수를 돌려준다."""
        remaining = [is_done for is_done in self._stuck.get(key, []) if not is_done()]
        if remaining:
            self._stuck[key] = remaining
        else:
            self._stuck.pop(key, None)
        return len(remaining)

    def _release(self, key: str) -> None:
        # 기억된 호출이 끝나면 곧바로 비운다. 비우지 않으면 같은 열쇠로 다시 부르기 전까지 끝난
        # 호출이 결과(서버 경로 커넥터는 크기 상한, 기본 100MB까지의 바이트)를 계속 쥐고 있다. 그
        # 크기는 명세가 규칙으로 따진 어림이고 재지 않았다.
        self._live(key)

    def _remember[T](
        self,
        future: asyncio.Future[T],
        key: str,
        kind: ConnectorCallKind,
        source: str | None,
    ) -> None:
        if future.done():
            return
        self._stuck.setdefault(key, []).append(future.done)
        future.add_done_callback(lambda _: self._release(key))
        log_event(
            logger,
            _TIMED_OUT_EVENT,
            level=logging.WARNING,
            source=source,
            kind=kind.value,
            outstanding=self.outstanding_calls,
        )

    def _remember_later[T](
        self,
        future: asyncio.Future[T],
        key: str,
        kind: ConnectorCallKind,
        source: str | None,
        delay: float,
    ) -> None:
        handle = asyncio.get_running_loop().call_later(
            delay, self._remember, future, key, kind, source
        )

        def cancel_timer(_: asyncio.Future[T]) -> None:
            handle.cancel()

        future.add_done_callback(cancel_timer)

    async def call[T](
        self,
        *,
        connector: str,
        config: Mapping[str, JsonValue],
        kind: ConnectorCallKind,
        start: Callable[[], Awaitable[T]],
        timeout_seconds: float,
        source: str | None = None,
    ) -> T:
        """`start()`가 내는 호출 하나를 `timeout_seconds`까지 기다린다. 막혀 있으면 `start`를 부르지
        않는다(코루틴을 미리 만들어 두면 부르지 않은 채 버려져 경고가 난다)."""
        key = _identity(connector, config)
        if self._live(key):
            raise ConnectorCallBlockedError
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        future = asyncio.ensure_future(start())
        future.add_done_callback(_retrieve_outcome)
        try:
            done, _ = await asyncio.wait({future}, timeout=timeout_seconds)
        except asyncio.CancelledError:
            # 부르는 쪽이 하던 일을 버렸다. 호출은 취소하지 않고, 제 한도까지 돌아오지 않으면 그때
            # 기억한다.
            if not future.done():
                self._remember_later(future, key, kind, source, max(0.0, deadline - loop.time()))
            raise
        if not done:
            self._remember(future, key, kind, source)
            raise ConnectorCallTimedOutError
        return future.result()

    async def iterate[T](
        self,
        *,
        connector: str,
        config: Mapping[str, JsonValue],
        items: AsyncIterator[T],
        timeout_seconds: float,
        source: str | None = None,
    ) -> AsyncIterator[T]:
        """커넥터의 `list()`를 받는다. 항목 하나를 받을 때마다 호출 하나이고 한도는 그 항목 하나에
        걸린다. 항목을 받을 때마다 막혔는지 다시 본다. 받는 쪽이 목록을 끝까지 받지 않고 멈춰도
        `items`를 닫지 않는다. 한도를 넘긴 호출이 아직 그 제너레이터 안에서 돌고 있을 수 있고,
        끊긴 폴더에서는 닫는 일도 돌아오지 않을 수 있어서다. 닫는 일은 부르는 쪽 몫이고, 닫지
        않으면 이벤트 루프가 그 제너레이터를 치울 때 닫는다."""
        while True:
            try:
                item = await self.call(
                    connector=connector,
                    config=config,
                    kind=ConnectorCallKind.LIST,
                    start=lambda: _advance(items),
                    timeout_seconds=timeout_seconds,
                    source=source,
                )
            except StopAsyncIteration:
                return
            yield item
