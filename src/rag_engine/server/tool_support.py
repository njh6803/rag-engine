"""MCP 도구 셋이 함께 쓰는 처리기 보조(명세 "MCP 도구", 티켓 07, 09).

도구 오류는 예외가 아니라 `isError`가 참인 결과이고 글 내용 하나가 Problem Details와 같은 모양의
JSON 문자열이다. SDK는 도구가 올린 예외 메시지에 `Error executing tool` 접두를 붙여 JSON을 깨므로,
도구는 실패를 예외로 올리지 않고 오류 결과를 직접 돌려준다(HTTP 요청 밖에서 불린 경우만
`LookupError`다). `detail`은 싣지 않아 질의와 문서 내용이 새지 않는다(원칙 V).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Final

from mcp.server.mcpserver import Context
from mcp.types import CallToolResult, TextContent
from pydantic import JsonValue, TypeAdapter
from starlette.types import Scope

from rag_engine.adapters.log_format import log_event
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.server.problems import ERROR_STATUS, ERROR_TITLE, ToolError
from rag_engine.server.request_context import request_id_of

logger = logging.getLogger(__name__)

# 도메인의 `JsonValue`와 pydantic의 `JsonValue`는 다른 별칭이라 모델에 넣기 전에 검증해 옮긴다.
METADATA: Final = TypeAdapter(dict[str, JsonValue])


def tool_error(code: ErrorCode, scope: Scope) -> CallToolResult:
    """도구 오류 결과. `detail`은 싣지 않는다."""
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


def request_scope(ctx: Context) -> Scope:
    """도구를 부른 HTTP 요청의 ASGI scope. 미들웨어가 판정한 토큰과 요청 ID가 거기 있다."""
    request = ctx.request_context.request
    if request is None:
        raise LookupError("HTTP 요청 밖에서 불린 도구다")
    return request.scope


async def run_guarded(
    tool: str, scope: Scope, call: Callable[[], Awaitable[CallToolResult]]
) -> CallToolResult:
    """도구 본문을 돌린다. 요청을 거절하는 오류는 그 코드의 도구 오류로, 어느 갈래에도 들지 않는
    예외는 로그에 남기고 `internal_error`로 낸다."""
    try:
        return await call()
    except RequestError as error:
        return tool_error(error.code, scope)
    except Exception as error:  # 어느 갈래에도 들지 않는 예외는 도구 오류 `internal_error`다
        log_event(
            logger,
            f"{tool}_failed",
            level=logging.ERROR,
            request_id=request_id_of(scope),
            exception=error,
        )
        return tool_error(ErrorCode.INTERNAL_ERROR, scope)
