"""마크다운 표 검사. 추적 마크다운의 표가 GFM 에서 깨지는 자리를 잡는다(대기열 44).

web-admin 설계 세션이 `.scratch/plan.md` 의 표를 두 번 깨뜨렸고 검사는 전부 초록이었다.
한 번은 칸 안에 줄바꿈 목록을 넣은 것이고(목록 줄이 표를 끊는다), 한 번은 코드 스팬 안의
`|` 다 — GFM 은 코드 스팬 안의 파이프도 칸 구분으로 읽는다(GFM 명세 표 확장, "Include a pipe
in a cell’s content by escaping it, including inside other inline spans").

**GFM 의 블록 파싱을 옮긴 것이다.** 표는 줄 두 개로 판정되지 않는다. cmark-gfm 은 줄마다
열린 컨테이너(인용 `>`, 목록 항목과 각주 정의의 들여쓰기)를 먼저 맞추고, 새 블록(제목·펜스·
HTML 블록·목록·들여쓴 코드)을 연 뒤, 남은 줄을 문단이나 표에 넣는다. 목록 문단의 게으른
연속 줄은 표가 되지 못하고, HTML 블록과 펜스 안은 표가 아니다. 이 파일은 그 알고리즘
(blocks.c 의 S_process_line)과 표 확장(extensions/table.c)을 옮겼다. cmark-gfm 과 견주는
차분 대조는 `.scratch/harness/probes/md_tables_vs_cmark.py` 다 — 저장소 마크다운 전부, 칸 수
한 줄씩, 표를 섞은 무작위 문서 18만 개에서 표의 모양(끝 줄과 본문 행)이 같았다(2026-09-29).

잡는 것(줄 번호는 개행으로 센다. CRLF·CR 도 줄 끝이고 BOM 은 벗긴다):
- 표의 행의 칸 수가 머리 행과 다르다. GFM 은 남는 칸을 버리고 모자란 칸을 빈 칸으로 채워
  조용히 렌더한다. 칸은 `|` 로 나누되 **바로 앞이 역슬래시인 `|` 는 역슬래시가 몇 개든
  내용이다**(칸 스캐너가 `(escaped_char|[^|\\r\\n])+` 의 최장 일치다). 앞뒤 파이프는 세지 않는다.
- 표 바로 아래에 빈 줄이 없다. 파이프 없는 줄도 칸 하나짜리 행이 되고, 목록·제목·인용·펜스·
  HTML·들여쓴 코드·수평선·각주 정의는 거기서 표를 끊는다(markdownlint MD058). 바깥 컨테이너가
  끝나서(다음 목록 항목, 인용 밖의 줄) 닫히는 표는 끊긴 것으로 보지 않는다. 다만 그 줄이 칸을
  나누는 `|` 를 품었으면 `>` 나 들여쓰기를 빠뜨린 행이라 끊긴 것이다.
- 표 안의 구분 행. 빈 줄 없이 붙은 표 둘은 하나가 되어 둘째 구분 행이 `---` 글자로 보인다.
- 표처럼 보이는데 표가 되지 않는 것. 머리 행에 칸을 나누는 `|` 가 있고 다음 줄이 구분 행
  모양일 때 — 칸 수가 다르다, 구분 행이 네 칸 이상 들여써졌다, 앞 목록·인용 문단의 게으른
  연속이다, 구분 행에 ASCII 가 아닌 공백(전각 공백 U+3000 등. GFM 의 공백은 스페이스·탭·
  \\v·\\f 뿐이다)이 있다, 같은 문단에서 앞 표 시도가 실패했다.

못 보는 것: 참조되지 않았거나 이름이 앞 정의와 겹친 각주 정의는 GitHub 에서 보이지 않는데
그 안의 표도 본다. 여러 줄에 걸친 링크 참조 정의(제목이 다음 줄로 넘어가는 것)는 한 줄짜리만
안다. 탭은 네 칸 단위로 먼저 편다(컨테이너 표식 사이에 걸친 탭의 부분 소비를 따로 두지 않는다).

사용: `uv run python tools/check_md_tables.py [파일 ...]`. 인자가 없으면 추적 마크다운
(`.md`, `.markdown`) 전부. pre-commit 은 스테이지된 마크다운을 한 프로세스로 넘긴다.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent

# pre-commit(identify) 이 markdown 으로 넘기는 확장자. 인자 없는 범위를 훅과 맞춘다. identify
# 2.6.19 의 EXTENSIONS 에서 잰 값이다(2026-09-29). identify 는 pre-commit 의 전이 의존이라 테스트가
# import 해 대조하지 않는다 — 의존성 선언은 ADR 이 먼저다(tech.md). 훅은 파일을 인자로 넘기므로
# identify 가 확장자를 더해도 새는 것은 인자 없는 범위뿐이다.
MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})
# 인덱스에서 내용이 있는 일반 파일의 모드. 160000(서브모듈)과 120000(링크)은 뺀다.
_REGULAR_MODES = frozenset({"100644", "100755"})
# `git ls-files` 를 기다리는 초(대기열 342). 인자 없이 돌 때(pytest 의 저장소 상태 시험, 손으로 칠
# 때)만 부른다. pre-commit 훅은 파일 이름을 넘겨 이 호출에 닿지 않는다.
CALL_TIMEOUT = 60
# 비 ASCII 문자는 chr() 로 만든다. 편집 도구가 역슬래시-u 이스케이프를 날것으로 저장한다.
_BOM = chr(0xFEFF)
# cmark 는 NUL 을 U+FFFD 로 바꾼 뒤 읽는다.
_REPLACEMENT = chr(0xFFFD)

# 성능: 정규식에서 같은 글자를 나눠 가질 수 있는 반복 둘은 소유 수량자(`*+`)로 둔다. 그렇지 않으면
# 끝에서 실패하는 긴 줄 하나에 제곱 시간이 든다(16KB 에 수 초 — PR #96 대체 리뷰가 쟀다).

# cmark-gfm 표 스캐너의 spacechar. 블록 들여쓰기는 스페이스만 센다(탭은 먼저 편다).
_SPACE = " \t\v\f"
# 뒤 공백은 소유 수량자다 — 패턴 끝의 `\|?[ \t\v\f]*` 과 같은 공백을 나눠 갖지 않게.
_MARKER = r"[ \t\v\f]*:?-+:?[ \t\v\f]*+"
_TABLE_START = re.compile(rf"\|?{_MARKER}(?:\|{_MARKER})*\|?[ \t\v\f]*")
_NON_ASCII_SPACE = re.compile(r"[^\S \t\v\f\n\r]")

_ATX = re.compile(r"#{1,6}(?:[ \t]|$)")
_SETEXT = re.compile(r"(?:=+|-+)[ \t]*")
_FENCE_OPEN = re.compile(r"(?P<fence>`{3,}|~{3,})(?P<info>.*)")
# 순서 목록의 번호는 ASCII 숫자만이다(`\d` 는 전각·아랍 숫자에도 맞는다).
_LIST_MARKER = re.compile(r"[-+*]|(?P<number>[0-9]{1,9})[.)]")
# GitHub 은 각주를 켜고 렌더한다. 각주 정의는 네 칸 들여쓰기로 이어지는 컨테이너다.
_FOOTNOTE = re.compile(r"\[\^[^\] \r\n\x00\t]+\]:[ \t]*")
# 한 줄짜리 링크 참조 정의. 문단이 이것으로만 되어 있으면 아래 `---` 는 제목 밑줄이 아니라
# 문단의 글이 된다(cmark 가 참조를 먼저 풀고 남은 내용이 없으면 제목을 만들지 않는다).
# 라벨의 "비공백 글자 하나" 는 첫 번째 것으로 못박고 반복은 소유 수량자다 — 그 글자를 어디에 둘지
# 고르는 되감기가 없어야 `[` 로 시작하고 `]` 가 없는 긴 줄에서 선형이다.
_REFERENCE = re.compile(
    r"\[(?:[ \t]|\\.)*+[^\]\\ \t](?:[^\]\\]|\\.)*+\]:[ \t]*(?:<[^>]*>|\S+)"
    r"(?:[ \t]+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?[ \t]*"
)

# HTML 블록의 시작 일곱(CommonMark 4.6). 유형 7 은 문단을 끊지 못한다.
_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|"
    "dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h1|h2|h3|h4|h5|h6|"
    "head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|"
    "p|param|section|source|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_TAG_SPACE = r"[ \t\n\v\f\r]"
_ATTRIBUTE = (
    rf"{_TAG_SPACE}+[A-Za-z_:][A-Za-z0-9:._-]*"
    rf"(?:{_TAG_SPACE}*={_TAG_SPACE}*(?:[^ \t\n\v\f\r\"'=<>`]+|'[^']*'|\"[^\"]*\"))?"
)
# 태그 이름의 대소문자 무시는 ASCII 만이다(유니코드 IGNORECASE 는 U+017F·U+212A 를 s·k 로 맞춘다).
_TAG_CASE = re.IGNORECASE | re.ASCII
_HTML_STARTS: tuple[tuple[int, re.Pattern[str]], ...] = (
    (1, re.compile(r"<(?:script|pre|style|textarea)(?:[ \t\v\f>]|$)", _TAG_CASE)),
    (2, re.compile(r"<!--")),
    (3, re.compile(r"<\?")),
    (4, re.compile(r"<![A-Z]")),
    (5, re.compile(r"<!\[CDATA\[")),
    (6, re.compile(rf"</?(?:{_BLOCK_TAGS})(?:[ \t\v\f]|/?>|$)", _TAG_CASE)),
)
_HTML_START_7 = re.compile(
    rf"<(?:[A-Za-z][A-Za-z0-9-]*(?:{_ATTRIBUTE})*{_TAG_SPACE}*/?>"
    rf"|/[A-Za-z][A-Za-z0-9-]*{_TAG_SPACE}*>)[ \t\f]*$"
)
_HTML_ENDS = {
    1: re.compile(r"</(?:script|pre|style|textarea)>", _TAG_CASE),
    2: re.compile(r"-->"),
    3: re.compile(r"\?>"),
    4: re.compile(r">"),
    5: re.compile(r"\]\]>"),
}

_Kind = Literal["quote", "item", "footnote", "paragraph", "fence", "icode", "html", "table"]
_LEAVES = frozenset({"paragraph", "table"})
_LAZY = "앞 목록·인용 문단의 게으른 연속이다"


@dataclass(frozen=True)
class Row:
    """표의 본문 행 하나. `cells` 는 GFM 이 채우거나 버리기 전의 칸 수다."""

    line: int
    cells: int
    looks_like_delimiter: bool


@dataclass
class Table:
    """GFM 이 만드는 표 하나. `cut_line` 은 빈 줄 없이 표를 끝낸 줄이다."""

    header_cells: int
    delimiter_line: int
    rows: list[Row] = field(default_factory=list[Row])
    cut_line: int | None = None


@dataclass(frozen=True)
class Refused:
    """표처럼 보이지만 GFM 이 표로 만들지 않는 자리. `line` 은 머리 행이다."""

    line: int
    reason: str


@dataclass
class _Block:
    kind: _Kind
    # item: 내용이 시작하는 열(표식 앞 들여쓰기 + 표식 폭 + 여백). 이어지는 줄은 이만큼 들여쓴다.
    offset: int = 0
    # item: 자식 블록이 생겼나. 첫 줄이 빈 항목은 다음 빈 줄에서 끝난다.
    has_child: bool = False
    fence: str = ""
    html_type: int = 0
    lines: list[tuple[int, str]] = field(default_factory=list[tuple[int, str]])
    # paragraph: 구분 행 모양의 줄이 칸 수로 표를 열지 못했다. cmark-gfm 은 그 문단에서 표를
    # 다시 열지 않는다(차분 대조가 찾았다). 빈 줄로 새 문단을 시작하면 열린다.
    visited: bool = False
    table: Table | None = None


def _pipe_end(text: str, index: int) -> int:
    """`[|] spacechar*` 의 길이. 파이프가 아니면 0."""
    if index >= len(text) or text[index] != "|":
        return 0
    end = index + 1
    while end < len(text) and text[end] in _SPACE:
        end += 1
    return end - index


def _cell_length(text: str, index: int) -> int:
    """칸 스캐너의 최장 일치. 바로 앞이 역슬래시인 `|` 는 칸 안이다."""
    end = index
    while end < len(text):
        if text[end] == "|" and not (end > index and text[end - 1] == "\\"):
            break
        end += 1
    return end - index


def row_cells(content: str) -> int:
    """cmark-gfm 의 row_from_string 이 한 줄에서 세는 칸 수. 행이 아니면 0."""
    offset = _pipe_end(content, 0)
    count = 0
    while offset < len(content):
        cell = _cell_length(content, offset)
        pipe = _pipe_end(content, offset + cell)
        if cell or pipe:
            count += 1
        offset += cell + pipe
        if not pipe:
            break
    return count


def _has_separator(content: str) -> bool:
    """칸을 나누는 `|` 가 있나. 머리 행이 표를 뜻했는지 가르는 데 쓴다."""
    return any(
        character == "|" and (index == 0 or content[index - 1] != "\\")
        for index, character in enumerate(content)
    )


def _thematic_stop(line: str, first: int) -> int:
    """`first` 부터가 수평선이면 -1, 아니면 수평선 글자(표식 하나·스페이스·탭)가 끊긴 자리.

    cmark 의 thematic_break_kill_pos 를 옮긴 것이다. 끊긴 자리보다 앞에서 다시 재면 같은 표식이라
    같은 자리에서 끊기므로, 부르는 쪽이 그 자리를 기억해 다시 재지 않는다. 그러지 않으면 한 줄에
    겹친 목록 표식(`- - - … a`)에서 단계마다 줄 끝까지 다시 잰다.
    """
    marker = line[first] if first < len(line) else ""
    if marker not in ("*", "-", "_"):
        return first
    count = 0
    end = first
    while end < len(line) and line[end] in (marker, " ", "\t"):
        count += line[end] == marker
        end += 1
    return -1 if end == len(line) and count >= 3 else end


def _after_quote_marker(line: str, first: int) -> int:
    """`first` 의 `>` 와 그 뒤의 선택 스페이스 하나를 지난 자리."""
    return first + 1 + (line[first + 1 : first + 2] == " ")


def _first_nonspace(line: str, position: int) -> tuple[int, int]:
    index = position
    while index < len(line) and line[index] == " ":
        index += 1
    return index, index - position


def _html_start(rest: str, *, in_paragraph: bool) -> int:
    for kind, pattern in _HTML_STARTS:
        if pattern.match(rest):
            return kind
    if not in_paragraph and _HTML_START_7.match(rest):
        return 7
    return 0


def _html_ends(content: str, kind: int) -> bool:
    pattern = _HTML_ENDS.get(kind)
    return pattern is not None and pattern.search(content) is not None


def _opens_fence(rest: str) -> str:
    opened = _FENCE_OPEN.fullmatch(rest)
    if opened is None:
        return ""
    fence = opened.group("fence")
    if fence[0] == "`" and "`" in opened.group("info"):
        return ""
    return fence


def _closes_fence(rest: str, fence: str) -> bool:
    run = len(rest) - len(rest.lstrip(fence[0]))
    return run >= len(fence) and rest[run:].strip(" \t") == ""


class _Parser:
    """cmark-gfm blocks.c 의 줄 처리(맞추기 → 새 블록 열기 → 게으른 연속 또는 내용 넣기)."""

    def __init__(self) -> None:
        self.stack: list[_Block] = []
        self.tables: list[Table] = []
        self.refused: list[Refused] = []

    def mark_cut(self, index: int, lineno: int) -> None:
        """`index` 부터 닫힐 표가 `lineno` 의 내용에 빈 줄 없이 끊겼다고 적는다.

        바깥 컨테이너가 끝나서(목록 항목의 들여쓰기가 줄었다, 인용의 `>` 가 없다) 닫히는 표는 대개
        끊긴 것이 아니다 — 다음 항목이나 목록 밖 문단은 표를 뜻한 줄이 아니다. 그 줄이 칸을 나누는
        `|` 를 품었을 때만 `feed` 가 이것을 부른다.
        """
        for block in self.stack[index:]:
            if block.table is not None:
                block.table.cut_line = lineno

    def close_from(self, index: int) -> None:
        """`index` 부터 닫는다."""
        del self.stack[index:]

    def open(self, container: int, lineno: int, block: _Block | None) -> int:
        """새 블록을 연다. 맞지 않은 블록과 블록을 품지 못하는 잎(문단·표)은 여기서 닫힌다.

        `block` 이 None 이면 한 줄짜리 잎(ATX 제목, 수평선)이라 스택에 남기지 않는다.
        """
        keep = container + 1
        if keep > 0 and self.stack[keep - 1].kind in _LEAVES:
            keep -= 1
            self.mark_cut(keep, lineno)
        self.close_from(keep)
        if self.stack and self.stack[-1].kind == "item":
            self.stack[-1].has_child = True
        if block is not None:
            self.stack.append(block)
        return len(self.stack) - 1

    def feed(self, lineno: int, raw: str) -> None:
        line = raw.expandtabs(4)
        position = 0
        matched = 0
        # cmark 의 first_nonspace 캐시. position 은 한 줄 안에서 줄지 않으므로, 앞서 찾은 첫
        # 비공백이 position 뒤에 있으면 그대로 맞다. 캐시가 없으면 컨테이너마다 같은 공백을 다시
        # 세어 깊은 중첩에서 제곱 이상이 된다(PR #96 대체 리뷰).
        scanned = -1
        thematic_kill = 0

        def first_nonspace() -> tuple[int, int]:
            nonlocal scanned
            if scanned < position:
                scanned, _ = _first_nonspace(line, position)
            return scanned, scanned - position

        for block in self.stack:
            first, indent = first_nonspace()
            blank = first == len(line)
            if block.kind == "quote":
                if indent > 3 or blank or line[first] != ">":
                    break
                position = _after_quote_marker(line, first)
            elif block.kind == "item":
                if indent >= block.offset:
                    position += block.offset
                elif blank and block.has_child:
                    position = first
                else:
                    break
            elif block.kind == "footnote":
                # 빈 줄은 정말 비어 있을 때만 잇는다(공백만 있는 줄은 끊는다, cmark-gfm 의 모양).
                if indent >= 4:
                    position += 4
                elif raw != "":
                    break
            elif block.kind == "fence":
                if indent <= 3 and _closes_fence(line[first:], block.fence):
                    self.stack.pop()
                    return
            elif block.kind == "icode":
                if indent >= 4:
                    position += 4
                elif blank:
                    position = first
                else:
                    break
            elif block.kind == "html":
                if blank and block.html_type >= 6:
                    break
            elif blank or (block.kind == "table" and row_cells(line[first:]) == 0):
                break
            matched += 1

        all_matched = matched == len(self.stack)
        maybe_lazy = bool(self.stack) and self.stack[-1].kind == "paragraph"
        container = matched - 1
        opened = False
        while True:
            kind = self.stack[container].kind if container >= 0 else "document"
            if kind in ("fence", "icode", "html"):
                break
            first, indent = first_nonspace()
            blank = first == len(line)
            rest = line[first:]
            indented = indent >= 4
            thematic = False
            if not indented and first >= thematic_kill:
                stop = _thematic_stop(line, first)
                thematic = stop < 0
                thematic_kill = max(thematic_kill, stop)
            if not indented and rest.startswith(">"):
                container = self.open(container, lineno, _Block("quote"))
                position = _after_quote_marker(line, first)
            elif not indented and _ATX.match(rest):
                self.open(container, lineno, None)
                return
            elif not indented and (fence := _opens_fence(rest)):
                self.open(container, lineno, _Block("fence", fence=fence))
                return
            elif not indented and (html := _html_start(rest, in_paragraph=kind == "paragraph")):
                self.open(container, lineno, _Block("html", html_type=html))
                if _html_ends(rest, html):
                    self.stack.pop()
                return
            elif not indented and kind == "paragraph" and _SETEXT.fullmatch(rest):
                paragraph = self.stack[container]
                if all(_REFERENCE.fullmatch(text) for _, text in paragraph.lines):
                    paragraph.lines = [(lineno, rest)]
                else:
                    self.stack.pop()
                return
            elif not indented and thematic:
                self.open(container, lineno, None)
                return
            elif not indented and (footnote := _FOOTNOTE.match(rest)):
                container = self.open(container, lineno, _Block("footnote"))
                position = first + footnote.end()
            elif indent < 4 and (
                width := self._list_marker(rest, interrupts_paragraph=kind == "paragraph")
            ):
                after = rest[width:]
                spaces = min(len(after) - len(after.lstrip(" ")), 6)
                if spaces >= 5 or spaces < 1 or after.strip(" ") == "":
                    padding, skip = width + 1, min(spaces, 1)
                else:
                    padding, skip = width + spaces, spaces
                container = self.open(container, lineno, _Block("item", offset=indent + padding))
                position = first + width + skip
            elif indented and not maybe_lazy and not blank:
                self.open(container, lineno, _Block("icode"))
                return
            elif kind == "paragraph" and self._try_header(
                container, lineno, rest, indented=indented
            ):
                return
            elif kind == "table" and not indented and not blank:
                table = self.stack[container].table
                if table is not None:
                    looks = _TABLE_START.fullmatch(rest) is not None
                    table.rows.append(Row(lineno, row_cells(rest), looks))
                return
            else:
                break
            opened = True
            maybe_lazy = False

        first, _ = first_nonspace()
        blank = first == len(line)
        tip = self.stack[-1] if self.stack else None
        if not opened and not all_matched and tip is not None and tip.kind == "paragraph":
            if not blank:
                self._note_refused(tip, lineno, line[first:], _LAZY)
                # cmark 는 게으른 줄을 앞 공백째 문단에 넣는다. 그 줄이 머리 행이 되면 앞 공백이
                # 빈 칸 하나로 세어진다(차분 대조가 찾았다).
                tip.lines.append((lineno, line[position:]))
                return
        if not opened:
            # 여기서 닫히는 표는 둘이다. 표 자신이 줄을 받지 못했거나(칸이 없는 `|` 뿐인 줄),
            # 바깥 컨테이너가 끝났다. 어느 쪽이든 그 줄이 칸을 나누는 `|` 를 품은 내용이면 행을
            # 뜻했으니 끊긴 것이다 — 뒤의 것은 인용의 `>` 나 목록의 들여쓰기를 빠뜨린 행이다(셀프
            # 리뷰가 찾았다). 빈 줄과 `|` 없는 줄은 표를 뜻한 줄이 아니다.
            tip_is_table = tip is not None and tip.kind == "table"
            stray_row = tip_is_table and not blank and _has_separator(line[first:])
            if stray_row:
                self.mark_cut(matched, lineno)
            self.close_from(matched)
        tip = self.stack[-1] if self.stack else None
        if tip is not None and tip.kind in ("fence", "icode"):
            return
        if tip is not None and tip.kind == "html":
            if _html_ends(line[position:], tip.html_type):
                self.stack.pop()
            return
        if blank:
            return
        if tip is not None and tip.kind == "paragraph":
            tip.lines.append((lineno, line[first:]))
            return
        if tip is not None and tip.kind == "item":
            tip.has_child = True
        self.stack.append(_Block("paragraph", lines=[(lineno, line[first:])]))

    @staticmethod
    def _list_marker(rest: str, *, interrupts_paragraph: bool) -> int:
        """목록 표식의 폭. 표식이 아니면 0. 문단을 끊을 때는 1 로 시작하고 내용이 있어야 한다."""
        marker = _LIST_MARKER.match(rest)
        # 표식 뒤는 스페이스나 줄 끝이어야 한다. \v·\f 는 여백이 아니다(`-\v|` 는 cmark 에서
        # 표의 머리 행이다, 차분 대조가 찾았다). 탭은 먼저 스페이스로 폈다.
        if marker is None or rest[marker.end() : marker.end() + 1] not in ("", " "):
            return 0
        if interrupts_paragraph:
            number = marker.group("number")
            if (number is not None and int(number) != 1) or rest[marker.end() :].strip(" ") == "":
                return 0
        return marker.end()

    def _try_header(self, container: int, lineno: int, rest: str, *, indented: bool) -> bool:
        """문단의 마지막 줄을 머리 행으로, 이 줄을 구분 행으로 표를 연다. 열었으면 True.

        True 는 "이 줄을 소비했다"는 뜻이라 `feed` 가 거기서 멈춘다. 명령과 질의가 한 몸인 것은
        cmark 의 try-open 함수(블록을 열어 보고 열었는지 돌려준다)를 그대로 옮긴 모양이다 — 나누면
        같은 판정을 두 번 한다(PR #96 리뷰가 짚었고 판단 항목으로 두었다).
        """
        paragraph = self.stack[container]
        if _TABLE_START.fullmatch(rest) is None:
            loose = _NON_ASCII_SPACE.sub(" ", rest)
            if _TABLE_START.fullmatch(loose) is not None and not indented:
                self._note_refused(paragraph, lineno, loose, "구분 행에 ASCII 가 아닌 공백이 있다")
            return False
        if indented:
            self._note_refused(paragraph, lineno, rest, "구분 행이 네 칸 이상 들여써졌다")
            return False
        if paragraph.visited:
            reason = "같은 문단에서 앞 구분 행이 표를 열지 못해 이 문단에서는 표가 열리지 않는다"
            self._note_refused(paragraph, lineno, rest, reason)
            return False
        _, header = paragraph.lines[-1]
        header_cells, delimiter_cells = row_cells(header), row_cells(rest)
        if header_cells != delimiter_cells:
            paragraph.visited = True
            reason = f"머리 행 {header_cells}칸, 구분 행 {delimiter_cells}칸"
            self._note_refused(paragraph, lineno, rest, reason)
            return False
        table = Table(header_cells, lineno)
        self.tables.append(table)
        self.stack[container] = _Block("table", table=table)
        return True

    def _note_refused(self, paragraph: _Block, lineno: int, rest: str, reason: str) -> None:
        """구분 행 모양의 줄이 표를 열지 못했다. 앞 줄이 칸을 나누면 표를 뜻한 것으로 본다."""
        if not paragraph.lines or _TABLE_START.fullmatch(rest) is None:
            return
        header_line, header = paragraph.lines[-1]
        if _has_separator(header) and header_line == lineno - 1:
            self.refused.append(Refused(header_line, reason))


def parse(text: str) -> tuple[list[Table], list[Refused]]:
    """문서 하나의 표와 표가 되지 못한 자리. BOM 을 벗기고 CRLF·CR 도 줄 끝으로 본다."""
    text = text.removeprefix(_BOM).replace("\0", _REPLACEMENT)
    lines = re.split(r"\r\n|\r|\n", text)
    parser = _Parser()
    for lineno, line in enumerate(lines, 1):
        parser.feed(lineno, line)
    return parser.tables, parser.refused


def problems_in(text: str) -> list[str]:
    """문서 하나의 어긋남. 항목은 `"<줄번호>: <무엇>"` 이고 줄 순서다."""
    tables, refused = parse(text)
    found: list[tuple[int, str]] = []
    for table in tables:
        for row in table.rows:
            if row.cells != table.header_cells:
                found.append((row.line, f"칸 {row.cells}, 머리 행 {table.header_cells}"))
            elif row.looks_like_delimiter:
                found.append((row.line, "표 안의 구분 행 — 빈 줄 없이 붙은 표 둘이 하나가 됐다"))
        if table.cut_line is not None:
            found.append((table.cut_line, "표 바로 아래에 빈 줄이 없다 — 여기서 표가 끊긴다"))
    found.extend((item.line, f"{item.reason} — 표로 읽히지 않는다") for item in refused)
    return [f"{line}: {message}" for line, message in sorted(found, key=lambda pair: pair[0])]


def tracked_markdown(root: Path = ROOT) -> list[Path]:
    """인덱스의 일반 마크다운 파일 중 작업 트리에 있는 것. 인자 없이 부를 때의 범위다. git 이
    실패하거나 `CALL_TIMEOUT` 초 안에 돌아오지 않으면 예외로 멈춘다."""
    listing = subprocess.run(
        ["git", "ls-files", "-s", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
        timeout=CALL_TIMEOUT,
    )
    files: list[Path] = []
    seen: set[str] = set()
    # UTF-8 이 아닌 경로 이름은 surrogateescape 로 살린다(열 때 읽을 수 없어 어긋남이 된다). 병합
    # 충돌 중에는 같은 경로가 단계 1·2·3 으로 세 번 나오므로 한 번만 훑는다.
    for entry in listing.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not entry:
            continue
        meta, name = entry.split("\t", 1)
        path = root / name
        if (
            name not in seen
            and meta.split(" ", 1)[0] in _REGULAR_MODES
            and path.suffix.lower() in MARKDOWN_SUFFIXES
            and path.is_file()
        ):
            seen.add(name)
            files.append(path)
    return files


def _problems_of(path: Path) -> list[str]:
    try:
        text = path.read_bytes().decode("utf-8")
    except OSError as error:
        return [f"0: 파일을 읽을 수 없어 판정하지 못했다 ({error.strerror})"]
    except UnicodeDecodeError as error:
        return [f"0: UTF-8 로 읽을 수 없어 판정하지 못했다 ({error.reason}, 바이트 {error.start})"]
    return problems_in(text)


def main(paths: list[Path] | None = None, root: Path = ROOT) -> int:
    """`paths` 를(없으면 추적 마크다운 전부) 훑는다. 어긋남이 하나라도 있으면 1."""
    problems: list[str] = []
    for path in paths if paths is not None else tracked_markdown(root):
        shown = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        problems.extend(f"{shown}:{problem}" for problem in _problems_of(path))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")
    raise SystemExit(main([Path(argument) for argument in sys.argv[1:]] or None))
