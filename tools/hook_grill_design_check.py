"""PreToolUse 훅(Skill). 모델이 `grill-with-docs`를 부르려 하면, 지금 하는 일이 실제 설계 인터뷰인지
확인하라는 계기를 컨텍스트에 넣는다.

`grill-with-docs`는 모델이 Skill 도구로 부를 수 있는 스킬이 됐다(PR #247). 그러면 `grilling`과
`domain-modeling`이 차례로 돌아 `GLOSSARY.md` 용어와 ADR 초안을 쓰는데, 설명(description)이 가르는
것은 모델의 판단뿐이다. 설계가 아닌 압박 질문("이 PR 설명을 grill해줘")에 불려도 용어·ADR 기록이
따라붙는다(`grill`이 `grilling`의 트리거와 겹친다). 이 훅이 부르기 직전에 한 번 더 묻는다.
사람이 슬래시 명령(`/grill-with-docs`)으로 시작한 인터뷰는 Skill 도구 호출이 아니라서 이 훅에 오지
않는다고 본다(어림이고 재지 않았다). 사람이 직접 요청한 것이므로 와도 맞다.

막지 않고 알린다. 훅은 대화를 읽지 못해 설계 인터뷰인지 가를 수 없고, 가르는 것은 모델이다. 막으면
사람이 요청한 인터뷰까지 막힌다. 계기만 주는 PreToolUse 훅은 호출을 그대로
돌린다(`.claude/rules/tools.md`). 스킬 본문은 호출이 돌아온 뒤에 실리고, 모델은 이 문장을 보고 그
본문을 따를지 정한다.

가르는 것은 입력의 `tool_input.skill` 하나다(Claude Code 2.1.296의 `claude -p` stream-json에서 본
모양: `{"skill": "grill-with-docs", "args": "…"}`, 2026-10-15 손으로 봤다). 앞의 `/`는 벗겨
비교한다. 이름이 그대로 `grill-with-docs`이거나, `.claude`로 시작하는 경로 접두에
`:grill-with-docs`가 붙은 것이다. 워크트리 세션은 이 저장소의 스킬을 뒤의 꼴
(`.claude/worktrees/<이름>:grill-with-docs`)로도 부른다. 첫 판은 앞의 꼴만 봐 뒤의 꼴을
놓친다(대기열 284). `grill-with-docs`를 뒤의 꼴로 부른 사건은 아직 없다. 그 꼴이 흔하다는 근거는
다른 스킬의 수다. 인계 훅 명세(`.scratch/token-usage/spec.md`의 "인계 훅", 2026-10-16)가 그날까지
7일의 메인 세션에서 `code-review`를 뒤의 꼴로 부른 것을 21회로 셌고(스크래치 스크립트로 손으로
셌다), 이 판정은 그 명세가 `code-review`를 가르는 판정과 같다.
`tools/hook_worktree_skill_overrides.py`가 돈 CLI 세션에서는 그 꼴이 꺼져 목록에 없고 부를 수도
없었지만(대기열 274), 이 PC의 데스크톱 앱 세션에서는 그 훅이 돈 뒤에도 그 꼴이 목록에 붙었다(그 훅의
못 보는 것). 판정은 그 꼴이 남는 세션(앱 세션, 그 훅보다 먼저 들어간 세션, 들어간 뒤에 새로 생긴
스킬)을 위해 둔다. 명세의 "`.claude`로 시작하는 경로"는 경로의 첫 토막으로 읽는다. 접두가 `.claude`
자체이거나 `.claude/`· `.claude\\`로 시작해야 하고, `.claudeX`·`.claude-plugin`은 그 폴더가
아니다(PR 직전 버그 축). 플러그인 이름이 붙은 호출(`플러그인:grill-with-docs`)과 `.claude` 밖의 경로
접두(다른 폴더의 스킬)는 이 저장소의 grill-with-docs가 아니라 지나간다.

못 보는 것:
- 대화의 내용. 설계 인터뷰가 맞는지는 모델이 가르고, 훅은 호출마다 같은 문장을 낸다(`args`가
  있어도).
- `args`가 가리키는 기능의 상태(명세 `.scratch/<slug>/spec.md`나 기능 계획의 `**설계:**` 줄이 이미
  있는지). 이미 설계가 끝난 기능에 불려도 알림은 같다. 계기 문장은 `docs/agents/issue-tracker.md`
  전체 계획 절의 설계 줄 항목, `grill-with-docs`의 설명, `next-session` 결정표와 같은 하나의
  조건(명세도 설계 줄도 없으면 설계 인터뷰, 설계 줄이 있고 명세가 없으면 명세)을 따른다(agent-os ADR
  0045 결정 4에서 옮겼다).
- 서브에이전트가 부른 호출. 입력의 `agent_id`로 가르지 않고 같은 문장을 낸다.
- 이 문장이 모델에게 닿는지는 등록 모양의 `claude -p` 세션에서 모델이 첫 문장을 옮기게 해서
  본다(스트림에는 additionalContext가 실리지 않는다, `hook_webfetch_summary`의 독스트링).
"""

from __future__ import annotations

import json
import sys
from typing import TypedDict

TOOL = "Skill"
SKILL = "grill-with-docs"
# 워크트리 세션이 이 저장소의 스킬 앞에 붙이는 경로 접두의 머리(`.claude/worktrees/<이름>:`).
# `.claude` 폴더 자체이거나 그 아래만 받는다. `.claudeX` 는 그 폴더가 아니다.
PATH_PREFIX = ".claude"
_PATH_PREFIXES = (f"{PATH_PREFIX}/", f"{PATH_PREFIX}\\")
# 알림의 첫 문장. 세션 확인이 모델이 이 문장을 옮겼는지 본다.
LEAD = "grill-with-docs를 부르기 전에 설계 인터뷰가 맞는지 확인한다"
_BODY = (
    "{lead}. 이 스킬은 grilling과 domain-modeling을 차례로 불러 GLOSSARY.md 용어와 ADR 초안을 쓴다."
    " 사용자가 이번 요청에서 설계 인터뷰를 청했거나(grill, 인터뷰 진행),"
    " 기능에 명세(`.scratch/<slug>/spec.md`)도 기능 계획의 `**설계:**` 줄도 없는 설계 단계라면"
    " 그대로 진행한다."
    " 구현, 리뷰, 사실 확인, 일반 질문이면 이 스킬이 돌려주는 지시(두 스킬 호출)를 따르지 않고"
    " 하던 일을 이어 간다."
)


class ToolInput(TypedDict, total=False):
    skill: object
    args: object


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분. `tool_input` 은 객체가 아닌 값이
    와도 `context_for` 가 런타임에 다시 본다."""

    tool_name: str
    tool_input: ToolInput


def context_for(payload: HookPayload) -> str | None:
    """`grill-with-docs` 호출이면 컨텍스트 문장, 아니면 None."""
    if payload.get("tool_name") != TOOL:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    skill = tool_input.get("skill")
    if not isinstance(skill, str) or not is_this_skill(skill.lstrip("/")):
        return None
    return _BODY.format(lead=LEAD)


def is_this_skill(name: str) -> bool:
    """이 저장소의 `grill-with-docs` 인가. 그대로의 이름이거나, `.claude` 폴더 자체나 그 아래를
    가리키는 경로 접두에 `:grill-with-docs` 가 붙은 것이다."""
    prefix, colon, skill = name.rpartition(":")
    in_folder = prefix == PATH_PREFIX or prefix.startswith(_PATH_PREFIXES)
    return skill == SKILL and (not colon or in_folder)


def main() -> int:
    payload: HookPayload = json.load(sys.stdin.buffer)
    context = context_for(payload)
    if context is None:
        return 0
    print(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context}}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
