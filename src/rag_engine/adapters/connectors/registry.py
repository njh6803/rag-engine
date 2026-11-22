"""커넥터 레지스트리. entry point 그룹 `rag_engine.connectors`에서 이름으로 커넥터를 찾아 원천의
설정으로 만든다(ADR 0012, source-sync 명세 "커넥터 인터페이스 1.0").

entry point가 가리키는 것은 설정을 받아 커넥터를 돌려주는 보통 함수다. 만드는 함수는 원천에 닿지
않으므로 이 호출에는 커넥터 호출의 한도를 걸지 않는다. 인터페이스 버전의 major가 1이 아니면 그
커넥터를 거부하고 기록한다. 설치되지 않은 이름과 major가 다른 커넥터와 불러오다 깨진 커넥터는
`ConnectorUnavailableError` 하나로 알린다. entry point를 읽다 깨진 것(다른 패키지의 손상된
메타데이터)도 같다. 만드는 함수가 올린 `ConnectorError`가 설정이 틀렸다는
`invalid_config`이면 그 사유만 들어 새로 올린다. 만들 때 낼 수 있는 사유는 이 하나뿐이라 다른 사유는
계약을 어긴 것이고 불러오다 깨진 것과 같이 `ConnectorUnavailableError`로 알린다.

서버가 요청 안에서 부르는 확인 셋도 이 레지스트리가 맡는다. 서버 경로 원천의 폴더 확인
(`locate_folder`), 이미 있는 원천의 폴더 살펴보기(`survey_folders`), 연결 확인
(`check_connection`)이다. 셋 모두 커넥터 호출 장치를 지나고 한도는 `REQUEST_CALL_TIMEOUT_SECONDS`
다. 한도를 넘긴 호출은 취소하지 않고 둔 채 그 호출을 기억해 같은 설정의 다음 호출을 막는다.
커넥터를 만드는 호출(`create`)은 이 한도 밖이고 이벤트 루프 위에서 돈다. 설치처가 만든 커넥터의
만드는 함수가 원천에 닿는 것은 인터페이스가 금지하고, 내장 서버 경로 커넥터는 닿지 않는다.

로그에는 커넥터의 이름과 인터페이스 버전, 예외의 종류 이름만 남긴다. 설치처가 만든 커넥터의 예외
글에는 토큰이나 연결 문자열이 섞일 수 있고 원천의 설정에는 폴더 이름이 든다(원칙 V).
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Iterable, Mapping, Sequence
from importlib.metadata import EntryPoint, entry_points
from typing import Final

from rag_engine.adapters.connectors import server_path
from rag_engine.adapters.connectors.guard import ConnectorCallGuard
from rag_engine.adapters.log_format import log_event
from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    SERVER_PATH_CONNECTOR,
    Connector,
    ConnectorBrokenError,
    ConnectorCallBlockedError,
    ConnectorCallKind,
    ConnectorCallTimedOutError,
    ConnectorError,
    ConnectorFactory,
    ConnectorFailureReason,
    ConnectorUnavailableError,
    FetchedItem,
    FolderLocation,
    FolderTarget,
    ListedItem,
    SourceReader,
)
from rag_engine.domain.entities import JsonValue

logger = logging.getLogger(__name__)

CONNECTOR_ENTRY_POINT_GROUP: Final = "rag_engine.connectors"
# 서버가 요청 안에서 하는 폴더 확인과 연결 확인의 한도(사용자 선택. source-sync 명세 "서버 경로
# 커넥터와 원천 폴더"의 폴더 확인 한도 항목). 시험은 생성자 인자로 짧은 값을 준다.
REQUEST_CALL_TIMEOUT_SECONDS: Final = 10.0


def _discover_entry_points() -> Iterable[EntryPoint]:
    return entry_points(group=CONNECTOR_ENTRY_POINT_GROUP)


def _major(semver: str) -> str:
    return semver.partition(".")[0]


class _GuardedReader:
    """커넥터의 `list()`와 `fetch`를 호출 장치에 태운다(`SourceReader`). 커넥터가 인터페이스에 없는
    예외를 내면 `ConnectorBrokenError`로 바꾸고 로그에 예외의 종류 이름만 남긴다. 커넥터의 예외
    글에는 토큰이나 연결 문자열이 섞일 수 있다(원칙 V)."""

    def __init__(
        self,
        guard: ConnectorCallGuard,
        connector: Connector,
        name: str,
        config: Mapping[str, JsonValue],
        source: str,
        timeout_seconds: float,
    ) -> None:
        self._guard = guard
        self._connector = connector
        self._name = name
        self._config = config
        self._source = source
        self._timeout_seconds = timeout_seconds

    async def list(self) -> AsyncIterator[ListedItem]:
        try:
            # `list`는 일반 함수로 선언돼 있어, 반복자를 돌려주기 전에 원천을 부르거나 예외를 올릴
            # 수도 있다. 그래서 반복자를 만드는 일도 `fetch`처럼 장치의 첫 호출로 태운다.
            items = await self._guard.call(
                connector=self._name,
                config=self._config,
                kind=ConnectorCallKind.LIST,
                start=self._open_iterator,
                timeout_seconds=self._timeout_seconds,
                source=self._source,
            )
            async for item in self._guard.iterate(
                connector=self._name,
                config=self._config,
                items=items,
                timeout_seconds=self._timeout_seconds,
                source=self._source,
            ):
                yield item
        except _PASSED_THROUGH:
            raise
        except Exception as error:  # 설치처의 커넥터가 어떻게 깨져도 같은 오류로 알린다
            self._log_broken(ConnectorCallKind.LIST, error)
            raise ConnectorBrokenError from None

    async def _open_iterator(self) -> AsyncIterator[ListedItem]:
        return aiter(self._connector.list())

    async def fetch(self, key: str) -> FetchedItem:
        try:
            return await self._guard.call(
                connector=self._name,
                config=self._config,
                kind=ConnectorCallKind.FETCH,
                start=lambda: self._connector.fetch(key),
                timeout_seconds=self._timeout_seconds,
                source=self._source,
            )
        except _PASSED_THROUGH:
            raise
        except Exception as error:
            self._log_broken(ConnectorCallKind.FETCH, error)
            raise ConnectorBrokenError from None

    def _log_broken(self, kind: ConnectorCallKind, error: Exception) -> None:
        log_event(
            logger,
            "connector_call_failed",
            level=logging.WARNING,
            connector=self._name,
            kind=kind.value,
            exception_type=type(error).__name__,
        )


_PASSED_THROUGH: Final = (
    ConnectorError,
    ConnectorCallTimedOutError,
    ConnectorCallBlockedError,
    asyncio.CancelledError,
)


class EntryPointConnectorRegistry:
    """`ConnectorRegistry`의 구현. `create`를 부를 때마다 entry point를 읽고 캐시하지 않는다.
    읽는 데 드는 시간은 재지 않았다. 동기화 작업은 한 번에 커넥터를 하나만 만들고, 색인 작업은
    원본을 읽을 때 문서마다 한 번 만든다. 색인 작업이 몰리면 이 호출이 잦아진다. 시험은 읽는
    함수를 바꿔 끼운다."""

    def __init__(
        self,
        discover: Callable[[], Iterable[EntryPoint]] | None = None,
        *,
        guard: ConnectorCallGuard | None = None,
        timeout_seconds: float = REQUEST_CALL_TIMEOUT_SECONDS,
    ) -> None:
        self._discover = discover if discover is not None else _discover_entry_points
        self._guard = guard if guard is not None else ConnectorCallGuard()
        self._timeout_seconds = timeout_seconds

    async def locate_folder(self, name: str, config: Mapping[str, JsonValue]) -> FolderLocation:
        if name != SERVER_PATH_CONNECTOR:
            raise ConnectorUnavailableError
        return await self._guarded_folder(name, config, source=None)

    async def survey_folders(self, targets: Sequence[FolderTarget]) -> list[FolderLocation | None]:
        return list(await asyncio.gather(*(self._survey(target) for target in targets)))

    async def check_connection(
        self, name: str, config: Mapping[str, JsonValue], source: str
    ) -> None:
        connector = self.create(name, config)
        unexpected: Exception | None = None
        try:
            await self._guard.call(
                connector=name,
                config=config,
                kind=ConnectorCallKind.CHECK,
                start=connector.check,
                timeout_seconds=self._timeout_seconds,
                source=source,
            )
        except (ConnectorError, ConnectorCallTimedOutError, ConnectorCallBlockedError):
            raise
        except Exception as error:  # 설치처의 커넥터가 어떻게 깨져도 같은 오류로 알린다
            unexpected = error
        if unexpected is not None:
            log_event(
                logger,
                "connector_call_failed",
                level=logging.WARNING,
                connector=name,
                kind=ConnectorCallKind.CHECK.value,
                exception_type=type(unexpected).__name__,
            )
            raise ConnectorBrokenError

    def open_reader(
        self,
        name: str,
        config: Mapping[str, JsonValue],
        *,
        source: str,
        timeout_seconds: float,
    ) -> SourceReader:
        return _GuardedReader(
            self._guard, self.create(name, config), name, config, source, timeout_seconds
        )

    async def _guarded_folder(
        self, name: str, config: Mapping[str, JsonValue], source: str | None
    ) -> FolderLocation:
        try:
            return await self._guard.call(
                connector=name,
                config=config,
                kind=ConnectorCallKind.FOLDER_CHECK,
                start=lambda: server_path.locate_folder(config),
                timeout_seconds=self._timeout_seconds,
                source=source,
            )
        except (ConnectorCallTimedOutError, ConnectorCallBlockedError):
            pass
        # 한도를 넘겼거나 같은 설정의 호출이 남아 있어 막혔다. 폴더를 읽을 수 없는 것과 같다.
        raise ConnectorError(ConnectorFailureReason.UNREADABLE)

    async def _survey(self, target: FolderTarget) -> FolderLocation | None:
        if target.connector != SERVER_PATH_CONNECTOR:
            return None
        try:
            return await self._guarded_folder(target.connector, target.config, target.source)
        except ConnectorError:
            return None

    def create(self, name: str, config: Mapping[str, JsonValue]) -> Connector:
        entry: EntryPoint | None = None
        discovery_failed = False
        try:
            entry = next((entry for entry in self._discover() if entry.name == name), None)
        except Exception as error:  # 다른 패키지의 깨진 메타데이터도 이 호출에 닿는다
            discovery_failed = True
            log_event(
                logger,
                "connector_rejected",
                level=logging.WARNING,
                connector=name,
                exception_type=type(error).__name__,
            )
        if discovery_failed:
            raise ConnectorUnavailableError
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
