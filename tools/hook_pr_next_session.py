"""PostToolUse 훅(Bash|PowerShell|GitHub MCP). PR을 열거나 병합하면 next-session 계기를 넣는다.

단계를 닫는 순간의 지침은 어겨진다(retro 계기가 그랬고 hook_journal_retro 가 됐다). 같은 자리라
처음부터 훅이고, 계기만 넣고 막지는 않는다. 게이트를 두지 않는 이유는 일지 2026-09-21 세션 경계.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Literal, TypedDict

Action = Literal["create", "merge"]

SHELL_TOOLS = frozenset({"Bash", "PowerShell"})
# 데스크톱 앱의 GitHub 플러그인 도구와 claude.ai 클라우드 세션의 GitHub 도구는 이름이 다르다.
# 클라우드 쪽이 빠져 PR을 열어도 계기가 들어오지 않았다(대기열 79). 이 표의 이름과
# .claude/settings.json 매처의 MCP 이름은 같아야 하고, tests/tools 가 두 집합이 같은지 본다.
# 못 보는 것: claude.ai 커넥터로 붙인 GitHub. 데스크톱 앱에서 커넥터 도구는 `mcp__<uuid>__…`
# 꼴이라(데스크톱 앱 세션의 Atlassian·Slack 커넥터가 그랬다, 2026-10-01 손으로 봤다) 여기 이름에
# 걸리지 않는다.
MCP_TOOLS: dict[str, Action] = {
    "mcp__plugin_github_github__create_pull_request": "create",
    "mcp__plugin_github_github__merge_pull_request": "merge",
    "mcp__github__create_pull_request": "create",
    "mcp__github__merge_pull_request": "merge",
}

# 명령 위치의 `gh pr create|merge` 만 계기다. echo·printf·커밋 메시지·heredoc 본문에 문구가
# 데이터로 들어가면 오탐이었다(CodeRabbit, PR #28). 셸 파서 없이 넷만 본다. heredoc 본문과
# 인용 구간을 버리고, 제어 연산자와 명령 치환(`$(`, 백틱)으로 나누고, 조각 앞의 공백·괄호·
# 환경변수 대입을 벗긴다. 대신 `bash -c "gh pr merge"` 같은 래퍼 뒤의 실행과
# `"$(gh pr create)"` 처럼 큰따옴표 안의 치환은 못 본다. 래퍼 스크립트 사각과 같은 종류다
# (일지 2026-09-21 세션 경계).
_GH_PR = re.compile(r"gh\s+pr\s+(create|merge)\b")
# 실행하지 않는 옵션. `--` 뒤는 옵션이 아니다(hook_handoff 의 `_NOT_RUNNING` 과 같다, 대기열 408).
_NOT_RUNNING = frozenset({"--dry-run", "--help", "-h"})
# hook_bash_heredoc 의 _OPENER 와 같다. 훅은 단독 실행 스크립트라 서로 import 하지 않는다.
_HEREDOC_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
# `2>&1` 의 & 는 리다이렉션이라 분리자가 아니다.
_SEPARATOR = re.compile(r"\|\||&&|\$\(|`|(?<![<>])[&|]|[;\n]")
_PREFIX = re.compile(r"^(?:\s+|[({]|[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*")

# `gh api` 로 `repos/<주인>/<이름>/pulls` 에 POST 하는 것도 PR 을 여는 것이다(대기열 408). 메서드는
# `-X`·`--method` 가 정하고, 없으면 몸(`-f`·`-F`·`--input`)이 있을 때 POST, 아니면 GET 이다.
# 도움말(`gh api --help`)은 필드만 말해, `--input` 은 탐침으로 쟀다
# (`.scratch/harness/probes/gh_api_method.py`). 엔드포인트가 인용되기
# 쉬워(`"repos/{owner}/{repo}/pulls"`) 인용 구간을 지우지 않고 그 안의 공백과 셸 문자를 `_` 로 바꿔
# 한 낱말로 남긴다. 판정은 hook_handoff 의 `opens_pr_by_api` 와 같고, 두 시험이 같은 표
# (`tests/tools/gh_api_cases.py`)를 쓴다. 못 보는 것: `gh api graphql` 의 `createPullRequest`,
# 변수로 준 엔드포인트(`gh api "$ENDPOINT"`), REST 의 병합(`PUT …/pulls/<번호>/merge`).
_GH_API = re.compile(r"gh\s+api(?![\w-])")
_NOT_WORD = re.compile(r"[^\w./{}:@=+,-]")
_PULLS = re.compile(r"(?:^|/)repos/[^/]+/[^/]+/pulls/?$")
_API_VALUE_OPTIONS = frozenset(
    {
        "-X",
        "--method",
        "-f",
        "--raw-field",
        "-F",
        "--field",
        "-H",
        "--header",
        "--input",
        "-q",
        "--jq",
        "-t",
        "--template",
        "--hostname",
        "-p",
        "--preview",
        "--cache",
    }
)
_API_BODY_OPTIONS = frozenset({"-f", "--raw-field", "-F", "--field", "--input"})
_CONTINUATION = re.compile(r"`\n")


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_name: str
    tool_input: ToolInput


def action_for(tool_name: str, command: str | None) -> Action | None:
    """PR을 여는 호출이면 "create", 병합하는 호출이면 "merge", 둘 다 아니면 None.

    셸 도구는 명령 위치에 있는 `gh pr create|merge` 와 `pulls` 에 POST 하는 `gh api` 를 찾고,
    GitHub MCP 도구는 이름으로 안다. `gh pr view|checks|comment` 와 `git push` 는 세션을 닫는 일이
    아니고, 문구를 데이터로 품은 echo·printf·커밋 메시지·heredoc 본문도 아니다. `--dry-run`·
    `--help`·`-h` 를 준 명령은 돌리지 않는다.
    """
    if tool_name in MCP_TOOLS:
        return MCP_TOOLS[tool_name]
    if tool_name not in SHELL_TOOLS or command is None:
        return None
    for segment in _executed_segments(command):
        match = _GH_PR.match(segment)
        if match is not None and _runs(segment[match.end() :]):
            return "create" if match.group(1) == "create" else "merge"
    if any(opens_pr_by_api(segment) for segment in _api_segments(command)):
        return "create"
    return None


def _runs(rest: str) -> bool:
    """명령 뒤의 글에 실행하지 않는 옵션이 없는가. `--` 뒤는 경로라 옵션으로 보지 않는다."""
    words = rest.split()
    options = words[: words.index("--")] if "--" in words else words
    return not _NOT_RUNNING.intersection(options)


def opens_pr_by_api(segment: str) -> bool:
    """조각이 `gh api` 로 `repos/<주인>/<이름>/pulls` 에 POST 하는가. 메서드는 `-X`·`--method` 가
    정하고, 없으면 몸(`-f`·`-F`·`--input`)이 있을 때 POST 다."""
    match = _GH_API.match(segment)
    if match is None:
        return False
    words = segment[match.end() :].split()
    method: str | None = None
    body = False
    endpoint: str | None = None
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        if word == "--":
            if endpoint is None and index < len(words):
                endpoint = words[index]
            break
        if not word.startswith("-") or word == "-":
            endpoint = word if endpoint is None else endpoint
            continue
        if word in _NOT_RUNNING:
            return False
        if word.startswith("--"):
            option, equals, value = word.partition("=")
        else:
            option, value = word[:2], word[2:]
            equals = "=" if value else ""
            value = value.removeprefix("=")  # `-X=POST` 의 `=` 는 값이 아니다
        if not equals and option in _API_VALUE_OPTIONS:
            value = words[index] if index < len(words) else ""
            index += 1
        if option in ("-X", "--method"):
            method = value.upper()
        elif option in _API_BODY_OPTIONS:
            body = True
    if endpoint is None or _PULLS.search(endpoint) is None:
        return False
    return method == "POST" if method is not None else body


def _executed_segments(command: str) -> list[str]:
    """명령 위치부터 시작하는 조각들. heredoc 본문과 인용 구간을 버리고 나눈 뒤 앞을 벗긴다."""
    joined = _QUOTED.sub("", "\n".join(_without_heredoc_bodies(command)))
    return [_PREFIX.sub("", piece, count=1) for piece in _SEPARATOR.split(joined)]


def _api_segments(command: str) -> list[str]:
    """`_executed_segments` 와 같되 인용 구간을 그 안의 글로 남긴다. 공백과 셸 문자는 `_` 로 바꿔
    한 낱말로 두고, 빈 인용도 `_` 로 자리를 지킨다. PowerShell 의 줄 이음(줄 끝 백틱)은 이어 붙인다.
    백틱에서 가르면 둘째 줄의 몸(`-f`)을 놓친다."""
    lines = _CONTINUATION.sub(" ", "\n".join(_without_heredoc_bodies(command)))
    joined = _QUOTED.sub(lambda quoted: _NOT_WORD.sub("_", quoted.group(0)[1:-1]) or "_", lines)
    return [_PREFIX.sub("", piece, count=1) for piece in _SEPARATOR.split(joined)]


def _without_heredoc_bodies(command: str) -> list[str]:
    """heredoc 여는 줄은 남기고 본문과 종료 줄을 버린다. 종료 판정은 hook_bash_heredoc 와 같다."""
    lines = command.splitlines()
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        opener = _HEREDOC_OPENER.search(line)
        if opener is None:
            continue
        strips_tabs = opener.group(1) == "-"
        terminator = opener.group(3)
        while index < len(lines):
            candidate = lines[index].lstrip("\t") if strips_tabs else lines[index]
            index += 1
            if candidate == terminator:
                break
    return kept


def context_for(action: Action) -> str:
    """에이전트에게 넣을 계기 문장. 성공 여부는 방금 본 도구 결과로 에이전트가 판단한다."""
    verb = "여는" if action == "create" else "병합하는"
    return (
        f"PR을 {verb} 명령이 실행됐다. 성공했으면 next-session 스킬의 계기다. "
        "사용자에게 묻지 말고 Skill 도구로 next-session 을 지금 돌린다. "
        "PR을 열었으면 그 스킬의 순서 1이 가리키는 병합 절차로 반영과 병합을 먼저 마친다. "
        "다만 인계 계기(hook_handoff)가 함께 왔으면 Skill 도구로 부르지 말고 그 계기의 문장대로 "
        "인계 절차 파일을 Read 로 열어 따른다. 세션은 그것으로 끝나지 않는다."
    )


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    tool_name = payload.get("tool_name")
    if tool_name is None:
        return 0
    command = payload.get("tool_input", {}).get("command")
    action = action_for(tool_name, command)
    if action is None:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context_for(action),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
