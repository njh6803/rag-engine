"""서버 경로 커넥터 `server_path`. 부모 폴더(`RAG_SOURCES_DIR`, 기본 `/sources`) 아래 하위 폴더
하나를 열거하고 파일을 받는다(source-sync 명세 "서버 경로 커넥터와 원천 폴더", ADR 0021).

설정은 `folder` 하나이고 부모 폴더 기준의 상대 경로다. 만드는 함수는 설정의 모양만 보고 파일
시스템을 부르지 않는다. 부모 폴더와 크기 상한(`RAG_MAX_UPLOAD_MB`)은 만들 때 프로세스 환경 변수에서
읽는다. 만드는 함수가 파일을 부르지 않으므로 설정 객체와 달리 `.env` 파일은 읽지 않는다(컨테이너는
환경 변수로 받는다). 상한이 틀린 값이면 기본값으로 읽는다(서버와 작업자는 그 값으로는 뜨지 않는다).

**확인과 열기는 한 동작이다.** 경로를 먼저 확인하고 나중에 같은 경로를 다시 여는 구현은 그 사이에
원천 폴더에 쓸 수 있는 쪽이 토막 하나를 심볼릭 링크로 바꿔 놓으면 부모 폴더 밖의 파일을 읽는다.
그래서 `NOFOLLOW_OPEN_AVAILABLE`이 참인 운영체제(제품 이미지의 리눅스)에서는 부모 폴더를 연 자리에서
시작해 토막마다 링크를 따르지 않는 열기(`O_NOFOLLOW`와 연 폴더 기준의 열기)로 내려간다. 마지막
토막은 막히지 않는 열기(`O_NONBLOCK`)를 더해 연다. 쓰는 쪽이 없는 FIFO는 읽기로 여는 호출이 돌아오지
않아, 연 파일로 종류를 확인하기 전에 멈추기 때문이다. 이 열기가 없는 운영체제(개발 기계의
Windows)에서는 토막마다 `lstat`으로 확인한 뒤 여는 길로 돌고 그 틈을 닫지 못한다. `O_NONBLOCK`을
더하는 까닭은 프로브 `.scratch/source-sync/probes/fifo-open/`의 A, B, C가 쟀고, 개발 기계에 그
열기가 없다는 것은 명세가 손으로 본 것이다("서버 경로 커넥터와 원천 폴더"의 확인과 열기 항목).

**파일 시스템을 부르는 일은 호출마다 새로 띄운 daemon 스레드 하나에서 한다.** 끊긴 공유 폴더에서는
읽기가 돌아오지 않을 수 있고, 이벤트 루프의 기본 스레드 풀이나 원천끼리 나눠 쓰는 풀을 차지하면
검색과 다른 원천의 색인이 멈춘다. daemon 스레드는 프로세스가 내려가는 것을 붙잡지 않는다. 같은
설정의 호출끼리도 스레드를 나눠 쓰지 않는다(명세 "동기화의 차례"). 한도를 걸고 돌아오지 않는 호출을
기억하는 일은 이 커넥터가 아니라 부르는 쪽의 몫이다.

로그에는 폴더와 파일의 이름을 싣지 않고 목록에 넣지 않은 것의 종류별 개수만 남긴다(원칙 V).
"""

import asyncio
import errno
import logging
import os
import stat
import threading
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Final, Literal, Protocol

from rag_engine.adapters.log_format import log_event
from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    ConnectorError,
    ConnectorFailureReason,
    FetchedItem,
    ListedItem,
)
from rag_engine.domain.entities import JsonValue
from rag_engine.domain.media_types import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

_DEFAULT_SOURCES_DIR: Final = "/sources"
# `adapters/settings.py`의 `max_upload_mb` 기본값과 같다(시험이 맞는지 본다).
DEFAULT_MAX_UPLOAD_MB: Final = 100
_BYTES_PER_MB: Final = 1024 * 1024
_READ_CHUNK_BYTES: Final = _BYTES_PER_MB

# 운영체제마다 있고 없는 플래그들이다. `O_BINARY`는 Windows에만 있고 나머지는 Windows에 없다. 없으면
# 0이라 플래그에 더해도 아무것도 바뀌지 않는다.
_O_RDONLY: Final[int] = os.O_RDONLY
_O_NOFOLLOW: Final[int] = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY: Final[int] = getattr(os, "O_DIRECTORY", 0)
_O_NONBLOCK: Final[int] = getattr(os, "O_NONBLOCK", 0)
_O_CLOEXEC: Final[int] = getattr(os, "O_CLOEXEC", 0)
_O_BINARY: Final[int] = getattr(os, "O_BINARY", 0)

# 링크를 따르지 않고 연 폴더 기준으로 내려가는 열기가 이 운영체제에 있는가.
NOFOLLOW_OPEN_AVAILABLE: Final = (
    _O_NOFOLLOW != 0
    and _O_DIRECTORY != 0
    and _O_NONBLOCK != 0
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
    and os.scandir in os.supports_fd
)

# 운영체제가 역슬래시를 경로 구분자로 읽으면(Windows) 키에서 거절한다. 설정은 어느 운영체제에서나
# 역슬래시를 거절한다. 그때는 키와 설정 모두 쌍점도 거절한다(`C:이름`이 부모 폴더를 버리고
# 드라이브를 가리킨다).
_BACKSLASH_IS_SEPARATOR: Final = "\\" in (os.sep, os.altsep)
_FORBIDDEN_SEGMENTS: Final = frozenset({"", ".", ".."})
# 링크를 따르지 않는 열기가 이 오류로 실패하면 링크이거나 폴더가 아니거나 열 수 없는 종류다.
# 리눅스에서 쟀더니 파일 링크는 `ELOOP`, 폴더 링크와 폴더가 아닌 것은 `ENOTDIR`, 소켓은 `ENXIO`였다.
# `EMLINK`는 일부 BSD가 링크에 내는 오류라 넣었고 재지 않았다.
_REJECTED_ERRNOS: Final = frozenset({errno.ELOOP, errno.ENOTDIR, errno.EMLINK, errno.ENXIO})

type _Kind = Literal["file", "dir", "link", "other"]


@dataclass(frozen=True, slots=True)
class _Entry:
    name: str
    kind: _Kind
    size: int
    mtime_ns: int

    @property
    def change_marker(self) -> str:
        """변경 확인값. 수정 시각(나노초 정수)과 크기를 쌍점으로 이은 글이다."""
        return f"{self.mtime_ns}:{self.size}"


@dataclass(frozen=True, slots=True)
class _FileContent:
    data: bytes
    mtime_ns: int


@dataclass(slots=True)
class _SkipCounts:
    symlinks: int = 0
    not_regular: int = 0
    undecodable_names: int = 0


class _Directory(Protocol):
    """연 폴더 하나. 두 구현이 같은 얼개를 갖는다(링크를 따르지 않는 열기, 확인한 뒤 여는 길).

    열기가 낸 `OSError` 가운데 링크이거나 폴더가 아니거나 없는 것은 `ConnectorError`로 옮겨 올리고,
    그 밖의 `OSError`는 그대로 올린다. 호출 하나를 감싸는 쪽이 그것을 `unreadable`로 옮긴다."""

    def child_dir(self, name: str, missing: ConnectorFailureReason) -> "_Directory":
        """하위 폴더를 연다. 링크이거나 폴더가 아니면 `rejected`, 없으면 `missing`이다."""
        ...

    def scan(self) -> Sequence[_Entry]:
        """이 폴더의 항목을 이름 순으로 낸다. 그 사이 사라진 항목은 뺀다."""
        ...

    def read_file(self, name: str, limit: int) -> _FileContent:
        """보통 파일을 `limit` 바이트까지 읽는다. 링크이거나 보통 파일이 아니면 `rejected`,
        없으면 `not_found`, 넘으면 끝까지 읽지 않고 `too_large`다."""
        ...

    def close(self) -> None: ...


def _failure_of(error: OSError, missing: ConnectorFailureReason) -> ConnectorFailureReason | None:
    """열기가 낸 오류를 사유로 옮긴다. 옮길 수 없는 오류는 `None`이고 `unreadable`로 다룬다."""
    if error.errno in _REJECTED_ERRNOS:
        return ConnectorFailureReason.REJECTED
    if error.errno == errno.ENOENT:
        return missing
    return None


def _kind_of(info: os.stat_result) -> _Kind:
    if stat.S_ISLNK(info.st_mode):
        return "link"
    if stat.S_ISDIR(info.st_mode):
        return "dir"
    if stat.S_ISREG(info.st_mode):
        return "file"
    return "other"


def _entry_of(name: str, kind: _Kind, info: os.stat_result) -> _Entry:
    return _Entry(name=name, kind=kind, size=info.st_size, mtime_ns=info.st_mtime_ns)


def _read_regular(descriptor: int, limit: int) -> _FileContent:
    """연 파일이 보통 파일인지 그 연 파일로 보고 읽는다. 닫는다. 크기가 `limit`을 넘는지 보려고
    `limit`보다 한 바이트 더 읽다가 넘으면 멈추고 `too_large`로 알린다(읽는 도중 자란 파일도
    잡는다)."""
    failure: ConnectorFailureReason | None = None
    data = b""
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            failure = ConnectorFailureReason.REJECTED
        elif info.st_size > limit:
            failure = ConnectorFailureReason.TOO_LARGE
        else:
            chunks: tuple[bytes, ...] = ()
            remaining = limit + 1
            while remaining > 0:
                chunk = os.read(descriptor, min(remaining, _READ_CHUNK_BYTES))
                if not chunk:
                    break
                chunks += (chunk,)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if len(data) > limit:
                failure = ConnectorFailureReason.TOO_LARGE
    finally:
        os.close(descriptor)
    if failure is not None:
        raise ConnectorError(failure)
    return _FileContent(data=data, mtime_ns=info.st_mtime_ns)


class _FdDirectory:
    """열린 폴더 기술자(fd)를 쥔 폴더. 이름은 이 폴더를 기준으로, 링크를 따르지 않고 연다."""

    def __init__(self, descriptor: int) -> None:
        self._descriptor = descriptor

    @classmethod
    def open_parent(cls, path: str) -> "_FdDirectory":
        # 부모 폴더는 운영자가 정한 자리라 링크여도 따른다. 링크를 막는 것은 그 아래부터다.
        return cls(os.open(path, _O_RDONLY | _O_DIRECTORY | _O_CLOEXEC))

    def child_dir(self, name: str, missing: ConnectorFailureReason) -> _Directory:
        flags = _O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
        try:
            descriptor = os.open(name, flags, dir_fd=self._descriptor)
        except OSError as error:
            failure = _failure_of(error, missing)
            if failure is None:
                raise
        else:
            return _FdDirectory(descriptor)
        # 예외 글에 경로가 실리지 않게 `except` 밖에서 올린다.
        raise ConnectorError(failure)

    def scan(self) -> Sequence[_Entry]:
        with os.scandir(self._descriptor) as iterator:
            names = sorted(entry.name for entry in iterator)
        entries: list[_Entry] = []
        for name in names:
            try:
                info = os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            entries.append(_entry_of(name, _kind_of(info), info))
        return tuple(entries)

    def read_file(self, name: str, limit: int) -> _FileContent:
        flags = _O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK | _O_CLOEXEC
        try:
            descriptor = os.open(name, flags, dir_fd=self._descriptor)
        except OSError as error:
            failure = _failure_of(error, ConnectorFailureReason.NOT_FOUND)
            if failure is None:
                raise
        else:
            return _read_regular(descriptor, limit)
        raise ConnectorError(failure)

    def close(self) -> None:
        os.close(self._descriptor)


def _is_link(path: str, info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or os.path.isjunction(path)


class _PathDirectory:
    """경로를 쥔 폴더. 링크를 따르지 않는 열기가 없는 운영체제에서 확인한 뒤 여는 길로 돈다."""

    def __init__(self, path: str) -> None:
        self._path = path

    @classmethod
    def open_parent(cls, path: str) -> "_PathDirectory":
        if not stat.S_ISDIR(os.stat(path).st_mode):
            raise ConnectorError(ConnectorFailureReason.UNREADABLE)
        return cls(path)

    def child_dir(self, name: str, missing: ConnectorFailureReason) -> _Directory:
        path = os.path.join(self._path, name)
        failure: ConnectorFailureReason | None = None
        try:
            info = os.lstat(path)
        except OSError as error:
            failure = _failure_of(error, missing)
            if failure is None:
                raise
        else:
            if _is_link(path, info) or not stat.S_ISDIR(info.st_mode):
                failure = ConnectorFailureReason.REJECTED
            else:
                return _PathDirectory(path)
        raise ConnectorError(failure)

    def scan(self) -> Sequence[_Entry]:
        entries: list[_Entry] = []
        with os.scandir(self._path) as iterator:
            for entry in sorted(iterator, key=lambda candidate: candidate.name):
                try:
                    info = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                kind = "link" if entry.is_junction() else _kind_of(info)
                entries.append(_entry_of(entry.name, kind, info))
        return tuple(entries)

    def read_file(self, name: str, limit: int) -> _FileContent:
        path = os.path.join(self._path, name)
        failure: ConnectorFailureReason | None = None
        try:
            info = os.lstat(path)
        except OSError as error:
            failure = _failure_of(error, ConnectorFailureReason.NOT_FOUND)
            if failure is None:
                raise
        else:
            if _is_link(path, info) or not stat.S_ISREG(info.st_mode):
                failure = ConnectorFailureReason.REJECTED
            else:
                return _read_regular(os.open(path, _O_RDONLY | _O_BINARY), limit)
        raise ConnectorError(failure)

    def close(self) -> None:
        return None


def _open_parent(path: str) -> _Directory:
    if NOFOLLOW_OPEN_AVAILABLE:
        return _FdDirectory.open_parent(path)
    return _PathDirectory.open_parent(path)


def _descend(
    start: _Directory, segments: Sequence[str], missing: ConnectorFailureReason
) -> _Directory:
    """`start`에서 토막마다 한 칸씩 내려가 마지막 폴더를 낸다. 지나온 폴더는 닫는다."""
    current = start
    try:
        for segment in segments:
            child = current.child_dir(segment, missing)
            current.close()
            current = child
    except BaseException:
        current.close()
        raise
    return current


def _is_utf8(name: str) -> bool:
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _folder_segments(config: Mapping[str, JsonValue]) -> tuple[str, ...]:
    """설정의 `folder`를 토막으로 나눈다. 모양이 틀리면 `invalid_config`다."""
    folder = config.get("folder")
    if (
        not isinstance(folder, str)
        or not _is_utf8(folder)
        or "\0" in folder
        or "\\" in folder
        or (_BACKSLASH_IS_SEPARATOR and ":" in folder)
        or folder.startswith("/")
    ):
        raise ConnectorError(ConnectorFailureReason.INVALID_CONFIG)
    segments = tuple(folder.removesuffix("/").split("/"))
    if any(segment in _FORBIDDEN_SEGMENTS for segment in segments):
        raise ConnectorError(ConnectorFailureReason.INVALID_CONFIG)
    return segments


def _key_segments(key: str) -> tuple[str, ...]:
    """키를 토막으로 나눈다. 파일 시스템을 부르기 전에 모양이 틀린 키를 `rejected`로 거절한다."""
    segments = tuple(key.split("/"))
    if (
        not _is_utf8(key)  # UTF-8로 쓸 수 없는 이름은 `list()`가 내지 않으므로 키일 수 없다
        or "\0" in key
        or key.startswith("/")
        or (_BACKSLASH_IS_SEPARATOR and ("\\" in key or ":" in key))
        or any(segment in _FORBIDDEN_SEGMENTS for segment in segments)
    ):
        raise ConnectorError(ConnectorFailureReason.REJECTED)
    return segments


def _upload_limit_bytes() -> int:
    raw = os.environ.get("RAG_MAX_UPLOAD_MB", "")
    try:
        megabytes = int(raw) if raw else DEFAULT_MAX_UPLOAD_MB
    except ValueError:
        # 서버와 작업자는 이 값이 틀리면 뜨지 않는다. 여기까지 온 틀린 값은 기본값으로 읽는다.
        megabytes = DEFAULT_MAX_UPLOAD_MB
    return (megabytes if megabytes > 0 else DEFAULT_MAX_UPLOAD_MB) * _BYTES_PER_MB


def _as_failure(error: Exception) -> Exception:
    """스레드에서 난 예외를 호출한 쪽에 돌려줄 꼴로 옮긴다. `OSError`는 `unreadable`이고, 글을 싣지
    않는 새 예외라 경로가 든 원래 예외가 사슬에 남지 않는다."""
    if isinstance(error, OSError):
        return ConnectorError(ConnectorFailureReason.UNREADABLE)
    return error


def _post_to_loop(loop: asyncio.AbstractEventLoop, callback: Callable[[], None]) -> None:
    """스레드에서 이벤트 루프로 일을 넘긴다. 루프가 이미 닫혔으면 버린다. 늦게 돌아온 호출의 결과는
    받을 쪽이 없다."""
    try:
        loop.call_soon_threadsafe(callback)
    except RuntimeError:
        pass


def _start_thread(target: Callable[[], None]) -> None:
    threading.Thread(target=target, daemon=True, name="server-path-connector").start()


async def _call_in_thread[T](work: Callable[[], T]) -> T:
    """`work`를 새로 띄운 daemon 스레드 하나에서 돌리고 결과를 기다린다. 이벤트 루프의 기본 스레드
    풀을 쓰지 않는다. 기다리는 쪽이 취소돼도 스레드는 끝날 때까지 돈다(밖에서 끝낼 길이 없다)."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[T] = loop.create_future()

    def deliver(settle: Callable[[], None]) -> None:
        _post_to_loop(loop, settle)

    def set_result(value: T) -> None:
        if not future.done():
            future.set_result(value)

    def set_failure(failure: Exception) -> None:
        if not future.done():
            future.set_exception(failure)

    def run() -> None:
        try:
            value = work()
        except Exception as error:
            failure = _as_failure(error)
            deliver(lambda: set_failure(failure))
        else:
            deliver(lambda: set_result(value))

    _start_thread(run)
    return await future


@dataclass(frozen=True, slots=True)
class _Item:
    item: ListedItem


@dataclass(frozen=True, slots=True)
class _Failed:
    error: Exception


@dataclass(frozen=True, slots=True)
class _Done:
    counts: _SkipCounts


class _Abandoned(Exception):
    """목록을 받던 쪽이 그만둬서 걷던 스레드가 멈춘다."""


def _mime_of(key: str) -> str | None:
    return SUPPORTED_EXTENSIONS.get(PurePosixPath(key).suffix.lower())


@dataclass(frozen=True, slots=True)
class _Frame:
    """걷는 중인 폴더 하나. 이 폴더의 키 앞머리와, 아직 보지 않은 항목이다."""

    directory: _Directory
    prefix: str
    entries: Iterator[_Entry]


class _Walk:
    """원천 폴더 아래를 끝까지 걸어 보통 파일을 `emit`으로 낸다. 하위 폴더를 읽지 못하면 그 폴더를
    빼고 계속하지 않고 목록 전체를 실패시킨다(줄어든 목록으로 삭제를 반영하지 않으려는 것). 깊은
    폴더에서 재귀 한도에 걸리지 않게 명시적인 더미로 걷는다."""

    def __init__(self, root: _Directory, emit: Callable[[ListedItem], None]) -> None:
        self._root = root
        self._emit = emit
        self._stack: tuple[_Frame, ...] = ()
        self._counts = _SkipCounts()

    def run(self) -> _SkipCounts:
        """끝까지 걸어 목록에 넣지 않은 것의 개수를 낸다. 중간에 실패하면 열어 둔 폴더를 모두
        닫는다."""
        try:
            self._enter(self._root, "")
            while self._stack:
                self._step()
        except BaseException:
            for frame in self._stack:
                frame.directory.close()
            raise
        return self._counts

    def _enter(self, directory: _Directory, prefix: str) -> None:
        try:
            entries = iter(directory.scan())
        except BaseException:
            directory.close()
            raise
        self._stack += (_Frame(directory, prefix, entries),)

    def _step(self) -> None:
        """맨 위 폴더의 다음 항목 하나를 처리한다. 항목이 떨어지면 그 폴더를 닫고 더미에서 뺀다."""
        frame = self._stack[-1]
        entry = next(frame.entries, None)
        if entry is None:
            self._stack = self._stack[:-1]
            frame.directory.close()
        elif not _is_utf8(entry.name):
            self._counts.undecodable_names += 1
        elif entry.kind == "link":
            self._counts.symlinks += 1
        elif entry.kind == "other":
            self._counts.not_regular += 1
        elif entry.kind == "dir":
            child = frame.directory.child_dir(entry.name, ConnectorFailureReason.UNREADABLE)
            self._enter(child, f"{frame.prefix}{entry.name}/")
        else:
            self._emit(ListedItem(f"{frame.prefix}{entry.name}", entry.change_marker, entry.size))


class ServerPathConnector:
    """원천 폴더 하나를 읽는 커넥터. 설정으로 만들어지고 상태를 들지 않는다."""

    def __init__(self, parent: str, folder: tuple[str, ...], limit_bytes: int) -> None:
        self._parent = parent
        self._folder = folder
        self._limit_bytes = limit_bytes

    @property
    def interface_version(self) -> str:
        return CONNECTOR_INTERFACE_VERSION

    async def check(self) -> None:
        await _call_in_thread(self._check_blocking)

    async def fetch(self, key: str) -> FetchedItem:
        segments = _key_segments(key)
        content = await _call_in_thread(lambda: self._fetch_blocking(segments))
        return FetchedItem(
            data=content.data,
            mime=_mime_of(key),
            updated_at=datetime.fromtimestamp(0, UTC)
            + timedelta(microseconds=content.mtime_ns // 1000),
            metadata={},
        )

    async def list(self) -> AsyncIterator[ListedItem]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[_Item | _Failed | _Done] = asyncio.Queue()
        abandoned = threading.Event()

        def deliver(message: _Item | _Failed | _Done) -> None:
            _post_to_loop(loop, lambda: queue.put_nowait(message))

        def emit(item: ListedItem) -> None:
            if abandoned.is_set():
                raise _Abandoned
            deliver(_Item(item))

        def run() -> None:
            try:
                counts = _Walk(self._open_source_folder(), emit).run()
            except _Abandoned:
                return
            except Exception as error:
                failure = _as_failure(error)
                deliver(_Failed(failure))
            else:
                deliver(_Done(counts))

        _start_thread(run)
        try:
            while True:
                message = await queue.get()
                if isinstance(message, _Item):
                    yield message.item
                elif isinstance(message, _Failed):
                    raise message.error
                else:
                    log_event(
                        logger,
                        "server_path_list_skipped",
                        skipped_symlinks=message.counts.symlinks,
                        skipped_not_regular=message.counts.not_regular,
                        skipped_undecodable_names=message.counts.undecodable_names,
                    )
                    return
        finally:
            abandoned.set()

    def _open_source_folder(self) -> _Directory:
        """부모 폴더에서 원천 폴더까지 토막마다 확인하며 열고, 원천 폴더를 낸다."""
        return _descend(_open_parent(self._parent), self._folder, ConnectorFailureReason.UNREADABLE)

    def _check_blocking(self) -> None:
        self._open_source_folder().close()

    def _fetch_blocking(self, segments: Sequence[str]) -> _FileContent:
        directory = _descend(
            self._open_source_folder(), segments[:-1], ConnectorFailureReason.NOT_FOUND
        )
        try:
            return directory.read_file(segments[-1], self._limit_bytes)
        finally:
            directory.close()


def create_server_path_connector(config: Mapping[str, JsonValue]) -> ServerPathConnector:
    """entry point `rag_engine.connectors`의 `server_path`가 가리키는 만드는 함수. 설정의 모양만
    보고 파일 시스템을 부르지 않는다."""
    folder = _folder_segments(config)
    parent = os.environ.get("RAG_SOURCES_DIR") or _DEFAULT_SOURCES_DIR
    return ServerPathConnector(parent, folder, _upload_limit_bytes())
