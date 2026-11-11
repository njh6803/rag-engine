"""MCP 도구 `search`(명세 "검색 흐름", "MCP 도구", 티켓 07, 09).

도구 처리기는 미들웨어가 판정해 scope에 둔 토큰 레코드를 읽어 토큰이 닿는 지식베이스를 가린다.
결과는 `SearchOutput`이고 outputSchema가 된다. 오류는 `isError`가 참인 결과다(`tool_support`). 질의
글은 로그에도 응답에도 싣지 않고 지연만 남긴다(원칙 V).
"""

import logging
import time
from datetime import datetime
from typing import Annotated, Final

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from starlette.types import Scope

from rag_engine.adapters.log_format import log_event
from rag_engine.app.search import SearchDeps, SearchRequest, SearchResults, search_documents
from rag_engine.domain.entities import SearchHit
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.server.auth import authenticated_token
from rag_engine.server.request_context import request_id_of
from rag_engine.server.tool_models import (
    FORMAT_VERSION,
    SearchFilterInput,
    SearchLocation,
    SearchOutput,
    SearchResult,
)
from rag_engine.server.tool_support import METADATA, request_scope, run_guarded

logger = logging.getLogger(__name__)

_MS_PER_SECOND: Final = 1000.0
TOOL_NAME: Final = "search"
_DESCRIPTION: Final = (
    "지식베이스에서 질의와 가까운 문서 조각을 찾는다. 결과마다 근거 위치(쪽, 절, 블록)와"
    " 문서의 갱신일, 점수가 붙고 점수가 큰 순서다. 지식베이스를 주지 않으면 기본 지식베이스를 쓴다."
    " filter로 그룹과 갱신일 기간을 좁힐 수 있다."
)


def _result(hit: SearchHit, rank: int) -> SearchResult:
    return SearchResult(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        source=hit.source,
        key=hit.key,
        title=hit.title,
        text=hit.text,
        location=SearchLocation(
            page=hit.location.page,
            section=list(hit.location.section),
            block_kind=hit.location.block_kind,
            block_range=hit.location.block_range,
        ),
        updated_at=hit.updated_at,
        effective_date=hit.effective_date,
        access_groups=list(hit.access_groups),
        metadata=METADATA.validate_python(hit.metadata),
        score=hit.score,
        rank=rank,
    )


def _output(found: SearchResults) -> CallToolResult:
    output = SearchOutput(
        format_version=FORMAT_VERSION,
        knowledge_base=found.knowledge_base,
        results=[_result(hit, rank) for rank, hit in enumerate(found.hits, start=1)],
    )
    return CallToolResult(
        content=[TextContent(type="text", text=output.model_dump_json())],
        structured_content=output.model_dump(mode="json"),
    )


def _instant(value: str | None) -> datetime | None:
    """오프셋이 붙은 ISO 8601 시각을 읽는다. 오프셋이 없거나 읽을 수 없으면 `invalid_argument`다.
    오류 메시지에 입력 값을 싣지 않는다."""
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise RequestError(
            ErrorCode.INVALID_ARGUMENT, "시각은 오프셋이 붙은 ISO 8601 형식이어야 한다"
        ) from None
    if parsed.utcoffset() is None:
        raise RequestError(ErrorCode.INVALID_ARGUMENT, "시각에 오프셋(Z나 +09:00)이 없다")
    return parsed


def _request(
    scope: Scope,
    query: str,
    top_k: int,
    knowledge_base: str | None,
    search_filter: SearchFilterInput | None,
) -> SearchRequest:
    given = search_filter or SearchFilterInput()
    return SearchRequest(
        query=query,
        top_k=top_k,
        knowledge_base=knowledge_base,
        allowed_knowledge_base_ids=authenticated_token(scope).knowledge_base_ids,
        groups=None if given.groups is None else tuple(given.groups),
        updated_after=_instant(given.updated_after),
        updated_before=_instant(given.updated_before),
    )


def register_search_tool(mcp: MCPServer, deps: SearchDeps, *, default_top_k: int) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    async def search(
        query: str,
        ctx: Context,
        top_k: int | None = None,
        knowledge_base: str | None = None,
        filter: SearchFilterInput | None = None,
    ) -> Annotated[CallToolResult, SearchOutput]:
        scope = request_scope(ctx)

        async def call() -> CallToolResult:
            request = _request(
                scope, query, default_top_k if top_k is None else top_k, knowledge_base, filter
            )
            started = time.perf_counter()
            found = await search_documents(deps, request)
            log_event(
                logger,
                "search",
                request_id=request_id_of(scope),
                duration_ms=(time.perf_counter() - started) * _MS_PER_SECOND,
                embedding_ms=found.timings.embedding_ms,
                sql_ms=found.timings.sql_ms,
                rerank_ms=found.timings.rerank_ms,
            )
            return _output(found)

        return await run_guarded(TOOL_NAME, scope, call)
