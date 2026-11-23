"""서버 경로 커넥터의 폴더 확인(source-sync 티켓 06, 명세 "서버 경로 커넥터와 원천 폴더").

폴더 찾기와 경로 확인은 커넥터 인터페이스 밖에서 서버가 부른다. 적은 글자 그대로 찾고, 없으면 NFC로
맞춘 이름이 같은 폴더가 하나뿐일 때만 그 폴더로 본다. 결과는 디스크의 이름과 지나온 폴더의 열쇠다.
`check()`는 폴더를 열고 첫 항목을 읽어 본다.
"""

import os
import unicodedata
from pathlib import Path

import pytest
from tests.support.server_path_faults import hide_entry_info, refuse_listing

from rag_engine.adapters.connectors.server_path import (
    create_server_path_connector,
    locate_folder,
)
from rag_engine.domain.connectors import ConnectorError, ConnectorFailureReason, FolderId

FOLDER = "규정집"


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sources"
    path.mkdir()
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


def _identity(path: Path) -> FolderId:
    info = os.stat(path)
    return (info.st_dev, info.st_ino)


async def _reason_of_locate(folder: str) -> ConnectorFailureReason:
    with pytest.raises(ConnectorError) as raised:
        await locate_folder({"folder": folder})
    return raised.value.reason


async def test_적은_글자_그대로_있는_폴더는_그_이름과_실제_폴더의_열쇠를_낸다(parent: Path) -> None:
    (parent / FOLDER).mkdir()

    location = await locate_folder({"folder": FOLDER})

    assert location.folder == FOLDER
    assert location.chain == (_identity(parent / FOLDER),)
    assert location.final == _identity(parent / FOLDER)


async def test_여러_단계의_폴더는_지나온_폴더마다_열쇠를_내고_마지막이_그_폴더다(
    parent: Path,
) -> None:
    (parent / "가" / "나" / "다").mkdir(parents=True)

    location = await locate_folder({"folder": "가/나/다/"})

    assert location.folder == "가/나/다"
    assert location.chain == (
        _identity(parent / "가"),
        _identity(parent / "가" / "나"),
        _identity(parent / "가" / "나" / "다"),
    )


async def test_합쳐_적은_글자로_적어도_풀어_적은_폴더가_하나뿐이면_디스크의_이름을_낸다(
    parent: Path,
) -> None:
    on_disk = unicodedata.normalize("NFD", FOLDER)
    assert on_disk != FOLDER
    (parent / on_disk).mkdir()

    location = await locate_folder({"folder": FOLDER})

    assert location.folder == on_disk
    assert location.final == _identity(parent / on_disk)


async def test_이름이_같은_글자_꼴이_디스크에_둘이면_적은_글자와_같은_쪽을_고른다(
    parent: Path,
) -> None:
    composed, decomposed = FOLDER, unicodedata.normalize("NFD", FOLDER)
    (parent / composed).mkdir()
    (parent / decomposed).mkdir()
    assert _identity(parent / composed) != _identity(parent / decomposed)

    location = await locate_folder({"folder": decomposed})

    assert location.folder == decomposed


async def test_적은_글자와_같은_이름은_없고_NFC로_맞춘_이름이_같은_폴더가_둘이면_찾지_못한다(
    parent: Path,
) -> None:
    composed, decomposed = FOLDER, unicodedata.normalize("NFD", FOLDER)
    (parent / composed).mkdir()
    (parent / decomposed).mkdir()
    # 첫 글자만 합치고 나머지는 푼 글자다. 디스크의 두 이름과 다르지만 NFC로 맞추면 둘과 같다.
    mixed = composed[0] + unicodedata.normalize("NFD", composed[1:])
    assert mixed not in (composed, decomposed)
    assert unicodedata.normalize("NFC", mixed) == composed

    assert await _reason_of_locate(mixed) is ConnectorFailureReason.NOT_FOUND


async def test_없는_폴더는_not_found다(parent: Path) -> None:
    assert await _reason_of_locate("없는폴더") is ConnectorFailureReason.NOT_FOUND


async def test_중간_토막이_없어도_not_found다(parent: Path) -> None:
    (parent / "가").mkdir()

    assert await _reason_of_locate("가/없는/다") is ConnectorFailureReason.NOT_FOUND


async def test_심볼릭_링크인_폴더는_rejected다(parent: Path, tmp_path: Path) -> None:
    (tmp_path / "밖").mkdir()
    (parent / FOLDER).symlink_to(tmp_path / "밖", target_is_directory=True)

    assert await _reason_of_locate(FOLDER) is ConnectorFailureReason.REJECTED


async def test_폴더가_아니라_파일이면_rejected다(parent: Path) -> None:
    (parent / FOLDER).write_bytes(b"x")

    assert await _reason_of_locate(FOLDER) is ConnectorFailureReason.REJECTED


@pytest.mark.parametrize("folder", ["../밖", "/절대", "", "가//나", "가\\나"])
async def test_폴더_값의_모양이_틀리면_파일_시스템을_보기_전에_invalid_config다(
    parent: Path, folder: str
) -> None:
    assert await _reason_of_locate(folder) is ConnectorFailureReason.INVALID_CONFIG


async def test_폴더_칸이_없으면_invalid_config다(parent: Path) -> None:
    with pytest.raises(ConnectorError) as raised:
        await locate_folder({})

    assert raised.value.reason is ConnectorFailureReason.INVALID_CONFIG


async def test_폴더를_열거할_수_없으면_unreadable이다(
    parent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (parent / FOLDER).mkdir()
    refuse_listing(monkeypatch, FOLDER)

    assert await _reason_of_locate(FOLDER) is ConnectorFailureReason.UNREADABLE


async def test_이름은_보이지만_항목의_정보를_읽을_수_없는_폴더는_unreadable이다(
    parent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 읽기 권한은 있고 탐색 권한이 없는 폴더의 모양이다. `list()`는 항목마다 정보를 읽는다.
    (parent / FOLDER).mkdir()
    hide_entry_info(monkeypatch)

    assert await _reason_of_locate(FOLDER) is ConnectorFailureReason.UNREADABLE


async def test_같은_폴더를_다르게_적어도_마지막_열쇠가_같고_안쪽_폴더의_지나온_열쇠에_바깥이_든다(
    parent: Path,
) -> None:
    (parent / "가" / "나").mkdir(parents=True)

    outer = await locate_folder({"folder": "가"})
    again = await locate_folder({"folder": "가/"})
    inner = await locate_folder({"folder": "가/나"})

    assert outer.final == again.final
    assert outer.final in inner.chain
    assert inner.final not in outer.chain


async def test_연결_확인은_폴더를_열기만_하지_않고_열거를_거절하는_폴더를_가린다(
    parent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (parent / FOLDER).mkdir()
    connector = create_server_path_connector({"folder": FOLDER})
    refuse_listing(monkeypatch, FOLDER)

    with pytest.raises(ConnectorError) as raised:
        await connector.check()

    assert raised.value.reason is ConnectorFailureReason.UNREADABLE


async def test_연결_확인은_이름은_보이지만_항목의_정보를_읽을_수_없는_폴더를_가린다(
    parent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (parent / FOLDER).mkdir()
    connector = create_server_path_connector({"folder": FOLDER})
    hide_entry_info(monkeypatch)

    with pytest.raises(ConnectorError) as raised:
        await connector.check()

    assert raised.value.reason is ConnectorFailureReason.UNREADABLE
