"""요청 문맥 미들웨어가 응답 도중의 실패와 취소를 어떻게 기록하는지 ASGI 수준에서 본다(명세
"로그, 요청 ID, 지연 기록"). 상태 줄이 클라이언트가 실제로 본 응답과 어긋나면 로그로 장애를 읽을
수 없다."""

import asyncio
import json

import pytest
from starlette.types import Message, Receive, Scope, Send

from rag_engine.adapters.log_format import configure_logging
from rag_engine.server.request_context import RequestContextMiddleware


async def _no_messages() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def _scope() -> Scope:
    return {"type": "http", "method": "GET", "path": "/아무", "headers": []}


def _events(capsys: pytest.CaptureFixture[str], event: str) -> list[dict[str, object]]:
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    return [line for line in lines if line["event"] == event]


async def test_응답을_시작한_뒤_실패해도_로그는_클라이언트가_본_상태를_남긴다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("json")

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("본문을 보내던 중 실패")

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    await RequestContextMiddleware(inner, [])(_scope(), _no_messages, send)

    (request,) = _events(capsys, "http_request")
    assert [message["type"] for message in sent] == ["http.response.start"]
    assert request["status"] == 200


async def test_응답을_시작하기_전에_취소되면_상태는_null이고_취소는_그대로_전파된다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("json")

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        raise asyncio.CancelledError

    async def send(message: Message) -> None:
        raise AssertionError(f"보내지 않아야 한다: {message}")

    with pytest.raises(asyncio.CancelledError):
        await RequestContextMiddleware(inner, [])(_scope(), _no_messages, send)

    (request,) = _events(capsys, "http_request")
    assert request["status"] is None
