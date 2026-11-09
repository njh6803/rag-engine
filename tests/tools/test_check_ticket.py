"""`tools/check_ticket.py` 를 임시 저장소의 진짜 `git commit` 으로 잰다.

임시 저장소(맨 원격 하나와 그 main)를 만들고, pre-commit 자리에 이 검사를 부르는 짧은 심을 두어
막힘과 지남, 막을 때의 글을 본다. 진짜 pre-commit 을 거쳐야 보이는 둘(스테이지하지 않은 고침을
치우는 것, 일부 파일만 커밋할 때의 임시 색인이 러너를 거쳐 검사에 닿는 것)은 임시 저장소에
pre-commit 을 깔고 러너의 `run` 으로 이 검사 하나를 부르는 설정으로 본다(명세
`.scratch/ticket-for-every-pr/spec.md` "이음매").
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from tools.run_hooks import REPO_LOCATION_VARS

from tools import check_ticket

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "check_ticket.py"
_IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")
_TIMEOUT = 120

NUMBER_COMMAND = "uv run python tools/sibling_overlap.py"
SLUG_RULE = "번호 없이"
BRANCH_COMMAND = "git branch -m"
CONVENTION = "docs/agents/issue-tracker.md"
NOTICE = "in-progress"

READY = "# 02: 일\n\n**Status:** ready-for-agent\n"
SEED = {
    "README.md": "읽어 보기\n",
    "tools/a.py": "A = 1\n",
    "docs/journal/2026-01-01-01-seed.md": "씨앗\n",
    ".scratch/feat/issues/02-thing.md": READY,
    ".scratch/harness/issues/001-old.md": "# 001: 옛 일\n\n**Status:** done\n",
}
# 브랜치를 딴 자리의 트리에 이 파일이 있으면 규약 뒤의 브랜치다. 내용은 보지 않는다
CHECK_MARK = {"tools/check_ticket.py": "# 검사 자리\n"}


@dataclass
class Repo:
    tmp: Path
    work: Path
    pusher: Path | None
    env: dict[str, str]

    def git(self, *args: str, cwd: Path | None = None, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *_IDENTITY, *args],
            cwd=cwd or self.work,
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
            check=False,
        )
        if check and result.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {result.stdout}{result.stderr}")
        return result.stdout.strip()

    def write(self, files: dict[str, str], cwd: Path | None = None) -> None:
        for name, text in files.items():
            path = (cwd or self.work) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")

    def commit(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        """진짜 커밋. 훅이 막으면 0이 아닌 코드로 돌아온다."""
        return subprocess.run(
            ["git", *_IDENTITY, "commit", "-q", *args],
            cwd=cwd or self.work,
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
            check=False,
        )

    def stage_commit(
        self, files: dict[str, str], cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.write(files, cwd)
        self.git("add", "-A", cwd=cwd)
        return self.commit("-m", "x", cwd=cwd)

    def push_main(self, files: dict[str, str]) -> None:
        """원격의 main 에 커밋 하나를 더하고 작업 클론이 가져온다."""
        assert self.pusher is not None
        self.write(files, self.pusher)
        self.git("add", "-A", cwd=self.pusher)
        self.git("commit", "-q", "-m", "main", cwd=self.pusher)
        self.git("push", "-q", "origin", "main", cwd=self.pusher)
        self.git("fetch", "-q", "origin")


def _env(tmp_path: Path) -> dict[str, str]:
    """저장소를 가리키는 변수를 벗기고 사용자·시스템 설정을 끊는다(사용자의 `core.hooksPath` 등)."""
    env = {k: v for k, v in os.environ.items() if k not in REPO_LOCATION_VARS}
    empty = tmp_path / "gitconfig"
    empty.write_text("", encoding="utf-8")
    env["GIT_CONFIG_GLOBAL"] = str(empty)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["PRE_COMMIT_HOME"] = str(tmp_path / "pre-commit-home")
    return env


def _shim(repo: Repo) -> None:
    """pre-commit 자리에 이 검사를 바로 부르는 심. 리눅스의 git 은 실행 권한이 없는 훅을
    건너뛴다."""
    hooks = repo.tmp / "hooks"
    hooks.mkdir(exist_ok=True)
    shim = hooks / "pre-commit"
    shim.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "{CHECK.as_posix()}"\n',
        encoding="utf-8",
        newline="\n",
    )
    shim.chmod(0o755)
    repo.git("config", "core.hooksPath", hooks.as_posix())


def _repo(tmp_path: Path, seed: dict[str, str], *, hook: bool = True) -> Repo:
    """원격과 그 main, 작업 클론. 작업 클론은 main 에 있다."""
    env = _env(tmp_path)
    remote = tmp_path / "origin.git"
    repo = Repo(tmp_path, tmp_path / "work", tmp_path / "pusher", env)
    repo.git("init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    repo.git("init", "-q", "-b", "main", str(repo.pusher), cwd=tmp_path)
    repo.git("remote", "add", "origin", str(remote), cwd=repo.pusher)
    repo.write(seed, repo.pusher)
    repo.git("add", "-A", cwd=repo.pusher)
    repo.git("commit", "-q", "-m", "씨앗", cwd=repo.pusher)
    repo.git("push", "-q", "origin", "main", cwd=repo.pusher)
    repo.git("clone", "-q", str(remote), str(repo.work), cwd=tmp_path)
    if hook:
        _shim(repo)
    return repo


@pytest.fixture
def 저장소(tmp_path: Path) -> Repo:
    """검사가 든 main 에서 딴 저장소."""
    return _repo(tmp_path, {**SEED, **CHECK_MARK})


BLOCKED = "커밋을 막았다"


def _막혔다(result: subprocess.CompletedProcess[str]) -> str:
    """판정 7 로 막혔다. git 이 실패해 2 로 끝난 것은 막힘으로 세지 않는다."""
    out = result.stdout + result.stderr
    assert result.returncode != 0, f"지나면 안 된다: {out}"
    assert BLOCKED in out, f"막는 글이 아니다: {out}"
    return out


def _지났다(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, f"막히면 안 된다: {result.stdout}{result.stderr}"
    return result.stdout + result.stderr


# --- 면제 모양 -------------------------------------------------------------------


def test_면제_모양만_바꾼_커밋은_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/design")
    _지났다(
        저장소.stage_commit(
            {
                "docs/journal/2026-01-02-01-x.md": "일지\n",
                ".scratch/retro-queue/0573.md": "대기열 항목\n",
                ".scratch/retro-queue/coderabbit-inline-size.md": "대기열 항목\n",
                ".scratch/retro-queue/README.md": "대기열 폴더\n",
                "docs/adr/0002-x.md": "결정\n",
                "docs/adr/README.md": "색인\n",
                "GLOSSARY.md": "용어\n",
                ".scratch/plan.md": "계획\n",
                ".scratch/plan-head.md": "손 파일\n",
                "docs/PRD.md": "범위\n",
                "docs/constitution/tech.md": "스택\n",
                "docs/constitution/README.md": "판\n",
                "docs/constitution/history.md": "기록\n",
                ".scratch/feat/spec.md": "명세\n",
                ".scratch/feat/plan.md": "기능 계획\n",
                ".scratch/feat/issues/03-next.md": READY,
                ".scratch/feat/probes/deep/p.py": "P = 1\n",
                ".scratch/feat/design/a.html": "<p>화면</p>\n",
            }
        )
    )


@pytest.mark.parametrize(
    "path",
    [
        ".scratch/harness/spec.md",
        ".scratch/harness/probes/p.py",
        ".scratch/feat/design.md",
        ".scratch/harness/plan.md",
        ".scratch/feat/sub/plan.md",
        ".scratch/feat/plan.md.bak",
        ".scratch/plan-head.md.bak",
        ".scratch/other/plan-head.md",
        "docs/constitution/history.md.bak",
        "docs/constitution/sub/history.md",
        "docs/history.md",
    ],
)
def test_면제_모양_밖의_scratch_파일을_섞으면_막는다(저장소: Repo, path: str) -> None:
    저장소.git("switch", "-q", "-c", "docs/design")
    out = _막혔다(저장소.stage_commit({"docs/journal/2026-01-02-01-x.md": "일지\n", path: "x\n"}))
    assert path in out


@pytest.mark.parametrize(
    "path",
    [
        ".scratch/retro-queue.md",
        ".scratch/retro-queue-x/x.md",
        ".scratch/retro-queue/issues/x.md",
        ".scratch/retro-queue/probes/p.py",
        ".scratch/retro-queue/design/a.html",
        ".scratch/retro-queue/sub/x.md",
        ".scratch/retro-queue/x.txt",
    ],
)
def test_대기열_폴더의_면제_꼴이_아닌_파일을_섞으면_막는다(저장소: Repo, path: str) -> None:
    # 폴더 바로 아래의 `.md` 만 면제다. 옛 파일, 비슷한 이름의 폴더, 기능 폴더의 갈래, 하위 폴더,
    # `.md` 가 아닌 파일은 면제가 아니다
    저장소.git("switch", "-q", "-c", "docs/design")
    out = _막혔다(저장소.stage_commit({"docs/journal/2026-01-02-01-x.md": "일지\n", path: "x\n"}))
    assert path in out


def test_대기열_폴더_바로_아래의_md는_다른_면제_모양_밖의_파일과_섞으면_막는다(
    저장소: Repo,
) -> None:
    저장소.git("switch", "-q", "-c", "docs/design")
    out = _막혔다(
        저장소.stage_commit({".scratch/retro-queue/0573.md": "항목\n", "tools/b.py": "B = 1\n"})
    )
    assert "tools/b.py" in out
    assert ".scratch/retro-queue/0573.md" not in out


def test_독스트링의_면제_모양_원천이_대기열_폴더를_든다() -> None:
    doc = check_ticket.__doc__
    assert doc is not None
    assert "`.scratch/retro-queue/*.md`" in doc
    assert "- `docs/journal/*.md`, `.scratch/retro-queue.md`" not in doc


def test_독스트링의_면제_모양_원천이_기능_계획과_손_파일을_든다() -> None:
    doc = check_ticket.__doc__
    assert doc is not None
    assert "`.scratch/<slug>/plan.md`" in doc
    assert "`.scratch/plan-head.md`" in doc


def test_독스트링의_면제_모양_원천이_헌법_판_이력_기록을_든다() -> None:
    doc = check_ticket.__doc__
    assert doc is not None
    assert "`docs/constitution/history.md`" in doc


def test_이름_바꾸기는_지운_것과_더한_것으로_센다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/design")
    저장소.git("mv", "tools/a.py", "docs/journal/2026-01-02-01-a.md")
    out = _막혔다(저장소.commit("-m", "x"))
    assert "tools/a.py" in out


# --- 티켓 모양 브랜치 --------------------------------------------------------------


def test_chore_브랜치가_그_티켓을_실으면_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/002-thing")
    _지났다(
        저장소.stage_commit(
            {".scratch/harness/issues/002-thing.md": "# 002\n", "tools/b.py": "B = 1\n"}
        )
    )


def test_chore_브랜치가_티켓을_빠뜨리면_막고_할_일을_든다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/002-thing")
    out = _막혔다(저장소.stage_commit({"tools/b.py": "B = 1\n"}))
    assert "tools/b.py" in out
    assert ".scratch/harness/issues/002-thing.md" in out
    assert SLUG_RULE in out and NUMBER_COMMAND not in out
    assert BRANCH_COMMAND in out
    assert CONVENTION in out


def test_chore_브랜치의_slug가_그_티켓을_실으면_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/ci-python-runner-pin")
    _지났다(
        저장소.stage_commit(
            {
                ".scratch/harness/issues/ci-python-runner-pin.md": "# ci-python-runner-pin: 고정\n",
                "tools/b.py": "B = 1\n",
            }
        )
    )


def test_chore_브랜치의_slug가_티켓을_빠뜨리면_막고_번호_없는_할_일을_든다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/ci-python-runner-pin")
    out = _막혔다(저장소.stage_commit({"tools/b.py": "B = 1\n"}))
    assert "tools/b.py" in out
    assert ".scratch/harness/issues/ci-python-runner-pin.md" in out
    assert SLUG_RULE in out and NUMBER_COMMAND not in out
    assert BRANCH_COMMAND in out and "chore/<slug>" in out
    assert CONVENTION in out


@pytest.mark.parametrize("이름", ["Foo", "09-x", "a_b"])
def test_이름_규칙에_맞지_않는_chore_브랜치는_같은_이름의_파일도_티켓으로_세지_않는다(
    저장소: Repo, 이름: str
) -> None:
    저장소.git("switch", "-q", "-c", f"chore/{이름}")
    _막혔다(
        저장소.stage_commit(
            {f".scratch/harness/issues/{이름}.md": "# 티켓\n", "tools/b.py": "B = 1\n"}
        )
    )


def test_다른_slug의_티켓은_가리키지_않는다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/ci-python-runner-pin")
    _막혔다(
        저장소.stage_commit(
            {".scratch/harness/issues/other-thing.md": "# other-thing\n", "tools/b.py": "B = 1\n"}
        )
    )


def test_다른_번호의_티켓은_가리키지_않는다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/002-thing")
    _막혔다(
        저장소.stage_commit(
            {".scratch/harness/issues/003-thing.md": "# 003\n", "tools/b.py": "B = 1\n"}
        )
    )


def test_지운_티켓은_가리키지_않는다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "feature/02-thing")
    저장소.git("rm", "-q", ".scratch/feat/issues/02-thing.md")
    저장소.write({"tools/b.py": "B = 1\n"})
    저장소.git("add", "-A")
    _막혔다(저장소.commit("-m", "x"))


def test_feature_브랜치는_어느_기능_폴더의_같은_이름_티켓으로도_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "feature/05-other")
    _지났다(
        저장소.stage_commit(
            {".scratch/elsewhere/issues/05-other.md": READY, "tools/b.py": "B = 1\n"}
        )
    )


def test_docs_브랜치는_harness_티켓을_하나라도_실으면_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/retro")
    _지났다(
        저장소.stage_commit(
            {".scratch/harness/issues/009-anything.md": "# 009\n", "tools/b.py": "B = 1\n"}
        )
    )


def test_docs_브랜치는_번호_없는_harness_티켓도_세어_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/retro")
    _지났다(
        저장소.stage_commit(
            {".scratch/harness/issues/queue-split.md": "# queue-split\n", "tools/b.py": "B = 1\n"}
        )
    )


def test_docs_브랜치는_이미_있는_harness_티켓을_고치기만_해도_지난다(저장소: Repo) -> None:
    # 못 보는 것: 회고 반영이 아닌 일을 실어도 지난다
    저장소.git("switch", "-q", "-c", "docs/retro")
    _지났다(
        저장소.stage_commit(
            {".scratch/harness/issues/001-old.md": "# 001: 고쳤다\n", "tools/b.py": "B = 1\n"}
        )
    )


@pytest.mark.parametrize(
    "path",
    [
        ".scratch/harness/issues/README.md",
        ".scratch/harness/issues/sub/009-x.md",
        ".scratch/harness/issues/009-x.txt",
        ".scratch/harness/issues/09-x.md",
        ".scratch/harness/issues/queue-split.txt",
        ".scratch/harness/issues/sub/queue-split.md",
        ".scratch/harness/issues/Queue-Split.md",
    ],
)
def test_docs_브랜치는_harness_티켓_모양이_아닌_파일로는_지나지_않는다(
    저장소: Repo, path: str
) -> None:
    저장소.git("switch", "-q", "-c", "docs/retro")
    _막혔다(저장소.stage_commit({path: "x\n", "tools/b.py": "B = 1\n"}))


def test_면제_밖_파일이_열_개를_넘으면_나머지_수를_든다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/many")
    out = _막혔다(저장소.stage_commit({f"tools/m{i:02}.py": "M = 1\n" for i in range(12)}))
    assert "tools/m09.py" in out
    assert "tools/m10.py" not in out
    assert "그 밖에 2개" in out


def test_앱_워크트리_모양의_브랜치는_막는다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "claude/happy-dijkstra")
    out = _막혔다(저장소.stage_commit({"tools/b.py": "B = 1\n"}))
    assert SLUG_RULE in out and BRANCH_COMMAND in out and NUMBER_COMMAND not in out


# --- 디스크에는 있는데 커밋에 들지 않은 티켓 -----------------------------------------------


def test_고치지_않은_ready_for_agent_티켓은_알린다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "feature/02-thing")
    out = _막혔다(저장소.stage_commit({"tools/a.py": "A = 2\n"}))
    assert ".scratch/feat/issues/02-thing.md" in out
    assert NOTICE in out


def test_한_번도_add하지_않은_새_티켓은_알린다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/002-new")
    저장소.write({".scratch/harness/issues/002-new.md": "# 002\n", "tools/a.py": "A = 2\n"})
    저장소.git("add", "tools/a.py")
    out = _막혔다(저장소.commit("-m", "x"))
    assert ".scratch/harness/issues/002-new.md" in out
    assert NOTICE in out


# --- 커밋의 길 -------------------------------------------------------------------


def test_일부_파일만_커밋하면_그_커밋에_들_것만_본다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "feature/02-thing")
    ticket = ".scratch/feat/issues/02-thing.md"
    저장소.write({ticket: READY.replace("ready-for-agent", "in-progress"), "tools/a.py": "A = 2\n"})
    # 색인에는 티켓이 있지만 `git commit <경로>` 는 HEAD 에 그 경로만 얹은 임시 색인으로 커밋한다
    저장소.git("add", ticket)
    _막혔다(저장소.commit("-m", "x", "--", "tools/a.py"))
    _지났다(저장소.commit("-m", "x", "--", "tools/a.py", ticket))


def test_a_옵션은_고친_추적_파일을_모두_본다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "feature/02-thing")
    저장소.write({"tools/a.py": "A = 2\n"})
    _막혔다(저장소.commit("-a", "-m", "x"))
    저장소.write(
        {".scratch/feat/issues/02-thing.md": READY.replace("ready-for-agent", "in-progress")}
    )
    _지났다(저장소.commit("-a", "-m", "x"))


def test_amend는_merge_base에서_고친_색인까지를_본다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/002-thing")
    ticket = ".scratch/harness/issues/002-thing.md"
    _지났다(저장소.stage_commit({ticket: "# 002\n", "tools/b.py": "B = 1\n"}))
    저장소.write({"tools/b.py": "B = 2\n"})
    _지났다(저장소.commit("-a", "--amend", "--no-edit"))
    저장소.git("rm", "-q", "--cached", ticket)
    _막혔다(저장소.commit("--amend", "--no-edit"))


# --- 지나는 자리 -----------------------------------------------------------------


def test_분리_HEAD는_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "--detach")
    _지났다(저장소.stage_commit({"tools/b.py": "B = 1\n"}))


def test_main은_지난다(저장소: Repo) -> None:
    _지났다(저장소.stage_commit({"tools/b.py": "B = 1\n"}))


def test_origin_main이_없으면_알리고_지난다(tmp_path: Path) -> None:
    repo = Repo(tmp_path, tmp_path / "solo", None, _env(tmp_path))
    repo.git("init", "-q", "-b", "main", str(repo.work), cwd=tmp_path)
    repo.write({**SEED, **CHECK_MARK})
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "씨앗")
    _shim(repo)
    repo.git("switch", "-q", "-c", "topic")
    out = _지났다(repo.stage_commit({"tools/b.py": "B = 1\n"}))
    assert "origin/main" in out


def test_얕은_클론에서_merge_base가_없으면_알리고_지난다(저장소: Repo) -> None:
    """딴 자리가 깊이 밖이면 공통 조상이 없어 보인다. 빈 트리에서 세면 C 가 저장소 전체가 된다."""
    assert 저장소.pusher is not None
    저장소.git("switch", "-q", "-c", "chore/002-thing", cwd=저장소.pusher)
    저장소.write({"tools/b.py": "B = 1\n"}, 저장소.pusher)
    저장소.git("add", "-A", cwd=저장소.pusher)
    저장소.git("commit", "-q", "-m", "가지", cwd=저장소.pusher)
    저장소.git("push", "-q", "origin", "chore/002-thing", cwd=저장소.pusher)
    저장소.git("switch", "-q", "main", cwd=저장소.pusher)
    저장소.push_main({"docs/journal/2026-01-02-01-main.md": "main\n"})
    shallow = 저장소.tmp / "shallow"
    remote = (저장소.tmp / "origin.git").as_uri()
    저장소.git("clone", "-q", "--depth", "1", "--no-single-branch", remote, str(shallow))
    repo = Repo(저장소.tmp, shallow, None, 저장소.env)
    _shim(repo)
    repo.git("switch", "-q", "chore/002-thing")
    _지났다(repo.stage_commit({"docs/journal/2026-01-03-01-x.md": "x\n"}))
    result = _바로(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "얕은 클론" in result.stdout


def test_고아_브랜치는_첫_커밋만_지나고_그_뒤는_뿌리의_트리로_판정을_받는다(저장소: Repo) -> None:
    # 못 보는 것: 첫 커밋은 HEAD 가 없어 지난다. `--orphan` 은 색인을 두어 뿌리가 검사를 든다
    저장소.git("checkout", "-q", "--orphan", "orphan-topic")
    out = _지났다(저장소.stage_commit({"tools/b.py": "B = 1\n"}))
    assert "HEAD" in out
    _막혔다(저장소.stage_commit({"tools/c.py": "C = 1\n"}))


def test_색인을_비우고_만든_고아_브랜치는_규약_전으로_지난다(저장소: Repo) -> None:
    # 못 보는 것: 뿌리의 트리에 이 검사가 없다
    저장소.git("checkout", "-q", "--orphan", "orphan-topic")
    저장소.git("rm", "-r", "-q", "--cached", ".")
    저장소.write({"tools/b.py": "B = 1\n"})
    저장소.git("add", "tools/b.py")
    _지났다(저장소.commit("-m", "x"))
    out = _지났다(저장소.stage_commit({"tools/c.py": "C = 1\n"}))
    assert "규약 전" in out


def test_고아_역사를_합친_보통_브랜치는_판정을_받는다(저장소: Repo) -> None:
    저장소.git("checkout", "-q", "--orphan", "orphan-topic")
    _지났다(저장소.stage_commit({"tools/b.py": "B = 1\n"}))
    저장소.git("switch", "-q", "-c", "docs/x", "origin/main")
    저장소.git(
        "merge", "-q", "--no-edit", "--allow-unrelated-histories", "-X", "ours", "orphan-topic"
    )
    _막혔다(저장소.stage_commit({"tools/c.py": "C = 1\n"}))


# --- 전환 -----------------------------------------------------------------------


@pytest.fixture
def 규약_전_브랜치(tmp_path: Path) -> Repo:
    """검사가 없던 main 에서 딴 `topic`. 그 뒤 원격의 main 에 검사가 들어왔다."""
    repo = _repo(tmp_path, SEED)
    repo.git("switch", "-q", "-c", "topic")
    repo.push_main(CHECK_MARK)
    return repo


def test_규약_전_브랜치는_지나고_main을_합친_뒤에도_지난다(규약_전_브랜치: Repo) -> None:
    out = _지났다(규약_전_브랜치.stage_commit({"tools/b.py": "B = 1\n"}))
    assert "규약 전" in out
    규약_전_브랜치.git("merge", "-q", "--no-edit", "origin/main")
    _지났다(규약_전_브랜치.stage_commit({"tools/c.py": "C = 1\n"}))


def test_자기_커밋이_없는_규약_전_브랜치는_HEAD를_딴_자리로_본다(규약_전_브랜치: Repo) -> None:
    out = _지났다(규약_전_브랜치.stage_commit({"tools/b.py": "B = 1\n"}))
    assert "규약 전" in out


def test_규약_전_브랜치를_rebase하면_판정을_받는다(규약_전_브랜치: Repo) -> None:
    _지났다(규약_전_브랜치.stage_commit({"tools/b.py": "B = 1\n"}))
    규약_전_브랜치.git("rebase", "-q", "origin/main")
    _막혔다(규약_전_브랜치.stage_commit({"tools/c.py": "C = 1\n"}))


def test_첫_자기_커밋은_날짜가_아니라_위상_순서로_고른다(규약_전_브랜치: Repo) -> None:
    # 이 티켓의 브랜치처럼 규약 전 브랜치가 첫 커밋에서 검사를 더했다. 둘째 커밋의 날짜가 더 이르면
    # 날짜로 고른 "첫 커밋" 은 둘째이고, 그 부모 트리에는 검사가 있어 막힌다
    _지났다(규약_전_브랜치.stage_commit(CHECK_MARK))
    early = "2020-01-01T00:00:00+0000"
    규약_전_브랜치.env["GIT_COMMITTER_DATE"] = early
    규약_전_브랜치.env["GIT_AUTHOR_DATE"] = early
    _지났다(규약_전_브랜치.stage_commit({"tools/b.py": "B = 1\n"}))
    del 규약_전_브랜치.env["GIT_COMMITTER_DATE"], 규약_전_브랜치.env["GIT_AUTHOR_DATE"]
    _지났다(규약_전_브랜치.stage_commit({"tools/c.py": "C = 1\n"}))


# --- 병합 -----------------------------------------------------------------------

JOURNAL = "docs/journal/2026-01-01-01-seed.md"


@pytest.mark.parametrize("place", ["클론", "링크드_워크트리"])
def test_충돌을_풀고_친_병합_커밋은_main이_들여온_파일을_세지_않는다(
    저장소: Repo, place: str
) -> None:
    if place == "클론":
        where = 저장소.work
        저장소.git("switch", "-q", "-c", "docs/journal-only")
    else:
        where = 저장소.tmp / "linked"
        저장소.git("worktree", "add", "-q", "-b", "docs/journal-only", str(where), "origin/main")
    _지났다(저장소.stage_commit({JOURNAL: "브랜치\n"}, cwd=where))
    저장소.push_main({JOURNAL: "main\n", "tools/new.py": "N = 1\n"})
    merged = subprocess.run(
        ["git", *_IDENTITY, "merge", "-q", "--no-edit", "origin/main"],
        cwd=where,
        env=저장소.env,
        capture_output=True,
        timeout=_TIMEOUT,
        check=False,
    )
    assert merged.returncode != 0, "충돌이 나야 한다"
    저장소.write({JOURNAL: "풀었다\n"}, cwd=where)
    저장소.git("add", JOURNAL, cwd=where)
    _지났다(저장소.commit("--no-edit", cwd=where))


def test_충돌_없는_병합은_훅이_돌지_않아_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/journal-only")
    _지났다(저장소.stage_commit({"docs/journal/2026-01-02-01-x.md": "일지\n"}))
    저장소.push_main({"tools/new.py": "N = 1\n"})
    저장소.git("merge", "-q", "--no-edit", "origin/main")
    assert (저장소.work / "tools" / "new.py").is_file()


def test_워크트리에서의_커밋도_판정한다(저장소: Repo) -> None:
    where = 저장소.tmp / "linked"
    저장소.git("worktree", "add", "-q", "-b", "chore/002-thing", str(where), "origin/main")
    _막혔다(저장소.stage_commit({"tools/b.py": "B = 1\n"}, cwd=where))
    _지났다(저장소.stage_commit({".scratch/harness/issues/002-thing.md": "# 002\n"}, cwd=where))


# --- 바로 친다 -------------------------------------------------------------------


def _바로(repo: Repo) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=repo.work,
        env=repo.env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
        check=False,
    )


def test_바로_치면_지금_색인으로_판정한다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/002-thing")
    저장소.write({"tools/b.py": "B = 1\n"})
    저장소.git("add", "-A")
    result = _바로(저장소)
    assert result.returncode == 1
    assert ".scratch/harness/issues/002-thing.md" in result.stderr


def test_저장소가_아닌_폴더에서는_git_실패로_2를_낸다(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    env = {**_env(tmp_path), "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    result = _바로(Repo(tmp_path, plain, None, env))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "symbolic-ref" in result.stderr


def test_인자를_잘못_주면_argparse가_접두_없이_2로_끝낸다(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK), "--모르는-인자"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stderr.startswith("usage:") and "check-ticket:" not in result.stderr


def test_바로_치면_전환의_한_줄이_보인다(규약_전_브랜치: Repo) -> None:
    result = _바로(규약_전_브랜치)
    assert result.returncode == 0
    assert "규약 전" in result.stdout


# --- CI ------------------------------------------------------------------------
#
# CI 는 PR 의 병합 커밋(첫 부모 base, 둘째 부모 머리)을 분리 HEAD 로 체크아웃하고, PR 의 값은 환경
# 변수로 받는다. 아래는 작업 클론에서 그 병합 커밋을 지어 체크아웃한 뒤 `--ci` 로 바로 친다.

DONE = "# 02: 일\n\n**Status:** done\n"
IN_PROGRESS = READY.replace("ready-for-agent", "in-progress")
CI_BLOCKED = "PR 을 막았다"


@dataclass(frozen=True)
class PR값:
    head_ref: str
    head: str
    base: str


def _PR_병합_커밋(repo: Repo, head_ref: str, base: str = "origin/main") -> PR값:
    """`head_ref` 를 `base` 에 합친 병합 커밋을 분리 HEAD 로 체크아웃한다(GitHub 의 PR 병합
    커밋)."""
    head = repo.git("rev-parse", head_ref)
    base_sha = repo.git("rev-parse", base)
    repo.git("switch", "-q", "--detach", base_sha)
    repo.git("merge", "-q", "--no-ff", "--no-edit", head)
    return PR값(head_ref, head, base_sha)


def _CI로_친다(
    repo: Repo, pr: PR값 | None, event: str | None = None
) -> subprocess.CompletedProcess[str]:
    """CI 처럼 친다. `pr` 이 없으면 PR 이 아닌 실행(push)이라 PR 의 값이 비어 있다. 이벤트 이름
    (`GITHUB_EVENT_NAME`)을 주지 않으면 `pr` 에 맞춘다. 이 시험이 CI 의 PR 실행에서 돌 때 물려받는
    값에 기대지 않는다."""
    values = ("", "", "") if pr is None else (pr.head_ref, pr.head, pr.base)
    name = event if event is not None else ("push" if pr is None else "pull_request")
    env = {
        **repo.env,
        "GITHUB_EVENT_NAME": name,
        **dict(zip(("PR_HEAD_REF", "PR_HEAD_SHA", "PR_BASE_SHA"), values, strict=True)),
    }
    return subprocess.run(
        [sys.executable, str(CHECK), "--ci"],
        cwd=repo.work,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
        check=False,
    )


def _CI가_막았다(result: subprocess.CompletedProcess[str]) -> str:
    out = result.stdout + result.stderr
    assert result.returncode == 1, f"CI 가 막아야 한다: {out}"
    assert CI_BLOCKED in out, f"CI 의 막는 글이 아니다: {out}"
    return out


def _CI가_지났다(result: subprocess.CompletedProcess[str]) -> str:
    out = result.stdout + result.stderr
    assert result.returncode == 0, f"CI 가 지나야 한다: {out}"
    return out


def _티켓_브랜치(repo: Repo, ticket: str) -> None:
    """`feature/02-thing` 이 그 티켓과 면제 밖 파일 하나를 실은 커밋을 든다."""
    repo.git("switch", "-q", "-c", "feature/02-thing")
    _지났다(
        repo.stage_commit({".scratch/feat/issues/02-thing.md": ticket, "tools/b.py": "B = 1\n"})
    )


def _훅을_건너뛰고_커밋한다(repo: Repo, files: dict[str, str]) -> None:
    """`--no-verify` 커밋. 커밋 검사를 거치지 않은 커밋이 PR 에 드는 길이다."""
    repo.write(files)
    repo.git("add", "-A")
    repo.git("commit", "-q", "--no-verify", "-m", "훅을 건너뛰었다")


def test_CI는_done이_아닌_티켓을_막고_경로와_값과_할_일을_든다(저장소: Repo) -> None:
    _티켓_브랜치(저장소, IN_PROGRESS)
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))
    assert ".scratch/feat/issues/02-thing.md" in out
    assert "in-progress" in out
    assert "done 으로" in out and "푸시" in out


@pytest.mark.parametrize("line", ["**Status:** done", "Status: done"])
def test_CI는_done인_티켓을_지난다(저장소: Repo, line: str) -> None:
    _티켓_브랜치(저장소, f"# 02: 일\n\n{line}\n")
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))


@pytest.mark.parametrize("line", ["**Status:** in-progress", "Status: in-progress"])
def test_CI는_두_꼴의_상태_줄을_모두_읽는다(저장소: Repo, line: str) -> None:
    _티켓_브랜치(저장소, f"# 02: 일\n\n{line}\n")
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))
    assert "in-progress" in out


def test_CI는_본문의_Status가_아니라_줄_머리의_상태_줄을_읽는다(저장소: Repo) -> None:
    # 기능을 닫는 판정의 문장처럼 본문이 상태 줄보다 먼저 `Status:` 를 다른 값과 함께 든다. 줄
    # 어디서든 첫 출현을 읽으면 done 을 읽는다
    ticket = (
        "# 02: 일\n\n- [ ] 기능을 닫으면 모든 티켓이 Status: done 이다\n\n**Status:** in-progress\n"
    )
    _티켓_브랜치(저장소, ticket)
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))
    assert "in-progress" in out


def test_CI는_상태_줄이_없는_티켓을_막는다(저장소: Repo) -> None:
    _티켓_브랜치(저장소, "# 02: 일\n\n본문만 있다\n")
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))
    assert "상태 줄이 없다" in out


def test_CI는_상태_줄의_값이_빈_티켓을_막는다(저장소: Repo) -> None:
    _티켓_브랜치(저장소, "# 02: 일\n\n**Status:**\n")
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))
    assert "상태 줄의 값이 비었다" in out


def test_CI는_docs_브랜치의_harness_티켓이_모두_done이어야_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/retro")
    done = ".scratch/harness/issues/009-a.md"
    open_ = ".scratch/harness/issues/010-b.md"
    _지났다(
        저장소.stage_commit(
            {
                done: "# 009\n\n**Status:** done\n",
                open_: "# 010\n\n**Status:** in-progress\n",
                "tools/b.py": "B = 1\n",
            }
        )
    )
    pr = _PR_병합_커밋(저장소, "docs/retro")
    out = _CI가_막았다(_CI로_친다(저장소, pr))
    assert open_ in out and done not in out
    저장소.git("switch", "-q", "docs/retro")
    _지났다(저장소.stage_commit({open_: "# 010\n\n**Status:** done\n"}))
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/retro")))


def test_CI는_면제_모양만_바꾼_PR을_티켓_상태와_상관없이_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "feature/02-thing")
    _지났다(
        저장소.stage_commit(
            {
                ".scratch/feat/issues/02-thing.md": IN_PROGRESS,
                "docs/journal/2026-01-02-01-x.md": "x\n",
            }
        )
    )
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))


def test_CI는_기능_계획과_손_파일만_바꾼_PR을_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/plan")
    _훅을_건너뛰고_커밋한다(
        저장소,
        {
            ".scratch/feat/plan.md": "기능 계획\n",
            ".scratch/plan-head.md": "손 파일\n",
            ".scratch/plan.md": "생성 파일\n",
        },
    )
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/plan")))


def test_CI는_헌법_판_이력_기록만_바꾼_PR을_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/history")
    _훅을_건너뛰고_커밋한다(
        저장소,
        {"docs/constitution/history.md": "기록\n", "docs/constitution/README.md": "판\n"},
    )
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/history")))


def test_CI는_대기열_폴더_바로_아래의_md만_바꾼_PR을_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "docs/retro")
    _훅을_건너뛰고_커밋한다(
        저장소,
        {
            ".scratch/retro-queue/0573.md": "항목\n",
            ".scratch/retro-queue/coderabbit-inline-size.md": "항목\n",
            "docs/journal/2026-01-02-01-x.md": "일지\n",
        },
    )
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/retro")))


@pytest.mark.parametrize(
    "path",
    [".scratch/retro-queue.md", ".scratch/retro-queue-x/x.md", ".scratch/retro-queue/issues/x.md"],
)
def test_CI는_대기열_폴더의_면제_꼴이_아닌_파일이_든_PR을_막는다(저장소: Repo, path: str) -> None:
    저장소.git("switch", "-q", "-c", "docs/retro")
    _훅을_건너뛰고_커밋한다(저장소, {".scratch/retro-queue/0573.md": "항목\n", path: "x\n"})
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/retro")))
    assert path in out


def test_CI는_분리_HEAD인_병합_커밋에서도_티켓_없는_PR을_막는다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/002-thing")
    _훅을_건너뛰고_커밋한다(저장소, {"tools/b.py": "B = 1\n"})
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "chore/002-thing")))
    assert 저장소.git("rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
    assert "tools/b.py" in out
    assert ".scratch/harness/issues/002-thing.md" in out
    assert SLUG_RULE in out and BRANCH_COMMAND in out and CONVENTION in out
    assert NUMBER_COMMAND not in out


def test_CI는_chore_slug_브랜치의_티켓_상태를_읽는다(저장소: Repo) -> None:
    ticket = ".scratch/harness/issues/ci-python-runner-pin.md"
    저장소.git("switch", "-q", "-c", "chore/ci-python-runner-pin")
    _지났다(
        저장소.stage_commit({ticket: "# x\n\n**Status:** in-progress\n", "tools/b.py": "B = 1\n"})
    )
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "chore/ci-python-runner-pin")))
    assert ticket in out and "in-progress" in out
    저장소.git("switch", "-q", "chore/ci-python-runner-pin")
    _지났다(저장소.stage_commit({ticket: "# x\n\n**Status:** done\n"}))
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "chore/ci-python-runner-pin")))


def test_CI는_chore_slug_브랜치가_티켓을_빠뜨리면_막는다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "chore/ci-python-runner-pin")
    _훅을_건너뛰고_커밋한다(저장소, {"tools/b.py": "B = 1\n"})
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "chore/ci-python-runner-pin")))
    assert ".scratch/harness/issues/ci-python-runner-pin.md" in out
    assert SLUG_RULE in out


def test_CI는_머리_커밋에는_있지만_PR의_변경에_들지_않은_티켓을_알린다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "-c", "feature/02-thing")
    _훅을_건너뛰고_커밋한다(저장소, {"tools/b.py": "B = 1\n"})
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "feature/02-thing")))
    assert ".scratch/feat/issues/02-thing.md" in out
    assert "PR 의 변경에 들지 않는다" in out
    # 그 티켓이 이미 done 이면(앞서 닫힌 티켓의 브랜치를 다시 쓴 PR) done 으로 고칠 것이 없다
    assert "이미 done 이면" in out and "새로 쓴다" in out


def test_CI는_판정_전에_받은_값과_병합_커밋의_첫_부모를_찍는다(저장소: Repo) -> None:
    _티켓_브랜치(저장소, DONE)
    pr = _PR_병합_커밋(저장소, "feature/02-thing")
    first_parent = 저장소.git("rev-parse", "HEAD^1")
    result = _CI로_친다(저장소, pr)
    line = next(x for x in result.stdout.splitlines() if "CI 입력" in x)
    for value in ("feature/02-thing", pr.head, pr.base, first_parent):
        assert value in line, line


def test_CI는_PR이_아닌_실행에서_한_줄을_찍고_지난다(저장소: Repo) -> None:
    result = _CI로_친다(저장소, None)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PR 이 아닌 실행" in result.stdout


def test_CI는_PR_실행인데_머리_브랜치가_비면_git_실패로_2를_낸다(저장소: Repo) -> None:
    # 워크플로의 env 이름이 도구와 어긋나거나 식이 비면, PR 이 push 처럼 판정 없이 지난다
    result = _CI로_친다(저장소, None, "pull_request")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "PR_HEAD_REF" in result.stderr


def test_CI는_체크아웃이_얕아_merge_base를_찾지_못하면_git_실패로_2를_낸다(저장소: Repo) -> None:
    # fetch-depth 를 줄이면 base 와 머리의 공통 조상이 깊이 밖이다. 커밋 검사의 얕은 클론처럼
    # 알리고 지나면 모든 PR 이 판정 없이 초록이다
    저장소.git("switch", "-q", "-c", "chore/002-thing")
    _훅을_건너뛰고_커밋한다(저장소, {"tools/b.py": "B = 1\n"})
    저장소.push_main({"docs/journal/2026-01-02-01-main.md": "main\n"})
    pr = _PR_병합_커밋(저장소, "chore/002-thing")
    저장소.git("update-ref", "refs/pull/1/merge", "HEAD")
    shallow = 저장소.tmp / "shallow"
    저장소.git("init", "-q", str(shallow))
    source = 저장소.work.as_uri()
    저장소.git("fetch", "-q", "--depth", "2", source, "refs/pull/1/merge", cwd=shallow)
    저장소.git("switch", "-q", "--detach", "FETCH_HEAD", cwd=shallow)
    repo = Repo(저장소.tmp, shallow, None, 저장소.env)
    assert repo.git("rev-parse", "--is-shallow-repository") == "true"
    result = _CI로_친다(repo, pr)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "fetch-depth" in result.stderr


def test_CI는_base_커밋을_찾지_못하면_git_실패로_2를_낸다(저장소: Repo) -> None:
    _티켓_브랜치(저장소, DONE)
    pr = _PR_병합_커밋(저장소, "feature/02-thing")
    result = _CI로_친다(저장소, PR값(pr.head_ref, pr.head, "0" * 40))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "PR_BASE_SHA" in result.stderr


def test_CI는_머리_브랜치가_main인_PR을_지난다(저장소: Repo) -> None:
    # 못 보는 것: 포크의 main 에서 연 PR 은 판정 1 로 지난다
    _훅을_건너뛰고_커밋한다(저장소, {"tools/b.py": "B = 1\n"})
    head = 저장소.git("rev-parse", "HEAD")
    base = 저장소.git("rev-parse", "origin/main")
    저장소.git("switch", "-q", "--detach", base)
    저장소.git("merge", "-q", "--no-ff", "--no-edit", head)
    _CI가_지났다(_CI로_친다(저장소, PR값("main", head, base)))


def test_CI는_다른_브랜치를_base로_둔_PR의_변경에_base_브랜치의_커밋을_세지_않는다(
    저장소: Repo,
) -> None:
    # base 브랜치는 면제 밖 파일과 기능 티켓을 들었고, 그 위의 docs 브랜치는 일지만 고쳤다.
    # origin/main 을 기준으로 세면 docs 브랜치의 변경에 면제 밖 파일이 섞여 막힌다
    _티켓_브랜치(저장소, DONE)
    저장소.git("switch", "-q", "-c", "docs/on-top")
    # 커밋 검사는 이 커밋을 막는다(아래 쌓은 브랜치 사례)
    _훅을_건너뛰고_커밋한다(저장소, {"docs/journal/2026-01-02-01-x.md": "x\n"})
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/on-top", base="feature/02-thing")))


def test_커밋_검사는_다른_브랜치_위에_쌓은_브랜치의_커밋을_base_브랜치의_변경까지_세어_막는다(
    저장소: Repo,
) -> None:
    # 못 보는 것(거짓 양성): 커밋 검사는 origin/main 에 견주므로, 면제 모양만 고친 커밋도 base
    # 브랜치가 든 면제 밖 파일 때문에 막힌다. 그 PR 은 CI 가 base 커밋에 견줘 지난다(위 사례)
    _티켓_브랜치(저장소, DONE)
    저장소.git("switch", "-q", "-c", "docs/on-top")
    out = _막혔다(저장소.stage_commit({"docs/journal/2026-01-02-01-x.md": "x\n"}))
    assert "tools/b.py" in out


def test_CI는_base_브랜치가_병합되어_main을_base로_둔_쌓은_PR을_막고_rebase_onto로_지난다(
    저장소: Repo,
) -> None:
    # 못 보는 것(거짓 양성): base 브랜치를 squash 로 병합하면 그 커밋은 main 에 없어, base 가
    # main 으로 바뀐 쌓은 PR 은 base 브랜치의 변경까지 제 것으로 세어 막힌다. 독스트링이 안내한
    # 길(`git rebase --onto origin/main <옛 base 브랜치>`)로 옮기면 지난다
    _티켓_브랜치(저장소, DONE)
    저장소.git("switch", "-q", "-c", "docs/on-top")
    _훅을_건너뛰고_커밋한다(저장소, {"docs/journal/2026-01-02-01-x.md": "x\n"})
    저장소.push_main({".scratch/feat/issues/02-thing.md": DONE, "tools/b.py": "B = 1\n"})
    out = _CI가_막았다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/on-top")))
    assert "tools/b.py" in out
    저장소.git("switch", "-q", "docs/on-top")
    저장소.git("rebase", "-q", "--onto", "origin/main", "feature/02-thing")
    _CI가_지났다(_CI로_친다(저장소, _PR_병합_커밋(저장소, "docs/on-top")))


def test_CI는_다른_브랜치를_base로_둔_PR의_전환에_base_브랜치의_커밋을_세지_않는다(
    규약_전_브랜치: Repo,
) -> None:
    # base 브랜치는 규약 전에 땄고 그 뒤 main 을 합쳐 검사를 들였다. 그 위에서 딴 머리는 규약
    # 뒤라 판정을 받는다. origin/main 을 기준으로 세면 base 브랜치의 첫 커밋이 머리의 첫 자기 커밋이
    # 되고, 그 부모(검사가 없던 main)로 전환이 되어 지난다
    repo = 규약_전_브랜치
    _지났다(repo.stage_commit({"tools/b.py": "B = 1\n"}))
    repo.git("merge", "-q", "--no-edit", "origin/main")
    repo.git("switch", "-q", "-c", "chore/002-thing")
    _훅을_건너뛰고_커밋한다(repo, {"tools/c.py": "C = 1\n"})
    out = _CI가_막았다(_CI로_친다(repo, _PR_병합_커밋(repo, "chore/002-thing", base="topic")))
    assert "tools/c.py" in out and "tools/b.py" not in out


def test_CI의_전환은_base에_검사가_없던_자리에서_딴_머리를_지난다(규약_전_브랜치: Repo) -> None:
    repo = 규약_전_브랜치
    _지났다(repo.stage_commit({"tools/b.py": "B = 1\n"}))
    out = _CI가_지났다(_CI로_친다(repo, _PR_병합_커밋(repo, "topic")))
    assert "규약 전" in out


def test_CI는_검사가_든_base로_rebase한_규약_전_머리를_판정한다(규약_전_브랜치: Repo) -> None:
    repo = 규약_전_브랜치
    _지났다(repo.stage_commit({"tools/b.py": "B = 1\n"}))
    repo.git("rebase", "-q", "origin/main")
    out = _CI가_막았다(_CI로_친다(repo, _PR_병합_커밋(repo, "topic")))
    assert "tools/b.py" in out


def test_CI의_첫_자기_커밋은_날짜가_아니라_위상_순서로_고른다(규약_전_브랜치: Repo) -> None:
    repo = 규약_전_브랜치
    _지났다(repo.stage_commit(CHECK_MARK))
    early = "2020-01-01T00:00:00+0000"
    repo.env["GIT_COMMITTER_DATE"] = early
    repo.env["GIT_AUTHOR_DATE"] = early
    _지났다(repo.stage_commit({"tools/b.py": "B = 1\n"}))
    del repo.env["GIT_COMMITTER_DATE"], repo.env["GIT_AUTHOR_DATE"]
    out = _CI가_지났다(_CI로_친다(repo, _PR_병합_커밋(repo, "topic")))
    assert "규약 전" in out


# --- 진짜 pre-commit ------------------------------------------------------------

_ENTRY = """\
import os
import sys
from pathlib import Path

sys.path.insert(0, {root!r})
from tools.run_checks import Check, run

checks = [Check("check-ticket", (sys.executable, {check!r}))]
sys.exit(run(checks, os.environ, Path.cwd(), sys.stdout.buffer))
"""


@pytest.fixture
def pre_commit_저장소(tmp_path: Path) -> Repo:
    """pre-commit 을 깐 저장소. 그 설정은 러너의 `run` 에 이 검사 하나와 임시 저장소를 넘긴다.

    러너의 `main` 은 작업 폴더를 이 저장소의 루트로 고정해 임시 저장소가 아니라 이 저장소를
    판정한다.
    """
    entry = tmp_path / "entry.py"
    entry.write_text(
        _ENTRY.format(root=str(ROOT), check=str(CHECK)), encoding="utf-8", newline="\n"
    )
    python = Path(sys.executable).as_posix()
    config = (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: ticket-runner\n"
        "        name: ticket-runner\n"
        f'        entry: \'"{python}" "{entry.as_posix()}"\'\n'
        "        language: system\n"
        "        always_run: true\n"
        "        pass_filenames: false\n"
    )
    repo = _repo(tmp_path, {**SEED, **CHECK_MARK, ".pre-commit-config.yaml": config}, hook=False)
    installed = subprocess.run(
        [sys.executable, "-m", "pre_commit", "install"],
        cwd=repo.work,
        env=repo.env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
        check=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return repo


def test_진짜_pre_commit에서_고치고_스테이지하지_않은_티켓은_알린다(
    pre_commit_저장소: Repo,
) -> None:
    repo = pre_commit_저장소
    repo.git("switch", "-q", "-c", "feature/02-thing")
    ticket = ".scratch/feat/issues/02-thing.md"
    repo.write({ticket: READY.replace("ready-for-agent", "in-progress"), "tools/a.py": "A = 2\n"})
    repo.git("add", "tools/a.py")
    out = _막혔다(repo.commit("-m", "x"))
    assert "check-ticket" in out
    assert ticket in out and NOTICE in out
    # pre-commit 이 치운 고침을 되돌려 놓았다
    assert "in-progress" in (repo.work / ticket).read_text(encoding="utf-8")


def test_진짜_pre_commit에서_일부_파일_커밋은_임시_색인을_본다(pre_commit_저장소: Repo) -> None:
    repo = pre_commit_저장소
    repo.git("switch", "-q", "-c", "feature/02-thing")
    ticket = ".scratch/feat/issues/02-thing.md"
    repo.write({ticket: READY.replace("ready-for-agent", "in-progress"), "tools/a.py": "A = 2\n"})
    repo.git("add", ticket)
    _막혔다(repo.commit("-m", "x", "--", "tools/a.py"))
    _지났다(repo.commit("-m", "x", "--", "tools/a.py", ticket))
