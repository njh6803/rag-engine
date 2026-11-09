"""tools/hook_report.py 검증.

기록의 모양은 이 PC의 세션 기록에서 손으로 본 것을 줄여 옮겼다(2026-10-19). 출력을 낸 훅만
`hook_success` 첨부를 남기고, 그 가운데에는 uv 의 가상 환경 경고(stderr)만 든 것도 섞인다. 도구
호출을 막은 훅은 첨부를 남기지 않고 도구 결과의 `<이벤트>:<도구> hook error: <이유>` 에만 이유가
남는다. Stop 훅이 막으면 `hook_blocking_error` 첨부가 이유와 명령을 함께 든다. 모델에게 간 계기는
명령 없는 `hook_additional_context` 첨부로도 남고, UserPromptSubmit 의 계기는 이것만 남는다
(2026-10-23, 대기열 404).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from tools.hook_report import (
    AMBIGUOUS,
    BLOCK,
    NOTICE,
    PROMPT_EVENT,
    UNKNOWN,
    Firing,
    Scan,
    fingerprints,
    folder_name_of,
    fragment_owner,
    introduced_dates,
    main_checkout_folder,
    model_context,
    registered_hooks,
    render,
    scan,
    transcript_files,
)
from tools.launch_hook import notice, skip_reason
from tools.run_hooks import create_fixtures, hook_environment, load_cases, message_of, substitute

ROOT = Path(__file__).resolve().parents[2]
TODAY = date(2026, 10, 19)
REPO = "C--project-agent"
LAUNCH = (
    'uv run --project "${CLAUDE_PROJECT_DIR}" --no-sync python '
    '"${CLAUDE_PROJECT_DIR}/tools/launch_hook.py" '
)
ENV_REASON = "`.env` 는 비밀이라 도구 출력에 싣지 않는다"
PROMPT_NOTICE = "지시문으로 연 새 세션이다. 제목을 브랜치 이름으로 바꾼다"
PROMPT_HOOKS = ("hook_prompt.py",)  # UserPromptSubmit 에 등록된 훅

type Record = dict[str, object]


def _notice(
    hook: str,
    stdout: str,
    uuid: str,
    when: str = "2026-10-18T01:00:00.000Z",
    *,
    stderr: str = "",
    command: str | None = None,
    event: str = "PostToolUse",
    session: str = "s1",
    tool: str = "toolu_1",
) -> Record:
    return {
        "type": "attachment",
        "uuid": uuid,
        "timestamp": when,
        "sessionId": session,
        "attachment": {
            "type": "hook_success",
            "hookName": "PostToolUse:Edit" if event == "PostToolUse" else event,
            "toolUseID": tool,
            "hookEvent": event,
            "command": LAUNCH + hook if command is None else command,
            "stdout": stdout,
            "stderr": stderr,
            "exitCode": 0,
            "content": "",
        },
    }


def _denied(
    content: str | list[dict[str, str]], uuid: str, when: str = "2026-10-18T02:00:00.000Z"
) -> Record:
    """`content` 가 글이면 훅 오류의 머리를 붙인 도구 결과이고, 목록이면 그대로 싣는다."""
    body = f"PreToolUse:Bash hook error: {content}" if isinstance(content, str) else content
    return {
        "type": "user",
        "uuid": uuid,
        "timestamp": when,
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": body, "is_error": True}
            ],
        },
    }


def _plain_result(text: str, uuid: str) -> Record:
    return {
        "type": "user",
        "uuid": uuid,
        "timestamp": "2026-10-18T02:00:00.000Z",
        "message": {"role": "user", "content": [{"type": "tool_result", "content": text}]},
    }


def _stopped(hook: str, reason: str, uuid: str) -> Record:
    return {
        "type": "attachment",
        "uuid": uuid,
        "timestamp": "2026-10-18T03:00:00.000Z",
        "attachment": {
            "type": "hook_blocking_error",
            "hookName": "Stop",
            "hookEvent": "Stop",
            "blockingError": {"blockingError": reason, "command": LAUNCH + hook},
        },
    }


def _write(path: Path, *records: Record) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    path.write_text(lines, encoding="utf-8")
    return path


def _context(text: str, event: str = "PostToolUse") -> str:
    """훅이 내는 꼴 그대로 한글을 `\\uXXXX` 로 이스케이프한 계기."""
    output = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
    return json.dumps(output)


def _attached(
    text: str,
    uuid: str,
    *,
    event: str = "UserPromptSubmit",
    session: str = "s1",
    tool: str = "hook-1",
    when: str = "2026-10-18T04:00:00.000Z",
) -> Record:
    """명령 없는 계기 첨부. SessionStart 의 것은 `toolUseID` 가 이벤트 이름이다(2026-10-23 이 PC의
    기록에서 손으로 봤다)."""
    return {
        "type": "attachment",
        "uuid": uuid,
        "timestamp": when,
        "sessionId": session,
        "attachment": {
            "type": "hook_additional_context",
            "content": [text],
            "hookName": event,
            "toolUseID": tool,
            "hookEvent": event,
        },
    }


def _tools(root: Path, sources: dict[str, str]) -> Path:
    tools = root / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        (tools / name).write_text(source, encoding="utf-8")
    return tools


def _counts(result: Scan) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for firing in result.firings:
        key = (firing.hook, firing.kind)
        counts[key] = counts.get(key, 0) + 1
    return counts


def test_폴더_이름은_영문자와_숫자_밖의_글자를_대시로_바꾼다() -> None:
    assert folder_name_of("C:\\project\\agent") == REPO
    assert folder_name_of("C:/project/agent") == REPO


def test_주_체크아웃과_그_워크트리의_기록만_읽고_서브에이전트_기록도_읽는다(
    tmp_path: Path,
) -> None:
    main = _write(tmp_path / REPO / "s.jsonl")
    worktree = _write(tmp_path / f"{REPO}--claude-worktrees-x" / "s.jsonl")
    sub = _write(tmp_path / f"{REPO}--claude-worktrees-x" / "s" / "subagents" / "a.jsonl")
    _write(tmp_path / f"{REPO}-runtime-platform" / "s.jsonl")
    _write(tmp_path / f"{REPO}-canary-02b21d0" / "s.jsonl")
    _write(tmp_path / f"C--Users-User-AppData-Local-Temp-claude-{REPO}-x" / "s.jsonl")
    assert sorted(transcript_files(tmp_path, REPO)) == sorted([main, worktree, sub])


def test_알림은_stdout을_낸_hook_success만_세고_stderr만_낸_것은_세지_않는다(
    tmp_path: Path,
) -> None:
    warning = "warning: `VIRTUAL_ENV=...` does not match the project environment path"
    path = _write(
        tmp_path / "s.jsonl",
        _notice("hook_a.py", _context("고쳐라"), "u1"),
        _notice("hook_b.py", "", "u2", stderr=warning),
    )
    assert _counts(scan([path], {}, ())) == {("hook_a.py", NOTICE): 1}


def test_래퍼가_훅_파일이_없어_지나간_알림은_세지_않는다(tmp_path: Path) -> None:
    absent = json.dumps(
        {"systemMessage": "launch_hook: 훅 파일이 없어 돌리지 않고 지나갔다: tools/hook_a.py."},
        ensure_ascii=False,
    )
    path = _write(tmp_path / "s.jsonl", _notice("hook_a.py", absent, "u1"))
    assert scan([path], {}, ()).firings == ()


def test_래퍼가_인자가_틀려_지나간_알림도_세지_않는다(tmp_path: Path) -> None:
    """표준 축 리뷰: 래퍼가 지나가며 내는 문구는 둘인데(`launch_hook.skip_reason`) 하나만 걸렀다."""
    wrong = json.dumps(
        {
            "systemMessage": "launch_hook: 등록 명령의 훅 이름 인자가 하나가 아니라(['a', 'b'])"
            " 아무 훅도 돌리지 않고 지나갔다."
        },
        ensure_ascii=False,
    )
    path = _write(tmp_path / "s.jsonl", _notice("hook_a.py", wrong, "u1"))
    assert scan([path], {}, ()).firings == ()


def test_래퍼가_지나가며_내는_실제_출력은_세지_않는다(tmp_path: Path) -> None:
    """PR 직전 버그 축: 위 두 시험은 문구를 손으로 옮겨, `launch_hook.skip_reason` 의 문구가
    바뀌어도 초록이었다. 래퍼의 함수로 지은 출력을 넣는다."""
    strings = {"hook_event_name": "PostToolUse"}
    outputs = [
        notice(skip_reason(argv), strings)
        for argv in (["launch_hook.py"], ["launch_hook.py", "hook_a.py"])
    ]
    records = [_notice("hook_a.py", out, f"u{i}") for i, out in enumerate(outputs)]
    assert scan([_write(tmp_path / "s.jsonl", *records)], {}, ()).firings == ()


def test_읽는_사이_사라진_기록_파일은_건너뛰고_읽지_못한_파일로_센다(tmp_path: Path) -> None:
    """PR 직전 버그 축: 도는 동안 다른 세션이 기한 지난 기록을 지우면 트레이스백으로 끝났다."""
    path = _write(tmp_path / "s.jsonl", _notice("hook_a.py", _context("고쳐라"), "u1"))
    result = scan([tmp_path / "gone.jsonl", path], {}, ())
    assert _counts(result) == {("hook_a.py", NOTICE): 1}
    assert result.unreadable == 1
    out = render(result, [], {}, TODAY, 28)
    assert "읽지 못한 파일 1개" in out


def test_tools_밖의_훅_명령의_알림은_세지_않는다(tmp_path: Path) -> None:
    plugin = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/security.sh" hook_a.py'
    path = _write(tmp_path / "s.jsonl", _notice("hook_a.py", _context("x"), "u1", command=plugin))
    assert scan([path], {}, ()).firings == ()


def test_래퍼_전의_등록_모양으로_부른_훅의_알림도_그_훅으로_센다(tmp_path: Path) -> None:
    old = "uv run --no-sync python tools/hook_a.py"
    path = _write(tmp_path / "s.jsonl", _notice("hook_a.py", _context("x"), "u1", command=old))
    assert _counts(scan([path], {}, ())) == {("hook_a.py", NOTICE): 1}


def test_같은_uuid는_파일이_달라도_한_번만_센다(tmp_path: Path) -> None:
    record = _notice("hook_a.py", _context("고쳐라"), "same")
    first = _write(tmp_path / "a.jsonl", record)
    second = _write(tmp_path / "b.jsonl", record)
    assert _counts(scan([first, second], {}, ())) == {("hook_a.py", NOTICE): 1}


def test_발동한_날은_기록_시각의_UTC_날짜다(tmp_path: Path) -> None:
    late = _notice("hook_a.py", _context("x"), "u1", "2026-10-18T23:30:00Z")
    seoul = _notice("hook_a.py", _context("x"), "u2", "2026-10-19T08:30:00+09:00")
    path = _write(tmp_path / "s.jsonl", late, seoul)
    days = [firing.day for firing in scan([path], {}, ()).firings]
    assert days == [date(2026, 10, 18), date(2026, 10, 18)]


def test_도구를_막은_이유는_가장_긴_조각이_든_훅으로_센다(tmp_path: Path) -> None:
    tools = _tools(
        tmp_path,
        {
            "hook_env.py": f'REASON = "{ENV_REASON}"\n',
            "hook_cd.py": (
                "def reason(cmd):\n"
                '    return f"`{cmd}` 가 셸의 작업 폴더를 바꾼다. 절대 경로를 쓴다"\n'
            ),
            "hook_quote.py": 'REASON = "비밀이라 도구 출력에"\n',
        },
    )
    prints = fingerprints(tools, ["hook_env.py", "hook_cd.py", "hook_quote.py"])
    assert fragment_owner(f"`cat .env`: {ENV_REASON}", prints) == "hook_env.py"
    cd_reason = "`cd x` 가 셸의 작업 폴더를 바꾼다. 절대 경로를 쓴다"
    assert fragment_owner(cd_reason, prints) == "hook_cd.py"


def test_어느_훅의_조각도_없는_이유는_모름으로_센다(tmp_path: Path) -> None:
    tools = _tools(tmp_path, {"hook_env.py": f'REASON = "{ENV_REASON}"\n'})
    prints = fingerprints(tools, ["hook_env.py", "hook_gone.py"])
    assert prints["hook_gone.py"] == frozenset()
    assert fragment_owner("플러그인 훅이 막았다", prints) == UNKNOWN


def test_같은_길이의_조각이_두_훅에_있으면_여럿으로_센다(tmp_path: Path) -> None:
    shared = 'REASON = "같은 문장을 두 훅이 함께 쓴다"\n'
    tools = _tools(tmp_path, {"hook_a.py": shared, "hook_b.py": shared})
    prints = fingerprints(tools, ["hook_a.py", "hook_b.py"])
    assert fragment_owner("같은 문장을 두 훅이 함께 쓴다", prints) == AMBIGUOUS


def test_짧은_문자열과_독스트링은_조각으로_쓰지_않는다(tmp_path: Path) -> None:
    """독스트링은 다른 훅의 이유를 인용할 수 있어 조각에서 뺀다."""
    source = f'"""이 훅은 {ENV_REASON} 같은 이유를 낸다."""\n\nKEY = "Bash"\nPATTERN = "deny"\n'
    tools = _tools(tmp_path, {"hook_a.py": source})
    assert fingerprints(tools, ["hook_a.py"])["hook_a.py"] == frozenset()


def test_막은_기록을_훅과_이유의_머리로_센다(tmp_path: Path) -> None:
    tools = _tools(tmp_path, {"hook_env.py": f'REASON = "{ENV_REASON}"\n'})
    prints = fingerprints(tools, ["hook_env.py"])
    path = _write(
        tmp_path / "s.jsonl",
        _denied(ENV_REASON, "u1"),
        _denied("다른 플러그인이 막았다\n둘째 줄", "u2"),
        _stopped("hook_stop.py", "한국어로 다시 쓴다", "u3"),
    )
    result = scan([path], prints, ())
    assert _counts(result) == {
        ("hook_env.py", BLOCK): 1,
        (UNKNOWN, BLOCK): 1,
        ("hook_stop.py", BLOCK): 1,
    }
    unknown = [firing for firing in result.firings if firing.hook == UNKNOWN]
    assert unknown[0].head == "다른 플러그인이 막았다"


def test_종료_코드_2로_막은_이유는_머리의_명령으로_훅을_고르고_머리_뒤를_적는다(
    tmp_path: Path,
) -> None:
    """두 훅이 같은 조각을 써도 머리의 명령이 훅을 정한다. 훅이 아닌 명령이면 조각으로 고른다."""
    shared = f'REASON = "{ENV_REASON}"\n'
    tools = _tools(tmp_path, {"hook_a.py": shared, "hook_b.py": shared})
    prints = fingerprints(tools, ["hook_a.py", "hook_b.py"])
    exit2 = f"[{LAUNCH}hook_b.py]: {ENV_REASON}\n둘째 줄"
    other = f'[bash "${{CLAUDE_PLUGIN_ROOT}}/x.sh"]: {ENV_REASON}'
    path = _write(tmp_path / "s.jsonl", _denied(exit2, "u1"), _denied(other, "u2"))
    result = scan([path], prints, ())
    assert result.firings == (
        Firing("hook_b.py", BLOCK, date(2026, 10, 18), ENV_REASON),
        Firing(AMBIGUOUS, BLOCK, date(2026, 10, 18), ENV_REASON),
    )


def test_도구_결과가_글_조각의_목록이어도_막은_이유를_읽는다(tmp_path: Path) -> None:
    blocks = [{"type": "text", "text": "PreToolUse:Grep hook error: 막았다"}]
    path = _write(tmp_path / "s.jsonl", _denied(blocks, "u1"))
    assert _counts(scan([path], {}, ())) == {(UNKNOWN, BLOCK): 1}


def test_훅_오류로_시작하지_않는_도구_결과는_세지_않는다(tmp_path: Path) -> None:
    path = _write(tmp_path / "s.jsonl", _plain_result("출력에 hook error: 가 든다", "u1"))
    assert scan([path], {}, ()).firings == ()


def test_읽지_못한_줄은_세고_건너뛰며_끝의_쓰다_만_줄은_버린다(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    record = json.dumps(_notice("hook_a.py", _context("x"), "u1"), ensure_ascii=False)
    path.write_text(f'not json\n[1, 2]\n{record}\n{{"type": "attach', encoding="utf-8")
    result = scan([path], {}, ())
    assert result.broken == 2
    assert _counts(result) == {("hook_a.py", NOTICE): 1}


def test_가장_이른_기록_날짜는_훅_밖의_기록까지_본다(tmp_path: Path) -> None:
    early: Record = {"type": "user", "uuid": "e", "timestamp": "2026-09-20T00:00:00Z"}
    path = _write(tmp_path / "s.jsonl", early, _notice("hook_a.py", _context("x"), "u1"))
    assert scan([path], {}, ()).earliest == date(2026, 9, 20)


def _prompt_prints(tmp_path: Path) -> dict[str, frozenset[str]]:
    tools = _tools(tmp_path, {"hook_prompt.py": f'CONTEXT = "{PROMPT_NOTICE}"\n'})
    return fingerprints(tools, ["hook_prompt.py"])


def _scan_prompt(tmp_path: Path, *records: Record) -> Scan:
    """`hook_prompt.py` 가 UserPromptSubmit 에 등록된 저장소로 기록 파일 하나를 훑는다."""
    path = _write(tmp_path / "s.jsonl", *records)
    return scan([path], _prompt_prints(tmp_path), PROMPT_HOOKS)


def test_hook_success_없이_남은_계기_첨부는_조각으로_그_훅의_알림으로_센다(tmp_path: Path) -> None:
    """대기열 404: UserPromptSubmit 훅의 계기는 명령 없는 첨부로만 남아, 첫 턴마다 알린
    `hook_prompt_directive` 를 창 안에서 알리지도 막지도 않았다며 뺄 후보로 냈다."""
    result = _scan_prompt(tmp_path, _attached(f"{PROMPT_NOTICE}\n둘째 줄", "u1"))
    assert result.firings == (Firing("hook_prompt.py", NOTICE, date(2026, 10, 18), PROMPT_NOTICE),)


def test_같은_세션과_이벤트에서_같은_글을_낸_hook_success가_있으면_첨부는_세지_않는다(
    tmp_path: Path,
) -> None:
    """PostToolUse 는 같은 계기를 명령 든 `hook_success` 와 명령 없는 첨부로 함께 남긴다.
    SessionStart 의 첨부는 `toolUseID` 가 이벤트 이름이라 `hook_success` 의 것과 달라 짝을 글로
    짓는다. 첨부가 `hook_success` 보다 먼저 읽혀도 짝을 짓는다."""
    start = _context(PROMPT_NOTICE, "SessionStart")
    result = _scan_prompt(
        tmp_path,
        _notice("hook_prompt.py", _context(PROMPT_NOTICE), "u1"),
        _attached(PROMPT_NOTICE, "u2", event="PostToolUse", tool="toolu_1"),
        _attached(PROMPT_NOTICE, "u3", event="SessionStart", tool="SessionStart"),
        _notice("hook_prompt.py", start, "u4", event="SessionStart", tool="0f6e1d2c"),
    )
    assert _counts(result) == {("hook_prompt.py", NOTICE): 2}


def test_짝은_세션과_이벤트가_모두_같아야_짓는다(tmp_path: Path) -> None:
    """PreToolUse 와 PostToolUse 는 같은 도구 호출의 `toolUseID` 를 함께 쓴다. 짝을 그 ID 로
    짓거나 세션을 보지 않으면 PostToolUse 의 첨부가 PreToolUse 나 다른 세션의 `hook_success` 와
    짝이 된다."""
    pre = _context(PROMPT_NOTICE, "PreToolUse")
    result = _scan_prompt(
        tmp_path,
        _notice("hook_prompt.py", pre, "u1", event="PreToolUse", tool="toolu_1"),
        _attached(PROMPT_NOTICE, "u2", event="PostToolUse", tool="toolu_1"),
        _notice("hook_prompt.py", _context(PROMPT_NOTICE), "u3", session="s2"),
        _attached(PROMPT_NOTICE, "u4", event="PostToolUse", session="s3"),
    )
    assert _counts(result) == {("hook_prompt.py", NOTICE): 2, (UNKNOWN, NOTICE): 2}


def test_같은_글의_첨부가_짝보다_많으면_남는_첨부만_센다(tmp_path: Path) -> None:
    result = _scan_prompt(
        tmp_path,
        _notice("hook_prompt.py", _context(PROMPT_NOTICE), "u1"),
        _attached(PROMPT_NOTICE, "u2", event="PostToolUse"),
        _attached(PROMPT_NOTICE, "u3", event="PostToolUse"),
    )
    assert _counts(result) == {("hook_prompt.py", NOTICE): 1, (UNKNOWN, NOTICE): 1}


def test_tools_밖의_훅이_낸_계기도_짝이_있으면_첨부를_세지_않는다(tmp_path: Path) -> None:
    """짝은 명령을 가리지 않는다. 플러그인 훅의 계기 첨부는 그 훅의 `hook_success` 와 짝지어 빼고
    가르지 못한 알림으로도 세지 않는다."""
    plugin = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/security.sh"'
    warning = "플러그인 경고: 비밀이 든 파일을 열었다"
    result = _scan_prompt(
        tmp_path,
        _notice("hook_prompt.py", _context(warning), "u1", command=plugin),
        _attached(warning, "u2", event="PostToolUse"),
    )
    assert result.firings == ()


def test_hook_system_message_첨부는_읽지_않는다(tmp_path: Path) -> None:
    """사용자에게 간 글이고, 같은 글의 `hook_success` 와 늘 짝이 있었다(2026-10-23 이 PC의
    기록에서 손으로 봤다). 모양은 그 기록의 Stop 첨부를 줄여 옮겼다."""
    record: Record = {
        "type": "attachment",
        "uuid": "u1",
        "timestamp": "2026-10-18T04:00:00.000Z",
        "sessionId": "s1",
        "attachment": {
            "type": "hook_system_message",
            "content": PROMPT_NOTICE,
            "hookName": "Stop",
            "toolUseID": "dedd58ee",
            "hookEvent": "Stop",
        },
    }
    assert _scan_prompt(tmp_path, record).firings == ()


def test_짝_없는_첨부의_래퍼_알림은_세지_않는다(tmp_path: Path) -> None:
    """UserPromptSubmit 은 래퍼의 `CONTEXT_EVENTS` 라 래퍼가 지나간 알림도 명령 없는 첨부로만
    남는다. 래퍼의 함수로 지은 글을 넣는다."""
    strings = {"hook_event_name": "UserPromptSubmit"}
    texts = [
        model_context(notice(skip_reason(argv), strings))
        for argv in (["launch_hook.py"], ["launch_hook.py", "hook_prompt.py"])
    ]
    records = [_attached(text or "", f"u{i}") for i, text in enumerate(texts)]
    assert all(texts)
    assert scan([_write(tmp_path / "s.jsonl", *records)], {}, PROMPT_HOOKS).firings == ()


def test_UserPromptSubmit_밖의_짝_없는_첨부는_조각이_맞아도_모름_알림으로_머리와_센다(
    tmp_path: Path,
) -> None:
    """다른 이벤트에서는 이 저장소의 훅이 `hook_success` 를 남겨 짝이 있으니, 짝 없는 첨부는 앱이
    넣은 글이다. 앱의 글에 든 낱말(경로의 `scratchpad`, 이벤트 이름)이 10자 조각과 맞아 그 훅의
    알림이나 여럿으로 세던 것을 셀프 리뷰가 이 PC의 기록에서 찾았다(일지 2026-10-23-19). 훅을 모두
    UserPromptSubmit 에 등록된 것으로 주어, 거르는 것이 이벤트임을 본다."""
    sources = {
        "hook_probe.py": 'PART = "scratchpad"\n',
        "hook_a.py": 'EVENT = "PostToolUse"\n',
        "hook_b.py": 'EVENT = "PostToolUse"\n',
    }
    prints = fingerprints(_tools(tmp_path, sources), list(sources))
    shown = "C:\\x\\scratchpad\\a.html is now visible in the Browser pane."
    modified = "PostToolUse hook modified C:\\x\\a.py"
    path = _write(
        tmp_path / "s.jsonl",
        _attached(shown, "u1", event="PostToolUse", tool="toolu_1"),
        _attached(modified, "u2", event="PostToolUse", tool="toolu_2"),
        _attached(
            "Also still to do in this turn:\n- x", "u3", event="SessionStart", tool="SessionStart"
        ),
    )
    firings = scan([path], prints, list(sources)).firings
    assert [(firing.hook, firing.kind, firing.head) for firing in firings] == [
        (UNKNOWN, NOTICE, shown),
        (UNKNOWN, NOTICE, modified),
        (UNKNOWN, NOTICE, "Also still to do in this turn:"),
    ]


def test_짝_없는_UserPromptSubmit_첨부는_그_이벤트에_등록된_훅의_조각과만_견준다(
    tmp_path: Path,
) -> None:
    """다른 이벤트의 훅이 더 긴 조각을 가져도 그 훅으로 세지 않고, 그 이벤트의 훅 조각이 없으면
    모름이다."""
    sources = {
        "hook_prompt.py": 'CONTEXT = "새 세션이다. 제목을"\n',
        "hook_post.py": f'REASON = "{ENV_REASON}"\n',
    }
    prints = fingerprints(_tools(tmp_path, sources), list(sources))
    path = _write(
        tmp_path / "s.jsonl",
        _attached(f"새 세션이다. 제목을 바꾼다. {ENV_REASON}", "u1"),
        _attached(f"앱 안내: {ENV_REASON}", "u2"),
    )
    firings = scan([path], prints, PROMPT_HOOKS).firings
    assert [firing.hook for firing in firings] == ["hook_prompt.py", UNKNOWN]


def test_못_보는_것_UserPromptSubmit에_든_다른_글도_그_이벤트_훅의_조각이_들면_그_훅으로_센다(
    tmp_path: Path,
) -> None:
    """짝 없는 첨부가 훅의 글인지는 조각으로만 가른다. 앱이 그 이벤트에 넣은 글이 있다면 그것도
    같다."""
    app = f"앱 안내: 앞 메시지가 '{PROMPT_NOTICE}' 를 받았다"
    assert _counts(_scan_prompt(tmp_path, _attached(app, "u1"))) == {("hook_prompt.py", NOTICE): 1}


@pytest.mark.parametrize(
    "stdout",
    [PROMPT_NOTICE, json.dumps({"systemMessage": PROMPT_NOTICE})],
    ids=["JSON_아님", "additionalContext_없음"],
)
def test_못_보는_것_stdout에_계기가_없으면_짝을_짓지_못해_첨부를_모름_알림으로도_센다(
    tmp_path: Path, stdout: str
) -> None:
    """이 저장소의 훅은 계기를 JSON 의 `additionalContext` 로 낸다. 맨 글 stdout 이 계기가 되는
    이벤트(SessionStart)의 훅이 생기면 그 알림은 `hook_success` 로 그 훅에, 첨부로 가르지 못한
    알림에 한 번씩 센다."""
    result = _scan_prompt(
        tmp_path,
        _notice("hook_prompt.py", stdout, "u1", event="SessionStart"),
        _attached(PROMPT_NOTICE, "u2", event="SessionStart", tool="SessionStart"),
    )
    assert _counts(result) == {("hook_prompt.py", NOTICE): 1, (UNKNOWN, NOTICE): 1}


def test_못_보는_것_같은_uuid의_짝_가운데_하나만_든_기록을_먼저_읽으면_첨부를_한_번_더_센다(
    tmp_path: Path,
) -> None:
    """같은 uuid 의 기록이 다른 세션 id 로 여러 기록 파일에 있다(2026-10-23 이 PC의 훅 첨부
    172개, 손으로 봤다). 같은 uuid 는 처음 읽은 것만 세므로, 앞 파일의 `hook_success` 가 다른
    세션의 열쇠로 들어가 뒤 파일의 첨부가 짝을 잃는다."""
    context = _context(PROMPT_NOTICE)
    copied = _write(tmp_path / "a.jsonl", _notice("hook_prompt.py", context, "u1", session="s2"))
    original = _write(
        tmp_path / "b.jsonl",
        _notice("hook_prompt.py", context, "u1"),
        _attached(PROMPT_NOTICE, "u2", event="PostToolUse"),
    )
    result = scan([copied, original], _prompt_prints(tmp_path), PROMPT_HOOKS)
    assert _counts(result) == {("hook_prompt.py", NOTICE): 1, (UNKNOWN, NOTICE): 1}


def test_model_context는_JSON의_additionalContext_글만_낸다() -> None:
    assert model_context(_context(PROMPT_NOTICE)) == PROMPT_NOTICE
    others = [
        PROMPT_NOTICE,
        "",
        "[1]",
        json.dumps({"systemMessage": PROMPT_NOTICE}),
        json.dumps({"hookSpecificOutput": {"additionalContext": 1}}),
    ]
    assert [model_context(stdout) for stdout in others] == [None] * len(others)


def test_등록된_훅은_launch_hook_명령에서_뽑고_다른_명령은_뺀다() -> None:
    def entry(command: str) -> dict[str, object]:
        return {"hooks": [{"type": "command", "command": command}]}

    settings = {
        "hooks": {
            "PreToolUse": [entry(LAUNCH + "hook_b.py"), entry(LAUNCH + "hook_a.py")],
            "Stop": [entry(LAUNCH + "hook_a.py")],
            "SessionStart": [entry("echo hi")],
        }
    }
    assert registered_hooks(json.dumps(settings)) == ["hook_a.py", "hook_b.py"]


def test_이벤트를_주면_그_이벤트에_등록된_훅만_뽑는다() -> None:
    def entry(hook: str) -> dict[str, object]:
        return {"hooks": [{"type": "command", "command": LAUNCH + hook}]}

    settings = {"hooks": {"UserPromptSubmit": [entry("hook_p.py")], "Stop": [entry("hook_s.py")]}}
    text = json.dumps(settings)
    assert registered_hooks(text, PROMPT_EVENT) == ["hook_p.py"]
    assert registered_hooks(text, "SessionStart") == []


def _firing(hook: str, kind: str, day: date) -> Firing:
    return Firing(hook, kind, day, "")


def test_표는_창_안의_알림과_막음을_훅마다_센다() -> None:
    result = Scan(
        (
            _firing("hook_a.py", NOTICE, date(2026, 10, 18)),
            _firing("hook_a.py", NOTICE, date(2026, 10, 18)),
            _firing("hook_a.py", BLOCK, date(2026, 10, 1)),
            _firing("hook_a.py", NOTICE, date(2026, 9, 1)),
            _firing("hook_gone.py", BLOCK, date(2026, 10, 2)),
        ),
        files=1,
        broken=0,
        earliest=date(2026, 9, 1),
    )
    out = render(result, ["hook_a.py"], {"hook_a.py": date(2026, 9, 1)}, TODAY, 28)
    assert "2026-09-22 ~ 2026-10-19" in out
    assert "| hook_a.py | 2 | 1 | 2 | 2026-10-18 |" in out
    assert "| hook_gone.py (등록 안 됨) | 0 | 1 | 1 | 2026-10-02 |" in out


def test_창보다_먼저_들였고_창_안에서_발동이_없는_훅을_뺄_후보로_적는다() -> None:
    result = Scan((_firing("hook_a.py", NOTICE, date(2026, 10, 18)),), 1, 0, date(2026, 9, 1))
    introduced = {
        "hook_a.py": date(2026, 9, 1),
        "hook_quiet.py": date(2026, 9, 1),
        "hook_young.py": date(2026, 10, 10),
    }
    out = render(result, ["hook_a.py", "hook_quiet.py", "hook_young.py"], introduced, TODAY, 28)
    lines = out.splitlines()
    candidates = next(line for line in lines if line.startswith("뺄 후보"))
    young = next(line for line in lines if line.startswith("아직 판단하지 않는 훅"))
    assert candidates == "뺄 후보: hook_quiet.py(2026-09-01 들임)"
    assert "hook_young.py(2026-10-10 들임)" in young


def test_들인_날을_모르는_훅은_후보에_넣지_않고_따로_적는다() -> None:
    out = render(Scan((), 1, 0, date(2026, 9, 1)), ["hook_new.py"], {}, TODAY, 28)
    assert "들인 날을 모르는 훅: hook_new.py" in out
    assert "뺄 후보: (없음)" in out


def test_가장_이른_기록이_창의_첫날보다_늦으면_앞쪽이_비었다고_적고_뺄_후보를_내지_않는다() -> None:
    """PR 직전 버그 축: 앞쪽이 빈 창에서도 조용한 훅을 모두 뺄 후보로 냈다."""
    result = Scan((), 1, 0, date(2026, 10, 1))
    out = render(result, ["hook_a.py"], {"hook_a.py": date(2026, 9, 1)}, TODAY, 28)
    assert "가장 이른 기록이 2026-10-01 이라 창의 앞 9일은 기록이 없다" in out
    assert "뺄 후보: 판정하지 않는다(창의 앞 9일에 기록이 없다" in out
    assert "hook_a.py(2026-09-01 들임)" not in out


def test_기록이_하나도_없으면_뺄_후보를_내지_않는다() -> None:
    """PR 직전 버그 축: 틀린 `--projects`·`--repo` 에서 등록 훅이 모두 뺄 후보로 나왔다."""
    out = render(Scan((), 0, 0, None), ["hook_a.py"], {"hook_a.py": date(2026, 9, 1)}, TODAY, 28)
    assert "뺄 후보: 판정하지 않는다(기록이 없다" in out
    assert "hook_a.py(2026-09-01 들임)" not in out


def test_모름과_여럿으로_센_막음은_이유의_머리와_함께_적는다() -> None:
    result = Scan(
        (
            Firing(UNKNOWN, BLOCK, date(2026, 10, 18), "플러그인이 막았다"),
            Firing(UNKNOWN, BLOCK, date(2026, 10, 18), "플러그인이 막았다"),
            Firing(AMBIGUOUS, BLOCK, date(2026, 10, 18), "같은 문장"),
        ),
        1,
        0,
        date(2026, 9, 1),
    )
    out = render(result, [], {}, TODAY, 28)
    assert f"| {UNKNOWN}" not in out
    assert f"| {AMBIGUOUS}" not in out
    assert "어느 훅인지 가르지 못한 막음 3건" in out
    assert "2건 (모름) 플러그인이 막았다" in out
    assert "1건 (여럿) 같은 문장" in out


def test_가르지_못한_알림은_막음과_따로_글의_머리와_함께_적는다() -> None:
    result = Scan(
        (
            Firing(UNKNOWN, NOTICE, date(2026, 10, 18), "Also still to do in this turn:"),
            Firing(UNKNOWN, BLOCK, date(2026, 10, 18), "플러그인이 막았다"),
        ),
        1,
        0,
        date(2026, 9, 1),
    )
    lines = render(result, [], {}, TODAY, 28).splitlines()
    notices = lines.index("어느 훅인지 가르지 못한 알림 1건(글의 머리마다):")
    blocks = lines.index("어느 훅인지 가르지 못한 막음 1건(이유의 머리마다):")
    assert lines[notices + 1] == "  1건 (모름) Also still to do in this turn:"
    assert lines[blocks + 1] == "  1건 (모름) 플러그인이 막았다"
    assert f"| {UNKNOWN}" not in "\n".join(lines)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/hook_report.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )


def _registration(hooks: list[str]) -> list[Record]:
    """훅마다 래퍼 모양의 명령 하나를 든 settings.json 의 이벤트 칸."""
    return [{"hooks": [{"type": "command", "command": LAUNCH + hook} for hook in hooks]}]


def _hook_repository(root: Path, hooks: list[str], prompt: dict[str, str] | None = None) -> None:
    """`hooks` 를 PostToolUse 에, `prompt`(훅 이름과 그 소스)를 UserPromptSubmit 에 래퍼 모양으로
    등록하고 2026-09-01 에 커밋한 임시 저장소."""
    prompt = prompt or {}
    _tools(root, {**dict.fromkeys(hooks, ""), **prompt})
    events = {"PostToolUse": _registration(hooks), PROMPT_EVENT: _registration(list(prompt))}
    (root / ".claude").mkdir()
    settings = json.dumps({"hooks": events})
    (root / ".claude" / "settings.json").write_text(settings, encoding="utf-8")
    _git(root, "init", "-q")
    _commit(root, "2026-09-01")


def _commit(root: Path, day: str) -> None:
    """작업 트리 전부를 `day` 의 커밋 날짜로 커밋한다."""
    _git(root, "add", "-A")
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", day],
        cwd=root,
        check=True,
        capture_output=True,
        env={**hook_environment(), "GIT_COMMITTER_DATE": f"{day}T00:00:00Z"},
    )


def test_워크트리에서도_주_체크아웃의_기록_폴더_이름을_짓는다(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    _hook_repository(main, [])
    _git(main, "worktree", "add", "-q", str(tmp_path / "wt"))
    folder = main_checkout_folder(main)
    assert folder.endswith("-main")
    assert main_checkout_folder(tmp_path / "wt") == folder


def test_지웠다가_다시_들인_훅은_다시_들인_날부터_센다(tmp_path: Path) -> None:
    _hook_repository(tmp_path, ["hook_a.py", "hook_b.py"])
    (tmp_path / "tools" / "hook_a.py").unlink()
    _commit(tmp_path, "2026-09-05")
    (tmp_path / "tools" / "hook_a.py").write_text("", encoding="utf-8")
    _commit(tmp_path, "2026-10-10")
    assert introduced_dates(tmp_path, ["hook_a.py", "hook_b.py", "hook_new.py"]) == {
        "hook_a.py": date(2026, 10, 10),
        "hook_b.py": date(2026, 9, 1),
    }


def test_못_보는_것_이름을_바꾼_훅은_새_이름을_더한_날부터_센다(tmp_path: Path) -> None:
    _hook_repository(tmp_path, ["hook_old.py"])
    source = 'REASON = "이름을 바꿔도 같은 훅이다"\n'
    (tmp_path / "tools" / "hook_old.py").write_text(source, encoding="utf-8")
    _commit(tmp_path, "2026-09-02")
    _git(tmp_path, "mv", "tools/hook_old.py", "tools/hook_renamed.py")
    _commit(tmp_path, "2026-10-10")
    assert introduced_dates(tmp_path, ["hook_renamed.py"]) == {
        "hook_renamed.py": date(2026, 10, 10)
    }


def test_main을_실제로_불러_임시_저장소의_표와_뺄_후보를_찍는다(tmp_path: Path) -> None:
    """UserPromptSubmit 훅의 행은 `main` 이 그 이벤트의 훅을 `scan` 에 넘기는 배선을 지킨다(harness
    005 PR 직전 버그 축. 넘기지 않으면 그 훅이 다시 뺄 후보로 나온다)."""
    root = tmp_path / "repo"
    prompt = {"hook_prompt.py": f'CONTEXT = "{PROMPT_NOTICE}"\n'}
    _hook_repository(root, ["hook_a.py", "hook_quiet.py"], prompt)
    projects = tmp_path / "projects"
    _write(
        projects / "R" / "s.jsonl",
        _notice("hook_a.py", "", "u0", "2026-09-20T00:00:00.000Z"),  # 창 앞의 기록
        _notice("hook_a.py", _context("고쳐라"), "u1"),
        _attached(PROMPT_NOTICE, "u2"),
    )
    done = _run(
        *("--projects", str(projects), "--repo", "R"),
        *("--root", str(root), "--today", "2026-10-19"),
    )
    assert done.returncode == 0, done.stderr
    assert "| hook_a.py | 1 | 0 | 1 | 2026-10-18 |" in done.stdout
    assert "| hook_prompt.py | 1 | 0 | 1 | 2026-10-18 |" in done.stdout
    assert "뺄 후보: hook_quiet.py(2026-09-01 들임)" in done.stdout


def test_main은_인자가_틀리면_까닭을_내고_2로_끝난다() -> None:
    days = _run("--days", "0")
    assert days.returncode == 2
    assert "양의 정수다: 0" in days.stderr
    today = _run("--today", "어제")
    assert today.returncode == 2
    assert "날짜는 YYYY-MM-DD다: 어제" in today.stderr
    # PR 직전 버그 축: 기록을 다 읽은 뒤 창을 계산하다 OverflowError 트레이스백으로 끝났다
    wide = _run("--days", "99999999")
    assert wide.returncode == 2
    assert "창이 날짜의 범위를 넘는다" in wide.stderr


def test_main은_settings를_읽지_못하면_2로_끝난다(tmp_path: Path) -> None:
    done = _run("--projects", str(tmp_path), "--repo", "R", "--root", str(tmp_path))
    assert done.returncode == 2
    assert "settings.json" in done.stderr


def test_이_저장소의_등록_훅을_스물넷_이상_읽고_모두_tools에_있다() -> None:
    """문턱은 rag-engine 킥오프(2026-11-09)에 등록한 훅의 수다(agent-os 는 `> 20`)."""
    hooks = registered_hooks((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert len(hooks) >= 24
    assert [hook for hook in hooks if not (ROOT / "tools" / hook).is_file()] == []


def test_이_저장소의_막는_사례마다_훅이_낸_이유를_그_훅으로_센다(tmp_path: Path) -> None:
    """훅 페이로드 표에서 훅마다 처음 나오는 deny·block 사례를 실제로 돌려, 그 이유를 이 도구가
    그 훅으로 세는지 본다. 막는 훅을 새로 들이거나 이유를 바꿔 조각이 겹치거나 짧아지면 여기서
    빨개진다. 커밋이 도는 동안만 있는 자리표시자(`${COMMITTING_REPO}`)와 `env` 를 쓰는 사례는
    빼고, 남은 사례가 막는 훅 열세 개 이상을 덮는지 단언한다. 문턱은 rag-engine 킥오프
    (2026-11-09)에 그 조건으로 걸린 막는 훅의 수다(agent-os 는 열 개)."""
    hooks = registered_hooks((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    prints = fingerprints(ROOT / "tools", hooks)
    replacements = create_fixtures(tmp_path)
    seen: set[str] = set()
    wrong: list[str] = []
    for case in load_cases():
        blocking = case.expect in ("deny", "block")
        skipped = case.env or "COMMITTING_REPO" in str(case.payload)
        if not blocking or skipped or case.hook in seen:
            continue
        seen.add(case.hook)
        done = subprocess.run(
            [sys.executable, str(ROOT / "tools" / case.hook)],
            input=json.dumps(substitute(case.payload, replacements)).encode("utf-8"),
            capture_output=True,
            env=hook_environment(),
            cwd=ROOT,
            check=False,
            timeout=120,
        )
        stdout = done.stdout.decode("utf-8", "replace")
        reason = message_of(done.returncode, stdout, done.stderr.decode("utf-8", "replace"))
        counted = fragment_owner(reason, prints)
        if counted != case.hook:
            wrong.append(f"{case.hook} ({case.note}) → {counted}: {reason[:80]}")
    assert wrong == []
    assert len(seen) >= 13


def test_이_저장소의_UserPromptSubmit_훅의_계기_사례마다_그_글을_그_훅으로_센다(
    tmp_path: Path,
) -> None:
    """UserPromptSubmit 의 계기는 `hook_success` 없이 명령 없는 첨부로만 남아 조각으로 훅을
    가른다(대기열 404). 훅 페이로드 표에서 그 이벤트의 훅이 계기를 내는 사례를 모두 실제로 돌려,
    그 글을 짝 없는 첨부로 넣은 기록을 이 도구가 그 훅으로 세는지 본다. 계기 글을 훅 파일 밖의
    글로만 짓거나 그 이벤트의 다른 훅 조각과 겹치면 여기서 빨개진다. `env` 를 쓰는 사례는 뺀다.
    문턱은 rag-engine 킥오프(2026-11-09)에 `hook_prompt_directive` 가 계기를 내는 사례의 수다
    (agent-os 는 하나 이상)."""
    settings = (ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    prompt_hooks = registered_hooks(settings, PROMPT_EVENT)
    prints = fingerprints(ROOT / "tools", registered_hooks(settings))
    replacements = create_fixtures(tmp_path)
    ran = 0
    wrong: list[str] = []
    for case in load_cases():
        if case.hook not in prompt_hooks or case.expect != "context" or case.env:
            continue
        done = subprocess.run(
            [sys.executable, str(ROOT / "tools" / case.hook)],
            input=json.dumps(substitute(case.payload, replacements)).encode("utf-8"),
            capture_output=True,
            env=hook_environment(),
            cwd=ROOT,
            check=False,
            timeout=120,
        )
        text = model_context(done.stdout.decode("utf-8", "replace")) or ""
        ran += 1
        path = _write(tmp_path / f"case{ran}.jsonl", _attached(text, f"u{ran}"))
        counted = [firing.hook for firing in scan([path], prints, prompt_hooks).firings]
        if counted != [case.hook]:
            wrong.append(f"{case.hook} ({case.note}) → {counted}: {text[:80]}")
    assert wrong == []
    assert ran >= 6
