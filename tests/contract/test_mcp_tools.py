"""MCP 계약 시험. 공식 SDK 의 클라이언트로 서버에 HTTP 접속해 도구 목록을 본다(operations.md 검증).

core 가 검색 도구를 만들기 전에는 MCP 도구 목록에 쓰기 도구가 없음만 본다(원칙 IV, ADR 0001).
"""

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from mcp import Client

from rag_engine.server import create_app

STARTUP_TIMEOUT_SECONDS = 10


@pytest.fixture
def mcp_url() -> Iterator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail(f"uvicorn 이 {STARTUP_TIMEOUT_SECONDS}초 안에 뜨지 않았다")
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(STARTUP_TIMEOUT_SECONDS)


async def test_MCP_도구_목록에는_읽기_전용이_아닌_도구가_없다(mcp_url: str) -> None:
    async with Client(mcp_url) as client:
        result = await client.list_tools()

    writable = [
        tool.name
        for tool in result.tools
        if tool.annotations is None or tool.annotations.read_only_hint is not True
    ]
    assert writable == []
