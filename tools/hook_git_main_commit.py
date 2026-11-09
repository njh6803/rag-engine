"""PreToolUse 훅(Bash|PowerShell). 커밋이 있는 저장소에서 보호 브랜치 위의 `git commit` 을 막는다.

main 은 보호 브랜치라 커밋이 있는 저장소에서 main 위의 커밋은 언제나 실수다. 같은 체크아웃을 세션
둘이 쓰다 커밋이 엉뚱한 브랜치에 들어간 것이 두 번이다(대기열 15) — PR #46(2026-09-23)에서는 다른
세션의 커밋이 내 피처 브랜치에 얹혔고, 2026-09-27 에는 다른 세션이 체크아웃을 main 으로 옮긴 32초 뒤
내 커밋이 main 에 들어갔다. 이 훅은 뒤의 모양을 막는다. 다른 세션의 존재는 훅이 알 수 없지만 지금
브랜치는 알 수 있고, main 위의 커밋을 막는 데는 그것으로 충분하다. 커밋이 하나도 없는 저장소의
main 은 막지 않는다. 킥오프는 새 프로젝트의 첫 커밋을 main 위에 하고(`KICKOFF.md` 8단계, ADR 0028),
막으려던 사고는 커밋이 없는 저장소에서 일어나지 않는다 — 다른 세션이 체크아웃을 옮겨 올 다른
브랜치가 아직 없다.

명령 위치의 `git commit` 만 본다(hook_pr_next_session 과 같은 방식 — heredoc 본문을 버리고 인용
구간을 자리표시자 `_` 로 바꾼 뒤 제어 연산자로 나누고 조각 앞을 벗긴다. 인용을 지우면
`git -c "k=v" commit` 의 commit 이 옵션 값 자리로 밀린다, PR #91 리뷰). 브랜치는 페이로드의
`cwd` 에서 `git branch --show-current` 로 읽는다. 브랜치가 보호 브랜치일 때만 같은 `cwd` 에서
`git rev-parse --verify HEAD` 로 커밋의 유무를 읽는다 — 훅은 Bash 호출마다 돌아
(`.claude/rules/tools.md` 의 시간 항목) 작업 브랜치의 커밋마다 git 을 한 번 더 띄우지 않는다. 둘 다
환경의 `GIT_DIR`·`GIT_WORK_TREE`·`GIT_COMMON_DIR` 을 벗기고 읽는다 — git 이 훅 자식에 내보낸 값이
남아 있으면 cwd 가 아닌 저장소의 브랜치가 나온다(pre-commit 아래 실측, 2026-09-28). 훅은 단독 실행
스크립트라 서로 import 하지 않는다.
못 보는 것: `git -C <다른 저장소> commit` 과 `cd <다른 저장소> && git commit`(둘 다 cwd 의 브랜치로
판정한다 — 앞은 못 막고 뒤는 오탐이다), 래퍼 스크립트 안의 커밋, detached HEAD(브랜치 이름이 비어
막지 않는다), `HEAD` 가 아직 커밋을 가리키지 않는 main(다른 브랜치에 커밋이 있는 저장소에서
`git switch --orphan main` 한 뒤 — 커밋의 유무를 저장소가 아니라 `HEAD` 로 재므로 막지 않는다),
git 이 없거나 저장소 밖이거나 `CALL_TIMEOUT` 초 안에 돌아오지 않을 때(막지 않는다 — 게이트가 아니라
안전장치라 fail-open 이다. 커밋의 유무를 읽지 못해도 커밋이 없다고 본다), 앞 모양(다른 세션의 커밋이
내 브랜치에 얹히는 것).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import TypedDict

PROTECTED = frozenset({"main"})
_REPO_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
# git 하나를 기다리는 초. 많아야 두 번 부르므로 더해도 등록의 시간 제한(20초) 안이다(대기열 342).
CALL_TIMEOUT = 8

# `commit-tree`·`commit-graph` 는 커밋이 아니라 배관이다. `\b` 는 `-` 앞에서도 경계라 따로 막는다.
_GIT_COMMIT = re.compile(r"git\s+(?:(?:-C|-c)\s+\S+\s+|--no-pager\s+)*commit(?![\w-])")
_HEREDOC_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
_SEPARATOR = re.compile(r"\|\||&&|\$\(|`|(?<![<>])[&|]|[;\n]")
_PREFIX = re.compile(r"^(?:\s+|[({]|[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*")


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput
    cwd: str


def commits_in(command: str) -> bool:
    """명령 위치에 `git commit` 이 있는가. echo·heredoc·커밋 메시지 안의 문구는 아니다."""
    return any(_GIT_COMMIT.match(segment) for segment in _executed_segments(command))


def _executed_segments(command: str) -> list[str]:
    joined = _QUOTED.sub("_", "\n".join(_without_heredoc_bodies(command)))
    return [_PREFIX.sub("", piece, count=1) for piece in _SEPARATOR.split(joined)]


def _without_heredoc_bodies(command: str) -> list[str]:
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


def _git(args: list[str], cwd: str | None) -> subprocess.CompletedProcess[str] | None:
    """`cwd` 에서 git 을 띄운다. 저장소를 가리키는 환경 변수를 벗긴다. 띄우지 못하거나
    `CALL_TIMEOUT` 초 안에 돌아오지 않으면 None."""
    env = {key: value for key, value in os.environ.items() if key not in _REPO_LOCATION_VARS}
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=CALL_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def current_branch(cwd: str | None) -> str | None:
    """`cwd` 의 현재 브랜치 이름. 저장소가 아니거나 detached 면 None."""
    result = _git(["branch", "--show-current"], cwd)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def head_has_commit(cwd: str | None) -> bool:
    """`cwd` 의 `HEAD` 가 커밋을 가리키는가. 첫 커밋 전의 브랜치면 다른 브랜치에 커밋이 있어도
    False 다. git 을 띄우지 못해도 False 다 — 막지 않는 쪽이다."""
    result = _git(["rev-parse", "--verify", "HEAD"], cwd)
    return result is not None and result.returncode == 0


def deny_reason(branch: str | None) -> str | None:
    """보호 브랜치면 막는 이유, 아니면 None. 브랜치만 보고, 커밋 명령인지와 `HEAD` 에 커밋이
    있는지는 부르는 쪽(`reason_at`)이 본다. 문구의 "커밋이 있는 저장소에서" 는 그 전제를 적은
    규칙이다."""
    if branch not in PROTECTED:
        return None
    return (
        f"지금 브랜치가 `{branch}` 이다. 커밋이 있는 저장소에서 보호 브랜치 위의 커밋은 언제나 "
        "실수다(대기열 15 — 2026-09-27 에 다른 세션이 체크아웃을 옮긴 32초 뒤의 커밋이 main 에 "
        "들어갔다). `git branch --show-current` 로 브랜치를 보고, 작업 브랜치로 옮기거나 만든 뒤 "
        "커밋한다."
    )


def reason_at(command: str, cwd: str | None) -> str | None:
    """`cwd` 에서 친 `command` 를 막는 이유, 아니면 None. 커밋 명령인지, 보호 브랜치인지, `HEAD` 에
    커밋이 있는지를 차례로 보고 앞에서 걸러지면 뒤의 git 을 띄우지 않는다."""
    if not commits_in(command):
        return None
    reason = deny_reason(current_branch(cwd))
    if reason is None or not head_has_commit(cwd):
        return None
    return reason


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    if command is None:
        return 0
    reason = reason_at(command, payload.get("cwd"))
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
