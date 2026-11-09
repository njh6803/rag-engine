"""tools/tidy_checkouts.py 의 판정과 삭제.

판정은 순수 함수로, 배관(`main`)은 임시 저장소의 실제 git 워크트리로 잰다. `gh` 와 잠금 pid 는
가짜로 준다. 윈도에서 다른 프로세스가 워크트리를 쥐었을 때의 실제 동작(이름 바꾸기가 막히는지,
git 이 지우다 만 폴더를 남기는지)은 CI(우분투)에서 재지 못해 `.scratch/harness/probes/
worktree_occupancy.py` 가 잰다. 여기서는 그 실패를 가짜 `rename`·`delete`·`git` 으로 넣는다.
"""

from __future__ import annotations

import ast
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Generator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from tools.hook_worktree_skill_overrides import KEY_PREFIX as HOOK_KEY_PREFIX
from tools.tidy_checkouts import (
    APP_MARKER,
    FRESH_SECONDS,
    SESSION_ENV,
    WORKTREE_OVERRIDE_PREFIX,
    Facts,
    Holder,
    Ops,
    StrayFacts,
    ToolError,
    Worktree,
    blob_ids,
    combine_holders,
    cut_links,
    cwd_holders,
    delete_path,
    describe_holders,
    dos_path,
    fold_ignored,
    hold_for_strangers,
    holders_in,
    holds_home,
    is_fresh,
    is_within,
    judge,
    judge_branch,
    judge_stray,
    lock_pid,
    long_path,
    looks_text,
    main,
    parse_merged,
    parse_worktrees,
    process_alive,
    process_session,
    real_git,
    same_path,
    scan_modules,
    session_in,
    settings_equivalent,
    tasklist_has,
    touched_at,
    tracked_dirs,
    tracked_links,
    unrecreatable,
)

from tools import tidy_checkouts

_HEAD = "b" * 40
_OLD = "a" * 40
# 가짜 세션 id. 실제 자식 프로세스의 환경에도 넣는다. 이 PC 의 어느 세션과도 겹치지 않는다
_SESSION = "local_00000000-0000-0000-0000-000000000001"
_OTHER_SESSION = "local_00000000-0000-0000-0000-000000000002"
_CALLER = "local_00000000-0000-0000-0000-000000000003"
_TOOL = Path(__file__).resolve().parents[2] / "tools" / "tidy_checkouts.py"


_WT = Worktree("C:/repo/.claude/worktrees/x", _HEAD, "chore/x")
_FACTS = Facts(
    exists=True,
    toplevel="C:/repo/.claude/worktrees/x",
    status="",
    status_err="",
    ignored=(),
    settings_same=True,
)


_MERGED = {"chore/x": frozenset({_HEAD})}


def _죽었다(_pid: int) -> bool:
    return False


def _살았다(_pid: int) -> bool:
    return True


# --- 읽기 ---------------------------------------------------------------------------------------


def test_워크트리_목록의_porcelain_을_읽는다() -> None:
    porcelain = (
        "worktree C:/repo\nHEAD " + _OLD + "\nbranch refs/heads/main\n\n"
        "worktree C:/repo/.claude/worktrees/a\nHEAD " + _HEAD + "\nbranch refs/heads/chore/a\n"
        "locked claude session a (pid 42)\n\n"
        "worktree C:/repo/.claude/worktrees/b\nHEAD " + _HEAD + "\ndetached\n\n"
        "worktree C:/repo/.claude/worktrees/c\nHEAD " + _HEAD + "\nbranch refs/heads/chore/c\n"
        "locked\nprunable gitdir file points to non-existent location\n\n"
    )
    assert parse_worktrees(porcelain) == [
        Worktree("C:/repo", _OLD, "main"),
        Worktree("C:/repo/.claude/worktrees/a", _HEAD, "chore/a", "claude session a (pid 42)"),
        Worktree("C:/repo/.claude/worktrees/b", _HEAD, None),
        Worktree("C:/repo/.claude/worktrees/c", _HEAD, "chore/c", "", prunable=True),
    ]


def test_잠금_사유에서_pid_를_읽는다() -> None:
    assert lock_pid("claude session 01-tokens (pid 29908)") == 29908
    assert lock_pid("") is None
    assert lock_pid("사람이 잠갔다") is None
    assert lock_pid("claude session a (pid 1) 덧붙임") is None


def test_병합된_PR_목록을_브랜치마다_머리의_집합으로_읽는다() -> None:
    text = (
        '[{"headRefName": "chore/a", "headRefOid": "' + _HEAD + '"},'
        ' {"headRefName": "chore/a", "headRefOid": "' + _OLD + '"},'
        ' {"headRefName": "chore/b", "headRefOid": "' + _OLD + '"}]'
    )
    assert parse_merged(text) == {
        "chore/a": frozenset({_HEAD, _OLD}),
        "chore/b": frozenset({_OLD}),
    }


@pytest.mark.parametrize(
    "text",
    [
        '{"headRefName": "a"}',
        "1",
        '[{"headRefName": 1, "headRefOid": "x"}]',
        '[{"headRefName": "a"}]',
        "[1]",
        "아님",
    ],
)
def test_병합된_PR_목록의_모양이_어긋나면_멈춘다(text: str) -> None:
    with pytest.raises(ValueError):
        parse_merged(text)


def test_tasklist_의_CSV_에서_pid_칸만_본다() -> None:
    output = '"claude.exe","29908","Console","1","123,456 K"\n'
    assert tasklist_has(output, 29908)
    assert not tasklist_has(output, 2990)
    assert not tasklist_has("정보: 지정된 조건에 맞는 작업이 실행되고 있지 않습니다.\n", 29908)


def test_작업_디렉터리가_폴더_자신이거나_그_아래일_때만_쥔_것으로_본다() -> None:
    folder = "C:/repo/.claude/worktrees/x"
    if sys.platform == "win32":
        assert is_within("c:\\repo\\.claude\\worktrees\\X\\", folder)
        # 작업 디렉터리를 `\\?\` 머리째 옮긴 프로세스는 PEB 에 그 머리가 남는다(PR 직전 버그 리뷰)
        assert is_within(r"\\?\C:\repo\.claude\worktrees\x\deep", folder)
    assert is_within("C:/repo/.claude/worktrees/x/", folder)
    assert is_within("C:/repo/.claude/worktrees/x/web/node_modules", folder)
    assert not is_within("C:/repo/.claude/worktrees/x2", folder)
    assert not is_within("C:/repo/.claude/worktrees", folder)


def test_쥔_프로세스는_이름과_pid_로_적고_못_찾은_것과_볼_수_없는_것을_가른다() -> None:
    found = [Holder(61148, "claude.exe"), Holder(7, "")]
    assert describe_holders(found) == (
        "작업 디렉터리로 쥔 프로세스: claude.exe(pid 61148), (이름 모름)(pid 7)"
    )
    # 읽지 못한 프로세스(다른 사용자, 높은 권한)가 있고, 리눅스는 모듈을 보지 않아 한쪽 훑기만으로도
    # 빈 목록이 온다. 그래서 무엇을 보았는지 단정하지 않는다
    assert describe_holders([]).startswith("읽을 수 있는 프로세스에서 쥔 것을 찾지 못했다")
    assert describe_holders(None).startswith("쥔 프로세스를 찾지 못했다")


def test_모듈을_올린_프로세스는_작업_디렉터리로_쥔_것과_갈라_적는다() -> None:
    """대기열 201. 다른 워크트리 세션의 pytest 가 하드링크로 같은 `.pyd` 를 올리고 있었다."""
    found = [Holder(61148, "claude.exe"), Holder(26016, "python.exe", "module")]
    assert describe_holders(found) == (
        "작업 디렉터리로 쥔 프로세스: claude.exe(pid 61148); "
        "모듈을 올린 프로세스: python.exe(pid 26016)"
    )
    assert describe_holders([Holder(26016, "python.exe", "module")]) == (
        "모듈을 올린 프로세스: python.exe(pid 26016)"
    )


def test_모듈은_프로세스마다_하나로_모은다() -> None:
    folder = "C:/repo/.claude/worktrees/x"
    modules = [
        (26016, "python.exe", "C:/repo/.claude/worktrees/x/.venv/Lib/a.pyd"),
        (26016, "python.exe", "C:/repo/.claude/worktrees/x/.venv/Lib/b.pyd"),
        (26016, "python.exe", "C:/repo/.venv/Lib/a.pyd"),
        (7, "node.exe", "C:/repo/.claude/worktrees/x2/web/node_modules/a.node"),
    ]
    assert holders_in(modules, folder, "module") == [Holder(26016, "python.exe", "module")]


@pytest.mark.parametrize(
    "error",
    [OSError("dll"), AttributeError("K32EnumProcessModulesEx"), ctypes.ArgumentError("bad")],
)
def test_모듈을_읽다_실패하면_볼_수_없는_것으로_돌려준다(
    error: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing() -> None:
        raise error

    # CI(우분투)에서도 예외를 삼키는 갈래를 밟도록 윈도로 보이게 한다(PR 직전 버그 리뷰)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(tidy_checkouts, "_windows_modules", failing, raising=False)
    assert scan_modules() is None


@pytest.mark.parametrize(
    "error",
    [
        OSError("dll"),
        AttributeError("K32EnumProcesses"),
        ctypes.ArgumentError("bad"),
        ValueError("x"),
    ],
)
def test_프로세스를_읽다_실패하면_볼_수_없는_것으로_돌려준다(
    error: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR #182 claude-review: 진단을 읽다 난 예외가 판정 4의 1의 이유 줄을 지우지 않게 한다."""

    def failing() -> None:
        raise error

    monkeypatch.setattr(tidy_checkouts, "_process_cwds", failing)
    assert cwd_holders(Path("C:/repo/.claude/worktrees/x")) is None


@contextmanager
def _자식이_쥔다(folder: Path, session: str | None = None) -> Generator[int]:
    """`folder` 를 작업 디렉터리로 쥔 자식 파이썬을 띄우고, 준비되면 그 pid 를 내준다. 환경의
    세션 id 는 `session` 으로 정한다. 이 시험을 돌린 세션의 id 를 물려주지 않는다."""
    script = "import sys\nprint('ready', flush=True)\nsys.stdin.read()\n"
    env = {key: value for key, value in os.environ.items() if key != SESSION_ENV}
    if session is not None:
        env[SESSION_ENV] = session
    child = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=folder,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdin is not None
    assert child.stdout is not None
    try:
        assert child.stdout.readline().strip() == "ready"
        yield child.pid
    finally:
        child.stdin.close()
        child.wait(timeout=10)


def test_폴더를_작업_디렉터리로_쥔_자식_프로세스를_찾는다(tmp_path: Path) -> None:
    """CI(우분투)는 `/proc` 로, 윈도는 PEB 로 읽는다. 다른 OS 는 볼 수 없다고 돌려준다."""
    folder = tmp_path / "wt"
    (folder / "deep").mkdir(parents=True)
    with _자식이_쥔다(folder / "deep") as pid:
        found = cwd_holders(folder)
    if sys.platform not in ("win32", "linux"):
        assert found is None
        return
    assert found is not None
    mine = [holder for holder in found if holder.pid == pid]
    assert mine, f"자식 pid {pid} 가 없다: {found}"
    assert mine[0].image
    assert os.getpid() not in {holder.pid for holder in found}


def test_자식_프로세스의_환경에서_세션_id_를_읽는다(tmp_path: Path) -> None:
    """CI(우분투)는 `/proc/<pid>/environ` 으로, 윈도는 PEB 의 환경 블록으로 읽는다. 다른 OS 는
    읽을 수 없다고(None) 돌려준다."""
    with _자식이_쥔다(tmp_path, _SESSION) as pid:
        found = process_session(pid)
    with _자식이_쥔다(tmp_path) as pid:
        missing = process_session(pid)
    if sys.platform not in ("win32", "linux"):
        assert found is None
        return
    assert found == _SESSION
    assert missing is None


def _적재할_DLL() -> Path:
    """복사해 올릴 확장 모듈. 표준 라이브러리의 `.pyd` 다(윈도에서만 부른다)."""
    found = sorted(Path(sys.base_prefix, "DLLs").glob("*.pyd"))
    assert found, "표준 라이브러리의 .pyd 를 찾지 못했다"
    return found[0]


@contextmanager
def _자식_파이썬(code: str) -> Generator[int]:
    """`code` 를 돈 뒤 기다리는 자식 파이썬을 띄우고 그 실제 파이썬의 pid 를 내준다. uv 의 venv
    파이썬은 실행기라 `Popen.pid` 가 실제 파이썬이 아니다. 작업 디렉터리는 이 테스트의 것이다."""
    script = f"import ctypes, os, sys\n{code}\nprint(os.getpid(), flush=True)\nsys.stdin.read()\n"
    child = subprocess.Popen(
        [sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    assert child.stdin is not None
    assert child.stdout is not None
    try:
        line = child.stdout.readline().strip()
        assert line.isdigit(), line
        yield int(line)
    finally:
        child.stdin.close()
        child.wait(timeout=10)


def _자식이_올린다(module: Path) -> AbstractContextManager[int]:
    return _자식_파이썬(f"lib = ctypes.WinDLL({str(module)!r})")


@pytest.mark.parametrize("linked", [False, True], ids=["폴더_안_이름", "폴더_밖_하드링크"])
def test_폴더_아래_모듈을_올린_자식_프로세스를_찾는다(tmp_path: Path, *, linked: bool) -> None:
    """대기열 201. 윈도는 올린 모듈의 매핑 이름과 그 파일의 하드링크 이름을 본다. uv 의 `.venv` 는
    기본으로 캐시에서 하드링크로 채워져, 다른 체크아웃의 파이썬이 올린 `.pyd` 가 이 폴더의 이름도
    막는다. 갈래는 `.scratch/harness/probes/module_holder.py` 의 G·E 와 같다. 윈도 밖은 볼 수 없다고
    돌려준다(적재한 모듈이 지우기를 막지 않는다고 알고 있다)."""
    if sys.platform != "win32":
        assert scan_modules() is None
        return
    folder = tmp_path / "wt"
    (folder / "deep").mkdir(parents=True)
    inside = folder / "deep" / "mod.pyd"
    outside = tmp_path / "outside.pyd"
    shutil.copyfile(_적재할_DLL(), outside if linked else inside)
    if linked:
        os.link(outside, inside)
    with _자식이_올린다(outside if linked else inside) as pid:
        found = holders_in(scan_modules(), str(folder), "module")
    assert found is not None
    assert Holder(pid, "python.exe", "module") in found, found
    assert os.getpid() not in {holder.pid for holder in found}


def test_윈도_폴더_아래_모듈의_다른_하드링크_이름은_펼치지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """못 보는 것을 고정한다. `SystemRoot` 아래에서 올린 모듈이 이 폴더의 이름과 같은 파일이어도
    대지 않는다(지나간다)."""
    if sys.platform != "win32":
        assert scan_modules() is None
        return
    system = tmp_path / "windows"
    system.mkdir()
    folder = tmp_path / "wt"
    folder.mkdir()
    loaded = system / "mod.pyd"
    shutil.copyfile(_적재할_DLL(), loaded)
    os.link(loaded, folder / "mod.pyd")
    with _자식이_올린다(loaded) as pid:
        # 자식이 뜬 뒤에 바꾼다. 자식의 환경에 가짜 SystemRoot 가 들어가지 않게 한다
        monkeypatch.setenv("SystemRoot", str(system))
        found = holders_in(scan_modules(), str(folder), "module")
    assert found is not None
    assert pid not in {holder.pid for holder in found}


def test_긴_경로_머리는_절대_경로를_정규화하지_않고_붙인다() -> None:
    """PR 직전 버그 리뷰. 끝의 점과 장치 이름을 지키고, 네트워크 공유는 `UNC` 머리를 쓴다."""
    if sys.platform != "win32":
        assert long_path("/repo/x/trail.") == "/repo/x/trail."
        return
    assert long_path("C:/repo/x/trail.") == "\\\\?\\C:\\repo\\x\\trail."
    assert long_path("C:\\repo\\x\\nul") == "\\\\?\\C:\\repo\\x\\nul"
    assert long_path("\\\\server\\share\\x") == "\\\\?\\UNC\\server\\share\\x"
    assert long_path("\\\\?\\C:\\repo\\x") == "\\\\?\\C:\\repo\\x"


def test_드라이브_문자가_없는_장치의_매핑_이름은_버린다() -> None:
    """못 보는 것을 고정한다. 네트워크 공유(`\\Device\\Mup`)에서 올린 모듈은 경로로 바꾸지
    못한다."""
    drives = {"\\Device\\HarddiskVolume2": "C:"}
    assert dos_path("\\Device\\HarddiskVolume2\\repo\\x.pyd", drives) == "C:\\repo\\x.pyd"
    assert dos_path("\\Device\\Mup\\server\\share\\x.pyd", drives) is None
    # 장치 이름의 앞부분만 같은 다른 장치는 그 드라이브가 아니다
    assert dos_path("\\Device\\HarddiskVolume22\\x.pyd", drives) is None


# --- 판정 2: 다시 만들 수 있는 무시된 것 ----------------------------------------------------------


def test_다시_만들_수_있는_무시된_것만_지나간다() -> None:
    entries = [
        ".venv/",
        "src/agent_os/__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".import_linter_cache/",
        ".grimp_cache/",
        "web/node_modules/",
        "web/apps/admin/.next/",
        "web/apps/admin/next-env.d.ts",
        "web/packages/ui/visual/test-results/",
        "web/apps/admin/playwright-report/",
        "web/apps/admin/blob-report/",
        "web/apps/admin/coverage/",
        "web/packages/ui/dist/",
        "web/packages/ui/storybook-static/",
        "web/apps/widget/storybook-static/",
        "web/apps/widget/public/fonts/",
        # 위젯 시작 래퍼가 짓는 페이지 안 번들(티켓 web-widget 10, 대기열 464)
        "web/apps/widget/public/element.js",
        # 관리 화면의 Storybook 정적 빌드(admin-style 티켓 03)
        "web/apps/admin/storybook-static/",
        ".claude/settings.local.json",
        # 2026-10-15 에 병합된 워크트리 다섯을 남긴 것들. 모두 루트 `.gitignore` 가 산출물·캐시라고
        # 적은 자리다
        ".ds-sync/",
        "ds-bundle/",
        ".design-sync/sb-reference/",
        ".design-sync/.cache/",
        ".scratch/harness/probes/session_cost/cache/",
        "grep.exe.stackdump",
    ]
    assert unrecreatable(entries, settings_same=True) == []


def test_다시_만들_수_없는_무시된_것을_돌려준다() -> None:
    """자리째로 보는 폴더와 파일은 같은 이름이 다른 자리에 있으면 다시 만들 수 없는 것이다. 플랜
    모드의 계획 파일은 세션의 계획 원문이라 산출물이 아니다. 접힌 폴더(`web/apps/widget/public/`)는
    그 안을 모르니 다시 만들 수 없는 것이다. 그래서 `gather` 가 git 의 접힘 없이 읽는다(대기열
    464). 폴더 안의 항목은 그 이름으로만 본다. 조상 폴더로 접는 것은 `fold_ignored` 다."""
    entries = [
        ".env",
        "traces/",
        ".claude/plans/",
        ".design-sync/learnings/",
        "web/.cache/",
        "web/apps/admin/dist/",
        ".venv/",
        "x.pyc",
        "stackdump",
        "web/apps/widget/public/",
        "web/apps/admin/public/element.js",
        "element.js",
        "web/apps/widget/public/element.js/",
        "a.grimp_cache/x.json",
        "x/.grimp_cache",
        "notes/.gitignore",
        "web/apps/widget/public/fontsx/a.woff2",
        "web/apps/widget/public/element.js/x",
    ]
    assert unrecreatable(entries, settings_same=True) == [
        ".env",
        "traces/",
        ".claude/plans/",
        ".design-sync/learnings/",
        "web/.cache/",
        "web/apps/admin/dist/",
        "x.pyc",
        "stackdump",
        "web/apps/widget/public/",
        "web/apps/admin/public/element.js",
        "element.js",
        "web/apps/widget/public/element.js/",
        "a.grimp_cache/x.json",
        "x/.grimp_cache",
        "notes/.gitignore",
        "web/apps/widget/public/fontsx/a.woff2",
        "web/apps/widget/public/element.js/x",
    ]


def test_루트와_다른_설정_파일은_다시_만들_수_없다() -> None:
    assert unrecreatable([".claude/settings.local.json"], settings_same=False) == [
        ".claude/settings.local.json"
    ]


def test_같은_이름의_파일은_다시_만들_수_있는_폴더가_아니다() -> None:
    assert unrecreatable([".venv", "node_modules"], settings_same=True) == [".venv", "node_modules"]


def _링크_없음(_relative: str) -> bool:
    return False


def _추적_없음(_relative: str) -> bool:
    return False


def test_무시된_항목을_가장_바깥의_다시_만들_수_있는_폴더로_접는다() -> None:
    """안쪽 `.gitignore` 로만 무시되는 폴더는 `matching` 이 그 안을 하나씩 찍는다. Grimp 는
    `.grimp_cache/` 안의 `.gitignore` 에 `*` 를 둔다(셀프 리뷰 명세 축). 폴더째 접어야 옮기기가 그
    폴더를 한 번에 옮긴다. 하나씩 옮기다 막히면 먼저 옮긴 안쪽 `.gitignore` 가 빠져 남은 항목이
    미추적이 된다(PR 직전 bug-perf-review). 접은 자리는 처음 나온 차례로 한 번만 든다."""
    entries = [
        ".grimp_cache/.gitignore",
        ".grimp_cache/CACHEDIR.TAG",
        ".grimp_cache/sub/",
        ".grimp_cache/x/node_modules/",
        "src/.grimp_cache/a.data.json",
        "web/apps/widget/public/fonts/a.woff2",
        ".venv/",
        "web/apps/widget/public/element.js",
    ]
    assert fold_ignored(entries, _링크_없음, _추적_없음) == (
        ".grimp_cache/",
        "src/.grimp_cache/",
        "web/apps/widget/public/fonts/",
        ".venv/",
        "web/apps/widget/public/element.js",
    )


def test_다시_만들_수_있는_폴더가_아닌_조상으로는_접지_않는다() -> None:
    """반박 시험. 조상 폴더는 다시 만들 수 있는 폴더의 이름이나 폴더 자리와 맞아야 하고, 이름이
    비슷한 폴더와 파일 자리(끝에 `/` 가 없는 `element.js`)는 조상이 되지 않는다."""
    entries = [
        "a.grimp_cache/x.json",
        "x/.grimp_cache",
        "notes/.gitignore",
        "web/apps/widget/public/fontsx/a.woff2",
        "web/apps/widget/public/element.js/x",
    ]
    assert fold_ignored(entries, _링크_없음, _추적_없음) == tuple(entries)


def test_무시된_항목을_가장_바깥의_링크로_접는다() -> None:
    """윈도의 git 2.32 는 정션을 따라가 `matching` 으로 그 안을 하나씩 찍는다(PR 직전
    bug-perf-review 가 재현했다). 링크 안의 항목을 옮기면 링크 바깥의 파일이 옮겨지므로 링크째로
    접는다. 그러면 링크는 제 이름으로 판정된다. 링크와 다시 만들 수 있는 폴더가 겹치면 더 바깥의
    것으로 접는다."""
    links = {"foo", "a/b", ".grimp_cache/l", "bar"}
    entries = [
        "foo/node_modules/",
        "foo/a.stackdump",
        "a/b/c/x.pyc",
        "a/y.stackdump",
        ".grimp_cache/l/x.json",
        "bar/.grimp_cache/a.json",
    ]
    assert fold_ignored(entries, links.__contains__, _추적_없음) == (
        "foo/",
        "a/b/",
        "a/y.stackdump",
        ".grimp_cache/",
        "bar/",
    )
    assert unrecreatable(["foo/", "a/b/"], settings_same=True) == ["foo/", "a/b/"]


def test_추적_파일이_든_조상으로는_링크가_아니면_접지_않는다() -> None:
    """PR 봇 CodeRabbit. 추적 파일이 든 폴더로 접으면 옮기기가 추적 파일까지 옮긴다. 그 폴더는
    건너뛰고 더 안쪽 조상을 본다. 링크는 추적 파일이 든 것으로 보여도 링크째로 접는다. 안을 하나씩
    옮기면 링크 바깥이 옮겨진다."""
    tracked = {"coverage", "a", "a/node_modules", "lnk"}
    links = {"lnk"}
    entries = [
        "coverage/.env",
        "coverage/node_modules/pkg/index.js",
        "a/node_modules/b/x.js",
        "lnk/x.json",
    ]
    assert fold_ignored(entries, links.__contains__, tracked.__contains__) == (
        "coverage/.env",
        "coverage/node_modules/",
        "a/node_modules/b/x.js",
        "lnk/",
    )


def test_tracked_dirs_는_추적_파일이_든_폴더를_모두_든다() -> None:
    """견줄 쪽과 함께 `normcase` 로 맞춰, 윈도에서는 대소문자만 다른 자리도 든 것으로 본다."""
    listing = "README.md\0coverage/keep.txt\0a/b/c.py\0"
    expected = {os.path.normcase(folder) for folder in ("coverage", "a", "a/b")}
    assert tracked_dirs(listing) == frozenset(expected)
    upper = os.path.normcase("COVERAGE") in tracked_dirs("coverage/keep.txt\0")
    assert upper == (sys.platform == "win32")


def test_tracked_links_는_추적_파일이_든_폴더_가운데_링크를_든다() -> None:
    """PR 직전 bug-perf-review 의 대체 리뷰. 추적 폴더를 갈음한 정션은 안에 무시된 것이 없으면
    `status` 에 아무것도 찍히지 않는다. 그래서 무시된 항목이 아니라 추적 파일이 든 폴더에서 링크를
    찾는다. 폴더마다 한 번만 보고, 링크 안의 폴더는 보지 않는다."""
    links = {"a/b", "coverage", "coverage/sub"}
    listing = "README.md\0a/b/c.py\0a/b/d.py\0a/x.py\0coverage/keep.txt\0coverage/sub/y.txt\0"
    seen: list[str] = []

    def is_link(relative: str) -> bool:
        seen.append(relative)
        return relative in links

    assert tracked_links(listing, is_link) == ("a/b/", "coverage/")
    assert seen == ["a", "a/b", "coverage"]


_HOOK_KEY = f"{HOOK_KEY_PREFIX}x:tdd"


@pytest.mark.parametrize(
    ("root", "worktree", "same"),
    [
        (b'{"env": {"A": "1"}}', b'{"env": {"A": "1"}}', True),
        (
            json.dumps(
                {"env": {"A": "1"}, "skillOverrides": {_HOOK_KEY: "off"}}, indent=2
            ).encode(),
            b'{"env": {"A": "1"}}',
            True,
        ),
        (b"{}", f'{{"skillOverrides": {{"{_HOOK_KEY}": "off"}}}}'.encode(), True),
        (
            f'{{"skillOverrides": {{"jira-start": "off", "{_HOOK_KEY}": "off"}}}}'.encode(),
            b'{"skillOverrides": {"jira-start": "off"}}',
            True,
        ),
        (b'{"permissions": {"allow": ["Bash(ls:*)"]}}', b"{}", False),
        (b"{}", b'{"permissions": {"allow": ["Bash(ls:*)"]}}', False),
        (b'{"skillOverrides": {"jira-start": "off"}}', b'{"skillOverrides": {}}', False),
        (b"{}", b"{\xb0", False),
        (b"[]", b"[ ]", False),
    ],
    ids=[
        "바이트가_같다",
        "루트에_훅의_키와_서식만_더했다",
        "워크트리에만_훅의_키",
        "다른_skillOverrides_키는_같다",
        "루트에만_다른_권한",
        "워크트리에만_다른_권한",
        "다른_skillOverrides_키가_다르다",
        "풀리지_않는다",
        "객체가_아니다",
    ],
)
def test_설정은_훅이_적는_워크트리_사본_키와_서식을_빼고_견준다(
    root: bytes, worktree: bytes, *, same: bool
) -> None:
    """대기열 274 의 훅(`tools/hook_worktree_skill_overrides.py`)이 주 체크아웃의 local 설정에
    `.claude/worktrees/` 키를 적고 다시 써도, 그 키 밖이 같은 워크트리 사본은 다시 만들 수 있다.
    그 밖의 차이(권한, 다른 스킬 설정)와 풀리지 않는 파일은 지금처럼 남긴다."""
    assert settings_equivalent(root, worktree) is same


def test_설정에서_빼는_키의_접두는_훅이_적는_접두와_같다() -> None:
    """훅끼리만 import 하지 않으므로 이 도구는 접두를 따로 둔다. 둘이 갈리면 지우는 판정이 조용히
    좁아지거나 넓어진다."""
    assert WORKTREE_OVERRIDE_PREFIX == HOOK_KEY_PREFIX


# --- 판정 ---------------------------------------------------------------------------------------


def test_모두_맞으면_지운다() -> None:
    verdict = judge(_WT, _FACTS, _MERGED, (), _죽었다, ())
    assert verdict.action == "delete"
    assert (verdict.branch, verdict.head, verdict.unlock) == ("chore/x", _HEAD, False)


def test_prunable_인데_폴더가_있으면_git_이_있을_때만_사람에게_넘긴다() -> None:
    """`.git` 없는 폴더는 지우다 만 폴더라 등록 없는 폴더의 판정으로 내용을 가른다(`_judge_all`)."""
    verdict = judge(replace(_WT, prunable=True), _FACTS, _MERGED, (), _죽었다, ())
    assert verdict.action == "human"
    assert "prunable" in verdict.reason
    dead = judge(replace(_WT, prunable=True), replace(_FACTS, has_git=False), {}, (), _죽었다, ())
    assert dead.action == "delete"
    assert ".git 이 없다" in dead.reason


def test_폴더가_없으면_등록만_걷도록_지운다() -> None:
    """2026-10-15 에 폴더 없는 prunable 등록 둘이 사람에게 넘겨진 채 남아 있었다. 폴더가 없으면
    잃을 것이 없다. 옆 이름(.tidy-probe)에 폴더가 남았으면 되돌릴 일이라 남긴다(되돌린다 줄이
    따로 찍힌다)."""
    missing = replace(_FACTS, exists=False, toplevel=None)
    verdict = judge(replace(_WT, prunable=True), missing, _MERGED, (), _죽었다, ())
    assert verdict.action == "delete"
    assert "등록만 남았다" in verdict.reason
    assert judge(_WT, missing, {}, (), _죽었다, ()).action == "delete"
    aside = judge(_WT, replace(missing, aside=True), _MERGED, (), _죽었다, ())
    assert aside.action == "keep"
    assert "restore" in aside.reason


def test_폴더가_없어도_잠긴_등록과_origin_main_에_없는_분리_HEAD_는_사람에게_넘긴다() -> None:
    """명세 축 리뷰(Critical). 등록이 그 커밋의 마지막 참조일 수 있어 걷으면 커밋이 매달린다.
    잠금은 이동식 매체를 지키는 수단이라 폴더가 없어도 판정이 남긴다."""
    missing = replace(_FACTS, exists=False, toplevel=None)
    detached = replace(_WT, branch=None)
    outside = judge(detached, missing, {}, (), _죽었다, ())
    assert outside.action == "human"
    assert "origin/main 에 없다" in outside.reason
    inside = judge(detached, replace(missing, contained=True), {}, (), _죽었다, ())
    assert (inside.action, inside.branch) == ("delete", None)
    locked = judge(replace(_WT, locked="이동식 매체"), missing, _MERGED, (), _죽었다, ())
    assert locked.action == "human"
    assert "잠겨" in locked.reason


def test_git_이_다른_저장소를_읽으면_사람에게_넘긴다() -> None:
    root = judge(_WT, replace(_FACTS, toplevel="C:/repo"), _MERGED, (), _죽었다, ())
    assert root.action == "human"
    assert "C:/repo" in root.reason
    assert judge(_WT, replace(_FACTS, toplevel=None), _MERGED, (), _죽었다, ()).action == "human"


def test_toplevel_은_구분자와_대소문자를_가리지_않고_견준다() -> None:
    if sys.platform != "win32":
        facts = replace(_FACTS, toplevel="C:/repo/.claude/worktrees/x/")
    else:
        facts = replace(_FACTS, toplevel="c:\\repo\\.claude\\worktrees\\X")
    assert judge(_WT, facts, _MERGED, (), _죽었다, ()).action == "delete"


def test_분리_HEAD_는_그_커밋이_origin_main_에_있을_때만_지운다() -> None:
    """2026-10-15 에 분리 HEAD 워크트리 일곱이 넘겨진 채 남아 있었다. 커밋이 `origin/main` 에
    있으면 잃을 것이 없다. 깨끗함과 주인 판정은 브랜치 워크트리와 같이 거친다."""
    detached = replace(_WT, branch=None)
    outside = judge(detached, _FACTS, _MERGED, (), _죽었다, ())
    assert outside.action == "human"
    assert "origin/main 에 없다" in outside.reason
    inside = judge(detached, replace(_FACTS, contained=True), {}, (), _죽었다, ())
    assert (inside.action, inside.branch, inside.head) == ("delete", None, _HEAD)
    assert "origin/main 에 있다" in inside.reason
    dirty = judge(detached, replace(_FACTS, contained=True, status=" M a"), {}, (), _죽었다, ())
    assert dirty.action == "keep"
    held = judge(detached, replace(_FACTS, contained=True), {}, (), _죽었다, _CLAUDE)
    assert held.action == "keep"


def test_병합된_PR_이_없으면_남긴다() -> None:
    verdict = judge(_WT, _FACTS, {}, (), _죽었다, ())
    assert verdict.action == "keep"
    assert "병합된 PR" in verdict.reason


def test_병합된_PR_의_머리가_브랜치_끝과_다르면_사람에게_넘긴다() -> None:
    verdict = judge(_WT, _FACTS, {"chore/x": frozenset({_OLD})}, (), _죽었다, ())
    assert verdict.action == "human"


def test_바뀐_파일이_있으면_남긴다() -> None:
    assert (
        judge(_WT, replace(_FACTS, status="?? new.py\0"), _MERGED, (), _죽었다, ()).action == "keep"
    )


def test_status_가_경고를_내면_남긴다() -> None:
    warned = replace(_FACTS, status_err="warning: could not open directory 'x/': Filename too long")
    assert judge(_WT, warned, _MERGED, (), _죽었다, ()).action == "keep"


def test_다시_만들_수_없는_무시된_것이_있으면_남긴다() -> None:
    verdict = judge(_WT, replace(_FACTS, ignored=(".venv/", ".env")), _MERGED, (), _죽었다, ())
    assert verdict.action == "keep"
    assert ".env" in verdict.reason


def test_설정_파일이_루트와_다르면_남긴다() -> None:
    facts = replace(_FACTS, ignored=(".claude/settings.local.json",), settings_same=False)
    assert judge(_WT, facts, _MERGED, (), _죽었다, ()).action == "keep"


def test_그_브랜치가_제목인_세션이_돌면_남긴다() -> None:
    verdict = judge(_WT, _FACTS, _MERGED, ("chore/x",), _죽었다, ())
    assert verdict.action == "keep"


def test_잠금_pid_가_살아_있으면_남긴다() -> None:
    locked = replace(_WT, locked="claude session x (pid 7)")
    verdict = judge(locked, _FACTS, _MERGED, (), _살았다, ())
    assert verdict.action == "keep"
    assert "7" in verdict.reason
    assert "claude session x" in verdict.reason


def test_잠금_pid_가_죽었으면_풀고_지운다() -> None:
    locked = replace(_WT, locked="claude session x (pid 7)")
    verdict = judge(locked, _FACTS, _MERGED, (), _죽었다, ())
    assert (verdict.action, verdict.unlock) == ("delete", True)


def test_잠금_사유에_pid_가_없으면_사람에게_넘긴다() -> None:
    assert judge(replace(_WT, locked=""), _FACTS, _MERGED, (), _죽었다, ()).action == "human"


_CLAUDE = (Holder(61148, "claude.exe"),)


def test_작업_디렉터리로_쥔_프로세스가_있으면_이름과_pid_를_들어_남긴다() -> None:
    """대기열 186. 쉬는 세션은 `isRunning` 이 아니어도 앱이 띄운 `claude.exe` 가 그 루트를 쥔다."""
    verdict = judge(_WT, _FACTS, _MERGED, (), _죽었다, _CLAUDE)
    assert verdict.action == "keep"
    assert "claude.exe(pid 61148)" in verdict.reason


def test_작업_디렉터리로_쥔_프로세스가_있으면_죽은_잠금도_풀지_않고_남긴다() -> None:
    locked = replace(_WT, locked="claude session x (pid 7)")
    verdict = judge(locked, _FACTS, _MERGED, (), _죽었다, _CLAUDE)
    assert (verdict.action, verdict.unlock) == ("keep", False)


def test_잠금_pid_가_살아_있으면_쥔_프로세스보다_잠금의_세션을_이유로_든다() -> None:
    locked = replace(_WT, locked="claude session x (pid 61148)")
    verdict = judge(locked, _FACTS, _MERGED, (), _살았다, _CLAUDE)
    assert verdict.action == "keep"
    assert "claude session x" in verdict.reason


def test_쥔_것을_하나라도_볼_수_있으면_합친다() -> None:
    cwd = [Holder(1, "claude.exe")]
    module = [Holder(2, "python.exe", "module")]
    assert combine_holders(cwd, module) == [*cwd, *module]
    assert combine_holders(None, module) == module
    assert combine_holders(cwd, None) == cwd
    assert combine_holders([], None) == []
    assert combine_holders(None, None) is None


def test_쥔_프로세스를_볼_수_없으면_판정_4의_점유_탐침에_맡긴다() -> None:
    assert judge(_WT, _FACTS, _MERGED, (), _죽었다, None).action == "delete"


def test_제목_모를_세션이_돌아도_작업_디렉터리로_쥔_워크트리는_넘기지_않고_남긴다() -> None:
    """2026-10-12 의 모양. 넘기면 사람에게 승인을 물어도 `remove` 의 탐침에서 막힐 뿐이다."""
    held = judge(_WT, _FACTS, _MERGED, (), _죽었다, _CLAUDE)
    assert hold_for_strangers([held], ("앱이 지은 이름",), {"main", "chore/x"}) == [held]


def test_폴더_안을_작업_디렉터리로_쥔_프로세스만_고른다() -> None:
    processes = [
        (1, "claude.exe", "C:/repo/.claude/worktrees/x"),
        (2, "python.exe", "C:/repo/.claude/worktrees/x/web"),
        (3, "claude.exe", "C:/repo/.claude/worktrees/x2"),
        (4, "claude.exe", "C:/repo"),
    ]
    assert holders_in(processes, "C:/repo/.claude/worktrees/x") == [
        Holder(1, "claude.exe"),
        Holder(2, "python.exe"),
    ]
    assert holders_in(None, "C:/repo/.claude/worktrees/x") is None


def test_제목이_어느_브랜치와도_맞지_않는_세션이_돌면_프로세스를_못_볼_때만_넘긴다() -> None:
    """2026-10-15 에 실행 중인 세션 다섯의 `claude.exe` 가 모두 그 워크트리를 작업 디렉터리로
    쥐고 있었다(`EnterWorktree` 로 들어간 세션 포함). 그러니 프로세스를 읽을 수 있으면 판정 3이
    이름으로 남기고, 제목으로 전부 넘기는 것은 읽을 수 없는 OS 에서만 한다."""
    delete = judge(_WT, _FACTS, _MERGED, (), _죽었다, ())
    keep = judge(_WT, _FACTS, {}, (), _죽었다, ())
    held = hold_for_strangers([delete, keep], ("앱이 지은 이름",), {"main", "chore/x"})
    assert [verdict.action for verdict in held] == ["hold", "keep"]
    assert "앱이 지은 이름" in held[0].reason


def test_제목이_체크아웃된_브랜치면_다른_워크트리는_그대로다() -> None:
    delete = judge(_WT, _FACTS, _MERGED, (), _죽었다, ())
    assert hold_for_strangers([delete], ("main",), {"main", "chore/x"}) == [delete]


def test_체크아웃되지_않은_브랜치는_병합된_PR_머리와_같을_때만_지운다() -> None:
    assert judge_branch("chore/x", _HEAD, _MERGED, ()).action == "delete"
    assert judge_branch("chore/x", _OLD, _MERGED, ()).action == "human"
    assert judge_branch("chore/y", _HEAD, _MERGED, ()).action == "keep"


def test_병합된_PR_이_없어도_커밋이_모두_origin_main_에_있는_브랜치는_지운다() -> None:
    """2026-10-15 에 `EnterWorktree` 가 만든 `worktree-*` 브랜치 53개가 PR 없이 남아 있었다.
    끝이 `origin/main` 에서 닿으면 잃는 것은 이름뿐이다. `main` 은 루트가 다른 브랜치에 있을 때
    체크아웃되지 않은 브랜치로 보여도 지우지 않는다."""
    gone = judge_branch("worktree-x", _HEAD, {}, (), contained=True)
    assert gone.action == "delete"
    assert "origin/main" in gone.reason
    assert judge_branch("worktree-x", _HEAD, {}, (), contained=False).action == "keep"
    assert judge_branch("main", _HEAD, {}, (), contained=True).action == "keep"
    assert judge_branch("master", _HEAD, {}, (), contained=True).action == "keep"
    # 병합된 PR 의 머리와 다른 끝은 origin/main 에 있어도 사람이 본다
    assert judge_branch("chore/x", _OLD, _MERGED, (), contained=True).action == "human"


def test_체크아웃되지_않은_브랜치도_그_브랜치가_제목인_세션이_돌면_남긴다() -> None:
    """대기열 286. 2026-10-16 에 실행 중인 세션 `chore/mutate-followups` 의 브랜치를 지울 후보로
    냈다. 지우는 두 길(병합된 PR 의 머리, origin/main 에 든 끝) 모두 남긴다. 워크트리처럼 판정 1이
    지울 것으로 낸 뒤에 보므로, 판정 1이 남기거나 넘긴 것은 그 이유를 그대로 든다."""
    by_pr = judge_branch("chore/x", _HEAD, _MERGED, ("chore/x",))
    assert by_pr.action == "keep", by_pr
    assert by_pr.reason == "제목이나 브랜치가 그 브랜치인 세션이 돈다"
    assert judge_branch("worktree-x", _HEAD, {}, ("worktree-x",), contained=True).action == "keep"
    assert judge_branch("chore/x", _HEAD, _MERGED, ("chore/y",)).action == "delete"
    assert judge_branch("chore/x", _OLD, _MERGED, ("chore/x",)).action == "human"
    unmerged = judge_branch("chore/y", _HEAD, _MERGED, ("chore/y",))
    assert unmerged.action == "keep"
    assert "병합된 PR 이 없고" in unmerged.reason


def test_다른_제목은_보지_않고_대소문자만_다르면_브랜치에서는_같다고_본다() -> None:
    """못 보는 것. 앞뒤 공백이나 꼬리가 붙은 제목은 다른 이름으로 본다. 대소문자만 다른 제목은
    체크아웃되지 않은 브랜치에서는 같은 이름으로 보아 남기고 워크트리에서는 다른 이름으로 본다."""
    for title in (" chore/x", "chore/x ", "chore/x (인계함)"):
        assert judge_branch("chore/x", _HEAD, _MERGED, (title,)).action == "delete", title
        assert judge(_WT, _FACTS, _MERGED, (title,), _죽었다, ()).action == "delete", title
    assert judge(_WT, _FACTS, _MERGED, ("Chore/X",), _죽었다, ()).action == "delete"
    assert judge_branch("chore/x", _HEAD, _MERGED, ("Chore/X",)).action == "keep"


def test_브랜치_끝이_병합된_PR_머리의_조상이면_지운다() -> None:
    """2026-10-20 에 `chore/skill-check-and-retro-section` 의 로컬 끝이 PR #114 의 머리보다 커밋
    넷 뒤였다. 로컬에만 있는 커밋이 없어 잃을 것이 없는데 사람에게 넘겼다. 조상인지는 `gather` 가
    git 으로 읽어 `behind` 로 넣는다. 판정 2·3은 그대로 본다."""
    moved = {"chore/x": frozenset({_OLD})}
    verdict = judge(_WT, replace(_FACTS, behind=True), moved, (), _죽었다, ())
    assert verdict.action == "delete", verdict
    assert "머리보다 뒤" in verdict.reason
    assert judge(_WT, _FACTS, moved, (), _죽었다, ()).action == "human"
    dirty = replace(_FACTS, behind=True, status=" M a")
    assert judge(_WT, dirty, moved, (), _죽었다, ()).action == "keep"
    assert judge_branch("chore/x", _HEAD, moved, (), behind=True).action == "delete"
    assert judge_branch("chore/x", _HEAD, moved, ()).action == "human"
    assert judge_branch("chore/x", _HEAD, moved, ("chore/x",), behind=True).action == "keep"


def test_막_딴_브랜치는_PR_없이_origin_main_에_있어도_남긴다() -> None:
    """대기열 440. 막 딴 것인지는 `judge` 와 `remove-branch` 가 reflog 로 읽어 `fresh` 로 넣는다.
    병합된 PR 로 지우는 두 길(머리와 같은 끝, 머리보다 뒤인 끝)은 보지 않는다. 주 체크아웃에서
    병합하고 main 으로 옮긴 직후의 정리가 그 브랜치를 바로 지운다."""
    kept = judge_branch("worktree-x", _HEAD, {}, (), contained=True, fresh=True)
    assert kept.action == "keep", kept
    assert "막 딴 브랜치다" in kept.reason
    assert judge_branch("chore/x", _HEAD, _MERGED, (), fresh=True).action == "delete"
    moved = {"chore/x": frozenset({_OLD})}
    assert judge_branch("chore/x", _HEAD, moved, (), behind=True, fresh=True).action == "delete"
    main_branch = judge_branch("main", _HEAD, {}, (), contained=True, fresh=True)
    assert main_branch.reason == "지우지 않는 브랜치다"


def test_reflog_의_마지막_기록이_창_안이거나_앞날이면_막_딴_것이다() -> None:
    """앞날 시각의 기록은 시계가 어긋난 PC 가 남긴 것이라 잰 나이를 믿지 않고 남기는 쪽이다. 기록이
    없으면 막 딴 것인지 모른다(못 보는 것)."""
    now = 1_800_000_000.0
    assert is_fresh(int(now) - FRESH_SECONDS + 1, now)
    assert not is_fresh(int(now) - FRESH_SECONDS, now)
    assert is_fresh(int(now) + 600, now)
    assert not is_fresh(None, now)


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("chore/x@{1792996632}\n", 1792996632),
        # git 은 브랜치 이름에 `@` 를 허락하고 `@{` 는 허락하지 않는다
        ("a@b@{1792996632}\n", 1792996632),
        ("", None),
        ("chore/x@{now}\n", None),
        ("chore/x\n", None),
    ],
    ids=["기록", "이름에_골뱅이", "기록_없음", "숫자가_아니다", "선택자가_없다"],
)
def test_reflog_의_선택자에서_기록_시각을_읽는다(printed: str, expected: int | None) -> None:
    """`git log -g -n 1 --format=%gd --date=unix` 의 출력. git 2.32 가 `chore/x@{1792996632}` 로
    찍는 것을 임시 저장소에서 손으로 봤다."""
    assert touched_at(printed) == expected


def test_앱의_표지가_있는_워크트리는_넘기지_않고_앱의_정리에_맡긴다() -> None:
    """2026-10-20 에 앱이 만든 분리 HEAD 워크트리 둘(`confident-wright-2d3ebf` 등)을 사람에게
    넘겼고, 시험하는 동안 앱이 그중 하나를 새 세션에 다시 내주었다. 표지가 있으면 앱의 정리
    (`[WorktreePool]`)가 지우므로 판정 1보다 먼저 남긴다(ADR 0032)."""
    marked = replace(_FACTS, app_marker=True)
    for wt, merged in ((_WT, _MERGED), (replace(_WT, branch=None), {})):
        verdict = judge(wt, marked, merged, (), _죽었다, ())
        assert verdict.action == "keep", verdict
        assert "claude-desktop-worktree" in verdict.reason


def test_쥔_프로세스가_모두_쉬는_세션의_것이면_끝낼_것으로_낸다() -> None:
    """2026-10-20. 병합되고 깨끗한 워크트리를 쉬는 세션(`isRunning` 이 아니다)의 `claude.exe` 가
    작업 디렉터리로 쥐어 남았다. 앱은 보관하기 전까지 그 프로세스를 띄워 둔다. 쥔 프로세스마다
    환경의 세션 id 를 읽어, 모두 부르는 쪽이 쉰다고 넘긴 세션의 것이면 끝낼 것으로 낸다."""
    owners = {61148: _SESSION}
    verdict = judge(_WT, _FACTS, _MERGED, (), _죽었다, _CLAUDE, owners=owners, idle={_SESSION})
    assert (verdict.action, verdict.sessions) == ("end", (_SESSION,)), verdict
    assert f"claude.exe(pid 61148, 세션 {_SESSION})" in verdict.reason


def test_쉰다고_받지_않은_세션이나_세션_모를_프로세스가_쥐면_남긴다() -> None:
    owners = {61148: _SESSION}
    idle = {_SESSION}
    mixed = (*_CLAUDE, Holder(7, "pwsh.exe"))
    unknown = judge(_WT, _FACTS, _MERGED, (), _죽었다, mixed, owners=owners, idle=idle)
    assert unknown.action == "keep", "세션 모를 프로세스가 섞였다"
    other = judge(
        _WT, _FACTS, _MERGED, (), _죽었다, _CLAUDE, owners={61148: _OTHER_SESSION}, idle=idle
    )
    assert other.action == "keep", "받지 않은 세션의 프로세스다"
    assert _OTHER_SESSION in other.reason
    assert judge(_WT, _FACTS, _MERGED, (), _죽었다, _CLAUDE, owners=owners).action == "keep"
    # 앞의 판정(판정 2, 실행 중 세션)이 먼저다
    dirty = replace(_FACTS, status=" M a")
    assert (
        judge(_WT, dirty, _MERGED, (), _죽었다, _CLAUDE, owners=owners, idle=idle).action == "keep"
    )
    running = ("chore/x",)
    kept = judge(_WT, _FACTS, _MERGED, running, _죽었다, _CLAUDE, owners=owners, idle=idle)
    assert kept.action == "keep"


def test_잠금_pid_가_쉬는_세션의_쥔_프로세스이면_끝낼_것으로_낸다() -> None:
    """셀프 리뷰 명세 축. 잠금 pid 는 그 워크트리를 연 세션의 `claude.exe` 다. 그 세션이 쉬면 잠금도
    쥔 프로세스로 끝낸다. 잠금 pid 가 쥔 것에 없거나(부르는 쪽이 넣지 않았다) 받지 않은 세션의
    것이면 잠금의 세션을 이유로 남긴다. 그대로 두면 판정이 `지운다` 로 흘러 산 잠금을 푼다."""
    locked = replace(_WT, locked="claude session x (pid 7)")
    lock = Holder(7, "", "lock")
    idle = {_SESSION}
    owners = {7: _SESSION, 61148: _SESSION}
    held = (*_CLAUDE, lock)
    verdict = judge(locked, _FACTS, _MERGED, (), _살았다, held, owners=owners, idle=idle)
    assert (verdict.action, verdict.sessions) == ("end", (_SESSION,)), verdict
    assert "잠금 pid: (이름 모름)(pid 7" in verdict.reason
    for holders, known in (
        (_CLAUDE, {7: _SESSION, 61148: _SESSION}),
        (held, {7: _OTHER_SESSION, 61148: _SESSION}),
        (held, {61148: _SESSION}),
    ):
        kept = judge(locked, _FACTS, _MERGED, (), _살았다, holders, owners=known, idle=idle)
        assert kept.action == "keep", kept
        assert "claude session x" in kept.reason


def test_환경에서_세션_id_를_모양이_맞을_때만_읽는다() -> None:
    """찍은 `end-holders` 명령을 에이전트가 셸에 그대로 친다. 모양이 어긋난 값은 세션이 없는 것으로
    본다."""
    assert session_in(["=C:=C:\\repo", "PATH=x", f"{SESSION_ENV}={_SESSION}"]) == _SESSION
    assert session_in(["PATH=x"]) is None
    assert session_in([f"{SESSION_ENV}=local_x; rm -rf /"]) is None
    assert session_in([f"{SESSION_ENV.lower()}={_SESSION}"]) is None


# --- 등록 없는 폴더(대기열 148) -------------------------------------------------------------------

_STRAY = "C:/repo/.claude/worktrees/stray"
_CLEAN_STRAY = StrayFacts(has_git=False, error="", links=(), uncommitted=())


def test_등록_없는_폴더는_내용이_모두_커밋에_있으면_지운다() -> None:
    verdict = judge_stray(_STRAY, _CLEAN_STRAY, ())
    assert (verdict.action, verdict.path, verdict.branch) == ("delete", _STRAY, None)


def test_등록_없는_폴더에_git_이_있으면_사람에게_넘긴다() -> None:
    """등록이 그 폴더를 잃었을 수 있다(점유 탐침이 옆 이름에 남긴 폴더가 그 모양이다)."""
    verdict = judge_stray(_STRAY, replace(_CLEAN_STRAY, has_git=True), ())
    assert verdict.action == "human"
    assert ".git" in verdict.reason


def test_탐침이_옆_이름에_남긴_폴더는_등록이_폴더를_잃었을_때만_되돌린다() -> None:
    """2026-10-15 에 옆 이름에 남은 폴더 하나가 되돌릴 자리만 안내된 채 사흘을 남아 있었다.
    되돌리기는 `restore` 명령으로 찍는다."""
    aside = "C:/repo/.claude/worktrees/x.tidy-probe"
    home = "C:/repo/.claude/worktrees/x"
    verdict = judge_stray(aside, replace(_CLEAN_STRAY, has_git=True), (), home)
    assert verdict.action == "restore"
    assert home in verdict.reason
    unknown = judge_stray(aside, replace(_CLEAN_STRAY, has_git=True), ())
    assert unknown.action == "human"
    assert "되돌" not in unknown.reason


def test_등록_없는_폴더에_커밋에_없는_파일이_있으면_남기고_몇_개를_든다() -> None:
    files = tuple(f"f{index}.py" for index in range(7))
    verdict = judge_stray(_STRAY, replace(_CLEAN_STRAY, uncommitted=files), ())
    assert verdict.action == "keep"
    assert "커밋에 없는 파일" in verdict.reason
    assert "f0.py" in verdict.reason
    assert "f6.py" not in verdict.reason
    assert "7개" in verdict.reason


def test_등록_없는_폴더에_링크가_있으면_남긴다() -> None:
    verdict = judge_stray(_STRAY, replace(_CLEAN_STRAY, links=("web/linked",)), ())
    assert verdict.action == "keep"
    assert "web/linked" in verdict.reason


def test_등록_없는_폴더를_읽다_막히면_남긴다() -> None:
    verdict = judge_stray(_STRAY, replace(_CLEAN_STRAY, error="WinError 5"), ())
    assert verdict.action == "keep"
    assert "WinError 5" in verdict.reason


def test_등록_없는_폴더를_쥔_프로세스가_있으면_남긴다() -> None:
    held = (Holder(26016, "python.exe", "module"),)
    verdict = judge_stray(_STRAY, _CLEAN_STRAY, held)
    assert verdict.action == "keep"
    assert "python.exe(pid 26016)" in verdict.reason


_CONTROLS = bytes(range(1, 8)) * 4


@pytest.mark.parametrize(
    ("data", "text"),
    [
        (b"one\ntwo\n", True),
        (b"one\r\ntwo\r\n", True),
        ("한글\r\n".encode(), True),
        (b"", True),
        (b"tab\tesc\x1b\r\nend\x1a", True),
        # 인쇄 문자가 많아 비율로는 텍스트인 내용이다. NUL 하나로 바이너리가 된다
        (b"x" * 300 + b"\r\n\0\r\n", False),
        (b"lone\rcr\r\n", False),
        (b"few\r\n" + _CONTROLS, False),
        # 인쇄 문자 127개와 비인쇄 하나. 끝의 \x1a 를 인쇄로 세면 128개가 되어 텍스트로 갈린다
        (b"a" * 127 + b"\x01\r\n\x1a", False),
    ],
    ids=[
        "LF",
        "CRLF",
        "한글_CRLF",
        "빈_내용",
        "인쇄로_치는_제어_문자",
        "NUL",
        "홀로_쓰인_CR",
        "비인쇄_비율",
        "끝의_EOF_는_어느_쪽에도_세지_않는다",
    ],
)
def test_블롭_이름은_git_hash_object_와_같은_판별로_낸다(
    repo: Path, data: bytes, *, text: bool
) -> None:
    """`.gitattributes` 의 `* text=auto eol=lf` 가 있는 저장소에서 git 이 텍스트로 보는 내용은 CRLF
    를 LF 로 바꾼 이름을, 바이너리로 보는 내용은 그대로의 이름을 낸다. 도구의 판별이 그와 같다."""
    (repo / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    (repo / "sample.txt").write_bytes(data)
    expected = _git("hash-object", "sample.txt", cwd=repo)
    body = data.replace(b"\r\n", b"\n") if text else data
    assert expected == hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()
    assert looks_text(data) is text
    assert expected in blob_ids(data)
    if not text:
        assert blob_ids(data) == {expected}


# --- 휴지통 지우기(delete_path) --------------------------------------------------------------


def _link(link: Path, target: Path) -> None:
    """디렉터리 링크. 윈도는 권한 없이 만드는 정션, 나머지는 심볼릭 링크."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_휴지통_지우기는_트리_밖을_가리키는_링크를_따라가지_않는다(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("남는다", encoding="utf-8")
    tree = tmp_path / "node_modules"
    (tree / "pkg").mkdir(parents=True)
    (tree / "pkg" / "index.js").write_text("x", encoding="utf-8")
    _link(tree / "linked", outside)
    delete_path(tree)
    assert not tree.exists()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "남는다"


def test_휴지통_지우기는_링크_자체만_지운다(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("남는다", encoding="utf-8")
    _link(tmp_path / "node_modules", outside)
    delete_path(tmp_path / "node_modules")
    assert not os.path.lexists(tmp_path / "node_modules")
    assert (outside / "keep.txt").exists()


def test_링크_끊기는_안의_링크만_끊고_바깥과_안의_파일은_둔다(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("남는다", encoding="utf-8")
    folder = tmp_path / "worktree"
    (folder / "deep" / "deeper").mkdir(parents=True)
    (folder / "deep" / "own.txt").write_text("안", encoding="utf-8")
    _link(folder / ".venv", outside)
    _link(folder / "deep" / "deeper" / "link", outside)
    assert cut_links(folder) == []
    assert not os.path.lexists(folder / ".venv")
    assert not os.path.lexists(folder / "deep" / "deeper" / "link")
    assert (folder / "deep" / "own.txt").read_text(encoding="utf-8") == "안"
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "남는다"
    # 문자열 경로도 같다
    _link(folder / "again", outside)
    assert cut_links(str(folder)) == []
    assert not os.path.lexists(folder / "again")


def _stuck_을_끊지_못하게_한다(monkeypatch: pytest.MonkeyPatch) -> None:
    """이름이 `stuck`인 링크만 끊지 못하게 `os.unlink`를 바꾼다."""
    진짜_unlink = os.unlink

    def 막는_unlink(path: str, *, dir_fd: int | None = None) -> None:
        if os.path.basename(path) == "stuck":
            raise PermissionError(path)
        진짜_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(os, "unlink", 막는_unlink)


def _끊지_못할_링크가_든_작업_트리(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`tmp_path/worktree/stuck`이 바깥을 가리키고 그 링크를 끊지 못하는 작업 트리."""
    outside = tmp_path / "outside"
    outside.mkdir()
    folder = tmp_path / "worktree"
    folder.mkdir()
    _link(folder / "stuck", outside)
    _stuck_을_끊지_못하게_한다(monkeypatch)
    return folder


def test_링크_끊기는_읽지_못한_폴더와_끊지_못한_링크를_준다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cut_links(tmp_path / "없음") == [str(tmp_path / "없음")]
    folder = _끊지_못할_링크가_든_작업_트리(tmp_path, monkeypatch)
    assert cut_links(folder) == [str(folder / "stuck")]


def test_링크_끊기는_끝에_구분자가_붙은_경로에서도_구분자를_겹치지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`long_path`가 끝 구분자를 떼는 경로(상대 경로, 리눅스의 절대 경로)에서 넘긴 머리 뒤에
    구분자를 하나 더 붙였다(티켓 07의 반영분 셀프 리뷰, PR #372 claude-review 첫 회차의 Nit)."""
    folder = _끊지_못할_링크가_든_작업_트리(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert cut_links("worktree" + os.sep) == [os.path.join("worktree", "stuck")]
    assert cut_links(str(folder) + os.sep) == [str(folder / "stuck")]
    # 읽지 못한 상대 경로 뿌리는 넘긴 꼴 그대로 준다(구분자를 붙이지 않는다)
    assert cut_links("없음") == ["없음"]


def test_링크_끊기는_MAX_PATH_를_넘는_깊이의_링크도_끊고_넘긴_꼴의_경로를_준다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """윈도에서 긴 경로(`LongPathsEnabled`)가 꺼져 있으면 260자를 넘는 폴더를 평범한 경로로 훑지
    못한다. 게이트 작업 트리의 `web/node_modules/.pnpm` 아래가 그 깊이다(티켓 07의 PR 직전
    bug-perf-review)."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("남는다", encoding="utf-8")
    folder = tmp_path / "worktree"
    deep = folder.joinpath(*["d" * 40] * 8)
    assert len(str(deep)) > 300
    os.makedirs(long_path(deep))
    _link(Path(long_path(deep / "link")), outside)

    assert cut_links(folder) == []
    assert not os.path.lexists(long_path(deep / "link"))
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "남는다"

    _link(Path(long_path(deep / "stuck")), outside)
    _stuck_을_끊지_못하게_한다(monkeypatch)
    assert cut_links(folder) == [str(deep / "stuck")]


def test_링크_끊기는_뿌리가_링크면_따라가지_않고_그_뿌리를_준다(tmp_path: Path) -> None:
    """뿌리 자체가 링크면 그 링크가 가리키는 트리 안의 링크를 끊지 않는다(티켓 07의 커밋 전 반박
    검증에서, 링크로 바뀐 게이트 작업 트리 자리를 따라가 바깥 트리의 링크를 모두 끊었다)."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(outside / "inner", elsewhere)
    root = tmp_path / "worktree"
    _link(root, outside)

    assert cut_links(root) == [str(root)]
    assert os.path.islink(outside / "inner") or os.path.isjunction(outside / "inner")
    assert os.path.islink(root) or os.path.isjunction(root)


def _가짜_홈(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`tmp_path/home/user`를 홈으로 삼는다. 윈도의 `expanduser`는 `USERPROFILE`을, 나머지는
    `HOME`을 읽는다. 진짜 홈과 드라이브 뿌리를 지우는 함수에 넣는 시험은 두지 않는다(티켓 07의
    셀프 리뷰 서브에이전트가 `cut_links("C:\\")`를 불러 사용자 프로필의 junction 열셋을 끊었다)."""
    home = tmp_path / "home" / "user"
    home.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    assert os.path.expanduser("~") == str(home)
    return home


def test_링크_끊기는_홈이나_그_조상이면_아무것도_끊지_않고_그_뿌리를_준다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    home = _가짜_홈(tmp_path, monkeypatch)
    _link(home / "Application Data", outside)

    assert cut_links(home) == [str(home)]
    assert cut_links(home.parent) == [str(home.parent)]
    assert os.path.isjunction(home / "Application Data") or os.path.islink(
        home / "Application Data"
    )
    # 홈 아래의 폴더는 그대로 끊는다
    (home / "sub").mkdir()
    _link(home / "sub" / "link", outside)
    assert cut_links(home / "sub") == []
    assert not os.path.lexists(home / "sub" / "link")


def test_홈을_품은_자리는_드라이브_뿌리와_홈과_그_조상이다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """지우는 함수를 부르지 않고 판정만 본다. 드라이브 뿌리는 이 판정에만 넣는다."""
    home = tmp_path / "home" / "user"
    (home / "AppData").mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    assert holds_home(tmp_path.anchor, home)
    assert holds_home(home, home)
    assert holds_home(home.parent, home)
    assert holds_home(str(home) + os.sep, home)
    assert holds_home(home / "AppData" / "..", home)
    assert not holds_home(home / "AppData", home)
    assert not holds_home(other, home)
    assert not holds_home(tmp_path / "home2", home)
    # 상대 경로와 링크 별명도 가리키는 자리로 본다
    monkeypatch.chdir(home.parent)
    assert holds_home("user", home)
    assert holds_home(".", home)
    _link(tmp_path / "alias", home.parent)
    assert holds_home(tmp_path / "alias" / "user", home)
    if sys.platform == "win32":
        assert holds_home(str(home).upper(), home)
        # 짧은 이름(8.3)도 가리키는 자리로 본다. 이 PC의 임시 폴더 볼륨은 짧은 이름을 만든다
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
        kernel.GetShortPathNameW.restype = ctypes.c_ulong
        buffer = ctypes.create_unicode_buffer(32768)
        if not kernel.GetShortPathNameW(str(tmp_path), buffer, len(buffer)):
            raise ctypes.WinError(ctypes.get_last_error())
        assert buffer.value != str(tmp_path), "임시 폴더에 짧은 이름이 없어 이 갈래를 재지 못한다"
        assert holds_home(buffer.value, home)
        assert holds_home(os.path.join(buffer.value, "home", "user"), home)
        # 홈이 없는 드라이브의 뿌리도 막는다. 같은 드라이브의 뿌리는 홈의 조상이라 이 갈래를
        # 가르지 못한다
        other_drive = "Y:\\" if tmp_path.anchor.upper().startswith("Z") else "Z:\\"
        assert holds_home(other_drive, home)


def test_못_보는_것_홈_판정은_다른_꼴의_같은_자리를_지나가고_빈_홈이면_작업_폴더를_막는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`holds_home` 독스트링의 못 보는 것. 판정 함수만 부른다."""
    home = tmp_path / "home" / "user"
    (home / "AppData").mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    assert not holds_home(home / "AppData", home)
    if sys.platform == "win32":
        unc = f"\\\\localhost\\{home.drive[0]}$" + str(home)[len(home.drive) :]
        assert not holds_home(unc, home)
        monkeypatch.setenv("USERPROFILE", "")
        monkeypatch.chdir(work)
        seen = os.path.expanduser("~")
        assert seen == ""
        assert holds_home(work, seen)
        assert holds_home(tmp_path, seen)
        assert not holds_home(home, seen)


def test_휴지통_지우기는_홈이나_그_조상이면_지우지_않고_PermissionError_다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _가짜_홈(tmp_path, monkeypatch)
    (home / "keep.txt").write_text("남는다", encoding="utf-8")
    for target in (home, home.parent):
        with pytest.raises(PermissionError, match="홈"):
            delete_path(target)
    assert (home / "keep.txt").read_text(encoding="utf-8") == "남는다"


def test_못_보는_것_휴지통_지우기는_홈을_가리키는_링크와_링크인_홈을_링크만_지운다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`delete_path` 독스트링의 끝 문장. 링크 갈래가 홈 가드보다 먼저 돈다."""
    real = tmp_path / "real" / "user"
    real.mkdir(parents=True)
    (real / "keep.txt").write_text("남는다", encoding="utf-8")
    home = tmp_path / "home"
    _link(home, real)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    assert os.path.expanduser("~") == str(home)
    alias = tmp_path / "alias"
    _link(alias, real.parent)

    delete_path(alias)
    delete_path(home)
    assert not os.path.lexists(alias)
    assert not os.path.lexists(home)
    assert (real / "keep.txt").read_text(encoding="utf-8") == "남는다"


def test_휴지통_지우기는_읽기_전용_파일도_지운다(tmp_path: Path) -> None:
    tree = tmp_path / ".venv"
    tree.mkdir()
    readonly = tree / "locked.txt"
    readonly.write_text("x", encoding="utf-8")
    readonly.chmod(0o444)
    delete_path(tree)
    assert not tree.exists()


def test_휴지통_지우기는_파일_하나도_지운다(tmp_path: Path) -> None:
    single = tmp_path / "next-env.d.ts"
    single.write_text("x", encoding="utf-8")
    delete_path(single)
    assert not single.exists()


def test_도구는_표준_라이브러리만_import_한다() -> None:
    """uv 의 `.venv` 는 기본으로 캐시에서 하드링크로 채워져(Claude 세션은 복사다, 대기열 217),
    도구가 서드파티 확장 모듈(pydantic 의 `.pyd`)을 싣으면 지울 워크트리의 같은 파일을 도구 자신이
    쥔다(프로브의 E 갈래)."""
    tree = ast.parse(_TOOL.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    assert modules, "import 를 하나도 읽지 못했다"
    assert modules - set(sys.stdlib_module_names) - {"__future__"} == set()


# --- 배관: 실제 git 워크트리 ----------------------------------------------------------------------

_IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")


def _git(*args: str, cwd: Path) -> str:
    result = real_git(list(args), cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-b", "main", cwd=root)
    ignore = ".venv/\nnode_modules/\n.env\n/.claude/worktrees/\n.claude/settings.local.json\n"
    (root / ".gitignore").write_text(ignore, encoding="utf-8")
    # 윈도의 write_text 는 줄 끝을 CRLF 로 써서, 커밋된 블롭이 core.autocrlf 에 따라 달라진다
    (root / "README.md").write_bytes(b"repo\n")
    _git("add", ".", cwd=root)
    _git(*_IDENTITY, "commit", "-m", "init", cwd=root)
    # 실제 저장소처럼 `origin/main` 을 둔다. 브랜치와 분리 HEAD 의 판정이 이것을 본다
    _git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=root)
    return root


def test_git_은_색인을_잠그지_않는_환경으로_돈다(repo: Path) -> None:
    alias = "alias.optional-locks=!echo locks=$GIT_OPTIONAL_LOCKS"
    assert _git("-c", alias, "optional-locks", cwd=repo) == "locks=0"


def _add(root: Path, name: str) -> tuple[Path, str]:
    path = root / ".claude" / "worktrees" / name
    _git("worktree", "add", "-b", f"chore/{name}", str(path), cwd=root)
    (path / ".venv" / "Lib").mkdir(parents=True)
    (path / ".venv" / "Lib" / "mod.py").write_text("x", encoding="utf-8")
    (path / "node_modules" / "pkg").mkdir(parents=True)
    (path / "node_modules" / "pkg" / "index.js").write_text("x", encoding="utf-8")
    return path, _git("rev-parse", "HEAD", cwd=path)


def _registered(root: Path, path: Path) -> bool:
    listing = parse_worktrees(_git("worktree", "list", "--porcelain", cwd=root) + "\n")
    return any(same_path(w.path, str(path)) for w in listing)


def _모듈_없음() -> list[tuple[int, str, str]]:
    return []


def _볼_수_없다() -> None:
    """프로세스를 읽을 수 없는 OS 의 훑기."""
    return None


def _add_detached(root: Path, name: str) -> tuple[Path, str]:
    """분리 HEAD 워크트리. `origin/main` 의 커밋을 가리킨다."""
    path = root / ".claude" / "worktrees" / name
    _git("worktree", "add", "--detach", str(path), cwd=root)
    return path, _git("rev-parse", "HEAD", cwd=path)


def _trash(root: Path) -> list[str]:
    trash = root / ".claude" / "worktrees" / ".tidy-trash"
    return sorted(p.name for p in trash.iterdir()) if trash.is_dir() else []


def _안_잔다(_seconds: float) -> None:
    return None


def _나중() -> float:
    """막 딴 브랜치의 창(`FRESH_SECONDS`)이 지난 때. 브랜치를 따고 바로 판정하는 시험이 떠난 세션이
    오래전에 남긴 브랜치를 그린다."""
    return time.time() + 2 * FRESH_SECONDS


def _ops(merged: dict[str, frozenset[str]], now: Callable[[], float] = _나중) -> Ops:
    """모듈 훑기는 한 번에 1초 안팎이라(`.scratch/harness/probes/module_holder.py` 에서 0.90~1.22초)
    가짜로 준다. 실제 훑기는 따로 잰다. 막 딴 브랜치를 재는 시험만 `now` 에 지금 시각을 준다."""

    def merged_source(_root: Path) -> dict[str, frozenset[str]]:
        return merged

    return Ops(merged=merged_source, pid_alive=_죽었다, modules=_모듈_없음, sleep=_안_잔다, now=now)


def _git_at(when: float, *args: str, cwd: Path) -> None:
    """reflog 의 기록 시각을 `when`(유닉스 초)으로 두고 git 을 친다. reflog 는 커미터 시각을
    적는다."""
    env = {**os.environ, "GIT_COMMITTER_DATE": f"{int(when)} +0000"}
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_judge_는_지울_후보와_명령을_찍는다(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path, head = _add(repo, "done")
    _add(repo, "open")
    code = main(["judge"], cwd=repo, ops=_ops({"chore/done": frozenset({head})}))
    out = capsys.readouterr().out
    assert code == 0, out
    lines = out.splitlines()
    done = next(line for line in lines if "done" in line)
    assert done.startswith("지운다")
    assert f'remove "{path.as_posix()}" chore/done {head}' in done
    opened = next(line for line in lines if "/open" in line)
    assert opened.startswith("남긴다")
    # 등록된 워크트리는 등록 없는 폴더로 다시 찍지 않는다
    assert not any("등록 없는 폴더" in line for line in lines), out


def test_judge_는_루트에_훅의_키만_더한_설정을_든_워크트리를_지울_후보로_찍는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """워크트리를 만들 때 받은 local 설정 사본은, 그 뒤 훅이 루트에 `.claude/worktrees/` 키를 적어도
    다시 만들 수 있는 것이다(대기열 274). 이 저장소처럼 `.claude/` 에 추적하는 파일이 있어야 git 이
    폴더째가 아니라 그 설정 파일 하나를 무시된 항목으로 낸다."""
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    _git("add", ".claude/settings.json", cwd=repo)
    _git(*_IDENTITY, "commit", "-m", "settings", cwd=repo)
    path, head = _add(repo, "done")
    (path / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    hooked = {"skillOverrides": {f"{HOOK_KEY_PREFIX}done:tdd": "off"}}
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.local.json").write_text(json.dumps(hooked), encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({"chore/done": frozenset({head})})) == 0
    done = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert done.startswith("지운다"), done


def test_judge_는_실행_중인_세션의_제목을_받는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, head = _add(repo, "done")
    merged = {"chore/done": frozenset({head})}
    assert main(["judge", "--running", "chore/done"], cwd=repo, ops=_ops(merged)) == 0
    assert next(line for line in capsys.readouterr().out.splitlines() if "done" in line).startswith(
        "남긴다"
    )


def test_judge_는_프로세스를_못_볼_때_제목_모를_세션_때문에_넘긴_후보에_명령을_붙인다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, head = _add(repo, "done")
    merged = {"chore/done": frozenset({head})}
    ops = replace(_ops(merged), processes=_볼_수_없다)
    assert main(["judge", "--running", "앱이 지은 이름"], cwd=repo, ops=ops) == 0
    done = next(line for line in capsys.readouterr().out.splitlines() if "done" in line)
    assert done.startswith("넘긴다")
    assert "앱이 지은 이름" in done
    assert f'승인하면 → uv run python tools/tidy_checkouts.py remove "{path.as_posix()}"' in done


def test_judge_는_프로세스를_볼_수_있으면_제목_모를_세션이_돌아도_지울_후보로_찍는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """2026-10-15. 세션은 작업 디렉터리로 잡힌다. 제목으로는 넘기지 않는다. 빈 목록은 읽지 못한
    것으로 본다(윈도의 프로세스 열거 실패가 빈 목록이다, PR #243 CodeRabbit). 훑기가 됐으면 이
    도구 자신의 파이썬이 들어 비지 않는다."""
    _, head = _add(repo, "done")
    merged = {"chore/done": frozenset({head})}

    def only_me() -> list[tuple[int, str, str]]:
        return [(os.getpid(), "python.exe", str(repo))]

    ops = replace(_ops(merged), processes=only_me)
    assert main(["judge", "--running", "앱이 지은 이름"], cwd=repo, ops=ops) == 0
    done = next(line for line in capsys.readouterr().out.splitlines() if "done" in line)
    assert done.startswith("지운다"), done
    empty = replace(_ops(merged), processes=_모듈_없음)
    assert main(["judge", "--running", "앱이 지은 이름"], cwd=repo, ops=empty) == 0
    held = next(line for line in capsys.readouterr().out.splitlines() if "done" in line)
    assert held.startswith("넘긴다"), held
    assert "앱이 지은 이름" in held


def test_judge_는_작업_디렉터리로_쥔_프로세스가_있으면_제목_모를_세션이_돌아도_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 186. 실제 자식 프로세스로 잰다. CI(우분투)는 `/proc` 로, 윈도는 PEB 로 읽는다."""
    path, head = _add(repo, "done")
    merged = {"chore/done": frozenset({head})}
    with _자식이_쥔다(path) as pid:
        assert main(["judge", "--running", "앱이 지은 이름"], cwd=repo, ops=_ops(merged)) == 0
    done = next(line for line in capsys.readouterr().out.splitlines() if "done" in line)
    if sys.platform not in ("win32", "linux"):
        assert done.startswith("넘긴다")
        return
    assert done.startswith("남긴다"), done
    assert f"(pid {pid}" in done
    assert "remove" not in done


def test_end_holders_는_쉬는_세션의_프로세스만_끝내고_judge_가_지울_것으로_낸다(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """실제 자식 프로세스로 잰다. 받은 세션 밖이면 끄지 않고, 받은 세션이면 끈 뒤 쥔 것이
    사라져 다음 `judge` 가 지울 것으로 낸다. 끈 뒤에는 실제로 기다린다(프로세스가 끝나는 데 틈이
    있다)."""
    monkeypatch.setenv(SESSION_ENV, _CALLER)
    path, head = _add(repo, "done")
    ops = replace(_ops({"chore/done": frozenset({head})}), sleep=time.sleep)
    with _자식이_쥔다(path, _SESSION) as pid:
        assert main(["judge", "--idle", _SESSION], cwd=repo, ops=ops) == 0
        line = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
        if sys.platform not in ("win32", "linux"):
            assert line.startswith("지운다"), line
            return
        assert line.startswith("끝낸다"), line
        assert f"pid {pid}, 세션 {_SESSION}" in line
        assert f'end-holders "{path.as_posix()}" {_SESSION}' in line
        assert main(["end-holders", str(path), _OTHER_SESSION], cwd=repo, ops=ops) == 1
        assert process_alive(pid)
        assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=ops) == 0
    capsys.readouterr()
    assert main(["judge"], cwd=repo, ops=ops) == 0
    done = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert done.startswith("지운다"), done


def _세션(sessions: dict[int, str]) -> Callable[[int], str | None]:
    def session_of(pid: int) -> str | None:
        return sessions.get(pid)

    return session_of


def _끄면_안_된다(pid: int) -> bool:
    raise AssertionError(f"pid {pid} 를 끄려 했다")


def _쥔다(path: Path, *pids: int) -> Callable[[], list[tuple[int, str, str]]]:
    def processes() -> list[tuple[int, str, str]]:
        return [(pid, "claude.exe", str(path)) for pid in pids]

    return processes


def test_judge_와_end_holders_는_부른_세션의_프로세스를_끝내지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """도구를 부른 세션은 환경의 세션 id 로 안다. 부르는 쪽이 그 세션을 쉰다고 넘겨도 빼고 본다."""
    monkeypatch.setenv(SESSION_ENV, _SESSION)
    path, head = _add(repo, "done")
    ops = replace(
        _ops({"chore/done": frozenset({head})}),
        processes=_쥔다(path, 4242),
        session_of=_세션({4242: _SESSION}),
        end=_끄면_안_된다,
    )
    assert main(["judge", "--idle", _SESSION], cwd=repo, ops=ops) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert line.startswith("남긴다"), line
    assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=ops) == 1
    assert "이 도구를 부른 세션" in capsys.readouterr().out


@pytest.mark.parametrize("own", [None, "local_모양이-아니다"])
def test_end_holders_는_부른_세션을_모르면_아무것도_끄지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, own: str | None
) -> None:
    """앱 밖에서 부르면 환경에 세션 id 가 없어 부른 세션을 뺄 수 없다. 그때는 끄지 않는다."""
    if own is None:
        monkeypatch.delenv(SESSION_ENV, raising=False)
    else:
        monkeypatch.setenv(SESSION_ENV, own)
    path, head = _add(repo, "done")
    ops = replace(
        _ops({"chore/done": frozenset({head})}),
        processes=_쥔다(path, 4242),
        session_of=_세션({4242: _SESSION}),
        end=_끄면_안_된다,
    )
    assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=ops) == 1
    assert "부른 세션을 모른다" in capsys.readouterr().out


def test_end_holders_는_받은_세션_밖의_프로세스가_하나라도_쥐면_아무것도_끄지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SESSION_ENV, _CALLER)
    path, head = _add(repo, "done")
    base = _ops({"chore/done": frozenset({head})})
    mixed = replace(
        base, processes=_쥔다(path, 1, 2), session_of=_세션({1: _SESSION}), end=_끄면_안_된다
    )
    assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=mixed) == 1
    assert "받은 세션 밖의 프로세스" in capsys.readouterr().out
    # 세션 id 모양이 아닌 인자는 인자 오류다
    assert main(["end-holders", str(path), "local_x;rm"], cwd=repo, ops=mixed) == 2
    assert "세션 id 모양" in capsys.readouterr().err


def test_end_holders_는_끄기_직전에_세션_id_가_바뀐_프로세스를_끄지_않는다(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pid 만 보고 끄지 않는다(`.claude/rules/probes.md`). 훑은 뒤 그 pid 가 끝나 다른 프로세스가
    받았으면 환경의 세션 id 가 다르다."""
    monkeypatch.setenv(SESSION_ENV, _CALLER)
    path, head = _add(repo, "done")
    reads: list[int] = []

    def drifting(pid: int) -> str | None:
        reads.append(pid)
        return _SESSION if len(reads) == 1 else _OTHER_SESSION

    ops = replace(
        _ops({"chore/done": frozenset({head})}),
        processes=_쥔다(path, 1),
        session_of=drifting,
        end=_끄면_안_된다,
    )
    assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=ops) == 1
    assert len(reads) == 2


def test_end_holders_는_끄기_전에_다시_판정해_지울_후보가_아니면_끄지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """셀프 리뷰 명세 축. `judge` 뒤에 바뀌었거나(파일을 고쳤다) 처음부터 후보가 아닌 워크트리
    (병합되지 않았다)를 쥔 프로세스는, 찍힌 적 없는 `end-holders` 를 치거나 옛 줄을 다시 쳐도
    끄지 않는다. `remove` 가 지우기 전에 다시 판정하는 것과 짝이다."""
    monkeypatch.setenv(SESSION_ENV, _CALLER)
    path, head = _add(repo, "done")
    held = replace(
        _ops({}), processes=_쥔다(path, 1), session_of=_세션({1: _SESSION}), end=_끄면_안_된다
    )
    assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=held) == 1
    assert "병합된 PR 이 없다" in capsys.readouterr().out
    (path / "new.txt").write_text("x", encoding="utf-8")
    merged = replace(held, merged=_ops({"chore/done": frozenset({head})}).merged)
    assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=merged) == 1
    assert "바뀐 파일이 있다" in capsys.readouterr().out


def test_end_holders_는_쉬는_세션의_산_잠금_pid_도_끄고_judge_가_풀고_지울_것으로_낸다(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """셀프 리뷰 명세 축. `EnterWorktree` 로 연 세션은 잠금 사유에 자기 pid 를 남기고, 인계할 때만
    푼다. 그 세션이 쉬면 잠금 pid 도 그 세션의 것이라 함께 끈다. 잠금 pid 가 작업 디렉터리로 쥐지
    않아도 끈다."""
    monkeypatch.setenv(SESSION_ENV, _CALLER)
    path, head = _add(repo, "done")
    _git("worktree", "lock", "--reason", "claude session done (pid 9)", str(path), cwd=repo)
    ended: list[int] = []

    def alive(pid: int) -> bool:
        return pid == 9 and pid not in ended

    def processes() -> list[tuple[int, str, str]]:
        return [] if 1 in ended else [(1, "claude.exe", str(path))]

    def end(pid: int) -> bool:
        ended.append(pid)
        return True

    ops = replace(
        _ops({"chore/done": frozenset({head})}),
        pid_alive=alive,
        processes=processes,
        session_of=_세션({1: _SESSION, 9: _SESSION}),
        end=end,
    )
    assert main(["judge", "--idle", _SESSION], cwd=repo, ops=ops) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert line.startswith("끝낸다"), line
    assert main(["end-holders", str(path), _SESSION], cwd=repo, ops=ops) == 0
    assert sorted(ended) == [1, 9]
    capsys.readouterr()
    assert main(["judge"], cwd=repo, ops=ops) == 0
    done = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert done.startswith("지운다"), done
    assert "풀고 지운다" in done


def test_judge_와_remove_는_병합된_PR_머리보다_뒤인_워크트리를_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """2026-10-20 `skill-check-and-retro-section` 의 모양. PR 머리는 다른 체크아웃에서 더 나갔고
    로컬 끝은 그 조상이다. 머리 커밋이 이 저장소에 없으면 조상인지 알 수 없어 넘긴다."""
    path, behind = _add(repo, "done")
    (path / "more.txt").write_bytes(b"x\n")
    _git("add", "more.txt", cwd=path)
    _git(*_IDENTITY, "commit", "-q", "-m", "PR 에 더한 커밋", cwd=path)
    ahead = _git("rev-parse", "HEAD", cwd=path)
    # 머리 커밋을 참조로 남긴다(원격 추적 브랜치의 자리)
    _git("update-ref", "refs/remotes/origin/chore/done", ahead, cwd=repo)
    _git("reset", "-q", "--hard", behind, cwd=path)
    merged = {"chore/done": frozenset({ahead})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert line.startswith("지운다"), line
    assert "머리보다 뒤" in line
    assert main(["judge"], cwd=repo, ops=_ops({"chore/done": frozenset({_OLD})})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert line.startswith("넘긴다"), line
    assert main(["remove", str(path), "chore/done", behind], cwd=repo, ops=_ops(merged)) == 0
    assert not path.exists()
    assert _git("branch", "--list", "chore/done", cwd=repo) == ""


def test_judge_는_병합된_PR_머리보다_앞선_워크트리를_넘긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """로컬에만 있는 커밋이 있다. 조상 판정의 방향(끝이 머리의 조상이다)이 뒤집히면 지운다."""
    path, merged_head = _add(repo, "done")
    (path / "local.txt").write_bytes(b"x\n")
    _git("add", "local.txt", cwd=path)
    _git(*_IDENTITY, "commit", "-q", "-m", "PR 뒤에 로컬에서만 더한 커밋", cwd=path)
    assert main(["judge"], cwd=repo, ops=_ops({"chore/done": frozenset({merged_head})})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert line.startswith("넘긴다"), line


def test_judge_와_remove_branch_는_병합된_PR_머리보다_뒤인_브랜치를_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _git("switch", "-q", "-c", "chore/loose", cwd=repo)
    (repo / "loose.txt").write_bytes(b"x\n")
    _git("add", "loose.txt", cwd=repo)
    _git(*_IDENTITY, "commit", "-q", "-m", "origin/main 에 없는 커밋", cwd=repo)
    tip = _git("rev-parse", "HEAD", cwd=repo)
    (repo / "more.txt").write_bytes(b"x\n")
    _git("add", "more.txt", cwd=repo)
    _git(*_IDENTITY, "commit", "-q", "-m", "PR 에 더한 커밋", cwd=repo)
    ahead = _git("rev-parse", "HEAD", cwd=repo)
    _git("update-ref", "refs/remotes/origin/chore/loose", ahead, cwd=repo)
    _git("reset", "-q", "--hard", tip, cwd=repo)
    _git("switch", "-q", "main", cwd=repo)
    merged = {"chore/loose": frozenset({ahead})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if " chore/loose" in line)
    assert line.startswith("브랜치를 지운다"), line
    assert main(["remove-branch", "chore/loose", tip], cwd=repo, ops=_ops(merged)) == 0
    assert _git("branch", "--list", "chore/loose", cwd=repo) == ""


def test_judge_와_remove_는_앱의_표지가_있는_워크트리를_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """표지는 워크트리마다의 git 디렉터리(`.git/worktrees/<이름>/`)에 있다. 표지가 없으면 지울
    분리 HEAD 워크트리다(origin/main 의 커밋)."""
    path, head = _add_detached(repo, "pool")
    gitdir = Path(_git("rev-parse", "--absolute-git-dir", cwd=path))
    (gitdir / APP_MARKER).write_text("", encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/pool" in line)
    assert line.startswith("남긴다"), line
    assert APP_MARKER in line
    assert main(["remove", str(path), ".detached", head], cwd=repo, ops=_ops({})) == 1
    assert path.exists()


def test_judge_는_워크트리가_여럿이어도_프로세스를_한_번만_훑는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """훑기 한 번이 약 0.1초다(lock_holder.py --folder). 워크트리마다 훑지 않는다."""
    _, first = _add(repo, "one")
    _, second = _add(repo, "two")
    (repo / ".claude" / "worktrees" / "stray").mkdir()
    scans: list[str] = []

    def processes() -> list[tuple[int, str, str]]:
        scans.append("cwd")
        return []

    def modules() -> list[tuple[int, str, str]]:
        scans.append("module")
        return []

    merged = {"chore/one": frozenset({first}), "chore/two": frozenset({second})}
    ops = replace(_ops(merged), processes=processes, modules=modules)
    assert main(["judge"], cwd=repo, ops=ops) == 0
    out = capsys.readouterr().out
    assert sum(line.startswith("지운다") for line in out.splitlines()) == 3, out
    assert sorted(scans) == ["cwd", "module"]


def test_remove_는_모듈을_올린_프로세스가_있어도_옮겨_두고_지우며_휴지통에_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """2026-10-15. 판정 3이 모듈을 올린 프로세스로 병합된 워크트리 55개를 남겼고, 그 프로세스는
    다른 세션의 pytest·esbuild 처럼 곧 끝나는 것이었다. 실제 자식 프로세스가 워크트리의 `.venv`
    아래 `.pyd` 를 올린 채로 `judge` 는 지울 후보로 찍고, `remove` 는 `.venv` 를 휴지통으로 옮겨
    워크트리와 브랜치를 지운 뒤 막힌 `.pyd` 를 쥔 pid 를 들어 남긴다. 자식이 끝난 뒤
    `empty-trash` 가 비운다. 윈도 밖은 적재한 모듈이 지우기를 막지 않는다."""
    path, head = _add(repo, "done")
    module = path / ".venv" / "Lib" / "mod.pyd"
    merged = {"chore/done": frozenset({head})}
    ops = replace(_ops(merged), modules=scan_modules)
    if sys.platform != "win32":
        assert main(["judge"], cwd=repo, ops=ops) == 0
        assert "지운다" in capsys.readouterr().out
        return
    shutil.copyfile(_적재할_DLL(), module)
    with _자식이_올린다(module) as pid:
        assert main(["judge"], cwd=repo, ops=ops) == 0
        done = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
        assert done.startswith("지운다"), done
        assert main(["remove", path.as_posix(), "chore/done", head], cwd=repo, ops=ops) == 0
        out = capsys.readouterr().out
        assert "휴지통에 남았다" in out
        assert f"python.exe(pid {pid})" in out
        assert not path.exists()
        assert _git("branch", "--list", "chore/done", cwd=repo) == ""
        assert _trash(repo) == ["done~~.venv"]
        assert main(["judge"], cwd=repo, ops=ops) == 0
        listed = capsys.readouterr().out
        assert "휴지통에 남았다" in listed
        assert "empty-trash" in listed
        assert main(["empty-trash"], cwd=repo, ops=ops) == 1
        blocked = capsys.readouterr().out
        assert "휴지통에 남았다" in blocked
        assert f"python.exe(pid {pid})" in blocked
        assert _trash(repo) == ["done~~.venv"]
    assert main(["empty-trash"], cwd=repo, ops=ops) == 0
    assert _trash(repo) == []


def _stray(repo: Path, name: str = "stray") -> Path:
    """루트의 커밋과 같은 내용, 다시 만들 수 있는 폴더, 루트와 같은 설정 파일이 든 등록 없는
    폴더."""
    stray = repo / ".claude" / "worktrees" / name
    (stray / ".venv" / "Lib").mkdir(parents=True)
    (stray / ".venv" / "Lib" / "mod.py").write_text("커밋에 없다", encoding="utf-8")
    (stray / "web" / "node_modules").mkdir(parents=True)
    (stray / "web" / "node_modules" / "x.js").write_text("x", encoding="utf-8")
    (stray / "README.md").write_bytes((repo / "README.md").read_bytes())
    (repo / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    (stray / ".claude").mkdir()
    (stray / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    return stray


def _stray_line(out: str) -> str:
    return next(line for line in out.splitlines() if "/stray" in line)


def test_judge_는_루트에_훅의_키만_더한_설정을_든_등록_없는_폴더를_지울_후보로_찍는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _stray(repo)
    hooked = {"skillOverrides": {f"{HOOK_KEY_PREFIX}stray:tdd": "off"}}
    (repo / ".claude" / "settings.local.json").write_text(json.dumps(hooked), encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    assert _stray_line(capsys.readouterr().out).startswith("지운다")


def test_judge_는_내용이_모두_커밋에_있는_등록_없는_폴더를_지울_후보로_찍는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)
    (repo / ".claude" / "worktrees" / "empty").mkdir()
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    out = capsys.readouterr().out
    line = _stray_line(out)
    assert line.startswith("지운다"), line
    assert f'remove-stray "{stray.as_posix()}"' in line
    empty = next(line for line in out.splitlines() if "/empty" in line)
    assert empty.startswith("지운다"), empty


def test_judge_는_CRLF_로_저장한_커밋된_파일을_커밋에_있는_것으로_본다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)
    (stray / "README.md").write_bytes((repo / "README.md").read_bytes().replace(b"\n", b"\r\n"))
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    assert _stray_line(capsys.readouterr().out).startswith("지운다")


@pytest.mark.parametrize(
    ("relative", "content"),
    [
        ("new.py", "새 파일"),
        ("README.md", "고친 내용"),
        (".env", "SECRET=x"),
        (".claude/settings.local.json", '{"permissions": {}}'),
    ],
    ids=["새_파일", "고친_파일", "무시된_env", "루트와_다른_설정"],
)
def test_judge_는_커밋에_없는_파일이_든_등록_없는_폴더를_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str], relative: str, content: str
) -> None:
    stray = _stray(repo)
    (stray / relative).write_text(content, encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("남긴다"), line
    assert relative in line


def test_judge_는_등록_없는_폴더의_위젯_페이지_안_번들을_다시_만들_수_있는_것으로_본다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 464 의 둘째(일지 2026-10-26-01 회고 1). 워크트리 판정과 같은 자리를 다시 만들 수 있는
    것으로 본다. 자리째로 보므로 다른 앱의 같은 이름은 커밋에 없는 파일이다."""
    stray = _stray(repo)
    bundle = stray / "web" / "apps" / "widget" / "public" / "element.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    assert _stray_line(capsys.readouterr().out).startswith("지운다")
    other = stray / "web" / "apps" / "admin" / "public" / "element.js"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"bundle")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("남긴다"), line
    assert "web/apps/admin/public/element.js" in line


def test_judge_는_다른_브랜치에만_있는_내용도_커밋에_있는_것으로_본다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """참조에서 닿는 커밋이면 된다. 병합 전 브랜치의 내용도 그 브랜치가 남아 있으면 되살릴 수
    있다."""
    stray = _stray(repo)
    _git("switch", "-c", "chore/side", cwd=repo)
    (repo / "side.py").write_text("옆 브랜치\n", encoding="utf-8")
    _git("add", "side.py", cwd=repo)
    _git(*_IDENTITY, "commit", "-m", "side", cwd=repo)
    _git("switch", "main", cwd=repo)
    (stray / "side.py").write_text("옆 브랜치\n", encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    assert _stray_line(capsys.readouterr().out).startswith("지운다")


def test_judge_는_리플로그에만_남은_내용을_커밋에_없는_것으로_보고_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """못 보는 것을 고정한다(안전한 쪽). 브랜치를 지우면 그 커밋은 리플로그에만 남는다."""
    stray = _stray(repo)
    _git("switch", "-c", "chore/gone", cwd=repo)
    content = "지운 브랜치\n".encode()
    (repo / "gone.py").write_bytes(content)
    _git("add", "gone.py", cwd=repo)
    _git(*_IDENTITY, "commit", "-m", "gone", cwd=repo)
    _git("switch", "main", cwd=repo)
    _git("branch", "-D", "chore/gone", cwd=repo)
    (stray / "gone.py").write_bytes(content)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("남긴다"), line
    assert "gone.py" in line


def test_judge_는_다른_경로의_같은_내용과_빈_파일과_실행_비트를_커밋에_있는_것으로_본다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """못 보는 것을 고정한다(지우는 쪽). 내용만 견주므로 경로, 실행 비트는 보지 않고, 참조에서 닿는
    커밋에 빈 파일이 있으면 새 빈 파일도 커밋에 있는 것으로 본다. 잃는 내용은 없다."""
    (repo / "empty.txt").write_bytes(b"")
    _git("add", "empty.txt", cwd=repo)
    _git(*_IDENTITY, "commit", "-m", "empty", cwd=repo)
    stray = _stray(repo)
    (stray / "moved").mkdir()
    (stray / "moved" / "readme-copy.md").write_bytes((repo / "README.md").read_bytes())
    (stray / "new-empty.txt").write_bytes(b"")
    (stray / "README.md").chmod(0o755)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    assert _stray_line(capsys.readouterr().out).startswith("지운다")


def test_judge_는_탐침이_남긴_옆_이름에_restore_를_찍고_restore_가_등록을_다시_맞춘다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 202 가 남긴 모양. 폴더를 잃은 등록은 옆 이름이 있으면 넘기고(되돌릴 일이다),
    옆 이름 폴더에는 `restore` 명령을 찍는다. 그 명령을 그대로 밟아 등록이 prunable 이 아니게
    되는지 본다."""
    path, _ = _add(repo, "lost")
    aside = path.with_name("lost.tidy-probe")
    os.rename(path, aside)
    # 원래 이름의 등록이 없는 옆 이름은 되돌리지 않는다
    unknown = path.with_name("unknown.tidy-probe")
    unknown.mkdir()
    (unknown / ".git").write_text("gitdir: C:/nowhere\n", encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    out = capsys.readouterr().out
    home = next(line for line in out.splitlines() if line.endswith("restore 가 되돌린다"))
    assert home.startswith("남긴다"), home
    line = next(
        line for line in out.splitlines() if "lost.tidy-probe" in line and "restore" in line
    )
    assert line.startswith("되돌린다"), line
    assert f'restore "{aside.as_posix()}"' in line
    other = next(line for line in out.splitlines() if "unknown.tidy-probe" in line)
    assert other.startswith("넘긴다"), other
    assert main(["restore", unknown.as_posix()], cwd=repo, ops=_ops({})) == 1
    assert "등록이 없다" in capsys.readouterr().out
    assert main(["restore", aside.as_posix()], cwd=repo, ops=_ops({})) == 0
    assert "되돌렸다" in capsys.readouterr().out
    listing = parse_worktrees(_git("worktree", "list", "--porcelain", cwd=repo) + "\n")
    restored = next(w for w in listing if w.branch == "chore/lost")
    assert not restored.prunable
    assert main(["restore", aside.as_posix()], cwd=repo, ops=_ops({})) == 1
    assert "끝나는 폴더가 아니다" in capsys.readouterr().out


def _쓴다(path: Path, data: bytes) -> None:
    """끝에 점이 붙은 이름과 장치 이름(`nul`)도 그대로 만든다. 윈도는 `\\\\?\\` 를 붙여야 한다."""
    target = "\\\\?\\" + str(path) if sys.platform == "win32" else str(path)
    with open(target, "wb") as handle:
        handle.write(data)


def test_judge_는_끝에_점이_붙은_이름과_장치_이름을_그대로_읽는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PR 직전 버그 리뷰. 경로를 정규화하면 윈도에서 `trail.` 을 `trail` 로 읽어, 커밋에 없는 내용이
    든 폴더를 지울 것으로 냈고 `nul` 은 읽다 막혔다."""
    stray = _stray(repo)
    committed = (repo / "README.md").read_bytes()
    _쓴다(stray / "trail", committed)
    _쓴다(stray / "trail.", "커밋에 없다\n".encode())
    _쓴다(stray / "nul", committed)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("남긴다"), line
    assert "커밋에 없는 파일이 1개 있다: trail." in line
    target = "\\\\?\\" + str(stray / "trail.") if sys.platform == "win32" else str(stray / "trail.")
    os.unlink(target)
    assert main(["remove-stray", stray.as_posix()], cwd=repo, ops=_ops({})) == 0
    assert not stray.exists()


def test_judge_는_큰_파일을_덩이로_읽고_줄_끝을_바꾼_이름은_셈하지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR 직전 버그·성능 리뷰. 상한을 넘는 파일은 통째로 읽지 않는다. 그대로의 이름은 같고, CRLF 로
    저장한 커밋된 내용은 남는 쪽이다(못 보는 것)."""
    monkeypatch.setattr(tidy_checkouts, "WHOLE_READ_LIMIT", 2)
    stray = _stray(repo)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    assert _stray_line(capsys.readouterr().out).startswith("지운다")
    (stray / "README.md").write_bytes((repo / "README.md").read_bytes().replace(b"\n", b"\r\n"))
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("남긴다"), line
    assert "README.md" in line


def test_judge_는_등록_없는_자리가_링크면_안을_읽지_않고_넘긴다(
    tmp_path: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "new.py").write_text("커밋에 없다", encoding="utf-8")
    holder = repo / ".claude" / "worktrees"
    holder.mkdir(parents=True)
    _link(holder / "stray", outside)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("넘긴다"), line
    assert "링크" in line
    # 안이 비어 지울 것으로 보일 자리여도 링크면 remove-stray 가 받지 않는다
    empty = tmp_path / "empty"
    empty.mkdir()
    _link(holder / "linked-empty", empty)
    for name in ("stray", "linked-empty"):
        assert main(["remove-stray", (holder / name).as_posix()], cwd=repo, ops=_ops({})) == 1
        assert os.path.lexists(holder / name)
    assert (outside / "new.py").exists()


def test_judge_는_그_안의_파일만_연_프로세스를_보지_못하고_지울_후보로_찍는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """못 보는 것을 고정한다. 작업 디렉터리도 모듈도 아니고 파일을 열기만 한 프로세스는 판정 3을
    지난다(`lock_holder.py` 의 C). 윈도에서는 `remove` 의 탐침이 막는다."""
    path, head = _add(repo, "done")
    opened = path / ".venv" / "Lib" / "mod.py"
    merged = {"chore/done": frozenset({head})}
    ops = replace(_ops(merged), modules=scan_modules)
    with _자식_파이썬(f"handle = open({str(opened)!r}, encoding='utf-8')"):
        assert main(["judge"], cwd=repo, ops=ops) == 0
    done = next(line for line in capsys.readouterr().out.splitlines() if "/done" in line)
    assert done.startswith("지운다"), done


def test_judge_는_git_이_있는_등록_없는_폴더를_넘긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)
    (stray / ".git").write_text("gitdir: C:/nowhere\n", encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("넘긴다"), line
    assert "remove-stray" not in line


def test_judge_는_등록_없는_폴더의_링크를_따라가지_않고_남긴다(
    tmp_path: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(stray / "linked", outside)
    # 다시 만들 수 있는 폴더 이름의 링크는 지울 때 링크 자체만 지워져 따지지 않는다
    _link(stray / "web" / ".next", outside)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = _stray_line(capsys.readouterr().out)
    assert line.startswith("남긴다"), line
    assert "linked" in line
    assert ".next" not in line


def test_judge_는_체크아웃되지_않은_병합된_브랜치를_찍는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _git("branch", "chore/loose", cwd=repo)
    tip = _git("rev-parse", "chore/loose", cwd=repo)
    assert main(["judge"], cwd=repo, ops=_ops({"chore/loose": frozenset({tip})})) == 0
    loose = next(line for line in capsys.readouterr().out.splitlines() if "chore/loose" in line)
    assert loose.startswith("브랜치를 지운다")
    assert f"remove-branch chore/loose {tip}" in loose


def test_judge_는_셸이_풀_글자가_든_브랜치에_명령을_찍지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """git 은 브랜치 이름에 `;` 를 허락하고, 에이전트는 찍힌 명령을 셸에 그대로 친다."""
    _git("branch", "chore/a;b", cwd=repo)
    tip = _git("rev-parse", "chore/a;b", cwd=repo)
    assert main(["judge"], cwd=repo, ops=_ops({"chore/a;b": frozenset({tip})})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "chore/a;b" in line)
    assert line.startswith("브랜치를 넘긴다")
    assert "remove-branch" not in line


def test_워크트리에서_부르면_아무것도_하지_않고_2로_끝난다(repo: Path) -> None:
    path, head = _add(repo, "done")
    merged = {"chore/done": frozenset({head})}
    assert main(["judge"], cwd=path, ops=_ops(merged)) == 2
    assert main(["remove", str(path), "chore/done", head], cwd=path, ops=_ops(merged)) == 2
    assert path.exists()


def test_지우다_만_워크트리_폴더_안에서_부르면_2로_끝난다(repo: Path) -> None:
    stray = repo / ".claude" / "worktrees" / "stray"
    stray.mkdir(parents=True)
    assert main(["judge"], cwd=stray, ops=_ops({})) == 2


def test_judge_는_체크아웃된_브랜치를_브랜치_줄로_찍지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, head = _add(repo, "done")
    main_tip = _git("rev-parse", "main", cwd=repo)
    merged = {"chore/done": frozenset({head}), "main": frozenset({main_tip})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    lines = capsys.readouterr().out.splitlines()
    branch_lines = [line for line in lines if line.startswith("브랜치")]
    assert not any("chore/done" in line or " main " in line for line in branch_lines)


def test_gh_가_실패하면_3으로_끝난다(repo: Path) -> None:
    def failing(_root: Path) -> dict[str, frozenset[str]]:
        raise ToolError("gh pr list 가 1 로 끝났다")

    assert main(["judge"], cwd=repo, ops=Ops(merged=failing, pid_alive=_죽었다)) == 3


def _멈춘_명령(seen: list[object]) -> object:
    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, 1)

    return stuck


def test_gh_가_시간을_넘기면_부르지_못한_것으로_멈춘다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """넘긴 gh 를 병합된 PR 이 없는 것으로 읽으면 판정이 달라진다. 종료 3 의 갈래로 간다(대기열
    342)."""
    seen: list[object] = []
    monkeypatch.setattr(subprocess, "run", _멈춘_명령(seen))

    with pytest.raises(ToolError, match="초 안에 돌아오지 않았다"):
        tidy_checkouts.gh_merged_heads(tmp_path)
    assert seen == [tidy_checkouts.CALL_TIMEOUT]


def test_tasklist_가_시간을_넘기면_살아_있다고_본다(monkeypatch: pytest.MonkeyPatch) -> None:
    """알 수 없으면 지우지 않는 쪽이다. CI(우분투)에서도 그 갈래를 밟도록 윈도로 보이게 한다."""
    seen: list[object] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", _멈춘_명령(seen))

    assert process_alive(4242)
    assert seen == [tidy_checkouts.CALL_TIMEOUT]


def test_살아_있는_pid_와_끝난_pid_를_가른다() -> None:
    assert process_alive(os.getpid())
    finished = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert not process_alive(int(finished.stdout))


def test_remove_는_무시된_것을_휴지통으로_옮긴_뒤_워크트리와_브랜치를_지우고_휴지통을_비운다(
    repo: Path,
) -> None:
    """옮기기(이름 바꾸기)는 git 보다 먼저, 휴지통 지우기는 git 보다 뒤다. 탐침의 이름 바꾸기
    둘(옮기고 되돌리기)이 앞에 있다."""
    path, head = _add(repo, "done")
    order: list[str] = []
    base = Ops()

    def rename(src: str, dst: str) -> None:
        if ".tidy-trash" in dst:
            order.append(Path(src).name)
            assert (path / ".git").exists(), "옮기기는 git 보다 먼저다"
        os.rename(src, dst)

    def delete(target: Path) -> None:
        order.append("delete:" + target.name)
        assert ".tidy-trash" in str(target), "지우기는 휴지통에서만 한다"
        base.delete(target)

    def git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if list(args[:2]) == ["worktree", "remove"]:
            order.append("git")
        return real_git(args, cwd)

    merged = {"chore/done": frozenset({head})}
    ops = replace(_ops(merged), delete=delete, git=git, rename=rename)
    assert main(["remove", path.as_posix(), "chore/done", head], cwd=repo, ops=ops) == 0
    assert sorted(order[:2]) == [".venv", "node_modules"]
    assert order[2] == "git"
    assert sorted(order[3:]) == ["delete:done~~.venv", "delete:done~~node_modules"]
    assert not path.exists()
    assert _git("branch", "--list", "chore/done", cwd=repo) == ""
    assert _trash(repo) == []


_WIDGET_PUBLIC = "web/apps/widget/public"


def _위젯을_띄운_워크트리(repo: Path, name: str) -> tuple[Path, str]:
    """위젯 시작 래퍼가 글꼴을 복사하고 페이지 안 번들을 지은 워크트리. 루트 `.gitignore` 처럼 그
    둘만 앵커로 무시하고 `public/` 은 추적하지 않으며, 그 위 `web/apps/widget/` 은 추적한다."""
    ignore = repo / ".gitignore"
    rules = f"/{_WIDGET_PUBLIC}/fonts/\n/{_WIDGET_PUBLIC}/element.js\n"
    ignore.write_bytes(ignore.read_bytes() + rules.encode())
    (repo / "web" / "apps" / "widget").mkdir(parents=True)
    (repo / "web" / "apps" / "widget" / "package.json").write_bytes(b"{}\n")
    _git("add", ".", cwd=repo)
    _git(*_IDENTITY, "commit", "-q", "-m", "위젯", cwd=repo)
    _git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=repo)
    path, head = _add(repo, name)
    public = path / _WIDGET_PUBLIC
    (public / "fonts").mkdir(parents=True)
    (public / "fonts" / "a.woff2").write_bytes(b"font")
    (public / "element.js").write_bytes(b"bundle")
    return path, head


def test_judge_와_remove_는_무시된_것만_든_미추적_폴더를_풀어_보고_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 464. git 의 기본 `--ignored`(traditional)는 무시된 것만 든 미추적 폴더를 그 폴더로
    접어 찍어, 위젯을 띄운 병합된 워크트리 아홉이 `web/apps/widget/public/` 때문에 남았다(일지
    2026-10-26-01 "정리"). 첫 단언은 그 접힘이 이 git 에서 나는지(재려는 상황의 표지)다. 풀어 읽은
    두 항목은 따로 휴지통으로 옮겨진다."""
    path, head = _위젯을_띄운_워크트리(repo, "widget")
    folded = _git("status", "--porcelain", "--ignored", cwd=path).splitlines()
    assert f"!! {_WIDGET_PUBLIC}/" in folded, folded
    merged = {"chore/widget": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/widget" in line)
    assert line.startswith("지운다"), line
    moved: list[str] = []

    def rename(src: str, dst: str) -> None:
        if ".tidy-trash" in dst:
            moved.append(Path(dst).name)
        os.rename(src, dst)

    ops = replace(_ops(merged), rename=rename)
    assert main(["remove", path.as_posix(), "chore/widget", head], cwd=repo, ops=ops) == 0
    assert not path.exists()
    assert _trash(repo) == []
    public = "widget~~web%2Fapps%2Fwidget%2Fpublic"
    assert f"{public}%2Ffonts" in moved, moved
    assert f"{public}%2Felement.js" in moved, moved


@pytest.mark.parametrize(
    ("relative", "reason"),
    [
        ("notes.txt", "바뀐 파일이 있다"),
        (".env", f"다시 만들 수 없는 무시된 항목: {_WIDGET_PUBLIC}/.env"),
    ],
    ids=["무시되지_않은_새_파일", "무시된_env"],
)
def test_judge_와_remove_는_풀어_본_폴더_안의_다시_만들_수_없는_것을_보고_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str], relative: str, reason: str
) -> None:
    """반박 시험(`.claude/rules/tools.md`). 접힌 폴더를 풀어 읽는 길이 그 안의 커밋하지 않은 파일과,
    무시됐지만 다시 만들 수 없는 파일을 지나치지 않는다. `.env` 는 픽스처의 `.gitignore` 가 어느
    깊이에서나 무시한다."""
    path, head = _위젯을_띄운_워크트리(repo, "widget")
    (path / _WIDGET_PUBLIC / relative).write_text("x", encoding="utf-8")
    merged = {"chore/widget": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/widget" in line)
    assert line.startswith("남긴다"), line
    assert line.endswith(f" — {reason}"), line
    assert main(["remove", path.as_posix(), "chore/widget", head], cwd=repo, ops=_ops(merged)) == 1
    assert (path / _WIDGET_PUBLIC / relative).exists()
    assert (path / _WIDGET_PUBLIC / "element.js").exists()


@pytest.mark.parametrize(
    ("folder", "action", "code"),
    [(".grimp_cache", "지운다", 0), ("notes", "남긴다", 1)],
    ids=["grimp_캐시", "다시_만들_수_없는_폴더"],
)
def test_judge_와_remove_는_안쪽_gitignore_로만_무시된_폴더를_조상_폴더로_가른다(
    repo: Path, capsys: pytest.CaptureFixture[str], folder: str, action: str, code: int
) -> None:
    """셀프 리뷰 명세 축. Grimp 는 `.grimp_cache/` 안에 `*` 줄이 든 `.gitignore` 를 두고(주
    체크아웃의 것을 손으로 봤다) 루트 `.gitignore` 는 그 폴더를 무시하지 않아, `matching` 은 그 안을
    하나씩 찍는다. 첫 단언은 그렇게 찍히는지(재려는 상황의 표지)다. 다시 만들 수 있는 폴더 아래면
    지우고, 같은 꼴이어도 그 밖의 폴더면 남긴다(반박 시험)."""
    path, head = _add(repo, "cachewt")
    cache = path / folder
    (cache / "sub").mkdir(parents=True)
    (cache / ".gitignore").write_text("# Automatically created by Grimp.\n*\n", encoding="utf-8")
    (cache / "CACHEDIR.TAG").write_text("Signature: x\n", encoding="utf-8")
    (cache / "sub" / "a.data.json").write_text("{}", encoding="utf-8")
    listed = _git("status", "--porcelain", "--ignored=matching", cwd=path).splitlines()
    assert f"!! {folder}/.gitignore" in listed, listed
    merged = {"chore/cachewt": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/cachewt" in line)
    assert line.startswith(action), line
    moved: list[str] = []

    def rename(src: str, dst: str) -> None:
        if ".tidy-trash" in dst:
            moved.append(Path(dst).name)
        os.rename(src, dst)

    argv = ["remove", path.as_posix(), "chore/cachewt", head]
    assert main(argv, cwd=repo, ops=replace(_ops(merged), rename=rename)) == code
    assert path.exists() == (code == 1)
    # 폴더째 한 번에 옮긴다(PR 직전 bug-perf-review). 안쪽 `.gitignore` 만 먼저 옮기면 남은 것이
    # 미추적이 된다
    cache_moves = sorted(name for name in moved if folder in name)
    assert cache_moves == ([f"cachewt~~{folder}"] if code == 0 else []), moved


@pytest.mark.parametrize(
    ("inner", "action", "code"),
    [(".env", "남긴다", 1), ("node_modules/pkg/index.js", "지운다", 0)],
    ids=["무시된_env", "다시_만들_수_있는_안쪽_폴더"],
)
def test_judge_와_remove_는_추적_파일이_든_폴더로_접지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str], inner: str, action: str, code: int
) -> None:
    """PR 봇 CodeRabbit 첫 회차(반박 시험, `.claude/rules/tools.md`). 다시 만들 수 있는 이름의
    폴더에 추적 파일이 있으면 git 은 그 안의 무시된 항목을 하나씩 찍는다(첫 단언이 그 표지다). 그
    폴더로 접으면 옮기기가 추적 파일까지 옮겨 `git worktree remove` 가 막힌다. 접지 않으면 무시된
    항목은 제 이름으로 판정되고, 그 안의 다시 만들 수 있는 폴더는 그 폴더로 접힌다."""
    path, _ = _add(repo, "trackedwt")
    (path / "coverage").mkdir()
    (path / "coverage" / "keep.txt").write_bytes(b"keep\n")
    _git("add", "coverage/keep.txt", cwd=path)
    _git(*_IDENTITY, "commit", "-m", "keep", cwd=path)
    head = _git("rev-parse", "HEAD", cwd=path)
    target = path / "coverage" / inner
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x", encoding="utf-8")
    listed = _git("status", "--porcelain", "--ignored=matching", cwd=path).splitlines()
    first = inner.split("/", 1)[0]
    assert any(entry.startswith(f"!! coverage/{first}") for entry in listed), listed
    merged = {"chore/trackedwt": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/trackedwt" in line)
    assert line.startswith(action), line
    if code == 1:
        assert line.endswith(" — 다시 만들 수 없는 무시된 항목: coverage/.env"), line
    moved: list[str] = []

    def rename(src: str, dst: str) -> None:
        if ".tidy-trash" in dst:
            moved.append(Path(dst).name)
        os.rename(src, dst)

    argv = ["remove", path.as_posix(), "chore/trackedwt", head]
    assert main(argv, cwd=repo, ops=replace(_ops(merged), rename=rename)) == code
    assert path.exists() == (code == 1)
    coverage_moves = sorted(name for name in moved if "coverage" in name)
    expected = ["trackedwt~~coverage%2Fnode_modules"] if code == 0 else []
    assert coverage_moves == expected, moved


def test_judge_는_ls_files_를_읽지_못하면_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """추적 파일이 든 폴더를 모르면 무시된 항목을 어디로 접을지 가를 수 없다. `status` 를 읽지
    못한 때와 같이 남긴다."""
    path, head = _add(repo, "lsfail")

    def git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if list(args[:1]) == ["ls-files"]:
            return subprocess.CompletedProcess(list(args), 128, "", "fatal: ls-files 막힘\n")
        return real_git(args, cwd)

    merged = {"chore/lsfail": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=replace(_ops(merged), git=git)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/lsfail" in line)
    assert line.endswith(" — git 이 경고를 냈다: ls-files: fatal: ls-files 막힘"), line
    assert path.exists()


@pytest.mark.parametrize(
    ("link", "layout", "windows"),
    [
        (
            ".grimp_cache",
            {".gitignore": "*\n", "a.json": "{}", "keep/secret.txt": "s"},
            ("지운다", "", 0),
        ),
        (
            "foo",
            {"node_modules/pkg/index.js": "x"},
            ("남긴다", " — 다시 만들 수 없는 무시된 항목: foo/", 1),
        ),
    ],
    ids=["다시_만들_수_있는_이름의_링크", "그_밖의_링크"],
)
def test_judge_와_remove_는_링크_안의_무시된_것을_링크째로_보고_바깥을_옮기지_않는다(
    repo: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    link: str,
    layout: dict[str, str],
    windows: tuple[str, str, int],
) -> None:
    """PR 직전 bug-perf-review(반박 시험, `.claude/rules/tools.md` 의 지우는 자리 안의 링크). 윈도의
    git 2.32 는 정션을 따라가 `matching` 으로 그 안을 하나씩 찍는다(첫 단언이 그 표지다). 링크째로
    접어, 다시 만들 수 있는 이름의 링크는 링크만 옮기고 그 밖의 링크는 남긴다. 리눅스의 git 은
    심볼릭 링크를 따라가지 않고 미추적 항목으로 찍어 바뀐 파일로 남긴다. 어느 쪽이든 링크 바깥의
    파일은 그대로다."""
    path, head = _add(repo, "linkwt")
    outside = tmp_path / "outside"
    for relative, text in layout.items():
        (outside / relative).parent.mkdir(parents=True, exist_ok=True)
        (outside / relative).write_text(text, encoding="utf-8")
    _link(path / link, outside)
    if sys.platform == "win32":
        listed = _git("status", "--porcelain", "--ignored=matching", cwd=path).splitlines()
        inner = next(iter(layout)).split("/", 1)[0]
        assert any(entry.startswith(f"!! {link}/{inner}") for entry in listed), listed
        action, suffix, code = windows
    else:
        assert f"?? {link}" in _git("status", "--porcelain", cwd=path).splitlines()
        action, suffix, code = "남긴다", " — 바뀐 파일이 있다", 1
    merged = {"chore/linkwt": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/linkwt" in line)
    assert line.startswith(action), line
    assert line.endswith(suffix), line
    argv = ["remove", path.as_posix(), "chore/linkwt", head]
    assert main(argv, cwd=repo, ops=_ops(merged)) == code
    assert sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*") if p.is_file()) == (
        sorted(layout)
    )


@pytest.mark.parametrize("ignored", [(".env",), ()], ids=["무시된_env", "무시된_것_없음"])
def test_judge_와_remove_는_추적_폴더를_갈음한_링크가_있으면_남긴다(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], ignored: tuple[str, ...]
) -> None:
    """셀프 리뷰 명세 축과 PR 직전 bug-perf-review 의 대체 리뷰(반박 시험, 지우는 자리 안의 링크).
    커밋한 `coverage/` 를 링크로 갈음하면 윈도의 git 2.32 는 정션을 따라가 추적 파일을 바뀌지 않은
    것으로 보고, 무시된 것이 있으면 `coverage/.env` 만, 없으면 아무것도 찍지 않는다(첫 단언이 그
    표지다). 링크째로 옮기면 추적 파일이 빠져 `git worktree remove` 가 막히고, 옮길 것이 없으면
    `git worktree remove` 가 정션을 따라가 링크 바깥의 파일을 지운다. 그래서 무시된 것과 상관없이
    남긴다. 리눅스의 git 은 심볼릭 링크를 따라가지 않아 바뀐 파일로 남긴다."""
    path, _ = _add(repo, "pinwt")
    (path / "coverage").mkdir()
    (path / "coverage" / "keep.txt").write_bytes(b"keep\n")
    _git("add", "coverage/keep.txt", cwd=path)
    _git(*_IDENTITY, "commit", "-m", "keep", cwd=path)
    head = _git("rev-parse", "HEAD", cwd=path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"keep\n")
    for name in ignored:
        (outside / name).write_text("SECRET=1", encoding="utf-8")
    shutil.rmtree(path / "coverage")
    _link(path / "coverage", outside)
    if sys.platform == "win32":
        listed = _git("status", "--porcelain", "--ignored=matching", cwd=path).splitlines()
        expected = [f"!! coverage/{name}" for name in ignored]
        assert [entry for entry in listed if "coverage" in entry] == expected, listed
        suffix = " — 추적 폴더를 링크가 갈음했다: coverage/"
    else:
        assert _git("status", "--porcelain", cwd=path), "리눅스의 git 이 바뀐 것을 찍지 않았다"
        suffix = " — 바뀐 파일이 있다"
    merged = {"chore/pinwt": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/pinwt" in line)
    assert line.startswith("남긴다"), line
    assert line.endswith(suffix), line
    argv = ["remove", path.as_posix(), "chore/pinwt", head]
    assert main(argv, cwd=repo, ops=_ops(merged)) == 1
    assert (path / "coverage" / "keep.txt").exists()
    assert sorted(p.name for p in outside.iterdir()) == sorted([*ignored, "keep.txt"])


@pytest.mark.parametrize(
    ("name", "committed", "layout", "reason"),
    [
        ("coverage", ("keep.txt",), {"keep.txt": "keep\n"}, "추적 폴더를 링크가 갈음했다"),
        ("foo", (), {"node_modules/pkg/index.js": "x"}, "다시 만들 수 없는 무시된 항목"),
    ],
    ids=["추적_폴더_자리의_링크", "무시된_것이_든_링크"],
)
def test_judge_와_remove_는_MAX_PATH_를_넘는_링크도_링크로_본다(
    repo: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    committed: tuple[str, ...],
    layout: dict[str, str],
    reason: str,
) -> None:
    """셀프 리뷰 명세 축(반박 시험, 윈도 경로 정규화가 바꾸는 이름). 링크 경로가 MAX_PATH(260자)를
    넘으면 `\\\\?\\` 없이 물은 링크 판정이 거짓이라(`LongPathsEnabled=0` 인 이 PC), 추적 폴더를
    갈음한 링크를 찾지 못해 `git worktree remove` 가 링크 바깥을 지웠고, 무시된 것이 든 링크를
    접지 못해 그 안의 `node_modules/` 를 옮겼다. 첫 단언(경로 길이)이 그 표지다. 리눅스의 git 은
    심볼릭 링크를 따라가지 않아 바뀐 파일로 남긴다."""
    path, head = _add(repo, "deepwt")
    link = "/".join(["d" * 40] * 5) + f"/{name}"
    assert len(str(path / link)) > 260
    if committed:
        Path(long_path(path / link)).mkdir(parents=True)
        for relative in committed:
            Path(long_path(path / link / relative)).write_bytes(layout[relative].encode())
        _git("add", link, cwd=path)
        _git(*_IDENTITY, "commit", "-m", "deep", cwd=path)
        head = _git("rev-parse", "HEAD", cwd=path)
        shutil.rmtree(long_path(path / link))
    else:
        Path(long_path(path / link)).parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    for relative, text in layout.items():
        (outside / relative).parent.mkdir(parents=True, exist_ok=True)
        (outside / relative).write_bytes(text.encode())
    _link(Path(long_path(path / link)), outside)
    if sys.platform == "win32":
        suffix = f" — {reason}: {link}/"
    else:
        assert _git("status", "--porcelain", cwd=path), "리눅스의 git 이 바뀐 것을 찍지 않았다"
        suffix = " — 바뀐 파일이 있다"
    merged = {"chore/deepwt": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/deepwt" in line)
    assert line.startswith("남긴다"), line
    assert line.endswith(suffix), line
    argv = ["remove", path.as_posix(), "chore/deepwt", head]
    assert main(argv, cwd=repo, ops=_ops(merged)) == 1
    assert sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*") if p.is_file()) == (
        sorted(layout)
    )


def test_remove_는_MAX_PATH_를_넘는_다시_만들_수_있는_이름의_링크도_링크만_옮긴다(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PR 봇 CodeRabbit 이 한도에 걸려 대신 돌린 bug-perf-review(반박 시험, 윈도 경로 정규화가
    바꾸는 이름). 다시 만들 수 있는 이름의 링크(`node_modules`)는 판정이 `지운다` 이고 `remove` 가
    링크만 휴지통으로 옮긴다. 링크 경로가 MAX_PATH(260자)를 넘으면 `\\\\?\\` 없이 물은
    `os.path.lexists` 가 거짓이라(`LongPathsEnabled=0` 인 이 PC) 옮기기가 그 링크를 건너뛰었고,
    `git worktree remove` 가 정션을 따라가 링크 바깥의 파일을 지웠다. 첫 단언(경로 길이)이 그
    표지다. 리눅스의 git 은 심볼릭 링크를 `node_modules/` 패턴에 맞추지 않고 미추적 항목으로 찍어
    바뀐 파일로 남긴다."""
    path, head = _add(repo, "deepnm")
    link = "/".join(["d" * 40] * 5) + "/node_modules"
    assert len(str(path / link)) > 260
    Path(long_path(path / link)).parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    layout = {"pkg/index.js": "x", "keep.txt": "keep\n"}
    for relative, text in layout.items():
        (outside / relative).parent.mkdir(parents=True, exist_ok=True)
        (outside / relative).write_bytes(text.encode())
    _link(Path(long_path(path / link)), outside)
    if sys.platform == "win32":
        action, suffix, code = "지운다", "", 0
    else:
        assert _git("status", "--porcelain", cwd=path), "리눅스의 git 이 바뀐 것을 찍지 않았다"
        action, suffix, code = "남긴다", " — 바뀐 파일이 있다", 1
    merged = {"chore/deepnm": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/deepnm" in line)
    assert line.startswith(action), line
    assert line.endswith(suffix), line
    argv = ["remove", path.as_posix(), "chore/deepnm", head]
    assert main(argv, cwd=repo, ops=_ops(merged)) == code
    assert sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*") if p.is_file()) == (
        sorted(layout)
    )


def test_못_보는_것_remove_는_휴지통_자리_이름이_한_토막_한도를_넘는_항목을_옮기지_못해_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """셀프 리뷰 명세 축(기점 35481b0b). 휴지통 자리 이름 `<워크트리 이름>~~<flatten(항목)>` 이 파일
    시스템이 경로 한 토막에 허용하는 길이(이 PC 의 NTFS 에서 255자)를 넘으면 이름 바꾸기가 막힌다.
    `judge` 는 `지운다` 를 내고 `remove` 는 남긴다(남기는 쪽이다). 첫 단언(자리 이름의 길이)이 그
    표지다."""
    path, head = _add(repo, "longslot")
    entry = "/".join(["d" * 40] * 6) + "/node_modules"
    assert len(f"{path.name}~~{tidy_checkouts.flatten(entry)}") > 255
    Path(long_path(path / entry / "pkg")).mkdir(parents=True)
    Path(long_path(path / entry / "pkg" / "index.js")).write_bytes(b"x")
    merged = {"chore/longslot": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/longslot" in line)
    assert line.startswith("지운다"), line
    argv = ["remove", path.as_posix(), "chore/longslot", head]
    assert main(argv, cwd=repo, ops=_ops(merged)) == 1
    assert f"다시 만들 수 있는 {entry}/ 를 휴지통으로 옮기다 막혔다" in capsys.readouterr().out
    assert os.path.lexists(long_path(path / entry / "pkg" / "index.js"))


def test_remove_는_judge_뒤에_바뀌었으면_손대지_않는다(repo: Path) -> None:
    path, head = _add(repo, "done")
    merged = {"chore/done": frozenset({head})}
    assert main(["remove", str(path), "chore/done", _OLD], cwd=repo, ops=_ops(merged)) == 1
    assert main(["remove", str(path), "chore/other", head], cwd=repo, ops=_ops(merged)) == 1
    unknown = str(repo / ".claude" / "worktrees" / "nope")
    assert main(["remove", unknown, "chore/done", head], cwd=repo, ops=_ops(merged)) == 1
    assert (path / ".venv").exists()
    assert _registered(repo, path)


def test_remove_는_탐침_자리가_이미_있으면_손대지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """윈도는 있는 폴더 위로 이름을 바꾸지 못해 탐침이 막힌 것으로도 1이 나므로 이유까지 본다.
    리눅스의 `rename` 은 빈 폴더를 덮어쓴다."""
    path, head = _add(repo, "done")
    path.with_name("done.tidy-probe").mkdir()
    merged = {"chore/done": frozenset({head})}
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=_ops(merged)) == 1
    assert "탐침 자리" in capsys.readouterr().out
    assert (path / ".venv").exists()


def test_remove_는_다시_판정해_어긋나면_손대지_않는다(repo: Path) -> None:
    """후보가 아니면 탐침(폴더 이름 바꾸기)도 하지 않는다. 옮기기 직전의 재판정과 따로 잰다."""
    path, head = _add(repo, "done")
    (path / "new.py").write_text("x", encoding="utf-8")
    renamed: list[str] = []

    def spy(src: str, dst: str) -> None:
        renamed.append(dst)
        os.rename(src, dst)

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=spy)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    assert renamed == []
    assert (path / ".venv").exists()


def test_remove_는_이름_바꾸기가_막히면_손대지_않는다(repo: Path) -> None:
    path, head = _add(repo, "done")

    def held(_src: str, _dst: str) -> None:
        raise PermissionError(13, "액세스가 거부되었습니다")

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=held)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    assert (path / ".venv" / "Lib" / "mod.py").exists()
    assert (path / ".git").exists()
    assert _registered(repo, path)


def test_remove_는_이름_바꾸기가_막히면_쥔_프로세스를_이유에_적는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 177. 남은 워크트리는 데스크톱 앱이 띄운 `claude.exe` 가 작업 디렉터리로 쥐었다."""
    path, head = _add(repo, "done")
    scans: list[int] = []

    def held(_src: str, _dst: str) -> None:
        raise PermissionError(32, "다른 프로세스가 파일을 사용 중이기 때문에")

    def processes() -> list[tuple[int, str, str]]:
        scans.append(1)
        return [(61148, "claude.exe", str(path)), (7, "python.exe", str(repo))]

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=held, processes=processes)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    out = capsys.readouterr().out
    assert "다른 프로세스가 쥐고 있다" in out
    assert "작업 디렉터리로 쥔 프로세스: claude.exe(pid 61148)" in out
    assert "pid 7" not in out
    assert len(scans) == 1


def test_remove_는_탐침이_지나면_옮기기_직전에만_한_번_훑는다(repo: Path) -> None:
    """탐침은 막혔을 때만 훑고, 지나간 지우기는 옮기기 직전의 다시 거르기에서 한 번 훑는다(판정
    4의 2). 탐침 앞의 재판정은 훑지 않는다."""
    path, head = _add(repo, "done")
    scans: list[int] = []

    def processes() -> list[tuple[int, str, str]]:
        scans.append(1)
        return []

    ops = replace(_ops({"chore/done": frozenset({head})}), processes=processes)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 0
    assert len(scans) == 1


def test_remove_는_judge_뒤에_작업_디렉터리_주인이_생기면_옮기기_전에_멈춘다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PR #184 리뷰. 리눅스의 탐침은 작업 디렉터리를 보지 못해, `judge` 뒤에 들어온 주인은 앞지우기
    직전의 다시 거르기가 잡는다. 죽은 잠금도 풀지 않는다."""
    path, head = _add(repo, "done")
    _git("worktree", "lock", "--reason", "claude session done (pid 999999)", str(path), cwd=repo)

    def processes() -> list[tuple[int, str, str]]:
        return [(61148, "claude.exe", str(path))]

    ops = replace(_ops({"chore/done": frozenset({head})}), processes=processes)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    out = capsys.readouterr().out
    assert "옮기기 직전에 다시 판정했다" in out
    assert "claude.exe(pid 61148)" in out
    assert (path / ".venv" / "Lib" / "mod.py").exists()
    assert _registered(repo, path)
    listing = parse_worktrees(_git("worktree", "list", "--porcelain", cwd=repo) + "\n")
    done = next(w for w in listing if w.branch == "chore/done")
    assert done.locked == "claude session done (pid 999999)"


def test_remove_는_이름을_끝내_되돌리지_못하면_다시_시도한_뒤_3으로_멈춘다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, head = _add(repo, "done")
    calls: list[str] = []
    slept: list[float] = []

    def stuck(src: str, dst: str) -> None:
        calls.append(dst)
        if len(calls) >= 2:
            raise PermissionError(5, "액세스가 거부되었습니다")
        os.rename(src, dst)

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=stuck, sleep=slept.append)
    try:
        assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 3
    finally:
        aside = Path(calls[0])
        if aside.exists():
            os.rename(aside, path)
    out = capsys.readouterr().out
    assert "멈췄다" in out
    assert f"{len(calls) - 1}번" in out
    assert len(calls) - 1 == len(slept) + 1 > 2
    assert _git("branch", "--list", "chore/done", cwd=repo) != ""


def test_remove_는_되돌리기가_한_번_막혀도_다시_시도해_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 202. 옮기기가 지난 뒤 되돌리기가 `WinError 5` 로 한 번 막혀 폴더가 옆 이름에
    남았다."""
    path, head = _add(repo, "done")
    calls: list[str] = []
    slept: list[float] = []

    def once(src: str, dst: str) -> None:
        if ".tidy-trash" in dst:
            os.rename(src, dst)
            return
        calls.append(dst)
        if len(calls) == 2:
            raise PermissionError(5, "액세스가 거부되었습니다")
        os.rename(src, dst)

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=once, sleep=slept.append)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 0
    assert len(calls) == 3
    assert len(slept) == 1
    assert "다시 시도" in capsys.readouterr().out
    assert not path.exists()
    assert not Path(calls[0]).exists()


def test_remove_는_모듈을_올린_프로세스를_옮기기_전에_보지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 201 의 반대 방향. 올린 모듈은 이름 바꾸기를 막지 않으므로 옮기기 전의 재판정은 모듈을
    보지 않고, 막히는 것은 휴지통에서 난다(실제 자식 프로세스로 재는 것은 위의 휴지통 시험)."""
    path, head = _add(repo, "done")
    module = str(path / ".venv" / "Lib" / "mod.pyd")

    def modules() -> list[tuple[int, str, str]]:
        return [(26016, "python.exe", module)]

    ops = replace(_ops({"chore/done": frozenset({head})}), modules=modules)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 0
    out = capsys.readouterr().out
    assert "남겼다" not in out
    assert not path.exists()
    assert _trash(repo) == []


def test_judge_는_분리_HEAD_가_origin_main_에_있으면_지울_후보로_찍고_remove_가_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """2026-10-15 에 모델 스윕과 옛 세션의 분리 HEAD 워크트리 일곱이 넘겨진 채 남아 있었다."""
    path, head = _add_detached(repo, "sweep")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/sweep" in line)
    assert line.startswith("지운다"), line
    assert f'remove "{path.as_posix()}" .detached {head}' in line
    assert main(["remove", path.as_posix(), ".detached", head], cwd=repo, ops=_ops({})) == 0
    assert "분리 HEAD" in capsys.readouterr().out
    assert not path.exists()
    assert not _registered(repo, path)


def test_judge_는_분리_HEAD_가_origin_main_에_없으면_사람에게_넘긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = _add_detached(repo, "sweep")
    (path / "new.txt").write_text("x", encoding="utf-8")
    _git("add", "new.txt", cwd=path)
    _git(*_IDENTITY, "commit", "-m", "유일한 커밋", cwd=path)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/sweep" in line)
    assert line.startswith("넘긴다"), line
    assert "origin/main 에 없다" in line


def test_judge_는_폴더_없는_등록을_지울_후보로_찍고_remove_가_등록을_걷는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """git 2.32 의 `worktree remove` 는 폴더가 없는 등록을 종료 0으로 걷는다(임시 저장소에서
    손으로 봤다). 브랜치는 남고 다음 `judge` 가 origin/main 에 있는 것으로 지운다."""
    path, head = _add(repo, "gone")
    shutil.rmtree(path)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/gone" in line)
    assert line.startswith("지운다"), line
    assert "등록만 남았다" in line
    assert main(["remove", path.as_posix(), "chore/gone", head], cwd=repo, ops=_ops({})) == 0
    assert "걷었다" in capsys.readouterr().out
    assert not _registered(repo, path)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    branch = next(line for line in capsys.readouterr().out.splitlines() if "chore/gone" in line)
    assert branch.startswith("브랜치를 지운다"), branch
    assert "origin/main" in branch


def test_judge_는_git_없는_prunable_폴더를_등록_없는_폴더처럼_판정하고_remove_가_걷는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """2026-10-15 에 `.git` 없이 `web/` 만 남은 prunable 워크트리가 넘겨진 채 남아 있었다. git 은
    폴더가 있는 채로는 그 등록을 걷지 않아, 폴더를 휴지통으로 옮긴 뒤 걷는다. 커밋에 없는 파일이
    있으면 남긴다."""
    path, head = _add(repo, "half")
    (path / ".git").unlink()
    (path / "late.py").write_text("커밋에 없다", encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/half" in line)
    assert line.startswith("남긴다"), line
    assert "late.py" in line
    (path / "late.py").unlink()
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/half" in line)
    assert line.startswith("지운다"), line
    assert f'remove "{path.as_posix()}" chore/half {head}' in line
    assert main(["remove", path.as_posix(), "chore/half", head], cwd=repo, ops=_ops({})) == 0
    assert "걷었다" in capsys.readouterr().out
    assert not path.exists()
    assert not _registered(repo, path)
    assert _trash(repo) == []


def test_judge_는_폴더_없는_등록의_옆_이름_폴더가_있으면_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = _add(repo, "lost")
    os.rename(path, path.with_name("lost.tidy-probe"))
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/lost " in line)
    assert line.startswith("남긴다"), line
    assert ".tidy-probe" in line


def test_judge_는_폴더_없는_분리_HEAD_등록을_origin_main_에_없으면_넘기고_있으면_걷는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """명세 축 리뷰(Critical). 폴더 없는 등록을 무조건 걷던 첫 판은 `origin/main` 에 없는 커밋의
    마지막 참조를 걷어 그 커밋이 매달렸다(리뷰가 임시 저장소에서 재현했다). 잠긴 등록도 걷지
    않는다."""
    unique, _ = _add_detached(repo, "unique")
    (unique / "only.txt").write_text("x", encoding="utf-8")
    _git("add", "only.txt", cwd=unique)
    _git(*_IDENTITY, "commit", "-q", "-m", "origin/main 에 없는 커밋", cwd=unique)
    head = _git("rev-parse", "HEAD", cwd=unique)
    shutil.rmtree(unique)
    plain, plain_head = _add_detached(repo, "plain")
    shutil.rmtree(plain)
    locked, _ = _add(repo, "locked")
    _git("worktree", "lock", "--reason", "이동식 매체", str(locked), cwd=repo)
    shutil.rmtree(locked)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    out = capsys.readouterr().out.splitlines()
    kept = next(line for line in out if "/unique" in line)
    assert kept.startswith("넘긴다"), kept
    assert "origin/main 에 없다" in kept
    gone = next(line for line in out if "/plain" in line)
    assert gone.startswith("지운다"), gone
    held = next(line for line in out if "/locked" in line)
    assert held.startswith("넘긴다"), held
    assert "잠겨" in held
    assert main(["remove", unique.as_posix(), ".detached", head], cwd=repo, ops=_ops({})) == 1
    assert "origin/main 에 없다" in capsys.readouterr().out
    assert _registered(repo, unique)
    assert _git("cat-file", "-t", head, cwd=repo) == "commit"
    assert main(["remove", plain.as_posix(), ".detached", plain_head], cwd=repo, ops=_ops({})) == 0
    assert not _registered(repo, plain)


def test_origin_main_이_없는_저장소에서는_분리_HEAD_와_PR_없는_브랜치를_모두_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """못 보는 것을 고정한다(얕은 클론, 클라우드 세션, 원격 없는 임시 저장소)."""
    _git("update-ref", "-d", "refs/remotes/origin/main", cwd=repo)
    path, _ = _add_detached(repo, "sweep")
    _git("branch", "worktree-x", cwd=repo)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    out = capsys.readouterr().out.splitlines()
    assert next(line for line in out if "/sweep" in line).startswith("넘긴다")
    assert next(line for line in out if "worktree-x" in line).startswith("브랜치를 남긴다")
    assert path.exists()


def test_휴지통_자리_이름은_옛_자리로_되돌릴_수_있다(repo: Path) -> None:
    """`__pycache__` 처럼 `_` 가 든 이름과 겹쳐 번호가 붙은 자리도 되돌린다."""
    for relative in ["src/agent_os/__pycache__/", "web/node_modules/", "odd%name/", ".venv/"]:
        slot = tidy_checkouts.trash_slot(repo, "wt", relative)
        slot.parent.mkdir(parents=True, exist_ok=True)
        slot.mkdir()
        again = tidy_checkouts.trash_slot(repo, "wt", relative)
        assert again != slot and again.name.endswith("~1")
        expected = (repo / ".claude" / "worktrees" / "wt" / relative.rstrip("/")).as_posix()
        assert tidy_checkouts.origin_of(repo, slot) == expected
        assert tidy_checkouts.origin_of(repo, again) == expected


def test_judge_는_PR_없이_origin_main_에_든_브랜치를_지울_후보로_찍고_remove_branch_가_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`EnterWorktree` 가 만들고 세션이 떠난 `worktree-*` 브랜치의 모양."""
    _git("branch", "worktree-x", cwd=repo)
    _git("branch", "ahead", cwd=repo)
    (repo / "more.txt").write_text("x", encoding="utf-8")
    _git("add", "more.txt", cwd=repo)
    _git(*_IDENTITY, "commit", "-m", "main 보다 앞선 커밋", cwd=repo)
    _git("branch", "-f", "ahead", "HEAD", cwd=repo)
    _git("reset", "-q", "--hard", "HEAD~1", cwd=repo)
    tip = _git("rev-parse", "worktree-x", cwd=repo)
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    out = capsys.readouterr().out
    gone = next(line for line in out.splitlines() if "worktree-x" in line)
    assert gone.startswith("브랜치를 지운다"), gone
    assert f"remove-branch worktree-x {tip}" in gone
    kept = next(line for line in out.splitlines() if " ahead " in line)
    assert kept.startswith("브랜치를 남긴다"), kept
    assert main(["remove-branch", "worktree-x", tip], cwd=repo, ops=_ops({})) == 0
    assert _git("branch", "--list", "worktree-x", cwd=repo) == ""
    assert _git("branch", "--list", "ahead", cwd=repo) != ""


def _branch_line(out: str, name: str) -> str:
    return next(line for line in out.splitlines() if f" {name} " in line)


def test_judge_와_remove_branch_는_막_딴_브랜치를_남기고_창이_지나면_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 440. 나란히 연 형제 세션이 `git worktree add -b` 로 딴 브랜치는 등록이 생기기 전이나
    `judge` 가 워크트리 목록을 읽은 뒤에 생기면 체크아웃되지 않은 것으로 보인다. 첫 세션의 정리가
    형제 셋의 브랜치를 PR 없이 origin/main 에 있다며 지울 후보로 냈다(일지 2026-10-23-13).
    `remove-branch` 의 재판정도 같은 창을 본다."""
    _git("branch", "worktree-x", cwd=repo)
    tip = _git("rev-parse", "worktree-x", cwd=repo)
    now = _ops({}, now=time.time)
    assert main(["judge"], cwd=repo, ops=now) == 0
    kept = _branch_line(capsys.readouterr().out, "worktree-x")
    assert kept.startswith("브랜치를 남긴다 worktree-x — 막 딴 브랜치다"), kept
    assert "remove-branch" not in kept
    assert main(["remove-branch", "worktree-x", tip], cwd=repo, ops=now) == 1
    assert "막 딴 브랜치다" in capsys.readouterr().out
    assert _git("branch", "--list", "worktree-x", cwd=repo) != ""
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    gone = _branch_line(capsys.readouterr().out, "worktree-x")
    assert gone.startswith("브랜치를 지운다"), gone
    assert main(["remove-branch", "worktree-x", tip], cwd=repo, ops=_ops({})) == 0
    assert _git("branch", "--list", "worktree-x", cwd=repo) == ""


def test_judge_와_remove_branch_는_이름을_바꾼_지_얼마_안_됐거나_앞날_기록이면_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """반박 시험(`.claude/rules/tools.md`). `EnterWorktree` 가 딴 `worktree-*` 를 세션이 `git branch
    -m` 으로 바꾼다. 바꾼 기록이 reflog 의 맨 위에 와(git 2.32 에서 손으로 봤다) 딴 지 오래된
    브랜치도 막 바꿨으면 막 딴 것이다. 앞날 시각의 기록(시계가 어긋난 PC)도 남긴다. 판정은 지금
    시각으로 한다. 같은 입력을 `remove-branch` 의 재판정에도 넣는다(셀프 리뷰 명세 축)."""
    old = time.time() - 2 * FRESH_SECONDS
    _git_at(old, "branch", "stale", cwd=repo)
    _git_at(old, "branch", "worktree-y", cwd=repo)
    _git("branch", "-m", "worktree-y", "chore/renamed", cwd=repo)
    _git_at(time.time() + 24 * FRESH_SECONDS, "branch", "ahead-clock", cwd=repo)
    assert main(["judge"], cwd=repo, ops=_ops({}, now=time.time)) == 0
    out = capsys.readouterr().out
    assert _branch_line(out, "stale").startswith("브랜치를 지운다")
    assert _branch_line(out, "chore/renamed").startswith("브랜치를 남긴다")
    assert _branch_line(out, "ahead-clock").startswith("브랜치를 남긴다")
    for name in ("chore/renamed", "ahead-clock"):
        tip = _git("rev-parse", name, cwd=repo)
        assert main(["remove-branch", name, tip], cwd=repo, ops=_ops({}, now=time.time)) == 1, name
        assert _git("rev-parse", name, cwd=repo) == tip


def test_못_보는_것_reflog_가_없는_브랜치는_막_딴_것인지_몰라_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """reflog 를 남기지 않는 저장소(`core.logAllRefUpdates=false`)와 기록이 만료된 브랜치. 잃는
    것은 이름이고 커밋은 origin/main 에 있다."""
    _git("-c", "core.logAllRefUpdates=false", "branch", "nolog", cwd=repo)
    assert _git("log", "-g", "--format=%gd", "refs/heads/nolog", "--", cwd=repo) == ""
    tip = _git("rev-parse", "nolog", cwd=repo)
    now = _ops({}, now=time.time)
    assert main(["judge"], cwd=repo, ops=now) == 0
    assert _branch_line(capsys.readouterr().out, "nolog").startswith("브랜치를 지운다")
    assert main(["remove-branch", "nolog", tip], cwd=repo, ops=now) == 0


def test_못_보는_것_judge_가_두_목록_사이에_체크아웃된_오래된_브랜치는_지울_후보로_찍는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`judge` 는 워크트리 목록을 읽은 뒤에 브랜치 목록을 읽는다. 그사이 형제 세션이 reflog 의
    마지막 기록이 창 밖인 브랜치를 체크아웃하면 체크아웃은 그 브랜치의 reflog 에 기록을 남기지 않아
    지울 후보로 찍힌다. `remove-branch` 가 등록을 다시 읽어 남긴다(셀프 리뷰 표준 축)."""
    _git_at(time.time() - 2 * FRESH_SECONDS, "branch", "chore/old", cwd=repo)
    tip = _git("rev-parse", "chore/old", cwd=repo)
    path = repo / ".claude" / "worktrees" / "old"

    def sibling_checks_out(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        listing_branches = "--format=%(refname:short) %(objectname)" in args
        if args[0] == "for-each-ref" and listing_branches and not path.exists():
            _git("worktree", "add", str(path), "chore/old", cwd=repo)
        return real_git(args, cwd)

    ops = replace(_ops({}, now=time.time), git=sibling_checks_out)
    assert main(["judge"], cwd=repo, ops=ops) == 0
    assert path.exists()
    line = _branch_line(capsys.readouterr().out, "chore/old")
    assert line.startswith("브랜치를 지운다"), line
    assert main(["remove-branch", "chore/old", tip], cwd=repo, ops=_ops({}, now=time.time)) == 1
    assert _git("rev-parse", "HEAD", cwd=path) == tip


def test_judge_와_remove_branch_는_대소문자가_바뀌어_찍힌_막_딴_브랜치도_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """반박 시험(같은 값을 견주는 다른 자리). 윈도에서 `for-each-ref` 가 `chore/Upper` 로 찍은
    브랜치의 reflog 를 찍힌 이름으로 읽는다(git 2.32 에서 손으로 봤다)."""
    _git("branch", "chore/x", cwd=repo)
    _git("branch", "Chore/Upper", cwd=repo)
    listed = _git("for-each-ref", "refs/heads", "--format=%(refname:short)", cwd=repo)
    printed = next(name for name in listed.splitlines() if name.lower() == "chore/upper")
    tip = _git("rev-parse", f"refs/heads/{printed}", cwd=repo)
    now = _ops({}, now=time.time)
    assert main(["judge"], cwd=repo, ops=now) == 0
    assert _branch_line(capsys.readouterr().out, printed).startswith("브랜치를 남긴다")
    assert main(["remove-branch", printed, tip], cwd=repo, ops=now) == 1
    assert _git("rev-parse", f"refs/heads/{printed}", cwd=repo) == tip


def test_judge_는_실행_중인_세션의_제목인_체크아웃되지_않은_브랜치를_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 286. 병합된 PR 로 지울 브랜치와 PR 없이 origin/main 에 든 브랜치 모두 남기고
    `remove-branch` 를 찍지 않는다. 제목이 다른 세션만 돌면 그대로 지울 후보다."""
    _git("branch", "chore/loose", cwd=repo)
    _git("branch", "worktree-x", cwd=repo)
    _git("branch", "worktree-y", cwd=repo)
    tip = _git("rev-parse", "chore/loose", cwd=repo)
    argv = ["judge", "--running", "chore/loose", "--running", "worktree-x"]
    assert main(argv, cwd=repo, ops=_ops({"chore/loose": frozenset({tip})})) == 0
    lines = capsys.readouterr().out.splitlines()
    for name in ("chore/loose", "worktree-x"):
        line = next(line for line in lines if f" {name} " in line)
        assert line == f"브랜치를 남긴다 {name} — 제목이나 브랜치가 그 브랜치인 세션이 돈다", line
    other = next(line for line in lines if " worktree-y " in line)
    assert other.startswith("브랜치를 지운다"), other


def test_judge_는_대소문자가_바뀌어_찍힌_브랜치도_그_제목의_세션이_돌면_남긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """윈도에서 낱개 참조의 폴더(`refs/heads/chore/`)가 이미 있으면 `Chore/Upper` 가 그 폴더 아래에
    들어가 `for-each-ref` 가 `chore/Upper` 로 찍는다. 세션 제목은 친 그대로다. 대소문자를 가린
    판은 그 세션의 브랜치를 지울 후보로 냈다(대기열 286 의 반박 시험)."""
    _git("branch", "chore/x", cwd=repo)
    _git("branch", "Chore/Upper", cwd=repo)
    if sys.platform == "win32":
        listed = _git("for-each-ref", "refs/heads", "--format=%(refname:short)", cwd=repo)
        assert "chore/Upper" in listed.splitlines(), listed
    assert main(["judge", "--running", "Chore/Upper"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/Upper" in line)
    assert line.startswith("브랜치를 남긴다"), line


def test_judge_와_remove_branch_는_대소문자가_바뀌어_찍힌_체크아웃된_브랜치를_지우지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """윈도에서 `Chore/Upper` 워크트리의 등록은 친 그대로 찍히고 `for-each-ref` 는 `chore/Upper` 로
    찍는다. 글자 그대로 견준 판은 그 브랜치를 체크아웃되지 않은 것으로 보아 지울 후보로 냈고,
    `remove-branch` 가 지워 커밋하지 않은 파일이 든 워크트리의 HEAD 가 끊겼다(git 의 `branch -D` 도
    대소문자를 가려 막지 않았다. 대기열 286 셀프 리뷰 명세 축)."""
    _git("branch", "chore/x", cwd=repo)
    path = repo / ".claude" / "worktrees" / "up"
    _git("worktree", "add", "-b", "Chore/Upper", str(path), cwd=repo)
    (path / "work.txt").write_text("x", encoding="utf-8")
    tip = _git("rev-parse", "HEAD", cwd=path)
    if sys.platform == "win32":
        listed = _git("for-each-ref", "refs/heads", "--format=%(refname:short)", cwd=repo)
        assert "chore/Upper" in listed.splitlines(), listed
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    lines = capsys.readouterr().out.splitlines()
    assert not [line for line in lines if line.startswith("브랜치를") and "/Upper" in line], lines
    assert main(["remove-branch", "chore/Upper", tip], cwd=repo, ops=_ops({})) == 1
    assert _git("rev-parse", "HEAD", cwd=path) == tip


def test_judge_는_git_없는_prunable_폴더의_분리_HEAD_가_origin_main_에_없으면_넘긴다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PR 직전 버그 리뷰(Major). 지우다 만 폴더의 등록도 그 커밋의 마지막 참조일 수 있다."""
    path, _ = _add_detached(repo, "half")
    (path / "only.txt").write_text("x", encoding="utf-8")
    _git("add", "only.txt", cwd=path)
    _git(*_IDENTITY, "commit", "-q", "-m", "origin/main 에 없는 커밋", cwd=path)
    head = _git("rev-parse", "HEAD", cwd=path)
    (path / ".git").unlink()
    (path / "only.txt").unlink()
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if "/half" in line)
    assert line.startswith("넘긴다"), line
    assert "origin/main 에 없다" in line
    assert main(["remove", path.as_posix(), ".detached", head], cwd=repo, ops=_ops({})) == 1
    assert _registered(repo, path)
    assert _git("cat-file", "-t", head, cwd=repo) == "commit"


def test_휴지통_자리가_링크면_읽지도_옮기지도_지우지도_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PR 직전 보안 리뷰(Medium). 휴지통 자리를 다른 폴더로 가는 정션으로 바꿔 두면 `empty-trash` 가
    링크 너머의 내용을 지웠다(리뷰가 재현했다)."""
    victim = repo.parent / "victim"
    (victim / "docs").mkdir(parents=True)
    (victim / "docs" / "secret.txt").write_text("남아야 한다", encoding="utf-8")
    path, head = _add(repo, "done")
    _link(repo / ".claude" / "worktrees" / ".tidy-trash", victim)
    merged = {"chore/done": frozenset({head})}
    assert main(["judge"], cwd=repo, ops=_ops(merged)) == 0
    out = capsys.readouterr().out
    assert "휴지통 자리가 링크거나 폴더가 아니다" in out
    assert "secret" not in out and "docs" not in out.split("휴지통")[1]
    assert main(["empty-trash"], cwd=repo, ops=_ops(merged)) == 1
    assert "휴지통 자리가 링크" in capsys.readouterr().out
    assert main(["remove", path.as_posix(), "chore/done", head], cwd=repo, ops=_ops(merged)) == 1
    assert "휴지통 자리가 링크" in capsys.readouterr().out
    assert (path / ".venv").exists()
    assert _registered(repo, path)
    assert (victim / "docs" / "secret.txt").read_text(encoding="utf-8") == "남아야 한다"


def test_judge_는_휴지통을_등록_없는_폴더로_찍지_않고_남은_것을_알린다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    trash = repo / ".claude" / "worktrees" / ".tidy-trash"
    (trash / "old~~.venv").mkdir(parents=True)
    (trash / "old~~.venv" / "x.py").write_text("x", encoding="utf-8")
    assert main(["judge"], cwd=repo, ops=_ops({})) == 0
    out = capsys.readouterr().out
    assert "등록 없는 폴더" not in out
    assert "휴지통에 남았다" in out
    assert "empty-trash" in out
    assert main(["empty-trash"], cwd=repo, ops=_ops({})) == 0
    assert _trash(repo) == []
    assert main(["empty-trash"], cwd=repo, ops=_ops({})) == 0
    assert "비어 있다" in capsys.readouterr().out


# --- remove-stray(대기열 148) ---------------------------------------------------------------------


def test_remove_stray_는_내용이_모두_커밋에_있는_등록_없는_폴더를_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)
    assert main(["remove-stray", stray.as_posix()], cwd=repo, ops=_ops({})) == 0
    assert "지웠다" in capsys.readouterr().out
    assert not stray.exists()
    assert (repo / "README.md").exists()


def test_remove_stray_는_등록된_워크트리를_지우지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`.git` 재판정도 1을 내므로 이유 문구로 자리 가드가 막았는지 본다."""
    path, _ = _add(repo, "done")
    assert main(["remove-stray", path.as_posix()], cwd=repo, ops=_ops({})) == 1
    assert "등록 없는 폴더가 아니다" in capsys.readouterr().out
    assert (path / ".git").exists()
    assert _registered(repo, path)


@pytest.mark.parametrize(
    "relative",
    ["src", ".claude/worktrees/stray/deep", "../outside"],
    ids=["루트_안", "더_깊이", "루트_밖"],
)
def test_remove_stray_는_워크트리_자리_바로_아래가_아니면_지우지_않는다(
    repo: Path, relative: str
) -> None:
    target = (repo / relative).resolve()
    target.mkdir(parents=True, exist_ok=True)
    assert main(["remove-stray", target.as_posix()], cwd=repo, ops=_ops({})) == 1
    assert target.exists()


def test_remove_stray_는_git_이_있거나_커밋에_없는_파일이_있으면_지우지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """후보가 아니면 탐침(폴더 이름 바꾸기)도 하지 않는다. 지우기 직전의 재판정과 따로 잰다."""
    stray = _stray(repo)
    (stray / "new.py").write_text("x", encoding="utf-8")
    renamed: list[str] = []

    def spy(src: str, dst: str) -> None:
        renamed.append(dst)
        os.rename(src, dst)

    ops = replace(_ops({}), rename=spy)
    assert main(["remove-stray", stray.as_posix()], cwd=repo, ops=ops) == 1
    assert "지우기 전에 다시 판정했다: 등록 없는 폴더에 커밋에 없는 파일" in capsys.readouterr().out
    other = _stray(repo, "other")
    (other / ".git").write_text("gitdir: C:/nowhere\n", encoding="utf-8")
    assert main(["remove-stray", other.as_posix()], cwd=repo, ops=ops) == 1
    assert "지우기 전에 다시 판정했다: 등록 없는 폴더인데 .git 이 있다" in capsys.readouterr().out
    assert renamed == []
    assert (stray / "README.md").exists()
    assert (other / "README.md").exists()


def test_remove_stray_는_탐침_뒤에_생긴_파일이_있으면_멈춘다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)

    def rename_then_write(src: str, dst: str) -> None:
        os.rename(src, dst)
        if Path(dst).name == "stray":
            (stray / "late.py").write_text("늦게 생겼다", encoding="utf-8")

    ops = replace(_ops({}), rename=rename_then_write)
    assert main(["remove-stray", stray.as_posix()], cwd=repo, ops=ops) == 1
    assert "late.py" in capsys.readouterr().out
    assert (stray / "late.py").exists()
    assert (stray / ".venv" / "Lib" / "mod.py").exists()


def test_remove_stray_는_쥔_프로세스가_있으면_멈춘다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)

    def modules() -> list[tuple[int, str, str]]:
        return [(26016, "python.exe", str(stray / ".venv" / "Lib" / "mod.pyd"))]

    ops = replace(_ops({}), modules=modules)
    assert main(["remove-stray", stray.as_posix()], cwd=repo, ops=ops) == 1
    assert "python.exe(pid 26016)" in capsys.readouterr().out
    assert (stray / "README.md").exists()


def test_remove_stray_는_탐침이_막히면_손대지_않는다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)

    def held(_src: str, _dst: str) -> None:
        raise PermissionError(32, "다른 프로세스가 파일을 사용 중이기 때문에")

    ops = replace(_ops({}), rename=held)
    assert main(["remove-stray", stray.as_posix()], cwd=repo, ops=ops) == 1
    assert "다른 프로세스가 쥐고 있다" in capsys.readouterr().out
    assert (stray / "README.md").exists()


def test_remove_stray_는_휴지통으로_옮긴_뒤_지우다_막혀도_워크트리_자리에서는_치운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = _stray(repo)

    def blocked(_target: Path) -> None:
        raise PermissionError(5, "액세스가 거부되었습니다")

    ops = replace(_ops({}), delete=blocked)
    assert main(["remove-stray", stray.as_posix()], cwd=repo, ops=ops) == 0
    out = capsys.readouterr().out
    assert "휴지통에 남았다" in out
    assert not stray.exists()
    assert _trash(repo) == ["stray~~"]


def test_remove_는_옮기기가_막히면_등록과_git_을_남기고_1로_끝난다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """탐침의 이름 바꾸기는 지나고 휴지통으로 옮기는 이름 바꾸기가 둘째에서 막힌다. 먼저 옮긴 것은
    휴지통에서 지운다."""
    path, head = _add(repo, "done")
    moves: list[str] = []

    def rename(src: str, dst: str) -> None:
        if ".tidy-trash" in dst:
            moves.append(Path(src).name)
            if len(moves) == 2:
                raise PermissionError(5, "액세스가 거부되었습니다")
        os.rename(src, dst)

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=rename)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    out = capsys.readouterr().out
    assert "옮기다 막혔다" in out
    assert (path / ".git").exists()
    assert (path / moves[1]).exists()
    assert not (path / moves[0]).exists()
    assert _registered(repo, path)
    assert _git("branch", "--list", "chore/done", cwd=repo) != ""
    assert _trash(repo) == []


def test_remove_는_git_이_지우다_실패하면_브랜치를_남기고_3으로_멈춘다(repo: Path) -> None:
    path, head = _add(repo, "done")

    def failing(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if list(args[:2]) == ["worktree", "remove"]:
            return subprocess.CompletedProcess(list(args), 255, "", "error: failed to delete")
        return real_git(args, cwd)

    ops = replace(_ops({"chore/done": frozenset({head})}), git=failing)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 3
    assert _git("branch", "--list", "chore/done", cwd=repo) != ""


def test_remove_는_죽은_잠금을_풀고_지운다(repo: Path) -> None:
    path, head = _add(repo, "done")
    _git("worktree", "lock", "--reason", "claude session done (pid 999999)", str(path), cwd=repo)
    merged = {"chore/done": frozenset({head})}
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=_ops(merged)) == 0
    assert not path.exists()


def test_remove_는_탐침이_막히면_죽은_잠금도_풀지_않는다(repo: Path) -> None:
    path, head = _add(repo, "done")
    _git("worktree", "lock", "--reason", "claude session done (pid 999999)", str(path), cwd=repo)

    def held(_src: str, _dst: str) -> None:
        raise PermissionError(13, "액세스가 거부되었습니다")

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=held)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    listing = parse_worktrees(_git("worktree", "list", "--porcelain", cwd=repo) + "\n")
    done = next(w for w in listing if w.branch == "chore/done")
    assert done.locked == "claude session done (pid 999999)"


def test_remove_는_옮기기_직전에_멈추면_죽은_잠금도_풀지_않는다(repo: Path) -> None:
    """PR #163 claude-review: 잠금을 푼 뒤에 재판정이 멈추면 '바꾼 것 없음'이 거짓이 된다."""
    path, head = _add(repo, "done")
    _git("worktree", "lock", "--reason", "claude session done (pid 999999)", str(path), cwd=repo)

    def rename_then_write(src: str, dst: str) -> None:
        os.rename(src, dst)
        if Path(dst).name == "done":
            (path / ".env").write_text("SECRET=x\n", encoding="utf-8")

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=rename_then_write)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    listing = parse_worktrees(_git("worktree", "list", "--porcelain", cwd=repo) + "\n")
    done = next(w for w in listing if w.branch == "chore/done")
    assert done.locked == "claude session done (pid 999999)"


def test_remove_는_판정_뒤에_생긴_무시된_파일을_지우지_않고_멈춘다(repo: Path) -> None:
    """판정과 옮기기 사이(탐침 동안)에 `.env` 가 생긴 경우다."""
    path, head = _add(repo, "done")

    def rename_then_write(src: str, dst: str) -> None:
        os.rename(src, dst)
        if Path(dst).name == "done":
            (path / ".env").write_text("SECRET=x\n", encoding="utf-8")

    ops = replace(_ops({"chore/done": frozenset({head})}), rename=rename_then_write)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    assert (path / ".env").exists()
    assert (path / ".venv" / "Lib" / "mod.py").exists()
    assert _registered(repo, path)


def test_remove_는_브랜치를_지우지_못하면_워크트리만_지우고_1로_끝난다(repo: Path) -> None:
    path, head = _add(repo, "done")

    def failing(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if list(args[:1]) == ["branch"]:
            return subprocess.CompletedProcess(list(args), 1, "", "error: branch is locked")
        return real_git(args, cwd)

    ops = replace(_ops({"chore/done": frozenset({head})}), git=failing)
    assert main(["remove", str(path), "chore/done", head], cwd=repo, ops=ops) == 1
    assert not path.exists()
    assert _git("branch", "--list", "chore/done", cwd=repo) != ""


def test_remove_branch_는_다시_보고_지운다(repo: Path) -> None:
    """브랜치에 origin/main 에 없는 커밋을 둬, 병합된 PR 만으로 지우는 길을 잰다."""
    _git("switch", "-q", "-c", "chore/loose", cwd=repo)
    (repo / "loose.txt").write_text("x", encoding="utf-8")
    _git("add", "loose.txt", cwd=repo)
    _git(*_IDENTITY, "commit", "-q", "-m", "origin/main 에 없는 커밋", cwd=repo)
    _git("switch", "-q", "main", cwd=repo)
    tip = _git("rev-parse", "chore/loose", cwd=repo)
    merged = {"chore/loose": frozenset({tip})}
    # 옛 머리도 병합된 PR 에 있어야 재확인이 판정 1과 따로 잰다
    both = {"chore/loose": frozenset({tip, _OLD})}
    assert main(["remove-branch", "chore/loose", _OLD], cwd=repo, ops=_ops(both)) == 1
    assert main(["remove-branch", "chore/loose", tip], cwd=repo, ops=_ops({})) == 1
    assert main(["remove-branch", "chore/loose", tip], cwd=repo, ops=_ops(merged)) == 0
    assert _git("branch", "--list", "chore/loose", cwd=repo) == ""


def test_remove_branch_는_체크아웃된_브랜치를_지우지_않는다(repo: Path) -> None:
    _, head = _add(repo, "done")
    merged = {"chore/done": frozenset({head})}
    assert main(["remove-branch", "chore/done", head], cwd=repo, ops=_ops(merged)) == 1


def test_remove_branch_는_judge_가_세션으로_남긴_브랜치도_지운다(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """못 보는 것. `judge` 뒤에 그 브랜치가 제목인 세션이 열려도 `remove-branch` 의 재판정은 세션을
    보지 않고(제목을 받지 않는다), 워크트리의 `remove` 처럼 대신 잡는 쥔 프로세스도 없어 지운다."""
    _git("branch", "chore/late", cwd=repo)
    tip = _git("rev-parse", "chore/late", cwd=repo)
    assert main(["judge", "--running", "chore/late"], cwd=repo, ops=_ops({})) == 0
    kept = next(line for line in capsys.readouterr().out.splitlines() if " chore/late " in line)
    assert kept.startswith("브랜치를 남긴다"), kept
    assert main(["remove-branch", "chore/late", tip], cwd=repo, ops=_ops({})) == 0
    assert _git("branch", "--list", "chore/late", cwd=repo) == ""


def test_CLI_를_하위_프로세스로_부르면_인자_오류에_2로_끝난다() -> None:
    result = subprocess.run(
        [sys.executable, str(_TOOL), "remove"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_help_는_git_밖에서도_모듈_독스트링을_줄바꿈_그대로_찍는다(tmp_path: Path) -> None:
    # 스킬 3은 독스트링을 파일 Read 가 아니라 이 출력으로 본다(대기열 271)
    doc = tidy_checkouts.__doc__
    assert doc is not None
    result = subprocess.run(
        [sys.executable, str(_TOOL), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert doc.strip() in result.stdout
