"""tools/hook_bash_cd_outside.py 의 순수 함수. main 은 실제 실행(tools/run_hooks.py)으로 본다."""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest
from tools.hook_bash_cd_outside import (
    cd_steps,
    checkout_of,
    deny_reason,
    normalize,
    resolve,
)


def _저장소(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    return path


def _워크트리(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".git").write_text("gitdir: ../../../.git/worktrees/x\n", encoding="utf-8")
    return path


@pytest.fixture
def 자리(tmp_path: Path) -> dict[str, str]:
    """주 체크아웃 하나와 그 안의 워크트리 둘, `.git` 없는 남은 워크트리 폴더, 체크아웃 밖 폴더."""
    main = _저장소(tmp_path / "agent")
    mine = _워크트리(main / ".claude" / "worktrees" / "mine")
    (mine / "web").mkdir()
    _워크트리(main / ".claude" / "worktrees" / "other")
    leftover = main / ".claude" / "worktrees" / "leftover"
    leftover.mkdir()
    scratch = tmp_path / "scratchpad"
    scratch.mkdir()
    return {
        "main": main.as_posix(),
        "mine": mine.as_posix(),
        "other": (main / ".claude" / "worktrees" / "other").as_posix(),
        "leftover": leftover.as_posix(),
        "scratch": scratch.as_posix(),
    }


def test_경로를_슬래시와_드라이브_대문자로_고른다() -> None:
    assert normalize("/c/project/agent") == "C:/project/agent"
    assert normalize("C:\\project\\agent\\..\\x") == "C:/project/x"
    assert normalize("c:/a//b/") == "C:/a/b"
    assert normalize("/c") == "C:/"
    assert normalize("/tmp/x/../y") == "/tmp/y"


def test_절대_경로가_아니면_고르지_않는다() -> None:
    assert normalize("web") is None
    assert normalize("C:web") is None


def test_대상을_지금_자리에서_푼다() -> None:
    assert resolve("web", "C:/w", "C:/Users/u") == "C:/w/web"
    assert resolve("../..", "C:/a/b/c", "C:/Users/u") == "C:/a"
    assert resolve("/c/x", "C:/w", "C:/Users/u") == "C:/x"
    assert resolve("~", "C:/w", "C:/Users/u") == "C:/Users/u"
    assert resolve("~/tmp", "C:/w", "C:/Users/u") == "C:/Users/u/tmp"


def test_풀_수_없는_대상은_None_이다() -> None:
    assert resolve("C:web", "C:/w", "C:/Users/u") is None
    assert resolve("~other/x", "C:/w", "C:/Users/u") is None
    assert resolve("web", None, "C:/Users/u") is None


def test_작업_폴더를_남기는_cd_를_찾는다() -> None:
    assert cd_steps("cd /c/x && ls") == [("cd", "/c/x")]
    assert cd_steps('cd "C:/Users/a b/x"; grep y z') == [("cd", "C:/Users/a b/x")]
    assert cd_steps("ls\ncd /c/x") == [("cd", "/c/x")]
    assert cd_steps("if cd /c/x; then ls; fi") == [("cd", "/c/x")]
    assert cd_steps("{ cd /c/x; ls; }") == [("cd", "/c/x")]
    assert cd_steps("X=1 cd /c/x") == [("cd", "/c/x")]
    assert cd_steps("cd -P /c/x 2>/dev/null") == [("cd", "/c/x")]
    assert cd_steps("cd -- -dir") == [("cd", "-dir")]
    assert cd_steps("cd \\\n  /c/x") == [("cd", "/c/x")]
    assert cd_steps("2>/dev/null cd /c/x") == [("cd", "/c/x")]
    assert cd_steps("> out.log cd /c/x") == [("cd", "/c/x")]
    assert cd_steps("eval cd /c/x") == [("cd", "/c/x")]


def test_here_string_은_heredoc_이_아니다() -> None:
    """`<<<` 를 heredoc 으로 읽으면 뒤의 줄을 본문으로 지운다(셀프 리뷰가 잡았다)."""
    assert cd_steps("grep x <<< bar\ncd /c/x") == [("cd", "/c/x")]


def test_산술의_왼쪽_밀기는_heredoc_이_아니다() -> None:
    """`$((1 << n))` 의 `<< n` 을 여는 표지로 읽으면 뒤의 줄을 지운다(PR 직전 리뷰가 잡았다)."""
    assert cd_steps("echo $((1 << n))\ncd /c/x") == [("cd", "/c/x")]
    assert cd_steps("(( x <<= 2 ))\ncd /c/x") == [("cd", "/c/x")]


def test_식별자_밖의_구분자와_역슬래시_구분자도_heredoc_이다() -> None:
    """못 알아보면 본문의 cd 를 명령으로 센다(PR 직전 리뷰가 잡았다)."""
    assert cd_steps("cat > f.sh <<'END-OF-FILE'\ncd /c/x\nEND-OF-FILE") == []
    assert cd_steps("cat <<\\EOF\ncd /c/x\nEOF") == []


def test_세미콜론_바로_뒤의_샵도_주석이다() -> None:
    """주석 속 작은따옴표가 인용을 열면 뒤의 cd 를 가린다(PR 직전 리뷰가 잡았다)."""
    assert cd_steps("ls;# it's\ncd /c/x") == [("cd", "/c/x")]


def test_인자_없는_cd_와_되돌리기와_pushd_를_가린다() -> None:
    assert cd_steps("cd") == [("cd", "~")]
    assert cd_steps("cd -") == [("cd", "-")]
    assert cd_steps("pushd /c/x && popd") == [("pushd", "/c/x"), ("popd", None)]


def test_변수와_치환이_든_대상은_None_이다() -> None:
    assert cd_steps('cd "$TMP"') == [("cd", None)]
    assert cd_steps("cd $(git rev-parse --show-toplevel)") == [("cd", None)]
    assert cd_steps("cd /c/x/*") == [("cd", None)]


def test_작업_폴더를_남기지_않는_cd_는_세지_않는다() -> None:
    """서브셸, 명령 치환, 파이프의 한 단, 백그라운드 목록에서 친 cd 는 그 셸 안에서 끝난다."""
    assert cd_steps("(cd /c/x && ls)") == []
    assert cd_steps("(ls; cd /c/x)") == []
    assert cd_steps("x=$(ls; cd /c/x; pwd)") == []
    assert cd_steps("(\ncd /c/x\n)") == []
    assert cd_steps("echo $(cd /c/x; pwd)") == []
    assert cd_steps("echo `cd /c/x`") == []
    assert cd_steps("cd /c/x | cat") == []
    assert cd_steps("cd /c/x &") == []
    assert cd_steps("cd /c/x && ls &") == []
    assert cd_steps("cd /c/x && ls & cd /c/y") == [("cd", "/c/y")]


def test_데이터로_든_cd_는_세지_않는다() -> None:
    assert cd_steps("echo 'cd /c/x'") == []
    assert cd_steps('git commit -m "cd /c/x 를 막는다"') == []
    assert cd_steps("cat <<'EOF' > note.md\ncd /c/x\nEOF") == []
    assert cd_steps("# cd /c/x") == []
    assert cd_steps("ls # (cd 는 나중에\ncd /c/x") == [("cd", "/c/x")]
    assert cd_steps("git -C /c/x log") == []
    assert cd_steps("abcd /c/x") == []


def test_가장_가까운_체크아웃을_고른다(자리: dict[str, str]) -> None:
    assert checkout_of(자리["mine"]) == 자리["mine"]
    assert checkout_of(자리["mine"] + "/web") == 자리["mine"]
    assert checkout_of(자리["mine"] + "/not/yet") == 자리["mine"]
    assert checkout_of(자리["main"] + "/docs") == 자리["main"]
    assert checkout_of(자리["scratch"]) is None


def test_체크아웃_안의_중첩_저장소는_다른_체크아웃이다(자리: dict[str, str]) -> None:
    """그 안에 머문 셸의 git 은 바깥 체크아웃이 아니라 그 저장소를 겨눈다."""
    nested = Path(자리["mine"]) / "probe-repo"
    (nested / ".git").mkdir(parents=True)

    reason = _막는_이유("cd probe-repo", 자리["mine"], 자리)

    assert _다른_체크아웃(nested.as_posix()) in reason


def test_git_없는_워크트리_폴더도_따로_센다(자리: dict[str, str]) -> None:
    """`.git` 이 없어 git 이 주 체크아웃을 루트로 읽는 폴더다(tidy-checkouts 3, 대기열 135)."""
    assert checkout_of(자리["leftover"]) == 자리["leftover"]


def _막는_이유(command: str, cwd: str, 자리: dict[str, str]) -> str:
    """막아야 하는 명령의 이유. 워크트리 가드가 다른 체크아웃을 겨눈 git 을 거부하므로 이유가
    `git -C` 를 대안으로 안내하지 않는지도 본다(일지 2026-10-06-12 회고 2)."""
    reason = deny_reason(command, cwd, 자리["scratch"])
    assert reason is not None, command
    assert "git -C" not in reason
    return reason


def _다른_체크아웃(place: str) -> str:
    return f"다른 체크아웃({place})"


def test_워크트리에서_주_체크아웃으로_옮기면_막는다(자리: dict[str, str]) -> None:
    """일지 2026-10-06-11 의 모양이다. 형제 일지 번호를 보려고 옮겼다."""
    reason = _막는_이유(f"cd {자리['main']}; ls docs/journal", 자리["mine"], 자리)

    assert _다른_체크아웃(자리["main"]) in reason
    assert "EnterWorktree" in reason


def test_체크아웃_밖으로_옮기면_막는다(자리: dict[str, str]) -> None:
    """일지 2026-10-12-09 의 모양이다. 카나리아 출력을 grep 하려고 스크래치패드로 옮겼다(06 도 같은
    자리로 옮겼다)."""
    reason = _막는_이유(f'cd "{자리["scratch"]}" && grep -n x y', 자리["mine"], 자리)

    assert f"체크아웃 밖의 `{자리['scratch']}`" in reason


def test_워크트리에서_남은_워크트리_폴더로_옮기면_막는다(자리: dict[str, str]) -> None:
    """일지 2026-10-07-15 의 모양이다."""
    reason = _막는_이유(f"cd {자리['leftover']} && ls", 자리["mine"], 자리)

    assert _다른_체크아웃(자리["leftover"]) in reason


def test_주_체크아웃에서_다른_워크트리로_옮기면_막는다(자리: dict[str, str]) -> None:
    """tidy-checkouts 를 도는 주 체크아웃 세션의 모양이다(그 스킬의 "하지 않는 것" 줄)."""
    leftover = _막는_이유(f"cd {자리['leftover']} && ls", 자리["main"], 자리)
    other = _막는_이유(f"cd {자리['other']}", 자리["main"], 자리)

    assert _다른_체크아웃(자리["leftover"]) in leftover
    assert _다른_체크아웃(자리["other"]) in other


def test_인자_없는_cd_와_pushd_도_막는다(자리: dict[str, str]) -> None:
    home = _막는_이유("cd", 자리["mine"], 자리)
    pushd = _막는_이유(f"pushd {자리['scratch']} && ls && popd", 자리["mine"], 자리)

    assert f"체크아웃 밖의 `{자리['scratch']}`" in home
    assert f"체크아웃 밖의 `{자리['scratch']}`" in pushd


def test_밖에_들렀다_돌아와도_막는다(자리: dict[str, str]) -> None:
    """들른 사이의 명령이 다른 자리에서 돈다. 중간이 실패하면 돌아오는 cd 도 돌지 않는다."""
    reason = _막는_이유(f"cd {자리['scratch']} && grep x y; cd -", 자리["mine"], 자리)

    assert "체크아웃 밖" in reason


def test_상대_경로를_차례로_풀어_밖으로_나가면_막는다(자리: dict[str, str]) -> None:
    """mine/web/../.. 는 워크트리를 담는 폴더라 주 체크아웃이다."""
    reason = _막는_이유("cd web && cd ../..", 자리["mine"], 자리)

    assert _다른_체크아웃(자리["main"]) in reason


def test_이미_밀려난_세션의_돌아오는_cd_도_막고_길을_안내한다(자리: dict[str, str]) -> None:
    """훅이 보지 못한 길로 주 체크아웃에 와 있는 워크트리 세션이다. 훅은 이 세션의 체크아웃을 몰라
    돌아오는 cd 를 막고, 이유가 `EnterWorktree(path)` 를 안내한다."""
    reason = _막는_이유(f"cd {자리['mine']}", 자리["main"], 자리)

    assert "EnterWorktree(path)" in reason


def test_제_체크아웃_루트로_옮기는_cd_는_지나간다(자리: dict[str, str]) -> None:
    mine, scratch = 자리["mine"], 자리["scratch"]

    assert deny_reason(f"cd {mine} && uv run pytest -q", mine, scratch) is None
    assert deny_reason("cd .", mine, scratch) is None


def test_주_체크아웃_세션의_루트_cd_는_지나간다(자리: dict[str, str]) -> None:
    """이 훅을 만든 세션이 tidy-checkouts 3에서 친 명령의 모양이다(`--running` 을 줄였다)."""
    command = f"cd {자리['main']} && uv run python tools/tidy_checkouts.py judge --running x"

    assert deny_reason(command, 자리["main"], 자리["scratch"]) is None


def test_작업_폴더를_남기지_않으면_지나간다(자리: dict[str, str]) -> None:
    assert deny_reason(f"(cd {자리['main']} && git log)", 자리["mine"], 자리["scratch"]) is None
    assert deny_reason(f"git -C {자리['main']} log", 자리["mine"], 자리["scratch"]) is None
    assert deny_reason(f"ls {자리['scratch']}", 자리["mine"], 자리["scratch"]) is None


def test_지금_자리가_체크아웃_밖이면_돌아오는_cd_를_막지_않는다(자리: dict[str, str]) -> None:
    """어느 체크아웃이 이 세션의 것인지 모른다. 돌아오는 길을 막지 않는다."""
    assert deny_reason(f"cd {자리['mine']}", 자리["scratch"], 자리["scratch"]) is None


def test_풀_수_없는_cd_뒤의_상대_경로는_판정하지_않는다(자리: dict[str, str]) -> None:
    assert deny_reason('cd "$X" && cd ..', 자리["mine"], 자리["scratch"]) is None


def test_대소문자만_다른_경로는_같은_체크아웃이다(자리: dict[str, str]) -> None:
    """윈도의 경로는 대소문자를 가리지 않는다. 손으로 친 대상의 대소문자가 페이로드와 다를 수
    있다."""
    assert deny_reason(f"cd {자리['mine'].upper()}", 자리["mine"], 자리["scratch"]) is None


def test_cwd_의_역슬래시_표기도_같은_자리로_본다(자리: dict[str, str]) -> None:
    cwd = 자리["mine"].replace("/", "\\")

    assert deny_reason(f"cd {자리['mine']}", cwd, 자리["scratch"]) is None
    assert "하위 폴더" in _하위_폴더_이유(f"cd {자리['mine']}/web", cwd, 자리)
    assert _다른_체크아웃(자리["main"]) in _막는_이유(f"cd {자리['main']}", cwd, 자리)


def _하위_폴더_이유(command: str, cwd: str, 자리: dict[str, str]) -> str:
    """하위 폴더로 옮겨 막는 이유. 체크아웃 밖으로 옮기는 이유와 문장이 다르다."""
    reason = deny_reason(command, cwd, 자리["scratch"])
    assert reason is not None, command
    assert "하위 폴더" in reason and "대기열 225·252" in reason
    return reason


def test_하위_폴더로_옮기면_막는다(자리: dict[str, str]) -> None:
    """대기열 225 의 셋째 사건(일지 2026-10-13-22)의 모양이다. 알림을 받은 뒤에도 같은 세션이 두 번
    더 옮겨 막기로 올렸다(대기열 252). 폴더는 없어도 판정한다."""
    command = "cd web/packages/ui/src/components && ls"

    reason = _하위_폴더_이유(command, 자리["mine"], 자리)

    assert f"{자리['mine']}/web/packages/ui/src/components" in reason
    assert "-C" in reason
    assert "( cd" in reason


def test_절대_경로로_하위_폴더에_들어가도_막는다(자리: dict[str, str]) -> None:
    _하위_폴더_이유(f"cd {자리['mine']}/web", 자리["mine"], 자리)


def test_주_체크아웃_세션의_하위_폴더도_막는다(자리: dict[str, str]) -> None:
    """워크트리 폴더도 주 체크아웃의 하위 폴더지만 그것은 다른 체크아웃이라 다른 이유로 막는다."""
    _하위_폴더_이유("cd docs", 자리["main"], 자리)


def test_한_호출_안에서_하위_폴더에_머물러도_막는다(자리: dict[str, str]) -> None:
    """작업 폴더는 다음 호출로 이어진다. 대안(`pnpm -C web`, 서브셸)이 있어 막는 값은 다시 치는
    한 번이다."""
    _하위_폴더_이유("cd web && pnpm verify", 자리["mine"], 자리)


def test_들렀다_돌아와도_막는다(자리: dict[str, str]) -> None:
    """`&&` 중간이 실패하면 돌아오는 cd 가 돌지 않는다. `;` 로 이어 늘 돌아오는 것도 막는다(거짓
    양성, 독스트링의 못 보는 것)."""
    _하위_폴더_이유("cd web && pnpm verify && cd ..", 자리["mine"], 자리)
    _하위_폴더_이유("cd web; pnpm verify; cd ..", 자리["mine"], 자리)


def test_하위_폴더에서_루트로_돌아오는_cd_는_지나간다(자리: dict[str, str]) -> None:
    mine, scratch = 자리["mine"], 자리["scratch"]

    assert deny_reason("cd ..", f"{mine}/web", scratch) is None
    assert deny_reason(f"cd {mine.upper()}", f"{mine}/web", scratch) is None


def test_작업_폴더를_남기지_않는_하위_폴더_cd_는_지나간다(자리: dict[str, str]) -> None:
    mine, scratch = 자리["mine"], 자리["scratch"]

    assert deny_reason("(cd web && pnpm verify)", mine, scratch) is None
    assert deny_reason("pnpm -C web verify", mine, scratch) is None
    assert deny_reason("cd web | cat", mine, scratch) is None


def test_밖으로_나가는_cd_가_있으면_그_이유를_낸다(자리: dict[str, str]) -> None:
    """하위 폴더에 들렀다 밖으로 나가면 밖으로 나가는 이유를 낸다. 그 이유가 다른 체크아웃의 길을
    안내한다."""
    reason = _막는_이유(f"cd web && cd {자리['scratch']}", 자리["mine"], 자리)

    assert "체크아웃 밖" in reason
    assert "하위 폴더" not in reason


def test_이미_하위_폴더에_있는_셸은_cd_가_없으면_지나간다(자리: dict[str, str]) -> None:
    """못 보는 것: 앞 호출에서 이미 옮겨진 자리는 cd 가 없는 명령에서 막지 않는다."""
    assert deny_reason("ls", f"{자리['mine']}/web", 자리["scratch"]) is None


def test_이미_하위_폴더에_있는_셸이_다른_하위_폴더로_옮기면_막는다(자리: dict[str, str]) -> None:
    """이유가 지금 작업 폴더가 루트가 아니라는 것과 루트로 돌아오는 길을 적는다. 루트에서 옮긴다고
    적으면 모델이 안내대로 루트 기준 상대 경로를 줘, 그 경로가 하위 폴더에서 풀린다(셀프 리뷰 두
    축)."""
    mine = 자리["mine"]

    reason = _하위_폴더_이유("cd ../docs", f"{mine}/web", 자리)

    assert f"지금 작업 폴더 `{mine}/web`" in reason
    assert f"`cd {shlex.quote(mine)}`" in reason


def test_루트로_돌아오는_cd_는_셸이_읽는_꼴로_적는다(tmp_path: Path) -> None:
    """루트에 공백이 있으면 안내대로 친 `cd` 가 실패하지 않게 인용한다(PR 직전 버그 축)."""
    root = _저장소(tmp_path / "a b")
    scratch = tmp_path / "scratchpad"
    scratch.mkdir()

    reason = deny_reason("cd ../docs", f"{root.as_posix()}/web", scratch.as_posix())

    assert reason is not None
    assert f"`cd '{root.as_posix()}'`" in reason


def test_루트에서_옮기면_루트에서_옮긴다고_적는다(자리: dict[str, str]) -> None:
    reason = _하위_폴더_이유("cd web", 자리["mine"], 자리)

    assert f"체크아웃 루트({자리['mine']})에서" in reason
    assert "지금 작업 폴더" not in reason


def test_못_보는_것_서브에이전트의_하위_폴더_cd_도_막는다(자리: dict[str, str]) -> None:
    """거짓 양성이다. 서브에이전트의 Bash 는 호출마다 작업 폴더가 처음으로 돌아간다고 그 프롬프트가
    적는다(claude 실행 파일의 문장을 읽었다, 재지 않았다). 그래도 이 훅은 입력의 `agent_id` 로
    가르지 않고 같은 이유로 막는다."""
    _하위_폴더_이유("cd web && pnpm verify", 자리["mine"], 자리)


def test_풀_수_없는_하위_폴더_cd_는_지나간다(자리: dict[str, str]) -> None:
    """못 보는 것: 변수가 든 대상(`cd "$X"`)은 풀지 않는다."""
    assert deny_reason('cd "$X"', 자리["mine"], 자리["scratch"]) is None


def test_체크아웃_밖의_cwd_에서는_하위_폴더_cd_를_막지_않는다(자리: dict[str, str]) -> None:
    assert deny_reason("cd sub", 자리["scratch"], 자리["scratch"]) is None
