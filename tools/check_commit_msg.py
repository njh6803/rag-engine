"""커밋 메시지 검사. 컨벤셔널 커밋 형식을 기계가 판정한다.

- 제목은 `<타입>: <제목>` 또는 `<타입>(<범위>): <제목>`. 타입은 git-commit 스킬의 표와 같다.
- 제목은 72자 이하, 끝에 마침표 없음.
- 제목은 git 처럼 첫 문단(앞의 빈 줄을 건너뛰고 다음 빈 줄까지)이다. git 은 그 줄들을 공백 하나로
  이어 제목으로 기록하므로(`git log --format=%s`), 줄이 여럿이면 제목 줄 뒤에 빈 줄이 없다고 잡는다.
  둘째 줄이 짧으면 이은 제목도 형식과 길이를 지나기 때문이다. 메시지 파일에서 그 빈 줄이 빠진 커밋이
  첫 줄만 보던 이 검사를 지났다(일지 2026-10-30-09 "봇 회차"). 줄은 git 처럼 `\n` 에서만 가르고,
  빈 줄과 줄 끝 공백은 git 의 ASCII 공백 넷(`GIT_SPACE`)으로 가른다. 파이썬의 `splitlines()` 와
  `strip()` 은 U+2028·`\x85`·NBSP·U+3000 도 따라 git 과 다르게 읽었다(PR 직전 버그 리뷰).
- Merge, Revert, fixup!, squash! 로 시작하는 메시지는 통과시킨다.

못 보는 것: `#` 로 시작하는 줄은 늘 건너뛴다. 편집기를 여는 커밋에서는 git 도 그 줄을 지우지만,
`-F` 로 넘긴 메시지에서는 남겨 제목으로도 읽는다. 그래서 `#` 줄이 제목 문단에 든 `-F` 메시지는
git 과 다르게 읽어 지나간다(시험이 실제 git 의 `%s` 와 견주어 고정한다). 견준 것은 기본 정리 모드의
`-F` 커밋이고, `--cleanup` 으로 정리 모드를 바꾼 커밋은 재지 않았다.

pre-commit의 commit-msg 스테이지가 돌린다. 산문 규칙(`docs/constitution/operations.md`)은
"왜와 남긴 위험을 본문에"이고 그것은 리뷰가 본다. 여기는 형식만.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPES = ("feat", "fix", "docs", "style", "refactor", "test", "chore", "perf")
PATTERN = re.compile(r"^(" + "|".join(TYPES) + r")(\([\w\-./ ]+\))?!?: \S.*$")
PASS_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ")
MAX_SUBJECT = 72
# git 의 isspace(`sane_ctype`)가 공백으로 보는 넷. 파이썬의 `strip()` 은 NBSP·U+3000 도 벗긴다.
GIT_SPACE = " \t\n\r"


def first_paragraph(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#"):
            continue
        if line.strip(GIT_SPACE):
            lines.append(line.rstrip(GIT_SPACE))
        elif lines:
            break
    return lines


def subject_of(text: str) -> str:
    return " ".join(first_paragraph(text))


def problems_for(subject: str) -> list[str]:
    if subject.startswith(PASS_PREFIXES):
        return []
    problems: list[str] = []
    if PATTERN.match(subject) is None:
        problems.append(
            f"제목이 '<타입>: <제목>' 형식이 아니다: {subject!r}. 타입은 {', '.join(TYPES)}"
        )
    if len(subject) > MAX_SUBJECT:
        problems.append(f"제목 {len(subject)}자 > {MAX_SUBJECT}자")
    if subject.endswith("."):
        problems.append("제목 끝에 마침표를 쓰지 않는다")
    return problems


def problems_in(text: str) -> list[str]:
    subject = subject_of(text)
    problems = problems_for(subject)
    if len(first_paragraph(text)) > 1 and not subject.startswith(PASS_PREFIXES):
        problems.insert(0, "제목 줄 뒤에 빈 줄이 없어 git 이 다음 줄까지 이어 제목으로 읽는다")
    return problems


def main(path: str) -> int:
    # 줄바꿈을 바꾸지 않고 읽는다. 바꾸면 제목에 홀로 든 `\r` 이 줄을 가른다.
    with Path(path).open(encoding="utf-8", newline="") as message:
        problems = problems_in(message.read())
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
