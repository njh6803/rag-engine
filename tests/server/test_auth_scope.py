"""인증 미들웨어를 ASGI 수준에서 직접 밟는다(명세 "인증과 권한", 티켓 04).

판정한 토큰 레코드가 ASGI scope에 놓여 안쪽 앱(MCP 도구의 Context)이 읽는 길과, HTTP가 아닌
연결을 닫는 기본은 HTTP 접속으로는 드러나지 않아 가짜 저장소와 가짜 안쪽 앱으로 본다.
"""

from datetime import datetime
from uuid import UUID

from starlette.types import Message, Receive, Scope, Send

from rag_engine.app.tokens import hash_token
from rag_engine.domain.entities import Token, TokenRole
from rag_engine.domain.identifiers import new_id
from rag_engine.server.auth import AuthMiddleware, authenticated_token
from rag_engine.server.request_context import RequestContextMiddleware

RAW = "rag_scope_token"


class _OneTokenStore:
    """`get_by_hash`만 쓰인다. 나머지 포트 메서드는 이 시험이 부르지 않는다."""

    def __init__(self, token: Token) -> None:
        self._token = token

    async def add(self, token: Token) -> None:
        raise NotImplementedError

    async def get(self, token_id: UUID) -> Token | None:
        raise NotImplementedError

    async def get_by_hash(self, token_hash: str) -> Token | None:
        return self._token if token_hash == self._token.token_hash else None

    async def list_tokens(self) -> list[Token]:
        raise NotImplementedError

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        raise NotImplementedError

    async def has_live_admin(self, now: datetime) -> bool:
        raise NotImplementedError


def _token() -> Token:
    return Token(
        id=new_id(),
        name="범위 시험",
        token_hash=hash_token(RAW),
        role=TokenRole.READER,
        knowledge_base_ids=(),
        expires_at=None,
        revoked_at=None,
        created_at=datetime.fromisoformat("2026-11-11T00:00:00+00:00"),
    )


async def _no_messages() -> Message:
    return {"type": "websocket.connect"}


async def test_통과시킨_요청의_scope에_판정한_토큰_레코드가_놓인다() -> None:
    token = _token()
    seen: list[Token] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(authenticated_token(scope))
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    app = RequestContextMiddleware(AuthMiddleware(inner, _OneTokenStore(token)), [])
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", f"Bearer {RAW}".encode())],
    }
    await app(scope, _no_messages, send)

    assert seen == [token]
    assert sent[0]["status"] == 204


async def test_HTTP가_아닌_연결은_안쪽_앱에_닿지_않고_닫힌다() -> None:
    reached: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        reached.append(scope["type"])

    app = AuthMiddleware(inner, _OneTokenStore(_token()))
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    await app({"type": "websocket", "path": "/mcp", "headers": []}, _no_messages, send)

    assert reached == []
    assert sent == [{"type": "websocket.close", "code": 1008}]


async def test_lifespan은_인증_없이_안쪽_앱으로_간다() -> None:
    reached: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        reached.append(scope["type"])

    app = AuthMiddleware(inner, _OneTokenStore(_token()))

    async def send(message: Message) -> None:
        raise AssertionError(f"보내지 않아야 한다: {message}")

    await app({"type": "lifespan"}, _no_messages, send)

    assert reached == ["lifespan"]
