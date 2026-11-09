"""PreToolUse 훅(Bash). 큰 heredoc 을 막고 Write 도구로 안내한다.

CLAUDE.md 환경 함정 "큰 heredoc 은 셸 파서가 깨진다. 긴 스크립트는 파일로"가 2026-09-21 세션에서
두 번 어겨졌다(테스트 파일, PR 본문). 기계적 패턴이라 훅이다. heredoc 본문이 MAX_LINES 를 넘으면
deny 하고 이유를 돌려준다. 에이전트는 그 이유를 읽고 Write 로 파일을 쓴다.
"""

from __future__ import annotations

import json
import re
import sys
from typing import TypedDict

MAX_LINES = 40


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput


_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


def longest_heredoc(command: str) -> int:
    """명령 안 heredoc 본문 중 가장 긴 것의 줄 수. heredoc 이 없으면 0.

    종료 줄은 Bash 와 같이 본다. `<<EOF` 는 줄 전체가 정확히 EOF 일 때만, `<<-EOF` 는 선행 탭을
    벗긴 뒤 EOF 일 때만 끝난다. 공백 들여쓰기된 ` EOF` 는 본문이다(PR #24 CodeRabbit 지적).
    """
    lines = command.splitlines()
    longest = 0
    index = 0
    while index < len(lines):
        match = _OPENER.search(lines[index])
        if match is None:
            index += 1
            continue
        strips_tabs = match.group(1) == "-"
        terminator = match.group(3)
        body = 0
        index += 1
        while index < len(lines) and not _closes(lines[index], terminator, strips_tabs=strips_tabs):
            body += 1
            index += 1
        longest = max(longest, body)
        index += 1
    return longest


def _closes(line: str, terminator: str, *, strips_tabs: bool) -> bool:
    candidate = line.lstrip("\t") if strips_tabs else line
    return candidate == terminator


def reason_for(command: str) -> str | None:
    length = longest_heredoc(command)
    if length <= MAX_LINES:
        return None
    return (
        f"heredoc 본문이 {length}줄이다(상한 {MAX_LINES}). 큰 heredoc 은 셸 파서가 깨진다"
        "(CLAUDE.md 환경 함정). Write 도구로 파일을 쓰고 셸에는 경로만 넘긴다."
    )


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    reason = reason_for(command) if command is not None else None
    if reason is None:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
