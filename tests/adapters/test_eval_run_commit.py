"""보고서의 `meta.commit`을 읽는 `current_commit`(티켓 search-eval 04).

저장소의 HEAD 커밋이면 그 40자리 해시이고, 저장소가 아니거나 커밋이 없으면 `None`이다. 보고서는
`None`이어도 쓴다.
"""

import subprocess
from pathlib import Path

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


def test_저장소가_아니면_없다고_낸다(tmp_path: Path) -> None:
    assert current_commit(tmp_path) is None


def test_커밋이_없는_저장소도_없다고_낸다(tmp_path: Path) -> None:
    _git(tmp_path, "init", "--quiet")

    assert current_commit(tmp_path) is None
