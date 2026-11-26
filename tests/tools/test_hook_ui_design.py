"""tools/hook_ui_design.py 의 판정과 표지. main 은 stdin 과 임시 폴더를 바꿔 끼워 표지 길을 보고,
래퍼를 거친 실제 실행은 tools/run_hooks.py 의 표가 본다.

경로는 이 저장소의 주 체크아웃과 워크트리 꼴이다.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from tools.hook_ui_design import (
    LEAD,
    TOOLS,
    HookPayload,
    claim_first,
    context_for,
    design_slug,
    main,
    marker_name,
)
from tools.run_hooks import registered_matchers

ROOT = "C:\\project\\rag-engine"
WORKTREE = ROOT + "\\.claude\\worktrees\\ui-design-skill-port"


def _write(file_path: str) -> HookPayload:
    return {"tool_name": "Write", "tool_input": {"file_path": file_path}}


def test_기능의_디자인_폴더에_쓰면_그_기능으로_알린다() -> None:
    context = context_for(_write(ROOT + "\\.scratch\\admin\\design\\README.md"))
    assert context is not None
    assert context.startswith(LEAD)
    assert "/ui-design admin" in context


def test_하위_폴더와_슬래시_꼴과_워크트리도_알린다() -> None:
    assert design_slug(ROOT + "\\.scratch\\admin\\design\\screens\\Main.dc.html") == "admin"
    assert design_slug("C:/project/rag-engine/.scratch/eval-screen/design/x.md") == "eval-screen"
    assert design_slug(WORKTREE + "\\.scratch\\admin\\design\\x.md") == "admin"


def test_Edit_도_알린다() -> None:
    payload: HookPayload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": ROOT + "\\.scratch\\group-kb\\design\\screens-prompt.md"},
    }
    context = context_for(payload)
    assert context is not None
    assert "/ui-design group-kb" in context


def test_디자인_폴더_밖의_scratch_파일은_지나간다() -> None:
    assert design_slug(ROOT + "\\.scratch\\admin\\spec.md") is None
    assert design_slug(ROOT + "\\.scratch\\admin\\issues\\01-x.md") is None
    assert design_slug(ROOT + "\\.scratch\\admin\\probes\\design\\x.py") is None


def test_design_폴더_자체나_scratch_밖의_design은_지나간다() -> None:
    # 폴더 이름만 같은 다른 자리와, 파일 없이 폴더로 끝나는 경로.
    assert design_slug(ROOT + "\\.scratch\\admin\\design") is None
    assert design_slug(ROOT + "\\web\\design\\x.md") is None
    assert design_slug(ROOT + "\\.scratch\\design\\x.md") is None


def test_점과_점점_토막을_접은_경로로_판정한다() -> None:
    # agent-os 에서 PR 직전 bug-perf-review 가 손으로 부른 반례들. 접기 전에는 `..` 를 기능으로
    # 읽거나 놓쳤다.
    assert design_slug(ROOT + "\\.scratch\\..\\design\\x\\y.md") is None
    assert design_slug(ROOT + "\\.scratch\\a\\design\\b\\..\\..\\c.md") is None
    assert design_slug(ROOT + "\\.scratch\\f\\design\\..") is None
    assert design_slug(ROOT + "\\.scratch\\f\\.\\design\\a.md") == "f"
    assert design_slug(ROOT + "\\.scratch\\f\\..\\g\\design\\a.md") == "g"


def test_접히지_않고_맨_앞에_남은_점점은_판정을_바꾸지_않는다() -> None:
    assert design_slug("..\\..\\.scratch\\f\\design\\a.md") == "f"
    assert design_slug("../.scratch/design/a.md") is None


def test_대소문자가_다른_폴더_이름도_디자인_폴더다() -> None:
    assert design_slug(ROOT + "\\.Scratch\\admin\\Design\\x.md") == "admin"


def test_못_보는_것_윈도가_끝의_점과_공백을_지우는_이름은_지나간다() -> None:
    assert design_slug(ROOT + "\\.scratch\\admin\\design.\\x.md") is None
    assert design_slug(ROOT + "\\.scratch\\admin\\design \\x.md") is None


def test_다른_도구와_경로_없는_입력은_지나간다() -> None:
    path = ROOT + "\\.scratch\\admin\\design\\x.md"
    read: HookPayload = {"tool_name": "Read", "tool_input": {"file_path": path}}
    assert context_for(read) is None
    assert context_for({"tool_name": "Write", "tool_input": {}}) is None
    assert context_for({"tool_name": "Write"}) is None


@pytest.mark.parametrize("tool_input", ["x", {"file_path": 1}, {"file_path": None}])
def test_꼴이_어긋난_입력은_예외_없이_지나간다(tool_input: object) -> None:
    # HookPayload 에 맞지 않는 꼴이라 main 처럼 JSON 에서 풀어 넘긴다.
    payload = json.loads(json.dumps({"tool_name": "Write", "tool_input": tool_input}))
    assert context_for(payload) is None


def test_못_보는_것_Bash_로_옮긴_디자인_파일은_지나간다() -> None:
    # 아티팩트에서 받은 파일을 cp 로 옮기면 이 훅은 보지 못한다. 등록 매처에도 Bash 가 없다.
    command = f"cp a.dc.html '{ROOT}\\.scratch\\admin\\design\\a.dc.html'"
    bash = {"tool_name": "Bash", "tool_input": {"command": command}}
    assert context_for(json.loads(json.dumps(bash))) is None


def test_못_보는_것_스킬을_이미_부른_세션에도_한_번_알린다() -> None:
    # 이 훅은 그 세션이 /ui-design 을 불렀는지 모른다. 표지가 없으면 스킬이 쓴 첫 파일에도 알린다.
    assert context_for(_write(ROOT + "\\.scratch\\admin\\design\\README.md")) is not None


def test_표지는_세션과_에이전트마다_한_번이다(tmp_path: Path) -> None:
    main_key = marker_name("s1", "")
    assert claim_first(main_key, tmp_path)
    assert not claim_first(main_key, tmp_path)
    assert claim_first(marker_name("s1", "agent-a"), tmp_path)
    assert claim_first(marker_name("s2", ""), tmp_path)


def test_표지를_쓰지_못하면_알린다(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    assert claim_first(marker_name("s1", ""), blocker / "state")
    assert claim_first(marker_name("s1", ""), blocker)


def test_표지_파일을_만들지_못하면_알린다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*_args: object) -> int:
        raise PermissionError

    monkeypatch.setattr(os, "open", denied)
    assert claim_first(marker_name("s1", ""), tmp_path)
    assert claim_first(marker_name("s1", ""), tmp_path)


def _run_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], payload: HookPayload
) -> str:
    """main 을 한 번 돌려 알린 문장을, 알리지 않았으면 빈 문자열을 돌려준다."""
    stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    assert main() == 0
    out = capsys.readouterr().out
    if not out:
        return ""
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert isinstance(context, str)
    return context


def _session_write(file_path: str, agent_id: str = "") -> HookPayload:
    payload = _write(file_path)
    payload["session_id"] = "session-1"
    if agent_id:
        payload["agent_id"] = agent_id
    return payload


def test_main_은_세션과_에이전트마다_한_번_알린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    path = ROOT + "\\.scratch\\admin\\design\\a.md"
    assert LEAD in _run_main(monkeypatch, capsys, _session_write(path))
    assert _run_main(monkeypatch, capsys, _session_write(path)) == ""
    assert LEAD in _run_main(monkeypatch, capsys, _session_write(path, "agent-a"))


def test_못_보는_것_한_번_알린_뒤의_다른_기능은_지나간다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # 표지는 세션·에이전트마다 하나라, 한 세션이 두 기능의 디자인 폴더에 쓰면 둘째 기능은 알림을
    # 받지 못한다.
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    first = ROOT + "\\.scratch\\admin\\design\\a.md"
    second = ROOT + "\\.scratch\\group-kb\\design\\a.md"
    assert LEAD in _run_main(monkeypatch, capsys, _session_write(first))
    assert _run_main(monkeypatch, capsys, _session_write(second)) == ""


def test_main_은_임시_폴더가_없으면_호출마다_알린다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_temp() -> str:
        raise FileNotFoundError("쓸 수 있는 임시 폴더가 없다")

    monkeypatch.setattr(tempfile, "gettempdir", no_temp)
    path = ROOT + "\\.scratch\\admin\\design\\a.md"
    assert LEAD in _run_main(monkeypatch, capsys, _session_write(path))
    assert LEAD in _run_main(monkeypatch, capsys, _session_write(path))


def test_main_은_세션을_모르면_임시_폴더가_있어도_호출마다_알린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    payload = _write(ROOT + "\\.scratch\\admin\\design\\a.md")
    assert LEAD in _run_main(monkeypatch, capsys, payload)
    assert LEAD in _run_main(monkeypatch, capsys, payload)
    assert not any(tmp_path.iterdir())


def test_등록의_매처가_훅이_아는_도구와_같다() -> None:
    assert registered_matchers("hook_ui_design.py", "PostToolUse") == ["|".join(TOOLS)]
