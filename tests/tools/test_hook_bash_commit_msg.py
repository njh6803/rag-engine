"""tools/hook_bash_commit_msg.py 의 함수. 판정은 tools/check_commit_msg.py 의 사본을 실제로 띄워
받는다. main 은 실제 실행(tools/run_hooks.py)으로 본다."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from tools.check_commit_msg import problems_for
from tools.hook_bash_commit_msg import (
    MessageFile,
    ancestors,
    checker_for,
    deny_reason,
    message_files,
    problems_of,
    resolve,
)

ROOT = Path(__file__).resolve().parents[2]
# 대기열 222 셋째 사건(일지 2026-10-13-30)의 제목 길이 76자를 흉내 낸다.
_긴_제목 = "chore: " + "가" * 69
_맞는_제목 = "chore: 커밋 메시지 제목을 먼저 대 본다"
_HOME = "/home/u"
_IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@localhost")


def _판정_파일(path: Path, *, commit_msg_hook: bool = True) -> Path:
    """commit-msg 판정을 부르는 pre-commit 설정과 그 스크립트의 사본을 둔다."""
    (path / "tools").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "tools" / "check_commit_msg.py", path / "tools" / "check_commit_msg.py")
    entry = "uv run python tools/check_commit_msg.py" if commit_msg_hook else "uv run ruff check"
    (path / ".pre-commit-config.yaml").write_text(f"entry: {entry}\n", encoding="utf-8")
    return path


def _저장소(path: Path, *, commit_msg_hook: bool = True) -> Path:
    """`.git` 이 있는 폴더(git 을 띄우지 않는다)에 판정 파일을 둔다. 이 폴더가 곧 이 훅의 저장소인
    시험에서 쓴다."""
    (path / ".git").mkdir(parents=True)
    return _판정_파일(path, commit_msg_hook=commit_msg_hook)


def _git(*args: str) -> None:
    subprocess.run(["git", *_IDENTITY, *args], check=True, capture_output=True, timeout=60)


def _git_저장소(path: Path) -> Path:
    """커밋이 하나 있는 실제 git 저장소에 판정 파일을 둔다."""
    _git("init", "-q", str(path))
    _git("-C", str(path), "commit", "-q", "--allow-empty", "-m", "init")
    return _판정_파일(path)


def _워크트리(main: Path, path: Path) -> Path:
    """`main` 에 등록한 워크트리에 판정 파일을 둔다."""
    _git("-C", str(main), "worktree", "add", "-q", "-b", path.name, str(path))
    return _판정_파일(path)


def _판정(path: Path) -> str:
    return f"{path.as_posix()}/tools/check_commit_msg.py"


@pytest.fixture
def 저장소(tmp_path: Path) -> str:
    """제목이 긴 `long.txt` 와 맞는 `good.txt` 를 루트와 하위 폴더 `sub` 에 둔 저장소."""
    repo = _저장소(tmp_path / "repo")
    for folder in (repo, repo / "sub"):
        folder.mkdir(exist_ok=True)
        (folder / "long.txt").write_text(f"{_긴_제목}\n\n본문\n", encoding="utf-8")
        (folder / "good.txt").write_text(f"{_맞는_제목}\n\n본문\n", encoding="utf-8")
    return repo.as_posix()


def _파일들(command: str) -> list[str]:
    return [message.file for message in message_files(command)]


def test_git_commit_의_F_와_file_인자를_찾는다() -> None:
    assert _파일들("git commit -F msg.txt") == ["msg.txt"]
    assert _파일들("git commit -Fmsg.txt") == ["msg.txt"]
    assert _파일들("git commit --file msg.txt") == ["msg.txt"]
    assert _파일들("git commit --file=msg.txt") == ["msg.txt"]
    assert _파일들("git commit -aF msg.txt") == ["msg.txt"]
    assert _파일들("git commit --amend -F 'a b.txt'") == ["a b.txt"]


def test_줄_끝_역슬래시로_이은_경로도_찾는다() -> None:
    """트랜스크립트에 흔한 모양이다(명세 축 셀프 리뷰가 잡았다)."""
    assert _파일들("git commit -F \\\n  msg.txt") == ["msg.txt"]


def test_SKIP_으로_commit_msg_를_건너뛰면_보지_않는다() -> None:
    assert _파일들("SKIP=commit-msg git commit -F msg.txt") == []
    assert _파일들("SKIP=ruff-check,commit-msg git commit -F msg.txt") == []
    assert _파일들("SKIP=ruff-check git commit -F msg.txt") == ["msg.txt"]


def test_F_가_여럿이면_마지막_것만_본다() -> None:
    """git 은 마지막 `-F` 를 메시지로 쓴다. 앞의 것으로 막으면 거짓 양성이다."""
    assert _파일들("git commit -F bad.txt -F good.txt") == ["good.txt"]


def test_git_의_C_폴더를_함께_준다() -> None:
    assert message_files("git -C sub commit -F msg.txt") == [MessageFile("sub", "msg.txt")]
    assert message_files("git -C a -C b commit -F m") == [MessageFile("a/b", "m")]


def test_체인과_줄바꿈_뒤의_커밋도_찾는다() -> None:
    command = "uv run pytest -q && git commit -F a.txt; echo ok\ngit commit -F b.txt"

    assert _파일들(command) == ["a.txt", "b.txt"]


def test_다른_옵션의_값은_파일로_보지_않는다() -> None:
    assert _파일들("git commit -m F") == []
    assert _파일들("git commit -mFix") == []
    assert _파일들("git commit --author F -m x") == []
    assert _파일들("git -c user.name=F commit -m x") == []
    assert _파일들("git commit -- -F msg.txt") == []


def test_커밋이_아니거나_표준_입력이면_찾지_않는다() -> None:
    """못 보는 것: `-F -`(heredoc 으로 넘긴 메시지)와 `-m` 은 보지 않는다."""
    assert _파일들("git commit -F - <<'EOF'\nchore: x\nEOF") == []
    assert _파일들("git log -F x") == []
    assert _파일들("echo git commit -F x") == []
    assert _파일들('git commit -m "chore: x"') == []


def test_git_을_다른_이름으로_부르면_찾지_않는다() -> None:
    """못 보는 것: `command git`, 전체 경로."""
    assert _파일들("command git commit -F msg.txt") == []
    assert _파일들("/usr/bin/git commit -F msg.txt") == []


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -F msg.txt",
        "git commit -nF msg.txt",
        "git commit -e -F msg.txt",
        "git commit --edit -F msg.txt",
        "git commit --squash=HEAD -F msg.txt",
        "git commit --fixup HEAD -F msg.txt",
        "git commit --cleanup=verbatim -F msg.txt",
        "git commit --dry-run -F msg.txt",
        "git commit --help -F msg.txt",
        "git commit -h -F msg.txt",
        "git -c core.hooksPath=/dev/null commit -F msg.txt",
        "export SKIP=commit-msg && git commit -F msg.txt",
        "SKIP=commit-msg; git commit -F msg.txt",
    ],
)
def test_메시지가_파일_그대로가_아니거나_훅을_건너뛰는_커밋은_보지_않는다(command: str) -> None:
    assert message_files(command) == []


def test_같은_명령에서_쓰는_파일은_보지_않는다() -> None:
    """PreToolUse 에서는 아직 없거나 옛 내용이다. 옛 내용으로 막으면 거짓 양성이다."""
    assert _파일들("printf 'chore: x\\n' > msg.txt && git commit -F msg.txt") == []
    assert _파일들("cp a.txt msg.txt; git commit -F msg.txt") == []


def test_철자가_달라도_같은_경로면_같은_파일이다() -> None:
    """PR 직전 버그 리뷰가 잡았다. 글자 그대로 견주면 옛 내용으로 막는다."""
    assert _파일들("printf x > ./msg.txt && git commit -F msg.txt") == []
    assert _파일들("printf x > msg.txt && git commit -F ./msg.txt") == []


def test_커밋_뒤의_명령은_보지_않는다() -> None:
    """뒤의 명령은 커밋이 읽는 내용을 바꾸지 않는다. 흔한 `&& rm <파일>` 도 판정한다."""
    assert _파일들("git commit -F msg.txt && rm msg.txt") == ["msg.txt"]


def test_앞에_cd_가_있으면_보지_않는다() -> None:
    """못 보는 것: 상대 경로가 어디서 풀릴지 모른다."""
    assert _파일들("cd sub && git commit -F msg.txt") == []
    assert _파일들("git commit -F msg.txt && cd sub") == ["msg.txt"]


def test_heredoc_본문은_명령으로_읽지_않는다() -> None:
    """본문의 `git commit -F` 줄은 커밋이 아니고, 본문의 작은따옴표도 파싱을 깨지 않는다."""
    assert _파일들("cat > run.sh <<EOF\ngit commit -F m.txt\nEOF") == []
    assert _파일들("git commit -F msg.txt\ncat <<EOF\ndon't\nEOF") == ["msg.txt"]


def test_짝_없는_따옴표는_shlex_가_거절해_찾지_않는다() -> None:
    """못 보는 것: 짝 없는 따옴표."""
    assert _파일들("git commit -F 'msg.txt") == []


def test_env_로_부르거나_앞_호출에서_export_한_SKIP_은_모른다() -> None:
    """못 보는 것: `env … git` 은 git 을 다른 이름으로 부르는 것이라 지나간다. 앞 호출에서 export 한
    `SKIP` 은 이 명령에 없어 판정한다(거짓 양성)."""
    assert _파일들("env SKIP=commit-msg git commit -F msg.txt") == []
    assert _파일들("git commit -F msg.txt") == ["msg.txt"]


def test_파일을_cwd_에서_푼다(tmp_path: Path) -> None:
    cwd = tmp_path.as_posix()

    assert resolve("msg.txt", cwd, _HOME) == f"{cwd}/msg.txt"
    assert resolve("/c/x/msg.txt", cwd, _HOME) == "C:/x/msg.txt"
    assert resolve("~/msg.txt", cwd, _HOME) == "/home/u/msg.txt"
    assert resolve("$TMP/msg.txt", cwd, _HOME) is None


def test_판정_스크립트는_커밋하는_저장소의_것이다(tmp_path: Path) -> None:
    repo = _저장소(tmp_path / "repo")
    (repo / "sub").mkdir()
    bare = _저장소(tmp_path / "bare", commit_msg_hook=False)

    assert checker_for((repo / "sub").as_posix(), own=repo.as_posix()) == _판정(repo)
    assert checker_for(bare.as_posix(), own=bare.as_posix()) is None
    assert checker_for((tmp_path / "nowhere").as_posix(), own=repo.as_posix()) is None


def test_이_훅의_저장소는_주_체크아웃과_등록된_워크트리다(tmp_path: Path) -> None:
    """워크트리 세션에서는 훅 파일이 주 체크아웃의 것이어도 판정은 그 워크트리의 스크립트가 한다.
    거꾸로 워크트리의 훅 파일이 주 체크아웃의 커밋을 판정하기도 한다."""
    main = _git_저장소(tmp_path / "agent")
    worktree = _워크트리(main, main / ".claude" / "worktrees" / "wt")
    (main / "sub").mkdir()

    assert checker_for(worktree.as_posix(), own=main.as_posix()) == _판정(worktree)
    assert checker_for((main / "sub").as_posix(), own=worktree.as_posix()) == _판정(main)


def test_이_훅의_저장소_밖이면_판정_스크립트를_고르지_않는다(tmp_path: Path) -> None:
    """대기열 246. 커밋 폴더의 가장 가까운 `.git` 조상이 그 저장소다. 이 훅의 저장소 안에 든 다른
    저장소(중첩 저장소)도 밖이다."""
    main = _git_저장소(tmp_path / "agent")
    other = _git_저장소(tmp_path / "other")
    nested = _git_저장소(main / "vendor" / "lib")

    assert checker_for(other.as_posix(), own=main.as_posix()) is None
    assert checker_for(nested.as_posix(), own=main.as_posix()) is None


def test_등록되지_않은_폴더의_git_파일이_이_저장소를_가리켜도_밖이다(tmp_path: Path) -> None:
    """커밋 폴더의 `.git` 만 읽으면 이 저장소의 워크트리 관리 폴더를 가리키게 지은 폴더를 이
    저장소로 읽는다. 등록(`worktrees/<이름>/gitdir`)에서 거꾸로 대 본다."""
    main = _git_저장소(tmp_path / "agent")
    _워크트리(main, tmp_path / "wt")
    fake = _판정_파일(tmp_path / "fake")
    admin = (main / ".git" / "worktrees" / "wt").as_posix()
    (fake / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")

    assert checker_for(fake.as_posix(), own=main.as_posix()) is None


def test_지운_워크트리의_남은_등록_자리에_새로_만든_저장소는_밖이다(tmp_path: Path) -> None:
    """워크트리 폴더를 git 없이 지우면 등록(`worktrees/<이름>/gitdir`)이 남는다. 그 자리에 새로 만든
    저장소는 이 저장소가 아니다. 등록된 워크트리의 `.git` 이 그 등록을 다시 가리킬 때만 센다(PR 직전
    버그 축이 재현했다)."""
    main = _git_저장소(tmp_path / "agent")
    worktree = _워크트리(main, tmp_path / "wt")
    assert checker_for(worktree.as_posix(), own=main.as_posix()) == _판정(worktree)

    shutil.rmtree(worktree)
    _git_저장소(worktree)

    assert checker_for(worktree.as_posix(), own=main.as_posix()) is None


def test_지운_워크트리_자리의_git_파일이_다른_저장소를_가리키면_밖이다(tmp_path: Path) -> None:
    """남은 등록이 가리키는 자리에 `.git` 파일이 있어도, 그 파일이 이 등록이 아니라 다른 저장소를
    가리키면 이 저장소가 아니다."""
    main = _git_저장소(tmp_path / "agent")
    worktree = _워크트리(main, tmp_path / "wt")
    other = _git_저장소(tmp_path / "other")
    shutil.rmtree(worktree)
    _판정_파일(worktree)
    (worktree / ".git").write_text(f"gitdir: {(other / '.git').as_posix()}\n", encoding="utf-8")

    assert checker_for(worktree.as_posix(), own=main.as_posix()) is None


def test_드라이브_루트까지_같은_절대_경로로_거슬러_올라간다() -> None:
    """드라이브 문자만 남은 `C:` 는 윈도에서 현재 폴더 기준이다. `C:/` 로 맞춰야 존재 확인, 경계
    판정, 설정 읽기, 판정 스크립트가 같은 자리를 본다(PR 직전 보안 리뷰)."""
    assert ancestors("C:/a/b") == ["C:/a/b", "C:/a", "C:/"]
    assert ancestors("/a/b/") == ["/a/b", "/a", "/"]


def test_못_보는_것_separate_git_dir_저장소의_워크트리에서는_주_체크아웃이_밖이다(
    tmp_path: Path,
) -> None:
    """거짓 음성이다. 공통 폴더의 이름이 `.git` 이 아니라 그 부모를 주 체크아웃으로 세지 않는다.
    반대로 주 체크아웃에 든 훅은 자신과 등록된 워크트리를 안다(PR 직전 버그 축)."""
    main = tmp_path / "sepmain"
    _git("init", "-q", "--separate-git-dir", str(tmp_path / "sep.gitdir"), str(main))
    _git("-C", str(main), "commit", "-q", "--allow-empty", "-m", "init")
    _판정_파일(main)
    worktree = _워크트리(main, tmp_path / "sepwt")

    assert checker_for(main.as_posix(), own=worktree.as_posix()) is None
    assert checker_for(worktree.as_posix(), own=main.as_posix()) == _판정(worktree)
    assert checker_for(main.as_posix(), own=main.as_posix()) == _판정(main)


def test_이_훅의_체크아웃에_git_이_없으면_모든_저장소가_밖이다(tmp_path: Path) -> None:
    """못 보는 것(거짓 음성). 훅의 체크아웃을 읽지 못하면 판정하지 않고 지나간다."""
    repo = _git_저장소(tmp_path / "repo")
    loose = tmp_path / "loose"
    loose.mkdir()

    assert checker_for(repo.as_posix(), own=loose.as_posix()) is None


def test_판정은_commit_msg_훅과_같다(저장소: str) -> None:
    checker = f"{저장소}/tools/check_commit_msg.py"

    assert problems_of(f"{저장소}/long.txt", checker) == problems_for(_긴_제목)
    assert problems_of(f"{저장소}/good.txt", checker) == []


def test_판정_문장_없이_끝나거나_시간을_넘기면_지나간다(tmp_path: Path) -> None:
    """못 보는 것: 자식이 시간 제한을 넘기거나 판정 문장 없이 끝난다."""
    silent = tmp_path / "silent.py"
    silent.write_text("raise SystemExit(1)\n", encoding="utf-8")
    slow = tmp_path / "slow.py"
    slow.write_text(
        "import time\ntime.sleep(5)\nprint('x')\nraise SystemExit(1)\n", encoding="utf-8"
    )

    assert problems_of("any.txt", silent.as_posix()) == []
    assert problems_of("any.txt", slow.as_posix(), timeout=0.5) == []


def test_제목이_걸리는_커밋을_막는다(저장소: str) -> None:
    reason = deny_reason("git commit -F long.txt", 저장소, _HOME, own=저장소)

    assert reason is not None
    assert "76자 > 72자" in reason
    assert "대기열 222" in reason


def test_절대_경로와_C_로_가리킨_파일도_막는다(저장소: str, tmp_path: Path) -> None:
    outside = tmp_path.as_posix()

    assert deny_reason(f"git -C {저장소} commit -F {저장소}/long.txt", outside, _HOME, own=저장소)
    assert deny_reason(f"git -C {저장소}/sub commit -F long.txt", outside, _HOME, own=저장소)
    assert deny_reason("git -C sub commit -F long.txt", 저장소, _HOME, own=저장소)


def test_이_저장소의_커밋은_밖의_메시지_파일도_판정한다(저장소: str, tmp_path: Path) -> None:
    """스크래치패드에 쓴 메시지 파일로 이 저장소에서 커밋하는 모양이다. 판정은 커밋하는 저장소를
    가르고, 파일이 어디 있는지는 가르지 않는다."""
    scratch = tmp_path / "scratchpad"
    scratch.mkdir()
    (scratch / "msg.txt").write_text(f"{_긴_제목}\n", encoding="utf-8")

    assert deny_reason(f"git commit -F {scratch.as_posix()}/msg.txt", 저장소, _HOME, own=저장소)


def test_제목이_맞으면_지나간다(저장소: str) -> None:
    assert deny_reason("git commit -F good.txt", 저장소, _HOME, own=저장소) is None
    assert deny_reason("git commit -F long.txt -F good.txt", 저장소, _HOME, own=저장소) is None


def test_commit_msg_판정이_없는_저장소는_지나간다(tmp_path: Path) -> None:
    bare = _저장소(tmp_path / "bare", commit_msg_hook=False)
    (bare / "long.txt").write_text(f"{_긴_제목}\n", encoding="utf-8")

    assert (
        deny_reason("git commit -F long.txt", bare.as_posix(), _HOME, own=bare.as_posix()) is None
    )


def test_파일이_없으면_지나간다(저장소: str) -> None:
    assert deny_reason("git commit -F none.txt", 저장소, _HOME, own=저장소) is None


def test_이_훅의_저장소_밖의_커밋은_판정_스크립트를_띄우지_않고_지나간다(tmp_path: Path) -> None:
    """대기열 246. 첫 판은 커밋하는 저장소가 이 프로젝트가 아니어도 그 저장소의 판정 스크립트를 권한
    확인 전에 띄웠다. 밖의 판정 스크립트는 띄워지면 표지 파일을 남기고 제목을 걸리게 한다."""
    main = _저장소(tmp_path / "agent")
    other = _git_저장소(tmp_path / "other")
    ran = tmp_path / "ran.txt"
    (other / "tools" / "check_commit_msg.py").write_text(
        f"from pathlib import Path\nPath({ran.as_posix()!r}).write_text('x')\n"
        "print('제목이 걸린다')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )
    (other / "msg.txt").write_text(f"{_긴_제목}\n", encoding="utf-8")

    assert (
        deny_reason("git commit -F msg.txt", other.as_posix(), _HOME, own=main.as_posix()) is None
    )
    assert not ran.exists()
    # 대조: 그 저장소가 이 훅의 저장소면 띄워 표지를 남기고 막는다
    assert deny_reason("git commit -F msg.txt", other.as_posix(), _HOME, own=other.as_posix())
    assert ran.exists()
