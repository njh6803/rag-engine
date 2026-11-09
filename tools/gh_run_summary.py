"""GitHub Actions 실행 로그 요약. 초록 체크가 실제로 무엇을 했는지 한 번에 본다.

`gh run view <run-id> --log`의 출력에서 판정에 필요한 것만 뽑는다. 줄마다 붙은
`<잡>\\t<단계>\\t<시각> ` 접두를 떼면 로그는 둘로 갈린다.

- Claude 단계의 stream-json 이벤트. 들여 쓴 JSON 객체라, 접두를 뗀 줄이 `{`인 데서 `}`인
  데까지를 객체 하나로 읽는다. 여기서 넷을 뽑는다.
  - 결과 블록(`type: result`)의 `RESULT_KEYS`와 거부. 거부는 `permission_denials` 배열의 길이와
    항목의 `tool_name`이다. 키가 없으면 0건이 아니라 없다고 적는다. 블록이 여럿이면 둘 다 모은다.
  - 훅 응답(`subtype: hook_response`) 중 `outcome`이 `success`가 아닌 것.
  - 알림(`subtype: notification`). 아래 실행들에서 Stop 훅의 오류는 훅 응답 없이 이것으로만
    남았다.
  - Claude의 말. assistant 메시지의 text 블록이고, 워크플로에 `show_full_output: true`가 켜져
    있을 때만 있다.
- 그 밖의 줄(러너와 액션의 출력)에서 `SIGNAL_PATTERNS`. 러너는 `::error::`·`::warning::`을
  `##[error]`·`##[warning]`으로 바꿔 찍는다.

이 모양은 실행 38181949361(PR #176, Claude Code 2.1.292), 38180949060(PR #174), 38120400317(PR
#172)의 로그를 읽어 맞췄다. 세 로그의 JSON 객체는 모두 읽혔다(28/28, 44/44, 6/6, 손으로 받은
로그를 손으로 셌다). 거부 항목의 모양은 로컬 `claude -p --allowedTools Read --permission-mode
default`(2.1.296)로 Write를 거부시켜 손으로 봤다.

못 보는 것.
- JSON 객체 안의 줄은 신호로 보지 않는다. Claude가 Read로 읽은 파일 원문(워크플로의 `::error`
  줄)이 신호로 쏟아지던 것을 막는 대신, 다른 단계가 찍은 JSON 안의 경고도 보지 않는다.
- 러너가 다시 보여 주는 스크립트 원문(`[36;1m` 머리)도 신호로 보지 않는다.
- 결과 블록의 옛 모양(`permission_denials_count`, `"subtype": "permission_denied"` 이벤트).
  2.1.292의 로그에 없어 뺐다.
- 줄이 잘려 닫히지 않은 객체. 실행 38182830347·38189417612 의 로그에서 도구 결과를 든 줄이 닫는
  따옴표 없이 끊겼다(PR 직전 버그 리뷰가 손으로 봤다, 원인은 모른다). 그 객체는 읽지 못한 것으로
  세고, 맨 앞의 `{` 가 오면 거기서 새 객체를 연다. 잘린 객체에 든 것(훅, 알림, 결과)은 잃는다.

쓰임: `uv run python tools/gh_run_summary.py 35505690924`. 리뷰 파이프라인의 "코멘트 없는 초록"이
리뷰를 했는지 안 했는지는 이 요약으로 판정한다(`docs/constitution/operations.md`).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None

RESULT_KEYS = ("num_turns", "total_cost_usd", "is_error", "terminal_reason")
SIGNAL_PATTERNS = (
    re.compile(r"^##\[(warning|error)\]"),
    re.compile(r"Skipping|Trigger result|workflow validation", re.IGNORECASE),
    re.compile(r"buffered inline comments|posted comment|create_comment", re.IGNORECASE),
)
SCRIPT_ECHO = re.compile(r"^(\x1b|\^\[)\[36;1m")  # 러너가 다시 보여 주는 `run:` 원문
PREFIX = re.compile(r"^[^\t]*\t[^\t]*\t\S*\s?")  # "<job>\t<step>\t<timestamp> " 접두
TEXT_LIMIT = 12
TEXT_WIDTH = 200
# 로그 받기를 기다리는 초. 로그는 실행 전체라 git 호출보다 넉넉히 둔다(대기열 342).
CALL_TIMEOUT = 120


@dataclass
class Summary:
    """`denials` 는 거부된 호출의 도구 이름이다. None 이면 결과 블록에 그 키가 없었다."""

    results: list[str] = field(default_factory=list[str])
    denials: list[str] | None = None
    hooks: list[str] = field(default_factory=list[str])
    notices: list[str] = field(default_factory=list[str])
    signals: list[str] = field(default_factory=list[str])
    texts: list[str] = field(default_factory=list[str])
    broken: int = 0


def strip_prefix(line: str) -> str:
    return PREFIX.sub("", line, count=1).rstrip()


def _blocks(lines: list[str]) -> Iterator[str | dict[str, Json] | None]:
    """JSON 객체는 dict, 그 밖의 줄은 문자열, 읽지 못했거나 닫히지 않은 객체는 None 으로 낸다."""
    buffer: list[str] | None = None
    for raw in lines:
        line = strip_prefix(raw)
        if buffer is not None and line == "{":
            # 들여 쓴 객체 안에서는 맨 앞의 `{` 가 나오지 않는다. 앞 객체의 줄이 잘려 닫히지 않았다
            yield None
            buffer = None
        if buffer is None:
            if line == "{":
                buffer = [line]
            else:
                yield line
            continue
        buffer.append(line)
        if line != "}":
            continue
        try:
            parsed: Json = json.loads("\n".join(buffer))
        except ValueError:
            parsed = None
        buffer = None
        yield parsed if isinstance(parsed, dict) else None
    if buffer is not None:
        yield None


def _one_line(text: str) -> str:
    return " ".join(text.split())[:TEXT_WIDTH]


def _result_lines(event: dict[str, Json]) -> list[str]:
    return [
        f'"{key}": {json.dumps(event[key], ensure_ascii=False)}'
        for key in RESULT_KEYS
        if key in event
    ]


def _denied_tools(event: dict[str, Json]) -> list[str] | None:
    """거부된 호출의 도구 이름. 결과 블록에 `permission_denials` 가 없으면 None."""
    denials = event.get("permission_denials")
    if not isinstance(denials, list):
        return None
    return [str(item.get("tool_name")) if isinstance(item, dict) else "?" for item in denials]


def _hook_error(event: dict[str, Json]) -> str | None:
    """훅 응답이 성공이 아니면 한 줄. 성공이면 None."""
    outcome = event.get("outcome")
    if outcome == "success":
        return None
    stderr = event.get("stderr")
    first = stderr.strip().splitlines()[0] if isinstance(stderr, str) and stderr.strip() else ""
    return f"훅 {event.get('hook_name')} 이 {outcome}(종료 {event.get('exit_code')}): {first}"


def _texts(event: dict[str, Json]) -> list[str]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [
        _one_line(text)
        for part in content
        if isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(text := part.get("text"), str)
    ]


def summarize(lines: list[str]) -> Summary:
    summary = Summary()
    for block in _blocks(lines):
        if block is None:
            summary.broken += 1
        elif isinstance(block, str):
            if not SCRIPT_ECHO.match(block) and any(p.search(block) for p in SIGNAL_PATTERNS):
                summary.signals.append(block.strip())
        elif block.get("type") == "result":
            summary.results.extend(_result_lines(block))
            denied = _denied_tools(block)
            if denied is not None:
                # 턴수·비용처럼 블록마다 모은다. 키 없는 블록이 앞 블록의 거부를 덮지 않는다
                summary.denials = [*(summary.denials or []), *denied]
        elif block.get("type") == "system" and block.get("subtype") == "hook_response":
            hook = _hook_error(block)
            if hook is not None:
                summary.hooks.append(hook)
        elif block.get("type") == "system" and block.get("subtype") == "notification":
            summary.notices.append(f"알림 {block.get('key')}: {block.get('text')}")
        elif block.get("type") == "assistant":
            summary.texts.extend(_texts(block))
    return summary


def _render_denials(denials: list[str] | None) -> str:
    if denials is None:
        return "거부: 결과 블록에 permission_denials 가 없다"
    if not denials:
        return "거부 0건"
    tools = ", ".join(f"{name} {count}" for name, count in Counter(denials).items())
    return f"거부 {len(denials)}건 (허용 도구 밖의 호출: {tools})"


def render(summary: Summary) -> str:
    out: list[str] = []
    out.append("## 결과")
    if summary.results or summary.denials is not None:
        out.extend(summary.results)
        out.append(_render_denials(summary.denials))
    else:
        out.append("(결과 블록 없음. 실행이 Claude 단계 전에 끝났다)")
    if summary.broken:
        out.append(f"JSON 으로 읽지 못한 객체 {summary.broken}개")
    out.append("## 훅·알림")
    out.extend([*summary.hooks, *summary.notices] or ["(없음)"])
    out.append("## 경고·건너뜀·코멘트 흔적")
    out.extend(summary.signals or ["(없음)"])
    out.append(f"## Claude의 말 (처음 {TEXT_LIMIT}개)")
    if summary.texts:
        out.extend(summary.texts[:TEXT_LIMIT])
        if len(summary.texts) > TEXT_LIMIT:
            out.append(f"... 외 {len(summary.texts) - TEXT_LIMIT}개")
    else:
        out.append("(없음. show_full_output이 꺼져 있거나 Claude 단계가 돌지 않았다)")
    return "\n".join(out)


def split_log(text: str) -> list[str]:
    """개행에서만 나눈다. `splitlines` 는 JSON 이 이스케이프하지 않는 U+2028 에서도 나눠 객체를
    깬다. 줄 끝의 `\\r` 은 `strip_prefix` 가 걷는다."""
    return text.split("\n")


def fetch_log(run_id: str) -> list[str]:
    """`gh`가 실패하면 CalledProcessError를, `CALL_TIMEOUT`초 안에 돌아오지 않으면 TimeoutExpired를
    올린다."""
    completed = subprocess.run(
        ["gh", "run", "view", run_id, "--log"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=CALL_TIMEOUT,
    )
    return split_log(completed.stdout)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].isdigit():
        sys.stderr.write("쓰임: uv run python tools/gh_run_summary.py <run-id>\n")
        return 2
    try:
        lines = fetch_log(argv[1])
    except subprocess.CalledProcessError as error:
        sys.stderr.write(str(error.stderr))
        return error.returncode
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"gh run view 가 {CALL_TIMEOUT}초 안에 돌아오지 않았다\n")
        return 1
    print(render(summarize(lines)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
