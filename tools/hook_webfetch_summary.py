"""PostToolUse 훅(WebFetch). WebFetch 가 페이지를 줄인 웹 요약을 돌려주면, 그 수와 인용을 근거로
쓰기 전에 본문을 대 보라는 계기를 컨텍스트에 넣는다.

WebFetch 의 출력은 대개 작은 모델이 받은 페이지를 프롬프트에 맞춰 줄인 것이다. 릴리스 노트의 요약이
`fastapi.sse` 가 들어온 판을 틀리게 줬고(태그를 대 보고 알았다, 일지 2026-09-26-01), 그 출력을
근거로 쓴 일이 세 번 있었다. 요약이 127개라 한 `@font-face` 를 명세와 ADR 에 사실로 적었는데 세어
보니 124개였다(대기열 124). 규약(`docs/agents/issue-tracker.md` 프로브와 근거)이 선 뒤에도
google/fonts 사본의 머리를 요약으로 보고 근거로 적었다가 PR 직전 리뷰가 짚었고(일지 2026-10-12-28),
WebFetch 로 확인한 수를 대화에서 "원문 대조"라고 보고했다(대기열 209, 일지 2026-10-12-37). 지침이
어겨졌으니 훅으로 간다(CLAUDE.md 교정 루프는 막는 훅 후보로 본다). 막지 않고 알린다 — 요약을 읽는
것은 잘못이 아니고, 잘못은 그 뒤의 보고에서 그것을 원문처럼 쓰는 데 있는데 훅은 그 문장을 보지
못한다. 대기열 항목도 계기 훅으로 정했다.

가르는 것은 결과 객체(`tool_response`)다. 키는 `bytes`·`code`·`codeText`·`durationMs`·`result`·`url`
이다(Claude Code 2.1.296, `.scratch/harness/probes/webfetch_payload/run.sh` 의 A).
- code·bytes·result 가 정수·정수·문자열이 아니거나 결과 객체가 없으면 수 없이 알린다 — 가르지 못할
  때 틀리게 알리는 값이, 요약을 원문처럼 쓰는 값보다 작다.
- code 가 2xx 가 아니면 침묵한다. 본 것은 둘이다. 리다이렉트는 다른 호스트로 가라는 안내만
  돌려주고(그때 bytes 는 안내문 자체의 크기라 아래 판정으로는 통과로 읽힌다), 404 는 본문을 받지
  않았다고 적는다. 줄인 본문이 없다.
- 결과의 UTF-8 바이트 수가 bytes 와 같으면 침묵한다. WebFetch 는 어떤 문서는 줄이지 않고 본문을
  그대로 돌려준다. 프로브 A 의 첫 호출 결과는 같은 주소를 `curl` 로 받은 본문과 34296바이트 모두
  같았다(손으로 대 봤다, 일지 2026-10-13-03). 이 저장소의 트랜스크립트에서 이 판정이 가른 두 무리는
  결과 길이와 bytes 의 비가 1 가까이와 0.35 아래로 떨어져 있었고 그 사이에 걸친 결과가 없었다(같은
  디렉터리의 `transcripts.py`, 수는 프로브 README 행). 글자 수가 아니라 UTF-8 바이트로 댄다 — 대시나
  한글이 든 본문은 둘이 다르다.
- 나머지는 알린다. 받은 바이트와 모델이 답한 글자 수를 들어 요약임을 보이고, 근거로 쓰거나 원문
  확인이라 말하려면 본문을 내려받아 대 보라고 한다. "줄였다"고 쓰지 않는다 — 작은 페이지에 설명을
  물으면 답이 본문보다 길 수 있다(PR 직전 버그·성능 리뷰).

그 문장이 모델에게 닿는 것은 프로브의 B 가 봤다. 등록 모양으로 붙인 `claude -p` 세션에서 요약 뒤에는
모델이 첫 문장(`LEAD`)을 옮겼고, 대조군 C(본문 통과)에서는 모델이 알림이 없다고 답했다. stream-json
에는 훅의 additionalContext 가 실리지 않아(B 의 스트림에서 그 문장은 모델의 답에만 있었다) 모델의
답이 증거다.

못 보는 것:
- 요약이 우연히 받은 본문과 바이트 수가 같으면 통과로 읽고 침묵한다.
- 2xx 가 아닌데 본문을 받아 줄인 결과. 잰 것은 301 과 404 뿐이고, 다른 code(403, 5xx 등)도 줄인
  본문이 없다고 보고 침묵한다.
- 리다이렉트 뒤에 다시 부른 호출. 그 결과가 요약이면 그때 알리고, 본문 통과면 침묵한다.
- 요약을 무엇에 쓰는지. 프롬프트와 그 뒤의 보고를 보지 않고 요약마다 알린다(제목만 물은 호출에도).
- WebSearch 의 결과와 서브에이전트 보고에 실린 웹 요약. 앞의 것은 이름으로 거르고(매처도 WebFetch
  하나다. MCP 의 fetch 같은 다른 가져오기 도구도 그렇다), 뒤의 것은 Agent 도구의 결과라 이 훅에 오지
  않는다. 서브에이전트가 부른 WebFetch 에는 입력(`agent_id`)으로 가르지 않고 같은 문장을 낸다. 그
  문장이 서브에이전트에게 닿는지는 재지 않았다.
"""

from __future__ import annotations

import json
import sys
from typing import TypedDict

TOOL = "WebFetch"
# 알림의 첫 문장. 프로브(`webfetch_payload/summarize.py`)가 모델이 이 문장을 옮겼는지 본다.
LEAD = "이 WebFetch 결과는 웹 요약이다"
_SIZED = "{lead}. 받은 본문({size}바이트)을 두고 작은 모델이 프롬프트에 맞춰 {chars}자로 답했다. "
_TAIL = (
    "여기서 얻은 수와 따옴표 인용을 근거로 쓰거나 '원문 확인'·'원문 대조'라고 말하려면, 본문을"
    " 내려받아(`curl` 등) 대 본 뒤 그 방법대로 적는다. 대 보지 않은 것은 주소와 함께 웹 요약이라고"
    " 적는다(`docs/agents/issue-tracker.md` 프로브와 근거)."
)
_UNSIZED = (
    f"{LEAD}. 작은 모델이 받은 본문을 프롬프트에 맞춰 줄인 것이다(결과 객체로 크기를 가르지"
    f" 못했다). {_TAIL}"
)


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분.

    결과 객체는 값을 읽은 뒤 좁히려고 `dict[str, object]` 로 적는다. 객체가 아닌 값이 와도
    `context_for` 가 런타임에 다시 본다."""

    tool_name: str
    tool_response: dict[str, object]


def context_for(payload: HookPayload) -> str | None:
    """웹 요약이면 컨텍스트 문장, 본문을 받지 못했거나 본문을 그대로 돌려줬으면 None."""
    if payload.get("tool_name") != TOOL:
        return None
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return _UNSIZED
    code, size, result = response.get("code"), response.get("bytes"), response.get("result")
    if not isinstance(code, int) or not isinstance(size, int) or not isinstance(result, str):
        return _UNSIZED
    if not 200 <= code < 300:
        return None
    if len(result.encode("utf-8")) == size:
        return None
    return _SIZED.format(lead=LEAD, size=size, chars=len(result)) + _TAIL


def main() -> int:
    payload: HookPayload = json.load(sys.stdin.buffer)
    context = context_for(payload)
    if context is None:
        return 0
    print(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
