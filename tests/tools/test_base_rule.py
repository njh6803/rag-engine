"""`tools/base_rule.py` 와 같은 규칙을 따로 구현한 두 곳을 묶는 시험.

기준 브랜치 규칙(ADR 0016, agent-os 의 ADR 0043 을 따른다)은 세 곳에 있다.
이 모듈, 단독 실행 훅 `tools/hook_push_behind_main.py`, CI 가 표준 라이브러리만으로 돌리는
`tools/check_ticket.py` 다. 같은 저장소 상태와 브랜치에서 셋이 같은 기준을 내야 한다. 규칙에 갈래가
더해지면(예: `release/*`) 그 접두의 이름을 든 `BRANCHES` 가 있어야 하나만 고친 변경이 여기서
빨개진다. `release/x` 는 이미 든다.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from tools.hook_push_behind_main import base_branch

from tools import base_rule, check_ticket

ROOT = Path(__file__).resolve().parents[2]
_IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")

BRANCHES = [
    "hotfix/x",
    "feature/01-x",
    "chore/x",
    "docs/x",
    "claude/x",
    "worktree-x",
    "hotfixes/x",
    "Hotfix/x",
    "release/x",
]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *_IDENTITY, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=60,
    )


def _repository(tmp_path: Path, *, with_dev: bool) -> Path:
    repo = tmp_path / "repo"
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "씨앗")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    if with_dev:
        _git(repo, "update-ref", "refs/remotes/origin/dev", "HEAD")
    return repo


@pytest.mark.parametrize("dev_exists", [True, False])
@pytest.mark.parametrize(
    ("branch", "main_based"),
    [
        ("hotfix/x", True),
        ("feature/01-x", False),
        ("chore/x", False),
        ("docs/x", False),
        ("claude/x", False),
        (None, False),
    ],
)
def test_순수_판정은_접두와_dev_추적_ref로_가른다(
    branch: str | None, *, main_based: bool, dev_exists: bool
) -> None:
    expected = "main" if main_based or not dev_exists else "dev"
    assert base_rule.base_name(branch, dev_exists=dev_exists) == expected


@pytest.mark.parametrize("with_dev", [True, False])
@pytest.mark.parametrize("branch", BRANCHES)
def test_세_구현은_같은_저장소와_브랜치에서_같은_기준을_낸다(
    tmp_path: Path, branch: str, *, with_dev: bool
) -> None:
    repo = _repository(tmp_path, with_dev=with_dev)
    by_module = base_rule.base_for(repo, branch)
    by_hook = base_branch(str(repo), branch)
    by_check = check_ticket.base_ref(repo, branch)
    assert by_hook == by_module, f"훅의 기준 {by_hook}, 모듈의 기준 {by_module}"
    assert by_check == f"refs/remotes/origin/{by_module}", f"검사의 기준 {by_check}"
    assert base_rule.base_ref(repo, branch) == f"origin/{by_module}"


def test_dev가_있으면_hotfix가_아닌_브랜치는_dev를_기준으로_한다(tmp_path: Path) -> None:
    repo = _repository(tmp_path, with_dev=True)
    assert base_rule.base_for(repo, "feature/01-x") == "dev"
    assert base_rule.base_for(repo, "hotfix/x") == "main"


def test_dev가_없으면_모두_main을_기준으로_한다(tmp_path: Path) -> None:
    repo = _repository(tmp_path, with_dev=False)
    assert {base_rule.base_for(repo, branch) for branch in BRANCHES} == {"main"}


def test_저장소가_아니면_dev가_없다고_읽고_main을_낸다(tmp_path: Path) -> None:
    # 못 보는 것: git 이 실패하면 dev 가 없다고 읽는다
    assert base_rule.base_for(tmp_path, "feature/01-x") == "main"
    assert base_rule.current_branch(tmp_path) is None


def test_현재_브랜치를_읽는다(tmp_path: Path) -> None:
    repo = _repository(tmp_path, with_dev=False)
    assert base_rule.current_branch(repo) == "main"
    _git(repo, "switch", "-q", "--detach")
    assert base_rule.current_branch(repo) is None


def test_이_저장소의_기준_규칙은_세_파일에만_있다() -> None:
    """hotfix 접두로 기준을 가르는 코드가 더 있으면 묶는 시험이 닿지 않는 네 번째 구현이다."""
    pattern = re.compile(r'["\']hotfix/["\']')
    found = sorted(
        path.name
        for path in (ROOT / "tools").glob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    )
    assert found == ["base_rule.py", "check_ticket.py", "hook_push_behind_main.py"], found
