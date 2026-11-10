"""mcp 2.3.0: 앱 바깥의 순수 ASGI 미들웨어가 scope 에 둔 값을 MCP 도구가 SDK 의 `Context` 로
읽는지 본다.

근거로 드는 곳은 명세(`.scratch/core/spec.md`)의 인증 절(미들웨어가 판정한 토큰 레코드를 ASGI scope
에 두고 도구가 Context 로 그 요청에 닿는다)이다. `probe_sdk.py` 는 Context 에서 요청 헤더를 읽는
데까지만 봤다. 2026-11-10 티켓 세션의 spec-reviewer 가 세션 스크래치패드에서 돌린 임시 스크립트를
옮겼다.

미들웨어가 scope 의 최상위 키(`rag_token`)와 `scope["state"]` 의 키 둘에 값을 두고, 도구가
`ctx.request_context.request.scope` 에서 둘을 읽어 돌려준다. 전송 모드 셋(stateless+SSE,
stateless+json_response, 세션 유지+SSE)을 SDK Client(2026 프로토콜)로 친다. 2025 프로토콜의 레거시
initialize 길은 `probe_scope_legacy.py` 가 본다.

실행: uv run python .scratch/core/probes/mcp-sdk/probe_scope.py
(저장소 루트에서. 127.0.0.1 의 빈 포트에 서버를 띄우고 바깥 네트워크는 쓰지 않는다. SDK 의 INFO
로그는 stderr 로 나가고 판정 줄은 stdout 이다.) 출력(stdout)은 `probe_scope_out.txt`(2026-11-10)다.
잰 판은 `probe_sdk.py` 독스트링과 같다(mcp 2.3.0).

타입 검사는 `probe_sdk.py` 독스트링의 방법대로 한다.

저장소로 옮기며 독스트링을 고치고, bool 인자를 키워드 전용으로(ruff FBT001), `scope["state"]` 를
`isinstance(…, dict)` 대신 `TypeGuard` 함수로 좁히게(pyright strict 의 partially unknown) 바꿨다.
"""

import asyncio
import socket
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypeGuard

import uvicorn
from fastapi import FastAPI
from mcp import Client
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.types import ASGIApp, Receive, Scope, Send

MODES = [(True, False), (True, True), (False, False)]


def is_str_map(v: object) -> TypeGuard[dict[str, object]]:
    return isinstance(v, dict)


class TokenMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope["rag_token"] = "tok-123"
            state = scope.setdefault("state", {})
            state["rag_token"] = "state-tok-456"
        await self.app(scope, receive, send)


def build(*, stateless: bool, json_response: bool) -> ASGIApp:
    mcp = MCPServer(name="p")

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    def whoami(ctx: Context) -> dict[str, object]:
        req = ctx.request_context.request
        scope: dict[str, object] = dict(req.scope) if req is not None else {}
        state = scope.get("state")
        state_key = state.get("rag_token") if is_str_map(state) else None
        return {
            "request_type": type(req).__name__,
            "scope_key": scope.get("rag_token"),
            "state_key": state_key,
            "protocol": ctx.request_context.protocol_version,
        }

    sec = TransportSecuritySettings(allowed_hosts=["127.0.0.1", "127.0.0.1:*"])
    sub = mcp.streamable_http_app(
        stateless_http=stateless, json_response=json_response, transport_security=sec
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/", sub)
    return TokenMiddleware(app)


async def call(url: str) -> object:
    async with Client(url) as client:
        r = await client.call_tool("whoami", {})
        return r.structured_content


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
    try:
        out = asyncio.run(call(f"http://127.0.0.1:{port}/mcp"))
        print(f"stateless={stateless} json={json_response} ->", out)
    finally:
        server.should_exit = True
        th.join(10)


if __name__ == "__main__":
    for st, js in MODES:
        run(stateless=st, json_response=js)
