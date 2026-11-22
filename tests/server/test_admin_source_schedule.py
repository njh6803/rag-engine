"""가져오는 원천의 일정과 다음 실행 시각을 다루는 관리 API(source-sync 티켓 10, 명세 "일정과 일정
확인", 스토리 10, 11, 12, 13, 21).

실제 uvicorn 서버와 실제 파일 시스템을 쓰고, 시각이 되었을 때 일정 확인이 작업을 넣는지는 같은
데이터베이스에 붙어 "그 시각"을 넣어 일정 확인을 한 번 돌려서 본다.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
import sqlalchemy as sa
from tests.harness import RunningServer
from tests.support.pull_source_http import SOURCES, errors, request
from tests.support.schedule_sources import SEOUL_CALCULATOR

from rag_engine.adapters.postgres.engine import create_engine, run_in_selector_loop
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.schedule_check import ScheduledSync, check_schedules

JOBS = "/api/v1/admin/jobs"
FOLDER = "규정집"
AT_TWO = "0 2 * * *"
SEOUL = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")
FAR_FUTURE = datetime(2100, 1, 1, tzinfo=UTC)


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """부모 폴더. `RAG_SOURCES_DIR`을 이 폴더로 바꾸고 원천 폴더를 하나 만들어 둔다."""
    path = tmp_path / "sources"
    path.mkdir()
    (path / FOLDER).mkdir()
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


def _create(server: RunningServer, name: str = "wiki", **body: object) -> httpx.Response:
    fields: dict[str, object] = {
        "kind": "pull",
        "connector": "server_path",
        "config": {"folder": FOLDER},
        **body,
    }
    return request(server, "POST", SOURCES, name=name, **fields)


def _next_run(body: dict[str, object]) -> datetime:
    value = body["next_run_at"]
    assert isinstance(value, str), f"next_run_at is {value!r}"
    assert value.endswith("Z")
    return datetime.fromisoformat(value)


def _is_next_two_o_clock(moment: datetime, zone: ZoneInfo, *, after: datetime) -> bool:
    local = moment.astimezone(zone)
    return (local.hour, local.minute, local.second) == (2, 0, 0) and (
        after < moment <= after + timedelta(days=1, hours=1)
    )


def _check_at(database_url: str, moment: datetime) -> list[ScheduledSync]:
    async def run() -> list[ScheduledSync]:
        engine = create_engine(database_url)
        try:
            return await check_schedules(PostgresUnitOfWork(engine), SEOUL_CALCULATOR, now=moment)
        finally:
            await engine.dispose()

    return run_in_selector_loop(run())


def _set_next_run_at(database_url: str, moment: datetime) -> None:
    """원천의 다음 실행 시각을 데이터베이스에 직접 적는다. 시각이 이미 지난 원천을 만든다."""

    async def run() -> None:
        engine = create_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    sa.text("UPDATE sources SET next_run_at = :moment WHERE name = 'wiki'"),
                    {"moment": moment},
                )
        finally:
            await engine.dispose()

    run_in_selector_loop(run())


def _job_count(server: RunningServer) -> int:
    return len(request(server, "GET", JOBS).json()["jobs"])


# ---------- 일정을 받는 규칙 ----------


@pytest.mark.parametrize(
    "expression",
    ["0 0 2 * * *", "* * * *", "", "61 * * * *", "0 24 * * *", "0 0 31 2 *", "0 0 * 13 *"],
    ids=["여섯칸", "네칸", "빈글", "분61", "시24", "2월31일", "13월"],
)
def test_받지_않는_일정은_만들_때_422이고_라이브러리의_글을_싣지_않는다(
    server: RunningServer, parent: Path, expression: str
) -> None:
    response = _create(server, schedule=expression)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert errors(response) == [("schedule", "invalid_schedule")]
    assert "cronsim" not in response.text.lower()
    assert request(server, "GET", f"{SOURCES}/wiki").status_code == 404


@pytest.mark.parametrize("expression", ["0 0 2 * * *", "61 * * * *", "0 0 31 2 *"])
def test_받지_않는_일정은_고칠_때도_422이고_원천은_그대로다(
    server: RunningServer, parent: Path, expression: str
) -> None:
    created = _create(server, schedule=AT_TWO).json()

    response = request(server, "PATCH", f"{SOURCES}/wiki", schedule=expression)

    assert response.status_code == 422
    assert errors(response) == [("schedule", "invalid_schedule")]
    assert "cronsim" not in response.text.lower()
    assert request(server, "GET", f"{SOURCES}/wiki").json() == created


def test_일정이_글이_아니면_422다(server: RunningServer, parent: Path) -> None:
    response = _create(server, schedule=5)

    assert response.status_code == 422
    assert [location for location, _ in errors(response)] == ["schedule"]


# ---------- 다음 실행 시각 ----------


def test_일정을_적어_만들면_다음_실행_시각이_설정한_시간대의_다음_02시다(
    server: RunningServer, parent: Path
) -> None:
    before = datetime.now(UTC)

    response = _create(server, schedule=AT_TWO)

    assert response.status_code == 201
    body = response.json()
    assert body["schedule"] == AT_TWO
    assert _is_next_two_o_clock(_next_run(body), SEOUL, after=before)
    assert request(server, "GET", f"{SOURCES}/wiki").json() == body


def test_시간대_설정을_바꾸면_그_시간대의_02시로_계산한다(
    run_server: Callable[..., RunningServer], parent: Path
) -> None:
    server = run_server(schedule_timezone="America/New_York")
    before = datetime.now(UTC)

    body = _create(server, schedule=AT_TWO).json()

    next_run = _next_run(body)
    assert _is_next_two_o_clock(next_run, NEW_YORK, after=before), (
        f"next_run_at time is {next_run:%H:%M}Z"
    )


def test_일정을_적지_않고_만들면_다음_실행_시각도_없다(server: RunningServer, parent: Path) -> None:
    body = _create(server).json()

    assert (body["schedule"], body["next_run_at"]) == (None, None)


def test_일정을_고치면_다음_실행_시각을_지금_다음으로_다시_계산한다(
    server: RunningServer, parent: Path
) -> None:
    created = _create(server).json()
    assert created["next_run_at"] is None
    before = datetime.now(UTC)

    set_up = request(server, "PATCH", f"{SOURCES}/wiki", schedule=AT_TWO).json()
    changed = request(server, "PATCH", f"{SOURCES}/wiki", schedule="30 3 * * *").json()

    assert set_up["schedule"] == AT_TWO
    assert _is_next_two_o_clock(_next_run(set_up), SEOUL, after=before)
    local = _next_run(changed).astimezone(SEOUL)
    assert changed["schedule"] == "30 3 * * *"
    assert (local.hour, local.minute) == (3, 30)


def test_일정에_null을_적으면_일정과_다음_실행_시각이_비고_적지_않으면_그대로다(
    server: RunningServer, parent: Path
) -> None:
    created = _create(server, schedule=AT_TWO).json()

    untouched = request(server, "PATCH", f"{SOURCES}/wiki", exclude_patterns=["임시"]).json()
    cleared = request(server, "PATCH", f"{SOURCES}/wiki", schedule=None)

    assert (untouched["schedule"], untouched["next_run_at"]) == (
        created["schedule"],
        created["next_run_at"],
    )
    assert cleared.status_code == 200
    assert (cleared.json()["schedule"], cleared.json()["next_run_at"]) == (None, None)
    assert request(server, "GET", f"{SOURCES}/wiki").json() == cleared.json()


def test_일시_중지하면_다음_실행_시각이_비고_다시_시작하면_다시_채운다(
    server: RunningServer, parent: Path
) -> None:
    created = _create(server, schedule=AT_TWO).json()

    paused = request(server, "POST", f"{SOURCES}/wiki/pause").json()
    before = datetime.now(UTC)
    resumed = request(server, "POST", f"{SOURCES}/wiki/resume").json()

    assert (paused["schedule"], paused["paused"], paused["next_run_at"]) == (AT_TWO, True, None)
    assert resumed["paused"] is False
    assert _is_next_two_o_clock(_next_run(resumed), SEOUL, after=before)
    assert resumed["next_run_at"] == created["next_run_at"]


def test_이미_돌고_있는_원천을_다시_시작해도_이미_지난_다음_실행_시각을_밀지_않는다(
    server: RunningServer, parent: Path, seeded_database_url: str
) -> None:
    _create(server, schedule=AT_TWO)
    overdue = datetime(2026, 11, 20, 17, 0, tzinfo=UTC)
    _set_next_run_at(seeded_database_url, overdue)

    resumed = request(server, "POST", f"{SOURCES}/wiki/resume").json()

    assert _next_run(resumed) == overdue
    assert [item.source for item in _check_at(seeded_database_url, overdue)] == ["wiki"]


def test_일시_중지한_원천의_일정을_고쳐도_다음_실행_시각은_빈_채로_두고_다시_시작하면_채운다(
    server: RunningServer, parent: Path
) -> None:
    _create(server, schedule=AT_TWO)
    request(server, "POST", f"{SOURCES}/wiki/pause")

    changed = request(server, "PATCH", f"{SOURCES}/wiki", schedule="30 3 * * *").json()
    resumed = request(server, "POST", f"{SOURCES}/wiki/resume").json()

    assert (changed["schedule"], changed["paused"], changed["next_run_at"]) == (
        "30 3 * * *",
        True,
        None,
    )
    assert _next_run(resumed).astimezone(SEOUL).minute == 30


def test_일정이_없는_원천을_다시_시작해도_다음_실행_시각은_비어_있다(
    server: RunningServer, parent: Path
) -> None:
    _create(server)
    request(server, "POST", f"{SOURCES}/wiki/pause")

    resumed = request(server, "POST", f"{SOURCES}/wiki/resume").json()

    assert (resumed["schedule"], resumed["next_run_at"]) == (None, None)


# ---------- 시각이 되면 일정 확인이 작업을 넣는다 ----------


def test_다시_시작한_원천은_그_시각에_일정_확인이_동기화_작업을_한_번_넣는다(
    server: RunningServer, parent: Path, seeded_database_url: str
) -> None:
    _create(server, schedule=AT_TWO)
    request(server, "POST", f"{SOURCES}/wiki/pause")
    assert _check_at(seeded_database_url, FAR_FUTURE) == []
    resumed = request(server, "POST", f"{SOURCES}/wiki/resume").json()
    due = _next_run(resumed)

    early = _check_at(seeded_database_url, due - timedelta(seconds=1))
    on_time = _check_at(seeded_database_url, due)
    again = _check_at(seeded_database_url, due)

    assert (early, again) == ([], [])
    assert [(item.source, item.started) for item in on_time] == [("wiki", True)]
    assert _job_count(server) == 1
    after = request(server, "GET", f"{SOURCES}/wiki").json()
    assert _next_run(after) == due + timedelta(days=1)
    assert after["last_sync"]["trigger"] == "schedule"
