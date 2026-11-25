"""커넥터의 `list()`를 호출 장치에 태우는 읽기 어댑터(source-sync 티켓 07, ADR 0023).
`Connector.list`는 일반 함수로 선언돼 있어 반복자를 돌려주기 전에 원천을 부를 수 있다. 그 부름도
장치의 막힘 판정을 지나야 한다."""

import asyncio
from importlib.metadata import EntryPoint

import pytest
from tests.support import plain_list_connectors

from rag_engine.adapters.connectors.guard import ConnectorCallGuard
from rag_engine.adapters.connectors.registry import (
    CONNECTOR_ENTRY_POINT_GROUP,
    EntryPointConnectorRegistry,
)
from rag_engine.domain.connectors import (
    ConnectorCallBlockedError,
    ConnectorCallKind,
    ConnectorCallTimedOutError,
)
from rag_engine.domain.entities import JsonValue

LIMIT = 0.05
FOLDER: dict[str, JsonValue] = {"folder": "규정집/인사"}


async def test_같은_설정의_남은_호출로_막혀_있으면_일반_함수인_list도_부르지_않는다() -> None:
    plain_list_connectors.LIST_CALLS.clear()
    entry = EntryPoint(
        name="installed",
        value="tests.support.plain_list_connectors:create_plain",
        group=CONNECTOR_ENTRY_POINT_GROUP,
    )
    guard = ConnectorCallGuard()
    registry = EntryPointConnectorRegistry(lambda: [entry], guard=guard)
    release = asyncio.Event()
    with pytest.raises(ConnectorCallTimedOutError):
        await guard.call(
            connector="installed",
            config=FOLDER,
            kind=ConnectorCallKind.LIST,
            start=release.wait,
            timeout_seconds=LIMIT,
        )
    reader = registry.open_reader("installed", FOLDER, source="인사", timeout_seconds=LIMIT)

    try:
        with pytest.raises(ConnectorCallBlockedError):
            async for _ in reader.list():
                pass
        calls = list(plain_list_connectors.LIST_CALLS)
    finally:
        release.set()
        while guard.outstanding_calls:
            await asyncio.sleep(0.001)

    assert calls == [], f"받은 호출: {calls}"
