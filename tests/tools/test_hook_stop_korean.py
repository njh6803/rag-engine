"""tools/hook_stop_korean.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

막을 답의 표본은 사용자가 "한국어로"라고 고친 직전 답이다(일지 2026-10-01-07 의 보고 언어 절).
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from tools.hook_stop_korean import block_reason_for, is_program_session, prose_of
from tools.run_hooks import hook_environment

HOOK = Path(__file__).parents[2] / "tools" / "hook_stop_korean.py"

# 일지 2026-10-01-07 의 세션이 낸 답. 사용자가 바로 다음에 "한국어로 말해줘"라고 했다.
ENGLISH = (
    "The new comment is just CodeRabbit confirming it received the review request, so there's "
    "nothing to fix or reply to. All three checks for `98f1ed0` (`verify`, `claude-review`, "
    "CodeRabbit) are still running. When they finish, I'll check the results, merge, and finish "
    "journal 07."
)


def test_사용자가_고친_영어_답은_막고_한국어로_다시_쓰라고_한다() -> None:
    reason = block_reason_for(ENGLISH)

    assert reason is not None
    assert "한국어" in reason


def test_영어_식별자가_섞인_한국어_답은_지나간다() -> None:
    message = (
        "PR #116을 병합했고 main을 당겼습니다. CI의 verify와 claude-review가 초록이고 "
        "CodeRabbit은 시간당 한도에 걸려 1회차만 봤습니다."
    )

    assert block_reason_for(message) is None


def test_코드_펜스_안의_영어는_세지_않는다() -> None:
    message = (
        "검증 명령의 결과는 아래와 같습니다.\n\n"
        "```\nAll checks passed. Found 0 errors in 112 files, no warnings were reported.\n"
        "Success: no issues found in 112 source files after the second pass of the checker.\n```\n"
    )

    assert block_reason_for(message) is None


def test_한글이_코드_스팬에만_있으면_영어_답이다() -> None:
    message = (
        "I updated `일지` and `대기열` with the results, then pushed the branch so the "
        "review can start on the remote."
    )

    assert block_reason_for(message) is not None


def test_코드만_든_답은_판정하지_않는다() -> None:
    assert block_reason_for("```bash\nuv run pytest -q\n```") is None


def test_글자가_적은_답은_판정하지_않는다() -> None:
    assert block_reason_for("OK.") is None


def test_여덟_글자의_영어_답은_판정해_막는다() -> None:
    """판정 하한(8)에 걸리는 여덟 글자. 측정에서 하한 아래의 영어 답은 "Next"(4) 하나였다."""
    assert block_reason_for("Now merge.") is not None


def test_막는_쪽의_경계_한글_두_글자를_인용한_영어_답() -> None:
    """측정에서 막은 답의 최고 비율은 0.041 이다. 이 문장(0.033)은 그 바로 아래 모양이다.

    트랜스크립트 d20ee262 의 텍스트이고, 도구 호출로 이어져 Stop 이 받은 답은 아니다.
    """
    message = 'The journal\'s "다음" section is newly written, so running retro as the hook asks.'

    assert block_reason_for(message) is not None


def test_지나가는_쪽의_경계_짧은_한국어_보고() -> None:
    """측정에서 막지 않은 답 중 비율이 둘째로 낮다(0.391, 트랜스크립트 39159309).

    가장 낮은 0.340 은 스킬 이름 목록이다(`test_식별자만_나열한_답은_판정하지_않는다`).
    """
    message = "새 커밋의 CI가 통과했습니다. Claude Code Review와 CodeRabbit을 기다립니다."

    assert block_reason_for(message) is None


def test_링크_대상과_URL_은_세지_않는다() -> None:
    message = (
        "PR을 열었습니다. [njh6803/agent-os#117](https://github.com/njh6803/agent-os/pull/117) "
        "이고 검사는 https://github.com/njh6803/agent-os/actions/runs/123456789 에서 봅니다."
    )

    assert block_reason_for(message) is None


def test_인용_블록의_영어는_세지_않는다() -> None:
    """첫 판의 탐침에서 막힌 한국어 답의 모양(트랜스크립트 828f69a1, 비율 0.18)."""
    message = (
        "본문에 서브에이전트의 보고에 대해 하라는 말은 없고, 사실 찾기를 맡기라는 말만 있다.\n\n"
        "> When a frontier question needs a fact from the environment (filesystem, tools, git),\n"
        "> dispatch a subagent to find it rather than asking the user, and wait for its report\n"
        "> before asking the downstream questions that depend on that fact.\n"
    )

    assert block_reason_for(message) is None


def test_식별자만_나열한_답은_판정하지_않는다() -> None:
    """스킬 이름을 쉼표로 나열한 답의 앞부분(트랜스크립트 b925504b).

    그 답 전체는 구분자 없는 이름(`grilling`, `tdd`)이 라틴 문자로 남아, 끝의 한국어 한 줄 덕에
    0.340 으로 지나갔다.
    """
    message = (
        "git-branch, git-commit, code-review, diagnosing-bugs, domain-modeling, "
        "claude-security:scan, code-review:code-review, coderabbit:autofix, tdd"
    )

    assert block_reason_for(message) is None


def test_한글도_라틴_문자도_아닌_글자는_세지_않는다() -> None:
    """못 보는 것의 고정. 일본어 답은 섞인 라틴 문자만으로 판정한다.

    라틴 문자가 8자 이상이면 막고, 적으면 지나간다.
    """
    long_latin = "PR を作成しました。Claude Code Review と CodeRabbit を待っています。"
    short_latin = "PR を作成しました。確認をお願いします。"

    assert block_reason_for(long_latin) is not None
    assert block_reason_for(short_latin) is None


def test_구분자_없는_이름만_나열한_답은_막힌다() -> None:
    """못 보는 것의 고정. `grilling`·`tdd` 같은 이름은 식별자로 빠지지 않고 산문으로 센다."""
    assert block_reason_for("grilling, tdd, retro, implement, simplify, loop, schedule") is not None


def test_따옴표로_길게_든_영어_원문은_센다() -> None:
    """못 보는 것의 고정. 인용 줄(`>`)만 빼고 산문 속 따옴표 인용은 센다."""
    message = (
        '스킬 본문은 "When a frontier question needs a fact from the environment, dispatch a '
        'subagent to find it rather than asking the user" 라고 적었다.'
    )

    assert block_reason_for(message) is not None


def test_SDK_로_띄운_세션만_프로그램_세션이다() -> None:
    """사람이 읽는 세션은 막고, 결과를 프로그램이 읽는 세션은 건드리지 않는다."""
    assert is_program_session("sdk-py")
    assert is_program_session("sdk-cli")
    assert not is_program_session("claude-desktop")
    assert not is_program_session("cli")
    assert not is_program_session(None)


def test_점이_없는_URL_과_상대_경로_링크도_뺀다() -> None:
    """표준 축 리뷰의 반례. 식별자 규칙만으로는 `http://localhost/` 와 `(README)` 가 남았다."""
    assert prose_of("서버 http://localhost/ 확인") == "서버  확인"
    assert prose_of("[README](README) 와 [절](#section) 참고") == "[README] 와 [절] 참고"


def test_한글_사이의_구분자는_식별자가_아니다() -> None:
    """표준 축 리뷰의 반례. `\\w` 로 보면 한글 낱말이 식별자로 빠졌다."""
    assert prose_of("읽기/쓰기와 결과:통과했습니다") == "읽기/쓰기와 결과:통과했습니다"


def test_닫히지_않은_펜스는_끝까지_코드다() -> None:
    assert prose_of("한 줄\n```\nnot closed\nstill code") == "한 줄\n"


def test_백틱이_든_줄은_펜스를_열지_않는다() -> None:
    """정보 문자열에 백틱이 있으면 펜스가 아니라 코드 스팬이다(CommonMark, PR #118 CodeRabbit)."""
    assert block_reason_for("```uv run pytest```\nNow merge.") is not None


def test_다른_문자가_섞인_줄은_펜스를_닫지_않는다() -> None:
    """닫는 펜스는 여는 펜스와 같은 문자만 쓴다(CommonMark, PR #118 CodeRabbit)."""
    message = (
        "```\nprint(1)\n```~~~\nNow merge this branch after the checks pass, please.\n```\n"
        "완료했습니다."
    )

    assert block_reason_for(message) is None


def test_긴_백틱_묶음의_코드_스팬도_뺀다() -> None:
    assert prose_of("앞 ``a ` b`` 뒤") == "앞  뒤"


def _run_hook(payload: Mapping[str, object], entrypoint: str | None) -> str:
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


def test_사람이_읽는_세션의_영어_답은_실제로_막는다() -> None:
    output = _run_hook({"last_assistant_message": ENGLISH}, "claude-desktop")

    assert json.loads(output)["decision"] == "block"


def test_SDK_세션의_영어_답은_실제로_지나간다() -> None:
    """보안 리뷰 같은 SDK 세션의 답은 프로그램이 읽는다(sdk-py 세션 247개의 텍스트가 모두 영어)."""
    assert _run_hook({"last_assistant_message": ENGLISH}, "sdk-py") == ""


def test_멈춤을_한_번_막은_뒤의_답은_다시_막지_않는다() -> None:
    """두 번째 Stop 의 입력은 `stop_hook_active` 가 참이다(stop_payload 탐침).

    사용자가 영어 답을 요청한 턴에 같은 답을 여러 번 막지 않게 한다.
    """
    payload = {"last_assistant_message": ENGLISH, "stop_hook_active": True}

    assert _run_hook(payload, "claude-desktop") == ""


def test_마지막_답이_입력에_없으면_지나간다() -> None:
    assert _run_hook({"transcript_path": "x.jsonl"}, None) == ""
