"""인증 미들웨어(FastAPI 앱 바깥의 ASGI, 명세 "인증과 권한", ADR 0014).

REST와 `/mcp` 둘 다에서 베어러 토큰을 본다. 없음·모름·회수는 401 `unauthenticated`, 만료는 401
`token_expired`, `reader`가 REST를 부르면 403 `forbidden`이다. `/health`만 인증 밖이다. 허용 호스트
판정(421)은 MCP SDK의 전송 보안이 `/mcp`에서만 한다.

판정한 토큰 레코드는 ASGI scope의 `state`에 둔다. MCP 도구는 SDK의 Context로 그 값에 닿는다
(`ctx.request_context.request.scope`, 프로브 `.scratch/core/probes/mcp-sdk/probe_scope.py`).
"""

from datetime import UTC, datetime

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from rag_engine.app.tokens import authenticate
from rag_engine.domain.entities import Token, TokenRole
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import TokenStore
from rag_engine.server.problem_response import problem_response
from rag_engine.server.request_context import is_mcp_path, request_id_of, scope_state

HEALTH_PATH = "/health"
_TOKEN_KEY = "token"
_BEARER = "bearer"
_POLICY_VIOLATION = 1008  # 웹소켓 닫힘 코드 "정책 위반"(RFC 6455 7.4.1)


def authenticated_token(scope: Scope) -> Token:
    """미들웨어가 판정해 둔 토큰 레코드. 미들웨어를 지나지 않은 scope면 오류다."""
    token = scope_state(scope).get(_TOKEN_KEY)
    if isinstance(token, Token):
        return token
    raise LookupError("인증을 지나지 않은 scope다")


def _bearer_token(scope: Scope) -> str | None:
    scheme, _, credentials = Headers(scope=scope).get("authorization", "").partition(" ")
    credentials = credentials.strip()
    return credentials if scheme.lower() == _BEARER and credentials else None


class AuthMiddleware:
    def __init__(self, app: ASGIApp, token_store: TokenStore) -> None:
        self.app = app
        self._tokens = token_store

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            # 웹소켓처럼 이 서버가 열지 않은 연결은 인증할 길이 없어 닫는다(기본이 닫힘, 원칙 V).
            await receive()
            await send({"type": "websocket.close", "code": _POLICY_VIOLATION})
            return
        if scope["path"] == HEALTH_PATH:
            await self.app(scope, receive, send)
            return
        request_id = request_id_of(scope)
        try:
            token = await authenticate(self._tokens, _bearer_token(scope), datetime.now(UTC))
        except RequestError as error:
            response = problem_response(
                error.code, request_id, headers={"WWW-Authenticate": "Bearer"}
            )
            await response(scope, receive, send)
            return
        if token.role is TokenRole.READER and not is_mcp_path(scope["path"]):
            await problem_response(ErrorCode.FORBIDDEN, request_id)(scope, receive, send)
            return
        scope_state(scope)[_TOKEN_KEY] = token
        await self.app(scope, receive, send)
