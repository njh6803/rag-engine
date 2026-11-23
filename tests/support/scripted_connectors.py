"""동기화 시험이 쓰는 대본대로 움직이는 커넥터 레지스트리(명세 "Testing Decisions").

폴더 하나(`ScriptedFolder`)가 가진 파일을 시험이 마음대로 바꾸고, 레지스트리가 그 폴더를 읽는 길
(`SourceReader`)을 연다. `fetches`는 `fetch`가 불린 키를 쌓아 "읽지 않았다"를 센다. 호출 장치와
커넥터 이름 찾기는 거치지 않는다(그쪽은 레지스트리 어댑터의 시험이 본다). 여기서는 동기화가 읽는
쪽의 예외를 어떻게 옮기는지를 본다.
"""

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field

from rag_engine.domain.connectors import (
    Connector,
    ConnectorError,
    ConnectorFailureReason,
    ConnectorUnavailableError,
    FetchedItem,
    FolderLocation,
    FolderTarget,
    ListedItem,
    SourceReader,
)
from rag_engine.domain.entities import JsonValue


@dataclass(slots=True)
class ScriptedFile:
    data: bytes
    marker: str
    size: int | None = None


@dataclass(slots=True)
class ScriptedFolder:
    """폴더 안의 파일과 그 폴더가 낼 고장. 시험이 값을 바꾼다."""

    files: dict[str, ScriptedFile] = field(default_factory=lambda: dict[str, ScriptedFile]())
    fetches: list[str] = field(default_factory=lambda: list[str]())
    # 목록의 끝에서 올릴 예외. 파일을 모두 낸 뒤에 올린다.
    list_error: Exception | None = None
    # 키마다 `fetch`가 올릴 예외.
    fetch_errors: dict[str, Exception] = field(default_factory=lambda: dict[str, Exception]())
    # 같은 키를 두 번 내게 한다.
    repeat_first_key: bool = False
    # 파일을 읽는 순간에 부르는 걸이. 시험이 읽는 사이에 파일을 바꾸는 데 쓴다.
    on_fetch: Callable[[str], None] | None = None

    def put(self, key: str, data: bytes, marker: str, size: int | None = None) -> None:
        self.files[key] = ScriptedFile(data, marker, size if size is not None else len(data))


class _ScriptedReader:
    def __init__(self, folder: ScriptedFolder) -> None:
        self._folder = folder

    async def list(self) -> AsyncIterator[ListedItem]:
        folder = self._folder
        for index, (key, file) in enumerate(list(folder.files.items())):
            yield ListedItem(key=key, change_marker=file.marker, size_bytes=file.size)
            if index == 0 and folder.repeat_first_key:
                yield ListedItem(key=key, change_marker=file.marker, size_bytes=file.size)
        if folder.list_error is not None:
            raise folder.list_error

    async def fetch(self, key: str) -> FetchedItem:
        folder = self._folder
        folder.fetches.append(key)
        if folder.on_fetch is not None:
            folder.on_fetch(key)
        if key in folder.fetch_errors:
            raise folder.fetch_errors[key]
        file = folder.files.get(key)
        if file is None:
            raise ConnectorError(ConnectorFailureReason.NOT_FOUND)
        return FetchedItem(data=file.data, mime=None, updated_at=None, metadata={})


class ScriptedRegistry:
    """원천의 이름과 설정과 상관없이 같은 폴더를 연다. `unavailable`이 참이면 커넥터를 만들 수
    없다고, `invalid_config`가 참이면 저장된 설정을 커넥터가 받지 않는다고 알린다."""

    def __init__(
        self, folder: ScriptedFolder, *, unavailable: bool = False, invalid_config: bool = False
    ) -> None:
        self.folder = folder
        self.unavailable = unavailable
        self.invalid_config = invalid_config

    def create(self, name: str, config: Mapping[str, JsonValue]) -> Connector:
        raise NotImplementedError

    async def locate_folder(self, name: str, config: Mapping[str, JsonValue]) -> FolderLocation:
        raise NotImplementedError

    async def survey_folders(self, targets: Sequence[FolderTarget]) -> list[FolderLocation | None]:
        raise NotImplementedError

    def open_reader(
        self,
        name: str,
        config: Mapping[str, JsonValue],
        *,
        source: str,
        timeout_seconds: float,
    ) -> SourceReader:
        if self.unavailable:
            raise ConnectorUnavailableError
        if self.invalid_config:
            raise ConnectorError(ConnectorFailureReason.INVALID_CONFIG)
        return _ScriptedReader(self.folder)

    async def check_connection(
        self, name: str, config: Mapping[str, JsonValue], source: str
    ) -> None:
        raise NotImplementedError
