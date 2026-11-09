"""Stop 훅. 턴을 끝내는 답의 산문이 한국어가 아니면 멈춤을 막고 한국어로 다시 쓰게 한다.

`CLAUDE.md` 의 "답변과 문서는 한국어로 쓴다"가 있는데도 세션의 보고를 영어로 썼고, 사용자가
"한국어로"라고 고친 것이 트랜스크립트에 다섯 번이다(세션 넷 — 2026-09-23 d20ee262, 2026-09-30
c3423704, 2026-10-01 7440a40d, 그리고 같은 날 59aeea28 에 두 번). 지침이 어겨진 것이라 막는
훅이다(CLAUDE.md 교정 루프, 대기열 83).

입력의 `last_assistant_message` 는 턴 전체가 아니라 마지막 텍스트다. 텍스트·도구 호출·텍스트로 된
턴에서 뒤의 것만 왔다(`.scratch/harness/probes/stop_payload/`, claude 2.1.286). 마지막 메시지에
텍스트 블록이 여럿일 때 그중 무엇이 오는지는 가르지 않았다. 판정은 그 답에서 코드 펜스, `>` 인용
줄, 코드 스팬, 마크다운 링크의 대상, URL, ASCII 글자 사이에 구분자가 든 토큰(경로, kebab·snake
이름)을 뺀 산문의 글자로 한다. 한글(음절과 호환 자모)과 라틴 문자를 합쳐 `MIN_LETTERS` 이상이고
그중 한글이 `MIN_HANGUL_RATIO` 보다 적으면 막는다.

문턱은 이 저장소와 그 워크트리의 트랜스크립트로 쟀다(`.scratch/harness/probes/stop_korean_ratio.py`,
2026-10-01). Stop 이 받는 답(`end_turn` 메시지의 마지막 텍스트)만 메시지 id 로 겹치지 않게 세어
754개를 판정했다. 막은 30개는 모두 비율 0.041 이하이고(가장 높은 것은 영어 보고 사이에 한국어 질문을
끼운 답), 막지 않은 답의 최저는 0.340 이었다. 그 사이가 비어 있어 문턱을 그 가운데 둔다. 사용자가
고친 다섯은 모두 막힌다. 인용 줄과 식별자를 빼는 규칙은 첫 판의 탐침(턴 끝을 잘못 잡았다)에서 막힌
한국어 답 둘 — 영어 원문을 `>` 로 길게 인용한 답과 스킬 이름을 나열한 답 — 에서 왔다.

SDK 로 띄운 세션(`CLAUDE_CODE_ENTRYPOINT` 가 `sdk-` 로 시작)은 판정하지 않는다. 같은
트랜스크립트의 `sdk-py` 세션 247개는 보안 리뷰이고, 텍스트 블록 262개가 모두 지금 판정으로
막힐 영어다. 그 세션은 `StructuredOutput` 도구 호출로 끝나 `end_turn` 답이 없었다. 거기서 Stop 이
도는지는 재지 않았지만, 돈다면 막기가 프로그램의 흐름에 끼어든다. 훅 환경의 변수와 트랜스크립트의
`entrypoint` 는 같은 값이었다 — 데스크톱 세션 안에서 띄운 `claude -p` 는 둘 다 물려받은
`claude-desktop` 이었다(위 탐침, 표본 하나).

멈춤을 막으면 이유가 모델에게 닿아 다음 답을 쓰고, 그 뒤의 두 번째 Stop 은 `stop_hook_active` 가
참이다(위 탐침). 그때는 판정하지 않아 한 턴에 다시 쓰기는 한 번이다. 사용자가 영어 답을 청한 턴은
이유 문장이 한국어 한 줄로 끝내라고 한다. 영어를 세션 내내 청하면 턴마다 한 번씩 막혀 왕복이 하나씩
더 든다. 훅 안의 예외는 막지 않고 지나간다(Claude Code 의 비차단 오류).

못 보는 것: 도구 호출 사이의 중간 텍스트(입력에 마지막 텍스트만 온다). 영어가 대부분이어도 한글이
20% 이상인 답. 한글도 라틴 문자도 아닌 글자(일본어, 중국어)는 세지 않는다 — 그런 답은 섞인 라틴
문자만으로 판정해, 8자 이상이면 막고 그보다 적으면 지나간다. 다른 Stop 훅이 먼저 막은 뒤의 영어
답(`stop_hook_active` 가 참이다). 산문 속 따옴표 인용은 센다 — 영어 원문을 따옴표로 길게 든 한국어
답은 막힐 수 있다. 구분자 없는 이름(`grilling`, `tdd`)은 산문으로 센다 — 이름만 나열한 답은 막힐
수 있다(스킬 목록 답 b925504b 는 끝의 한국어 한 줄로 0.340 이 되어 지나갔다). 식별자에 붙은 한글
조사는 식별자와 함께 빠진다. 데스크톱 세션 안에서 띄운 `claude -p` 는 부모의 값을 물려받아
판정한다. 재지 못한 것: SDK 세션의 훅 환경이 실제로 `sdk-py` 인지(Python SDK 설치가 uv 캐시
오류로 실패했다)와 그 세션이 프로젝트 설정을 싣는지, CI 의 claude-review(claude-code-action)와
claude.ai 클라우드 세션의 entrypoint 와 이 훅이 실리는지.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import TypedDict

# 이보다 글자(한글과 라틴 문자)가 적은 답은 판정하지 않는다. "OK"·"Next" 같은 한 낱말 답이다.
# 측정에서 판정하지 않은 22개 중 한글이 없는 것은 "Next"(4) 하나였다(2026-10-01).
MIN_LETTERS = 8
# 한글이 글자의 이 비율보다 적으면 한국어 답이 아니다. 측정의 빈 구간(0.041~0.340)의 가운데다.
MIN_HANGUL_RATIO = 0.2
# 프로그램이 읽는 세션의 entrypoint 머리(sdk-py, sdk-ts, sdk-cli).
SDK_PREFIX = "sdk-"

# 여는 펜스부터 같은 문자로 여는 길이 이상의 닫는 펜스까지. 닫히지 않으면 끝까지다(CommonMark).
# 백틱 펜스의 정보 문자열에는 백틱이 없다 — 있으면 펜스가 아니라 코드 스팬이다.
_FENCE = re.compile(
    r"^ {0,3}(?:"
    r"(?P<ticks>`{3,})[^`\n]*\n.*?(?:^ {0,3}(?P=ticks)`*[ \t]*$|\Z)"
    r"|(?P<tildes>~{3,})[^\n]*\n.*?(?:^ {0,3}(?P=tildes)~*[ \t]*$|\Z))",
    re.MULTILINE | re.DOTALL,
)
# 인용 블록의 줄.
_BLOCKQUOTE = re.compile(r"^ {0,3}>.*$", re.MULTILINE)
# 같은 길이의 백틱 묶음으로 닫는 코드 스팬. 한 줄 안에서만 본다.
_CODE_SPAN = re.compile(r"(?<!`)(?P<ticks>`+)(?!`).+?(?<!`)(?P=ticks)(?!`)")
# 마크다운 링크의 대상. 링크 글은 산문으로 남긴다.
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://\S*")
# ASCII 글자 사이에 구분자가 든 토큰. 경로, kebab·snake 이름, `owner/repo#1` 같은 식별자다. 한글
# 사이의 구분자(`읽기/쓰기`)는 식별자가 아니다. 토큰에 붙은 한글 조사도 같이 빠진다.
_IDENTIFIER = re.compile(r"\S*[A-Za-z0-9_][-_./:#@][A-Za-z0-9_]\S*")
_HANGUL = re.compile(r"[가-힣ㄱ-ㆎ]")
_LATIN = re.compile(r"[A-Za-z]")


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 Stop 훅 입력 중 이 훅이 읽는 부분."""

    stop_hook_active: bool
    last_assistant_message: str


def prose_of(message: str) -> str:
    """코드 펜스, 인용 블록, 코드 스팬, 링크 대상, URL, 식별자를 뺀 산문."""
    prose = _FENCE.sub("", message)
    prose = _BLOCKQUOTE.sub("", prose)
    prose = _CODE_SPAN.sub("", prose)
    prose = _LINK_TARGET.sub("]", prose)
    prose = _URL.sub("", prose)
    return _IDENTIFIER.sub("", prose)


def letter_counts(message: str) -> tuple[int, int]:
    """산문의 (한글 음절과 자모 수, 라틴 문자 수)."""
    prose = prose_of(message)
    return len(_HANGUL.findall(prose)), len(_LATIN.findall(prose))


def block_reason_for(message: str) -> str | None:
    """산문이 한국어가 아니면 멈춤을 막을 이유, 아니면 None."""
    hangul, latin = letter_counts(message)
    letters = hangul + latin
    if letters < MIN_LETTERS or hangul >= letters * MIN_HANGUL_RATIO:
        return None
    return (
        f"이번 턴의 마지막 답의 산문이 한국어가 아니다(코드를 뺀 글자 {letters}자 중 한글 "
        f"{hangul}자). CLAUDE.md 의 원칙대로 답변은 한국어로 쓴다. 같은 내용을 한국어로 다시 "
        "쓴다. 코드, 명령, 식별자, 인용은 그대로 둔다. 사용자가 영어 답을 요청했다면 다시 쓰지 "
        "않고 그 사실만 한국어 한 줄로 적는다."
    )


def is_program_session(entrypoint: str | None) -> bool:
    """SDK 로 띄운 세션인가. 그 답은 프로그램이 읽는다."""
    return entrypoint is not None and entrypoint.startswith(SDK_PREFIX)


def main() -> int:
    payload: HookPayload = json.load(sys.stdin.buffer)
    if payload.get("stop_hook_active"):
        return 0
    if is_program_session(os.environ.get("CLAUDE_CODE_ENTRYPOINT")):
        return 0
    message = payload.get("last_assistant_message")
    if not isinstance(message, str):
        return 0
    reason = block_reason_for(message)
    if reason is None:
        return 0
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
