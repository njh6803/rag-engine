"""보고서의 `meta.commit`을 읽는 `current_commit`(티켓 search-eval 04).

저장소의 HEAD 커밋이면 그 40자리 해시이고, 저장소가 아니거나 커밋이 없으면 `None`이다. 보고서는
`None`이어도 쓴다.
"""

import subprocess
from pathlib import Path

import pytest

from rag_engine.adapters.eval_run import current_commit

GIT_IDENTITY = ["-c", "user.name=시험", "-c", "user.email=test@example.invalid"]


def _git(folder: Path, *arguments: str) -> str:
    done = subprocess.run(
        ["git", *GIT_IDENTITY, *arguments],
        cwd=folder,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return done.stdout.strip()


def test_저장소의_머리_커밋을_낸다(tmp_path: Path) -> None:
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "commit", "--quiet", "--allow-empty", "-m", "시험")

    commit = current_commit(tmp_path)

    assert commit == _git(tmp_path, "rev-parse", "HEAD")
    assert commit is not None
    assert len(commit) == 40


def test_다른_저장소를_가리키는_GIT_DIR이_있어도_그_폴더의_커밋을_낸다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`git -C`를 줘도 `GIT_DIR`이 있으면 git이 그 저장소를 읽는다. 훅이나 다른 도구의 환경이
    남은 셸에서 부르면 보고서의 `meta.commit`에 다른 저장소의 커밋이 적힌다."""
    repository = tmp_path / "repository"
    elsewhere = tmp_path / "elsewhere"
    for folder in (repository, elsewhere):
        folder.mkdir()
        _git(folder, "init", "--quiet")
        _git(folder, "commit", "--quiet", "--allow-empty", "-m", folder.name)
    expected = _git(repository, "rev-parse", "HEAD")
    assert expected != _git(elsewhere, "rev-parse", "HEAD")
    monkeypatch.setenv("GIT_DIR", str(elsewhere / ".git"))

    assert current_commit(repository) == expected


def test_저장소가_아니면_없다고_낸다(tmp_path: Path) -> None:
    assert current_commit(tmp_path) is None


def test_커밋이_없는_저장소도_없다고_낸다(tmp_path: Path) -> None:
    _git(tmp_path, "init", "--quiet")

    assert current_commit(tmp_path) is None
