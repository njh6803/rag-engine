"""tools/hook_git_main_commit.py 의 순수 함수와 저장소 읽기. main 은 실제 실행으로 확인한다."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import tools.hook_git_main_commit as hook
from tools.hook_git_main_commit import (
    commits_in,
    current_branch,
    deny_reason,
    head_has_commit,
    reason_at,
)
from tools.run_hooks import registered_hooks

# 작성자 설정이 없는 환경에서도 커밋을 만든다(선례 tools/run_hooks.py 의 `_IDENTITY`).
_작성자 = ["-c", "user.name=test", "-c", "user.email=test@localhost"]


def test_명령_위치의_git_commit_을_잡는다() -> None:
    assert commits_in("git add -A && git commit -m 'feat: x'")
    assert commits_in("git commit -F .git/MSG")
    assert commits_in("cd sub; git -C . commit --amend --no-edit")
    assert commits_in('[ "$(git branch --show-current)" = main ] && git commit -m x')


def test_커밋이_아닌_git_명령은_잡지_않는다() -> None:
    assert not commits_in("git log --oneline -5")
    assert not commits_in("git status --short && git diff")
    assert not commits_in("gh pr merge 12 --squash")


def test_데이터로_든_문구는_잡지_않는다() -> None:
    """echo·heredoc·커밋 메시지 안의 `git commit` 은 실행이 아니다(hook_pr_next_session 과 같다)."""
    assert not commits_in("echo 'git commit 은 나중에'")
    assert not commits_in("cat <<'EOF' > note.md\ngit commit -m x\nEOF")
    assert not commits_in('git commit-tree HEAD^{tree} -m "x"')


def test_인용된_옵션_값_뒤의_commit_도_잡는다() -> None:
    """PR #91 리뷰: 인용을 지우면 commit 이 -c 의 값 자리로 밀린다."""
    assert commits_in('git -c "user.name=작성자" commit -m x')


def test_보호_브랜치에서만_막는_이유를_낸다() -> None:
    reason = deny_reason("main")

    assert reason is not None
    assert "main" in reason
    assert deny_reason("feature/01-x") is None
    assert deny_reason(None) is None
    assert deny_reason("chore/x") is None


def test_커밋_명령이_아니면_git_을_띄우지_않는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """훅은 Bash 호출마다 돈다. 커밋이 아닌 명령에서는 브랜치도 커밋의 유무도 읽지 않는다. 커밋
    명령은 같은 가짜로 둘 다 읽고 막는다 — 가짜가 실제로 불리는 자리라는 대조다."""
    읽은_것: list[str] = []

    def 브랜치를_기록한다(cwd: str | None) -> str:
        읽은_것.append("브랜치")
        return "main"

    def 커밋을_기록한다(cwd: str | None) -> bool:
        읽은_것.append("커밋")
        return True

    monkeypatch.setattr(hook, "current_branch", 브랜치를_기록한다)
    monkeypatch.setattr(hook, "head_has_commit", 커밋을_기록한다)

    assert reason_at("git log --oneline -5", None) is None
    assert 읽은_것 == []
    assert reason_at("git commit -m x", None) is not None
    assert 읽은_것 == ["브랜치", "커밋"]


def _저장소를_만든다(path: Path, 브랜치: str) -> None:
    subprocess.run(["git", "init", "-q", "-b", 브랜치, str(path)], check=True)


def _빈_커밋을_만든다(path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(path), *_작성자, "commit", "-q", "--allow-empty", "-m", "x"], check=True
    )


def test_현재_브랜치를_읽는다(tmp_path: Path) -> None:
    _저장소를_만든다(tmp_path / "on-main", "main")
    _저장소를_만든다(tmp_path / "on-topic", "chore/x")

    assert current_branch(str(tmp_path / "on-main")) == "main"
    assert current_branch(str(tmp_path / "on-topic")) == "chore/x"


def test_환경의_GIT_DIR_을_무시한다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """pre-commit 이 워크트리에서 훅을 돌릴 때 git 이 내보내는 값이다. 읽을 것은 cwd 의 저장소다."""
    _저장소를_만든다(tmp_path / "on-main", "main")
    _저장소를_만든다(tmp_path / "on-topic", "chore/x")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "on-main" / ".git"))

    assert current_branch(str(tmp_path / "on-topic")) == "chore/x"


def test_커밋이_없는_저장소의_main_에서는_첫_커밋을_막지_않는다(tmp_path: Path) -> None:
    """킥오프가 main 위에 하는 새 프로젝트의 첫 커밋이다(`KICKOFF.md` 8단계, ADR 0028)."""
    _저장소를_만든다(tmp_path / "new", "main")

    assert reason_at("git add -A && git commit -m x", str(tmp_path / "new")) is None


def test_커밋이_하나_있는_저장소의_main_에서는_막는다(tmp_path: Path) -> None:
    repo = tmp_path / "used"
    _저장소를_만든다(repo, "main")
    _빈_커밋을_만든다(repo)

    reason = reason_at("git commit -m x", str(repo))

    assert reason is not None
    assert "`main`" in reason
    assert "커밋이 있는 저장소" in reason


def test_다른_브랜치에_커밋이_있어도_main_이_아직_커밋을_가리키지_않으면_막지_않는다(
    tmp_path: Path,
) -> None:
    """못 보는 것. 커밋의 유무를 저장소가 아니라 `HEAD` 로 잰다."""
    repo = tmp_path / "orphan"
    _저장소를_만든다(repo, "chore/x")
    _빈_커밋을_만든다(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "--orphan", "main"], check=True)

    assert current_branch(str(repo)) == "main"
    assert reason_at("git commit -m x", str(repo)) is None


def test_커밋의_유무를_읽을_때도_환경의_GIT_DIR_을_무시한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """커밋이 있는 저장소를 가리키는 `GIT_DIR` 이 남아 있어도 읽을 것은 cwd 의 저장소다."""
    _저장소를_만든다(tmp_path / "used", "main")
    _빈_커밋을_만든다(tmp_path / "used")
    _저장소를_만든다(tmp_path / "new", "main")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "used" / ".git"))

    assert reason_at("git commit -m x", str(tmp_path / "new")) is None


def test_작업_브랜치에서는_커밋의_유무를_읽지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """훅은 Bash 호출마다 돈다. 작업 브랜치의 커밋마다 git 을 한 번 더 띄우지 않는다."""
    읽은_자리: list[str | None] = []

    def 기록한다(cwd: str | None) -> bool:
        읽은_자리.append(cwd)
        return True

    _저장소를_만든다(tmp_path / "on-topic", "chore/x")
    monkeypatch.setattr(hook, "head_has_commit", 기록한다)

    assert reason_at("git commit -m x", str(tmp_path / "on-topic")) is None
    assert 읽은_자리 == []


def test_git_을_띄우지_못하면_HEAD_에_커밋이_없다고_본다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """게이트가 아니라 안전장치다. 커밋이 없다고 보아 막지 않는 쪽으로 간다. git 이 있었다면 참이
    나올 저장소를 읽는다."""
    repo = tmp_path / "used"
    _저장소를_만든다(repo, "main")
    _빈_커밋을_만든다(repo)
    (tmp_path / "빈-PATH").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "빈-PATH"))

    assert not head_has_commit(str(repo))


def test_저장소가_아니면_None이다(tmp_path: Path) -> None:
    """게이트가 아니라 안전장치다. 저장소 밖에서는 막지 않는다."""
    (tmp_path / "plain").mkdir()

    assert current_branch(str(tmp_path / "plain")) is None


def test_git_이_시간을_넘기면_띄우지_못한_것처럼_막지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """두 호출의 제한을 더해도 등록의 20초 안이다. 넘기면 등록의 시간 제한(fail-open)과 같은
    쪽으로 끝나되 더 일찍 끝난다(대기열 342)."""
    seen: list[object] = []

    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, hook.CALL_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", stuck)

    assert current_branch(str(tmp_path)) is None
    assert not head_has_commit(str(tmp_path))
    assert reason_at("git commit -m x", str(tmp_path)) is None
    assert seen == [hook.CALL_TIMEOUT] * 3


def test_main_위에서_커밋의_유무를_읽다가_시간을_넘겨도_막지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """막는 갈래의 둘째 git 만 넘긴 때다. 커밋의 유무를 읽지 못하면 커밋이 없다고 본다(독스트링의
    fail-open)."""

    def main_then_stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[1:] == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(args, 0, "main\n", "")
        raise subprocess.TimeoutExpired(args, hook.CALL_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", main_then_stuck)

    assert reason_at("git commit -m x", str(tmp_path)) is None


def test_한_번의_판정이_부르는_git_의_시간_제한을_더해도_등록의_시간_제한_안이다() -> None:
    """`reason_at` 은 git 을 많아야 둘(브랜치, 커밋의 유무) 부른다. 등록의 시간 제한을 넘기면
    훅이 끊겨 같은 fail-open 이지만, 훅 스스로 끝내야 그 뒤의 판정 없이 일찍 끝난다."""
    assert hook.CALL_TIMEOUT * 2 < registered_hooks()["hook_git_main_commit.py"].timeout
