"""Claude 가짜 끝점. 시험이 쓰는 작은 ASGI 앱 하나가 Messages API의 응답 모양을 흉내 낸다(명세
Testing Decisions의 새 이음매, 선례 `tests/support/tei_stub.py`).

`POST /v1/messages` 하나를 낸다. 받은 요청의 헤더와 본문을 `requests`에 남겨 시험이 인증 헤더와
요청 칸을 단언한다. 판정은 시험이 `relevant_when`으로 정한다. 그 함수는 질의의 글과 조각의 글을
받아 관련 있으면 참을 낸다. 어댑터가 두 글을 `<query>`와 `<passage>` 표지로 싸 보내므로 스텁이 그
모양에서 두 글을 뽑는다. 응답은 구조화된 출력의 모양이다. 내용 블록 하나가 `{"relevant": 참거짓}`
JSON 글을 싣는다.

오류를 내게 하는 길은 둘이다. `fail_from`은 그 순번(1부터)부터의 모든 요청에, `fail_next`는
앞으로 받는 요청 몇 개에 주어진 상태 코드로 답한다. 오류 본문은 `SECRET_MESSAGE`를 담아 시험이
어댑터가 서버의 오류 글을 옮기지 않음을 본다. 실제 API의 응답 모양은 티켓의 실제 호출 확인(프로브
폴더 `judge-call`)이 잰다. 이 스텁은 그 모양을 흉내 낼 뿐이라 실제 API가 같은지를 말하지 않는다.
"""

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from rag_engine.domain.entities import JsonValue

SECRET_MESSAGE: Final = "CLAUDE-SERVER-DETAIL-MUST-NOT-LEAK"

# 판정기의 설정 셋(명세 "LLM 관련성 판정"). 모두 기본값이 없다. 시험은 이 값으로 환경을 채운다.
JUDGE_URL_ENV: Final = "RAG_JUDGE_URL"
JUDGE_MODEL_ENV: Final = "RAG_JUDGE_MODEL"
JUDGE_API_KEY_ENV: Final = "RAG_JUDGE_API_KEY"
JUDGE_MODEL: Final = "claude-test"
JUDGE_API_KEY: Final = "sk-ant-test-SECRET-KEY-VALUE"

_ERROR_TYPES: Final = {
    400: "invalid_request_error",
    401: "authentication_error",
    403: "permission_error",
    404: "not_found_error",
    429: "rate_limit_error",
    500: "api_error",
    503: "api_error",
    529: "overloaded_error",
}

_PROMPT: Final = re.compile(r"<query>\n(.*?)\n</query>\n\n<passage>\n(.*)\n</passage>", re.DOTALL)


@dataclass(frozen=True, slots=True)
class RecordedMessage:
    headers: Mapping[str, str]
    body: Mapping[str, JsonValue]

    def pair(self) -> tuple[str, str]:
        """사용자 메시지에서 질의의 글과 조각의 글을 뽑는다. 그 모양이 아니면 단언이 실패한다."""
        found = _PROMPT.search(self._text())
        assert found is not None, "사용자 메시지가 질의와 조각의 표지 모양이 아니다"
        return found.group(1), found.group(2)

    def _text(self) -> str:
        messages = self.body.get("messages")
        assert isinstance(messages, list)
        first = messages[0]
        assert isinstance(first, dict)
        content = first["content"]
        if isinstance(content, str):
            return content
        assert isinstance(content, list)
        texts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return "".join(texts)


def _never_relevant(query: str, passage: str) -> bool:
    del query, passage
    return False


@dataclass(slots=True)
class ClaudeStub:
    relevant_when: Callable[[str, str], bool] = _never_relevant
    requests: list[RecordedMessage] = field(default_factory=lambda: [])
    _queued_statuses: list[int] = field(default_factory=lambda: [])
    _queued_bodies: list[dict[str, JsonValue]] = field(default_factory=lambda: [])
    _failing_from: tuple[int, int] | None = None
    app: FastAPI = field(init=False)

    def __post_init__(self) -> None:
        self.app = FastAPI()
        self.app.add_api_route("/v1/messages", self._messages, methods=["POST"])

    def fail_next(self, *statuses: int) -> None:
        """앞으로 받는 요청 가운데 앞의 몇 개가 차례로 이 상태 코드로 답하게 한다."""
        self._queued_statuses.extend(statuses)

    def fail_from(self, number: int, status: int) -> None:
        """`number`번째(1부터) 요청부터 모든 요청이 이 상태 코드로 답하게 한다."""
        self._failing_from = (number, status)

    def heal(self) -> None:
        """`fail_next`와 `fail_from`이 정한 오류를 모두 거두고 이어 오는 요청에 정상으로 답한다."""
        self._queued_statuses.clear()
        self._failing_from = None

    def reply_next(self, body: dict[str, JsonValue]) -> None:
        """다음 요청 하나에 상태 200과 이 본문으로 답한다. 응답의 모양이 어긋난 경우를 시험한다."""
        self._queued_bodies.append(body)

    def count(self) -> int:
        return len(self.requests)

    async def _messages(self, request: Request) -> Response:
        body: dict[str, JsonValue] = json.loads(await request.body())
        headers = {name.lower(): value for name, value in request.headers.items()}
        recorded = RecordedMessage(headers, body)
        self.requests.append(recorded)
        status = self._forced_status()
        if status is not None:
            error_type = _ERROR_TYPES.get(status, "api_error")
            return JSONResponse(
                {"type": "error", "error": {"type": error_type, "message": SECRET_MESSAGE}},
                status_code=status,
            )
        if self._queued_bodies:
            return JSONResponse(self._queued_bodies.pop(0))
        query, passage = recorded.pair()
        verdict = json.dumps({"relevant": self.relevant_when(query, passage)})
        return JSONResponse(
            {
                "id": "msg_stub",
                "type": "message",
                "role": "assistant",
                "model": body.get("model", "stub-model"),
                "content": [{"type": "text", "text": verdict}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )

    def _forced_status(self) -> int | None:
        if self._queued_statuses:
            return self._queued_statuses.pop(0)
        if self._failing_from is not None and len(self.requests) >= self._failing_from[0]:
            return self._failing_from[1]
        return None
