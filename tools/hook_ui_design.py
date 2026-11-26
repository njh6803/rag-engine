"""PostToolUse 훅(Write|Edit). 기능의 디자인 폴더(`.scratch/<기능>/design/`) 아래 파일을 쓰거나
고치면, 화면을 그리거나 옮기는 일이라면 `/ui-design <기능>` 스킬을 불러 따르라는 계기를
세션·에이전트마다 한 번 컨텍스트에 넣는다.

왜. 화면 디자인 절차는 프로젝트 스킬 `/ui-design` 이고, 그 한 단계가 플러그인 스킬 `frontend-design`
을 부른다. 스킬 목록 예산에서 `frontend-design` 은 설명을 잃어 모델이 스스로 고르는 길이 사라졌고,
`/ui-design` 도 설명을 먼저 잃을 수 있다. 그래서 설명과 무관하게 남는 하네스의 계기 둘을 두었다.
하나는 `next-session` 결정표의 "화면 디자인" 줄이고, 다른 하나가 쓴 파일의 경로를 보는 이 훅이다
(agent-os ADR 0033 이력 2026-10-20 "하네스가 스킬을 부르는 자리를 감사하고, 설명에만 기대던 계기를
하네스로 옮긴다"에서 옮겼다. 이 저장소의 결정은 ADR 0026 "화면 그림을 명세 앞에 둔다"). 쓰는 순간에
알리는 계기 훅이고 막지 않는다. 디자인 폴더의 쓰기가 다 화면 작업은 아니다(README 의 한 줄 고침,
명세 세션의 링크). 경로 규칙(`.claude/rules/*.md` 의 `paths`)으로 두지 않은 까닭도 그 이력이다. 그
규칙은 디자인 파일을 여는 코드 세션에도 실리고, Write 로 처음 만드는 파일에 실리는지는 재지 못했다.
등록은 새 매처 묶음을 만들지 않고 첫 `Write|Edit` 묶음에 더한다. 값은 Write·Edit 마다 래퍼를 거친
파이썬 한 번이다(약 0.2초, `.claude/rules/tools.md` 의 시간 항목의 어림이고 이 훅은 재지 않았다).

판정. 도구가 Write·Edit 이고 `tool_input.file_path` 가 문자열이며, 경로를 `/`·`\\` 로 가른 토막에
`.scratch`, 기능, `design` 이 이어지고 그 뒤에 토막이 하나 이상 있으면(대소문자를 가리지 않는다)
알린다. 가르기 전에 `.`·`..` 토막을 접는다(`posixpath.normpath`). 접히지 않고 남는 `..` 는 경로
맨 앞뿐이라 `.scratch` 뒤에 오지 않고 판정을 바꾸지 않는다. 문장에는 그 기능 토막을 넣어
`/ui-design <기능>` 으로 적는다. `.scratch/design/` 처럼 기능 토막이 없는 경로와 `design` 으로
끝나는 폴더 경로는 지나간다.

한 번. 표지는 `tools/launch_hook.py` 의 모양이다. 임시 폴더(`tempfile.gettempdir()`) 아래
`STATE_DIR` 에 세션 ID 와 `agent_id`(서브에이전트는 컨텍스트가 따로다)의 해시로 빈 파일을 `O_EXCL`
로 만든다. 세션을 모르거나 표지를 쓰지 못하면 호출마다 알린다. 알리지 못하는 것보다 되풀이가
낫다(래퍼와 같다).

못 보는 것:
- Bash(`cp`, heredoc, `>`)로 디자인 폴더에 둔 파일. 이 훅은 편집 도구에만 붙는다. 아티팩트에서
  `read` 로 받은 화면 파일을 `cp` 로 옮기는 길이 그것이고, 그 길은 `/ui-design` 이 이미 돌고 있을
  때다.
- 이미 `/ui-design` 을 부른 세션인지. 그 스킬이 쓰는 첫 파일(README 표)에도 한 번 알린다. 문장이
  "이미 부른 세션이면 무시한다"를 든다.
- 한 번 알린 뒤의 다른 기능. 표지는 세션·에이전트마다 하나라, 한 세션이 두 기능의 디자인 폴더에 쓰면
  둘째 기능은 알림을 받지 못한다. 컨텍스트 압축이나 이어 하기로 알림 문장이 사라져도 같은 세션 ID 면
  표지가 남아 알리지 않는다.
- 윈도가 경로 토막 끝의 점과 공백을 지워 읽는 이름. `design.` 이나 `design ` 은 윈도에서 디자인
  폴더로 풀리지만 이 훅은 글자 그대로 가르므로 지나간다.
- 이 문장이 메인 세션과 서브에이전트의 모델에게 닿는지. 입력의 `agent_id` 로 표지만 가르고 같은
  문장을 낸다. 재지 않았다.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

TOOLS = ("Write", "Edit")
STATE_DIR = "rag-engine-ui-design"
# 알림의 첫 문장. 알림이 모델에게 닿는지 잴 때 모델이 옮겼는지 볼 문구다.
LEAD = "기능의 디자인 폴더에 파일을 썼다"
_BODY = (
    "{lead}(`.scratch/{slug}/design/`). 화면을 그리거나(목업, 와이어프레임) 그린 화면을 이 폴더로"
    " 옮기는 일이면, 더 쓰기 전에 Skill 도구로 `ui-design` 을 인자 `{slug}` 로 불러"
    "(`/ui-design {slug}`) 그 순서를 따른다. 그 스킬이 `frontend-design` 을 부르고, 저장소 규칙과"
    " 부딪치면 저장소 규칙을 따르며 부딪친 자리를 기록한다. 이미 그 스킬을 부른 세션이거나 화면"
    " 작업이 아니면(README 한 줄, 명세의 링크) 이 알림은 무시한다. 이 알림은 세션·에이전트마다"
    " 한 번이다."
)
_SEPARATORS = re.compile(r"[\\/]+")


class ToolInput(TypedDict, total=False):
    file_path: object


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분. `tool_input` 은 객체가 아닌 값이
    와도 `context_for` 가 런타임에 다시 본다."""

    tool_name: str
    tool_input: ToolInput
    session_id: str
    agent_id: str


def design_slug(path: str) -> str | None:
    """`.scratch/<기능>/design/` 아래 파일이면 그 기능 토막(쓴 그대로), 아니면 None. 접지 않으면
    `..` 를 기능으로 읽었다(agent-os 에서 셀프 리뷰가 Minor 로 남기고 PR 직전 bug-perf-review 가
    다시 냈다)."""
    parts = [part for part in posixpath.normpath(_SEPARATORS.sub("/", path)).split("/") if part]
    folded = [part.casefold() for part in parts]
    # 마지막 토막은 파일이라 design 자리에서 뺀다.
    for index in range(len(parts) - 3):
        if folded[index] == ".scratch" and folded[index + 2] == "design":
            return parts[index + 1]
    return None


def context_for(payload: HookPayload) -> str | None:
    """디자인 폴더 아래 파일을 쓰거나 고쳤으면 컨텍스트 문장, 아니면 None."""
    if payload.get("tool_name") not in TOOLS:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    path = tool_input.get("file_path")
    if not isinstance(path, str):
        return None
    slug = design_slug(path)
    if slug is None:
        return None
    return _BODY.format(lead=LEAD, slug=slug)


def marker_name(session_id: str, agent_id: str) -> str:
    """세션·에이전트 하나의 표지 파일 이름. 둘의 해시다(`tools/launch_hook.py` 의 모양)."""
    joined = f"{session_id}\0{agent_id}"
    return hashlib.sha256(joined.encode("utf-8", "surrogatepass")).hexdigest()


def claim_first(name: str, directory: Path) -> bool:
    """`directory` 에 표지 `name` 을 이 호출이 처음 만들었으면 True, 이미 있으면 False. 만들지
    못하면 True 다. 폴더 자리의 파일은 makedirs 가 FileExistsError 로 알리므로 표지가 이미 있는 것과
    따로 잡는다."""
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        return True
    try:
        os.close(os.open(directory / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    except OSError:
        return True
    return True


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md.
    payload: HookPayload = json.load(sys.stdin.buffer)
    context = context_for(payload)
    if context is None:
        return 0
    session = payload.get("session_id")
    agent = payload.get("agent_id")
    if isinstance(session, str) and session:
        name = marker_name(session, agent if isinstance(agent, str) else "")
        try:
            directory = Path(tempfile.gettempdir()) / STATE_DIR
        except OSError:
            # 쓸 수 있는 임시 폴더가 없다. 표지를 쓰지 못한 것과 같이 알린다.
            directory = None
        if directory is not None and not claim_first(name, directory):
            return 0
    print(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
