"""mcp 의 도구가 선언하지 않은 입력 인자를 받았을 때의 동작을 본다.

보는 것:
1. 도구 목록의 inputSchema 에 `additionalProperties` 가 실리는지(최상위와 중첩 모델).
2. SDK 클라이언트로 선언하지 않은 최상위 인자(`min_score`)를 함께 보냈을 때 오류인지, 조용히
   무시되는지.
3. 중첩 모델(`filter`) 안의 선언하지 않은 키를 보냈을 때.
4. 대조군. 선언한 인자의 타입이 틀렸을 때의 오류 모양.
5. SDK 클라이언트가 보내기 전에 스스로 거르는지 가리려고, 2와 3의 요청을 raw httpx2 로도 보낸다
   (stateless + JSON 응답).

도구의 모양은 `src/rag_engine/server/search_tool.py` 의 `search` 를 줄인 것이다(선택 인자와 중첩
pydantic 모델). 중첩 모델의 설정은 `tool_models.py` 의 `SearchFilterInput` 처럼 `frozen=True` 만
둔다.

실행: uv run python -X utf8 .scratch/search-eval/probes/mcp-args/probe_unknown_args.py
(저장소 루트에서. 127.0.0.1 의 빈 포트에 서버를 띄우고 바깥 네트워크는 쓰지 않는다.)

2026-11-12에 돌렸다(출력 `probe_unknown_args_out.txt`). 결과 요약은 같은 폴더의 README 표에 있다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from importlib.metadata import version

import httpx2
import uvicorn
from fastapi import FastAPI
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict
from starlette.types import ASGIApp

logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.ERROR)


def section(title: str) -> None:
    print(f"\n===== {title} =====")


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


class FilterInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    groups: list[str] | None = None
    updated_after: str | None = None


class Output(BaseModel):
    echoed_query: str
    echoed_top_k: int | None
    echoed_groups: list[str] | None


def build_mcp() -> MCPServer:
    mcp = MCPServer(name="probe", log_level="ERROR")

    @mcp.tool(name="search", annotations=ToolAnnotations(read_only_hint=True))
    def search(query: str, top_k: int | None = None, filter: FilterInput | None = None) -> Output:
        return Output(
            echoed_query=query,
            echoed_top_k=top_k,
            echoed_groups=None if filter is None else filter.groups,
        )

    return mcp


def wrap(mcp: MCPServer, mcp_app: ASGIApp) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/", mcp_app)
    return app


async def call(client: Client, label: str, arguments: dict[str, object]) -> None:
    try:
        result = await client.call_tool("search", arguments)
    except Exception as exc:
        print(f"{label} -> 예외: {type(exc).__name__}: {str(exc)[:300]}")
        return
    first = result.content[0] if result.content else None
    text = first.text[:300] if isinstance(first, TextContent) else None
    print(
        f"{label} -> is_error={result.is_error}"
        f" structured_content={result.structured_content} text={text}"
    )


async def probe_with_sdk_client(base: str) -> None:
    section("1: 도구 목록의 inputSchema")
    async with Client(f"{base}/mcp") as client:
        print("negotiated protocol_version:", client.protocol_version)
        tools = await client.list_tools()
        for tool in tools.tools:
            schema = tool.input_schema
            print("inputSchema:", json.dumps(schema, ensure_ascii=False))
            print("최상위 additionalProperties:", schema.get("additionalProperties", "(없음)"))
            definitions = schema.get("$defs", {})
            nested = definitions.get("FilterInput", {}) if isinstance(definitions, dict) else {}
            print(
                "FilterInput additionalProperties:",
                nested.get("additionalProperties", "(없음)") if isinstance(nested, dict) else "?",
            )

        section("2~4: SDK 클라이언트로 부르기")
        await call(client, "선언한 인자만", {"query": "q", "top_k": 3})
        await call(
            client, "모르는 최상위 인자 min_score", {"query": "q", "top_k": 3, "min_score": 0.5}
        )
        await call(
            client,
            "중첩 filter 안의 모르는 키",
            {"query": "q", "filter": {"groups": ["g1"], "unknown_key": 1}},
        )
        await call(client, "대조군: top_k 타입 틀림", {"query": "q", "top_k": "많이"})
        await call(client, "대조군: 필수 인자 query 빠짐", {"top_k": 3})


async def probe_raw(base: str) -> None:
    section("5: raw httpx2 로 같은 요청(stateless + JSON 응답)")
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/call",
        "Mcp-Name": "search",
    }
    cases: list[tuple[str, dict[str, object]]] = [
        ("모르는 최상위 인자 min_score", {"query": "q", "top_k": 3, "min_score": 0.5}),
        (
            "중첩 filter 안의 모르는 키",
            {"query": "q", "filter": {"groups": ["g1"], "unknown_key": 1}},
        ),
    ]
    async with httpx2.AsyncClient() as http:
        for request_id, (label, arguments) in enumerate(cases, start=1):
            body: dict[str, object] = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": arguments,
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                        "io.modelcontextprotocol/clientCapabilities": {},
                    },
                },
            }
            response = await http.post(f"{base}/mcp", json=body, headers=headers)
            print(
                f"{label} -> status:",
                response.status_code,
                "content-type:",
                response.headers.get("content-type"),
            )
            print("body:", response.text[:600].replace("\n", " "))


def main() -> None:
    print("mcp", version("mcp"), "| pydantic", version("pydantic"), "| httpx2", version("httpx2"))

    mcp = build_mcp()
    with serve(wrap(mcp, mcp.streamable_http_app())) as base:
        asyncio.run(probe_with_sdk_client(base))

    mcp = build_mcp()
    with serve(wrap(mcp, mcp.streamable_http_app(stateless_http=True, json_response=True))) as base:
        asyncio.run(probe_raw(base))

    section("끝")


if __name__ == "__main__":
    main()
