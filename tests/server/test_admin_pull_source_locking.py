"""폴더를 정하는 요청끼리의 차례(source-sync 티켓 06, 명세의 서버 경로 커넥터 잠금 항목).

겹침 확인과 저장은 작업 단위 하나에서 하고, 그 요청끼리는 차례로 지난다. 첫째 요청을
겹침 확인을 지난 뒤 커밋하기 전에 붙잡아 둔다. 붙잡지 않으면 두 요청이 저절로 차례로
지나 잠금이 없어도 시험이 초록이 된다. 시험 서버는 스레드에서 돈다
(`tests/conftest.py`의 `run_server`).
"""

import asyncio
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from tests.harness import RunningServer
from tests.support.pull_source_http import create_pull, request

from rag_engine.adapters.postgres.catalog import PostgresCatalog
from rag_engine.domain.entities import JsonValue, Source

SOURCES = "/api/v1/admin/sources"
# 제품의 연결 풀은 5에 넘침 10이다(`adapters/postgres/engine.py`). 그보다 많이 보낸다.
MORE_THAN_POOL = 20
WAIT_SECONDS = 15


class Hold:
    """이름이 `first`인 원천을 저장하기 직전(겹침 확인을 지난 뒤)에 붙잡는다."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self._gate = threading.Event()

    def release(self) -> None:
        self._gate.set()

    async def wait(self) -> None:
        self.entered.set()
        while not self._gate.is_set():
            await asyncio.sleep(0.01)


@pytest.fixture
def hold(monkeypatch: pytest.MonkeyPatch) -> Iterator[Hold]:
    holding = Hold()
    real_create_source = PostgresCatalog.create_source

    async def create_source(self: PostgresCatalog, source: Source) -> None:
        if source.name == "first":
            await holding.wait()
        await real_create_source(self, source)

    monkeypatch.setattr(PostgresCatalog, "create_source", create_source)
    yield holding
    holding.release()


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sources"
    names = (
        f"{prefix}{number}" for prefix in ("폴더", "원래") for number in range(MORE_THAN_POOL + 1)
    )
    for folder in ("a/b", *names):
        (path / folder).mkdir(parents=True)
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


def _create(server: RunningServer, name: str, folder: str) -> httpx.Response:
    return httpx.post(
        server.base_url + SOURCES,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json={
            "name": name,
            "kind": "pull",
            "connector": "server_path",
            "config": {"folder": folder},
        },
        timeout=WAIT_SECONDS,
    )


def _names(server: RunningServer) -> list[str]:
    response = httpx.get(
        server.base_url + SOURCES,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        timeout=WAIT_SECONDS,
    )
    names: list[str] = [source["name"] for source in response.json()["sources"]]
    return names


@pytest.mark.usefixtures("parent")
def test_서로_겹치는_폴더의_원천을_동시에_만들면_하나만_만들어지고_다른_하나는_409다(
    server: RunningServer, hold: Hold
) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_create, server, "first", "a")
        assert hold.entered.wait(WAIT_SECONDS)
        second = pool.submit(_create, server, "second", "a/b")
        time.sleep(0.5)  # 둘째가 확인을 지나 먼저 끝나지 않고 첫째를 기다리는지 본다
        assert not second.done()
        hold.release()
        results = (first.result(WAIT_SECONDS), second.result(WAIT_SECONDS))

    assert results[0].status_code == 201
    assert results[1].status_code == 409
    assert results[1].json()["code"] == "source_folder_overlap"
    assert [name for name in _names(server) if name in {"first", "second"}] == ["first"]


@pytest.mark.usefixtures("parent")
def test_차례를_기다리는_요청은_연결을_쥐지_않아_목록_조회가_첫째를_풀기_전에_답한다(
    server: RunningServer, hold: Hold
) -> None:
    with ThreadPoolExecutor(max_workers=MORE_THAN_POOL + 1) as pool:
        first = pool.submit(_create, server, "first", "a")
        assert hold.entered.wait(WAIT_SECONDS)
        waiting: list[Future[httpx.Response]] = [
            pool.submit(_create, server, f"other{number}", f"폴더{number}")
            for number in range(MORE_THAN_POOL)
        ]
        time.sleep(1.0)  # 요청이 모두 서버에 닿아 차례를 기다리게 한다
        assert not any(request.done() for request in waiting)

        started = time.monotonic()
        names = _names(server)
        elapsed = time.monotonic() - started

        hold.release()
        statuses = [request.result(WAIT_SECONDS).status_code for request in (first, *waiting)]

    assert "default" in names
    assert elapsed < WAIT_SECONDS / 2
    assert statuses == [201] * (MORE_THAN_POOL + 1)


class HoldFirstUpdate:
    """`arm()`을 부른 뒤 처음 오는 폴더 고치기를 저장하기 직전에 붙잡는다."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self._gate = threading.Event()
        self._armed = False

    def arm(self) -> None:
        self._armed = True

    def release(self) -> None:
        self._gate.set()

    async def wait_if_first(self) -> None:
        if not self._armed or self.entered.is_set():
            return
        self.entered.set()
        while not self._gate.is_set():
            await asyncio.sleep(0.01)


@pytest.fixture
def hold_update(monkeypatch: pytest.MonkeyPatch) -> Iterator[HoldFirstUpdate]:
    holding = HoldFirstUpdate()
    real_update = PostgresCatalog.update_pull_source

    async def update_pull_source(
        self: PostgresCatalog,
        source_id: UUID,
        *,
        config: Mapping[str, JsonValue] | None,
        exclude_patterns: Sequence[str] | None,
    ) -> None:
        await holding.wait_if_first()
        await real_update(self, source_id, config=config, exclude_patterns=exclude_patterns)

    monkeypatch.setattr(PostgresCatalog, "update_pull_source", update_pull_source)
    yield holding
    holding.release()


def _move(server: RunningServer, name: str, folder: str) -> httpx.Response:
    return request(server, "PATCH", f"{SOURCES}/{name}", config={"folder": folder})


@pytest.mark.usefixtures("parent")
def test_폴더를_고치는_요청도_차례를_기다리는_동안_연결을_쥐지_않아_목록_조회가_답한다(
    server: RunningServer, hold_update: HoldFirstUpdate
) -> None:
    for number in range(MORE_THAN_POOL + 1):
        assert create_pull(server, f"src{number}", f"원래{number}").status_code == 201
    hold_update.arm()

    with ThreadPoolExecutor(max_workers=MORE_THAN_POOL + 1) as pool:
        first = pool.submit(_move, server, "src0", "a")
        assert hold_update.entered.wait(WAIT_SECONDS)
        waiting: list[Future[httpx.Response]] = [
            pool.submit(_move, server, f"src{number}", f"폴더{number}")
            for number in range(1, MORE_THAN_POOL + 1)
        ]
        time.sleep(3.0)  # 고치기 요청은 확인이 길어 모두 닿아 차례를 기다리게 하려면 더 기다린다
        assert not any(request.done() for request in waiting)

        started = time.monotonic()
        names = _names(server)
        elapsed = time.monotonic() - started

        hold_update.release()
        statuses = [request.result(WAIT_SECONDS).status_code for request in (first, *waiting)]

    assert "default" in names
    assert elapsed < WAIT_SECONDS / 2
    assert statuses == [200] * (MORE_THAN_POOL + 1)
