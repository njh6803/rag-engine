"""서버 경로 커넥터가 읽는 폴더에서 권한 오류를 일으키는 시험 도우미.

시험을 도는 사용자가 root 일 수 있고 Windows 는 폴더의 권한 비트가 다르다. 그래서 `chmod`로
폴더를 만들지 않고, 커넥터가 폴더를 읽는 호출을 바꿔 끼워 같은 결과를 낸다. 서버가 같은
프로세스에서 도는 시험(`tests/conftest.py`의 `run_server`)과 커넥터를 바로 부르는 시험이 함께
쓴다.
"""

import os
from collections.abc import Iterator
from types import TracebackType

import pytest

_DENIED = "권한 없음"


def refuse_listing(monkeypatch: pytest.MonkeyPatch, folder: str) -> None:
    """`folder`로 끝나는 경로와 폴더 기술자의 열거를 권한 오류로 거절한다."""
    real_scandir = os.scandir

    def scandir(path: str | int) -> Iterator[os.DirEntry[str]]:
        if isinstance(path, int) or os.fsdecode(path).replace("\\", "/").endswith(folder):
            raise PermissionError(13, _DENIED)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)


class _Unreadable:
    """이름은 보이지만 항목의 정보를 읽을 수 없는 항목."""

    def __init__(self, name: str) -> None:
        self.name = name

    def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
        raise PermissionError(13, _DENIED)

    def is_junction(self) -> bool:
        return False


class _Listing:
    """`with os.scandir(...) as iterator`가 쓰는 모양. 항목은 `_Unreadable` 하나다."""

    def __enter__(self) -> Iterator[_Unreadable]:
        return iter([_Unreadable("항목.docx")])

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def hide_entry_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """폴더를 열거하면 이름은 나오지만 항목의 정보는 읽을 수 없게 한다. 읽기 권한은 있고 탐색
    권한이 없는 폴더의 모양이다(실제 열거는 항목마다 정보를 읽는다)."""
    real_stat = os.stat

    def scandir(path: str | int) -> _Listing:
        return _Listing()

    def stat(
        path: str | bytes | int, *, dir_fd: int | None = None, follow_symlinks: bool = True
    ) -> os.stat_result:
        if dir_fd is not None:
            raise PermissionError(13, _DENIED)
        return real_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "scandir", scandir)
    monkeypatch.setattr(os, "stat", stat)
