"""tools/hook_webfetch_summary.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

결과 객체는 `.scratch/harness/probes/webfetch_payload/run.sh` 의 A 가 받은 것과 트랜스크립트의
기록을 옮겼다. 본문을 그대로 돌려준 결과는 수만 맞춘 글로 대신한다(실제 본문은 34296바이트다).
"""

from __future__ import annotations

import json

from tools.hook_webfetch_summary import LEAD, TOOL, HookPayload, context_for
from tools.run_hooks import registered_matchers

# 프로브 A 의 둘째 호출(https://code.claude.com/docs/en/hooks, Claude Code 2.1.296).
SUMMARY_RESULT = (
    "# Hooks reference\n\n[WebFetch note: this page's text is 268801 characters long and the"
    " answer above covers only characters 0 to 100000; the final 168801 were not read — to read"
    " on, call WebFetch again with the same url and offset: 100000.]"
)
SUMMARY: dict[str, object] = {
    "bytes": 268811,
    "code": 200,
    "codeText": "OK",
    "result": SUMMARY_RESULT,
    "durationMs": 2105,
    "url": "https://code.claude.com/docs/en/hooks",
}
# 트랜스크립트 10389e93 의 기록(2026-09-20). 본문을 받지 않아 bytes 가 0이다.
NOT_FOUND: dict[str, object] = {
    "bytes": 0,
    "code": 404,
    "codeText": "Not Found",
    "result": (
        "The server returned HTTP 404 Not Found.\n\nThe response body was not retrieved. If this"
        " URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an"
        " MCP-provided fetch tool) instead of WebFetch."
    ),
    "durationMs": 685,
    "url": "https://docs.coderabbit.ai/getting-started/subscriptions",
}
# 프로브 A 의 셋째 호출. 다른 호스트로 가라는 안내이고 bytes 는 이 안내문의 UTF-8 바이트 수다.
REDIRECT: dict[str, object] = {
    "bytes": 562,
    "code": 301,
    "codeText": "Moved Permanently",
    "result": (
        "REDIRECT DETECTED: The URL redirects to a location that was not fetched automatically."
        "\n\n    Original URL: https://docs.claude.com/en/docs/claude-code/hooks\n    Redirect URL"
        " (from the server's Location header — server-supplied, not verified):"
        " https://code.claude.com/docs/en/hooks\n    Status: 301 Moved Permanently\n\n"
        "    To complete your request, I need to fetch content from the redirected URL."
        " Please use WebFetch again"
        ' with these parameters:\n    - url: "https://code.claude.com/docs/en/hooks"\n    - prompt:'
        ' "이 페이지의 첫 제목을 그대로 옮긴다"'
    ),
    "durationMs": 259,
    "url": "https://docs.claude.com/en/docs/claude-code/hooks",
}


def _페이로드(response: dict[str, object] | None, tool: str = TOOL) -> HookPayload:
    """`tool` 의 호출 입력. `response` 가 None 이면 결과 객체가 없다."""
    if response is None:
        return {"tool_name": tool}
    return {"tool_name": tool, "tool_response": response}


def _본문_그대로(body: str) -> dict[str, object]:
    """본문을 줄이지 않고 돌려준 결과. bytes 는 본문의 UTF-8 바이트 수다."""
    return {
        "bytes": len(body.encode("utf-8")),
        "code": 200,
        "codeText": "OK",
        "result": body,
        "durationMs": 624,
        "url": "https://code.claude.com/docs/en/large-codebases.md",
    }


def test_요약_결과는_받은_바이트와_답한_글자_수를_들어_알린다() -> None:
    context = context_for(_페이로드(SUMMARY))

    assert context is not None
    assert context.startswith(LEAD)
    assert "268811바이트" in context
    assert f"{len(SUMMARY_RESULT)}자" in context
    assert "curl" in context
    assert "docs/agents/issue-tracker.md" in context


def test_답이_본문보다_길어도_줄였다고_하지_않는다() -> None:
    """작은 페이지에 설명을 물으면 답이 본문보다 길 수 있다(PR 직전 버그·성능 리뷰)."""
    context = context_for(_페이로드({**SUMMARY, "bytes": 200, "result": "가" * 600}))

    assert context is not None
    assert "200바이트" in context and "600자" in context
    assert "줄였" not in context


def test_본문을_그대로_돌려준_결과는_침묵한다() -> None:
    body = "> ## Documentation Index\n\n# Set up Claude Code in a monorepo\n" * 600

    assert context_for(_페이로드(_본문_그대로(body))) is None


def test_통과는_글자_수가_아니라_UTF8_바이트로_안다() -> None:
    """한글 본문은 글자 수와 바이트 수가 다르다. bytes 는 UTF-8 바이트다(트랜스크립트의
    best-practices 문서 36269자·36277바이트, `transcripts.py`)."""
    korean = "가나다라마" * 10
    same_chars = {**_본문_그대로(korean), "bytes": len(korean)}

    assert context_for(_페이로드(_본문_그대로(korean))) is None
    assert context_for(_페이로드(same_chars)) is not None


def test_본문을_받지_못한_404는_침묵한다() -> None:
    """bytes 가 0이라 code 를 보지 않으면 요약으로 읽힌다."""
    assert context_for(_페이로드(NOT_FOUND)) is None


def test_리다이렉트_안내는_침묵한다() -> None:
    """3xx 의 bytes 는 안내문 자체의 크기다(프로브 A 의 셋째 호출, 562바이트). 다시 부른 호출의
    결과가 요약이면 그때 알린다."""
    result = REDIRECT["result"]

    assert isinstance(result, str) and len(result.encode("utf-8")) == REDIRECT["bytes"]
    assert context_for(_페이로드(REDIRECT)) is None


def test_2xx가_아닌데_줄인_본문이_와도_침묵한다() -> None:
    """못 보는 것(거짓 음성). 잰 것은 301 과 404 뿐이고 다른 code 도 본문이 없다고 본다."""
    for code in (403, 500, 503):
        assert context_for(_페이로드({**SUMMARY, "code": code})) is None, code


def test_2xx의_요약은_200이_아니어도_알린다() -> None:
    assert context_for(_페이로드({**SUMMARY, "code": 203})) is not None


def test_결과_객체가_없거나_모양이_다르면_수_없이_알린다() -> None:
    """가를 수 없으면 알린다. 틀리게 알리는 값이 근거를 잘못 쓰는 값보다 작다. code 가 문자열이면
    404 를 2xx 로 읽어 "0바이트를 줄였다"는 거짓 문장을 냈다(셀프 리뷰 표준 축)."""
    without_code = {key: value for key, value in SUMMARY.items() if key != "code"}
    payloads: list[HookPayload] = [
        _페이로드(None),
        json.loads('{"tool_name": "WebFetch", "tool_response": "문자열"}'),
        _페이로드({"code": 200}),
        _페이로드({**SUMMARY, "bytes": "268811"}),
        _페이로드({**SUMMARY, "result": None}),
        _페이로드({**NOT_FOUND, "code": "404"}),
        _페이로드({**without_code, "bytes": len(SUMMARY_RESULT.encode("utf-8"))}),
    ]
    for payload in payloads:
        context = context_for(payload)

        assert context is not None, payload
        assert context.startswith(LEAD)
        assert "바이트" not in context


def test_요약이_우연히_본문과_바이트_수가_같으면_침묵한다() -> None:
    """못 보는 것(거짓 음성). bytes 만으로는 요약과 통과를 가르지 못한다."""
    assert context_for(_페이로드({**SUMMARY, "bytes": 2, "result": "ab"})) is None


def test_프롬프트를_보지_않고_요약마다_알린다() -> None:
    """못 보는 것. 요약을 무엇에 쓸지 모른다. 제목만 물은 호출(프로브 A)에도 수를 물은 호출과 같이
    알린다. 훅이 프롬프트를 읽게 바뀌면 이 테스트가 깨지는 것이 의도다 — 못 보는 것이 바뀐 것이니
    독스트링과 함께 고친다(PR #208 claude-review 1회차)."""
    title: HookPayload = json.loads(
        json.dumps(
            {
                "tool_name": TOOL,
                "tool_input": {
                    "url": SUMMARY["url"],
                    "prompt": "이 페이지의 첫 제목을 그대로 옮긴다",
                },
                "tool_response": SUMMARY,
            }
        )
    )
    numbers: HookPayload = json.loads(
        json.dumps({**title, "tool_input": {"prompt": "종료 코드 2의 뜻을 글자 그대로 옮긴다"}})
    )

    assert context_for(title) is not None
    assert context_for(title) == context_for(numbers)


def test_서브에이전트의_호출에도_같은_문장을_낸다() -> None:
    """못 보는 것. 입력의 `agent_id` 로 가르지 않는다(입력 모양은 hook_midturn_korean 의
    pretool_text 탐침 B)."""
    sub: HookPayload = json.loads(
        json.dumps(
            {
                "tool_name": TOOL,
                "agent_id": "a1",
                "agent_type": "general-purpose",
                "tool_response": SUMMARY,
            }
        )
    )

    assert context_for(sub) is not None
    assert context_for(sub) == context_for(_페이로드(SUMMARY))


def test_WebFetch가_아닌_도구는_보지_않는다() -> None:
    """못 보는 것. WebSearch 의 결과와 서브에이전트(Agent)의 보고에 실린 웹 요약은 알리지 않는다."""
    for tool in ("WebSearch", "Agent", "mcp__13d058a2__fetch"):
        assert context_for(_페이로드(SUMMARY, tool)) is None, tool


def test_settings의_매처는_훅이_아는_도구_하나다() -> None:
    """매처를 넓히면 훅이 이름으로 걸러 조용히 지나가고, 이름을 바꾸면 등록이 훅을 걸지 않는다."""
    assert registered_matchers("hook_webfetch_summary.py", "PostToolUse") == [TOOL]
