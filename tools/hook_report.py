"""세션 기록에서 훅마다 알린 수와 막은 수를 센다.

retro가 새 훅·검사를 승인하기 전과 모델이 바뀐 뒤(`docs/model-selection.md` 4절)에 뺄 후보를 고르는
자리다(ADR 0036). 하네스는 더하는 장치만 있고 쓰이는지 재는 장치가 없었다. 훅 래퍼
(`tools/launch_hook.py`)에 기록을 더하지 않은 것은 래퍼가 훅의 출력을 바꾸지 않는다는 불변식
때문이고, Claude Code가 이미 세션 기록에 훅의 출력을 남기기 때문이다.

판정.
- 기록: `--projects`(기본 `~/.claude/projects`) 아래 이 저장소의 폴더, 곧 주 체크아웃의 경로로 지은
  이름(`--repo`)의 폴더와 그 이름 뒤에 `--claude-worktrees-`가 붙은 워크트리 폴더의 `*.jsonl` 전부다
  (서브에이전트 기록이 든 하위 폴더도 읽는다). 같은 `uuid`의 기록은 파일이 달라도 한 번 센다. 줄바꿈
  없는 마지막 줄은 쓰는 중일 수 있어 버린다.
- 훅 명령: `launch_hook.py <훅>`이거나, 래퍼 전의 등록 모양처럼 `tools/<훅>`을 바로 부르는 것이다.
- 알림: `hook_success` 첨부 가운데 명령이 훅 명령이고 stdout이 빈 글이 아닌 것. 이 첨부는 출력을 낸
  훅만 남는다. stderr만 낸 것(uv의 가상 환경 경고)과 래퍼가 훅을 돌리지 않고 지나간 알림(훅 파일이
  없다, 훅 이름 인자가 하나가 아니다. `launch_hook.skip_reason`의 두 문구)은 세지 않는다(2026-10-19
  이 PC의 기록에서 손으로 봤다).
- 계기 첨부: 모델에게 간 계기(`additionalContext`)는 명령 없는 `hook_additional_context` 첨부로도
  남는다. 첨부 하나를 같은 세션·이벤트에서 같은 글을 stdout(JSON)의 `additionalContext`로 낸
  `hook_success` 하나(명령을 가리지 않는다. 플러그인 훅도)와 짝지어 뺀다. 짝을 `toolUseID`로 짓지
  않는 것은 SessionStart의 첨부는 그 자리가 이벤트 이름이라 `hook_success`의 것과 달라서다.
  UserPromptSubmit(`PROMPT_EVENT`)의 계기는 첨부로만 남고 `hook_success`가 없어(대기열 404), 그
  이벤트의 짝 없는 첨부는 그 이벤트에 등록된 훅의 조각과만 아래 막음처럼 견주어(`fragment_owner`)
  그 훅의 알림으로 센다. 다른 이벤트에서는 이 저장소의 훅이 `hook_success`를 남겨 짝이 있으니, 짝
  없는 첨부는 `UNKNOWN` 알림이다. 이벤트를 가리지 않고 모든 훅의 조각과 견주던 판은 앱의 글에 든
  낱말(경로의 `scratchpad`, `PostToolUse`)이 10자 이상 조각과 맞아 그 훅의 알림이나 `AMBIGUOUS`로
  셌다(셀프 리뷰가 이 PC의 기록에서 손으로 봤다, 일지 2026-10-23-19). 래퍼의 두 문구는 세지
  않는다. 2026-10-23 이 PC의 기록 5430개를 커밋하지 않은 스크래치 스크립트로 손으로 봤다. 계기를
  낸 `hook_success`는 모두 짝이 있었고, 짝 없는 첨부는 UserPromptSubmit 462건(모두
  `hook_prompt_directive`의 조각으로 갈렸다)과 앱이 넣은 글(SessionStart 72건, PostToolUse
  15건)이었다. 사용자에게 간 글의 `hook_system_message` 첨부는 모두 같은 글의 `hook_success`와
  짝이 있어 읽지 않는다.
- 막음: 도구 호출을 막은 훅은 첨부를 남기지 않고 도구 결과의
  `<이벤트>:<도구> hook error: <이유>`에만 이유가 남는다. 종료 코드 2로 막았으면 이유가
  `[<명령>]: `로 시작해 그 명령의 훅으로 센다. 아니면 이유에 든 글을 등록된 훅 파일의 문자열
  조각(독스트링을 뺀 문자열 상수와 f-문자열의 고정된 부분 가운데 `MIN_FRAGMENT`자 이상)과 견주어
  가장 긴 조각이 든 훅으로 센다. 가장 긴 조각이 두 훅에 같은 길이로 있으면 `AMBIGUOUS`, 든 조각이
  없으면 `UNKNOWN`이다. Stop 등이 막은 `hook_blocking_error` 첨부는 명령을 들어 그 명령의 훅으로
  센다. `UNKNOWN`과 `AMBIGUOUS`는 알림과 막음으로 나눠 표 밖에 글의 머리와 함께 적는다.
- 창: 기록 시각의 UTC 날짜가 `--today`(기본 UTC 오늘)로 끝나는 `--days`(기본 28)일 안.
- 등록 훅: `<루트>/.claude/settings.json`의 명령에서 뽑는다. 들인 날은
  `git log --diff-filter=A`가 그 파일을 마지막으로 더한 커밋의 날짜다(지웠다가 다시 들인 훅은 다시
  들인 날이다).
- 뺄 후보: 창의 첫날보다 먼저 들였고 창 안에서 알리지도 막지도 않은 등록 훅. 창 안에 들인 훅과 들인
  날을 모르는 훅은 따로 적는다. 손상을 막는 훅은 0건이어도 남긴다. 그 판정은 retro 4단계가 한다.
  기록이 하나도 없거나 가장 이른 기록이 창의 첫날보다 늦으면 후보를 판정하지 않는다. 기록이 빈 날의
  발동은 0으로 보여 조용한 훅이 모두 후보가 된다.
- 읽는 사이 사라졌거나 열지 못한 기록 파일은 건너뛰고 머리 줄에 센다.

못 보는 것.
- 알림을 읽은 모델이 따랐는지는 모른다. 무시된 알림도 한 번으로 센다.
- 막는 훅의 이유나 짝 없는 UserPromptSubmit 계기 글이 그 훅 파일 밖(다른 모듈, 실행 중에 읽은
  파일)의 글로만 지어지면 `UNKNOWN`이다. 그래서 훅 페이로드 표의 막는 사례와 UserPromptSubmit 훅의
  계기 사례마다 그 글을 이 도구가 그 훅으로 세는지 시험이 본다.
- 훅이 이유나 계기 문장을 바꾸면 그 전의 막음과 짝 없는 UserPromptSubmit 알림은 지금 파일의 조각과
  맞지 않아 `UNKNOWN`이다. 2026-10-19 이 PC의 기록에서 `hook_bash_python_stub`의 옛 이유
  (2026-09-22~09-28 판의 "Git Bash 의 python 은") 24건이 그랬다.
- 막은 이유에 다른 훅의 조각이 더 길게 인용되면 그 훅으로 센다. 짝 없는 UserPromptSubmit 첨부는
  조각으로만 훅을 가르므로, 그 이벤트의 훅 조각이 든 다른 글(앱이 그 이벤트에 넣은 글이 있다면)도
  그 훅의 알림으로 센다.
- stdout이 JSON이 아니거나 `additionalContext`가 없는 `hook_success`는 짝이 되지 못해, 같은 글의
  첨부가 짝 없는 첨부로 남아 그 알림을 한 번 더 센다(UserPromptSubmit 밖이면 `UNKNOWN` 알림으로).
  이 저장소의 훅은 JSON을 낸다.
- 같은 uuid의 기록이 다른 세션 id로 여러 기록 파일에 있다(2026-10-23 이 PC의 훅 첨부 172개, 손으로
  봤다). 같은 uuid는 처음 읽은 것만 세므로, 앞 파일에 `hook_success`만 다른 세션 id로 적혀 있으면
  뒤 파일의 첨부가 짝을 잃어 한 번 더 센다(UserPromptSubmit 밖이면 `UNKNOWN` 알림으로).
- pre-commit과 CI의 검사는 세지 않는다(세션 기록에 없다). `tools/` 밖의 훅(플러그인 훅)의 알림도
  세지 않는다(그 계기 첨부는 그 훅의 `hook_success`와 짝지어 뺀다). 그 훅이나 앱이 도구 호출을
  막은 것과 앱이 `hook_success` 없이 넣은 계기(SessionStart의 세션 안내 등)는 `UNKNOWN`으로 센다.
- 기록 보존 기한(Claude Code 의 `cleanupPeriodDays`, 기본 30일)보다 긴 창은 앞쪽이 비어 0으로 센다.
  그래서 가장 이른 기록 날짜를 함께 찍고, 그 날이 창의 첫날보다 늦으면 비어 있는 날 수를 적고 뺄
  후보는 판정하지 않는다.
- 카나리아 체크아웃(`<이름>-canary-*`)과 다른 PC의 기록은 읽지 않는다.
- 이름을 바꾼 훅은 새 이름을 더한 날을 들인 날로 본다. 옛 이름으로 지낸 날은 세지 않는다.

쓰임: `uv run python tools/hook_report.py [--days N] [--today YYYY-MM-DD] [--projects <폴더>]
[--repo <폴더 이름>] [--root <저장소 루트>]`. 기본 루트는 이 파일이 든 체크아웃이고, 기본 `--repo`는
그 체크아웃의 주 체크아웃 경로로 짓는다(`git rev-parse --git-common-dir`). 표준 라이브러리만 쓴다.
종료 0은 표를 냈다, 2는 인자가 틀렸거나(창이 날짜의 범위를 넘는 `--days` 도) settings.json·git을
읽지 못했다. 기록 파일을 모두 읽어 이 PC의 기록 4705개에서 한 번에 1분 남짓 걸렸다(2026-10-20, PR
직전 리뷰가 `time` 으로 한 번 손으로 쟀다. 다른 세션이 돌던 때다). Bash 도구로 칠 때는 `timeout` 을
300000으로 준다(기본 120초).
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

NOTICE = "알림"
BLOCK = "막음"
UNKNOWN = "(모름)"
AMBIGUOUS = "(여럿)"
MIN_FRAGMENT = 10
HEAD_WIDTH = 60
DEFAULT_DAYS = 28
GIT_TIMEOUT = 30
WORKTREE_INFIX = "--claude-worktrees-"
WRAPPER_NOTICES = ("launch_hook: 훅 파일이 없어", "launch_hook: 등록 명령의 훅 이름 인자가")
PROMPT_EVENT = "UserPromptSubmit"  # 훅의 계기가 `hook_success` 없이 첨부로만 남는 이벤트
ROOT = Path(__file__).resolve().parent.parent

HOOK_COMMAND = re.compile(r"(?:launch_hook\.py\"?\s+|tools/)(hook_[A-Za-z0-9_]+\.py)")
COMMAND_HEAD = re.compile(r"^\[(.*?)\]: ", re.DOTALL)  # 종료 코드 2로 막은 이유의 머리
# 이벤트 이름(`PreToolUse`)과 도구 이름(`Bash`, `mcp__x__y`). `\w` 는 한글에도 맞아 쓰지 않는다
HOOK_ERROR = re.compile(r"^[A-Z][A-Za-z]+(?::[A-Za-z0-9_.-]+)? hook error: (.*)", re.DOTALL)

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


class ContextKey(NamedTuple):
    """계기를 맞대는 열쇠. 같은 세션·이벤트에서 낸 같은 글이면 같은 계기다."""

    session: str
    event: str
    text: str


@dataclass(frozen=True)
class Firing:
    """훅 한 번의 발동. `head` 는 막은 이유나 짝 없는 계기 글의 첫 줄 머리이고, `hook_success` 로
    센 알림이면 빈 글이다."""

    hook: str
    kind: str
    day: date
    head: str


@dataclass(frozen=True)
class Scan:
    """`broken` 은 JSON 객체로 읽지 못한 줄 수, `earliest` 는 시각이 든 기록 가운데 가장 이른
    날, `unreadable` 은 열지 못한 기록 파일 수(`files` 에 든다)다."""

    firings: tuple[Firing, ...]
    files: int
    broken: int
    earliest: date | None
    unreadable: int = 0


def folder_name_of(checkout: str) -> str:
    """Claude Code가 그 체크아웃의 세션 기록을 두는 폴더 이름. 영문자와 숫자 밖의 글자를 `-`로
    바꾼다(`tools/token_report.py` 의 같은 이름 함수와 같다)."""
    return re.sub(r"[^A-Za-z0-9]", "-", checkout)


def transcript_files(projects: Path, repo: str) -> list[Path]:
    folders = [projects / repo, *projects.glob(f"{repo}{WORKTREE_INFIX}*")]
    return sorted(path for folder in folders if folder.is_dir() for path in folder.rglob("*.jsonl"))


def _docstrings(tree: ast.Module) -> set[int]:
    """모듈·클래스·함수의 첫 문장이 문자열이면 그 노드의 id."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
    return found


def _fragments(source: str) -> frozenset[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return frozenset()
    skip = _docstrings(tree)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            found.update(part.strip() for part in node.value.splitlines())
    return frozenset(part for part in found if len(part) >= MIN_FRAGMENT)


def fingerprints(tools: Path, hooks: Iterable[str]) -> dict[str, frozenset[str]]:
    """훅마다 막은 이유를 알아볼 문자열 조각. 파일이 없거나 읽지 못하면 빈 집합이다. f-문자열의
    고정된 부분도 `ast.Constant` 라 함께 든다."""
    prints: dict[str, frozenset[str]] = {}
    for hook in hooks:
        try:
            prints[hook] = _fragments((tools / hook).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            prints[hook] = frozenset()
    return prints


def fragment_owner(text: str, prints: Mapping[str, frozenset[str]]) -> str:
    """막은 이유나 짝 없는 계기 글에 든 가장 긴 조각의 훅."""
    best = 0
    owners: list[str] = []
    for hook, parts in prints.items():
        length = max((len(part) for part in parts if part in text), default=0)
        if length > best:
            best, owners = length, [hook]
        elif length == best and length:
            owners.append(hook)
    if not owners:
        return UNKNOWN
    return owners[0] if len(owners) == 1 else AMBIGUOUS


def _obj(value: Json) -> dict[str, Json]:
    return value if isinstance(value, dict) else {}


def _list(value: Json) -> list[Json]:
    return value if isinstance(value, list) else []


def _str(value: Json) -> str:
    return value if isinstance(value, str) else ""


def _parse_json(text: str) -> Json:
    # `json.loads` 의 반환형은 Any 라, 여기서 `Json` 으로 받아 뒤의 좁히기가 타입 검사를 지나게
    # 한다.
    return json.loads(text)


def model_context(stdout: str) -> str | None:
    """훅 stdout(JSON)이 모델에게 넘긴 `additionalContext`. JSON 이 아니거나 그 값이 없으면 None."""
    try:
        output = _parse_json(stdout)
    except ValueError:  # JSONDecodeError 도 여기 든다
        return None
    text = _obj(_obj(output).get("hookSpecificOutput")).get("additionalContext")
    return text if isinstance(text, str) else None


def _day(value: Json) -> date | None:
    try:
        moment = datetime.fromisoformat(_str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.astimezone(UTC).date() if moment.tzinfo is not None else None


def _head(reason: str) -> str:
    return (reason.strip().splitlines() or [""])[0][:HEAD_WIDTH]


def _hook_of(command: str) -> str | None:
    match = HOOK_COMMAND.search(command)
    return match.group(1) if match else None


def _is_notice(text: str) -> bool:
    """훅의 stdout 이나 계기 글이 알림인지. 래퍼가 지나간 두 문구는 빼는데, 래퍼는 처음부터 한글을
    이스케이프하지 않고 냈다(`ensure_ascii=False`)."""
    return bool(text.strip()) and not any(notice in text for notice in WRAPPER_NOTICES)


def _result_texts(record: dict[str, Json]) -> list[str]:
    """사용자 기록의 도구 결과 글. 글 조각의 목록이면 이어 붙인다."""
    texts: list[str] = []
    for block in _list(_obj(record.get("message")).get("content")):
        part = _obj(block)
        if part.get("type") != "tool_result":
            continue
        content = part.get("content")
        if isinstance(content, str):
            texts.append(content)
        else:
            texts.append("".join(_str(_obj(item).get("text")) for item in _list(content)))
    return texts


def _record_firings(
    record: dict[str, Json], prints: Mapping[str, frozenset[str]]
) -> list[tuple[str, str, str]]:
    """기록 하나의 (훅, 종류, 이유 머리) 들."""
    attachment = _obj(record.get("attachment"))
    kind = attachment.get("type")
    if kind == "hook_success":
        hook = _hook_of(_str(attachment.get("command")))
        if hook is not None and _is_notice(_str(attachment.get("stdout"))):
            return [(hook, NOTICE, "")]
        return []
    if kind == "hook_blocking_error":
        error = _obj(attachment.get("blockingError"))
        reason = _str(error.get("blockingError"))
        hook = _hook_of(_str(error.get("command"))) or fragment_owner(reason, prints)
        return [(hook, BLOCK, _head(reason))]
    if record.get("type") != "user":
        return []
    found: list[tuple[str, str, str]] = []
    for text in _result_texts(record):
        match = HOOK_ERROR.match(text)
        if not match:
            continue
        reason = match.group(1)
        head = COMMAND_HEAD.match(reason)
        hook = _hook_of(head.group(1)) if head else None
        body = reason[head.end() :] if head else reason
        found.append((hook or fragment_owner(body, prints), BLOCK, _head(body)))
    return found


def _context_key(record: dict[str, Json], attachment: dict[str, Json], text: str) -> ContextKey:
    return ContextKey(_str(record.get("sessionId")), _str(attachment.get("hookEvent")), text)


def _given_context(record: dict[str, Json]) -> ContextKey | None:
    """`hook_success` 의 stdout 이 모델에게 넘긴 계기. 명령을 가리지 않는다."""
    attachment = _obj(record.get("attachment"))
    if attachment.get("type") != "hook_success":
        return None
    text = model_context(_str(attachment.get("stdout")))
    return None if text is None else _context_key(record, attachment, text)


def _attached_contexts(record: dict[str, Json]) -> list[ContextKey]:
    """명령 없는 `hook_additional_context` 첨부에 든 계기 글들."""
    attachment = _obj(record.get("attachment"))
    if attachment.get("type") != "hook_additional_context":
        return []
    texts = [part for part in _list(attachment.get("content")) if isinstance(part, str)]
    return [_context_key(record, attachment, text) for text in texts]


def scan(
    files: Iterable[Path], prints: Mapping[str, frozenset[str]], prompt_hooks: Collection[str]
) -> Scan:
    """`prompt_hooks` 는 `PROMPT_EVENT` 에 등록된 훅이다."""
    firings: list[Firing] = []
    seen: set[str] = set()
    broken = 0
    count = 0
    unreadable = 0
    earliest: date | None = None
    given: Counter[ContextKey] = Counter()
    attached: list[tuple[ContextKey, date]] = []
    for path in files:
        count += 1
        try:
            parts = path.read_bytes().split(b"\n")
        except OSError:  # 도는 동안 다른 세션이 기한 지난 기록을 지웠다
            unreadable += 1
            continue
        parts.pop()
        for raw in parts:
            if not raw.strip():
                continue
            try:
                record = _parse_json(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                broken += 1
                continue
            if not isinstance(record, dict):
                broken += 1
                continue
            uuid = _str(record.get("uuid"))
            if uuid and uuid in seen:
                continue
            seen.add(uuid)
            day = _day(record.get("timestamp"))
            if day is None:
                continue
            earliest = day if earliest is None else min(earliest, day)
            for hook, kind, head in _record_firings(record, prints):
                firings.append(Firing(hook, kind, day, head))
            if (sent := _given_context(record)) is not None:
                given[sent] += 1
            attached += [(key, day) for key in _attached_contexts(record)]
    firings += _unpaired_notices(given, attached, prints, prompt_hooks)
    return Scan(tuple(firings), count, broken, earliest, unreadable)


def _unpaired_notices(
    given: Counter[ContextKey],
    attached: Iterable[tuple[ContextKey, date]],
    prints: Mapping[str, frozenset[str]],
    prompt_hooks: Collection[str],
) -> list[Firing]:
    """짝 없는 계기 첨부의 알림. 짝은 같은 열쇠의 `hook_success` 하나에 첨부 하나다."""
    left = Counter(given)
    firings: list[Firing] = []
    for key, day in attached:
        if left[key]:
            left[key] -= 1
        elif _is_notice(key.text):
            owner = _unpaired_owner(key, prints, prompt_hooks)
            firings.append(Firing(owner, NOTICE, day, _head(key.text)))
    return firings


def _unpaired_owner(
    key: ContextKey, prints: Mapping[str, frozenset[str]], prompt_hooks: Collection[str]
) -> str:
    """짝 없는 계기 글의 훅. `PROMPT_EVENT` 의 글만 그 이벤트에 등록된 훅의 조각과 견준다. 다른
    이벤트에서는 이 저장소의 훅이 `hook_success` 를 남겨 짝이 있으니 짝 없는 글은 `UNKNOWN` 이다."""
    if key.event != PROMPT_EVENT:
        return UNKNOWN
    return fragment_owner(key.text, {hook: prints.get(hook, frozenset()) for hook in prompt_hooks})


def registered_hooks(settings: str, event: str | None = None) -> list[str]:
    """settings.json 글의 명령 가운데 훅 명령의 훅 이름. `event` 를 주면 그 이벤트에 등록된
    것만이다. ValueError 는 JSON 이 아닐 때다."""
    found: set[str] = set()
    for name, groups in _obj(_obj(_parse_json(settings)).get("hooks")).items():
        if event is not None and name != event:
            continue
        for group in _list(groups):
            for entry in _list(_obj(group).get("hooks")):
                hook = _hook_of(_str(_obj(entry).get("command")))
                if hook is not None:
                    found.add(hook)
    return sorted(found)


def _git(root: Path, *args: str) -> str:
    """git 출력. 실패하거나 시간을 넘기면 OSError 로 올린다."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise OSError(f"git {args[0]} 이 {GIT_TIMEOUT}초 안에 끝나지 않았다") from error
    if done.returncode != 0:
        raise OSError(done.stderr.strip() or f"git {args[0]} 이 {done.returncode}로 끝났다")
    return done.stdout


def introduced_dates(root: Path, hooks: Iterable[str]) -> dict[str, date]:
    """훅 파일을 마지막으로 더한 커밋의 날짜. 지웠다가 다시 들인 훅은 다시 들인 날부터 센다. 기록에
    없는 훅(커밋하지 않은 새 훅)은 빠진다."""
    wanted = {f"tools/{hook}": hook for hook in hooks}
    if not wanted:
        return {}
    log = _git(root, "log", "--diff-filter=A", "--name-only", "--format=@%cs", "--", *wanted)
    dates: dict[str, date] = {}
    current: date | None = None
    for line in log.splitlines():
        if line.startswith("@"):
            current = date.fromisoformat(line[1:])
        elif current is not None and line in wanted:
            # 기록은 새것부터라 처음 것이 마지막에 더한 날이다
            dates.setdefault(wanted[line], current)
    return dates


def _listed(hooks: Iterable[str], introduced: Mapping[str, date]) -> str:
    text = ", ".join(f"{hook}({introduced[hook].isoformat()} 들임)" for hook in hooks)
    return text or "(없음)"


def render(
    result: Scan, hooks: Sequence[str], introduced: Mapping[str, date], today: date, days: int
) -> str:
    start = today - timedelta(days=days - 1)
    inside = [firing for firing in result.firings if start <= firing.day <= today]
    earliest = result.earliest.isoformat() if result.earliest else "없음"
    unopened = f", 읽지 못한 파일 {result.unreadable}개" if result.unreadable else ""
    out = [
        f"훅 발동 {start.isoformat()} ~ {today.isoformat()} ({days}일, UTC 날짜). 기록 파일"
        f" {result.files}개, 읽지 못한 줄 {result.broken}개{unopened}, 가장 이른 기록 {earliest}.",
    ]
    if result.earliest is not None and result.earliest > start:
        gap = (result.earliest - start).days
        out.append(f"가장 이른 기록이 {earliest} 이라 창의 앞 {gap}일은 기록이 없다.")
    counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    active_days: defaultdict[str, set[date]] = defaultdict(set)
    for firing in inside:
        if firing.hook in (UNKNOWN, AMBIGUOUS):
            continue
        counts[firing.hook][firing.kind] += 1
        active_days[firing.hook].add(firing.day)
    out += ["", "| 훅 | 알림 | 막음 | 발동한 날 | 마지막 |", "|---|---|---|---|---|"]
    ranked = sorted(counts, key=lambda hook: (-sum(counts[hook].values()), hook))
    for hook in ranked:
        mark = "" if hook in hooks else " (등록 안 됨)"
        last = max(active_days[hook]).isoformat()
        notices, blocks = counts[hook][NOTICE], counts[hook][BLOCK]
        out.append(f"| {hook}{mark} | {notices} | {blocks} | {len(active_days[hook])} | {last} |")
    quiet = [hook for hook in hooks if hook not in counts]
    old = [hook for hook in quiet if hook in introduced and introduced[hook] < start]
    young = [hook for hook in quiet if hook in introduced and introduced[hook] >= start]
    undated = [hook for hook in quiet if hook not in introduced]
    # 기록이 비어 있는 날에는 발동했어도 0으로 보여, 조용한 훅을 모두 후보로 낸다
    if result.earliest is None:
        verdict = "판정하지 않는다(기록이 없다. `--projects`·`--repo` 를 본다)"
    elif result.earliest > start:
        verdict = (
            f"판정하지 않는다(창의 앞 {(result.earliest - start).days}일에 기록이 없다."
            " `--days` 를 줄여 다시 돌린다)"
        )
    else:
        verdict = _listed(old, introduced)
    out += [
        "",
        f"뺄 후보: {verdict}",
        "  (창보다 먼저 들였고 창 안에서 알리지도 막지도 않았다. 손상을 막는 훅은 0건이어도 남긴다."
        " 판정은 retro 4단계)",
        f"아직 판단하지 않는 훅(창 안에 들였다): {_listed(young, introduced)}",
    ]
    if undated:
        out.append(f"들인 날을 모르는 훅: {', '.join(undated)}")
    unattributed = [firing for firing in inside if firing.hook in (UNKNOWN, AMBIGUOUS)]
    for kind, what in ((NOTICE, "글"), (BLOCK, "이유")):
        group = [firing for firing in unattributed if firing.kind == kind]
        if not group:
            continue
        out.append(f"어느 훅인지 가르지 못한 {kind} {len(group)}건({what}의 머리마다):")
        heads = Counter((firing.hook, firing.head) for firing in group)
        for (hook, head), number in heads.most_common():
            out.append(f"  {number}건 {hook} {head}")
    return "\n".join(out)


def main_checkout_folder(root: Path) -> str:
    """주 체크아웃의 기록 폴더 이름. 워크트리에서 돌아도 공통 git 디렉터리의 부모로 찾는다.
    OSError 는 `_git` 의 것이다."""
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    return folder_name_of(str(Path(common).parent))


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"양의 정수다: {text}") from error
    if value < 1:
        raise argparse.ArgumentTypeError(f"양의 정수다: {text}")
    return value


def _date_of(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"날짜는 YYYY-MM-DD다: {text}") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hook_report.py", description="훅마다 알린 수와 막은 수. 자세한 것은 독스트링."
    )
    parser.add_argument("--days", type=_positive, default=DEFAULT_DAYS, help="창의 날 수")
    parser.add_argument("--today", type=_date_of, help="창의 끝 날 YYYY-MM-DD(기본 UTC 오늘)")
    parser.add_argument("--projects", type=Path, help="세션 기록 폴더(기본 ~/.claude/projects)")
    parser.add_argument(
        "--repo", help="이 저장소의 기록 폴더 이름(기본 주 체크아웃의 경로로 짓는다)"
    )
    parser.add_argument(
        "--root", type=Path, default=ROOT, help="settings.json 과 git 의 저장소 루트"
    )
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    root: Path = args.root
    days: int = args.days
    today: date = args.today or datetime.now(UTC).date()
    if days - 1 > (today - date.min).days:  # 기록을 다 읽은 뒤 창을 계산하다 넘치지 않게
        sys.stderr.write(f"창이 날짜의 범위를 넘는다: --days {days}\n")
        return 2
    projects: Path = args.projects or Path.home() / ".claude" / "projects"
    try:
        settings = (root / ".claude" / "settings.json").read_text(encoding="utf-8")
        hooks = registered_hooks(settings)
        prompt_hooks = registered_hooks(settings, PROMPT_EVENT)
        repo: str = args.repo or main_checkout_folder(root)
        introduced = introduced_dates(root, hooks)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        sys.stderr.write(f"settings.json 이나 git 을 읽지 못했다: {error}\n")
        return 2
    prints = fingerprints(root / "tools", hooks)
    result = scan(transcript_files(projects, repo), prints, prompt_hooks)
    print(render(result, hooks, introduced, today, days))
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
