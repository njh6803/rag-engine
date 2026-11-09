"""PreToolUse 훅(Bash|PowerShell). origin/main 보다 뒤처진 브랜치의 `git push` 를 막고 먼저 합치게
한다.

막는 대상은 실수로 내는 길(뒤처진 줄 모르고 푸시하는 것)이다. 일부러 뒤처진 채 푸시하는 것은
탈출구(`PUSH_BEHIND_OK`)로 지나가고, 래퍼(`bash -c "git push"`) 같은 우회는 막지 않고 아래 못 보는
것에 든다.

왜. `tools/protection.json` 의 strict 보호라 PR 은 최신 main 위에서 돈 CI 로만 병합된다. 푸시하는
순간에 이미 뒤처졌으면 병합 전에 어차피 main 을 합쳐야 하므로, 그대로 푸시한 CI 는 한 번 더 돈다.
먼저 합치고 푸시하면 그 한 번이 준다. 합친 뒤의 로컬 게이트는 어느 쪽이든 돈다. CI 실행의 갈래와
main 합치기의 수는 `.scratch/harness/probes/ci_wait/runs_per_pr.py` 가 낸다(일지 2026-10-13-38).

왜 막는가. 계기(`additionalContext`)만 주는 PreToolUse 훅은 명령을 그대로 돌린다. 모델의 차례가
훅과 도구 실행 사이에 없어, 알림은 푸시가 나간 뒤에야 읽힌다(훅 실행 순서에서 끌어낸 판단이고 재지
않았다). 커밋 뒤의 PostToolUse 에 알리는 판은 이 저장소의 커밋이 pre-commit 때문에 백그라운드로 돌아
커밋이 도는 동안 알림이 와서 접었다(셀프 리뷰 명세 축). 같은 처지였던 대기열
86(`hook_pr_head_sync`)과 같이 사용자가 막기를 골랐다(일지 2026-10-13-50).

판정. 명령 위치의 `git push`(`git -C <경로>`, `git -c <설정>`, `git --no-pager` 를 앞에 둔 것 포함.
hook_git_main_commit 과 같은 정규식과 인용 자리표시자 `_`)가 있고, 지우는 푸시(`--delete`, `-d`,
`:<브랜치>`)도 도움말(`-h`, 그것이 든 짧은 옵션 묶음, `--help`·`--help-all`. `asks_help`)도 아니고,
명령에 `PUSH_BEHIND_OK` 가 없으면 잰다. 도움말은 git 이 사용법을 내고 끝나 푸시하지 않는다. 셀프
리뷰의 명세 축 리뷰어가 확인하려고 친 `git push -h` 를 막았다(대기열 300). 페이로드의 `cwd` 에서
지금 브랜치를 읽고(main 이거나 detached HEAD 면 재지 않는다), `git fetch -q origin main` 으로
origin/main 을 갱신한 뒤 `git rev-list --count HEAD..origin/main` 이 1 이상이면 막는다. git 은
저장소를 가리키는 `GIT_*` 를 벗기고 호출마다 시간 제한을 둔다. fetch 는 출력을 버려 손자 프로세스가
살아 있어도 제한에서 끊긴다(`quiet_git`). 셋의 합(18초)에 기동 시간을 더해도 등록의 20초 안이다.
넘기거나 git 이 실패하면 막지 않는다(fail-open — 안전장치가 아니라 CI 한 번을 아끼는 장치다).

못 보는 것.
- 래퍼 뒤의 푸시(`bash -c "git push"`)와 큰따옴표 안의 치환(`"$(git push)"`).
- PowerShell 의 제어 블록(`if ($?) { git push }`)과 접두 명령(`time git push`) 뒤의 푸시. 조각 앞을
  벗기는 규칙이 그 모양을 모른다. 막지 않는다.
- `--tags` 만 올리는 푸시. 브랜치를 올리지 않아 CI 를 다시 돌리지 않는데도 잰다(탈출구로 지나간다).
- `cd <다른 저장소> && git push` 와 `git -C <다른 저장소> push`. 그 저장소가 아니라 페이로드의 `cwd`
  로 잰다(hook_git_main_commit 과 같은 한계).
- 원격 이름이 origin 이 아니거나 기본 브랜치가 main 이 아닌 저장소. 재지 않는다.
- fetch 가 실패하거나(오프라인, 지워진 원격) 시간을 넘기는 것. 막지 않는다.
- 판정 뒤에 main 이 움직이는 것. 푸시한 CI 가 도는 동안 형제가 병합하면 여전히 한 번 더 돈다.
- 값을 먹는 긴 옵션을 줄인 이름(`--push-opt -h`). 줄이지 않은 이름만 값을 먹는다고 보아 그 값
  `-h` 를 도움말로 읽고 지나간다(거짓 음성). git 은 줄인 이름을 받아 `-h` 를 값으로 먹고 푸시한다.
- 인용한 `-h`(`git push "-h"`). 인용 구간은 자리표시자로 바뀌어 도움말로 읽지 못하고 잰다(거짓
  양성). git 은 인용을 벗긴 `-h` 를 받아 사용법을 낸다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from typing import TypedDict

_REPO_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
# 로컬 git 호출 하나와 fetch 하나의 시간 제한(초).
GIT_TIMEOUT = 5.0
FETCH_TIMEOUT = 8.0
BYPASS = "PUSH_BEHIND_OK"

# hook_git_main_commit 의 _GIT_COMMIT 과 같은 모양이다(PR #91 리뷰). `git push-x` 같은 이름은 뺀다.
_GIT_PUSH = re.compile(r"git\s+(?:(?:-C|-c)\s+\S+\s+|--no-pager\s+)*push(?![\w-])")
# `--delete`, 합친 것을 포함한 짧은 옵션의 `d`(`-d`, `-fd`), 지우기 refspec(`:<브랜치>`).
# `HEAD:main` 처럼 콜론 앞에 글자가 있는 refspec 은 공백 바로 뒤가 아니라 잡지 않는다.
_DELETION = re.compile(r"\s(?:--delete|-[A-Za-z]*d[A-Za-z]*)(?:\s|$)|\s:\S")
# 다음 낱말을 값으로 먹는 긴 옵션. 줄인 이름은 모른다(독스트링의 못 보는 것). 짧은 옵션은 `-o`
# 하나다. tests/tools 의 시험이 이 기계의 `git push -h` 와 맞춘다.
VALUE_LONG_OPTIONS = frozenset(
    {"--push-option", "--receive-pack", "--exec", "--repo", "--recurse-submodules"}
)
# 아래 넷은 hook_git_main_commit 의 것과 같다. 훅은 단독 실행 스크립트라 서로 import 하지 않는다.
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


def checks_push(command: str) -> bool:
    """잴 푸시인가. 명령 위치의 `git push` 가 있고, 지우는 푸시도 도움말도 아니고, 탈출구가 없다."""
    joined = _QUOTED.sub(_placeholder, "\n".join(_without_heredoc_bodies(command)))
    if BYPASS in joined:
        return False
    for piece in _SEPARATOR.split(joined):
        segment = _PREFIX.sub("", piece, count=1)
        push = _GIT_PUSH.match(segment)
        if push is None or _DELETION.search(segment):
            continue
        if not asks_help(segment[push.end() :].split()):
            return True
    return False


def asks_help(words: list[str]) -> bool:
    """push 뒤의 낱말에 도움말(`-h`, 그것이 든 짧은 옵션 묶음, `--help`·`--help-all`)이 있는가.

    git 은 이 옵션을 만나면 사용법을 내고 푸시하지 않은 채 끝난다. 하위 명령 바로 뒤의 `--help`
    는 git 이 `git help push` 로 바꿔 돌린다. 값을 먹는 옵션의 값(`-o -h`, 묶음에서 `o` 뒤의 글자)과
    `--` 뒤는 옵션이 아니다. 여기까지는 tests/tools 의 실제 git 시험이 이 기계의 git 으로 잰다.
    낱말 머리의 `#` 부터는 셸이 버리는 주석이라 그 뒤를 읽지 않는다. 읽으면 `git push origin x #
    -h` 를 도움말로 보고 재지 않는데, git 은 그 명령으로 푸시한다(셀프 리뷰 명세 축)."""
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        if word == "--" or word.startswith("#"):
            return False
        if word in ("--help", "--help-all"):
            return True
        if word in VALUE_LONG_OPTIONS:
            index += 1
        elif word.startswith("-") and not word.startswith("--"):
            for position, letter in enumerate(word[1:], start=1):
                if letter == "o":
                    index += 0 if word[position + 1 :] else 1
                    break
                if letter == "h":
                    return True
    return False


def _placeholder(quoted: re.Match[str]) -> str:
    """인용 구간의 자리표시자. 인용한 지우기 refspec(`":old"`)은 머리의 콜론을 남긴다."""
    return ":_" if quoted.group(0)[1:2] == ":" else "_"


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


def _environment() -> dict[str, str]:
    """저장소를 가리키는 `GIT_*` 를 벗기고, 자격 증명을 묻느라 멈추지 않게 한다."""
    environment = {k: v for k, v in os.environ.items() if k not in _REPO_LOCATION_VARS}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment


def run_git(cwd: str, timeout: float, *args: str) -> str | None:
    """git 의 표준 출력. 실패하거나 띄우지 못하거나 시간을 넘기면 None."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=_environment(),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def quiet_git(cwd: str, timeout: float, *args: str) -> bool:
    """출력을 버리고 git 이 성공했는지만 낸다.

    fetch 처럼 손자 프로세스(`git-remote-https`, `ssh`)를 띄우는 호출에 쓴다. 출력을 붙잡으면
    kill 뒤에도 손자가 쥔 파이프가 닫히기를 기다려 시간 제한이 늦게 끝난다. 윈도에서 2초 제한이
    12초 자는 손자가 끝난 뒤에야 돌아왔다(멈춘 fetch 시험과
    `.scratch/harness/probes/push_behind_hook_mutations.toml` 의 "fetch 의 출력을 붙잡는다").
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def behind_count(cwd: str) -> int | None:
    """origin/main 을 fetch 로 갱신한 뒤 `cwd` 의 브랜치가 뒤처진 커밋 수. 재지 못하면 None.

    main 이거나 detached HEAD 면 재지 않는다. 원격 추적 ref 를 옮기는 부수 효과가 있다.
    """
    branch = run_git(cwd, GIT_TIMEOUT, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch is None or branch == "main":
        return None
    if not quiet_git(cwd, FETCH_TIMEOUT, "fetch", "-q", "origin", "main"):
        return None
    count = run_git(cwd, GIT_TIMEOUT, "rev-list", "--count", "HEAD..origin/main")
    return int(count) if count is not None and count.isdigit() else None


def reason_text(count: int) -> str:
    return (
        f"이 브랜치는 origin/main 보다 {count}커밋 뒤처졌다. strict 보호라 병합 전에 어차피 "
        "main 을 합쳐야 해서, 지금 푸시하면 CI 가 한 번 더 돈다. `git merge origin/main` 으로 "
        "합치고(충돌이면 풀고) CLAUDE.md 의 검증 명령과 `uv run python tools/sibling_overlap.py` "
        "를 지난 뒤 다시 푸시한다. 충돌 없는 합치기에는 pre-commit 이 돌지 않는다. 일부러 뒤처진 "
        f"채 푸시하려면 Bash 에서 `{BYPASS}=1 git push …`, PowerShell 에서 "
        f"`$env:{BYPASS}='1'; git push …` 로 친다(일지 2026-10-13-50)."
    )


def reason_for(command: str, cwd: str, behind: Callable[[str], int | None]) -> str | None:
    """막을 이유. 잴 푸시가 아니면 git 을 부르지 않는다."""
    if not checks_push(command):
        return None
    count = behind(cwd)
    return reason_text(count) if count else None


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    if command is None:
        return 0
    reason = reason_for(command, payload.get("cwd") or os.getcwd(), behind_count)
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
