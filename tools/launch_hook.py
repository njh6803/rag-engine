"""훅 등록의 실행 래퍼. 인자로 받은 이름의 훅 파일이 이 파일 옆(`tools/`)에 없으면 막지 않고 0으로
끝나며 그것을 세션에 알리고, 있으면 같은 프로세스에서 그 훅을 `__main__` 으로 돌린다.

등록이 `python "${CLAUDE_PROJECT_DIR}/tools/<훅>.py"` 꼴이던 때는 훅 파일이 없으면 파이썬이 2로
끝났다. PreToolUse 에서 2는 "막아라"라 그 매처의 모든 호출이 막혔다(2026-09-29 실측). PR #120
세션이 다시 시작되며 워크트리의 settings.json(새 훅의 등록)을 싣고 `${CLAUDE_PROJECT_DIR}` 은 그
파일이 없는 주 체크아웃을 가리켜 Bash·PowerShell 이 전부 막혔다(대기열 91, 일지 2026-10-02-01).
새 훅을 병합한 뒤 주 체크아웃을 당기지 않은 채 워크트리에서 다시 시작한 세션도 같다. 이제 그 자리의
훅은 없는 것처럼 지나간다. `claude -p` 세션에서 없는 훅을 옛 모양으로 더하면 Bash 가 막혔고 이
래퍼로 더하면 돌았다(2026-10-02, `.scratch/harness/probes/hook_registration/run.sh`).

지나갈 때는 stdout 에 JSON 하나를 낸다. 사용자에게는 `systemMessage`, 모델에게는 `CONTEXT_EVENTS`
일 때 `additionalContext` 다(`notice`). 첫 판은 stderr 에 한 줄만 남겼는데, 종료 0의 stderr 는
디버그 로그로만 가서 `.env` 읽기 차단(`hook_env_read`)이 꺼져도 세션이 몰랐다(대기열 93, PR #121
claude-review). `claude -p` 세션에서 PreToolUse 의 알림은 모델이 모델 몫의 문장을 옮겼고, Stop 의
알림은 사용자 알림 하나로 끝나 대화가 이어지지 않았다(2026-10-02, 같은 `run.sh` 의 E·F, 대조군
G). 인자가 틀린 것과 파일이 없는 것은 문구를 가른다(`skip_reason`) — 고치는 자리가 다르다(앞의
것은 등록, 뒤의 것은 주 체크아웃 당기기). json 은 이 길에서만 import 한다.

알림은 세션·에이전트·이벤트·이유마다 처음 한 번만 내고, 그 뒤에는 출력 없이 0으로 지나간다
(`notice_key`, `claim_first_notice`). 다시 연 워크트리 세션에서 주 체크아웃에 없는 새 훅을
Write·Edit 마다 알려 같은 문단이 약 마흔 번 컨텍스트에 쌓였다(대기열 174, 일지 2026-10-12-05). 첫
알림은 꺼진 훅의 일을 챙기게 해 주므로 없애지 않는다. 세션을 모르는 페이로드(`session_id` 가 없거나
문자열이 아니다)와 표지를 쓰지 못할 때는 예전처럼 호출마다 알린다.

등록 명령의 모양은 그대로이고 스크립트 자리에 이 파일이, 끝에 훅 이름이 온다. 셸 문법(`[ -f … ]`)을
더하지 않으므로 등록이 셸에 기대는 몫(`${CLAUDE_PROJECT_DIR}` 의 전개와 따옴표)은 래퍼 전과 같다.
모양은 `tools/run_hooks.py` 가 대조한다. 래퍼는 훅 한 번에 약 10ms 를 더한다(2026-10-02,
`.scratch/harness/probes/hook_registration/time_launch.sh`. 93 반영 뒤에 다시 재 바로 205~218ms,
래퍼 212~220ms).

훅이 있으면 종료 코드와 stdin·stdout 은 훅을 바로 돌릴 때와 같다. 훅 안의 예외도 1(막지 않는
오류)로 끝나지만, stderr 의 traceback 에는 래퍼와 runpy 의 프레임이 더해진다. 훅이 보는 `__name__`
은 `__main__` 이고, `__file__`·`sys.argv[0]` 은 같은 훅 파일을 가리키며(구분자 문자열은 다를 수
있다 — 지금 훅은 둘 다 쓰지 않는다), `sys.path[0]` 은 둘 다 `tools/` 다.

못 보는 것:
- 이 파일 자체가 없을 때. 그때는 예전처럼 파이썬이 2로 끝나고, 모든 등록이 그렇다. 2의 효과는
  이벤트마다 다르다 — PreToolUse 는 그 매처의 호출을 막고, UserPromptSubmit·Stop 도 2를 막기로
  읽는다(공식 hooks 문서, 재지 않았다). 주 체크아웃이 이 파일을 들인 커밋보다 뒤에 있으면 그렇다.
  이 파일을 들이는 PR 이 병합된 뒤 주 체크아웃을 당기기 전, 주 체크아웃이 그보다 앞서 딴 브랜치에
  있을 때, 이 파일의 이름을 바꾼 뒤다. 그래서 이 파일을 들인 PR 은 병합 직후 주 체크아웃을 당긴다
  (주 체크아웃 세션의 tidy-checkouts, next-session merge.md 의 "워크트리에서 병합할 때").
- 훅 파일은 있지만 그 판이 등록과 맞지 않는 것(주 체크아웃의 옛 훅이 새 등록의 이벤트로 도는 것).
- 알림이 데스크톱 앱에서 어떻게 보이는지. `systemMessage` 는 `claude -p` 의 stream-json 에서
  `informational` 이벤트로 오는 것만 봤다. 공식 hooks 문서는 Setup 이 JSON 출력(`systemMessage`
  포함)을 버리고 StopFailure 가 출력을 무시한다고 적는다 — 그 이벤트에 훅을 등록하면 알림이 없다.
  지금 등록된 이벤트(UserPromptSubmit, PreToolUse, PostToolUse, Stop)는 아니다.
- 첫 알림을 받은 뒤 모델이 그것을 잃는 것. 컨텍스트가 압축되면 요약에 남는지 모르고, 다시 알리지
  않는다. 사용자는 첫 `systemMessage` 를 봤다.
- 표지의 수명. 임시 디렉터리의 `STATE_DIR` 에 알림마다 빈 파일 하나가 남고 지우지 않는다. 세션
  ID 가 같은 채 다시 시작한 세션(이어 하기)은 앞에서 알린 것을 다시 알리지 않는다 — 모델이 이어받은
  대화에 첫 알림이 있으면 맞고, 압축으로 잃었으면 위와 같다.
- Stop 에서는 모델이 알림을 받지 않는다. 사용자가 보고 전할 때까지 모델은 그 훅이 꺼진 것을 모른다.
"""

from __future__ import annotations

import os
import runpy
import sys

# pathlib 을 쓰지 않는다. pathlib 을 import 하지 않는 훅에서 그 import 가 훅 한 번에 약 8ms 를
# 더했다(손으로 견줬다, 일지 2026-10-02-02). json 도 지나갈 때만 import 한다.
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = "agent-os-launch-hook"
# `hookSpecificOutput.additionalContext` 를 모델에게 전하는 이벤트(공식 hooks 문서, 2026-10-02
# 읽음). Stop·SubagentStop 도 받지만 거기서는 대화를 잇게 해 턴이 끝날 때마다 한 번 더 돈다 —
# 넣지 않는다(`claude -p` 세션에서 Stop 의 additionalContext 가 답 하나를 더했다,
# `.scratch/harness/probes/hook_registration/run.sh` 의 G). 러너(tools/run_hooks.py)는 이 집합을
# import 하지 않고 `NOTICE_ONLY_EVENTS` 로 따로 적어 대조한다 — 여기를 고치면 그쪽도 본다.
CONTEXT_EVENTS = frozenset(
    {
        "SessionStart",
        "SubagentStart",
        "UserPromptSubmit",
        "UserPromptExpansion",
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "PostToolBatch",
        "PostModelSwitch",
    }
)


def hook_path(argv: list[str]) -> str | None:
    """`argv` 의 훅 이름이 가리키는 `tools/` 의 파일. 이름이 하나가 아니거나 파일이 없으면 None."""
    if len(argv) != 2:
        return None
    path = os.path.join(TOOLS_DIR, argv[1])
    return path if os.path.isfile(path) else None


def skip_reason(argv: list[str]) -> str:
    """훅을 돌리지 않고 지나가는 이유. 인자가 틀린 것과 파일이 없는 것은 고치는 자리가 다르다."""
    if len(argv) != 2:
        return (
            f"launch_hook: 등록 명령의 훅 이름 인자가 하나가 아니라({argv[1:]}) 아무 훅도"
            " 돌리지 않고 지나갔다. 등록 모양은 tools/run_hooks.py 의 REGISTRATION 이고 그"
            " 대조가 커밋을 막는다."
        )
    return (
        f"launch_hook: 훅 파일이 없어 돌리지 않고 지나갔다: {os.path.join(TOOLS_DIR, argv[1])}."
        " 그 훅이 막거나 알리던 것이 이 호출에서 꺼져 있다. 주 체크아웃이 그 훅을 들인 커밋보다"
        " 뒤에 있으면(병합 뒤 당기지 않았거나 워크트리에서 더한 훅이 아직 병합되지 않았다) 그렇다."
        " 병합된 훅이면 주 체크아웃을 당긴다(주 체크아웃 세션에서 /tidy-checkouts)."
    )


# 모델에게만 덧붙인다. 사용자에게는 같은 이유를 systemMessage 로 낸다(보이는지는 이벤트와 화면에
# 따른다 — 독스트링의 못 보는 것). 지나간 훅은 막는 훅일 수도 계기 훅일 수도 있다.
MODEL_SUFFIX = (
    " 같은 이유를 사용자 알림(systemMessage)으로도 냈다. 그 훅이 막던 일은 스스로 하지 않고,"
    " 알리던 일은 스스로 챙긴다. 세션을 알면 같은 알림은 이 세션에서 다시 내지 않는다."
)


def payload_strings(payload: bytes) -> dict[str, str]:
    """페이로드의 최상위 값 가운데 문자열인 것. 읽지 못하거나 JSON 객체가 아니면 비었다 — 그때
    래퍼는 이벤트도 세션도 모르는 것으로 본다. 목록·숫자 페이로드는 `items` 가 없어 AttributeError
    다."""
    import json

    try:
        data: dict[str, object] = json.loads(payload)
        return {key: value for key, value in data.items() if isinstance(value, str)}
    except (ValueError, AttributeError):
        return {}


def notice(reason: str, strings: dict[str, str]) -> str:
    """지나간 것을 알리는 출력. 사용자에게는 `systemMessage`(공통 필드라 이벤트를 가리지 않고
    낸다), 모델에게는 `CONTEXT_EVENTS` 일 때만 `additionalContext`(이유 뒤에 `MODEL_SUFFIX`)다.
    이벤트는 페이로드의 `hook_event_name` 이고(`payload_strings`), 없으면 모르는 이벤트로 본다 —
    Claude Code 는 이벤트 이름이 다른 `hookSpecificOutput` 을 받지 않는다."""
    import json

    event = strings.get("hook_event_name")
    output: dict[str, object] = {"systemMessage": reason}
    if event in CONTEXT_EVENTS:
        output["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": reason + MODEL_SUFFIX,
        }
    return json.dumps(output, ensure_ascii=False)


def notice_key(reason: str, strings: dict[str, str]) -> str | None:
    """같은 알림을 한 번으로 세는 열쇠. 세션(`session_id`)을 모르면 None 이고 호출마다 알린다.

    세션 말고도 에이전트·이벤트·이유를 가른다. 서브에이전트는 세션 ID 가 같아도 컨텍스트가 따로이고
    입력에 `agent_id` 가 온다(`tools/hook_midturn_korean.py`). 사용자에게만 가는 이벤트(Stop)에서
    먼저 알렸으면 모델은 아직 모른다. 이유는 훅 파일이 없는 것과 등록 인자가 틀린 것을 가르고, 앞의
    것에는 찾은 훅 파일의 경로가, 뒤의 것에는 받은 인자가 든다(`skip_reason`)."""
    session = strings.get("session_id")
    if not session:
        return None
    import hashlib

    parts = (session, strings.get("agent_id", ""), strings.get("hook_event_name", ""), reason)
    # JSON 의 짝 없는 서로게이트 이스케이프도 문자열로 온다. 그대로 바이트로 옮긴다.
    return hashlib.sha256("\0".join(parts).encode("utf-8", "surrogatepass")).hexdigest()


def claim_first_notice(key: str) -> bool:
    """`key` 의 표지 파일을 이 호출이 처음 만들었으면 True, 이미 있으면 False. 표지는 임시
    디렉터리 아래 `STATE_DIR` 에 둔다. 표지를 만들지 못하면 True 다 — 알리지 못하는 것보다
    되풀이가 낫다.

    묻기와 기록을 나누지 않는다. `O_EXCL` 생성 하나가 둘을 겸해야, 한 메시지의 병렬 도구 호출에서
    도는 래퍼 둘이 함께 처음이라고 보지 않는다. 디렉터리 자리의 파일은 makedirs 가 FileExistsError
    로 알리므로 표지가 이미 있는 것과 따로 잡는다. 쓸 수 있는 임시 디렉터리 후보가 하나도 없으면
    `tempfile.gettempdir` 가 FileNotFoundError 를 내므로 그것도 같은 `try` 에 둔다."""
    import tempfile

    try:
        directory = os.path.join(tempfile.gettempdir(), STATE_DIR)
        os.makedirs(directory, exist_ok=True)
    except OSError:
        return True
    try:
        os.close(os.open(os.path.join(directory, key), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    except OSError:
        return True
    return True


def main() -> int:
    path = hook_path(sys.argv)
    if path is None:
        reason = skip_reason(sys.argv)
        strings = payload_strings(sys.stdin.buffer.read())
        key = notice_key(reason, strings)
        if key is None or claim_first_notice(key):
            # 훅 환경에 PYTHONUTF8 이 있다고 가정하지 않는다. 텍스트 스트림은 cp949 일 수 있다.
            sys.stdout.buffer.write(notice(reason, strings).encode("utf-8"))
        sys.stderr.buffer.write(f"{reason}\n".encode())  # 종료 0의 stderr 는 디버그 로그로 간다
        return 0
    sys.argv = [path]
    runpy.run_path(path, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
