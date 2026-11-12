"""기준 브랜치 규칙의 구현. 단독 실행 스크립트가 아닌 도구(검사, 점검, 보고)가 함께 쓴다.

규칙의 원천은 ADR 0016 이다(agent-os 의 ADR 0043 과 그 저장소의 전환 티켓 `dev-branch-transition`
의 "기준 브랜치 규칙"을 따른다). 기준 브랜치는 PR 의 base 이자 워크트리를 딸 자리다. 브랜치 접두로
가른다.

- `hotfix/*` 는 `main` 이다.
- 그 밖(`feature/*`, `chore/*`, `docs/*`, 앱이 만든 이름, 분리 HEAD)은 이 클론에 `origin/dev` 의
  추적 ref 가 있으면 `dev`, 없으면 `main` 이다. 원격에 dev 가 있어도 이 클론이 받은 적이 없으면 main
  이다. dev 를 따기 전에는 모든 도구가 지금처럼 main 을 기준으로 돌고, dev 를 딴 순간부터 같은
  코드가 dev 를 기준으로 쓴다.

이 규칙을 따로 구현한 곳이 둘 더 있다. 둘 다 이 모듈을 import 하지 못하는 단독 실행 스크립트다.
`tools/hook_push_behind_main.py` 의 `base_branch`(훅은 서로 import 하지 않는다,
`.claude/rules/tools.md`)와 `tools/check_ticket.py` 의 `base_ref`(CI 가 uv 없이 표준
라이브러리만으로 돌린다)다. 셋이 같은 입력에 같은 기준을 낸다는 것은 `tests/tools/test_base_rule.py`
가 시험의 브랜치 이름마다 고정하고(정상 저장소에서만이다. git 이 실패하면 훅은 기준을 내지 않고 이
모듈은 main 을 낸다), `hotfix/` 로 기준을 가르는 파일이 더 늘면 같은 시험이 잡는다. 규칙에 갈래가
더해지면(예: `release/*`) 세 곳이 함께 바뀌어야 한다. 시험의 이름 목록(`BRANCHES`)에 그 접두의
이름이 있는 갈래는 하나만 바꾸면 빨개지고, 없는 갈래는 목록에 더해야 잡힌다(`release/x` 는 이미
든다).

못 보는 것. 이 클론의 `origin/dev` 가 낡았는지는 보지 않는다(받지 않은 채 오래 지난 클론은 옛 dev 를
기준으로 쓴다). git 이 실패하거나 시간을 넘기면 dev 가 없다고 읽어 main 을 낸다. 기준을 잘못 고른
도구는 번호 겹침을 놓치거나 지울 것을 남기는 쪽으로 틀리지 지우는 쪽으로 틀리지 않는다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REMOTE = "origin"
MAIN = "main"
DEV = "dev"
HOTFIX_PREFIX = "hotfix/"
GIT_TIMEOUT = 30.0


def base_name(branch: str | None, *, dev_exists: bool) -> str:
    """`branch` 의 기준 브랜치 이름(`main` 이나 `dev`). 규칙의 순수한 판정이다.

    `branch` 가 None 이면 분리 HEAD 다. 접두를 알 수 없으니 hotfix 가 아닌 쪽으로 읽는다.
    """
    if branch is not None and branch.startswith(HOTFIX_PREFIX):
        return MAIN
    return DEV if dev_exists else MAIN


def _succeeds(cwd: Path, *args: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def has_ref(cwd: Path, name: str) -> bool:
    """`origin/<name>` 의 추적 ref 가 이 클론에 있고 커밋을 가리키는지."""
    return _succeeds(
        cwd, "rev-parse", "--verify", "--quiet", f"refs/remotes/{REMOTE}/{name}^{{commit}}"
    )


def current_branch(cwd: Path) -> str | None:
    """지금 브랜치, 분리 HEAD 이거나 git 이 실패하면 None."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "symbolic-ref", "-q", "--short", "HEAD"],
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def base_for(cwd: Path, branch: str | None) -> str:
    """`branch` 의 기준 브랜치 이름. `origin/dev` 의 추적 ref 가 있는지만 로컬 git 으로 본다."""
    if branch is not None and branch.startswith(HOTFIX_PREFIX):
        return MAIN
    return base_name(branch, dev_exists=has_ref(cwd, DEV))


def base_ref(cwd: Path, branch: str | None) -> str:
    """`branch` 가 견줄 원격 추적 ref 의 짧은 이름(`origin/main` 이나 `origin/dev`)."""
    return f"{REMOTE}/{base_for(cwd, branch)}"
