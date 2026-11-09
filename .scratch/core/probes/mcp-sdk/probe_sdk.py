"""mcp 2.3.0 확인 스크립트. 서버를 uvicorn 스레드로 띄우고 SDK 클라이언트와 raw httpx2 로 쳐 본다.

보는 것(절 번호는 설계 인터뷰의 질문 번호):
1. 전송 보안. 기본값(host 127.0.0.1)에서 다른 Host 헤더가 421, 다른 Origin 이 403 인지,
   `allowed_hosts` 의 `kb.example.com:*` 와일드카드가 포트 달린 Host 를 통과시키는지, host='0.0.0.0'
   을 주면 자동 켜짐이 빠지는지.
2. 인증. 마운트한 MCP 앱 앞의 순수 ASGI 미들웨어가 고정 베어러 토큰 없는 요청을 401 로 막는지, SDK
   의 `token_verifier`+`AuthSettings` 길에서 401 응답과 `/.well-known/oauth-protected-resource/mcp`
   가 어떻게 나오는지, `AuthSettings` 가 어떤 인자 조합에서 만들어지고 경고하는지.
3/4. 도구 목록의 outputSchema(pydantic 모델, TypedDict, str, list, structured_output=False)와
   structuredContent, 도구 안 `Context` 에서 `_meta`·헤더·세션 ID 를 읽을 수 있는지.
5. 세션 모드. 기본(stateful, SSE)과 stateless_http=True+json_response=True 에서 레거시 initialize 의
   Mcp-Session-Id 와 content-type.

실행: uv run python .scratch/core/probes/mcp-sdk/probe_sdk.py
(저장소 루트에서. 127.0.0.1 의 빈 포트에 서버를 띄우고 바깥 네트워크는 쓰지 않는다.)
타입 검사: uv run pyright 는 저장소 설정의 기본 exclude(`**/.*`) 때문에 `.scratch` 아래를 0개 파일로
지나가므로, exclude 를 비운 임시 pyrightconfig 로 `uv run pyright -p <그 설정> <이 폴더>` 를 돌린다.

2026-11-09에 돌렸다(출력 `probe_out.txt`). 기본값에서 Host=example.com 421, Origin=evil 403;
allowed_hosts 와일드카드로 kb.example.com:8443 통과; host='0.0.0.0' 이면 Host·Origin 판정이 모두
빠진다(400 세션 없음까지 간다). ASGI 미들웨어는 401+WWW-Authenticate 를 내고 SDK Client 는
ExceptionGroup 으로 실패한다. AuthSettings 는 issuer_url 만으로는 ValidationError,
validate_token_resource 를 안 주면 MCPDeprecationWarning, token_verifier 는 auth 없이 ValueError.
token_verifier 길에서는 401 에 resource_metadata 가 붙고 `/.well-known/oauth-protected-resource/mcp`
가 200 이다. 도구는 모델·TypedDict 가 그대로, str·list 는 `{"result": ...}` 로 싸인 outputSchema 를
내고, `_meta.principal` 이 도구 `Context` 의 request_context.meta 로 닿으며 헤더도 읽힌다. 세션은
기본이 레거시 initialize 에 Mcp-Session-Id 와 text/event-stream, stateless+json_response 는 세션 ID
없이 application/json 이다.

잰 판(2026-11-09, `uv run python -c` 로 importlib.metadata 를 손으로 봤다): mcp 2.3.0, httpx2
2.16.0, fastapi 0.162.2, uvicorn 0.54.0, starlette 1.10.0, pydantic 2.14.3.

저장소로 옮기며(2026-11-09) 원칙 II(`Any`·`type: ignore` 금지)와 pyright strict 에 맞춰 타입만
고쳤고, 옮긴 뒤 다시 돌려 `probe_out.txt` 와 무작위 Mcp-Session-Id 한 줄만 다름을 봤다.
`**kwargs: Any` → 명시 인자, `dict[str, Any]` → `dict[str, object]`(pydantic 은 둘 다 any 스키마),
`hasattr`+속성 접근 → `getattr`, `AuthSettings(...)` → `AuthSettings.model_validate({...})`(같은
검증기를 지난다), `content[0].text` → TextContent 로 좁히기, ExceptionGroup 의 첫 하위 예외 꺼내기를
함수로.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
import warnings
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import TypedDict, TypeGuard

import httpx2
import uvicorn
from fastapi import FastAPI
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import TextContent, ToolAnnotations
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

warnings.simplefilter("default")
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.ERROR)


def section(title: str) -> None:
    print(f"\n===== {title} =====")


def is_group(exc: BaseException) -> TypeGuard[BaseExceptionGroup[BaseException]]:
    """isinstance 만으로 좁히면 pyright 가 하위 예외를 Unknown 으로 읽어 TypeGuard 로 감쌌다."""
    return isinstance(exc, BaseExceptionGroup)


def unwrap(exc: BaseException) -> BaseException:
    """ExceptionGroup 이면 첫 하위 예외를 돌려준다(한 겹만)."""
    return exc.exceptions[0] if is_group(exc) else exc


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


class Hit(BaseModel):
    doc_id: str
    score: float


class SearchResult(BaseModel):
    hits: list[Hit]
    total: int


class TDResult(TypedDict):
    answer: str
    n: int


def build_mcp(
    token_verifier: TokenVerifier | None = None, auth: AuthSettings | None = None
) -> MCPServer:
    mcp = MCPServer(name="probe", log_level="ERROR", token_verifier=token_verifier, auth=auth)

    @mcp.tool(
        name="search",
        description="검색",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )
    def search(query: str, top_k: int = 3) -> SearchResult:
        return SearchResult(hits=[Hit(doc_id="d1", score=0.9)], total=1)

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    def typed_dict_tool(x: int) -> TDResult:
        return {"answer": "ok", "n": x}

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    def str_tool(x: int) -> str:
        return str(x)

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    def list_tool(x: int) -> list[str]:
        return [str(x)]

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True), structured_output=False)
    def unstructured_tool(x: int) -> SearchResult:
        return SearchResult(hits=[], total=0)

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    def whoami(ctx: Context) -> dict[str, object]:
        headers = ctx.headers
        rc = ctx.request_context
        req = rc.request
        token = get_access_token()
        # 2.3.0 의 ServerSession 에는 connection 속성이 없다(출력의 "n/a"). 있을 때만 세션 ID 를
        # 읽는다.
        connection: object | None = getattr(ctx.session, "connection", None)
        session_id = getattr(connection, "session_id", "n/a") if connection is not None else "n/a"
        return {
            "meta": dict(rc.meta) if rc.meta is not None else None,
            "ctx_headers_type": type(headers).__name__ if headers is not None else None,
            "authorization_via_ctx_headers": (
                headers.get("authorization") if headers is not None else None
            ),
            "x_subject_via_ctx_headers": headers.get("x-subject") if headers is not None else None,
            "request_type": type(req).__name__ if req is not None else None,
            "authorization_via_request": (
                req.headers.get("authorization") if req is not None else None
            ),
            "protocol_version": rc.protocol_version,
            "session_id": session_id,
            "access_token_client_id": token.client_id if token is not None else None,
            "access_token_scopes": token.scopes if token is not None else None,
        }

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


class FixedBearerMiddleware:
    """마운트한 MCP 앱 앞에 두는 순수 ASGI 미들웨어. /mcp 에만 고정 베어러 토큰을 요구한다."""

    TOKEN = "secret-token"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            auth = next((v.decode() for k, v in scope["headers"] if k == b"authorization"), None)
            if auth != f"Bearer {self.TOKEN}":
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
                return
        await self.app(scope, receive, send)


async def probe_tools_and_context(base: str) -> None:
    section("3/4: 도구 목록(outputSchema), structuredContent, Context 로 _meta/헤더 읽기")
    http = httpx2.AsyncClient(headers={"Authorization": "Bearer abc123", "X-Subject": "alice"})
    async with http:
        transport = streamable_http_client(f"{base}/mcp", http_client=http)
        async with Client(transport) as client:
            print("negotiated protocol_version:", client.protocol_version)
            tools = await client.list_tools()
            for t in tools.tools:
                hint = t.annotations.read_only_hint if t.annotations else None
                print(f"- {t.name}: read_only_hint={hint}")
                print("    inputSchema:", json.dumps(t.input_schema, ensure_ascii=False))
                print(
                    "    outputSchema:",
                    json.dumps(t.output_schema, ensure_ascii=False) if t.output_schema else None,
                )
            r = await client.call_tool("search", {"query": "q"})
            print("search structured_content:", r.structured_content)
            print("search content:", [c.model_dump(mode="json") for c in r.content])
            r = await client.call_tool("typed_dict_tool", {"x": 2})
            print("typed_dict_tool structured_content:", r.structured_content)
            r = await client.call_tool("str_tool", {"x": 2})
            print("str_tool structured_content:", r.structured_content)
            r = await client.call_tool("list_tool", {"x": 2})
            print("list_tool structured_content:", r.structured_content)
            r = await client.call_tool("unstructured_tool", {"x": 2})
            first = r.content[0]
            text = first.text if isinstance(first, TextContent) else first
            print("unstructured_tool structured_content:", r.structured_content, "| content:", text)
            r = await client.call_tool(
                "whoami", {}, meta={"principal": {"subject": "alice", "groups": ["g1"]}}
            )
            print(
                "whoami structured_content:",
                json.dumps(r.structured_content, ensure_ascii=False, indent=1),
            )


async def probe_host_header(base: str, label: str) -> None:
    section(f"1: Host 헤더 판정 ({label})")
    async with httpx2.AsyncClient() as http:
        body: dict[str, object] = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
        hdrs = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        r = await http.post(f"{base}/mcp", json=body, headers=hdrs)
        print("Host=127.0.0.1:port ->", r.status_code, r.text[:120].replace("\n", " "))
        r = await http.post(f"{base}/mcp", json=body, headers={**hdrs, "Host": "example.com"})
        print("Host=example.com ->", r.status_code, r.text[:120].replace("\n", " "))
        r = await http.post(
            f"{base}/mcp", json=body, headers={**hdrs, "Host": "kb.example.com:8443"}
        )
        print("Host=kb.example.com:8443 ->", r.status_code, r.text[:120].replace("\n", " "))
        r = await http.post(
            f"{base}/mcp", json=body, headers={**hdrs, "Origin": "http://evil.example"}
        )
        print("Origin=http://evil.example ->", r.status_code, r.text[:120].replace("\n", " "))


async def probe_fixed_bearer(base: str) -> None:
    section("2: Starlette/ASGI 미들웨어로 고정 베어러 토큰")
    async with httpx2.AsyncClient() as http:
        r = await http.post(
            f"{base}/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )
        print("raw no token ->", r.status_code, dict(r.headers).get("www-authenticate"), r.text)
        r = await http.get(f"{base}/health")
        print("raw /health no token ->", r.status_code)
    try:
        async with Client(f"{base}/mcp") as client:
            await client.list_tools()
        print("SDK Client no token -> 성공(예상 밖)")
    except BaseException as exc:
        inner = unwrap(exc)
        print(
            "SDK Client no token -> 예외:",
            type(exc).__name__,
            "/",
            type(inner).__name__,
            str(inner)[:200],
        )
    http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {FixedBearerMiddleware.TOKEN}"})
    async with http:
        async with Client(streamable_http_client(f"{base}/mcp", http_client=http)) as client:
            tools = await client.list_tools()
            print("SDK Client with token -> tools:", [t.name for t in tools.tools][:3])


class StaticVerifier:
    def __init__(self, accepted: str) -> None:
        self.accepted = accepted

    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self.accepted:
            return AccessToken(token=token, client_id="fixed-client", scopes=["read"])
        return None


async def probe_sdk_token_verifier(base: str) -> None:
    section("2: SDK 의 token_verifier + AuthSettings 로 베어러 검증")
    async with httpx2.AsyncClient() as http:
        body: dict[str, object] = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
        hdrs = {"Accept": "application/json, text/event-stream"}
        r = await http.post(f"{base}/mcp", json=body, headers=hdrs)
        print("no token ->", r.status_code, dict(r.headers).get("www-authenticate"), r.text)
        r = await http.post(
            f"{base}/mcp", json=body, headers={**hdrs, "Authorization": "Bearer wrong"}
        )
        print("wrong token ->", r.status_code, r.text)
        r = await http.get(f"{base}/.well-known/oauth-protected-resource")
        print("GET /.well-known/oauth-protected-resource ->", r.status_code, r.text[:200])
        r = await http.get(f"{base}/.well-known/oauth-protected-resource/mcp")
        print("GET /.well-known/oauth-protected-resource/mcp ->", r.status_code, r.text[:200])
    http = httpx2.AsyncClient(headers={"Authorization": "Bearer good"})
    async with http:
        async with Client(streamable_http_client(f"{base}/mcp", http_client=http)) as client:
            r = await client.call_tool("whoami", {})
            sc = r.structured_content
            print(
                "good token -> whoami access_token:",
                sc["access_token_client_id"],
                sc["access_token_scopes"],
            )


async def probe_session_modes(base: str, label: str) -> None:
    section(f"5: 세션 모드 ({label})")
    async with httpx2.AsyncClient() as http:
        hdrs = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        init: dict[str, object] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0"},
            },
        }
        r = await http.post(f"{base}/mcp", json=init, headers=hdrs)
        print(
            "legacy initialize ->",
            r.status_code,
            "content-type:",
            r.headers.get("content-type"),
            "Mcp-Session-Id:",
            r.headers.get("mcp-session-id"),
        )
        modern: dict[str, object] = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "ping",
            "params": {"_meta": {}},
        }
        r = await http.post(
            f"{base}/mcp", json=modern, headers={**hdrs, "MCP-Protocol-Version": "2026-07-28"}
        )
        print(
            "modern ping (2026-07-28) ->",
            r.status_code,
            "content-type:",
            r.headers.get("content-type"),
            "Mcp-Session-Id:",
            r.headers.get("mcp-session-id"),
            r.text[:160].replace("\n", " "),
        )
    async with Client(f"{base}/mcp") as client:
        print("SDK Client negotiated:", client.protocol_version)
        r = await client.call_tool("whoami", {})
        print("whoami session_id:", r.structured_content["session_id"])


def main() -> None:
    # --- 1. transport_security 기본값 (host 인자 기본 127.0.0.1 → 자동 켜짐)
    mcp = build_mcp()
    app = wrap_fastapi(mcp, mcp.streamable_http_app())
    with serve(app) as base:
        asyncio.run(probe_host_header(base, "기본값: transport_security=None, host=127.0.0.1"))
        asyncio.run(probe_tools_and_context(base))
        asyncio.run(probe_session_modes(base, "기본: stateful, SSE"))

    # --- 1b. 와일드카드 포트 허용
    mcp = build_mcp()
    ts = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["kb.example.com:*", "127.0.0.1:*"],
        allowed_origins=["https://kb.example.com:*"],
    )
    app = wrap_fastapi(mcp, mcp.streamable_http_app(transport_security=ts))
    with serve(app) as base:
        asyncio.run(probe_host_header(base, "allowed_hosts=['kb.example.com:*','127.0.0.1:*']"))

    # --- 1c. host 를 0.0.0.0 으로 주면 자동 켜짐이 빠진다
    mcp = build_mcp()
    app = wrap_fastapi(mcp, mcp.streamable_http_app(host="0.0.0.0"))
    with serve(app) as base:
        asyncio.run(probe_host_header(base, "transport_security=None, host='0.0.0.0'"))

    # --- 2a. ASGI 미들웨어 고정 토큰
    mcp = build_mcp()
    app = wrap_fastapi(mcp, mcp.streamable_http_app(), middleware=FixedBearerMiddleware)
    app.add_api_route("/health", lambda: {"status": "ok"}, methods=["GET"])
    with serve(app) as base:
        asyncio.run(probe_fixed_bearer(base))

    # --- 2b. SDK token_verifier
    section("2: AuthSettings 생성")
    try:
        # resource_server_url 이 필수인지 본다(일부러 빠뜨린다).
        AuthSettings.model_validate({"issuer_url": "https://issuer.example"})
    except Exception as exc:
        print(
            "AuthSettings(issuer_url only) ->", type(exc).__name__, str(exc).splitlines()[0][:120]
        )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        auth = AuthSettings.model_validate(
            {
                "issuer_url": "https://issuer.example",
                "resource_server_url": "http://127.0.0.1/mcp",
                "validate_token_resource": False,
            }
        )
        print(
            "AuthSettings(issuer_url, resource_server_url, validate_token_resource=False) -> ok;"
            " warnings:",
            [str(w.message)[:80] for w in caught],
        )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        AuthSettings.model_validate(
            {"issuer_url": "https://issuer.example", "resource_server_url": "http://127.0.0.1/mcp"}
        )
        print(
            "AuthSettings(... validate_token_resource unset) -> warnings:",
            [type(w.message).__name__ for w in caught],
        )
    try:
        MCPServer(name="x", token_verifier=StaticVerifier("good"))
    except Exception as exc:
        print("MCPServer(token_verifier without auth) ->", type(exc).__name__, str(exc)[:120])
    mcp = build_mcp(token_verifier=StaticVerifier("good"), auth=auth)
    app = wrap_fastapi(mcp, mcp.streamable_http_app())
    with serve(app) as base:
        asyncio.run(probe_sdk_token_verifier(base))

    # --- 5. stateless + json_response
    mcp = build_mcp()
    app = wrap_fastapi(mcp, mcp.streamable_http_app(stateless_http=True, json_response=True))
    with serve(app) as base:
        asyncio.run(probe_session_modes(base, "stateless_http=True, json_response=True"))

    section("끝")


if __name__ == "__main__":
    main()
