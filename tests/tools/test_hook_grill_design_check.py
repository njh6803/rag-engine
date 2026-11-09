"""tools/hook_grill_design_check.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

입력 모양은 `claude -p` stream-json 에서 본 Skill 호출(`{"skill": ..., "args": ...}`)을 옮겼다.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.hook_grill_design_check import LEAD, SKILL, TOOL, HookPayload, context_for
from tools.run_hooks import registered_matchers


def _호출(skill: object, tool: str = TOOL) -> HookPayload:
    return json.loads(json.dumps({"tool_name": tool, "tool_input": {"skill": skill, "args": "x"}}))


def test_grill_with_docs_호출이면_설계_인터뷰인지_확인하라고_알린다() -> None:
    context = context_for(_호출(SKILL))

    assert context is not None
    assert context.startswith(LEAD)
    assert "grilling" in context and "domain-modeling" in context
    assert ".scratch/<slug>/" in context


def test_알림이_드는_용어집은_이_저장소의_용어집이다() -> None:
    """rag-engine 의 용어집은 루트 `GLOSSARY.md` 다(`docs/agents/domain.md`. 그 파일은 용어가
    확정될 때 생긴다). agent-os 의 `CONTEXT.md` 를 들면 모델이 쓰지 않을 파일을 찾는다."""
    context = context_for(_호출(SKILL))
    domain = (Path(__file__).parents[2] / "docs" / "agents" / "domain.md").read_text(
        encoding="utf-8"
    )

    assert context is not None
    assert "GLOSSARY.md" in context
    assert "CONTEXT.md" not in context
    assert "`GLOSSARY.md`" in domain


def test_설계_단계의_조건은_명세도_설계_줄도_없는_기능이다() -> None:
    """계기 문장 넷(ADR 0045 결정 4)이 같은 조건 하나를 말한다. 폴더의 유무가 아니다."""
    context = context_for(_호출(SKILL))

    assert context is not None
    assert "spec.md" in context
    assert "**설계:**" in context
    assert "기능 계획" in context
    assert "가 없는 설계 단계" not in context


def test_앞의_슬래시는_벗겨_비교한다() -> None:
    assert context_for(_호출("/grill-with-docs")) is not None


def test_다른_스킬은_침묵한다() -> None:
    """grill-with-docs 가 부르는 grilling 과 domain-modeling 도 이 훅에서는 지나간다. 알림이
    라우터의 호출 하나에만 붙어야 한 번에 한 번만 모델에게 닿는다."""
    for skill in ("grilling", "domain-modeling", "code-review", "grill-with-docs-extra", ""):
        assert context_for(_호출(skill)) is None, skill


def test_워크트리_세션이_부르는_경로_접두_이름도_알린다() -> None:
    """대기열 284. 워크트리 세션은 이 저장소의 스킬을 `.claude/worktrees/<이름>:<스킬>` 로 부른다
    (트랜스크립트의 Skill 입력에서 `code-review`·`next-session` 을 그 꼴로 부른 것을 봤다). 인계 훅
    명세(`.scratch/token-usage/spec.md`)가 `code-review` 를 가르는 판정과 같다."""
    assert context_for(_호출(".claude/worktrees/existing-hook-fixes:grill-with-docs")) is not None


def test_다른_자리의_같은_이름은_지나간다() -> None:
    """플러그인 이름(`플러그인:이름`)과 `.claude` 로 시작하지 않는 경로 접두(다른 폴더의 스킬)는 이
    저장소의 grill-with-docs 가 아니다. 접두가 맞아도 이름이 다르면 지나간다."""
    assert context_for(_호출("some-plugin:grill-with-docs")) is None
    assert context_for(_호출("web:grill-with-docs")) is None
    assert context_for(_호출(".claude/worktrees/x:grilling")) is None


def test_경로_접두는_claude_폴더_자체이거나_그_아래다() -> None:
    """`.claude` 로 시작하는 다른 이름(`.claudeX`, `.claude-plugin`)은 그 폴더가 아니다(PR 직전 버그
    축). 윈도 구분자도 받는다."""
    assert context_for(_호출(".claude:grill-with-docs")) is not None
    assert context_for(_호출(".claude\\worktrees\\x:grill-with-docs")) is not None
    assert context_for(_호출(".claudeX:grill-with-docs")) is None
    assert context_for(_호출(".claude-plugin:grill-with-docs")) is None


def test_Skill이_아닌_도구는_보지_않는다() -> None:
    assert context_for(_호출(SKILL, tool="Read")) is None


def test_입력_모양이_다르면_침묵한다() -> None:
    """가를 수 없으면 알리지 않는다. 이 알림은 확인을 부탁하는 것이지 안전장치가 아니다. 잘못
    알려도 모델이 하던 일을 멈출 값이 더 크다."""
    payloads: list[HookPayload] = [
        {"tool_name": TOOL},
        json.loads('{"tool_name": "Skill", "tool_input": "grill-with-docs"}'),
        json.loads('{"tool_name": "Skill", "tool_input": {"skill": 1}}'),
        json.loads('{"tool_name": "Skill", "tool_input": {"args": "x"}}'),
    ]
    for payload in payloads:
        assert context_for(payload) is None, payload


def test_대화를_보지_않고_args와_상관없이_같은_문장을_낸다() -> None:
    """못 보는 것. 훅은 대화와 args 가 가리키는 기능의 상태를 읽지 않는다. 읽게 바뀌면 이 테스트가
    깨지는 것이 의도다. 못 보는 것이 바뀐 것이니 독스트링과 함께 고친다."""
    with_args = json.loads(
        json.dumps({"tool_name": TOOL, "tool_input": {"skill": SKILL, "args": "admin-foo"}})
    )
    without_args = json.loads(json.dumps({"tool_name": TOOL, "tool_input": {"skill": SKILL}}))

    assert context_for(with_args) is not None
    assert context_for(with_args) == context_for(without_args)


def test_서브에이전트의_호출에도_같은_문장을_낸다() -> None:
    """못 보는 것. 입력의 `agent_id` 로 가르지 않는다."""
    sub = json.loads(
        json.dumps(
            {
                "tool_name": TOOL,
                "agent_id": "a1",
                "agent_type": "general-purpose",
                "tool_input": {"skill": SKILL},
            }
        )
    )

    assert context_for(sub) is not None
    assert context_for(sub) == context_for(_호출(SKILL))


def test_settings의_매처는_훅이_아는_도구_하나다() -> None:
    """매처를 넓히면 훅이 이름으로 걸러 조용히 지나가고, 이름을 바꾸면 등록이 훅을 걸지 않는다."""
    assert registered_matchers("hook_grill_design_check.py", "PreToolUse") == [TOOL]
