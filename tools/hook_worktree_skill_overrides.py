"""PostToolUse 훅(EnterWorktree). 세션이 주 체크아웃의 워크트리(`.claude/worktrees/<이름>/`)에
들어가면, 그 워크트리의 스킬 사본이 스킬 목록에 붙지 않게 주 체크아웃의
`.claude/settings.local.json` 의 `skillOverrides` 에 경로를 단
이름(`.claude/worktrees/<이름>:<스킬>`)마다 `"off"` 를 적는다.

대기열 274 다. 주 체크아웃에서 시작해 워크트리에 들어간 세션은, 그 뒤 주 체크아웃의 스킬 파일이
바뀌면(다른 세션이 주 체크아웃을 당기면) 그 워크트리의 스킬을 바뀌지 않은 것까지 모두 경로를 단
이름으로 목록에 더한다. 워크트리가 `.gitignore` 에 든 이 저장소의 모양에서는, 주 체크아웃 세션이
워크트리 파일을 읽거나, 들어간 뒤 읽기만 하거나, 워크트리에서 시작한 세션에서는 붙지 않았다
(`.gitignore` 에 없으면 주 체크아웃 세션이 읽기만 해도 붙었다). `skillOverrides` 에 경로를 단 이름을
그대로 키로 `"off"` 를 주면 그 이름만 빠졌고, 세션 도중에 local 설정에 써도 먹었으며, 프로젝트
설정의 `skillOverrides` 와 합쳐졌다. 워크트리 이름 자리의 별표는 먹지 않아 워크트리마다 이름을
적는다. 이 훅을 등록한 세션에서도 바깥 변경 뒤 경로를 단 이름이 붙지 않았고, 훅이 적은 뒤에 새로
생긴 스킬은 붙었다. 모두 `.scratch/harness/probes/worktree_skill_listing.py` 가 claude CLI 2.1.303
에서 갈래마다 한 회차로 쟀다. 이 PC 의 데스크톱 앱 세션에서는 이 훅이 키를 적었는데도 이름이
붙었다(못 보는 것의 데스크톱 앱 항목). 더한 목록이 세션이 끝날 때까지 호출마다 입력에 실린다는 것은
어림이다(첨부가 대화 기록에 남는다고 보았고, 프로브는 한 턴만 돈다).

끄는 값이 있다. 공식 문서(skills 의 "Load skills in monorepos and subdirectories" 절, 2026-10-19
원문을 내려받아 읽었다)는 경로를 단
이름을 목록에 실을 때 일하는 파일이 든 폴더의 사본을 부르라는 안내를 함께 싣는다고 적고, 이 저장소의
세션은 그 꼴로 Skill 을 190번 불렀다(`.scratch/harness/probes/session_cost/branches.json` 의
브랜치별 `skills` 를 손으로 더했다. 그 파일은 2026-09-19 뒤 병합된 PR 의 브랜치를 담고 2026-10-16 에
커밋됐다). 끄면 그 이름은 부를 수 없고(숨긴 스킬을 전체 이름으로 부르면
`skillOverrides` 오류다, 같은 문서의 "Override skill visibility from settings"), Skill 호출은 주
체크아웃에 실린 사본으로 돈다. 워크트리에서 고친 스킬은 원래부터 그 이름이 아니라 Read 로 디스크의
`SKILL.md` 를 열어 따른다(`docs/constitution/operations.md` 환경 규약 상세. 경로를 단 이름은 붙은
때의 판이다). 그래서 끄더라도 워크트리의 판을 따를 길은 남는다.

추적하는 `.claude/settings.json` 이 아니라 local 에 쓰는 것은 워크트리 이름이 티켓마다 달라서다.
local 은 이 PC 의 사용자 전역 ignore 가 덮어 추적되지 않는다(`tools/check_instructions.py` 의 local
검사 독스트링). 키의 이름공간 `.claude/worktrees/` 는 이 훅이 맡는다. 쓸 때마다 그 접두의 키 가운데
워크트리 폴더가 없어진 것을 걷고 들어간 워크트리의 키를 더하며, 다른 키와 다른 설정은 그대로 둔다.
바뀔 것이 없으면 쓰지 않고 침묵한다. 썼으면 사용자에게만 알린다(`systemMessage`). local 이 UTF-8 이
아니거나 JSON 객체로 풀리지 않거나 `skillOverrides` 가 객체가 아니면 고치지 않고 알린다. 쓸 때는
앞 실행이 쓰다 죽어 남긴 한 시간 넘은 임시 파일을 치운다. 워크트리를 만들 때 받은 local 사본은 이
훅이 루트를 고친 뒤 루트와 바이트가 달라지므로, `tools/tidy_checkouts.py` 의 `settings_equivalent`
가 이 훅의 키와 서식을 빼고 견준다.

클라우드 세션(`CLAUDE_CODE_REMOTE` 가 `true`)에서는 침묵한다. 클라우드 체크아웃에는 그 ignore 가
없어, 쓰면 추적하지 않는 파일로 남는다(2026-10-19 클라우드 컨테이너에서 `git check-ignore` 가 1
이었다, 손으로 봤다).

못 보는 것:
- 머리말의 `name` 이 폴더 이름과 다른 스킬. 키는 폴더 이름으로 짓는다(이 저장소의 스킬 열여섯은 둘이
  같았다, 2026-10-19 손으로 봤다. 프로브의 스킬도 둘이 같아 목록이 어느 쪽으로 이름을 짓는지는 재지
  않았다).
- 들어간 뒤에 그 워크트리에 새로 생긴 스킬. 다음 `EnterWorktree` 에서 적는다.
- local 설정이 git 에서 무시되는지. 클라우드 세션만 침묵하고, 무시되지 않는 다른 체크아웃에서는
  local 이 추적하지 않는 파일로 남는다(쓰다 실패한 임시 파일은 지운다). 이 PC 의 주 체크아웃에서는
  사용자 전역 ignore(`~/.config/git/ignore` 의 `**/.claude/settings.local.json`)가 덮어, 이 PC 의 앱
  세션들이 이 훅으로 키를 적은 local 이 `git status` 에 나오지 않았다(2026-10-19 워크트리에 들어가기
  전의 `git status --porcelain` 과, 다음 세션이 시작할 때 앱이 넣은 git 상태로 봤다. 일지
  2026-10-20-01).
- `EnterWorktree` 밖의 길로 붙는 사본. 워크트리가 `.gitignore` 에 없는 저장소에서 주 체크아웃 세션이
  워크트리 파일을 읽어 붙는 것은 이 훅이 보지 않는다.
- 다른 길로 워크트리에 온 세션(앱이 워크트리 폴더에서 연 세션, `/cd`)과 이 훅이 들어오기 전에 들어간
  세션.
- 같은 파일을 같은 때 쓰는 다른 쓰기(Claude Code 의 권한 기억, `/skills` 메뉴, 다른 세션의 이 훅).
  읽고 쓰는 사이에 끼면 나중 쓰기가 이긴다.
- 데스크톱 앱 세션. 이 PC 의 앱(기록 줄의 `version` 으로 Claude Code 2.1.299)에서 주 체크아웃을 연
  세션이 `EnterWorktree(name)` 으로 들어가자 이 훅이 그 워크트리의 스킬 열여섯에 키를 적었는데,
  사람이 주 체크아웃의 스킬 파일을 고친 뒤 붙은 추가분에 그 가운데 목록에 실리는 열하나가 모두
  경로를 단 이름으로 실렸다(나머지 다섯은 `disable-model-invocation` 이라 원래 목록에 없다). 들어간
  뒤 만든 스킬도 같은 추가분에 실려 목록을 다시 훑은 것이 보였다. 같은 날 다른 앱 세션이 같은
  워크트리에 `EnterWorktree(path)` 로 다시 들어갔을 때도(키는 그대로 있었다, Grep 으로 개수를
  봤다) 같은 열하나가 붙었다. 2026-10-19 두 회차이고, 판정은
  `.scratch/harness/probes/worktree_overrides_app.py` 다(일지 2026-10-20-01). 까닭은 가르지 않았다.
  후보는 셋이다. 하나, 들어간 뒤 세션이 주 체크아웃이 아닌 워크트리의 local 을 읽는다. 두 회차
  모두 세션의 기록 파일이 워크트리 이름의 프로젝트 폴더로 옮겨졌고, 워크트리의 local 사본은 이
  훅이 쓰기 전에 복사되어 두 회차 모두 그 키가 없었다(손으로 봤다). 공식 문서(settings 의 "Where
  Claude Code keeps the local file in a git repository", 2026-10-19 원문을 내려받아 읽었다)는
  Windows 에서 local 이 `.claude/settings.json` 곁에 남는다고 적는다. 이 훅은 운영 규약의 모드
  표가 `EnterWorktree` 로 들어온 세션의 훅 등록을 주 체크아웃의 것으로 적은 데 기대어 그 곁을 주
  체크아웃의 local 로 보았는데(어림), 이 후보가 맞으면 그 어림이 틀렸다. CLI 의 프로브는
  `git worktree add` 로 만들어 local 사본이 없는 워크트리에 `EnterWorktree(path)` 로
  들어갔다(그 프로브의 코드를 읽었다). 그래서 이 후보가 맞으면 갈린 것은 앱과 CLI 가 아니라
  워크트리에 local 사본이 있었는지일 수 있다. 앱의 둘째 회차도 `path` 로 들어갔으니 들어가는
  꼴(`name` 과 `path`)은 갈린 까닭이 아니다. 둘, 그 판이 경로를 단 키를 맞추지 않는다(실행
  파일에 `skillOverrides` 가 든 줄이 있다는 것만 손으로 봤고(`grep -a -c`), 그것은 그 판이 그
  설정을 안다는 것만 보인다). 셋, Windows 에서 바꿔 끼운(`os.replace`) 파일을 설정 감시가 보지
  못한다. 둘째 회차는 키가 적힌 뒤에 시작한 세션이고, 그 세션에서 이 훅은 바뀔 것이 없어 쓰지
  않았는데도 붙었다. 세션이 시작할 때 local 을 읽는다면 이 후보만으로는 둘째 회차를 설명하지
  못한다(세션이 설정을 언제 읽는지는 재지 않았다).
  들어간 뒤 스킬을 만들지 않은 셋째 앱 세션(같은 판, `EnterWorktree(path)`, 키가 있었다)에서는
  다른 세션이 주 체크아웃을 당겨 스킬 파일 하나가 바뀌었고, 당긴 72초 뒤의 추가분에 주
  체크아웃의 맨 이름 넷만 실렸다. 목록이 워크트리를 다시 훑었는지 가를 표지가 없어 측정으로
  세지 않았다. 그래서 앱에서 워크트리를 다시 훑게 하는 것이 주 체크아웃의 변경만인지 들어간 뒤
  생긴 스킬도 드는지는 모른다(CLI 의 프로브에서는 새 스킬을 만들지 않은 갈래도 주 체크아웃의
  변경만으로 다시 훑었다).
- 끈 이름은 Skill 도구로 부를 수 없다(공식 문서 skills의 "Override skill visibility from settings":
  숨긴 스킬을 전체 이름으로 부르면 `skillOverrides` 오류다. 2026-10-19 원문을 내려받아 읽었다).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import TypedDict

TOOL = "EnterWorktree"
WORKTREES = Path(".claude") / "worktrees"
# 스킬 목록이 워크트리 사본에 붙이는 접두. 윈도 PC 의 트랜스크립트에서도 슬래시였다(일지
# 2026-10-16-27 의 `.claude/worktrees/harness-audit:code-review`).
KEY_PREFIX = ".claude/worktrees/"
LOCAL = Path(".claude") / "settings.local.json"
OFF = "off"
OVERRIDES = "skillOverrides"
# 쓸 때 치우는 남은 임시 파일의 나이(초). 이보다 새 것은 다른 세션의 이 훅이 쓰는 중일 수 있다.
STALE_TEMP_SECONDS = 3600
# `json.loads` 의 반환형은 Any 라, 이것으로 받아 뒤의 좁히기가 타입 검사를 지나게 한다
# (선례 `tools/token_report.py` 의 `Json`).
type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


class UnfixableSettingsError(ValueError):
    """local 설정을 고칠 수 없다. 메시지가 사용자에게 알릴 까닭이다."""


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분. 값의 꼴은 런타임에 다시 본다."""

    tool_name: str
    tool_input: Json
    tool_response: Json


def entered_worktree(payload: HookPayload, root: Path) -> Path | None:
    """`root` 의 `.claude/worktrees/` 바로 아래 워크트리에 들어간 `EnterWorktree` 면 그 경로, 아니면
    None. 경로는 결과의 `worktreePath` 를 먼저, 없으면 입력의 `path` 를 본다."""
    if payload.get("tool_name") != TOOL:
        return None
    raw = _str_field(payload.get("tool_response"), "worktreePath") or _str_field(
        payload.get("tool_input"), "path"
    )
    if not raw:
        return None
    worktree = Path(raw)
    if worktree.resolve().parent != (root / WORKTREES).resolve():
        return None
    return worktree


def _str_field(value: Json, key: str) -> str | None:
    if not isinstance(value, dict):
        return None
    field = value.get(key)
    return field if isinstance(field, str) else None


def skill_names(worktree: Path) -> list[str]:
    """워크트리의 프로젝트 스킬. `.claude/skills/<이름>/SKILL.md` 가 있는 폴더 이름이다."""
    folder = worktree / ".claude" / "skills"
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if (p / "SKILL.md").is_file())


def updated(settings: dict[str, Json], root: Path, worktree: Path) -> dict[str, Json] | None:
    """`worktree` 의 스킬 사본을 끄는 키를 더하고 없어진 워크트리의 키를 걷은 새 설정. 바뀔 것이
    없으면 None 이다. `settings` 는 고치지 않는다."""
    current = settings.get(OVERRIDES, {})
    if not isinstance(current, dict):
        raise UnfixableSettingsError(f"{OVERRIDES} 가 객체가 아니다")
    kept = {
        key: value
        for key, value in current.items()
        if not key.startswith(KEY_PREFIX) or _worktree_alive(root, key)
    }
    added: dict[str, Json] = {
        f"{KEY_PREFIX}{worktree.name}:{skill}": OFF for skill in skill_names(worktree)
    }
    overrides = {**kept, **added}
    if overrides == current:
        return None
    return {**settings, OVERRIDES: overrides}


def _worktree_alive(root: Path, key: str) -> bool:
    name = key[len(KEY_PREFIX) :].rpartition(":")[0]
    return bool(name) and (root / WORKTREES / name).is_dir()


def apply(root: Path, worktree: Path) -> str | None:
    """`root` 의 local 설정을 고친다. 썼거나 고치지 못했으면 사용자에게 알릴 문장, 바뀔 것이 없으면
    None 이다. 고치는 일은 `_fix` 가 하고, 여기서는 그 실패를 알림으로 바꾸기만 한다."""
    try:
        return _fix(root / LOCAL, root, worktree)
    except UnfixableSettingsError as error:
        return _cannot(str(error))


def _fix(path: Path, root: Path, worktree: Path) -> str | None:
    """쓴 것을 알리는 문장을 돌려준다. 실패는 돌려주지 않고 `UnfixableSettingsError` 로 던져,
    호출부가 반환값을 버려도 묻히지 않는다."""
    new = updated(read_settings(path), root, worktree)
    if new is None:
        return None
    _write(path, new)
    count = len(skill_names(worktree))
    return (
        f"워크트리 {worktree.name} 의 스킬 사본 {count}개를 스킬 목록에서 끄도록 "
        f"{LOCAL.as_posix()} 의 {OVERRIDES} 에 적었다(대기열 274). CLI 2.1.303 세션에서는 "
        "주 체크아웃의 스킬이 바뀌어도 경로를 단 사본이 목록에 붙지 않았지만, "
        "이 PC 의 데스크톱 앱 2.1.299 세션 두 회차에서는 붙었다."
    )


def read_settings(path: Path) -> dict[str, Json]:
    """local 설정. 파일이 없으면 빈 설정이고, 읽거나 풀지 못하면 `UnfixableSettingsError` 다."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError as error:
        raise UnfixableSettingsError("UTF-8 이 아니다") from error
    except OSError as error:
        raise UnfixableSettingsError(f"읽지 못했다({error})") from error
    return _parsed(text)


def _parsed(text: str) -> dict[str, Json]:
    try:
        value: Json = json.loads(text)
    except json.JSONDecodeError as error:
        raise UnfixableSettingsError(f"JSON 으로 풀리지 않는다({error})") from error
    if not isinstance(value, dict):
        raise UnfixableSettingsError("맨 위가 객체가 아니다")
    return value


def _cannot(reason: str) -> str:
    return (
        f"{LOCAL.as_posix()} 를 고치지 못해({reason}) 워크트리 스킬 사본을 스킬 목록에서 끄지 "
        "못했다(대기열 274). 파일을 고치면 다음 EnterWorktree 에서 다시 적는다."
    )


def _write(path: Path, settings: dict[str, Json]) -> None:
    """쓰지 못하면 `UnfixableSettingsError` 다."""
    try:
        _replace(path, settings)
    except OSError as error:
        raise UnfixableSettingsError(f"쓰지 못했다({error})") from error


def _replace(path: Path, settings: dict[str, Json]) -> None:
    """같은 폴더의 임시 파일에 쓰고 바꿔 끼운다. 쓰다 끊겨도 원래 파일이 반쯤 남지 않고, 바꿔
    끼우지 못하면 임시 파일을 지운다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _sweep_stale_temps(path)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _sweep_stale_temps(path: Path) -> None:
    """앞 실행이 쓰다 죽어(시간 제한의 강제 종료, 앱 종료) 남긴 임시 파일 가운데
    `STALE_TEMP_SECONDS` 가 넘은 것을 지운다. git 이 무시하지 않아 주 체크아웃을 더럽히기 때문이다.
    지우지 못하면 둔다."""
    cutoff = time.time() - STALE_TEMP_SECONDS
    for leftover in path.parent.glob(f"{path.name}.*.tmp"):
        if _modified_before(leftover, cutoff):
            with contextlib.suppress(OSError):
                leftover.unlink()


def _modified_before(path: Path, cutoff: float) -> bool:
    """`path` 가 `cutoff` 전에 마지막으로 바뀌었는지. 그사이 사라졌거나 볼 수 없으면 아니라고
    본다."""
    try:
        return path.stat().st_mtime < cutoff
    except OSError:
        return False


def main() -> int:
    payload: HookPayload = json.load(sys.stdin.buffer)
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return 0
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if not project:
        return 0
    root = Path(project)
    worktree = entered_worktree(payload, root)
    if worktree is None:
        return 0
    notice = apply(root, worktree)
    if notice is not None:
        print(json.dumps({"systemMessage": notice}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
