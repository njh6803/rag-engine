"""API 문서의 판 칸과 MCP 초기화 응답의 서버 정보(`serverInfo.version`)가 설치된 패키지의 번호를
그대로 보인다(release-image 명세 "번호가 보이는 자리", 스토리 39). MCP 표준의 칸에 싣는 값이라
검색 도구의 형식과 그 판(`1.1.0`)을 바꾸지 않으므로 `tests/contract/`가 아니라 여기에 둔다."""

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


def _authorized(server: RunningServer) -> dict[str, str]:
    return {"Authorization": f"Bearer {server.admin_token}"}


def test_API_문서의_판_칸이_설치된_번호다(
    marker_release_number: str, run_server: Callable[..., RunningServer]
) -> None:
    server = run_server()

    response = httpx.get(f"{server.base_url}/openapi.json", headers=_authorized(server))

    assert response.status_code == 200
    assert response.json()["info"]["version"] == marker_release_number


def test_MCP_서버_정보의_판이_설치된_번호다(
    marker_release_number: str, run_server: Callable[..., RunningServer]
) -> None:
    server = run_server(mcp_json_response=True)

    response = httpx.post(
        server.mcp_url,
        json=INITIALIZE,
        headers={**_authorized(server), "Accept": "application/json, text/event-stream"},
    )

    assert response.status_code == 200
    server_info = response.json()["result"]["serverInfo"]
    assert server_info["name"] == "rag-engine"
    assert server_info["version"] == marker_release_number
