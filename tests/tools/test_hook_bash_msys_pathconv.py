"""tools/hook_bash_msys_pathconv.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

모양 표는 `.scratch/harness/probes/msys_pathconv/run.sh` 가 이 PC 의 Git Bash(MSYS 런타임 3.1.7)에서
낸 A·A2 절을 옮긴 것이다. 기대가 참이면 네이티브 프로그램이 바뀐 인자를 받았다.
"""

from __future__ import annotations

import pytest
import tools.hook_bash_msys_pathconv as hook
from tools.hook_bash_msys_pathconv import context_for, converted_arguments, converts, under_msys
from tools.run_hooks import registered_matchers

PROBED: list[tuple[str, bool]] = [
    ("origin/main:.scratch/retro-queue.md", True),
    ("origin/main:README.md", False),
    ("a76107e:.scratch/retro-queue.md", False),
    ("HEAD:src/agent_os/main.py", False),
    ("origin/main:src/agent_os/main.py", False),
    ("origin/main:src", False),
    ("HEAD~1:tools/canary.py", False),
    ("feature/x:feature/x", False),
    ("HEAD:refs/heads/chore/x", False),
    ("refs/heads/a:refs/remotes/origin/a", False),
    ("a/b:c/d", False),
    ("a/b:c", False),
    ("a:b/c", False),
    ("a/b:c/d:e/f", False),
    ("a/b:c:d/e", False),
    ("origin/main:./src/x.py", False),
    ("https://github.com/a/b", False),
    ("git@github.com:njh6803/agent-os.git", False),
    ("localhost:8000/api", False),
    ("--format=a/b:c/d", False),
    ("x=a/b:c/d", False),
    ("C:/project/agent", False),
    ("@{u}:src/x.py", False),
    (":src/x.py", False),
    (":/message", False),
    ("origin/main:.scratch", True),
    ("origin/main:.env.example", True),
    ("origin/main:.github/workflows/ci.yml", True),
    ("origin/main:/x", True),
    ("origin/main://x", False),
    ("origin/main:../x", False),
    ("origin/main::.x", False),
    ("origin/main:.x::y", False),
    ("HEAD~1:.scratch/x.md", False),
    ("main:.scratch/x.md", False),
    ("origin/main:.scratch/*.md", False),
    ("origin/main:.scratch/[x].md", False),
    ("origin/main:.scratch/x.md:y", True),
    ("origin/main@{1}:.scratch/x.md", True),
    ("origin/~x:.y", False),
    ("a@@b/c:.d", False),
    ("~/x:.y", False),
    ("+refs/heads/a:.b", True),
    ("origin\\main:.x", True),
    ("..:.x", False),
    ("x=origin/main:.x", True),
    ("x=y:origin/main:.x", False),
    ("--format=origin/main:.x", True),
    ("-Lorigin/main:.x", False),
    ("see origin/main:.x", False),
    ("fix: origin/main:.x", False),
    ("a b/c:.d e", False),
    ("origin/main:.sc`x", False),
    ("origin/main:.sc'x", False),
    ("origin/main:.scratch/x?.md", False),
    ("a:b=origin/main:.x", True),
    ("-Lx:origin/main:.y", True),
    ("-x,origin/main:.y", True),
    ("origin/main:.gitignore", True),
    ("@/a:.b", True),
    ("see\torigin/main:.x", False),
    ("see\norigin/main:.x", False),
]


@pytest.mark.parametrize(("argument", "expected"), PROBED)
def test_바뀌는지는_프로브가_잰_것과_같다(argument: str, *, expected: bool) -> None:
    assert converts(argument) is expected


def test_슬래시로_시작하는_인자는_보지_않는다() -> None:
    """거짓 음성이다. 프로브에서 `/c/project:/d/x` 는 `C:\\project;D:\\x` 로 바뀌었다.

    `/` 로 시작하는 인자는 소스에서 다른 갈래라 옮기지 않았다. git 의 `<rev>:<경로>` 꼴이 아니다.
    """
    assert converts("/c/project:/d/x") is False


def test_머리_글자_뒤가_슬래시_둘인_인자는_바뀐다고_잘못_본다() -> None:
    """거짓 양성이다. 프로브에서 `+//:/`·`%//:/` 는 그대로였다.

    MSYS 는 머리 글자를 건너뛰고 `/` 로 시작하는 갈래로 보는데 그 갈래를 옮기지 않았다.
    """
    assert converts("+//:/") is True
    assert converts("%//:/") is True


def test_등호가_수천_개여도_예외_없이_끝까지_본다() -> None:
    """MSYS 는 `=` 마다 뒤를 다시 본다. 재귀로 옮기면 천 개쯤에서 한도를 넘었다(PR 직전 리뷰)."""
    assert converts("=" * 5000) is False
    assert converts("a=" * 3000 + "origin/main:.x") is True
    assert converts("-x," * 3000 + "origin/main:.x") is True


def test_콜론이나_git이_없는_명령은_낱말로_나누지_않는다(monkeypatch: pytest.MonkeyPatch) -> None:
    """모든 Bash 호출에 붙는 훅이다. shlex 는 긴 낱말에 제곱 시간이 들어 미리 거른다."""

    def no_split(command: str) -> list[list[str]]:
        raise AssertionError(f"나누지 말아야 할 명령을 나눴다: {command}")

    monkeypatch.setattr(hook, "_segments", no_split)
    assert converted_arguments("ls -la tools") == []
    assert converted_arguments("git status --short") == []
    assert converted_arguments('python -c "print(1)" origin/main:.x') == []


def test_사건의_명령에서_바뀌는_인자를_찾는다() -> None:
    """일지 2026-10-12-21 의 명령이다."""
    command = "git show origin/main:.scratch/harness/probes/README.md"
    assert converted_arguments(command) == ["origin/main:.scratch/harness/probes/README.md"]


def test_git_옵션과_파이프와_체인_뒤에서도_찾는다() -> None:
    expected = ["origin/main:.scratch/x.md"]
    assert (
        converted_arguments("git -c core.longpaths=true show origin/main:.scratch/x.md | head -5")
        == expected
    )
    assert converted_arguments("cd web && git show origin/main:.scratch/x.md") == expected
    assert converted_arguments("echo hi; git show origin/main:.scratch/x.md") == expected
    assert converted_arguments("echo hi\ngit show origin/main:.scratch/x.md") == expected
    assert (
        converted_arguments("if git cat-file -e origin/main:.scratch/x.md; then echo y; fi")
        == expected
    )


def test_따옴표는_변환을_막지_않아_풀고_본다() -> None:
    """셸이 따옴표를 벗긴 뒤의 인자를 MSYS 가 바꾼다."""
    assert converted_arguments('git show "origin/main:.scratch/x.md"') == [
        "origin/main:.scratch/x.md"
    ]
    assert converted_arguments("git show 'origin/main:.scratch/x.md'") == [
        "origin/main:.scratch/x.md"
    ]


def test_명령_치환과_줄_잇기와_git_경로도_본다() -> None:
    expected = ["origin/main:.x"]
    assert converted_arguments("a=$(git show origin/main:.x)") == expected
    assert converted_arguments("git show \\\n  origin/main:.x") == expected
    assert converted_arguments("/mingw64/bin/git.exe show origin/main:.x") == expected
    assert converted_arguments("GIT_PAGER=cat git show origin/main:.x") == expected
    assert converted_arguments("env git show origin/main:.x") == expected


def test_리다이렉션은_조각을_가르지_않고_대상과_fd만_뺀다() -> None:
    expected = ["origin/main:.x"]
    assert converted_arguments("git show > out.txt origin/main:.x") == expected
    assert converted_arguments("git show >| out.txt origin/main:.x") == expected
    assert converted_arguments("git show 2>/dev/null origin/main:.x") == expected
    assert converted_arguments("2>/dev/null git show origin/main:.x") == expected


def test_주석_뒤의_줄과_산술의_왼쪽_밀기_뒤의_줄도_본다() -> None:
    """shlex 의 주석은 개행까지 먹고, 산술 안의 `<<` 는 heredoc 이 아니다."""
    expected = ["origin/main:.x"]
    assert converted_arguments("echo hi # note\ngit show origin/main:.x") == expected
    assert converted_arguments("echo $((1 << 2))\ngit show origin/main:.x") == expected


def test_바뀌는_인자를_모두_찾는다() -> None:
    command = "git diff origin/main:.a HEAD:.a origin/main:.b"
    assert converted_arguments(command) == ["origin/main:.a", "origin/main:.b"]


def test_변환을_끈_명령은_보지_않는다() -> None:
    assert converted_arguments("MSYS_NO_PATHCONV=1 git show origin/main:.x") == []
    assert converted_arguments("export MSYS_NO_PATHCONV=1\ngit show origin/main:.x") == []
    assert converted_arguments("MSYS2_ARG_CONV_EXCL='*' git show origin/main:.x") == []


def test_MSYS_프로그램의_인자는_바뀌지_않는다() -> None:
    """프로브 B 절. MSYS 프로그램(`/usr/bin/printf`·`/usr/bin/echo`)에 넘긴 인자는 그대로였다."""
    assert converted_arguments("echo origin/main:.x") == []
    assert converted_arguments("grep -n origin/main:.x notes.md") == []


def test_heredoc_본문과_주석과_공백이_든_메시지는_보지_않는다() -> None:
    assert converted_arguments("git commit -F - <<'EOF'\ngit show origin/main:.x\nEOF") == []
    assert converted_arguments("git show HEAD # origin/main:.x") == []
    assert converted_arguments('git commit -m "see origin/main:.x"') == []


def test_here_string은_heredoc이_아니라_뒤의_줄을_본다() -> None:
    command = "git hash-object --stdin <<< x\ngit show origin/main:.x"
    assert converted_arguments(command) == ["origin/main:.x"]


def test_닫히지_않은_따옴표가_든_명령은_보지_않는다() -> None:
    assert converted_arguments('git show "origin/main:.x') == []


def test_git_밖의_네이티브_프로그램은_보지_않는다() -> None:
    """거짓 음성이다. uv·gh·docker 도 네이티브라 같은 인자가 바뀐다(프로브 A 는 uv 로 쟀다)."""
    assert converted_arguments("uv run python tools/x.py origin/main:.x") == []


def test_다른_명령을_거쳐_부른_git은_보지_않는다() -> None:
    """거짓 음성이다. 인용 안의 명령, xargs, 백틱 치환 안의 git 이다."""
    assert converted_arguments('bash -c "git show origin/main:.x"') == []
    assert converted_arguments("printf 'origin/main:.x' | xargs git show") == []
    assert converted_arguments("echo `git show origin/main:.x`") == []


def test_같은_줄의_따옴표_안에_든_왼쪽_화살표_둘_뒤의_줄은_보지_않는다() -> None:
    """거짓 음성이다. 따옴표 안의 `<<` 를 heredoc 으로 읽어 뒤의 줄을 지운다."""
    assert converted_arguments('echo "a << b"\ngit show origin/main:.x') == []


def test_프로세스_치환_뒤의_인자는_보지_않는다() -> None:
    """거짓 음성이다. `<(` 의 괄호가 조각을 가른다."""
    assert converted_arguments("git diff <(echo x) origin/main:.x") == []


def test_변수가_든_인자는_보지_않는다() -> None:
    """거짓 음성이다. 셸이 펼친 값을 모른다. `REV=origin/main` 이면 앞의 것은 바뀐다."""
    assert converted_arguments('git show "$REV:.scratch/x.md"') == []
    assert converted_arguments('git show "origin/main:$f"') == []


def test_heredoc_본문으로_돌리는_git은_보지_않는다() -> None:
    """거짓 음성이다. 본문은 대개 데이터라 벗기는데, 셸이 실행하는 본문도 함께 벗긴다."""
    assert converted_arguments("bash <<'EOF'\ngit show origin/main:.x\nEOF") == []


def test_단어_가운데의_샵_뒤는_보지_않는다() -> None:
    """거짓 음성이다. 셸과 달리 단어 가운데의 `#` 부터 주석으로 읽는다."""
    assert converted_arguments("git show a#b origin/main:.x") == []


def test_같은_명령_어디에든_변환을_끄는_대입이_있으면_보지_않는다() -> None:
    """거짓 음성이다. 끈 조각과 다른 조각의 git 도, `MSYS2_ARG_CONV_EXCL` 의 값이 그 인자를 덮지
    않아도 그렇다."""
    assert converted_arguments("MSYS_NO_PATHCONV=1 git status; git show origin/main:.x") == []
    assert converted_arguments("MSYS2_ARG_CONV_EXCL=--foo git show origin/main:.x") == []


def test_안내는_인자와_우회를_든다() -> None:
    context = context_for("git show origin/main:.scratch/x.md")
    assert context is not None
    assert "`origin/main:.scratch/x.md`" in context
    assert "git 바로 앞에 `MSYS_NO_PATHCONV=1`" in context
    assert "<rev>:./<경로>" in context


def test_바뀌는_인자가_없으면_안내도_없다() -> None:
    assert context_for("git show origin/main:README.md") is None


def test_윈도이거나_MSYSTEM이_있을_때만_Git_Bash로_본다() -> None:
    assert under_msys("nt", {}) is True
    assert under_msys("posix", {"MSYSTEM": "MINGW64"}) is True
    assert under_msys("posix", {}) is False


def test_PowerShell_도구는_보지_않는다() -> None:
    """거짓 음성이다. settings.json 이 이 훅을 Bash 매처에만 건다."""
    assert registered_matchers("hook_bash_msys_pathconv.py", "PreToolUse") == ["Bash"]
