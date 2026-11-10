"""MCP 계약 시험. 공식 SDK 의 클라이언트로 서버에 HTTP 접속해 도구 목록을 본다(operations.md 검증).

core 가 검색 도구를 만들기 전에는 MCP 도구 목록에 쓰기 도구가 없음만 본다(원칙 IV, ADR 0001).
`/mcp`는 토큰으로 닫혀 있어 클라이언트가 베어러 토큰을 실어 접속한다.
"""

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from tests.harness import RunningServer


async def test_MCP_도구_목록에는_읽기_전용이_아닌_도구가_없다(server: RunningServer) -> None:
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {server.admin_token}"}
    ) as http:
        async with Client(streamable_http_client(server.mcp_url, http_client=http)) as client:
            result = await client.list_tools()

    writable = [
        tool.name
        for tool in result.tools
        if tool.annotations is None or tool.annotations.read_only_hint is not True
    ]
    assert writable == []
