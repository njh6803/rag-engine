"""HTTP 표면을 짓는다. REST 와 MCP 를 한 FastAPI 앱이 연다(ADR 0005)."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server import MCPServer


def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    mcp = MCPServer(name="rag-engine")
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        # 마운트한 하위 앱의 lifespan 은 돌지 않아 여기서 세션 관리자를 돌린다(ADR 0005).
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="rag-engine", lifespan=lifespan)
    app.add_api_route("/health", health, methods=["GET"])
    # 하위 앱은 자기 안에 `/mcp` 경로를 둔다. "/" 마운트는 모든 경로를 받으므로 REST 경로 뒤에 둔다.
    app.mount("/", mcp_app)
    return app
