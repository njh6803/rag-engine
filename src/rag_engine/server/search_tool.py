"""MCP 도구 `search`(명세 "검색 흐름", "MCP 도구", 티켓 07).

도구 처리기는 미들웨어가 판정해 scope에 둔 토큰 레코드를 읽어 토큰이 닿는 지식베이스를 가린다.
결과는 `SearchOutput`이고 outputSchema가 된다. 오류는 `isError`가 참인 결과이고 글 내용 하나가
Problem Details와 같은 모양의 JSON 문자열이다. SDK는 도구가 올린 예외 메시지에
`Error executing tool` 접두를 붙이므로, 이 도구는 검색의 실패를 예외로 올리지 않고 오류 결과를 직접
돌려준다(HTTP 요청 밖에서 불린 경우만 `LookupError`다). 질의
글은 로그에도 응답에도 싣지 않고 지연만 남긴다(원칙 V).
"""

import logging
import time
from typing import Annotated, Final

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import JsonValue, TypeAdapter
from starlette.types import Scope

from rag_engine.adapters.log_format import log_event
from rag_engine.app.search import SearchDeps, SearchRequest, SearchResults, search_documents
from rag_engine.domain.entities import SearchHit
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.server.auth import authenticated_token
from rag_engine.server.problems import ERROR_STATUS, ERROR_TITLE, ToolError
from rag_engine.server.request_context import request_id_of
from rag_engine.server.tool_models import (
    FORMAT_VERSION,
    SearchLocation,
    SearchOutput,
    SearchResult,
)

logger = logging.getLogger(__name__)

_MS_PER_SECOND: Final = 1000.0
# 도메인의 `JsonValue`와 pydantic의 `JsonValue`는 다른 별칭이라 모델에 넣기 전에 검증해 옮긴다.
_METADATA: Final = TypeAdapter(dict[str, JsonValue])
TOOL_NAME: Final = "search"
_DESCRIPTION: Final = (
    "지식베이스에서 질의와 가까운 문서 조각을 찾는다. 결과마다 근거 위치(쪽, 절, 블록)와"
    " 문서의 갱신일, 점수가 붙고 점수가 큰 순서다. 지식베이스를 주지 않으면 기본 지식베이스를 쓴다."
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
        metadata=_METADATA.validate_python(hit.metadata),
        score=hit.rrf_score,
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


def tool_error(code: ErrorCode, scope: Scope) -> CallToolResult:
    """도구 오류 결과. `detail`은 싣지 않아 질의와 문서 내용이 새지 않는다."""
    problem = ToolError(
        title=ERROR_TITLE[code],
        status=ERROR_STATUS[code],
        code=code,
        request_id=request_id_of(scope),
    )
    return CallToolResult(
        content=[TextContent(type="text", text=problem.model_dump_json(exclude_none=True))],
        is_error=True,
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
    ) -> Annotated[CallToolResult, SearchOutput]:
        request_object = ctx.request_context.request
        if request_object is None:
            raise LookupError("HTTP 요청 밖에서 불린 도구다")
        scope = request_object.scope
        token = authenticated_token(scope)
        request = SearchRequest(
            query=query,
            top_k=default_top_k if top_k is None else top_k,
            knowledge_base=knowledge_base,
            allowed_knowledge_base_ids=token.knowledge_base_ids,
        )
        started = time.perf_counter()
        try:
            found = await search_documents(deps, request)
        except RequestError as error:
            return tool_error(error.code, scope)
        except Exception as error:  # 어느 갈래에도 들지 않는 예외는 도구 오류 `internal_error`다
            log_event(
                logger,
                "search_failed",
                level=logging.ERROR,
                request_id=request_id_of(scope),
                exception=error,
            )
            return tool_error(ErrorCode.INTERNAL_ERROR, scope)
        log_event(
            logger,
            "search",
            request_id=request_id_of(scope),
            duration_ms=(time.perf_counter() - started) * _MS_PER_SECOND,
            embedding_ms=found.timings.embedding_ms,
            sql_ms=found.timings.sql_ms,
        )
        return _output(found)
