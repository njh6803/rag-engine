"""커넥터 레지스트리. entry point 그룹 `rag_engine.connectors`에서 이름으로 커넥터를 찾아 원천의
설정으로 만든다(ADR 0012, source-sync 명세 "커넥터 인터페이스 1.0").

entry point가 가리키는 것은 설정을 받아 커넥터를 돌려주는 보통 함수다. 만드는 함수는 원천에 닿지
않으므로 이 호출에는 커넥터 호출의 한도를 걸지 않는다. 인터페이스 버전의 major가 1이 아니면 그
커넥터를 거부하고 기록한다. 설치되지 않은 이름과 major가 다른 커넥터와 불러오다 깨진 커넥터는
`ConnectorUnavailableError` 하나로 알린다. 만드는 함수가 올린 `ConnectorError`가 설정이 틀렸다는
`invalid_config`이면 그 사유만 들어 새로 올린다. 만들 때 낼 수 있는 사유는 이 하나뿐이라 다른 사유는
계약을 어긴 것이고 불러오다 깨진 것과 같이 `ConnectorUnavailableError`로 알린다.

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
    ConnectorFailureReason,
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
        # 올리는 예외는 모두 아래 `except` 밖에서 올린다. `except` 안에서 올리면 `from None`으로도
        # `__context__`에 원래 예외가 남고, 그 예외의 원인에 설치처의 글이 실려 있을 수 있다.
        connector: Connector | None = None
        invalid_config = False
        interface_version = ""
        major = ""
        try:
            factory: ConnectorFactory = entry.load()
            created = factory(config)
            interface_version = created.interface_version
            major = _major(interface_version)
            connector = created
        except ConnectorError as error:
            # 만들 때 낼 수 있는 사유는 `invalid_config` 하나다. 다른 사유는 계약을 어긴 것이다.
            invalid_config = error.reason is ConnectorFailureReason.INVALID_CONFIG
            if not invalid_config:
                log_event(
                    logger,
                    "connector_rejected",
                    level=logging.WARNING,
                    connector=name,
                    exception_type=type(error).__name__,
                )
        except Exception as error:  # 설치처의 커넥터가 어떻게 깨져도 같은 거부로 알린다
            log_event(
                logger,
                "connector_rejected",
                level=logging.WARNING,
                connector=name,
                exception_type=type(error).__name__,
            )
        if invalid_config:
            raise ConnectorError(ConnectorFailureReason.INVALID_CONFIG)
        if connector is None:
            raise ConnectorUnavailableError
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
