"""tools/hook_worktree_skill_overrides.py 의 판정과 쓰기.

입력 모양은 claude 2.1.303 의 `claude -p` 세션에서 PostToolUse 훅이 받은 `EnterWorktree` 페이로드를
옮겼다(`tool_input.path`, `tool_response.worktreePath`·`worktreeBranch`·`message`, 일지
2026-10-19-14). 쓰기는 임시 폴더를 주 체크아웃으로 두고 본다. 그 폴더는 git 저장소가 아니라, 훅이
local 설정이 무시되는지 보지 않고 쓴다는 것(독스트링의 못 보는 것)도 함께 고정된다. main 은 하위
프로세스로 두 번(쓰는 길과 클라우드의 침묵) 실제로 띄운다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tools.hook_worktree_skill_overrides import (
    KEY_PREFIX,
    LOCAL,
    OFF,
    STALE_TEMP_SECONDS,
    TOOL,
    HookPayload,
    Json,
    UnfixableSettingsError,
    apply,
    entered_worktree,
    skill_names,
    updated,
)
from tools.run_hooks import registered_matchers

_HOOK = Path(__file__).resolve().parents[2] / "tools" / "hook_worktree_skill_overrides.py"


def _워크트리(root: Path, name: str, skills: tuple[str, ...] = ("code-review", "tdd")) -> Path:
    worktree = root / ".claude" / "worktrees" / name
    for skill in skills:
        folder = worktree / ".claude" / "skills" / skill
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: {skill}\n---\n", encoding="utf-8")
    return worktree


def _진입(worktree: Path, tool: str = TOOL) -> HookPayload:
    text = json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": {"path": str(worktree)},
            "tool_response": {
                "worktreePath": str(worktree),
                "worktreeBranch": worktree.name,
                "message": f"Entered worktree at “{worktree}” on branch “{worktree.name}”.",
            },
        }
    )
    return json.loads(text)


def _로컬(root: Path) -> dict[str, Json]:
    value: Json = json.loads((root / LOCAL).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_등록된_매처는_EnterWorktree_하나다() -> None:
    assert registered_matchers("hook_worktree_skill_overrides.py", "PostToolUse") == [TOOL]


def test_주_체크아웃의_워크트리_자리로_들어간_호출만_고른다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")
    assert entered_worktree(_진입(worktree), tmp_path) == worktree


def test_다른_도구와_다른_자리의_워크트리는_고르지_않는다(tmp_path: Path) -> None:
    """경로를 단 이름의 접두는 `.claude/worktrees/<이름>` 이라, 그 바로 아래가 아닌 워크트리(다른
    폴더에 판 것, 그 안의 하위 폴더)는 이 훅이 적을 이름을 모른다."""
    worktree = _워크트리(tmp_path, "x")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert entered_worktree(_진입(worktree, tool="ExitWorktree"), tmp_path) is None
    assert entered_worktree(_진입(elsewhere), tmp_path) is None
    assert entered_worktree(_진입(worktree / ".claude"), tmp_path) is None


def test_결과에_경로가_없으면_입력의_경로를_본다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")
    payload = _진입(worktree)
    payload["tool_response"] = "Entered worktree"
    assert entered_worktree(payload, tmp_path) == worktree


def test_스킬_이름은_SKILL_md_가_있는_폴더다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x", ("b-skill", "a-skill"))
    (worktree / ".claude" / "skills" / "empty").mkdir()
    assert skill_names(worktree) == ["a-skill", "b-skill"]
    assert skill_names(tmp_path / "없는-폴더") == []


def test_들어간_워크트리의_스킬마다_끄는_키를_더하고_다른_설정은_둔다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")
    settings: dict[str, Json] = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "skillOverrides": {"jira-start": "off", "tdd": "name-only"},
    }

    result = updated(settings, tmp_path, worktree)

    assert result is not None
    assert result["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert result["skillOverrides"] == {
        "jira-start": "off",
        "tdd": "name-only",
        f"{KEY_PREFIX}x:code-review": OFF,
        f"{KEY_PREFIX}x:tdd": OFF,
    }
    assert settings["skillOverrides"] == {"jira-start": "off", "tdd": "name-only"}


def test_없어진_워크트리의_키는_걷고_남은_워크트리의_키는_둔다(tmp_path: Path) -> None:
    """정리(`tidy-checkouts`)가 지운 워크트리의 키가 쌓이지 않게 한다."""
    kept = _워크트리(tmp_path, "kept")
    entered = _워크트리(tmp_path, "new", ("tdd",))
    settings: dict[str, Json] = {
        "skillOverrides": {
            f"{KEY_PREFIX}kept:tdd": OFF,
            f"{KEY_PREFIX}gone:tdd": OFF,
        }
    }

    result = updated(settings, tmp_path, entered)

    assert result is not None
    assert result["skillOverrides"] == {
        f"{KEY_PREFIX}kept:tdd": OFF,
        f"{KEY_PREFIX}new:tdd": OFF,
    }
    assert kept.is_dir()


def test_바뀔_것이_없으면_None_이다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x", ("tdd",))
    settings: dict[str, Json] = {"skillOverrides": {f"{KEY_PREFIX}x:tdd": OFF}}
    assert updated(settings, tmp_path, worktree) is None


def test_스킬이_없는_워크트리는_None_이다(tmp_path: Path) -> None:
    worktree = tmp_path / ".claude" / "worktrees" / "bare"
    worktree.mkdir(parents=True)
    assert updated({}, tmp_path, worktree) is None


def test_skillOverrides_가_객체가_아니면_멈춘다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")
    with pytest.raises(UnfixableSettingsError):
        updated({"skillOverrides": ["tdd"]}, tmp_path, worktree)


def test_파일이_없으면_새로_만들고_알린다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")

    notice = apply(tmp_path, worktree)

    assert notice is not None and "2개" in notice and LOCAL.as_posix() in notice
    assert _로컬(tmp_path) == {
        "skillOverrides": {f"{KEY_PREFIX}x:code-review": OFF, f"{KEY_PREFIX}x:tdd": OFF}
    }


def test_BOM_이_붙은_설정도_풀어_고친다(tmp_path: Path) -> None:
    """윈도의 편집기와 PowerShell 은 UTF-8 파일 앞에 BOM 을 붙이기도 한다."""
    worktree = _워크트리(tmp_path, "x", ("tdd",))
    (tmp_path / LOCAL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / LOCAL).write_text('{"env": {"A": "1"}}', encoding="utf-8-sig")

    assert apply(tmp_path, worktree) is not None
    assert _로컬(tmp_path) == {"env": {"A": "1"}, "skillOverrides": {f"{KEY_PREFIX}x:tdd": OFF}}


def test_다시_들어가면_쓰지_않고_침묵한다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")
    assert apply(tmp_path, worktree) is not None
    before = (tmp_path / LOCAL).stat().st_mtime_ns

    assert apply(tmp_path, worktree) is None
    assert (tmp_path / LOCAL).stat().st_mtime_ns == before


def test_들어간_뒤_새로_생긴_스킬은_다음_진입에서_적는다(tmp_path: Path) -> None:
    """못 보는 것: 첫 진입 뒤에 생긴 스킬은 그 진입의 키에 없다. 다음 진입이 더한다."""
    worktree = _워크트리(tmp_path, "x", ("tdd",))
    assert apply(tmp_path, worktree) is not None
    _워크트리(tmp_path, "x", ("late",))
    assert f"{KEY_PREFIX}x:late" not in json.dumps(_로컬(tmp_path))

    assert apply(tmp_path, worktree) is not None
    assert _로컬(tmp_path)["skillOverrides"] == {
        f"{KEY_PREFIX}x:tdd": OFF,
        f"{KEY_PREFIX}x:late": OFF,
    }


def test_머리말_이름이_폴더와_달라도_키는_폴더_이름이다(tmp_path: Path) -> None:
    """못 보는 것: 목록이 머리말의 `name` 으로 이름을 지으면 이 키는 그 사본에 맞지 않는다."""
    worktree = _워크트리(tmp_path, "x", ("folder-name",))
    (worktree / ".claude" / "skills" / "folder-name" / "SKILL.md").write_text(
        "---\nname: front-name\n---\n", encoding="utf-8"
    )
    assert skill_names(worktree) == ["folder-name"]


def test_바꿔_끼우지_못하면_임시_파일을_지우고_알린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """윈도에서 다른 프로세스가 local 설정을 연 채면 바꿔 끼우기가 막힐 수 있다."""
    worktree = _워크트리(tmp_path, "x")

    def refuse(_src: object, _dst: object) -> None:
        raise PermissionError("열려 있다")

    monkeypatch.setattr(os, "replace", refuse)

    notice = apply(tmp_path, worktree)

    assert notice is not None and "쓰지 못했다" in notice and "열려 있다" in notice
    assert sorted(p.name for p in (tmp_path / LOCAL).parent.iterdir()) == ["worktrees"]


def test_쓸_때_한_시간_넘은_임시_파일은_치우고_새_것은_둔다(tmp_path: Path) -> None:
    """쓰다 죽은 실행(시간 제한의 강제 종료, 앱 종료)이 남긴 임시 파일은 git 이 무시하지 않아 주
    체크아웃을 더럽힌다. 새 것은 다른 세션의 이 훅이 쓰는 중일 수 있어 둔다."""
    worktree = _워크트리(tmp_path, "x")
    old = tmp_path / ".claude" / "settings.local.json.111.tmp"
    old.write_text("x", encoding="utf-8")
    hour_ago = time.time() - STALE_TEMP_SECONDS - 60
    os.utime(old, (hour_ago, hour_ago))
    fresh = tmp_path / ".claude" / "settings.local.json.222.tmp"
    fresh.write_text("y", encoding="utf-8")

    assert apply(tmp_path, worktree) is not None
    assert not old.exists()
    assert fresh.exists()


def test_읽지_못하는_설정은_까닭과_함께_알린다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")
    (tmp_path / LOCAL).mkdir()

    notice = apply(tmp_path, worktree)

    assert notice is not None and "읽지 못했다" in notice
    assert (tmp_path / LOCAL).is_dir()


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        ("{깨진".encode(), "JSON 으로 풀리지 않는다"),
        (b"[1, 2]", "맨 위가 객체가 아니다"),
        (b'{"skillOverrides": "off"}', "skillOverrides 가 객체가 아니다"),
        (b'{"permissions": {"allow": ["Bash(\xb0\xa1)"]}}', "UTF-8 이 아니다"),
    ],
    ids=["JSON", "맨_위", "skillOverrides", "cp949"],
)
def test_풀지_못하는_설정은_고치지_않고_까닭과_함께_알린다(
    tmp_path: Path, data: bytes, reason: str
) -> None:
    worktree = _워크트리(tmp_path, "x")
    (tmp_path / LOCAL).write_bytes(data)

    notice = apply(tmp_path, worktree)

    assert notice is not None and "끄지 못했다" in notice and reason in notice
    assert (tmp_path / LOCAL).read_bytes() == data


def _띄운다(root: Path, payload: HookPayload, **env: str) -> subprocess.CompletedProcess[str]:
    child = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
    child.update({"CLAUDE_PROJECT_DIR": str(root), **env})
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=child,
        check=False,
    )


def test_main_은_적은_뒤_사용자에게만_알린다(tmp_path: Path) -> None:
    worktree = _워크트리(tmp_path, "x")

    result = _띄운다(tmp_path, _진입(worktree))

    assert result.returncode == 0, result.stderr
    output: Json = json.loads(result.stdout)
    assert isinstance(output, dict) and set(output) == {"systemMessage"}
    assert f"{KEY_PREFIX}x:tdd" in json.dumps(_로컬(tmp_path))


def test_main_은_클라우드_세션에서_쓰지_않고_침묵한다(tmp_path: Path) -> None:
    """클라우드 체크아웃에는 `settings.local.json` 을 무시하는 사용자 전역 ignore 가 없어, 쓰면
    추적하지 않는 파일로 남는다(2026-10-19 클라우드 컨테이너의 `git check-ignore` 가 1 이었다)."""
    worktree = _워크트리(tmp_path, "x")

    result = _띄운다(tmp_path, _진입(worktree), CLAUDE_CODE_REMOTE="true")

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not (tmp_path / LOCAL).exists()
