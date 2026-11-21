"""커넥터 레지스트리 시험이 entry point 로 가리키는 가짜 커넥터를 만드는 함수들(명세 "커넥터
인터페이스 1.0"). 모듈 최상위에서 부수 효과를 내지 않는다.

함수마다 설치처가 만들 수 있는 모양 하나를 흉내 낸다. 정상, 설정이 모자란 것, 다른 major 의
인터페이스를 쓰는 것, 예고 없이 깨지는 것이다.
"""

from collections.abc import AsyncIterator, Mapping

from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    ConnectorError,
    ConnectorFailureReason,
    FetchedItem,
    ListedItem,
)
from rag_engine.domain.entities import JsonValue

LEAKED_TEXT = "비밀번호-hunter2"


class FakeConnector:
    """항목 하나를 내는 커넥터. 받은 설정을 그대로 들고 있어 시험이 넘어온 값을 본다."""

    def __init__(
        self, config: Mapping[str, JsonValue], interface_version: str = CONNECTOR_INTERFACE_VERSION
    ) -> None:
        self.config = config
        self._interface_version = interface_version

    @property
    def interface_version(self) -> str:
        return self._interface_version

    async def list(self) -> AsyncIterator[ListedItem]:
        yield ListedItem(key="a.pdf", change_marker="1", size_bytes=3)

    async def fetch(self, key: str) -> FetchedItem:
        return FetchedItem(data=b"abc", mime=None, updated_at=None, metadata={})

    async def check(self) -> None:
        return None


def create_fake(config: Mapping[str, JsonValue]) -> FakeConnector:
    return FakeConnector(config)


def create_requiring_folder(config: Mapping[str, JsonValue]) -> FakeConnector:
    """`folder` 칸이 문자열이 아니면 설정이 틀렸다고 알린다."""
    if not isinstance(config.get("folder"), str):
        raise ConnectorError(ConnectorFailureReason.INVALID_CONFIG)
    return FakeConnector(config)


def create_next_major(config: Mapping[str, JsonValue]) -> FakeConnector:
    return FakeConnector(config, interface_version="2.0.0")


def create_next_minor(config: Mapping[str, JsonValue]) -> FakeConnector:
    return FakeConnector(config, interface_version="1.7.2")


class _NumericVersionConnector:
    """인터페이스 버전을 문자열이 아닌 정수로 내는 잘못 만든 커넥터."""

    interface_version = 1


def create_numeric_version(config: Mapping[str, JsonValue]) -> object:
    return _NumericVersionConnector()


def create_chained(config: Mapping[str, JsonValue]) -> FakeConnector:
    """설치처의 예외 글이 원인으로 묶인 채 `invalid_config`를 낸다."""
    raise ConnectorError(ConnectorFailureReason.INVALID_CONFIG) from ValueError(LEAKED_TEXT)


def create_unreadable(config: Mapping[str, JsonValue]) -> FakeConnector:
    """만들 때 낼 수 없는 사유(`unreadable`)를 낸다. 계약을 어긴 커넥터다."""
    raise ConnectorError(ConnectorFailureReason.UNREADABLE)


def create_broken(config: Mapping[str, JsonValue]) -> FakeConnector:
    """인터페이스에 없는 예외를 비밀번호처럼 보이는 글과 함께 낸다."""
    raise RuntimeError(LEAKED_TEXT)
