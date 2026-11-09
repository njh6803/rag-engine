"""ADR 포인터 검사. 본문의 `(바뀜: ...)` 포인터가 가리키는 이력 제목과 맞는지 본다(대기열 97).

포인터 규약은 `.claude/rules/adr.md`다. 이력이 본문 문장을 바꾸면 그 문장 뒤에 포인터를 달고,
제목은 가리키는 ADR(앞에 `ADR NNNN`이 없으면 자기 ADR)의 `## 이력` 안 `###` 줄에서 날짜 뒤를
글자 그대로 옮긴다. 이 검사는 PR #124의 스크래치 프로브를 옮긴 것이다. 프로브는 아무도 자동으로
돌리지 않았고, 손으로 쓴 정규식이 첫 판에서 `(바뀜: ADR NNNN)` 둘을 세지 않았으며, 번호 뒤 공백이
빠진 모양과 `## 이력` 밖의 `###` 줄은 CodeRabbit이 잡았다.

잡는 것:
- 모양이 틀린 `(바뀜:`. 모양은 셋이다 — `(바뀜: 이력 날짜 "제목")`,
  `(바뀜: ADR NNNN 이력 날짜 "제목")`, `(바뀜: ADR NNNN)`. 날짜는 `YYYY-MM-DD`, 번호는 네 자리,
  낱말 사이 공백은 꼭 하나다.
- 가리킨 이력 제목이 그 ADR의 `## 이력` 절에 없다. 같은 모양의 `###` 줄이 이력 밖에 있어도
  없는 것이다.
- 없는 ADR을 가리킨다.
- 포인터가 `## 이력` 절 안에 있다. 포인터는 본문의 표시이고, 지난 이력 항목은 기록이다.
  이력 절은 제목이 정확히 `## 이력`인 절이고 다음 `##` 제목에서 끝난다. `## 개정 이력`(0006)은
  이력 절이 아니다.
- 번호가 겹친 ADR 파일. 둘 다 판정하고 그 번호를 가리키는 포인터는 둘의 이력 제목을 함께 본다.
- ADR 파일이 하나도 없는 것. 디렉터리를 잘못 가리키면 빈 범위가 조용히 초록이 된다.

코드로 보지 않는 것: 펜스 안의 줄(그 안의 `## 이력`도 절을 바꾸지 않는다), 그리고 바로 앞이
백틱인 `(바뀜:`(코드 스팬으로 적은 모양의 예시).

못 보는 것: 포인터가 달려야 하는데 없는 본문 문장, 그리고 제목이 맞아도 그 이력이 정말 그
문장을 바꿨는지. 둘 다 뜻의 판단이라 사람과 리뷰가 본다. 코드 스팬이 `(바뀜:` 바로 앞에서
시작하지 않으면(`` `예: (바뀜: …)` ``) 포인터로 읽는다. 한 줄에 모양이 틀린 것이 여럿이면 줄마다
한 번 알린다.

사용: `uv run python tools/check_adr_pointers.py [ADR 디렉터리]`. 인자가 없으면 `docs/adr`.
pytest의 저장소 상태 테스트(`tests/tools/test_check_adr_pointers.py`)가 돌리고, 따로 게이트를
두지 않는다.
"""

from __future__ import annotations

import io
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = ROOT / "docs" / "adr"
MARK = "(바뀜:"
HISTORY_HEADING = "## 이력"
# 바로 앞이 백틱인 `(바뀜:`은 코드 스팬으로 적은 예시다(규약 문서가 모양을 그렇게 적는다).
# 두 정규식이 이 접두를 함께 써야 모양 틀림의 개수 대조가 맞는다(PR #125 claude-review).
_OUTSIDE_CODE = r"(?<!`)"
_MARK_OUTSIDE_CODE = re.compile(_OUTSIDE_CODE + r"\(바뀜:")
POINTER = re.compile(
    _OUTSIDE_CODE + r"\(바뀜: (?:"
    r'이력 (?P<date>\d{4}-\d{2}-\d{2}) "(?P<title>[^"]+)"'
    r"|ADR (?P<adr>\d{4})"
    r'(?: 이력 (?P<cited_date>\d{4}-\d{2}-\d{2}) "(?P<cited_title>[^"]+)")?'
    r")\)"
)
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_NUMBER = re.compile(r"(\d{4})-")

TitlesOf = Callable[[str], set[str] | None]


def _lines_with_section(text: str) -> Iterator[tuple[int, str, bool]]:
    """(1부터 센 줄 번호, 줄, 그 줄이 `## 이력` 절 안인가). `##` 제목 줄 자신은 그 절에 든다.

    펜스 안의 줄(여닫는 줄 포함)은 빈 줄로 낸다. 그 안의 `## 이력`과 `(바뀜:`은 코드다.
    """
    in_history = False
    fence = ""
    for number, line in enumerate(text.splitlines(), start=1):
        if fence:
            if _closes(fence, line):
                fence = ""
            yield number, "", in_history
            continue
        opening = _FENCE.match(line)
        if opening is not None:
            fence = opening.group(1)
            yield number, "", in_history
            continue
        if line.startswith("## "):
            in_history = line.strip() == HISTORY_HEADING
        yield number, line, in_history


def _closes(fence: str, line: str) -> bool:
    """같은 문자로 여는 펜스 이상 길게 쓰고 그 뒤에 공백만 있는 줄이 펜스를 닫는다(CommonMark)."""
    closing = _FENCE.match(line)
    return (
        closing is not None
        and closing.group(1).startswith(fence)
        and not line[closing.end() :].strip()
    )


def history_titles(text: str) -> set[str]:
    """`## 이력` 절 안의 `###` 제목(날짜 포함). 다른 `##` 절의 같은 모양 줄은 이력이 아니다."""
    return {
        line[4:].strip()
        for _, line, in_history in _lines_with_section(text)
        if in_history and line.startswith("### ")
    }


def problems_in(text: str, titles_of: TitlesOf) -> list[str]:
    """ADR 하나의 어긋남을 `줄: 이유`로 낸다.

    `titles_of`는 다른 ADR 번호를 받아 그 이력 제목을 주고, 그 ADR이 없으면 None이다.
    """
    own_titles = history_titles(text)
    found: list[str] = []
    for number, line, in_history in _lines_with_section(text):
        matches = list(POINTER.finditer(line))
        if len(_MARK_OUTSIDE_CODE.findall(line)) != len(matches):
            found.append(f"{number}: 모양이 맞지 않는 `{MARK}`가 있다")
        for match in matches:
            reason = "이력 절 안에 있다" if in_history else _reason(match, own_titles, titles_of)
            if reason is not None:
                found.append(f"{number}: {match.group(0)} — {reason}")
    return found


def _reason(match: re.Match[str], own_titles: set[str], titles_of: TitlesOf) -> str | None:
    cited = match.group("adr")
    titles = own_titles if cited is None else titles_of(cited)
    if titles is None:
        return f"ADR {cited}이 없다"
    date = match.group("date") or match.group("cited_date")
    title = match.group("title") or match.group("cited_title")
    if date is not None and f"{date} {title}" not in titles:
        return "가리킨 이력 제목이 없다"
    return None


def main(adr_dir: Path = ADR_DIR) -> int:
    """`adr_dir`의 `NNNN-*.md`를 모두 판정한다. 어긋남이 하나라도 있으면 1.

    ADR이 하나도 없으면 디렉터리를 잘못 가리킨 것이라 1이다(빈 범위의 초록은 판정이 아니다).
    번호가 겹친 파일은 모두 판정하고, 그 번호를 가리키는 포인터는 겹친 파일들의 이력 제목을
    함께 본다.
    """
    adrs: list[tuple[str, Path, str]] = []
    for path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        number = _NUMBER.match(path.name)
        if number is not None:
            adrs.append((number.group(1), path, path.read_text(encoding="utf-8")))
    if not adrs:
        print(f"ADR 파일이 하나도 없다 — {adr_dir.as_posix()}를 가리킨 것이 맞는지 본다")
        return 1
    titles: dict[str, set[str]] = {}
    for number, _, text in adrs:
        titles.setdefault(number, set()).update(history_titles(text))
    numbers = [number for number, _, _ in adrs]
    problems: list[str] = []
    for number, path, text in adrs:
        if numbers.count(number) > 1:
            problems.append(f"{path.name}:0: ADR 번호 {number}이 다른 파일과 겹친다")
        problems.extend(f"{path.name}:{problem}" for problem in problems_in(text, titles.get))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ADR_DIR))
