"""PreToolUse 훅(Bash|PowerShell). PR head 가 로컬 HEAD 에 못 미치는데 리뷰를 부르면 막는다.

대기열 86. PR #117 에서 푸시 직후 GitHub 가 PR head 를 갱신하기 전에 `gh pr ready` 를 쳐서,
claude-review 가 옛 head(이미 되돌린 실험 커밋)를 보고 그 안의 `exit 1` 을 Critical 로 냈다.
같은 때 남긴 `@coderabbitai review` 는 "Head commit changed" 로 리뷰하지 않았다(일지
2026-10-01-09). 둘 다 어긋난 결과가 돌아온 뒤에야 알 수 있고 명령의 모양이 정해져 있어, 첫
사건에서 막는 훅으로 왔다(`.claude/rules/tools.md` 의 예외). 계기만 주면 명령은 그대로 돌아 옛
head 의 리뷰가 남는다.

잡는 명령은 둘이다. 명령 위치의 `gh pr ready`(`--undo` 는 draft 로 되돌리는 것이라 뺀다), 그리고
명령 위치의 `gh pr comment` 가 있고 명령 어딘가에 `@coderabbitai review`(또는 `full review`)가
있는 것. 명령 위치를 고르는 법은 hook_git_main_commit 과 같다(heredoc 본문을 버리고 인용을
자리표시자 `_` 로 바꾼 뒤 제어 연산자로 나눈다). 코멘트 본문은 인용이나 heredoc 안에 있으므로
언급은 원래 명령에서 찾는다.

판정은 두 단계다.
1. 선택자(PR 번호·URL·브랜치) 없이 쳤으면 지금 브랜치의 PR 이다. upstream(`@{u}`)이 같은 이름의
   원격 브랜치이고, 로컬 HEAD 가 그것과 다르며 그 조상도 아니면 푸시하지 않은 커밋이 있다는 것이라
   막는다. PR head 는 기껏해야 upstream 이므로 로컬 HEAD 와 같을 수 없다. 네트워크 없이 판정한다.
   upstream 이 다른 이름(base 를 추적하는 작업 브랜치)이면 이 단계를 건너뛴다 — 첫 판은 그 upstream
   으로 재서 푸시한 뒤에도 영원히 막았다(PR #120 claude-review).
2. 그 밖에는 `gh pr view [선택자] --json headRefOid,headRefName` 으로 PR head 를 읽는다. PR 의
   브랜치가 지금 브랜치이고, PR head 가 로컬 HEAD 와 다르고, 로컬에 있는 커밋이며, 로컬 HEAD 가
   PR head 의 조상도 아니면 막는다. PR 쪽이 앞선 것은 당기지 않았을 뿐이라 리뷰는 맞는 것을 본다.
   로컬에 없는 PR head 는 앞섰는지 알 수 없어 지나간다. 이 클론이 푸시한 옛 head 는 로컬에 있고,
   없는 것은 대개 다른 곳(GitHub 화면의 제안 커밋, 다른 세션)이 푸시한 앞선 head 다. 첫 판은 이
   경우를 막았다. 셀프 리뷰 두 축이 따로 재현했고, 기다려도 같아지지 않고 푸시는 non-ff 로
   거부되어 거부 이유가 안내한 길로는 풀리지 않았다.
git 과 gh 는 페이로드의 `cwd` 에서 돌고, 저장소를 가리키는 `GIT_*` 는 벗긴다(hook_git_main_commit).
못 보는 것:
- 인용된 선택자나 저장소 값(`gh pr ready "$PR"`). 판정하지 않는다.
- `--body-file` 이 가리키는 파일 안의 언급, `gh api` 로 남긴 코멘트, GitHub MCP 도구(이 훅은 셸
  매처다).
- `gh pr merge`. 병합 직전 확인은 `operations.md` 리뷰 파이프라인의 지침이다.
- 다른 명령의 데이터로 든 언급과 같은 명령 안의 `gh pr comment`. 언급이 그 코멘트의 것인지 가리지
  않는다(거짓 양성).
- `cd <다른 저장소> && gh pr ready` 와 `Set-Location`. cwd 의 저장소로 판정한다(hook_git_main_commit
  과 같은 한계).
- 로컬에 없는 PR head 가 사실은 옛 head 인 경우(다른 클론이 푸시한 것). 지나간다.
- 판정 뒤에 head 가 바뀌는 것(다른 세션이 막 푸시한 것).
- git·gh 가 없거나, 저장소 밖이거나, detached HEAD 이거나, 커밋이 없거나, gh 가 실패하거나 시간을
  넘기면 막지 않는다. 게이트가 아니라 안전장치라 fail-open 이다.
- 이 파일 자체가 없을 때. 등록의 실행 래퍼(tools/launch_hook.py)가 막지 않고 지나가게 해, 이 훅이
  없는 것과 같다(대기열 91). PR #120 세션이 다시 시작되며 워크트리의 settings.json 을 싣고
  `${CLAUDE_PROJECT_DIR}` 은 아직 이 파일이 없는 주 체크아웃을 가리켰다. 그때는 등록이 이 파일을
  바로 불러 파이썬이 2로 끝났고 모든 Bash·PowerShell 이 막혔다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Literal, NamedTuple, TypedDict

Kind = Literal["ready", "coderabbit"]

_REPO_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
# 호출 하나가 멈춰도 훅이 끝나도록 저마다 끊는다. 합은 settings.json 의 20초를 넘을 수 있는데,
# 넘으면 Claude Code 가 훅을 끊고 지나간다(fail-open) — 어느 쪽이든 막지 않는다.
_GIT_TIMEOUT = 5
_GH_TIMEOUT = 10
_QUOTED_PLACEHOLDER = "_"

_REQUEST = re.compile(r"gh\s+pr\s+(ready|comment)(?![\w-])(.*)", re.DOTALL)
_CODERABBIT = re.compile(r"@coderabbitai\s+(?:full\s+)?review\b", re.IGNORECASE)
_VALUE_OPTIONS = frozenset({"-b", "--body", "-F", "--body-file", "-R", "--repo"})
_REPO_OPTIONS = frozenset({"-R", "--repo"})
# 대상이 다음 토큰인 리다이렉션 연산자. `2>&1` 처럼 대상이 붙은 것은 토큰 하나로 끝난다.
_BARE_REDIRECT = re.compile(r"\d*(?:>>?|&>>?|<<?-?)")
_HEREDOC_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
_SEPARATOR = re.compile(r"\|\||&&|\$\(|`|(?<![<>])[&|]|[;\n]")
_PREFIX = re.compile(r"^(?:\s+|[({]|[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*")


class Request(NamedTuple):
    """리뷰를 부르는 명령 하나. 선택자와 저장소는 적지 않았으면 None 이다."""

    kind: Kind
    selector: str | None
    repo: str | None


class LocalState(NamedTuple):
    branch: str
    head: str
    upstream: str | None

    def upstream_if_different(self) -> str | None:
        """읽은 upstream 이 HEAD 와 다르면 그 upstream, 아니면 None. 1단계가 볼 일이 있는 경우다."""
        if self.upstream is None or self.upstream == self.head:
            return None
        return self.upstream


class PrHead(NamedTuple):
    oid: str
    branch: str


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput
    cwd: str


class _PrView(TypedDict, total=False):
    """`gh pr view --json headRefOid,headRefName` 의 출력. 값은 읽은 뒤 좁힌다."""

    headRefOid: object
    headRefName: object


def request_in(command: str) -> Request | None:
    """명령 위치의 `gh pr ready` 나 CodeRabbit 을 부르는 `gh pr comment`. 없으면 None."""
    mentions_coderabbit = _CODERABBIT.search(command) is not None
    for segment in _executed_segments(command):
        match = _REQUEST.match(segment)
        if match is None:
            continue
        kind: Kind = "ready" if match.group(1) == "ready" else "coderabbit"
        if kind == "coderabbit" and not mentions_coderabbit:
            continue
        return _parse_arguments(kind, match.group(2).split())
    return None


def _parse_arguments(kind: Kind, tokens: list[str]) -> Request | None:
    selector: str | None = None
    repo: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if "<" in token or ">" in token:
            # 리다이렉션. 연산자만 떨어져 있으면(`> out`, `<< EOF`) 뒤의 대상도 건너뛴다.
            if _BARE_REDIRECT.fullmatch(token):
                index += 1
            continue
        if token == "--undo":
            return None
        name, has_value, inline = token.partition("=")
        if name in _REPO_OPTIONS:
            value = inline if has_value else (tokens[index] if index < len(tokens) else "")
            index += 0 if has_value else 1
            if value in ("", _QUOTED_PLACEHOLDER):
                return None
            repo = value
            continue
        if token.startswith("-"):
            if name in _VALUE_OPTIONS and not has_value:
                index += 1
            continue
        if selector is None:
            if token == _QUOTED_PLACEHOLDER:
                return None
            selector = token
    return Request(kind, selector, repo)


def _executed_segments(command: str) -> list[str]:
    joined = _QUOTED.sub(_QUOTED_PLACEHOLDER, "\n".join(_without_heredoc_bodies(command)))
    return [_PREFIX.sub("", piece, count=1) for piece in _SEPARATOR.split(joined)]


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


def _short(oid: str) -> str:
    return oid[:7]


def _effect(kind: Kind) -> str:
    if kind == "ready":
        return "`gh pr ready` 는 그 순간의 PR head 로 claude-review 를 돌린다"
    return '`@coderabbitai review` 는 head 가 바뀌면 "Head commit changed" 로 버려진다'


def unpushed_reason(
    request: Request, local: LocalState, *, head_behind_upstream: bool
) -> str | None:
    """선택자 없는 요청에서 로컬 HEAD 가 upstream 에 아직 없으면 막는 이유, 아니면 None."""
    upstream = local.upstream_if_different()
    if request.selector is not None or upstream is None or head_behind_upstream:
        return None
    return (
        f"로컬 HEAD `{_short(local.head)}` 가 upstream `{_short(upstream)}` 에 아직 없다. "
        f"{_effect(request.kind)}(대기열 86). 푸시하지 않은 커밋은 리뷰되지 않는다. 먼저 푸시하고, "
        "`gh pr view --json headRefOid` 가 로컬 HEAD 와 같아진 뒤 다시 친다."
    )


def stale_reason(request: Request, local: LocalState, pr: PrHead, *, pr_ahead: bool) -> str | None:
    """PR head 가 지금 브랜치의 로컬 HEAD 에 못 미치면 막는 이유, 아니면 None."""
    if pr.branch != local.branch or pr.oid == local.head or pr_ahead:
        return None
    return (
        f"PR head 가 아직 `{_short(pr.oid)}` 이고 로컬 HEAD 는 `{_short(local.head)}` 다. "
        f"{_effect(request.kind)}(대기열 86 — PR #117 에서 푸시 직후 둘 다 옛 head 를 봤다). "
        "푸시 뒤 GitHub 가 PR head 를 갱신하는 데 몇십 초 걸릴 수 있다. 푸시하지 않았으면 먼저 "
        "푸시하고, `gh pr view --json headRefOid` 가 로컬 HEAD 와 같아진 뒤 다시 친다."
    )


def _environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in _REPO_LOCATION_VARS}


def _git(cwd: str | None, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=_environment(),
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_line(cwd: str | None, *args: str) -> str | None:
    result = _git(cwd, *args)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def local_state(cwd: str | None) -> LocalState | None:
    """`cwd` 의 브랜치, HEAD, upstream. 저장소가 아니거나 detached 이거나 커밋이 없으면 None.

    upstream 은 같은 이름의 원격 브랜치를 추적할 때만 읽는다. base 를 추적하는 작업 브랜치(`git
    checkout -b x origin/main`)의 upstream 은 PR head 가 아니라, 그것으로 재면 푸시한 뒤에도 막는다.
    """
    branch = _git_line(cwd, "branch", "--show-current")
    head = _git_line(cwd, "rev-parse", "--verify", "-q", "HEAD")
    if branch is None or head is None:
        return None
    merge = _git_line(cwd, "config", "--get", f"branch.{branch}.merge")
    if merge != f"refs/heads/{branch}":
        return LocalState(branch, head, None)
    return LocalState(branch, head, _git_line(cwd, "rev-parse", "--verify", "-q", "@{u}"))


def is_ancestor(cwd: str | None, older: str, newer: str) -> bool:
    """`older` 가 `newer` 의 조상(같은 것 포함)인가. 모르는 커밋이면 False."""
    result = _git(cwd, "merge-base", "--is-ancestor", older, newer)
    return result is not None and result.returncode == 0


def has_commit(cwd: str | None, oid: str) -> bool:
    """`oid` 가 `cwd` 저장소에 있는 커밋인가."""
    result = _git(cwd, "cat-file", "-e", f"{oid}^{{commit}}")
    return result is not None and result.returncode == 0


def pr_view_args(request: Request) -> list[str]:
    """PR head 를 읽는 `gh` 의 인자. 선택자가 없으면 gh 가 지금 브랜치의 PR 을 고른다."""
    args = ["pr", "view"]
    if request.selector is not None:
        args.append(request.selector)
    if request.repo is not None:
        args += ["--repo", request.repo]
    return [*args, "--json", "headRefOid,headRefName"]


def parse_pr_view(text: str) -> PrHead | None:
    """`gh pr view --json headRefOid,headRefName` 의 출력. 객체가 아니거나 값이 문자열이 아니면
    None.

    `{` 로 시작하는 올바른 JSON 은 객체뿐이라 주해가 참이다(hook_prompt_directive 와 같다).
    """
    if not text.lstrip().startswith("{"):
        return None
    try:
        view: _PrView = json.loads(text)
    except ValueError:
        return None
    oid = view.get("headRefOid")
    branch = view.get("headRefName")
    if not isinstance(oid, str) or not isinstance(branch, str):
        return None
    return PrHead(oid, branch)


def pr_head(cwd: str | None, request: Request) -> PrHead | None:
    """gh 로 읽은 PR head. gh 가 없거나 실패하거나 시간을 넘기면 None."""
    gh = shutil.which("gh")
    if gh is None:
        return None
    try:
        result = subprocess.run(
            [gh, *pr_view_args(request)],
            cwd=cwd,
            env=_environment(),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=_GH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return parse_pr_view(result.stdout)


def reason_for(request: Request, cwd: str | None) -> str | None:
    """막는 이유. 1단계(로컬)가 막으면 gh 를 부르지 않는다."""
    local = local_state(cwd)
    if local is None:
        return None
    # upstream 이 같으면 조상 판정(git 호출)이 필요 없다. 조건은 unpushed_reason 과 같은 질의다.
    upstream = local.upstream_if_different()
    if upstream is not None:
        behind = is_ancestor(cwd, local.head, upstream)
        reason = unpushed_reason(request, local, head_behind_upstream=behind)
        if reason is not None:
            return reason
    pr = pr_head(cwd, request)
    return None if pr is None else judge_pr(cwd, request, local, pr)


def judge_pr(cwd: str | None, request: Request, local: LocalState, pr: PrHead) -> str | None:
    """gh 로 읽은 PR head 를 로컬과 견준다. 로컬에 없는 PR head 는 앞섰는지 몰라 지나간다."""
    if pr.branch != local.branch or pr.oid == local.head or not has_commit(cwd, pr.oid):
        return None
    return stale_reason(request, local, pr, pr_ahead=is_ancestor(cwd, local.head, pr.oid))


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    request = request_in(command) if command is not None else None
    if request is None:
        return 0
    reason = reason_for(request, payload.get("cwd"))
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
