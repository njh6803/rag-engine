"""PreToolUse 훅(Bash). `git commit -F <파일>` 의 메시지를 그 저장소의 commit-msg 판정으로 먼저 대
보고, 걸리면 커밋을 막는다.

막는 대상은 실수로 내는 길(commit-msg 가 거절할 메시지 파일로 하는 커밋)이다. 일부러 하는
우회(`-m`·heredoc 의 `-F -`, `--no-verify`, `git` 을 다른 이름으로 부르기)는 막지 않는다 — 막는
자리를 앞당길 뿐이라 commit-msg 단계가 그대로 판정하거나 건너뛴다. 아래 못 보는 것에 든다.

커밋 메시지 형식(제목 72자 등)은 pre-commit 의 commit-msg 단계(`tools/check_commit_msg.py`)가
판정한다. 그 단계는 pre-commit 단계의 검사가 모두 끝난 뒤라, 제목 하나 때문에 약 7~8분의 게이트를
한 번 더 돌았다. 세 번(일지 2026-10-13-06 의 484초, 2026-10-13-12·2026-10-13-30 의 약 7분)
있었다(대기열 222).
대기열 항목은 "알린다"였지만 막는다. PreToolUse 의 additionalContext 는 도구 결과 옆에 들어가고
Claude 는 그것을 다음 모델 요청에서 읽는다(공식 hooks 문서, 2026-10-13 내려받아 글자 그대로 대
봤다: "next to the tool result", "Claude reads the reminder on the next model request"). 커밋이
게이트를 다 돈 뒤에야 모델이 알림을 보니 되풀이를 줄이지 못한다.

막는 것은 commit-msg 훅이 같은 파일을 거절할 커밋으로 좁힌다. 막는 훅은 지침으로 적은 뒤에도
어겨진 것이 확인된 뒤에만 더한다는 규약(.claude/rules/tools.md)을 이 훅은 새 금지로 읽지 않는다 —
막는 자리를 앞당길 뿐이어야 한다. 그래서 git 이 그 파일을 그대로 메시지로 쓰지 않거나 commit-msg
판정이 돌지 않을 수 있는 커밋은 보지 않는다. `--no-verify`·`-n`, 커밋 앞의 대입이나 앞 명령의
`export` 로 준 `SKIP=…commit-msg…`, `git -c core.hooksPath=…`(훅을 건너뛰거나 바꾼다), `-e`·`--edit`
(편집 뒤의 메시지가 판정된다), `--squash`·`--fixup`(git 이 제목에 접두를 붙여 통과 접두에 든다),
`--cleanup`(정리 방식에 따라 판정이 보는 첫 줄이 달라진다), `--dry-run`·`--help`·`-h`(커밋하지
않는다), `-F -`, 커밋 앞의 단순 명령에 그 파일 인자가 나오는 것(먼저 쓰는 파일이라 PreToolUse 에서는
없거나 옛 내용이다. `./m.txt` 와 `m.txt` 처럼 철자가 달라도 같은 경로면 같다고 본다. 커밋 뒤의
`&& rm <파일>` 은 커밋이 읽는 내용을 바꾸지 않아 보지 않는다), 커밋 앞에 `cd`·`pushd` 가 있는
것(상대 경로가 어디서 풀릴지 모른다)이다. `-F` 가 여럿이면 git 처럼 마지막 것만 본다. 판정
스크립트는 커밋하는 저장소의 것이다. 커밋 폴더(`cwd` 와 `git -C`)의 가장 가까운 `.git` 조상이 그
루트이고, 그 루트가 이 훅의 저장소(아래 신뢰 경계)에 들고, 루트의 `.pre-commit-config.yaml` 이
`tools/check_commit_msg.py` 를 부르고 그 파일이 있을 때만 판정한다. 메시지 파일이 어디 있는지는
가르지 않는다(스크래치패드의 파일로 이 저장소에서 커밋해도 판정한다). 판정은 옮겨 적지 않고 그
스크립트를 자식 프로세스로 띄워 받는다. 같은 판정이 정의로 서고, 훅끼리 import 하지 않는
규약(.claude/rules/tools.md)도 지킨다. 워크트리 세션에서는 훅 파일이 주 체크아웃의 것이어도 판정은
그 워크트리의 스크립트가 한다.

찾는 것. 명령을 shlex 로 낱말로 나누고 제어 연산자(`&&`, `;`, `|`, 줄바꿈 등)에서 가른 단순
명령마다, 앞의 변수 대입을 벗긴 첫 낱말이 `git` 이고 전역 옵션 뒤의 하위 명령이 `commit` 이면 그
인자에서 `-F <파일>`·`-F<파일>`·`--file <파일>`·`--file=<파일>`·묶은 짧은 옵션(`-aF <파일>`)을
찾는다. 값을 받는 다른 옵션(`-m`, `-c`, `-C`, `-t`, `--author` 등)의 값은 건너뛰고, `--` 뒤는 보지
않는다. 줄 끝 역슬래시로 이은 줄은 한 줄로 보고, heredoc 본문 줄은 비운다(본문의 `git commit` 은
명령이 아니다). 파일은 커밋 폴더에서 풀고, `~` 와 Git Bash 의 `/c/…` 표기를 받는다.

못 보는 것(모두 지나간다): `-F -`(heredoc 이나 파이프로 넘긴 메시지)와 `-m` 의 메시지, 위에서 보지
않는다고 적은 커밋, 변수·치환이 든 경로, shlex 가 거절하는 명령(짝 없는 따옴표), `git` 을 다른
이름으로 부르는 것(`command git`, `env … git`, 전체 경로). 자식이 시간 제한(10초)을 넘기거나 판정
문장 없이 끝나도 지나간다. 앞 호출에서 `export` 한 `SKIP` 은 모른다 — 그 셸에서 커밋하면 commit-msg
훅이 돌지 않는데도 막는다(거짓 양성). 이 훅의 저장소 밖에서 하는 커밋(다른 프로젝트, 이 체크아웃
안에 든 중첩 저장소)과, 이 훅이 든 체크아웃의 `.git` 을 읽지 못해 이 훅의 저장소를 모를 때의 커밋은
그 저장소에 commit-msg 판정이 있어도 판정하지 않는다. `--separate-git-dir` 로 만든 저장소의
워크트리에 이 훅이 들면 주 체크아웃의 커밋도 밖으로 본다(공통 폴더의 이름이 `.git` 이 아니라 그
부모를 주 체크아웃으로 세지 않는다 — 거짓 음성).

판정 스크립트를 실행하는 신뢰 경계. 판정 스크립트는 이 훅의 저장소의 것만 띄운다. 이 훅은 권한
확인 전에 돌아, 띄우는 스크립트는 사용자가 그 Bash 명령을 승인하기 전에 돈다. 첫 판은 커밋하는
저장소가 이 프로젝트가 아니어도 그 저장소의 스크립트를 띄웠다(대기열 246). 이 훅의 저장소는 이 훅
파일이 든 체크아웃(래퍼가 `runpy` 로 띄워도 `__file__` 은 그 파일이다)의 공통 git 폴더에서 git 을
띄우지 않고 읽는다. 그 체크아웃의 `.git` 이 폴더면 그것이, 파일이면 `gitdir:` 이 가리키는 폴더의
`commondir` 가 공통 폴더다. 그 체크아웃 자신, 이름이 `.git` 인 공통 폴더의 부모(주 체크아웃), 공통
폴더의 `worktrees/<이름>/gitdir` 이 가리키는 `.git` 의 부모(등록된 워크트리)가 이 훅의 저장소다.
경로는 심볼릭 링크와 대소문자를 풀어(`realpath`, `normcase`) 견준다. 판정은 양쪽을 다 대 본다. 커밋
폴더의 `.git` 만 읽고 등록에서 거꾸로 대 보지 않으면, `.git` 파일이 이 저장소의 워크트리 관리 폴더를
가리키게 지은 폴더를 이 저장소로 읽는다. 거꾸로 등록의 `gitdir` 만 믿으면, 워크트리 폴더를 git 없이
지운 뒤 남은 등록의 자리에 새로 만든 저장소를 이 저장소로 읽는다. 그래서 등록된 워크트리는 그
`.git` 파일의 `gitdir:` 이 다시 그 등록을 가리킬 때만 센다. 커밋 폴더의 조상을 거슬러 오를 때
드라이브 문자만 남은 자리는 `C:/` 로 맞춘다. `C:` 는 윈도에서 현재 폴더 기준이라 그대로 두면 존재
확인과 판정 스크립트는 드라이브 루트를, 경계 판정과 설정 읽기는 훅의 현재 폴더를 본다. 경위는 일지
2026-10-13-47 과 2026-10-16-27.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, TypedDict

CHECKER = "tools/check_commit_msg.py"
PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"
CHECK_TIMEOUT = 10.0
# 이 훅 파일이 든 체크아웃. 이 훅의 저장소를 여기서 읽는다(독스트링의 신뢰 경계).
HOOK_CHECKOUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONTROL = re.compile(r"^[;&|()<>\n]+$")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# git 의 전역 옵션 가운데 값을 다음 낱말로 받는 것.
_GLOBAL_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
# `git commit` 의 짧은 옵션 가운데 값을 받는 것. 값은 붙여 쓰거나 다음 낱말이다.
_SHORT_WITH_VALUE = frozenset("mcCtF")
# 값을 붙여서만 받는 짧은 옵션(`-S[<keyid>]`, `-u[<mode>]`). 그 뒤의 글자는 값이다.
_SHORT_WITH_ATTACHED = frozenset("Su")
# 이 짧은 옵션이 있으면 보지 않는다(독스트링). `-n` 은 `--no-verify`, `-e` 는 `--edit`, `-h` 는
# 도움말이다.
_SHORT_UNJUDGED = frozenset("neh")
_LONG_UNJUDGED = frozenset(
    {"--no-verify", "--edit", "--squash", "--fixup", "--cleanup", "--dry-run", "--help"}
)
# here-string `<<<` 은 heredoc 이 아니다. tools/hook_bash_cd_outside.py 와 같은 모양이다.
_HEREDOC_OPENER = re.compile(r"(?<!<)<<(?!<)(-?)\s*\\?(['\"]?)([^\s;&|<>()'\"\\]+)\2")
# 값을 다음 낱말로 받는 긴 옵션. 값을 받아도 `_LONG_UNJUDGED` 에 든 것(`--fixup` 등)은 거기서 먼저
# 판정을 접으므로 여기 두지 않는다.
_LONG_WITH_VALUE = frozenset(
    {
        "--message",
        "--reuse-message",
        "--reedit-message",
        "--author",
        "--date",
        "--template",
        "--trailer",
        "--pathspec-from-file",
    }
)
_DIRECTORY_CHANGERS = frozenset({"cd", "pushd", "popd"})
_UNRESOLVABLE = re.compile(r"[$`*?\[]")
_MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")
_DRIVE_ONLY = re.compile(r"^[A-Za-z]:$")
_ABSOLUTE = re.compile(r"^(?:/|[A-Za-z]:/)")


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput
    cwd: str


class MessageFile(NamedTuple):
    """커밋 하나의 메시지 파일 인자와 그 커밋의 `git -C` 폴더(없으면 빈 문자열)."""

    directory: str
    file: str


def message_files(command: str) -> list[MessageFile]:
    """판정할 `git commit` 마다 마지막 `-F`·`--file` 의 파일 인자. 보지 않는 커밋은 뺀다."""
    # 줄 끝 역슬래시는 줄을 잇는다. 그대로 두면 shlex 가 이스케이프된 줄바꿈을 값으로 읽는다.
    source = "\n".join(_without_heredoc_bodies(command.replace("\\\n", " ")))
    lexer = shlex.shlex(source, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    commands: list[list[str]] = [[]]
    for token in tokens:
        if _CONTROL.match(token) is None:
            commands[-1].append(token)
        elif commands[-1]:
            commands.append([])
    found: list[MessageFile] = []
    for index, words in enumerate(commands):
        message = _commit_message(words)
        if message is None:
            continue
        # 커밋보다 앞의 명령만 본다. 뒤의 명령(`&& rm <파일>`)은 커밋이 읽는 내용을 바꾸지 않는다.
        before = commands[:index]
        if any(other and other[0] in _DIRECTORY_CHANGERS for other in before):
            continue
        if any(_skips_commit_msg(other) for other in before):
            continue
        written = _same_path(message.file)
        if any(_same_path(word) == written for other in before for word in other):
            continue
        found.append(message)
    return found


def _same_path(word: str) -> str:
    """같은 파일을 가리키는 철자(`./m.txt`, `m.txt`, `/c/x`, `C:\\x`)를 하나로 고른다."""
    return posixpath.normpath(_native(word))


def _skips_commit_msg(words: list[str]) -> bool:
    """`SKIP=…commit-msg…` 만 대입하거나 `export` 하는 명령인가. 그 뒤의 커밋은 commit-msg 를
    건너뛴다."""
    names = words[1:] if words and words[0] == "export" else words
    return (
        bool(names)
        and all(_ASSIGNMENT.match(word) for word in names)
        and any(_is_skip_commit_msg(word) for word in names)
    )


def _is_skip_commit_msg(word: str) -> bool:
    name, _, value = word.partition("=")
    return name == "SKIP" and "commit-msg" in value.split(",")


def _without_heredoc_bodies(command: str) -> list[str]:
    """heredoc 본문 줄을 비운다. 본문의 `git commit …` 은 명령이 아니고, 본문의 작은따옴표는
    shlex 가 거절한다."""
    lines = command.split("\n")
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
            body = lines[index]
            index += 1
            if (body.lstrip("\t") if strips_tabs else body) == terminator:
                kept.append(body)
                break
            kept.append("")
    return kept


def _commit_message(words: list[str]) -> MessageFile | None:
    index = 0
    while index < len(words) and _ASSIGNMENT.match(words[index]):
        if _is_skip_commit_msg(words[index]):
            return None
        index += 1
    if index >= len(words) or words[index] != "git":
        return None
    index += 1
    directory = ""
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        index += 1
        if option in _GLOBAL_WITH_VALUE and index < len(words):
            if option == "-C":
                directory = posixpath.join(directory, words[index]) if directory else words[index]
            # 훅 폴더를 바꾸면 commit-msg 훅이 돌지 않을 수 있다.
            if option == "-c" and words[index].lower().startswith("core.hookspath="):
                return None
            index += 1
    if index >= len(words) or words[index] != "commit":
        return None
    file = _last_file_argument(words[index + 1 :])
    if file is None or file == "-":
        return None
    return MessageFile(directory, file)


def _last_file_argument(arguments: list[str]) -> str | None:
    """마지막 `-F` 의 값. 없거나 보지 않는 커밋(`_SHORT_UNJUDGED`, `_LONG_UNJUDGED`)이면 None."""
    file: str | None = None
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if word == "--":
            break
        if word.startswith("--"):
            name, has_value, value = word.partition("=")
            if name in _LONG_UNJUDGED:
                return None
            if name == "--file":
                if has_value:
                    file = value
                elif index < len(arguments):
                    file = arguments[index]
                    index += 1
            elif name in _LONG_WITH_VALUE and not has_value:
                index += 1
            continue
        if not word.startswith("-") or word == "-":
            continue
        for position, flag in enumerate(word[1:], start=1):
            if flag in _SHORT_UNJUDGED:
                return None
            if flag in _SHORT_WITH_ATTACHED:
                break
            if flag in _SHORT_WITH_VALUE:
                value = word[position + 1 :]
                if not value and index < len(arguments):
                    value = arguments[index]
                    index += 1
                if flag == "F" and value:
                    file = value
                break
    return file


def _native(path: str) -> str:
    """Git Bash 의 `/c/…` 를 `C:/…` 로, 역슬래시를 슬래시로."""
    text = path.replace("\\", "/")
    msys = _MSYS_DRIVE.match(text)
    return f"{msys.group(1).upper()}:{text[2:]}" if msys else text


def resolve(path: str, cwd: str, home: str) -> str | None:
    """인자를 `cwd` 에서 푼 경로. 변수·치환·글롭이 들었으면 None."""
    if _UNRESOLVABLE.search(path):
        return None
    if path == "~" or path.startswith("~/"):
        return posixpath.normpath(f"{_native(home)}/{path[2:]}")
    text = _native(path)
    if _ABSOLUTE.match(text):
        return posixpath.normpath(text)
    return posixpath.normpath(f"{_native(cwd)}/{text}")


def _canonical(path: str) -> str:
    """견주려고 고른 경로. 심볼릭 링크와 윈도의 짧은 이름, 대소문자를 푼다."""
    return os.path.normcase(os.path.realpath(path))


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _common_dir(checkout: str) -> str | None:
    """`checkout` 의 공통 git 폴더. `.git` 이 폴더면 그것, 파일이면 `gitdir:` 이 가리키는 폴더의
    `commondir`(없으면 그 폴더)다. 읽지 못하면 None."""
    dot_git = os.path.join(checkout, ".git")
    if os.path.isdir(dot_git):
        return dot_git
    text = _read(dot_git)
    if text is None or not text.startswith("gitdir:"):
        return None
    gitdir = os.path.join(checkout, text.removeprefix("gitdir:").strip())
    common = _read(os.path.join(gitdir, "commondir"))
    return gitdir if common is None else os.path.join(gitdir, common)


def repository_roots(checkout: str) -> frozenset[str]:
    """`checkout` 이 든 저장소의 체크아웃들(그 자신, 주 체크아웃, 등록된 워크트리). `_canonical` 로
    고른 경로이고, `checkout` 의 `.git` 을 읽지 못하면 빈다."""
    common = _common_dir(checkout)
    if common is None:
        return frozenset()
    common = os.path.normpath(common)
    roots = [checkout]
    if os.path.basename(common) == ".git":
        roots.append(os.path.dirname(common))
    admin = os.path.join(common, "worktrees")
    try:
        names = os.listdir(admin)
    except OSError:
        names = []
    for name in names:
        worktree = _linked_worktree(os.path.join(admin, name))
        if worktree is not None:
            roots.append(worktree)
    return frozenset(_canonical(root) for root in roots)


def _linked_worktree(entry: str) -> str | None:
    """등록 `entry`(`worktrees/<이름>`)의 워크트리 폴더. 그 폴더의 `.git` 파일이 다시 이 등록을
    가리킬 때만이다. 워크트리 폴더를 git 없이 지우면 등록이 남아, 같은 자리에 새로 만든 저장소를 이
    저장소로 읽는다(PR 직전 버그 축)."""
    target = _read(os.path.join(entry, "gitdir"))
    if not target:
        return None
    dot_git = os.path.join(entry, target)
    back = _read(dot_git)
    if back is None or not back.startswith("gitdir:"):
        return None
    linked = os.path.join(os.path.dirname(dot_git), back.removeprefix("gitdir:").strip())
    return os.path.dirname(dot_git) if _canonical(linked) == _canonical(entry) else None


def ancestors(directory: str) -> list[str]:
    """`directory` 와 그 조상들, 가까운 것부터. 드라이브 문자만 남은 자리는 `C:/` 로 맞춘다.
    `C:` 는 윈도에서 현재 폴더 기준이라, 그대로 두면 존재 확인과 판정 스크립트(`C:/…`)는 드라이브
    루트를, 경계 판정과 설정 읽기는 현재 폴더를 본다(PR 직전 보안 리뷰)."""
    parts = directory.rstrip("/").split("/")
    found: list[str] = []
    for end in range(len(parts), 0, -1):
        root = "/".join(parts[:end]) or "/"
        found.append(f"{root}/" if _DRIVE_ONLY.match(root) else root)
    return found


def checker_for(directory: str, *, own: str) -> str | None:
    """`directory` 에서 커밋하면 commit-msg 단계가 돌릴 판정 스크립트. 그 저장소가 `own`(이 훅이
    든 체크아웃)의 저장소가 아니거나, 그 저장소의 pre-commit 설정이 그것을 부르지 않거나 파일이
    없으면 None."""
    for root in ancestors(directory):
        if not os.path.exists(posixpath.join(root, ".git")):
            continue
        if _canonical(root) not in repository_roots(own):
            return None
        checker = posixpath.join(root, CHECKER)
        try:
            config = Path(root, PRE_COMMIT_CONFIG).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        return checker if CHECKER in config and os.path.isfile(checker) else None
    return None


def problems_of(path: str, checker: str, timeout: float = CHECK_TIMEOUT) -> list[str]:
    """`checker` 가 그 파일에 내는 문장들. 통과하거나 판정 문장 없이 끝나거나 `timeout` 초를
    넘기면 빈다."""
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            [sys.executable, checker, path],
            capture_output=True,
            env=environment,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 1:
        return []
    return result.stdout.decode("utf-8", "replace").splitlines()


def deny_reason(command: str, cwd: str, home: str, *, own: str) -> str | None:
    """판정할 커밋의 메시지 파일이 그 저장소의 commit-msg 판정에 걸리면 막는 이유, 아니면 None.
    `own` 은 이 훅이 든 체크아웃이고, 그 저장소 밖의 커밋은 판정하지 않는다."""
    if "commit" not in command:
        return None
    for message in message_files(command):
        directory = resolve(message.directory or ".", cwd, home)
        path = None if directory is None else resolve(message.file, directory, home)
        if directory is None or path is None or not os.path.isfile(path):
            continue
        checker = checker_for(directory, own=own)
        problems = [] if checker is None else problems_of(path, checker)
        if problems:
            return (
                f"커밋 메시지 파일 `{message.file}` 이 commit-msg 훅({CHECKER})의 판정에"
                f" 걸린다: {' / '.join(problems)}. 이대로 치면 pre-commit 단계의 검사(몇 분)를"
                " 모두 돈 뒤 commit-msg 단계에서 막혀 게이트를 한 번 더 돈다(대기열 222)."
                " 파일의 제목을 고치고 다시 친다."
            )
    return None


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    cwd = payload.get("cwd")
    if command is None or cwd is None:
        return 0
    reason = deny_reason(command, cwd, str(Path.home()), own=HOOK_CHECKOUT)
    if reason is None:
        return 0
    output = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
    sys.stdout.buffer.write(json.dumps({"hookSpecificOutput": output}).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
