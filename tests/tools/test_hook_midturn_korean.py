"""tools/hook_midturn_korean.py 의 순수 함수와, 자식으로 띄운 훅의 실제 출력. 기다리지 않는 길
하나는 이 프로세스에서 main 을 불러 기다림이 불리는지 본다.

트랜스크립트의 모양은 `.scratch/harness/probes/pretool_text/` 탐침이 본 것이다(claude 2.1.286).
기록은 내용 블록 하나에 한 줄이고, 파일에는 메시지가 끝나거나 도구 결과를 쓸 때 그때까지의 블록이
함께 쓰인다. 그래서 병렬 호출의 첫 PreToolUse 에서는 자기 기록이 아직 없다.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools.hook_midturn_korean import (
    MIN_HANGUL_RATIO,
    MIN_LETTERS,
    WAIT_SECONDS,
    is_program_session,
    letter_counts,
    midturn_text,
    notice_for,
    prose_of,
    tail_lines,
)
from tools.hook_stop_korean import MIN_HANGUL_RATIO as STOP_MIN_HANGUL_RATIO
from tools.hook_stop_korean import MIN_LETTERS as STOP_MIN_LETTERS
from tools.hook_stop_korean import letter_counts as stop_letter_counts
from tools.hook_stop_korean import prose_of as stop_prose_of
from tools.run_hooks import hook_environment

from tools import hook_midturn_korean

HOOK = Path(__file__).parents[2] / "tools" / "hook_midturn_korean.py"

# 일지 2026-10-02-03 의 세션이 도구 호출 사이에 쓴 영어 문장의 모양("Now" 로 시작하는 한 줄).
ENGLISH = "Now let me run the full verification suite before committing."
KOREAN = "이제 커밋 전에 검증 명령을 모두 돌리겠습니다."


def _record(message_id: str, blocks: tuple[Mapping[str, str], ...], *, is_sidechain: bool) -> str:
    record = {
        "type": "assistant",
        "isSidechain": is_sidechain,
        "message": {"id": message_id, "role": "assistant", "content": list(blocks)},
    }
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def _assistant(message_id: str, *blocks: Mapping[str, str]) -> str:
    """Claude Code 가 쓰는 주 세션의 assistant 기록 한 줄. 블록은 보통 하나다."""
    return _record(message_id, blocks, is_sidechain=False)


def _sidechain(message_id: str, *blocks: Mapping[str, str]) -> str:
    """서브에이전트가 남긴 assistant 기록 한 줄."""
    return _record(message_id, blocks, is_sidechain=True)


def _result(tool_use_id: str) -> str:
    content = [{"type": "tool_result", "tool_use_id": tool_use_id, "content": "ok"}]
    record = {"type": "user", "message": {"role": "user", "content": content}}
    return json.dumps(record, separators=(",", ":"))


def _text(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def _use(tool_use_id: str) -> dict[str, str]:
    return {"type": "tool_use", "id": tool_use_id, "name": "Bash"}


def test_도구_호출_앞의_영어_중간_문장은_알린다() -> None:
    notice = notice_for(ENGLISH)

    assert notice is not None
    assert "한국어" in notice


def test_한국어_중간_문장은_알리지_않는다() -> None:
    assert notice_for(KOREAN) is None


def test_식별자가_섞인_한국어_중간_문장은_알리지_않는다() -> None:
    message = "`tools/run_hooks.py`를 게이트로 보게 `_GATE`에 넣고 pytest를 돌립니다."

    assert notice_for(message) is None


def test_글자가_적은_중간_문장은_판정하지_않는다() -> None:
    assert notice_for("OK.") is None


def test_코드만_든_중간_문장은_판정하지_않는다() -> None:
    assert notice_for("```bash\nuv run pytest -q\n```") is None


def test_산문_규칙과_문턱은_Stop_훅과_같다() -> None:
    """훅은 서로 import 하지 않아 정규식을 옮겨 왔다. 규칙마다 걸리는 문장으로 두 사본을 대조한다.

    한쪽만 고치면 여기서 빨갛다. 규칙 하나하나의 근거는 tests/tools/test_hook_stop_korean.py 다.
    """
    samples = [
        "앞\n```py\ncode\n```\n뒤",
        "앞\n~~~\ncode\n~~~\n뒤",
        "한 줄\n```\nnot closed",
        "```uv run pytest```\nNow merge.",
        "```\nprint(1)\n```~~~\nstill code\n```\n완료",
        "본문\n> quoted line\n뒤",
        "앞 `code` 와 ``a ` b`` 뒤",
        "[README](README) 와 [절](#section)",
        "서버 http://localhost/ 와 https://example.com/a?b=1 확인",
        "tools/run_hooks.py 와 kebab-name, snake_name, owner/repo#1 을 본다",
        "읽기/쓰기와 결과:통과했습니다",
        "자모 ㄱㄴㅎ ㆎ 와 라틴 abc XYZ, 그리고 일본語 です",
    ]

    assert [prose_of(s) for s in samples] == [stop_prose_of(s) for s in samples]
    assert [letter_counts(s) for s in samples] == [stop_letter_counts(s) for s in samples]
    assert (MIN_LETTERS, MIN_HANGUL_RATIO) == (STOP_MIN_LETTERS, STOP_MIN_HANGUL_RATIO)


def test_자기_호출_앞의_텍스트를_돌려준다() -> None:
    lines = [_assistant("m1", {"type": "thinking"}), _assistant("m1", _text(ENGLISH))]
    lines.append(_assistant("m1", _use("t1")))

    assert midturn_text(lines, "t1") == ENGLISH


def test_자기_tool_use_가_아직_기록되지_않았으면_모른다고_답한다() -> None:
    """병렬 호출의 첫 PreToolUse. 그 메시지의 기록이 아직 쓰이지 않았다. 빈 문자열(판정할 글이
    없다)과 갈라 None 이다 — 훅은 None 일 때만 다시 읽는다."""
    lines = [_assistant("m0", _text(KOREAN)), _assistant("m0", _use("t0")), _result("t0")]

    assert midturn_text(lines, "t1") is None


def test_병렬_호출은_텍스트_바로_뒤의_호출만_판정한다() -> None:
    """둘째 호출 앞은 형제 tool_use 다. 같은 문장을 호출마다 알리지 않는다."""
    lines = [
        _assistant("m1", _text(ENGLISH)),
        _assistant("m1", _use("t1")),
        _assistant("m1", _use("t2")),
    ]

    assert midturn_text(lines, "t1") == ENGLISH
    assert midturn_text(lines, "t2") == ""


def test_첫_호출의_결과가_먼저_쓰여도_둘째_호출은_판정하지_않는다() -> None:
    """데스크톱 세션의 병렬 Read 에서 첫 결과가 둘째 tool_use 앞에 쓰인 모양. 2026-10-02 세션
    4d667e76 의 트랜스크립트에서 tool_use 가 둘 이상인 메시지 40개 중 2개였다
    (`.scratch/harness/probes/pretool_text/interleave.py`)."""
    lines = [
        _assistant("m1", _text(ENGLISH)),
        _assistant("m1", _use("t1")),
        _result("t1"),
        _assistant("m1", _use("t2")),
    ]

    assert midturn_text(lines, "t2") == ""


def test_앞선_메시지의_텍스트는_이_호출의_것이_아니다() -> None:
    lines = [
        _assistant("m1", _text(ENGLISH)),
        _assistant("m1", _use("t1")),
        _result("t1"),
        _assistant("m2", _use("t2")),
    ]

    assert midturn_text(lines, "t2") == ""


def test_앞_턴의_답은_텍스트_없이_시작한_호출의_것이_아니다() -> None:
    """앞 턴을 끝낸 답(텍스트만)과 새 턴의 첫 호출 사이에는 tool_use 가 없다. 메시지 id 로
    가른다."""
    prompt = json.dumps({"type": "user", "message": {"role": "user", "content": "다음"}})
    lines = [_assistant("m1", _text(ENGLISH)), prompt, _assistant("m2", _use("t2"))]

    assert midturn_text(lines, "t2") == ""


def test_앞선_tool_use_뒤의_텍스트_블록만_이어서_본다() -> None:
    lines = [
        _assistant("m1", _text("First,")),
        _assistant("m1", _text("this.")),
        _assistant("m1", _use("t1")),
        _assistant("m1", _text("then that.")),
        _assistant("m1", _use("t2")),
    ]

    assert midturn_text(lines, "t1") == "First,\n\nthis."
    assert midturn_text(lines, "t2") == "then that."


def test_사이드체인의_기록은_보지_않는다() -> None:
    """서브에이전트의 기록이 주 트랜스크립트에 섞여도 그 호출은 주 세션의 것이 아니다."""
    lines = [_sidechain("s1", _text(ENGLISH)), _sidechain("s1", _use("t1"))]

    assert midturn_text(lines, "t1") is None


def test_JSON_이_아닌_줄과_잘린_줄은_건너뛴다() -> None:
    lines = ['ated": "잘린 앞줄"}', "", _assistant("m1", _text(ENGLISH))]
    lines.append(_assistant("m1", _use("t1")))

    assert midturn_text(lines, "t1") == ENGLISH


def test_꼬리만_읽으면_잘린_첫_줄을_버린다(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_bytes(b'{"a": 1}\n{"b": 2}\n{"c": 3}\n')

    assert tail_lines(path, 12) == ['{"c": 3}']
    assert tail_lines(path, 1000) == ['{"a": 1}', '{"b": 2}', '{"c": 3}']


def test_꼬리의_한글이_바이트_중간에서_잘려도_읽는다(tmp_path: Path) -> None:
    """첫 줄 19바이트 중 오프셋 9(`가` 의 셋째 바이트)부터 읽는다."""
    path = tmp_path / "t.jsonl"
    path.write_bytes('{"a": "가나다"}\n{"b": "라"}\n'.encode())

    assert tail_lines(path, 23) == ['{"b": "라"}']


def test_트랜스크립트가_없으면_빈_목록(tmp_path: Path) -> None:
    assert tail_lines(tmp_path / "없음.jsonl", 1000) == []


def test_SDK_로_띄운_세션만_프로그램_세션이다() -> None:
    assert is_program_session("sdk-py")
    assert not is_program_session("claude-desktop")
    assert not is_program_session(None)


def _write_transcript(path: Path, text: str, tool_use_id: str) -> None:
    lines = [_assistant("m1", _text(text)), _assistant("m1", _use(tool_use_id))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_hook(payload: Mapping[str, object], entrypoint: str | None = None) -> str:
    """훅을 자식으로 돌려 stdout 을 돌려준다. 환경은 러너의 것에 entrypoint 하나를 더한다."""
    env = hook_environment()
    if entrypoint is not None:
        env["CLAUDE_CODE_ENTRYPOINT"] = entrypoint
    process = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        env=env,
        check=True,
        timeout=20,
    )
    return process.stdout.decode("utf-8").strip()


def _payload(transcript: Path, tool_use_id: str) -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_use_id": tool_use_id,
        "transcript_path": str(transcript),
    }


def test_영어_중간_문장_뒤의_호출에서_실제로_알린다(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, ENGLISH, "t1")

    output = json.loads(_run_hook(_payload(transcript, "t1"), "claude-desktop"))

    assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "한국어" in output["hookSpecificOutput"]["additionalContext"]


def test_한국어_중간_문장_뒤의_호출은_실제로_조용하다(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, KOREAN, "t1")

    assert _run_hook(_payload(transcript, "t1")) == ""


def test_서브에이전트의_호출은_보지_않는다(tmp_path: Path) -> None:
    """서브에이전트의 중간 문장은 사용자에게 보이지 않는다. 입력에 `agent_id` 가 온다(탐침 B)."""
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, ENGLISH, "t1")
    payload = {**_payload(transcript, "t1"), "agent_id": "a1", "agent_type": "general-purpose"}

    assert _run_hook(payload) == ""


def test_SDK_세션의_호출은_보지_않는다(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, ENGLISH, "t1")

    assert _run_hook(_payload(transcript, "t1"), "sdk-py") == ""


def test_기다리는_사이에_쓰인_자기_기록을_읽어_알린다(tmp_path: Path) -> None:
    """병렬 호출의 첫 PreToolUse. 메시지가 끝나 기록이 쓰이는 것은 훅이 시작한 뒤다."""
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(_result("t0") + "\n", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(HOOK)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=hook_environment(),
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(json.dumps(_payload(transcript, "t1")).encode("utf-8"))
    process.stdin.close()
    time.sleep(WAIT_SECONDS / 4)
    with transcript.open("a", encoding="utf-8") as late:
        late.write(_assistant("m1", _text(ENGLISH)) + "\n" + _assistant("m1", _use("t1")) + "\n")

    # stdin 을 이미 닫아 communicate() 를 쓰지 않는다. 리눅스의 communicate() 는 닫힌 stdin 을
    # flush 하다 ValueError 를 낸다(PR #123 CI, 윈도우에서는 지나갔다).
    stdout = process.stdout.read()
    process.wait(timeout=20)

    assert "additionalContext" in stdout.decode("utf-8")


def test_자기_tool_use_가_끝내_없으면_기다림_상한_뒤_조용히_지나간다(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, ENGLISH, "t1")
    start = time.monotonic()

    output = _run_hook(_payload(transcript, "없는-id"))

    assert output == ""
    assert time.monotonic() - start >= WAIT_SECONDS


def test_트랜스크립트_경로가_없으면_조용히_지나간다() -> None:
    assert _run_hook({"hook_event_name": "PreToolUse", "tool_use_id": "t1"}) == ""


def test_트랜스크립트_파일이_없으면_기다리지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """파일이 없는 경로(이 세션은 워크트리로 옮기자 옛 폴더의 파일이 사라졌다)에서 호출마다 상한만큼
    늦추지 않는다. 파일은 있는데 더 쓰이지 않는 사본의 경로는 이 가드가 막지 못한다(독스트링의 못
    보는 것).

    걸린 시간이 아니라 기다림(`time.sleep`)이 불리는지 본다. 자식으로 띄운 훅이 상한(2초) 안에
    끝나는지 재던 판은 전체 스위트의 부하에서, 훅이 한 번도 쉬지 않았는데도 자식을 띄우고 모듈을
    읽는 데만 2초를 넘겨 빨갰다(ADR 0035 의 2026-10-19 트랜스크립트 파일 이력). 상한을 넓히면
    상한만큼 기다리는 회귀도 지나가 그 길은 쓰지 않는다. `time.sleep` 없이 도는 기다림은 이 시험이
    보지 못한다."""

    def 기다린다(seconds: float) -> None:
        raise AssertionError(f"파일이 없는데 {seconds}초 쉬며 기록을 기다렸다")

    monkeypatch.setattr(
        hook_midturn_korean, "time", SimpleNamespace(monotonic=time.monotonic, sleep=기다린다)
    )
    # 이 세션이 SDK 로 떴으면 main 이 가드 앞에서 돌아가 시험이 헛돈다
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
    payload = json.dumps(_payload(tmp_path / "없음.jsonl", "t1")).encode("utf-8")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8"))

    assert hook_midturn_korean.main() == 0
    assert capsys.readouterr().out == ""
