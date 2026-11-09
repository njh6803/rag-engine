"""PreToolUse 훅(Bash). Git Bash 가 git 의 인자를 경로 목록으로 바꿀 모양이면 알린다. 막지 않는다.

Git Bash(MSYS)는 네이티브 프로그램을 띄울 때 경로처럼 보이는 인자를 윈도 경로로 바꾼다.
`git show origin/main:.scratch/x.md` 의 인자는 git 에 `origin\\main;.scratch\\x.md` 로 가서 명령이
실패한다. 다섯 세션이 여섯 번 헛쳤고 매번 일지에만 남았다(대기열 195, 일지 2026-09-23-02·
2026-10-05-02(두 번)·2026-10-07-12·2026-10-11-01·2026-10-12-21. 대기열 행은 2026-10-11-01 을 빠뜨려
다섯으로 셌다). 실패는 대개 `fatal:` 로 드러나 조용하지 않다(`git show` 는 `fatal: ambiguous
argument 'origin\\main;.scratch\\retro-queue.md'` 로 끝났다, 2026-10-12 손으로 봤다). 지침으로 적은
적도 없어 막는 훅이 아니라 additionalContext 로 알린다(.claude/rules/tools.md). 거짓 양성의 비용은
문장 하나다. 다만 `git rev-parse --verify --quiet` 처럼 종료 코드만 내는 명령은 아무것도 찍지 않고
1로 끝나(프로브 C 절) "없다"로 조용히 읽힌다. 알림은 그런 결과를 다시 보게 한다.

무엇이 바뀌는지는 `.scratch/harness/probes/msys_pathconv/run.sh` 로 쟀다(이 PC, MSYS 런타임 3.1.7,
git 2.32.0.windows.2). 일지의 옛 가설(콜론 양쪽에 `/`)은 틀렸다 — `a/b:c/d` 는 바뀌지 않는다.
판정은 git-for-windows/msys2-runtime 의 `winsup/cygwin/msys2_path_conv.cc` 에 있는
`find_path_start_and_type` 의 차례를 따르고, 그 차례는 `converts` 의 독스트링에 적었다(그 파일을
마지막으로 고친 main 의 커밋 `a362d1c` 를 2026-10-12 에 읽었다). 소스와 3.1.7 이 다른 자리(`..:.x`
는 소스대로면 바뀌는데 이 PC 에서는 바뀌지 않았다)는 잰 것을 따랐다. 이 저장소에서는 점으로 시작하는
경로(`.scratch/`·`.claude/`·`.github/`·`.gitignore`)를 가리킨 `<rev>:<경로>` 가 바뀐다. 판정 표는
tests/tools/test_hook_bash_msys_pathconv.py 가 그 프로브의 출력을 옮긴다.

MSYS 프로그램에 넘긴 인자는 바뀌지 않아(프로브 B 절의 `/usr/bin/printf`·`/usr/bin/echo`) 명령
위치의 git 만 본다. 따옴표는 셸이 벗긴 뒤에 바뀌므로(프로브 A 절은 모양을 모두 따옴표로 넘겼다)
풀고 본다(`shlex`). `:` 나 `git` 이 없는 명령은 나누지 않고 지나간다. 조각은 `;`·`&&`·`||`·`|`·
`&`·괄호·개행으로 가르고, 리다이렉션(`>|` 포함)은 조각을 가르지 않고 그 대상과 바로 앞의 fd 숫자만
뺀다(`git show 2>/dev/null origin/main:.x`, `2>/dev/null git …`).
명령 위치는 조각 머리의 환경변수 대입과 `if`·`then`·`env`·`time` 같은 낱말 뒤다. heredoc 본문은
벗기고(산술 `(( … ))` 안의 `<<` 는 heredoc 이 아니다. 판정은 hook_bash_cd_outside 와 같다), 줄
잇기(`\\` 개행)는 잇는다. 같은 명령 어디에든 `MSYS_NO_PATHCONV=` 나 `MSYS2_ARG_CONV_EXCL=` 이 있으면
보지 않는다. Bash 도구가 Git Bash 인 자리, 곧 윈도(`os.name` 이 `nt`)이거나 MSYS 가 남기는
`MSYSTEM` 이 있을 때만 알린다. 클라우드의 리눅스 세션은 MSYS 가 아니다. 리눅스 CI 의 훅 러너는
발동 사례에 `MSYSTEM` 을 넣어 돌린다.

못 보는 것: git 밖의 네이티브 프로그램(`uv`·`gh`·`docker`. 프로브 A 는 uv 로 쟀다), 다른 명령을
거쳐 부른 git(`bash -c "git …"`, `xargs git`, 백틱 치환), heredoc 본문으로 셸이 돌리는
git(`bash <<'EOF'`), 같은 줄의 따옴표 안에 든 `<<`(heredoc 으로 읽어 뒤의 줄을 지운다.
hook_bash_cd_outside 와 같다), 변수·치환이 든 인자(`"$REV:.scratch/x.md"`. 셸이 펼친 값을
모른다), `/` 로 시작하는 인자(소스에서 다른 갈래라 옮기지 않았다. `/c/project:/d/x` 는 바뀐다),
프로세스 치환 `<( … )` 뒤의 인자(괄호가 조각을 가른다), 단어 가운데의 `#` 뒤(셸과 달리 주석으로
읽는다), 끈 대입이 다른 조각에만 있거나 `MSYS2_ARG_CONV_EXCL` 의 값이 그 인자를 덮지 않는 명령,
닫히지 않은 따옴표가 든 명령 전체, PowerShell 도구(매처가 Bash 다. 여섯 사건이 모두 Git Bash
였다). 모두 거짓 음성이다. 거짓 양성은 머리 글자(`+`·`%` 등) 바로 뒤가 `//:` 인 인자다(`+//:/` 는
바뀌지 않는데 알린다). MSYS 는 그런 머리 글자를 건너뛰고 `/` 로 시작하는 갈래로 보는데, 그
갈래를 옮기지 않아서다. PR 직전 리뷰가 이 PC 의 Git Bash 로 인자 약 6만 개를 손으로 대조해 이
모양 열하나만 거짓 양성으로 찾았다.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from collections.abc import Mapping
from typing import TypedDict

# 조각을 가르는 글자. shlex 가 인용 밖의 이 글자들을 따로 떼어 낸다.
_PUNCTUATION = "();<>|&\n"
# 리다이렉션 연산자(`>`·`>>`·`>|`·`2>&1` 의 `>&`·`&>`·`<<`·`<<<`). 조각을 가르지 않고 대상 하나를
# 먹는다.
_REDIRECTION = re.compile(r"[<>&]*[<>][<>&]*\|?")
_PATHCONV_OFF = re.compile(r"\b(?:MSYS_NO_PATHCONV|MSYS2_ARG_CONV_EXCL)=")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_LEADING_WORDS = frozenset(
    {
        "!",
        "{",
        "if",
        "then",
        "else",
        "elif",
        "do",
        "while",
        "until",
        "time",
        "command",
        "exec",
        "nohup",
        "env",
    }
)
_GIT = re.compile(r"(?:.*[/\\])?git(?:\.exe)?", re.IGNORECASE)
_SKIP_CHARS = frozenset("`'*?[]")
_SKIP_PARTS = ("/~", "::", "@@", ":./", ":../")
# here-string `<<<` 은 heredoc 이 아니다. 구분자 모양은 hook_bash_cd_outside 와 같다.
_HEREDOC_OPENER = re.compile(r"(?<!<)<<(?!<)(-?)\s*\\?(['\"]?)([^\s;&|<>()'\"\\]+)\2")


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput


def converts(argument: str) -> bool:
    """Git Bash 가 네이티브 프로그램에 넘길 때 이 인자를 경로 목록으로 바꾸는가.

    차례는 MSYS 소스를 따르고 결과는 프로브로 쟀다(모듈 독스트링).
    1. 공백·탭·개행, `` ` ``·`'`·`*`·`?`·`[`·`]`, `/~`·`::`·`@@`, `:./`·`:../`(git 의
       `<rev>:./<경로>`)가 든 인자는 바뀌지 않는다.
    2. `~` 로 시작하면 바뀌지 않는다. `/` 로 시작하면 보지 않는다(소스에서 다른 갈래라 옮기지
       않았다).
    3. 앞에서부터 읽다가 첫 `=` 를 만나면 그 뒤를 2부터 다시 본다(`x=origin/main:.x`). `-` 로
       시작하면 첫 `:`·`,` 에서도 그렇다(`-Lx:origin/main:.y`·`-x,origin/main:.y` 는 바뀌고
       `-Lorigin/main:.x` 는 그대로다).
    4. 첫 `:` 뒤가 `.`·`/` 면 그 앞에 `/`·`\\` 가 있을 때 바뀌고(`//` 는 URL 이라 아니다) 없으면
       그대로다. 다른 글자면 그 뒤에 `=` 가 있을 때만 그 글자를 건너뛰고 읽어 간다
       (`a:b=origin/main:.x` 는 바뀐다).
    """
    if any(char.isspace() for char in argument):
        return False
    if any(char in _SKIP_CHARS for char in argument) or any(
        part in argument for part in _SKIP_PARTS
    ):
        return False
    last_equals = argument.rfind("=")
    start = 0
    # MSYS 는 `=`(`-` 머리면 `:`·`,` 도) 뒤를 같은 함수로 다시 본다. 재귀하면 `=` 가 천 개쯤에서
    # 한도를 넘어 훅이 예외로 끝나므로(PR 직전 리뷰) 그 자리로 옮겨 다시 돈다.
    while argument[start : start + 1] not in ("~", "/"):
        dashed = argument[start : start + 1] == "-"
        has_slashes = False
        index = start + 1 if dashed else start
        start = -1
        while index < len(argument):
            char = argument[index]
            if char == "=" or (dashed and char in ":,"):
                start = index + 1
                break
            if char == ":" and index + 1 < len(argument):
                if argument[index + 1] in "./":
                    return has_slashes and argument[index + 1 : index + 3] != "//"
                if last_equals <= index:
                    return False
                index += 2
                continue
            if char in "/\\":
                has_slashes = True
            index += 1
        if start < 0:
            return False
    return False


def converted_arguments(command: str) -> list[str]:
    """명령 위치의 git 이 받을 인자 가운데 Git Bash 가 바꿀 것들. 없으면 비어 있다."""
    # 바뀌는 인자에는 늘 `:` 가 있고 보는 명령은 git 뿐이다. 둘 중 하나라도 없으면 낱말로 나누지
    # 않는다. shlex 는 긴 낱말 하나에 제곱 시간이 들어 1MB 따옴표 문자열에 약 20초였다(PR 직전
    # 리뷰가 손으로 봤다). 모든 Bash 호출에 붙는 훅이라 대부분의 명령이 여기서 끝난다.
    if ":" not in command or "git" not in command.lower() or _PATHCONV_OFF.search(command):
        return []
    found: list[str] = []
    for segment in _segments(command):
        found.extend(argument for argument in _git_arguments(segment) if converts(argument))
    return found


def _segments(command: str) -> list[list[str]]:
    """따옴표를 푼 낱말들을 조각마다. 따옴표가 닫히지 않으면 비어 있다."""
    source = "\n".join(_without_heredoc_bodies(command.replace("\\\n", " ")))
    # shlex 의 주석은 줄 끝의 개행까지 먹는다. 개행을 둘로 늘려 주석 뒤에도 조각 경계를 남긴다.
    source = source.replace("\n", "\n\n")
    lexer = shlex.shlex(source, posix=True, punctuation_chars=_PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    takes_target = False
    for token in tokens:
        if takes_target:
            takes_target = False
        elif not token or any(char not in _PUNCTUATION for char in token):
            segments[-1].append(token)
        elif _REDIRECTION.fullmatch(token):
            if segments[-1] and segments[-1][-1].isdigit():
                segments[-1].pop()
            takes_target = True
        else:
            segments.append([])
    return [segment for segment in segments if segment]


def _git_arguments(segment: list[str]) -> list[str]:
    """조각의 명령이 git 이면 그 인자들, 아니면 비어 있다."""
    index = 0
    while index < len(segment) and (
        segment[index] in _LEADING_WORDS or _ASSIGNMENT.match(segment[index])
    ):
        index += 1
    if index == len(segment) or _GIT.fullmatch(segment[index]) is None:
        return []
    return segment[index + 1 :]


def _without_heredoc_bodies(command: str) -> list[str]:
    """heredoc 본문 줄을 뺀 줄들. 종료 줄 판정은 hook_bash_heredoc 과 같다. `<<-` 는 탭만 벗긴다."""
    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        opener = _heredoc_opener(line)
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


def _heredoc_opener(line: str) -> re.Match[str] | None:
    """줄에서 heredoc 을 여는 첫 표지. 산술 `(( … ))` 안의 `<<`(왼쪽 밀기)는 아니다."""
    for opener in _HEREDOC_OPENER.finditer(line):
        before = line[: opener.start()]
        if before.count("((") <= before.count("))"):
            return opener
    return None


def context_for(command: str) -> str | None:
    """알릴 문장. 바뀔 인자가 없으면 None."""
    arguments = converted_arguments(command)
    if not arguments:
        return None
    shown = ", ".join(f"`{argument}`" for argument in arguments)
    return (
        f"이 명령의 {shown} 은(는) Git Bash(MSYS)가 경로 목록으로 바꿔 git 에 넘긴다"
        "(`origin/main:.scratch/x.md` 가 `origin\\main;.scratch\\x.md` 로 간다, 대기열 195)."
        " 첫 콜론 왼쪽에 `/` 가 있고 오른쪽이 `.`·`/` 로 시작하면 대개 그렇다(`:./` 와 `//` 는"
        " 아니다). 결과가 실패나 '없음'이면 이 때문일 수 있다. 그 git 바로 앞에"
        " `MSYS_NO_PATHCONV=1` 을 붙여 다시 치거나, 저장소 루트에서 `<rev>:./<경로>` 로 쓴다."
    )


def under_msys(os_name: str, environ: Mapping[str, str]) -> bool:
    """Bash 도구가 Git Bash(MSYS)인 자리인가. 윈도이거나 MSYS 가 남기는 `MSYSTEM` 이 있다."""
    return os_name == "nt" or "MSYSTEM" in environ


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    if command is None or not under_msys(os.name, os.environ):
        return 0
    context = context_for(command)
    if context is None:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
