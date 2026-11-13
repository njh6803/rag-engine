"""PreToolUse 훅(Bash). 게이트가 파이프에 묻히거나 체인 뒤의 `$?` 로 읽히면 경고한다. 막지 않는다.

CLAUDE.md 환경 함정 "파이프와 `&&`·`;` 체인 뒤의 `$?`는 마지막 명령의 종료 코드다. 판정 명령은
파이프·체인 없이 돌린다"가 네 번 어겨졌다(대기열 19 — `| tail -3; echo $?` 류). 게이트의 빨강이
tail 의 초록에 가려진다. 지침으로 적은 뒤에도 어겨졌으니 훅이고, 거짓 양성(`set -o pipefail`, 로그만
자르는 파이프)이 있어 deny 가 아니라 additionalContext 로 알린다. 거짓 양성의 비용은 문장 하나다.
어긴 동기가 출력 줄이기였으므로 경고는 대안(파일로 리다이렉트)을 함께 준다.

게이트 명령은 rag-engine 의 검증 명령인 pytest·pyright·ruff·lint-imports·zizmor 와
`tools/check_*.py`·`tools/mutate.py`·훅 러너 `tools/run_hooks.py` 다. 훅 러너는 CLAUDE.md 가
게이트로 센다. 목록에 없던 때 판정마다 `echo "… $?"` 를 붙인 명령에서 러너 뒤의 `$?` 를 앞선
게이트의 것으로 보고 두 번 거짓 경고했다(agent-os 일지 2026-10-02-03, 대기열 95). 검사 러너
`tools/run_checks.py` 도 같은 까닭으로 본다. 게이트 여럿을 함께 띄우고 그 결과로 끝나는 명령이라
게이트 수는 늘지 않는다(agent-os ADR 0005 이력 2026-10-07). 커밋 직전의 형제 번호 대조
`tools/sibling_overlap.py` 도 출력대로 고칠 것이 있으면 1로 끝나는 판정이라 본다(번호 겹침, 판을
올리지 않은 헌법 파일 등. 조건의 원천은 그 독스트링이다. 대기열 115·175·224·235). 검증 명령은 아니라
게이트 수에 들지 않는다. agent-os 의 web 명령(`pnpm -C web verify`·`visual`, Playwright 실행)은
rag-engine 에 없어 뺐다. 명령 위치에 선 것만 센다 — `uv run …`, `python`·`py` 와 `-m` 뒤도 명령
위치다. 판정 둘.
- 게이트가 파이프(`|`)의 마지막이 아닌 자리에 있다. 서브셸 안이어도 본다. 그 파이프의 종료 코드는
  마지막 명령의 것이다.
- `$?` 마다 본다 — 그 바로 앞 조각이 게이트가 아니고 그 앞 어딘가에 아직 읽히지 않은 게이트가
  있다. `$?` 는 바로 앞 명령의 것이라 게이트의 결과가 아니다(대기열 11 — `&&` 체인 뒤의 `$?`).
  게이트 바로 다음 조각이 `$?` 를 읽었으면 그 게이트는 읽힌 것이다. 그 뒤 다른 명령 다음의 `$?` 는
  그 명령의 종료 코드를 읽는 것이라 경고하지 않는다(대기열 gate-pipe-read-status — `ruff …;
  echo ruff=$?; plan_table.py …; echo plan=$?`). 파이프 경고가 이미 있으면 같은 원인이라 이 경고는
  내지 않는다.
인용 구간은 지우지 않고 자리표시자 `_` 로 바꾼다. 지우면 `--project "경로" pytest` 의 pytest 가 옵션
값 자리로 밀려 명령 위치를 잃는다(PR #91 리뷰).
못 보는 것: `set -o pipefail` 이 켜진 파이프(그래도 경고한다 — 거짓 양성), `2>&1 | tee` 처럼 결과를
버리지 않는 파이프(그래도 경고한다), 래퍼 스크립트 안의 게이트, `$PIPESTATUS`, PowerShell 의
`$LASTEXITCODE`(이 훅은 Bash 매처다). 게이트 바로 다음 조각에 `$?` 가 들었으면 그 종료 코드를 실제로
쓰는지는 보지 않고 읽은 것으로 센다(`pytest; true $?; other; echo $?` 는 조용하다 — 거짓 음성).
"""

from __future__ import annotations

import json
import re
import sys
from typing import TypedDict

_GATE = re.compile(
    r"^(?:"
    r"(?:uv\s+run\s+(?:\S+\s+)*?)?(?:(?:python3?|py)\s+(?:-\S+\s+)*?(?:-m\s+)?)?"
    r"(?:pytest|pyright|ruff|lint-imports|zizmor"
    r"|tools/(?:check_\w+|mutate|run_hooks|run_checks|sibling_overlap)\.py)\b"
    r")"
)
_HEREDOC_OPENER = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_SINGLE_QUOTED = re.compile(r"'[^']*'")
_DOUBLE_QUOTED = re.compile(r"\"(?:[^\"\\]|\\.)*\"")
# 파이프라인을 가르는 것: `;`, `&&`, `||`, 개행, 백그라운드 `&`. `2>&1` 의 & 는 리다이렉션이다.
_CHAIN = re.compile(r"\|\||&&|(?<![<>|])&(?!&)|[;\n]")
# 파이프 하나. `||` 는 _CHAIN 이 이미 갈랐다.
_PIPE = re.compile(r"(?<!\|)\|(?!\|)")
# `$?` 판정용 조각 경계. _CHAIN 에 파이프를 더한 것이다 — 파이프 뒤의 명령도 "바로 앞 명령" 이다.
_SEGMENT = re.compile(r"\|\||&&|(?<![<>])[&|]|[;\n]")
_PREFIX = re.compile(r"^(?:\s+|[({]|[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*")
_REDIRECT_HINT = (
    "출력을 줄이려면 파이프 대신 파일로 리다이렉트하고(`> <스크래치 경로>/gate.log 2>&1`),"
    " 종료 코드를 본 뒤 그 파일에서 실패 줄만 읽는다."
)


class ToolInput(TypedDict, total=False):
    command: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_input: ToolInput


def is_gate(segment: str) -> bool:
    """명령 위치에 게이트 명령이 선 조각인가."""
    return _GATE.match(_PREFIX.sub("", segment, count=1)) is not None


def warnings_for(command: str) -> list[str]:
    """경고 문장들. 없으면 비어 있다."""
    without_heredoc = "\n".join(_without_heredoc_bodies(command))
    warnings = _pipe_warnings(_DOUBLE_QUOTED.sub("_", _SINGLE_QUOTED.sub("_", without_heredoc)))
    if warnings:
        return warnings
    # `$?` 는 큰따옴표 안에서도 확장되므로 따옴표 글자만 벗기고 본다.
    return _exit_code_warnings(_SINGLE_QUOTED.sub("_", without_heredoc).replace('"', ""))


def _pipe_warnings(text: str) -> list[str]:
    warnings: list[str] = []
    for pipeline in _CHAIN.split(text):
        stages = _PIPE.split(pipeline)
        for stage in stages[:-1]:
            if is_gate(stage):
                warnings.append(
                    f"`{stage.strip()}` 가 파이프의 마지막이 아니다. 파이프의 종료 코드는 마지막"
                    " 명령의 것이라 이 게이트의 빨강이 가려진다(CLAUDE.md 환경 함정). 판정 명령은"
                    f" 파이프 없이 돌린다. {_REDIRECT_HINT}"
                )
    return warnings


def _exit_code_warnings(text: str) -> list[str]:
    if "$?" not in text:
        return []
    segments = [_PREFIX.sub("", s, count=1) for s in _SEGMENT.split(text)]
    warnings: list[str] = []
    for index, segment in enumerate(segments):
        if "$?" not in segment:
            continue
        if index == 0 or is_gate(segments[index - 1]):
            continue
        # 바로 다음 조각이 `$?` 를 읽은 게이트는 결과가 이미 읽혔다. 그 뒤 다른 명령 다음의 `$?` 는
        # 그 명령의 종료 코드를 읽는 것이라 게이트의 결과를 가리지 않는다.
        unread_gates = [
            i for i in range(index - 1) if is_gate(segments[i]) and "$?" not in segments[i + 1]
        ]
        if not unread_gates:
            continue
        gate = segments[unread_gates[-1]].strip()
        warning = (
            "`$?` 바로 앞 명령이 게이트가 아니다. `$?` 는 마지막 명령의 종료 코드라 앞의 게이트"
            f"(`{gate}`)의 결과가 아니다(CLAUDE.md 환경 함정). 판정 명령"
            f" 뒤에서 바로 읽거나 파이프·체인 없이 돌린다. {_REDIRECT_HINT}"
        )
        if warning not in warnings:
            warnings.append(warning)
    return warnings


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


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    command = payload.get("tool_input", {}).get("command")
    warnings = warnings_for(command) if command is not None else []
    if not warnings:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": " ".join(warnings),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
