"""서버 경로 커넥터(`server_path`). 부모 폴더 아래 하위 폴더 하나를 열거하고 파일을 받는다
(source-sync 명세 "서버 경로 커넥터와 원천 폴더", ADR 0021, 티켓 04).

시험은 실제 파일 시스템으로 한다. 링크를 따르지 않는 열기(`O_NOFOLLOW`와 연 폴더 기준의 열기)는
리눅스에만 있고 이 저장소의 개발 기계(Windows)에는 없다. 그래서 운영체제마다 다른 기대는
`sys.platform` 으로 가려 단언하고, 건너뛰지 않는다(원칙 I).
"""

import asyncio
import logging
import os
import sys
import threading
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from rag_engine.adapters.connectors import server_path as server_path_module
from rag_engine.adapters.connectors.registry import EntryPointConnectorRegistry
from rag_engine.adapters.connectors.server_path import (
    DEFAULT_MAX_UPLOAD_MB,
    NOFOLLOW_OPEN_AVAILABLE,
    ServerPathConnector,
    create_server_path_connector,
)
from rag_engine.adapters.settings import Settings
from rag_engine.domain.connectors import (
    CONNECTOR_INTERFACE_VERSION,
    ConnectorError,
    ConnectorFailureReason,
    FetchedItem,
    ListedItem,
)
from rag_engine.domain.entities import JsonValue

FOLDER: Final = "규정집"
IS_WINDOWS: Final = sys.platform == "win32"
MIB: Final = 1024 * 1024
# 2023-11-14T22:13:20.123456Z. 수정 시각을 이 값으로 박아 두면 변경 확인값과 갱신 시각의 기대가
# 시험을 돌린 시각에 기대지 않는다.
KNOWN_MTIME_NS: Final = 1_700_000_000_123_456_000
KNOWN_MTIME: Final = datetime(2023, 11, 14, 22, 13, 20, 123456, tzinfo=UTC)


@pytest.fixture
def sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """부모 폴더. `RAG_SOURCES_DIR`을 이 폴더로 바꾼다. 원천 폴더는 `규정집`이다."""
    parent = tmp_path / "sources"
    parent.mkdir()
    monkeypatch.setenv("RAG_SOURCES_DIR", str(parent))
    monkeypatch.delenv("RAG_MAX_UPLOAD_MB", raising=False)
    return parent


@pytest.fixture
def folder(sources: Path) -> Path:
    path = sources / FOLDER
    path.mkdir()
    return path


def _connector(config_folder: JsonValue = FOLDER) -> ServerPathConnector:
    return create_server_path_connector({"folder": config_folder})


async def _listed(connector: ServerPathConnector) -> list[ListedItem]:
    return [item async for item in connector.list()]


async def _keys(connector: ServerPathConnector) -> list[str]:
    return sorted(item.key for item in await _listed(connector))


async def _reason_of_list(connector: ServerPathConnector) -> ConnectorFailureReason:
    with pytest.raises(ConnectorError) as raised:
        await _listed(connector)
    return raised.value.reason


async def _reason_of_fetch(connector: ServerPathConnector, key: str) -> ConnectorFailureReason:
    with pytest.raises(ConnectorError) as raised:
        await connector.fetch(key)
    return raised.value.reason


async def _reason_of_check(connector: ServerPathConnector) -> ConnectorFailureReason:
    with pytest.raises(ConnectorError) as raised:
        await connector.check()
    return raised.value.reason


def _make_fifo(path: Path) -> None:
    """이름 있는 파이프를 만든다. Windows에는 없어 부르는 쪽이 운영체제를 가려 부른다."""
    if sys.platform == "win32":
        raise AssertionError("이 운영체제에는 FIFO가 없다")
    os.mkfifo(path)


def _forbid_file_system(monkeypatch: pytest.MonkeyPatch) -> None:
    """파일 시스템을 부르면 시험이 실패하게 한다. 만드는 함수와 키 검사가 닿지 않는다는 근거다."""

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"파일 시스템을 불렀다: {args!r}")

    for name in ("open", "scandir", "stat", "lstat", "listdir", "read"):
        monkeypatch.setattr(os, name, forbidden)


# ---------- 등록과 만드는 함수 ----------


def test_이름_server_path로_entry_point에서_찾아_만든다(sources: Path) -> None:
    connector = EntryPointConnectorRegistry().create("server_path", {"folder": FOLDER})

    assert isinstance(connector, ServerPathConnector)
    assert connector.interface_version == CONNECTOR_INTERFACE_VERSION


@pytest.mark.parametrize(
    "config_folder",
    [
        "",
        "/",
        ".",
        "..",
        "a/..",
        "../a",
        "a/../b",
        "a/./b",
        "./a",
        "/절대",
        "a//b",
        "a//",
        "a\\b",
        "\\a",
        "a\0b",
        5,
        None,
        ["a"],
    ],
)
def test_폴더_설정이_틀리면_만드는_함수가_invalid_config로_알린다(
    sources: Path, config_folder: JsonValue
) -> None:
    with pytest.raises(ConnectorError) as raised:
        create_server_path_connector({"folder": config_folder})

    assert raised.value.reason is ConnectorFailureReason.INVALID_CONFIG


def test_UTF_8로_쓸_수_없는_폴더_이름은_invalid_config다(sources: Path) -> None:
    with pytest.raises(ConnectorError) as raised:
        create_server_path_connector({"folder": "깨진\ud800이름"})

    assert raised.value.reason is ConnectorFailureReason.INVALID_CONFIG


def test_쌍점이_든_폴더는_드라이브_표기를_읽는_운영체제에서만_거절한다(sources: Path) -> None:
    if IS_WINDOWS:
        with pytest.raises(ConnectorError) as raised:
            create_server_path_connector({"folder": "C:src"})
        assert raised.value.reason is ConnectorFailureReason.INVALID_CONFIG
    else:
        assert create_server_path_connector({"folder": "C:src"}).interface_version


def test_folder_칸이_없으면_invalid_config다(sources: Path) -> None:
    with pytest.raises(ConnectorError) as raised:
        create_server_path_connector({})

    assert raised.value.reason is ConnectorFailureReason.INVALID_CONFIG


def test_만드는_함수는_파일_시스템을_부르지_않는다(
    sources: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_file_system(monkeypatch)

    connector = create_server_path_connector({"folder": "없는/하위"})

    assert connector.interface_version == CONNECTOR_INTERFACE_VERSION


async def test_여러_단계_폴더와_끝의_슬래시를_받는다(sources: Path) -> None:
    nested = sources / "규정집" / "인사"
    nested.mkdir(parents=True)
    (nested / "a.pdf").write_bytes(b"1")

    assert await _keys(_connector("규정집/인사/")) == ["a.pdf"]


# ---------- 목록 ----------


async def test_목록은_하위_폴더_끝까지_걸어_상대_경로_키로_낸다(folder: Path) -> None:
    (folder / "a.pdf").write_bytes(b"1")
    (folder / "하위" / "더깊이").mkdir(parents=True)
    (folder / "하위" / "b.docx").write_bytes(b"22")
    (folder / "하위" / "더깊이" / "c.hwpx").write_bytes(b"333")

    items = {item.key: item for item in await _listed(_connector())}

    assert sorted(items) == ["a.pdf", "하위/b.docx", "하위/더깊이/c.hwpx"]
    assert [items[key].size_bytes for key in sorted(items)] == [1, 2, 3]


async def test_변경_확인값은_수정_시각_나노초와_크기를_쌍점으로_이은_글이다(folder: Path) -> None:
    path = folder / "a.pdf"
    path.write_bytes(b"12345")
    os.utime(path, ns=(KNOWN_MTIME_NS, KNOWN_MTIME_NS))

    (item,) = await _listed(_connector())

    assert item.change_marker == f"{KNOWN_MTIME_NS}:5"


async def test_한글_이름의_두_꼴은_디스크_이름_그대로_서로_다른_키가_된다(folder: Path) -> None:
    composed = unicodedata.normalize("NFC", "한글문서.pdf")
    decomposed = unicodedata.normalize("NFD", "한글문서.pdf")
    assert composed != decomposed
    (folder / composed).write_bytes("합침".encode())
    (folder / decomposed).write_bytes("풀어씀".encode())

    keys = await _keys(_connector())

    assert keys == sorted([composed, decomposed]), f"키: {keys!r}"


async def test_심볼릭_링크와_보통_파일이_아닌_것은_목록에_넣지_않는다(
    folder: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (folder / "보통.pdf").write_bytes(b"1")
    (folder / "하위").mkdir()
    (folder / "하위" / "안.pdf").write_bytes(b"2")
    outside = tmp_path / "밖.pdf"
    outside.write_bytes(b"3")
    outside_dir = tmp_path / "밖폴더"
    outside_dir.mkdir()
    (outside_dir / "밖의안.pdf").write_bytes(b"4")
    (folder / "파일링크.pdf").symlink_to(outside)
    (folder / "폴더링크").symlink_to(outside_dir, target_is_directory=True)
    special = 0
    if not IS_WINDOWS:
        _make_fifo(folder / "파이프.pdf")
        special = 1
    undecodable = 0
    if not IS_WINDOWS:
        with open(os.path.join(os.fsencode(folder), b"\xff\xfe.pdf"), "wb") as handle:
            handle.write(b"5")
        undecodable = 1

    with caplog.at_level(logging.INFO, logger=server_path_module.__name__):
        keys = await _keys(_connector())

    assert keys == ["보통.pdf", "하위/안.pdf"]
    records = [r for r in caplog.records if r.name == server_path_module.__name__]
    assert len(records) == 1, f"로그 한 줄이어야 한다: {[r.getMessage() for r in records]}"
    fields = records[0].__dict__["event_fields"]
    assert fields == {
        "skipped_symlinks": 2,
        "skipped_not_regular": special,
        "skipped_undecodable_names": undecodable,
    }


async def test_목록의_로그에는_폴더와_파일_이름을_싣지_않는다(
    folder: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (folder / "비밀문서.pdf").write_bytes(b"1")

    with caplog.at_level(logging.DEBUG, logger=server_path_module.__name__):
        await _listed(_connector())

    logged = " ".join(str(record.__dict__) for record in caplog.records)
    assert FOLDER not in logged
    assert "비밀문서" not in logged


async def test_하위_폴더를_읽지_못하면_그_폴더를_빼지_않고_목록_전체가_unreadable이다(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (folder / "a.pdf").write_bytes(b"1")
    (folder / "잠김").mkdir()
    (folder / "잠김" / "b.pdf").write_bytes(b"2")
    real_open = os.open
    real_scandir = os.scandir

    def refuse_open(path: str | os.PathLike[str], *args: int, **kwargs: int) -> int:
        if os.fsdecode(path).replace("\\", "/").endswith("잠김"):
            raise PermissionError(13, "권한 없음")
        return real_open(path, *args, **kwargs)

    def refuse_scandir(path: str):
        if path.replace("\\", "/").endswith("잠김"):
            raise PermissionError(13, "권한 없음")
        return real_scandir(path)

    def scandir_by_descriptor(path: str | int):
        return real_scandir(path) if isinstance(path, int) else refuse_scandir(path)

    monkeypatch.setattr(os, "open", refuse_open)
    monkeypatch.setattr(os, "scandir", scandir_by_descriptor)

    assert await _reason_of_list(_connector()) is ConnectorFailureReason.UNREADABLE


# ---------- 경로 확인 ----------


async def test_원천_폴더가_없으면_list와_check는_unreadable이다(sources: Path) -> None:
    connector = _connector("없는폴더")

    assert await _reason_of_list(connector) is ConnectorFailureReason.UNREADABLE
    assert await _reason_of_check(connector) is ConnectorFailureReason.UNREADABLE


async def test_부모_폴더가_없어도_unreadable이다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_SOURCES_DIR", str(tmp_path / "없는부모"))
    connector = _connector()

    assert await _reason_of_list(connector) is ConnectorFailureReason.UNREADABLE
    assert await _reason_of_check(connector) is ConnectorFailureReason.UNREADABLE


async def test_원천_폴더_자체가_링크면_rejected다(sources: Path, tmp_path: Path) -> None:
    real = tmp_path / "다른곳"
    real.mkdir()
    (real / "a.pdf").write_bytes(b"1")
    (sources / FOLDER).symlink_to(real, target_is_directory=True)
    connector = _connector()

    assert await _reason_of_list(connector) is ConnectorFailureReason.REJECTED
    assert await _reason_of_check(connector) is ConnectorFailureReason.REJECTED
    assert await _reason_of_fetch(connector, "a.pdf") is ConnectorFailureReason.REJECTED


async def test_부모에서_원천_폴더까지의_중간_토막이_링크면_rejected다(
    sources: Path, tmp_path: Path
) -> None:
    real = tmp_path / "다른곳"
    (real / "인사").mkdir(parents=True)
    (real / "인사" / "a.pdf").write_bytes(b"1")
    (sources / FOLDER).symlink_to(real, target_is_directory=True)
    connector = _connector("규정집/인사")

    assert await _reason_of_list(connector) is ConnectorFailureReason.REJECTED
    assert await _reason_of_check(connector) is ConnectorFailureReason.REJECTED
    assert await _reason_of_fetch(connector, "a.pdf") is ConnectorFailureReason.REJECTED


async def test_원천_폴더가_폴더가_아니면_rejected다(sources: Path) -> None:
    (sources / FOLDER).write_bytes("파일이다".encode())
    connector = _connector()

    assert await _reason_of_list(connector) is ConnectorFailureReason.REJECTED
    assert await _reason_of_check(connector) is ConnectorFailureReason.REJECTED


async def test_원천_폴더가_멀쩡하면_check는_아무것도_올리지_않는다(folder: Path) -> None:
    assert await _connector().check() is None


async def test_부모_폴더_바로_아래의_파일은_어느_원천에도_들지_않는다(
    sources: Path, folder: Path
) -> None:
    (sources / "README.txt").write_bytes("안내".encode())
    (folder / "a.pdf").write_bytes(b"1")

    assert await _keys(_connector()) == ["a.pdf"]


# ---------- 받기 ----------


async def test_fetch는_바이트와_확장자로_정한_MIME과_수정_시각을_낸다(folder: Path) -> None:
    path = folder / "대문자.PDF"
    path.write_bytes("%PDF-본문".encode())
    os.utime(path, ns=(KNOWN_MTIME_NS, KNOWN_MTIME_NS))

    item = await _connector().fetch("대문자.PDF")

    assert item == FetchedItem(
        data="%PDF-본문".encode(), mime="application/pdf", updated_at=KNOWN_MTIME, metadata={}
    )


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("a.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("b.hwpx", "application/hwp+zip"),
        ("c.txt", None),
        ("확장자없음", None),
    ],
)
async def test_MIME은_키의_확장자로_정하고_모르면_비운다(
    folder: Path, name: str, mime: str | None
) -> None:
    (folder / name).write_bytes(b"1")

    assert (await _connector().fetch(name)).mime == mime


async def test_하위_폴더의_파일을_키로_받는다(folder: Path) -> None:
    (folder / "하위").mkdir()
    (folder / "하위" / "b.pdf").write_bytes("안쪽".encode())

    assert (await _connector().fetch("하위/b.pdf")).data == "안쪽".encode()


async def test_없는_키는_not_found다(folder: Path) -> None:
    (folder / "하위").mkdir()
    connector = _connector()

    assert await _reason_of_fetch(connector, "없음.pdf") is ConnectorFailureReason.NOT_FOUND
    assert await _reason_of_fetch(connector, "하위/없음.pdf") is ConnectorFailureReason.NOT_FOUND
    assert await _reason_of_fetch(connector, "없는폴더/a.pdf") is ConnectorFailureReason.NOT_FOUND


async def test_받는_도중_원천_폴더가_사라졌으면_unreadable이다(sources: Path) -> None:
    assert await _reason_of_fetch(_connector(), "a.pdf") is ConnectorFailureReason.UNREADABLE


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/a.pdf",
        "a//b.pdf",
        "./a.pdf",
        "a/./b.pdf",
        "../밖.pdf",
        "하위/../../밖.pdf",
        "a\0b.pdf",
    ],
)
async def test_키_토막이_틀리면_파일_시스템을_부르지_않고_rejected다(
    folder: Path, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    connector = _connector()
    _forbid_file_system(monkeypatch)

    assert await _reason_of_fetch(connector, key) is ConnectorFailureReason.REJECTED


async def test_UTF_8로_쓸_수_없는_키는_파일_시스템을_부르지_않고_rejected다(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connector = _connector()
    _forbid_file_system(monkeypatch)

    assert await _reason_of_fetch(connector, "\ud800.pdf") is ConnectorFailureReason.REJECTED


async def test_원천_폴더_밖의_파일은_dotdot_키로도_읽지_못한다(sources: Path, folder: Path) -> None:
    (sources / "밖의파일.pdf").write_bytes("밖의 비밀".encode())

    for key in ("../밖의파일.pdf", "하위/../../밖의파일.pdf"):
        assert await _reason_of_fetch(_connector(), key) is ConnectorFailureReason.REJECTED, key


async def test_링크는_따라가지_않고_rejected다(folder: Path, tmp_path: Path) -> None:
    outside = tmp_path / "밖.pdf"
    outside.write_bytes("밖의 비밀".encode())
    (folder / "링크.pdf").symlink_to(outside)
    outside_dir = tmp_path / "밖폴더"
    outside_dir.mkdir()
    (outside_dir / "x.pdf").write_bytes("밖의 비밀".encode())
    (folder / "폴더링크").symlink_to(outside_dir, target_is_directory=True)
    connector = _connector()

    assert await _reason_of_fetch(connector, "링크.pdf") is ConnectorFailureReason.REJECTED
    assert await _reason_of_fetch(connector, "폴더링크/x.pdf") is ConnectorFailureReason.REJECTED


async def test_키가_가리키는_것이_폴더면_rejected다(folder: Path) -> None:
    (folder / "하위").mkdir()

    assert await _reason_of_fetch(_connector(), "하위") is ConnectorFailureReason.REJECTED


async def test_목록을_받은_뒤_링크로_바뀐_파일은_받지_않고_rejected다(
    folder: Path, tmp_path: Path
) -> None:
    (folder / "a.pdf").write_bytes(b"1")
    connector = _connector()
    (item,) = await _listed(connector)
    outside = tmp_path / "밖.pdf"
    outside.write_bytes("밖의 비밀".encode())
    (folder / "a.pdf").unlink()
    (folder / "a.pdf").symlink_to(outside)

    assert await _reason_of_fetch(connector, item.key) is ConnectorFailureReason.REJECTED


async def test_역슬래시는_운영체제가_구분자로_읽을_때만_거절한다(
    folder: Path, sources: Path
) -> None:
    (sources / "밖의파일.pdf").write_bytes("밖의 비밀".encode())
    connector = _connector()
    if IS_WINDOWS:
        for key in ("a\\..\\..\\밖의파일.pdf", "C:밖의파일.pdf"):
            assert await _reason_of_fetch(connector, key) is ConnectorFailureReason.REJECTED, key
        return
    (folder / "annual\\2024.pdf").write_bytes(b"1")

    assert await _keys(connector) == ["annual\\2024.pdf"]
    assert (await connector.fetch("annual\\2024.pdf")).data == b"1"


async def test_상한을_넘는_파일은_끝까지_읽지_않고_too_large다(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_MAX_UPLOAD_MB", "1")
    (folder / "딱맞음.pdf").write_bytes(b"0" * MIB)
    (folder / "넘침.pdf").write_bytes(b"0" * (MIB + 1))
    connector = _connector()
    read_sizes: list[int] = []
    real_read = os.read

    def counting_read(descriptor: int, length: int) -> bytes:
        data = real_read(descriptor, length)
        read_sizes.append(len(data))
        return data

    monkeypatch.setattr(os, "read", counting_read)

    assert await _reason_of_fetch(connector, "넘침.pdf") is ConnectorFailureReason.TOO_LARGE
    assert sum(read_sizes) == 0, f"상한을 넘는 파일을 읽었다: {sum(read_sizes)}바이트"
    assert len((await connector.fetch("딱맞음.pdf")).data) == MIB


async def test_읽는_도중_자라_상한을_넘은_파일도_too_large다(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_MAX_UPLOAD_MB", "1")
    (folder / "자람.pdf").write_bytes(b"0" * (MIB + 1))
    real_fstat = os.fstat

    def stale_fstat(descriptor: int) -> os.stat_result:
        real = real_fstat(descriptor)
        # 크기를 확인한 뒤에 파일이 자란 장면: 확인 때는 0바이트였다고 답한다.
        return os.stat_result(
            (
                real.st_mode,
                real.st_ino,
                real.st_dev,
                real.st_nlink,
                real.st_uid,
                real.st_gid,
                0,
                int(real.st_atime),
                int(real.st_mtime),
                int(real.st_mtime),
            )
        )

    monkeypatch.setattr(os, "fstat", stale_fstat)

    assert await _reason_of_fetch(_connector(), "자람.pdf") is ConnectorFailureReason.TOO_LARGE


async def test_부모_폴더_환경_변수가_없으면_sources를_연다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAG_SOURCES_DIR", raising=False)
    opened: list[str] = []

    def record_and_fail(path: str | os.PathLike[str], *args: object, **kwargs: object) -> object:
        opened.append(os.fspath(path))
        raise FileNotFoundError(2, "없음")

    monkeypatch.setattr(os, "open", record_and_fail)
    monkeypatch.setattr(os, "stat", record_and_fail)

    assert await _reason_of_check(_connector()) is ConnectorFailureReason.UNREADABLE
    assert opened[:1] == ["/sources"]


@pytest.mark.parametrize("value", ["abc", "0", "-5", ""])
async def test_틀린_상한_값은_기본값으로_읽는다(
    folder: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("RAG_MAX_UPLOAD_MB", value)
    (folder / "a.pdf").write_bytes(b"0" * (2 * MIB))

    assert len((await _connector().fetch("a.pdf")).data) == 2 * MIB


def test_상한의_기본값은_설정_객체의_기본값과_같다() -> None:
    assert Settings.model_fields["max_upload_mb"].default == DEFAULT_MAX_UPLOAD_MB


# ---------- 파일 시스템을 부르는 스레드 ----------


def _forbid_default_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """이벤트 루프의 기본 스레드 풀(`run_in_executor`, `asyncio.to_thread`)로 일을 넘기면
    실패한다."""

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("이벤트 루프의 기본 스레드 풀을 썼다")

    monkeypatch.setattr(asyncio.get_running_loop(), "run_in_executor", forbidden)


def _record_calling_threads(monkeypatch: pytest.MonkeyPatch) -> list[threading.Thread]:
    seen: list[threading.Thread] = []

    def wrap[**P, T](original: Callable[P, T]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            seen.append(threading.current_thread())
            return original(*args, **kwargs)

        return wrapper

    for name in ("open", "scandir", "stat", "lstat", "read"):
        monkeypatch.setattr(os, name, wrap(getattr(os, name)))
    return seen


async def test_호출은_새로_띄운_daemon_스레드_하나에서_돌고_기본_풀을_쓰지_않는다(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (folder / "하위").mkdir()
    (folder / "하위" / "a.pdf").write_bytes(b"1")
    (folder / "b.pdf").write_bytes(b"2")
    connector = _connector()
    _forbid_default_pool(monkeypatch)
    caller = threading.current_thread()
    seen = _record_calling_threads(monkeypatch)

    await _listed(connector)
    list_threads = list(seen)
    seen.clear()
    await connector.fetch("하위/a.pdf")
    fetch_threads = list(seen)
    seen.clear()
    await connector.check()
    check_threads = list(seen)

    for name, threads in (
        ("list", list_threads),
        ("fetch", fetch_threads),
        ("check", check_threads),
    ):
        distinct = set(threads)
        assert len(distinct) == 1, f"{name} 한 번이 스레드 {len(distinct)}개를 썼다"
        (thread,) = distinct
        assert thread is not caller, f"{name}이 이벤트 루프의 스레드에서 돌았다"
        assert thread.daemon, f"{name}의 스레드가 daemon이 아니다"
    assert len({*list_threads, *fetch_threads, *check_threads}) == 3, "호출끼리 스레드를 나눠 썼다"


async def test_같은_설정의_호출끼리도_스레드를_나눠_쓰지_않는다(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (folder / "a.pdf").write_bytes(b"1")
    connector = _connector()
    twin = _connector()
    seen = _record_calling_threads(monkeypatch)

    await asyncio.gather(connector.fetch("a.pdf"), twin.fetch("a.pdf"))
    await connector.fetch("a.pdf")
    await connector.fetch("a.pdf")

    assert len(set(seen)) == 4, f"스레드 {len(set(seen))}개로 호출 넷을 처리했다"


# ---------- 확인과 열기는 한 동작 ----------


def test_링크를_따르지_않는_열기는_Windows_밖에서만_쓸_수_있다() -> None:
    # 개발 기계(Windows)에는 없어 확인한 뒤 여는 길로 돈다. 제품 이미지는 리눅스라 늘 앞의 길이다.
    assert NOFOLLOW_OPEN_AVAILABLE is (sys.platform != "win32")


async def test_목록을_받은_뒤_FIFO로_바뀐_키의_fetch는_기다리지_않고_거절한다(folder: Path) -> None:
    (folder / "a.pdf").write_bytes(b"1")
    connector = _connector()
    (item,) = await _listed(connector)
    if IS_WINDOWS:
        # FIFO가 없는 운영체제에서는 보통 파일이 아닌 것(폴더)으로 바뀐 경우를 같은 길로 본다.
        (folder / "a.pdf").unlink()
        (folder / "a.pdf").mkdir()
    else:
        (folder / "a.pdf").unlink()
        _make_fifo(folder / "a.pdf")

    reason = await asyncio.wait_for(_reason_of_fetch(connector, item.key), timeout=10)

    assert reason is ConnectorFailureReason.REJECTED


async def test_하위_폴더를_링크로_바꿔치는_경쟁에서도_밖의_내용을_읽지_않는다(
    sources: Path, folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inside_dir = folder / "하위"
    inside_dir.mkdir()
    (inside_dir / "x.pdf").write_bytes("안의 내용".encode())
    outside = tmp_path / "밖"
    outside.mkdir()
    (outside / "x.pdf").write_bytes("밖의 비밀".encode())
    if IS_WINDOWS:
        # 이 길은 확인한 뒤 여는 길이라 틈이 있다(명세가 적은 대가). 경쟁으로 단언하지 않고,
        # fetch가 열기 전에 토막마다 `os.lstat`으로 확인하는 길로 도는지를 본다.
        assert NOFOLLOW_OPEN_AVAILABLE is False
        checked: list[str] = []
        real_lstat = os.lstat

        def recording_lstat(path: str | os.PathLike[str]) -> os.stat_result:
            checked.append(os.fspath(path))
            return real_lstat(path)

        monkeypatch.setattr(os, "lstat", recording_lstat)
        assert (await _connector().fetch("하위/x.pdf")).data == "안의 내용".encode()
        assert any(path.endswith("하위") for path in checked), checked
        return
    parked = folder / "보관"
    link = folder / "링크"
    link.symlink_to(outside, target_is_directory=True)
    stop = threading.Event()

    def swap() -> None:
        while not stop.is_set():
            os.rename(inside_dir, parked)
            os.rename(link, inside_dir)  # 하위 = 밖을 가리키는 링크
            os.rename(inside_dir, link)
            os.rename(parked, inside_dir)  # 하위 = 진짜 폴더

    swapper = threading.Thread(target=swap, daemon=True)
    connector = _connector()
    contents: set[bytes] = set()
    swapper.start()
    try:
        for _ in range(1500):
            try:
                item = await connector.fetch("하위/x.pdf")
            except ConnectorError:
                continue
            contents.add(item.data)
    finally:
        stop.set()
        swapper.join(timeout=10)

    assert contents <= {"안의 내용".encode()}, f"밖의 내용을 읽었다: {contents!r}"
    assert contents, "한 번도 읽지 못해 경쟁을 본 것이 아니다"
