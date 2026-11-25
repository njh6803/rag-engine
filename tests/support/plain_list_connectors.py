"""`list`를 비동기 제너레이터가 아니라 일반 함수로 선언한 커넥터의 흉내(source-sync 티켓 07).
`Connector.list`의 선언(`def list(self) -> AsyncIterator`)은 이 꼴을 허용하고, 이 꼴은 반복자를
돌려주기 전에 원천을 부를 수 있다. 부른 횟수를 `LIST_CALLS`에 남긴다. 시험이 시작 전에 비운다."""

from collections.abc import AsyncIterator, Mapping

from rag_engine.domain.connectors import CONNECTOR_INTERFACE_VERSION, FetchedItem, ListedItem
from rag_engine.domain.entities import JsonValue

LIST_CALLS: list[str] = []


async def _no_items() -> AsyncIterator[ListedItem]:
    for item in tuple[ListedItem, ...]():
        yield item


class _PlainListConnector:
    @property
    def interface_version(self) -> str:
        return CONNECTOR_INTERFACE_VERSION

    def list(self) -> AsyncIterator[ListedItem]:
        LIST_CALLS.append("list")
        return _no_items()

    async def fetch(self, key: str) -> FetchedItem:
        raise AssertionError

    async def check(self) -> None:
        return None


def create_plain(config: Mapping[str, JsonValue]) -> _PlainListConnector:
    return _PlainListConnector()
