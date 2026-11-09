"""tools/hook_env_read.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

대기열 43 — 감사 중 grep 한 번에 `.env` 의 키가 도구 출력에 실렸다. 발동해야 할 것과 발동하지
말아야 할 것을 반씩 둔다. 뒤의 것이 거짓 양성의 경계다. 첫 구현의 구멍 열둘과 오탐 아홉은
2026-09-28 적대 검증 워크플로가 찾았고 그 입력들이 여기 있다.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from tools.hook_env_read import (
    OPTION_SPECS,
    WRAPPERS,
    deny_reason_for_command,
    deny_reason_for_grep_tool,
    env_file_name,
    reason_for,
)


@pytest.mark.parametrize(
    "명령",
    [
        # 대기열 448 에 남았던 사례. 옵션 읽기를 명령마다의 레코드와 getopt 읽기 함수 하나로 합쳐
        # 닫았다(harness 티켓 012). 파일 옵션(diff·sort·gawk), `--` 뒤의 위치 인자, 긴 값 옵션의
        # 줄임이다.
        "diff --from-file=.env x.txt",
        "diff --to-file .env x.txt",
        "sort --files0-from=.env",
        "gawk -i .env '{print}' x.txt",
        "gawk -E .env x.txt",
        "gawk --exec=.env x.txt",
        "grep -- --file .env",
        # `--` 를 모르면 `-e` 가 `.env` 를 패턴으로 먹는다. 앞의 것은 `--file` 이 파일 옵션이라
        # `--` 를 몰라도 막혀 `--` 처리를 재지 못했다(변이 표 `env_read_wrappers_mutations.toml`).
        "grep -- -e .env",
        "sudo --us root cat .env",
        # 표에 없는 플래그(ack·ag 의 `--color`, ag 의 `--ackmate`)가 값 옵션 이름의 머리이고 같은
        # 명령에 진짜 줄임이 함께 있다. 모든 옵션을 플래그로 읽은 글과 모두 줄임으로 읽은 글 둘만 본
        # 판이 지나보냈다(셀프 리뷰 명세 축). 옵션마다의 조합을 모두 본다.
        "ack .env --color --mat X",
        "ack --color --files-f .env KEY",
        "ag --color --path .env KEY",
        "ag --ackmate --path .env KEY",
        # 셸·git 의 옵션도 레코드로 읽는다. `--norc` 의 `c` 를 `-c` 로 세거나 하위 명령을 첫
        # 인자로만 본 판이 지나보냈다(셀프 리뷰 표준 축). `+o` 는 옛 읽기가 맡는다.
        "bash --norc -c 'cat .env'",
        "bash --rcfile x -c 'cat .env'",
        "bash -x -c 'cat .env'",
        # `-c` 뒤의 옵션. bash 는 `-e` 를 옵션으로 읽고 첫 위치 인자를 돌린다. `-c` 다음 낱말만 보는
        # 옛 읽기는 `-e` 를 명령 글로 집는다.
        "bash -c -e 'cat .env'",
        "bash +o posix -c 'cat .env'",
        "git -C . diff --no-index .env x",
        "git -c core.pager=cat show HEAD:.env",
        "cat .env",
        "cat '.env'",
        'head -n 1 "C:/project/agent/.env"',
        "grep ANTHROPIC .env",
        "grep -e ANTHROPIC .env",
        "grep -ie ANTHROPIC .env",
        "rg -ie ANTHROPIC .env",
        "sed -ne 1p .env",
        "rg -ig '*' ANTHROPIC .env",
        # ag 의 `-t`(--all-text)·`-f`(--follow)는 값을 먹지 않는다. rg 의 표를 쓴 판이 `KEY` 를
        # 값으로 먹어 `.env` 를 패턴으로 버렸다(푸시 뒤 자동 보안 리뷰, 대기열 422).
        "ag -it ANTHROPIC .env",
        "ag -t ANTHROPIC .env",
        "ag -ft ANTHROPIC .env",
        # ack 3 의 `-A`·`-B` 는 값이 선택인 숫자라 숫자가 아닌 `KEY` 를 먹지 않는다(ConfigLoader.pm
        # 의 `A|after-context:-1`). man 페이지의 `-A NUM` 을 따른 판이 지나보냈다(셀프 리뷰).
        "ack -A ANTHROPIC .env",
        "ack -B ANTHROPIC .env",
        "ack --after-context ANTHROPIC .env",
        # ack 의 `--match` 는 패턴을 따로 줘 남은 위치 인자가 모두 파일이다(셀프 리뷰 명세 축).
        "ack --match ANTHROPIC .env",
        "ack --match=ANTHROPIC .env",
        "ack .env --match ANTHROPIC",
        # 표의 값 옵션은 값만 먹는다(ag `src/options.c`, ack `ConfigLoader.pm`).
        "ag -G py ANTHROPIC .env",
        "ag --workers 2 ANTHROPIC .env",
        "ack --type python ANTHROPIC .env",
        "ack --pager less ANTHROPIC .env",
        # 파일을 값으로 받아 읽는 옵션의 값. `--files-from` 을 값 옵션 표에 넣은 판이 뒤의 `.env` 를
        # 값으로 먹어 `ack KEY --files-from .env` 를 지나보냈다(셋째 푸시 뒤 자동 보안 리뷰).
        "ack ANTHROPIC --files-from .env",
        "ack --files-from=.env ANTHROPIC",
        "ack --ackrc .env ANTHROPIC src/",
        "grep -f .env x.txt",
        "grep --file=.env x.txt",
        "grep -if.env x.txt",
        "grep -rn --exclude-from .env KEY src/",
        "rg -f .env src/",
        "rg --ignore-file .env KEY src/",
        "ag -p .env KEY src/",
        "ag --path-to-ignore=.env KEY src/",
        "sed -f .env x.txt",
        "awk -f .env x.txt",
        # getopt_long 은 파일 옵션의 줄임도 받는다. sed 4.8 이 `--fi=` 를 `--file=` 로 읽었다(셀프
        # 리뷰 명세 축이 손으로 봤다).
        "sed --fi=.env x.txt",
        "grep --exclude-fr .env KEY src/",
        # sed 의 긴 꼴, gawk 의 `--source`, getopt_long 의 긴 옵션 줄임도 패턴을 옵션으로 준다(같은
        # 리뷰). 줄임의 최소 길이는 명령마다 달라 sed 는 `--e` 로 `--expression` 을 읽는다(sed 4.8,
        # 셀프 리뷰 두 축이 손으로 봤다).
        "sed --expression 1p .env",
        "sed --expression=1p .env",
        "sed --exp=1p .env",
        "sed --e=1p .env",
        "sed --fil=script.sed .env",
        "gawk --source='{print}' .env",
        "gawk --so='{print}' .env",
        "awk --source '{print}' .env",
        "grep --reg=ANTHROPIC .env",
        "sed -n 1p ../.env",
        "awk '{print $1}' .env",
        "less .env.local",
        "source .env",
        ". .env",
        "sudo cat .env",
        "\\cat .env",
        "/usr/bin/cat .env",
        "timeout 5 cat .env",
        "timeout -k 3 5 cat .env",
        "cat .ENV",
        "cat .e*",
        "head -n 1 .env*",
        "sed -n 1p '.e?v'",
        "nice -n 10 cat .env",
        "env cat .env",
        "PYTHONUTF8=1 cat .env | head -n 1",
        "ls && (cat .env)",
        "echo start; tail -n 2 .env",
        "if [ -f .env ]; then cat .env; fi",
        "while true; do head -n 1 .env; done",
        "cat \\\n  .env",
        "diff .env .env.example",
        "paste .env x.txt",
        "git diff --no-index .env .env.example",
        "find . -name '.env*' -exec cat {} +",
        'bash -c "cat .env"',
        "sh -lc 'grep KEY .env'",
        'eval "cat .env"',
        'echo "$(cat .env)"',
        "echo `cat .env`",
        "diff <(cat .env) <(cat .env.example)",
    ],
)
def test_env_를_읽는_명령을_막는다(명령: str) -> None:
    reason = deny_reason_for_command(명령)

    assert reason is not None
    assert ".env.example" in reason


@pytest.mark.parametrize(
    "명령",
    [
        "column .env",
        "column -t -s = .env",
        "column .e*",
        "rev .env",
        "rev .e*",
        "command column .env",
        "command -p cat .env",
        "nice rev .env",
        "nice -n5 cat .env",
        "nice -5 cat .env",
        "nice --adjustment=5 cat .env",
        "nice --adjustment 5 cat .env",
        "timeout 5 column .env",
        "timeout -s KILL 5 rev .env",
        "env -i cat .env",
        "env -u HOME cat .env",
        "sudo -u root cat .env",
        "sudo -iu root cat .env",
        "sudo -uroot cat .env",
        "sudo --user root cat .env",
        "/usr/bin/env cat .env",
        "/usr/bin/time -v cat .env",
        "env -a x cat .env",
        "env --argv0 x cat .env",
        "exec -a x cat .env",
        "time -p cat .env",
        "command nice timeout 5 rev .env",
        # 값 옵션(`--login-class`)의 머리인 플래그. `flags` 에 없어도 플래그로 읽은 글이 막으므로 이
        # 입력은 `flags` 를 재지 않는다. 옛 판도 막던 것을 고정한다(harness 티켓 012).
        "sudo --login cat .env",
        "sudo -- cat .env",
        "env - cat .env",
    ],
)
def test_묻지_않고_도는_읽기_명령과_옵션이_붙은_래퍼도_막는다(명령: str) -> None:
    """Claude Code 가 묻지 않고 돌린 읽기 명령 가운데 `column`·`rev` 가 빠져 있었다. 권한 규칙은
    래퍼(`command`·`env`·`nice`·`timeout`)를 벗겨 대 보는데, 이 훅은 래퍼 뒤의 옵션을 명령으로
    읽었다(대기열 162, 일지 2026-10-07-21 의 `review_git_read.py`)."""
    reason = deny_reason_for_command(명령)

    assert reason is not None
    assert ".env.example" in reason


def test_래퍼를_벗겨도_읽지_않는_명령은_막지_않는다() -> None:
    for 명령 in (
        "command -v cat",
        "command -v cat .env",
        "command -V cat .env",
        "column -t notes.txt",
        "rev notes.txt",
        "timeout 5 ls -la .env",
        "nice -n 5 stat .env",
        "env -i FOO=1 printenv FOO",
    ):
        assert deny_reason_for_command(명령) is None, 명령


def test_입력_리다이렉션도_읽기다() -> None:
    assert deny_reason_for_command("while read l; do echo $l; done < .env") is not None
    assert deny_reason_for_command('echo "$(< .env)"') is not None
    assert deny_reason_for_command('done < "$PWD/.env"') is not None
    assert deny_reason_for_command("cat < .env.example") is None


@pytest.mark.parametrize(
    "명령",
    [
        "grep -rn ANTHROPIC .",
        "grep -r ANTHROPIC",
        "grep -Rin -A 3 KEY",
        "grep -rC3 KEY",
        "grep --recursive KEY ./",
        "grep -rn KEY ..",
        "grep -rn KEY 2>/dev/null",
        "grep -rn KEY 2>&1 | head -n 20",
        "grep -rn KEY > hits.txt",
        'grep -rn KEY "$PWD"',
        'grep -rn KEY "$CLAUDE_PROJECT_DIR"',
        "grep -rn --include=* KEY .",
        "rg --hidden --no-ignore KEY",
        "rg --hidden -u KEY",
        "rg -. --no-ignore KEY",
        "rg -uu KEY .",
        "rg -nuu KEY",
        "rg -uu KEY 2>/dev/null",
        "rg -uu -g '.env*' KEY",
        # `.env` 하나만 빼면 `.env.local` 은 읽는다(푸시 뒤 자동 보안 리뷰, 대기열 422).
        "grep -rn --exclude .env KEY .",
        "grep -rn --exclude=.env.local KEY .",
        # grep 의 `--exclude` 는 대소문자를 가린다. GNU grep 3.1 이 `--exclude='.ENV*'` 로 `.env` 를
        # 읽었다(2026-10-23 손으로 봤다, 푸시 뒤 자동 보안 리뷰).
        "grep -rn --exclude='.ENV*' KEY .",
        # 긴 옵션 줄임을 패턴 옵션으로 보는 것은 파일 읽기 판정만이고 훑기 판정은 그대로다. grep 은
        # `--reg KEY` 를 `--regexp KEY` 로 읽어 경로 없이 루트를 훑는다.
        "grep -rn --reg KEY",
        # 값을 먹는 긴 옵션은 값 옵션 표에도 있어야 그 값을 경로로 세지 않는다. 표에 없던 판이
        # `list.txt` 를 위치 인자로 세어 `KEY` 를 경로로 읽었다(셀프 리뷰 표준 축이 grep 3.1 로
        # 봤다).
        "grep -rn --exclude-from list.txt KEY",
        # GNU grep 의 다른 긴 값 옵션도 같다. 표에 없던 판이 `5` 를 패턴, `KEY` 를 경로로 읽었다
        # (넷째 푸시 뒤 CodeRabbit·자동 보안 리뷰). 줄임(`--max-c 5`)은 아래에 있다(대기열 448).
        "grep -rn --max-count 5 KEY",
        "grep -rn --after-context 3 KEY",
        "grep -rn --before-context 3 KEY",
        "grep -rn --context 3 KEY",
        "grep -rn --binary-files text KEY",
        "grep -rn --devices read KEY",
        "grep -rn --directories recurse KEY",
        "grep -rn --label x KEY",
        "grep -rn --group-separator x KEY",
        "grep -rn --file patterns.txt",
        "grep -rn --regexp KEY",
        # `--file` 의 앞글자 견줌이 `--files-with-matches` 를 패턴 옵션으로 읽어 `KEY` 를 경로로
        # 봤다.
        "grep -rn --files-with-matches KEY",
        # 긴 값 옵션의 줄임과, 묶음 속 값 옵션 뒤의 글자. 옛 판은 `5` 를 패턴, `KEY` 를 경로로
        # 읽었고, `_` 가 든 묶음을 묶음으로 보지 않아 `-uu` 를 세지 못했다(대기열 448).
        "grep -rn --max-c 5 KEY",
        "grep -n --recur KEY",
        "rg -uueKEY_X",
        "rg -uue KEY_X",
        # `-d recurse` 는 `-r` 과 같다. `-r`·`-R` 만 본 판이 지나보냈다(셀프 리뷰 표준 축).
        "grep -d recurse KEY .",
        "grep --directories=rec KEY",
        "grep -nd recurse KEY",
    ],
)
def test_env_를_빼지_않은_저장소_전체_grep_을_막는다(명령: str) -> None:
    """감사에서 실제로 키가 실린 모양이다. grep 은 숨김 파일을 건너뛰지 않는다."""
    reason = deny_reason_for_command(명령)

    assert reason is not None
    assert "저장소 전체" in reason


def test_루트를_절대_경로나_상위_체인으로_줘도_훑기다(tmp_path: Path) -> None:
    """서브에이전트는 절대 경로를 쓴다. 판정은 cwd 기준으로 푼 경로에 `.env` 가 있는지다."""
    (tmp_path / ".env").write_text("K=v\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "deep").mkdir()
    root = tmp_path.as_posix()

    assert deny_reason_for_command(f"grep -rn KEY {root}", cwd=str(tmp_path / "src")) is not None
    assert (
        deny_reason_for_command("grep -rn KEY ../..", cwd=str(tmp_path / "src" / "deep"))
        is not None
    )
    assert deny_reason_for_command(f"rg -uu KEY {root}", cwd=str(tmp_path)) is not None
    assert deny_reason_for_command(f"grep -rn KEY {root}/src", cwd=str(tmp_path)) is None
    assert deny_reason_for_command("grep -rn KEY src/deep", cwd=str(tmp_path)) is None


@pytest.mark.parametrize(
    "명령",
    [
        "cat .env.example",
        "grep ANTHROPIC .env.example",
        "uv run --env-file .env pytest -m llm",
        "ls -la .env",
        "stat .env",
        "grep -rn KEY src/ tests/",
        "grep -rn --exclude=.env* KEY .",
        "grep -rn --exclude .env* KEY .",
        # 값 여럿이 합쳐 `.env` 꼴을 모두 뺀다(셀프 리뷰 두 축, GNU grep 3.1 로 손으로 봤다).
        "grep -rn --exclude .env --exclude '.env.*' KEY .",
        "grep -rn --exclude .env --exclude .env.local --exclude .env.production KEY .",
        "grep -rn --include=*.py KEY .",
        "grep -n KEY pyproject.toml",
        "grep -n .env .gitignore",
        "grep -rn '\\.env\\.example' docs/",
        "git ls-files | grep .env",
        "git status --short | grep -c '.env'",
        "grep -rnE 'ANTHROPIC|OPENAI' src/",
        "grep -rn KEY \\\n  src/",
        "grep -rn KEY *",
        "rg KEY",
        "rg --hidden KEY .",
        "rg --no-ignore KEY",
        "rg --no-ignore-messages KEY",
        "rg -uu -g '!.env*' KEY",
        "rg -uu --glob=!.env* KEY .",
        "rg -uu -t py KEY",
        "rg -uu -g '*.py' KEY",
        # ack 3 의 `-t` 는 값을 꼭 받아(`t|type=s`) `.env` 가 패턴이다.
        "ack -t python .env",
        "ag -G py .env",
        # ack 의 `--pager` 는 값이 선택인 문자열이고 Getopt::Long 이 `-` 로 시작하지 않는 다음
        # 낱말을 값으로 먹어 `.env` 가 패턴이다(값이 선택인데 표에 둔 하나뿐인 옵션).
        "ack --pager ANTHROPIC .env",
        # 파일을 읽는 옵션이라도 값이 `.env` 가 아니면, 패턴으로 준 `.env` 는 파일이 아니다.
        "grep -f patterns.txt src/x.py",
        "ack --files-from list.txt ANTHROPIC",
        "grep -e .env .gitignore",
        "sed --expression 1p notes.md",
        # 패턴 옵션의 줄임은 그 명령의 옵션으로 본다. grep 의 `--ma` 는 `--max-count` 이고 ack 의
        # `--match` 가 아니다(셀프 리뷰 명세 축). ack 의 `--files-from` 은 `--file` 이 아니다.
        "grep --ma=2 .env .gitignore",
        "ack --files-from list.txt .env",
        # 값 옵션 이름의 머리이기도 한 플래그는 getopt_long 이 그대로의 이름으로 읽는다. `--binary`
        # 를 `--binary-files` 의 줄임으로 읽으면 `KEY` 를 값으로 먹어 루트를 훑는다고 본다.
        "grep -rn --binary KEY src/",
        "sudo --login cat notes.md",
        # 값을 먹는 옵션의 값은 파일이 아니다. `sort -o` 는 쓰는 자리다.
        "sort -o .env notes.txt",
        "diff --label .env a.txt b.txt",
        # `sort --random-source` 는 그 파일을 난수로 읽을 뿐 내용을 내지 않는다(coreutils 의
        # `sort --help` 가 "get random bytes from FILE" 로 적는다). 파일 옵션에 넣지 않았다.
        # 출력 순서가 그 바이트로 정해지는 일부러 하는 우회는 모듈 독스트링의 못 보는 것이다.
        "sort -R --random-source .env notes.txt",
        "grep -d skip KEY .",
        "git -C sub status .env",
        "bash --norc -c 'cat notes.md'",
        "echo '.env is secret'",
        "cat <<'EOF' > note.md\ncat .env\nEOF",
        "cat > .env <<'EOF'\nK=v\nEOF",
        "cat .env.example > .env",
        'gh pr create --body "the hook denies < .env reads and cat .env"',
        "cat .envrc",
        "cat *",
        "cat *.py",
        "cat .env.ex*",
        "cat config.env",
        "cat docs/env.md",
        "printf 'ANTHROPIC_API_KEY=\\n' > .env",
        "[ -f .env ] && echo exists",
    ],
)
def test_읽지_않는_명령은_막지_않는다(명령: str) -> None:
    assert deny_reason_for_command(명령) is None


def test_env_파일_이름을_알아보고_example_은_뺀다() -> None:
    assert env_file_name(".env") == ".env"
    assert env_file_name(".ENV") == ".ENV"
    assert env_file_name("../.env.local") == ".env.local"
    assert env_file_name("$PWD/.env") == ".env"
    assert env_file_name("--file=.env") == ".env"
    assert env_file_name(".env.example") is None
    assert env_file_name(".Env.Example") is None
    assert env_file_name(".envrc") is None
    assert env_file_name("config.env") is None


def test_Grep_도구는_경로와_glob_을_본다() -> None:
    """Grep 도구는 glob 없이 훑을 때만 숨김 파일을 건너뛴다. 경로나 glob 이 닿으면 읽는다(실측)."""
    assert deny_reason_for_grep_tool(".env", None) is not None
    assert deny_reason_for_grep_tool("C:\\project\\agent\\.env", None) is not None
    assert deny_reason_for_grep_tool("C:/project/agent", ".env*") is not None
    assert deny_reason_for_grep_tool("C:/project/agent", ".env.*") is not None
    assert deny_reason_for_grep_tool("C:/project/agent", "*") is not None
    assert deny_reason_for_grep_tool("C:/project/agent", ".*") is not None
    assert deny_reason_for_grep_tool("C:/project/agent", "**/.env") is not None
    assert deny_reason_for_grep_tool(".env.example", None) is None
    assert deny_reason_for_grep_tool("C:/project/agent", ".env.example") is None
    assert deny_reason_for_grep_tool("src", "*.py") is None
    assert deny_reason_for_grep_tool(None, None) is None


@pytest.mark.parametrize(
    "glob",
    [
        "{*.md,**}",
        "{.claude/**,docs/*.md}",
        "**/{.env,x}",
        "*.{md,env}",
        "{docs/*.md,{a,.e*}}",
        "{.env}",
        "**/{.e*}",
        "{.{env},y}",
    ],
)
def test_Grep_도구의_glob_은_중괄호_갈래마다_본다(glob: str) -> None:
    """한 갈래만 `.env` 에 닿아도 막는다. 마지막 `/` 뒤 조각만 본 판은 `{.claude/**,docs/*.md}` 를
    지나보냈다(대기열 369). Grep 도구는 `{*.md,**}` 로 gitignore 된 숨김 파일을 읽었다(2026-10-22
    손으로 봤다)."""
    assert deny_reason_for_grep_tool("C:/project/agent", glob) is not None


@pytest.mark.parametrize(
    "glob",
    [
        "{*.md,docs/*.md}",
        "*.{py,md}",
        "{src,tests}/**/*.py",
        "{.env.example,*.md}",
        "{*.md",
        "{*.md}",
        "{{.env,x}",
    ],
)
def test_Grep_도구의_중괄호_glob_이_env_에_닿지_않으면_지나간다(glob: str) -> None:
    """`{{.env,x}` 의 첫 `{` 는 짝이 없어 글자로 남고(bash 처럼 뒤의 묶음만 푼다), 남은 `{` 가
    갈래마다 붙어 `.env` 에 바로 맞지 않는다."""
    assert deny_reason_for_grep_tool("C:/project/agent", glob) is None


def test_못_보는_것_gitignore_하지_않은_env_는_glob_없는_Grep_도_읽는다() -> None:
    """거짓 음성이다. Grep 도구는 glob 이 없어도 숨김 파일을 읽었다(2026-10-22 손으로 봤다). 훅은
    경로와 glob 만 보므로, gitignore 하지 않은 `.env` 가 든 폴더를 glob 없이 훑으면 지나간다."""
    assert deny_reason_for_grep_tool("C:/project/agent", None) is None


@pytest.mark.parametrize(
    "명령",
    [
        "cat .{env,x}",
        "cat ./.{envrc,env}",
        "rg -uu -g '{*.md,**}' KEY",
        "rg -uu -g '{.env}' KEY",
        "grep -rn --include={*.py,.env} KEY .",
    ],
)
def test_셸과_rg_와_grep_의_중괄호도_갈래마다_닿는지_본다(명령: str) -> None:
    """bash 는 따옴표 없는 `{a,b}` 를 갈래로 펼치고 rg 의 glob 도 중괄호를 갈래로 읽는다. 같은 값을
    견주는 자리라 Grep 도구와 함께 고쳤다(대기열 369)."""
    assert deny_reason_for_command(명령) is not None


@pytest.mark.parametrize(
    "명령",
    [
        "cat .{envrc,gitignore}",
        "rg -uu -g '{*.py,*.md}' KEY",
        "grep -rn --include={*.py,*.md} KEY .",
    ],
)
def test_중괄호의_갈래가_모두_env_밖이면_막지_않는다(명령: str) -> None:
    assert deny_reason_for_command(명령) is None


@pytest.mark.parametrize("명령", ["cat '.{env,x}'", "cat .{env}"])
def test_못_보는_것_읽는_명령의_인용된_중괄호와_쉼표_없는_묶음도_펼쳐_막는다(명령: str) -> None:
    """거짓 양성이다. 토큰은 shlex 가 인용을 벗긴 뒤라 인용된 중괄호(bash 가 펼치지 않는다)를
    가르지 못한다. 쉼표 없는 묶음은 rg·Grep 도구의 glob 처럼 갈래 하나로 풀어, bash 가 글자로 두는
    `.{env}` 도 `.env` 로 본다."""
    assert deny_reason_for_command(명령) is not None


@pytest.mark.parametrize(
    "명령", ["grep -rn --exclude={.env*,x} KEY .", "rg -uu -g '!{.env*,x}' KEY"]
)
def test_못_보는_것_빼는_glob_의_중괄호는_펼치지_않아_막는다(명령: str) -> None:
    """거짓 양성이다. 빼는 자리(`--exclude`, rg 의 `!`)의 중괄호는 펼치지 않는다. 따옴표가 있으면
    grep 은 중괄호를 글자로 읽어 `.env` 를 빼지 않으므로, 펼쳐서 뺀다고 보면 문이 열린다."""
    assert deny_reason_for_command(명령) is not None


@pytest.mark.parametrize(
    "명령",
    [
        "cat .en[!{}]",
        "cat .en[u-{}]",
        "cat .e[a-{][!}]",
        "grep -r --include=.en[u-{}] KEY .",
        "rg --hidden --no-ignore -g .en[u-{}] KEY .",
        "rg -uu -g '.en[!{}]' KEY",
    ],
)
def test_대괄호_안의_중괄호는_펼치기_전의_glob_으로도_본다(명령: str) -> None:
    """bash·GNU grep·ripgrep 은 대괄호 안의 `{`·`}` 를 글자로 읽어 `.en[!{}]` 가 `.env` 에 맞는다.
    펼친 갈래만 본 판은 `[!{}]` 를 `[!]` 로 깨뜨려 지나보냈다(옛 판은 막았다. PR 직전 보안 리뷰가
    판정 함수와 가짜 숨김 파일로 봤다)."""
    assert deny_reason_for_command(명령) is not None


@pytest.mark.parametrize("glob", ["\\.env", "\\.e\\nv", "**/\\.env*"])
def test_Grep_도구의_glob_의_역슬래시는_이스케이프로도_읽는다(glob: str) -> None:
    """Grep 도구는 glob 을 rg 에 넘기고 rg 는 역슬래시를 이스케이프로 읽는다. 역슬래시를 `/` 로만
    바꿔 본 판이 지나보냈다(셀프 리뷰 표준 축)."""
    assert deny_reason_for_grep_tool("C:/project/agent", glob) is not None


@pytest.mark.parametrize(
    "명령", ["grep -rn --include='\\.env' KEY .", "grep -rn --include='.e\\nv' KEY ."]
)
def test_grep_의_include_의_역슬래시는_이스케이프로도_읽는다(명령: str) -> None:
    """GNU grep 3.1 이 둘 다 `.env` 를 읽었다(2026-10-23 셀프 리뷰 표준 축이 손으로 봤다)."""
    assert deny_reason_for_command(명령) is not None


def test_못_보는_것_grep_의_빼는_glob_의_역슬래시는_풀지_않아_막는다() -> None:
    """거짓 양성이다. GNU grep 3.1 은 `--exclude='\\.env*'` 로 `.env` 꼴을 뺐다(셀프 리뷰 표준 축이
    손으로 봤다). rg 의 같은 꼴은 `_BASH_RG_STRICTER` 가 실제 rg 와 맞댄다."""
    assert deny_reason_for_command("grep -rn --exclude='\\.env*' KEY .") is not None


@pytest.mark.parametrize("glob", [".en[!{}]", "**/.en[!{}]", ".en[u-{}]", ".e[a-{][!}]"])
def test_Grep_도구의_대괄호_안의_중괄호도_막는다(glob: str) -> None:
    assert deny_reason_for_grep_tool("C:/project/agent", glob) is not None


@pytest.mark.parametrize(
    "명령", ["cat .en[^x]", "rg -uu -g '.en[^x]' KEY", "grep -rn --exclude=.en[^v] KEY ."]
)
def test_대괄호의_캐럿은_느낌표처럼_부정으로_읽는다(명령: str) -> None:
    """bash·GNU grep·ripgrep 은 `[^x]` 를 `[!x]` 처럼 부정으로 읽고 fnmatch 는 `^` 를 글자로 읽는다.
    그래서 `.en[^x]` 를 지나보냈고, `--exclude=.en[^v]` 는 `.env` 를 빼지 않는데 뺀다고 봤다(이 PR
    전부터 있던 구멍, PR 직전 보안 리뷰)."""
    assert deny_reason_for_command(명령) is not None
    assert deny_reason_for_grep_tool("C:/project/agent", ".en[^x]") is not None


def test_못_보는_것_갈래가_상한을_넘는_glob_은_닿는지_보지_않고_막는다() -> None:
    """거짓 양성이다. 갈래는 묶음 수에 지수로 늘어, 다 펼쳐 판정하면 묶음 열여섯에 7초가 걸렸고
    훅의 시간 제한(20초)을 넘으면 막지 않고 지나간다(fail-open, PR 직전 리뷰가 쟀다). 그래서 갈래가
    256을 넘으면 어느 갈래도 `.env` 에 닿지 않아도 막는다. 256 까지는 판정한다."""
    started = time.monotonic()
    assert deny_reason_for_grep_tool("C:/project/agent", "{a,b}" * 9) is not None
    assert deny_reason_for_grep_tool("C:/project/agent", "{a,b}" * 40) is not None
    assert deny_reason_for_command("cat " + "{a,b}" * 40) is not None
    assert deny_reason_for_grep_tool("C:/project/agent", "{a,b}" * 8) is None
    assert time.monotonic() - started < 20


def test_도구가_Grep_이면_경로를_Bash_면_명령을_판정한다() -> None:
    assert reason_for("Grep", {"path": ".env"}) is not None
    assert reason_for("Bash", {"command": "cat .env"}) is not None
    assert reason_for("Bash", {"command": "cat .env.example"}) is None
    assert reason_for("Bash", {}) is None


def test_Bash_를_막으면_묶은_다른_명령도_돌지_않았다고_알린다() -> None:
    """편집과 검색을 한 호출에 묶었다가 검색이 막혀 편집도 돌지 않았다(대기열 111)."""
    bash = reason_for("Bash", {"command": "sed -i s/a/b/ f.md && cat .env"})
    assert bash is not None
    assert "호출 전체가 돌지 않았다" in bash
    grep = reason_for("Grep", {"path": ".env"})
    assert grep is not None
    assert "호출 전체가 돌지 않았다" not in grep


@pytest.mark.parametrize(
    "명령",
    [
        "grep -rn --co KEY src/",
        "grep -rn --inc=*.py KEY .",
    ],
)
def test_못_보는_것_줄임은_두_글로_읽어_어느_쪽이든_걸리면_막는다(명령: str) -> None:
    """거짓 양성이다. 줄임을 받는 명령에서 표의 이름과 그대로 같지 않은 긴 옵션은 값 옵션의 줄임으로
    읽은 글과 플래그로 읽은 글을 모두 판정한다(harness 티켓 012). `--co` 는 grep 의 `--context`·
    `--count`·`--color` 의 머리라 grep 이 모호하다고 거부하는데, 값 옵션으로 읽은 글이 `KEY` 를 먹어
    루트를 훑는다고 본다. `--inc` 는 grep 이 `--include` 로 읽어 좁히는데, 플래그로 읽은 글이 좁히지
    않는다."""
    reason = deny_reason_for_command(명령)
    assert reason is not None
    assert "저장소 전체를 훑으며" in reason


def test_못_보는_것_가를_긴_옵션이_여덟을_넘으면_읽는_명령을_막는다() -> None:
    """거짓 양성이다. 옵션마다 플래그로 읽을지 줄임으로 읽을지의 조합이 2 의 여덟제곱을 넘으면 다
    판정하지 않고 막는다(`_MAX_AMBIGUOUS`). `--af` 는 grep 이 `--after-context` 로 읽어 `.env` 를
    읽지 않는다. 여덟이면 판정한다."""
    reason = deny_reason_for_command("grep" + " --af 1" * 9 + " KEY notes.md")
    assert reason is not None
    assert "다 판정하지 못한다" in reason
    assert deny_reason_for_command("grep" + " --af 1" * 8 + " KEY notes.md") is None


def test_레코드의_파일_옵션과_패턴_옵션은_값_옵션이다() -> None:
    """`OptionSpec` 독스트링의 불변식. 파일·패턴 옵션이 값 옵션 표에 없으면 그 값을 위치 인자로
    센다."""
    for spec in [*OPTION_SPECS.values(), *WRAPPERS.values()]:
        assert spec.files <= spec.values
        assert spec.patterns <= spec.values


@pytest.mark.parametrize(
    "명령",
    [
        'for f in .env*; do cat "$f"; done',
        "ls -a | xargs cat",
        "python -c \"print(open('.env').read())\"",
        "cp .env copy.txt",
        "grep -rn KEY sub/",
        "cat C:\\Users\\me\\.env",
        "env -S 'cat .env'",
        "stdbuf -o0 cat .env",
        "rg -uu -g '!.env' -g '!.env.local' -g '!.env.production' KEY .",
        "grep -rn --exclude '.en*[!g]' KEY .",
        "rg -uu -g '!.en*[!g]' KEY .",
        "rg -g .env.staging KEY",
    ],
)
def test_독스트링이_못_본다고_적은_것은_정말_못_본다(명령: str) -> None:
    """못 본다는 주장도 잰다(.claude/rules/tools.md). 잡게 되면 독스트링을 고친다."""
    assert deny_reason_for_command(명령, cwd=None) is None
