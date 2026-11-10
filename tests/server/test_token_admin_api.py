"""토큰 관리 API(명세 "관리 API", 스토리 31)와 Problem Details 모양(ADR 0015).

발급·목록·회수는 `admin` 토큰만 부른다. 오류 응답은 미디어 타입 `application/problem+json`이다.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from tests.harness import RunningServer

PATH = "/api/v1/admin/tokens"


def _auth(server: RunningServer) -> dict[str, str]:
    return {"Authorization": f"Bearer {server.admin_token}"}


def _post(server: RunningServer, body: object) -> httpx.Response:
    return httpx.post(server.base_url + PATH, headers=_auth(server), json=body)


def test_발급하면_201과_원문을_한_번_돌려주고_그_토큰으로_접속된다(
    server: RunningServer,
) -> None:
    response = _post(server, {"name": "운영 토큰", "role": "admin"})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "id",
        "name",
        "role",
        "knowledge_bases",
        "expires_at",
        "created_at",
        "token",
    }
    assert body["token"].startswith("rag_")
    assert (body["name"], body["role"], body["knowledge_bases"]) == ("운영 토큰", "admin", [])
    assert body["expires_at"] is None
    assert body["created_at"].endswith("Z")
    UUID(body["id"])
    listed = httpx.get(server.base_url + PATH, headers={"Authorization": f"Bearer {body['token']}"})
    assert listed.status_code == 200


def test_목록은_원문_없이_지식베이스_이름과_만료를_낸다(server: RunningServer) -> None:
    expires_at = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
    created = _post(
        server,
        {
            "name": "읽기",
            "role": "reader",
            "knowledge_bases": ["default"],
            "expires_at": expires_at.isoformat(),
        },
    ).json()

    response = httpx.get(server.base_url + PATH, headers=_auth(server))

    assert response.status_code == 200
    tokens = response.json()["tokens"]
    assert [token["name"] for token in tokens] == ["시험", "읽기"]
    assert all("token" not in token for token in tokens)
    reader = tokens[1]
    assert reader["id"] == created["id"]
    assert reader["knowledge_bases"] == ["default"]
    assert reader["expires_at"] == expires_at.isoformat().replace("+00:00", "Z")
    assert created["token"] not in response.text


def test_admin_토큰에_범위를_주면_422이고_어느_칸인지_알린다(server: RunningServer) -> None:
    response = _post(server, {"name": "범위", "role": "admin", "knowledge_bases": ["default"]})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert (body["code"], body["status"], body["type"]) == ("validation_error", 422, "about:blank")
    assert body["request_id"] == response.headers["x-request-id"]
    assert [error["loc"] for error in body["errors"]] == [["body", "knowledge_bases"]]


def test_이미_지난_만료_시각은_422이다(server: RunningServer) -> None:
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()

    response = _post(server, {"name": "지남", "role": "reader", "expires_at": past})

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["errors"]] == [["body", "expires_at"]]


def test_422의_errors에는_입력_값과_ctx를_싣지_않는다(server: RunningServer) -> None:
    secret = "비밀로_남길_입력값"

    response = _post(server, {"name": "", "role": secret, "expires_at": "내일"})

    assert response.status_code == 422
    errors = response.json()["errors"]
    assert {tuple(error["loc"]) for error in errors} == {
        ("body", "name"),
        ("body", "role"),
        ("body", "expires_at"),
    }
    assert all(set(error) == {"loc", "type", "msg"} for error in errors)
    assert secret not in response.text


def test_시각에_오프셋이_없으면_422이다(server: RunningServer) -> None:
    response = _post(
        server, {"name": "오프셋", "role": "reader", "expires_at": "2099-01-01T00:00:00"}
    )

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["errors"]] == [["body", "expires_at"]]


def test_없는_지식베이스를_범위로_주면_404이다(server: RunningServer) -> None:
    response = _post(
        server, {"name": "없음", "role": "reader", "knowledge_bases": ["없는_지식베이스"]}
    )

    assert response.status_code == 404
    assert response.json()["code"] == "knowledge_base_not_found"
    assert response.headers["content-type"] == "application/problem+json"


def test_회수하면_204이고_다시_회수해도_204이다(server: RunningServer) -> None:
    token_id = _post(server, {"name": "회수", "role": "reader"}).json()["id"]
    url = f"{server.base_url}{PATH}/{token_id}"

    first = httpx.delete(url, headers=_auth(server))
    second = httpx.delete(url, headers=_auth(server))

    assert (first.status_code, second.status_code) == (204, 204)
    assert first.content == b""
    listed = httpx.get(server.base_url + PATH, headers=_auth(server)).json()["tokens"]
    assert [token["name"] for token in listed] == ["시험", "회수"]


def test_없는_토큰을_회수하면_404이다(server: RunningServer) -> None:
    response = httpx.delete(
        f"{server.base_url}{PATH}/01960000-0000-7000-8000-000000000000", headers=_auth(server)
    )

    assert response.status_code == 404
    assert response.json()["code"] == "token_not_found"


def test_토큰_id가_UUID가_아니면_422이다(server: RunningServer) -> None:
    response = httpx.delete(f"{server.base_url}{PATH}/아님", headers=_auth(server))

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["errors"]] == [["path", "token_id"]]
