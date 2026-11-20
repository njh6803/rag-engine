"""`tools/check_notes.py` 를 임시 git 저장소에서 잰다(release-image 티켓 05).

임시 저장소(맨 원격 하나와 그 main, 작업 클론)를 만들고, 커밋 검사 모드는 스테이지한 변경으로,
CI 모드는 브랜치의 머리 커밋과 main 의 커밋을 환경 변수로 주어 진짜 프로세스로 부른다(선례
`tests/tools/test_check_ticket.py`). 판정은 도구의 독스트링이 원천이다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from tools.run_checks import CHECKS
from tools.run_hooks import REPO_LOCATION_VARS

from rag_engine.adapters.postgres.migrate import MIGRATIONS_DIRECTORY
from tools import check_notes

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "check_notes.py"
_IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")
_TIMEOUT = 120

FEATURES = "docs/release-notes/features"
UPGRADE = "docs/release-notes/upgrade"
INTRO = "docs/release-notes/intro"
VERSIONS = "src/rag_engine/adapters/postgres/migrations/versions"

PLAN = "# 기능 계획\n\n**슬라이스:** 1\n"
END = "\n**끝:** 2026-11-15\n"
PARAGRAPH = "운영자는 이제 설정 파일의 새 칸으로 모델을 고른다.\n"
UPGRADE_TEXT = "설정 파일의 `old` 칸을 `new` 칸으로 바꾼다.\n"

COMMIT_BLOCKED = "커밋을 막았다"
PR_BLOCKED = "PR 을 막았다"


@dataclass
class Repo:
    tmp: Path
    work: Path
    pusher: Path
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
            path.write_text(text, encoding="utf-8", newline="")

    def commit(self, files: dict[str, str]) -> None:
        """훅 없이 커밋한다. 지난 커밋을 쌓는 데 쓴다."""
        self.write(files)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x")

    def remove(self, *names: str) -> None:
        for name in names:
            self.git("rm", "-q", name)

    def push_main(self, files: dict[str, str]) -> None:
        self.write(files, self.pusher)
        self.git("add", "-A", cwd=self.pusher)
        self.git("commit", "-q", "-m", "main", cwd=self.pusher)
        self.git("push", "-q", "origin", "main", cwd=self.pusher)
        self.git("fetch", "-q", "origin")

    def run(
        self, *args: str, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECK), *args],
            cwd=self.work,
            env={**self.env, **(extra or {})},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
            check=False,
        )

    def staged(self, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
        """파일을 스테이지하고 커밋 검사 모드로 친다. 커밋은 하지 않는다."""
        self.write(files)
        self.git("add", "-A")
        return self.run()

    def ci(
        self,
        title: str,
        *,
        files: dict[str, str] | None = None,
        head_ref: str = "feature/x",
        mode: str = "--ci",
        event: str = "pull_request",
    ) -> subprocess.CompletedProcess[str]:
        """`files` 를 커밋한 브랜치의 머리를 main 에 견줘 CI 처럼 친다."""
        if files:
            self.commit(files)
        return self.run(
            mode,
            extra={
                "GITHUB_EVENT_NAME": event,
                "PR_HEAD_REF": head_ref,
                "PR_HEAD_SHA": self.git("rev-parse", "HEAD"),
                "PR_BASE_SHA": self.git("rev-parse", "origin/main"),
                "PR_TITLE": title,
            },
        )


def _env(tmp_path: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in REPO_LOCATION_VARS}
    empty = tmp_path / "gitconfig"
    empty.write_text("", encoding="utf-8")
    env["GIT_CONFIG_GLOBAL"] = str(empty)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


@pytest.fixture
def 저장소(tmp_path: Path) -> Repo:
    """main 의 이력 둘. 앞 커밋은 제품 경로와 기능 `feat` 의 티켓을 함께 고쳤고(담은 기능), 뒤
    커밋은 기능 `plain`(제품 변경이 없다)과 `fresh`(아직 제품 변경이 없다)의 계획과 티켓이다. 작업
    클론은 그 main 에서 딴 `feature/x` 에 있다."""
    env = _env(tmp_path)
    remote = tmp_path / "origin.git"
    repo = Repo(tmp_path, tmp_path / "work", tmp_path / "pusher", env)
    repo.git("init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    repo.git("init", "-q", "-b", "main", str(repo.pusher), cwd=tmp_path)
    repo.git("remote", "add", "origin", str(remote), cwd=repo.pusher)
    repo.write(
        {
            "README.md": "읽어 보기\n",
            "src/app.py": "A = 1\n",
            ".scratch/feat/plan.md": PLAN,
            ".scratch/feat/issues/01-a.md": "# 01\n\n**Status:** done\n",
            ".scratch/feat/issues/02-b.md": "# 02\n\n**Status:** ready-for-agent\n",
        },
        repo.pusher,
    )
    repo.git("add", "-A", cwd=repo.pusher)
    repo.git("commit", "-q", "-m", "제품과 티켓", cwd=repo.pusher)
    repo.write(
        {
            ".scratch/plain/plan.md": PLAN,
            ".scratch/plain/issues/01-p.md": "# 01\n\n**Status:** ready-for-agent\n",
            ".scratch/fresh/plan.md": PLAN,
            ".scratch/fresh/issues/01-f.md": "# 01\n\n**Status:** ready-for-agent\n",
        },
        repo.pusher,
    )
    repo.git("add", "-A", cwd=repo.pusher)
    repo.git("commit", "-q", "-m", "문서만", cwd=repo.pusher)
    repo.git("push", "-q", "origin", "main", cwd=repo.pusher)
    repo.git("clone", "-q", str(remote), str(repo.work), cwd=tmp_path)
    repo.git("switch", "-q", "-c", "feature/x")
    return repo


def _막혔다(result: subprocess.CompletedProcess[str], wording: str = COMMIT_BLOCKED) -> str:
    out = result.stdout + result.stderr
    assert result.returncode == 1, f"막아야 한다(종료 {result.returncode}): {out}"
    assert wording in out, f"막는 글이 아니다: {out}"
    return out


def _지났다(result: subprocess.CompletedProcess[str]) -> str:
    out = result.stdout + result.stderr
    assert result.returncode == 0, f"지나야 한다(종료 {result.returncode}): {out}"
    return out


# --- (다) 모양: 순수 함수 --------------------------------------------------------


def test_기능_단락은_400자까지_지나고_401자에서_막힌다() -> None:
    assert check_notes.fragment_problems(f"{FEATURES}/a.md", "가" * 400 + "\n") == []
    problems = check_notes.fragment_problems(f"{FEATURES}/a.md", "가" * 401 + "\n")
    assert len(problems) == 1, f"401자 단락 문제가 {len(problems)}개다"
    assert "401" in problems[0]


def test_기능_단락의_글자_수는_줄바꿈을_뺀다() -> None:
    # CRLF 로 쓴 한 줄짜리 400자도 400자다. 끝의 줄바꿈 둘이 글자 수에 들지 않는다
    assert check_notes.fragment_problems(f"{FEATURES}/a.md", "가" * 400 + "\r\n") == []


def test_기능_단락은_빈_줄이_들면_막힌다() -> None:
    problems = check_notes.fragment_problems(f"{FEATURES}/a.md", "첫 줄\n\n둘째 단락\n")
    assert len(problems) == 1 and "단락" in problems[0]


def test_기능_단락은_여러_줄이어도_빈_줄이_없으면_한_단락이다() -> None:
    assert check_notes.fragment_problems(f"{FEATURES}/a.md", "첫 줄\n둘째 줄\n") == []


def test_공백만_있는_줄도_빈_줄이다() -> None:
    assert check_notes.fragment_problems(f"{FEATURES}/a.md", "첫 줄\n  \n둘째\n")


@pytest.mark.parametrize("folder", [FEATURES, UPGRADE, INTRO])
@pytest.mark.parametrize("text", ["", "\n", "  \n\n"])
def test_원고는_비어_있으면_막힌다(folder: str, text: str) -> None:
    name = "0.1.0" if folder == INTRO else "a"
    problems = check_notes.fragment_problems(f"{folder}/{name}.md", text)
    assert problems and "비어" in problems[0]


@pytest.mark.parametrize("folder", [FEATURES, UPGRADE, INTRO])
@pytest.mark.parametrize("text", ["# 머리\n본문\n", "본문\n## 소제목\n"])
def test_원고는_머리_줄이_있으면_막힌다(folder: str, text: str) -> None:
    name = "0.1.0" if folder == INTRO else "a"
    problems = check_notes.fragment_problems(f"{folder}/{name}.md", text)
    assert any("#" in p for p in problems)


def test_줄_가운데의_샵은_머리가_아니다() -> None:
    assert check_notes.fragment_problems(f"{FEATURES}/a.md", "이슈 #12 를 고쳤다\n") == []


@pytest.mark.parametrize("folder", [UPGRADE, INTRO])
def test_할_일과_소개_글에는_길이_상한이_없다(folder: str) -> None:
    name = "0.1.0" if folder == INTRO else "a"
    text = ("긴 줄이다.\n\n" * 200) + "끝\n"
    assert check_notes.fragment_problems(f"{folder}/{name}.md", text) == []


@pytest.mark.parametrize("name", ["0.1.0", "10.20.30", "0.0.0"])
def test_소개_글의_이름은_X_Y_Z가_지난다(name: str) -> None:
    assert check_notes.fragment_problems(f"{INTRO}/{name}.md", "소개\n") == []


@pytest.mark.parametrize("name", ["v0.1.0", "0.1", "0.1.0-rc.1", "01.2.3", "intro", "0.1.0.1"])
def test_소개_글의_이름이_X_Y_Z가_아니면_막힌다(name: str) -> None:
    problems = check_notes.fragment_problems(f"{INTRO}/{name}.md", "소개\n")
    assert len(problems) == 1 and "X.Y.Z" in problems[0]


def test_할_일_파일의_이름은_보지_않는다() -> None:
    assert check_notes.fragment_problems(f"{UPGRADE}/아무_이름.md", "할 일\n") == []


# --- (다) 모양: 진짜 저장소 ---------------------------------------------------------


def test_커밋_검사는_스테이지한_원고의_모양을_본다(저장소: Repo) -> None:
    out = _막혔다(저장소.staged({f"{FEATURES}/feat.md": "첫 단락\n\n둘째 단락\n"}))
    assert f"{FEATURES}/feat.md" in out


def test_커밋_검사는_원고가_아닌_파일을_보지_않는다(저장소: Repo) -> None:
    _지났다(
        저장소.staged(
            {
                "docs/release-notes/README.md": "# 설명\n",
                f"{FEATURES}/sub/x.md": "# 머리\n",
                f"{FEATURES}/x.txt": "",
            }
        )
    )


def test_지운_원고는_보지_않는다(저장소: Repo) -> None:
    저장소.commit({f"{UPGRADE}/old.md": "할 일\n"})
    저장소.git("rm", "-q", f"{UPGRADE}/old.md")
    _지났다(저장소.run())


# --- (나) 기능 단락의 빠뜨림 -------------------------------------------------------


def test_제품_변경을_담은_기능의_끝_줄에_기능_단락이_없으면_막는다(저장소: Repo) -> None:
    out = _막혔다(저장소.staged({".scratch/feat/plan.md": PLAN + END}))
    assert f"{FEATURES}/feat.md" in out


def test_제품_변경을_담은_기능의_끝_줄과_기능_단락을_함께_싣으면_지난다(저장소: Repo) -> None:
    _지났다(저장소.staged({".scratch/feat/plan.md": PLAN + END, f"{FEATURES}/feat.md": PARAGRAPH}))


def test_기능_단락을_먼저_커밋했으면_끝_줄만_싣는_커밋도_지난다(저장소: Repo) -> None:
    저장소.commit({f"{FEATURES}/feat.md": PARAGRAPH})
    _지났다(저장소.staged({".scratch/feat/plan.md": PLAN + END}))


def test_제품_변경이_없는_기능은_끝_줄만_싣고_지난다(저장소: Repo) -> None:
    _지났다(저장소.staged({".scratch/plain/plan.md": PLAN + END}))


def test_제품_변경이_없는_기능의_기능_단락은_막는다(저장소: Repo) -> None:
    out = _막혔다(
        저장소.staged({".scratch/plain/plan.md": PLAN + END, f"{FEATURES}/plain.md": PARAGRAPH})
    )
    assert f"{FEATURES}/plain.md" in out


def test_끝_줄_없이_기능_단락만_더해도_제품_변경이_없으면_막는다(저장소: Repo) -> None:
    _막혔다(저장소.staged({f"{FEATURES}/plain.md": PARAGRAPH}))


def test_끝_줄_없이_기능_단락만_더해도_제품_변경을_담았으면_지난다(저장소: Repo) -> None:
    _지났다(저장소.staged({f"{FEATURES}/feat.md": PARAGRAPH}))


def test_지금_보는_변경이_제품과_티켓을_함께_고치면_담은_것이다(저장소: Repo) -> None:
    # `fresh` 는 지난 이력에 제품 변경이 없다. 이번 변경이 제품과 티켓을 함께 고친다
    files = {
        ".scratch/fresh/plan.md": PLAN + END,
        ".scratch/fresh/issues/01-f.md": "# 01\n\n**Status:** done\n",
        "src/app.py": "A = 2\n",
    }
    _막혔다(저장소.staged(files))
    _지났다(저장소.staged({f"{FEATURES}/fresh.md": PARAGRAPH}))


def test_제품만_고치고_티켓은_고치지_않으면_그_기능이_담은_것이_아니다(저장소: Repo) -> None:
    _지났다(저장소.staged({".scratch/fresh/plan.md": PLAN + END, "src/app.py": "A = 2\n"}))


def test_다른_기능의_티켓과_제품을_함께_고친_커밋은_이_기능의_것이_아니다(저장소: Repo) -> None:
    저장소.commit(
        {".scratch/feat/issues/02-b.md": "# 02\n\n**Status:** done\n", "src/b.py": "B = 1\n"}
    )
    _지났다(저장소.staged({".scratch/plain/plan.md": PLAN + END}))


def test_features_파일의_이름은_있는_기능_계획의_slug여야_한다(저장소: Repo) -> None:
    out = _막혔다(저장소.staged({f"{FEATURES}/nothing.md": PARAGRAPH}))
    assert "nothing" in out and "기능 계획" in out


def test_harness는_기능_계획이_없어_기능_단락을_더하지_못한다(저장소: Repo) -> None:
    _막혔다(저장소.staged({f"{FEATURES}/harness.md": PARAGRAPH}))


@pytest.mark.parametrize("slug", ["harness", "retro-queue"])
def test_기능이_아닌_폴더는_계획이_있어도_기능_단락을_못_더한다(저장소: Repo, slug: str) -> None:
    files = {f".scratch/{slug}/plan.md": PLAN, f"{FEATURES}/{slug}.md": PARAGRAPH}
    out = _막혔다(저장소.staged(files))
    assert f"{FEATURES}/{slug}.md" in out


@pytest.mark.parametrize("slug", ["harness", "retro-queue"])
def test_기능이_아닌_폴더는_끝_줄과_제품_변경이_함께여도_단락을_묻지_않는다(
    저장소: Repo, slug: str
) -> None:
    files = {
        f".scratch/{slug}/plan.md": PLAN + END,
        f".scratch/{slug}/issues/01-x.md": "# 01\n\n**Status:** done\n",
        "src/app.py": "A = 2\n",
    }
    _지났다(저장소.staged(files))


def test_이미_있던_끝_줄을_둔_채_계획을_고치는_것은_기능_단락을_다시_묻지_않는다(
    저장소: Repo,
) -> None:
    저장소.commit({".scratch/plain/plan.md": PLAN + END})
    _지났다(저장소.staged({".scratch/plain/plan.md": PLAN + END + "\n덧붙임\n"}))


def test_끝_줄을_지우는_변경은_기능_단락을_묻지_않는다(저장소: Repo) -> None:
    저장소.commit({".scratch/feat/plan.md": PLAN + END, f"{FEATURES}/feat.md": PARAGRAPH})
    _지났다(저장소.staged({".scratch/feat/plan.md": PLAN}))


def test_기능_계획이_아닌_plan_md는_끝_줄을_보지_않는다(저장소: Repo) -> None:
    _지났다(
        저장소.staged(
            {
                ".scratch/plan.md": PLAN + END,
                ".scratch/harness/plan.md": PLAN + END,
                ".scratch/feat/sub/plan.md": PLAN + END,
            }
        )
    )


def test_끝_줄은_줄_머리에_있을_때만_읽는다(저장소: Repo) -> None:
    _지났다(저장소.staged({".scratch/feat/plan.md": PLAN + "\n설명 **끝:** 2026-11-15\n"}))


def test_한_PR의_제품_변경과_끝_줄이_다른_커밋에_나뉘면_커밋_검사는_놓치고_CI가_잡는다(
    저장소: Repo,
) -> None:
    저장소.commit({"src/app.py": "A = 2\n"})
    저장소.commit({".scratch/fresh/issues/01-f.md": "# 01\n\n**Status:** done\n"})
    # 끝 줄을 싣는 커밋의 스테이지 변경에는 제품 경로가 없고, 지난 커밋 어느 것도 제품과 이 기능의
    # 티켓을 함께 고치지 않았다
    _지났다(저장소.staged({".scratch/fresh/plan.md": PLAN + END}))
    저장소.git("commit", "-q", "-m", "끝")
    out = _막혔다(저장소.ci("feat: 기능을 더한다 (#1)"), PR_BLOCKED)
    assert f"{FEATURES}/fresh.md" in out


def test_티켓과_제품_변경을_다른_커밋에_나눠_고친_기능은_커밋_검사가_단락을_막고_CI는_지난다(
    저장소: Repo,
) -> None:
    저장소.commit({"src/app.py": "A = 2\n"})
    저장소.commit({".scratch/fresh/issues/01-f.md": "# 01\n\n**Status:** done\n"})
    # 제품 변경의 정의는 티켓 파일을 고친 커밋 가운데 제품 경로도 고친 것이 있는가다. 둘이 다른
    # 커밋에 있으면 커밋 검사는 담지 않은 기능으로 읽는다. CI 는 PR 의 변경 전체에서 둘을 함께 본다
    files = {".scratch/fresh/plan.md": PLAN + END, f"{FEATURES}/fresh.md": PARAGRAPH}
    out = _막혔다(저장소.staged(files))
    assert "제품 경로를 고친 적이 없는데" in out, f"막는 글이 다른 까닭이다: {out}"
    저장소.git("commit", "-q", "-m", "끝")
    _지났다(저장소.ci("feat: 기능을 더한다 (#1)"))


def test_병합_커밋은_커밋_검사가_보지_않고_알린다(저장소: Repo) -> None:
    # 다른 기능이 main 에서 끝났다. 그 기능 단락을 들여오는 병합은 이 브랜치의 이력에 그 기능의
    # 제품 변경이 없어도 막히지 않는다
    저장소.push_main(
        {"src/app.py": "A = 3\n", ".scratch/feat/issues/02-b.md": "# 02\n\n**Status:** done\n"}
    )
    저장소.push_main({".scratch/feat/plan.md": PLAN + END, f"{FEATURES}/feat.md": PARAGRAPH})
    저장소.git("merge", "-q", "--no-commit", "--no-ff", "origin/main")
    out = _지났다(저장소.run())
    assert "병합" in out


def test_기준_브랜치를_병합해_들여온_제품_변경도_기능이_담은_것으로_센다(저장소: Repo) -> None:
    # 리뷰 반영 중 base 를 머리 브랜치에 병합하는 흐름이다. 기능 `fresh` 의 제품 변경은 main 에서
    # 이 브랜치가 딴 뒤에 들어왔고, 이 브랜치에는 병합 커밋의 둘째 부모로만 있다
    저장소.push_main(
        {"src/app.py": "A = 4\n", ".scratch/fresh/issues/01-f.md": "# 01\n\n**Status:** done\n"}
    )
    저장소.git("merge", "-q", "--no-ff", "-m", "병합", "origin/main")
    out = _막혔다(
        저장소.ci("feat: 기능을 마친다 (#1)", files={".scratch/fresh/plan.md": PLAN + END}),
        PR_BLOCKED,
    )
    assert f"{FEATURES}/fresh.md" in out


def test_병합_커밋이_들여온_제품_변경과_티켓_변경을_한_커밋으로_세지_않는다(저장소: Repo) -> None:
    # main 에서 제품 변경과 티켓 변경이 따로 들어왔다. 병합 커밋의 합친 변경에는 둘이 함께
    # 보이지만, 어느 커밋도 둘을 함께 고치지 않았으므로 이 기능이 제품 변경을 담은 것이 아니다
    저장소.push_main({"src/app.py": "A = 5\n"})
    저장소.push_main({".scratch/fresh/issues/01-f.md": "# 01\n\n**Status:** done\n"})
    저장소.git("merge", "-q", "--no-ff", "-m", "병합", "origin/main")
    _지났다(저장소.ci("docs: 기능을 마친다 (#1)", files={".scratch/fresh/plan.md": PLAN + END}))


def test_CI가_끝_줄과_기능_단락의_빠뜨림을_잡는다(저장소: Repo) -> None:
    out = _막혔다(
        저장소.ci("feat: 기능을 마친다 (#1)", files={".scratch/feat/plan.md": PLAN + END}),
        PR_BLOCKED,
    )
    assert f"{FEATURES}/feat.md" in out


# --- (가) 느낌표와 할 일 ------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "기능을 더한다",
        "feature: 기능을 더한다",
        "feat 기능을 더한다",
        "feat:기능을 더한다",
        "feat: ",
        "Feat: 기능을 더한다",
    ],
)
def test_커밋_제목의_꼴이_아닌_PR_제목은_막는다(저장소: Repo, title: str) -> None:
    result = 저장소.ci(title, files={"README.md": "다시\n"})
    _막혔다(result, PR_BLOCKED)


@pytest.mark.parametrize(
    "title",
    [
        "feat: 기능을 더한다 (#1)",
        "fix(web): 화면을 고친다",
        "chore(a/b.c d): 자리",
        "docs: " + "길" * 120,
        "feat: 끝에 마침표.",
        'Revert "feat: 기능을 더한다"',
        "Merge branch 'dev'",
        "fixup! feat: 기능",
        "squash! feat: 기능",
    ],
)
def test_꼴에_맞거나_통과_접두인_PR_제목은_받는다(저장소: Repo, title: str) -> None:
    # 길이 상한과 끝 마침표는 보지 않고, 통과 접두는 느낌표가 없는 제목으로 읽는다
    _지났다(저장소.ci(title, files={"README.md": "다시\n"}))


def test_느낌표가_있는데_할_일_파일이_없으면_막는다(저장소: Repo) -> None:
    out = _막혔다(저장소.ci("feat!: 설정 칸이 바뀐다", files={"src/app.py": "A = 2\n"}), PR_BLOCKED)
    assert UPGRADE in out


def test_느낌표와_할_일_파일과_제품_변경이_맞으면_지난다(저장소: Repo) -> None:
    _지났다(
        저장소.ci(
            "feat!: 설정 칸이 바뀐다",
            files={"src/app.py": "A = 2\n", f"{UPGRADE}/rename.md": UPGRADE_TEXT},
        )
    )


@pytest.mark.parametrize("title", ["feat(web)!: 화면이 바뀐다", "fix!: 값이 바뀐다"])
def test_범위가_있는_느낌표도_읽는다(저장소: Repo, title: str) -> None:
    _막혔다(저장소.ci(title, files={"src/app.py": "A = 2\n"}), PR_BLOCKED)


def test_느낌표가_있어도_제품_경로를_고치지_않았으면_막는다(저장소: Repo) -> None:
    out = _막혔다(
        저장소.ci("docs!: 설명이 바뀐다", files={f"{UPGRADE}/rename.md": UPGRADE_TEXT}),
        PR_BLOCKED,
    )
    assert "제품" in out


@pytest.mark.parametrize("path", ["src/x.py", "pyproject.toml", "uv.lock", "deploy/x"])
def test_제품_경로_넷이_모두_제품_변경이다(저장소: Repo, path: str) -> None:
    _지났다(
        저장소.ci(
            "feat!: 바뀐다",
            files={path: "x\n", f"{UPGRADE}/rename.md": UPGRADE_TEXT},
        )
    )


@pytest.mark.parametrize("path", ["README.md", "docs/x.md", "compose.test.yml", "compose.eval.yml"])
def test_제품_경로가_아닌_파일만_고치면_느낌표를_받지_않는다(저장소: Repo, path: str) -> None:
    out = _막혔다(
        저장소.ci(
            "feat!: 바뀐다",
            files={path: "x\n", f"{UPGRADE}/rename.md": UPGRADE_TEXT},
        ),
        PR_BLOCKED,
    )
    assert "제품" in out


def test_느낌표가_없는데_할_일_파일을_새로_더하면_막는다(저장소: Repo) -> None:
    out = _막혔다(
        저장소.ci(
            "feat: 설정 칸이 바뀐다",
            files={"src/app.py": "A = 2\n", f"{UPGRADE}/rename.md": UPGRADE_TEXT},
        ),
        PR_BLOCKED,
    )
    assert f"{UPGRADE}/rename.md" in out


def test_있던_할_일_파일을_고치는_것은_느낌표가_없어도_된다(저장소: Repo) -> None:
    저장소.push_main({f"{UPGRADE}/rename.md": UPGRADE_TEXT})
    저장소.git("merge", "-q", "--ff-only", "origin/main")
    _지났다(저장소.ci("fix: 문구를 고친다", files={f"{UPGRADE}/rename.md": UPGRADE_TEXT + "더\n"}))


@pytest.mark.parametrize("name", ["sub/rename.md", "rename.txt"])
def test_할_일_폴더_아래의_하위_폴더_파일과_md가_아닌_파일도_새로_더한_것으로_센다(
    저장소: Repo, name: str
) -> None:
    # 릴리스를 내는 도구가 그 폴더 아래에 더한 파일을 모두 노트에 싣기 때문이다
    out = _막혔다(저장소.ci("feat: 바뀐다", files={f"{UPGRADE}/{name}": UPGRADE_TEXT}), PR_BLOCKED)
    assert f"{UPGRADE}/{name}" in out
    # 느낌표를 붙여 (가)를 채워도 (다)가 원고가 아닌 파일로 막는다
    out = _막혔다(저장소.ci("feat!: 바뀐다", files={"src/app.py": "A = 2\n"}), PR_BLOCKED)
    assert "업그레이드 원고가 아니다" in out
    assert f"{UPGRADE}/{name}" in out


def test_할_일_파일을_다른_이름으로_옮기면_새로_더한_것으로_세어_막는다(저장소: Repo) -> None:
    # 이름 바꾸기는 지운 것과 더한 것 둘로 센다(독스트링의 못 보는 것)
    저장소.push_main({f"{UPGRADE}/old.md": UPGRADE_TEXT})
    저장소.git("merge", "-q", "--ff-only", "origin/main")
    저장소.git("mv", f"{UPGRADE}/old.md", f"{UPGRADE}/new.md")
    저장소.git("commit", "-q", "-m", "옮김")
    out = _막혔다(저장소.ci("fix: 이름을 바꾼다"), PR_BLOCKED)
    assert f"{UPGRADE}/new.md" in out


def test_제품_경로_밖의_도구와_시험만_고치면_느낌표를_받지_않는다(저장소: Repo) -> None:
    out = _막혔다(
        저장소.ci(
            "chore!: 도구가 바뀐다",
            files={"tools/x.py": "x\n", "tests/x.py": "x\n", f"{UPGRADE}/rename.md": UPGRADE_TEXT},
        ),
        PR_BLOCKED,
    )
    assert "제품" in out


def test_단락의_내용은_보지_않아_경로와_ADR_번호가_든_단락도_지난다() -> None:
    # 운영자의 말로 썼는지는 리뷰의 몫이다(독스트링의 못 보는 것)
    assert (
        check_notes.fragment_problems(
            f"{FEATURES}/a.md", "src/rag_engine/x.py 와 docs/adr 의 ADR 0020 을 고쳤다.\n"
        )
        == []
    )


def test_기능_단락은_앞쪽의_빈_줄도_막는다() -> None:
    assert check_notes.fragment_problems(f"{FEATURES}/a.md", "\n첫 줄\n")


def test_얕은_체크아웃은_merge_base를_못_찾아_종료_2다(저장소: Repo) -> None:
    저장소.commit({"README.md": "다시\n"})
    shallow = 저장소.tmp / "shallow"
    저장소.git(
        "clone", "-q", "--depth", "1", "--no-single-branch", 저장소.work.as_uri(), str(shallow),
        cwd=저장소.tmp,
    )  # fmt: skip
    result = subprocess.run(
        [sys.executable, str(CHECK), "--ci"],
        cwd=shallow,
        env={
            **저장소.env,
            "GITHUB_EVENT_NAME": "pull_request",
            "PR_HEAD_REF": "feature/x",
            "PR_HEAD_SHA": 저장소.git("rev-parse", "HEAD"),
            "PR_BASE_SHA": 저장소.git("rev-parse", "origin/main"),
            "PR_TITLE": "fix: 고친다",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "얕" in result.stderr


def test_PR에서_더한_뒤_같은_PR에서_지운_할_일_파일은_새로_더한_것이_아니다(저장소: Repo) -> None:
    저장소.commit({f"{UPGRADE}/rename.md": UPGRADE_TEXT})
    저장소.git("rm", "-q", f"{UPGRADE}/rename.md")
    저장소.git("commit", "-q", "-m", "지움")
    _지났다(저장소.ci("fix: 고친다"))


def test_머리가_main이나_dev인_PR은_건너뛴다(저장소: Repo) -> None:
    저장소.commit({f"{FEATURES}/nothing.md": "첫\n\n둘째\n"})
    for head_ref in ("main", "dev"):
        _지났다(저장소.ci("느낌표도 꼴도 없다", head_ref=head_ref))


def test_PR이_아닌_실행은_알리고_지난다(저장소: Repo) -> None:
    result = 저장소.run("--ci", extra={"GITHUB_EVENT_NAME": "push", "PR_HEAD_REF": ""})
    out = _지났다(result)
    assert "PR 이 아닌" in out


@pytest.mark.parametrize("mode", ["--ci", "--title-only"])
def test_PR_실행인데_제목이_비면_git_실패와_같은_종료_2다(저장소: Repo, mode: str) -> None:
    저장소.commit({"README.md": "다시\n"})
    result = 저장소.run(
        mode,
        extra={
            "GITHUB_EVENT_NAME": "pull_request",
            "PR_HEAD_REF": "feature/x",
            "PR_HEAD_SHA": 저장소.git("rev-parse", "HEAD"),
            "PR_BASE_SHA": 저장소.git("rev-parse", "origin/main"),
            "PR_TITLE": "",
        },
    )
    assert result.returncode == 2
    assert "PR_TITLE" in result.stderr


def test_CI_모드는_받은_커밋을_못_찾으면_종료_2다(저장소: Repo) -> None:
    result = 저장소.run(
        "--ci",
        extra={
            "GITHUB_EVENT_NAME": "pull_request",
            "PR_HEAD_REF": "feature/x",
            "PR_HEAD_SHA": "0" * 40,
            "PR_BASE_SHA": 저장소.git("rev-parse", "origin/main"),
            "PR_TITLE": "feat: 기능",
        },
    )
    assert result.returncode == 2


# --- (가) 마이그레이션 파일을 고친 PR의 느낌표 ---------------------------------------------

MIGRATION = f"{VERSIONS}/0004_add_column.py"
MIGRATION_TEXT = 'revision = "0004"\n'


def _마이그레이션이_있는_저장소(저장소: Repo) -> Repo:
    """main 에 마이그레이션 파일이 이미 있고, 작업 브랜치가 그것을 받은 상태."""
    저장소.push_main({MIGRATION: MIGRATION_TEXT})
    저장소.git("merge", "-q", "--ff-only", "origin/main")
    return 저장소


def test_마이그레이션을_더하고_느낌표가_없으면_막는다(저장소: Repo) -> None:
    out = _막혔다(저장소.ci("feat: 열을 더한다", files={MIGRATION: MIGRATION_TEXT}), PR_BLOCKED)
    assert MIGRATION in out
    assert "느낌표" in out


def test_마이그레이션을_고치고_느낌표가_없으면_막는다(저장소: Repo) -> None:
    저장소 = _마이그레이션이_있는_저장소(저장소)
    out = _막혔다(
        저장소.ci("fix: 열을 고친다", files={MIGRATION: MIGRATION_TEXT + "#\n"}), PR_BLOCKED
    )
    assert MIGRATION in out


def test_마이그레이션을_지우고_느낌표가_없으면_막는다(저장소: Repo) -> None:
    저장소 = _마이그레이션이_있는_저장소(저장소)
    저장소.git("rm", "-q", MIGRATION)
    저장소.git("commit", "-q", "-m", "지움")
    out = _막혔다(저장소.ci("fix: 열을 지운다"), PR_BLOCKED)
    assert MIGRATION in out


def test_마이그레이션을_옮기면_옛_경로와_새_경로를_모두_본다(저장소: Repo) -> None:
    # 이름 바꾸기는 지운 것과 더한 것 둘이다. 폴더 안에서 이름만 바꿔도 막는다
    저장소 = _마이그레이션이_있는_저장소(저장소)
    renamed = f"{VERSIONS}/0004_renamed.py"
    저장소.git("mv", MIGRATION, renamed)
    저장소.git("commit", "-q", "-m", "옮김")
    out = _막혔다(저장소.ci("refactor: 이름을 바꾼다"), PR_BLOCKED)
    assert MIGRATION in out, f"옛 경로 {MIGRATION} 가 출력에 없다"
    assert renamed in out, f"새 경로 {renamed} 가 출력에 없다"


@pytest.mark.parametrize("destination", ["src/elsewhere.py", "moved.py"])
def test_마이그레이션을_폴더_밖으로_옮기면_옛_경로로_막는다(저장소: Repo, destination: str) -> None:
    저장소 = _마이그레이션이_있는_저장소(저장소)
    저장소.git("mv", MIGRATION, destination)
    저장소.git("commit", "-q", "-m", "옮김")
    out = _막혔다(저장소.ci("refactor: 옮긴다"), PR_BLOCKED)
    assert MIGRATION in out


def test_마이그레이션을_폴더_안으로_옮겨_들이면_새_경로로_막는다(저장소: Repo) -> None:
    저장소.push_main({"src/outside.py": MIGRATION_TEXT})
    저장소.git("merge", "-q", "--ff-only", "origin/main")
    (저장소.work / VERSIONS).mkdir(parents=True)
    저장소.git("mv", "src/outside.py", MIGRATION)
    저장소.git("commit", "-q", "-m", "옮김")
    out = _막혔다(저장소.ci("refactor: 옮겨 들인다"), PR_BLOCKED)
    assert MIGRATION in out


def test_마이그레이션과_느낌표와_할_일_파일이_맞으면_지난다(저장소: Repo) -> None:
    _지났다(
        저장소.ci(
            "feat!: 열이 늘어난다",
            files={MIGRATION: MIGRATION_TEXT, f"{UPGRADE}/backup.md": UPGRADE_TEXT},
        )
    )


def test_마이그레이션이_있어도_느낌표가_있고_할_일_파일이_없으면_막는다(저장소: Repo) -> None:
    out = _막혔다(저장소.ci("feat!: 열이 늘어난다", files={MIGRATION: MIGRATION_TEXT}), PR_BLOCKED)
    assert UPGRADE in out


def test_마이그레이션이_범위_있는_제목의_느낌표로도_지난다(저장소: Repo) -> None:
    _지났다(
        저장소.ci(
            "feat(db)!: 열이 늘어난다",
            files={MIGRATION: MIGRATION_TEXT, f"{UPGRADE}/backup.md": UPGRADE_TEXT},
        )
    )


@pytest.mark.parametrize(
    "path",
    [
        f"{VERSIONS}/note.txt",
        f"{VERSIONS}/README.md",
        "src/rag_engine/adapters/postgres/migrations/env.py",
        "src/rag_engine/adapters/postgres/migrations/script.py.mako",
        "tests/adapters/test_migrations.py",
    ],
)
def test_versions_밖이거나_py가_아닌_파일은_마이그레이션이_아니다(저장소: Repo, path: str) -> None:
    _지났다(저장소.ci("fix: 고친다", files={path: "x\n"}))


@pytest.mark.parametrize("head_ref", ["dev", "main"])
def test_출시_PR과_운영에서_개발로_합치기_PR은_마이그레이션이_있어도_면제한다(
    저장소: Repo, head_ref: str
) -> None:
    # 머리가 dev 인 출시 PR 과 머리가 main 인 합치기 PR 은 제목이 번호의 원천이 아니다
    _지났다(저장소.ci("느낌표가 없다", files={MIGRATION: MIGRATION_TEXT}, head_ref=head_ref))


def test_핫픽스_PR은_마이그레이션이_있으면_느낌표를_요구한다(저장소: Repo) -> None:
    _막혔다(
        저장소.ci(
            "fix: 열을 바로잡는다", files={MIGRATION: MIGRATION_TEXT}, head_ref="hotfix/column"
        ),
        PR_BLOCKED,
    )
    _지났다(
        저장소.ci(
            "fix!: 열을 바로잡는다",
            files={f"{UPGRADE}/backup.md": UPGRADE_TEXT},
            head_ref="hotfix/column",
        )
    )


def test_제목만_고친_실행도_마이그레이션과_느낌표의_짝을_본다(저장소: Repo) -> None:
    저장소.commit({MIGRATION: MIGRATION_TEXT})
    _막혔다(저장소.ci("feat: 열을 더한다", mode="--title-only"), PR_BLOCKED)


def test_제목만_고친_실행도_마이그레이션_PR의_머리가_main이면_건너뛴다(저장소: Repo) -> None:
    저장소.commit({MIGRATION: MIGRATION_TEXT})
    _지났다(저장소.ci("feat: 열을 더한다", head_ref="main", mode="--title-only"))


def test_같은_PR에서_더한_뒤_지운_마이그레이션은_바뀐_파일이_아니다(저장소: Repo) -> None:
    저장소.commit({MIGRATION: MIGRATION_TEXT})
    저장소.git("rm", "-q", MIGRATION)
    저장소.git("commit", "-q", "-m", "지움")
    _지났다(저장소.ci("fix: 고친다"))


def test_커밋_검사는_PR_제목을_몰라_마이그레이션의_느낌표를_묻지_않는다(저장소: Repo) -> None:
    _지났다(저장소.staged({MIGRATION: MIGRATION_TEXT}))


def test_느낌표가_없는_통과_접두_제목도_마이그레이션이_있으면_막는다(저장소: Repo) -> None:
    # `Revert "…"` 같은 통과 접두는 느낌표가 없는 제목으로 읽는다
    _막혔다(
        저장소.ci('Revert "feat: 열을 더한다"', files={MIGRATION: MIGRATION_TEXT}),
        PR_BLOCKED,
    )


def test_versions_아래_하위_폴더의_py도_마이그레이션으로_센다(저장소: Repo) -> None:
    # 독스트링의 못 보는 것: 경로만 보고 하위 폴더도 센다
    nested = f"{VERSIONS}/archive/0001_old.py"
    out = _막혔다(저장소.ci("fix: 정리한다", files={nested: "x\n"}), PR_BLOCKED)
    assert nested in out


def test_마이그레이션_판정은_글을_보지_않고_경로만_본다(저장소: Repo) -> None:
    # 독스트링의 못 보는 것: 빈 파일이어도 마이그레이션 경로면 걸린다
    _막혔다(저장소.ci("fix: 정리한다", files={MIGRATION: ""}), PR_BLOCKED)


def test_재색인이나_계약_앞자리를_올리는_변경은_기계가_알아보지_않아_지난다(저장소: Repo) -> None:
    # 독스트링의 못 보는 것: 제품 경로만 고친 변경은 제목에 느낌표가 없어도 지난다
    _지났다(저장소.ci("feat: 색인 판의 요소를 바꾼다", files={"src/app.py": "A = 9\n"}))


def test_마이그레이션_폴더의_경로는_alembic_폴더_설정과_같다() -> None:
    # 도구는 alembic 을 import 하지 않으려고 경로를 글자로 둔다. 그 글자가 실제 폴더와 같아야 한다
    real = (MIGRATIONS_DIRECTORY / "versions").relative_to(ROOT).as_posix()
    assert check_notes.MIGRATION_VERSIONS == real
    assert any((ROOT / real).glob("*.py")), "마이그레이션 파일이 없으면 경로가 틀린 것이다"


# --- 부르는 자리: 검사 러너, ci.yml, PR 제목 워크플로 ---------------------------------------


def test_커밋_전_검사_러너가_노트_검사를_돈다() -> None:
    commands = {check.id: check.command for check in CHECKS}
    expected = ("uv", "run", "python", "tools/check_notes.py")
    found = commands.get("check-notes")
    assert found == expected, f"check-notes 항목의 명령이 {found} 이다"


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def _active(name: str) -> str:
    """워크플로에서 주석을 걷어 낸 글. 주석으로 꺼 둔 줄은 CI 가 돌리지 않으므로 세지 않는다."""
    lines: list[str] = []
    for line in _workflow(name).splitlines():
        code = line.split(" #", 1)[0].rstrip()
        if code.strip() and not code.lstrip().startswith("#"):
            lines.append(code)
    return "\n".join(lines)


@pytest.mark.parametrize(
    ("name", "command"),
    [
        ("ci.yml", "python3 tools/check_notes.py --ci"),
        ("pr-title.yml", "python3 tools/check_notes.py --title-only"),
    ],
)
def test_워크플로가_노트_검사를_부르고_제목을_환경_변수로_넘긴다(name: str, command: str) -> None:
    text = _active(name)
    assert command in text, f"{name} 에 {command} 가 없다"
    # 검사를 부르는 스텝 자신의 env 가 제목을 받아야 한다. 다른 스텝의 env 로 옮기면 빈 제목을 본다
    step = next(part for part in text.split("\n      - ") if command in part)
    variable, expression = "PR_TITLE", "${{ github.event.pull_request.title }}"
    assert f"{variable}: {expression}" in step, f"노트 검사 스텝의 env 에 {variable} 가 없다"
    # 제목을 식으로 명령에 펼치면 그 안의 명령이 실행될 수 있다(zizmor 의 template-injection)
    expressions = [line for line in text.splitlines() if "github.event.pull_request.title" in line]
    assert expressions, "워크플로가 PR 제목을 넘기지 않는다"
    inline = [line for line in expressions if not line.strip().startswith("PR_TITLE:")]
    assert not inline, f"PR 제목을 {len(inline)}곳에서 env 밖으로 펼쳤다"


def test_PR_제목_워크플로는_제목을_고칠_때만_돌고_필수_검사가_아니다() -> None:
    text = _active("pr-title.yml")
    types = [line.strip() for line in text.splitlines() if line.strip().startswith("types:")]
    assert types == ["types: [edited]"], f"types 줄이 {types} 이다"
    # ci.yml 의 verify 가 기다리는 잡에 들지 않는다. 필수 검사로 두면 제목을 고치지 않은 PR 이
    # 결과를 기다리며 병합이 대기한다
    assert "pr-title" not in _workflow("ci.yml").split("verify:", 1)[1]


# --- 원고 폴더가 없어도 돈다 ----------------------------------------------------------------


def test_원고_폴더가_하나도_없는_저장소에서도_세_모드가_돈다(저장소: Repo) -> None:
    assert not (저장소.work / "docs" / "release-notes").exists()
    _지났다(저장소.run())
    _지났다(저장소.ci("fix: 고친다", files={"src/app.py": "A = 2\n"}))
    _지났다(저장소.ci("fix: 고친다", mode="--title-only"))


# --- 작은 워크플로: 제목만 다시 본다 -----------------------------------------------------


def test_제목만_고친_실행은_느낌표와_할_일만_본다(저장소: Repo) -> None:
    files = {f"{FEATURES}/nothing.md": "첫\n\n둘째\n"}
    # 모양과 기능 단락의 빠뜨림은 보지 않는다
    _지났다(저장소.ci("feat: 기능을 더한다", files=files, mode="--title-only"))
    _막혔다(저장소.ci("꼴이 아니다", mode="--title-only"), PR_BLOCKED)


def test_제목만_고친_실행도_느낌표와_할_일_파일의_짝을_본다(저장소: Repo) -> None:
    저장소.commit({"src/app.py": "A = 2\n"})
    _막혔다(저장소.ci("feat!: 바뀐다", mode="--title-only"), PR_BLOCKED)


def test_제목만_고친_실행도_머리가_main이면_건너뛴다(저장소: Repo) -> None:
    _지났다(저장소.ci("꼴이 아니다", head_ref="main", mode="--title-only"))


# --- 커밋 검사 모드 -----------------------------------------------------------------


def test_커밋_검사는_PR_제목을_보지_않아_느낌표_짝을_묻지_않는다(저장소: Repo) -> None:
    _지났다(저장소.staged({f"{UPGRADE}/rename.md": UPGRADE_TEXT, "src/app.py": "A = 2\n"}))


def test_main과_dev_위의_커밋은_지난다(저장소: Repo) -> None:
    저장소.git("switch", "-q", "main")
    _지났다(저장소.staged({f"{FEATURES}/nothing.md": "첫\n\n둘째\n"}))


def test_바꾼_것이_없으면_지난다(저장소: Repo) -> None:
    _지났다(저장소.run())


def test_저장소가_아닌_폴더는_종료_2다(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK), str(tmp_path)],
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
        check=False,
    )
    assert result.returncode == 2
    assert result.stderr.startswith("check-notes: ")


def test_두_모드를_함께_주면_사용법_오류다(저장소: Repo) -> None:
    result = 저장소.run("--ci", "--title-only")
    assert result.returncode == 2


def test_막는_글은_규약_원천을_든다(저장소: Repo) -> None:
    out = _막혔다(저장소.staged({f"{FEATURES}/nothing.md": PARAGRAPH}))
    assert "docs/constitution/operations.md" in out
    assert out.startswith("check-notes: ")
