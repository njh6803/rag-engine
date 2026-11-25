"""가져오는 원천을 되살리는 관리 API(source-sync 티켓 12, 명세 "원천 삭제와 되살리기"와 "서버 경로
커넥터와 원천 폴더"의 겹침 항목).

실제 uvicorn 서버와 실제 파일 시스템을 쓴다. 이 서버에는 작업자가 없으므로, 원천 삭제 작업이
끝난 뒤의 모양은 작업 행의 상태를 직접 `succeeded`로 써서 만든다. 폴더를 여는 호출은 이름으로
붙잡아 돌아오지 않는 폴더를 흉내 낸다(`test_admin_pull_source_stuck_calls.py`와 같은 장치).
"""

import os
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psycopg
import pytest
from tests.harness import RunningServer
from tests.support.pull_source_http import SOURCES, create_pull, request
from tests.support.schedule_sources import SEOUL_CALCULATOR

from rag_engine.adapters.connectors.registry import EntryPointConnectorRegistry
from rag_engine.adapters.postgres.engine import create_engine, run_in_selector_loop
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.schedule_check import ScheduledSync, check_schedules

TIMEOUT_SECONDS = 2.0
STUCK = "끊김"
NORMAL = "정상"
PARENT_OF_STUCK = "공유"
AT_TWO = "0 2 * * *"
FAR_FUTURE = datetime(2100, 1, 1, tzinfo=UTC)


class Gate:
    """이름이 `STUCK`인 폴더를 여는 호출을 풀어 줄 때까지 붙잡는다. `arm()` 전에는 가만히 둔다."""

    def __init__(self) -> None:
        self.armed = False
        self.entered = threading.Event()
        self._released = threading.Event()

    def arm(self) -> None:
        self.armed = True

    def release(self) -> None:
        self._released.set()

    def touch(self, path: str | os.PathLike[str]) -> None:
        name = os.fsdecode(path).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        if self.armed and name == STUCK:
            self.entered.set()
            self._released.wait(60)


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
    for folder in (STUCK, NORMAL, f"{PARENT_OF_STUCK}/{STUCK}"):
        (path / folder).mkdir(parents=True)
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


@pytest.fixture
def server(run_server: Callable[..., RunningServer], parent: Path, gate: Gate) -> RunningServer:
    del parent, gate
    return run_server(
        connector_registry=EntryPointConnectorRegistry(timeout_seconds=TIMEOUT_SECONDS)
    )


def _delete_and_finish(server: RunningServer, name: str) -> None:
    """원천을 지우고, 작업자가 원천 삭제 작업을 끝낸 모양을 만든다."""
    assert request(server, "DELETE", f"{SOURCES}/{name}").status_code == 202
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE jobs SET status = 'succeeded' WHERE kind = 'delete_source'")


def _restore(server: RunningServer, name: str) -> httpx.Response:
    return request(server, "POST", f"{SOURCES}/{name}/restore")


def _shown(server: RunningServer, name: str) -> dict[str, object]:
    shown: dict[str, object] = request(server, "GET", f"{SOURCES}/{name}").json()
    return shown


def _check_at(database_url: str, moment: datetime) -> list[ScheduledSync]:
    async def run() -> list[ScheduledSync]:
        engine = create_engine(database_url)
        try:
            return await check_schedules(PostgresUnitOfWork(engine), SEOUL_CALCULATOR, now=moment)
        finally:
            await engine.dispose()

    return run_in_selector_loop(run())


def test_가져오는_원천을_되살리면_202와_연결_확인이_나오고_다음_실행_시각이_다시_찬다(
    server: RunningServer,
) -> None:
    created = request(
        server,
        "POST",
        SOURCES,
        name="wiki",
        kind="pull",
        connector="server_path",
        config={"folder": NORMAL},
        schedule=AT_TWO,
    )
    assert created.status_code == 201
    _delete_and_finish(server, "wiki")
    assert _shown(server, "wiki")["next_run_at"] is None

    response = _restore(server, "wiki")

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"job_id", "connection_check"}
    assert body["connection_check"] == {"ok": True, "code": None}
    shown = _shown(server, "wiki")
    assert shown["deleted_at"] is None
    assert shown["next_run_at"] is not None


def test_지운_원천에는_일정_확인이_동기화를_넣지_않고_되살린_뒤에는_넣는다(
    server: RunningServer,
) -> None:
    created = request(
        server,
        "POST",
        SOURCES,
        name="wiki",
        kind="pull",
        connector="server_path",
        config={"folder": NORMAL},
        schedule=AT_TWO,
    )
    assert created.status_code == 201
    _delete_and_finish(server, "wiki")
    database_url = server.settings.database_url
    assert _check_at(database_url, FAR_FUTURE) == []

    assert _restore(server, "wiki").status_code == 202

    assert [item.source for item in _check_at(database_url, FAR_FUTURE)] == ["wiki"]


def test_폴더를_여는_호출이_돌아오지_않는_원천도_한도_안에_되살리고_읽지_못했다고_답한다(
    server: RunningServer, gate: Gate
) -> None:
    assert create_pull(server, "wiki", STUCK).status_code == 201
    _delete_and_finish(server, "wiki")
    gate.arm()

    started = time.monotonic()
    response = _restore(server, "wiki")
    elapsed = time.monotonic() - started

    assert response.status_code == 202
    assert response.json()["connection_check"] == {"ok": False, "code": "source_unreadable"}
    assert _shown(server, "wiki")["deleted_at"] is None
    # 폴더 찾기와 연결 확인이 각각 한도까지 기다린다. 그 둘이 이 요청의 전부다.
    assert elapsed < 4 * TIMEOUT_SECONDS + 10


def test_그사이_다른_원천이_겹치는_폴더를_쓰게_됐으면_되살리기는_409이고_원천은_지운_채다(
    server: RunningServer,
) -> None:
    assert create_pull(server, "wiki", PARENT_OF_STUCK).status_code == 201
    _delete_and_finish(server, "wiki")
    assert create_pull(server, "other", f"{PARENT_OF_STUCK}/{STUCK}").status_code == 201

    response = _restore(server, "wiki")

    assert response.status_code == 409
    assert response.json()["code"] == "source_folder_overlap"
    assert _shown(server, "wiki")["deleted_at"] is not None
    with psycopg.connect(server.settings.database_url) as connection:
        queued = connection.execute(
            "SELECT count(*) FROM jobs WHERE kind = 'restore_source'"
        ).fetchone()
    assert queued == (0,)


def test_폴더를_살피는_사이_원천의_폴더가_바뀌고_지워져도_바뀐_폴더로_겹침을_다시_본다(
    run_server: Callable[..., RunningServer], parent: Path, gate: Gate
) -> None:
    del parent
    # 살피는 호출이 풀려 나기 전에 시간 제한이 먼저 풀리지 않도록 제한을 길게 둔다.
    server = run_server(connector_registry=EntryPointConnectorRegistry(timeout_seconds=30))
    assert create_pull(server, "wiki", STUCK).status_code == 201
    gate.arm()
    answers: list[httpx.Response] = []
    restoring = threading.Thread(target=lambda: answers.append(_restore(server, "wiki")))
    restoring.start()
    assert gate.entered.wait(30)

    # 되살리는 요청이 원천 자신의 폴더를 살피며 붙잡힌 사이, 같은 원천의 폴더가 바뀌고 원천이
    # 지워지고 바뀐 폴더를 다른 원천이 쓴다.
    changed = request(server, "PATCH", f"{SOURCES}/wiki", config={"folder": NORMAL})
    assert changed.status_code == 200
    _delete_and_finish(server, "wiki")
    assert create_pull(server, "other", NORMAL).status_code == 201
    gate.release()
    restoring.join(60)

    assert [response.status_code for response in answers] == [409]
    assert answers[0].json()["code"] == "source_folder_overlap"
    assert _shown(server, "wiki")["deleted_at"] is not None


def test_폴더를_차지한_다른_원천을_지우고_나면_되살리기를_받는다(server: RunningServer) -> None:
    assert create_pull(server, "wiki", NORMAL).status_code == 201
    _delete_and_finish(server, "wiki")
    # 지운 원천의 폴더는 겹침을 가리는 대상이 아니라서 다른 원천이 같은 폴더를 가질 수 있다.
    assert create_pull(server, "other", NORMAL).status_code == 201
    assert _restore(server, "wiki").status_code == 409

    assert request(server, "DELETE", f"{SOURCES}/other").status_code == 202
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE jobs SET status = 'succeeded' WHERE kind = 'delete_source'")

    assert _restore(server, "wiki").status_code == 202
