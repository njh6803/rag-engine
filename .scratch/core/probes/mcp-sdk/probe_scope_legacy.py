"""mcp 2.3.0: 2025 프로토콜(2025-06-18)의 레거시 initialize 길에서도 MCP 도구가 scope 의 값을
읽는지 raw httpx 로 본다.

근거로 드는 곳은 `probe_scope.py` 와 같다(명세의 인증 절). 서버는 `probe_scope.py` 의 `build` 를
그대로 쓰고, 클라이언트만 SDK Client 대신 initialize, notifications/initialized(세션 ID 가 오면),
tools/call 을 손으로 보낸다. 2026-11-10 티켓 세션의 spec-reviewer 가 세션 스크래치패드에서 돌린 임시
스크립트를 옮겼다.

실행: uv run python .scratch/core/probes/mcp-sdk/probe_scope_legacy.py
(저장소 루트에서. 같은 폴더의 `probe_scope.py` 를 가져온다.) 출력(stdout)은
`probe_scope_legacy_out.txt`(2026-11-10)다. 타입 검사는 `probe_sdk.py` 독스트링의 방법에 더해 임시
설정의 `extraPaths` 에 이 폴더를 넣는다(`probe_scope` 를 찾게).

저장소로 옮기며 독스트링을 고치고, `probe_scope.py` 의 폴더를 인자 대신 이 파일의 위치로 찾게
했으며, bool 인자를 키워드 전용으로(ruff FBT001), 요청 본문 사전에 `dict[str, object]` 주석을
달게(pyright strict) 바꿨다.
"""

import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))
from probe_scope import MODES, build  # noqa: E402

ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def body_json(r: httpx.Response) -> object:
    if r.headers.get("content-type", "").startswith("text/event-stream"):
        data = [ln[5:].strip() for ln in r.text.splitlines() if ln.startswith("data:")]
        return json.loads(data[-1])
    return r.json()


def run(*, stateless: bool, json_response: bool) -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    app = build(stateless=stateless, json_response=json_response)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    th = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    th.start()
    while not server.started:
        time.sleep(0.01)
    url = f"http://127.0.0.1:{port}/mcp"
    init: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "raw", "version": "0"},
        },
    }
    try:
        with httpx.Client(timeout=10) as c:
            r = c.post(url, json=init, headers=ACCEPT)
            sid = r.headers.get("mcp-session-id")
            h = {**ACCEPT, "mcp-protocol-version": "2025-06-18"}
            if sid:
                h["mcp-session-id"] = sid
                c.post(
                    url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=h
                )
            call: dict[str, object] = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "whoami", "arguments": {}},
            }
            r2 = c.post(url, json=call, headers=h)
            print(
                f"legacy stateless={stateless} json={json_response} init={r.status_code} "
                f"sid={'yes' if sid else 'no'} call={r2.status_code} ->",
                body_json(r2),
            )
    finally:
        server.should_exit = True
        th.join(10)


if __name__ == "__main__":
    for st, js in MODES:
        run(stateless=st, json_response=js)
