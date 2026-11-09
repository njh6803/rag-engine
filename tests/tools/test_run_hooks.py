"""tools/run_hooks.py — 판정·표 읽기·빈자리 셈은 순수 함수로, 배관은 실제 훅 하나로 잰다.

표의 빈자리(등록과 표가 한쪽에만 있는 훅, 발동·침묵 한쪽이 없는 훅)는 러너가 스스로 센다. 여기서는
이 저장소가 지금 빈자리 0인 것과 빈자리를 만들면 잡히는 것을 한 쌍으로 둔다(tests.md). 등록 쪽을
빼는 변이와 표 쪽을 빼는 변이가 각각 하나다.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import get_args

import pytest
import tools.run_hooks as run_hooks_module
from pydantic import JsonValue
from tools.hook_prompt_directive import HEADLESS_MARKER
from tools.run_hooks import (
    PAYLOADS,
    ROOT,
    Case,
    Expectation,
    NoticeResult,
    Registration,
    coverage_gaps,
    create_fixtures,
    expected_notice,
    fixtures,
    hook_environment,
    launch_argv,
    load_cases,
    message_of,
    missing_fragments,
    notice_outcome,
    outcome_of,
    registered_hooks,
    registered_matchers,
    registration_command,
    run_case,
    run_notices,
    substitute,
)


def _specific(**fields: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **fields}})


def test_종료_코드와_출력을_기대로_읽는다() -> None:
    """notice 는 `test_사용자에게만_가는_systemMessage_는_notice_다` 가 본다."""
    deny = _specific(permissionDecision="deny", permissionDecisionReason="x")
    context = _specific(additionalContext="retro")
    assert outcome_of(0, deny, "PreToolUse") == "deny"
    assert outcome_of(0, context, "PreToolUse") == "context"
    block = json.dumps({"decision": "block", "reason": "x"})
    assert outcome_of(0, block, "UserPromptSubmit") == "block"
    assert outcome_of(2, "이유", "PreToolUse") == "block"
    assert outcome_of(0, "", "PreToolUse") == "silent"
    assert outcome_of(0, "   \n", "PreToolUse") == "silent"


def test_기대_밖의_결과는_그대로_설명한다() -> None:
    """트레이스백(종료 1, stderr 만)과 JSON 아닌 출력은 기대와 어긋나는 것으로 보인다."""
    assert outcome_of(1, "", "PreToolUse") == "exit 1"
    assert outcome_of(0, "not json", "PreToolUse") == "output"
    assert outcome_of(0, "[1, 2]", "PreToolUse") == "output"
    assert outcome_of(0, _specific(), "PreToolUse") == "output"


def test_hookEventName_이_없거나_등록된_이벤트와_다르면_어긋남이다() -> None:
    """hookEventName 이 없거나 다른 hookSpecificOutput 은 Claude Code 가 받지 않는다."""
    without_event = json.dumps({"hookSpecificOutput": {"permissionDecision": "deny"}})
    assert outcome_of(0, without_event, "PreToolUse") == "output"
    assert outcome_of(0, _specific(permissionDecision="deny"), "PostToolUse") == "event PreToolUse"


def test_자리표시자는_표_안까지_바꾼다() -> None:
    payload: dict[str, JsonValue] = {
        "tool_input": {"command": "cat ${ROOT}/x"},
        "cwd": "${MAIN_REPO}",
        "n": 1,
        "l": ["${ROOT}"],
    }

    assert substitute(payload, {"ROOT": "/r", "MAIN_REPO": "/m"}) == {
        "tool_input": {"command": "cat /r/x"},
        "cwd": "/m",
        "n": 1,
        "l": ["/r"],
    }


def test_표의_기대는_Expectation_의_값이어야_한다(tmp_path: Path) -> None:
    table = tmp_path / "t.toml"
    table.write_text(
        '[[case]]\nhook = "hook_env_read.py"\nexpect = "warn"\npayload = { tool_name = "Bash" }\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expect"):
        load_cases(table)


def _docstring_placeholders(docstring: str) -> set[str]:
    """러너 독스트링의 자리표시자 문단(`자리표시자 —` 부터 사례의 `env` 문장 앞까지)이 드는 이름.

    문단 밖의 `${CLAUDE_PROJECT_DIR}`(등록 명령의 전개)는 러너가 채우는 값이 아니라 뺀다.
    """
    head, tail = "자리표시자 —", "`env` 는 자리표시자를 바꾼 뒤"
    assert head in docstring, f"독스트링에 자리표시자 문단의 머리({head})가 없다"
    assert tail in docstring, f"독스트링에 자리표시자 문단의 끝({tail})이 없다"
    start, end = docstring.index(head), docstring.index(tail)
    return set(re.findall(r"\$\{([A-Z0-9_]+)\}", docstring[start:end]))


def test_이_저장소의_러너_독스트링은_자리표시자와_같은_집합을_든다(tmp_path: Path) -> None:
    """수 낱말을 두 PR 이 같이 고쳐 실제와 어긋난 채 합쳐졌다(대기열 245). 수 대신 집합을 견준다."""
    with fixtures(tmp_path) as values:
        keys = set(values)

    assert keys, "자리표시자가 하나도 없다. fixtures 를 잘못 읽었다"
    assert _docstring_placeholders(run_hooks_module.__doc__ or "") == keys


def test_독스트링에서_자리표시자_하나를_빼면_잡는다() -> None:
    docstring = run_hooks_module.__doc__ or ""
    trimmed = docstring.replace("`${KOREAN_HEREDOC_45}`", "`KOREAN_HEREDOC_45`")

    assert "KOREAN_HEREDOC_45" in _docstring_placeholders(docstring)
    assert "KOREAN_HEREDOC_45" not in _docstring_placeholders(trimmed)


def _table_expectations(table: str) -> tuple[str, ...]:
    """표 머리의 `# 기대:` 줄에서 첫 마침표 앞의 `|` 로 가른 값."""
    (line,) = [line for line in table.splitlines() if line.startswith("# 기대:")]
    head = line.removeprefix("# 기대:").split(".", 1)[0]
    return tuple(part.strip() for part in head.split("|"))


def test_이_저장소의_표_머리의_기대는_러너의_기대와_같다() -> None:
    """`notice` 를 더하며 러너만 고쳐 표 머리가 넷으로 남은 것을 PR 직전 리뷰가 잡았다(대기열
    311)."""
    table = PAYLOADS.read_text(encoding="utf-8")

    assert _table_expectations(table) == get_args(Expectation)


def test_표_머리의_기대에서_하나를_빼면_잡는다() -> None:
    table = "# 기대: deny | block | context | silent. notice 는 …\n"

    assert _table_expectations(table) != get_args(Expectation)


def test_침묵_사례에는_찾을_문장이_없어_contains_를_받지_않는다(tmp_path: Path) -> None:
    table = tmp_path / "t.toml"
    table.write_text(
        '[[case]]\nhook = "hook_env_read.py"\nexpect = "silent"\ncontains = ["x"]\n'
        'payload = { tool_name = "Bash" }\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="contains"):
        load_cases(table)


def _fake_root(tmp_path: Path, output: dict[str, JsonValue]) -> Path:
    """래퍼 사본과 `output` 을 내는 가짜 훅을 `tools/` 에 둔 루트. 러너는 등록의 모양 그대로 이
    루트의 래퍼를 띄우고, 래퍼는 자기 옆의 훅을 돌린다. `output` 이 비면 아무것도 내지 않는다."""
    root = tmp_path / "fake-root"
    (root / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "launch_hook.py", root / "tools")
    text = json.dumps(output) if output else ""
    (root / "tools" / "hook_fake_notice.py").write_text(
        f"import sys\n\nsys.stdout.write({text!r})\n", encoding="utf-8"
    )
    return root


_NOTICE_TABLE = (
    '[[case]]\nhook = "hook_fake_notice.py"\nexpect = "notice"\ncontains = ["턴이 끝났다"]\n'
    'payload = { hook_event_name = "Stop" }\n'
)


@pytest.mark.parametrize(
    ("output", "outcome", "missing"),
    [
        ({"systemMessage": "턴이 끝났다"}, "notice", ()),
        (
            {
                "systemMessage": "턴이 끝났다",
                "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "턴이 끝났다"},
            },
            "context",
            (),
        ),
        ({}, "silent", ("턴이 끝났다",)),
    ],
    ids=["systemMessage_하나", "additionalContext_도", "출력_없음"],
)
def test_표의_notice_사례는_사용자에게만_가는_systemMessage_하나를_낸_훅에서만_맞는다(
    tmp_path: Path, output: dict[str, JsonValue], outcome: str, missing: tuple[str, ...]
) -> None:
    """표를 읽고(`load_cases`) 래퍼로 띄워 대조하는(`run_case`) 길이다. 판정 함수(`outcome_of`)는
    이 길이 notice 를 받기 전에도 notice 를 냈다. 모델에게도 가는 additionalContext 가 함께 있으면
    context 다. 맞는 갈래의 조각은 systemMessage 에만 있다."""
    root = _fake_root(tmp_path, output)
    table = tmp_path / "t.toml"
    table.write_text(_NOTICE_TABLE, encoding="utf-8")

    [case] = load_cases(table, root)
    result = run_case(case, {}, Registration("Stop", 20), root)

    assert (result.outcome, result.missing) == (outcome, missing)
    assert result.ok is (outcome == "notice")


def test_훅이_내는_문장은_JSON_을_풀어_읽고_종료_2_면_stderr_다() -> None:
    """훅은 `json.dumps` 의 기본값으로 한글을 이스케이프해 낸다. 날것 stdout 에서는 찾지 못한다."""
    deny = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "`.env` 는 비밀이다",
            }
        }
    )
    context = json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "회고를 돈다"}}
    )
    block = json.dumps({"decision": "block", "reason": "한국어로 답한다"})

    assert "비밀" not in deny
    assert "`.env` 는 비밀이다" in message_of(0, deny, "")
    assert "회고를 돈다" in message_of(0, context, "")
    assert "한국어로 답한다" in message_of(0, block, "")
    assert message_of(2, "", "막는 이유\n") == "막는 이유\n"
    assert message_of(0, "not json", "") == ""


def test_찾을_문장_가운데_훅의_문장에_없는_것을_돌려준다() -> None:
    assert missing_fragments(
        "tidy-checkouts 를 먼저 돈다", ["tidy-checkouts", "EnterWorktree"]
    ) == ["EnterWorktree"]
    assert missing_fragments("아무 문장", []) == []


def test_기대한_판정이어도_찾을_문장이_빠지면_어긋남이다(tmp_path: Path) -> None:
    """옛 훅도 같은 종류의 결과를 내면 판정만으로는 새 동작을 가르지 못한다(대기열 130)."""
    replacements = create_fixtures(tmp_path)
    registration = Registration("PreToolUse", 20)
    payload: dict[str, JsonValue] = {"tool_name": "Bash", "tool_input": {"command": "cat .env"}}
    found = Case(hook="hook_env_read.py", expect="deny", payload=payload, contains=[".env.example"])
    absent = Case(hook="hook_env_read.py", expect="deny", payload=payload, contains=["없는 문구"])

    found_result = run_case(found, replacements, registration)
    absent_result = run_case(absent, replacements, registration)

    assert found_result.ok
    assert absent_result.outcome == "deny"
    assert absent_result.missing == ("없는 문구",)
    assert not absent_result.ok


def test_표가_가리키는_훅_파일은_있어야_한다(tmp_path: Path) -> None:
    table = tmp_path / "t.toml"
    table.write_text(
        '[[case]]\nhook = "hook_없다.py"\nexpect = "deny"\npayload = { tool_name = "Bash" }\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="없다"):
        load_cases(table)


def _settings(hooks: dict[str, list[dict[str, JsonValue]]]) -> str:
    groups = {event: [{"hooks": entries}] for event, entries in hooks.items()}
    return json.dumps({"hooks": groups})


# 등록 모양의 글자는 test_러너가_띄우는_인자는_… 가 인자 목록으로 고정한다. 여기서는 그 원천을 쓴다.
_REGISTERED_X = registration_command("hook_x.py")


def test_등록은_이벤트와_시간_제한이고_시간_제한이_없으면_Claude_Code_기본값이다(
    tmp_path: Path,
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(
        _settings({"PreToolUse": [{"command": _REGISTERED_X, "timeout": 20}]}), encoding="utf-8"
    )
    assert registered_hooks(settings) == {"hook_x.py": Registration("PreToolUse", 20)}

    settings.write_text(_settings({"PostToolUse": [{"command": _REGISTERED_X}]}), encoding="utf-8")
    assert registered_hooks(settings) == {"hook_x.py": Registration("PostToolUse", 60)}


def test_훅_하나가_이벤트_둘에_등록되면_거절한다(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    entry: dict[str, JsonValue] = {"command": _REGISTERED_X}
    settings.write_text(
        _settings({"PreToolUse": [entry], "PostToolUse": [entry]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="둘에 등록"):
        registered_hooks(settings)


def test_래퍼를_거치지_않거나_모양이_다른_등록은_거절한다(tmp_path: Path) -> None:
    """옛 모양은 훅 파일이 없으면 2로 끝나 PreToolUse 면 그 매처의 모든 호출을 막았다(대기열 91).

    `--project` 가 빠지면 저장소 밖에서 시스템 파이썬으로 돈다(KICKOFF.md 하네스 런타임).
    """
    settings = tmp_path / "settings.json"
    commands = [
        'uv run --project "${CLAUDE_PROJECT_DIR}" --no-sync python'
        ' "${CLAUDE_PROJECT_DIR}/tools/hook_x.py"',
        'uv run --no-sync python "${CLAUDE_PROJECT_DIR}/tools/launch_hook.py" hook_x.py',
        _REGISTERED_X.replace("hook_x.py", "tools/hook_x.py"),
        _REGISTERED_X + " --flag",
    ]
    for command in commands:
        settings.write_text(_settings({"PreToolUse": [{"command": command}]}), encoding="utf-8")

        with pytest.raises(ValueError, match="등록 모양"):
            registered_hooks(settings)


def test_훅_이름과_이벤트로_등록의_매처를_돌려준다(tmp_path: Path) -> None:
    """매처가 없는 묶음은 빈 문자열이다. 그 이벤트에 등록되지 않은 훅은 빈 목록이다(대기열 216)."""
    settings = tmp_path / "settings.json"
    entry: dict[str, JsonValue] = {"command": _REGISTERED_X}
    other: dict[str, JsonValue] = {"command": registration_command("hook_y.py")}
    groups: dict[str, JsonValue] = {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [entry, other]},
            {"matcher": "Grep", "hooks": [other]},
            {"hooks": [entry]},
        ]
    }
    settings.write_text(json.dumps({"hooks": groups}), encoding="utf-8")

    assert registered_matchers("hook_x.py", "PreToolUse", settings) == ["Bash", ""]
    assert registered_matchers("hook_y.py", "PreToolUse", settings) == ["Bash", "Grep"]
    assert registered_matchers("hook_z.py", "PreToolUse", settings) == []
    assert registered_matchers("hook_x.py", "PostToolUse", settings) == []


def test_러너가_띄우는_인자는_등록_명령에서_루트만_바꾼_것이다() -> None:
    root = Path("/r o/agent")

    assert launch_argv("hook_x.py", root) == [
        "uv",
        "run",
        "--project",
        "/r o/agent",
        "--no-sync",
        "python",
        "/r o/agent/tools/launch_hook.py",
        "hook_x.py",
    ]


def test_루트의_따옴표는_인자를_가르지_않고_경로에_남는다() -> None:
    """셸의 `"${CLAUDE_PROJECT_DIR}"` 전개는 경로 속 따옴표를 글자로 남긴다(PR #121 CodeRabbit)."""
    argv = launch_argv("hook_x.py", Path('/r"o/agent'))

    assert argv[3] == '/r"o/agent'
    assert argv[6] == '/r"o/agent/tools/launch_hook.py'
    assert len(argv) == 8


def _case(hook: str, expect: str) -> Case:
    return Case.model_validate({"hook": hook, "expect": expect, "payload": {}})


def test_등록과_표의_빈자리를_센다() -> None:
    """표에 없는 훅, 등록되지 않은 훅, 침묵만 있는 훅, 발동만 있는 훅이 각각 한 줄이다."""
    cases = [
        _case("hook_env_read.py", "deny"),
        _case("hook_env_read.py", "silent"),
        _case("hook_bash_heredoc.py", "silent"),
        _case("hook_bash_gate_pipe.py", "context"),
        _case("hook_prompt_directive.py", "context"),
        _case("hook_prompt_directive.py", "silent"),
    ]
    registered = {
        "hook_env_read.py",
        "hook_bash_heredoc.py",
        "hook_bash_gate_pipe.py",
        "hook_journal_retro.py",
    }

    assert coverage_gaps(cases, registered) == [
        "hook_bash_gate_pipe.py: 침묵 사례가 없다",
        "hook_bash_heredoc.py: 발동 사례가 없다",
        "hook_journal_retro.py: 등록됐는데 표에 없다",
        "hook_prompt_directive.py: 표에 있는데 등록되지 않았다",
    ]


def test_빈자리_셈은_notice_를_발동으로_센다() -> None:
    """사용자에게만 알리는 훅도 notice 사례를 발동으로 둔다."""
    cases = [
        _case("hook_notice_and_silent.py", "notice"),
        _case("hook_notice_and_silent.py", "silent"),
        _case("hook_notice_only.py", "notice"),
    ]
    registered = {"hook_notice_and_silent.py", "hook_notice_only.py"}

    assert coverage_gaps(cases, registered) == ["hook_notice_only.py: 침묵 사례가 없다"]


def test_이_저장소의_표는_등록된_훅마다_발동과_침묵이_있다() -> None:
    registered = registered_hooks()

    assert registered
    assert coverage_gaps(load_cases(PAYLOADS), registered) == []


def test_이_저장소의_표에서_contains_를_단_사례는_지금_훅의_문장에_조각이_모두_있다(
    tmp_path: Path,
) -> None:
    """pre-commit 의 러너가 모든 사례를 돌리지만, 조각을 단 사례만 여기서도 돌려 변이가 겨눌 자리를
    둔다. 조각을 단 사례가 없으면 범위가 빈 것이라 실패한다."""
    cases = [case for case in load_cases(PAYLOADS) if case.contains]
    registrations = registered_hooks()

    with fixtures(tmp_path) as replacements:
        results = [run_case(case, replacements, registrations[case.hook]) for case in cases]

    assert cases
    assert [(r.case.note, r.outcome, r.missing) for r in results if not r.ok] == []


def test_등록된_훅을_표에서_빼면_빈자리를_잡는다() -> None:
    cases = [case for case in load_cases(PAYLOADS) if case.hook != "hook_env_read.py"]

    assert coverage_gaps(cases, registered_hooks()) == ["hook_env_read.py: 등록됐는데 표에 없다"]


def test_표의_훅을_등록에서_빼면_빈자리를_잡는다() -> None:
    """settings.json 에서 등록만 지우고 파일과 사례를 남기면 실제 세션에는 그 훅이 없다."""
    registered = {hook for hook in registered_hooks() if hook != "hook_env_read.py"}

    assert coverage_gaps(load_cases(PAYLOADS), registered) == [
        "hook_env_read.py: 표에 있는데 등록되지 않았다"
    ]


def test_자식_환경은_러너를_띄운_세션의_entrypoint_를_물려주지_않는다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stop 훅(hook_stop_korean)은 SDK 세션에서 침묵한다. 러너가 SDK 세션 안에서 돌면 그 값을
    물려받아 발동 사례가 침묵으로 어긋난다. 판정이 러너를 띄운 자리에 기대지 않게 한다.
    """
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-py")

    # 키만 본다. 환경 전체를 단언하면 실패 출력에 값(토큰일 수 있다)이 찍힌다.
    assert "CLAUDE_CODE_ENTRYPOINT" not in hook_environment().keys()


def test_자식_환경은_러너를_띄운_세션이_클라우드인지_물려주지_않는다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`hook_worktree_skill_overrides` 는 클라우드 세션에서 쓰지 않는다. 러너가 클라우드 세션
    안에서 돌면 그 값을 물려받아 로컬 사례가 침묵으로 어긋난다. 클라우드 사례는 표의 `env` 가 값을
    준다.
    """
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")

    assert "CLAUDE_CODE_REMOTE" not in hook_environment().keys()


def test_자식_환경은_러너를_띄운_세션이_헤드리스인지_물려주지_않는다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`hook_prompt_directive` 는 `CLAUDE_CODE_SESSION_ATTENDED` 가 `0` 이거나 헤드리스 표지가 있는
    세션에 첫 턴 티켓 알림을 내지 않는다. `claude -p` 세션의 커밋에서 러너가 그 값을 물려받으면
    발동 사례가 침묵으로 어긋난다.
    """
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ATTENDED", "0")
    monkeypatch.setenv(HEADLESS_MARKER, "1")

    assert "CLAUDE_CODE_SESSION_ATTENDED" not in hook_environment().keys()
    assert HEADLESS_MARKER not in hook_environment().keys()


def test_실제_훅_하나를_페이로드로_돌려_판정한다(tmp_path: Path) -> None:
    """배관(uv run 자식, 바이트 stdin, PYTHONUTF8 없는 환경)을 한 번은 실제로 본다."""
    replacements = create_fixtures(tmp_path)
    registration = Registration("PreToolUse", 20)
    deny = Case(
        hook="hook_env_read.py",
        expect="deny",
        payload={"tool_name": "Bash", "tool_input": {"command": "cat .env"}},
    )
    silent = Case(
        hook="hook_env_read.py",
        expect="silent",
        payload={"tool_name": "Bash", "tool_input": {"command": "ls"}},
    )

    assert run_case(deny, replacements, registration).ok
    assert run_case(silent, replacements, registration).ok
    assert (tmp_path / "on-main" / ".git").is_dir()
    assert (tmp_path / "transcript-used.jsonl").is_file()


def test_사례의_env_는_자리표시자를_바꿔_자식_환경을_덧씌운다(tmp_path: Path) -> None:
    """`CLAUDE_PROJECT_DIR` 과 `CLAUDE_CODE_REMOTE` 를 보는 PostToolUse 훅의 판정을 사례가 정한다.
    훅이 `${WORKTREE_SKILLS_REPO}` 로 바뀐 `CLAUDE_PROJECT_DIR` 을 읽어야 그 폴더의 워크트리 스킬을
    본다. 같은 진입에 클라우드 표지를 더하면 쓰지 않는다. agent-os 에서는 같은 것을 SessionStart 훅
    `hook_session_web_deps` 로 쟀고, rag-engine 은 그 훅을 복사하지 않아 남은 훅으로 옮겼다.
    """
    replacements = create_fixtures(tmp_path)
    registration = Registration("PostToolUse", 20)
    side = "${WORKTREE_SKILLS_REPO}/.claude/worktrees/side"
    payload: dict[str, JsonValue] = {
        "session_id": "run-hooks-env",
        "cwd": side,
        "hook_event_name": "PostToolUse",
        "tool_name": "EnterWorktree",
        "tool_input": {"path": side},
        "tool_response": {"worktreePath": side, "worktreeBranch": "side"},
    }
    project = {"CLAUDE_PROJECT_DIR": "${WORKTREE_SKILLS_REPO}"}
    cloud = Case(
        hook="hook_worktree_skill_overrides.py",
        expect="silent",
        payload=payload,
        env={**project, "CLAUDE_CODE_REMOTE": "true"},
    )
    local = Case(
        hook="hook_worktree_skill_overrides.py",
        expect="notice",
        payload=payload,
        env=project,
        contains=["스킬 사본 2개"],
    )

    assert run_case(cloud, replacements, registration).ok
    assert run_case(local, replacements, registration).ok
    written = Path(replacements["WORKTREE_SKILLS_REPO"]) / ".claude" / "settings.local.json"
    assert written.is_file()


def test_중간_문장_트랜스크립트는_영어_뒤의_첫_호출에서만_알림을_낸다(tmp_path: Path) -> None:
    """`${MIDTURN_TRANSCRIPT}` 가 표의 세 사례를 실제로 가르는지 본다(대기열 94)."""
    replacements = create_fixtures(tmp_path)
    registration = Registration("PreToolUse", 20)

    def case(tool_use_id: str, expect: Expectation) -> Case:
        payload: dict[str, JsonValue] = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "transcript_path": "${MIDTURN_TRANSCRIPT}",
        }
        return Case(hook="hook_midturn_korean.py", expect=expect, payload=payload)

    assert run_case(case("toolu_english", "context"), replacements, registration).ok
    assert run_case(case("toolu_sibling", "silent"), replacements, registration).ok
    assert run_case(case("toolu_korean", "silent"), replacements, registration).ok


def test_러너도_등록처럼_래퍼로_띄워_없는_훅은_알림이다(tmp_path: Path) -> None:
    """훅을 바로 띄우면 파이썬이 2로 끝나 block 으로 읽힌다. 세션이 띄우는 모양과 같아야 한다."""
    replacements = create_fixtures(tmp_path)
    case = Case(
        hook="hook_없다.py",
        expect="context",
        payload={"hook_event_name": "PreToolUse", "tool_name": "Bash"},
    )

    result = run_case(case, replacements, Registration("PreToolUse", 20))

    assert result.outcome == "context"


def test_사용자에게만_가는_systemMessage_는_notice_다() -> None:
    """표의 훅이 사람에게만 알릴 때와, 래퍼가 Stop 처럼 additionalContext 를 내지 않는 이벤트에서
    지나갈 때의 출력이다(대기열 93). additionalContext 가 함께 있으면 모델에게도 가므로 context
    다."""
    assert outcome_of(0, json.dumps({"systemMessage": "x"}), "Stop") == "notice"
    both = json.dumps(
        {
            "systemMessage": "x",
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "x"},
        }
    )
    assert outcome_of(0, both, "PreToolUse") == "context"
    assert outcome_of(0, json.dumps({"systemMessage": ""}), "Stop") == "output"


def test_등록된_이벤트마다_래퍼가_없는_훅을_지나갈_때의_알림을_받아들이는_모양으로_낸다() -> None:
    """세션이 띄우는 모양(uv run 래퍼)과 등록된 이벤트 이름 그대로 잰다. 래퍼의 사본 테스트는 이벤트
    이름을 손으로 고른다."""
    registrations = registered_hooks()

    results = run_notices(registrations)

    assert {result.event for result in results} == {r.event for r in registrations.values()}
    assert [result for result in results if not result.ok] == []


def test_래퍼의_알림은_모델에게_닿는_이벤트에서_context_이고_Stop_계열에서_notice_다() -> None:
    """Stop·SubagentStop 의 additionalContext 는 대화를 잇는다. 나머지 이벤트에서 notice 만 나오면
    모델에게 가는 알림이 빠진 것이다 — 러너가 둘 다 받으면 그것을 0으로 지나간다(PR #122
    CodeRabbit)."""
    for event in ("PreToolUse", "PostToolUse", "UserPromptSubmit"):
        assert expected_notice(event) == "context"
        assert not NoticeResult(event, "notice", "").ok
    for event in ("Stop", "SubagentStop"):
        assert expected_notice(event) == "notice"
        assert not NoticeResult(event, "context", "").ok


def test_래퍼의_알림은_사용자에게_가는_systemMessage_가_없으면_context_여도_어긋남이다() -> None:
    """outcome_of 는 additionalContext 만 있어도 context 다. 표의 context 사례는 사용자 몫을
    요구하지 않으니(대부분의 훅은 모델에게만 알린다) 그 판정은 그대로 두고, 래퍼의 알림만 사용자
    몫을 따로 본다(PR #122 CodeRabbit 2회차)."""
    specific = {"hookEventName": "PreToolUse", "additionalContext": "x"}
    model_only = json.dumps({"hookSpecificOutput": specific})
    both = json.dumps({"systemMessage": "x", "hookSpecificOutput": specific})

    assert notice_outcome(0, model_only, "PreToolUse") != "context"
    assert notice_outcome(0, both, "PreToolUse") == "context"
    assert notice_outcome(0, json.dumps({"systemMessage": "x"}), "Stop") == "notice"
    assert notice_outcome(2, "", "PreToolUse") == "block"


@pytest.mark.parametrize("outcome", ["silent", "block", "output", "event Stop", "timeout"])
def test_래퍼의_알림이_기대한_판정이_아니면_어긋남이다(outcome: str) -> None:
    assert not NoticeResult("PreToolUse", outcome, "").ok
    assert NoticeResult("PreToolUse", "context", "").ok
    assert NoticeResult("Stop", "notice", "").ok


def test_푸시하지_않은_커밋이_있는_저장소를_만든다(tmp_path: Path) -> None:
    """`${UNPUSHED_REPO}` 는 upstream 이 HEAD 의 조상이고 HEAD 와 다르다.

    hook_pr_head_sync 의 발동 사례가 기대는 모양이다.
    """
    repo = create_fixtures(tmp_path)["UNPUSHED_REPO"]

    def rev(name: str) -> str:
        result = subprocess.run(
            ["git", "-C", repo, "rev-parse", name], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    ancestor = subprocess.run(
        ["git", "-C", repo, "merge-base", "--is-ancestor", "@{u}", "HEAD"], check=False
    )

    assert rev("HEAD") != rev("@{u}")
    assert ancestor.returncode == 0


def test_origin_main보다_한_커밋_뒤처진_저장소를_만든다(tmp_path: Path) -> None:
    """`${BEHIND_REPO}` 는 main 이 아닌 작업 브랜치이고 origin/main 에 HEAD 에 없는 커밋이 하나다.

    hook_push_behind_main 의 deny 사례가 기대는 모양이다.
    """
    repo = create_fixtures(tmp_path)["BEHIND_REPO"]

    def git_line(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", repo, *args], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    assert git_line("symbolic-ref", "--short", "HEAD") == "chore/x"
    assert git_line("rev-list", "--count", "HEAD..origin/main") == "1"


def test_일지_훅의_이름_꼴_사례는_저장소_픽스처를_쓰지_않는다(tmp_path: Path) -> None:
    """이름 꼴(ADR 0045 결정 7)은 파일 이름만 보므로 번호 저장소와 `${TODAY}` 가 없다. 훅이 자식
    프로세스로 번호 도구를 돌리던 때의 픽스처가 되살아나지 않게 한다."""
    replacements = create_fixtures(tmp_path)

    assert "NUMBERED_REPO" not in replacements
    assert "TODAY" not in replacements


def test_열린_PR_저장소는_origin_에_브랜치_끝을_머리로_둔_PR_의_ref_를_든다(tmp_path: Path) -> None:
    """`${OPEN_PR_REPO}` 는 hook_push_delete_open_pr 의 deny 사례가 기대는 모양이다."""
    repo = create_fixtures(tmp_path)["OPEN_PR_REPO"]
    result = subprocess.run(
        ["git", "-C", repo, "ls-remote", "origin"], check=True, capture_output=True, text=True
    )
    refs = dict(line.split("\t")[::-1] for line in result.stdout.splitlines())

    assert refs["refs/pull/7/head"] == refs["refs/heads/chore/x"]
    assert "refs/pull/7/merge" in refs


def test_main_저장소_둘은_커밋의_유무로_갈린다(tmp_path: Path) -> None:
    """`${MAIN_REPO}` 는 커밋이 하나 있는 main 이고 `${EMPTY_MAIN_REPO}` 는 커밋이 없는 main 이다.

    hook_git_main_commit 의 deny 사례와 첫 커밋 침묵 사례가 기대는 모양이다. 빈 저장소의 main
    이면 그 훅이 침묵해 deny 사례가 어긋난다.
    """
    replacements = create_fixtures(tmp_path)

    def git(name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", replacements[name], *args], capture_output=True, text=True, check=False
        )

    for name in ("MAIN_REPO", "EMPTY_MAIN_REPO"):
        assert git(name, "branch", "--show-current").stdout.strip() == "main"
    assert git("MAIN_REPO", "rev-parse", "--verify", "HEAD").returncode == 0
    assert git("EMPTY_MAIN_REPO", "rev-parse", "--verify", "HEAD").returncode != 0


def test_등록된_이벤트와_다른_훅은_실제로_돌려도_어긋남이다(tmp_path: Path) -> None:
    replacements = create_fixtures(tmp_path)
    deny = Case(
        hook="hook_env_read.py",
        expect="deny",
        payload={"tool_name": "Bash", "tool_input": {"command": "cat .env"}},
    )

    result = run_case(deny, replacements, Registration("PostToolUse", 20))

    assert result.outcome == "event PreToolUse"
    assert not result.ok


def test_시간_제한을_넘긴_자식은_timeout_으로_판정한다(tmp_path: Path) -> None:
    """제한 0초 — uv 자식이 뜨기도 전에 끝나므로 어떤 훅이든 넘긴다."""
    replacements = create_fixtures(tmp_path)
    case = Case(hook="hook_env_read.py", expect="silent", payload={"tool_name": "Bash"})

    result = run_case(case, replacements, Registration("PreToolUse", 0))

    assert result.outcome == "timeout"
    assert not result.ok
    assert "0초" in result.output
