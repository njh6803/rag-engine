"""설치처가 만든 커넥터가 인터페이스에 없는 예외를 비밀번호처럼 보이는 글과 함께 내는 흉내
(source-sync 티켓 07). `EntryPointConnectorRegistry`의 entry point가 가리키는 함수들이다. 모듈
최상위에서 부수 효과를 내지 않는다."""

from collections.abc import AsyncIterator, Mapping

from tests.support.fake_connectors import LEAKED_TEXT

from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    FetchedItem,
    ListedItem,
)
from rag_engine.domain.entities import JsonValue

LEAKED_KEY = "비밀키-파일.docx"


class _LeakyConnector:
    def __init__(self, *, list_breaks: bool) -> None:
        self._list_breaks = list_breaks

    @property
    def interface_version(self) -> str:
        return CONNECTOR_INTERFACE_VERSION

    async def list(self) -> AsyncIterator[ListedItem]:
        if self._list_breaks:
            raise RuntimeError(LEAKED_TEXT)
        yield ListedItem(key=LEAKED_KEY, change_marker="1", size_bytes=3)

    async def fetch(self, key: str) -> FetchedItem:
        raise RuntimeError(LEAKED_TEXT)

    async def check(self) -> None:
        return None


class _SynchronousRaiser:
    """`list`가 비동기 제너레이터가 아니라 일반 함수라서, 반복자를 돌려주기도 전에 예외를 올린다.
    `Connector.list`의 선언(`def list(self) -> AsyncIterator`)이 이 꼴을 허용한다."""

    @property
    def interface_version(self) -> str:
        return CONNECTOR_INTERFACE_VERSION

    def list(self) -> AsyncIterator[ListedItem]:
        raise RuntimeError(LEAKED_TEXT)

    async def fetch(self, key: str) -> FetchedItem:
        raise RuntimeError(LEAKED_TEXT)

    async def check(self) -> None:
        return None


def create_list_raises_synchronously(config: Mapping[str, JsonValue]) -> _SynchronousRaiser:
    return _SynchronousRaiser()


def create_list_breaks(config: Mapping[str, JsonValue]) -> _LeakyConnector:
    return _LeakyConnector(list_breaks=True)


def create_fetch_breaks(config: Mapping[str, JsonValue]) -> _LeakyConnector:
    return _LeakyConnector(list_breaks=False)
