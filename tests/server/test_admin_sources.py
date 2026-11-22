"""밀어 넣는 원천을 만들고 보는 관리 API(source-sync 명세 "관리 API", 스토리 1).

`POST /api/v1/admin/sources`는 밀어 넣는 원천(`kind: push`)만 만든다. 원천 응답의 칸은 목록과 하나
보기가 같고, 가져오는 원천만 쓰는 칸은 밀어 넣는 원천에서 null이다. 실제 uvicorn 서버를 쓴다.
"""

import httpx
import pytest
from tests.harness import RunningServer
from tests.support.round_trip import RoundTrip

SOURCES = "/api/v1/admin/sources"
SOURCE_FIELDS = {
    "name",
    "kind",
    "connector",
    "config",
    "group",
    "schedule",
    "next_run_at",
    "paused",
    "exclude_patterns",
    "created_at",
    "deleted_at",
    "documents",
    "last_sync",
}


def _headers(server: RunningServer) -> dict[str, str]:
    return {"Authorization": f"Bearer {server.admin_token}"}


def _create(server: RunningServer, **body: object) -> httpx.Response:
    return httpx.post(server.base_url + SOURCES, headers=_headers(server), json=body)


def _get(server: RunningServer, path: str = SOURCES) -> httpx.Response:
    return httpx.get(server.base_url + path, headers=_headers(server))


def _issue_locations(response: httpx.Response) -> list[list[str | int]]:
    return [issue["loc"] for issue in response.json()["errors"]]


def test_밀어_넣는_원천을_만들면_201과_원천을_낸다(server: RunningServer) -> None:
    response = _create(server, name="groupware", kind="push")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == SOURCE_FIELDS
    assert (body["name"], body["kind"]) == ("groupware", "push")
    assert body["created_at"].endswith("Z")
    assert body["deleted_at"] is None
    assert body["documents"] == {"total": 0, "failed": 0, "skipped": 0}


def test_밀어_넣는_원천에서는_가져오는_원천만_쓰는_칸이_모두_null이다(
    server: RunningServer,
) -> None:
    body = _create(server, name="groupware", kind="push").json()

    assert {
        name: body[name]
        for name in (
            "connector",
            "config",
            "group",
            "schedule",
            "next_run_at",
            "paused",
            "exclude_patterns",
            "last_sync",
        )
    } == {
        "connector": None,
        "config": None,
        "group": None,
        "schedule": None,
        "next_run_at": None,
        "paused": None,
        "exclude_patterns": None,
        "last_sync": None,
    }


def test_원천_하나_보기는_만든_원천을_이름으로_낸다(server: RunningServer) -> None:
    created = _create(server, name="wiki", kind="push").json()

    response = _get(server, f"{SOURCES}/wiki")

    assert response.status_code == 200
    assert response.json() == created


def test_원천_목록은_만든_차례로_기본_원천_둘을_앞에_두고_하나_보기와_같은_모양이다(
    server: RunningServer,
) -> None:
    _create(server, name="b", kind="push")
    _create(server, name="a", kind="push")

    response = _get(server)

    assert response.status_code == 200
    listed = response.json()["sources"]
    assert [source["name"] for source in listed] == ["default", "upload", "b", "a"]
    for source in listed:
        assert source == _get(server, f"{SOURCES}/{source['name']}").json()


def test_migrate가_만든_default와_upload는_밀어_넣는_원천으로_보인다(server: RunningServer) -> None:
    for name in ("default", "upload"):
        body = _get(server, f"{SOURCES}/{name}").json()

        assert (body["name"], body["kind"], body["connector"]) == (name, "push", None)


def test_없는_원천을_보면_404_source_not_found다(server: RunningServer) -> None:
    response = _get(server, f"{SOURCES}/nothing")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "source_not_found"


@pytest.mark.parametrize(
    "name", ["Groupware", "a" * 64, "-wiki", "_wiki", "wiki system", "wiki\n", ""]
)
def test_규칙에_어긋나는_이름으로_만들면_422이고_위치의_마지막_토막이_name이다(
    server: RunningServer, name: str
) -> None:
    response = _create(server, name=name, kind="push")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert [location[-1] for location in _issue_locations(response)] == ["name"]
    assert _get(server).json()["sources"][-1]["name"] == "upload"


@pytest.mark.parametrize("name", ["default", "upload"])
def test_이미_있는_이름으로_만들면_409_source_already_exists다(
    server: RunningServer, name: str
) -> None:
    response = _create(server, name=name, kind="push")

    assert response.status_code == 409
    assert response.json()["code"] == "source_already_exists"


def test_같은_이름으로_두_번_만들면_둘째가_409이고_원천은_하나다(server: RunningServer) -> None:
    assert _create(server, name="wiki", kind="push").status_code == 201

    second = _create(server, name="wiki", kind="push")

    assert second.status_code == 409
    assert second.json()["code"] == "source_already_exists"
    assert [source["name"] for source in _get(server).json()["sources"]].count("wiki") == 1


def test_가져오는_원천은_커넥터와_설정을_빠뜨리면_그_칸에서_422다(server: RunningServer) -> None:
    response = _create(server, name="folder", kind="pull")

    assert response.status_code == 422
    assert [location[-1] for location in _issue_locations(response)] == ["connector", "config"]
    assert _get(server, f"{SOURCES}/folder").status_code == 404


def test_알_수_없는_갈래는_kind에서_422이고_보낸_값을_응답에_싣지_않는다(
    server: RunningServer,
) -> None:
    response = _create(server, name="folder", kind="비밀값-xyz")

    assert response.status_code == 422
    assert [location[-1] for location in _issue_locations(response)] == ["kind"]
    assert "비밀값-xyz" not in response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("connector", "server-path"),
        ("config", {"folder": "규정집"}),
        ("group", "default"),
        ("schedule", "0 2 * * *"),
        ("exclude_patterns", ["임시/"]),
    ],
)
def test_밀어_넣는_원천에_가져오는_원천만_쓰는_칸을_적으면_그_칸에서_422다(
    server: RunningServer, field: str, value: object
) -> None:
    response = _create(server, name="groupware", kind="push", **{field: value})

    assert response.status_code == 422
    assert [location[-1] for location in _issue_locations(response)] == [field]
    assert _get(server, f"{SOURCES}/groupware").status_code == 404


@pytest.mark.parametrize("body", [{"kind": "push"}, {"name": "wiki"}])
def test_이름이나_갈래를_빠뜨리면_빠진_칸에서_422다(
    server: RunningServer, body: dict[str, object]
) -> None:
    response = httpx.post(server.base_url + SOURCES, headers=_headers(server), json=body)

    assert response.status_code == 422
    missing = "name" if "kind" in body else "kind"
    assert [location[-1] for location in _issue_locations(response)] == [missing]


async def test_reader_토큰은_원천을_만들지도_보지도_못한다(round_trip: RoundTrip) -> None:
    token = await round_trip.issue_reader("default")
    headers = {"Authorization": f"Bearer {token}"}
    base = round_trip.server.base_url

    created = httpx.post(base + SOURCES, headers=headers, json={"name": "a", "kind": "push"})
    listed = httpx.get(base + SOURCES, headers=headers)
    one = httpx.get(base + f"{SOURCES}/default", headers=headers)
    anonymous = httpx.get(base + SOURCES)
    assert [created.status_code, listed.status_code, one.status_code] == [403, 403, 403]
    assert [r.json()["code"] for r in (created, listed, one)] == ["forbidden"] * 3
    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == "unauthenticated"
