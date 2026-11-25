"""커넥터 호출 장치(source-sync 티켓 05, ADR 0023). 호출 하나를 정한 한도까지만 기다리고, 한도를
넘긴 호출은 취소하지도 끝내지도 않고 둔다. 남은 호출이 있는 동안 같은 이름과 설정의 새 호출은
커넥터를 부르지 않고 막힌다. 시험은 붙잡아 둘 수 있는 가짜 커넥터와 짧은 한도로 장치만 돌린다.
"""

import asyncio
import gc
import logging
import time
import weakref
from collections.abc import AsyncIterator, Callable
from typing import TypeGuard

import pytest
from tests.support.fake_connectors import LEAKED_TEXT
from tests.support.holding_connectors import FETCHED, EndlessConnector, HoldingConnector

from rag_engine.adapters.connectors.guard import ConnectorCallGuard
from rag_engine.domain.connectors import (
    ConnectorCallBlockedError,
    ConnectorCallKind,
    ConnectorCallTimedOutError,
    ConnectorError,
    ConnectorFailureReason,
    ListedItem,
)
from rag_engine.domain.entities import JsonValue

LIMIT = 0.05
FOLDER_A: dict[str, JsonValue] = {"folder": "규정집/인사"}
FOLDER_B: dict[str, JsonValue] = {"folder": "규정집/재무"}
SECRET_KEY = "비밀문서/급여표_2026.pdf"


async def _until(condition: Callable[[], bool], report: Callable[[], str] | None = None) -> None:
    deadline = time.monotonic() + 5.0
    while not condition():
        detail = report() if report else ""
        assert time.monotonic() < deadline, f"5초 안에 서지 않았다. {detail}"
        await asyncio.sleep(0.001)


def _timed_out_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """한도를 넘길 때 남기는 로그 줄만 모은다."""
    return [r for r in caplog.records if r.getMessage() == "connector_call_timed_out"]


def _is_field_map(value: object) -> TypeGuard[dict[str, object]]:
    # `log_event`가 싣는 키워드 인자라 키는 문자열이다.
    return isinstance(value, dict)


def _fields(record: logging.LogRecord) -> dict[str, object]:
    fields: object = record.__dict__.get("event_fields")
    assert _is_field_map(fields)
    return fields


@pytest.fixture
async def holding() -> AsyncIterator[HoldingConnector]:
    connector = HoldingConnector()
    yield connector
    connector.release()  # 시험이 끝나면 붙잡힌 호출을 놓아 이벤트 루프가 정리되게 한다
    await asyncio.sleep(0)


async def _fetch(
    guard: ConnectorCallGuard,
    connector: HoldingConnector,
    *,
    name: str = "server-path",
    config: dict[str, JsonValue] = FOLDER_A,
    source: str | None = "인사규정",
    timeout: float = LIMIT,
) -> object:
    return await guard.call(
        connector=name,
        config=config,
        kind=ConnectorCallKind.FETCH,
        start=lambda: connector.fetch(SECRET_KEY),
        timeout_seconds=timeout,
        source=source,
    )


async def test_한도_안에_돌아오는_호출은_커넥터의_결과를_그대로_돌려준다() -> None:
    connector = HoldingConnector(hold=False)

    result = await _fetch(ConnectorCallGuard(), connector)

    assert result is FETCHED
    assert connector.calls == ["fetch"]


async def test_커넥터가_낸_예외는_그대로_부르는_쪽에_넘어간다() -> None:
    error = ConnectorError(ConnectorFailureReason.NOT_FOUND)

    async def failing() -> None:
        raise error

    with pytest.raises(ConnectorError) as caught:
        await ConnectorCallGuard().call(
            connector="server-path",
            config=FOLDER_A,
            kind=ConnectorCallKind.CHECK,
            start=failing,
            timeout_seconds=LIMIT,
        )

    assert caught.value is error


async def test_한도를_넘긴_호출은_기다리던_쪽만_한도에_돌아오고_그_호출은_살아_있다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    started = time.monotonic()

    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding)

    assert time.monotonic() - started < 2.0  # 한도의 몇십 배 안에 돌아온다
    await asyncio.sleep(LIMIT)
    assert holding.cancelled == 0, f"취소된 호출 {holding.cancelled}개"
    assert (holding.calls, holding.finished) == (["fetch"], 0)
    holding.release()
    await _until(lambda: holding.finished == 1)  # 풀어 주자 취소되지 않은 채 끝까지 돈다
    assert holding.cancelled == 0


async def test_남은_호출이_있는_동안_같은_이름과_설정의_호출은_커넥터를_부르지_않고_막힌다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding)

    with pytest.raises(ConnectorCallBlockedError):
        await _fetch(guard, holding)

    assert holding.calls == ["fetch"]
    assert guard.outstanding_calls == 1


async def test_막힌_호출은_호출의_종류가_달라도_같은_이름과_설정이면_막힌다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding)

    with pytest.raises(ConnectorCallBlockedError):
        await guard.call(
            connector="server-path",
            config=FOLDER_A,
            kind=ConnectorCallKind.CHECK,
            start=holding.check,
            timeout_seconds=LIMIT,
        )

    assert holding.calls == ["fetch"]


async def test_기억의_단위는_원천이_아니라_이름과_설정이라_다른_원천의_호출도_막힌다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding, source="인사규정")

    with pytest.raises(ConnectorCallBlockedError):
        await _fetch(guard, holding, source=None)  # 원천이 아직 없는 폴더 확인도 같다

    assert holding.calls == ["fetch"]


async def test_설정을_견주는_것은_값이라_키_순서가_달라도_같은_설정이다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    first: dict[str, JsonValue] = {"folder": "a", "depth": 2, "tags": ["x", {"y": 1, "z": 2}]}
    again: dict[str, JsonValue] = {"tags": ["x", {"z": 2, "y": 1}], "depth": 2, "folder": "a"}
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding, config=first)

    with pytest.raises(ConnectorCallBlockedError):
        await _fetch(guard, holding, config=again)

    assert holding.calls == ["fetch"]


async def test_설정이_다르거나_이름이_다르면_남은_호출이_있어도_커넥터를_부른다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding)

    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding, config=FOLDER_B)
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding, name="db")

    assert holding.calls == ["fetch", "fetch", "fetch"]


async def test_붙잡아_둔_호출을_풀어_주면_같은_이름과_설정으로_다시_부른다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding)
    holding.release()
    await _until(lambda: holding.finished == 1)

    result = await _fetch(guard, holding)

    assert result is FETCHED
    assert holding.calls == ["fetch", "fetch"]
    assert guard.outstanding_calls == 0


async def test_같은_설정으로_남은_호출이_둘이면_둘이_모두_돌아온_뒤에야_다시_부른다() -> None:
    guard = ConnectorCallGuard()
    first, second = HoldingConnector(), HoldingConnector()
    # 첫 호출이 한도를 넘기기 전에 둘이 함께 나가 있었다
    results = await asyncio.gather(
        _fetch(guard, first), _fetch(guard, second), return_exceptions=True
    )
    assert all(isinstance(result, ConnectorCallTimedOutError) for result in results)
    assert guard.outstanding_calls == 2, f"기억한 호출 {guard.outstanding_calls}개"

    first.release()
    await _until(lambda: first.finished == 1)
    with pytest.raises(ConnectorCallBlockedError):
        await _fetch(guard, HoldingConnector())  # 하나가 남아 있다
    second.release()
    await _until(lambda: second.finished == 1)

    assert await _fetch(guard, HoldingConnector(hold=False)) is FETCHED
    assert guard.outstanding_calls == 0


async def test_남는_호출의_수에는_상한이_없다() -> None:
    guard = ConnectorCallGuard()
    connectors = [HoldingConnector() for _ in range(300)]

    # 두 번에 나눠 보낸다. 뒤의 묶음은 앞의 묶음이 이미 기억된 뒤에 나가므로, 남은 수가 많다고 뒤의
    # 호출을 막는 상한이 있으면 여기서 걸린다.
    results: list[object] = []
    for wave in (connectors[:150], connectors[150:]):
        results += await asyncio.gather(
            *(
                _fetch(guard, connector, config={"folder": f"공유{id(connector)}"}, timeout=0.01)
                for connector in wave
            ),
            return_exceptions=True,
        )

    blocked = [result for result in results if isinstance(result, ConnectorCallBlockedError)]
    assert not blocked, f"막힌 호출 {len(blocked)}개"
    assert all(isinstance(result, ConnectorCallTimedOutError) for result in results)
    assert guard.outstanding_calls == 300
    for connector in connectors:
        connector.release()
    await _until(lambda: guard.outstanding_calls == 0)


async def test_부르는_쪽이_하던_일을_버려도_한도_안에_돌아오면_기억하지_않는다(
    holding: HoldingConnector, caplog: pytest.LogCaptureFixture
) -> None:
    guard = ConnectorCallGuard()
    waiting = asyncio.create_task(_fetch(guard, holding, timeout=5.0))
    await _until(lambda: holding.calls == ["fetch"])

    waiting.cancel()  # 작업 담당 기록을 잃어 작업이 거두어졌다
    with pytest.raises(asyncio.CancelledError):
        await waiting
    holding.release()
    await _until(lambda: holding.finished == 1)

    with caplog.at_level(logging.DEBUG):
        assert await _fetch(guard, HoldingConnector(hold=False), timeout=5.0) is FETCHED
        await asyncio.sleep(0.05)
    assert guard.outstanding_calls == 0
    logged = _timed_out_records(caplog)
    assert logged == [], f"바로 기억해 남긴 로그 {len(logged)}줄"


async def test_버린_시도의_호출이_제_한도까지_돌아오지_않으면_그때_한도를_넘긴_호출로_기억한다(
    holding: HoldingConnector, caplog: pytest.LogCaptureFixture
) -> None:
    guard = ConnectorCallGuard()
    waiting = asyncio.create_task(_fetch(guard, holding, timeout=0.2))
    await _until(lambda: holding.calls == ["fetch"])
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    # 한도 안이라 아직 기억하지 않는다. 바로 기억했다면 이 호출은 막혔을 것이다.
    still_free = HoldingConnector(hold=False)
    assert await _fetch(guard, still_free, timeout=5.0) is FETCHED
    assert guard.outstanding_calls == 0

    with caplog.at_level(logging.DEBUG):
        await _until(
            lambda: guard.outstanding_calls == 1,
            lambda: f"한도 뒤에 기억한 호출 {guard.outstanding_calls}개",
        )
    with pytest.raises(ConnectorCallBlockedError):
        await _fetch(guard, HoldingConnector(hold=False))
    assert holding.cancelled == 0
    timed_out = _timed_out_records(caplog)
    assert len(timed_out) == 1
    assert _fields(timed_out[0]) == {"source": "인사규정", "kind": "fetch", "outstanding": 1}


async def test_한도를_넘길_때_남기는_로그_한_줄은_원천과_종류와_남은_수만_싣는다(
    holding: HoldingConnector, caplog: pytest.LogCaptureFixture
) -> None:
    guard = ConnectorCallGuard()
    secret_config: dict[str, JsonValue] = {"folder": "/비밀/경로", "token": LEAKED_TEXT}

    with caplog.at_level(logging.DEBUG), pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding, config=secret_config)

    records = _timed_out_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert _fields(records[0]) == {"source": "인사규정", "kind": "fetch", "outstanding": 1}
    everything = " ".join(repr(record.__dict__) for record in caplog.records)
    for forbidden in (SECRET_KEY, LEAKED_TEXT, "/비밀/경로", "비밀문서"):
        assert forbidden not in everything


async def test_원천이_아직_없는_폴더_확인은_원천_이름을_비운_채_종류를_싣는다(
    holding: HoldingConnector, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG), pytest.raises(ConnectorCallTimedOutError):
        await ConnectorCallGuard().call(
            connector="server-path",
            config=FOLDER_A,
            kind=ConnectorCallKind.FOLDER_CHECK,
            start=holding.check,
            timeout_seconds=LIMIT,
        )

    [record] = _timed_out_records(caplog)
    assert _fields(record) == {"source": None, "kind": "folder_check", "outstanding": 1}


async def test_막혀서_커넥터를_부르지_않은_호출은_로그를_남기지_않는다(
    holding: HoldingConnector, caplog: pytest.LogCaptureFixture
) -> None:
    guard = ConnectorCallGuard()
    with pytest.raises(ConnectorCallTimedOutError):
        await _fetch(guard, holding)
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        for _ in range(3):
            with pytest.raises(ConnectorCallBlockedError):
                await _fetch(guard, holding)

    assert caplog.records == [], f"막힌 호출이 남긴 로그 {len(caplog.records)}줄"


async def test_남은_수는_설정마다가_아니라_장치_전체에서_센다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    guard = ConnectorCallGuard()
    held = [HoldingConnector(), HoldingConnector()]

    with caplog.at_level(logging.DEBUG):
        for index, connector in enumerate(held):
            with pytest.raises(ConnectorCallTimedOutError):
                await _fetch(guard, connector, config={"folder": f"공유{index}"})

    counts = [_fields(record)["outstanding"] for record in _timed_out_records(caplog)]
    assert counts == [1, 2], f"로그에 실린 남은 수의 차례 {counts}"
    for connector in held:
        connector.release()
    await _until(lambda: guard.outstanding_calls == 0)


class _Payload:
    """약한 참조를 걸 수 있는 결과 값."""


async def test_기억된_호출이_끝나면_다시_부르지_않아도_그_결과를_쥐고_있지_않는다() -> None:
    guard = ConnectorCallGuard()
    gate = asyncio.Event()
    produced: list[weakref.ref[_Payload]] = []

    async def slow_fetch() -> _Payload:
        await gate.wait()
        payload = _Payload()
        produced.append(weakref.ref(payload))
        return payload

    with pytest.raises(ConnectorCallTimedOutError):
        await guard.call(
            connector="server-path",
            config=FOLDER_A,
            kind=ConnectorCallKind.FETCH,
            start=slow_fetch,
            timeout_seconds=LIMIT,
        )
    gate.set()
    await _until(lambda: len(produced) == 1)
    await asyncio.sleep(0.01)  # 끝난 호출의 완료 콜백이 돈다
    gc.collect()

    assert produced[0]() is None, f"끝난 호출이 쥔 결과 {type(produced[0]()).__name__}"


_ITEMS = [ListedItem(key=f"{n}.pdf", change_marker="1", size_bytes=1) for n in range(3)]


async def _receive(
    guard: ConnectorCallGuard, connector: HoldingConnector, *, timeout: float = LIMIT
) -> list[ListedItem]:
    return [
        item
        async for item in guard.iterate(
            connector="server-path",
            config=FOLDER_A,
            items=connector.list(),
            timeout_seconds=timeout,
            source="인사규정",
        )
    ]


async def test_목록은_항목을_하나씩_내고_끝나면_끝난다() -> None:
    connector = HoldingConnector(hold=False, items=_ITEMS)

    assert await _receive(ConnectorCallGuard(), connector) == _ITEMS


async def test_목록의_한도는_항목_하나에_걸려_늦은_항목에서_한도에_돌아오고_그_호출은_남는다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    guard = ConnectorCallGuard()
    connector = HoldingConnector(items=_ITEMS, hold_list_at=1)
    received: list[ListedItem] = []

    with caplog.at_level(logging.DEBUG), pytest.raises(ConnectorCallTimedOutError):
        async for item in guard.iterate(
            connector="server-path",
            config=FOLDER_A,
            items=connector.list(),
            timeout_seconds=LIMIT,
            source="인사규정",
        ):
            received.append(item)

    assert received == _ITEMS[:1]
    assert guard.outstanding_calls == 1
    [record] = _timed_out_records(caplog)
    assert _fields(record) == {"source": "인사규정", "kind": "list", "outstanding": 1}
    connector.release()
    await _until(lambda: guard.outstanding_calls == 0)


async def test_목록의_항목을_기다리다_버려도_한도까지_돌아오지_않으면_그때_기억한다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    guard = ConnectorCallGuard()
    connector = HoldingConnector(items=_ITEMS, hold_list_at=0)
    receiving = asyncio.create_task(_receive(guard, connector, timeout=0.2))
    await _until(lambda: connector.calls == ["list"])

    receiving.cancel()  # 작업 담당 기록을 잃어 작업이 거두어졌다
    with pytest.raises(asyncio.CancelledError):
        await receiving
    assert guard.outstanding_calls == 0  # 제 한도 안이라 아직 기억하지 않는다

    with caplog.at_level(logging.DEBUG):
        await _until(
            lambda: guard.outstanding_calls == 1,
            lambda: f"한도 뒤에 기억한 목록 호출 {guard.outstanding_calls}개",
        )
    [record] = _timed_out_records(caplog)
    assert _fields(record) == {"source": "인사규정", "kind": "list", "outstanding": 1}
    connector.release()
    await _until(lambda: guard.outstanding_calls == 0)


async def test_목록을_받는_중에_다른_자리가_같은_설정을_막으면_다음_항목은_커넥터를_부르지_않는다(
    holding: HoldingConnector,
) -> None:
    guard = ConnectorCallGuard()
    listing = HoldingConnector(hold=False, items=_ITEMS)
    items = guard.iterate(
        connector="server-path",
        config=FOLDER_A,
        items=listing.list(),
        timeout_seconds=LIMIT,
        source="인사규정",
    )
    assert await anext(items) == _ITEMS[0]

    with pytest.raises(
        ConnectorCallTimedOutError
    ):  # 다른 자리의 호출이 같은 설정으로 한도를 넘겼다
        await _fetch(guard, holding)
    with pytest.raises(ConnectorCallBlockedError):
        await anext(items)

    assert listing.calls == ["list"]


async def test_끝없는_목록을_받는_동안에도_같은_이벤트_루프의_다른_일이_돈다() -> None:
    guard = ConnectorCallGuard()
    connector = EndlessConnector(cap=500_000)
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.005)
            ticks += 1

    tick_task = asyncio.create_task(ticker())
    try:
        async for _item in guard.iterate(
            connector="custom",
            config=FOLDER_A,
            items=connector.list(),
            timeout_seconds=600.0,
        ):
            if ticks >= 3:
                break
    finally:
        tick_task.cancel()

    assert ticks >= 3
    assert connector.emitted > 0
