"""토큰 인증(명세 "인증과 권한", ADR 0014). 실제 uvicorn 서버에 httpx로 접속한다.

판정은 FastAPI 앱 바깥의 ASGI 미들웨어가 REST와 `/mcp` 둘 다에서 한다. `/health`만 인증 밖이고, 허용
호스트 판정(421)은 `/mcp`에서만 한다.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from tests.harness import RunningServer

ADMIN_PATH = "/api/v1/admin/tokens"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "시험", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _issue(
    server: RunningServer, *, via: httpx.Client | None = None, **body: object
) -> tuple[str, str]:
    """admin 토큰으로 토큰을 발급하고 (id, 원문)을 낸다. `via`를 주면 그 클라이언트로 보낸다."""
    post = httpx.post if via is None else via.post
    response = post(
        server.base_url + ADMIN_PATH,
        headers=_bearer(server.admin_token),
        json={"name": "시험", "role": "admin", **body},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], response.json()["token"]


def _mcp_initialize(server: RunningServer, token: str | None, **headers: str) -> httpx.Response:
    auth = {} if token is None else _bearer(token)
    return httpx.post(server.mcp_url, json=INITIALIZE, headers={**MCP_HEADERS, **auth, **headers})


def test_health는_토큰_없이_답한다(server: RunningServer) -> None:
    response = httpx.get(server.base_url + "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_토큰_없는_REST_요청은_401_인증되지_않음이다(server: RunningServer) -> None:
    response = httpx.get(server.base_url + ADMIN_PATH)

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert body["code"] == "unauthenticated"
    assert (body["type"], body["status"]) == ("about:blank", 401)
    assert isinstance(body["title"], str)
    assert body["request_id"] == response.headers["x-request-id"]
    assert "detail" not in body


@pytest.mark.parametrize(
    "authorization",
    ["Bearer rag_wrong_token", "Bearer", "Basic abc", "rag_only_token"],
)
def test_틀린_토큰과_잘못된_Authorization_헤더는_REST에서_401이다(
    server: RunningServer, authorization: str
) -> None:
    response = httpx.get(server.base_url + ADMIN_PATH, headers={"Authorization": authorization})

    assert (response.status_code, response.json()["code"]) == (401, "unauthenticated")


def test_토큰_없는_MCP_요청과_틀린_토큰은_401이다(server: RunningServer) -> None:
    without = _mcp_initialize(server, None)
    wrong = _mcp_initialize(server, "rag_wrong_token")

    assert [(r.status_code, r.json()["code"]) for r in (without, wrong)] == [
        (401, "unauthenticated"),
        (401, "unauthenticated"),
    ]
    assert without.headers["content-type"] == "application/problem+json"


def test_모르는_경로도_토큰이_없으면_401이다(server: RunningServer) -> None:
    assert httpx.get(server.base_url + "/없는/경로").status_code == 401


def test_admin_토큰은_REST와_MCP를_모두_연다(server: RunningServer) -> None:
    rest = httpx.get(server.base_url + ADMIN_PATH, headers=_bearer(server.admin_token))
    mcp = _mcp_initialize(server, server.admin_token)

    assert (rest.status_code, mcp.status_code) == (200, 200)


def test_reader_토큰은_MCP와_health만_열고_REST는_403이다(server: RunningServer) -> None:
    _, reader = _issue(server, role="reader")

    rest = httpx.get(server.base_url + ADMIN_PATH, headers=_bearer(reader))
    health = httpx.get(server.base_url + "/health", headers=_bearer(reader))
    mcp = _mcp_initialize(server, reader)

    assert (rest.status_code, rest.json()["code"]) == (403, "forbidden")
    assert rest.headers["content-type"] == "application/problem+json"
    assert (health.status_code, mcp.status_code) == (200, 200)


def test_회수된_토큰은_회수_사실을_드러내지_않고_401이다(server: RunningServer) -> None:
    token_id, token = _issue(server)
    assert httpx.get(server.base_url + ADMIN_PATH, headers=_bearer(token)).status_code == 200

    revoked = httpx.delete(
        f"{server.base_url}{ADMIN_PATH}/{token_id}", headers=_bearer(server.admin_token)
    )

    after = httpx.get(server.base_url + ADMIN_PATH, headers=_bearer(token))
    assert revoked.status_code == 204
    assert (after.status_code, after.json()["code"]) == (401, "unauthenticated")
    assert _mcp_initialize(server, token).status_code == 401


def test_만료된_토큰은_401_토큰_만료이고_만료_전에는_받는다(server: RunningServer) -> None:
    # 만료 시각을 셈한 뒤 발급과 첫 조회까지가 여유 2초 안이어야 한다. 최상위 `httpx.post`가
    # 호출마다 새 클라이언트를 만드는 시간(프로브는 생성 전체를 쟀다. 그 안에 SSL 컨텍스트 생성이
    # 든다는 것은 코드를 읽은 것이다)이 그 창에 들지 않게 클라이언트를 먼저 만든다
    # (`.scratch/harness/probes/kiwi_warmup_stall/`의 `httpx.Client() construction` 줄).
    with httpx.Client() as client:
        expires_at = (datetime.now(UTC) + timedelta(seconds=2)).isoformat()
        _, token = _issue(server, via=client, expires_at=expires_at)
        before_expiry = client.get(server.base_url + ADMIN_PATH, headers=_bearer(token))
    assert before_expiry.status_code == 200

    time.sleep(2.2)

    for response in (
        httpx.get(server.base_url + ADMIN_PATH, headers=_bearer(token)),
        _mcp_initialize(server, token),
    ):
        assert (response.status_code, response.json()["code"]) == (401, "token_expired")


def test_허용_호스트_밖의_MCP_요청은_421이다(server: RunningServer) -> None:
    response = _mcp_initialize(server, server.admin_token, Host="evil.example.com")

    assert response.status_code == 421


def test_허용_호스트_판정은_MCP에서만_하고_REST는_Host를_보지_않는다(
    server: RunningServer,
) -> None:
    health = httpx.get(server.base_url + "/health", headers={"Host": "evil.example.com"})
    rest = httpx.get(
        server.base_url + ADMIN_PATH,
        headers={**_bearer(server.admin_token), "Host": "evil.example.com"},
    )

    assert (health.status_code, rest.status_code) == (200, 200)


def test_토큰이_없으면_허용_호스트_밖이어도_401이_먼저다(server: RunningServer) -> None:
    response = _mcp_initialize(server, None, Host="evil.example.com")

    assert response.status_code == 401


def test_허용_호스트는_그대로와_포트가_붙은_두_꼴을_받고_localhost도_자동으로_받는다(
    run_server: Callable[..., RunningServer],
) -> None:
    server = run_server(allowed_hosts=["mcp.internal"])

    accepted = [
        _mcp_initialize(server, server.admin_token, Host=host).status_code
        for host in ("mcp.internal", "mcp.internal:8443", "localhost", "127.0.0.1:9000")
    ]
    rejected = _mcp_initialize(server, server.admin_token, Host="other.internal")

    assert accepted == [200, 200, 200, 200]
    assert rejected.status_code == 421


@pytest.mark.parametrize("path", ["/health", ADMIN_PATH])
def test_응답마다_UUIDv7_요청_ID가_헤더로_붙는다(server: RunningServer, path: str) -> None:
    first = httpx.get(server.base_url + path)
    second = httpx.get(server.base_url + path)

    ids = [UUID(response.headers["x-request-id"]) for response in (first, second)]
    assert ids[0] != ids[1]
    assert [request_id.version for request_id in ids] == [7, 7]


def test_들어온_X_Request_Id는_쓰지_않는다(server: RunningServer) -> None:
    forged = "00000000-0000-7000-8000-000000000000"

    response = httpx.get(server.base_url + "/health", headers={"X-Request-Id": forged})

    assert response.headers["x-request-id"] != forged
