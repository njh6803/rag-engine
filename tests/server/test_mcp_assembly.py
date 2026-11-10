"""MCP 전송 설정 둘(`RAG_MCP_STATELESS`, `RAG_MCP_JSON_RESPONSE`)이 `/mcp`의 전송에 그대로 이어진다
(명세 "층, 패키지, 조립"). 기본은 세션 없음 + SSE 응답이다."""

from collections.abc import Callable

import httpx
from tests.harness import RunningServer

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


def _initialize(server: RunningServer) -> httpx.Response:
    return httpx.post(
        server.mcp_url,
        json=INITIALIZE,
        headers={
            "Authorization": f"Bearer {server.admin_token}",
            "Accept": "application/json, text/event-stream",
        },
    )


def test_기본은_세션_없음과_SSE_응답이다(server: RunningServer) -> None:
    response = _initialize(server)

    assert response.status_code == 200
    assert "mcp-session-id" not in response.headers
    assert response.headers["content-type"].startswith("text/event-stream")


def test_세션_유지를_고르면_초기화_응답이_세션_ID를_준다(
    run_server: Callable[..., RunningServer],
) -> None:
    response = _initialize(run_server(mcp_stateless=False))

    assert response.status_code == 200
    assert response.headers["mcp-session-id"]


def test_JSON_응답을_고르면_SSE_대신_JSON으로_답한다(
    run_server: Callable[..., RunningServer],
) -> None:
    response = _initialize(run_server(mcp_json_response=True))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["result"]["serverInfo"]["name"] == "rag-engine"
