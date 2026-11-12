"""수집 API → 작업자 한 번 돌기 → MCP `search`의 왕복 시험 도우미(티켓 07).

실제 uvicorn 서버(기본 레코드가 든 데이터베이스)에 REST로 수집하고, 작업자는 같은 설정으로 한 번
돌리며, 검색은 공식 MCP SDK의 클라이언트로 `/mcp`에 HTTP 접속해 부른다. 임베딩 서버만 `TeiStub`이고,
서버와 작업자가 각자 클라이언트로 접속하도록 실제 HTTP 포트에 띄운다. 기본 판의 끝점을 그 주소로
고친다.
"""

import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Final

import httpx
import httpx2
import psycopg
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent
from tests.harness import RunningServer
from tests.records import make_index_version, make_knowledge_base
from tests.support.docx_files import docx_bytes
from tests.support.tei_server import serve_stub
from tests.support.tei_stub import TeiStub

from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import Group, IndexVersionStatus
from rag_engine.domain.identifiers import new_id
from rag_engine.server.tool_models import DocumentOutput, KnowledgeBasesOutput, SearchOutput
from rag_engine.worker.assembly import run_once_with_settings

INGEST_PATH: Final = "/api/v1/ingest/documents"
TOKEN_PATH: Final = "/api/v1/admin/tokens"
# 기본 판의 차원은 `RAG_DEFAULT_EMBEDDING_DIMENSIONS`의 기본값이다. 스텁이 같은 차원으로 낸다.
DEFAULT_DIMENSIONS: Final = 1024


def new_stub() -> TeiStub:
    return TeiStub(dimensions=DEFAULT_DIMENSIONS)


def new_reranker_stub() -> TeiStub:
    """기본 지식베이스의 리랭커 설정(`RAG_DEFAULT_RERANKER_MODEL`의 기본값)이 가리키는 모델이다."""
    return TeiStub(model_id="BAAI/bge-reranker-v2-m3")


def point_default_version_at(server: RunningServer, endpoint: str) -> None:
    """기본 판에 적힌 임베딩 끝점을 스텁 주소로 고친다. 서버와 작업자는 판에 적힌 끝점을 쓴다."""
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE index_versions SET embedding_endpoint = %s", [endpoint])


def point_default_reranker_at(server: RunningServer, endpoint: str) -> None:
    """기본 지식베이스에 적힌 리랭커 끝점을 스텁 주소로 고친다."""
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE knowledge_bases SET reranker_endpoint = %s", [endpoint])


@dataclass(frozen=True, slots=True)
class RoundTrip:
    server: RunningServer
    stub: TeiStub
    reranker_stub: TeiStub
    embedding_endpoint: str

    def auth(self, token: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token or self.server.admin_token}"}

    async def ingest(
        self,
        title: str,
        *paragraphs: str,
        filename: str = "규정.docx",
        fields: dict[str, str] | None = None,
    ) -> httpx.Response:
        """`fields`는 수집 API의 폼 칸(`group`, `metadata`, `updated_at`)이다. DOCX 바이트에는
        만든 시각이 들어 같은 글도 부를 때마다 달라진다. 같은 바이트를 다시 넣으려면
        `ingest_bytes`를 쓴다."""
        return await self.ingest_bytes(docx_bytes(title, *paragraphs), filename, fields)

    async def ingest_bytes(
        self, data: bytes, filename: str = "규정.docx", fields: dict[str, str] | None = None
    ) -> httpx.Response:
        async with httpx.AsyncClient() as http:
            return await http.post(
                self.server.base_url + INGEST_PATH,
                headers=self.auth(),
                files={"file": (filename, data)},
                data=fields,
            )

    async def delete(self, key: str, *, token: str | None = None) -> httpx.Response:
        """수집 API의 삭제. 키는 URL 인코딩한 쿼리 매개변수다."""
        async with httpx.AsyncClient() as http:
            return await http.delete(
                self.server.base_url + INGEST_PATH, headers=self.auth(token), params={"key": key}
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

    def add_group(self, name: str, *knowledge_bases: str) -> None:
        """그룹을 더하고 이름을 준 지식베이스의 그룹 집합에 넣는다."""
        with psycopg.connect(self.server.settings.database_url, autocommit=True) as connection:
            connection.execute(
                "INSERT INTO groups (id, name) VALUES (gen_random_uuid(), %s)", [name]
            )
        self.link_group(name, *knowledge_bases)

    async def add_group_with_knowledge_base(self, group: str, knowledge_base: str) -> None:
        """그룹 하나와 그 그룹만 든 지식베이스(첫 현재 판 포함)를 `Catalog` 어댑터로 만든다. 임베딩
        끝점은 기본 판과 같은 스텁이고 리랭커는 없다."""
        engine = create_engine(self.server.settings.database_url)
        try:
            unit_of_work = PostgresUnitOfWork(engine)
            new_group = Group(new_id(), group, "")
            base = replace(
                make_knowledge_base(knowledge_base), embedding_endpoint=self.embedding_endpoint
            )
            version = make_index_version(base, IndexVersionStatus.CURRENT)
            async with unit_of_work.begin() as transaction:
                await transaction.catalog.add_group(new_group)
                await transaction.catalog.add_knowledge_base(base)
                await transaction.catalog.add_group_to_knowledge_base(base.id, new_group.id)
                await transaction.catalog.add_index_version(version)
                await transaction.index.create_version_index(version)
                await transaction.catalog.switch_current_version(base.id, version.id)
        finally:
            await engine.dispose()

    def link_group(self, group: str, *knowledge_bases: str) -> None:
        """있는 그룹을 이름을 준 지식베이스의 그룹 집합에 넣는다."""
        with psycopg.connect(self.server.settings.database_url, autocommit=True) as connection:
            for knowledge_base in knowledge_bases:
                connection.execute(
                    "INSERT INTO knowledge_base_groups (knowledge_base_id, group_id)"
                    " SELECT knowledge_bases.id, groups.id FROM knowledge_bases, groups"
                    " WHERE knowledge_bases.name = %s AND groups.name = %s",
                    [knowledge_base, group],
                )

    def point_knowledge_bases_at_stub(self) -> None:
        """모든 지식베이스 행의 임베딩 끝점을 스텁 주소로 맞춘다. 재색인이 만드는 새 판은 지식베이스
        행의 끝점을 쓰는데, `wire_stubs`는 옛 판의 끝점만 고쳐 두기 때문이다."""
        with psycopg.connect(self.server.settings.database_url, autocommit=True) as connection:
            connection.execute(
                "UPDATE knowledge_bases SET embedding_endpoint = %s", [self.embedding_endpoint]
            )

    def change_settings(self, chunk_tokens: int = 64) -> None:
        """모든 지식베이스 설정의 청킹 크기를 고쳐 "재색인 필요"를 만든다. 끝점도 스텁 주소로
        맞춘다."""
        with psycopg.connect(self.server.settings.database_url, autocommit=True) as connection:
            connection.execute(
                "UPDATE knowledge_bases SET chunk_tokens = %s, chunk_overlap_tokens = 8",
                [chunk_tokens],
            )
        self.point_knowledge_bases_at_stub()

    async def reindex(self, name: str = "default") -> httpx.Response:
        """관리 API의 재색인 시작."""
        async with httpx.AsyncClient() as http:
            return await http.post(
                self.server.base_url + f"/api/v1/admin/knowledge-bases/{name}/reindex",
                headers=self.auth(),
            )

    def drop_reranker(self) -> None:
        """기본 지식베이스에서 리랭커 설정을 지운다. 검색은 RRF 점수로 나간다."""
        with psycopg.connect(self.server.settings.database_url, autocommit=True) as connection:
            connection.execute(
                "UPDATE knowledge_bases SET reranker_endpoint = NULL, reranker_model = NULL"
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

    async def call(
        self, tool: str, arguments: dict[str, object], *, token: str | None = None
    ) -> CallToolResult:
        async with httpx2.AsyncClient(headers=self.auth(token)) as http:
            async with Client(
                streamable_http_client(self.server.mcp_url, http_client=http)
            ) as client:
                return await client.call_tool(tool, arguments)

    async def search(
        self, query: str, *, token: str | None = None, **arguments: object
    ) -> CallToolResult:
        return await self.call("search", {"query": query, **arguments}, token=token)

    async def get_document(
        self, document_id: object, *, token: str | None = None, **arguments: object
    ) -> CallToolResult:
        return await self.call(
            "get_document", {"document_id": str(document_id), **arguments}, token=token
        )

    async def list_knowledge_bases(self, *, token: str | None = None) -> CallToolResult:
        return await self.call("list_knowledge_bases", {}, token=token)


@contextmanager
def wire_stubs(server: RunningServer) -> Generator[RoundTrip]:
    """임베딩 스텁과 리랭커 스텁을 실제 포트에 띄우고 서버의 기본 판과 기본 지식베이스가 그 주소를
    쓰게 한 왕복 도우미를 낸다. 블록을 나가면 스텁을 내린다."""
    stub = new_stub()
    reranker_stub = new_reranker_stub()
    with serve_stub(stub) as endpoint, serve_stub(reranker_stub) as reranker_endpoint:
        point_default_version_at(server, endpoint)
        point_default_reranker_at(server, reranker_endpoint)
        yield RoundTrip(server, stub, reranker_stub, endpoint)


def output(result: CallToolResult) -> SearchOutput:
    """성공한 도구 결과를 출력 모델로 읽는다. 모델에 맞지 않으면 검증 오류로 실패한다."""
    assert result.is_error is not True
    return SearchOutput.model_validate(result.structured_content)


def document_output(result: CallToolResult) -> DocumentOutput:
    assert result.is_error is not True
    return DocumentOutput.model_validate(result.structured_content)


def knowledge_bases_output(result: CallToolResult) -> KnowledgeBasesOutput:
    assert result.is_error is not True
    return KnowledgeBasesOutput.model_validate(result.structured_content)


def error_body(result: CallToolResult) -> dict[str, object]:
    """도구 오류 결과의 글 내용(Problem Details 모양의 JSON)."""
    assert result.is_error is True, "도구 오류가 아니라 결과를 냈다"
    (content,) = result.content
    assert isinstance(content, TextContent)
    body: dict[str, object] = json.loads(content.text)
    return body
