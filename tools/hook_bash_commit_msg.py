"""PreToolUse 훅(Bash). `git commit` 의 메시지(`-F <파일>`, `-m`, `-F -` 로 넘기는 heredoc)를 그
저장소의 commit-msg 판정으로 먼저 대 보고, 걸리면 커밋을 막는다.

막는 대상은 실수로 내는 길(commit-msg 가 거절할 메시지로 하는 커밋)이다. 일부러 하는
우회(`--no-verify`, `SKIP`, `git` 을 다른 이름으로 부르기)는 막지 않는다 — 막는 자리를 앞당길
뿐이라 commit-msg 단계가 그대로 판정하거나 건너뛴다. 아래 못 보는 것에 든다.

커밋 메시지 형식(제목 72자 등)은 pre-commit 의 commit-msg 단계(`tools/check_commit_msg.py`)가
판정한다. 그 단계는 pre-commit 단계의 검사가 모두 끝난 뒤라, 제목 하나 때문에 약 7~8분의 게이트를
한 번 더 돌았다. 세 번(일지 2026-10-13-06 의 484초, 2026-10-13-12·2026-10-13-30 의 약 7분)
있었다(대기열 222). 첫 버전은 `-F <파일>` 만 봐서 `-m`(제목 72자 초과로 6.5~17분), `cd <폴더> &&`
로 시작하는 복합 명령, `-F -` 가 훅을 지나가 같은 사건이 아홉 번째까지 났다(대기열 항목
`commit-msg-after-slow-checks`, harness 티켓 `commit-title-check-before-slow-checks`).
대기열 항목은 "알린다"였지만 막는다. PreToolUse 의 additionalContext 는 도구 결과 옆에 들어가고
Claude 는 그것을 다음 모델 요청에서 읽는다(공식 hooks 문서, 2026-10-13 내려받아 글자 그대로 대
봤다: "next to the tool result", "Claude reads the reminder on the next model request"). 커밋이
게이트를 다 돈 뒤에야 모델이 알림을 보니 되풀이를 줄이지 못한다.

막는 것은 commit-msg 훅이 같은 메시지를 거절할 커밋으로 좁힌다. 막는 훅은 지침으로 적은 뒤에도
어겨진 것이 확인된 뒤에만 더한다는 규약(.claude/rules/tools.md)을 이 훅은 새 금지로 읽지 않는다 —
막는 자리를 앞당길 뿐이어야 한다. 그래서 git 이 그 메시지를 그대로 쓰지 않거나 commit-msg
판정이 돌지 않을 수 있는 커밋은 보지 않는다. `--no-verify`·`-n`, 커밋 앞의 대입이나 앞 명령의
`export` 로 준 `SKIP=…commit-msg…`, `git -c core.hooksPath=…`·`git --config-env=core.hooksPath=…`
(훅을 건너뛰거나 바꾼다), `-e`·`--edit`(편집 뒤의 메시지가 판정된다), `--squash`·`--fixup`(git 이
제목에 접두를 붙여 통과 접두에 든다), `--cleanup`(정리 방식에 따라 판정이 보는 첫 줄이 달라진다),
`--dry-run`·`--help`·`-h`(커밋하지 않는다), 이 긴 옵션들의 줄임(`--no-verif`, `--dry`, `--squ=HEAD`.
git 2.32.0.windows.2 가 받아들이는 것을 손으로 봤고, 세 글자 이상이 어느 한 이름의 앞부분이면 같은
옵션으로 본다), `-m` 을 `-F`·`-C`·`-c` 와 함께 쓴 것(git 이 "Option -m cannot be combined with
-c/-C/-F" 로 끝낸다. git 2.32.0.windows.2 에서 손으로 봤다),
`-C`·`-c`·`--reuse-message`·`--reedit-message` (다른 커밋의 메시지다), 커밋 앞의 단순 명령에 그 파일
인자가 나오는 것(먼저 쓰는 파일이라 PreToolUse 에서는 없거나 옛 내용이다. `./m.txt` 와 `m.txt` 처럼
철자가 달라도 같은 경로면 같다고 본다. 커밋 뒤의 `&& rm <파일>` 은 커밋이 읽는 내용을 바꾸지 않아
보지 않는다), 이동한 곳을 알 수 없는 `cd`·`pushd`·`popd`(아래)다. `-F` 가 여럿이면 git 처럼 마지막
것만 본다. `-m` 이 여럿이면 git 처럼 빈 줄 하나로 이은 글을 본다(같은 git 에서 손으로 봤다). 판정
스크립트는 커밋하는 저장소의 것이다. 커밋 폴더(`cwd` 와 `git -C`)의 가장 가까운 `.git` 조상이 그
루트이고, 그 루트가 이 훅의 저장소(아래 신뢰 경계)에 들고, 루트의 `.pre-commit-config.yaml` 이
`tools/check_commit_msg.py` 를 부르고 그 파일이 있을 때만 판정한다. 메시지 파일이 어디 있는지는
가르지 않는다(스크래치패드의 파일로 이 저장소에서 커밋해도 판정한다). 판정은 옮겨 적지 않고 그
스크립트를 자식 프로세스로 띄워 받는다. 명령에서 읽은 글(`-m`, 표준 입력)은 임시 파일에 써서 같은
스크립트에 파일로 넘기고 끝나면 지운다. 같은 판정이 정의로 서고, 훅끼리 import 하지 않는
규약(.claude/rules/tools.md)도 지킨다. 워크트리 세션에서는 훅 파일이 주 체크아웃의 것이어도 판정은
그 워크트리의 스크립트가 한다.

찾는 것. 명령을 shlex 로 낱말로 나누고 제어 연산자(`&&`, `;`, `|`, 줄바꿈 등)에서 가른 단순
명령마다, 앞의 변수 대입을 벗긴 첫 낱말이 `git` 이고 전역 옵션 뒤의 하위 명령이 `commit` 이면 그
인자에서 `-F <파일>`·`-F<파일>`·`--file <파일>`·`--file=<파일>`·묶은 짧은 옵션(`-aF <파일>`)과
`-m <글>`·`-m<글>`·`--message <글>`·`--message=<글>`·`-am <글>` 을 찾는다. 값을 받는 다른
옵션(`-t`, `--author` 등)의 값은 건너뛰고, `--` 뒤는 보지 않는다. 줄 끝 역슬래시로 이은 줄은 한 줄로
보고, heredoc 본문 줄은 비운다(본문의 `git commit` 은 명령이 아니다). 파일은 커밋 폴더에서 풀고, `~`
와 Git Bash 의 `/c/…` 표기를 받는다.

메시지를 명령에서 읽는 길 둘. 첫째 `-F -` 는 같은 줄에서 연 heredoc 이 하나일 때 그 본문이 메시지다
(`git commit -F - <<'EOF'`, `cat <<'EOF' | git commit -F -`). 구분자에 따옴표나 역슬래시가 붙지
않은 heredoc 은 본문에 `$`·백틱·역슬래시가 없을 때만 본다. 둘째 `-m` 값 하나가 통째로
`$(cat <<'EOF' … EOF)` 이면(에이전트가 커밋할 때 흔한 꼴) 그 줄에서 연 heredoc 본문이 값이다. 이
꼴은 구분자에 따옴표가 붙은 heredoc 만 본다.

커밋 폴더. 커밋보다 앞의 `cd <경로>`·`pushd <경로>` 를 `&&`·`;`·줄바꿈으로 이은 것만 믿고 그
폴더에서 `git -C` 와 파일 경로를 푼다(절대 경로 이동은 앞의 이동을 덮는다). 이동한 곳을 알 수 없으면
보지 않는다: `cd -`, 인자가 없거나 둘 이상, 변수·글롭이 든 경로, `cd ~user`(`~` 와 `~/…` 만 푼다),
`pushd +1`, `popd`, `||`·`|`·`&`·괄호·리다이렉트에 얽힌 이동, `{ cd x; …; }`·`then cd x`·
`do cd x`·`! cd x` 처럼 예약어 바로 뒤의 이동(그 이동이 어디까지 미치는지 모른다).

못 보는 것(모두 지나간다): 위에서 보지 않는다고 적은 커밋, `-F -` 의 메시지를 다른 명령이 만드는 것
(`echo … | git commit -F -`, `<<<`), 표준 입력을 파일에서 받는 `git commit -F - < m.txt`, 같은 줄에
heredoc 이 둘이거나 본문이 풀리는 heredoc(같은 줄의 다른 명령이 연 heredoc 을 `-F -` 의 입력으로
오해하는 나머지 꼴도 여기 든다), 변수·치환이 든 `-m` 값(`-m "$TITLE"`, `-m "$(make_title)"`. shlex
가 따옴표 종류를 지워 작은따옴표 안의 `$` 도 같이 지나간다), `-m` 의 따옴표 안에 `<< 낱말` 이 든
커밋(그 줄을 heredoc 이 여는 줄로 읽어 뒤를 삼키므로 그 커밋도 못 본다), 변수·치환이 든 경로,
shlex 가 거절하는 명령(짝 없는
따옴표), `git` 을 다른 이름으로 부르는 것(`command git`, `env … git`, 전체 경로), `GIT_DIR=`·
`--git-dir`·`--work-tree` 로 다른 저장소에 하는 커밋(커밋 폴더의 저장소로 판정한다. `-F` 길에도 있던
사각이다). 자식이 시간
제한(10초)을 넘기거나 판정 문장 없이 끝나도 지나간다. 앞 호출에서 `export` 한 `SKIP` 은 모른다 — 그
셸에서 커밋하면 commit-msg 훅이 돌지 않는데도 막는다(거짓 양성). 이 훅의 저장소 밖에서 하는
커밋(다른 프로젝트, 이 체크아웃 안에 든 중첩 저장소)과, 이 훅이 든 체크아웃의 `.git` 을 읽지 못해 이
훅의 저장소를 모를 때의 커밋은 그 저장소에 commit-msg 판정이 있어도 판정하지 않는다.
`--separate-git-dir` 로 만든 저장소의 워크트리에 이 훅이 들면 주 체크아웃의 커밋도 밖으로 본다(공통
폴더의 이름이 `.git` 이 아니라 그 부모를 주 체크아웃으로 세지 않는다 — 거짓 음성).

판정 스크립트를 실행하는 신뢰 경계. 판정 스크립트는 이 훅의 저장소의 것만 띄운다. 이 훅은 권한
확인 전에 돌아, 띄우는 스크립트는 사용자가 그 Bash 명령을 승인하기 전에 돈다. 첫 버전은 커밋하는
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
import tempfile
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
_GLOBAL_WITH_VALUE = frozenset(
    {"-C", "-c", "--config-env", "--git-dir", "--work-tree", "--namespace"}
)
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
        "--author",
        "--date",
        "--template",
        "--trailer",
        "--pathspec-from-file",
    }
)
# 다른 커밋의 메시지를 쓰는 긴 옵션. `-m`·`-F` 와 함께 쓰면 git 이 오류로 끝낸다.
_LONG_REUSE = frozenset({"--reuse-message", "--reedit-message"})
_DIRECTORY_CHANGERS = frozenset({"cd", "pushd", "popd"})
# 이동 앞에 붙어 그 이동이 미치는 범위를 모르게 만드는 셸 예약어.
_SHELL_KEYWORDS = frozenset(
    {"{", "!", "if", "then", "elif", "else", "while", "until", "do", "time"}
)
# 앞 명령이 끝난 뒤에 도는 연결(제어 연산자에서 줄바꿈을 뺀 것). `||`·`|`·`&`·괄호는 뒤의 명령이
# 같은 폴더에서 돈다고 할 수 없다.
_SEQUENTIAL = frozenset({"", "&&", ";"})
# 실행 때 값이 정해지는 글(변수, 명령 치환). shlex 가 따옴표 종류를 지워 작은따옴표 안의 `$` 도
# 든다.
_EXPANDS = re.compile(r"[$`]")
# 따옴표 없는 heredoc 의 본문에서 셸이 푸는 것.
_HEREDOC_EXPANDS = re.compile(r"[$`\\]")
# 구분자에 역슬래시를 붙인 heredoc(`<<\EOF`)도 따옴표를 붙인 것처럼 본문을 풀지 않는다.
_ESCAPED_DELIMITER = re.compile(r"<<-?\s*\\")
# `-m` 값 하나가 통째로 `$(cat <<'EOF' … EOF)` 인 모양. 본문 줄은 `_split_heredocs` 가 비운 뒤다.
_CAT_HEREDOC = re.compile(r"\A\$\(\s*cat\s+<<-?\s*\\?(['\"]?)(\w+)\1\s*\n+\2\s*\)\Z")
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


class CommitMessage(NamedTuple):
    """커밋 하나의 메시지 출처. `file` 은 `-F` 의 파일 인자, `text` 는 명령에서 읽은 글(`-m`,
    표준 입력 heredoc)이고 둘 중 하나만 든다. `directory` 는 커밋 폴더를 훅의 `cwd` 에서 푸는
    상대 경로(앞선 `cd` 와 `git -C` 를 이은 것)다."""

    directory: str
    file: str | None
    text: str | None


class _Heredoc(NamedTuple):
    """한 줄에서 연 heredoc 하나. `literal` 은 본문을 셸이 풀지 않고 글자 그대로 쓰는가(구분자에
    따옴표나 역슬래시가 붙었다)."""

    literal: bool
    body: str


class _SimpleCommand(NamedTuple):
    """제어 연산자로 가른 단순 명령 하나. `lines` 는 낱말마다 시작 줄, `before` 는 이 명령 바로
    앞의 제어 연산자들(없으면 빈 문자열)이다."""

    words: list[str]
    lines: list[int]
    before: str


class _Arguments(NamedTuple):
    """`git commit` 인자에서 읽은 메시지 관련 값. `values` 는 `-m` 의 값과 그 줄, `reuses` 는 `-C`·
    `-c` 처럼 다른 커밋의 메시지를 쓰는가."""

    file: str | None
    file_line: int
    values: list[tuple[str, int]]
    reuses: bool


def commit_messages(command: str) -> list[CommitMessage]:
    """판정할 `git commit` 마다 메시지의 출처. 보지 않는 커밋은 뺀다."""
    commands, bodies = _simple_commands(command)
    found: list[CommitMessage] = []
    # 앞선 `cd` 가 정한 폴더. None 이면 어디인지 모른다.
    workdir: str | None = ""
    for index, simple in enumerate(commands):
        if simple.words[0] in _DIRECTORY_CHANGERS:
            workdir = _after_move(workdir, commands, index)
            continue
        if (
            simple.words[0] in _SHELL_KEYWORDS
            and simple.words[1:2]
            and (simple.words[1] in _DIRECTORY_CHANGERS)
        ):
            # `{ cd x; …; }`, `if …; then cd x; fi` 의 이동은 어디까지 미치는지 모른다.
            workdir = None
            continue
        following = commands[index + 1].before if index + 1 < len(commands) else ""
        message = _commit_message(simple, bodies, following)
        if message is None or workdir is None:
            continue
        # 커밋보다 앞의 명령만 본다. 뒤의 명령(`&& rm <파일>`)은 커밋이 읽는 내용을 바꾸지 않는다.
        before = commands[:index]
        if any(_skips_commit_msg(other.words) for other in before):
            continue
        if message.file is not None:
            written = _same_path(message.file)
            if any(_same_path(word) == written for other in before for word in other.words):
                continue
        found.append(message._replace(directory=_join_dir(workdir, message.directory)))
    return found


def _simple_commands(command: str) -> tuple[list[_SimpleCommand], dict[int, list[_Heredoc]]]:
    """명령을 shlex 로 낱말로 나누고 제어 연산자에서 가른 단순 명령들과, 줄마다 그 줄에서 연
    heredoc 들. shlex 가 거절하는 명령(짝 없는 따옴표)이면 둘 다 빈다."""
    kept, bodies = _split_heredocs(command)
    lexer = shlex.shlex("\n".join(kept), posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return [], {}
    commands: list[_SimpleCommand] = []
    words: list[str] = []
    lines: list[int] = []
    before = ""
    line = 0
    for token in tokens:
        if _CONTROL.match(token) is None:
            words.append(token)
            lines.append(line)
        else:
            if words:
                commands.append(_SimpleCommand(words, lines, before))
                words, lines, before = [], [], ""
            before += token
        line += token.count("\n")
    if words:
        commands.append(_SimpleCommand(words, lines, before))
    return commands, bodies


def _after_move(workdir: str | None, commands: list[_SimpleCommand], index: int) -> str | None:
    """`commands[index]`(`cd`·`pushd`·`popd`) 뒤의 폴더. 알 수 없으면 None. 이동은
    `&&`·`;`·줄바꿈으로 이은 단순 `cd <경로>` 일 때만 믿는다. `||`·`|`·`&`·괄호의 이동은 뒤의 커밋이
    그 폴더에서 돈다고 할 수 없다."""
    simple = commands[index]
    last = index + 1 == len(commands)
    if not _is_sequential(simple.before) or not (
        last or _is_sequential(commands[index + 1].before)
    ):
        return None
    arguments = simple.words[1:]
    if simple.words[0] == "popd" or len(arguments) != 1:
        return None
    target = arguments[0]
    # `cd -`, `pushd +1` 은 스택을 따르고, `~user` 는 `resolve` 가 풀지 못한다.
    if target.startswith(("-", "+")) or _UNRESOLVABLE.search(target) or _is_other_home(target):
        return None
    if _is_absolute_directory(target):
        return target
    return None if workdir is None else _join_dir(workdir, target)


def _is_sequential(operators: str) -> bool:
    """앞 명령이 끝난 뒤에 이 명령이 도는 연결(`&&`, `;`, 줄바꿈)인가."""
    return operators.replace("\n", "") in _SEQUENTIAL


def _is_absolute_directory(path: str) -> bool:
    text = _native(path)
    return text == "~" or text.startswith("~/") or _ABSOLUTE.match(text) is not None


def _is_other_home(path: str) -> bool:
    """`~user/x` 꼴인가. 홈 폴더 `~` 와 `~/x` 만 `resolve` 가 푼다."""
    return path.startswith("~") and path != "~" and not path.startswith("~/")


def _join_dir(base: str, new: str) -> str:
    """`base` 에서 `new` 로 옮긴 폴더. `new` 가 절대 경로(와 `~`)면 `new` 다."""
    if not base or _is_absolute_directory(new):
        return new
    return posixpath.join(base, new) if new else base


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


def _split_heredocs(command: str) -> tuple[list[str], dict[int, list[_Heredoc]]]:
    """heredoc 본문 줄을 비운 줄들과, 줄 번호마다 그 줄에서 연 heredoc 들. 본문의 `git commit …`
    은 명령이 아니고, 본문의 작은따옴표는 shlex 가 거절한다."""
    lines = command.split("\n")
    kept: list[str] = []
    heredocs: dict[int, list[_Heredoc]] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        # 줄 끝 역슬래시는 줄을 잇는다. 그대로 두면 shlex 가 이스케이프된 줄바꿈을 값으로 읽는다.
        # heredoc 본문 줄은 이 반복이 아니라 아래 안쪽 반복이 읽어, 본문의 역슬래시는 그대로 둔다.
        while line.endswith("\\") and index < len(lines):
            line = f"{line[:-1]} {lines[index]}"
            index += 1
        opened = len(kept)
        kept.append(line)
        for opener in _HEREDOC_OPENER.finditer(line):
            strips_tabs = opener.group(1) == "-"
            terminator = opener.group(3)
            literal = (
                opener.group(2) != "" or _ESCAPED_DELIMITER.search(opener.group(0)) is not None
            )
            body: list[str] = []
            while index < len(lines):
                text = lines[index]
                index += 1
                if (text.lstrip("\t") if strips_tabs else text) == terminator:
                    kept.append(text)
                    break
                kept.append("")
                body.append(text.lstrip("\t") if strips_tabs else text)
            heredocs.setdefault(opened, []).append(
                _Heredoc(literal, "".join(f"{b}\n" for b in body))
            )
    return kept, heredocs


def _commit_message(
    simple: _SimpleCommand, bodies: dict[int, list[_Heredoc]], following: str
) -> CommitMessage | None:
    """`simple` 이 판정할 `git commit` 이면 그 메시지의 출처. `following` 은 바로 뒤 명령 앞의 제어
    연산자다(`-F -` 의 입력이 `<` 로 파일에서 오는지 본다)."""
    words = simple.words
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
                directory = _join_dir(directory, words[index])
            # 훅 폴더를 바꾸면 commit-msg 훅이 돌지 않을 수 있다.
            if option in ("-c", "--config-env") and words[index].lower().startswith(
                "core.hookspath="
            ):
                return None
            index += 1
        elif option.lower().startswith("--config-env=core.hookspath="):
            return None
    if index >= len(words) or words[index] != "commit":
        return None
    scan = _scan_arguments(words[index + 1 :], simple.lines[index + 1 :])
    # `-m` 은 `-F`·`-C`·`-c` 와 함께 쓰면 git 이 오류로 끝낸다. `-C`·`-c` 의 메시지는 다른 커밋의
    # 것이다.
    if scan is None or scan.reuses or (scan.values and scan.file is not None):
        return None
    if scan.values:
        text = _joined_values(scan.values, bodies)
        return None if text is None else CommitMessage(directory, None, text)
    if scan.file is None:
        return None
    if scan.file == "-":
        if following.replace("\n", "") == "<":
            # `git commit -F - < msg.txt`: 입력이 heredoc 이 아니라 파일이다.
            return None
        text = _stdin_text(bodies.get(scan.file_line, []))
        return None if text is None else CommitMessage(directory, None, text)
    return CommitMessage(directory, scan.file, None)


def _joined_values(values: list[tuple[str, int]], bodies: dict[int, list[_Heredoc]]) -> str | None:
    """`-m` 값들을 git 처럼 빈 줄 하나로 이은 글. 값이 실행 때 정해지면(변수, 치환) None 이다. 값
    하나가 통째로 `$(cat <<'EOF' … EOF)` 이면 그 줄에서 연 heredoc 본문이 값이다."""
    parts: list[str] = []
    for value, line in values:
        if _EXPANDS.search(value) is None:
            parts.append(value)
            continue
        docs = bodies.get(line, [])
        if _CAT_HEREDOC.match(value) is None or len(docs) != 1 or not docs[0].literal:
            return None
        # `$(…)` 는 끝의 줄바꿈을 지운다.
        parts.append(docs[0].body.rstrip("\n"))
    text = "\n\n".join(parts)
    return text if text.strip() else None


def _stdin_text(docs: list[_Heredoc]) -> str | None:
    """`-F -` 로 읽을 표준 입력의 글. 같은 줄의 heredoc 이 하나이고 본문을 셸이 풀지 않을
    때만이다."""
    if len(docs) != 1:
        return None
    doc = docs[0]
    if not doc.literal and _HEREDOC_EXPANDS.search(doc.body):
        return None
    return doc.body


def _is_unjudged_long(name: str) -> bool:
    """`--no-verify` 처럼 판정을 건너뛰거나 바꾸는 긴 옵션이거나 그 줄임인가. git 은 모호하지 않은
    접두(`--no-verif`, `--dry`)도 받는다. 모호한 접두는 git 이 오류로 끝내 커밋이 없으니 어느 쪽으로
    읽어도 같다."""
    return len(name) > 2 and any(full.startswith(name) for full in _LONG_UNJUDGED)


def _scan_arguments(arguments: list[str], lines: list[int]) -> _Arguments | None:
    """`-F`·`--file` 의 마지막 값과 모든 `-m`·`--message` 값. 보지 않는 커밋(`_SHORT_UNJUDGED`,
    `_LONG_UNJUDGED`)이면 None."""
    file: str | None = None
    file_line = 0
    values: list[tuple[str, int]] = []
    reuses = False
    index = 0
    while index < len(arguments):
        word = arguments[index]
        line = lines[index]
        index += 1
        if word == "--":
            break
        if word.startswith("--"):
            name, has_value, value = word.partition("=")
            if _is_unjudged_long(name):
                return None
            if name in ("--file", "--message"):
                if not has_value:
                    if index >= len(arguments):
                        continue
                    value, line = arguments[index], lines[index]
                    index += 1
                if name == "--file":
                    file, file_line = value, line
                else:
                    values.append((value, line))
            elif name in _LONG_REUSE:
                reuses = True
                index += 0 if has_value else 1
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
                    value, line = arguments[index], lines[index]
                    index += 1
                if flag == "F" and value:
                    file, file_line = value, line
                elif flag == "m":
                    values.append((value, line))
                elif flag in "cC":
                    reuses = True
                break
    return _Arguments(file, file_line, values, reuses)


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


def problems_of_text(text: str, checker: str, timeout: float = CHECK_TIMEOUT) -> list[str]:
    """`checker` 가 명령에서 읽은 메시지 글에 내는 문장들. 판정 스크립트는 파일만 받아 임시 파일에
    쓰고 부른다(판정을 옮겨 적지 않는다). 줄바꿈은 그대로 쓴다."""
    try:
        handle, path = tempfile.mkstemp(prefix="commit-msg-", suffix=".txt")
    except OSError:
        return []
    try:
        with os.fdopen(handle, "wb") as written:
            written.write(text.encode("utf-8"))
        return problems_of(path, checker, timeout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _problems(message: CommitMessage, directory: str, home: str, *, own: str) -> list[str]:
    """`message` 가 그 커밋 폴더의 저장소 commit-msg 판정에 내는 문장들."""
    if message.file is not None:
        path = resolve(message.file, directory, home)
        if path is None or not os.path.isfile(path):
            return []
        checker = checker_for(directory, own=own)
        return [] if checker is None else problems_of(path, checker)
    if message.text is None:
        return []
    checker = checker_for(directory, own=own)
    return [] if checker is None else problems_of_text(message.text, checker)


def deny_reason(command: str, cwd: str, home: str, *, own: str) -> str | None:
    """판정할 커밋의 메시지(`-F` 의 파일, `-m`, 표준 입력 heredoc)가 그 저장소의 commit-msg 판정에
    걸리면 막는 이유, 아니면 None. `own` 은 이 훅이 든 체크아웃이고, 그 저장소 밖의 커밋은 판정하지
    않는다."""
    if "commit" not in command:
        return None
    for message in commit_messages(command):
        directory = resolve(message.directory or ".", cwd, home)
        problems = [] if directory is None else _problems(message, directory, home, own=own)
        if problems:
            target = (
                f"커밋 메시지 파일 `{message.file}` 이"
                if message.file is not None
                else "커밋 메시지(`-m` 이나 표준 입력)가"
            )
            fix = "파일의 제목을" if message.file is not None else "제목을"
            return (
                f"{target} commit-msg 훅({CHECKER})의 판정에"
                f" 걸린다: {' / '.join(problems)}. 이대로 치면 pre-commit 단계의 검사(몇 분)를"
                " 모두 돈 뒤 commit-msg 단계에서 막혀 게이트를 한 번 더 돈다(대기열 222)."
                f" {fix} 고치고 다시 친다."
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
