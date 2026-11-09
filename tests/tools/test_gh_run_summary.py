"""tools/gh_run_summary.py의 순수 함수 검증. 셸을 부르는 fetch_log는 실제 실행으로 확인한다.

로그 조각은 실제 로그(실행 38181949361, 38120400317)의 모양을 따른다. Claude 단계의 이벤트는
들여 쓴 JSON 객체가 줄마다 `<잡>\\t<단계>\\t<시각> ` 접두를 달고 찍힌다.
"""

from __future__ import annotations

import json
import subprocess

import pytest
from tools.gh_run_summary import (
    CALL_TIMEOUT,
    TEXT_WIDTH,
    Json,
    main,
    render,
    split_log,
    summarize,
)

PREFIX = "claude-review\tRun Claude Code Review\t2026-09-20T10:45:00.0000000Z "


def log(*lines: str) -> list[str]:
    return [PREFIX + line for line in lines]


def event(payload: dict[str, Json]) -> list[str]:
    """이벤트 하나를 실제 로그처럼 들여 쓴 JSON 줄로 찍는다."""
    return log(*json.dumps(payload, ensure_ascii=False, indent=2).split("\n"))


def result(**fields: Json) -> list[str]:
    return event({"type": "result", "subtype": "success", "is_error": False, **fields})


def test_결과_블록의_턴수와_비용과_거부_0건을_남기고_스트림_잡음은_버린다() -> None:
    lines = [
        *event({"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 12}),
        *result(
            num_turns=4, total_cost_usd=0.18, terminal_reason="completed", permission_denials=[]
        ),
    ]
    summary = summarize(lines)
    assert summary.results == [
        '"num_turns": 4',
        '"total_cost_usd": 0.18',
        '"is_error": false',
        '"terminal_reason": "completed"',
    ]
    assert summary.denials == []
    assert "거부 0건" in render(summary)


def test_거부는_결과_블록의_배열에서_도구별로_센다() -> None:
    denials: list[Json] = [
        {"tool_name": "Bash", "tool_use_id": "toolu_1", "tool_input": {"command": "ls"}},
        {"tool_name": "WebFetch", "tool_use_id": "toolu_2", "tool_input": {}},
        {"tool_name": "Bash", "tool_use_id": "toolu_3", "tool_input": {"command": "pwd"}},
    ]
    summary = summarize(result(num_turns=2, permission_denials=denials))
    assert summary.denials == ["Bash", "WebFetch", "Bash"]
    assert "거부 3건 (허용 도구 밖의 호출: Bash 2, WebFetch 1)" in render(summary)


def test_결과_블록이_여럿이면_거부를_모으고_키_없는_블록이_덮지_않는다() -> None:
    """PR #182 claude-review: 턴수·비용은 블록마다 쌓이는데 거부는 마지막 블록이 덮어 썼다."""
    denials: list[Json] = [{"tool_name": "Bash", "tool_use_id": "toolu_1", "tool_input": {}}]
    summary = summarize([*result(num_turns=1, permission_denials=denials), *result(num_turns=2)])
    assert summary.denials == ["Bash"]
    assert "거부 1건" in render(summary)


def test_결과_블록에_거부_키가_없으면_0건과_가른다() -> None:
    summary = summarize(result(num_turns=1))
    assert summary.denials is None
    text = render(summary)
    assert "거부 0건" not in text
    assert "permission_denials 가 없다" in text


def test_훅_응답의_오류는_이름과_종료_코드와_stderr_첫_줄로_찍고_성공은_찍지_않는다() -> None:
    failed: dict[str, Json] = {
        "type": "system",
        "subtype": "hook_response",
        "hook_name": "SessionStart:startup",
        "hook_event": "SessionStart",
        "output": "/bin/sh: 1: uv: not found\n",
        "stdout": "",
        "stderr": "/bin/sh: 1: uv: not found\nsecond line\n",
        "exit_code": 127,
        "outcome": "error",
    }
    passed: dict[str, Json] = {**failed, "hook_name": "Stop", "exit_code": 0, "outcome": "success"}
    summary = summarize([*event(failed), *event(passed)])
    assert summary.hooks == [
        "훅 SessionStart:startup 이 error(종료 127): /bin/sh: 1: uv: not found"
    ]
    assert "훅 SessionStart:startup" in render(summary)


def test_알림은_클로드의_말이_아니라_훅_알림_절에_찍힌다() -> None:
    notice: dict[str, Json] = {
        "type": "system",
        "subtype": "notification",
        "key": "stop-hook-error",
        "text": "Stop hook error occurred · ctrl+o to see",
        "priority": "immediate",
    }
    summary = summarize(event(notice))
    assert summary.notices == ["알림 stop-hook-error: Stop hook error occurred · ctrl+o to see"]
    assert summary.texts == []


def test_도구_결과에_실린_원문은_신호가_아니고_러너의_오류_줄은_신호다() -> None:
    """Claude 가 Read 로 읽은 워크플로 원문에 `::error`·`##[error]`·`Skipping` 이 들어 있었다."""
    workflow = 'echo "::error::코멘트가 없다"\n##[error]Skipping 은 원문이다'
    tool_result: dict[str, Json] = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": workflow}],
        },
    }
    lines = [
        *event(tool_result),
        *log("##[error]Claude result reported subtype success with is_error:true"),
    ]
    summary = summarize(lines)
    assert summary.signals == ["##[error]Claude result reported subtype success with is_error:true"]


def test_러너가_다시_보여_주는_스크립트_원문은_신호가_아니다() -> None:
    lines = log(
        '^[[36;1m  echo "::error::Claude Code Review가 코멘트를 남기지 않았다."^[[0m',
        '\x1b[36;1m  echo "##[warning]Skipping"\x1b[0m',
    )
    assert summarize(lines).signals == []


def test_워크플로_검증_건너뜀은_신호로_잡히고_결과_블록_없음을_알린다() -> None:
    summary = summarize(
        log("##[warning]Skipping action due to workflow validation: Workflow validation failed.")
    )
    assert len(summary.signals) == 1
    assert "workflow validation" in summary.signals[0]
    assert "결과 블록 없음" in render(summary)


def test_클로드의_말은_텍스트_블록을_한_줄로_접고_폭을_자른다() -> None:
    long_text = "가" * (TEXT_WIDTH + 50)
    assistant: dict[str, Json] = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "첫 줄\n\n둘째 줄"},
                {"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {}},
                {"type": "text", "text": long_text},
            ],
        },
    }
    summary = summarize(event(assistant))
    assert summary.texts == ["첫 줄 둘째 줄", "가" * TEXT_WIDTH]


def test_JSON_으로_읽지_못한_객체와_닫히지_않은_객체를_센다() -> None:
    lines = log("{", '  "type": "result",', '  "num_turns": ,', "}", "{", '  "type": "system",')
    summary = summarize(lines)
    assert summary.broken == 2
    assert "JSON 으로 읽지 못한 객체 2개" in render(summary)


def test_잘린_객체는_뒤의_객체를_삼키지_않는다() -> None:
    """실행 38182830347 의 로그에서 도구 결과 줄이 닫는 따옴표 없이 끊기고 다음 줄이 `{` 였다."""
    lines = [
        *log("{", '  "type": "user",', '  "content": "끊긴 원문'),
        *result(num_turns=3, permission_denials=[]),
    ]
    summary = summarize(lines)
    assert summary.broken == 1
    assert summary.results[0] == '"num_turns": 3'


def test_로그는_개행에서만_줄을_나눈다() -> None:
    """JSON 은 U+2028 을 이스케이프하지 않는다. 그 글자에서 줄을 나누면 객체가 깨진다."""
    separator = chr(0x2028)
    assistant: dict[str, Json] = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": f"a{separator}b"}]},
    }
    summary = summarize(split_log("\n".join(event(assistant))))
    assert summary.broken == 0
    assert summary.texts == ["a b"]


def test_인자가_없으면_쓰임을_알리고_2를_돌려준다(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["gh_run_summary.py"]) == 2
    assert main(["gh_run_summary.py", "abc"]) == 2
    assert "쓰임" in capsys.readouterr().err


def test_gh_가_시간을_넘기면_알리고_1을_돌려준다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[object] = []

    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, CALL_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", stuck)

    assert main(["gh_run_summary.py", "123"]) == 1
    assert f"{CALL_TIMEOUT}초 안에 돌아오지 않았다" in capsys.readouterr().err
    assert seen == [CALL_TIMEOUT]
