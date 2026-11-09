"""mcp 2.3.0 확인 스크립트 2: 세션 ID 와 다중 프로세스 제약, Host 와일드카드의 포트 없는 경우, 401
때 클라이언트 예외 사슬.

보는 것:
5. 레거시(2025-06-18) initialize 핸드셰이크가 기본(stateful)과 stateless_http=True 에서
   Mcp-Session-Id 를 내는지, 모르는 세션 ID(다른 워커가 받은 꼴)와 세션 ID 없는 요청이 어떻게
   처리되는지, `Client(mode="legacy")` 가 붙는지.
1. `allowed_hosts=["kb.example.com:*"]` 에 포트 없는 Host 와 대문자 Host 가 통과하는지.
2. 401 을 내는 ASGI 미들웨어 뒤에서 SDK Client 의 예외가 어떤 사슬(ExceptionGroup → MCPError)로
   오는지.

실행: uv run python .scratch/core/probes/mcp-sdk/probe_sessions.py
(저장소 루트에서. 127.0.0.1 의 빈 포트에 서버를 띄우고 바깥 네트워크는 쓰지 않는다.)
타입 검사는 probe_sdk.py 독스트링의 방법대로.

2026-11-09에 돌렸다(출력 `probe_sessions_out.txt`). stateful 에서는 initialize 가 세션 ID 를 내고
모르는 세션 ID 는 404 "Session not found", 세션 ID 없는 요청은 400. stateless 에서는 세션 ID 가 없고
어떤 세션 ID 로도 200 이다(워커 여럿에 붙일 수 있다). `kb.example.com:*` 는 포트 없는 Host 와 대문자
Host 를 421 로 막는다(포트가 붙은 소문자만 통과). 401 때 SDK Client 는 ExceptionGroup 두 겹 안에
MCPError 다.

잰 판: probe_sdk.py 독스트링과 같다(mcp 2.3.0, httpx2 2.16.0, fastapi 0.162.2, uvicorn 0.54.0).

저장소로 옮기며(2026-11-09) 원칙 II 와 pyright strict 에 맞춰 타입만 고쳤다(`Any`
→ `ASGIApp`·`dict[str, object]`, ExceptionGroup 좁히기). 옮긴 뒤 다시 돌려 `probe_sessions_out.txt`
와 무작위 Mcp-Session-Id 만 다름을 봤다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import TypeGuard

import httpx2
import uvicorn
from fastapi import FastAPI
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.types import ASGIApp, Receive, Scope, Send

logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.ERROR)


def section(title: str) -> None:
    print(f"\n===== {title} =====")


def is_group(exc: BaseException) -> TypeGuard[BaseExceptionGroup[BaseException]]:
    """isinstance 만으로 좁히면 pyright 가 하위 예외를 Unknown 으로 읽어 TypeGuard 로 감쌌다."""
    return isinstance(exc, BaseExceptionGroup)


@contextmanager
def serve(app: ASGIApp) -> Generator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)


def build_mcp() -> MCPServer:
    mcp = MCPServer(name="probe", log_level="ERROR")

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    def echo(x: int) -> int:
        return x

    return mcp


def wrap_fastapi(
    mcp: MCPServer, mcp_app: ASGIApp, middleware: Callable[[ASGIApp], ASGIApp] | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    if middleware is not None:
        app.add_middleware(middleware)
    app.mount("/", mcp_app)
    return app


class Deny401:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = json.dumps({"error": "invalid_token"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b'Bearer error="invalid_token"'),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


HDRS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INIT: dict[str, object] = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "probe", "version": "0"},
    },
}
LIST: dict[str, object] = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


def first_sse_data(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("data:"):
            return line[5:].strip()[:160]
    return text[:160]


async def probe_legacy_sessions(base: str, label: str) -> None:
    section(f"5: 레거시(2025-06-18) 핸드셰이크 세션 ({label})")
    async with httpx2.AsyncClient() as http:
        r = await http.post(f"{base}/mcp", json=INIT, headers=HDRS)
        sid = r.headers.get("mcp-session-id")
        print("initialize ->", r.status_code, "Mcp-Session-Id:", sid)
        if sid:
            await http.post(
                f"{base}/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers={**HDRS, "Mcp-Session-Id": sid},
            )
            r = await http.post(f"{base}/mcp", json=LIST, headers={**HDRS, "Mcp-Session-Id": sid})
            print("tools/list with own session id ->", r.status_code, first_sse_data(r.text))
        r = await http.post(f"{base}/mcp", json=LIST, headers={**HDRS, "Mcp-Session-Id": "0" * 32})
        print(
            "tools/list with unknown session id (다른 워커가 받은 꼴) ->",
            r.status_code,
            r.text[:160],
        )
        r = await http.post(f"{base}/mcp", json=LIST, headers=HDRS)
        print(
            "tools/list with no session id, no initialize ->", r.status_code, first_sse_data(r.text)
        )
    async with Client(f"{base}/mcp", mode="legacy") as client:
        tools = [t.name for t in (await client.list_tools()).tools]
        print("SDK Client(mode='legacy') negotiated:", client.protocol_version, "| tools:", tools)


async def probe_host_no_port(base: str) -> None:
    section("1: allowed_hosts=['kb.example.com:*'] 에 포트 없는 Host")
    async with httpx2.AsyncClient() as http:
        for host in ("kb.example.com", "kb.example.com:443", "KB.example.com:443"):
            r = await http.post(f"{base}/mcp", json=LIST, headers={**HDRS, "Host": host})
            print(f"Host={host} ->", r.status_code, r.text[:80].replace("\n", " "))


def walk(e: BaseException, depth: int = 0) -> None:
    print("  " * depth + f"{type(e).__module__}.{type(e).__name__}: {str(e)[:160]}")
    if is_group(e):
        for sub in e.exceptions:
            walk(sub, depth + 1)
    elif e.__cause__ is not None:
        walk(e.__cause__, depth + 1)


async def probe_401_chain(base: str) -> None:
    section("2: 401 때 SDK Client 예외 사슬")
    try:
        async with Client(f"{base}/mcp") as client:
            await client.list_tools()
    except BaseException as exc:
        walk(exc)
    try:
        async with Client(f"{base}/mcp", mode="legacy") as client:
            await client.list_tools()
    except BaseException as exc:
        inner = exc.exceptions[0] if is_group(exc) else exc
        name = type(inner).__module__ + "." + type(inner).__name__
        print("mode='legacy' ->", name, str(inner)[:160])


def main() -> None:
    mcp = build_mcp()
    with serve(wrap_fastapi(mcp, mcp.streamable_http_app())) as base:
        asyncio.run(probe_legacy_sessions(base, "기본 stateful"))

    mcp = build_mcp()
    with serve(wrap_fastapi(mcp, mcp.streamable_http_app(stateless_http=True))) as base:
        asyncio.run(probe_legacy_sessions(base, "stateless_http=True"))

    mcp = build_mcp()
    ts = TransportSecuritySettings(allowed_hosts=["kb.example.com:*"])
    with serve(wrap_fastapi(mcp, mcp.streamable_http_app(transport_security=ts))) as base:
        asyncio.run(probe_host_no_port(base))

    mcp = build_mcp()
    with serve(wrap_fastapi(mcp, mcp.streamable_http_app(), middleware=Deny401)) as base:
        asyncio.run(probe_401_chain(base))

    section("끝")


if __name__ == "__main__":
    main()
