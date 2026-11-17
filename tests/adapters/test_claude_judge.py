"""Claude 관련성 판정기 어댑터(티켓 search-eval 12, ADR 0019, 명세 "LLM 관련성 판정").

뒤에는 가짜 끝점(`tests/support/claude_stub.py`)을 붙인다. 요청의 모양, 상태 코드에 따른 실패 갈래,
읽을 수 없는 응답, 그리고 실패의 메시지와 SDK 로그에 키와 서버의 글과 질의의 글이 새지 않는지를
본다. 실제 API의 응답 모양은 이 시험이 말하지 않는다(프로브 `judge-call`이 잰다).
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

import pytest
from anthropic import AsyncAnthropic
from tests.support.claude_server import serve_claude_stub
from tests.support.claude_stub import (
    JUDGE_API_KEY,
    JUDGE_MODEL,
    SECRET_MESSAGE,
    ClaudeStub,
)

from rag_engine.adapters import claude_judge
from rag_engine.adapters.claude_judge import PROMPT_VERSION, ClaudeRelevanceJudge
from rag_engine.adapters.judge_settings import JudgeSettings
from rag_engine.domain.entities import JsonValue
from rag_engine.domain.errors import ErrorCode, PermanentFailure, TransientFailure

QUERY = "입사하고 언제부터 연차가 생기나요"
TEXT = "휴가\n\n연차휴가는 입사 일 년 뒤부터 발생한다."


@contextmanager
def _judge(stub: ClaudeStub) -> Generator[ClaudeRelevanceJudge]:
    with serve_claude_stub(stub) as url:
        yield ClaudeRelevanceJudge(JudgeSettings(url=url, model=JUDGE_MODEL, api_key=JUDGE_API_KEY))


def _message(content: list[JsonValue], stop_reason: str = "end_turn") -> dict[str, JsonValue]:
    return {
        "id": "msg_stub",
        "type": "message",
        "role": "assistant",
        "model": JUDGE_MODEL,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _text(value: str) -> JsonValue:
    return {"type": "text", "text": value}


def test_지시문의_판은_1부터의_정수다() -> None:
    assert PROMPT_VERSION == 1


async def test_글에_따라_참과_거짓을_낸다() -> None:
    stub = ClaudeStub(relevant_when=lambda query, passage: "연차" in passage)
    with _judge(stub) as judge:
        assert await judge.judge(QUERY, TEXT) is True
        assert await judge.judge(QUERY, "출장비는 실비로 정산한다") is False
        await judge.aclose()


async def test_요청에_모델과_키와_구조화된_출력의_스키마와_두_글이_든다() -> None:
    stub = ClaudeStub()
    with _judge(stub) as judge:
        await judge.judge(QUERY, TEXT)
        await judge.aclose()

    (request,) = stub.requests
    # 설치된 SDK(2.8.0)는 키를 `Authorization: Bearer`로 보낸다(`_api_key_auth`).
    assert request.headers["authorization"] == f"Bearer {JUDGE_API_KEY}"
    assert request.body["model"] == JUDGE_MODEL
    assert request.pair() == (QUERY, TEXT)
    system = request.body["system"]
    assert isinstance(system, str)
    assert system.strip()
    config = request.body["output_config"]
    assert isinstance(config, dict)
    output_format = config["format"]
    assert isinstance(output_format, dict)
    assert output_format["type"] == "json_schema"
    schema = output_format["schema"]
    assert isinstance(schema, dict)
    assert schema["required"] == ["relevant"]
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert properties["relevant"] == {"type": "boolean"}


@pytest.mark.parametrize("status", [408, 409, 429, 500, 503, 529])
async def test_시간_초과와_요청_한도와_서버_오류는_일시_실패이고_SDK가_몰래_다시_하지_않는다(
    status: int,
) -> None:
    stub = ClaudeStub()
    stub.fail_next(status, status, status)
    with _judge(stub) as judge, pytest.raises(TransientFailure) as caught:
        await judge.judge(QUERY, TEXT)

    assert caught.value.code is ErrorCode.JUDGE_UNAVAILABLE
    assert stub.count() == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_인증과_요청_오류는_영구_실패다(status: int) -> None:
    stub = ClaudeStub()
    stub.fail_next(status)
    with _judge(stub) as judge, pytest.raises(PermanentFailure) as caught:
        await judge.judge(QUERY, TEXT)

    assert caught.value.code is ErrorCode.JUDGE_REJECTED
    assert stub.count() == 1


@pytest.mark.parametrize("status", [401, 503])
async def test_실패의_메시지에_서버의_글과_키와_질의의_글이_없고_원인을_잇지_않는다(
    status: int,
) -> None:
    stub = ClaudeStub()
    stub.fail_next(status)
    with _judge(stub) as judge, pytest.raises((TransientFailure, PermanentFailure)) as caught:
        await judge.judge(QUERY, TEXT)

    error = caught.value
    for secret in (SECRET_MESSAGE, JUDGE_API_KEY, QUERY, TEXT):
        assert secret not in str(error)
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


async def test_연결할_수_없으면_일시_실패다() -> None:
    judge = ClaudeRelevanceJudge(
        JudgeSettings(url="http://127.0.0.1:1", model=JUDGE_MODEL, api_key=JUDGE_API_KEY)
    )

    with pytest.raises(TransientFailure) as caught:
        await judge.judge(QUERY, TEXT)
    await judge.aclose()

    assert caught.value.code is ErrorCode.JUDGE_UNAVAILABLE
    assert JUDGE_API_KEY not in str(caught.value)


@pytest.mark.parametrize(
    "body",
    [
        _message([_text("관련 있다")]),
        _message([_text('{"relevant": "yes"}')]),
        _message([_text("[true]")]),
        _message([]),
        _message([_text('{"relevant": true}')], stop_reason="refusal"),
        _message([_text('{"relevant": true}')], stop_reason="max_tokens"),
    ],
    ids=["JSON이 아니다", "참거짓이 아니다", "객체가 아니다", "글이 없다", "거절", "길이에서 잘림"],
)
async def test_읽을_수_없는_응답은_영구_실패다(body: dict[str, JsonValue]) -> None:
    stub = ClaudeStub()
    stub.reply_next(body)
    with _judge(stub) as judge, pytest.raises(PermanentFailure) as caught:
        await judge.judge(QUERY, TEXT)

    assert caught.value.code is ErrorCode.JUDGE_REJECTED
    assert "관련 있다" not in str(caught.value)


async def test_생각_블록이_앞서_와도_글_블록의_판정을_읽는다() -> None:
    stub = ClaudeStub()
    thinking: JsonValue = {"type": "thinking", "thinking": "조각을 본다", "signature": "stub"}
    stub.reply_next(_message([thinking, _text('{"relevant": true}')]))
    with _judge(stub) as judge:
        assert await judge.judge(QUERY, TEXT) is True
        await judge.aclose()


@pytest.mark.parametrize(
    ("name", "child"),
    [
        ("anthropic", "anthropic"),
        ("httpx2", "httpx2"),
        ("httpcore2", "httpcore2.http11"),
        # 요청의 본문을 찍는 로거는 `anthropic`의 자식 `anthropic._base_client`다. 호출하는 쪽이 이
        # 자식에 수준을 직접 주면 부모를 되돌려도 그 수준이 이긴다.
        ("anthropic._base_client", "anthropic._base_client"),
    ],
)
def test_SDK_로거의_수준을_경고로_되돌려_요청_본문이_로그에_가지_않게_한다(
    name: str, child: str
) -> None:
    # SDK 2.8.0은 `httpx`와 `httpcore`가 아니라 이름 끝에 2가 붙은 `httpx2`, `httpcore2`를 쓴다.
    # `httpcore2`는 `httpcore2.http11` 같은 자식 로거가 수준을 물려받는 부모다.
    logging.getLogger(name).setLevel(logging.DEBUG)

    ClaudeRelevanceJudge(JudgeSettings(url="http://127.0.0.1:1", model="m", api_key="k"))

    assert logging.getLogger(child).getEffectiveLevel() >= logging.WARNING


def test_SDK의_OpenTelemetry_추적을_끄고_환경_변수가_본문을_켜도_추적은_꺼진다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # SDK는 `open_telemetry`를 받지 못하면 이 환경 변수로 span에 글을 싣는 방식을 고른다.
    monkeypatch.setenv("ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE", "content")
    seen: dict[str, object] = {}

    class _Spy:
        def __init__(self, **kwargs: object) -> None:
            seen.update(kwargs)

    monkeypatch.setattr(claude_judge, "AsyncAnthropic", _Spy)
    ClaudeRelevanceJudge(JudgeSettings(url="http://127.0.0.1:1", model="m", api_key="k"))

    assert seen.get("open_telemetry") is False
    # 그 값이 정말 추적을 끄는지는 SDK가 정한다. 같은 환경에서 실제 클라이언트로 본다.
    client = AsyncAnthropic(api_key="k", open_telemetry=False)
    assert client.open_telemetry["traces"]["enabled"] is False
