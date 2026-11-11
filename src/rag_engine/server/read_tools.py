"""MCP 읽기 도구 `get_document`, `list_knowledge_bases`(명세 "MCP 도구", 티켓 09).

검색 도구와 같은 규약이다. 토큰 범위는 미들웨어가 scope에 둔 토큰 레코드에서 읽고, 오류는
`isError`가 참인 결과로 돌려준다(`tool_support`). 문서 본문은 `include_text`가 참일 때만 싣는다.
"""

from typing import Annotated, Final
from uuid import UUID

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from rag_engine.app.read_documents import (
    DocumentView,
    KnowledgeBaseView,
    get_document,
    list_knowledge_bases,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import UnitOfWork
from rag_engine.server.auth import authenticated_token
from rag_engine.server.tool_models import (
    FORMAT_VERSION,
    DocumentOutput,
    KnowledgeBasesOutput,
    KnowledgeBaseSummary,
)
from rag_engine.server.tool_support import METADATA, request_scope, run_guarded

GET_DOCUMENT: Final = "get_document"
LIST_KNOWLEDGE_BASES: Final = "list_knowledge_bases"
_READ_ONLY: Final = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


def _document_output(view: DocumentView) -> CallToolResult:
    document = view.document
    output = DocumentOutput(
        format_version=FORMAT_VERSION,
        document_id=document.id,
        source=view.source,
        key=document.key,
        title=document.title,
        group=view.group,
        mime=document.mime,
        size_bytes=document.size_bytes,
        updated_at=document.updated_at,
        metadata=METADATA.validate_python(document.metadata),
        chunk_counts=view.chunk_counts,
        text_length=view.text_length,
        text=view.text,
        next_offset=view.next_offset,
    )
    return _result(output.model_dump_json(), output.model_dump(mode="json"))


def _knowledge_bases_output(views: list[KnowledgeBaseView]) -> CallToolResult:
    output = KnowledgeBasesOutput(
        format_version=FORMAT_VERSION,
        knowledge_bases=[
            KnowledgeBaseSummary(
                name=view.knowledge_base.name,
                description=view.knowledge_base.description,
                document_count=view.document_count,
                is_default=view.knowledge_base.is_default,
            )
            for view in views
        ],
    )
    return _result(output.model_dump_json(), output.model_dump(mode="json"))


def _result(text: str, structured: dict[str, object]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=text)], structured_content=structured
    )


def _document_id(value: str) -> UUID:
    """문서 식별자를 읽는다. 읽을 수 없으면 `invalid_argument`이고 오류에 입력 값을 싣지 않는다."""
    try:
        return UUID(value)
    except ValueError:
        raise RequestError(ErrorCode.INVALID_ARGUMENT, "document_id가 UUID 형식이 아니다") from None


def register_read_tools(mcp: MCPServer, unit_of_work: UnitOfWork, *, max_text_chars: int) -> None:
    @mcp.tool(
        name=GET_DOCUMENT,
        description=(
            "문서 하나의 정보를 낸다. 원천, 키, 제목, 그룹, 형식, 갱신일, 메타데이터, 토큰이 닿는"
            " 지식베이스마다의 조각 수와 전문의 길이(text_length)가 든다. include_text를 참으로"
            " 주면 전문의 offset부터 max_chars 안의 창(text)과 다음 창의 offset(next_offset)도"
            " 싣는다. next_offset이 null이 아니면 그 값을 offset으로 넘겨 이어서 읽는다."
            f" max_chars는 1부터 {max_text_chars}까지이고 주지 않으면 {max_text_chars}다."
            " offset은 0 이상이고 전문의 길이를 넘으면 오류다."
        ),
        annotations=_READ_ONLY,
    )
    async def get_document_tool(
        document_id: str,
        ctx: Context,
        *,
        include_text: bool = False,
        offset: int = 0,
        max_chars: int | None = None,
    ) -> Annotated[CallToolResult, DocumentOutput]:
        scope = request_scope(ctx)

        async def call() -> CallToolResult:
            view = await get_document(
                unit_of_work,
                _document_id(document_id),
                allowed_knowledge_base_ids=authenticated_token(scope).knowledge_base_ids,
                include_text=include_text,
                offset=offset,
                max_chars=max_chars,
                max_text_chars=max_text_chars,
            )
            return _document_output(view)

        return await run_guarded(GET_DOCUMENT, scope, call)

    @mcp.tool(
        name=LIST_KNOWLEDGE_BASES,
        description=(
            "토큰이 닿는 지식베이스의 목록을 낸다. "
            "이름, 설명, 문서 수와 기본 지식베이스인지가 든다."
        ),
        annotations=_READ_ONLY,
    )
    async def list_knowledge_bases_tool(
        ctx: Context,
    ) -> Annotated[CallToolResult, KnowledgeBasesOutput]:
        scope = request_scope(ctx)

        async def call() -> CallToolResult:
            views = await list_knowledge_bases(
                unit_of_work,
                allowed_knowledge_base_ids=authenticated_token(scope).knowledge_base_ids,
            )
            return _knowledge_bases_output(views)

        return await run_guarded(LIST_KNOWLEDGE_BASES, scope, call)
