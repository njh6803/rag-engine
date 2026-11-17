"""`tools/eval_gate_paths.py` 의 시험. 빠른 게이트(검색 평가)를 돌릴지를 경로로 가른다(search-eval
11).

판정 함수는 순수하다. 이벤트 이름과 바뀐 경로 목록만 보고 답한다. 푸시와 수동 실행은 경로와 무관하게
평가하고, PR 에서 바뀐 경로를 읽지 못했거나(None) 비어 있으면 평가한다(닫힘 쪽). 목록 밖의 파일만
바뀐 PR 만 평가하지 않는다. 이름을 바꾼 파일은 옛 경로와 새 경로를 모두 판정해야 하므로, 그 경우는
진짜 저장소에서 git 이 내는 목록으로 본다. CI 가 부르는 진입점(`python3 tools/eval_gate_paths.py`)은
subprocess 로 한 번 실제로 부른다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from tools.eval_gate_paths import (
    EVALUATED_PATHS,
    changed_paths,
    decide,
    decide_full,
    should_evaluate,
)

from tools import eval_gate_paths

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "eval_gate_paths.py"
_IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *_IDENTITY, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        timeout=120,
    )
    return result.stdout.strip()


def test_목록은_명세의_일곱_경로다() -> None:
    assert set(EVALUATED_PATHS) == {
        "src/",
        "pyproject.toml",
        "uv.lock",
        "evals/",
        "tools/search_eval.py",
        "compose.eval.yml",
        ".github/workflows/ci.yml",
    }


@pytest.mark.parametrize(
    "path",
    [
        "src/rag_engine/app/search.py",
        "src/x",
        "pyproject.toml",
        "uv.lock",
        "evals/public-docs/config.json",
        "evals/public-docs/records/query-embeddings.f32",
        "tools/search_eval.py",
        "compose.eval.yml",
        ".github/workflows/ci.yml",
    ],
)
def test_목록의_경로가_바뀐_PR은_평가한다(path: str) -> None:
    assert should_evaluate("pull_request", [path]) is True


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/PRD.md",
        ".scratch/search-eval/spec.md",
        "tests/tools/test_search_eval.py",
        "tools/check_ticket.py",
        "tools/search_eval_helper.py",
        "compose.test.yml",
        "compose.yml",
        "src",
        "srcs/x.py",
        "evals-notes/a.md",
        "pyproject.toml.bak",
        "sub/pyproject.toml",
        "sub/src/a.py",
        ".github/workflows/other.yml",
        # 경로는 git 이 낸 그대로 견준다(모듈 독스트링의 못 보는 것). CI 는 리눅스라 이 꼴이 나오지
        # 않는다.
        "SRC/a.py",
        "src\\a.py",
    ],
)
def test_목록_밖의_경로만_바뀐_PR은_평가하지_않는다(path: str) -> None:
    assert should_evaluate("pull_request", [path]) is False


def test_목록_밖과_안이_섞이면_평가한다() -> None:
    assert (
        should_evaluate("pull_request", ["README.md", "docs/a.md", "src/rag_engine/x.py"]) is True
    )


@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
@pytest.mark.parametrize("paths", [None, [], ["README.md"], ["src/a.py"]])
def test_푸시와_수동_실행은_경로와_무관하게_평가한다(event: str, paths: list[str] | None) -> None:
    assert should_evaluate(event, paths) is True


@pytest.mark.parametrize("paths", [None, []])
def test_PR_에서_바뀐_경로를_읽지_못했거나_비었으면_평가한다(paths: list[str] | None) -> None:
    assert should_evaluate("pull_request", paths) is True


@pytest.mark.parametrize("event", ["", "schedule", "pull_request_target", "issue_comment"])
def test_알지_못하는_이벤트는_평가한다(event: str) -> None:
    assert should_evaluate(event, ["README.md"]) is True


@pytest.mark.parametrize(
    ("event", "paths", "reason_part"),
    [
        ("push", ["README.md"], "push 는 바뀐 경로를 보지 않고 늘 평가한다"),
        ("workflow_dispatch", None, "workflow_dispatch 는 바뀐 경로를 보지 않고 늘 평가한다"),
        ("schedule", None, "알지 못하는 이벤트(schedule)"),
        ("", None, "알지 못하는 이벤트(빈 값)"),
        ("pull_request", None, "읽지 못했거나 비어 있어 평가한다"),
        ("pull_request", [], "읽지 못했거나 비어 있어 평가한다"),
        ("pull_request", ["README.md", "src/a.py"], "평가하는 경로가 바뀌었다: src/a.py"),
        (
            "pull_request",
            ["README.md", "docs/a.md"],
            "평가하는 경로가 바뀌지 않았다(바뀐 파일 2개)",
        ),
    ],
)
def test_판정은_이유를_함께_낸다(event: str, paths: list[str] | None, reason_part: str) -> None:
    evaluate, reason = decide(event, paths)
    assert evaluate is should_evaluate(event, paths)
    assert reason_part in reason


def _저장소(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "dev")
    (repo / "src").mkdir()
    (repo / "docs").mkdir()
    # 이름 바꾸기 찾기가 같은 파일로 보도록 내용을 충분히 길게 둔다.
    (repo / "src" / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
    (repo / "README.md").write_text("처음\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _분기한다(repo: Path) -> str:
    """`feature/x` 를 따고 갈라진 자리(base)의 SHA 를 돌려준다."""
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feature/x")
    return base


def _커밋한다(repo: Path, message: str) -> str:
    """작업 트리 전체를 커밋하고 그 SHA 를 돌려준다."""
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_src_의_파일을_목록_밖으로_옮긴_PR_도_평가한다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    base = _분기한다(repo)
    _git(repo, "mv", "src/a.py", "docs/a.py")
    head = _커밋한다(repo, "move")
    # 이름 바꾸기 찾기를 켠 `--name-only` 는 새 경로만 내어 이 PR 이 평가를 건너뛴다. 그 오판을 이
    # 시험이 잡는다.
    with_renames = _git(repo, "diff", "--name-only", base, head).splitlines()
    assert with_renames == ["docs/a.py"]
    assert should_evaluate("pull_request", with_renames) is False
    paths = changed_paths(repo, base, head)
    assert paths is not None
    assert sorted(paths) == ["docs/a.py", "src/a.py"]
    assert should_evaluate("pull_request", paths) is True


def test_바뀐_경로는_merge_base_부터_읽는다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    fork_point = _분기한다(repo)
    (repo / "README.md").write_text("PR 의 변경\n", encoding="utf-8")
    head = _커밋한다(repo, "pr")
    # base 가 그 사이에 앞서 갔다. base 의 새 커밋이 PR 의 변경으로 읽히면 안 된다.
    _git(repo, "checkout", "-q", "dev")
    (repo / "src" / "b.py").write_text("y = 2\n", encoding="utf-8")
    base = _커밋한다(repo, "base moved")
    assert base != fork_point
    paths = changed_paths(repo, base, head)
    assert paths == ["README.md"]
    assert should_evaluate("pull_request", paths) is False


def test_경로에_한글과_공백이_있어도_그대로_읽는다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    base = _분기한다(repo)
    (repo / "src" / "한 글.py").write_text("z = 3\n", encoding="utf-8")
    head = _커밋한다(repo, "korean")
    assert changed_paths(repo, base, head) == ["src/한 글.py"]


def test_커밋을_읽지_못하면_None_이다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    assert changed_paths(repo, "0" * 40, head) is None
    assert changed_paths(repo, head, "") is None
    assert changed_paths(tmp_path / "없는-폴더", head, head) is None


def test_바뀐_경로를_읽다_실패하면_None_이다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # merge-base 는 구했는데 그 뒤의 diff 가 실패하는 길은 진짜 저장소로 만들기 어려워 git 호출을
    # 바꿔 본다.
    def fake_git(repo: Path, *args: str) -> str | None:
        return "abc123\n" if args[0] == "merge-base" else None

    monkeypatch.setattr(eval_gate_paths, "_git", fake_git)
    assert changed_paths(tmp_path, "base", "head") is None


def test_얕은_체크아웃에서_base_가_없으면_None_이고_평가한다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    base = _분기한다(repo)
    (repo / "README.md").write_text("문서만\n", encoding="utf-8")
    head = _커밋한다(repo, "docs")
    shallow = tmp_path / "shallow"
    _git(
        tmp_path,
        "clone",
        "-q",
        "--depth",
        "1",
        "--branch",
        "feature/x",
        repo.as_uri(),
        str(shallow),
    )
    paths = changed_paths(shallow, base, head)
    assert paths is None
    assert should_evaluate("pull_request", paths) is True


def test_main_이_푸시에서는_출력_파일에_true_를_쓴다(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    code = eval_gate_paths.main(
        env={"GITHUB_EVENT_NAME": "push", "GITHUB_OUTPUT": str(out)}, repo=tmp_path
    )
    assert code == 0
    assert out.read_text(encoding="utf-8") == "evaluate=true\n"


def test_main_이_문서만_바꾼_PR_에서는_false_를_쓴다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    base = _분기한다(repo)
    (repo / "README.md").write_text("문서만\n", encoding="utf-8")
    head = _커밋한다(repo, "docs")
    out = tmp_path / "out.txt"
    env = {
        "GITHUB_EVENT_NAME": "pull_request",
        "PR_BASE_SHA": base,
        "PR_HEAD_SHA": head,
        "GITHUB_OUTPUT": str(out),
    }
    assert eval_gate_paths.main(env=env, repo=repo) == 0
    assert out.read_text(encoding="utf-8") == "evaluate=false\n"


def test_main_이_PR_의_커밋_값이_없으면_true_를_쓴다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    out = tmp_path / "out.txt"
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_OUTPUT": str(out)}
    assert eval_gate_paths.main(env=env, repo=repo) == 0
    assert out.read_text(encoding="utf-8") == "evaluate=true\n"


def test_main_은_출력_파일이_없어도_표준_출력에_이유와_함께_답한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert eval_gate_paths.main(env={"GITHUB_EVENT_NAME": "workflow_dispatch"}, repo=tmp_path) == 0
    assert "evaluate=true (workflow_dispatch 는 바뀐 경로를 보지 않고 늘 평가한다)" in (
        capsys.readouterr().out
    )


def _진입점을_부른다(cwd: Path, env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GITHUB_")}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )


def test_진입점은_CI_가_부르는_꼴로_문서만_바꾼_PR_에서_false_를_쓴다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    base = _분기한다(repo)
    (repo / "README.md").write_text("문서만\n", encoding="utf-8")
    head = _커밋한다(repo, "docs")
    out = tmp_path / "out.txt"
    result = _진입점을_부른다(
        repo,
        {
            "GITHUB_EVENT_NAME": "pull_request",
            "PR_BASE_SHA": base,
            "PR_HEAD_SHA": head,
            "GITHUB_OUTPUT": str(out),
        },
    )
    assert result.returncode == 0, result.stderr
    assert "evaluate=false" in result.stdout
    assert out.read_text(encoding="utf-8") == "evaluate=false\n"


def test_진입점은_검색_코드가_바뀐_PR_에서_true_를_쓴다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path)
    base = _분기한다(repo)
    (repo / "src" / "a.py").write_text("x = 2\n" * 40, encoding="utf-8")
    head = _커밋한다(repo, "src")
    out = tmp_path / "out.txt"
    result = _진입점을_부른다(
        repo,
        {
            "GITHUB_EVENT_NAME": "pull_request",
            "PR_BASE_SHA": base,
            "PR_HEAD_SHA": head,
            "GITHUB_OUTPUT": str(out),
        },
    )
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") == "evaluate=true\n"


# ---- 전체 게이트(search-eval 15): 이벤트와 PR 의 base 브랜치만 본다 ----


def test_수동_실행은_base_와_무관하게_전체_게이트를_평가한다() -> None:
    assert decide_full("workflow_dispatch", "")[0] is True
    assert decide_full("workflow_dispatch", "dev")[0] is True


def test_base_가_main_인_PR_은_전체_게이트를_평가한다() -> None:
    assert decide_full("pull_request", "main")[0] is True


@pytest.mark.parametrize(
    "base",
    ["dev", "feature/x", "hotfix/y", "Main", "main2", "origin/main", "refs/heads/main", " main"],
)
def test_base_가_main_이_아닌_PR_은_전체_게이트를_평가하지_않는다(base: str) -> None:
    assert decide_full("pull_request", base)[0] is False


def test_PR_의_base_를_읽지_못하면_전체_게이트를_평가한다() -> None:
    assert decide_full("pull_request", "")[0] is True


@pytest.mark.parametrize("base", ["", "main", "dev"])
def test_푸시는_main_푸시도_전체_게이트를_평가하지_않는다(base: str) -> None:
    assert decide_full("push", base)[0] is False


@pytest.mark.parametrize("event", ["", "schedule", "pull_request_target", "issue_comment"])
def test_알지_못하는_이벤트는_전체_게이트를_평가한다(event: str) -> None:
    assert decide_full(event, "dev")[0] is True


@pytest.mark.parametrize(
    ("event", "base", "evaluate", "reason_part"),
    [
        ("workflow_dispatch", "", True, "workflow_dispatch 는 늘 평가한다"),
        ("pull_request", "main", True, "base 가 main 인 PR 이라 평가한다"),
        ("pull_request", "dev", False, "base 가 dev 인 PR 은 빠른 게이트만 본다"),
        ("pull_request", "", True, "PR 의 base 를 읽지 못해 평가한다"),
        ("push", "", False, "푸시에서는 평가하지 않는다"),
        ("schedule", "", True, "알지 못하는 이벤트(schedule)"),
        ("", "", True, "알지 못하는 이벤트(빈 값)"),
    ],
)
def test_전체_게이트의_판정은_이유를_함께_낸다(
    event: str, base: str, *, evaluate: bool, reason_part: str
) -> None:
    decided, reason = decide_full(event, base)
    assert decided is evaluate
    assert reason_part in reason


def test_main_이_EVAL_GATE_full_의_main_PR_에서_true_를_쓴다(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    env = {
        "EVAL_GATE": "full",
        "GITHUB_EVENT_NAME": "pull_request",
        "PR_BASE_REF": "main",
        "GITHUB_OUTPUT": str(out),
    }
    assert eval_gate_paths.main(env=env, repo=tmp_path) == 0
    assert out.read_text(encoding="utf-8") == "evaluate=true\n"


def test_main_이_EVAL_GATE_full_의_dev_PR_에서_경로를_보지_않고_false_를_쓴다(
    tmp_path: Path,
) -> None:
    repo = _저장소(tmp_path)
    base = _분기한다(repo)
    (repo / "src" / "a.py").write_text("x = 2\n" * 40, encoding="utf-8")
    head = _커밋한다(repo, "src")
    out = tmp_path / "out.txt"
    env = {
        "EVAL_GATE": "full",
        "GITHUB_EVENT_NAME": "pull_request",
        "PR_BASE_REF": "dev",
        "PR_BASE_SHA": base,
        "PR_HEAD_SHA": head,
        "GITHUB_OUTPUT": str(out),
    }
    assert eval_gate_paths.main(env=env, repo=repo) == 0
    assert out.read_text(encoding="utf-8") == "evaluate=false\n"


def test_main_이_EVAL_GATE_full_의_수동_실행에서_true_를_쓴다(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    env = {"EVAL_GATE": "full", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_OUTPUT": str(out)}
    assert eval_gate_paths.main(env=env, repo=tmp_path) == 0
    assert out.read_text(encoding="utf-8") == "evaluate=true\n"


def test_main_이_EVAL_GATE_full_의_푸시에서_false_를_쓴다(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    env = {"EVAL_GATE": "full", "GITHUB_EVENT_NAME": "push", "GITHUB_OUTPUT": str(out)}
    assert eval_gate_paths.main(env=env, repo=tmp_path) == 0
    assert out.read_text(encoding="utf-8") == "evaluate=false\n"


@pytest.mark.parametrize("gate", ["", "fast"])
def test_main_은_EVAL_GATE_가_없거나_fast_면_빠른_게이트로_가른다(
    tmp_path: Path, gate: str
) -> None:
    out = tmp_path / "out.txt"
    env = {"GITHUB_EVENT_NAME": "push", "GITHUB_OUTPUT": str(out)}
    if gate:
        env["EVAL_GATE"] = gate
    assert eval_gate_paths.main(env=env, repo=tmp_path) == 0
    assert out.read_text(encoding="utf-8") == "evaluate=true\n"


def test_main_은_알지_못하는_EVAL_GATE_를_알리고_2로_끝나며_출력을_쓰지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.txt"
    env = {"EVAL_GATE": "ful", "GITHUB_EVENT_NAME": "push", "GITHUB_OUTPUT": str(out)}
    code = eval_gate_paths.main(env=env, repo=tmp_path)
    assert code == 2, f"알지 못하는 EVAL_GATE 가 종료 코드 {code} 로 끝났다"
    assert not out.exists()
    err = capsys.readouterr().err
    assert "EVAL_GATE" in err
    assert "받은 값: ful" in err
    assert "fast" in err
    assert "full" in err


def test_진입점은_CI_가_부르는_꼴로_dev_PR_에서_전체_게이트를_false_로_쓴다(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    result = _진입점을_부른다(
        tmp_path,
        {
            "EVAL_GATE": "full",
            "GITHUB_EVENT_NAME": "pull_request",
            "PR_BASE_REF": "dev",
            "GITHUB_OUTPUT": str(out),
        },
    )
    assert result.returncode == 0, result.stderr
    assert "evaluate=false" in result.stdout
    assert out.read_text(encoding="utf-8") == "evaluate=false\n"


def test_진입점은_CI_가_부르는_꼴로_수동_실행에서_전체_게이트를_true_로_쓴다(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out.txt"
    result = _진입점을_부른다(
        tmp_path,
        {"EVAL_GATE": "full", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_OUTPUT": str(out)},
    )
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") == "evaluate=true\n"
