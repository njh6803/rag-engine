"""설치처가 만든 커넥터의 흉내로 보는 관리 API(source-sync 티켓 06, 명세 "Testing Decisions"의
설치처 커넥터 항목).

가짜 커넥터는 entry point를 직접 만들어 레지스트리에 준다. 서버 경로가 아닌 커넥터는 폴더 확인과
겹침 확인을 하지 않는다.
"""

import logging
from collections.abc import Callable
from importlib.metadata import EntryPoint

import psycopg
import pytest
from tests.harness import RunningServer
from tests.support.fake_connectors import LEAKED_TEXT
from tests.support.pull_source_http import SOURCES, errors, request

from rag_engine.adapters.connectors.registry import (
    CONNECTOR_ENTRY_POINT_GROUP,
    EntryPointConnectorRegistry,
)

_MODULE = "tests.support.fake_connectors"
_FAKES = {
    "fake": "create_fake",
    "needs_folder": "create_requiring_folder",
    "next_major": "create_next_major",
    "broken_check": "create_broken_check",
    "rejecting_check": "create_rejecting_check",
}


def _entries() -> list[EntryPoint]:
    return [
        EntryPoint(name=name, value=f"{_MODULE}:{function}", group=CONNECTOR_ENTRY_POINT_GROUP)
        for name, function in _FAKES.items()
    ]


@pytest.fixture
def fake_server(run_server: Callable[..., RunningServer]) -> RunningServer:
    return run_server(connector_registry=EntryPointConnectorRegistry(_entries))


def _create(
    server: RunningServer, name: str, connector: str, config: dict[str, object] | None = None
) -> int:
    response = request(
        server,
        "POST",
        SOURCES,
        name=name,
        kind="pull",
        connector=connector,
        config={"folder": "x"} if config is None else config,
    )
    return response.status_code


def test_인터페이스_버전의_major가_다른_커넥터로_원천을_만들면_422_connector_unavailable이다(
    fake_server: RunningServer,
) -> None:
    response = request(
        fake_server,
        "POST",
        SOURCES,
        name="wiki",
        kind="pull",
        connector="next_major",
        config={"folder": "x"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert errors(response) == [("connector", "connector_unavailable")]
    assert request(fake_server, "GET", f"{SOURCES}/wiki").status_code == 404


def test_설치되지_않은_이름의_커넥터로_만들면_422_connector_unavailable이다(
    fake_server: RunningServer,
) -> None:
    response = request(
        fake_server,
        "POST",
        SOURCES,
        name="wiki",
        kind="pull",
        connector="nothing",
        config={},
    )

    assert response.status_code == 422
    assert errors(response) == [("connector", "connector_unavailable")]


def test_만드는_함수가_받지_않는_설정은_422_invalid_config다(fake_server: RunningServer) -> None:
    response = request(
        fake_server,
        "POST",
        SOURCES,
        name="wiki",
        kind="pull",
        connector="needs_folder",
        config={"folder": 3},
    )

    assert response.status_code == 422
    assert errors(response) == [("config", "invalid_config")]


def test_서버_경로가_아닌_커넥터는_폴더_확인과_겹침_확인을_하지_않는다(
    fake_server: RunningServer,
) -> None:
    assert _create(fake_server, "first", "fake") == 201
    assert _create(fake_server, "second", "fake") == 201


def test_설정을_고칠_때도_커넥터의_설정_확인을_다시_한다(fake_server: RunningServer) -> None:
    assert _create(fake_server, "wiki", "needs_folder") == 201

    rejected = request(fake_server, "PATCH", f"{SOURCES}/wiki", config={"folder": 3})
    accepted = request(fake_server, "PATCH", f"{SOURCES}/wiki", config={"folder": "y"})

    assert rejected.status_code == 422
    assert errors(rejected) == [("config", "invalid_config")]
    assert accepted.status_code == 200
    assert accepted.json()["config"] == {"folder": "y"}


def test_정상_커넥터의_연결_확인은_ok다(fake_server: RunningServer) -> None:
    assert _create(fake_server, "wiki", "fake") == 201

    response = request(fake_server, "POST", f"{SOURCES}/wiki/check")

    assert response.json() == {"ok": True, "code": None}


def test_경로_확인에_걸렸다고_알리는_커넥터의_연결_확인은_source_path_rejected다(
    fake_server: RunningServer,
) -> None:
    assert _create(fake_server, "wiki", "rejecting_check") == 201

    response = request(fake_server, "POST", f"{SOURCES}/wiki/check")

    assert response.json() == {"ok": False, "code": "source_path_rejected"}


def test_인터페이스에_없는_예외는_connector_error이고_응답과_로그에_그_글이_없다(
    fake_server: RunningServer, caplog: pytest.LogCaptureFixture
) -> None:
    assert _create(fake_server, "wiki", "broken_check") == 201

    with caplog.at_level(logging.INFO):
        response = request(fake_server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "code": "connector_error"}
    assert LEAKED_TEXT not in response.text
    logged = " ".join(str(record.__dict__) + record.getMessage() for record in caplog.records)
    assert LEAKED_TEXT not in logged
    failed = [record for record in caplog.records if record.getMessage() == "connector_call_failed"]
    assert [record.__dict__["event_fields"]["exception_type"] for record in failed] == [
        "RuntimeError"
    ]


def test_저장해_둔_설정을_만드는_함수가_받지_않으면_연결_확인은_connector_unavailable이다(
    fake_server: RunningServer,
) -> None:
    assert _create(fake_server, "wiki", "needs_folder") == 201
    with psycopg.connect(fake_server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE sources SET config = '{}'::jsonb WHERE name = 'wiki'")

    response = request(fake_server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "code": "connector_unavailable"}


def test_설치되지_않게_된_커넥터의_원천도_연결_확인은_connector_unavailable이다(
    run_server: Callable[..., RunningServer],
) -> None:
    server = run_server(connector_registry=EntryPointConnectorRegistry(_entries))
    assert _create(server, "wiki", "fake") == 201
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE sources SET connector = 'uninstalled' WHERE name = 'wiki'")

    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.json() == {"ok": False, "code": "connector_unavailable"}
