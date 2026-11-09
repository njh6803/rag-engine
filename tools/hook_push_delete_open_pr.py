"""PreToolUse 훅(Bash|PowerShell). 열린 PR 의 머리 브랜치를 원격에서 지우는 `git push` 를 막는다.

막는 대상은 실수로 내는 길(병합과 지우기를 한 번에 보내 병합이 실패해도 지우기가 나가는 것)이다.
일부러 하는 우회(`bash -c "git push …"` 같은 래퍼, 별칭, `gh api -X DELETE` 로 지우기)는 막지 않고
아래 못 보는 것에 든다.

왜. `gh pr merge` 와 `git push origin --delete <브랜치>` 를 한 번에 나란히 보냈다. 병합은 base 보다
뒤처져 실패했는데 지우기는 나가, 머리 브랜치를 잃은 PR 이 닫혔다(대기열 262, 일지 2026-10-15-01).
`next-session` 의 `merge.md` "워크트리에서 병합할 때" 가 병합 뒤에 원격을 정리하라고 순서를 적지만
지침이라 한 번에 보내면 지나간다. 계기(`additionalContext`)만 주는 PreToolUse 훅은 명령을 그대로
돌리므로 막는다(`.claude/rules/tools.md`). 병합이 끝난 PR 은 열린 PR 이 아니라 지나간다.

판정. 명령은 주석(인용 밖 낱말 머리의 `#` 부터 줄 끝)을 뺀 글과 빼지 않은 글을 둘 다 읽어
합친다(이 훅의 주석 판정이 셸의 이스케이프와 인용을 다 따르지 못해 한쪽만 읽으면 지우는 푸시를 숨길
수 있다, `deletions`). 글마다 제어 연산자(`;`·`&&`·`||`·`|`·`&`· 줄바꿈)로 가르고, 조각마다 shlex 로
나눈 낱말에서 리다이렉션(`> 파일`, `2>&1`, `>log`), 환경 대입(`X=1`), 복합문의
예약어(`then`·`do`·`{`·`!` 등)를 벗긴 뒤 `git` 과 그 전역 옵션(`-C <경로>`, `-c <설정>`,
`--no-pager` 등) 다음의 `push` 를 찾는다. 리다이렉션은 셸이 먹어 git 이 보지 못한다. 벗기지 않던 첫
판은 `> C:\\log.txt` 의 대상을 지울 ref 로 읽어 git 이 거절할 푸시로 보고 지나갔다(셀프 리뷰 명세
축). git 이 읽는 그대로 지울 브랜치를 읽는다.
- 지우기 모드. `--delete`, 그 모호하지 않은 머리(`--de`·`--del` 등. git 의 parse-options 가 받는다),
  짧은 옵션 `-d` 와 그것이 든 묶음(`-fd`). 옵션은 refspec 뒤에 와도 된다. 첫 위치 인자가 원격이고
  나머지가 지울 ref 다. `refs/heads/` 는 벗기고, 다른 `refs/`(태그)는 브랜치가 아니라 뺀다.
- 지우기 refspec. 지우기 모드가 아니어도 `:<브랜치>`·`+:<브랜치>` 는 지운다. `:` 만은 맞는 것을 모두
  올리는 것이라 지우기가 아니다.
- 값을 먹는 옵션(`-o`, `--push-option`, `--receive-pack`, `--exec`, `--repo`,
  `--recurse-submodules`)의 값은 위치 인자가 아니다. `=` 로만 값을 받는 옵션(`--signed`,
  `--force-with-lease`)은 다음 낱말을 먹지 않는다. 값을 먹는지는 `git push -h` 가 적는 꼴(띄어 쓴
  `<…>`·`(…)` 이면 먹고 `[=…]` 이면 먹지 않는다)과 같고, 시험이 이 기계의 git 과 대 본다. 첫 판은
  `--recurse-submodules` 를 먹지 않는다고 적어 그 값을 원격으로 읽었다(대기열 296). `--` 뒤는 모두
  위치 인자다.
- 도움말. `-h`(그것이 든 묶음 `-dh` 포함)·`--help`·`--help-all` 이면 git 이 사용법을 내고 끝나
  지우지 않으므로 지나간다. 값을 먹는 옵션의 값(`-o -h`, 묶음에서 `o` 뒤의 글자)은 도움말이 아니다.
  첫 판은 `-h` 를 값 없는 옵션으로 넘겨 도움말을 지우는 푸시로 읽었다(대기열 300).
- 건너뛰는 길. `--dry-run`(머리 줄임, `-n` 과 그것이 든 묶음 포함)이면 지우지 않아 지나간다. 뒤의
  `--no-dry-run`·`--no-delete` 는 앞의 것을 거둔다(git 의 parse-options 는 뒤의 것이 이긴다). 모호한
  긴 옵션 머리(`--d`)는 git 이 거절해 지나간다. 지울 ref 가 없으면 git 이 거절해 지나간다.
그 뒤 지울 브랜치마다 열린 PR 을 찾는다. 원격은 이름으로 준 것만 페이로드의 `cwd` 에서 `git remote
get-url` 로 URL 을 읽는다. URL 이나 경로로 적은 원격은 묻지 않고 지나간다. 명령 글의 주소로 접속하면
권한 판정 전에 그 호스트로 요청이 나가기 때문이다(`_remote_url`, PR 직전 보안 리뷰). github.com 이면
`gh api repos/<owner>/<repo>/pulls?state=open` 의 REST 로 열린 PR 의 머리(이 저장소의 브랜치만.
포크의 같은 이름은 지워도 닫히지 않는다)를 읽는다. 클라우드 세션에서도 REST 는
열린다(`.claude/rules/tools.md`). gh 가 없거나 실패하거나 github.com 이 아니면
`git ls-remote <원격>` 의 `refs/pull/N/head` 가 그 브랜치의 끝과 같고 `refs/pull/N/merge` 가 있는 PR
을 열린 것으로 본다(`tools/sibling_overlap.py` 와 같은 길. 그 도구의 독스트링이 2026-10-07 클라우드
컨테이너에서 손으로 본 것으로, merge ref 는 열린 PR 에만 있었다). git 과 gh 는 저장소를 가리키는
`GIT_*` 를 벗기고 호출마다 시간 제한을 둔다(get-url 3초, gh 7초, ls-remote 7초). 한 명령의 지우는
푸시가 여럿이어도 그 합은 15초를 넘기지 않는다. 남은 시간이 그보다 짧으면 그만큼만 기다리고, 다 쓰면
묻지 않는다. 기동을 더해도 등록의 20초 안이다. 출력은 파이프가 아니라 임시 파일로 받는다. https
원격의 `ls-remote` 가 띄운 손자 프로세스가 파이프를 쥐면 시간 제한에서 끊기지
않는다(`.claude/rules/tools.md`). 넘기거나 실패하면 막지 않는다(fail-open). 원격을 읽지 못하면 푸시
자신도 실패한다. `-` 로 시작하는 원격은 git 에 넘기지 않는다(`open_heads`). 막을 때는 호출 전체가
돌지 않았다고 함께 알린다(같은 호출에 묶은 다른 명령도 돌지 않았다). 안내하는 확인과 닫기는
REST(`gh api`)로 적는다. `gh pr view`· `gh pr close` 는 GraphQL 이라 클라우드 세션에서
막힌다(`.claude/rules/tools.md`).

못 보는 것.
- 래퍼 뒤의 푸시(`bash -c "git push …"`, `env git push`, `sudo`)와 별칭(`git p`), PowerShell 의
  백틱 줄 이어 쓰기(줄바꿈에서 명령이 갈린다).
- 셸이 버리는 자리(PowerShell 블록 주석 `<# … #>`, bash 백틱 치환, 이스케이프로 이 훅의 인용 판정을
  어긋나게 한 꼬리 주석)에 든 독 낱말. 도움말 `-h`, 표에 없는 긴 옵션, 콜론이 든 refspec 이 그
  자리에 있으면 두 글 모두 git 이 지우지 않는다고 보고 지나간다(거짓 음성). 일부러 꾸민 꼴이라 막는
  대상 밖이다. PR 직전 보안 리뷰가 `-h` 로 짚었고, 긴 옵션과 콜론 낱말은 `-h` 를 도움말로 보기
  전부터 같았다.
- git 이 더한 옵션. 긴 옵션 표(`_PUSH_LONG`)는 git 의 옵션 목록을 손으로 옮긴 것이라 git 이 옵션을
  더하면 조용히 낡는다(PR #257 claude-review 넷째 회차). 표에 없는 긴 옵션이 든 지우는 푸시는 git 이
  거절할 푸시로 보고 지나간다(거짓 음성). 짧은 옵션은 표 없이 `-o` 하나만 값을 먹는다고 보므로, git
  이 값을 먹는 짧은 옵션을 더하면 그 값을 원격으로 읽는다. 표를 대 보는 시험은 그 옵션을 아는 git
  에서 돌 때만 빨개진다.
- git 이 거절하는 옵션의 조합. `--delete` 와 `--all`·`--mirror`·`--tags` 를 함께 쓴 푸시를 git 은
  `--delete is incompatible with --all, --mirror and --tags` 로 거절하는데(git 2.32 의 임시
  저장소에서 손으로 봤다), 이 훅은 그 조합을 보지 않고 지우는 푸시로 읽어 열린 PR 의 머리면
  막는다(거짓 양성). git 이 어차피 거절하는 명령이라 막는 값은 이유 문장 하나다.
- `--prune`·`--mirror` 가 지우는 브랜치. 무엇이 지워질지 원격과 로컬을 견줘야 안다.
- git 이 아닌 길의 지우기. `gh api -X DELETE …/git/refs/heads/<브랜치>`, GitHub 웹, MCP 도구.
  `gh pr merge --delete-branch` 는 병합한 뒤에만 지워 대상이 아니다.
- `git -C <다른 저장소> push` 와 `cd <다른 저장소> && git push`. 원격 이름은 페이로드의 `cwd` 에서
  푼다(hook_push_behind_main 과 같은 한계).
- URL 이나 경로로 적은 원격(`git push https://github.com/o/r.git --delete x`). 묻지 않아 그 열린 PR
  을 놓친다.
- 원격을 읽지 못하거나(오프라인) 시간을 넘기는 것, merge ref 가 없는 열린 PR(gh 를 쓰지 못할 때,
  `tools/sibling_overlap.py` 의 못 보는 것). 막지 않는다.
- gh 를 쓰지 못하는 길은 PR 의 머리를 브랜치 이름이 아니라 커밋으로 대 본다. 열린 PR 의 머리와 같은
  커밋을 끝으로 둔 다른 브랜치(새 커밋 없이 딴 브랜치)를 지우면 막는다(거짓 양성).
- 판정 뒤에 PR 이 열리는 것. 지운 뒤 새로 연 PR 은 이 훅과 무관하다.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from typing import NamedTuple, TypedDict

_REPO_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")
URL_TIMEOUT = 3.0
GH_TIMEOUT = 7.0
LS_REMOTE_TIMEOUT = 7.0
# 한 명령의 모든 지우는 푸시가 쓰는 시간의 합. 등록의 20초에서 기동을 뺀 몫이다.
BUDGET = 15.0

_HEREDOC_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
# 명령 자리 앞에 올 수 있는 셸 예약어. `fi`·`done`·`}` 는 `;` 뒤 제 조각이라 여기 없어도 된다.
_RESERVED = frozenset({"if", "then", "else", "elif", "do", "while", "until", "{", "!"})
_GITHUB_URL = re.compile(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
_PULL_REF = re.compile(r"^refs/pull/(\d+)/(head|merge)$")
_GH_JQ = r'.[] | "\(.number)\t\(.head.repo.full_name // "")\t\(.head.ref)"'
# git 전역 옵션 가운데 다음 낱말을 값으로 먹는 것(`git -C <경로> push`).
_GIT_VALUE_OPTIONS = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}
)
# `git push` 의 긴 옵션과 다음 낱말을 값으로 먹는지. 머리 줄임은 이 표에서 모호하지 않을 때만 받는다
# (git 의 parse-options 와 같다). `no-` 꼴은 git 이 스스로 지어 받는 부정이다. git 의 옵션 목록을
# 손으로 옮긴 표라 git 이 옵션을 더하면 낡는다(독스트링의 못 보는 것). 칸은 시험이 이 기계의
# `git push -h` 와 맞춘다.
_PUSH_LONG: dict[str, bool] = {
    "all": False,
    "branches": False,
    "mirror": False,
    "delete": False,
    "tags": False,
    "follow-tags": False,
    "signed": False,
    "atomic": False,
    "push-option": True,
    "receive-pack": True,
    "exec": True,
    "repo": True,
    "force-with-lease": False,
    "force-if-includes": False,
    "force": False,
    "set-upstream": False,
    "thin": False,
    "quiet": False,
    "verbose": False,
    "progress": False,
    # `=` 없이 쓰면 다음 낱말을 값으로 먹는다(git 이 그 낱말을 모드로 읽어 `bad recurse-submodules
    # argument` 를 낸다, 대기열 296). `signed`·`force-with-lease` 는 `=` 로만 받는다
    "recurse-submodules": True,
    "verify": False,
    "ipv4": False,
    "ipv6": False,
    "dry-run": False,
    "porcelain": False,
    "prune": False,
}
_PUSH_LONG_NAMES = (*_PUSH_LONG, *(f"no-{name}" for name in _PUSH_LONG))


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput
    cwd: str


class Deletion(NamedTuple):
    """지우는 푸시 하나. `remote` 는 명령에 적힌 원격(이름이나 URL)이다."""

    remote: str
    branches: tuple[str, ...]


class PushWords(NamedTuple):
    """push 뒤의 낱말을 git 처럼 읽은 것. 지우기·시험 실행 옵션과, 옵션이 아닌 낱말(원격과
    refspec)."""

    delete: bool
    dry_run: bool
    positionals: list[str]


def deletions(command: str) -> list[Deletion]:
    """명령 안의 지우는 `git push` 들. 지우지 않거나 git 이 거절할 푸시는 뺀다.

    주석을 뺀 글과 빼지 않은 글을 둘 다 읽어 합친다. 이 훅의 주석 판정은 셸의 이스케이프와 인용을 다
    따르지 못해, 셸이 명령으로 읽는 자리를 주석으로 버리면 지우는 푸시를 숨길 수 있다(PR 직전 보안
    리뷰가 설정 훅에서 짚은 것과 같은 꼴). 빼지 않은 글만 읽으면 꼬리 주석의 낱말이 지울 ref 로
    들어가, 콜론이 든 주석(`# see: x`)에서 git 이 거절할 푸시로 보고 지나간다."""
    found: list[Deletion] = []
    for text in (command, _without_comments(command)):
        for words in _segments(text):
            push = _push_arguments(words)
            deletion = None if push is None else _deletion(push)
            if deletion is not None and deletion not in found:
                found.append(deletion)
    return found


def _segments(command: str) -> list[list[str]]:
    """제어 연산자로 가른 조각마다의 낱말. heredoc 본문과 리다이렉션은 뺀다.

    shlex 의 주석(`commenters` 의 기본값 `#`)은 끈다. 줄바꿈을 ` ; ` 로 바꾼 뒤라 주석이 글 끝까지
    이어져, 앞 줄의 주석 하나가 뒤의 지우는 푸시를 삼켰다(PR 직전 버그 축). 주석은 부르는 쪽이
    `_without_comments` 로 뺀 글을 따로 넘긴다(`deletions`)."""
    text = "\n".join(_without_heredoc_bodies(command))
    text = re.sub(r"\\\r?\n", " ", text).replace("\n", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.commenters = ""
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = text.split()
    segments: list[list[str]] = [[]]
    skip = False
    for token in tokens:
        if skip:
            skip = False
            continue
        if token and all(char in ";&|()" for char in token):
            segments.append([])
        elif token and all(char in "<>&" for char in token):
            # 리다이렉션 연산자. 앞에 붙은 파일 서술자(`2>`)와 뒤의 대상을 함께 뺀다
            words = segments[-1]
            if words and words[-1].isdigit():
                words.pop()
            skip = True
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _without_comments(text: str) -> str:
    """인용 밖에서 낱말 머리의 `#` 부터 그 줄 끝까지를 뺀다. `${#a}`·`a#b` 처럼 낱말 안의 `#` 는
    둔다."""
    kept: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] in " \t\n;&|()"):
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        kept.append(char)
        index += 1
    return "".join(kept)


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


def _push_arguments(words: list[str]) -> list[str] | None:
    """조각이 `git [전역 옵션] push …` 이면 push 뒤의 낱말, 아니면 None. 앞의 환경 대입과
    복합문의 예약어(`then`·`do`·`{`·`!` 등)는 벗긴다."""
    index = 0
    while index < len(words) and (_ASSIGNMENT.match(words[index]) or words[index] in _RESERVED):
        index += 1
    if index >= len(words) or _command_name(words[index]) != "git":
        return None
    index += 1
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        index += 2 if option in _GIT_VALUE_OPTIONS else 1
    if index >= len(words) or words[index] != "push":
        return None
    return words[index + 1 :]


def _command_name(word: str) -> str:
    name = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name.removesuffix(".exe")


def _long_option(word: str) -> str | None:
    """`--<머리>[=값]` 의 온전한 이름. 표에 없거나 모호하면 None(git 이 거절한다)."""
    head = word[2:].split("=", 1)[0]
    if head in _PUSH_LONG_NAMES:
        return head
    matches = [name for name in _PUSH_LONG_NAMES if name.startswith(head)]
    return matches[0] if len(matches) == 1 else None


def _deletion(args: list[str]) -> Deletion | None:
    """push 뒤의 낱말에서 지울 브랜치. 지우지 않거나 git 이 거절하면 None."""
    words = _push_words(args)
    if words is None:
        return None
    delete, dry_run, positionals = words
    if dry_run or not positionals:
        return None
    remote, refspecs = positionals[0], positionals[1:]
    if delete:
        if not refspecs or any(":" in refspec for refspec in refspecs):
            return None  # git 이 거절한다
        names = [_branch(refspec) for refspec in refspecs]
    else:
        names = [_colon_target(refspec) for refspec in refspecs]
    branches = tuple(name for name in names if name)
    return Deletion(remote, branches) if branches else None


def _push_words(args: list[str]) -> PushWords | None:
    """push 뒤의 낱말을 옵션(긴 이름과 그 줄임, 묶음 `-fd`, 값을 먹는 옵션)과 나머지로 가른다.
    git 이 푸시하지 않으면 None 이다. 거절하는 긴 옵션(표에 없거나 모호한 줄임. `--help` 도 표에
    없다)과 도움말 `-h`(묶음 `-dh` 포함)가 그렇다."""
    delete = dry_run = False
    positionals: list[str] = []
    index = 0
    while index < len(args):
        word = args[index]
        index += 1
        if word == "--":
            positionals += args[index:]
            break
        if word.startswith("--"):
            name = _long_option(word)
            if name is None:
                return None
            # 뒤의 부정이 앞의 것을 거둔다(parse-options 는 뒤의 것이 이긴다)
            delete = {"delete": True, "no-delete": False}.get(name, delete)
            dry_run = {"dry-run": True, "no-dry-run": False}.get(name, dry_run)
            if _PUSH_LONG.get(name) and "=" not in word:
                index += 1
            continue
        if word.startswith("-") and word != "-":
            letters = word[1:]
            for position, letter in enumerate(letters):
                if letter == "o":
                    index += 0 if letters[position + 1 :] else 1
                    break
                if letter == "h":
                    return None  # git 이 사용법을 내고 끝난다(대기열 300)
                delete = delete or letter == "d"
                dry_run = dry_run or letter == "n"
            continue
        positionals.append(word)
    return PushWords(delete, dry_run, positionals)


def _colon_target(refspec: str) -> str | None:
    """지우기 refspec(`:<ref>`·`+:<ref>`)이 지울 브랜치. 아니면 None. `:` 만은 지우기가 아니다."""
    body = refspec.removeprefix("+")
    return _branch(body[1:]) if body.startswith(":") else None


def _branch(ref: str) -> str | None:
    """지울 ref 의 브랜치 이름. 다른 `refs/`(태그)는 None."""
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/") or None
    if ref.startswith("refs/"):
        return None
    return ref or None


def github_repo(url: str) -> tuple[str, str] | None:
    """원격 URL 이 github.com 의 것이면 (owner, repo)."""
    match = _GITHUB_URL.search(url.strip())
    return (match.group(1), match.group(2)) if match else None


def gh_open_heads(listing: str, full_name: str, branches: Sequence[str]) -> dict[str, list[int]]:
    """`gh api` 의 "번호\\t머리 저장소\\t머리 브랜치" 줄에서 이 저장소의 `branches` 를 머리로 둔
    PR."""
    found: dict[str, list[int]] = {}
    for line in listing.splitlines():
        number, _, rest = line.strip("\r").partition("\t")
        repo, _, ref = rest.partition("\t")
        if number.isdigit() and repo.lower() == full_name.lower() and ref in branches:
            found.setdefault(ref, []).append(int(number))
    return found


def refs_open_heads(listing: str, branches: Sequence[str]) -> dict[str, list[int]]:
    """`git ls-remote` 줄에서, merge ref 가 있고 head 가 `branches` 의 끝과 같은 PR."""
    tips: dict[str, str] = {}
    heads: dict[int, str] = {}
    merges: set[int] = set()
    for line in listing.splitlines():
        sha, _, ref = line.strip().partition("\t")
        if ref.startswith("refs/heads/"):
            tips[ref.removeprefix("refs/heads/")] = sha
        elif match := _PULL_REF.match(ref):
            if match.group(2) == "head":
                heads[int(match.group(1))] = sha
            else:
                merges.add(int(match.group(1)))
    found: dict[str, list[int]] = {}
    for branch in branches:
        tip = tips.get(branch)
        numbers = sorted(n for n, sha in heads.items() if sha == tip and n in merges)
        if tip is not None and numbers:
            found[branch] = numbers
    return found


def _environment() -> dict[str, str]:
    """저장소를 가리키는 `GIT_*` 를 벗기고, 자격 증명을 묻느라 멈추지 않게 한다."""
    environment = {k: v for k, v in os.environ.items() if k not in _REPO_LOCATION_VARS}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GH_PROMPT_DISABLED"] = "1"
    return environment


def _run(command: list[str], cwd: str | None, timeout: float, deadline: float) -> str | None:
    """표준 출력. 실패하거나 띄우지 못하거나 시간을 넘기면 None. `timeout` 과 `deadline`(단조
    시계의 끝) 가운데 먼저 오는 것까지 기다리고, 남은 시간이 없으면 띄우지 않는다.

    출력은 임시 파일로 받는다. 파이프면 `ls-remote` 가 띄운 손자 프로세스(`git-remote-https`)가
    쥐어 시간 제한에서 끊기지 않는다(`.claude/rules/tools.md`)."""
    wait = min(timeout, deadline - time.monotonic())
    if wait <= 0:
        return None
    with tempfile.TemporaryFile() as out:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=_environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=wait,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        out.seek(0)
        text = out.read().decode("utf-8", "replace")
    return text if result.returncode == 0 else None


def _remote_url(remote: str, cwd: str | None, deadline: float) -> str | None:
    """이름으로 준 원격의 URL. URL 이나 경로로 적은 원격은 None 이다(묻지 않는다).

    명령 글의 주소로 접속하면 이 훅이 권한 판정보다 먼저 그 호스트에 요청을 보내, 사용자가 그
    호출을 거부해도 주소에 담은 데이터가 이미 나간다. 윈도의 `//호스트/공유` 는 SMB 접속도 띄울 수
    있다(PR 직전 보안 리뷰가 로컬 HTTP 서버로 재현했다). 이름으로 준 원격을 남의 주소로 바꾸려면
    `git remote add`·`set-url` 이 먼저 권한 판정을 거친다."""
    if any(char in remote for char in "/:\\@") or remote == ".":
        return None
    url = _run(["git", "remote", "get-url", remote], cwd, URL_TIMEOUT, deadline)
    return url.strip() if url else None


class Lookup(NamedTuple):
    """지울 브랜치마다 그것을 머리로 둔 열린 PR 번호와, 원격이 GitHub 이면 그 (owner, repo)."""

    found: dict[str, list[int]]
    repo: tuple[str, str] | None


def open_heads(deletion: Deletion, cwd: str | None, deadline: float) -> Lookup:
    """열린 PR 을 찾는다. 읽지 못하거나 `deadline` 을 넘기면 빈 표다(fail-open).

    `-` 로 시작하는 원격은 git 에 넘기지 않는다. `git push --delete -- --upload-pack=<명령> …` 의
    낱말은 git push 에는 원격 이름이지만 `git ls-remote` 에는 옵션이라, 넘기면 이 훅이 그 명령을
    띄운다(PR 직전 보안 리뷰). 브랜치는 `refs/heads/<브랜치>` 꼴로만 넘겨 `-` 로 시작해도 옵션이
    되지 않는다."""
    if deletion.remote.startswith("-"):
        return Lookup({}, None)
    url = _remote_url(deletion.remote, cwd, deadline)
    if url is None:
        return Lookup({}, None)
    repo = github_repo(url)
    gh = shutil.which("gh")
    if repo is not None and gh is not None:
        endpoint = f"repos/{repo[0]}/{repo[1]}/pulls?state=open&per_page=100"
        command = [gh, "api", endpoint, "--paginate", "--jq", _GH_JQ]
        listing = _run(command, cwd, GH_TIMEOUT, deadline)
        if listing is not None:
            return Lookup(gh_open_heads(listing, f"{repo[0]}/{repo[1]}", deletion.branches), repo)
    refs = [f"refs/heads/{branch}" for branch in deletion.branches]
    command = ["git", "ls-remote", deletion.remote, *refs, "refs/pull/*/head", "refs/pull/*/merge"]
    listing = _run(command, cwd, LS_REMOTE_TIMEOUT, deadline)
    found = {} if listing is None else refs_open_heads(listing, deletion.branches)
    return Lookup(found, repo)


def reason_for(command: str, cwd: str | None, budget: float = BUDGET) -> str | None:
    """막는 이유. 지우는 푸시가 없거나 그 브랜치에 열린 PR 이 없으면 None. 모든 지우는 푸시가
    함께 쓰는 시간은 `budget` 초다."""
    deadline = time.monotonic() + budget
    for deletion in deletions(command):
        lookup = open_heads(deletion, cwd, deadline)
        if lookup.found:
            return _reason(deletion.remote, lookup)
    return None


def _reason(remote: str, lookup: Lookup) -> str:
    pulls = ", ".join(
        f"`{branch}`(PR {', '.join(f'#{n}' for n in numbers)})"
        for branch, numbers in lookup.found.items()
    )
    first = next(iter(lookup.found.values()))[0]
    where = f"{lookup.repo[0]}/{lookup.repo[1]}" if lookup.repo else "<owner>/<repo>"
    return (
        f"`{remote}` 에서 지우려는 브랜치 {pulls} 가 열린 PR 의 머리다. 머리 브랜치를 지우면"
        " GitHub 이 그 PR 을 닫는다. 병합 전이거나 병합이 실패했으면 지우지 않는다(대기열 262."
        " 병합이 base 보다 뒤처져 실패했는데 같은 묶음의 지우기가 PR 을 닫았다). 병합을 먼저"
        f" 끝내고(`gh api repos/{where}/pulls/{first} --jq .merged` 가 true) 다시 친다. PR 을"
        f" 버리려는 것이면 먼저 닫고(`gh api -X PATCH repos/{where}/pulls/{first} -f state=closed`)"
        " 다시 친다. 둘 다 REST 라 클라우드 세션에서도 돈다. 이 호출 전체가 돌지 않았다. 같은"
        " 호출에 묶은 다른 명령이 있으면 그것만 따로 다시 친다."
    )


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    reason = reason_for(command, payload.get("cwd")) if command is not None else None
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
