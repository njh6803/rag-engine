"""PreToolUse 훅(Bash|PowerShell|Read|Grep). 사용자 설정 파일을 출력하는 호출을 막는다.

대상은 둘이다. `~/.claude/settings.json`(사용자 설정)과 `~/.claude.json`(앱 상태).
`CLAUDE_CONFIG_DIR` 이 있으면 그 아래의 `settings.json`·`.claude.json` 도 든다. 둘 다 `env`(와 MCP
서버의 환경·헤더) 같은 갈래에 비밀을 들 수 있다. 설정의 한 갈래를 통째로 출력해 비밀이 세션 기록에
남았고, `.env` 만 보는 `hook_env_read` 는 그것을 잡지 못했다(대기열 272, 일지 2026-10-16-01). 실패가
조용하고(기록에 남은 뒤에야 안다) 모양이 고정돼 첫 사건에서 막는 훅으로
갔다(그때의 `.claude/rules/tools.md` 예외, `hook_env_read` 선례. 지금은 손상이 그 예외다). 계기만
주는 PreToolUse 훅은 명령을 그대로 돌려 막지 못한다.

막는 모양.
- Read 의 `file_path` 가 대상이다. 오프셋을 준 일부 읽기도 막는다. 어느 줄에 비밀이 있는지 모른다.
- Grep 도구의 출력이 내용(`output_mode: content`)이고, `path` 가 대상이거나 `path`(없으면 cwd)가
  대상을 품은 폴더(홈, `~/.claude`, 그 위의 폴더)이고 glob 이 없거나 glob 이 대상의 이름에 맞는다.
  glob 의 중괄호(`*.{md,json}`)는 ripgrep 처럼 펼친다. git 저장소가 아닌 폴더에서 Grep 도구는 glob
  없이도 숨김 파일(`.claude.json`, `.claude/` 아래)을 읽었다(셀프 리뷰 표준 축이 가짜 파일로 손으로
  봤다). 홈은 git 저장소가 아니다. 기본 출력(`files_with_matches`)과 `count` 는 파일 이름과 수만 내
  지나간다.
- Bash·PowerShell 에서 읽는 명령(`cat`·`head`·`grep`·`sed`·`jq`, `Get-Content`·`gc`·`type`·
  `Select-String` 등)의 낱말에 대상이 있다. `jq` 는 필터가 키만 내면(`keys`, `.env | keys`)
  지나간다. 재귀로 훑는 명령(`rg`·`ag`·`ack`, `-r`·`-R`·`--recursive` 를 준 `grep`)은 낱말이 대상을
  품은 폴더여도 막는다. `[IO.File]::Read…` 가 든 명령은 어느 낱말에든 대상이 있으면 막는다. 명령은
  글 셋을 모두 보고 어느 쪽에서든 걸리면 막는다. 주석(인용 밖 낱말 머리의 `#` 부터 줄 끝)을 뺀 글,
  빼지 않은 글, 백틱을 지운 글이다. 이 훅의 주석 판정은 셸의 이스케이프와 인용(PowerShell 의
  `` `# ``, bash 의 `"a\\" # "`)을 다 따르지 못해, 한쪽만 보면 셸이 명령으로 읽는 자리를 주석으로
  버려 대상을 숨길 수 있다(PR 직전 보안 리뷰). 백틱은 bash 에서 명령 치환이고 PowerShell 에서
  이스케이프다. 글마다 줄 이어 쓰기(`\\` 와 줄바꿈)를 붙인 뒤 인용 밖의 제어 연산자(`;`·`|`·`&`·
  줄바꿈)와 괄호·백틱으로 가르므로 `$(cat …)` 와 `(Get-Content …)` 의 안도 본다.
  `bash -c`·`powershell -Command` 의 문자열은 한 겹씩 풀어 본다. 명령 앞의 환경 대입(`X=1`),
  PowerShell 의 변수 대입(`$s = …`), 옵션 없는 래퍼(`command`·`env`·`time` 등)는 벗긴다.
낱말 안의 경로는 `settings.json`·`.claude.json` 으로 끝나는 조각을 찾아 푼다. `~`,
`$HOME`·`${HOME}`· `$env:USERPROFILE`·`%USERPROFILE%`·`$CLAUDE_CONFIG_DIR` 같은 머리는 그 환경
값으로, Git Bash 의 `/c/…` 는 `C:/…` 로, 상대 경로는 페이로드의 `cwd` 로 풀고, 윈도에서는 대소문자를
가리지 않고 견준다. 모르는 변수로 시작하는 `.claude.json` 은 대상으로 본다(그 이름은 홈 밖에 두지
않는다). 경로의 규칙(윈도·POSIX)은 인자로 받아, 우분투의 CI 에서도 윈도 경로의 판정을 잴 수 있다.
프로젝트의 `.claude/settings.json` 은 대상이 아니다. update-config 가 이 저장소에서 여는 설정이고
비밀을 두지 않는다(반례 축, 대기열 272). 사용자 범위의 update-config 는 이 훅에 막힌다. 그 스킬은
설정 파일을 Read 로 열고, 그 Read 가 비밀이 기록에 실리는 바로 그 길이다. Edit·Write 는 앞의 Read 를
요구해 그 길로도 고치지 못한다. 그래서 막을 때 키 이름만 보는 명령(`keys_command`. 값은 내지 않고
최상위 키와, 값이 객체(dict)이면 그 안의 키 이름 스물까지)과, 값을 바꾸는 길(JSON 을 읽어 그 키만
고쳐 쓰는 스크립트를 출력 없이 돌리거나 사람에게 부탁한다)을 함께 준다.

못 보는 것.
- 언어 안의 읽기(`python -c "open(…)"`). 키 명령이 그 길이라 막지 않는다.
- 내용을 내지 않는 Grep(`files_with_matches`·`count`)으로 정규식을 바꿔 가며 값을 한 글자씩 맞혀
  보는 것. 출력에 값이 실리지 않아 막는 모양 밖이다. 이 훅이 막는 것은 실수로 값을 기록에 싣는
  길이고, 일부러 값을 빼내려는 호출은 바로 위의 언어 안의 읽기로도 지나간다(PR 뒤 백그라운드 보안
  리뷰).
- 복사본(`cp ~/.claude.json x && cat x`), `cd ~ && cat .claude.json` 처럼 조각마다 바뀐 cwd 의
  상대 경로, 경로 없이 cwd 를 훑는 재귀 검색(`cd ~ && grep -r x`), 변수에 담은 경로(`p=…; cat $p`,
  `Get-Content (Join-Path $HOME '.claude.json')`), 명령이 넘긴 인자(`xargs`).
- 프로세스 환경의 출력(`env`, `printenv`, `Get-ChildItem env:`). 설정의 `env` 는 세션의 환경에
  들어가 이 길로도 나온다. 대상 파일을 읽는 것이 아니라 이 훅의 판정 밖이다.
- 위 목록 밖의 읽는 명령, 옵션이 있는 래퍼(`sudo -u x cat …`), 경로 안의 이스케이프
  (`~/.claude\\.json`), PowerShell 의 백틱 줄 이어 쓰기.
- 두 대상 밖의 파일(`~/.claude/settings.local.json`, 다른 도구의 설정). 비밀을 둔 파일이 더 있으면
  `places` 의 대상에 더한다.
- 거짓 양성: 꼬리 주석에 대상 경로를 적은 읽기 명령(`… | head # ~/.claude/settings.json`). 주석을
  빼지 않은 글도 보기 때문이다.
"""

from __future__ import annotations

import fnmatch
import json
import ntpath
import os
import posixpath
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypedDict

type Flavor = Literal["nt", "posix"]

TARGET_NAMES = ("settings.json", ".claude.json")
READERS = frozenset(
    {
        "cat", "tac", "head", "tail", "less", "more", "bat",
        "grep", "egrep", "fgrep", "rg", "ag", "ack", "findstr",
        "sed", "awk", "gawk", "cut", "tr", "sort", "uniq", "nl", "column", "rev",
        "strings", "xxd", "od", "hexdump", "base64", "iconv",
        "diff", "cmp", "comm", "paste", "source", "jq",
        "get-content", "gc", "type", "select-string", "sls", "format-hex", "fhx",
    }
)  # fmt: skip
# 늘 재귀로 훑는 검색 명령. `grep` 류는 재귀 옵션이 있을 때만이다.
RECURSIVE_SEARCHERS = frozenset({"rg", "ag", "ack"})
GREPS = frozenset({"grep", "egrep", "fgrep"})
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "pwsh", "powershell", "cmd"})
_SHELL_FLAGS = frozenset({"-c", "-command", "/c"})
_WRAPPERS = frozenset({"command", "builtin", "env", "exec", "nohup", "time", "nice", "sudo"})
_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
_PS_ASSIGNMENT = re.compile(r"^\$[\w:]+=?$")
_SHORT_CLUSTER = re.compile(r"^-[A-Za-z]+$")
_HEREDOC_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_IO_FILE = re.compile(r"\[(?:System\.)?IO\.File\]::Read", re.IGNORECASE)
# 낱말 안의 경로 조각. 머리의 드라이브(`C:`)와 PowerShell 환경 변수(`$env:NAME`)의 콜론만 받고,
# `-Path:` 같은 옵션의 콜론에서는 끊는다.
_CANDIDATE = re.compile(
    r"(?:\$\{?env:\w+\}?|(?<![A-Za-z])[A-Za-z]:)?"
    r"[^'\"<>=,():;|&`]*?(?:settings\.json|\.claude\.json)(?![\w.-])",
    re.IGNORECASE,
)
# 경로의 머리. `~`, `$NAME`·`${NAME}`·`$env:NAME`·`${env:NAME}`, `%NAME%`. 둘째 묶음이 `env:` 다.
_HEAD = re.compile(r"^(?:~|\$\{?(env:)?(\w+)\}?|%(\w+)%)(?=[\\/]|$)", re.IGNORECASE)
_MSYS = re.compile(r"^/([A-Za-z])(?=/|$)")
# 키만 내는 jq 필터(`keys`, `.env | keys`, `length`, `type`).
_KEYS_FILTER = re.compile(r"^\s*(?:\.[\w.\"\[\]-]*\s*\|\s*)?(?:keys|keys_unsorted|length|type)\s*$")
_JQ_VALUE_OPTIONS = frozenset({"--indent", "-L", "--arg", "--argjson", "--slurpfile", "--rawfile"})
_UNKNOWN = "\0"


class ToolInput(TypedDict, total=False):
    command: str
    file_path: str
    path: str
    glob: str
    output_mode: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_name: str
    tool_input: ToolInput
    cwd: str


def _module(flavor: Flavor):
    """경로 규칙의 모듈. 반환 타입은 pyright 가 두 모듈의 합으로 추론한다(`ModuleType` 으로 적으면
    속성이 알 수 없는 타입이 된다)."""
    return ntpath if flavor == "nt" else posixpath


def _key(flavor: Flavor, path: str) -> str:
    """견줄 열쇠. 윈도는 대소문자와 구분자를 맞춘다."""
    module = _module(flavor)
    return module.normcase(module.normpath(path))


@dataclass(frozen=True)
class Places:
    """경로를 푸는 자리. `targets` 는 견줄 열쇠 → 보여 줄 경로다."""

    flavor: Flavor
    cwd: str
    homes: tuple[str, ...]
    variables: Mapping[str, str]
    targets: Mapping[str, str]

    def key(self, path: str) -> str:
        return _key(self.flavor, path)


def _msys(path: str) -> str:
    """Git Bash 의 `/c/…` 를 `C:/…` 로."""
    return _MSYS.sub(lambda m: f"{m.group(1).upper()}:", path)


def places(environ: Mapping[str, str], cwd: str, flavor: Flavor) -> Places:
    """환경에서 홈과 대상을 푼다. 홈은 `USERPROFILE`·`HOME` 이고, 둘 다 없으면 `~` 를 푼 값이다."""
    upper = {name.upper(): value for name, value in environ.items()}
    variables = {
        name: _msys(upper[name]) if flavor == "nt" else upper[name]
        for name in ("HOME", "USERPROFILE", "CLAUDE_CONFIG_DIR")
        if upper.get(name)
    }
    homes = tuple(dict.fromkeys(variables[n] for n in ("USERPROFILE", "HOME") if n in variables))
    if not homes:
        homes = (os.path.expanduser("~"),)
    module = _module(flavor)
    files = [module.join(home, ".claude.json") for home in homes]
    files += [module.join(home, ".claude", "settings.json") for home in homes]
    if config := variables.get("CLAUDE_CONFIG_DIR"):
        files += [module.join(config, name) for name in TARGET_NAMES]
    targets = {_key(flavor, file): file for file in files}
    return Places(flavor, cwd, homes, variables, targets)


def _resolve(path: str, place: Places) -> list[str]:
    """경로 조각을 견줄 열쇠들로. 머리의 변수를 모르면 `_UNKNOWN` 하나다. 윈도가 아니어도
    백슬래시는 구분자로 본다(리눅스의 PowerShell 이 받는 `$HOME\\.claude\\…`)."""
    module = _module(place.flavor)
    path = path if place.flavor == "nt" else path.replace("\\", "/")
    head = _HEAD.match(path)
    if head is not None:
        name = head.group(2) or head.group(3)
        rest = path[head.end() :].lstrip("\\/")
        # `$HOME` 은 Bash 에서는 환경 변수, PowerShell 에서는 환경에 없어도 서는 자동 변수다
        if name is None or (name.upper() == "HOME" and head.group(1) is None):
            bases = place.homes
        else:
            value = place.variables.get(name.upper())
            bases = (value,) if value else ()
        if not bases:
            return [_UNKNOWN]
        return [place.key(module.join(base, rest)) for base in bases]
    resolved = _msys(path) if place.flavor == "nt" else path
    if not module.isabs(resolved):
        resolved = module.join(place.cwd, resolved)
    return [place.key(resolved)]


def target_of(word: str, place: Places) -> str | None:
    """낱말이 가리키는 대상의 경로. 없으면 None. 모르는 변수로 시작하는 `.claude.json` 은 홈의
    `.claude.json` 으로 든다(키 명령에 펼치지 못한 변수를 넣지 않게)."""
    for match in _CANDIDATE.finditer(word):
        # 인용이 어긋난 글에서는 조각 앞에 공백이 붙어 머리(`~`)를 읽지 못한다
        candidate = match.group(0).strip()
        for key in _resolve(candidate, place):
            if key in place.targets:
                return place.targets[key]
            if key == _UNKNOWN and candidate.lower().endswith(".claude.json"):
                return _module(place.flavor).join(place.homes[0], ".claude.json")
    return None


def _inside(folder: str, target: str, flavor: Flavor) -> bool:
    """열쇠 `target` 이 열쇠 `folder` 이거나 그 아래인가."""
    separator = "\\" if flavor == "nt" else "/"
    prefix = folder if folder.endswith(separator) else folder + separator
    return target == folder or target.startswith(prefix)


def targets_under(path: str, place: Places) -> list[str]:
    """`path` 가 품은 대상의 열쇠들. 모르는 변수로 시작하면 빈 목록이다."""
    return [
        target
        for folder in _resolve(path, place)
        if folder != _UNKNOWN
        for target in place.targets
        if _inside(folder, target, place.flavor)
    ]


def keys_command(path: str) -> str:
    """대상의 키 이름만 내는 명령. 값은 내지 않는다."""
    posix = path.replace("\\", "/")
    return (
        'uv run python -c "import json, pathlib; '
        f"d = json.loads(pathlib.Path('{posix}').read_text(encoding='utf-8')); "
        "print({k: sorted(v)[:20] if isinstance(v, dict) else type(v).__name__"
        ' for k, v in d.items()})"'
    )


def _reason(what: str, path: str) -> str:
    return (
        f"{what} 사용자 설정 파일 `{path}` 을 출력한다. 이 파일은 `env`(와 MCP 서버의 환경·헤더)"
        " 같은 갈래에 비밀을 들 수 있어 도구 출력에 싣지 않는다(대기열 272. 설정의 한 갈래를 통째로"
        f" 출력해 비밀이 세션 기록에 남았다). 키 이름만 보려면 `{keys_command(path)}` 를 친다. 값을"
        " 바꿀 때는 JSON 을 읽어 그 키만 고쳐 쓰는 스크립트를 출력 없이 돌리거나 사람에게 부탁한다."
        " update-config 스킬이 사용자 범위에서 이 파일을 Read 로 열려 해도 여기서 막히고, Edit 는"
        " 그 Read 를 요구해 쓰지 못한다. 프로젝트 설정(`.claude/settings.json`)은 막지 않는다."
    )


WHOLE_CALL_NOTE = (
    " 이 호출 전체가 돌지 않았다. 같은 호출에 묶은 다른 명령이 있으면 그것만 따로 다시 친다."
)


def reason_for(tool_name: str, tool_input: ToolInput, place: Places) -> str | None:
    """막는 이유. 사용자 설정 파일을 출력하지 않으면 None."""
    if tool_name == "Read":
        path = target_of(tool_input.get("file_path", ""), place)
        return None if path is None else _reason("Read 가", path)
    if tool_name == "Grep":
        path = _grep_target(tool_input, place)
        return None if path is None else _reason("Grep 도구가", path)
    command = tool_input.get("command")
    if command is None:
        return None
    found = _command_target(command, place)
    return None if found is None else _reason(f"`{found[0]}` 가", found[1]) + WHOLE_CALL_NOTE


def _grep_target(tool_input: ToolInput, place: Places) -> str | None:
    """Grep 도구가 내용을 낼 대상. 출력이 `content` 이고, `path` 가 대상이거나 대상을 품은 폴더이고
    glob 이 없거나 맞는다. 기본 출력(`files_with_matches`)과 `count` 는 이름과 수만 내 지나간다."""
    if tool_input.get("output_mode") != "content":
        return None
    path = tool_input.get("path")
    if path is not None and (found := target_of(path, place)) is not None:
        return found
    glob = tool_input.get("glob")
    leaves = [] if glob is None else _braces(glob.replace("\\", "/").rsplit("/", 1)[-1])
    for target in targets_under(path or place.cwd, place):
        shown = place.targets[target]
        name = shown.replace("\\", "/").rsplit("/", 1)[-1]
        if glob is None or any(fnmatch.fnmatch(name, leaf) for leaf in leaves):
            return shown
    return None


def _braces(pattern: str) -> list[str]:
    """glob 의 중괄호(`*.{md,json}`)를 ripgrep 처럼 펼친다. 중첩도 안쪽부터 펼친다."""
    found = re.search(r"\{([^{}]*)\}", pattern)
    if found is None:
        return [pattern]
    head, tail = pattern[: found.start()], pattern[found.end() :]
    return [
        expanded
        for choice in found.group(1).split(",")
        for expanded in _braces(head + choice + tail)
    ]


def _command_target(command: str, place: Places) -> tuple[str, str] | None:
    """(명령 이름, 대상 경로). 읽는 명령의 낱말에 대상이 없으면 None.

    주석을 뺀 글과 빼지 않은 글을 둘 다 보고 어느 쪽에서든 걸리면 막는다. 이 훅의 주석 판정은 셸의
    이스케이프와 인용을 다 따르지 못해(PowerShell 의 `` `# ``, bash 의 `"a\\" # "`), 셸이 명령으로
    읽는 자리를 주석으로 버리면 대상을 숨길 수 있다(PR 직전 보안 리뷰). 그 대가로 꼬리 주석에 대상
    경로를 적은 읽기 명령은 막힌다(거짓 양성, 못 보는 것)."""
    # 셋째 글은 백틱을 지운 것이다. bash 의 백틱은 명령 치환이라 조각을 가르지만 PowerShell 의
    # 백틱은 이스케이프라, 갈라 읽으면 `` `#x `` 뒤의 경로가 명령 이름이 아닌 조각에 남는다
    for text in (_without_comments(command), command, command.replace("`", "")):
        if (found := _target_in(text, place)) is not None:
            return found
    return None


def _target_in(command: str, place: Places) -> tuple[str, str] | None:
    """한 글에서 찾은 (명령 이름, 대상 경로)."""
    segments = _segments(command)
    if _IO_FILE.search(command):
        for segment in segments:
            for word in _words(segment):
                if (path := target_of(word, place)) is not None:
                    return "[IO.File]::Read", path
    for segment in segments:
        words = _strip_prefix(_words(segment))
        if not words:
            continue
        name = words[0].replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
        args = words[1:]
        if name in SHELLS:
            inner = _shell_argument(args)
            if inner is not None and (found := _command_target(inner, place)) is not None:
                return found
            continue
        if name not in READERS or (name == "jq" and _keys_only(args)):
            continue
        for word in args:
            if (path := target_of(word, place)) is not None:
                return words[0], path
        if _recursive(name, args):
            for word in args:
                if not word.startswith("-") and (found := targets_under(word, place)):
                    return words[0], place.targets[found[0]]
    return None


def _recursive(name: str, args: list[str]) -> bool:
    """폴더를 재귀로 훑는 검색인가. `rg`·`ag`·`ack` 는 늘, `grep` 류는 재귀 옵션이 있을 때다."""
    if name in RECURSIVE_SEARCHERS:
        return True
    if name not in GREPS:
        return False
    return any(
        arg in {"--recursive", "--dereference-recursive"}
        or (_SHORT_CLUSTER.match(arg) is not None and bool(set("rR") & set(arg[1:])))
        for arg in args
    )


def _without_comments(text: str) -> str:
    """인용 밖에서 공백·연산자 뒤 낱말 머리의 `#` 부터 그 줄 끝까지를 뺀다. 꼬리 주석에 든 경로를
    읽는 명령의 인자로 읽었다(PR 직전 버그 축). `${#a}`·`a#b` 처럼 낱말 안의 `#` 는 둔다."""
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
        elif char == "#" and (index == 0 or text[index - 1] in " \t\n;|&()"):
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        kept.append(char)
        index += 1
    return "".join(kept)


def _segments(command: str) -> list[str]:
    """줄 이어 쓰기를 붙인 뒤 인용 밖의 제어 연산자·괄호·백틱으로 가른 조각. heredoc 본문은 뺀다."""
    text = re.sub(r"\\\r?\n", " ", "\n".join(_without_heredoc_bodies(command)))
    pieces: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in text:
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char in ";|&\n()`":
            pieces.append("".join(current))
            current = []
        else:
            current.append(char)
    pieces.append("".join(current))
    return [piece for piece in pieces if piece.strip()]


def _words(segment: str) -> list[str]:
    """인용 밖 공백으로 가르고 인용 부호를 벗긴 낱말. 백슬래시는 글자 그대로다(윈도 경로)."""
    words: list[str] = []
    current: list[str] = []
    quote: str | None = None
    started = False
    for char in segment:
        if quote is not None:
            if char == quote:
                quote = None
            else:
                current.append(char)
        elif char in "'\"":
            quote = char
            started = True
        elif char.isspace():
            if current or started:
                words.append("".join(current))
            current, started = [], False
        else:
            current.append(char)
    if current or started:
        words.append("".join(current))
    return words


def _strip_prefix(words: list[str]) -> list[str]:
    """명령 앞의 환경 대입, PowerShell 의 변수 대입, 옵션 없는 래퍼를 벗긴다."""
    index = 0
    while index < len(words):
        word = words[index]
        if _ASSIGNMENT.match(word) or word.lower() in _WRAPPERS:
            index += 1
        elif _PS_ASSIGNMENT.match(word):
            index += 1
            if not word.endswith("=") and index < len(words) and words[index] == "=":
                index += 1
        else:
            break
    return words[index:]


def _shell_argument(args: list[str]) -> str | None:
    """`bash -c "…"`·`powershell -Command …`·`cmd /c …` 의 명령 문자열."""
    for index, arg in enumerate(args):
        if arg.lower() in _SHELL_FLAGS and index + 1 < len(args):
            return " ".join(args[index + 1 :])
    return None


def _keys_only(args: list[str]) -> bool:
    """jq 의 필터가 키만 내는가. 필터를 파일로 받으면(`-f`) 모른다고 본다."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"-f", "--from-file"} or arg.startswith("--from-file="):
            return False
        if arg in _JQ_VALUE_OPTIONS:
            index += 3 if arg in {"--arg", "--argjson", "--slurpfile", "--rawfile"} else 2
            continue
        if arg.startswith("-") and arg != "-":
            index += 1
            continue
        return _KEYS_FILTER.match(arg) is not None
    return False


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


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    flavor: Flavor = "nt" if os.name == "nt" else "posix"
    place = places(os.environ, payload.get("cwd") or os.getcwd(), flavor)
    reason = reason_for(payload.get("tool_name", ""), payload.get("tool_input", {}), place)
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
