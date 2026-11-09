"""PreToolUse 훅(Bash). 셸의 작업 폴더를 지금 체크아웃 밖으로 옮기는 `cd` 와, 같은 체크아웃의
하위 폴더로 옮기는 `cd` 를 막는다.

막는 대상은 실수로 내는 길(작업 폴더가 다음 호출로 이어지는 것을 잊은 `cd`)이다. 일부러 하는
우회(변수에 담은 대상 `cd "$X"`, 인용 안의 `eval "cd …"`, 스크립트 파일 안의 cd, PowerShell 의
`Set-Location`)는 막지 않고 아래 못 보는 것에 든다.

Bash 도구의 작업 폴더는 호출 사이에 이어진다. `cd` 로 다른 체크아웃이나 스크래치패드에 들어가면 그
뒤의 상대 경로와 git 이 그 자리에 닿는다. 워크트리 세션의 일지에 여섯 번 있다. 주 체크아웃으로
셋(일지 2026-09-28-02, 2026-10-06-11, 2026-10-07-01. 뒤의 둘은 그 뒤 모든 명령을 앱의 가드가 거부해
`EnterWorktree(path)` 로 돌아왔다), 지우다 만 워크트리 폴더로 하나(2026-10-07-15. `.git` 이 없어 그
안의 git 은 주 체크아웃에 닿는다), 스크래치패드로 둘(2026-10-12-06·09)이다. 대기열 123 은 그중
06-11, 07-15, 12-09 를 회차로 셌다. 주 체크아웃으로 간 셋은 원래 저장소 루트로 cd 하지 말라는 앱의
환경 안내를 어긴 것이라 막는 훅이다(CLAUDE.md 교정 루프). 스크래치패드로 간 둘은 그 안내 밖이지만
사용자가 같은 행으로 세기를 승인했다(일지 2026-10-12-09 회고 4). 주 체크아웃 세션에도 건다. 사건은
없지만 같은 cd 이고, 그 세션에는 가드가 없어 잘못 옮긴 뒤의 git 이 다른 체크아웃에, `.git` 없는
폴더에서는 루트에 조용히 닿는다. 실패가 조용하고 패턴이 고정된 것은 첫 사건에서 막는다던
그때의 예외(.claude/rules/tools.md, 2026-10-19에 손상으로 좁혔다)를 가드 없는 쪽에 넓혔다.
tidy-checkouts 의 "하지 않는 것" 줄(남은 워크트리 폴더로 cd 하지 않는다)도 주 체크아웃 세션에서 도는
스킬의 것이다. 경로를 인자로 주는 대안이 있어 막는 값은 다시 치는 한 번이다.

하위 폴더로 옮기는 `cd` 도 막는다(대기열 252). `cd web/packages/ui/src/components && …` 가 작업
폴더를 같은 워크트리의 하위 폴더로 옮겨 다음 호출의 상대 경로가 그 자리에서 풀렸다. 세 번(일지
2026-10-12-36, 2026-10-13-10, 2026-10-13-22) 있었고 셋째에야 알아채 절대 경로로 되돌렸다. 그래서
처음에는 막지 않고 알렸다(additionalContext, 대기열 225). git 은 여전히 제 체크아웃에 닿고, 한 호출
안에서 그 자리에 머무는 쓰임(`cd web && pnpm …`)이 있어서였다. 그 알림을 받은 뒤에도 같은 세션이
하위 폴더로 두 번 더 옮겼고, 셋째 뒤 변환기가 하위 폴더에서 돌아 모듈을 찾지 못했다(일지
2026-10-13-62). 지침(알림)으로 적은 뒤에도 어겨져 막는 훅으로 올렸다(.claude/rules/tools.md 의
계기·막는 훅 가름). 한 호출 안에 머무는 쓰임도 막히지만 폴더를 인자로 주거나(`pnpm -C web …`) 서브셸
`( cd web && … )` 로 가두는 대안이 있어 막는 값은 다시 치는 한 번이다. 밖으로 옮기는 자리가 있으면
그 이유를 낸다(다른 체크아웃의 길을 안내한다).

판정. 명령 위치의 `cd`·`pushd`·`popd` 를 차례로 따라가며 페이로드의 `cwd` 에서 대상을 푼다. 풀린
자리 하나라도 `cwd` 가 든 체크아웃 밖이면 막는다. 마지막 자리만 보지 않는다 — 들른 사이의 명령이
다른 자리에서 돌고, `&&` 중간이 실패하면 돌아오는 `cd` 가 돌지 않는다. 체크아웃은 가장 가까운 조상
중 `.claude/worktrees/<이름>` 이거나 `.git` 이 있는 폴더다. 앞의 것은 `.git` 이 없어도 따로
센다(지우다 만 폴더). git 을 부르지 않는다 — 그 폴더에서 부른 git 은 주 체크아웃을 루트로 읽는다.
체크아웃 안의 중첩 저장소(`.git` 이 있는 하위 폴더)도 다른 체크아웃으로 센다. 그 안에 머문 셸의 git
은 그 저장소를 겨눈다. 밖으로 옮기는 자리가 없으면 같은 길로 풀린 자리 하나라도 그 체크아웃의
루트가 아닐 때 하위 폴더의 이유로 막는다. 들렀다 돌아오는 `cd web && … && cd ..` 도 막는다 —
중간이 실패하면 돌아오지 않는다.
역슬래시와 슬래시, 대소문자(윈도의 경로는 가리지 않는다), Git Bash 의 `/c/…` 표기는 같은 자리로
본다. `CLAUDE_PROJECT_DIR` 은 쓰지 않는다. 워크트리 세션에서는 주 체크아웃을
가리킨다(.claude/rules/tools.md).

세지 않는 것. 작업 폴더를 남기지 않는 곳 — 서브셸 `( … )`, 명령 치환 `$( … )`·백틱, 둘 이상의
단으로 된 파이프의 한 단, `&` 로 끝나 백그라운드로 도는 `&&`·`||` 목록 — 의 `cd` 와, 인용·heredoc
본문·주석 안의 문구다. 명령 앞의 리다이렉션(`2>/dev/null cd …`)과 인용 없는 `eval` 은 벗기고 본다.
인용은 지우지 않고 같은 길이의 `_` 로 바꿔(PR #91 리뷰의 자리표시자를 길이까지 맞춘 것) 구조는 가린
문자열에서 보고 인자는 같은 자리의 원문에서 꺼낸다. `cwd` 가 어느 체크아웃에도 들지 않으면 막지
않는다. 이 세션의 체크아웃을 몰라, 막으면 돌아오는 `cd` 까지 막는다.

못 보는 것: 변수·치환·글롭이 든 대상(`cd "$TMP"`. 그 뒤의 상대 경로도 판정하지 않는다),
`cd -`·`popd`(돌아간 자리를 따라가지 않아 그 뒤의 상대 경로도 판정하지 않는다), `CDPATH`, 심볼릭
링크, 인용 안에서 도는 `eval "cd …"`, 스크립트 파일 안의 cd, 함수 본문의 cd(한 줄 정의
`f() { cd …; }` 와 `function` 정의는 세지 않아 그 함수를 부르면 놓치고, 여러 줄 정의는 부르지 않아도
센다), `case` 갈래 안의 cd 와 짝 없는 `)` 뒤의 깊이, `$'…'` 안의 이스케이프된 작은따옴표 뒤,
백그라운드로 돈 묶음 `{ cd …; } &` 과 파이프의 한 단이 된 묶음 `{ cd …; } | cat`(센다 — 거짓 양성),
옵션이 붙은 `time -p cd …`, 같은 줄의 따옴표 안에 든 `<<`(heredoc 으로 읽어 뒤의 줄을 지운다. 이
저장소에서 흔한 `"$(cat <<'EOF'` 와 줄 단위로 가르지 못한다), PowerShell 의 `Set-Location`(이 훅은
Bash 매처다. 여섯 사건이 모두 Bash 였다). 이 훅이 보지 못한 길로 이미 다른 체크아웃에 들어간 세션은
돌아오는 cd 도 막힌다. 그 세션의 체크아웃을 몰라서다. 워크트리 세션은 `EnterWorktree(path)` 로
돌아오고(이유 문장이 안내한다), 주 체크아웃 세션이 워크트리로 밀려났으면 cd 로 돌아올 길이 없다.
하위 폴더 판정이 못 보는 것: `;` 로 이어 늘 돌아오는 `cd web; …; cd ..`(그래도 막는다 — 거짓
양성), 서브에이전트의 하위 폴더 `cd`(서브에이전트의 Bash 는 호출마다 작업 폴더가 처음으로 돌아간다고
그 프롬프트가 적는다 — claude 실행 파일의 문장을 읽었고 재지 않았다. 입력의 `agent_id` 로 가르지
않고 막는다 — 거짓 양성), 앞 호출에서 이미 하위 폴더로 옮겨진 셸(`cwd` 가 하위 폴더여도 `cd` 가 없는
명령은 막지 않는다. `cd` 가 있으면 이유가 지금 작업 폴더와 루트로 돌아오는 길을 적는다), 위의 못
보는 것과 같은 풀 수 없는 대상(`cd "$X"`).
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import sys
from pathlib import Path
from typing import Literal, NamedTuple, TypedDict

Verb = Literal["cd", "pushd", "popd"]
# (동사, 대상). 대상은 인자 그대로이고, 인자 없는 cd 는 `~`, 풀 수 없으면 None 이다.
Step = tuple[Verb, str | None]
# `_VERB` 가 잡은 낱말을 `Verb` 로 좁힌다.
_VERBS: dict[str, Verb] = {"cd": "cd", "pushd": "pushd", "popd": "popd"}

_MENTION = re.compile(r"(?<![\w-])(?:cd|pushd|popd)(?![\w-])")
# here-string `<<<` 은 heredoc 이 아니다. 잡으면 뒤의 줄을 본문으로 지운다. 구분자는 식별자 밖의
# 글자(`END-OF-FILE`)와 역슬래시 인용(`<<\EOF`)도 받는다. 못 알아보면 본문의 cd 를 센다.
_HEREDOC_OPENER = re.compile(r"(?<!<)<<(?!<)(-?)\s*\\?(['\"]?)([^\s;&|<>()'\"\\]+)\2")
# 파이프라인을 가르는 것과 파이프 한 단을 가르는 것. `2>&1`·`&>` 의 & 와 `>|` 의 | 는
# 리다이렉션이다.
_SEPARATOR = re.compile(r"\|\||&&|;;|\|&|[;\n]|(?<![<>&])&(?![&>])|(?<![>|])\|(?![|&])")
_PIPES = frozenset({"|", "|&"})
# 한 목록 안을 잇는 것. 목록이 `&` 로 끝나면 bash 는 그 목록 전체를 백그라운드로 돌린다.
_LIST_JOINERS = frozenset({"&&", "||", *_PIPES})
_PREFIX = re.compile(
    r"(?:\s+|[{!](?=\s)|(?:if|then|else|elif|do|while|until|time|builtin|command|eval)(?=\s)"
    r"|[A-Za-z_][A-Za-z0-9_]*=\S*(?=\s)|\d*(?:[<>]{1,2}|&>)&?\s*[^\s<>&;|]+(?=\s))*"
)
_VERB = re.compile(r"(cd|pushd|popd)(?=\s|$)")
_REDIRECTION = re.compile(r"^(?:\d*[<>]|&>)")
_UNRESOLVABLE = re.compile(r"[$`*?\[]")
_MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")
_DRIVE = re.compile(r"^([A-Za-z]):(?=/|$)")
_DRIVE_RELATIVE = re.compile(r"^[A-Za-z]:")


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput
    cwd: str


def normalize(path: str) -> str | None:
    """절대 경로를 슬래시와 대문자 드라이브로 고른다. 절대 경로가 아니면 None."""
    text = path.replace("\\", "/")
    msys = _MSYS_DRIVE.match(text)
    if msys is not None:
        text = f"{msys.group(1)}:{text[2:]}"
    drive = ""
    matched = _DRIVE.match(text)
    if matched is not None:
        drive = f"{matched.group(1).upper()}:"
        text = text[2:] or "/"
    if not text.startswith("/"):
        return None
    return drive + posixpath.normpath(re.sub("/+", "/", text))


def resolve(target: str, current: str | None, home: str) -> str | None:
    """`cd` 의 대상을 `current` 에서 풀어 고른 절대 경로. 풀 수 없으면 None."""
    if target == "~" or target.startswith("~/"):
        base = normalize(home)
        return None if base is None else normalize(f"{base}/{target[2:]}")
    if target.startswith("~"):
        return None
    absolute = normalize(target)
    if absolute is not None:
        return absolute
    if _DRIVE_RELATIVE.match(target) or current is None:
        return None
    return normalize(f"{current}/{target}")


def checkout_of(path: str) -> str | None:
    """`path` 를 담은 가장 가까운 체크아웃. `.claude/worktrees/<이름>` 이거나 `.git` 이 있는
    조상이다.

    앞의 것은 `.git` 이 없어도 체크아웃으로 센다. 없는 경로도 조상을 따라 판정한다."""
    parts = path.replace("\\", "/").rstrip("/").split("/")
    for end in range(len(parts), 0, -1):
        if (
            end >= 3
            and parts[end - 2].lower() == "worktrees"
            and parts[end - 3].lower() == ".claude"
        ):
            return "/".join(parts[:end])
        folder = "/".join(parts[:end])
        if os.path.exists(f"{folder}/.git"):
            return folder or "/"
    return None


def cd_steps(command: str) -> list[Step]:
    """작업 폴더를 남기는 자리에 선 `cd`·`pushd`·`popd` 를 차례로."""
    source = "\n".join(_without_heredoc_bodies(command.replace("\\\n", "  ")))
    masked = _top_level(_masked(source))
    segments = _segments(masked)
    background = _backgrounded(segments)
    steps: list[Step] = []
    for index, (start, end, separator) in enumerate(segments):
        before = segments[index - 1][2] if index else ""
        if separator in _PIPES or before in _PIPES or index in background:
            continue
        prefix = _PREFIX.match(masked, start, end)
        verb = _VERB.match(masked, prefix.end() if prefix else start, end)
        if verb is None:
            continue
        steps.append(_step(verb.group(1), source[verb.end() : end]))
    return steps


def _backgrounded(segments: list[tuple[int, int, str]]) -> set[int]:
    """`&` 로 끝나는 목록에 든 조각의 번호들."""
    indexes: set[int] = set()
    start = 0
    for index, (_, _, separator) in enumerate(segments):
        if separator in _LIST_JOINERS:
            continue
        if separator == "&":
            indexes.update(range(start, index + 1))
        start = index + 1
    return indexes


def _step(word: str, arguments: str) -> Step:
    verb = _VERBS[word]
    if verb == "popd":
        return (verb, None)
    try:
        tokens = shlex.split(arguments, comments=True)
    except ValueError:
        return (verb, None)
    rest = [token for token in tokens if not _REDIRECTION.match(token)]
    while rest and rest[0].startswith("-") and rest[0] != "-":
        option = rest.pop(0)
        if option == "--":
            break
    if not rest:
        return (verb, "~" if verb == "cd" else None)
    target = rest[0]
    if _UNRESOLVABLE.search(target) or (verb == "pushd" and target.startswith("+")):
        return (verb, None)
    return (verb, target)


def _masked(text: str) -> str:
    """인용·이스케이프·주석을 같은 길이의 `_` 로 바꾼다. 줄바꿈은 둔다."""
    out = list(text)
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            close = text.find("'", index + 1)
            index = _blank(out, index, len(text) if close < 0 else close + 1)
        elif char == '"':
            index = _blank(out, index, _double_quote_end(text, index))
        elif char == "\\" and index + 1 < len(text):
            index = _blank(out, index, index + 2)
        elif char == "#" and (index == 0 or text[index - 1].isspace() or text[index - 1] in ";&|("):
            close = text.find("\n", index)
            index = _blank(out, index, len(text) if close < 0 else close)
        else:
            index += 1
    return "".join(out)


def _double_quote_end(text: str, start: int) -> int:
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
        elif text[index] == '"':
            return index + 1
        else:
            index += 1
    return len(text)


def _blank(out: list[str], start: int, end: int) -> int:
    for index in range(start, end):
        if out[index] != "\n":
            out[index] = "_"
    return end


def _top_level(masked: str) -> str:
    """서브셸·명령 치환·백틱 안을 `_` 로 바꾼다. 그 안의 cd 는 작업 폴더를 남기지 않는다."""
    out: list[str] = []
    depth = 0
    in_backtick = False
    for char in masked:
        if char == "`":
            in_backtick = not in_backtick
            out.append("_")
        elif char == "(":
            depth += 1
            out.append("_")
        elif char == ")":
            depth = max(0, depth - 1)
            out.append("_")
        else:
            out.append("_" if depth or in_backtick else char)
    return "".join(out)


def _segments(masked: str) -> list[tuple[int, int, str]]:
    """(시작, 끝, 뒤의 구분자). 마지막 조각의 구분자는 빈 문자열이다."""
    segments: list[tuple[int, int, str]] = []
    position = 0
    for separator in _SEPARATOR.finditer(masked):
        segments.append((position, separator.start(), separator.group()))
        position = separator.end()
    segments.append((position, len(masked), ""))
    return segments


def _without_heredoc_bodies(command: str) -> list[str]:
    """heredoc 본문 줄을 같은 길이의 공백으로 바꾼다. 자리를 원문과 맞추려고 지우지 않는다."""
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
            body = lines[index]
            candidate = body.lstrip("\t") if strips_tabs else body
            index += 1
            if candidate == terminator:
                kept.append(body)
                break
            kept.append(" " * len(body))
    return kept


def _heredoc_opener(line: str) -> re.Match[str] | None:
    """줄에서 heredoc 을 여는 첫 표지. 산술 `(( … ))` 안의 `<<`(왼쪽 밀기)는 아니다."""
    for opener in _HEREDOC_OPENER.finditer(line):
        before = line[: opener.start()]
        if before.count("((") <= before.count("))"):
            return opener
    return None


class Destination(NamedTuple):
    """`cd` 하나가 옮긴 자리. `place` 는 그 자리가 든 체크아웃이고 없으면 None 이다."""

    shown: str
    path: str
    place: str | None


def deny_reason(command: str, cwd: str, home: str) -> str | None:
    """작업 폴더를 `cwd` 가 든 체크아웃 밖이나 그 체크아웃의 하위 폴더로 옮기면 막는 이유, 아니면
    None.

    풀린 자리 하나라도 그 체크아웃 밖이면 밖의 이유를 낸다. 그런 자리가 없고 하나라도 그
    체크아웃의 루트가 아니면 하위 폴더의 이유를 낸다. `home` 은 인자 없는 `cd` 와 `~` 의 자리다."""
    start = normalize(cwd)
    own = None if start is None or _MENTION.search(command) is None else checkout_of(start)
    if start is None or own is None:
        return None
    destinations = _destinations(command, start, home)
    for destination in destinations:
        if destination.place is None or destination.place.lower() != own.lower():
            return _reason(destination, own)
    for destination in destinations:
        if destination.path.lower() != own.lower():
            return _subfolder_reason(destination, own, start)
    return None


def _destinations(command: str, start: str, home: str) -> list[Destination]:
    """`start` 에서 차례로 풀린 자리들."""
    # `cd -` 와 `popd` 는 모르는 자리로 둔다. 밖으로 나가는 첫 자리에서 이미 막으므로 그 둘이 돌아갈
    # 곳은 안이거나 모르는 자리다. 판정은 바뀌지 않고 뒤의 상대 경로만 판정하지 않게 된다.
    found: list[Destination] = []
    current: str | None = start
    for verb, target in cd_steps(command):
        current = None if target in (None, "-") else resolve(target, current, home)
        if current is not None:
            found.append(Destination(f"{verb} {target}", current, checkout_of(current)))
    return found


def _subfolder_reason(destination: Destination, own: str, start: str) -> str:
    """하위 폴더로 옮겨 막는 이유. `start` 가 루트가 아니면(앞 호출에서 이미 옮겨졌다) 그 사실과
    루트로 돌아오는 길을 적는다. 루트에서 옮긴다고 적으면 안내한 폴더 인자를 루트 기준으로 줘, 그
    경로가 하위 폴더에서 풀린다."""
    moved = start.lower() != own.lower()
    origin = (
        f"지금 작업 폴더 `{start}`(이미 체크아웃 루트 {own} 가 아니다)에서"
        if moved
        else f"체크아웃 루트({own})에서"
    )
    text = (
        f"`{destination.shown}` 가 셸의 작업 폴더를 {origin} 하위 폴더 `{destination.path}` 로"
        " 옮긴다. Bash 의 작업 폴더는 다음 호출로 이어져, 그 뒤 명령의 상대 경로가 그 하위 폴더에서"
        " 풀린다(대기열 225·252 — 알림을 받은 뒤에도 하위 폴더로 옮겨 변환기가 모듈을 찾지 못했다)."
        " 폴더를 인자로 주거나(`pnpm -C <폴더>`, `uv run --directory <폴더>`, `git -C <폴더>`,"
        " `ls <경로>`), 서브셸 `( cd <폴더> && … )` 로 가둬 다시 친다. 이 호출 전체가 돌지 않았다."
    )
    if moved:
        text += (
            " 상대 경로는 지금 작업 폴더에서 풀리니,"
            f" 먼저 `cd {shlex.quote(own)}` 으로 루트에 돌아오거나(이 `cd` 는 지나간다) 절대 경로를"
            " 준다."
        )
    return text


def _reason(destination: Destination, own: str) -> str:
    place = destination.place
    where = "체크아웃 밖" if place is None else f"다른 체크아웃({place})"
    return (
        f"`{destination.shown}` 가 셸의 작업 폴더를 지금 작업 폴더가 든 체크아웃({own})에서"
        f" {where}의 `{destination.path}` 로 옮긴다. Bash 의 작업 폴더는 다음 호출로 이어져"
        " 그 뒤의 상대 경로와 git 이 그 자리에 닿는다(대기열 123 — 워크트리 세션에서는 그 뒤"
        " 모든 명령을 앱의 가드가 거부했고, `.git` 없는 폴더의 git 은 주 체크아웃에 닿는다)."
        " 옮기지 말고 경로를 인자로 준다(`ls <경로>`, `grep … <경로>`, Read 도구). 여러 명령이"
        " 그 자리에서 돌아야 하면"
        " 스크립트 파일로 써서 경로로 부른다. 다른 워크트리에서 일하려는 것이면, 또는 워크트리"
        " 세션이 이미 다른 체크아웃으로 밀려나 제 워크트리로 돌아가려는 것이면"
        " `EnterWorktree(path)` 로 옮긴다."
    )


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    cwd = payload.get("cwd")
    if command is None or cwd is None:
        return 0
    reason = deny_reason(command, cwd, str(Path.home()))
    if reason is None:
        return 0
    output = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
    print(json.dumps({"hookSpecificOutput": output}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
