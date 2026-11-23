"""끊긴 공유 폴더가 답하지 않을 때의 관리 API(source-sync 티켓 06, 명세 "Testing Decisions"의 폴더
확인 장면과 연결 확인 장면).

폴더를 여는 호출(`os.open`과 `os.lstat`)을 이름으로 붙잡아 돌아오지 않는 폴더를 흉내 낸다. 시험
서버는 같은 프로세스의 스레드에서 돌아 `monkeypatch`가 서버 쪽 호출에도 닿는다. 서버의 호출 한도는
레지스트리의 생성자 인자로 짧게 준다.
"""

import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from tests.harness import RunningServer
from tests.support.pull_source_http import SOURCES, create_pull, errors, request

from rag_engine.adapters.connectors.registry import EntryPointConnectorRegistry

TIMEOUT_SECONDS = 2.0
# 기다리지 않고 답해야 하는 요청의 상한. 홀로 돌리면 0.1초 안쪽이다.
PROMPT_SECONDS = 1.0
STUCK = "끊김"
DENIED = "잠김"
GUARD_LOGGER = "rag_engine.adapters.connectors.guard"


class Gate:
    """이름이 `STUCK`인 폴더를 여는 호출을 풀어 줄 때까지 붙잡고, `DENIED`는 권한 오류로 만든다."""

    def __init__(self) -> None:
        self.armed = False
        self.denied = False
        self.entered = threading.Event()
        self._released = threading.Event()
        self.threads: list[threading.Thread] = []

    def arm(self) -> None:
        self.armed = True

    def deny(self) -> None:
        self.denied = True

    def release(self) -> None:
        self._released.set()

    def touch(self, path: str | os.PathLike[str]) -> None:
        name = os.fsdecode(path).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        if self.armed and name == STUCK:
            self.threads.append(threading.current_thread())
            self.entered.set()
            self._released.wait(60)
        if self.denied and name == DENIED:
            raise PermissionError(13, "권한 없음")


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[Gate]:
    holder = Gate()

    def guarded(original: Callable[..., object]) -> Callable[..., object]:
        def wrapper(path: str | os.PathLike[str], *args: object, **kwargs: object) -> object:
            holder.touch(path)
            return original(path, *args, **kwargs)

        return wrapper

    for name in ("open", "lstat"):
        monkeypatch.setattr(os, name, guarded(getattr(os, name)))
    yield holder
    holder.release()


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sources"
    for folder in (STUCK, DENIED, "정상", "다른", f"공유/{STUCK}"):
        (path / folder).mkdir(parents=True)
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


@pytest.fixture
def server(run_server: Callable[..., RunningServer], parent: Path, gate: Gate) -> RunningServer:
    """붙잡는 장치와 짧은 한도의 레지스트리를 쓰는 서버. 두 픽스처가 서버보다 먼저 선다."""
    del parent, gate
    return run_server(
        connector_registry=EntryPointConnectorRegistry(timeout_seconds=TIMEOUT_SECONDS)
    )


def _source_names(server: RunningServer) -> list[str]:
    found: list[str] = [item["name"] for item in request(server, "GET", SOURCES).json()["sources"]]
    return found


def _timed[T](call: Callable[[], T]) -> tuple[T, float]:
    started = time.monotonic()
    result = call()
    return result, time.monotonic() - started


def test_끊긴_폴더로_만드는_요청은_한도_뒤_422_unreadable이고_원천이_생기지_않는다(
    server: RunningServer, gate: Gate
) -> None:
    gate.arm()

    response, elapsed = _timed(lambda: create_pull(server, "wiki", STUCK))

    assert response.status_code == 422
    assert errors(response) == [("config", "unreadable")]
    assert TIMEOUT_SECONDS <= elapsed < TIMEOUT_SECONDS + 10
    assert "wiki" not in _source_names(server)


def test_끊긴_폴더로_고치는_요청도_422_unreadable이고_원천은_그대로다(
    server: RunningServer, gate: Gate
) -> None:
    assert create_pull(server, "wiki", "정상").status_code == 201
    gate.arm()

    response = request(server, "PATCH", f"{SOURCES}/wiki", config={"folder": STUCK})

    assert response.status_code == 422
    assert errors(response) == [("config", "unreadable")]
    assert request(server, "GET", f"{SOURCES}/wiki").json()["config"] == {"folder": "정상"}


def test_권한_오류도_끊긴_폴더와_같은_응답이다(server: RunningServer, gate: Gate) -> None:
    gate.arm()
    gate.deny()
    stuck = create_pull(server, "wiki", STUCK)

    denied, elapsed = _timed(lambda: create_pull(server, "wiki", DENIED))

    assert (denied.status_code, errors(denied)) == (stuck.status_code, errors(stuck))
    assert elapsed < PROMPT_SECONDS
    assert denied.json()["code"] == stuck.json()["code"] == "validation_error"


def test_한도를_넘긴_요청이_끝난_뒤_다른_원천을_만드는_요청은_기다리지_않고_지난다(
    server: RunningServer, gate: Gate
) -> None:
    gate.arm()
    assert create_pull(server, "wiki", STUCK).status_code == 422

    response, elapsed = _timed(lambda: create_pull(server, "other", "다른"))

    assert response.status_code == 201
    assert elapsed < PROMPT_SECONDS


def test_붙잡아_둔_확인을_뒤늦게_풀어_줘도_원천이_생기지_않는다(
    server: RunningServer, gate: Gate
) -> None:
    gate.arm()
    assert create_pull(server, "wiki", STUCK).status_code == 422

    gate.release()
    for thread in gate.threads:
        thread.join(10)
    time.sleep(0.5)  # 늦게 돌아온 결과가 쓰일 틈을 준다

    assert "wiki" not in _source_names(server)


def test_붙잡아_둔_확인을_뒤늦게_풀어_줘도_원천이_고쳐지지_않는다(
    server: RunningServer, gate: Gate
) -> None:
    assert create_pull(server, "wiki", "정상").status_code == 201
    gate.arm()
    assert request(server, "PATCH", f"{SOURCES}/wiki", config={"folder": STUCK}).status_code == 422

    gate.release()
    for thread in gate.threads:
        thread.join(10)
    time.sleep(0.5)

    assert request(server, "GET", f"{SOURCES}/wiki").json()["config"] == {"folder": "정상"}


def test_같은_폴더로_다시_온_요청은_기다리지_않고_같은_422를_받는다(
    server: RunningServer, gate: Gate
) -> None:
    gate.arm()
    first = create_pull(server, "wiki", STUCK)

    again, elapsed = _timed(lambda: create_pull(server, "again", STUCK))

    assert (again.status_code, errors(again)) == (first.status_code, errors(first))
    assert elapsed < PROMPT_SECONDS
    assert len(gate.threads) == 1, "남은 호출이 있는 동안 폴더를 다시 열었다"


def test_다른_원천의_폴더가_답하지_않으면_한도_안에_끝나고_글자로_견준다(
    server: RunningServer, gate: Gate
) -> None:
    assert create_pull(server, "frozen", f"공유/{STUCK}").status_code == 201
    gate.arm()

    overlapping, elapsed = _timed(lambda: create_pull(server, "outer", "공유"))
    apart = create_pull(server, "apart", "다른")

    assert (overlapping.status_code, overlapping.json()["code"]) == (409, "source_folder_overlap")
    assert elapsed < TIMEOUT_SECONDS + 10
    assert apart.status_code == 201
    assert "outer" not in _source_names(server)


def test_답하지_않는_것으로_기억된_원천과는_기다리지_않고_글자로_견준다(
    server: RunningServer, gate: Gate
) -> None:
    assert create_pull(server, "frozen", f"공유/{STUCK}").status_code == 201
    gate.arm()
    assert create_pull(server, "outer", "공유").status_code == 409

    overlapping, elapsed = _timed(lambda: create_pull(server, "again", "공유"))

    assert overlapping.status_code == 409
    assert elapsed < PROMPT_SECONDS


def test_연결_확인은_한도를_넘기면_source_unreadable이고_이어진_요청은_커넥터를_부르지_않는다(
    server: RunningServer, gate: Gate
) -> None:
    assert create_pull(server, "wiki", STUCK).status_code == 201
    gate.arm()

    first, first_elapsed = _timed(lambda: request(server, "POST", f"{SOURCES}/wiki/check"))
    again, again_elapsed = _timed(lambda: request(server, "POST", f"{SOURCES}/wiki/check"))

    assert first.status_code == again.status_code == 200
    assert first.json() == again.json() == {"ok": False, "code": "source_unreadable"}
    assert first_elapsed >= TIMEOUT_SECONDS
    assert again_elapsed < PROMPT_SECONDS
    assert len(gate.threads) == 1, "남은 호출이 있는 동안 커넥터를 다시 불렀다"


def test_설정을_고친_뒤의_연결_확인은_새_설정으로_커넥터를_부른다(
    server: RunningServer, gate: Gate
) -> None:
    assert create_pull(server, "wiki", STUCK).status_code == 201
    gate.arm()
    assert request(server, "POST", f"{SOURCES}/wiki/check").json()["ok"] is False

    assert request(server, "PATCH", f"{SOURCES}/wiki", config={"folder": "정상"}).status_code == 200
    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.json() == {"ok": True, "code": None}


def test_한도를_넘길_때_로그_한_줄에_폴더와_설정이_없다(
    server: RunningServer, gate: Gate, caplog: pytest.LogCaptureFixture
) -> None:
    gate.arm()

    with caplog.at_level(logging.WARNING):
        create_pull(server, "wiki", STUCK)

    records = [record for record in caplog.records if record.name == GUARD_LOGGER]
    assert [record.getMessage() for record in records] == ["connector_call_timed_out"]
    logged = " ".join(str(record.__dict__) for record in caplog.records)
    assert STUCK not in logged
    assert "'folder':" not in logged
    assert "'config'" not in logged


def test_폴더_확인의_스레드는_새로_띄운_daemon_스레드이고_기본_풀의_스레드가_아니다(
    server: RunningServer, gate: Gate
) -> None:
    gate.arm()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(create_pull, server, "wiki", STUCK)
        assert gate.entered.wait(10)
        (thread,) = gate.threads
        assert thread.daemon
        assert thread.name == "server-path-connector"
        assert not thread.name.startswith("asyncio_")
        assert threading.main_thread() is not thread
        response: httpx.Response = pending.result(TIMEOUT_SECONDS + 30)

    assert response.status_code == 422
