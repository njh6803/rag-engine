"""tools/hook_bash_commit_msg.py 의 함수. 판정은 tools/check_commit_msg.py 의 사본을 실제로 띄워
받는다. main 은 실제 실행(tools/run_hooks.py)으로 본다."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from tools.check_commit_msg import problems_for
from tools.hook_bash_commit_msg import (
    CommitMessage,
    ancestors,
    checker_for,
    commit_messages,
    deny_reason,
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
    return [m.file for m in commit_messages(command) if m.file is not None]


def _글들(command: str) -> list[str]:
    """명령에서 읽은 메시지 글(`-m`, 표준 입력). 파일 인자는 뺀다."""
    return [m.text for m in commit_messages(command) if m.text is not None]


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
    assert commit_messages("git -C sub commit -F msg.txt") == [
        CommitMessage("sub", "msg.txt", None)
    ]
    assert commit_messages("git -C a -C b commit -F m") == [CommitMessage("a/b", "m", None)]


def test_체인과_줄바꿈_뒤의_커밋도_찾는다() -> None:
    command = "uv run pytest -q && git commit -F a.txt; echo ok\ngit commit -F b.txt"

    assert _파일들(command) == ["a.txt", "b.txt"]


def test_다른_옵션의_값은_파일로_보지_않는다() -> None:
    assert _파일들("git commit -m F") == []
    assert _파일들("git commit -mFix") == []
    assert _파일들("git commit --author F -m x") == []
    assert _파일들("git -c user.name=F commit -m x") == []
    assert _파일들("git commit -- -F msg.txt") == []


def test_커밋이_아니면_찾지_않는다() -> None:
    assert commit_messages("git log -F x") == []
    assert commit_messages("git log -m x") == []
    assert commit_messages("echo git commit -F x") == []
    assert commit_messages('echo git commit -m "chore: x"') == []


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
        "git commit --no-verif -F msg.txt",
        "git commit --dry -F msg.txt",
        "git commit --help -F msg.txt",
        "git commit -h -F msg.txt",
        "git -c core.hooksPath=/dev/null commit -F msg.txt",
        "export SKIP=commit-msg && git commit -F msg.txt",
        "SKIP=commit-msg; git commit -F msg.txt",
    ],
)
def test_메시지가_파일_그대로가_아니거나_훅을_건너뛰는_커밋은_보지_않는다(command: str) -> None:
    assert commit_messages(command) == []


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


def test_앞에_cd_가_있으면_그_폴더에서_푼다() -> None:
    """대기열 항목 3회차의 `cd <워크트리> &&` 복합 명령이다. 이동한 폴더를 커밋 폴더로 준다."""
    assert commit_messages("cd sub && git commit -F msg.txt") == [
        CommitMessage("sub", "msg.txt", None)
    ]
    assert commit_messages("cd a; cd b\ngit commit -F m") == [CommitMessage("a/b", "m", None)]
    assert commit_messages("cd /abs && cd rel && git -C x commit -F m") == [
        CommitMessage("/abs/rel/x", "m", None)
    ]
    assert commit_messages("cd a && cd /abs && git commit -F m") == [
        CommitMessage("/abs", "m", None)
    ]
    assert commit_messages("pushd sub && git commit -F msg.txt") == [
        CommitMessage("sub", "msg.txt", None)
    ]
    assert commit_messages("git commit -F msg.txt && cd sub") == [
        CommitMessage("", "msg.txt", None)
    ]


@pytest.mark.parametrize(
    "command",
    [
        "cd - && git commit -F msg.txt",
        "cd && git commit -F msg.txt",
        "cd $WORKTREE && git commit -F msg.txt",
        "cd a b && git commit -F msg.txt",
        "popd && git commit -F msg.txt",
        "cd sub || git commit -F msg.txt",
        "cd sub | git commit -F msg.txt",
        "cd sub & git commit -F msg.txt",
        "(cd sub && git commit -F msg.txt)",
        "(cd sub) && git commit -F msg.txt",
        "cd ~nobody/x && git commit -F msg.txt",
        "pushd +1 && git commit -F msg.txt",
        "{ cd sub; git commit -F msg.txt; }",
        "if true; then cd sub; fi; git commit -F msg.txt",
        "while cd sub; do git commit -F msg.txt; done",
        "! cd sub && git commit -F msg.txt",
    ],
)
def test_이동한_곳을_알_수_없으면_보지_않는다(command: str) -> None:
    """못 보는 것: 상대 경로가 어디서 풀릴지 모른다(거짓 음성). `||`, 파이프, `&`, 괄호 안의 이동은
    뒤의 커밋이 그 폴더에서 돈다고 할 수 없다."""
    assert commit_messages(command) == []


def test_홈_폴더로의_이동은_알_수_있다() -> None:
    """`~` 와 `~/x` 는 `resolve` 가 푼다. `~user/x` 는 풀지 못해 위에서 보지 않는다."""
    assert commit_messages("cd ~ && git commit -F m") == [CommitMessage("~", "m", None)]
    assert commit_messages("cd ~/x && git commit -F m") == [CommitMessage("~/x", "m", None)]


def test_알_수_없는_이동은_절대_경로_이동이_다시_정한다() -> None:
    assert commit_messages("cd - && cd sub && git commit -F m") == []
    assert commit_messages("cd $X; cd /abs && git commit -F m") == [
        CommitMessage("/abs", "m", None)
    ]


def test_cd_복합_명령에서_앞에서_쓰는_파일은_여전히_보지_않는다() -> None:
    assert commit_messages("cd sub && printf x > m.txt && git commit -F m.txt") == []


def test_dash_m_의_메시지를_찾는다() -> None:
    assert _글들('git commit -m "chore: x"') == ["chore: x"]
    assert _글들("git commit -am 'chore: x'") == ["chore: x"]
    assert _글들("git commit -mchore:x") == ["chore:x"]
    assert _글들("git commit --message='chore: x'") == ["chore: x"]
    assert _글들("git commit --message 'chore: x'") == ["chore: x"]
    assert commit_messages('git -C sub commit -m "chore: x"') == [
        CommitMessage("sub", None, "chore: x")
    ]


def test_dash_m_이_여럿이면_git_처럼_빈_줄로_잇는다() -> None:
    assert _글들('git commit -m "chore: x" -m "본문"') == ["chore: x\n\n본문"]


def test_dash_m_옆의_다른_옵션_값은_메시지로_보지_않는다() -> None:
    assert _글들("git commit --author 'a b' -m 'chore: x'") == ["chore: x"]
    assert _글들("git commit -m 'chore: x' -- -m y") == ["chore: x"]
    assert _글들("git commit --amend --no-edit") == []


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x -F msg.txt",
        "git commit -F msg.txt -m x",
        "git commit -C HEAD -m x",
        "git commit -c HEAD -m x",
        "git commit --reuse-message=HEAD -m x",
        "git commit --reedit-message HEAD -m x",
        "git commit --no-verify -m x",
        "git commit -nm x",
        "git commit -e -m x",
        "git commit --fixup HEAD -m x",
        "git commit --dry-run -m x",
        "git commit --no-verif -m x",
        "git commit --dry -m x",
        "git commit --squ=HEAD -m x",
        "git commit --ed -m x",
        "git commit --clean=verbatim -m x",
        "git commit --fix=HEAD -m x",
        "git commit --he -m x",
        "git --config-env=core.hooksPath=HOOKS commit -m x",
        "git --config-env core.hooksPath=HOOKS commit -m x",
        "SKIP=commit-msg git commit -m x",
        "export SKIP=commit-msg && git commit -m x",
        "git -c core.hooksPath=/dev/null commit -m x",
        'git commit -m ""',
        'git commit -m "  "',
    ],
)
def test_메시지가_그대로_쓰이지_않거나_훅을_건너뛰는_dash_m_은_보지_않는다(command: str) -> None:
    """git 은 `-m` 을 `-F`·`-C`·`-c` 와 함께 쓰면 오류로 끝낸다. 빈 메시지도 커밋하지 않는다."""
    assert commit_messages(command) == []


def test_변수와_치환이_든_dash_m_은_보지_않는다() -> None:
    """못 보는 것: 값이 실행 때 정해진다. 작은따옴표 안의 `$` 도 shlex 가 따옴표 종류를 지워 같이
    지나간다(거짓 음성)."""
    assert _글들('git commit -m "chore: $TITLE"') == []
    assert _글들('git commit -m "$(make_title)"') == []
    assert _글들('git commit -m "chore: `date`"') == []
    assert _글들("git commit -m 'chore: costs $5'") == []


_치환_heredoc = "git commit -m \"$(cat <<'EOF'\n{본문}\nEOF\n)\"\n"


def test_dash_m_의_cat_heredoc_치환은_본문을_메시지로_본다() -> None:
    """에이전트가 커밋할 때 가장 흔한 꼴이다."""
    command = _치환_heredoc.format(본문="chore: x\n\n본문 줄\nCo-Authored-By: a")

    assert _글들(command) == ["chore: x\n\n본문 줄\nCo-Authored-By: a"]
    assert _글들("git add . && " + command) == ["chore: x\n\n본문 줄\nCo-Authored-By: a"]


def test_cat_heredoc_치환의_본문_따옴표와_달러는_글자_그대로_본다() -> None:
    """구분자에 따옴표를 붙인 heredoc 은 본문을 글자 그대로 쓴다."""
    command = _치환_heredoc.format(본문="chore: don't $x `y`")

    assert _글들(command) == ["chore: don't $x `y`"]


def test_따옴표_없는_구분자의_heredoc_치환은_보지_않는다() -> None:
    """못 보는 것: 본문의 `$`·백틱이 실행 때 풀린다."""
    command = _치환_heredoc.format(본문="chore: x").replace("<<'EOF'", "<<EOF")

    assert _글들(command) == []


def test_cat_heredoc_말고_다른_치환은_보지_않는다() -> None:
    assert _글들('git commit -m "$(cat msg.txt)"') == []
    assert _글들("git commit -m \"$(echo x; cat <<'EOF'\nchore: x\nEOF\n)\"") == []
    assert _글들("git commit -m \"x $(cat <<'EOF'\nchore: x\nEOF\n)\"") == []


def test_표준_입력_heredoc_의_메시지를_찾는다() -> None:
    """대기열 항목 8회차의 `git commit -F -` 꼴이다."""
    assert _글들("git commit -F - <<'EOF'\nchore: x\n\n본문\nEOF") == ["chore: x\n\n본문\n"]
    assert _글들("git commit -F- <<'EOF'\nchore: x\nEOF") == ["chore: x\n"]
    assert _글들("git commit --file=- <<'EOF'\nchore: x\nEOF") == ["chore: x\n"]
    assert _글들("cat <<'EOF' | git commit -F -\nchore: x\nEOF") == ["chore: x\n"]
    assert _글들("git commit -F - <<-'EOF'\n\tchore: x\n\tEOF") == ["chore: x\n"]
    assert commit_messages("cd sub && git commit -F - <<'EOF'\nchore: x\nEOF") == [
        CommitMessage("sub", None, "chore: x\n")
    ]


def test_여러_줄_명령에서도_커밋이_있는_줄의_heredoc_을_고른다() -> None:
    """앞 줄에 다른 heredoc 이 있어도 커밋 줄에서 연 것의 본문이 메시지다. 줄 번호가 어긋나면
    앞 줄의 본문이나 빈 목록을 받는다."""
    before = "cat <<'X'\n앞 줄의 본문\nX\n"

    assert _글들(before + "git commit -F - <<'EOF'\nchore: x\nEOF") == ["chore: x\n"]
    assert _글들(before + _치환_heredoc.format(본문="chore: y")) == ["chore: y"]
    assert _글들("git add .\n" + _치환_heredoc.format(본문="chore: z")) == ["chore: z"]
    assert _글들('echo "두 줄\n문자열" && git commit -m "chore: w"') == ["chore: w"]


def test_따옴표_없는_구분자라도_본문에_치환이_없으면_본다() -> None:
    assert _글들("git commit -F - <<EOF\nchore: x\nEOF") == ["chore: x\n"]


@pytest.mark.parametrize(
    "command",
    [
        "git commit -F -",
        "echo 'chore: x' | git commit -F -",
        "git commit -F - <<< 'chore: x'",
        "git commit -F - <<EOF\nchore: $X\nEOF",
        "git commit -F - <<'A' <<'B'\nchore: x\nA\nchore: y\nB",
        "git commit -F - -m x <<'EOF'\nchore: x\nEOF",
        "git commit -F - < msg.txt; cat <<'EOF'\nchore: x\nEOF",
        "git commit -F - <msg.txt\ncat <<'EOF'\nchore: x\nEOF",
    ],
)
def test_못_보는_표준_입력은_찾지_않는다(command: str) -> None:
    """못 보는 것: 메시지를 다른 명령이 만들거나 본문이 실행 때 풀리거나 같은 줄에 heredoc 이
    둘이다. `-F -` 와 `-m` 을 함께 쓰는 커밋은 git 이 오류로 끝낸다."""
    assert commit_messages(command) == []


def test_heredoc_본문_줄_끝의_역슬래시는_줄을_잇지_않는다() -> None:
    """본문의 역슬래시 줄바꿈까지 이으면 제목 줄 뒤의 빈 줄이 지워져 옳은 메시지를 막는다."""
    command = "git commit -F - <<'EOF'\nchore: a \\\n\nbody\nEOF"

    assert _글들(command) == ["chore: a \\\n\nbody\n"]
    assert _글들("git commit \\\n  -m \\\n  'chore: x'") == ["chore: x"]


def test_못_보는_것_따옴표_안의_heredoc_표지는_뒤를_삼켜_지나간다() -> None:
    """`-m` 의 여러 줄 글에 `<< 낱말` 이 있으면 heredoc 여는 정규식이 따옴표 안을 가르지 못해 닫는
    따옴표를 삼키고 shlex 가 거절한다(거짓 음성)."""
    assert _글들('git commit -m "chore: x\n\nbody << x\nmore"') == []


def test_표준_입력_heredoc_뒤의_F_파일은_파일로_본다() -> None:
    assert commit_messages("git commit -F - -F msg.txt <<'EOF'\nchore: x\nEOF") == [
        CommitMessage("", "msg.txt", None)
    ]


def test_heredoc_본문은_명령으로_읽지_않는다() -> None:
    """본문의 `git commit -F` 줄은 커밋이 아니고, 본문의 작은따옴표도 파싱을 깨지 않는다."""
    assert _파일들("cat > run.sh <<EOF\ngit commit -F m.txt\nEOF") == []
    assert _파일들("git commit -F msg.txt\ncat <<EOF\ndon't\nEOF") == ["msg.txt"]
    assert _글들("cat > run.sh <<EOF\ngit commit -m 'chore: x'\nEOF") == []


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


def test_dash_m_의_긴_제목을_막는다(저장소: str) -> None:
    """대기열 항목 4~7·9회차의 `git commit -m` 이다."""
    reason = deny_reason(f'git commit -m "{_긴_제목}"', 저장소, _HOME, own=저장소)

    assert reason is not None
    assert "76자 > 72자" in reason
    assert "대기열 222" in reason
    assert deny_reason(f'git commit -am "{_긴_제목}" -m 본문', 저장소, _HOME, own=저장소)


def test_dash_m_의_틀린_타입을_막는다(저장소: str) -> None:
    """대기열 222 의 첫 사건(`ci:` 타입)의 모양이다."""
    reason = deny_reason('git commit -m "ci: 워크플로를 고친다"', 저장소, _HOME, own=저장소)

    assert reason is not None
    assert "타입은 feat" in reason


def test_cd_복합_명령의_커밋을_막고_이동한_폴더에서_파일을_푼다(
    저장소: str, tmp_path: Path
) -> None:
    """대기열 항목 3회차의 `cd <워크트리> && git commit -F` 모양이다. 루트의 파일은 길고 sub 의
    같은 이름 파일은 맞아서, 어느 폴더에서 풀리는지가 판정을 가른다."""
    (Path(저장소) / "msg.txt").write_text(f"{_긴_제목}\n", encoding="utf-8")
    (Path(저장소) / "sub" / "msg.txt").write_text(f"{_맞는_제목}\n", encoding="utf-8")
    outside = tmp_path.as_posix()

    for command in (
        f"cd {저장소} && git commit -F msg.txt",
        f'cd {저장소} && git commit -m "{_긴_제목}"',
    ):
        assert deny_reason(command, outside, _HOME, own=저장소), f"{command!r} 막히지 않았다"
    assert deny_reason("git commit -F msg.txt", 저장소, _HOME, own=저장소)
    assert deny_reason("cd sub && git commit -F msg.txt", 저장소, _HOME, own=저장소) is None


def test_cd_로_다른_저장소에_들어가면_그_저장소의_경계로_본다(tmp_path: Path) -> None:
    """이동한 폴더가 이 훅의 저장소 밖이면 판정 스크립트를 띄우지 않는다(대기열 246)."""
    main = _저장소(tmp_path / "agent")
    other = _git_저장소(tmp_path / "other")
    ran = tmp_path / "ran.txt"
    (other / "tools" / "check_commit_msg.py").write_text(
        f"from pathlib import Path\nPath({ran.as_posix()!r}).write_text('x')\n"
        "print('제목이 걸린다')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )

    command = f'cd {other.as_posix()} && git commit -m "{_긴_제목}"'
    assert deny_reason(command, main.as_posix(), _HOME, own=main.as_posix()) is None
    assert not ran.exists()


def test_표준_입력_heredoc_의_긴_제목을_막는다(저장소: str) -> None:
    """대기열 항목 8회차의 `git commit -F -` 다."""
    command = f"git commit -F - <<'EOF'\n{_긴_제목}\n\n본문\nEOF"

    assert deny_reason(command, 저장소, _HOME, own=저장소)


def test_cat_heredoc_치환의_긴_제목을_막는다(저장소: str) -> None:
    command = _치환_heredoc.format(본문=f"{_긴_제목}\n\n본문\nCo-Authored-By: a")

    assert deny_reason(command, 저장소, _HOME, own=저장소)
    assert deny_reason("git add . && " + command, 저장소, _HOME, own=저장소)


def test_맞는_제목의_dash_m_과_표준_입력은_지나간다(저장소: str) -> None:
    ok = _치환_heredoc.format(본문=f"{_맞는_제목}\n\n본문")

    assert deny_reason(f'git commit -m "{_맞는_제목}"', 저장소, _HOME, own=저장소) is None
    assert deny_reason(ok, 저장소, _HOME, own=저장소) is None
    command = f"git commit -F - <<'EOF'\n{_맞는_제목}\nEOF"
    assert deny_reason(command, 저장소, _HOME, own=저장소) is None


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
    """대기열 246. 첫 버전은 커밋하는 저장소가 이 프로젝트가 아니어도 그 저장소의 판정 스크립트를
    권한 확인 전에 띄웠다. 밖의 판정 스크립트는 띄워지면 표지 파일을 남기고 제목을 걸리게 한다."""
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
