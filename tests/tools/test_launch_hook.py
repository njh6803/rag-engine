"""tools/launch_hook.py — 훅 등록의 실행 래퍼(대기열 91·93).

래퍼 사본을 임시 디렉터리에 두고 그 옆에 손으로 지은 훅을 둔다. 래퍼는 자기 옆에서 훅을 찾으므로
사본은 이 저장소의 훅이 아니라 임시 훅을 돈다. 이 저장소의 훅을 래퍼로 도는 것과, 등록된 이벤트마다
지나갈 때의 알림이 Claude Code 가 받아들이는 모양인지는 tools/run_hooks.py 가 pre-commit 에서 잰다.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

import pytest
from tools.launch_hook import MODEL_SUFFIX, STATE_DIR, claim_first_notice
from tools.run_hooks import ROOT, hook_environment

LAUNCHER = ROOT / "tools" / "launch_hook.py"


class _Specific(TypedDict, total=False):
    hookEventName: str
    additionalContext: str
    permissionDecision: str


class _Notice(TypedDict, total=False):
    systemMessage: str
    hookSpecificOutput: _Specific


def _돌린다(
    *argv: str, stdin: bytes = b"", temp: Path | None = None
) -> subprocess.CompletedProcess[bytes]:
    """`temp` 를 주면 자식의 임시 디렉터리를 거기로 돌린다. 세션이 든 페이로드는 래퍼가 표지를
    남기므로, 실제 임시 디렉터리에 남기면 다음 실행의 첫 호출이 조용해진다."""
    env = hook_environment()
    if temp is not None:
        env.update({name: str(temp) for name in ("TMPDIR", "TEMP", "TMP")})
    return subprocess.run(
        [sys.executable, *argv],
        input=stdin,
        capture_output=True,
        env=env,
        check=False,
        timeout=60,
    )


def _페이로드(event: str = "PostToolUse", **fields: str) -> bytes:
    return json.dumps({"hook_event_name": event, **fields}).encode()


def _래퍼_사본을_둔다(directory: Path) -> str:
    launcher = directory / "launch_hook.py"
    shutil.copyfile(LAUNCHER, launcher)
    return str(launcher)


def _알림(launched: subprocess.CompletedProcess[bytes]) -> _Notice:
    assert launched.returncode == 0, launched.stderr.decode("utf-8", "replace")
    notice: _Notice = json.loads(launched.stdout)
    return notice


def _모델이_받는_문구(notice: _Notice) -> str:
    return notice.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_훅_파일이_없으면_막지_않고_모델과_사용자에게_알린다(tmp_path: Path) -> None:
    """옛 등록(`python <훅 경로>`)은 같은 자리에서 2로 끝났다. PreToolUse 에서 2는 막기다. 래퍼가
    stderr 에만 남기면(종료 0의 stderr 는 디버그 로그로만 간다) 막는 훅이 꺼진 것을 세션이 모른다
    (대기열 93)."""
    launcher = _래퍼_사본을_둔다(tmp_path)
    payload = b'{"hook_event_name": "PreToolUse", "tool_name": "Bash"}'

    launched = _돌린다(launcher, "hook_없다.py", stdin=payload)
    direct = _돌린다(str(tmp_path / "hook_없다.py"), stdin=payload)
    notice = _알림(launched)
    specific = notice.get("hookSpecificOutput", {})

    assert direct.returncode == 2
    assert specific.get("hookEventName") == "PreToolUse"
    assert "permissionDecision" not in specific
    to_model, to_user = _모델이_받는_문구(notice), notice.get("systemMessage", "")
    assert "hook_없다.py" in to_user
    # 모델에게는 사용자와 같은 이유에 할 일 문장을 더한다. 탐침은 이것으로 어느 쪽이 닿았는지
    # 가른다
    assert to_model == to_user + MODEL_SUFFIX
    assert MODEL_SUFFIX.strip() not in to_user


def test_같은_세션의_같은_훅은_첫_알림만_내고_뒤는_조용히_지나간다(tmp_path: Path) -> None:
    """다시 연 워크트리 세션에서 주 체크아웃에 없는 새 훅을 래퍼가 Write·Edit 마다 알려 같은 문단이
    약 마흔 번 컨텍스트에 쌓였다(대기열 174, 일지 2026-10-12-05). 알림은 꺼진 훅의 일을 챙기게
    해 주므로 없애지 않고 한 번만 낸다."""
    launcher = _래퍼_사본을_둔다(tmp_path)
    payload = _페이로드(session_id="세션-1")

    first = _알림(_돌린다(launcher, "hook_없다.py", stdin=payload, temp=tmp_path))
    again = _돌린다(launcher, "hook_없다.py", stdin=payload, temp=tmp_path)

    assert "hook_없다.py" in _모델이_받는_문구(first)
    assert again.returncode == 0
    assert again.stdout == b""


@pytest.mark.parametrize(
    "fields",
    [
        {"session_id": "세션-2"},
        {"session_id": "세션-1", "agent_id": "에이전트-1"},
        {"session_id": "세션-1", "event": "PreToolUse"},
    ],
    ids=["다른 세션", "서브에이전트", "다른 이벤트"],
)
def test_세션이나_에이전트나_이벤트가_다르면_다시_알린다(
    tmp_path: Path, fields: dict[str, str]
) -> None:
    """서브에이전트는 세션 ID 가 같아도 컨텍스트가 따로다(입력에 `agent_id` 가 온다,
    tools/hook_midturn_korean.py). Stop 처럼 사용자에게만 가는 이벤트에서 먼저 알렸으면 모델은 아직
    모르므로 이벤트도 가른다."""
    launcher = _래퍼_사본을_둔다(tmp_path)
    _알림(_돌린다(launcher, "hook_없다.py", stdin=_페이로드(session_id="세션-1"), temp=tmp_path))
    other = _알림(_돌린다(launcher, "hook_없다.py", stdin=_페이로드(**fields), temp=tmp_path))

    assert "hook_없다.py" in other.get("systemMessage", "")


def test_훅이_다르면_같은_세션에서도_다시_알린다(tmp_path: Path) -> None:
    launcher = _래퍼_사본을_둔다(tmp_path)
    payload = _페이로드(session_id="세션-1")
    _알림(_돌린다(launcher, "hook_가.py", stdin=payload, temp=tmp_path))

    other = _알림(_돌린다(launcher, "hook_나.py", stdin=payload, temp=tmp_path))

    assert "hook_나.py" in other.get("systemMessage", "")


@pytest.mark.parametrize(
    "payload",
    [b'{"hook_event_name": "PostToolUse"}', b'{"session_id": 7}', b'{"session_id": ""}', b"[1]"],
    ids=["세션 없음", "문자열 아닌 세션", "빈 세션", "목록"],
)
def test_세션을_모르면_호출마다_알린다(tmp_path: Path, payload: bytes) -> None:
    """한 번으로 셀 열쇠가 없다. 조용히 지나가는 것보다 되풀이가 낫다. 러너(tools/run_hooks.py)의
    알림 판정도 세션 없는 페이로드라 커밋마다 같은 출력을 본다."""
    launcher = _래퍼_사본을_둔다(tmp_path)

    for _ in range(2):
        assert _알림(_돌린다(launcher, "hook_없다.py", stdin=payload, temp=tmp_path))


def test_표지를_쓰지_못하면_호출마다_알린다(tmp_path: Path) -> None:
    """표지 디렉터리 자리에 파일이 있으면 makedirs 가 FileExistsError 를 낸다. 그것을 '이미
    알렸다' 로 읽으면 한 번도 알리지 않고 지나간다."""
    launcher = _래퍼_사본을_둔다(tmp_path)
    (tmp_path / STATE_DIR).write_text("디렉터리가 아니다", encoding="utf-8")
    payload = _페이로드(session_id="세션-1")

    for _ in range(2):
        assert _알림(_돌린다(launcher, "hook_없다.py", stdin=payload, temp=tmp_path))


def test_쓸_수_있는_임시_디렉터리가_없어도_처음이라고_보고_알린다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """읽기 전용 컨테이너처럼 임시 디렉터리 후보가 모두 막히면 `tempfile.gettempdir` 가
    FileNotFoundError 를 낸다. 그 예외로 래퍼가 1로 끝나면 알림이 한 번도 나가지 않는다(PR 직전
    버그·성능 리뷰가 후보를 없는 경로로 바꿔 손으로 재현했다)."""

    def no_usable_temp() -> str:
        raise FileNotFoundError("No usable temporary directory found")

    monkeypatch.setattr(tempfile, "gettempdir", no_usable_temp)

    assert claim_first_notice("열쇠") is True


def test_Stop_에서는_사용자에게만_알리고_대화를_잇지_않는다(tmp_path: Path) -> None:
    """Stop 의 additionalContext 는 대화를 잇게 한다(공식 hooks 문서). 그러면 턴이 끝날 때마다 한
    번 더 돈다."""
    payload = b'{"hook_event_name": "Stop", "stop_hook_active": false}'

    notice = _알림(_돌린다(_래퍼_사본을_둔다(tmp_path), "hook_없다.py", stdin=payload))

    assert set(notice) == {"systemMessage"}


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not json",
        b"[1, 2]",
        b'{"tool_name": "Bash"}',
        b'{"hook_event_name": ["PreToolUse"]}',
    ],
    # 마지막은 해시할 수 없는 값이다. 집합에 바로 물으면 TypeError 로 1이 되어 알림이 없다
    ids=["빈", "JSON 아님", "목록", "이벤트 없음", "목록인 이벤트"],
)
def test_이벤트를_모르면_사용자에게만_알린다(tmp_path: Path, payload: bytes) -> None:
    """hookEventName 이 이벤트와 다른 hookSpecificOutput 은 Claude Code 가 받지 않는다.
    systemMessage 는 모든 이벤트가 받는다."""
    notice = _알림(_돌린다(_래퍼_사본을_둔다(tmp_path), "hook_없다.py", stdin=payload))

    assert set(notice) == {"systemMessage"}


def test_훅_이름_인자가_틀려도_지나가고_파일이_없을_때와_다른_이유를_알린다(tmp_path: Path) -> None:
    """등록 모양이 틀린 것이다. 그것은 tools/run_hooks.py 의 대조가 잡고, 세션은 막지 않는다. 같은
    문구면 주 체크아웃을 당겨도 풀리지 않는 것을 당기라고 알린다(PR #121 claude-review Nit)."""
    launcher = _래퍼_사본을_둔다(tmp_path)
    payload = b'{"hook_event_name": "PreToolUse"}'

    no_name = _모델이_받는_문구(_알림(_돌린다(launcher, stdin=payload)))
    two_names = _모델이_받는_문구(_알림(_돌린다(launcher, "hook_a.py", "hook_b.py", stdin=payload)))
    missing = _모델이_받는_문구(_알림(_돌린다(launcher, "hook_없다.py", stdin=payload)))

    # 임시 경로에 이 테스트의 이름이 들어가므로 낱말 하나가 아니라 문구로 가른다
    wrong_argv, no_file = "인자가 하나가 아니라", "훅 파일이 없어"
    assert wrong_argv in no_name and no_file not in no_name
    assert wrong_argv in two_names and "hook_a.py" in two_names
    assert no_file in missing and wrong_argv not in missing
    assert "주 체크아웃을 당긴다" in missing and "당긴다" not in no_name


def test_파일이_없을_때_안내하는_스킬_명령은_이_저장소에_있다(tmp_path: Path) -> None:
    """안내문은 주 체크아웃을 당기는 길로 스킬 명령(`/tidy-checkouts`)을 든다. 스킬 이름을 바꾸거나
    지우면 안내문이 조용히 낡으므로, 안내문이 든 `/<이름>` 꼴 명령마다 이 저장소에 그 스킬 파일이
    있는지 본다(PR #141 claude-review). 안내문에는 없는 훅의 경로가 들고 리눅스에서는 그 경로가
    공백 뒤의 `/`로 시작하므로, 경로를 먼저 걷어 내고 찾는다."""
    payload = b'{"hook_event_name": "PreToolUse"}'
    launcher = _래퍼_사본을_둔다(tmp_path)
    missing = _모델이_받는_문구(_알림(_돌린다(launcher, "hook_없다.py", stdin=payload)))
    hook_path = str(tmp_path / "hook_없다.py")
    assert hook_path in missing, missing

    text = missing.replace(hook_path, "<훅 경로>")
    commands = re.findall(r"(?:^|[\s(])/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)", text)

    assert "tidy-checkouts" in commands, missing
    for command in commands:
        assert (ROOT / ".claude" / "skills" / command / "SKILL.md").is_file(), command


def test_훅의_종료_코드와_stdin_stdout_stderr_는_그대로다(tmp_path: Path) -> None:
    (tmp_path / "hook_막는다.py").write_text(
        "import sys\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n"
        "sys.stderr.buffer.write('막은 이유'.encode('utf-8'))\n"
        "raise SystemExit(2)\n",
        encoding="utf-8",
    )
    payload = '{"tool_input": {"command": "한글 명령"}}'.encode()

    launched = _돌린다(_래퍼_사본을_둔다(tmp_path), "hook_막는다.py", stdin=payload)

    assert launched.returncode == 2
    assert launched.stdout == payload
    assert launched.stderr.decode("utf-8") == "막은 이유"


def test_훅_안의_예외는_바로_돌릴_때처럼_1이다(tmp_path: Path) -> None:
    """PreToolUse 에서 1은 막지 않는 오류다. 래퍼가 이것을 2로 바꾸거나 삼키지 않는다."""
    (tmp_path / "hook_깨진다.py").write_text("raise RuntimeError('버그')\n", encoding="utf-8")

    launched = _돌린다(_래퍼_사본을_둔다(tmp_path), "hook_깨진다.py")

    assert launched.returncode == 1
    assert b"RuntimeError" in launched.stderr


def test_훅은_바로_돌릴_때와_같은_이름과_인자와_경로를_본다(tmp_path: Path) -> None:
    hook = tmp_path / "hook_본다.py"
    hook.write_text(
        "import json, sys\n"
        "print(json.dumps({'name': __name__, 'argv': sys.argv, 'file': __file__,"
        " 'path0': sys.path[0]}))\n",
        encoding="utf-8",
    )

    launched = _돌린다(_래퍼_사본을_둔다(tmp_path), "hook_본다.py")
    seen = json.loads(launched.stdout)

    assert launched.returncode == 0
    assert seen["name"] == "__main__"
    assert [Path(arg).resolve() for arg in seen["argv"]] == [hook.resolve()]
    assert Path(seen["file"]).resolve() == hook.resolve()
    assert Path(seen["path0"]).resolve() == tmp_path.resolve()
