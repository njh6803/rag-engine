"""커넥터 인터페이스 1.0.0과 그것이 주고받는 값(명세 "커넥터 인터페이스 1.0", ADR 0012)."""

import copy
import inspect
import pickle
from collections.abc import AsyncIterator, Mapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    Connector,
    ConnectorError,
    ConnectorFailureReason,
    ConnectorUnavailableError,
    FetchedItem,
    ListedItem,
)
from rag_engine.domain.entities import JsonValue

UPDATED = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)


class _FakeConnector:
    """Protocol 을 채우는지 보는 최소 구현. 항목 둘을 내고 `check()`는 아무것도 하지 않는다."""

    interface_version = CONNECTOR_INTERFACE_VERSION

    def __init__(self, config: Mapping[str, JsonValue]) -> None:
        self.config = config

    async def list(self) -> AsyncIterator[ListedItem]:
        yield ListedItem(key="a.pdf", change_marker="1", size_bytes=10)
        yield ListedItem(key="b/c.docx", change_marker="2", size_bytes=None)

    async def fetch(self, key: str) -> FetchedItem:
        if key != "a.pdf":
            raise ConnectorError(ConnectorFailureReason.NOT_FOUND)
        return FetchedItem(data=b"%PDF", mime="application/pdf", updated_at=UPDATED, metadata={})

    async def check(self) -> None:
        return None


def test_커넥터_인터페이스의_버전은_세_자리_1_0_0이다() -> None:
    assert CONNECTOR_INTERFACE_VERSION == "1.0.0"


@pytest.mark.parametrize("reason", list(ConnectorFailureReason))
def test_예외는_복사와_pickle을_거쳐도_같은_사유를_든다(reason: ConnectorFailureReason) -> None:
    error = ConnectorError(reason)

    assert copy.copy(error).reason is reason
    # 이 시험이 방금 직접 만든 값만 되돌려 읽는다. 믿지 않는 데이터를 읽는 자리가 아니다.
    restored = pickle.loads(pickle.dumps(error))
    assert isinstance(restored, ConnectorError)
    assert restored.reason is reason


def test_예외의_사유_값은_닫힌_다섯이다() -> None:
    assert {reason.value for reason in ConnectorFailureReason} == {
        "invalid_config",
        "unreadable",
        "rejected",
        "not_found",
        "too_large",
    }


@pytest.mark.parametrize("reason", list(ConnectorFailureReason))
def test_예외는_사유를_들고_글에는_사유_값만_싣는다(reason: ConnectorFailureReason) -> None:
    error = ConnectorError(reason)

    assert error.reason is reason
    assert str(error) == reason.value


def test_예외에_사유_말고_글을_넘길_길이_없다() -> None:
    assert list(inspect.signature(ConnectorError).parameters) == ["reason"]


def test_쓸_수_없는_커넥터_예외는_사유_예외와_다른_종류다() -> None:
    assert not issubclass(ConnectorUnavailableError, ConnectorError)
    assert not issubclass(ConnectorError, ConnectorUnavailableError)


async def test_목록은_비동기_반복이고_받기와_연결_확인은_비동기_함수다() -> None:
    connector: Connector = _FakeConnector({"folder": "a"})

    items = [item async for item in connector.list()]
    fetched = await connector.fetch("a.pdf")
    await connector.check()

    assert connector.interface_version == "1.0.0"
    assert [item.key for item in items] == ["a.pdf", "b/c.docx"]
    assert items[1].size_bytes is None
    assert (fetched.data, fetched.mime, fetched.updated_at) == (b"%PDF", "application/pdf", UPDATED)


async def test_없는_키를_받으면_not_found_사유의_예외가_난다() -> None:
    connector: Connector = _FakeConnector({})

    with pytest.raises(ConnectorError) as caught:
        await connector.fetch("없음.pdf")

    assert caught.value.reason is ConnectorFailureReason.NOT_FOUND


def test_받은_결과의_MIME과_갱신_시각은_모르면_비운다() -> None:
    fetched = FetchedItem(data=b"x", mime=None, updated_at=None, metadata={"title": "제목"})

    assert fetched.mime is None
    assert fetched.updated_at is None
    assert fetched.metadata == {"title": "제목"}


def test_목록_항목과_받은_결과는_바꿀_수_없다() -> None:
    item = ListedItem(key="a.pdf", change_marker="1", size_bytes=None)
    fetched = FetchedItem(data=b"x", mime=None, updated_at=None, metadata={})
    field = "key"

    with pytest.raises(FrozenInstanceError):
        setattr(item, field, "b.pdf")
    with pytest.raises(FrozenInstanceError):
        setattr(fetched, "data", b"y")  # noqa: B010
