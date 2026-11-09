"""tools/hook_pr_head_sync.py 의 순수 함수와 git 읽기. main 은 실제 실행으로 확인한다(페이로드 표).

`gh pr view` 를 부르는 길은 네트워크라 여기서 돌리지 않는다. 그 명령의 모양과 출력 읽기만 잰다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from tools.hook_pr_head_sync import (
    LocalState,
    PrHead,
    Request,
    has_commit,
    is_ancestor,
    judge_pr,
    local_state,
    parse_pr_view,
    pr_view_args,
    request_in,
    stale_reason,
    unpushed_reason,
)

_HEAD = "b" * 40
_OLD = "a" * 40


def test_gh_pr_ready_를_잡는다() -> None:
    assert request_in("gh pr ready") == Request("ready", None, None)
    assert request_in("gh pr ready 117") == Request("ready", "117", None)
    assert request_in("git push && gh pr ready 117") == Request("ready", "117", None)
    assert request_in("gh pr ready https://github.com/o/r/pull/5") == Request(
        "ready", "https://github.com/o/r/pull/5", None
    )


def test_draft_로_되돌리는_ready_는_잡지_않는다() -> None:
    assert request_in("gh pr ready 117 --undo") is None


def test_coderabbit_요청_코멘트를_잡는다() -> None:
    assert request_in('gh pr comment 117 --body "@coderabbitai review"') == Request(
        "coderabbit", "117", None
    )
    assert request_in("gh pr comment -b '@coderabbitai full review'") == Request(
        "coderabbit", None, None
    )
    heredoc = "gh pr comment 117 --body-file - <<'EOF'\n@coderabbitai review\nEOF"
    assert request_in(heredoc) == Request("coderabbit", "117", None)


def test_리다이렉션은_선택자가_아니다() -> None:
    assert request_in("gh pr ready 117 2>&1") == Request("ready", "117", None)
    assert request_in("gh pr ready > out.txt") == Request("ready", None, None)
    heredoc = "gh pr comment --body-file - << EOF\n@coderabbitai review\nEOF"
    assert request_in(heredoc) == Request("coderabbit", None, None)
    quoted_heredoc = "gh pr comment -F - <<'EOF'\n@coderabbitai review\nEOF"
    assert request_in(quoted_heredoc) == Request("coderabbit", None, None)


def test_coderabbit_을_부르지_않는_코멘트는_잡지_않는다() -> None:
    assert request_in('gh pr comment 117 --body "반영했다. 다시 봐 달라"') is None


def test_저장소_옵션은_넘기고_인용된_값은_판정하지_않는다() -> None:
    assert request_in("gh pr ready 117 -R njh6803/agent-os") == Request(
        "ready", "117", "njh6803/agent-os"
    )
    assert request_in("gh pr ready 117 --repo=njh6803/agent-os") == Request(
        "ready", "117", "njh6803/agent-os"
    )
    assert request_in('gh pr ready "$PR"') is None
    assert request_in('gh pr ready 117 --repo "$REPO"') is None


def test_데이터로_든_문구와_다른_gh_명령은_잡지_않는다() -> None:
    assert request_in("echo 'gh pr ready 117'") is None
    assert request_in("git commit -m 'gh pr ready 뒤에 리뷰'") is None
    assert request_in("gh pr view 117 --json headRefOid") is None
    assert request_in("gh pr checks 117") is None


def _로컬(upstream: str | None) -> LocalState:
    return LocalState("chore/x", _HEAD, upstream)


def test_선택자_없는_요청은_푸시하지_않은_커밋을_막는다() -> None:
    reason = unpushed_reason(Request("ready", None, None), _로컬(_OLD), head_behind_upstream=False)

    assert reason is not None
    assert _HEAD[:7] in reason
    assert _OLD[:7] in reason
    assert "푸시" in reason


def test_upstream_과_같거나_뒤처졌거나_없으면_로컬_판정은_지나간다() -> None:
    bare = Request("ready", None, None)

    assert unpushed_reason(bare, _로컬(_HEAD), head_behind_upstream=False) is None
    assert unpushed_reason(bare, _로컬(_OLD), head_behind_upstream=True) is None
    assert unpushed_reason(bare, _로컬(None), head_behind_upstream=False) is None


def test_선택자가_있으면_로컬_판정을_하지_않는다() -> None:
    """다른 브랜치의 PR 일 수 있다. 그 PR 의 브랜치는 gh 가 알려 준다."""
    named = Request("ready", "119", None)

    assert unpushed_reason(named, _로컬(_OLD), head_behind_upstream=False) is None


def test_PR_head_가_로컬_HEAD_에_못_미치면_막는다() -> None:
    reason = stale_reason(
        Request("ready", "117", None), _로컬(_HEAD), PrHead(_OLD, "chore/x"), pr_ahead=False
    )

    assert reason is not None
    assert _OLD[:7] in reason
    assert _HEAD[:7] in reason
    assert "claude-review" in reason


def test_coderabbit_요청의_이유는_버려지는_요청을_말한다() -> None:
    reason = stale_reason(
        Request("coderabbit", "117", None), _로컬(_HEAD), PrHead(_OLD, "chore/x"), pr_ahead=False
    )

    assert reason is not None
    assert "Head commit changed" in reason


def test_같거나_앞섰거나_다른_브랜치의_PR_이면_지나간다() -> None:
    ready = Request("ready", "117", None)

    assert stale_reason(ready, _로컬(_HEAD), PrHead(_HEAD, "chore/x"), pr_ahead=False) is None
    assert stale_reason(ready, _로컬(_HEAD), PrHead(_OLD, "chore/x"), pr_ahead=True) is None
    assert stale_reason(ready, _로컬(_HEAD), PrHead(_OLD, "chore/y"), pr_ahead=False) is None


def test_대소문자가_다른_언급도_잡는다() -> None:
    assert request_in('gh pr comment 117 --body "@CodeRabbitAI review"') == Request(
        "coderabbit", "117", None
    )


def test_gh_pr_view_인자는_선택자와_저장소를_넘긴다() -> None:
    assert pr_view_args(Request("ready", None, None)) == [
        "pr",
        "view",
        "--json",
        "headRefOid,headRefName",
    ]
    assert pr_view_args(Request("coderabbit", "117", "o/r")) == [
        "pr",
        "view",
        "117",
        "--repo",
        "o/r",
        "--json",
        "headRefOid,headRefName",
    ]


def test_gh_pr_view_출력을_읽는다() -> None:
    assert parse_pr_view(f'{{"headRefOid": "{_OLD}", "headRefName": "chore/x"}}') == PrHead(
        _OLD, "chore/x"
    )
    assert parse_pr_view("no pull requests found") is None
    assert parse_pr_view('{"headRefOid": 1, "headRefName": "chore/x"}') is None
    assert parse_pr_view("[]") is None


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _푸시한_저장소(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "chore/x", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "chore/x", str(work)], check=True)
    _git(work, "commit", "-q", "--allow-empty", "-m", "a")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "chore/x")
    return work


def test_브랜치_HEAD_upstream_을_읽는다(tmp_path: Path) -> None:
    work = _푸시한_저장소(tmp_path)
    pushed = _git(work, "rev-parse", "HEAD")
    _git(work, "commit", "-q", "--allow-empty", "-m", "b")
    head = _git(work, "rev-parse", "HEAD")

    assert local_state(str(work)) == LocalState("chore/x", head, pushed)


def test_upstream_이_없으면_None_으로_읽는다(tmp_path: Path) -> None:
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "chore/x", str(work)], check=True)
    _git(work, "commit", "-q", "--allow-empty", "-m", "a")

    assert local_state(str(work)) == LocalState("chore/x", _git(work, "rev-parse", "HEAD"), None)


def test_다른_이름의_브랜치를_추적하면_upstream_을_읽지_않는다(tmp_path: Path) -> None:
    """`git checkout -b x origin/main` 처럼 base 를 추적하는 작업 브랜치(PR #120 claude-review).

    그 upstream 은 PR head 가 아니라서, 로컬 판정이 그것으로 재면 푸시한 뒤에도 영원히 막는다.
    """
    work = _푸시한_저장소(tmp_path)
    _git(work, "checkout", "-q", "-b", "topic", "--track", "origin/chore/x")
    _git(work, "commit", "-q", "--allow-empty", "-m", "b")

    state = local_state(str(work))

    assert state is not None
    assert state.branch == "topic"
    assert state.upstream is None


def test_커밋이_없거나_저장소가_아니면_None이다(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", "-b", "chore/x", str(empty)], check=True)
    plain = tmp_path / "plain"
    plain.mkdir()

    assert local_state(str(empty)) is None
    assert local_state(str(plain)) is None


def test_환경의_GIT_DIR_을_무시한다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = _푸시한_저장소(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "init", "-q", "-b", "main", str(other)], check=True)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))

    state = local_state(str(work))

    assert state is not None
    assert state.branch == "chore/x"


def test_조상인지_본다(tmp_path: Path) -> None:
    work = _푸시한_저장소(tmp_path)
    older = _git(work, "rev-parse", "HEAD")
    _git(work, "commit", "-q", "--allow-empty", "-m", "b")
    newer = _git(work, "rev-parse", "HEAD")

    assert is_ancestor(str(work), older, newer)
    assert not is_ancestor(str(work), newer, older)
    assert not is_ancestor(str(work), newer, "c" * 40)


def test_로컬에_있는_커밋인지_본다(tmp_path: Path) -> None:
    work = _푸시한_저장소(tmp_path)

    assert has_commit(str(work), _git(work, "rev-parse", "HEAD"))
    assert not has_commit(str(work), "c" * 40)


def test_gh_가_읽은_PR_head_를_로컬과_견준다(tmp_path: Path) -> None:
    """뒤처진 옛 head 는 막고, 앞선 head 와 로컬에 없는 head 는 지나간다.

    로컬에 없는 head 는 대개 다른 곳이 푸시한 앞선 head 다. 첫 판은 이것을 막았고, 셀프 리뷰가
    재현했다 — 기다려도 같아지지 않고 푸시는 non-ff 라 거부 이유가 안내한 길로 풀리지 않았다.
    """
    work = _푸시한_저장소(tmp_path)
    older = _git(work, "rev-parse", "HEAD")
    _git(work, "commit", "-q", "--allow-empty", "-m", "b")
    head = _git(work, "rev-parse", "HEAD")
    _git(work, "commit", "-q", "--allow-empty", "-m", "c")
    ahead = _git(work, "rev-parse", "HEAD")
    _git(work, "reset", "-q", "--hard", head)
    local = LocalState("chore/x", head, older)
    ready = Request("ready", "117", None)

    assert judge_pr(str(work), ready, local, PrHead(older, "chore/x")) is not None
    assert judge_pr(str(work), ready, local, PrHead(ahead, "chore/x")) is None
    assert judge_pr(str(work), ready, local, PrHead("c" * 40, "chore/x")) is None
    assert judge_pr(str(work), ready, local, PrHead(head, "chore/x")) is None
    assert judge_pr(str(work), ready, local, PrHead(older, "chore/y")) is None
