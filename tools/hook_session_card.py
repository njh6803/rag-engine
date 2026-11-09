"""PreToolUse 훅(mcp__ccd_session__start_session). 모델이 스스로 내는 세션 카드를 막는다.

모델이 스스로 낸 카드로 열린 세션은 이 저장소의 절차 밖에서 연다. 첫 메시지가 지시문이 아니라 첫
턴 훅이 침묵하고, 제목을 브랜치로 바꾸라는 계기가 없으며, ADR 0036 의 제품 먼저도 거치지 않는다.
ADR 0037 의 셈에서 세션 여는 도구의 호출 35 가운데 16 이 스스로 낸 카드였다. 막기는 그 ADR 의 결정
("세션 카드")이고, 막는 대상은 지침을 몰라 내는 실수의 길이다. 일부러 하는 우회는 아래 못 보는 것의
첫 항목이다.

막는 것. `tool_input.initiation` 이 `own_initiative` 인 호출이다. `permissionDecision: deny` 와
까닭의 글을 낸다. 그 글은 도구 결과로 모델에게 가고 카드는 만들어지지 않는다(아래 측정에서 카드
id 가 없었다).

지나보내는 것(아무것도 내지 않는다). `user_asked`(사용자가 말로 시킨 새 세션), `offer`(사용자에게
묻는 카드), `initiation` 없이 `proposal_id` 만 든 호출(이미 뜬 카드를 시작한다), 풀 수 없는
입력(JSON 이 아니다, 최상위나 `tool_input` 이 객체가 아니다). 풀 수 없는 입력을 막지 않는 것은 그
입력이 무엇을 하려는지 모르기 때문이다.

측정. 데스크톱 앱 세션에서 이 매처의 PreToolUse 훅이 `own_initiative` 호출을 받았고 입력에
`initiation` 키가 있었다. deny 로 막자 도구 결과가 `PreToolUse:mcp__ccd_session__start_session hook
error: ` 뒤에 이유 글을 붙인 꼴로 모델에게 갔고 카드 id 가 없었다
(`.scratch/ticket-for-every-pr/probes/card_block/`, 결과는 같은 `probes/README.md`. 판은 Claude
Code 2.1.299 로, 출력이 아니라 탐침 세션 기록에서 손으로 봤다). 표본은 호출 하나씩이고 그 탐침은
래퍼 없이 `settings.local.json` 에 등록했다.

못 보는 것.
- `initiation` 은 모델이 적는 값이다. 모델이 스스로 낸 일을 `user_asked` 로 적으면 막지 못한다(ADR
  0037 Consequences). 까닭의 글이 값을 바꿔 다시 부르지 말라고 적는 것이 이 길에 대한 전부다.
- 앱이 도구 이름을 바꾸면 매처가 맞지 않아 이 훅이 불리지 않고 조용히 지나간다. 매처를 넓히지 않는
  것은 다른 MCP 서버의 같은 이름 도구까지 막을 수 있어서다(명세의 거부한 안).
- 사람이 카드를 눌러 시작한 것과 다른 세션 도구(`hand_off_to_session` 등)는 보지 않는다. 그것을
  지키는 것은 매처뿐이고, `output_for` 는 `tool_name` 을 보지 않아 다른 도구의 입력이라도
  `initiation` 이 `own_initiative` 이면 막는다.
- `initiation` 값은 글자 그대로 견준다. 대소문자나 앞뒤 공백이 다르면(`Own_Initiative`,
  ` own_initiative`) 지나간다. 실제 입력은 소문자 enum 그대로였다(위 측정).
- `tool_input` 이 객체가 아니라 JSON 을 담은 문자열로 오면 풀지 않고 지나간다. 실제 입력은 객체였다.
"""

from __future__ import annotations

import json
import sys
from typing import TypedDict

BLOCKED_INITIATION = "own_initiative"

REASON = (
    "모델이 스스로 내는 세션 카드(`initiation: own_initiative`)는 이 저장소에서 막는다. "
    '후속 일은 지금 일지의 "다음"이나 대기열 항목(`.scratch/retro-queue/`, 회고)으로 적는다. '
    "`initiation` 을 `user_asked` 나 `offer` 로 바꿔 다시 부르지 않는다 — 그 값은 사용자가 말로 "
    '새 세션을 시켰거나 사용자에게 물을 때만 쓴다. 근거는 ADR 0037 의 "세션 카드"다.'
)


class ToolInput(TypedDict, total=False):
    initiation: object


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분. 객체가 아닌 값이 와도
    `output_for` 가 런타임에 다시 본다."""

    tool_input: ToolInput


type JsonValue = HookPayload | list[object] | str | float | bool | None


def output_for(raw: bytes) -> str | None:
    """훅 입력 바이트에 대한 표준 출력. 막지 않으면 None."""
    try:
        payload: JsonValue = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    if tool_input.get("initiation") != BLOCKED_INITIATION:
        return None
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        }
    )


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    output = output_for(sys.stdin.buffer.read())
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
