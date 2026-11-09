"""PreToolUse 훅(Bash|Grep). `.env` 를 읽는 명령과 `.env` 를 경로로 준 Grep 을 막는다.
막는 대상은 실수로 내는 길(무심코 친 명령이 `.env` 의 값을 도구 출력에 싣는 것)이다. 일부러 하는
우회는 막지 않고, 그 대표 길을 아래 못 보는 것에 든다.

이 저장소의 `permissions.deny` 는 모든 위치의 `.env` 에 Read·Edit 를 막고(`//**/.env`. `./` 는
세션 cwd 기준이라 워크트리 세션에서 주 체크아웃에 닿지 않았다), PowerShell 의 `Get-Content`·
`Select-String`(별칭은 정규화된다)을 막는다(`.scratch/harness/probes/env_deny_probe.md`). Bash
규칙은 호출의 모양만 맞춰 grep 의 인자 자리를 못 보므로 Bash 는 이 훅이 맡는다. 2026-09-28
하네스 감사에서 서브에이전트의 grep 한 번에 `.env` 의 키 값이 도구 출력에 실렸다(대기열 43).
실패가 조용하고(실린 뒤에야 안다) 패턴이 고정돼 첫 사건에서 막는 훅으로 갔다
(`.claude/rules/tools.md`). Grep 도구는 glob 없이 훑으면 gitignore 된 파일을 건너뛰지만(숨김
파일은 읽는다), 경로로 `.env` 를 주거나 glob 의 한 갈래(중괄호면 갈래마다)가 그 파일에 바로 맞으면
읽는다(2026-09-28 가짜 `.env` 로 실측. 2026-10-22 에 손으로 봤다. 숨김 파일은 gitignore 하지 않은
가짜 파일로, `{*.md,**}` 는 gitignore 된 숨김 가짜 파일로 봤다, 대기열 369). 그래서 glob 은 중괄호
갈래마다 펼쳐 본다. Grep 도구는 glob 칸을 공백과 쉼표로 나눠 rg 의 `--glob` 여럿으로 넘기므로
(`grep_tool_globs`, 대기열 422) 나눈 조각마다 본다. 판정은 `tests/tools/test_hook_env_read_rg.py` 가
gitignore 된 가짜 `.env` 를 두고 실제 rg 와 맞댄다.
`.env.example` 은 읽어도 된다. 파일 이름은 대소문자를 가리지 않는다(Windows 는 `.ENV` 도 같은
파일이다).

Bash 에서 막는 모양 셋.
- 읽는 명령의 인자에 `.env` 파일. `cat .env`, `grep KEY .env`, `sed -n 1p ../.env`, `source .env`,
  `diff .env x`, `find … -exec cat {} +`, `git diff --no-index .env x`. 셸이 `.env` 로 펼칠 glob
  (`cat .e*`)도 — `*` 는 점파일을 빼므로 `cat *` 은 아니다. `bash -c "…"`·`eval`·`$(…)`·백틱·`<(…)`
  안의 명령도 한 겹씩 풀어 본다.
- 입력 리다이렉션 `< .env`.
- 저장소 전체를 훑는 grep. `grep -r` 이 경로 없이, 또는 `.`·`..`·절대 경로·`$PWD` 같은 루트 표기로
  돌면서 `--exclude=.env*` 도 `--include=*.py` 같은 좁힘도 없다. grep 은 숨김 파일을 건너뛰지 않는다
  (`*` 는 셸이 점파일을 빼므로 훑기가 아니다). 빼기는 `.env` 꼴(`_ENV_SAMPLES`)을 모두 빼야 뺀
  것이다(`--exclude .env` 는 `.env.local` 을 읽는다). rg 는 기본으로 숨김·gitignore 파일을
  건너뛰므로 `--hidden` 과 `--no-ignore`(`-u` 하나가 `--no-ignore`, `-uu` 가 둘 다)가 함께 있고
  `-g '!.env*'` 도 `-t py` 같은 좁힘도 없을 때, 또는 `-g`(`--glob`·`--iglob`, 붙여 쓴 `-g.env`, 묶은
  `-ig .env`)가 `.env` 를 고를 때 같은 판정이다. rg 의 `-g` 는 무시·숨김 규칙과 `-t` 를 이기고 뒤에
  온 glob 이 이기므로 `.env` 꼴의 견본마다 맞는 마지막 glob 으로 가른다(`_rg_reads`. `--hidden` 없는
  `rg -g .env x .` 를 지나보낸 판이 있었다, 대기열 422). 루트인지는 페이로드의
  `cwd` 기준으로 푼 경로가 cwd·`CLAUDE_PROJECT_DIR` 이거나 그 안에 `.env` 파일이 있는지(이름만
  본다)로 가른다. `.`·`..` 는 조각마다의 cwd 를 모르므로 언제나 루트로 본다 —
  `cd src && grep -r x .` 는 오탐이다.
토큰은 shlex 로 나눈다 — 인용 안의 `|` 는 분리자가 아니고 `cat ".env"` 의 인자는 보인다. grep·sed·
awk 류의 첫 위치 인자는 패턴이라 파일로 보지 않는다(`grep .env .gitignore` 는 `.gitignore` 를 읽는
것이다). 리다이렉션 대상은 인자가 아니다(`cat x > .env` 는 쓰기다).
옵션은 명령마다의 레코드(`OptionSpec`: 값 옵션, 파일 옵션, 패턴 옵션, 줄임을 가를 플래그, 줄임을
받는지)와 getopt 읽기 함수 하나(`_read_options`)로 읽고, 판정은 그 함수가 낸 (옵션, 값) 쌍과 위치
인자만 본다. 래퍼, git 의 전역 옵션, 셸의 `-c` 도 레코드로 읽는다(셸은 옛 읽기도 함께 본다,
`_shell_c_arguments`). 묶은 짧은 옵션은 앞에서 읽어 값 옵션의 값을 위치 인자로 세지 않고(`rg -ig
.env KEY` 는 경로가 없다), `--` 뒤는 모두 위치 인자다. 줄임을 받는 명령에서 표의 이름과 그대로 같지
않은데 표의 옵션 머리인 긴 옵션은 옵션마다 플래그로 읽을지 값 옵션의 줄임으로 읽을지를 정한 조합을
모두 판정한다(`_readings`). 자리마다 표와 읽는 법을 따로 둔 판이 하류와 다르게 읽는 사례를 푸시마다
새 자리에서 냈다(대기열 448, harness 티켓 012).
읽는 명령의 목록(`READERS`)에는 Claude Code 가 묻지 않고 돌린 `column`·`rev` 도 든다(대기열 162.
`.scratch/harness/probes/review_git_read.py` 가 glob 경로로 `.git/config` 를 읽거나 권한 단계를
지난 명령이다, 일지 2026-10-07-21). 명령 앞의 래퍼(`sudo`·`command`·`env`·`nice`·`timeout`·`exec`·
`time`·`nohup`·`builtin`)는 경로를 벗긴 이름으로 찾고(`/usr/bin/env`), 그 뒤의 옵션과 옵션 값까지
getopt 처럼 벗긴다(`-n5`, `-iu root`, `--user root`). 같은 프로브에서 권한 규칙이
래퍼(`env`·`command`·`nice`·`timeout`)를 벗겨 대 봤다. 이 훅은 래퍼 뒤의 옵션을 명령 이름으로 읽어
`nice -n5 cat .env`·`command -p cat .env`·`env -i cat .env` 를 지나보냈다(일지 2026-10-13-67 의
세션이 스크래치 스크립트로 찍어 봤고, 그 입력은 지금 tests/tools 가 고정한다). `command -v`·`-V` 는
명령을 찾기만 해 막지 않는다.
못 보는 것: 변수 간접 참조(`for f in .env*; do cat "$f"`), 다른 명령이 넘긴 인자(`ls -a | xargs
cat`), 언어 안의 읽기(`python -c "open('.env')"`), `cp .env x` 뒤의 `cat x`, `uv run --env-file
.env` 뒤의 `printenv`(그 명령은 LLM 테스트의 사전이라 막지 않는다), 상대 경로로 준 하위 디렉터리를
훑는 `grep -r x sub/`·`rg -g .env x sub/`(그 아래에 `.env` 가 있으면 읽는다. `..` 가 없는 상대
경로는 루트로 보지 않는다, `_is_root`), 백슬래시 경로(`C:\\x\\.env` —
shlex 가 이스케이프로 읽는다), 래퍼 스크립트 안의 읽기, 위 목록 밖의 래퍼(`stdbuf -o0 cat .env`)와
명령을 문자열 하나로 받는 래퍼 (`env -S 'cat .env'`), 레코드가 없는 명령의 옵션 값(`cat` 류는
값 옵션을 모르니 값이 `.env` 면 위치 인자로 보아 막는 쪽이다), PowerShell 도구(권한 deny 가
`Get-Content`·`Select-String` 과 그 별칭만 막고 `[IO.File]::ReadAllText` 같은 읽기는 지나간다 —
2026-09-29 가짜 `.env` 로 실측), 내용을 내지 않고 출력의 모양만 그 파일에 기대는 읽기(`sort -R
--random-source .env x` 는 `x` 의 줄 순서가 `.env` 의 바이트로 정해져, 되풀이하면 몇 비트씩 맞혀
볼 수 있다. 일부러 하는 우회다), `.env` 밖의 비밀 파일(사용자 설정의 env 값 등), gitignore 하지 않은
`.env` 가 든 폴더를 glob 없이 훑는 Grep 도구(숨김 파일을 읽는다),
견본(`.env`·`.env.local`·`.env.production`, `_ENV_SAMPLES`) 밖의 `.env` 꼴만 고르거나 남기는 glob.
판정이 견본에만 glob 을 대 보기 때문이다. 견본을 하나씩 모두 뺀 빼기
(`rg -uu -g '!.env' -g '!.env.local' -g '!.env.production'`), 견본만 빼는 한 glob
(`grep -r --exclude '.en*[!g]'`), 견본 밖을 고르는 glob(`rg -g .env.staging`)이 그 예이고, 셋 다
`.env.staging` 을 읽는다. 거짓 양성으로는 빼는 자리(`--exclude`, rg 의 `!`)의 중괄호가 있다. 펼치지
않아, 따옴표 없이 bash 가 펼쳐 `.env` 를 빼는 `--exclude={.env*,x}` 도 막는다. 인용된 중괄호는 grep
이 글자로 읽어 `.env` 를 빼지 않으므로 펼쳐서 뺀다고 보지 않는다. 닿는지 보는 자리는 거꾸로 펼쳐
본다. 토큰은 shlex 가 인용을 벗긴 뒤라, bash 가 펼치지 않는 인용된 중괄호(`cat '.{env,x}'`)와 쉼표
없는 묶음(`cat .{env}`, rg·Grep 도구의 glob 처럼 갈래 하나로 푼다)도 `.env` 로 보아 막는다. 갈래가
256 을 넘는 glob(`{a,b}` 아홉)은 어느 갈래도 `.env` 에 닿지 않아도 막는다. 다 펼쳐 판정하면 훅의
시간 제한을 넘어 지나가기 때문이다. rg·Grep 도구의 glob 에서 rg 는 읽지 않는데 막는 자리도 있다.
고르는 쪽의 대소문자(`-g .ENV`), 앞의 `./`(`-g ./.env`), 겹친 묶음(`{{.env}}`), 빼는 쪽의
중괄호(`-g .env -g '!{.env}'`)와 `--iglob` 의 빼기 대소문자(`_rg_excludes`), Grep 도구 glob 칸의
순서(`.env !.env` 는 뒤의 빼기가 이기지만 순서를 보지 않는다), 마지막 `/` 앞의 디렉터리
조각(`src/**` 를 `**` 로 읽는다), 디렉터리가 붙은 빼는 glob(`!sub/.env` 는 그 폴더만 빼지만 빼지
않는다고 본다, `_rg_excludes`), 빼는 glob 의 역슬래시(`!\\.env*` 는 rg 가 이스케이프로 읽어 `.env`
꼴을 빼지만 풀어 보지 않는다)이다. `tests/tools/test_hook_env_read_rg.py` 가 실제 rg 와 맞대
고정한다. grep 의 `--exclude='\\.env*'` 도 grep 이 `.env` 꼴을 빼는데(2026-10-23 GNU grep 3.1, 셀프
리뷰 표준 축이 손으로 봤다) 풀어 보지 않아 막는다. 옵션 줄임을 두 글로 읽어 생기는 거짓 양성도
있다. 하류가 모호하다고 거부하는 줄임(`grep -rn --co KEY src/` 의 `--co` 는 `--context`·`--count`·
`--color` 의 머리다)을 값 옵션으로 읽은 글이 `KEY` 를 먹어 루트를 훑는다고 보고, 하류가 받아 좁히는
줄임(`grep -rn --inc=*.py KEY .`)을 플래그로 읽은 글이 좁히지 않는다고 본다. 가를 긴 옵션이
여덟(`_MAX_AMBIGUOUS`)을 넘으면 조합을 다 판정하지 않고 읽는 명령을 막는다(`grep --af 1` 아홉).
ag·ack 의 레코드
(`_AG`, `_ACK`)는 두 도구의 파서 소스를 읽어 지었고 실제로 재지 않았다. 에이전트 층의 두
장치(권한 deny, 이 훅)가 못 보는 것은 셋째 층이 맡는다. 키 자체다 — 사용 한도를 건 개발용 키만 두고,
도구 출력에 실린 키는 회전한다(`docs/constitution/operations.md` 가드레일).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from collections.abc import Callable
from enum import Enum
from typing import NamedTuple, TypedDict

READERS = frozenset(
    {
        "cat", "tac", "head", "tail", "less", "more", "bat",
        "grep", "egrep", "fgrep", "rg", "ag", "ack",
        "sed", "awk", "gawk", "cut", "tr", "sort", "uniq", "nl", "column", "rev",
        "strings", "xxd", "od", "hexdump", "base64",
        "diff", "cmp", "comm", "paste",
        "source", ".",
    }
)  # fmt: skip
PATTERN_COMMANDS = frozenset({"grep", "egrep", "fgrep", "rg", "ag", "ack", "sed", "awk", "gawk"})
SHELLS = frozenset({"bash", "sh", "zsh", "dash"})
GIT_READING_SUBCOMMANDS = frozenset({"diff", "show", "grep", "blame"})
ALLOWED_ENV_FILES = frozenset({".env.example"})
_RESERVED = frozenset(
    {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for", "{", "}", "!"}
)
_ROOTISH = frozenset({".", "./", "..", "../"})
# `.env` 꼴의 견본. 견본 하나라도 읽으면 닿는다고 본다. 빼는지는 견본마다 본다(grep 은
# `_excludes_every_env`, rg 는 `_rg_reads`).
_ENV_SAMPLES = (".env", ".env.local", ".env.production")
# `.env`, `.env.local`, `../.env`, `$PWD/.env`, `C:/x/.env`. `.envrc`·`config.env` 는 아니다.
_ENV_FILE = re.compile(r"(?<![\w.-])(?:[\w.:~${}-]+/)*(\.env(?:\.[\w-]+)?)(?![\w.-])", re.I)
_HEREDOC_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
_ESCAPE = re.compile(r"\\(.)")


class Abbreviation(Enum):
    """명령이 긴 옵션의 줄임(`--max-c` 를 `--max-count` 로)을 받는가."""

    ACCEPTED = "accepted"
    REFUSED = "refused"


class OptionSpec(NamedTuple):
    """명령 하나의 옵션 레코드. 옵션 읽기(`_read_options`)와 판정은 모두 이것만 본다. 짧은 옵션은
    `-x`, 긴 옵션은 `--name` 꼴로 적는다. 자리마다 따로 둔 표와 읽기 함수가 하류와 다르게 읽는
    사례를 푸시마다 새 자리에서 냈다(대기열 448, harness 티켓 012).

    - `values`: 값을 하나 더 먹는 옵션. 그 값은 위치 인자가 아니다. 값이 선택인
      옵션(`--color[=W]`)은 `=` 로 붙인 값만 받으므로 넣지 않는다. 예외는 다음 낱말을 값으로 먹는
      선택 값 옵션(ag·ack 의 `--pager`)이다.
    - `files`: 값이 읽는 파일인 옵션. 값이 `.env` 면 읽는다고 본다. `values` 에도 있어야 한다.
    - `patterns`: 패턴(sed·awk 는 스크립트)을 따로 줘 위치 인자가 모두 파일이 되는 옵션. `values`
      에도 있어야 한다.
    - `flags`: 값을 먹지 않는 긴 옵션 가운데 줄임을 가를 때 알아야 하는 것. getopt_long 은 그대로의
      이름을 줄임보다 먼저 읽으므로, 값 옵션 이름의 머리인 플래그(`--binary` 와 `--binary-files`)를
      여기 두어야 줄임으로 읽지 않는다. 판정이 이름을 보는 플래그(`--recursive`)도 줄임으로 찾으려고
      둔다. 모든 플래그를 옮기지는 않는다.
    - `abbreviation`: 긴 옵션의 줄임을 받는가(getopt_long, Getopt::Long). rg 와 git 은 받지 않는다.
    """

    values: frozenset[str] = frozenset()
    files: frozenset[str] = frozenset()
    patterns: frozenset[str] = frozenset()
    flags: frozenset[str] = frozenset()
    abbreviation: Abbreviation = Abbreviation.REFUSED


# grep 은 GNU grep 3.x. `--binary` 는 `-U` 의 긴 꼴이다. GNU grep 3.1 이 `--max-c 1` 을
# `--max-count 1` 로, `--binary` 를 그대로의 플래그로 읽고 `--co` 는 모호하다고 거부하는 것을
# 2026-10-26 손으로 봤다.
_GREP = OptionSpec(
    values=frozenset(
        {
            "-A", "-B", "-C", "-m", "-e", "-f", "-d", "-D", "--include", "--exclude",
            "--exclude-dir", "--exclude-from", "--regexp", "--file", "--max-count",
            "--after-context", "--before-context", "--context", "--binary-files", "--devices",
            "--directories", "--label", "--group-separator",
        }
    ),
    # 표에 없던 `--exclude-from` 의 값을 경로로 세어 `grep -rn --exclude-from list.txt KEY` 가
    # 루트를 훑지 않는다고 본 판이 있었다(셀프 리뷰 표준 축). `grep -f .env` 는 그 전부터
    # 지나갔다(셋째 푸시 뒤 자동 보안 리뷰).
    files=frozenset({"-f", "--file", "--exclude-from"}),
    # 모든 명령에 같은 패턴 표를 쓴 판은 `--file` 의 앞글자 견줌으로 grep 의
    # `--files-with-matches` 를 패턴 옵션으로 읽어 `grep -rn --files-with-matches KEY` 를
    # 지나보냈고, ack 의 `--match` 를 grep 에도 견줘 `grep --ma=2 .env .gitignore`(`--max-count`)를
    # 막았다(셀프 리뷰 두 축).
    patterns=frozenset({"-e", "-f", "--regexp", "--file"}),
    flags=frozenset({"--binary", "--recursive", "--dereference-recursive"}),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
# rg 14.1.1 의 `rg --help` 에서 값을 받는 옵션을 모두 옮겼다(`-x VALUE, --long=VALUE` 와
# `--long=VALUE` 꼴, 2026-10-23 손으로 봤다). `--maxdepth` 는 `--max-depth` 의 숨은 별칭이다. 빠진
# `-r` 뒤의 `g` 를 `-g` 로 읽어 `rg -uu -rg ^ .` 를 지나보낸 판이 있었다(PR 직전 보안 리뷰).
_RG = OptionSpec(
    values=frozenset(
        {
            "-A", "-B", "-C", "-m", "-e", "-f", "-g", "-t", "-T", "-E", "-j", "-M", "-d", "-r",
            "--after-context", "--before-context", "--context", "--max-count", "--regexp",
            "--file", "--glob", "--iglob", "--type", "--type-not", "--type-add", "--encoding",
            "--threads", "--max-columns", "--pre", "--sort", "--sortr", "--color", "--colors",
            "--max-depth", "--context-separator", "--dfa-size-limit", "--engine",
            "--field-context-separator", "--field-match-separator", "--generate",
            "--hostname-bin", "--hyperlink-format", "--ignore-file", "--max-filesize",
            "--maxdepth", "--path-separator", "--pre-glob", "--regex-size-limit", "--replace",
            "--type-clear",
        }
    ),
    files=frozenset({"-f", "--file", "--ignore-file"}),
    patterns=frozenset({"-e", "-f", "--regexp", "--file"}),
)  # fmt: skip
# ag·ack 의 값 옵션. 다음 낱말을 값으로 먹는 것만 두고, 근거는 man 페이지가 아니라 파서의 정의다
# (ag 는 `src/options.c` 의 getopt 문자열과 `required_argument`, ack 3 은
# `lib/App/Ack/ConfigLoader.pm` 의 Getopt::Long 명세. 2026-10-23 원문을 받아 읽었다). 이 PC 와 CI
# 에 둘 다 없어 실제로 재지 않았다. 값을 먹지 않는 옵션을 표에 두면 그 뒤의 패턴을 값으로 먹어
# 파일을 패턴으로 버리고(거짓 음성), 값을 먹는 옵션을 빼면 그 값을 패턴으로 버려 파일을 파일로
# 본다(막는 쪽). 그래서 모르면 뺀다. 값이 선택인 것도 뺀다. ag 의 `--after`·`--before`·`--context`
# 는 `=` 로 붙인 값만 받고(짧은 `-A`·`-B`·`-C` 는 값을 꼭 받는다), ack 의 `-A`·`-B`·`-C`·`-p` 는
# 숫자가 아닌 다음 낱말을 먹지 않는다. ack 의 `--pager` 는 값이 선택이지만 Getopt::Long 이 `-` 로
# 시작하지 않는 다음 낱말을 값으로 먹어 둔다. 이 표의 앞선 두 판이 틀렸다. rg 의 표를 함께 쓴 판은
# ag 의 `-t`(--all-text)·`-f`(--follow)를 값 옵션으로 읽어 `ag -t KEY .env` 를 지나보냈고(푸시 뒤
# 자동 보안 리뷰, 대기열 422), man 페이지의 `-A NUM`·`-g PATTERN` 을 따른 판은 ack 의 `-A`·`-B`(값이
# 선택인 숫자)와 `-g`(값 없는 플래그)를 값 옵션으로 읽어 `ack -A KEY .env` 를 지나보냈다(셀프 리뷰).
# ag·ack 가 줄임을 받는다는 것은 파서(getopt_long, Getopt::Long)에서 미룬 것이고 재지 않았다.
_AG = OptionSpec(
    values=frozenset(
        {
            "-A", "-B", "-C", "-G", "-g", "-m", "-p", "-W",
            "--file-search-regex", "--filename-pattern", "--max-count", "--path-to-ignore",
            "--width", "--ignore", "--ignore-dir", "--depth", "--pager", "--workers",
            "--color-line-number", "--color-match", "--color-path", "--ackmate-dir-filter",
        }
    ),
    files=frozenset({"-p", "--path-to-ignore"}),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
# `--files-from` 을 값 옵션 표에만 넣은 판이 `ack KEY --files-from .env` 를 지나보냈다(셋째 푸시 뒤
# 자동 보안 리뷰). ack 3 의 `--ignore-file` 은 파일이 아니라 거름 명세(`--ignore-file=FILTER:ARGS`,
# ack 3 의 POD)라 파일 옵션에 넣지 않는다. `--match` 를 값 옵션 표에만 둔 판이 패턴을 값으로 먹고
# `.env` 를 패턴으로 버려 `ack --match KEY .env` 를 지나보냈다(셀프 리뷰 명세 축).
_ACK = OptionSpec(
    values=frozenset(
        {
            "-m", "-t", "-T",
            "--max-count", "--type", "--match", "--output", "--and", "--or", "--not",
            "--range-start", "--range-end", "--files-from", "--ignore-dir", "--ignore-directory",
            "--noignore-dir", "--noignore-directory", "--ignore-file", "--type-add", "--type-set",
            "--type-del", "--color-match", "--color-filename", "--color-colno", "--color-lineno",
            "--ackrc", "--pager",
        }
    ),
    files=frozenset({"--files-from", "--ackrc"}),
    patterns=frozenset({"--match"}),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
# sed 는 GNU sed 4.x. getopt_long 은 파일 옵션의 줄임도 받아 sed 4.8 이 `--fi=` 를 `--file=` 로,
# `--e=` 를 `--expression=` 으로 읽었다(셀프 리뷰 두 축이 손으로 봤다).
_SED = OptionSpec(
    values=frozenset({"-e", "-f", "-l", "--expression", "--file", "--line-length"}),
    files=frozenset({"-f", "--file"}),
    patterns=frozenset({"-e", "-f", "--expression", "--file"}),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
# gawk 5.0.0 의 `gawk --help` 에서 옮겼다. `-i`·`--include` 는 읽을 소스 라이브러리이고 프로그램
# 글을 대신하지 않으며, `-E`·`--exec` 는 `-f` 처럼 프로그램 파일을 준다. 두 파일을 가짜 파일로 주어
# `gawk -i <파일> '{print}' a.txt` 는 위치 인자의 프로그램도 돌리고 `gawk -E <파일> a.txt` 는
# `a.txt` 를 입력으로 읽는 것을 2026-10-26 손으로 봤다. 값이 선택인 `-d`·`-D`·`-L`·`-o`·`-p` 는 넣지
# 않는다.
_AWK = OptionSpec(
    values=frozenset(
        {
            "-F", "-v", "-f", "-e", "-E", "-i", "-l",
            "--field-separator", "--assign", "--file", "--source", "--exec", "--include",
            "--load",
        }
    ),
    files=frozenset({"-f", "-E", "-i", "--file", "--exec", "--include"}),
    patterns=frozenset({"-f", "-e", "-E", "--file", "--source", "--exec"}),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
# diff·sort·head·tail·cut 는 GNU diffutils·coreutils. 값 옵션 표에 없는 옵션의 값은 위치 인자로 세어
# 막는 쪽으로 기운다. `diff --from-file=.env`·`sort --files0-from=.env` 를 지나보낸 판이
# 있었다(대기열 448). diffutils 3.7 과 coreutils 8.32 의 `--help` 로 이름을 대 봤고, 가짜 파일로
# `diff --from-file=` 이 그 내용을 차이로, `sort --files0-from=` 이 오류 문구로 내는 것을 2026-10-26
# 손으로 봤다. diff 의 `--context`·`--unified` 는 값이 선택이라 값 옵션에, sort 의
# `--random-source`(읽지만 내지 않는다)는 파일 옵션에 넣지 않는다.
_DIFF = OptionSpec(
    values=frozenset(
        {
            "-C", "-U", "-F", "-I", "-x", "-X", "-S", "-L", "-D", "-W",
            "--show-function-line", "--ignore-matching-lines", "--exclude", "--exclude-from",
            "--starting-file", "--label", "--ifdef", "--width", "--tabsize", "--from-file",
            "--to-file", "--line-format", "--old-line-format", "--new-line-format",
            "--unchanged-line-format", "--old-group-format", "--new-group-format",
            "--changed-group-format", "--unchanged-group-format", "--horizon-lines", "--palette",
        }
    ),
    files=frozenset({"-X", "--exclude-from", "--from-file", "--to-file"}),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
_SORT = OptionSpec(
    values=frozenset(
        {
            "-k", "-t", "-o", "-S", "-T",
            "--key", "--field-separator", "--output", "--buffer-size", "--temporary-directory",
            "--files0-from", "--parallel", "--batch-size", "--compress-program", "--sort",
            "--random-source",
        }
    ),
    files=frozenset({"--files0-from"}),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
_HEAD = OptionSpec(
    values=frozenset({"-n", "-c", "--lines", "--bytes"}), abbreviation=Abbreviation.ACCEPTED
)  # fmt: skip
_TAIL = OptionSpec(
    values=frozenset(
        {"-n", "-c", "-s", "--lines", "--bytes", "--sleep-interval", "--pid",
         "--max-unchanged-stats"}
    ),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
_CUT = OptionSpec(
    values=frozenset(
        {"-b", "-c", "-d", "-f", "--bytes", "--characters", "--delimiter", "--fields",
         "--output-delimiter"}
    ),
    abbreviation=Abbreviation.ACCEPTED,
)  # fmt: skip
OPTION_SPECS = {
    "grep": _GREP,
    "egrep": _GREP,
    "fgrep": _GREP,
    "rg": _RG,
    "ag": _AG,
    "ack": _ACK,
    "sed": _SED,
    "awk": _AWK,
    "gawk": _AWK,
    "diff": _DIFF,
    "sort": _SORT,
    "head": _HEAD,
    "tail": _TAIL,
    "cut": _CUT,
}  # fmt: skip
_NO_OPTIONS = OptionSpec()
# 명령 자리 앞의 래퍼. 옵션은 getopt 처럼 읽고(`_read_options`), 첫 위치 인자에서 멈춘다. `timeout`
# 은 옵션 뒤의 시간 하나를 더 먹는다. sudo 는 getopt_long 이라 줄임을 받는다(`sudo --us root`).
# 그것을 모르던 판은 `sudo --us root cat .env` 의 `root` 를 명령으로 읽었다(대기열 448). `--login`
# 은 `--login-class` 의 머리인 플래그다.
WRAPPERS: dict[str, OptionSpec] = {
    "sudo": OptionSpec(
        values=frozenset(
            {
                "-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T", "-c", "-R",
                "--user", "--group", "--close-from", "--chdir", "--host", "--prompt", "--role",
                "--type", "--other-user", "--command-timeout", "--login-class", "--chroot",
            }
        ),
        flags=frozenset({"--login"}),
        abbreviation=Abbreviation.ACCEPTED,
    ),
    "env": OptionSpec(
        values=frozenset({"-u", "--unset", "-C", "--chdir", "-a", "--argv0"}),
        abbreviation=Abbreviation.ACCEPTED,
    ),
    "exec": OptionSpec(values=frozenset({"-a"})),
    "nice": OptionSpec(
        values=frozenset({"-n", "--adjustment"}), abbreviation=Abbreviation.ACCEPTED
    ),
    "timeout": OptionSpec(
        values=frozenset({"-k", "-s", "--kill-after", "--signal"}),
        abbreviation=Abbreviation.ACCEPTED,
    ),
    "time": OptionSpec(
        values=frozenset({"-o", "-f", "--output", "--format"}),
        abbreviation=Abbreviation.ACCEPTED,
    ),
    "command": _NO_OPTIONS,
    "nohup": _NO_OPTIONS,
    "builtin": _NO_OPTIONS,
}  # fmt: skip
# git 의 하위 명령 앞 전역 옵션. git 은 줄임을 받지 않는다(2026-10-26 이 PC 의 git 2.32 가
# `git --git-d=x status` 를 unknown option 으로 거부한 것을 손으로 봤다). 하위 명령을 첫 인자로만 본
# 판이 `git -C . diff --no-index .env x` 를 지나보냈다(셀프 리뷰 표준 축).
_GIT = OptionSpec(
    values=frozenset(
        {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}
    )
)  # fmt: skip
# 셸의 `-c` 는 값을 먹지 않는 플래그이고, 명령 글은 첫 위치 인자다. 긴 옵션의 `c` 를 `-c` 로 센 판이
# `bash --norc -c 'cat .env'` 의 `-c` 를 명령 글로 읽어 지나보냈다(셀프 리뷰 표준 축).
_SHELL = OptionSpec(values=frozenset({"-o", "-O", "--rcfile", "--init-file"}))


class ToolInput(TypedDict, total=False):
    command: str
    path: str
    glob: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_name: str
    tool_input: ToolInput
    cwd: str


class Segment(NamedTuple):
    """제어 연산자로 가른 명령 조각. `inputs` 는 `<` 리다이렉션의 대상들."""

    words: list[str]
    inputs: list[str]


def env_file_name(token: str) -> str | None:
    """토큰이 `.env` 파일을 가리키면 그 파일 이름, `.env.example` 이거나 아니면 None.

    glob 문자가 든 토큰은 여기서 보지 않는다 — `.env.ex*` 는 `.env.example` 만 펼치므로
    `_glob_reaching_env` 가 fnmatch 로 가른다.
    """
    if any(char in token for char in "*?["):
        return None
    match = _ENV_FILE.search(token)
    if match is None or match.group(1).lower() in ALLOWED_ENV_FILES:
        return None
    return match.group(1)


def _glob_reaching_env(token: str) -> str | None:
    """셸이 `.env` 로 펼칠 glob 이면 그 토큰(`.e*`, `.env*`, `.{env,x}`). 점으로 시작하지 않는
    갈래는 아니다. 중괄호는 bash 가 갈래로 펼치므로 갈래마다 본다(대기열 369). 갈래는
    `_brace_branches` 가 펼쳐 bash 가 글자로 두는 꼴도 막는다(모듈 독스트링의 못 보는 것). 펼치기
    전의 토큰도 본다(`_candidates`)."""
    candidates = _candidates(token.replace("\\", "/"))
    if candidates is None:
        return token
    for branch in candidates:
        leaf = branch.rsplit("/", 1)[-1]
        if not leaf.startswith("."):
            continue
        if any(char in leaf for char in "*?[") and _matches_env(leaf):
            return token
        if branch != token and env_file_name(branch) is not None:
            return token
    return None


def deny_reason_for_command(command: str, cwd: str | None = None) -> str | None:
    """Bash 명령이 `.env` 를 읽으면 막는 이유, 아니면 None. `cwd` 는 루트 판정의 기준이다."""
    segments, nested = _parse(command)
    for segment in segments:
        reason = _segment_reason(segment.words, segment.inputs, cwd)
        if reason is not None:
            return reason
    for inner in nested:
        reason = deny_reason_for_command(inner, cwd)
        if reason is not None:
            return reason
    return None


def deny_reason_for_grep_tool(path: str | None, glob: str | None) -> str | None:
    """Grep 도구의 경로나 glob 이 `.env` 파일에 닿으면 막는 이유, 아니면 None.

    Grep 도구는 glob 의 갈래가 바로 맞는 gitignore 된 파일도 읽으므로 `*`·`.*`·`**` 도 `.env` 에
    닿는 glob 이다. 중괄호는 갈래마다 펼쳐 한 갈래라도 닿으면 막는다(`{*.md,**}` 가 gitignore 된
    숨김 파일을 읽었다, 2026-10-22 손으로 봤다, 대기열 369). 확장자 glob(`*.py`)은 닿지 않는다.
    """
    if path is not None:
        name = env_file_name(path.replace("\\", "/"))
        if name is not None:
            return _grep_tool_reason(f"경로 `{name}`")
    if glob is not None and any(_reaches_env(piece) for piece in grep_tool_globs(glob)):
        return _grep_tool_reason(f"glob `{glob}`(glob 에 맞는 gitignore 된 파일도 읽는다)")
    return None


def grep_tool_globs(glob: str) -> list[str]:
    """Grep 도구가 glob 칸을 rg 의 `--glob` 여럿으로 나누는 그대로 나눈다. 공백으로 나누고, 중괄호가
    없는 조각은 쉼표로도 나눈다. 중괄호가 있는 조각은 쉼표로 나누지 않는다. 2026-10-23 claude
    2.1.302 의 Grep 도구로 손으로 봤다(`*.md,x`·`*.md x` 가 무시된 `x` 를 읽었고 `{*.md},x` 는
    아무것도 내지 않았다, 대기열 422). 통째로만 본 판이 `*.md,.env` 를 지나보냈다."""
    pieces: list[str] = []
    for piece in glob.split():
        if "{" in piece and "}" in piece:
            pieces.append(piece)
        else:
            pieces.extend(part for part in piece.split(",") if part)
    return pieces


def _grep_tool_reason(target: str) -> str:
    return (
        f"Grep 도구의 {target} 이 `.env` 에 닿는다. `.env` 는 비밀이라 도구 출력에 싣지 않는다"
        "(대기열 43). 확장자 glob 이나 하위 경로를 주고, 키 이름은 `.env.example` 에서 본다."
    )


def _file_reason(cmd: str, name: str) -> str:
    return (
        f"`{cmd}` 가 `{name}` 을 읽는다. `.env` 는 비밀이라 도구 출력에 싣지 않는다(대기열 43 — "
        "2026-09-28 감사에서 grep 한 번에 키가 실렸다). 키 이름은 `.env.example` 에 있고 값은 "
        "사용자가 넣는다. LLM 테스트는 `uv run --env-file .env pytest -m llm`(위젯은 "
        "`-m llm_widget`)으로 값을 프로세스에만 넘긴다(워크트리에서의 경로는 operations.md "
        "LLM 테스트)."
    )


def _sweep_reason(cmd: str, hint: str) -> str:
    return (
        f"`{cmd}` 가 저장소 전체를 훑으며 `.env` 를 빼지 않는다. `{hint}` 를 붙이거나 "
        "`src/ tests/ docs/` 같은 경로를 준다. 2026-09-28 감사에서 전체 grep 한 번에 `.env` 의 "
        "키가 도구 출력에 실렸다(대기열 43)."
    )


def _segment_reason(words: list[str], inputs: list[str], cwd: str | None) -> str | None:
    for target in inputs:
        name = env_file_name(target)
        if name is not None:
            return _file_reason("<", name)
    commands = _command_words(words)
    if commands is None:
        return _ambiguous_reason(words)
    for command in commands:
        reason = _command_reason(command, cwd)
        if reason is not None:
            return reason
    return None


def _ambiguous_reason(words: list[str]) -> str:
    return (
        f"`{' '.join(words)}` 의 긴 옵션 가운데 줄임인지 플래그인지 가를 수 없는 것이 "
        f"{_MAX_AMBIGUOUS} 개를 넘어 `.env` 를 읽는지 다 판정하지 못한다. 긴 옵션을 표의 이름 "
        "그대로 쓴다."
    )


def _command_words(words: list[str]) -> list[list[str]] | None:
    """래퍼를 벗긴 명령 낱말들. 래퍼의 긴 옵션을 플래그로 읽을지 줄임으로 읽을지의 조합마다
    하나이고(`_every_choice`), 조합이 너무 많으면 None 이다."""
    return _every_choice(lambda choices: _strip_prefix(words, choices))


def _command_reason(words: list[str], cwd: str | None) -> str | None:
    if not words:
        return None
    cmd, args = _command_name(words[0]), words[1:]
    if cmd in SHELLS:
        for inner in _shell_c_arguments(args):
            reason = deny_reason_for_command(inner, cwd)
            if reason is not None:
                return reason
        return None
    if cmd == "eval":
        return deny_reason_for_command(" ".join(args), cwd)
    spec = OPTION_SPECS.get(cmd, _NO_OPTIONS)
    readings = _readings(args, spec)
    if readings is None:
        return _ambiguous_reason(words) if cmd in READERS else None
    if cmd in READERS:
        for reading in readings:
            reason = _reader_reason(cmd, spec, reading)
            if reason is not None:
                return reason
    if cmd == "find" and any(_command_name(arg) in READERS for arg in args):
        for arg in args:
            name = env_file_name(arg) or _glob_reaching_env(arg)
            if name is not None:
                return _file_reason("find -exec", name)
    if cmd == "git":
        return _git_reason(args)
    if cmd in {"grep", "egrep", "fgrep"} and any(_grep_sweeps_root(r, cwd) for r in readings):
        return _sweep_reason(cmd, "--exclude=.env*")
    if cmd == "rg" and any(_rg_sweeps_root(r, cwd) for r in readings):
        return _sweep_reason(cmd, "-g '!.env*'")
    return None


def _git_reason(args: list[str]) -> str | None:
    """git 의 읽는 하위 명령이 `.env` 를 인자로 받는가. 전역 옵션(`-C .`)은 `_GIT` 로 벗긴다."""
    rest = _read_options(args, _GIT, _Choices(0), _Order.STOP_AT_POSITIONAL).positionals
    if not rest or rest[0] not in GIT_READING_SUBCOMMANDS:
        return None
    for arg in rest[1:]:
        name = env_file_name(arg)
        if name is not None:
            return _file_reason(f"git {rest[0]}", name)
    return None


def _reader_reason(cmd: str, spec: OptionSpec, reading: Reading) -> str | None:
    """읽는 명령이 위치 인자나 파일 옵션의 값으로 `.env` 를 읽는가. 패턴 명령의 첫 위치 인자는
    패턴이다(`_operands`)."""
    operands = _operands(reading, spec) if cmd in PATTERN_COMMANDS else reading.positionals
    for candidate in [*operands, *reading.values_of(spec.files)]:
        name = env_file_name(candidate) or _glob_reaching_env(candidate)
        if name is not None:
            return _file_reason(cmd, name)
    return None


def _operands(reading: Reading, spec: OptionSpec) -> list[str]:
    """패턴 명령이 파일이나 경로로 읽는 위치 인자. 패턴 옵션(`spec.patterns`)이 없으면 첫 위치
    인자는 패턴이고, 있으면 위치 인자가 모두 파일이다."""
    return reading.positionals if reading.given(spec.patterns) else reading.positionals[1:]


def _strip_prefix(words: list[str], choices: _Choices) -> list[str]:
    """명령 자리 앞의 예약어·환경변수 대입·래퍼와 그 옵션을 벗긴다. 래퍼는 경로를 벗긴 이름으로
    찾고(`/usr/bin/env`), 옵션은 `_read_options` 로 첫 위치 인자까지 읽는다. `env -` 의 `-` 는
    `-i` 와 같아 벗긴다. `command -v`·`-V` 는 명령을 찾기만 하고 돌리지 않아 빈 목록이다."""
    index = 0
    while index < len(words):
        word = words[index]
        if word in _RESERVED or _ASSIGNMENT.match(word):
            index += 1
            continue
        wrapper = _command_name(word)
        spec = WRAPPERS.get(wrapper)
        if spec is None:
            break
        reading = _read_options(words[index + 1 :], spec, choices, _Order.STOP_AT_POSITIONAL)
        if wrapper == "command" and reading.given(frozenset({"-v", "-V"})):
            return []
        rest = reading.positionals
        while rest and rest[0] == "-":
            rest = rest[1:]
        if wrapper == "timeout":
            rest = rest[1:]  # 시간
        words, index = rest, 0
    return words[index:]


class Option(NamedTuple):
    """옵션 낱말 하나(묶음이면 글자 하나)를 읽은 것. `names` 는 그 낱말이 가리킬 수 있는 옵션들이다.
    그대로의 이름이면 하나이고, 줄임으로 읽은 글에서는 머리가 맞는 표의 옵션 모두다(`_long_names`).
    `value` 는 먹은 값이나 `=` 로 붙인 값이고, 없으면 None 이다."""

    names: frozenset[str]
    value: str | None


class Reading(NamedTuple):
    """명령 인자를 getopt 처럼 읽은 글. 옵션은 인자의 차례대로다."""

    options: list[Option]
    positionals: list[str]

    def given(self, names: frozenset[str]) -> bool:
        return any(option.names & names for option in self.options)

    def count(self, names: frozenset[str]) -> int:
        """`names` 의 옵션 하나만 가리키는 옵션의 수(`-uu` 는 `-u` 둘)."""
        return sum(1 for option in self.options if len(option.names) == 1 and option.names <= names)

    def values_of(self, names: frozenset[str]) -> list[str]:
        """`names` 가운데 하나를 가리킬 수 있는 옵션의 값들. 차례는 인자의 차례다."""
        return [
            option.value
            for option in self.options
            if option.names & names and option.value is not None
        ]

    def exact_values(self, name: str) -> list[str]:
        """그 옵션 하나만 가리키는 옵션의 값들. 좁히거나 빼는 옵션(`--include`, `--exclude`)은
        줄임이 여럿에 맞으면 하류가 거부하므로 그 값으로 좁혔다고 보지 않는다."""
        return [
            option.value
            for option in self.options
            if option.names == frozenset({name}) and option.value is not None
        ]


def _readings(args: list[str], spec: OptionSpec) -> list[Reading] | None:
    """판정할 글들. 표의 이름과 그대로 같지 않은데 표의 옵션 머리인 긴 옵션(모호한 옵션)마다 쓴
    이름 그대로 두어 값 없는 플래그로 읽을지 값 옵션의 줄임으로 읽을지를 정한 조합마다 한
    글이다(`_every_choice`). 판정은 어느 글에서든 걸리면 막는다(`.claude/rules/tools.md` 의 다르게
    읽은 글을 모두 보는 항목). 훅은 하류의 플래그를 다 옮기지 않아 줄임이 모호한지 알 수 없기
    때문이다. 조합이 너무 많으면 None 이다. 줄임을 몰랐던 판이 `grep --reg=KEY .env`·`sed --exp=1p
    .env` 의 `.env` 를 패턴으로 버렸고(GNU grep 3.1 의 `--reg=` 와 sed 4.8 의 `--exp=`·`--e=` 가
    파일을 읽었다, 2026-10-23 손으로 봤다, 셋째 푸시 뒤 자동 보안 리뷰), 값 옵션의 줄임을 몰랐던
    판이 `grep -rn --max-c 5 KEY` 의 `KEY` 를 경로로 읽었다(대기열 448). 모든 옵션을 플래그로 읽은
    글과 모두 줄임으로 읽은 글 둘만 본 판은 표에 없는 플래그(ack 의 `--color`)와 줄임(`--mat`)이
    함께 든 `ack .env --color --mat X` 를 지나보냈다(셀프 리뷰 명세 축)."""
    if spec.abbreviation is Abbreviation.REFUSED:
        return [_read_options(args, spec, _Choices(0))]
    return _every_choice(lambda choices: _read_options(args, spec, choices))


# 플래그로 읽을지 줄임으로 읽을지 가르는 긴 옵션의 상한. 조합이 2 의 이 수제곱이다. 넘으면 다
# 판정하지 않고 막는다. 갈래가 256 을 넘는 glob 을 막는 것(`_brace_branches`)과 같은 까닭이다.
_MAX_AMBIGUOUS = 8


class _Choices:
    """모호한 긴 옵션을 만나는 차례마다 줄임으로 읽을지. `mask` 의 k 번째 비트가 k 번째로 만난
    모호한 옵션을 정한다. `seen` 은 지금까지 만난 수다."""

    def __init__(self, mask: int) -> None:
        self.mask = mask
        self.seen = 0

    def next_abbreviates(self) -> bool:
        chosen = bool(self.mask >> self.seen & 1)
        self.seen += 1
        return chosen


def _every_choice[T](read: Callable[[_Choices], T]) -> list[T] | None:
    """모호한 긴 옵션을 플래그로 읽을지 줄임으로 읽을지의 조합마다 `read` 를 불러 다른 결과를
    모은다. 한 길에서 만난 모호한 옵션이 `_MAX_AMBIGUOUS` 를 넘으면 None 이다. 앞의 비트로 고른
    읽기가 값을 먹는지에 따라 뒤에서 만나는 옵션이 달라지므로, 만난 수만큼 열거할 마스크를 늘려
    간다. 마스크 `m` 의 길이 `s` 개를 만났으면 `s` 번째 위의 비트는 결과를 바꾸지 않아, 늘린 한계
    안의 마스크가 모든 길을 덮는다."""
    results: list[T] = []
    mask, limit = 0, 1
    while mask < limit:
        choices = _Choices(mask)
        result = read(choices)
        if choices.seen > _MAX_AMBIGUOUS:
            return None
        limit = max(limit, 1 << choices.seen)
        if result not in results:
            results.append(result)
        mask += 1
    return results


class _Order(Enum):
    """옵션을 어디까지 읽는가. GNU getopt 는 위치 인자 뒤의 옵션도 읽고(`PERMUTE`), 래퍼·git·셸은
    첫 위치 인자에서 멈춰 그 뒤를 모두 위치 인자로 둔다(`STOP_AT_POSITIONAL`)."""

    PERMUTE = "permute"
    STOP_AT_POSITIONAL = "stop_at_positional"


def _read_options(
    args: list[str], spec: OptionSpec, choices: _Choices, order: _Order = _Order.PERMUTE
) -> Reading:
    """인자를 getopt 처럼 읽는다. 레코드가 있는 명령과 래퍼·git·셸의 옵션 읽기는 모두 이 함수
    하나이고, 판정은 그 결과만 본다(harness 티켓 012). 셸의 `-c` 는 옛 읽기(`_shell_c_arguments`)도
    함께 본다.

    - `--` 뒤는 모두 위치 인자다. 그것을 모른 판이 `grep -- --file .env` 의 `.env` 를 `--file` 의
      값으로 먹었다(대기열 448). `-` 하나도 위치 인자다(표준 입력).
    - 긴 옵션은 `--opt 값` 과 `--opt=값` 이다. 이름은 `_long_names` 가 푼다.
    - 짧은 옵션 묶음은 앞에서 읽어 처음 만난 값 옵션의 뒤 글자가, 뒤가 비었으면 다음 낱말이 값이다
      (`-n5`, `-iu root`, `-uueKEY`). 묶음 속의 값 옵션을 보지 않은 판이 `rg -ig .env KEY` 의 `.env`
      를 패턴, `KEY` 를 경로로 읽었고(푸시 뒤 자동 보안 리뷰, 대기열 422), 글자만 든 묶음을
      정규식으로 센 판이 `rg -uueKEY_X` 의 `-uu` 를 세지 못했다(대기열 448).
    - 위치 인자 뒤의 옵션을 읽을지는 `order` 가 정한다.
    """
    options: list[Option] = []
    positionals: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--":
            positionals.extend(args[index:])
            break
        if not arg.startswith("-") or arg == "-":
            if order is _Order.STOP_AT_POSITIONAL:
                positionals.extend(args[index - 1 :])
                break
            positionals.append(arg)
            continue
        if arg.startswith("--"):
            name, eq, attached = arg.partition("=")
            names = _long_names(name, spec, choices)
            if eq or not names & spec.values:
                options.append(Option(names, attached if eq else None))
            else:
                options.append(Option(names, args[index] if index < len(args) else None))
                index += 1
            continue
        for offset, letter in enumerate(arg[1:], start=2):
            short = f"-{letter}"
            if short not in spec.values:
                options.append(Option(frozenset({short}), None))
                continue
            value = arg[offset:]
            if not value and index < len(args):
                value = args[index]
                index += 1
            options.append(Option(frozenset({short}), value or None))
            break
    return Reading(options, positionals)


def _long_names(name: str, spec: OptionSpec, choices: _Choices) -> frozenset[str]:
    """긴 옵션 이름이 가리키는 옵션들. 표(`values`, `flags`)에 그대로 있으면 그것 하나다.
    getopt_long 은 그대로의 이름을 줄임보다 먼저 읽는다. 줄임을 받는 명령에서 머리가 맞는 표의
    옵션이 있으면 모호한 옵션이라 `choices` 가 정한다. 줄임으로 읽으면 머리가 맞는 표의 옵션
    모두이고(`--e` 는 grep 의 `--exclude`·`--exclude-dir`·`--exclude-from`), 아니면 쓴 이름
    그대로다. 머리는 `--` 와 한 글자 이상이다. 줄임의 최소 길이는 명령마다 달라(sed 는 `--e`,
    grep 의 `--r` 은 겹쳐 거부한다) 한 글자부터 본다."""
    if (
        spec.abbreviation is Abbreviation.REFUSED
        or len(name) < 3
        or name in spec.values
        or name in spec.flags
    ):
        return frozenset({name})
    matches = frozenset(option for option in spec.values | spec.flags if option.startswith(name))
    if matches and choices.next_abbreviates():
        return matches
    return frozenset({name})


def _command_name(word: str) -> str:
    """`\\grep`·`/usr/bin/cat`·백틱이 붙은 것도 명령 이름으로."""
    return word.lstrip("\\`").replace("\\", "/").rsplit("/", 1)[-1]


def _shell_c_arguments(args: list[str]) -> list[str]:
    """셸이 `-c` 로 돌릴 명령 글의 후보. `_SHELL` 로 읽은 첫 위치 인자와, 옵션 낱말에 `c` 가 든
    첫 짧은 옵션 다음 낱말(옛 읽기. `+o posix` 같은 `+` 옵션을 레코드가 읽지 못해 둔다) 둘을 모두
    본다(`.claude/rules/tools.md` 의 다르게 읽은 글을 모두 보는 항목)."""
    candidates: list[str] = []
    reading = _read_options(args, _SHELL, _Choices(0), _Order.STOP_AT_POSITIONAL)
    if reading.given(frozenset({"-c"})) and reading.positionals:
        candidates.append(reading.positionals[0])
    for index, arg in enumerate(args):
        if arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]:
            if index + 1 < len(args) and args[index + 1] not in candidates:
                candidates.append(args[index + 1])
            break
    return candidates


_GREP_RECURSIVE = frozenset({"-r", "-R", "--recursive", "--dereference-recursive"})


def _grep_sweeps_root(reading: Reading, cwd: str | None) -> bool:
    if not reading.given(_GREP_RECURSIVE) and not _grep_recurses_directories(reading):
        return False
    if _excludes_every_env(reading.exact_values("--exclude")):
        return False
    includes = reading.exact_values("--include")
    if includes and not any(_reaches_env(value) for value in includes):
        return False
    return _paths_reach_root(reading, _GREP, cwd)


def _grep_recurses_directories(reading: Reading) -> bool:
    """`-d recurse`(`--directories=recurse`)는 `-r` 과 같다. 값은 GNU grep 이 argmatch 로 읽어
    모호하지 않은 줄임(`rec`)도 받으므로 `recurse` 의 머리면 훑는다고 본다(`r`·`re` 는 `read` 와
    겹쳐 grep 이 거부한다. 막는 쪽이다. 2026-10-26 GNU grep 3.1 에서 `grep -d rec FAKEKEY .` 가 하위
    폴더를 훑고 `-d r`·`-d re` 가 ambiguous argument 로 끝난 것을 손으로 봤다). `-r`·`-R` 만 본 판이
    `grep -d recurse KEY .` 를 지나보냈다(셀프 리뷰 표준 축)."""
    values = reading.values_of(frozenset({"-d", "--directories"}))
    return any(value and "recurse".startswith(value) for value in values)


_RG_GLOB_OPTIONS = frozenset({"-g", "--glob", "--iglob"})


def _rg_sweeps_root(reading: Reading, cwd: str | None) -> bool:
    """rg 가 루트를 훑으며 `.env` 를 읽는가. glob(`-g`·`--glob`·`--iglob`)의 차례는 인자의 차례다.
    짧은 옵션 묶음 안의 `g` 도 본다(`-ig.env`, `-ug .env`). rg 는 묶음을 앞에서부터 읽어 값을 먹는
    옵션을 만나면 그 뒤를 값으로 읽는다(`-tg` 의 `g` 는 `-t` 의 값이다. rg 14.1.1 이 `-t g` 처럼
    `unrecognized file type: g` 로 끝났다, 2026-10-23 손으로 봤다). 값 옵션 표(`_RG`)가 rg 의 값
    옵션을 다 담지 못하면 그 옵션의 값 `g` 를 `-g` 로 읽어, 뒤의 낱말이 `.env` 가 아닌 고르는 glob
    이 되어 훑기를 지나보낸다(`-rg ^` 가 그랬다, PR 직전 보안 리뷰)."""
    u_count = reading.count(frozenset({"-u", "--unrestricted"}))
    hidden = reading.given(frozenset({"--hidden", "-."})) or u_count >= 2
    no_ignore = u_count >= 1 or any(
        name.startswith("--no-ignore") and name != "--no-ignore-messages"
        for option in reading.options
        for name in option.names
    )
    typed = reading.given(frozenset({"-t", "--type"}))
    unrestricted = hidden and no_ignore and not typed
    globs = reading.values_of(_RG_GLOB_OPTIONS)
    if not any(_rg_reads(globs, sample, unrestricted=unrestricted) for sample in _ENV_SAMPLES):
        return False
    return _paths_reach_root(reading, _RG, cwd)


def _rg_reads(globs: list[str], sample: str, *, unrestricted: bool) -> bool:
    """rg 가 `.env` 꼴의 견본 하나를 읽는가. 그 견본에 맞는 마지막 glob 이 정한다. rg 의 `-g` 는
    무시 규칙과 숨김 규칙을 이기고(`--hidden`·`--no-ignore` 없이 `-g .env` 가 gitignore 된 `.env` 를
    읽었다), `-t` 로 좁혀도 읽으며, 뒤에 온 glob 이 이긴다(`-g '!.env*' -g .env` 는 읽고 거꾸로는
    읽지 않았다). 2026-10-23 rg 14.1.1 로 손으로 봤고 `tests/tools/test_hook_env_read_rg.py` 가
    실제 rg 와 맞댄다(대기열 422). 맞는 glob 이 없으면 고르는 glob 이 하나도 없고 무시·숨김 규칙을
    모두 끄고 `-t` 로 좁히지 않은(`unrestricted`) 때만 읽는다. 견본마다 보지 않고 `.env` 꼴 하나라도
    빼면 뺀다고 본 판이 `-g '.env*' -g '!.env'`·`-uu -g '!.env'` 의 `.env.local` 을 지나보냈다(푸시
    뒤 자동 보안 리뷰)."""
    decision: bool | None = None
    for glob in globs:
        if glob.startswith("!"):
            if _rg_excludes(glob[1:], sample):
                decision = False
        elif _rg_selects(glob, sample):
            decision = True
    if decision is not None:
        return decision
    return unrestricted and all(glob.startswith("!") for glob in globs)


def _rg_selects(pattern: str, sample: str) -> bool:
    """rg 의 고르는 glob 이 견본에 닿는가. 중괄호 갈래마다 대소문자 없이 본다(`_reaches_env` 와 같은
    너그러움, 모듈 독스트링의 거짓 양성). 갈래가 너무 많으면 닿는다고 본다. 역슬래시는
    `_glob_readings` 의 글을 모두 본다."""
    for reading in _glob_readings(pattern):
        candidates = _candidates(reading)
        if candidates is None:
            return True
        if any(
            fnmatch.fnmatch(sample, branch.rsplit("/", 1)[-1].replace("[^", "[!").lower())
            for branch in candidates
        ):
            return True
    return False


def _rg_excludes(pattern: str, sample: str) -> bool:
    """rg 의 빼는 glob(`!` 뒤)이 견본을 빼는가. 펼치지 않고 대소문자를 가려 본다. rg 의 `-g` 는
    대소문자를 가려, Windows 에서도 `-g .env -g '!.ENV'` 가 `.env` 를 읽었다(2026-10-23 rg 14.1.1,
    셀프 리뷰 명세 축이 손으로 봤다). `--iglob` 과 `--glob-case-insensitive` 의 빼기도 가려 보아,
    `--iglob '!.ENV'` 는 빼지 않는다고 본다(거짓 양성). 앞의 `**/` 를 뗀 뒤에도 `/` 가 남은 glob 은
    한 폴더만 빼므로 빼지 않는다고 본다. `-g .env -g '!sub/.env'` 는 루트의 `.env` 를,
    `-uu -g '!/.env'` 는 `sub/.env` 를 읽었는데 마지막 `/` 앞을 떼고 본 판이 둘을
    지나보냈다(2026-10-23 rg 14.1.1, PR 직전 bug-perf-review 가 손으로 봤다). 그래서 `!sub/**` 처럼
    그 폴더만 빼는 glob 도 빼지 않는다고 본다(거짓 양성)."""
    while pattern.startswith("**/"):
        pattern = pattern[3:]
    return "/" not in pattern and fnmatch.fnmatchcase(sample, pattern.replace("[^", "[!"))


def _matches_env(pattern: str) -> bool:
    """glob 이 `.env` 나 `.env.<무엇>` 에 닿는가. `**/.env*` 는 앞의 디렉터리 조각을 뗀다. 중괄호는
    펼치지 않는다. 대괄호의 `[^` 는 `[!` 로 읽는다. bash·GNU grep·ripgrep 은 둘 다 부정으로 읽고
    fnmatch 는 `^` 를 글자로 읽어, `.en[^x]` 를 지나보내고 `--exclude=.en[^v]` 가 `.env` 를 뺀다고
    봤다(PR 직전 보안 리뷰)."""
    return any(_env_samples_matched(pattern))


def _excludes_every_env(patterns: list[str]) -> bool:
    """grep 의 `--exclude` 값들이 합쳐 `.env` 꼴의 견본을 모두 빼는가. 견본마다 그것을 빼는 값이
    하나라도 있어야 한다(`--exclude .env --exclude '.env.*'` 는 모두 뺀다). 중괄호는 펼치지 않아,
    인용된 중괄호를 글자로 읽는 grep 이 `.env` 를 빼지 않는데도 뺀다고 보지 않게 한다. 하나만 빼는
    glob(`.env`, `.env.local`)은 남은 꼴을 읽는다. 값 하나라도 견본 하나에 맞으면 뺀다고 본 판이
    `grep -r --exclude .env` 를 지나보냈고(푸시 뒤 자동 보안 리뷰가 rg 의 같은 판정에서 찾았다,
    대기열 422), 값마다 견본 모두를 요구한 판은 합쳐야 모두 빼는 명령을 막았다(셀프 리뷰 두 축.
    GNU grep 3.1 로 `--exclude .env` 가 `.env.local` 을 읽고 둘을 합치면 읽지 않는 것을 손으로
    봤다). rg 도 견본마다 본다(`_rg_reads`). 빼기는 대소문자를 가려 본다. GNU grep 3.1 이
    `--exclude='.ENV*'` 로 `.env` 를 읽었는데 대소문자 없이 견준 판이 뺀다고 봤다(2026-10-23 손으로
    봤다, 푸시 뒤 자동 보안 리뷰)."""
    matched = [_env_samples_excluded(pattern) for pattern in patterns]
    return bool(matched) and all(any(row[i] for row in matched) for i in range(len(_ENV_SAMPLES)))


def _env_samples_matched(pattern: str) -> list[bool]:
    """glob 의 마지막 조각이 `.env` 꼴의 견본마다 맞는가. 닿는지 보는 자리라 대소문자는 가리지
    않는다(거짓 양성 쪽)."""
    leaf = pattern.rsplit("/", 1)[-1].replace("[^", "[!").lower()
    return [fnmatch.fnmatch(sample, leaf) for sample in _ENV_SAMPLES]


def _env_samples_excluded(pattern: str) -> list[bool]:
    """grep 의 빼는 glob 의 마지막 조각이 견본마다 맞는가. 대소문자를 가린다
    (`_excludes_every_env`)."""
    leaf = pattern.rsplit("/", 1)[-1].replace("[^", "[!")
    return [fnmatch.fnmatchcase(sample, leaf) for sample in _ENV_SAMPLES]


def _reaches_env(pattern: str) -> bool:
    """중괄호 갈래 가운데 하나라도 `.env` 에 닿는가(`.env.example` 만 맞는 갈래는 아니다). 닿는지
    보는 자리(Grep 도구의 glob, rg 의 glob, grep 의 `--include`)가 쓴다. 갈래가 너무 많으면 닿는다고
    본다(`_brace_branches`). 역슬래시는 `_glob_readings` 의 글을 모두 본다."""
    for reading in _glob_readings(pattern):
        candidates = _candidates(reading)
        if candidates is None:
            return True
        if any(
            branch.rsplit("/", 1)[-1].lower() not in ALLOWED_ENV_FILES and _matches_env(branch)
            for branch in candidates
        ):
            return True
    return False


def _glob_readings(pattern: str) -> set[str]:
    """닿는지 볼 glob 의 글들. 그대로의 글, 역슬래시를 이스케이프로 지운 글, `\\` 를 `/` 로
    바꾼 글이다. 하나라도 닿으면 닿는다고 본다(`.claude/rules/tools.md` 의 이스케이프 항목). 실제 rg
    14.1.1 이 Windows 에서도 `-g '\\.env'`·`-g '\\.e\\nv'` 로 `.env` 를 읽고(`_BASH_RG_SAME`), GNU
    grep 3.1 이 `--include='\\.env'`·`--include='.e\\nv'` 로 읽었는데(2026-10-23 셀프 리뷰 표준 축이
    손으로 봤다), 역슬래시를 글자나 `/` 로만 본 판이 rg·Grep 도구·grep 의 셋을 지나보냈다(푸시 뒤
    자동 보안 리뷰, 셀프 리뷰 표준 축)."""
    return {pattern, _ESCAPE.sub(r"\1", pattern), pattern.replace("\\", "/")}


def _candidates(pattern: str) -> list[str] | None:
    """닿는지 볼 glob 들. 펼친 갈래와 펼치기 전의 패턴이다. 대괄호 안의 `{`·`}` 는 bash·GNU grep·
    ripgrep 이 글자로 읽어 `.en[!{}]` 가 `.env` 에 맞는데, 펼치면 `[!{}]` 가 `[!]` 로 깨져 맞지
    않는다. 펼친 갈래만 본 판이 그것을 지나보냈다(옛 판은 막았다, PR 직전 보안 리뷰). 갈래가
    너무 많으면 None 이다."""
    branches = _brace_branches(pattern)
    if branches is None:
        return None
    return branches if pattern in branches else [pattern, *branches]


# 펼칠 갈래의 상한. 갈래는 묶음 수에 지수로 늘어(`{a,b}` 열여섯에 65536), 다 펼쳐 판정하면 열여섯에
# 7초가 걸렸고 훅의 시간 제한(20초)을 넘으면 막지 않고 지나간다(fail-open, PR 직전 리뷰가 쟀다).
_BRANCH_LIMIT = 256


def _brace_branches(pattern: str) -> list[str] | None:
    """중괄호 갈래를 모두 펼친 glob 들. 여러 묶음과 겹친 묶음(`{a,{b,c}}`)도 푼다. 쉼표가 없는
    묶음(`{x}`)은 갈래 하나로 푼다. Grep 도구의 glob 이 그렇게 읽는다(2026-10-22 손으로 봤다.
    `.ignore` 에 든 숨김 파일을 glob 없이는 건너뛰고 `{<그 이름>}` 으로는 읽었으며, `{*.md}` 는
    마크다운을 찾았다). rg 의 `-g '{.env}'` 도 같고, 실제 rg 와 맞대는 시험이
    `tests/tools/test_hook_env_read_rg.py` 다(대기열 422). rg 14.1.1 은 겹친 묶음(`{{.env}}`)을 풀지
    못해 오류로 끝나는데 여기서는 펼쳐 막는다(거짓 양성). bash 는 그것을 글자로 두는데, 대괄호
    밖이면 글자로 둔 갈래는 `{`·`}` 가 남아 `.env` 에 바로 맞지 않는다. 대괄호 안이면 맞을 수 있어
    부르는 쪽이 펼치기 전의 패턴도 본다(`_candidates`). 짝이 없는 `{` 는 bash 처럼 글자로 두고 그
    뒤의 묶음을 푼다(`{{a,b}` 는 `{a`·`{b`). 갈래가 `_BRANCH_LIMIT` 를 넘으면 펼치기를 멈추고 None
    이다."""
    done: list[str] = []
    pending = [pattern]
    while pending:
        current = pending.pop()
        group = _first_group(current)
        if group is None:
            done.append(current)
        else:
            head, options, tail = group
            pending.extend(head + option + tail for option in reversed(options))
        if len(done) + len(pending) > _BRANCH_LIMIT:
            return None
    return done


def _first_group(pattern: str) -> tuple[str, list[str], str] | None:
    """짝이 맞는 첫 중괄호 묶음의 앞, 갈래들, 뒤. 묶음이 없으면 None 이다."""
    start = pattern.find("{")
    while start != -1:
        depth = 0
        commas: list[int] = []
        end = -1
        for index in range(start, len(pattern)):
            char = pattern[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
            elif char == "," and depth == 1:
                commas.append(index)
        if end == -1:
            start = pattern.find("{", start + 1)
            continue
        bounds = [start, *commas, end]
        options = [
            pattern[left + 1 : right] for left, right in zip(bounds, bounds[1:], strict=False)
        ]
        return pattern[:start], options, pattern[end + 1 :]
    return None


def _paths_reach_root(reading: Reading, spec: OptionSpec, cwd: str | None) -> bool:
    """훑는 경로(`_operands`)가 루트에 닿는가. 경로가 없으면 루트다."""
    paths = _operands(reading, spec)
    return not paths or any(_is_root(path, cwd) for path in paths)


def _is_root(path: str, cwd: str | None) -> bool:
    """경로가 저장소 루트(또는 `.env` 가 있는 디렉터리)인가. 확장 전 변수·홈은 보수적으로 루트.
    `.` 을 다르게 쓴 꼴(`./.`, `.//`)도 루트다. 그 꼴을 루트로 보지 않아 `rg -g .env x ./.` 를
    지나보낸 판이 있었다(PR 직전 bug-perf-review)."""
    if path in _ROOTISH or os.path.normpath(path.replace("\\", "/")) in _ROOTISH:
        return True
    if path.startswith(("$", "~")):
        return True
    if not (
        os.path.isabs(path) or path.startswith("/") or ".." in path.replace("\\", "/").split("/")
    ):
        return False
    base = cwd or os.getcwd()
    resolved = os.path.normpath(os.path.join(base, path))
    if _same_path(resolved, base):
        return True
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project and _same_path(resolved, project):
        return True
    if os.path.isfile(os.path.join(resolved, ".env")):
        return True
    return path.startswith("/") and not os.path.isdir(resolved)  # `/c/…` 처럼 못 푸는 절대 경로


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _parse(command: str) -> tuple[list[Segment], list[str]]:
    """명령을 (단어들, 입력 리다이렉션 대상들) 조각과 안에 든 명령 치환들로 나눈다."""
    text = "\n".join(_without_heredoc_bodies(command))
    # 줄 이음은 붙이고, 줄바꿈과 백틱은 분리자로. 백틱은 shlex 가 모르므로 여기서 가른다.
    text = re.sub(r"\\\r?\n", " ", text).replace("\n", " ; ").replace("`", " ; ")
    tokens = _tokens(text)
    nested = [inner for token in tokens for inner in _nested_commands(token)]
    segments: list[Segment] = []
    words: list[str] = []
    inputs: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if _is_separator(token):
            if words or inputs:
                segments.append(Segment(words, inputs))
                words, inputs = [], []
            continue
        if _is_redirect(token):
            if words and len(words[-1]) == 1 and words[-1].isdigit():
                words.pop()  # `2>` 의 파일 서술자
            if index < len(tokens) and tokens[index] == "(":
                continue  # `<(…)` 는 리다이렉션이 아니라 명령 치환
            if index < len(tokens) and not _is_separator(tokens[index]):
                target = tokens[index]
                index += 1
                if token.startswith("<") and not token.startswith("<<"):
                    inputs.append(target)
            continue
        words.append(token)
    if words or inputs:
        segments.append(Segment(words, inputs))
    return segments, nested


def _tokens(text: str) -> list[str]:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return text.split()


def _is_separator(token: str) -> bool:
    return bool(token) and all(char in ";|&()" for char in token)


def _is_redirect(token: str) -> bool:
    return bool(token) and ("<" in token or ">" in token) and all(char in "<>&|" for char in token)


def _nested_commands(token: str) -> list[str]:
    """인용된 토큰 안의 `$(…)`·`<(…)` 명령 치환 본문들. 인용 밖의 것은 shlex 가 이미 갈랐다."""
    inner: list[str] = []
    for match in re.finditer(r"\$\(|<\(", token):
        depth, index = 1, match.end()
        while index < len(token) and depth:
            depth += {"(": 1, ")": -1}.get(token[index], 0)
            index += 1
        inner.append(token[match.end() : index - 1 if depth == 0 else index])
    return inner


def _without_heredoc_bodies(command: str) -> list[str]:
    lines = command.splitlines()
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        opener = _HEREDOC_OPENER.search(line)
        if opener is None:
            continue
        strips_tabs = opener.group(1) == "-"
        terminator = opener.group(3)
        while index < len(lines):
            candidate = lines[index].lstrip("\t") if strips_tabs else lines[index]
            index += 1
            if candidate == terminator:
                break
    return kept


# 막기는 호출 단위라 같은 호출에 묶은 편집도 돌지 않는다. 편집과 `.env` 글자가 든 검색을 한
# 호출에 묶었다가 편집이 빠질 뻔했다(대기열 111, 일지 2026-10-06-02).
WHOLE_CALL_NOTE = (
    " 이 Bash 호출 전체가 돌지 않았다. 편집 같은 다른 명령을 묶었으면 그것만 따로 다시 친다"
    "(대기열 111)."
)


def reason_for(tool_name: str, tool_input: ToolInput, cwd: str | None = None) -> str | None:
    if tool_name == "Grep":
        return deny_reason_for_grep_tool(tool_input.get("path"), tool_input.get("glob"))
    command = tool_input.get("command")
    reason = deny_reason_for_command(command, cwd) if command is not None else None
    return None if reason is None else reason + WHOLE_CALL_NOTE


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    reason = reason_for(
        payload.get("tool_name", ""), payload.get("tool_input", {}), payload.get("cwd")
    )
    if reason is None:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
