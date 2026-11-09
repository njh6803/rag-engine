"""mcp 2.3.0: 전송 모드별로 요청 하나 안의 진행률 알림(notifications/progress)이 클라이언트에 닿는지
본다.

모드 셋: 기본(세션 유지, SSE), stateless_http=True + SSE, stateless_http=True + json_response=True.
도구가 report_progress 를 세 번 부르고, 클라이언트의 progress_callback 이 몇 번 불리는지 센다.

실행: uv run python .scratch/core/probes/mcp-sdk/probe_progress.py
(저장소 루트에서. 127.0.0.1 의 빈 포트에 서버를 띄우고 바깥 네트워크는 쓰지 않는다.)
타입 검사는 probe_sdk.py 독스트링의 방법대로.

2026-11-09에 돌렸다(출력 `probe_progress_out.txt`). 세션 유지+SSE 와 stateless+SSE 는
progress_callback 이 3번 불렸고, stateless+json_response=True 는 0번이다(JSON 응답 모드에서는 요청
중간의 알림이 전달되지 않는다). 잰 판은 probe_sdk.py 독스트링과 같다(mcp 2.3.0).

저장소로 옮기며(2026-11-09) `@asynccontextmanager` 의 반환 주석을 pyright 가 deprecated 라고 한
`AsyncIterator[None]` 에서 `AsyncGenerator[None]` 으로, `**kwargs: Any` 를 명시 인자로 바꿨고,
선택하지 않은 규칙의 `# noqa: BLE001` 을 지웠다. 옮긴 뒤 다시 돌려 `probe_progress_out.txt` 와 같은
출력을 봤다.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import socket
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from mcp import Client
from mcp.server.mcpserver import Context, MCPServer
from starlette.types import ASGIApp

logging.getLogger("mcp").setLevel(logging.ERROR)


def build() -> MCPServer:
    mcp = MCPServer(name="probe", log_level="ERROR")

    @mcp.tool()
    async def slow(n: int, ctx: Context) -> str:
        for i in range(n):
            await ctx.report_progress(i + 1, n, f"step {i + 1}")
            await asyncio.sleep(0.05)
        return "done"

    return mcp


def wrap(mcp: MCPServer, mcp_app: ASGIApp) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/", mcp_app)
    return app


def start(app: FastAPI) -> tuple[uvicorn.Server, str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(200):
        if server.started:
            return server, f"http://127.0.0.1:{port}"
        time.sleep(0.05)
    raise RuntimeError("uvicorn did not start")


async def call(base: str, label: str) -> None:
    got: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        got.append((progress, total, message))

    async with Client(f"{base}/mcp") as client:
        r = await client.call_tool("slow", {"n": 3}, progress_callback=on_progress)
        text = r.structured_content if r.structured_content is not None else r.content[0]
        print(f"[{label}] result={text} progress_callbacks={len(got)} {got}")


def main() -> None:
    print("call_tool signature:", inspect.signature(Client.call_tool))
    print("report_progress signature:", inspect.signature(Context.report_progress))
    # (이름표, stateless_http, json_response). 첫 모드는 streamable_http_app() 의 기본값 그대로다.
    modes: list[tuple[str, bool, bool]] = [
        ("기본: 세션 유지 + SSE", False, False),
        ("stateless_http=True + SSE", True, False),
        ("stateless_http=True + json_response=True", True, True),
    ]
    for label, stateless_http, json_response in modes:
        mcp = build()
        mcp_app = mcp.streamable_http_app(
            stateless_http=stateless_http, json_response=json_response
        )
        server, base = start(wrap(mcp, mcp_app))
        try:
            asyncio.run(call(base, label))
        except Exception as exc:
            print(f"[{label}] 실패: {type(exc).__name__}: {exc}")
        finally:
            server.should_exit = True
            time.sleep(0.3)


if __name__ == "__main__":
    main()
