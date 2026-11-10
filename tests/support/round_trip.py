"""수집 API → 작업자 한 번 돌기 → MCP `search`의 왕복 시험 도우미(티켓 07).

실제 uvicorn 서버(기본 레코드가 든 데이터베이스)에 REST로 수집하고, 작업자는 같은 설정으로 한 번
돌리며, 검색은 공식 MCP SDK의 클라이언트로 `/mcp`에 HTTP 접속해 부른다. 임베딩 서버만 `TeiStub`이고,
서버와 작업자가 각자 클라이언트로 접속하도록 실제 HTTP 포트에 띄운다. 기본 판의 끝점을 그 주소로
고친다.
"""

import json
from dataclasses import dataclass
from typing import Final

import httpx
import httpx2
import psycopg
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent
from tests.harness import RunningServer
from tests.support.docx_files import docx_bytes
from tests.support.tei_stub import TeiStub

from rag_engine.server.tool_models import SearchOutput
from rag_engine.worker.assembly import run_once_with_settings

INGEST_PATH: Final = "/api/v1/ingest/documents"
TOKEN_PATH: Final = "/api/v1/admin/tokens"
# 기본 판의 차원은 `RAG_DEFAULT_EMBEDDING_DIMENSIONS`의 기본값이다. 스텁이 같은 차원으로 낸다.
DEFAULT_DIMENSIONS: Final = 1024


def new_stub() -> TeiStub:
    return TeiStub(dimensions=DEFAULT_DIMENSIONS)


def point_default_version_at(server: RunningServer, endpoint: str) -> None:
    """기본 판에 적힌 임베딩 끝점을 스텁 주소로 고친다. 서버와 작업자는 판에 적힌 끝점을 쓴다."""
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE index_versions SET embedding_endpoint = %s", [endpoint])


@dataclass(frozen=True, slots=True)
class RoundTrip:
    server: RunningServer
    stub: TeiStub

    def auth(self, token: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token or self.server.admin_token}"}

    async def ingest(
        self, title: str, *paragraphs: str, filename: str = "규정.docx"
    ) -> httpx.Response:
        async with httpx.AsyncClient() as http:
            return await http.post(
                self.server.base_url + INGEST_PATH,
                headers=self.auth(),
                files={"file": (filename, docx_bytes(title, *paragraphs))},
            )

    async def work(self) -> int:
        """작업자를 한 번 돌려 처리한 작업 수를 받는다."""
        return await run_once_with_settings(self.server.settings)

    def add_knowledge_base(self, name: str) -> None:
        """현재 판이 없는 지식베이스 행을 더한다. 범위 판정 시험이 이름만 필요로 한다."""
        with psycopg.connect(self.server.settings.database_url, autocommit=True) as connection:
            connection.execute(
                "INSERT INTO knowledge_bases (id, name, embedding_endpoint, embedding_model,"
                " embedding_dimensions, chunking_strategy, chunk_tokens, chunk_overlap_tokens)"
                " VALUES (gen_random_uuid(), %s, 'http://127.0.0.1:1', 'm', 16,"
                " 'structure', 512, 0)",
                [name],
            )

    async def issue_reader(self, *knowledge_bases: str) -> str:
        """지식베이스 범위를 단 `reader` 토큰의 원문."""
        async with httpx.AsyncClient() as http:
            response = await http.post(
                self.server.base_url + TOKEN_PATH,
                headers=self.auth(),
                json={"name": "범위", "role": "reader", "knowledge_bases": list(knowledge_bases)},
            )
        assert response.status_code == 201
        raw: str = response.json()["token"]
        return raw

    async def search(
        self, query: str, *, token: str | None = None, **arguments: object
    ) -> CallToolResult:
        async with httpx2.AsyncClient(headers=self.auth(token)) as http:
            async with Client(
                streamable_http_client(self.server.mcp_url, http_client=http)
            ) as client:
                return await client.call_tool("search", {"query": query, **arguments})


def output(result: CallToolResult) -> SearchOutput:
    """성공한 도구 결과를 출력 모델로 읽는다. 모델에 맞지 않으면 검증 오류로 실패한다."""
    assert result.is_error is not True
    return SearchOutput.model_validate(result.structured_content)


def error_body(result: CallToolResult) -> dict[str, object]:
    """도구 오류 결과의 글 내용(Problem Details 모양의 JSON)."""
    assert result.is_error is True, "도구 오류가 아니라 결과를 냈다"
    (content,) = result.content
    assert isinstance(content, TextContent)
    body: dict[str, object] = json.loads(content.text)
    return body
