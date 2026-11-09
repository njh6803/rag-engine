"""PreToolUse 훅(모든 도구). 도구 호출 앞의 중간 문장이 한국어가 아니면 알린다. 막지 않는다.

Stop 훅(`hook_stop_korean`, 대기열 83)은 턴 끝의 마지막 텍스트만 받아 도구 호출 사이의 문장을 보지
못한다. 일지 2026-10-01-08·09 와 2026-10-02-01·02·03 의 다섯 세션이 그 자리에 영어를 썼고(02-03 은
텍스트 블록 예순일곱 중 일곱, 그중 다섯이 "Now" 로 시작하는 한 줄), 지침으로 적은 뒤에도 어겨져
계기 훅이다(대기열 94). 이미 보낸 문장은 되돌릴 수 없으니 막지 않고 `additionalContext` 로 다음
문장부터 한국어로 쓰게 한다.

입력에는 텍스트가 없어 트랜스크립트를 읽는다(`.scratch/harness/probes/pretool_text/`,
claude 2.1.286, 2026-10-02 에 두 번). 기록은 내용 블록 하나에 한 줄이고 `timestamp` 는 블록마다
다르지만, 파일에는 메시지가 끝날 때 함께 쓰였다. 단일 호출은 자기 블록이 메시지의 끝이라
PreToolUse 에서 앞의 텍스트와 자기 `tool_use` 가 이미 있었다(여덟 번). 한 메시지의 병렬 호출은
앞쪽 호출의 PreToolUse 에서 둘 다 아직 없었다 — Bash 둘의 첫 호출은 60~160ms, Read 셋의 첫
호출은 1020~1040ms, 둘째는 460ms 뒤에 나타났다. 데스크톱 세션(4d667e76)에서는 tool_use 가 둘
이상인 메시지 40개 중 2개가 첫 결과를 쓸 때 그 앞의 블록이 함께 쓰여 `tool_use` 와 결과가 번갈아
기록됐다(같은 탐침의 `interleave.py`). 그래서 입력의 `tool_use_id` 로 자기 기록을 찾고, 같은
메시지에서 앞선 `tool_use` 뒤(없으면 메시지 처음)부터 자기까지의 텍스트 블록을 판정한다. 병렬
호출의 둘째부터는 앞이 형제라 판정하지 않아, 상태 파일 없이 문장 하나에 한 번 알린다. 자기 기록이
없으면 `POLL_SECONDS` 마다 다시 읽되 `WAIT_SECONDS` 를 넘기지 않는다. 그 사이 첫 호출의 도구는
메시지가 끝날 때까지 늦게 시작한다. 트랜스크립트 파일이 없으면 기다리지 않는다. 끝의
`TAIL_BYTES` 만 읽는다 — 이 저장소의 가장 큰 트랜스크립트(31MB)에서 훅 한 번이 234~243ms 로,
트랜스크립트를 읽지 않는 길(217~233ms)보다 약 15ms 더 들었다(같은 탐침의 `time_hook.sh`, 래퍼
포함, 세 번 쟀다). 기록이 끝내 없으면 2.2~2.3초다.

판정은 Stop 훅과 같다 — 코드 펜스, `>` 인용 줄, 코드 스팬, 링크 대상, URL, 구분자가 든 식별자를 뺀
산문에서 한글과 라틴 문자를 합쳐 `MIN_LETTERS` 이상이고 그중 한글이 `MIN_HANGUL_RATIO` 보다
적으면 알린다. 훅은 서로 import 하지 않아(.claude/rules/tools.md) 정규식을 옮겨 왔다. 문턱은 이
저장소의 트랜스크립트에서 이 훅이 고를 중간 문장 4311개로 쟀다(`.scratch/harness/probes/
midturn_korean_ratio.py`, 2026-10-02). 알리는 것은 521개이고 가장 높은 비율이 0.172 이며, 한국어
문장의 가장 낮은 비율은 0.333(식별자가 많은 병합 보고)이다. 그 사이(0.22~0.32)의 여섯은 한국어
낱말을 인용한 영어 문장이고 알리지 않는다. 문턱을 올리면 한국어 쪽과의 거리가 좁아져 Stop 훅과 같은
0.2 에 둔다. 서브에이전트의 호출(입력에 `agent_id` 가 온다)과 SDK 세션은 보지 않는다 — 앞의 것은
사용자에게 보이지 않고 그 기록이 주 트랜스크립트에 없었으며, 뒤의 것은 프로그램이 읽는다.

못 보는 것: 텍스트만 있고 도구 호출이 없는 메시지(턴 끝이면 Stop 훅이 본다). 상한 안에 자기 기록이
쓰이지 않은 호출(병렬 호출의 뒤 블록이 오래 이어질 때 — 놓칠 뿐 겹쳐 알리지는 않는다). 끝의
`TAIL_BYTES` 밖으로 밀려난 기록. 트랜스크립트에 `text` 가 아닌 블록으로 남은 문장(2026-10-02 세션
4d667e76 에서 사용자에게 보인 중간 문장 하나가 `thinking` 블록으로 기록된 것을 손으로 봤다).
사이드체인으로 기록된 메시지. 한국어 낱말을 많이 인용한 영어 문장(위의 여섯). 입력의
`transcript_path` 가 파일은 있는데 더 쓰이지 않는 사본을 가리키면 호출마다 상한만큼 늦고 침묵한다 —
워크트리를 오간 세션의 사본이 두 폴더에 남은 것은 봤으나(1c1bd2d5), 그 경로가 입력으로 오는지는
재지 않았다. 한글도 라틴 문자도 아닌 글자, 산문 속 따옴표 인용, 구분자 없는 이름의 판정은 Stop 훅의
독스트링과 같다. 알림은 상태 없이 영어 문장마다 나간다.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

MIN_LETTERS = 8
MIN_HANGUL_RATIO = 0.2
SDK_PREFIX = "sdk-"
# 트랜스크립트 끝에서 읽는 바이트. 자기 기록 뒤에 오는 것은 형제 호출의 기록과 결과뿐이다.
TAIL_BYTES = 2 * 1024 * 1024
# 자기 기록을 기다리는 상한과 간격. 병렬 호출의 첫 호출은 메시지가 끝나 기록이 쓰일 때까지 기다린다.
# 탐침에서 Bash 둘의 첫 호출이 60~160ms, Read 셋의 첫 호출이 1020~1040ms, 둘째가 460ms 였다.
WAIT_SECONDS = 2.0
POLL_SECONDS = 0.05

# 아래 정규식과 `prose_of`·`letter_counts`, 위의 문턱 둘은 tools/hook_stop_korean.py 와 같다.
# tests/tools/test_hook_midturn_korean.py 의 `test_산문_규칙과_문턱은_Stop_훅과_같다` 가 대조한다.
_FENCE = re.compile(
    r"^ {0,3}(?:"
    r"(?P<ticks>`{3,})[^`\n]*\n.*?(?:^ {0,3}(?P=ticks)`*[ \t]*$|\Z)"
    r"|(?P<tildes>~{3,})[^\n]*\n.*?(?:^ {0,3}(?P=tildes)~*[ \t]*$|\Z))",
    re.MULTILINE | re.DOTALL,
)
_BLOCKQUOTE = re.compile(r"^ {0,3}>.*$", re.MULTILINE)
_CODE_SPAN = re.compile(r"(?<!`)(?P<ticks>`+)(?!`).+?(?<!`)(?P=ticks)(?!`)")
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://\S*")
_IDENTIFIER = re.compile(r"\S*[A-Za-z0-9_][-_./:#@][A-Za-z0-9_]\S*")
_HANGUL = re.compile(r"[가-힣ㄱ-ㆎ]")
_LATIN = re.compile(r"[A-Za-z]")


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 PreToolUse 훅 입력 중 이 훅이 읽는 부분."""

    agent_id: str
    tool_use_id: str
    transcript_path: str


class Block(TypedDict, total=False):
    type: str
    id: str
    text: str


class Message(TypedDict, total=False):
    id: str
    content: list[Block] | str


class Record(TypedDict, total=False):
    """트랜스크립트 JSONL 한 줄 중 이 훅이 읽는 부분."""

    type: str
    isSidechain: bool
    message: Message


def prose_of(message: str) -> str:
    """코드 펜스, 인용 블록, 코드 스팬, 링크 대상, URL, 식별자를 뺀 산문."""
    prose = _FENCE.sub("", message)
    prose = _BLOCKQUOTE.sub("", prose)
    prose = _CODE_SPAN.sub("", prose)
    prose = _LINK_TARGET.sub("]", prose)
    prose = _URL.sub("", prose)
    return _IDENTIFIER.sub("", prose)


def letter_counts(message: str) -> tuple[int, int]:
    """산문의 (한글 음절과 자모 수, 라틴 문자 수)."""
    prose = prose_of(message)
    return len(_HANGUL.findall(prose)), len(_LATIN.findall(prose))


def notice_for(text: str) -> str | None:
    """중간 문장의 산문이 한국어가 아니면 알릴 문장, 아니면 None."""
    hangul, latin = letter_counts(text)
    letters = hangul + latin
    if letters < MIN_LETTERS or hangul >= letters * MIN_HANGUL_RATIO:
        return None
    return (
        f"이 도구 호출 앞에 쓴 중간 문장의 산문이 한국어가 아니다(코드를 뺀 글자 {letters}자 중 "
        f"한글 {hangul}자). 도구 호출 사이의 문장도 사용자에게 보인다. CLAUDE.md 의 원칙대로 다음 "
        "문장부터 한국어로 쓴다. 이미 보낸 문장은 다시 쓰지 않는다. 사용자가 영어를 요청했다면 이 "
        "알림은 따르지 않는다."
    )


def is_program_session(entrypoint: str | None) -> bool:
    """SDK 로 띄운 세션인가. 그 출력은 프로그램이 읽는다."""
    return entrypoint is not None and entrypoint.startswith(SDK_PREFIX)


def tail_lines(path: Path, limit: int) -> list[str]:
    """파일 끝 `limit` 바이트의 줄들. 앞이 잘렸으면 첫 줄을 버린다. 파일이 없으면 빈 목록."""
    try:
        with path.open("rb") as transcript:
            size = transcript.seek(0, os.SEEK_END)
            start = max(0, size - limit)
            transcript.seek(start)
            data = transcript.read()
    except OSError:
        return []
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[1:] if start > 0 else lines


def _assistant_blocks(lines: Sequence[str]) -> list[tuple[str, Block]]:
    """사이드체인이 아닌 assistant 기록의 (메시지 id, 블록)들. 순서대로."""
    blocks: list[tuple[str, Block]] = []
    for line in lines:
        # 도구 결과처럼 큰 user 기록은 풀지 않는다. assistant 기록에는 이 낱말이 반드시 있다.
        if '"assistant"' not in line or not line.lstrip().startswith("{"):
            continue
        try:
            record: Record = json.loads(line)
        except ValueError:
            continue
        message = record.get("message")
        if record.get("type") != "assistant" or record.get("isSidechain") or message is None:
            continue
        content = message.get("content")
        if isinstance(content, str):
            continue
        message_id = message.get("id", "")
        blocks.extend((message_id, block) for block in content or [])
    return blocks


def midturn_text(lines: Sequence[str], tool_use_id: str) -> str | None:
    """`tool_use_id` 호출 바로 앞의 중간 문장. 그 호출의 기록이 아직 없으면 None.

    같은 메시지에서 앞선 `tool_use` 뒤(없으면 메시지 처음)부터 자기까지의 텍스트 블록을 잇는다. 병렬
    호출의 둘째부터는 앞이 형제 `tool_use` 라 빈 문자열이다 — 같은 문장을 호출마다 알리지 않는다.
    """
    blocks = _assistant_blocks(lines)
    own = next(
        (
            index
            for index, (_, block) in enumerate(blocks)
            if block.get("type") == "tool_use" and block.get("id") == tool_use_id
        ),
        None,
    )
    if own is None:
        return None
    message_id = blocks[own][0]
    texts: list[str] = []
    for block_message, block in reversed(blocks[:own]):
        if block_message != message_id or block.get("type") == "tool_use":
            break
        if block.get("type") == "text":
            texts.append(block.get("text", ""))
    return "\n\n".join(text for text in reversed(texts) if text.strip())


def main() -> int:
    # stdin 은 바이트로. 이유는 .claude/rules/tools.md(대기열 25).
    payload: HookPayload = json.load(sys.stdin.buffer)
    if "agent_id" in payload or is_program_session(os.environ.get("CLAUDE_CODE_ENTRYPOINT")):
        return 0
    transcript_path = payload.get("transcript_path")
    tool_use_id = payload.get("tool_use_id")
    if not transcript_path or not tool_use_id:
        return 0
    transcript = Path(transcript_path)
    # 파일이 없으면 기다려도 나타나지 않는다(낡은 경로). 호출마다 상한만큼 늦추지 않는다.
    if not transcript.is_file():
        return 0
    deadline = time.monotonic() + WAIT_SECONDS
    text = midturn_text(tail_lines(transcript, TAIL_BYTES), tool_use_id)
    while text is None and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        text = midturn_text(tail_lines(transcript, TAIL_BYTES), tool_use_id)
    notice = notice_for(text) if text else None
    if notice is None:
        return 0
    output = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": notice}}
    # ASCII 로 낸다. 훅 환경의 stdout 은 cp949 일 수 있다(대기열 25).
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
