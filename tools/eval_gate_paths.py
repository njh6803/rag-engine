"""빠른 게이트(검색 평가)를 돌릴지를 바뀐 경로로 가른다. CI 의 `eval-fast` 잡이 체크아웃 다음에
부른다.

결정은 ADR 0018 이고 목록과 판정의 근거는 명세 `.scratch/search-eval/spec.md` 의 "CI 게이트와 기준
보고서"다. 검색에 영향을 주지 않는 PR 에서는 평가하지 않고, 그 잡은 나머지 스텝을 건너뛴 채 성공으로
끝난다(잡 자체를 건너뛰면 필수 검사 `verify` 가 빨강으로 센다). 이 스크립트를 부르는 시점에는 uv 를
아직 준비하지 않았으므로 표준 라이브러리만 쓰고, `python3 tools/eval_gate_paths.py` 로 부른다
(`tools/check_ticket.py` 와 같다).

판정(`decide`, 결과만 필요하면 `should_evaluate`)은 이벤트 이름과 바뀐 경로의 목록만 받는 순수
함수다.

- 푸시와 수동 실행(`workflow_dispatch`)은 경로를 보지 않고 늘 평가한다. 같은 브랜치에 푸시가
  이어지면 `concurrency` 가 앞 실행을 취소해 마지막 머리만 재어지므로, 앞 커밋과의 차이로 가르면
  검색을 바꾼 푸시가 문서만 바꾼 다음 푸시에 취소될 때 평가 없이 초록이 된다.
- PR 은 `EVALUATED_PATHS` 가운데 하나라도 바뀌었으면 평가한다. 바뀐 경로를 읽지 못했거나(None)
  목록이 비었으면 평가한다(닫힘 쪽). 바뀐 것이 없다고 읽으면 조용히 초록이 되기 때문이다.
- 알지 못하는 이벤트도 평가한다.

바뀐 경로(`changed_paths`)는 base 와 머리의 merge-base 부터 머리까지의
`git diff --name-only --no-renames` 다. 이름 바꾸기 찾기가 켜져 있으면 `--name-only` 가 새 경로만
내어, `src/` 의 파일을 목록 밖으로 옮긴 PR 이 평가를 건너뛴다(그래서 `--no-renames` 로 옛 경로와 새
경로를 모두 받는다). 경로는 `-z` 로 받아 한글 이름이 따옴표와 8진수 이스케이프로 감싸이지 않는다.

CLI(`main`)는 환경 변수 `GITHUB_EVENT_NAME`, `PR_BASE_SHA`, `PR_HEAD_SHA` 를 읽어 `evaluate=true` 나
`evaluate=false` 를 `GITHUB_OUTPUT` 파일에 쓰고 표준 출력에도 이유와 함께 찍는다. PR 값은 워크플로가
env 로 넘긴다(식을 스크립트에 바로 펼치지 않는다. 사용자가 정하는 `head_ref` 의 바로 펼침은 zizmor
가 주입으로 잡고, 두 SHA 는 잡지 않지만 같은 모양을 지킨다). git 이 실패해도 종료 코드는 0 이고
평가한다고 답한다. 이 스텝이 빨개져 잡이 빨개지는 것과 같은 닫힘이지만, 이유가 출력에 남는다.

못 보는 것. 목록에서 빠진 경로의 변경은 PR 에서는 평가되지 않고 병합 뒤의 푸시에서 잡힌다.
merge-base 는 base 의 SHA 와 머리의 SHA 로 구하므로 체크아웃이 두 커밋을 모두 가져야 한다(잡이
`fetch-depth: 0` 으로 받는다). 얕은 체크아웃에서는 merge-base 를 구하지 못해 평가한다. 경로는 git 이
낸 그대로 견주므로 대소문자와 구분자를 정규화하지 않는다(`SRC/a.py` 나 `src\\a.py` 는 평가하는
경로가 아니다). CI 는 리눅스라 git 이 `/` 구분의 실제 대소문자로 내므로 영향이 없다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

# 끝이 `/` 인 항목은 그 폴더 아래 전부이고, 아닌 항목은 그 파일 하나다. 저장소 루트 기준 경로다.
EVALUATED_PATHS: tuple[str, ...] = (
    "src/",
    "pyproject.toml",
    "uv.lock",
    "evals/",
    "tools/search_eval.py",
    "compose.eval.yml",
    ".github/workflows/ci.yml",
)
# 경로와 무관하게 늘 평가하는 이벤트.
ALWAYS_EVENTS: frozenset[str] = frozenset({"push", "workflow_dispatch"})
PULL_REQUEST = "pull_request"
GIT_TIMEOUT = 60.0


def is_evaluated_path(path: str) -> bool:
    """`path`(저장소 루트 기준, `/` 구분)가 평가하는 경로인지."""
    for entry in EVALUATED_PATHS:
        if entry.endswith("/"):
            if path.startswith(entry):
                return True
        elif path == entry:
            return True
    return False


def decide(event_name: str, changed: list[str] | None) -> tuple[bool, str]:
    """이 이벤트에서 빠른 게이트를 평가할지와 그 이유. 순수 함수다."""
    if event_name != PULL_REQUEST:
        if event_name in ALWAYS_EVENTS:
            return True, f"{event_name} 는 바뀐 경로를 보지 않고 늘 평가한다"
        return True, f"알지 못하는 이벤트({event_name or '빈 값'})라 평가한다"
    if not changed:
        return True, "PR 에서 바뀐 경로를 읽지 못했거나 비어 있어 평가한다"
    hits = [path for path in changed if is_evaluated_path(path)]
    if hits:
        return True, f"평가하는 경로가 바뀌었다: {', '.join(hits[:5])}"
    return False, f"평가하는 경로가 바뀌지 않았다(바뀐 파일 {len(changed)}개)"


def should_evaluate(event_name: str, changed: list[str] | None) -> bool:
    """`decide` 의 결정만."""
    return decide(event_name, changed)[0]


def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def changed_paths(repo: Path, base: str, head: str) -> list[str] | None:
    """base 와 머리의 merge-base 부터 머리까지 바뀐 경로. 읽지 못하면 None.

    이름을 바꾼 파일은 옛 경로와 새 경로를 모두 돌려준다.
    """
    if not base or not head:
        return None
    merge_base = _git(repo, "merge-base", base, head)
    if merge_base is None or not merge_base.strip():
        return None
    out = _git(repo, "diff", "-z", "--name-only", "--no-renames", merge_base.strip(), head)
    if out is None:
        return None
    return [path for path in out.split("\0") if path]


def main(*, env: Mapping[str, str] | None = None, repo: Path | None = None) -> int:
    environ = os.environ if env is None else env
    root = Path.cwd() if repo is None else repo
    event = environ.get("GITHUB_EVENT_NAME", "")
    changed: list[str] | None = None
    if event == PULL_REQUEST:
        changed = changed_paths(
            root, environ.get("PR_BASE_SHA", ""), environ.get("PR_HEAD_SHA", "")
        )
    evaluate, reason = decide(event, changed)
    line = f"evaluate={'true' if evaluate else 'false'}"
    print(f"{line} ({reason})")
    output = environ.get("GITHUB_OUTPUT", "")
    if output:
        with open(output, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
