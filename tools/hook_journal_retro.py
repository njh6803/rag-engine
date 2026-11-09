"""PostToolUse 훅(Write|Edit). 일지를 단계를 닫는 모양으로 갱신하면 retro 계기를, 새 일지 파일의
이름이 시각 꼴(`<날짜>-<HHMM>-<슬러그>.md`)이 아니면 짓는 명령을 컨텍스트에 넣는다.

계기는 retro 스킬 설명("일지의 '다음' 절을 갱신하며 단계를 닫을 때")에 지침으로 있었는데
2026-09-21 세션에서 에이전트가 일지를 쓰고도 돌리지 않았다. 지침이 어겨졌으니 훅이다(CLAUDE.md
교정 루프). stdin 으로 훅 JSON 을 받고, 경로가 docs/journal/*.md 이면 additionalContext 를 낸다.

발동 조건은 넷이다. 쓴 본문 — Write 의 `content` 나 Edit 의 `new_string` — 이 줄 머리의 `## 다음`
제목을 담고, 그 절(다음 `#`·`##` 제목 전까지)에 자리 표시가 아닌 줄이 있고, Edit 이면 그 절이
`old_string` 의 절과 다르고, 쓰기 뒤의 일지 파일에 자리 표시가 아닌 `## 회고` 절이 아직 없을 때.
대기열 28(사용자 승인 2026-09-24)은 Write 를 무조건 계기로 두었는데, 세션 첫머리에 일지를 새로 쓰는
Write 는 단계를 닫는 것이 아니라 좁혔다(PR #91 리뷰). 경로만 보던 동안 인용 하나를 고친 Edit 마다
계기가 울렸다(대기열 28 의 5회차와 일지 2026-09-27-01·02 의 둘). 세션이 그것을 무시하는 법을
배우고, 무시하는 습관은 진짜 계기도 무시하게 만든다. 뒤의 세 조건도 같은 이유다. 부분 문자열로 보던
동안 일지 산문의 코드 스팬 `` `## 다음` `` 에 울렸다(대기열 74). 괄호 한 줄짜리 자리 표시로 절을
먼저 두자 울렸고, 회고를 그 절 앞에 적어 넣는 Edit — 절은 old_string 과 new_string 에 그대로 있다 —
에 다시 울렸다(대기열 62). retro 를 먼저 돌고 "다음" 을 적은 편집에도 울렸다(일지 2026-09-30-02,
2026-10-01-03). 회고 절은 retro 가 돈 흔적이라, 그것이 있으면 단계는 이미 닫혔다(사용자 결정
2026-10-01, 일지 2026-10-01-04).
못 보는 것: `## 다음` 제목 아래 불릿만 고친 Edit(제목이 new_string 에 없다). 그것은 절을 새로 쓴
것이 아니라 손본 것이라 계기가 아니다. 괄호 한 쌍으로 감싼 한 줄 밖의 자리 표시("TBD", "…", 번호
목록, 두 줄에 걸친 괄호, 괄호 안의 괄호)는 내용으로 본다. 펜스 코드 블록을 가리지 않는다 — 펜스 안의
`## 다음` 줄은 제목으로, 절 안 펜스의 `#`·`##` 줄은 절의 끝으로 본다. 기존 절을 그대로 둔 채 파일
전체를 다시 쓴 Write 에는 울린다(Write 의 입력에는 앞 내용이 없다). retro 를 돌았어도 회고 절을
적기 전에 "다음" 을 쓰면 울린다. 한 일지에 두 단계를 닫으면 둘째에는 울리지 않는다(첫 회고 절이
있다). 일지 파일을 읽지 못하면 회고 절이 없는 것으로 본다.

이름 꼴(ADR 0045 결정 7). 일지 이름은 `<날짜>-<HHMM>-<슬러그>.md` 이고 앞부분은 그 세션이 일지를
만든 로컬 시분이라 나눠 쓰는 번호가 없다. 새 일지를 만든 Write 의 파일 이름이 이 꼴이 아니면 짓는
명령(Bash 의 `date +%Y-%m-%d-%H%M`, PowerShell 의 `Get-Date -Format yyyy-MM-dd-HHmm`)과 원천
(`docs/constitution/operations.md` 의 일지 규칙)을 알린다. 옛 꼴(`<날짜>-<NN>-…`)을 습관대로 만든
세션을 커밋 전에 일지 이름 시험(`tests/test_journal_names.py`)이 잡기 전에 알리려는 것이다. 새
파일인지는 Write 결과의 `type` 이 `create` 인지로 가른다(덮어쓰면 `update`, Edit 의 결과에는 그 값이
없다. 2026-10-16 claude 2.1.300, `.scratch/harness/probes/journal_number_hook/run.py` 의 A). 파일
이름만 보고 자식 프로세스를 띄우지 않는다. 번호를 대 보던 옛 판은 `tools/sibling_overlap.py` 를
자식으로 돌려 한 번에 9~11초가 들었고, 시간 제한도 그만큼 길게 잡아야 했다.
못 보는 것(이름 꼴): 꼴만 맞고 시각이 지금이 아닌 이름(`2026-11-07-9999-x.md`, 어제 시각), 날짜가
실제로 있는 날인지, Write 가 아닌 길로 만든 일지(Bash 의 `cat >`·`mv`·`git mv`, PowerShell), 이미
있는 경로를 덮어쓴 Write(`update`), 같은 분의 겹침(`tests/test_journal_names.py` 가 커밋 전에 본다),
계기를 읽기 전에 컨텍스트가 압축되어 알림이 사라진 것.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import TypedDict

JOURNAL_PARTS = ("docs", "journal")
# 줄 머리의 제목만. 산문의 코드 스팬 `## 다음` 은 제목이 아니다(대기열 74).
CLOSING_HEADING = re.compile(r"^## 다음[ \t\r]*$", re.MULTILINE)
# `## 회고` 와 `## 회고 (2026-09-21, 슬라이스를 닫은 뒤)` 같은 덧붙인 제목.
RETRO_HEADING = re.compile(r"^## 회고(?:[ \t].*)?\r?$", re.MULTILINE)
# 절은 다음 `#`·`##` 제목에서 끝난다. `###` 는 절 안이다.
SECTION_END = re.compile(r"^#{1,2} ", re.MULTILINE)
# 괄호 한 쌍으로 감싼 한 줄(불릿이어도). "(회고 뒤에 채운다)" 같은 자리 표시다(대기열 62).
# 안에 괄호가 또 있으면 `(web-admin) 04 가 다음이다 (05~08)` 같은 내용일 수 있다.
PLACEHOLDER = re.compile(r"^(?:[-*] +)?[(（][^()（）]*[)）]$")
# `<날짜>-<HHMM>-<슬러그>.md`. `tests/test_journal_names.py` 의 새 꼴과 같다
STAMPED_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-.+\.md$")


class ToolInput(TypedDict, total=False):
    file_path: str
    content: str
    old_string: str
    new_string: str


class HookPayload(TypedDict, total=False):
    """Claude Code 가 stdin 으로 주는 훅 입력 중 이 훅이 읽는 부분."""

    tool_name: str
    tool_input: ToolInput
    tool_response: dict[str, object]


CONTEXT = (
    "docs/journal/ 의 일지를 단계를 닫는 모양으로 갱신했다('다음' 절을 새로 썼다). "
    "retro 스킬의 계기다. 사용자에게 묻지 말고 Skill 도구로 retro 를 지금 돌린다."
)
NAME_LEAD = "새 일지 파일의 이름이 `<날짜>-<HHMM>-<슬러그>.md` 꼴이 아니다."
# 옮길 때의 길. Write 로 새 이름을 만들고 옛 파일을 남기면 일지가 둘이 된다
RENAME_NOTE = (
    "이름은 바꾼다(`mv <옛> <새>`). Write 로 새 이름을 만들고 옛 파일을 남기면 일지가 둘이 된다."
)


def is_journal(file_path: str) -> bool:
    """docs/journal/<name>.md 인가."""
    path = PurePath(file_path.replace("\\", "/"))
    parts = path.parts
    if path.suffix != ".md" or len(parts) < 3:
        return False
    return tuple(parts[-3:-1]) == JOURNAL_PARTS


def _body_after(text: str, start: int) -> str:
    """`start`(제목 줄 끝)부터 다음 `#`·`##` 제목 전까지. 앞뒤 공백은 벗긴다."""
    rest = text[start:]
    end = SECTION_END.search(rest)
    return (rest[: end.start()] if end else rest).strip()


def section_body(text: str, heading: re.Pattern[str]) -> str | None:
    """`heading` 의 첫 절의 본문. 제목이 없으면 None."""
    found = heading.search(text)
    return None if found is None else _body_after(text, found.end())


def is_written(body: str) -> bool:
    """절에 자리 표시가 아닌 줄이 하나라도 있는가."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return any(not PLACEHOLDER.match(line) for line in lines)


def retro_recorded(journal: str) -> bool:
    """자리 표시가 아닌 회고 절이 하나라도 있는가. 날짜를 붙인 회고 절이 더해질 수 있어 첫 절만
    보지 않는다."""
    return any(
        is_written(_body_after(journal, found.end())) for found in RETRO_HEADING.finditer(journal)
    )


def context_for(
    tool_name: str,
    file_path: str,
    text: str | None,
    previous: str | None = None,
    journal: str | None = None,
) -> str | None:
    """단계를 닫는 일지 갱신이면 컨텍스트 문장, 아니면 None. `text` 는 Write 의 content 나 Edit 의
    new_string, `previous` 는 Edit 의 old_string, `journal` 은 쓰기 뒤의 일지 전체다."""
    if not is_journal(file_path) or tool_name not in ("Write", "Edit") or text is None:
        return None
    closing = section_body(text, CLOSING_HEADING)
    if closing is None or not is_written(closing):
        return None
    if previous is not None and section_body(previous, CLOSING_HEADING) == closing:
        return None
    if journal is not None and retro_recorded(journal):
        return None
    return CONTEXT


def read_journal(file_path: str) -> str | None:
    """쓰기 뒤의 일지 전체. 읽지 못하면 None 이다."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def created_journal(tool_name: str, file_path: str, response: Mapping[str, object] | None) -> bool:
    """새 일지 파일을 만든 Write 인가. 결과의 `type` 이 `create` 다."""
    return (
        tool_name == "Write"
        and is_journal(file_path)
        and response is not None
        and response.get("type") == "create"
    )


def name_context(file_path: str) -> str | None:
    """새 일지의 이름이 시각 꼴이 아니면 알릴 문장, 맞으면 None."""
    name = PurePath(file_path.replace("\\", "/")).name
    if STAMPED_NAME.match(name):
        return None
    return (
        f"{NAME_LEAD} 만든 파일은 `{name}` 이다. 앞부분은 지금의 로컬 날짜와 시분이고 Bash 의"
        " `date +%Y-%m-%d-%H%M` 이나 PowerShell 의 `Get-Date -Format yyyy-MM-dd-HHmm` 으로 짓는다"
        "(`docs/constitution/operations.md` 의 일지 규칙). 번호는 받지 않는다."
        f" {RENAME_NOTE} 이 일지를 든 인용이 있으면 함께 고친다."
    )


def main() -> int:
    payload: HookPayload = json.load(sys.stdin.buffer)
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path")
    if file_path is None:
        return 0
    tool_name = payload.get("tool_name", "")
    if tool_name == "Write":
        text, previous = tool_input.get("content"), None
    else:
        text, previous = tool_input.get("new_string"), tool_input.get("old_string")
    # 일지가 아닌 파일은 읽지 않는다. context_for 도 같은 조건으로 거르지만 읽기가 그보다 먼저다.
    journal = read_journal(file_path) if is_journal(file_path) else None
    contexts = [context_for(tool_name, file_path, text, previous, journal)]
    if created_journal(tool_name, file_path, payload.get("tool_response")):
        contexts.append(name_context(file_path))
    context = "\n\n".join(item for item in contexts if item is not None)
    if not context:
        return 0
    print(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
