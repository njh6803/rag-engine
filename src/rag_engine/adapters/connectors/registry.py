"""커넥터 레지스트리. entry point 그룹 `rag_engine.connectors`에서 이름으로 커넥터를 찾아 원천의
설정으로 만든다(ADR 0012, source-sync 명세 "커넥터 인터페이스 1.0").

entry point가 가리키는 것은 설정을 받아 커넥터를 돌려주는 보통 함수다. 만드는 함수는 원천에 닿지
않으므로 이 호출에는 커넥터 호출의 한도를 걸지 않는다. 인터페이스 버전의 major가 1이 아니면 그
커넥터를 거부하고 기록한다. 설치되지 않은 이름과 major가 다른 커넥터와 불러오다 깨진 커넥터는
`ConnectorUnavailableError` 하나로 알린다. 만드는 함수가 올린 `ConnectorError`(설정이 틀렸다는
`invalid_config`)는 그대로 전한다.

로그에는 커넥터의 이름과 인터페이스 버전, 예외의 종류 이름만 남긴다. 설치처가 만든 커넥터의 예외
글에는 토큰이나 연결 문자열이 섞일 수 있고 원천의 설정에는 폴더 이름이 든다(원칙 V).
"""

import logging
from collections.abc import Callable, Iterable, Mapping
from importlib.metadata import EntryPoint, entry_points
from typing import Final

from rag_engine.adapters.log_format import log_event
from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    Connector,
    ConnectorError,
    ConnectorFactory,
    ConnectorUnavailableError,
)
from rag_engine.domain.entities import JsonValue

logger = logging.getLogger(__name__)

CONNECTOR_ENTRY_POINT_GROUP: Final = "rag_engine.connectors"


def _discover_entry_points() -> Iterable[EntryPoint]:
    return entry_points(group=CONNECTOR_ENTRY_POINT_GROUP)


def _major(semver: str) -> str:
    return semver.partition(".")[0]


class EntryPointConnectorRegistry:
    """`ConnectorRegistry`의 구현. `create`를 부를 때마다 entry point를 읽고 캐시하지 않는다.
    읽는 데 드는 시간은 재지 않았다. 작업자가 문서마다 커넥터를 만들게 되면(명세 "수집 파이프라인과
    작업") 그 호출이 잦아지므로, 그때 부르는 티켓이 캐시를 더한다. 시험은 읽는 함수를 바꿔
    끼운다."""

    def __init__(self, discover: Callable[[], Iterable[EntryPoint]] | None = None) -> None:
        self._discover = discover if discover is not None else _discover_entry_points

    def create(self, name: str, config: Mapping[str, JsonValue]) -> Connector:
        entry = next((entry for entry in self._discover() if entry.name == name), None)
        if entry is None:
            log_event(logger, "connector_rejected", level=logging.WARNING, connector=name)
            raise ConnectorUnavailableError
        try:
            factory: ConnectorFactory = entry.load()
            connector = factory(config)
            interface_version = connector.interface_version
            major = _major(interface_version)
        except ConnectorError as error:
            # 사유 값만 전한다. 설치처의 예외가 원인으로 묶여 있으면 그 글이 따라가지 않게 끊는다.
            raise ConnectorError(error.reason) from None
        except Exception as error:  # 설치처의 커넥터가 어떻게 깨져도 같은 거부로 알린다
            log_event(
                logger,
                "connector_rejected",
                level=logging.WARNING,
                connector=name,
                exception_type=type(error).__name__,
            )
            raise ConnectorUnavailableError from None
        if major != _major(CONNECTOR_INTERFACE_VERSION):
            log_event(
                logger,
                "connector_rejected",
                level=logging.WARNING,
                connector=name,
                interface_version=interface_version,
            )
            raise ConnectorUnavailableError
        return connector
