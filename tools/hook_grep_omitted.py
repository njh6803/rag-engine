"""PostToolUse 훅(Grep). Grep 도구가 긴 일치 줄을 `[Omitted long matching line]` 으로만 내면, 생략된
줄의 수와 자리를 들어 그 줄을 따로 열어 보라는 계기를 컨텍스트에 넣는다.

잔존 grep 이 열린 대기열 31행을 그 표지 뒤에 두고 놓쳤고, 셀프 리뷰 두 축이 찾았다(대기열 145,
일지 2026-10-07-14). 다음 회고에서도 같은 표지가 나와 그때는 알아채 Bash 로 다시 읽었다(일지
2026-10-07-17). 출력의 고정 표지라 지침보다 훅이 맞다. 막지 않고 알린다 — 생략된 결과를 받는 것은
잘못이 아니고, 잘못은 그 줄을 열지 않고 잔존이 0이라고 세는 데 있는데 훅은 그 판단을 보지 못한다.

가르는 것은 결과 객체(`tool_response`)의 `content` 다. 키는 `mode`·`numFiles`·`filenames`·`content`·
`numLines`·`totalLines` 이고, 생략된 줄은 `content` 에
`<경로>:<줄 번호>:[Omitted long matching line]` 꼴로 실린다(Claude Code 2.1.296,
`.scratch/harness/probes/grep_omitted/run.py` 의 A). 경로는 여러 파일을 훑을 때만 붙고, 줄 번호는
`-n` 일 때만 붙는다(이 훅을 만든 세션이 Grep 도구로 손으로 봤다). 문턱은 바이트가 아니라 글자로
500자다 — 같은 프로브의 A 에서 영문·한글 500자 줄(한글은 1488바이트)은 그대로, 501자 줄은 표지로
나왔다. 한글은 UTF-16 단위로도 500이라, 글자인지 UTF-16 단위인지는 가르지 않았다.
- 줄이 표지 그대로이거나 `:` 뒤가 표지로 끝나면 생략된 일치 줄로 센다. 자리는 표지 앞의 머리다.
  머리가 줄 번호뿐이면(파일 하나를 훑었다) 입력의 경로를 붙인다.
- 생략된 문맥 줄(`-A`·`-B`·`-C`)은 다른 표지(`[Omitted long context line]`)이고 일치를 숨기지 않아
  세지 않는다(손으로 봤다).
- 어느 자리에도 줄 번호가 없으면 `-n` 을 켜고 다시 부르라고 덧붙인다.

그 문장이 모델에게 닿는 것은 같은 프로브의 B 가 본다. 대조군 C 는 표지 없는 일치에서 모델이 알림이
없다고 답하는 것이다.

못 보는 것:
- 줄의 내용이 `:` 와 표지로 끝나는 일치. 문서가 그 표지를 인용한 줄이면 내용이 보이는데도 생략으로
  센다(거짓 양성).
- content 가 아닌 모드(files_with_matches, count). 줄을 내지 않아 생략도 없다.
- 경로가 `:숫자` 로 끝나는 파일을 `-n` 없이 훑은 결과. 그 끝을 줄 번호로 읽어 `-n` 을 켜라는 문장을
  빼먹는다(거짓 음성. 알림 자체는 나간다).
- 표지 문구나 결과 객체의 키가 바뀐 판. 그러면 침묵한다.
- 생략된 줄을 무엇에 쓰는지. 잔존을 세는 중인지 보지 않고 생략마다 알린다.
- Bash 의 `grep`·`rg`. 매처 밖이라 이 훅에 오지 않는다(그 출력이 긴 줄을 어떻게 내는지는 재지
  않았다). 서브에이전트가 부른 Grep 에도 같은 문장을 내지만, 그 문장이 서브에이전트에게 닿는지는
  재지 않았다.
"""

from __future__ import annotations

import json
import sys
from typing import TypedDict

TOOL = "Grep"
MARKER = "[Omitted long matching line]"
# 알림의 첫 문장. 프로브(`grep_omitted/run.py`)가 모델이 이 문장을 옮겼는지 본다.
LEAD = "이 Grep 결과에는 내용 없이 생략된 일치 줄이 있다"
# 자리를 이만큼만 들고 나머지는 수로 적는다.
SHOWN = 10


class ToolInput(TypedDict, total=False):
    pattern: str
    path: str
    output_mode: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분.

    `ToolInput` 은 실제 Grep 입력의 모양을 닮게 적되 훅이 읽는 것은 `path` 뿐이다(`pattern`·
    `output_mode` 는 시험이 실제 입력을 흉내 내려고 쓴다). 결과 객체는 값을 읽은 뒤 좁히려고
    `dict[str, object]` 로 적는다."""

    tool_name: str
    tool_input: ToolInput
    tool_response: dict[str, object]


def omitted_places(content: str, path: str | None) -> list[str]:
    """생략된 일치 줄마다 그 자리(`<경로>:<줄 번호>`, 줄 번호, 경로). 모르면 빈 문자열이다."""
    places: list[str] = []
    for line in content.splitlines():
        if line != MARKER and not line.endswith(":" + MARKER):
            continue
        place = line.removesuffix(MARKER).removesuffix(":")
        if path and (not place or place.isdigit()):
            place = f"{path}:{place}" if place else path
        places.append(place)
    return places


def context_for(payload: HookPayload) -> str | None:
    """생략된 일치 줄이 있으면 컨텍스트 문장, 없거나 Grep 의 content 결과가 아니면 None."""
    if payload.get("tool_name") != TOOL:
        return None
    response = payload.get("tool_response")
    content = response.get("content") if isinstance(response, dict) else None
    if not isinstance(content, str):
        return None
    tool_input = payload.get("tool_input")
    path = tool_input.get("path") if isinstance(tool_input, dict) else None
    places = omitted_places(content, path)
    if not places:
        return None
    shown = ", ".join(place or "(자리 모름)" for place in places[:SHOWN])
    rest = (
        f" 외 {len(places) - SHOWN}개(나머지는 위 결과의 같은 표지 줄)"
        if len(places) > SHOWN
        else ""
    )
    numbered = any(place.rsplit(":", 1)[-1].isdigit() for place in places)
    retry = "" if numbered else " 줄 번호가 없으니 `-n` 을 켜고 다시 부른다."
    return (
        f"{LEAD}. 긴 일치 줄 {len(places)}개가 `{MARKER}` 로만 나왔다: {shown}{rest}."
        " 그 줄은 패턴에 맞았지만 내용은 보이지 않았다. 잔존을 세거나 일치를 하나씩 판정하는"
        " 중이면 그 줄을 따로 열어 본다(Read 도구의 offset 에 그 줄 번호, limit 에 1 을"
        f" 준다).{retry}"
    )


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
