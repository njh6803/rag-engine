"""tools/hook_push_delete_open_pr.py 의 판정. git·gh 를 부르는 길은 임시 저장소로 실제로 돌린다.

막는 훅이 git 이 읽는 그대로 지우는 푸시를 읽는다고 주장하므로, git 이 입력을 다르게 읽는 길(옵션의
자리와 줄임, 짧은 옵션 묶음, 지우기 refspec 의 꼴, git 앞의 전역 옵션)과 지우기를 건너뛰는
길(`--dry-run`, 지울 ref 가 없는 것, 태그)을 하나씩 고정한다(`.claude/rules/tools.md`).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from tools.hook_push_delete_open_pr import (
    Deletion,
    deletions,
    gh_open_heads,
    github_repo,
    reason_for,
    refs_open_heads,
)
from tools.run_hooks import registered_matchers

IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@localhost")


@pytest.mark.parametrize(
    ("명령", "원격", "브랜치"),
    [
        pytest.param("git push origin --delete chore/x", "origin", ("chore/x",), id="사건의_꼴"),
        pytest.param("git push origin -d chore/x", "origin", ("chore/x",), id="짧은_옵션"),
        pytest.param("git push -d origin chore/x", "origin", ("chore/x",), id="원격_앞의_옵션"),
        pytest.param("git push origin chore/x --delete", "origin", ("chore/x",), id="뒤의_옵션"),
        pytest.param("git push origin --del chore/x", "origin", ("chore/x",), id="긴_옵션_줄임"),
        pytest.param("git push -fd origin chore/x", "origin", ("chore/x",), id="짧은_옵션_묶음"),
        pytest.param("git push --delete origin a b", "origin", ("a", "b"), id="브랜치_둘"),
        pytest.param("git push origin :chore/x", "origin", ("chore/x",), id="콜론_refspec"),
        pytest.param("git push origin +:chore/x", "origin", ("chore/x",), id="강제_콜론_refspec"),
        pytest.param(
            "git push origin :refs/heads/chore/x", "origin", ("chore/x",), id="온전한_ref_이름"
        ),
        pytest.param(
            "git push origin --delete refs/heads/chore/x", "origin", ("chore/x",), id="온전한_이름"
        ),
        pytest.param('git push origin --delete "chore/x"', "origin", ("chore/x",), id="인용"),
        pytest.param("git -C ../x push origin -d chore/x", "origin", ("chore/x",), id="git_-C"),
        pytest.param(
            "git -c core.x=1 --no-pager push origin -d chore/x",
            "origin",
            ("chore/x",),
            id="git_전역_옵션",
        ),
        pytest.param(
            "git push -o ci.skip origin -d chore/x", "origin", ("chore/x",), id="값을_먹는_옵션"
        ),
        pytest.param(
            "git push --push-option ci.skip origin -d chore/x",
            "origin",
            ("chore/x",),
            id="값을_먹는_긴_옵션",
        ),
        pytest.param(
            "git push --recurse-submodules check origin --delete chore/x",
            "origin",
            ("chore/x",),
            id="recurse_submodules_의_값",
        ),
        pytest.param(
            "git push --recurse check origin --delete chore/x",
            "origin",
            ("chore/x",),
            id="recurse_submodules_줄임의_값",
        ),
        pytest.param(
            "git push --recurse-submodules=check origin --delete chore/x",
            "origin",
            ("chore/x",),
            id="recurse_submodules_의_붙은_값",
        ),
        pytest.param(
            "git push --signed origin --delete chore/x",
            "origin",
            ("chore/x",),
            id="값을_붙여서만_받는_옵션",
        ),
        pytest.param(
            "git push https://github.com/o/r.git --delete chore/x",
            "https://github.com/o/r.git",
            ("chore/x",),
            id="원격_URL",
        ),
        pytest.param(
            "git push -oh origin --delete chore/x", "origin", ("chore/x",), id="묶음의_o_가_먹은_h"
        ),
        pytest.param(
            "git push -o -h origin --delete chore/x", "origin", ("chore/x",), id="o_의_값인_h"
        ),
    ],
)
def test_지우는_푸시를_git_처럼_읽는다(명령: str, 원격: str, 브랜치: tuple[str, ...]) -> None:
    assert deletions(명령) == [Deletion(원격, 브랜치)]


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param(
            "gh pr merge 251 --squash --match-head-commit abc && git push origin --delete chore/x",
            id="병합과_한_묶음",
        ),
        pytest.param("git push origin --delete chore/x; git fetch origin", id="세미콜론"),
        pytest.param("cd /c/x && GIT_TRACE=0 git push origin -d chore/x", id="환경_대입"),
        pytest.param("git status\ngit push origin -d chore/x", id="줄바꿈"),
        pytest.param("git push origin --delete chore/x > C:\\log.txt", id="출력_리다이렉션"),
        pytest.param("git push origin --delete chore/x 2>&1", id="서술자_리다이렉션"),
        pytest.param("git push origin --delete chore/x >log.txt", id="붙은_리다이렉션"),
        pytest.param(
            "git push --dry-run --no-dry-run origin --delete chore/x", id="dry_run_을_거둔다"
        ),
        pytest.param("# 정리\ngit push origin --delete chore/x", id="앞의_주석_줄"),
        pytest.param("git push origin --delete chore/x # 병합 뒤", id="꼬리_주석"),
        pytest.param("git push origin --delete chore/x # see: #252", id="콜론이_든_꼬리_주석"),
        pytest.param(
            'echo "a\\" # "; git push origin --delete chore/x', id="인용_안_이스케이프_뒤의_샵"
        ),
        pytest.param("echo ${#a}; git push origin --delete chore/x", id="낱말_안의_샵"),
        pytest.param("if true; then git push origin --delete chore/x; fi", id="then_뒤"),
        pytest.param("for b in x; do git push origin --delete chore/x; done", id="do_뒤"),
        pytest.param("{ git push origin --delete chore/x; }", id="중괄호_뒤"),
        pytest.param("! git push origin --delete chore/x", id="느낌표_뒤"),
    ],
)
def test_묶은_명령_속의_지우는_푸시도_읽는다(명령: str) -> None:
    """사건은 병합과 지우기를 한 번에 나란히 보낸 것이다(대기열 262, 일지 2026-10-15-01). 주석을
    빼지 않은 글도 함께 읽어, 꼬리 주석의 낱말이 지울 ref 로 든 지우기가 하나 더 나올 수 있다. 막는
    판정에는 해가 없다(그 낱말의 열린 PR 은 없다)."""
    assert Deletion("origin", ("chore/x",)) in deletions(명령)


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param("git push -u origin chore/x", id="올리는_푸시"),
        pytest.param("git push origin HEAD:main", id="콜론_앞에_글자"),
        pytest.param("git push origin :", id="맞는_것_모두_올리기"),
        pytest.param("git push origin --delete", id="지울_ref_가_없다"),
        pytest.param("git push --dry-run origin --delete chore/x", id="dry_run"),
        pytest.param("git push origin -nd chore/x", id="묶음의_n"),
        pytest.param("git push origin --dry --delete chore/x", id="dry_run_줄임"),
        pytest.param("git push origin --d chore/x", id="모호한_줄임은_git_이_거절한다"),
        pytest.param("git push origin --delete refs/tags/v1", id="태그"),
        pytest.param("echo 'git push origin --delete chore/x'", id="문자열_안"),
        pytest.param("git push-x origin --delete chore/x", id="다른_명령_이름"),
        pytest.param("cat <<'EOF'\ngit push origin --delete chore/x\nEOF", id="heredoc_본문"),
        pytest.param("git log -- push origin --delete chore/x", id="다른_하위_명령"),
        pytest.param("git push --delete --no-delete origin chore/x", id="delete_를_거둔다"),
        pytest.param("git push -h origin --delete chore/x", id="도움말"),
        pytest.param("git push origin --delete chore/x -h", id="뒤의_도움말"),
        pytest.param("git push -dh origin chore/x", id="묶음의_도움말"),
        pytest.param("git push --help origin --delete chore/x", id="긴_도움말"),
        pytest.param("git push origin --delete chore/x --help-all", id="help_all"),
        pytest.param("git push -o ci.skip -h origin -d chore/x", id="값을_먹은_옵션_뒤의_도움말"),
    ],
)
def test_지우지_않는_푸시와_푸시가_아닌_명령은_대상이_없다(명령: str) -> None:
    """git 이 지우지 않으므로 훅도 지나간다. `--d` 는 `--delete`·`--dry-run` 둘의 머리라 git 이
    모호하다며 거절한다."""
    assert deletions(명령) == []


@pytest.mark.parametrize(
    "명령",
    [
        pytest.param('bash -c "git push origin --delete chore/x"', id="셸_래퍼"),
        pytest.param("git push --prune origin 'refs/heads/*:refs/heads/*'", id="prune"),
        pytest.param("git push --mirror origin", id="mirror"),
        pytest.param("gh api -X DELETE repos/o/r/git/refs/heads/chore/x", id="REST_로_지우기"),
        pytest.param("env git push origin --delete chore/x", id="env_래퍼"),
        pytest.param("sudo git push origin --delete chore/x", id="sudo"),
        pytest.param("git p origin --delete chore/x", id="별칭"),
        pytest.param("git push origin `\n--delete chore/x", id="PowerShell_백틱_줄_이어_쓰기"),
        pytest.param("git push origin --delete chore/x <# -h #>", id="블록_주석_속의_도움말"),
        pytest.param("git push origin --delete chore/x `true -h`", id="백틱_치환_속의_도움말"),
        pytest.param(
            "X=\\' git push origin --delete chore/x # -h", id="이스케이프에_속은_꼬리_주석"
        ),
        pytest.param("git push origin --delete chore/x <# --x #>", id="블록_주석_속의_긴_옵션"),
    ],
)
def test_못_보는_것_래퍼와_prune_과_REST_는_지나간다(명령: str) -> None:
    """거짓 음성이다. 독스트링의 못 보는 것에 적은 길이다."""
    assert deletions(명령) == []


# `git push -h` 의 옵션 줄. 네 칸 들여쓴 `-` 로 시작하고 설명과는 두 칸 이상 띄운다.
_도움말_옵션_줄 = re.compile(r"^ {4}(-\S.*?)(?: {2,}|$)", re.MULTILINE)


def _도움말이_적는_옵션() -> list[tuple[str, bool]]:
    """이 기계의 `git push -h` 가 적는 옵션 낱말과, 그것이 다음 낱말을 값으로 먹는지. 값이 띄어
    쓴 `<…>`·`(…)` 이면 먹고, `[=…]` 이면 `=` 로만 받는다. `--[no-]` 꼴은 부정도 낸다(값을 먹지
    않는다)."""
    environment = {**os.environ, "LC_ALL": "C", "LANGUAGE": "C"}
    result = subprocess.run(
        ["git", "push", "-h"],
        capture_output=True,
        env=environment,
        timeout=30,
        check=False,
    )
    text = (result.stdout + result.stderr).decode("utf-8", "replace").replace("\r\n", "\n")
    found: list[tuple[str, bool]] = []
    for spec in _도움말_옵션_줄.findall(text):
        takes = " <" in spec or " (" in spec
        found += [(f"-{short}", takes) for short in re.findall(r"(?<![\w-])-(\w)\b", spec)]
        for negatable, name in re.findall(r"--(\[no-\])?([a-z0-9][a-z0-9-]*)", spec):
            found.append((f"--{name}", takes))
            if negatable:
                found.append((f"--no-{name}", False))
    return found


def test_git_push_도움말의_옵션이_먹는_낱말을_git_처럼_가른다() -> None:
    """대기열 296. 옵션 표는 git 의 옵션 목록을 손으로 옮긴 것이라, 값을 먹는 옵션을 먹지 않는다고
    적으면 그 값을 원격으로 읽어 지우는 푸시를 놓친다(`--recurse-submodules` 칸이 그랬다). 표에 없는
    옵션은 git 이 거절할 푸시로 보고 지나간다. 이 기계의 git 이 적는 옵션마다 값을 하나 끼운
    지우는 푸시에서 원격과 브랜치를 git 처럼 가르는지 본다. 다른 판의 git 이 더한 옵션은 그 git 에서
    이 시험이 빨개진다. 낱말을 가르는 것만 본다. `--all`·`--mirror`·`--tags` 는 git 이 `--delete` 와
    함께 거절하는데 이 훅은 지우는 푸시로 읽는다(아래 못 보는 것 시험)."""
    options = _도움말이_적는_옵션()
    words = {word for word, _ in options}
    assert {"--delete", "-d", "--recurse-submodules", "-o", "--force-with-lease"} <= words

    wrong: list[str] = []
    for word, takes in options:
        command = f"git push {word}{' v' if takes else ''} origin --delete chore/x"
        expected = [] if word in ("-n", "--dry-run") else [Deletion("origin", ("chore/x",))]
        if deletions(command) != expected:
            wrong.append(f"{word}(값을 먹는다: {takes})")
    assert wrong == []


def test_못_보는_것_표에_없는_긴_옵션은_지나간다() -> None:
    """거짓 음성이다. git 이 옵션을 더해 표가 낡으면 그 옵션이 든 지우는 푸시를 git 이 거절할 푸시로
    본다. 위의 도움말 시험은 그 옵션을 아는 git 에서만 빨개진다."""
    assert deletions("git push --some-future-option origin --delete chore/x") == []


def test_못_보는_것_값을_먹는_새_짧은_옵션의_값은_원격으로_읽는다() -> None:
    """거짓 음성이다. 짧은 옵션은 표 없이 `-o` 하나만 값을 먹는다고 본다. git 이 값을 먹는 짧은
    옵션을 더하면 그 값이 원격이 되고, 그 원격 이름을 풀지 못해 묻지 않고 지나간다."""
    assert deletions("git push -X v origin --delete chore/x") == [
        Deletion("v", ("origin", "chore/x"))
    ]


@pytest.mark.parametrize("옵션", ["--all", "--mirror", "--tags"])
def test_못_보는_것_git_이_거절하는_조합도_지우는_푸시로_읽는다(옵션: str) -> None:
    """거짓 양성이다. git 은 `--delete` 와 이 옵션을 함께 쓴 푸시를 거절한다(git 2.32 의 임시
    저장소에서 손으로 봤다). 이 훅은 그 조합을 보지 않아, 열린 PR 의 머리면 막는다."""
    assert deletions(f"git push {옵션} origin --delete chore/x") == [
        Deletion("origin", ("chore/x",))
    ]


def test_github_원격만_owner_와_repo_를_낸다() -> None:
    assert github_repo("https://github.com/njh4803/agent-os.git") == ("njh4803", "agent-os")
    assert github_repo("git@github.com:njh4803/agent-os.git") == ("njh4803", "agent-os")
    assert github_repo("C:/tmp/origin.git") is None


def test_gh_목록에서_이_저장소의_머리만_고른다() -> None:
    """포크의 같은 이름 브랜치는 이 원격의 브랜치를 지워도 닫히지 않는다."""
    listing = "251\tnjh4803/agent-os\tchore/x\n9\tfork/agent-os\tchore/y\n12\t\tchore/z\n"

    found = gh_open_heads(listing, "njh4803/agent-os", ("chore/x", "chore/y", "chore/z"))

    assert found == {"chore/x": [251]}


def test_ls_remote_에서_merge_ref_가_있는_PR_의_머리를_고른다() -> None:
    """merge ref 는 열린 PR 에만 있었다(`tools/sibling_overlap.py` 독스트링, 2026-10-07 클라우드
    컨테이너에서 손으로 봤다)."""
    listing = (
        "aaa\trefs/heads/chore/x\nbbb\trefs/heads/chore/y\n"
        "aaa\trefs/pull/7/head\nccc\trefs/pull/7/merge\n"
        "bbb\trefs/pull/3/head\n"
    )

    assert refs_open_heads(listing, ("chore/x", "chore/y", "chore/z")) == {"chore/x": [7]}


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def _repository(tmp_path: Path, *, merge_ref: bool) -> Path:
    """origin(bare)에 `chore/x` 와 그 끝을 머리로 둔 PR 7 의 ref 가 있는 저장소. `chore/same` 은
    같은 커밋을, `chore/other` 는 그 위의 다른 커밋을 끝으로 둔다."""
    origin, repo = tmp_path / "origin.git", tmp_path / "repo"
    _git("init", "-q", "--bare", "-b", "main", str(origin))
    _git("init", "-q", "-b", "chore/x", str(repo))
    _git("-C", str(repo), *IDENTITY, "commit", "-q", "--allow-empty", "-m", "x")
    _git("-C", str(repo), "remote", "add", "origin", str(origin))
    _git("-C", str(repo), "push", "-q", "origin", "chore/x", "chore/x:chore/same")
    tip = _git("-C", str(repo), "rev-parse", "HEAD")
    _git("-C", str(repo), *IDENTITY, "commit", "-q", "--allow-empty", "-m", "other")
    _git("-C", str(repo), "push", "-q", "origin", "HEAD:chore/other")
    _git("-C", str(origin), "update-ref", "refs/pull/7/head", tip)
    if merge_ref:
        _git("-C", str(origin), "update-ref", "refs/pull/7/merge", tip)
    return repo


@pytest.mark.parametrize(
    ("args", "outcome"),
    [
        pytest.param(["-h", "origin", "--delete", "chore/x"], "usage", id="도움말"),
        pytest.param(["origin", "--delete", "chore/x", "-h"], "usage", id="뒤의_도움말"),
        pytest.param(["-dh", "origin", "chore/x"], "usage", id="묶음의_도움말"),
        pytest.param(["origin", "--delete", "chore/x", "--help-all"], "usage", id="help_all"),
        pytest.param(["--help", "origin", "--delete", "chore/x"], "git help", id="긴_도움말"),
        pytest.param(["-oh", "origin", "--delete", "chore/x"], "delete", id="묶음의_o_가_먹은_h"),
        pytest.param(["-o", "-h", "origin", "--delete", "chore/x"], "delete", id="o_의_값인_h"),
    ],
)
def test_도움말_판정이_실제_git_과_같다(tmp_path: Path, args: list[str], outcome: str) -> None:
    """대기열 300. `-h` 를 값 없는 옵션으로 넘기던 판은 도움말을 지우는 푸시로 읽었다. 꼴마다 git 을
    실제로 쳐 origin 의 `chore/x` 가 지워졌는지, 도움말의 표지와 훅의 판정을 함께 본다. 사용법의
    종료 코드는 git 판마다 달라 보지 않는다(harness 티켓 018). 하위 명령 바로 뒤의 `--help` 는
    `git help` 로 바뀐다. 도움말 페이지를 띄우지 않게 `help.format` 을 man 으로, 뷰어를 없는
    이름으로 둔다(윈도 git 의 기본 html 은 브라우저를 연다)."""
    repo = _repository(tmp_path, merge_ref=True)
    origin = tmp_path / "origin.git"
    _git("-C", str(origin), "config", "receive.advertisePushOptions", "true")
    environment = {**os.environ, "GIT_TRACE": "1", "LC_ALL": "C", "LANGUAGE": "C"}
    result = subprocess.run(
        ["git", "-c", "help.format=man", "-c", "man.viewer=absent-viewer", "push", *args],
        cwd=repo,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    output = result.stdout + result.stderr
    probe = ["git", "-C", str(origin), "rev-parse", "-q", "--verify", "refs/heads/chore/x"]
    remains = subprocess.run(probe, capture_output=True, timeout=30, check=False).returncode == 0

    context = f"{result.returncode} {output[-500:]}"
    if outcome == "usage":
        assert remains, context
        assert "usage: git push" in output, context
    elif outcome == "git help":
        assert remains, context
        assert "built-in: git help" in output, context
    else:
        assert not remains, context
    assert (deletions("git push " + " ".join(args)) == []) is (outcome != "delete")


def test_열린_PR_의_머리를_지우는_푸시를_막는다(tmp_path: Path) -> None:
    repo = _repository(tmp_path, merge_ref=True)

    reason = reason_for("git push origin --delete chore/x && git fetch origin", str(repo))

    assert reason is not None
    assert "#7" in reason
    assert "chore/x" in reason
    assert "gh api repos/<owner>/<repo>/pulls/7" in reason


def test_못_보는_것_URL_이나_경로로_적은_원격은_묻지_않고_지나간다(tmp_path: Path) -> None:
    """거짓 음성이다. 명령 글의 주소로 훅이 권한 판정 전에 접속하면, 사용자가 그 호출을 거부해도
    요청이 이미 나간다(PR 직전 보안 리뷰가 로컬 HTTP 서버로 재현했다). 그래서 이름으로 준 원격만
    `git remote get-url` 로 풀어 묻는다. 여기서는 열린 PR 이 있는 원격을 경로로 적어도 지나간다."""
    repo = _repository(tmp_path, merge_ref=True)
    origin = (tmp_path / "origin.git").as_posix()

    assert deletions(f"git push {origin} --delete chore/x") == [Deletion(origin, ("chore/x",))]
    assert reason_for(f"git push {origin} --delete chore/x", str(repo)) is None
    assert reason_for("git push origin --delete chore/x", str(repo)) is not None


def test_시간_예산을_다_쓰면_묻지_않고_지나간다(tmp_path: Path) -> None:
    """지우는 푸시가 여럿이어도 한 명령의 합이 등록의 시간 제한을 넘지 않게 한다(fail-open)."""
    repo = _repository(tmp_path, merge_ref=True)

    assert reason_for("git push origin --delete chore/x", str(repo), budget=0) is None
    assert reason_for("git push origin --delete chore/x", str(repo)) is not None


def test_못_보는_것_다른_저장소의_원격_이름은_cwd_에서_푼다(tmp_path: Path) -> None:
    """거짓 음성이다. `git -C <열린 PR 이 있는 저장소> push origin …` 도 원격 이름은 cwd 에서
    푼다."""
    repo = _repository(tmp_path, merge_ref=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    command = f"git -C {repo.as_posix()} push origin --delete chore/x"

    assert deletions(command) == [Deletion("origin", ("chore/x",))]
    assert reason_for(command, str(elsewhere)) is None


def test_대시로_시작하는_브랜치의_열린_PR_도_막는다(tmp_path: Path) -> None:
    """git 은 `refs/heads/-x` 를 받는다(셀프 리뷰 표준 축이 `git check-ref-format` 으로 손으로
    봤다). 브랜치는 `refs/heads/<브랜치>` 꼴로만 git 에 넘겨 옵션이 되지 않으니 가드는 원격에만
    건다."""
    repo = _repository(tmp_path, merge_ref=True)
    origin = tmp_path / "origin.git"
    _git("-C", str(repo), "push", "-q", "origin", "HEAD:refs/heads/-x")
    tip = _git("-C", str(origin), "rev-parse", "refs/heads/-x")
    _git("-C", str(origin), "update-ref", "refs/pull/8/head", tip)
    _git("-C", str(origin), "update-ref", "refs/pull/8/merge", tip)

    reason = reason_for("git push origin :-x", str(repo))

    assert reason is not None
    assert "#8" in reason


@pytest.mark.parametrize(
    ("merge_ref", "명령"),
    [
        pytest.param(False, "git push origin --delete chore/x", id="병합_뒤_merge_ref_없음"),
        pytest.param(True, "git push origin --delete chore/other", id="PR_없는_브랜치"),
        pytest.param(True, "git push nowhere --delete chore/x", id="없는_원격"),
    ],
)
def test_열린_PR_이_없거나_원격을_읽지_못하면_지나간다(
    tmp_path: Path, *, merge_ref: bool, 명령: str
) -> None:
    """없는 원격은 푸시 자신도 실패하므로 막지 않는다(fail-open)."""
    repo = _repository(tmp_path, merge_ref=merge_ref)

    assert reason_for(명령, str(repo)) is None


def test_옵션처럼_보이는_원격은_git_에_넘기지_않는다(tmp_path: Path) -> None:
    """`--` 뒤의 `--upload-pack=<명령>` 은 git push 에는 원격 이름이지만 `ls-remote` 에는 옵션이다.
    넘기면 훅이 그 명령을 띄운다(PR 직전 보안 리뷰). 띄웠으면 표지 파일이 생긴다."""
    repo = _repository(tmp_path, merge_ref=True)
    marker = tmp_path / "pwned"
    command = f"git push --delete -- --upload-pack='touch {marker.as_posix()}' chore/x"

    assert deletions(command) == [
        Deletion(f"--upload-pack=touch {marker.as_posix()}", ("chore/x",))
    ]
    assert reason_for(command, str(repo)) is None
    assert not marker.exists()


def test_못_보는_것_merge_ref_길은_같은_커밋의_다른_브랜치도_막는다(tmp_path: Path) -> None:
    """거짓 양성이다. gh 를 쓰지 못하는 길은 PR 의 머리를 브랜치 이름이 아니라 커밋으로 대 본다."""
    repo = _repository(tmp_path, merge_ref=True)

    reason = reason_for("git push origin --delete chore/same", str(repo))

    assert reason is not None
    assert "#7" in reason


def test_settings의_매처는_셸_도구_둘이다() -> None:
    """매처를 넓히면 훅이 명령이 없는 입력에서 조용히 지나가고, 좁히면 그 도구의 지우기를 놓친다."""
    matchers = registered_matchers("hook_push_delete_open_pr.py", "PreToolUse")

    assert len(matchers) == 1
    assert set(matchers[0].split("|")) == {"Bash", "PowerShell"}
