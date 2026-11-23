"""서버가 요청 안에서 부르는 레지스트리의 확인 셋(source-sync 티켓 06): 폴더 확인, 이미 있는 원천의
폴더 살펴보기, 연결 확인.

셋 모두 호출 장치를 지나고 한도를 넘긴 호출은 취소하지 않은 채 둔다. 한도는 생성자 인자로 짧게 준다.
폴더 확인은 `server_path.locate_folder`를 바꿔 끼워 돌아오지 않는 호출을 흉내 낸다.
"""

import asyncio
import logging
import time
from collections.abc import Iterator, Mapping
from importlib.metadata import EntryPoint

import pytest
from tests.support.fake_connectors import LEAKED_TEXT

from rag_engine.adapters.connectors import server_path
from rag_engine.adapters.connectors.registry import (
    CONNECTOR_ENTRY_POINT_GROUP,
    EntryPointConnectorRegistry,
)
from rag_engine.domain.connectors import (
    SERVER_PATH_CONNECTOR,
    ConnectorBrokenError,
    ConnectorCallBlockedError,
    ConnectorCallTimedOutError,
    ConnectorError,
    ConnectorFailureReason,
    ConnectorUnavailableError,
    FolderLocation,
    FolderTarget,
)
from rag_engine.domain.entities import JsonValue

TIMEOUT_SECONDS = 0.3
_MODULE = "tests.support.fake_connectors"


def _entry(name: str, function: str) -> EntryPoint:
    return EntryPoint(name=name, value=f"{_MODULE}:{function}", group=CONNECTOR_ENTRY_POINT_GROUP)


def _registry() -> EntryPointConnectorRegistry:
    entries = [
        _entry("fake", "create_fake"),
        _entry("rejecting", "create_rejecting_check"),
        _entry("broken", "create_broken_check"),
    ]
    return EntryPointConnectorRegistry(lambda: entries, timeout_seconds=TIMEOUT_SECONDS)


class Folders:
    """`server_path.locate_folder`를 대신한다. 폴더 이름마다 정해 둔 대로 답하거나 돌아오지
    않는다."""

    def __init__(self) -> None:
        self.hanging: set[str] = set()
        self.missing: set[str] = set()
        self.calls: list[str] = []
        self.release = asyncio.Event()

    async def locate(self, config: Mapping[str, JsonValue]) -> FolderLocation:
        folder = str(config["folder"])
        self.calls.append(folder)
        if folder in self.hanging:
            await self.release.wait()
        if folder in self.missing:
            raise ConnectorError(ConnectorFailureReason.NOT_FOUND)
        return FolderLocation(folder=folder, chain=((1, len(folder)),))


@pytest.fixture
def folders(monkeypatch: pytest.MonkeyPatch) -> Iterator[Folders]:
    fake = Folders()
    monkeypatch.setattr(server_path, "locate_folder", fake.locate)
    yield fake
    fake.release.set()


def _target(folder: str, source: str = "wiki") -> FolderTarget:
    return FolderTarget(source, SERVER_PATH_CONNECTOR, {"folder": folder})


async def test_서버_경로가_아닌_이름으로_폴더를_확인하면_쓸_수_없는_커넥터다(
    folders: Folders,
) -> None:
    with pytest.raises(ConnectorUnavailableError):
        await _registry().locate_folder("fake", {"folder": "a"})

    assert folders.calls == []


async def test_폴더_확인은_결과를_그대로_낸다(folders: Folders) -> None:
    location = await _registry().locate_folder(SERVER_PATH_CONNECTOR, {"folder": "a"})

    assert location == FolderLocation(folder="a", chain=((1, 1),))


async def test_폴더_확인이_낸_커넥터_오류는_그대로_올라온다(folders: Folders) -> None:
    folders.missing.add("a")

    with pytest.raises(ConnectorError) as raised:
        await _registry().locate_folder(SERVER_PATH_CONNECTOR, {"folder": "a"})

    assert raised.value.reason is ConnectorFailureReason.NOT_FOUND


async def test_한도를_넘긴_폴더_확인은_unreadable이고_같은_설정으로_다시_부르면_바로_unreadable이다(
    folders: Folders,
) -> None:
    folders.hanging.add("a")
    registry = _registry()

    with pytest.raises(ConnectorError) as first:
        await registry.locate_folder(SERVER_PATH_CONNECTOR, {"folder": "a"})
    started = time.monotonic()
    with pytest.raises(ConnectorError) as again:
        await registry.locate_folder(SERVER_PATH_CONNECTOR, {"folder": "a"})

    assert first.value.reason is again.value.reason is ConnectorFailureReason.UNREADABLE
    assert time.monotonic() - started < TIMEOUT_SECONDS
    assert folders.calls == ["a"]


async def test_살펴보기는_폴더가_없거나_답하지_않거나_서버_경로가_아닌_대상을_None으로_낸다(
    folders: Folders,
) -> None:
    folders.missing.add("없음")
    folders.hanging.add("끊김")
    targets = [
        _target("정상"),
        _target("없음"),
        _target("끊김"),
        FolderTarget("other", "fake", {"folder": "정상"}),
    ]

    found = await _registry().survey_folders(targets)

    assert found == [FolderLocation("정상", ((1, 2),)), None, None, None]


async def test_살펴보기는_대상마다_따로_내보내_같은_한도_동안_함께_기다린다(
    folders: Folders,
) -> None:
    folders.hanging.update({"가", "나", "다"})

    started = time.monotonic()
    found = await _registry().survey_folders([_target("가"), _target("나"), _target("다")])
    elapsed = time.monotonic() - started

    assert found == [None, None, None]
    assert elapsed < TIMEOUT_SECONDS * 2.5


async def test_답하지_않는_것으로_기억된_대상은_다시_부르지_않고_None이다(folders: Folders) -> None:
    folders.hanging.add("끊김")
    registry = _registry()
    await registry.survey_folders([_target("끊김")])

    started = time.monotonic()
    found = await registry.survey_folders([_target("끊김"), _target("정상")])

    assert found == [None, FolderLocation("정상", ((1, 2),))]
    assert time.monotonic() - started < TIMEOUT_SECONDS
    assert folders.calls.count("끊김") == 1


async def test_정상_커넥터의_연결_확인은_돌아온다() -> None:
    await _registry().check_connection("fake", {}, "wiki")


async def test_연결_확인이_낸_커넥터_오류는_그대로_올라온다() -> None:
    with pytest.raises(ConnectorError) as raised:
        await _registry().check_connection("rejecting", {}, "wiki")

    assert raised.value.reason is ConnectorFailureReason.REJECTED


async def test_연결_확인에서_만들_수_없는_커넥터는_쓸_수_없는_커넥터다() -> None:
    with pytest.raises(ConnectorUnavailableError):
        await _registry().check_connection("nothing", {}, "wiki")


async def test_연결_확인이_인터페이스에_없는_예외를_내면_글_없는_오류로_바꾸고_종류만_기록한다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING), pytest.raises(ConnectorBrokenError) as raised:
        await _registry().check_connection("broken", {}, "wiki")

    assert LEAKED_TEXT not in str(raised.value)
    assert raised.value.__cause__ is None
    logged = " ".join(str(record.__dict__) for record in caplog.records)
    assert LEAKED_TEXT not in logged
    assert "RuntimeError" in logged


async def test_한도를_넘긴_연결_확인은_시간_초과이고_이어진_연결_확인은_막힌다() -> None:
    entries = [_entry("hanging", "create_hanging_check")]
    registry = EntryPointConnectorRegistry(lambda: entries, timeout_seconds=TIMEOUT_SECONDS)

    with pytest.raises(ConnectorCallTimedOutError):
        await registry.check_connection("hanging", {}, "wiki")
    with pytest.raises(ConnectorCallBlockedError):
        await registry.check_connection("hanging", {}, "wiki")


async def test_한도를_넘긴_연결_확인도_설정이_다르면_막지_않는다() -> None:
    entries = [_entry("hanging", "create_hanging_check")]
    registry = EntryPointConnectorRegistry(lambda: entries, timeout_seconds=TIMEOUT_SECONDS)
    with pytest.raises(ConnectorCallTimedOutError):
        await registry.check_connection("hanging", {"folder": "a"}, "wiki")

    with pytest.raises(ConnectorCallTimedOutError):
        await registry.check_connection("hanging", {"folder": "b"}, "wiki")
