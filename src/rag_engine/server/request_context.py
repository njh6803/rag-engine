"""요청 문맥 미들웨어(FastAPI 앱 바깥의 ASGI, 명세 "로그, 요청 ID, 지연 기록").

가장 바깥에서 요청마다 서버가 UUIDv7 요청 ID를 만들어 응답 헤더 `X-Request-Id`로 돌려주고, 들어오는
`X-Request-Id`는 믿지 않고 쓰지 않는다(로그 주입을 막는다). 요청이 끝나면 `http_request` 이벤트 한
줄을 남기고, 안쪽에서 처리하지 못한 예외는 500 Problem Details로 바꾼다.

경로는 라우트 템플릿으로만 남긴다. 실제 값(문서 키, id)이나 쿼리 문자열은 어떤 줄에도 없다.
"""

import logging
import time
from collections.abc import Sequence
from typing import TypeGuard
from uuid import UUID

from starlette.datastructures import MutableHeaders
from starlette.routing import BaseRoute, Match, Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rag_engine.adapters.log_format import log_event, request_id_var
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.server.problem_response import problem_response

REQUEST_ID_HEADER = "X-Request-Id"
MCP_PATH = "/mcp"
_UNMATCHED = "unmatched"
_REQUEST_ID_KEY = "request_id"

logger = logging.getLogger("rag_engine.server.http")


def _is_state(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def scope_state(scope: Scope) -> dict[str, object]:
    """ASGI scope의 `state`. 요청 ID와 인증 결과를 둔다. uvicorn은 요청마다 빈 사본을 준다."""
    state: object = scope.get("state")
    if _is_state(state):
        return state
    fresh: dict[str, object] = {}
    scope["state"] = fresh
    return fresh


def request_id_of(scope: Scope) -> UUID:
    request_id = scope_state(scope).get(_REQUEST_ID_KEY)
    if isinstance(request_id, UUID):
        return request_id
    raise LookupError("요청 ID를 두지 않은 scope다. 요청 문맥 미들웨어가 가장 바깥에 있어야 한다")


def is_mcp_path(path: str) -> bool:
    return path == MCP_PATH or path.startswith(MCP_PATH + "/")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, routes: Sequence[BaseRoute]) -> None:
        self.app = app
        # 경로 템플릿을 찾는 데만 쓴다. 모든 경로를 받는 하위 앱 마운트는 뺀다.
        self._routes = [route for route in routes if isinstance(route, Route)]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = new_id()
        scope_state(scope)[_REQUEST_ID_KEY] = request_id
        reset = request_id_var.set(request_id)
        outcome = _Outcome()
        started = time.perf_counter()
        try:
            await self._run(scope, receive, send, request_id, outcome)
        finally:
            log_event(
                logger,
                "http_request",
                request_id=request_id,
                duration_ms=(time.perf_counter() - started) * 1000,
                method=scope["method"],
                path=self._path_template(scope),
                # 응답을 시작하기 전에 취소되면(클라이언트가 끊음) 상태가 없어 null이다.
                status=outcome.status or None,
            )
            request_id_var.reset(reset)

    async def _run(
        self, scope: Scope, receive: Receive, send: Send, request_id: UUID, outcome: "_Outcome"
    ) -> None:
        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                outcome.status = message["status"]
                outcome.response_started = True
                message.setdefault("headers", [])
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = str(request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as error:
            # 서드파티 예외의 메시지에는 입력 값이 실릴 수 있어 로그 포매터가 타입과 프레임만
            # 싣는다.
            # 응답을 이미 시작했으면(스트리밍 도중) 클라이언트가 본 상태를 그대로 둔다.
            if not outcome.response_started:
                outcome.status = 500
            log_event(
                logger,
                "request_failed",
                level=logging.ERROR,
                request_id=request_id,
                exception=error,
                status=outcome.status,
            )
            if not outcome.response_started:
                response = problem_response(ErrorCode.INTERNAL_ERROR, request_id)
                await response(scope, receive, send_with_request_id)

    def _path_template(self, scope: Scope) -> str:
        for route in self._routes:
            if route.matches(scope)[0] is not Match.NONE:
                return route.path
        return MCP_PATH if is_mcp_path(scope["path"]) else _UNMATCHED


class _Outcome:
    """응답의 상태. 응답 헤더를 보낸 시점에 채워진다. 안쪽에서 예외가 나면 응답이 시작되지 않았어도
    기록할 상태(500)는 정해지므로 시작 여부를 상태와 따로 둔다."""

    def __init__(self) -> None:
        self.status = 0
        self.response_started = False
