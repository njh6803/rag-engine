"""tools/check_constitution_version.py 의 헌법 판 검사.

판정은 커밋에 들 판(색인), `origin/main`, 그 둘의 merge-base 를 견준다. 그래서 시험은 임시 원격과
클론에서 실제 git 으로 돈다(`.claude/rules/tests.md`).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from tools.check_constitution_version import Judged, main
from tools.run_hooks import hook_environment

ROOT = Path(__file__).resolve().parents[2]
README = "docs/constitution/README.md"
OPERATIONS = "docs/constitution/operations.md"
TECH = "docs/constitution/tech.md"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _쓴다(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _스테이지한다(root: Path, files: dict[str, str]) -> None:
    _쓴다(root, files)
    _git(root, "add", *files)


def _커밋한다(root: Path, files: dict[str, str], message: str) -> None:
    _스테이지한다(root, files)
    _git(root, "commit", "-q", "-m", message)


def _헌법(version: str, vacated: str = "") -> str:
    """판 줄과, 아직 쓰이지 않은 비워 둔 판의 문장(한 줄에 하나)만 든 헌법 README."""
    return f"# 헌법\n\n**Version**: {version} | **Ratified**: 2026-09-19\n\n{vacated}\n"


RESERVE = "1.0.1은 함께 돌던 형제 브랜치(`topic`)가 먼저 매겨 비워 두었다."


SEED = {README: _헌법("1.0.0"), OPERATIONS: "운영\n", TECH: "스택\n", "README.md": "읽어 보기\n"}


def _원격과_클론(tmp_path: Path) -> tuple[Path, Path]:
    """(작업 클론, 원격에 밀어 넣는 다른 클론). 작업 클론은 씨앗 커밋의 `topic` 에 있다."""
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    pusher = tmp_path / "pusher"
    _git(tmp_path, "clone", "-q", str(remote), str(pusher))
    _git(pusher, "checkout", "-q", "-b", "main")
    _커밋한다(pusher, SEED, "씨앗")
    _git(pusher, "push", "-q", "origin", "main")
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _git(work, "checkout", "-q", "-b", "topic")
    return work, pusher


@pytest.fixture
def 저장소(tmp_path: Path) -> tuple[Path, Path]:
    return _원격과_클론(tmp_path)


def _main_에_민다(work: Path, pusher: Path, files: dict[str, str]) -> None:
    """origin/main 에 커밋 하나를 밀고 작업 클론이 받아 온다."""
    _커밋한다(pusher, files, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")


def _판정(root: Path) -> tuple[int, str]:
    줄: list[str] = []
    code = main([str(root)], out=줄.append)
    return code, "\n".join(줄)


@pytest.mark.parametrize(
    ("judged", "기대"),
    [
        (Judged([], "1.0.0", "1.0.0", "1.0.0", None), True),
        (Judged([OPERATIONS], "1.0.1", "1.0.0", "1.0.0", None), True),
        (Judged([OPERATIONS], "1.0.0", "1.0.0", "1.0.0", None), False),
        (Judged([OPERATIONS], "1.0.1", "1.0.1", "1.0.0", None), False),
        (Judged([OPERATIONS], "1.0.0", "1.0.1", "1.0.0", None), False),
        (Judged([OPERATIONS], None, "1.0.0", "1.0.0", None), False),
        (Judged([OPERATIONS], "1.0.2", "1.0.2", "1.0.0", "1.0.1"), True),
    ],
    ids=[
        "고친_헌법_파일이_없다",
        "main_과_merge_base_둘과_다르다",
        "둘과_같다",
        "main_이_같은_판을_먼저_매겼다",
        "merge_base_의_판_그대로다",
        "판_줄이_없다",
        "main_이_이_가지_몫으로_비워_둔_판의_문장을_지웠다",
    ],
)
def test_판을_올렸는지는_main_과_merge_base_의_판_둘과_다른지로_본다(
    judged: Judged, *, 기대: bool
) -> None:
    assert judged.passes is 기대


def test_헌법_파일을_고치고_판을_올리지_않으면_막는다(저장소: tuple[Path, Path]) -> None:
    """거버넌스의 semver 문장이 있는데도 PR 열하나(#19~#50)가 판을 올리지 않았다(대기열 31)."""
    work, _ = 저장소
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n"})

    code, 출력 = _판정(work)

    assert code == 1
    assert "판을 올리지 않았다" in 출력
    assert OPERATIONS in 출력
    assert "1.0.0" in 출력
    # 막는 글은 이력 문단을 더하라는 말 대신 비워 둔 판의 신호와 까닭을 적을 자리를 알려 준다
    assert "이력 문단" not in 출력
    assert "비워 둔" in 출력
    assert "ADR 이력이나 일지" in 출력


def test_같은_커밋에서_판을_올리면_지나간다(저장소: tuple[Path, Path]) -> None:
    work, _ = 저장소
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.1")})

    code, 출력 = _판정(work)

    assert code == 0, 출력


def test_못_보는_것_고친_커밋과_판을_올린_커밋을_나누면_앞_커밋이_막힌다(
    저장소: tuple[Path, Path],
) -> None:
    """판정은 커밋에 들 판이라, 가지 전체로는 판을 올렸어도 판을 올리기 전의 커밋은 막힌다(잘못
    막는다). 판을 올린 커밋은 지나간다."""
    work, _ = 저장소
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n"})

    assert _판정(work)[0] == 1

    _git(work, "commit", "-q", "-m", "고친 커밋")
    _스테이지한다(work, {README: _헌법("1.0.1")})

    assert _판정(work)[0] == 0


def test_못_보는_것_판_줄만_바뀌면_크기와_까닭을_적었는지는_보지_않고_지나간다(
    저장소: tuple[Path, Path],
) -> None:
    """문구 하나를 고치고 major 로 올리며 까닭을 어디에도 적지 않아도 지나간다(놓친다). 헌법
    README 에는 판 줄 곁에 비워 둔 판의 문장만 있고 이력 문단이 없다."""
    work, _ = 저장소
    _스테이지한다(work, {OPERATIONS: "운영의 문구\n", README: _헌법("2.0.0")})

    code, 출력 = _판정(work)

    assert code == 0, 출력
    assert "2.0.0은" not in (work / README).read_text(encoding="utf-8")


def test_앞_커밋에서_판을_올렸으면_다른_헌법_파일만_고친_커밋도_지나간다(
    저장소: tuple[Path, Path],
) -> None:
    """판은 가지(PR)마다 한 번 올린다. 헌법 README 의 2.4.0 이 PR 열하나를 한 번에 묶었다."""
    work, _ = 저장소
    _커밋한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.1")}, "운영")
    _스테이지한다(work, {TECH: "스택을 고쳤다\n"})

    code, 출력 = _판정(work)

    assert code == 0, 출력


def test_main_이_같은_판을_먼저_매겼으면_막는다(저장소: tuple[Path, Path]) -> None:
    work, pusher = 저장소
    _main_에_민다(work, pusher, {TECH: "그쪽 스택\n", README: _헌법("1.0.1")})
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.1")})

    code, 출력 = _판정(work)

    assert code == 1
    assert "판을 올리지 않았다" in 출력


def test_main_이_이_가지_몫으로_비워_둔_판의_문장을_지웠으면_지나간다(
    저장소: tuple[Path, Path],
) -> None:
    """main 을 합치며 판 줄을 main 의 것으로 두고 이 가지 몫으로 비워 둔 문장을 지우는 모양이다
    (대기열 279, retro-queue-per-item 06, `tools/sibling_overlap.py` 의 `reserved_version`)."""
    work, pusher = 저장소
    _main_에_민다(work, pusher, {TECH: "그쪽 스택\n", README: _헌법("1.0.2", RESERVE)})
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.2")})

    code, 출력 = _판정(work)

    assert code == 0, 출력


def test_비워_둔_판의_문장을_지우지_않고_판_줄만_main_과_같으면_막는다(
    저장소: tuple[Path, Path],
) -> None:
    """판 줄이 main 과 같아도 main 이 이 가지 몫으로 비워 둔 문장을 그대로 두면 판을 가져가지 않은
    것이다. 다른 가지 몫의 문장을 지운 것도 이 가지의 판이 아니다."""
    work, pusher = 저장소
    other = "1.0.3은 함께 돌던 형제 브랜치(`other`)가 먼저 매겨 비워 두었다."
    main_헌법 = _헌법("1.0.4", f"{RESERVE}\n{other}")
    _main_에_민다(work, pusher, {TECH: "그쪽 스택\n", README: main_헌법})
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: main_헌법})

    assert _판정(work)[0] == 1

    _스테이지한다(work, {README: _헌법("1.0.4", RESERVE)})

    assert _판정(work)[0] == 1

    _스테이지한다(work, {README: _헌법("1.0.4", other)})

    assert _판정(work)[0] == 0


def test_main_이_고친_헌법_파일은_이_가지가_고친_것으로_세지_않는다(
    저장소: tuple[Path, Path],
) -> None:
    """main 을 합치는 커밋의 색인은 merge-base 와 견주면 main 의 변경이 모두 든다. main 과 같은
    파일은 main 이 들여온 것이다(`tools/sibling_overlap.py` 의 `_own_changes`)."""
    work, pusher = 저장소
    _커밋한다(work, {"README.md": "이 가지\n"}, "가지")
    _main_에_민다(work, pusher, {OPERATIONS: "그쪽 운영\n", README: _헌법("1.0.1")})
    _git(work, "merge", "-q", "--no-commit", "--no-ff", "origin/main")

    code, 출력 = _판정(work)

    assert code == 0, 출력


def _dev_가_판을_올렸다(work: Path, pusher: Path, version: str) -> None:
    """원격에 main 에서 딴 dev 를 두고 dev 에서 헌법 판을 올린 뒤 작업 클론이 받아 온다."""
    _git(pusher, "checkout", "-q", "-b", "dev", "main")
    _커밋한다(pusher, {README: _헌법(version)}, "dev 가 판을 올린다")
    _git(pusher, "push", "-q", "origin", "dev")
    _git(work, "fetch", "-q", "origin")


def test_origin_dev_가_있으면_dev_가_먼저_매긴_판과_겹치면_막고_dev_를_기준으로_알린다(
    저장소: tuple[Path, Path],
) -> None:
    work, pusher = 저장소
    _dev_가_판을_올렸다(work, pusher, "1.0.1")
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.1")})

    code, 출력 = _판정(work)

    assert code == 1
    assert "origin/dev" in 출력
    assert "origin/main" not in 출력


def test_origin_dev_가_있어도_hotfix_브랜치는_main_을_기준으로_판을_견준다(
    저장소: tuple[Path, Path],
) -> None:
    """같은 변경이라도 기준이 main 이면 dev 의 판과 겹치지 않아 지나간다."""
    work, pusher = 저장소
    _dev_가_판을_올렸다(work, pusher, "1.0.1")
    _git(work, "checkout", "-q", "-b", "hotfix/x")
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.1")})

    code, 출력 = _판정(work)

    assert code == 0, 출력


def test_색인을_보고_작업_트리에서만_올린_판은_세지_않는다(저장소: tuple[Path, Path]) -> None:
    work, _ = 저장소
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n"})
    _쓴다(work, {README: _헌법("1.0.1")})

    assert _판정(work)[0] == 1


def test_origin_main_이_없으면_판정하지_못했다고_2다(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _커밋한다(tmp_path, SEED, "씨앗")
    _스테이지한다(tmp_path, {OPERATIONS: "운영을 고쳤다\n"})

    code, 출력 = _판정(tmp_path)

    assert code == 2
    assert "origin/main" in 출력


def test_git_저장소_밖이면_그렇게_알리고_2다(tmp_path: Path) -> None:
    code, 출력 = _판정(tmp_path)

    assert code == 2
    assert "git 저장소 안이 아니다" in 출력
    assert "origin/main 이 없다" not in 출력


def test_얕은_클론에서_merge_base_가_없으면_2이고_안내한_명령으로_이력을_받으면_판정한다(
    tmp_path: Path,
) -> None:
    """가지와 main 을 깊이 1로 받으면 공통 조상이 없다. 안내한 명령을 그대로 쳐서 풀리는지 본다."""
    _, pusher = _원격과_클론(tmp_path)
    _git(pusher, "checkout", "-q", "-b", "topic")
    _커밋한다(pusher, {"README.md": "가지\n"}, "가지")
    _git(pusher, "push", "-q", "origin", "topic")
    _git(pusher, "checkout", "-q", "main")
    _커밋한다(pusher, {TECH: "그쪽 스택\n"}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    shallow = tmp_path / "shallow"
    remote = (tmp_path / "origin.git").as_uri()
    _git(tmp_path, "clone", "-q", "--depth", "1", "--branch", "topic", remote, str(shallow))
    _git(shallow, "fetch", "-q", "--depth", "1", "origin", "main:refs/remotes/origin/main")
    _스테이지한다(shallow, {OPERATIONS: "운영을 고쳤다\n"})

    code, 출력 = _판정(shallow)

    assert code == 2
    assert "merge-base 가 없다" in 출력
    assert "`git fetch --unshallow origin`" in 출력

    _git(shallow, "fetch", "-q", "--unshallow", "origin")
    code, 출력 = _판정(shallow)

    assert code == 1, 출력
    assert "판을 올리지 않았다" in 출력


def _이_훅만_든_설정(tmp_path: Path) -> Path:
    """이 저장소의 `.pre-commit-config.yaml` 에서 이 검사의 훅 항목만 떼어 낸 설정. 명령은 종료
    3으로 끝나는 파이썬으로 바꿔, 훅이 돌았는지만 본다(`files` 와 `pass_filenames` 는 그대로다)."""
    lines = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8").splitlines()
    start = lines.index("      - id: check-constitution-version")
    end = next(
        (
            at
            for at in range(start + 1, len(lines))
            if lines[at].startswith(("      - ", "      #"))
        ),
        len(lines),
    )
    python = Path(sys.executable).as_posix()
    hook = [
        f'        entry: {python} -c "raise SystemExit(3)"'
        if line.startswith("        entry:")
        else line
        for line in lines[start:end]
    ]
    assert any(line.startswith("        files:") for line in hook)
    config = tmp_path / "hook.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n" + "\n".join(hook) + "\n", encoding="utf-8"
    )
    return config


def _pre_commit_을_돌린다(work: Path, config: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-m", "pre_commit", "run", "--config", str(config)],
        cwd=work,
        capture_output=True,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
        timeout=120,
    )
    return done.stdout.decode("utf-8") + done.stderr.decode("utf-8")


def test_못_보는_것_헌법_파일을_지우기만_한_커밋에는_pre_commit_이_이_검사를_띄우지_않는다(
    저장소: tuple[Path, Path], tmp_path: Path
) -> None:
    """pre-commit 은 지운 파일을 훅의 `files` 거르기에 넘기지 않는다(놓친다). 같은 색인에 도구를
    바로 부르면 막는다. 헌법 파일을 고친 커밋에서는 같은 설정의 훅이 돈다."""
    work, _ = 저장소
    config = _이_훅만_든_설정(tmp_path)
    _git(work, "rm", "-q", TECH)

    출력 = _pre_commit_을_돌린다(work, config)

    assert "(no files to check)Skipped" in 출력, 출력
    assert _판정(work)[0] == 1

    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n"})
    출력 = _pre_commit_을_돌린다(work, config)

    assert "exit code: 3" in 출력, 출력


def test_못_보는_것_받지_않은_main_이_같은_판을_먼저_매겼어도_지나간다(
    저장소: tuple[Path, Path],
) -> None:
    """`origin/main` 은 로컬의 것이다(놓친다). 받아 오면 막는다."""
    work, pusher = 저장소
    _커밋한다(pusher, {TECH: "그쪽 스택\n", README: _헌법("1.0.1")}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.1")})

    assert _판정(work)[0] == 0

    _git(work, "fetch", "-q", "origin")

    assert _판정(work)[0] == 1


def test_못_보는_것_분리_HEAD_에서는_비워_둔_판을_찾지_못해_막는다(
    저장소: tuple[Path, Path],
) -> None:
    """비워 둔 판은 브랜치 이름으로 찾는다(잘못 막는다). 같은 색인이 가지 위에서는 지나간다."""
    work, pusher = 저장소
    _main_에_민다(work, pusher, {TECH: "그쪽 스택\n", README: _헌법("1.0.2", RESERVE)})
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n", README: _헌법("1.0.2")})

    assert _판정(work)[0] == 0

    _git(work, "checkout", "-q", "--detach")
    code, 출력 = _판정(work)

    assert code == 1
    assert "판을 올리지 않았다" in 출력


def test_인자가_둘_이상이면_2다(tmp_path: Path) -> None:
    줄: list[str] = []

    assert main([str(tmp_path), str(tmp_path)], out=줄.append) == 2
    assert 줄 == ["사용: uv run python -m tools.check_constitution_version [저장소 루트]"]


def test_pre_commit_처럼_띄우면_막는_까닭을_UTF_8_로_알린다(저장소: tuple[Path, Path]) -> None:
    """pre-commit 은 `uv run python -m tools.check_constitution_version` 으로 띄운다. 훅 환경에
    `PYTHONUTF8` 이 있다고 가정하지 않는다. 자식의 `PYTHONIOENCODING` 을 cp949 로 두어, 로캘이
    UTF-8 인 곳에서도 다시 열기를 빼면 빨갛게 한다."""
    work, _ = 저장소
    _스테이지한다(work, {OPERATIONS: "운영을 고쳤다\n"})

    done = subprocess.run(
        [sys.executable, "-m", "tools.check_constitution_version", str(work)],
        cwd=ROOT,
        capture_output=True,
        env={**hook_environment(), "PYTHONIOENCODING": "cp949"},
        check=False,
        timeout=60,
    )
    stdout = done.stdout.decode("utf-8")

    assert done.returncode == 1, done.stderr.decode("utf-8", "replace")
    assert "판을 올리지 않았다" in stdout
    assert OPERATIONS in stdout
