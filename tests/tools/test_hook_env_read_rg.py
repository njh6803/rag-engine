"""tools/hook_env_read.py 의 glob 판정을 실제 rg 와 맞댄다(대기열 422, harness 티켓 007).

훅은 하류(Grep 도구가 띄우는 rg, Bash 의 rg)가 읽는 `.env` 를 막는다고 주장하므로, 그 하류를 실제로
띄워 판정과 견준다(`.claude/rules/tools.md` 의 하류 판정 항목). glob 의 중괄호를 bash 처럼 읽은 판이
rg 의 `{.env}` 를 지나보냈고(대기열 422), 손으로 본 꼴만 시험한 판이 그것을 놓쳤다.

전제 셋. 무엇으로 알았는지를 함께 적는다.
- Grep 도구는 rg 를 띄우고, 숨김 파일은 읽고 gitignore 는 따른다. glob 은 공백으로 나누고, 중괄호가
  없는 조각은 쉼표로도 나눠 조각마다 `--glob` 하나로 넘긴다. 2026-10-23 claude 2.1.302 의 Grep
  도구로 손으로 봤다(일지 2026-10-23-33). 그래서 여기서는 rg 에 `--hidden` 과 훅의 `grep_tool_globs`
  가 낸 조각을 넘기고, 나누는 규칙 자체는 손으로 본 표(`test_Grep_도구의_glob_을_도구처럼_나눈다`)로
  고정한다.
- rg 는 PATH 의 `rg`, 없으면 Claude Code 실행 파일을 실행 이름 `rg` 로 띄운 것이다. 그 실행 파일은
  ripgrep 14.1.1 로 답했다(이 PC, 손으로 봤다). CI 는 `ci.yml` 이 apt 로 ripgrep 을 깐다.
  어느 것도 없으면 건너뛰지 않고 실패한다(`.claude/rules/tests.md`).
- 가짜 `.env` 는 `git init` 한 임시 폴더의 `.gitignore` 로 무시한다. 이 저장소와 같은 모양이다.
"""

from __future__ import annotations

import posixpath
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
from tools.hook_env_read import deny_reason_for_command, deny_reason_for_grep_tool, grep_tool_globs

_MARKER = "MARKER_422"
_FILES = (".env", ".env.local", ".env.example", "a.md", "b.py", "sub/.env", "sub/c.py")
# rg 가 낸 경로 가운데 이것이면 `.env` 에 닿은 것이다. `.env.example` 은 읽어도 된다.
_SECRETS = frozenset({".env", ".env.local", "sub/.env"})


def _rg_command() -> tuple[list[str], str | None]:
    """rg 를 띄울 인자 머리와 실행 파일. PATH 의 rg 가 먼저다."""
    found = shutil.which("rg")
    if found is not None:
        return [found], None
    claude = shutil.which("claude")
    if claude is not None:
        return ["rg"], claude
    pytest.fail(
        "rg 를 찾지 못했다. PATH 에 rg 를 두거나 Claude Code(`claude`)를 깐다. 건너뛰지 않는다."
    )


@pytest.fixture(scope="module")
def rg() -> tuple[list[str], str | None]:
    head, executable = _rg_command()
    version = subprocess.run(
        [*head, "--version"], executable=executable, capture_output=True, text=True, timeout=30
    )
    assert version.stdout.startswith("ripgrep"), (version.stdout, version.stderr)
    return head, executable


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("env_rg")
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=30)
    (root / ".gitignore").write_text(".env*\n!.env.example\n", encoding="utf-8")
    for name in _FILES:
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"{_MARKER}\n", encoding="utf-8")
    return root


def _rg_reads_secret(
    rg: tuple[list[str], str | None], repo: Path, args: list[str], paths: tuple[str, ...] = ()
) -> bool:
    head, executable = rg
    result = subprocess.run(
        # `--no-config`: 사용자의 `RIPGREP_CONFIG_PATH` 가 `--hidden` 같은 기본값을 바꾸지 않게
        # 한다.
        [*head, "--no-config", "-l", *args, _MARKER, *paths],
        executable=executable,
        cwd=repo,
        # 경로를 주지 않은 rg 는 stdin 이 파이프면 stdin 을 찾는다. pytest 의 캡처에 기대지 않는다.
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # 2 는 고른 파일이 없거나(`No files were searched`) glob 을 풀지 못한 것(`{.env`, 겹친
    # 묶음)이다. 둘 다 아무것도 읽지 않았다.
    assert result.returncode in {0, 1} or (
        result.returncode == 2
        and not result.stdout
        and ("No files were searched" in result.stderr or "error parsing glob" in result.stderr)
    ), result.stderr
    # 경로를 준 rg 는 그 경로를 머리에 붙여 낸다(`./.\.env`, `sub/../.env`).
    hits = {posixpath.normpath(line.strip().replace("\\", "/")) for line in result.stdout.split()}
    return bool(hits & _SECRETS)


def test_가짜_env_는_glob_없이는_rg_가_읽지_않는다(
    rg: tuple[list[str], str | None], repo: Path
) -> None:
    """맞대기의 바탕이다. 이것이 깨지면(gitignore 를 안 따르면) 아래 사례가 모두 뜻을 잃는다."""
    assert not _rg_reads_secret(rg, repo, ["--hidden"])
    assert _rg_reads_secret(rg, repo, ["--hidden", "--no-ignore"])


# Grep 도구의 glob 칸. 훅이 막는지와 실제 rg 가 `.env` 를 읽는지가 같아야 한다.
_GREP_TOOL_SAME = [
    ".env", "{.env}", ".{env}", ".e{n}v", "{.env,}", "{,.env}", "{a,.env}", "*", ".*", "**",
    "**/.env", "sub/*", ".en[!x]", ".en[^x]", "{*.md,**}", "*.{md,env}", ".en[!{}]",
    "*.md,.env", "*.md .env", "*.py\t.env", ".env,", "{a,b}.md .env", "!*.md,.env",
    "*.md", "*.py", ".env.example", "{.env.example,*.md}", "!*.md", "{.env", "{*.md},.env",
    "*.md,*.py", "{.env, x}",
]  # fmt: skip
# 훅이 막는데 rg 는 읽지 않는 것(거짓 양성). 훅이 보수적으로 고른 자리라 막는 쪽을 단언한다.
# `.ENV`: rg 의 glob 은 대소문자를 가리고 훅은 가리지 않는다(Windows 는 같은 파일이다).
# `{{.env}}`: rg 14.1.1 은 겹친 묶음을 풀지 못해 오류로 끝나고 훅은 둘 다 푼다.
# `.env !.env`: 뒤의 빼기가 이기지만 Grep 도구의 glob 에서 순서는 보지 않는다.
# `src/** tests/**`: 훅은 마지막 `/` 앞의 디렉터리 조각을 떼고 보아 `**` 로 읽는다.
# `./.env`: rg 는 앞의 `./` 를 맞추지 않고 훅은 마지막 `/` 앞을 뗀다.
_GREP_TOOL_STRICTER = [".ENV", "{{.env}}", ".env !.env", "src/** tests/**", "./.env"]


def _grep_tool_args(glob: str) -> list[str]:
    """Grep 도구가 rg 에 넘기는 인자. 숨김 파일을 읽고, glob 칸은 나눈 조각마다 `--glob` 이다."""
    return ["--hidden"] + [arg for piece in grep_tool_globs(glob) for arg in ("--glob", piece)]


@pytest.mark.parametrize("glob", _GREP_TOOL_SAME)
def test_Grep_도구의_glob_판정이_실제_rg_와_같다(
    rg: tuple[list[str], str | None], repo: Path, glob: str
) -> None:
    args = _grep_tool_args(glob)
    reads = _rg_reads_secret(rg, repo, args)
    blocks = deny_reason_for_grep_tool(str(repo), glob) is not None
    assert blocks == reads, f"rg 가 읽는가 {reads}, 훅이 막는가 {blocks}, rg 인자 {args}"


@pytest.mark.parametrize("glob", _GREP_TOOL_STRICTER)
def test_Grep_도구의_glob_에서_훅이_rg_보다_넓게_막는_자리(
    rg: tuple[list[str], str | None], repo: Path, glob: str
) -> None:
    args = _grep_tool_args(glob)
    assert not _rg_reads_secret(rg, repo, args)
    assert deny_reason_for_grep_tool(str(repo), glob) is not None


@pytest.mark.parametrize(
    ("glob", "조각"),
    [
        ("*.md,secret.txt", ["*.md", "secret.txt"]),
        ("*.md .hid", ["*.md", ".hid"]),
        ("{secret.txt}", ["{secret.txt}"]),
        ("{*.md},secret.txt", ["{*.md},secret.txt"]),
        ("{a,b}.md .env", ["{a,b}.md", ".env"]),
        (" *.py ,, .env ", ["*.py", ".env"]),
    ],
)
def test_Grep_도구의_glob_을_도구처럼_나눈다(glob: str, 조각: list[str]) -> None:
    """앞의 넷은 2026-10-23 claude 2.1.302 의 Grep 도구로 손으로 봤다(모듈 독스트링). 무시된
    `secret.txt`·`.hid` 를 첫째·둘째는 읽었고, 셋째는 그 파일을, 넷째는 아무것도 내지 않았다."""
    assert grep_tool_globs(glob) == 조각


# Bash 의 rg. rg 의 `-g` 는 무시 규칙과 숨김 규칙을 이기고, 뒤에 온 glob 이 이긴다
# (2026-10-23 rg 14.1.1 로 손으로 봤다, 일지 2026-10-23-33).
_BASH_RG_SAME = [
    "rg -g .env {m} .", "rg -g '{{.env}}' {m} .", "rg --glob=.env {m} .", "rg -g.env {m} .",
    "rg -g '*' {m} .", "rg -g '**/.env' {m}", "rg --iglob .env {m} .", "rg -t py -g .env {m} .",
    "rg -g '!.env*' -g .env {m} .", "rg -g '*.md' -g .env {m} .", "rg -g '!*.md' -uu {m} .",
    "rg -uu {m} .", "rg --hidden --no-ignore {m}",
    "rg -g .env -g '!.env*' {m} .", "rg -g '*.md' {m} .", "rg -uu -g '!.env*' {m} .",
    "rg -uu -t py {m} .", "rg -g '!*.md' {m} .", "rg {m} .", "rg --hidden {m} .",
    "rg -g .env.example {m} .", "rg -g '*.md,.env' {m} .",
    # 묶은 짧은 옵션 속의 `g` 와 대소문자를 가리는 빼기(셀프 리뷰 두 축이 찾았다).
    "rg -ig.env {m} .", "rg -ug .env {m} .", "rg -sg .env {m} .", "rg -Ig .env {m} .",
    "rg -tpy -g .env {m} .", "rg -g .env -g '!.ENV' {m} .", "rg --glob=.env --glob='!.ENV' {m} .",
    "rg -uu -g '!.ENV' {m} .", "rg -g .env -- {m} .",
    # 표에 없던 값 옵션과 디렉터리가 붙은 빼기(PR 직전 보안 리뷰와 bug-perf-review 가 찾았다).
    # `-rg` 는 `-r g` 다. 그 `g` 를 `-g` 로 읽은 판이 `-uu -rg ^` 를 지나보냈다.
    "rg -uu -rg {m} .", "rg -r X -g .env {m}", "rg -d 3 -g .env {m}",
    "rg --replace X -g .env {m}", "rg --max-filesize 1M -g .env {m}",
    "rg -g .env -g '!sub/.env' {m} .", "rg -uu -g '!/.env' {m} .", "rg -uu -g '!**/.env*' {m} .",
    # 경로 없는 묶은 짧은 옵션과 `.env` 하나만 빼는 빼기(푸시 뒤 자동 보안 리뷰가 찾았다).
    # `-ig .env {m}` 의 `.env` 는 `-g` 의 값이라 `{m}` 이 패턴이고 경로가 없다. `!.env` 는
    # `.env.local` 을 빼지 않는다.
    "rg -ig .env {m}", "rg -ug .env {m}", "rg -ig.env {m}",
    "rg -g '.env*' -g '!.env' {m} .", "rg -uu -g '!.env' {m} .", "rg -uu -g '!.env.local' {m} .",
    # 빼기 여럿이 합쳐 `.env` 꼴을 모두 뺀다(grep 의 같은 꼴, 셀프 리뷰 두 축).
    "rg -uu -g '!.env' -g '!.env.*' {m} .",
    # 역슬래시는 rg 가 이스케이프로 읽어 `\.env` 가 `.env` 다(푸시 뒤 자동 보안 리뷰. 2026-10-23
    # Windows 의 rg 14.1.1 도 그렇게 읽었다).
    "rg -g '\\.env' {m} .", "rg -g '\\.e\\nv' {m} .",
]  # fmt: skip
# 훅이 막는데 rg 는 읽지 않는 것(거짓 양성). 고르는 쪽의 대소문자, 앞의 `./`, 빼는 쪽의 중괄호,
# `--iglob` 의 빼기 대소문자, 디렉터리가 붙은 빼기다(모듈 독스트링의 못 보는 것).
_BASH_RG_STRICTER = [
    "rg -g .ENV {m} .", "rg -g ./.env {m} .", "rg -g .env -g '!{{.env}}' {m} .",
    "rg -g .env --iglob '!.ENV' {m} .", "rg -g '.env*' -g '!/.env*' -g '!sub/.env*' {m} .",
    "rg -uu -g '!\\.env*' {m} .",
]  # fmt: skip


def test_못_보는_것_하위_폴더를_준_rg_glob_은_그_아래_env_를_읽어도_지나간다(
    rg: tuple[list[str], str | None], repo: Path
) -> None:
    """거짓 음성이다. 루트인지는 경로로만 가르고(`_is_root`), `sub` 는 루트가 아니다."""
    assert _rg_reads_secret(rg, repo, ["-g", ".env"], ("sub",))
    assert deny_reason_for_command(f"rg -g .env {_MARKER} sub", str(repo)) is None


@pytest.mark.parametrize("명령", _BASH_RG_SAME)
def test_Bash_의_rg_판정이_실제_rg_와_같다(
    rg: tuple[list[str], str | None], repo: Path, 명령: str
) -> None:
    command = 명령.format(m=_MARKER)
    args = [arg for arg in shlex.split(command)[1:] if arg not in {_MARKER, "."}]
    reads = _rg_reads_secret(rg, repo, args)
    blocks = deny_reason_for_command(command, str(repo)) is not None
    assert blocks == reads, f"rg 가 읽는가 {reads}, 훅이 막는가 {blocks}, 명령 {command}"


@pytest.mark.parametrize("경로", ["./.", ".//", "././", "sub/.."])
def test_점을_다르게_쓴_경로를_루트로_본다(
    rg: tuple[list[str], str | None], repo: Path, 경로: str
) -> None:
    """`_is_root` 가 `_ROOTISH` 에 없는 꼴을 루트가 아니라고 읽어 지나보낸 판이 있었다(PR 직전
    bug-perf-review). 경로는 패턴 뒤에 와야 해 표(`_BASH_RG_SAME`)의 꼴로 띄우지 않는다."""
    assert _rg_reads_secret(rg, repo, ["-g", ".env"], (경로,))
    assert deny_reason_for_command(f"rg -g .env {_MARKER} {경로}", str(repo)) is not None


@pytest.mark.parametrize("명령", _BASH_RG_STRICTER)
def test_Bash_의_rg_에서_훅이_rg_보다_넓게_막는_자리(
    rg: tuple[list[str], str | None], repo: Path, 명령: str
) -> None:
    command = 명령.format(m=_MARKER)
    args = [arg for arg in shlex.split(command)[1:] if arg not in {_MARKER, "."}]
    assert not _rg_reads_secret(rg, repo, args)
    assert deny_reason_for_command(command, str(repo)) is not None
