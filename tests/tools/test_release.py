"""tools/release.py 의 시험. 번호·노트·배포 파일 묶음·번호 태그 판정.

번호와 노트는 임시 git 저장소에 커밋과 태그를 만들어 넣고 읽는다(선례 test_check_ticket.py).
번호 태그 판정의 입력은 `docker buildx imagetools inspect` 의 출력 꼴이다. agent-os 저장소가
2026-11-16 에 로컬 레지스트리로 조회해 적어 둔 꼴을 옮겼고, 이 저장소에서는 다시 조회하지 않았다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from tools.check_commit_msg import PATTERN
from tools.release import (
    PRODUCT_PATHS,
    ReleaseError,
    TagVerdict,
    build_bundle,
    classify,
    ensure_untaken,
    judge_number_tag,
    main,
    plan_release,
    render_notes,
)
from tools.run_hooks import REPO_LOCATION_VARS

_GIT_TIMEOUT = 120
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
# `rag-engine --version` 의 둘째 줄부터와 같은 꼴이다(`src/rag_engine/main.py` 의 `version_lines`).
CONTRACT = (
    "검색 도구의 형식 1.1.0\n"
    "수집 API와 관리 API의 경로 v1\n"
    "파서 인터페이스 1.0.0\n"
    "색인 형식의 스키마 1\n"
)
CONTRACT_SECTION = f"## 계약의 판\n\n```text\n{CONTRACT}```"


def _계약_파일(tmp_path: Path) -> Path:
    target = tmp_path / "계약의_판.txt"
    target.write_text(CONTRACT, encoding="utf-8", newline="\n")
    return target


class Repo:
    """임시 git 저장소. 커밋마다 겹치지 않는 내용을 쓴다."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.count = 0

    def git(self, *args: str) -> str:
        done = subprocess.run(
            [
                "git",
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@example.com",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=self.path,
            env={k: v for k, v in os.environ.items() if k not in REPO_LOCATION_VARS},
            capture_output=True,
            check=True,
            encoding="utf-8",
            timeout=_GIT_TIMEOUT,
        )
        return done.stdout.strip()

    def commit(self, subject: str, files: dict[str, str] | None = None) -> str:
        self.count += 1
        for name, text in (files if files is not None else {"docs/n.md": str(self.count)}).items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", subject)
        return self.git("rev-parse", "HEAD")

    def product(self, subject: str, files: dict[str, str] | None = None) -> str:
        """제품 경로(`src/`)를 고치는 커밋."""
        merged = {f"src/p{self.count + 1}.py": "x"}
        merged.update(files or {})
        return self.commit(subject, merged)

    def tag(self, name: str, rev: str = "HEAD") -> None:
        self.git("tag", name, rev)

    def config(self, text: str) -> None:
        target = self.path / "deploy" / "release.toml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    made = Repo(tmp_path / "repo")
    made.commit("chore: 시작", {"README.md": "x"})
    return made


def _number(repo: Repo) -> str | None:
    return plan_release(repo.path).number


# ---------- 번호 ----------


def test_태그_없이_출시_후보_칸만_있으면_rc_1이다(repo: Repo) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    repo.product("feat: 첫 기능 (#1)")
    plan = plan_release(repo.path)
    assert plan.release is True
    assert plan.number == "0.1.0-rc.1"
    assert plan.tag == "v0.1.0-rc.1"
    assert plan.previous_tag is None


def test_출시_후보가_있으면_다음_차례로_오른다(repo: Repo) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0-rc.1")
    repo.product("fix: 고친다 (#2)")
    plan = plan_release(repo.path)
    assert plan.number == "0.1.0-rc.2"
    assert plan.previous_tag == "v0.1.0-rc.1"
    assert [commit.subject for commit in plan.commits] == ["fix: 고친다 (#2)"]


def test_출시_후보의_차례는_가장_큰_n에서_이어진다(repo: Repo) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    repo.product("feat: 하나 (#1)")
    repo.tag("v0.1.0-rc.1")
    repo.product("fix: 둘 (#2)")
    repo.tag("v0.1.0-rc.2")
    repo.product("fix: 셋 (#3)")
    repo.tag("v0.1.0-rc.10")
    repo.product("fix: 넷 (#4)")
    assert _number(repo) == "0.1.0-rc.11"


def test_칸을_지운_뒤_지난_릴리스가_출시_후보면_정식_릴리스다(repo: Repo) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0-rc.2")
    repo.config("")
    repo.commit("chore: 칸을 지운다", {"deploy/release.toml": ""})
    assert _number(repo) == "0.1.0"


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("fix: 고친다 (#2)", "0.1.1"),
        ("chore: 손본다 (#2)", "0.1.1"),
        ("docs(adr): 적는다 (#2)", "0.1.1"),
        ('Revert "feat: 되돌린다"', "0.1.1"),
        ("feat: 더한다 (#2)", "0.2.0"),
        ("feat(core): 범위가 붙은 기능 (#2)", "0.2.0"),
        ("fix!: 깨뜨리며 고친다 (#2)", "0.2.0"),
        ("chore(deploy)!: 설정 칸을 바꾼다 (#2)", "0.2.0"),
    ],
)
def test_정식_릴리스_뒤의_제목이_다음_번호를_정한다(
    repo: Repo, subject: str, expected: str
) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product(subject)
    assert _number(repo) == expected


def test_맨_앞자리는_느낌표로도_오르지_않는다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v1.2.3")
    repo.product("feat!: 크게 바꾼다 (#2)")
    assert _number(repo) == "1.3.0"


def test_72자를_넘는_feat_제목도_가운데_자리를_올린다(repo: Repo) -> None:
    repo.product("fix: 앞 (#1)")
    repo.tag("v0.1.0")
    subject = "feat: " + "가" * 70 + " (#2)"
    assert len(subject) > 72
    repo.product(subject)
    assert _number(repo) == "0.2.0"


def test_제품_경로를_고치지_않은_커밋만_있으면_릴리스하지_않는다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.commit("feat: 문서에만 닿는다 (#2)", {"docs/guide.md": "g", "tools/x.py": "x"})
    repo.commit("fix: 릴리스 노트 원고만 더한다 (#3)", {"docs/release-notes/features/a.md": "단락"})
    plan = plan_release(repo.path)
    assert plan.release is False
    assert plan.number is None
    assert plan.previous_tag == "v0.1.0"


def test_제품_경로_넷이_모두_릴리스를_일으킨다(repo: Repo) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    repo.commit("chore: 설정", {"deploy/release.toml": 'candidate_for = "0.1.0"\n'})
    repo.tag("v0.1.0-rc.1")
    for index, path in enumerate(PRODUCT_PATHS):
        target = path if "." in path else f"{path}/f.txt"
        repo.commit(f"chore: 경로 {index}", {target: str(index)})
        assert plan_release(repo.path).release is True, path
        repo.tag(f"v0.1.0-rc.{index + 2}")
        repo.commit("chore: 문서만", {"docs/g.md": str(index)})
        assert plan_release(repo.path).release is False, path
    assert PRODUCT_PATHS == ("src", "pyproject.toml", "uv.lock", "deploy")


def test_pyproject_toml만_고친_커밋도_제품_변경이라_릴리스를_일으킨다(repo: Repo) -> None:
    """이미지를 짓는 입력이고 `[project.scripts]`처럼 잠금 파일이 따라 바뀌지 않는 칸이 있다."""
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.commit("chore: 진입점만 바꾼다 (#2)", {"pyproject.toml": "[project.scripts]\n"})
    plan = plan_release(repo.path)
    assert plan.release is True
    assert plan.number == "0.1.1"
    assert [commit.subject for commit in plan.commits] == ["chore: 진입점만 바꾼다 (#2)"]


@pytest.mark.parametrize("path", ["compose.test.yml", "compose.eval.yml", "README.md"])
def test_시험용_평가용_compose와_README만_고친_커밋은_제품_변경이_아니다(
    repo: Repo, path: str
) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.commit(f"chore: {path}만 고친다 (#2)", {path: "x"})
    plan = plan_release(repo.path)
    assert plan.release is False
    assert plan.commits == ()


def test_제품_경로를_고친_커밋만_범위에_든다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.commit("docs: 문서 (#2)", {"docs/a.md": "a"})
    repo.product("fix: 제품 (#3)")
    repo.commit("test: 도구 시험 (#4)", {"tests/t.py": "t"})
    plan = plan_release(repo.path)
    assert [commit.subject for commit in plan.commits] == ["fix: 제품 (#3)"]


def test_버전_태그가_하나도_없으면_저장소의_처음부터_본다(repo: Repo) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    repo.product("feat: 하나 (#1)")
    repo.product("fix: 둘 (#2)")
    plan = plan_release(repo.path)
    assert plan.previous_tag is None
    assert [commit.subject for commit in plan.commits] == ["feat: 하나 (#1)", "fix: 둘 (#2)"]


def test_버전_태그_꼴이_아닌_태그는_무시한다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    for name in (
        "v0.1",
        "v01.2.3",
        "0.9.0",
        "v0.1.0-rc.0",
        "v0.1.0-rc.01",
        "v9.9.9-beta",
        "release-9",
    ):
        repo.tag(name)
    repo.product("fix: 고친다 (#2)")
    plan = plan_release(repo.path)
    assert plan.previous_tag == "v0.1.0"
    assert plan.number == "0.1.1"


def test_유의적_버전의_차례로_지난_릴리스를_고른다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.9.0")
    repo.tag("v0.10.0")
    repo.tag("v0.10.0-rc.3")
    repo.product("fix: 고친다 (#2)")
    plan = plan_release(repo.path)
    assert plan.previous_tag == "v0.10.0"
    assert plan.number == "0.10.1"


def test_출시_병합과_되돌려_합치기를_거쳐도_핫픽스는_다시_실리지_않는다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.git("switch", "-q", "-c", "dev")
    repo.product("feat: 개발 쪽 기능 (#2)")
    repo.git("switch", "-q", "main")
    repo.product("fix: main 의 핫픽스 (#3)")
    repo.tag("v0.1.1")
    repo.git("switch", "-q", "dev")
    repo.git("merge", "-q", "--no-ff", "-m", "Merge main into dev", "main")
    repo.product("fix: 개발 쪽 고침 (#4)")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "-m", "Merge pull request #5 from dev", "dev")
    plan = plan_release(repo.path)
    assert [commit.subject for commit in plan.commits] == [
        "feat: 개발 쪽 기능 (#2)",
        "fix: 개발 쪽 고침 (#4)",
    ]
    assert plan.number == "0.2.0"


def test_출시_병합의_둘째_부모_쪽_커밋을_첫_부모만_따라가다_놓치지_않는다(repo: Repo) -> None:
    repo.tag("v0.0.1")
    repo.git("switch", "-q", "-c", "dev")
    repo.product("fix: 티켓 하나 (#1)")
    repo.product("fix: 티켓 둘 (#2)")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "-m", "Merge pull request #3 from dev", "dev")
    subjects = [commit.subject for commit in plan_release(repo.path).commits]
    assert subjects == ["fix: 티켓 하나 (#1)", "fix: 티켓 둘 (#2)"]


def test_바꾸고_되돌린_한_쌍도_둘_다_제품_변경이라_릴리스가_난다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)", {"src/q.py": "처음"})
    repo.tag("v0.1.0")
    repo.git("switch", "-q", "-c", "side")
    repo.commit("chore: 바꾼다 (#2)", {"src/q.py": "바뀜"})
    repo.commit("chore: 되돌린다 (#3)", {"src/q.py": "처음"})
    repo.git("switch", "-q", "main")
    repo.commit("docs: 문서 (#4)", {"docs/a.md": "a"})
    repo.git("merge", "-q", "--no-ff", "-m", "Merge pull request #5 from side", "side")
    subjects = [commit.subject for commit in plan_release(repo.path).commits]
    assert subjects == ["chore: 바꾼다 (#2)", "chore: 되돌린다 (#3)"]


# ---------- 구성 오류 ----------


def test_칸도_태그도_없으면_구성_오류다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    with pytest.raises(ReleaseError, match="출시 후보 칸"):
        plan_release(repo.path)


def test_칸이_지난_정식_릴리스보다_크지_않으면_구성_오류다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.config('candidate_for = "0.1.0"\n')
    repo.commit("chore: 칸을 적는다", {"deploy/release.toml": 'candidate_for = "0.1.0"\n'})
    with pytest.raises(ReleaseError, match="지난 정식 릴리스"):
        plan_release(repo.path)


def test_칸으로_계산한_출시_후보가_지난_릴리스보다_크지_않으면_구성_오류다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("feat: 둘 (#2)")
    repo.tag("v0.2.0-rc.1")
    repo.commit("chore: 칸을 적는다", {"deploy/release.toml": 'candidate_for = "0.1.1"\n'})
    with pytest.raises(ReleaseError, match="지난 릴리스보다"):
        plan_release(repo.path)


def test_계산한_태그가_이미_있으면_구성_오류다() -> None:
    ensure_untaken("v0.1.0-rc.2", ["v0.1.0-rc.1"])
    with pytest.raises(ReleaseError, match="이미 있다"):
        ensure_untaken("v0.1.0-rc.2", ["v0.1.0-rc.1", "v0.1.0-rc.2"])


def test_지난_릴리스가_조상이_아니면_구성_오류다(repo: Repo) -> None:
    repo.git("switch", "-q", "-c", "other")
    repo.product("feat: 다른 가지 (#1)")
    repo.tag("v0.1.0")
    repo.git("switch", "-q", "main")
    repo.product("fix: main 쪽 (#2)")
    with pytest.raises(ReleaseError, match="조상"):
        plan_release(repo.path)


@pytest.mark.parametrize(
    "text",
    [
        'candidate_for = "0.1.0"\nother = 1\n',
        'candidate_for = "0.1"\n',
        'candidate_for = "01.2.3"\n',
        'candidate_for = "0.1.0-rc.1"\n',
        'candidate_for = "v0.1.0"\n',
        "candidate_for = 1\n",
        'candidate_for = "0.1.0"\n[table]\nx = 1\n',
        "이건 toml 이 아니다 =\n",
    ],
)
def test_릴리스_설정_파일의_다른_칸과_틀린_꼴은_구성_오류다(repo: Repo, text: str) -> None:
    repo.commit("chore: 설정 (#1)", {"deploy/release.toml": text})
    with pytest.raises(ReleaseError, match="release.toml"):
        plan_release(repo.path)


def test_릴리스_설정_파일이_없거나_비면_칸이_없는_것이다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)")
    assert _number(repo) == "0.1.1"
    repo.commit("chore: 빈 설정 (#3)", {"deploy/release.toml": ""})
    assert _number(repo) == "0.1.1"


# ---------- 제목 읽기 ----------


def test_제목은_커밋_검사의_정규식으로만_읽는다() -> None:
    assert classify("feat: 더한다") == ("feat", False)
    assert classify("feat(core)!: 깬다") == ("feat", True)
    assert classify("fix!: 깬다") == ("fix", True)
    assert classify("chore(deploy): 손본다 (#9)") == ("chore", False)
    assert classify('Revert "feat!: 되돌린다"') == (None, False)
    assert classify("Merge branch x") == (None, False)
    assert classify("그냥 문장") == (None, False)
    # 길이와 끝 마침표는 보지 않는다(검사의 `PATTERN` 만으로 읽는다)
    assert classify("feat: " + "x" * 100 + ".") == ("feat", False)
    assert PATTERN.match("feat: " + "x" * 100) is not None


# ---------- 번호 도구의 출력 ----------


def test_번호_도구는_태그가_있을_때와_없을_때_지난_릴리스를_낸다(
    repo: Repo, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    repo.product("feat: 첫 기능 (#1)")
    assert main(["number", "--repo", str(repo.path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "release=true",
        "number=0.1.0-rc.1",
        "tag=v0.1.0-rc.1",
        "previous_tag=",
    ]
    repo.tag("v0.1.0-rc.1")
    repo.product("fix: 고친다 (#2)")
    assert main(["number", "--repo", str(repo.path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "release=true",
        "number=0.1.0-rc.2",
        "tag=v0.1.0-rc.2",
        "previous_tag=v0.1.0-rc.1",
    ]


def test_번호_도구는_릴리스하지_않아도_성공이고_구성_오류는_까닭과_함께_실패한다(
    repo: Repo, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.product("feat: 첫 기능 (#1)")
    assert main(["number", "--repo", str(repo.path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("release: ")
    assert "출시 후보 칸" in captured.err
    repo.tag("v0.1.0")
    repo.commit("docs: 문서만 (#2)", {"docs/a.md": "a"})
    assert main(["number", "--repo", str(repo.path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "release=false",
        "number=",
        "tag=",
        "previous_tag=v0.1.0",
    ]


def test_머리를_고르면_그_시점의_번호와_노트를_낸다(
    repo: Repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.config('candidate_for = "0.1.0"\n')
    first = repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0-rc.1")
    second = repo.product("fix: 고친다 (#2)")
    base = ["--repo", str(repo.path)]
    contract = ["--contract-versions", str(_계약_파일(tmp_path))]
    assert main(["number", *base, "--head", first]) == 0
    assert capsys.readouterr().out.splitlines()[:2] == ["release=false", "number="]
    assert main(["number", *base, "--head", second]) == 0
    assert "number=0.1.0-rc.2" in capsys.readouterr().out.splitlines()
    assert main(["notes", "--number", "0.1.0-rc.2", *base, *contract, "--head", second]) == 0
    assert "- 고친다 (#2)" in capsys.readouterr().out
    assert main(["number", *base, "--head", "없는-리비전"]) == 1
    assert capsys.readouterr().err.startswith("release: ")
    assert main(["notes", "--number", "0.1.0-rc.2", *base, *contract, "--head", "없는-리비전"]) == 1
    assert capsys.readouterr().err.startswith("release: ")


def test_머리가_빼기로_시작하면_git_옵션으로_읽히기_전에_거절한다(
    repo: Repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.product("feat: 첫 기능 (#1)")
    leaked = tmp_path / "새어_나온_파일"
    option = f"--output={leaked}"
    with pytest.raises(ReleaseError, match="리비전"):
        plan_release(repo.path, option)
    with pytest.raises(ReleaseError, match="리비전"):
        render_notes(repo.path, "0.1.0", CONTRACT, None, option)
    assert main(["number", "--repo", str(repo.path), f"--head={option}"]) == 1
    assert capsys.readouterr().err.startswith("release: ")
    assert not leaked.exists()


def test_스크립트로_불러도_돌고_구성_오류는_종료_코드_1이다(repo: Repo) -> None:
    """CI 는 `python3 tools/release.py` 로 부른다. 저장소 루트가 import 경로에 없는 길이다."""
    script = Path(__file__).resolve().parents[2] / "tools" / "release.py"
    repo.product("feat: 첫 기능 (#1)")
    broken = subprocess.run(
        [sys.executable, str(script), "number", "--repo", str(repo.path)],
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert broken.returncode == 1
    assert broken.stdout == ""
    assert "release: " in broken.stderr
    assert "출시 후보 칸" in broken.stderr
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)")
    done = subprocess.run(
        [sys.executable, str(script), "number", "--repo", str(repo.path)],
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert done.returncode == 0
    assert done.stdout.splitlines() == [
        "release=true",
        "number=0.1.1",
        "tag=v0.1.1",
        "previous_tag=v0.1.0",
    ]


def test_스크립트로_불러도_노트와_묶음이_나온다(repo: Repo, tmp_path: Path) -> None:
    """CI 가 부르는 꼴 그대로다. 한국어 노트가 stdout 으로 깨지지 않고 나오는지도 본다."""
    script = Path(__file__).resolve().parents[2] / "tools" / "release.py"
    _notes_이력(repo)
    contract = tmp_path / "contract.txt"
    contract.write_text(CONTRACT, encoding="utf-8")
    notes = subprocess.run(
        [
            sys.executable,
            str(script),
            "notes",
            "--number",
            "0.1.0-rc.2",
            "--repo",
            str(repo.path),
            "--contract-versions",
            str(contract),
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert notes.returncode == 0
    # 윈도의 텍스트 stdout 은 줄바꿈을 CRLF 로 내보내므로 맞춘 뒤 대 본다.
    shown = notes.stdout.decode("utf-8").replace("\r\n", "\n")
    assert shown == render_notes(repo.path, "0.1.0-rc.2", CONTRACT)
    source = _틀(tmp_path)
    bundle = subprocess.run(
        [
            sys.executable,
            str(script),
            "bundle",
            "--number",
            "0.1.0-rc.2",
            "--namespace",
            "njh6803",
            "--source",
            str(source),
            "--out",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert bundle.returncode == 0
    assert Path(bundle.stdout.strip()) == tmp_path / "out" / "rag-engine-0.1.0-rc.2.tar.gz"
    assert Path(bundle.stdout.strip()).is_file()


# ---------- 노트 ----------


def _notes_이력(repo: Repo) -> None:
    repo.product(
        "feat: 알파를 더한다 (#1)",
        {"docs/release-notes/features/alpha.md": "알파 단락이다.\n"},
    )
    repo.product("fix(core): 재개를 고친다 (#2)")
    repo.tag("v0.1.0-rc.1")
    repo.commit(
        "chore: 알파 단락을 고친다 (#3)", {"docs/release-notes/features/alpha.md": "고친 알파.\n"}
    )
    repo.commit(
        "chore(deploy): 배포 틀을 손본다 (#4)",
        {"deploy/standalone/compose.yaml": "x"},
    )
    repo.product(
        "feat(admin)!: 규칙 파일을 옮긴다 (#5)",
        {
            "docs/release-notes/upgrade/rules.md": "`rules.yaml`을 `policy.yaml`로 옮긴다.\n",
            "docs/release-notes/features/beta.md": "베타 단락이다.\n",
        },
    )
    repo.commit("docs: 안내를 쓴다 (#6)", {"docs/release-notes/intro/0.1.0.md": "0.1.0 소개다.\n"})
    repo.product('Revert "feat: 실험"')


def test_출시_후보의_노트는_지난_릴리스_뒤만_차례대로_싣는다(repo: Repo) -> None:
    _notes_이력(repo)
    assert render_notes(repo.path, "0.1.0-rc.2", CONTRACT) == (
        "## 소개\n\n0.1.0 소개다.\n\n"
        "## 기능 소개\n\n베타 단락이다.\n\n"
        "## 업그레이드할 때 할 일\n\n"
        "### 규칙 파일을 옮긴다 (#5)\n\n"
        "`rules.yaml`을 `policy.yaml`로 옮긴다.\n\n"
        f"{CONTRACT_SECTION}\n\n"
        "## 그 밖의 변경\n\n"
        "- 배포 틀을 손본다 (#4)\n"
        '- Revert "feat: 실험"\n'
    )


def test_정식_릴리스의_노트는_지난_정식_릴리스_뒤_전부를_싣는다(repo: Repo) -> None:
    _notes_이력(repo)
    notes = render_notes(repo.path, "0.1.0", CONTRACT)
    # 지난 정식 릴리스가 없으니 처음부터이고, 출시 후보 `rc.1` 에 실린 변경도 다시 선다.
    # 기능 단락은 더해진 커밋의 차례이고 글은 릴리스하는 커밋의 것이다.
    assert notes.index("## 소개") < notes.index("## 기능 소개")
    assert "고친 알파.\n\n베타 단락이다." in notes
    assert "## 새 기능\n\n- 알파를 더한다 (#1)\n" in notes
    assert "## 고친 것\n\n- 재개를 고친다 (#2)\n" in notes
    order = [
        "## 업그레이드할 때 할 일",
        "## 계약의 판",
        "## 새 기능",
        "## 고친 것",
        "## 그 밖의 변경",
    ]
    assert [notes.index(heading) for heading in order] == sorted(notes.index(h) for h in order)


def test_범위_밖에서_더해진_원고는_뒤에_고쳐져도_다시_싣지_않는다(repo: Repo) -> None:
    _notes_이력(repo)
    notes = render_notes(repo.path, "0.1.0-rc.2", CONTRACT)
    assert "알파" not in notes
    assert "고친 알파" not in notes


def test_범위_안에서_이름을_바꾼_기능_원고는_바꾼_뒤의_이름으로_싣는다(repo: Repo) -> None:
    """git log 는 기본으로 이름 바꾸기를 찾아 옮긴 파일을 더해진 것이 아니라 바뀐 것으로 낸다."""
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product(
        "feat: 베타를 더한다 (#2)", {"docs/release-notes/features/beta.md": "베타 단락이다.\n"}
    )
    repo.git("mv", "docs/release-notes/features/beta.md", "docs/release-notes/features/gamma.md")
    repo.commit("docs: 베타 원고의 이름을 바꾼다 (#3)")
    assert "## 기능 소개\n\n베타 단락이다.\n" in render_notes(repo.path, "0.2.0", CONTRACT)


def test_범위_밖에서_더해진_원고는_범위_안에서_이름을_바꿔도_다시_싣지_않는다(repo: Repo) -> None:
    repo.product(
        "feat: 알파를 더한다 (#1)", {"docs/release-notes/features/alpha.md": "알파 단락이다.\n"}
    )
    repo.tag("v0.1.0")
    repo.git("mv", "docs/release-notes/features/alpha.md", "docs/release-notes/features/delta.md")
    repo.commit("docs: 알파 원고의 이름을 바꾼다 (#2)")
    repo.product("feat: 다음 기능 (#3)")
    notes = render_notes(repo.path, "0.2.0", CONTRACT)
    assert "알파 단락" not in notes
    assert "기능 소개" not in notes


def test_빈_묶음은_머리째_빼지만_계약의_판은_늘_선다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)")
    assert render_notes(repo.path, "0.1.1", CONTRACT) == (
        f"{CONTRACT_SECTION}\n\n## 고친 것\n\n- 고친다 (#2)\n"
    )


def test_느낌표_커밋은_업그레이드할_때_할_일에만_서고_새_기능에는_서지_않는다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product(
        "feat!: 바꾼다 (#2)",
        {"docs/release-notes/upgrade/a.md": "하나\n\n둘\n"},
    )
    repo.product("fix!: 고치며 바꾼다 (#3)", {"docs/release-notes/upgrade/b.md": "셋\n"})
    notes = render_notes(repo.path, "0.2.0", CONTRACT)
    assert notes == (
        "## 업그레이드할 때 할 일\n\n"
        "### 바꾼다 (#2)\n\n하나\n\n둘\n\n"
        "### 고치며 바꾼다 (#3)\n\n셋\n\n"
        f"{CONTRACT_SECTION}\n"
    )


def test_지운_뒤_같은_경로에_다시_더한_원고는_각_커밋이_더한_글로_싣는다(repo: Repo) -> None:
    path = "docs/release-notes/upgrade/change.md"
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("feat!: 처음 바꾼다 (#2)", {path: "A 에서 B 로\n"})
    repo.git("rm", "-q", path)
    repo.commit("docs: 안내를 지운다 (#3)", {})
    repo.product("feat!: 다시 바꾼다 (#4)", {path: "B 에서 C 로\n"})
    assert render_notes(repo.path, "0.2.0", CONTRACT) == (
        "## 업그레이드할 때 할 일\n\n"
        "### 처음 바꾼다 (#2)\n\nA 에서 B 로\n\n"
        "### 다시 바꾼다 (#4)\n\nB 에서 C 로\n\n"
        f"{CONTRACT_SECTION}\n"
    )


def test_소개_글은_릴리스하는_커밋에_있을_때만_싣는다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)", {"docs/release-notes/intro/0.2.0.md": "0.2.0 소개\n"})
    assert "## 소개" not in render_notes(repo.path, "0.1.1", CONTRACT)
    assert render_notes(repo.path, "0.2.0-rc.1", CONTRACT).startswith("## 소개\n\n0.2.0 소개\n")


def _grype(*matches: dict[str, object]) -> str:
    return json.dumps({"matches": list(matches), "descriptor": {"name": "grype"}})


def _match(
    identifier: str,
    package: str,
    severity: str,
    fixed: list[str],
    *,
    version: str = "1.0",
    related: list[str] | None = None,
) -> dict[str, object]:
    return {
        "vulnerability": {
            "id": identifier,
            "severity": severity,
            "fix": {"versions": fixed, "state": "fixed" if fixed else "not-fixed"},
        },
        "relatedVulnerabilities": [{"id": one} for one in related or []],
        "artifact": {"name": package, "version": version},
    }


def test_경고는_고칠_수_있는_critical만_이미지별로_적는다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)")
    serve = _grype(
        _match("CVE-2026-0001", "zlib", "Critical", ["1.2.12", "1.3"], version="1.2.11"),
        _match("CVE-2026-0001", "zlib", "Critical", ["1.2.12", "1.3"], version="1.2.11"),
        _match("CVE-2026-0002", "libx", "Critical", []),
        _match("CVE-2026-0003", "liby", "High", ["2.0"]),
        _match("GHSA-aaaa-bbbb-cccc", "npm-pkg", "critical", ["9.9"], related=["CVE-2026-0004"]),
    )
    widget = _grype(_match("CVE-2026-0003", "liby", "High", ["2.0"]))
    notes = render_notes(repo.path, "0.1.1", CONTRACT, {"server": serve, "worker": widget})
    assert notes == (
        "## 경고\n\n"
        "- CVE-2026-0001: server 이미지의 zlib 1.2.11에 있다. 고친 번호는 1.2.12, 1.3이다.\n"
        "- CVE-2026-0004: server 이미지의 npm-pkg 1.0에 있다. 고친 번호는 9.9이다.\n\n"
        f"{CONTRACT_SECTION}\n\n"
        "## 고친 것\n\n- 고친다 (#2)\n"
    )


def test_고칠_수_있는_critical이_없으면_경고_묶음이_빠진다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)")
    only = _grype(_match("CVE-1", "a", "Critical", []), _match("CVE-2", "b", "High", ["1"]))
    assert "경고" not in render_notes(repo.path, "0.1.1", CONTRACT, {"server": only})
    assert "경고" not in render_notes(repo.path, "0.1.1", CONTRACT, {"server": _grype()})


def test_거르지_않은_grype_json이_아니면_실패한다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    wrong_type = (
        json.dumps({"matches": None, "descriptor": {}}),
        json.dumps({"matches": {}, "descriptor": {}}),
    )
    for broken in ("", "{", "[]", json.dumps({"other": 1}), *wrong_type):
        with pytest.raises(ReleaseError, match="grype"):
            render_notes(repo.path, "0.1.0-rc.1", CONTRACT, {"server": broken})


def test_노트_도구는_글을_표준_출력에_낸다(
    repo: Repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)")
    report = tmp_path / "server.json"
    report.write_text(_grype(_match("CVE-9", "z", "Critical", ["2"])), encoding="utf-8")
    base = ["notes", "--repo", str(repo.path), "--number", "0.1.1"]
    contract = ["--contract-versions", str(_계약_파일(tmp_path))]
    assert main([*base, *contract, "--grype", f"server={report}"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("## 경고\n\n- CVE-9: server 이미지의 z 1.0에 있다.")
    assert CONTRACT_SECTION in out
    assert main([*base, *contract, "--grype", "깨진"]) == 1
    assert "NAME=PATH" in capsys.readouterr().err


def test_계약의_판_줄은_받은_그대로_노트에_실린다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    repo.tag("v0.1.0")
    repo.product("fix: 고친다 (#2)")
    lines = "검색 도구의 형식 1.1.0\n수집 API v1\n  들여쓴 줄도 그대로\n"
    notes = render_notes(repo.path, "0.1.1", lines)
    assert (
        "## 계약의 판\n\n```text\n검색 도구의 형식 1.1.0\n수집 API v1\n  들여쓴 줄도 그대로\n```"
        in notes
    )


@pytest.mark.parametrize("contract", ["", "\n", "  \n\n \t\n"])
def test_계약의_판_줄을_받지_못하면_노트를_짓지_않는다(repo: Repo, contract: str) -> None:
    repo.product("feat: 첫 기능 (#1)")
    with pytest.raises(ReleaseError, match="계약의 판 줄이 비었다"):
        render_notes(repo.path, "0.1.0-rc.1", contract)


def test_코드_울타리가_든_계약의_판_줄은_노트_꼴을_깨므로_받지_않는다(repo: Repo) -> None:
    repo.product("feat: 첫 기능 (#1)")
    with pytest.raises(ReleaseError, match="코드 울타리"):
        render_notes(repo.path, "0.1.0-rc.1", "검색 도구의 형식 1.1.0\n```\n## 가짜 절\n")


def test_계약의_판_줄의_줄바꿈_꼴은_맞추고_첫_줄까지_담아도_그대로_싣는다(repo: Repo) -> None:
    """`rag-engine --version` 의 첫 줄까지 담아 넘겨도 도구는 거르지 않는다(못 보는 것)."""
    repo.product("feat: 첫 기능 (#1)")
    notes = render_notes(repo.path, "0.1.0-rc.1", "0.1.0-rc.1\r\n검색 도구의 형식 1.1.0\r\n")
    assert "## 계약의 판\n\n```text\n0.1.0-rc.1\n검색 도구의 형식 1.1.0\n```" in notes


def test_노트_도구는_계약의_판_파일이_없거나_읽지_못하면_실패한다(
    repo: Repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.product("feat: 첫 기능 (#1)")
    base = ["notes", "--repo", str(repo.path), "--number", "0.1.0-rc.1"]
    assert main(base) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("release: ")
    assert "--contract-versions 가 없다" in captured.err
    assert main([*base, "--contract-versions", str(tmp_path / "없다")]) == 1
    assert "파일을 읽지 못했다" in capsys.readouterr().err
    broken = tmp_path / "깨진.txt"
    broken.write_bytes(b"\xff\xfe\x00 UTF-8 \xc3\x28")
    assert main([*base, "--contract-versions", str(broken)]) == 1
    assert "파일을 읽지 못했다" in capsys.readouterr().err
    empty = tmp_path / "빈.txt"
    empty.write_text("\n", encoding="utf-8")
    assert main([*base, "--contract-versions", str(empty)]) == 1
    assert "계약의 판 줄이 비었다" in capsys.readouterr().err


# ---------- 배포 파일 묶음 ----------


def _틀(tmp_path: Path) -> Path:
    source = tmp_path / "standalone"
    (source / "proxy").mkdir(parents=True)
    (source / "sites").mkdir()
    (source / ".env.example").write_text(
        "RAG_ENGINE_VERSION=@RAG_ENGINE_VERSION@\nRAG_ENGINE_NAMESPACE=@RAG_ENGINE_NAMESPACE@\n",
        encoding="utf-8",
    )
    (source / "compose.yaml").write_text(
        "image: ${RAG_ENGINE_NAMESPACE}/rag-engine-server:${RAG_ENGINE_VERSION}\n", encoding="utf-8"
    )
    (source / "proxy" / "nginx.conf").write_text("listen 443;\n", encoding="utf-8")
    (source / "sites" / "README.md").write_text(
        "번호 @RAG_ENGINE_VERSION@ 에서 @RAG_ENGINE_VERSION@ 로\n", encoding="utf-8"
    )
    return source


def test_묶음은_같은_이름의_폴더_하나로_풀리고_릴리스_번호와_이름공간이_채워진다(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    bundle = build_bundle(_틀(tmp_path), out, "0.1.0-rc.1", "njh6803")
    assert bundle == out / "rag-engine-0.1.0-rc.1.tar.gz"
    unpacked = tmp_path / "unpacked"
    with tarfile.open(bundle) as archive:
        archive.extractall(unpacked, filter="data")
    assert [entry.name for entry in unpacked.iterdir()] == ["rag-engine-0.1.0-rc.1"]
    root = unpacked / "rag-engine-0.1.0-rc.1"
    assert (root / ".env.example").read_text(encoding="utf-8") == (
        "RAG_ENGINE_VERSION=0.1.0-rc.1\nRAG_ENGINE_NAMESPACE=njh6803\n"
    )
    assert (root / "compose.yaml").read_text(encoding="utf-8") == (
        "image: ${RAG_ENGINE_NAMESPACE}/rag-engine-server:${RAG_ENGINE_VERSION}\n"
    )
    assert (root / "proxy" / "nginx.conf").read_text(encoding="utf-8") == "listen 443;\n"
    assert (root / "sites" / "README.md").read_text(encoding="utf-8") == (
        "번호 0.1.0-rc.1 에서 0.1.0-rc.1 로\n"
    )
    assert "@RAG_ENGINE_" not in "".join(
        path.read_text(encoding="utf-8") for path in root.rglob("*") if path.is_file()
    )


def test_같은_입력이면_묶음의_바이트가_같다(tmp_path: Path) -> None:
    source = _틀(tmp_path)
    first = build_bundle(source, tmp_path / "a", "0.1.0", "njh6803").read_bytes()
    second = build_bundle(source, tmp_path / "b", "0.1.0", "njh6803").read_bytes()
    assert first == second


def test_모르는_자리_표지가_남으면_묶음을_짓지_않는다(tmp_path: Path) -> None:
    source = _틀(tmp_path)
    (source / "extra.txt").write_text("@RAG_ENGINE_TYPO@\n", encoding="utf-8")
    with pytest.raises(ReleaseError, match="@RAG_ENGINE_TYPO@"):
        build_bundle(source, tmp_path / "out", "0.1.0", "njh6803")
    assert not (tmp_path / "out" / "rag-engine-0.1.0.tar.gz").exists()


@pytest.mark.parametrize("left", ["@RAG_ENGINE_TYPO", "@RAG_ENGINE_A-B@", "@RAG_ENGINE_@"])
def test_닫는_골뱅이가_빠졌거나_낱말이_다른_모르는_자리_표지도_묶음을_짓지_않는다(
    tmp_path: Path, left: str
) -> None:
    source = _틀(tmp_path)
    (source / "extra.txt").write_text(f"x {left} y\n", encoding="utf-8")
    with pytest.raises(ReleaseError, match="모르는 자리 표지"):
        build_bundle(source, tmp_path / "out", "0.1.0", "njh6803")
    assert not (tmp_path / "out" / "rag-engine-0.1.0.tar.gz").exists()


def test_소문자가_든_모르는_자리_표지도_묶음을_짓지_않는다(tmp_path: Path) -> None:
    source = _틀(tmp_path)
    (source / "extra.txt").write_text("@RAG_ENGINE_version@\n", encoding="utf-8")
    with pytest.raises(ReleaseError, match="@RAG_ENGINE_version@"):
        build_bundle(source, tmp_path / "out", "0.1.0", "njh6803")


@pytest.mark.parametrize(
    ("number", "namespace", "reason"),
    [
        ("v0.1.0", "njh6803", "릴리스 번호"),
        ("0.1", "njh6803", "릴리스 번호"),
        ("0.1.0", "", "이름공간"),
        ("0.1.0", "Rag Engine", "이름공간"),
        ("0.1.0", "a/b", "이름공간"),
        ("0.1.0", "docker.io/foo", "이름공간"),
        ("0.1.0", "-a", "이름공간"),
        ("0.1.0", "a_", "이름공간"),
    ],
)
def test_번호나_이름공간이_틀리면_묶음을_짓지_않는다(
    tmp_path: Path, number: str, namespace: str, reason: str
) -> None:
    with pytest.raises(ReleaseError, match=reason):
        build_bundle(_틀(tmp_path), tmp_path / "out", number, namespace)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("namespace", ["njh6803", "my-org", "a--b", "my_org", "a__b", "a.b-c"])
def test_도커_경로_한_토막으로_읽히는_이름공간은_받는다(tmp_path: Path, namespace: str) -> None:
    assert build_bundle(_틀(tmp_path), tmp_path / "out", "0.1.0", namespace).is_file()


def test_utf8이_아닌_파일은_그대로_담고_빈_하위_폴더는_담지_않는다(tmp_path: Path) -> None:
    source = _틀(tmp_path)
    raw = b"\xff\xfe@RAG_ENGINE_TYPO@"
    (source / "blob.bin").write_bytes(raw)
    (source / "empty").mkdir()
    bundle = build_bundle(source, tmp_path / "out", "0.1.0", "njh6803")
    with tarfile.open(bundle) as archive:
        names = archive.getnames()
        member = archive.extractfile("rag-engine-0.1.0/blob.bin")
        assert member is not None
        assert member.read() == raw
    assert "rag-engine-0.1.0/empty" not in names


def test_심볼릭_링크가_있으면_묶음을_짓지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """윈도에서는 링크를 만들 권한이 없을 수 있어 `is_symlink` 만 바꿔 같은 길을 밟는다."""
    source = _틀(tmp_path)
    (source / "link").write_text("x\n", encoding="utf-8")
    original = Path.is_symlink

    def fake(self: Path) -> bool:
        return self.name == "link" or original(self)

    monkeypatch.setattr(Path, "is_symlink", fake)
    with pytest.raises(ReleaseError, match="심볼릭 링크"):
        build_bundle(source, tmp_path / "out", "0.1.0", "njh6803")


def test_틀_폴더_자체가_심볼릭_링크이면_묶음을_짓지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """윈도에서는 링크를 만들 권한이 없을 수 있어 `is_symlink` 만 바꿔 같은 길을 밟는다."""
    source = _틀(tmp_path)
    original = Path.is_symlink

    def fake(self: Path) -> bool:
        return self == source or original(self)

    monkeypatch.setattr(Path, "is_symlink", fake)
    with pytest.raises(ReleaseError, match="틀 폴더가 심볼릭 링크"):
        build_bundle(source, tmp_path / "out", "0.1.0", "njh6803")
    assert not (tmp_path / "out" / "rag-engine-0.1.0.tar.gz").exists()


def test_틀이_없거나_비면_묶음을_짓지_않는다(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="틀"):
        build_bundle(tmp_path / "없다", tmp_path / "out", "0.1.0", "njh6803")
    (tmp_path / "빈").mkdir()
    with pytest.raises(ReleaseError, match="틀"):
        build_bundle(tmp_path / "빈", tmp_path / "out", "0.1.0", "njh6803")


def test_묶음_도구는_만든_파일의_경로를_낸다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "bundle",
            "--number",
            "0.1.0",
            "--namespace",
            "njh6803",
            "--source",
            str(_틀(tmp_path)),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "out" / "rag-engine-0.1.0.tar.gz")


def test_묶음을_쓰지_못하면_접두를_붙여_종료_코드_1이다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    not_a_folder = tmp_path / "파일"
    not_a_folder.write_text("x", encoding="utf-8")
    code = main(
        [
            "bundle",
            "--number",
            "0.1.0",
            "--namespace",
            "njh6803",
            "--source",
            str(_틀(tmp_path)),
            "--out",
            str(not_a_folder),
        ]
    )
    assert code == 1
    assert capsys.readouterr().err.startswith("release: ")


# ---------- 번호 태그 판정 ----------

NOT_FOUND = "ERROR: registry.example/njh6803/rag-engine-server:0.1.0: not found"
UNEXPECTED = "ERROR: unexpected status from HEAD request to http://r/v2/x/manifests/1: "
# agent-os 저장소가 2026-11-16 에 로컬 `registry:3` 에 출처 증명과 SBOM 을 붙여 올린 이미지 색인
# (릴리스 워크플로가 올리는 꼴)을 `docker buildx imagetools inspect <참조>` 로 조회해 적어 둔 꼴을
# 옮기고 이름만 이 저장소의 것으로 바꿨다(그 워크플로는 release-image 의 08 이 들인다). 이
# 저장소에서는 조회해 보지 않았다. 맨 앞 칸에서
# 시작하는 첫 `Digest:` 줄은 하나이고, `Manifests:` 아래는 들여쓰며(증명 매니페스트의 `Annotations`
# 아래 줄은 더 들여쓴다) 그 안의 digest 는 맨 앞 칸에서 시작하지 않는다.
EXISTING = (
    "Name:      registry.example/njh6803/rag-engine-server:0.1.0\n"
    "MediaType: application/vnd.oci.image.index.v1+json\n"
    "Digest:    {digest}\n"
    "           \n"
    "Manifests: \n"
    "  Name:        registry.example/njh6803/rag-engine-server:0.1.0@sha256:" + "c" * 64 + "\n"
    "  MediaType:   application/vnd.oci.image.manifest.v1+json\n"
    "  Platform:    linux/amd64\n"
    "               \n"
    "  Name:        registry.example/njh6803/rag-engine-server:0.1.0@sha256:" + "d" * 64 + "\n"
    "  MediaType:   application/vnd.oci.image.manifest.v1+json\n"
    "  Platform:    unknown/unknown\n"
    "  Annotations: \n"
    "    vnd.docker.reference.digest: sha256:" + "c" * 64 + "\n"
    "    vnd.docker.reference.type:   attestation-manifest\n"
)


def test_조회_출력의_마지막_줄이_not_found로_끝날_때만_없다고_읽고_붙인다() -> None:
    assert judge_number_tag(1, NOT_FOUND, DIGEST_A) is TagVerdict.ATTACH
    assert judge_number_tag(1, NOT_FOUND + "\n\n", DIGEST_A) is TagVerdict.ATTACH
    assert judge_number_tag(1, "경고 줄\r\n" + NOT_FOUND + "\r\n", DIGEST_A) is TagVerdict.ATTACH


def test_같은_digest면_그대로_두고_다른_digest면_거부한다() -> None:
    assert judge_number_tag(0, EXISTING.format(digest=DIGEST_A), DIGEST_A) is TagVerdict.KEEP
    assert judge_number_tag(0, EXISTING.format(digest=DIGEST_B), DIGEST_A) is TagVerdict.REJECT


@pytest.mark.parametrize(
    "output",
    [
        'ERROR: failed to do request: Head "http://localhost:1/v2/x/manifests/1": '
        "dial tcp 127.0.0.1:1: connect: connection refused",
        f"{UNEXPECTED}401 Unauthorized",
        f"{UNEXPECTED}429 Too Many Requests",
        f"{UNEXPECTED}500 Internal Server Error",
        "ERROR: pull access denied, repository does not exist or may require authorization: "
        "server message: insufficient_scope: authorization failed",
        # 앞 줄에 not found 가 있어도 마지막 줄이 아니면 없다고 읽지 않는다
        "ERROR: a: not found\nERROR: failed to do request: timeout",
        "ERROR: a: not found.",
        "ERROR: a not found",
        "",
    ],
)
def test_조회가_실패하면_붙이지_않는다(output: str) -> None:
    assert judge_number_tag(1, output, DIGEST_A) is TagVerdict.HOLD


def test_종료_코드_0인데_digest를_읽지_못하면_붙이지_않는다() -> None:
    assert judge_number_tag(0, "Name: x\nMediaType: y\n", DIGEST_A) is TagVerdict.HOLD
    assert judge_number_tag(0, NOT_FOUND, DIGEST_A) is TagVerdict.HOLD
    assert judge_number_tag(2, NOT_FOUND + "x", DIGEST_A) is TagVerdict.HOLD


def test_종료_코드가_1이_아니면_not_found로_끝나도_붙이지_않는다() -> None:
    """셸이 docker 를 못 찾은 127 같은 실패를 없다고 읽어 번호 태그를 덮지 않는다."""
    assert judge_number_tag(127, "sh: 1: docker: not found", DIGEST_A) is TagVerdict.HOLD
    assert judge_number_tag(2, NOT_FOUND, DIGEST_A) is TagVerdict.HOLD


def test_올린_digest가_sha256_꼴이_아니면_판정하지_않고_실패한다() -> None:
    for pushed in ("", "abc", "sha256:xyz", "sha256:" + "A" * 64):
        with pytest.raises(ReleaseError, match="digest"):
            judge_number_tag(1, NOT_FOUND, pushed)


def test_번호_태그_판정은_첫_digest_줄만_본다() -> None:
    output = EXISTING.format(digest=DIGEST_A) + f"\nManifests:\n  Digest:    {DIGEST_B}\n"
    assert judge_number_tag(0, output, DIGEST_A) is TagVerdict.KEEP
