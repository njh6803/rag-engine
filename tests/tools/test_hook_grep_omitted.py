"""tools/hook_grep_omitted.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

결과 객체의 `content` 는 `.scratch/harness/probes/grep_omitted/run.py` 의 A 가 받은 것(Claude Code
2.1.296)에서 500자 줄을 뺀 것과, 이 훅을 만든 세션이 Grep 도구로 손으로 받은 출력이다.
"""

from __future__ import annotations

import json

from tools.hook_grep_omitted import LEAD, MARKER, TOOL, HookPayload, ToolInput, context_for
from tools.run_hooks import registered_matchers

# 프로브 A 의 결과에서 500자 줄 둘을 뺐다. 경로는 세션 cwd 기준이고 윈도에서는 역슬래시다.
DIRECTORY_CONTENT = (
    "fixture\\korean.txt:2:[Omitted long matching line]\n"
    "fixture\\lines.txt:1:PROBE short\n"
    "fixture\\lines.txt:3:[Omitted long matching line]\n"
    "fixture\\wide.txt:1:[Omitted long matching line]"
)
# 손으로 받은 출력. 짧은 일치 줄 양옆의 600자 문맥 줄이 다른 표지로 생략됐다.
CONTEXT_ONLY = (
    "C:\\scratch\\omit\\ctx.txt-1-[Omitted long context line]\n"
    "C:\\scratch\\omit\\ctx.txt:2:PROBE short\n"
    "C:\\scratch\\omit\\ctx.txt-3-[Omitted long context line]"
)


def _페이로드(content: object, tool: str = TOOL, path: str | None = None) -> HookPayload:
    """content 모드 Grep 의 호출 입력. `path` 는 Grep 에 준 경로다."""
    tool_input: ToolInput = {"pattern": "PROBE", "output_mode": "content"}
    if path is not None:
        tool_input["path"] = path
    return {
        "tool_name": tool,
        "tool_input": tool_input,
        "tool_response": {"mode": "content", "content": content, "numLines": 1},
    }


def test_디렉터리를_훑은_결과의_생략된_일치_줄을_수와_자리로_알린다() -> None:
    context = context_for(_페이로드(DIRECTORY_CONTENT))

    assert context is not None
    assert context.startswith(LEAD)
    assert "3개" in context
    for place in ("fixture\\korean.txt:2", "fixture\\lines.txt:3", "fixture\\wide.txt:1"):
        assert place in context, place
    assert "fixture\\lines.txt:1" not in context
    assert "`-n`" not in context
    assert "limit 에 1" in context


def test_입력이_객체가_아니어도_터지지_않고_결과로_알린다() -> None:
    """PostToolUse 의 예외는 지나가지만 알림이 빠진다. 실제 Grep 은 객체를 주지만 모양에 기대지
    않는다."""
    payload: HookPayload = json.loads(
        json.dumps(
            {
                "tool_name": TOOL,
                "tool_input": None,
                "tool_response": {"mode": "content", "content": DIRECTORY_CONTENT},
            }
        )
    )

    assert context_for(payload) is not None


def test_파일_하나를_줄_번호와_훑으면_자리에_입력의_경로를_붙인다() -> None:
    """파일 하나를 주면 결과의 줄에 경로가 없고 줄 번호만 있다(손으로 받은 `11:` 꼴)."""
    payload = _페이로드(f"7:MARK500 x\n11:{MARKER}", path="C:/scratch/omit/lens.txt")

    context = context_for(payload)

    assert context is not None
    assert "C:/scratch/omit/lens.txt:11" in context
    assert "1개" in context


def test_줄_번호_없이_훑은_결과는_경로만_들고_n을_켜라고_한다() -> None:
    context = context_for(_페이로드(f"C:\\scratch\\omit\\lens.txt:{MARKER}"))

    assert context is not None
    assert "C:\\scratch\\omit\\lens.txt" in context
    assert "`-n`" in context


def test_파일_하나를_줄_번호_없이_훑으면_줄이_표지_그대로이고_자리는_입력의_경로다() -> None:
    context = context_for(_페이로드(f"MARK400 x\n{MARKER}", path="C:/scratch/omit/lens.txt"))

    assert context is not None
    assert "C:/scratch/omit/lens.txt" in context
    assert "1개" in context
    assert "`-n`" in context


def test_경로가_숫자로_끝나는_파일을_줄_번호_없이_훑으면_n을_켜라는_말만_빠진다() -> None:
    """못 보는 것: 끝의 `:12` 를 줄 번호로 읽는다(거짓 음성). 알림과 자리는 나간다."""
    context = context_for(_페이로드(f"MARK400 x\n{MARKER}", path="C:/scratch/omit/log:12"))

    assert context is not None
    assert context.startswith(LEAD)
    assert "C:/scratch/omit/log" in context
    assert "`-n`" not in context


def test_생략된_문맥_줄만_있으면_일치를_숨기지_않아_침묵한다() -> None:
    assert context_for(_페이로드(CONTEXT_ONLY)) is None


def test_생략된_줄이_없으면_침묵한다() -> None:
    assert context_for(_페이로드("fixture\\lines.txt:1:PROBE short")) is None


def test_열_개가_넘으면_앞의_열_자리만_들고_나머지는_수로_적는다() -> None:
    content = "\n".join(f"big.txt:{line}:{MARKER}" for line in range(1, 13))

    context = context_for(_페이로드(content))

    assert context is not None
    assert "12개" in context
    assert "big.txt:10" in context
    assert "big.txt:11" not in context
    assert "외 2개" in context
    assert "나머지는 위 결과" in context


def test_Grep이_아닌_도구와_content가_없는_결과는_보지_않는다() -> None:
    """content 가 아닌 모드(files_with_matches, count)에는 줄이 없다."""
    assert context_for(_페이로드(DIRECTORY_CONTENT, tool="Bash")) is None
    assert context_for(_페이로드(None)) is None
    assert context_for({"tool_name": TOOL}) is None
    files_only: HookPayload = {
        "tool_name": TOOL,
        "tool_response": {"mode": "files_with_matches", "filenames": ["a.txt"], "numFiles": 1},
    }
    assert context_for(files_only) is None
    count: HookPayload = {"tool_name": TOOL, "tool_response": {"mode": "count", "numMatches": 3}}
    assert context_for(count) is None


def test_표지_문구나_결과_객체의_키가_바뀐_판에는_침묵한다() -> None:
    """거짓 음성이다. 2.1.296 의 표지와 `content` 키에 기대므로, 판이 바뀌면 생략이 있어도
    지나간다."""
    renamed: HookPayload = {
        "tool_name": TOOL,
        "tool_response": {"mode": "content", "output": DIRECTORY_CONTENT},
    }
    assert context_for(renamed) is None
    reworded = DIRECTORY_CONTENT.replace(MARKER, "[Long matching line omitted]")
    assert context_for(_페이로드(reworded)) is None


def test_줄의_내용이_표지로_끝나는_일치도_생략으로_센다() -> None:
    """거짓 양성이다. 일지가 그 표지를 인용한 줄을 훑으면 내용이 보이는데도 알린다."""
    quoted = f"docs/journal/x.md:12:    541:{MARKER}"

    context = context_for(_페이로드(quoted))

    assert context is not None
    assert "docs/journal/x.md:12:    541" in context


def test_settings의_매처는_훅이_아는_도구_하나다() -> None:
    """매처를 넓히면 훅이 이름으로 걸러 조용히 지나가고, 이름을 바꾸면 등록이 훅을 걸지 않는다."""
    assert registered_matchers("hook_grep_omitted.py", "PostToolUse") == [TOOL]
