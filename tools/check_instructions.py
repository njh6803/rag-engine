"""지침 파일과 하네스 설정 검사. 규칙 배치는 런북 3단계와 agent-os ADR 0004의 기계 판정자이고, 경로
참조 두 가지(rules 의 glob, 훅 명령)는 2026-09-23 의 잠김(PR #52)에서, `@` 임포트와 임포트된 파일의
경로와 사본 센티널과 훅의 stdin 은 2026-09-28 의 하네스 감사(대기열 25·32 와 감사 지적)에서, 중첩
지침 파일은 web-admin 티켓 01 에서, rules 와 임포트된 파일 안의 `@` 는 2026-09-29 실측에서 왔다.

- `.claude/rules/` 아래(하위 폴더까지)의 규칙은 `paths` 프론트매터가 있어야 한다. 없으면 매 세션
  전부 실린다.
- 그 `paths`의 glob은 저장소에서 무언가를 가리켜야 한다. 아무것도 안 가리키면 그 규칙이 조용히
  안 실린다.
- `.claude/settings.json`의 훅은 저장소 파일을 `${CLAUDE_PROJECT_DIR}`로 부른다. 상대 경로면 세션이
  루트를 벗어나는 순간 깨진다.
- `CLAUDE.md`는 200줄 이하다.
- `CLAUDE.md`의 `@` 임포트는 `docs/constitution/principles.md` 하나뿐이다. 줄 머리만이 아니라
  문장 속 `@경로` 도 임포트다(공식 문서: "reference them with @ syntax anywhere"). 코드 스팬과
  펜스 안, 닫힌 HTML 주석 안은 아니다(주석은 2026-09-29 실측, PR #100 리뷰).
- 임포트된 파일 안의 백틱 경로는 저장소 루트 기준으로 실재해야 한다. `@` 임포트의 상대 경로는 그
  임포트를 담은 파일 기준으로 풀리지만, 백틱 경로는 모델이 읽는 글자라 루트(작업의 자리) 기준으로
  읽혔다(대기열 32, PR #43 이 헌법의 형제 `README.md` 를 루트 README 로 읽어 버전을 못 찾았다).
- 원본 위에 덧댄 스킬 사본은 `프로젝트 사본` 주석을 지니고 있어야 하고, 그 주석을 지닌 사본은
  `PATCHED_SKILLS` 에 있어야 한다. 한쪽만 보면 목록 밖의 사본이 되돌려져도 초록이다.
- `tools/hook_*.py`는 stdin 을 바이트(`sys.stdin.buffer`)로 읽는다. 훅 환경에 `PYTHONUTF8` 이 있다고
  가정하지 않는다 — 없으면 텍스트 stdin 은 cp949 이고, 한글이 든 입력은 예외 없이 출력 0바이트가
  된다(대기열 25).
- `tools/` 의 파이썬은 외부 명령을 기다리는 호출(`subprocess.run`, `communicate`, `wait` 등)에
  시간 제한을 둔다. 멈춘 호출은 루프의 시간 제한으로 끊지 못한다(대기열 342). 판정과 빼는 표지는
  `calls_without_timeout` 의 독스트링이 원천이다.
- `src`·`tests`·`tools` 의 파이썬은 매개변수와 반환의 주석을 `bool | None` 으로 두지 않는다. 세
  값으로 갈래를 고르는 꼴이고 ruff FBT 는 키워드 전용 매개변수를 보지 않는다(대기열 423). 판정은
  `optional_bool_annotations` 의 독스트링이 원천이다.
- 루트 밖에 `CLAUDE.md` 와 `AGENTS.md` 가 없다. `next dev` 가 앱 폴더에 두 파일을 만든다(agent-os
  ADR 0021, web-admin 티켓 01).
- rules 파일과 임포트된 파일 안에도 `@` 임포트가 없다. 그것들도 따라가서 실린다.
- `.claude/settings.local.json` 에 가드(deny·ask·hooks)가 없다. local 은 워크트리에 없어 거기서 연
  세션에서 조용히 빠진다(2026-10-05 워크트리 감사).

pre-commit이 커밋마다 돌린다. 규칙을 쓰는 시점에 걸리는 것과 나중에 전부 재배치하는 것은
비용이 다르다(선행 저장소 AAPP-15).
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, NamedTuple, TypedDict

ROOT = Path(__file__).resolve().parent.parent
MAX_LINES = 200
ALLOWED_IMPORTS = ["@docs/constitution/principles.md"]
PATCHED_SKILLS = (
    "code-review",
    "grill-with-docs",
    "grilling",
    "implement",
    "retro",
    "to-spec",
    "to-tickets",
)
SENTINEL = "프로젝트 사본"
NESTED_INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")
# `bool | None` 검사가 훑는 디렉터리. pyright 의 `include` 와 같고 시험이 맞댄다.
OPTIONAL_BOOL_ROOTS = ("src", "tests", "tools")
SETTINGS = Path(".claude") / "settings.json"
LOCAL_SETTINGS = Path(".claude") / "settings.local.json"
PROJECT_DIR_PLACEHOLDER = "${CLAUDE_PROJECT_DIR}"
# 백틱 토큰이 경로인지 가르는 확장자. 슬래시가 있으면 확장자와 무관하게 경로다. `agent_os.core` 나
# `Any` 처럼 슬래시도 이 확장자도 없는 토큰은 경로가 아니다.
PATH_EXTENSIONS = (".md", ".py", ".toml", ".json", ".yaml", ".yml", ".ps1", ".txt", ".sh")

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
_PATHS_KEY = re.compile(r"^paths:[ \t]*(.*)$", re.M)
# 블록 목록의 항목. 키와 같은 깊이(`- "src/**"`)도 받는다(YAML 이 받는다). 값 없는 `-` 는
# 빈 항목이다.
_LIST_ITEM = re.compile(r"^[ \t]*-[ \t]*(.*?)[ \t]*$")
# 상대 경로처럼 생긴 토큰. 바로 앞 글자가 경로의 일부(`/`, `}`, 이름 글자)면 잡지 않아서
# `${CLAUDE_PROJECT_DIR}/tools/x.py` 의 `tools/x.py` 는 지나간다.
_PATH_TOKEN = re.compile(r"(?<![\w/}.~-])([\w.-]+(?:/[\w.-]+)+)")
# 펜스와 블록 HTML 주석의 경계는 CommonMark 다. 여는 펜스는 0~3칸 들여쓴(목록 표지 뒤도) ```
# 이상이나 ~~~ 이상이고(백틱 펜스의 정보 문자열에는 백틱이 없다), 닫는 펜스는 같은 문자로 여는 길이
# 이상이다.
# 블록 주석은 0~3칸 들여쓴 `<!--` 로 여는 줄부터 `-->` 가 든 줄까지다. 네 칸 이상은 들여쓴 코드다.
_FENCE_OPEN = re.compile(r"^ {0,3}(?:(?:[-+*]|\d{1,9}[.)])[ \t]+)?(?:(`{3,})[^`]*|(~{3,}).*)$")
_FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
_COMMENT_BLOCK_OPEN = re.compile(r"^ {0,3}<!--")
_HTML_BLOCK_OPEN = re.compile(r"^ {0,3}</?[A-Za-z]")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
# 문단 속 주석과 코드 스팬은 빈 줄(문단의 끝)을 넘지 못한다. 코드 스팬은 같은 길이의 백틱끼리
# 짝짓는다.
_INLINE_COMMENT = re.compile(r"<!--(?:(?!\n[ \t]*\n).)*?-->", re.S)
_INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_INLINE_CODE_LINES = re.compile(r"(?<!`)(`+)(?!`)((?:(?!\n[ \t]*\n).)+?)(?<!`)\1(?!`)", re.S)
# 임포트된 파일의 백틱 경로를 뽑는 데만 쓴다.
_CODE_SPAN = re.compile(r"`([^`\n]+)`")
# 줄의 자리. `_block_lines` 가 붙이고 두 읽기가 다르게 거른다.
_Place = Literal["text", "html", "unclosed"]
# `@경로` 임포트. 앞이 공백이나 줄 머리이고 뒤가 공백이나 줄 끝인 토큰을 모두 센다. 한글이 든 것만
# 뺀다 — 조사가 붙은 `@x.md를` 은 실리지 않았다(2026-09-29 `claude -p` 2.1.281 실측. 한글 이름의
# 파일은 실렸으니 그 이름의 파일이 없어서로 보인다 — 추론, `at_imports` 의 못 보는 것). 앞이 공백이
# 아닌 `noreply@anthropic.com` 과 `(@x.md)` 도 아니다(같은 실측). 그 밖의 문장부호가 든 것(`@x.md.`,
# `@x.md,`, `@c++.md`)은 재지 않은 것까지 보수적으로 센다 — 실리는 파일을 놓치는 것보다 백틱으로
# 옮기는 것이 싸다. `@x.md.` 는 끝의 마침표까지 토큰이라 허용된 임포트와 다른 것으로 잡힌다.
_IMPORT_TOKEN = re.compile(r"(?<!\S)@([^\s가-힣]+)(?=\s|$)")
_PATHISH = re.compile(r"^\.?[\w.-]+(?:/[\w.*-]+)*/?$")
# 이 검사가 부르는 git 하나를 기다리는 초. 넘기면 알 수 없는 것으로 센다.
CALL_TIMEOUT = 60
# 외부 명령을 기다리는 `subprocess` 의 함수(대기열 342). `Popen` 은 띄우기만 하고 기다리지 않는다.
_WAITING_FUNCTIONS = frozenset({"run", "call", "check_call", "check_output"})
# 받는 쪽의 형을 보지 않는 메서드와 timeout 이 들어가는 위치 인자의 자리.
_WAITING_METHODS = {"communicate": 1, "wait": 0}
# 시간 제한을 두지 않는 자리의 표지. 주석의 머리이고 까닭이 뒤따라야 한다.
_NO_TIMEOUT_MARKER = re.compile(r"^#\s*시간 제한 없음:\s*\S")
# 표지로 빼지 않는 메서드. 끝낸 뒤에도 트리를 떠난 손자가 파이프를 쥐면 돌아오지 않는다.
_UNMARKABLE_METHODS = frozenset({"communicate"})


class _HookCommand(TypedDict, total=False):
    type: str
    command: str


class _HookGroup(TypedDict, total=False):
    matcher: str
    hooks: list[_HookCommand]


class _Settings(TypedDict, total=False):
    hooks: dict[str, list[_HookGroup]]


class _Permissions(TypedDict, total=False):
    deny: list[str]
    ask: list[str]


class _LocalSettings(TypedDict, total=False):
    permissions: _Permissions
    hooks: dict[str, list[_HookGroup]]


class _LocalPlace(NamedTuple):
    """local 설정 파일 하나와 그것을 알릴 이름, 고치는 길."""

    path: Path
    label: str
    fix: str


def _front_matter(text: str) -> str | None:
    match = _FRONT_MATTER.match(text)
    return None if match is None else match.group(1)


def _opens_quote(value: str, index: int) -> bool:
    """YAML 따옴표는 값의 머리나 공백·`[`·`,` 뒤에서만 연다. 낱말 속의 `'`(`it's`)는 아니다."""
    return value[index] in "\"'" and (index == 0 or value[index - 1] in " \t[,")


def _split_patterns(value: str) -> list[str]:
    """쉼표로 가른 패턴들. 중괄호(`*.{ts,tsx}`)와 따옴표 안의 쉼표는 가르지 않는다."""
    items: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ""
    for index, char in enumerate(value):
        if quote:
            quote = "" if char == quote else quote
        elif _opens_quote(value, index):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth = max(depth - 1, 0)
        elif char == "," and depth == 0:
            items.append("".join(current))
            current = []
            continue
        current.append(char)
    items.append("".join(current))
    return items


def _without_yaml_comment(value: str) -> str:
    """YAML 뒷주석(`# 설명`)을 뗀 값. 따옴표 안의 `#` 는 주석이 아니다(`"docs/ #x/**"`).

    따옴표를 벗기기 전의 값에 쓴다. 벗긴 뒤에 쓰면 따옴표가 지키던 ` #` 를 주석으로 자른다.
    """
    quote = ""
    for index, char in enumerate(value):
        if quote:
            quote = "" if char == quote else quote
        elif _opens_quote(value, index):
            quote = char
        elif char == "#" and (index == 0 or value[index - 1] in " \t"):
            return value[:index]
    return value


def _block_items(after_key: str) -> list[str]:
    """`paths:` 줄 뒤의 블록 목록 항목. 빈 줄과 주석 줄은 넘고, 항목이 아닌 줄에서 멈춘다."""
    items: list[str] = []
    for line in after_key.split("\n")[1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = _LIST_ITEM.match(line)
        if item is None:
            break
        items.append(item.group(1))
    return items


def _paths_patterns(text: str) -> list[str] | None:
    """`paths` 의 패턴들. 프론트매터나 키가 없거나 항목이 비었으면 없는 것(`None`)이다.

    공식 문서가 받는 모양 셋을 읽는다. 블록 목록(`- "src/**"`), 흐름 목록(`["src/**", "b/**"]`),
    쉼표로 가른 문자열(`"src/**, b/**"`). 블록 목록은 키와 항목 사이, 항목 사이의 빈 줄과 주석
    줄을 넘는다 — 넘지 못하던 때는 주석 뒤의 항목을 잘라 죽은 glob 을 숨겼다(PR #100 리뷰). 두
    검사가 이 판정을 같이 쓴다. 따로 쓰면 항목 없는 `paths:` 가 둘 다를 빠져나간다.

    이 판정은 YAML 파서가 아니다. 못 보는 것: 여러 줄에 걸친 흐름 목록과 plain 스칼라, 블록
    스칼라(`|`·`>`), 따옴표 친 키, 앵커, `null`, 따옴표 없이 `*` 로 여는 패턴(YAML 에서는 별칭),
    겹친 키(Claude Code 는 뒤의 값을 썼는데 여기서는 앞의 값을 읽는다), 그리고
    YAML 로 읽히지 않는 프론트매터. 마지막 것을 공식 문서는 `paths` 없는 규칙처럼 매 세션
    싣는다고 하지만, 2.1.281 에서 닫히지 않은 흐름 목록(`["sub/**"`)과 따옴표(`"sub/**`)는 시작
    때도 그 경로를 Read 할 때도 실리지 않았다(2026-09-29 실측,
    `.scratch/harness/probes/import_comments/`). 어느 쪽이든 여기서는 살아 있는 glob 으로 보인다.
    """
    front = _front_matter(text)
    if front is None:
        return None
    key = _PATHS_KEY.search(front)
    if key is None:
        return None
    inline = _without_yaml_comment(key.group(1)).strip()
    if inline.startswith("["):
        items = _split_patterns(inline.strip("[]"))
    elif inline:
        items = _split_patterns(inline.strip("\"'"))
    else:
        items = [_without_yaml_comment(item) for item in _block_items(front[key.end() :])]
    patterns = [item.strip().strip("\"'").strip() for item in items]
    return [pattern for pattern in patterns if pattern] or None


def _rule_files(root: Path) -> list[Path]:
    """`.claude/rules/` 아래의 규칙 파일 전부. Claude Code 는 하위 폴더까지 재귀로 싣는다."""
    return sorted((root / ".claude" / "rules").rglob("*.md"))


def rules_without_paths(root: Path = ROOT) -> list[Path]:
    return [
        path
        for path in _rule_files(root)
        if _paths_patterns(path.read_text(encoding="utf-8")) is None
    ]


def rules_with_dead_paths(root: Path = ROOT) -> list[str]:
    """`paths`의 glob마다 저장소에서 하나라도 가리키는지 본다.

    파일을 옮기거나 나누면 그 이름을 적은 규칙이 조용히 안 실린다. 훅과 달리 아무 오류도 나지
    않아서, 판정자가 없으면 아무도 모른다. `paths` 가 없는 파일은 `rules_without_paths` 가 잡는다.

    판정은 `pathlib` 의 glob 이다. 이 저장소의 패턴은 `dir/**` 와 정확한 파일 경로뿐이라 그것으로
    충분하다. 못 보는 것: 중괄호 확장처럼 `pathlib` 이 모르는 문법은 살아 있어도 죽었다고 본다(쓰게
    되면 이 판정을 먼저 넓힌다). `dir/**` 는 빈 디렉터리도 살아 있다고 본다. glob 이 gitignore 된
    로컬 파일을 보고 윈도에서 대소문자를 무시하므로, 로컬 초록이 CI 에서 빨강이 될 수 있다 — 그때는
    CI 가 맞다.
    """
    problems: list[str] = []
    for path in _rule_files(root):
        patterns = _paths_patterns(path.read_text(encoding="utf-8"))
        if patterns is None:
            continue
        rule = path.relative_to(root).as_posix()
        for pattern in patterns:
            try:
                dead = next(root.glob(pattern), None) is None
            except (ValueError, NotImplementedError) as error:
                problems.append(f"{rule}: paths 의 '{pattern}' 를 glob 으로 읽을 수 없다({error})")
                continue
            if dead:
                problems.append(
                    f"{rule}: paths 의 '{pattern}' 가 아무 파일도 가리키지 않는다. 그 규칙이"
                    " 조용히 안 실린다"
                )
    return problems


def _local_problem(place: _LocalPlace) -> str | None:
    """local 설정 파일 하나의 문제. 파일이 없거나 가드가 없으면 None.

    깨진 JSON 은 예외가 아니라 문제로 돌려준다. 주 체크아웃의 local 까지 읽으므로 예외면 이
    워크트리에서 고칠 수 없는 파일 하나가 모든 커밋을 트레이스백으로 막는다.
    """
    if not place.path.exists():
        return None
    try:
        settings: _LocalSettings = json.loads(place.path.read_text(encoding="utf-8"))
    except ValueError:
        return f"{place.label}: JSON 으로 읽을 수 없다. 가드가 있는지 판정하지 못했다. {place.fix}"
    permissions = settings.get("permissions", {})
    guards: list[str] = []
    if permissions.get("deny"):
        guards.append("permissions.deny")
    if permissions.get("ask"):
        guards.append("permissions.ask")
    hooks = settings.get("hooks", {})
    if any(group.get("hooks") for groups in hooks.values() for group in groups):
        guards.append("hooks")
    if not guards:
        return None
    return (
        f"{place.label}: 가드({', '.join(guards)})가 있다. local 은 워크트리에 없어 거기서 연"
        f" 세션에서 조용히 빠진다. {place.fix}"
    )


def _main_checkout(root: Path) -> Path | None:
    """`root` 가 든 저장소의 주 체크아웃. git 저장소가 아니거나 알 수 없으면 None. git 이
    `CALL_TIMEOUT` 초 안에 돌아오지 않은 것도 알 수 없는 것이다.

    워크트리의 공용 git 디렉터리(`<주 체크아웃>/.git`)의 부모다. pre-commit 이 워크트리 커밋에서
    내보내는 `GIT_DIR` 같은 위치 변수가 남으면 `root` 가 아니라 그 저장소를 보므로 `GIT_` 로
    시작하는 변수를 모두 벗긴다(`tools/run_hooks.py` 의 `REPO_LOCATION_VARS` 를 덮는다. 이 도구는
    스크립트로 돌아 그 모듈을 import 하지 못한다, `.claude/rules/tools.md`).
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
            timeout=CALL_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    common = Path(result.stdout.strip())
    if result.returncode != 0 or common.name != ".git":
        return None
    return common.parent


def local_settings_with_guards(root: Path = ROOT) -> list[str]:
    """local 설정에 가드(`permissions.deny`·`permissions.ask`·`hooks`)가 있는지 본다.

    가드 목록이 비지 않았으면 문제다. 훅은 이벤트 이름이 아니라 실제 훅 항목이 있어야 가드다. 깨진
    JSON 도 문제로 낸다. 워크트리에서 돌면 그 워크트리의 local 과 함께 주 체크아웃의 local 도 본다.

    local(`.claude/settings.local.json`)은 추적하지 않는다(이 PC 의 사용자 전역 ignore). 손으로 판
    워크트리에는 없고 EnterWorktree 는 만들 때 한 번 복사하므로, 워크트리 폴더에서 연 세션에서는
    거기 둔 가드가 알림 없이 빠진다(2026-10-05 워크트리 감사 서브에이전트가 워크트리마다 local
    유무를 손으로 대조했다). 가드는 추적하는 `settings.json` 에 두고 local 은 allow 만 든다. 가드를
    잃는 쪽은 주 체크아웃의 local 이다.

    못 보는 것: `env`·`model` 같은 다른 키(사람마다 다를 수 있어 두었다), 사용자 수준
    `~/.claude/settings.json`. CI 체크아웃에는 local 이 없어 이 검사는 pre-commit 에서만 뜻이 있다.
    """
    places = [
        _LocalPlace(
            root / LOCAL_SETTINGS,
            LOCAL_SETTINGS.as_posix(),
            "이 파일을 고친다(가드는 settings.json 으로 옮기고 local 에는 allow 만 둔다)",
        )
    ]
    main = _main_checkout(root)
    if main is not None and main.resolve() != root.resolve():
        places.append(
            _LocalPlace(
                main / LOCAL_SETTINGS,
                f"{(main / LOCAL_SETTINGS).as_posix()}(주 체크아웃)",
                "주 체크아웃의 파일이라 이 워크트리에서 고치지 않고 사람에게 알린다",
            )
        )
    return [problem for place in places if (problem := _local_problem(place)) is not None]


def _hook_commands(root: Path) -> Iterator[tuple[str, str]]:
    """`.claude/settings.json` 의 훅 명령을 (이벤트, 명령) 으로 하나씩 낸다. 설정이 없으면 없다."""
    path = root / SETTINGS
    if not path.exists():
        return
    settings: _Settings = json.loads(path.read_text(encoding="utf-8"))
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                yield event, hook.get("command", "")


def hooks_with_relative_paths(root: Path = ROOT) -> list[str]:
    """훅 명령이 저장소 파일을 상대 경로로 부르는지 본다.

    훅은 세션의 현재 디렉터리에서 돈다. 상대 경로면 세션이 저장소 루트를 벗어나는 순간 스크립트를
    못 찾고, 파이썬은 그때 종료 코드 2 로 끝나는데 PreToolUse 에서 2 는 "막아라" 다. 그래서 경로
    하나가 틀리면 모든 Bash 호출이 막힌다(2026-09-23, PR #52).

    저장소에 실재하는 파일을 가리키는 토큰만 잡는다. 모든 훅에 `${CLAUDE_PROJECT_DIR}` 을 요구하면
    `echo` 나 홈 디렉터리에 쓰는 훅처럼 저장소 파일을 부르지 않는 훅이 커밋을 막는다.

    받는 모양은 경로 앞의 `${CLAUDE_PROJECT_DIR}/` 하나다. 그래서 잡는 것 중에 동작하는 것도 있다 —
    `cd "$CLAUDE_PROJECT_DIR" && python tools/x.py` 처럼 먼저 옮기는 훅, 그리고 저장소 경로를
    데이터로만 쓰는 훅(`grep -q docs/x.md`). 못 보는 것: 백슬래시 경로(`tools\\x.py`),
    루트의 파일을 이름만으로 부르는 것(`python x.py`), `$PWD/…`, 그리고 `uv run` 에
    `--project` 가 빠진 것(저장소 밖에서
    프로젝트가 아니라 시스템 파이썬으로 돈다). 이 넷은 tools/run_hooks.py 가 등록 명령을 한 모양과
    대조해 잡는다(대기열 91). 등록이 래퍼에 넘기는 훅 이름(`hook_x.py`)은 슬래시가 없어 여기서
    경로로 잡지 않는다.
    """
    problems: list[str] = []
    for event, command in _hook_commands(root):
        for token in _PATH_TOKEN.finditer(command):
            relative = token.group(1)
            if (root / relative).is_file():
                problems.append(
                    f"{SETTINGS.as_posix()} 의 {event} 훅이 저장소 파일을 상대 경로로 부른다:"
                    f" {relative}. 훅은 세션의 현재 디렉터리에서 돌아 루트를 벗어나면 못 찾는다."
                    f' "{PROJECT_DIR_PLACEHOLDER}/{relative}" 로 쓴다'
                )
    return problems


def _comment_residual(block: str) -> str:
    """블록 주석 줄들에서 주석 구간을 뺀 나머지(c29·c53).

    짝 없는 `<!--` 는 다음 문단과 짝짓지 않게 지운다.
    """
    return _HTML_COMMENT.sub("", block).replace("<!--", "")


def _block_lines(text: str) -> list[tuple[_Place, str]]:
    """본문의 줄을 (자리, 줄)로 가른다. 펜스와 닫힌 블록 HTML 주석은 빼고 한 줄씩 상태를 넘긴다.

    둘을 따로 지우면 서로의 표지를 잘못 짝짓는다. 주석 안의 ``` 는 펜스가 아니고 펜스 안의
    `<!--` 는 주석이 아니다(사례 c25·c26). 목록 표지 줄에서 연 펜스(`- ```bash`)도 연다 — 모르면
    그 닫는 줄을 여는 줄로 읽는다(c50·c56). 블록 주석의 마지막 `-->` 뒤 글자는 `text` 로
    남긴다(c29). 주석 안의 `@` 는 블록이든 문단 속이든 따라가지 않았다(2026-09-29 claude 2.1.281
    실측, `.scratch/harness/probes/import_comments/`. 블록 주석은 루트 CLAUDE.md·rules·임포트된
    파일에서, 문단 속 주석은 임포트된 파일에서 쟀다). `html` 은 HTML 블록(`<div>` 같은 줄부터 빈
    줄까지)이고 그 안의 ``` 와 `<!--` 는 표지가 아니다. `unclosed` 는 파일 끝까지 닫히지 않은 펜스와
    주석의 줄이다. 두 읽기(`_counted_text`, `_loaded_text`)가 이 자리를 다르게 거른다.
    """
    lines: list[tuple[_Place, str]] = []
    held: list[str] = []
    fence = ""
    in_comment = False
    in_html = False
    for line in text.split("\n"):
        if in_html:
            if not line.strip():
                in_html = False
            lines.append(("html" if in_html else "text", line))
            continue
        if fence:
            held.append(line)
            closing = _FENCE_CLOSE.match(line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence):
                fence, held = "", []
            continue
        if in_comment:
            held.append(line)
            if "-->" in line:
                lines.append(("text", _comment_residual("\n".join(held))))
                in_comment, held = False, []
            continue
        opening = _FENCE_OPEN.match(line)
        if opening:
            fence, held = opening.group(1) or opening.group(2), [line]
            continue
        if _COMMENT_BLOCK_OPEN.match(line):
            if "-->" in line:
                lines.append(("text", _comment_residual(line)))
            else:
                in_comment, held = True, [line]
            continue
        if _HTML_BLOCK_OPEN.match(line):
            in_html = True
            lines.append(("html", line))
            continue
        lines.append(("text", line))
    lines.extend(("unclosed", line) for line in held)
    return lines


def _inline_comment(match: re.Match[str]) -> str:
    """문단 속 주석은 지운다. 들여쓴 코드 블록(빈 줄 뒤 네 칸 이상)에서 연 것은 코드라 둔다.

    문단 바로 뒤의 네 칸 줄은 문단이 이어지는 것이라 코드가 아니다(c04 는 둔다, c48 은 지운다).
    """
    text = match.string
    start = text.rfind("\n", 0, match.start()) + 1
    head = text[start : match.start()].expandtabs(4)
    before = text[: max(start - 1, 0)]
    previous = before[before.rfind("\n") + 1 :] if start else ""
    in_code = len(head) - len(head.lstrip(" ")) >= 4 and not previous.strip()
    return match.group(0) if in_code else " "


def _without_inline(text: str, spans: re.Pattern[str]) -> str:
    """코드 스팬과 문단 속 주석을 뺀다. 문단 속 주석은 빈 줄을 넘지 못한다(c52)."""
    return _INLINE_COMMENT.sub(_inline_comment, spans.sub(" ", text))


def _counted_text(text: str) -> str:
    """임포트를 셀 본문. 확실히 안 실리는 자리만 좁게 뺀다 — 펜스, 닫힌 주석, 한 줄 코드 스팬.

    HTML 블록과 닫히지 않은 펜스·주석은 글자로 둔다. 인라인 태그로 여는 문단(c60)이나 네 칸으로 닫은
    목록 펜스(c59)처럼 표지를 잘못 읽어도 뒤의 임포트가 숨지 않게 하려는 것이다. 코드 스팬이 줄을
    넘으면 들여쓴 코드 줄의 ``` 끼리 짝지어 사이의 임포트를 숨긴다(c40).
    """
    counted = "\n".join(line for _place, line in _block_lines(text))
    return _without_inline(counted, _INLINE_CODE)


def _loaded_text(text: str) -> str:
    """허용 임포트가 실리는지 볼 본문. 넓게 뺀다 — HTML 블록(c11), 닫히지 않은 펜스와 주석
    (c06·c07), 줄을 넘는 코드 스팬(c10·c49)까지. 헌법 줄은 이 본문에도 남아야 한다.
    """
    loaded = "\n".join(line for place, line in _block_lines(text) if place == "text")
    return _without_inline(loaded, _INLINE_CODE_LINES)


def at_imports(text: str) -> list[str]:
    """본문이 임포트하는 `@경로` 전부. 줄 머리든 문장 속이든 같다.

    2026-09-28 까지는 `line.startswith("@")` 만 봐서 "자세한 것은 @docs/PRD.md" 같은 한 구절이
    파일 하나를 매 세션 통째로 싣는데 검사는 초록이었다. 무엇을 세는지는 `_IMPORT_TOKEN` 이다.
    끝의 마침표는 토큰에 든다 — 그것을 떼어 맞추던 때는 실리지 않는
    `@docs/constitution/principles.md.` 가 허용 목록을 통과했다.

    Claude Code 는 marked 렉서의 토큰에서 임포트를 찾고 이 판정은 줄과 정규식으로 흉내 낸다.
    그래서 본문을 두 번 읽는다. 여기는 좁게 뺀 본문(`_counted_text`)에서 센다. 허용된 임포트가
    실리는지는 `claude_md_problems` 가 넓게 뺀 본문(`_loaded_text`)에서 본다. 어느 쪽이 틀려도
    빨강으로 틀린다. 못 보는 것(2026-09-29 실측, 괄호는 `.scratch/harness/probes/import_comments/`
    의 사례 id). 실리지 않는데 세는 자리(거짓 빨강) — HTML 블록(c37), 들여쓴 코드 블록(c34),
    인용문 안의 펜스(c36), 프론트매터(c38), 그리고 추론으로 네 칸 이상 들여쓴 목록 속 펜스. 실리는데
    세지 않는 자리(거짓 초록) — 굵게·링크 글자·인라인 태그(c42~c44), `#` 조각이나 한글이 든
    경로(c45·c46).
    """
    return ["@" + match.group(1) for match in _IMPORT_TOKEN.finditer(_counted_text(text))]


def claude_md_problems(root: Path = ROOT) -> list[str]:
    text = (root / "CLAUDE.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    problems: list[str] = []
    if len(lines) > MAX_LINES:
        problems.append(f"CLAUDE.md {len(lines)}줄 > {MAX_LINES}줄. 로드 시점 표로 다시 나눈다")
    imports = at_imports(text)
    if imports != ALLOWED_IMPORTS:
        problems.append(
            f"CLAUDE.md의 @ 임포트는 {ALLOWED_IMPORTS}뿐이어야 한다. 지금: {imports}."
            " 문장 속 @경로 도 임포트다. 가리키려면 백틱에 넣는다"
        )
    # 허용된 임포트는 실려야 한다. 넓게 뺀 본문에도 한 줄 단독으로 남아야 한다. 인용문·목록·문장
    # 속도 실렸지만 받지 않는다.
    visible = [line.rstrip() for line in _loaded_text(text).split("\n")]
    for allowed in ALLOWED_IMPORTS:
        if allowed not in visible:
            problems.append(
                f"CLAUDE.md의 {allowed} 는 주석과 코드 밖의 한 줄에 단독으로, 들여쓰지 않고"
                " 적는다. 이 검사가 받는 모양은 그것 하나다(주석·펜스 안이면 헌법이 실리지 않는다)"
            )
    return problems


def imports_outside_claude_md(root: Path = ROOT) -> list[str]:
    """rules 파일과 임포트된 파일 안의 `@경로`.

    임포트는 루트 `CLAUDE.md` 에서만 일어나지 않는다. 규칙 파일과 임포트된 파일 안의 `@경로` 도
    따라가서 통째로 실린다(2026-09-29 `claude -p` 2.1.281 실측, 공식 문서: 최대 네 단계 재귀).
    `CLAUDE.md` 의 허용 목록만 보면 그 문이 열려 있다. 판정은 `at_imports` 와 같다.
    """
    imported_files = [root / imported[1:] for imported in ALLOWED_IMPORTS]
    targets = _rule_files(root) + [path for path in imported_files if path.is_file()]
    problems: list[str] = []
    for path in targets:
        imports = at_imports(path.read_text(encoding="utf-8"))
        if imports:
            problems.append(
                f"{path.relative_to(root).as_posix()}: @ 임포트 {imports}. rules 와 임포트된 파일"
                " 안의 @경로 도 통째로 실린다(CLAUDE.md 의 허용 목록 밖). 가리키려면 백틱에 넣는다"
            )
    return problems


def _looks_like_path(token: str) -> bool:
    if _PATHISH.match(token) is None:
        return False
    return "/" in token or token.endswith(PATH_EXTENSIONS)


def _exists(root: Path, token: str) -> bool:
    if "*" in token:
        return next(root.glob(token), None) is not None
    if token.endswith("/"):
        return (root / token).is_dir()
    return (root / token).exists()


def imported_files_with_dead_paths(root: Path = ROOT) -> list[str]:
    """임포트된 파일의 백틱 경로가 저장소 루트 기준으로 실재하는지 본다.

    `@` 임포트의 상대 경로는 그 임포트를 담은 파일 기준으로 풀린다(공식 memory 문서). 그러나 백틱
    경로는 임포트가 아니라 모델이 읽는 글자이고, 모델은 그것을 작업의 자리인 루트 기준으로 읽었다.
    `principles.md` 가 형제 `README.md` 를 이름만으로 가리켰을 때 루트 README 로 읽혀 PR #43 이 헌법
    버전을 찾지 못했다(대기열 9·32). 경로로 보는 것은 슬래시가 있거나 `PATH_EXTENSIONS` 로 끝나는
    백틱 토큰이다. 못 보는 것: 백틱 없는 경로, 이름이 우연히 루트에도 있는 형제 파일(그때는 있다고
    보고 지나간다).
    """
    problems: list[str] = []
    for imported in ALLOWED_IMPORTS:
        relative = imported[1:]
        path = root / relative
        if not path.is_file():
            problems.append(f"CLAUDE.md 가 임포트하는 {relative} 이 없다")
            continue
        for token in _CODE_SPAN.findall(path.read_text(encoding="utf-8")):
            if _looks_like_path(token) and not _exists(root, token):
                problems.append(
                    f"{relative}: `{token}` 이 저장소 루트 기준으로 없다. 백틱 경로는 모델이 루트"
                    " 기준으로 읽으므로 형제 파일도 전체 경로로 적는다"
                )
    return problems


def patched_skills_without_sentinel(root: Path = ROOT) -> list[str]:
    """덧댄 사본이 `npx skills update -p`에 덮어써졌는지 본다.

    무엇을 덧댔는지는 각 파일의 `<!-- 프로젝트 사본 ... -->` 주석이 기록한다.
    주석이 사라졌으면 사본이 원본으로 되돌아간 것이고, 그 뒤로도 리뷰는 초록이다.
    """
    problems: list[str] = []
    for name in PATCHED_SKILLS:
        path = root / ".claude" / "skills" / name / "SKILL.md"
        if not path.exists():
            problems.append(f".claude/skills/{name}/SKILL.md 없음. 사본이 사라졌다")
        elif SENTINEL not in path.read_text(encoding="utf-8"):
            problems.append(
                f".claude/skills/{name}/SKILL.md에 '{SENTINEL}' 주석 없음."
                " npx skills update가 덧댄 것을 되돌렸다"
            )
    return problems


def skills_with_sentinel_not_listed(root: Path = ROOT) -> list[str]:
    """센티널을 지닌 사본이 `PATCHED_SKILLS` 밖에 있는지 본다. 앞 검사의 역방향이다.

    목록은 손으로 유지된다. 사본을 새로 덧대며 주석은 붙이고 목록은 잊으면, 그 사본은 앞 검사가
    보지 않아 `npx skills update -p` 가 되돌려도 초록이다(2026-09-28 감사). 주석을 붙이는 커밋에서
    걸리므로 사람이 기억할 것이 없다.
    """
    problems: list[str] = []
    for path in sorted((root / ".claude" / "skills").glob("*/SKILL.md")):
        name = path.parent.name
        if name in PATCHED_SKILLS:
            continue
        if SENTINEL in path.read_text(encoding="utf-8"):
            problems.append(
                f".claude/skills/{name}/SKILL.md 에 '{SENTINEL}' 주석이 있는데"
                " tools/check_instructions.py 의 PATCHED_SKILLS 에 없다. 목록 밖의 사본은"
                " 되돌려져도 검사가 초록이다"
            )
    return problems


def _is_sys_stdin(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "stdin"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def text_stdin_lines(source: str) -> list[int]:
    """`sys.stdin.buffer` 가 아닌 `sys.stdin` 과 `from sys import stdin` 이 나오는 줄들.

    못 보는 것: `import sys as s` 뒤의 `s.stdin`, `open(0)`, `io.TextIOWrapper(...)` 로 다시 감싼
    것. 훅이 그렇게 쓸 이유가 없어 닫지 않았다. 생기면 여기서 넓힌다.
    """
    tree = ast.parse(source)
    buffered = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "buffer" and _is_sys_stdin(node.value)
    }
    lines = {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and _is_sys_stdin(node) and id(node) not in buffered
    }
    lines.update(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "sys"
        and any(alias.name == "stdin" for alias in node.names)
    )
    return sorted(lines)


def hooks_reading_text_stdin(root: Path = ROOT) -> list[str]:
    """훅이 stdin 을 텍스트로 읽는지 본다.

    훅 프로세스에 `PYTHONUTF8` 이 없으면 텍스트 stdin 이 cp949 로 읽힌다. 한글이 든 페이로드는
    깨져서 매치되지 않고, 예외 없이 exit 0·출력 0바이트로 끝나 "발동 조건 아님" 과 구별되지 않는다
    (PR #60 에서 변이로 실측, 대기열 25). 판정은 AST 라 독스트링의 낱말은 세지 않는다.
    """
    problems: list[str] = []
    for path in sorted((root / "tools").glob("hook_*.py")):
        for lineno in text_stdin_lines(path.read_text(encoding="utf-8")):
            problems.append(
                f"{path.relative_to(root).as_posix()}:{lineno}: sys.stdin 을 텍스트로 읽는다."
                " 훅 환경은 cp949 라 한글이 깨진다. json.load(sys.stdin.buffer) 로 읽는다"
            )
    return problems


def _subprocess_names(tree: ast.Module) -> tuple[set[str], dict[str, str]]:
    """`subprocess` 모듈을 가리키는 이름(별칭 포함)과, 거기서 가져온 기다리는 함수의 이름(별칭 →
    원래 이름)."""
    modules: set[str] = set()
    functions: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(
                alias.asname or alias.name for alias in node.names if alias.name == "subprocess"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            functions.update(
                (alias.asname or alias.name, alias.name)
                for alias in node.names
                if alias.name in _WAITING_FUNCTIONS
            )
    return modules, functions


def _waiting(
    call: ast.Call, modules: set[str], functions: dict[str, str]
) -> tuple[bool, int | None]:
    """외부 명령을 기다리는 호출인지와, timeout 이 들어가는 위치 인자의 자리(키워드로만 받으면
    None)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in functions, None
    if not isinstance(func, ast.Attribute):
        return False, None
    if isinstance(func.value, ast.Name) and func.value.id in modules:
        return func.attr in _WAITING_FUNCTIONS, None
    if func.attr in _WAITING_METHODS:
        return True, _WAITING_METHODS[func.attr]
    return False, None


def _is_limit(value: ast.expr) -> bool:
    """timeout 으로 준 값이 시간 제한인가. 글자 그대로의 None 만 아니다."""
    return not (isinstance(value, ast.Constant) and value.value is None)


def _has_timeout(call: ast.Call, position: int | None) -> bool:
    for keyword in call.keywords:
        if keyword.arg == "timeout":
            return _is_limit(keyword.value)
    if position is None or len(call.args) <= position:
        return False
    if any(isinstance(arg, ast.Starred) for arg in call.args[: position + 1]):
        return False
    return _is_limit(call.args[position])


def _marked_lines(source: str) -> set[int]:
    """까닭을 적은 표지 주석이 있는 줄. 주석은 토큰으로 읽어 문자열 속 글자는 세지 않는다."""
    return {
        token.start[0]
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT and _NO_TIMEOUT_MARKER.match(token.string)
    }


def untimed_call_lines(source: str) -> list[tuple[int, str]]:
    """외부 명령을 시간 제한 없이 기다리는 호출의 줄과 부른 이름. 판정은 `calls_without_timeout`."""
    tree = ast.parse(source)
    modules, functions = _subprocess_names(tree)
    marked = _marked_lines(source)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        waiting, position = _waiting(node, modules, functions)
        if not waiting or _has_timeout(node, position):
            continue
        markable = not (
            isinstance(node.func, ast.Attribute) and node.func.attr in _UNMARKABLE_METHODS
        )
        span = range(node.lineno, (node.end_lineno or node.lineno) + 1)
        if markable and marked.intersection(span):
            continue
        found.append((node.lineno, ast.unparse(node.func)))
    return sorted(found)


def tool_sources(root: Path = ROOT) -> list[Path]:
    """시간 제한 검사가 훑는 파일. `tools/` 아래(하위 폴더까지)의 파이썬이다."""
    return sorted(
        (root / "tools").rglob("*.py"), key=lambda path: path.relative_to(root).as_posix()
    )


def calls_without_timeout(root: Path = ROOT) -> list[str]:
    """`tools/` 의 파이썬에서 외부 명령을 기다리는 호출에 시간 제한이 있는지 본다(대기열 342).

    `subprocess` 의 `run`·`call`·`check_call`·`check_output` 과 `communicate`·`wait` 메서드에
    `timeout` 이 없거나 글자 그대로 None 이면 문제다. `.claude/rules/tools.md` 는 기다리거나
    되풀이하는 도구가 부르는 외부 명령에 호출마다 시간 제한을 두라고 한다. 루프의 시간 제한은
    호출이 돌아와야 비교되므로 멈춘 호출을 끊지 못한다. 그 항목을 `tools/run_checks.py` 의
    `run_one` 이 멈추는 중에 거절한 검사의 `process.communicate()` 에서 어겼고, 셀프 리뷰를 지나
    PR 직전 `bug-perf-review` 가 잡았다(일지 2026-10-17-12). 어느 도구가 기다리는 도구인지는
    AST 로 가를 수 없어 `tools/` 전부에 건다.

    기다릴 일이 없는 자리(끝낸 자식을 거두는 `wait`)와 끊으면 안 되는 자리(지우는 git 을 도중에
    끊으면 지우다 만 폴더가 남는다)는 그 호출이 걸친 줄에 `# 시간 제한 없음: <까닭>` 주석을 달아
    뺀다. 주석의 머리여야 하고 까닭이 비면 빼지 않는다. `communicate` 는 표지로 빼지 않는다. 끝낸
    뒤에도 트리를 떠난 손자가 파이프를 쥐면 돌아오지 않아(위 사건) timeout 으로 거둔다. 들인
    때(2026-10-19) 잡힌 열셋 가운데 넷이 표지를 단 자리였고 나머지 아홉에는 시간 제한을 더했다.

    잘못 막는 것: 받는 쪽의 형을 보지 않아 `threading.Event().wait()` 같은 다른 `wait` 와
    `communicate` 도 잡는다. 그것도 끝없이 기다리므로 같게 다룬다. `asyncio` 하위 프로세스의
    `wait`·`communicate` 는 timeout 을 받지 않아 `asyncio.wait_for` 로 감싸도 잡히고,
    `communicate` 는 표지로도 뺄 수 없다. 지금 `tools/` 에는 asyncio 가 없어 들일 때 이 판정을
    함께 고친다. `*`·`**` 로 펼친 인자는 timeout 이 든지 몰라 없는 것으로 본다.

    못 보는 것: 변수에 담아 부른 함수(`runner = subprocess.run`), `getattr` 으로 꺼낸 것, 모듈을
    다른 이름에 대입한 것(`sp = subprocess`), `from subprocess import *` 뒤의 이름,
    `getoutput`·`getstatusoutput`(timeout 을 받지 않는다), `with Popen(...)` 이 빠져나갈 때의
    암묵 `wait`, `Popen` 의 파이프를 직접 읽는 것(`process.stdout.read()`, `for line in
    process.stdout`), `os.system`·`os.popen`·`os.waitpid`, `functools.partial` 로 감싼 함수,
    timeout 에 준 변수나 식의 값이 None 인 것(`timeout=None if slow else 5`). 표지는 줄 단위라
    표지가 걸린 줄의 다른 호출도 함께 뺀다. `tests/` 는 보지 않는다.
    """
    problems: list[str] = []
    for path in tool_sources(root):
        relative = path.relative_to(root).as_posix()
        for lineno, name in untimed_call_lines(path.read_text(encoding="utf-8")):
            problems.append(
                f"{relative}:{lineno}: {name} 에 timeout 이 없다. 멈춘 외부 명령은 루프의 시간"
                " 제한으로 끊지 못한다. timeout 을 주고 넘김을 실패 갈래로 세거나, 기다릴 일이"
                " 없거나 끊으면 안 되는 자리면 그 호출에 '# 시간 제한 없음: <까닭>' 주석을 단다"
                "(.claude/rules/tools.md)"
            )
    return problems


def _parsed(node: ast.expr) -> ast.expr:
    """문자열로 쓴 주해는 표현식으로 다시 읽는다. 읽지 못하거나 문자열이 아니면 그대로다."""
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return node
    try:
        return ast.parse(node.value.strip(), mode="eval").body
    except SyntaxError:
        return node


def _union_members(node: ast.expr) -> list[ast.expr] | None:
    """합 주석의 갈래들. 합이 아니면 None 이다.

    `a | b`, `Optional[a]`(`a` 와 None), `Union[a, b]` 를 펴고, 갈래가 다시 합이거나 문자열이면
    그것도 끝까지 편다.
    """
    match _parsed(node):
        case ast.BinOp(left=left, op=ast.BitOr(), right=right):
            direct = [left, right]
        case ast.Subscript(value=base, slice=inner) if _typing_name(base) == "Optional":
            direct = [inner, ast.Constant(value=None)]
        case ast.Subscript(value=base, slice=ast.Tuple(elts=elements)) if (
            _typing_name(base) == "Union"
        ):
            direct = list(elements)
        case _:
            return None
    flat: list[ast.expr] = []
    for member in direct:
        flat.extend(_union_members(member) or [_parsed(member)])
    return flat


def _typing_name(node: ast.expr) -> str | None:
    """`Optional` 도 `typing.Optional` 도 `tp.Optional` 도 같은 이름으로 본다."""
    match node:
        case ast.Name(id=name) | ast.Attribute(attr=name):
            return name
        case _:
            return None


def _member_kind(node: ast.expr) -> str | None:
    match node:
        case ast.Name(id="bool"):
            return "bool"
        case ast.Constant(value=None):
            return "None"
        case _:
            return None


def _is_optional_bool(annotation: ast.expr) -> bool:
    """주석이 `bool` 과 None 두 갈래만으로 된 합인가."""
    members = _union_members(annotation)
    if members is None:
        return False
    return {_member_kind(member) for member in members} == {"bool", "None"}


def _annotated_slots(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[tuple[ast.expr, str]]:
    """함수의 주석 자리와 그 이름. 매개변수 다섯 갈래와 반환이다."""
    arguments = function.args
    every = [
        *arguments.posonlyargs,
        *arguments.args,
        *([arguments.vararg] if arguments.vararg else []),
        *arguments.kwonlyargs,
        *([arguments.kwarg] if arguments.kwarg else []),
    ]
    for argument in every:
        if argument.annotation is not None:
            yield argument.annotation, f"{function.name} 의 {argument.arg}"
    if function.returns is not None:
        yield function.returns, f"{function.name} 의 반환"


def optional_bool_lines(source: str) -> list[tuple[int, str]]:
    """`bool | None` 주석의 줄과 자리(`<함수> 의 <매개변수>`·`<함수> 의 반환`). 판정은
    `optional_bool_annotations`.
    """
    found: list[tuple[int, int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for annotation, place in _annotated_slots(node):
            if _is_optional_bool(annotation):
                found.append((annotation.lineno, annotation.col_offset, place))
    return [(line, place) for line, _, place in sorted(found)]


def optional_bool_sources(root: Path = ROOT) -> list[Path]:
    """`bool | None` 검사가 훑는 파일. `OPTIONAL_BOOL_ROOTS` 아래(하위 폴더까지)의 파이썬이다."""
    return sorted(
        (path for directory in OPTIONAL_BOOL_ROOTS for path in (root / directory).rglob("*.py")),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def optional_bool_annotations(root: Path = ROOT) -> list[str]:
    """매개변수와 반환의 주석이 `bool` 과 None 두 갈래인 자리(대기열 423).

    세 값(`True`·`False`·`None`)으로 출력을 고르는 꼴이다. `CODING_STANDARDS.md` 의 불리언 플래그
    줄이 막는 것인데, ruff FBT 는 키워드 전용 매개변수를 보지 않는다. 그래서
    `tools/hook_choice_facts.py` 의 `output_for(..., first: bool | None)` 이 셀프 리뷰 표준 축까지
    지나갔고 `Seen` 열거로 고쳤다(일지 2026-10-22-11). 갈래는 열거(`enum.Enum`)로 둔다.

    잡는 모양: `bool | None`, `None | bool`, `Optional[bool]`, `Union[bool, None]`(`Optional`·
    `Union` 은 `typing.`·별칭 접두를 가리지 않는다), 같은 갈래를 거듭 쓴 `bool | None | None`, 합
    안의 합(`Optional[bool | None]`, `Union[bool, Optional[bool]]`), 그리고 주석 전체나 갈래 하나를
    문자열로 쓴 주해(`'bool | None'`, `Optional['bool']`. 앞뒤 공백은 벗긴다). 자리는
    함수(`async def` 포함)의 위치 전용·위치·`*args`·키워드 전용·`**kwargs` 매개변수와 반환이다. 훑는
    범위는 `OPTIONAL_BOOL_ROOTS`(pyright 의 `include` 와 같다. 시험이 맞댄다)이고,
    `.scratch/**/probes/` 는 pyright 와 타입 우회 검사처럼 보지 않는다. 들인 때(2026-10-23) 잡힌
    곳은 범위 안에 하나(`tools/canary.py` 의 `_registered` 반환. 열거로 고치며 이름을
    `_registration` 으로 바꿨다), probes 에 셋이었다(probes 는 이 판정 함수를 커밋하지 않은
    스크립트로 돌려 손으로 셌다).

    잘못 막는 것: "모른다" 를 None 으로 돌려주는 반환도 잡는다. 그것도 세 갈래이므로 열거로 둔다.
    뺄 표지는 두지 않았다. 들인 때 범위 안에서 잡힌 하나가 바로 그 반환이었고 열거로 고쳤다.
    이름 `Optional`·`Union` 이 typing 의 것인지 보지 않아, 같은 이름의 다른 것으로 쓴 주석도
    잡는다.

    못 보는 것: 함수의 매개변수와 반환만 보고, 합이 아닌 것으로 감싸면 안을 열지 않는다. 감싼
    주석(`list[bool | None]`, `Annotated[bool | None, ...]`), 별칭(`Flag = bool | None` 뒤의
    `x: Flag`), 변수와 클래스 칸(데이터클래스 칸 포함)의 주석(`seen: bool | None`)은 지나간다.
    갈래는 이름 `bool` 과 상수 None 으로만 알아봐서 `builtins.bool | None` 과 `bool | NoneType`
    도 지나간다. 세 갈래가 아닌 합(`bool | int | None`)은 이 검사의 대상이 아니다.
    """
    problems: list[str] = []
    for path in optional_bool_sources(root):
        relative = path.relative_to(root).as_posix()
        for lineno, place in optional_bool_lines(path.read_text(encoding="utf-8")):
            subject = f"{place}이" if place.endswith("반환") else f"{place} 가"
            problems.append(
                f"{relative}:{lineno}: {subject} bool | None 이다. 세 값으로 갈래를 고르는 꼴이라"
                " 열거(enum.Enum)로 둔다(CODING_STANDARDS.md 불리언 플래그 인자)"
            )
    return problems


def nested_instruction_files(root: Path = ROOT) -> list[str]:
    """루트 밖의 `CLAUDE.md` 와 `AGENTS.md`.

    지침은 `.claude/rules/*.md` + `paths` 에 둔다(`CLAUDE.md` 의 로드 시점 표). 하위 디렉터리의
    `CLAUDE.md` 는 Claude 가 그 디렉터리의 파일을 Read 할 때 통째로 실리고(cwd 가 그 디렉터리면 시작
    시), 그 안의 `@` 임포트도 따라온다. 그래서 루트 지침에 거는 검사(200줄, 임포트 허용 목록) 밖에
    놓인다(2026-09-29 `claude -p` 2.1.281 실측). `next dev` 는 에이전트를 감지하면 앱 폴더에
    두 파일을 만든다(agent-os ADR 0021). `agentRules: false` 가 그것을 끄지만, 설정 한 줄을 보는
    테스트보다 결과를 보는 검사가 원인과 무관하게 잡는다.

    작업 트리를 훑으므로 pre-commit 은 추적하지 않는 파일도 보고, CI 는 체크아웃된 것(추적하는
    것)만 본다. 보지 않는 곳: 어느 깊이든 `node_modules`, 루트의 `.venv` 와 `.git`(설치된
    의존성과 git 의 것이라 이 저장소의 지침이 아니다), `.claude/worktrees`(다른 체크아웃의 루트
    `CLAUDE.md`). 못 보는 것: 대소문자가 다른 이름(`claude.md`), 다른 도구의 지침 파일
    이름(`GEMINI.md`, `.cursorrules`), 하위 디렉터리의 `CLAUDE.local.md` 와 `.claude/rules/`
    (공식 문서상 이것들도 그 디렉터리에서 실린다).
    """
    skipped = {root / ".venv", root / ".git", root / ".claude" / "worktrees"}
    found: list[str] = []
    for directory, subdirectories, files in os.walk(root):
        current = Path(directory)
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name != "node_modules" and current / name not in skipped
        )
        if current == root:
            continue
        found.extend(
            (current / name).relative_to(root).as_posix()
            for name in NESTED_INSTRUCTION_FILES
            if name in files
        )
    return [
        f"{path}: 루트 밖의 지침 파일이다. 지침은 .claude/rules/*.md + paths 에 둔다"
        "(CLAUDE.md 의 로드 시점 표)."
        for path in sorted(found)
    ]


def main(root: Path = ROOT) -> int:
    """검사 열을 모아 돈다. `root` 는 CLI 첫 인자로도 받는다(임시 트리에서 빨강을 재는 테스트)."""
    problems = [
        f"{path.relative_to(root)}: paths 프론트매터 없음. 없으면 매 세션 실린다"
        for path in rules_without_paths(root)
    ]
    problems.extend(rules_with_dead_paths(root))
    problems.extend(hooks_with_relative_paths(root))
    problems.extend(local_settings_with_guards(root))
    problems.extend(claude_md_problems(root))
    problems.extend(imported_files_with_dead_paths(root))
    problems.extend(patched_skills_without_sentinel(root))
    problems.extend(skills_with_sentinel_not_listed(root))
    problems.extend(hooks_reading_text_stdin(root))
    problems.extend(calls_without_timeout(root))
    problems.extend(optional_bool_annotations(root))
    problems.extend(nested_instruction_files(root))
    problems.extend(imports_outside_claude_md(root))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT))
