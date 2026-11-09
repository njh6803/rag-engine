"""PostToolUse 훅(Write|Edit). 쓴 파일에 날것 줄 구분 문자나 보이지 않는 문자가 있으면 그 자리를
컨텍스트에 넣는다.

편집 도구에 넘긴 U+2028·U+2029 의 역슬래시-u 이스케이프가 날것 문자로 저장된다(대기열 22·160). 그
문자는 보이지 않아 쓴 세션도 리뷰어도 모르고, 커밋 전 `tools/check_line_separators.py` 가 pre-commit
끝에 커밋을 막고서야 드러났다. 일지 2026-10-07-19 에서는 테스트 소스에서 한 번, 그 사건을 적던
일지에서 한 번 더 났다. 막는 것은 그 검사가 이미 한다. 이 훅은 알리는 때를 편집 직후로 당기는 계기
훅이다(대기열 160, 막는 훅의 기준은 .claude/rules/tools.md).

판정은 그 검사와 같다. 처음 8000 바이트에 NUL 이 없고 UTF-8 로 읽히는 파일에서, BOM 을 벗기고 줄은
개행으로만, 열은 코드 포인트로 세어 U+2028·U+2029·U+0085 와 뒤에 LF 가 없는 CR 을 찾고, `.py` 에서는
ASCII 밖의 유니코드 일반 범주 Zs·Cf 문자(줄바꿈 없는 공백, 전각 공백, 폭 없는 공백, 방향 제어 문자,
머리 뒤의 U+FEFF 등)도 찾는다(대기열 52). 훅은 단독 실행이라 그 검사를 import 하지 않고 같은 판정을
옮겨 적었다. 두 쪽이 잡는 문자와 그 자리가 갈리면 테스트가 모든 코드 포인트로 잡는다. 디코드 길(BOM,
NUL, UTF-8 실패)과 문자 이름은 견주지 않고 각자의 테스트가 본다. 줄 구분 문자는 파일의 확장자와
자리를 가리지 않는다 — 검사는 추적 파일만 보지만, 날것 줄 구분 문자는 어느 파일에서든 거의 늘
사고다.

못 보는 것: Bash 나 다른 도구로 쓴 파일(`sed -i`, heredoc). UTF-8 로 읽히지 않는 파일과 이진 파일
(검사가 앞의 것을 판정하지 못했다고 막는다). `.py` 밖의 보이지 않는 문자와 Zs·Cf 밖의 보이지 않는
문자(검사도 보지 않는다, 그 독스트링). 파일을 읽지 못하면 아무것도 알리지 않는다(fail-open, 판정은
커밋 전 검사에 남는다).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import TypedDict

# 이스케이프가 아니라 chr() 다. 이 훅이 알리려는 사고가 이 파일에 나면 검사에 걸린다. CR 은 뒤에 LF
# 가 없을 때만 잡는다.
CR = chr(0x0D)
SEPARATORS = {
    chr(0x2028): "LINE SEPARATOR",
    chr(0x2029): "PARAGRAPH SEPARATOR",
    chr(0x0085): "NEXT LINE",
    CR: "CARRIAGE RETURN",
}
INVISIBLE_CATEGORIES = frozenset({"Zs", "Cf"})
SOURCE_SUFFIXES = frozenset({".py"})
_LF = chr(0x0A)
_SEPARATOR_PATTERN = "|".join(
    re.escape(each) + (f"(?!{_LF})" if each == CR else "") for each in SEPARATORS
)
# git 의 xdiff-interface.c `FIRST_FEW_BYTES`. 이 길이 안에 NUL 이 있으면 이진이다.
TEXT_PROBE = 8000
SHOWN = 10


class ToolInput(TypedDict, total=False):
    file_path: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_name: str
    tool_input: ToolInput


def _spots(text: str, pattern: re.Pattern[str]) -> Iterator[tuple[int, int, str]]:
    """`pattern` 이 맞은 문자마다 (줄, 열, 문자). 줄은 개행으로만 세고 열은 코드 포인트로 센다."""
    line, line_start, scanned = 1, 0, 0
    for match in pattern.finditer(text):
        start = match.start()
        newlines = text.count(_LF, scanned, start)
        if newlines:
            line += newlines
            line_start = text.rfind(_LF, scanned, start) + 1
        scanned = start
        yield line, start - line_start + 1, match.group()


def _invisible_name(character: str) -> str | None:
    if unicodedata.category(character) in INVISIBLE_CATEGORIES:
        return unicodedata.name(character, "")
    return None


def _name(character: str) -> str | None:
    """알릴 문자면 그 이름. 어느 쪽을 알릴지는 정규식이 정한다."""
    return SEPARATORS.get(character) or _invisible_name(character)


def _invisible_class(text: str) -> str | None:
    """`text` 에 든 ASCII 밖의 Zs·Cf 문자만 담은 문자 클래스. 범주는 서로 다른 글자에만 묻는다."""
    found = sorted(
        each for each in set(text) if ord(each) > 0x7F and _invisible_name(each) is not None
    )
    return f"[{''.join(re.escape(each) for each in found)}]" if found else None


def flagged_in(text: str, suffix: str) -> list[str]:
    """확장자가 `suffix` 인 파일의 글에서 알릴 문자의 자리. 항목은 `"<줄>행 <열>열 U+XXXX
    <이름>"` 이고 자리 순이다. 보이지 않는 문자는 `SOURCE_SUFFIXES` 에서만 본다."""
    invisible = _invisible_class(text) if suffix in SOURCE_SUFFIXES else None
    pattern = _SEPARATOR_PATTERN if invisible is None else f"{_SEPARATOR_PATTERN}|{invisible}"
    return [
        f"{line}행 {column}열 U+{ord(character):04X} {name}"
        for line, column, character in _spots(text, re.compile(pattern))
        if (name := _name(character)) is not None
    ]


def summary(file_path: str, found: list[str]) -> str:
    """찾은 자리들을 컨텍스트 문장으로. 앞의 `SHOWN` 개만 적고 나머지는 센다."""
    shown = ", ".join(found[:SHOWN])
    rest = f" 외 {len(found) - SHOWN}개" if len(found) > SHOWN else ""
    return (
        f"`{file_path}` 에 날것 줄 구분 문자나 보이지 않는 문자가 {len(found)}개 있다: "
        f"{shown}{rest}. 편집 도구가 역슬래시-u·역슬래시-r 이스케이프를 날것 문자로 저장했을 수 "
        "있다(대기열 22·52·160). 소스에 그 문자가 필요하면 chr(0x2028) 처럼 만들고, 문서에는 "
        "이스케이프 대신 `U+2028` 로 적는다. 필요 없는 문자면 지우거나 공백은 ASCII 공백으로, 홀로 "
        "선 CR 은 개행으로 바꾼다. 커밋 전 `tools/check_line_separators.py` 가 막으니 지금 고친다."
    )


def context_for(tool_name: str, file_path: str) -> str | None:
    """Write·Edit 가 쓴 파일에 알릴 문자가 있으면 컨텍스트 문장, 아니면 None."""
    if tool_name not in ("Write", "Edit"):
        return None
    path = Path(file_path)
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:TEXT_PROBE]:
        return None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    found = flagged_in(text, path.suffix)
    return summary(file_path, found) if found else None


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    file_path = payload.get("tool_input", {}).get("file_path")
    if file_path is None:
        return 0
    context = context_for(payload.get("tool_name", ""), file_path)
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
