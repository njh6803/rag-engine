"""주석·독스트링 감기. 파이썬 파일의 주석·독스트링 문단에서 넘친 줄을 어절 단위로 감는다.

ruff 는 한글을 폭 2로 센다. 편집 직후 훅(`hook_ruff_line_width`)이 넘친 줄을 알려 주지만 고치는 것은
손이라, 세션마다 스크래치에 감기 스크립트를 새로 지었다(대기열 112, 4회차). 그 스크립트들이 줄 끝을
CRLF 로 바꾸고, 빈 줄과 닫는 따옴표를 문단에 붙이고, 혼자 선 `사용:` 줄을 다음 문장에 붙이고, 코드
스팬을 줄에서 갈랐다(일지 2026-10-01-01, 2026-10-06-01). 이 도구는 그 넷을 시험으로 막는다.

감는 법. 넘친 줄의 꼬리 어절을 다음 줄 앞으로 넘긴다. 다음 줄이 넘치면 거듭하고, 문단의 끝 줄이면
같은 머리로 새 줄을 낸다. 짧은 줄을 끌어올려 합치지 않는다 — 문단을 통째로 다시 채우던 도우미가 혼자
선 줄을 다음 문장에 붙였다. 그래서 바뀌는 줄은 넘친 줄부터 넘침이 흡수되는 줄까지이고, 나머지 줄은
바이트 그대로다. 어절은 공백으로 가르되 코드 스팬(같은 수의 백틱 사이)은 가르지 않는다. 독스트링 끝
줄의 닫는 따옴표는 문단의 끝 줄에 붙어 다닌다. 원래 줄은 제 줄 끝(LF·CRLF)을 지키고, 새 줄은 원래 끝
줄의 줄 끝을 받는다.

문단은 머리(들여쓰기와 `#` 과 그 뒤 공백, 독스트링의 여는 따옴표)가 같은 줄의 연속이다. 주석은 앞이
공백뿐인 `#` 줄이고(줄 끝 주석은 아니다), 독스트링은 문장 자리에 홀로 선 세 따옴표
문자열이다(모듈·클래스·함수의 독스트링과 속성 아래의 문자열). 독스트링의 여는 줄 다음은 따옴표를 뺀
들여쓰기가 머리다. 경계는 틀려도 안전한 쪽으로 둔다 — 경계가 하나 더 있으면 줄이 조금 들쭉날쭉할
뿐이지만, 놓치면 문장이 합쳐진다. 빈 줄, 머리가 다른 줄(더 들여 쓴 예시), 닫는 따옴표만 선 줄, 지시
주석(`# noqa`, `#!`, SPDX 머리 등), `#` 바로 뒤에 공백이 없는 주석(`##` 제목, `#:` 속성 설명),
doctest 줄(`>>>`, `...`), 코드 펜스(백틱 셋)의 여닫는 줄과 그 안, 역슬래시로 끝나는 줄(다음 줄과
이어 읽힌다), 탭이 든 줄은 문단에 들지 않는다. 같은 까닭으로 역슬래시 바로 뒤에서는 끊지 않는다.
목록 표지(`- `, `1. `)나 이름표(`사용:`, `못 보는 것:`)로 시작하는 줄은 새 문단을 연다. 목록 항목의
이어지는 줄은 표지 너비만큼 더 들여 쓴다.

폭과 넘친 줄의 판정은 ruff 의 E501 을 따른다. 동아시아 넓은 글자는 2, 결합 문자·제어 문자·폭 없는
형식 문자와 조합형 한글의 가운뎃소리·끝소리 자모는 0, 나머지는 1이다. 공백으로 가른 덩어리가 하나인
줄, 끝 덩어리가 URL(`://`)이고 그 앞까지가 줄 길이 안인 줄,
`# SPDX-License-Identifier:`·`# SPDX-FileCopyrightText:` 줄은 넘친 줄이 아니다. 줄 끝 주석이 ruff 의
지시 주석(`# noqa: B010`, `# pyright:` 등)이면 그 앞의 코드만 재고, 코드를 들지 않은 `# noqa` 와
E501 을 든 noqa 는 그 줄을 넘친 줄로 보지 않는다. 그 판정들을 ruff 와 대조하는 것은
`.scratch/harness/probes/rewrap_width.py` 이고, 이 저장소의 줄과 그 프로브가 더한 줄만 잰다. 판정이
ruff 판에 묶여 있으니 ruff 를 올리면 그 프로브를 다시 돌린다. 줄 길이는 파일마다 ruff 처럼 조상에서
가장 가까운 설정(`.ruff.toml`, `ruff.toml`, `tool.ruff` 표가 든 `pyproject.toml`)에서 읽는다.
`lint.pycodestyle.max-line-length` 가 있으면 그것, 없으면 `line-length`, 그것도 없으면 ruff 의
기본값 88이다.

사용: `uv run python tools/rewrap_comments.py <파일> [<파일> ...]`. 파일을 고쳐 쓰고 감은 자리와
감은 뒤에도 넘친 줄을 줄마다 알린다. 종료 0 은 넘친 줄이 남지 않았다, 1 은 남았다, 2 는 인자가
없거나, 파일이나 설정을 읽지 못했거나, ruff 설정 밖이거나, 파이썬으로 파싱하지 못했거나(그 파일은
고치지 않는다), 고쳐 쓰지 못했다. 2가 나도 뒤의 파일은 마저 본다. 쓰기는 파일을 비운 뒤 쓰므로 쓰는
도중의 실패(디스크가 찼다)는 파일을 자를 수 있다.

못 보는 것: 코드 줄과 줄 끝 주석, 독스트링이 아닌 문자열(남았다고 알린다 — 코드 줄은 커밋 전
`ruff format` 이 감는다), 한 어절이 폭을 넘는 줄. 주석으로 막아 둔 코드는 산문으로 보고 감는다.
줄바꿈은 공백으로 읽는다. 그래서 공백 없이 이어지는 자리(괄호 앞, 가운뎃점 뒤)에서 끊어 둔 줄로
꼬리를 넘기면 그 사이에 공백이 하나 생긴다. 문단을 한 줄로 써 두고 이 도구로 감으면 공백에서만
끊긴다. 이름표도 목록 표지도 아닌 혼자 선 짧은 줄은 문단의 일부로 보아 앞줄에서 넘친 꼬리를 받는다.
짧은 줄을 채우지 않으므로 리뷰가 짚는 어색한 줄바꿈은 고치지 않는다. 주석으로 막은 코드, 공백 없는
줄바꿈, 혼자 선 짧은 줄의 셋은 시험이 지금의 동작으로 고정한다. 두 줄에 걸쳐 쓴 코드 스팬은 닫는
백틱이 다음 줄에서 새 스팬을 열어 그 줄의 나머지가 한 어절이 된다(감지 않고 남았다고 알린다). 이
저장소 밖의 드문 문자(일부 기호, 이 파이썬의 유니코드 표에 없는 코드 포인트)는 ruff 와 폭이 다를 수
있다(PR 직전 리뷰가 전체 코드 포인트를 손으로 쟀다). 설정의 `extend` 는 따라가지 않는다. 탭의 폭은
4로 어림하고 재지 않았다(`git grep -P '\\t' -- '*.py'` 로 손으로 본 2026-10-07 에 이 저장소의 파이썬
파일에는 탭이 없었다). 홀로 선 CR 이 든 파일은 감지 않는다 — 파이썬은 그것을 줄 끝으로 읽고 이
도구는 개행(`\\n`)으로만 가른다.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
# 이스케이프가 아니라 chr() 다. 편집 도구가 이스케이프를 날것으로 바꾼다(대기열 160).
BOM = chr(0xFEFF)
TAB_WIDTH = 4
ZERO_WIDTH_CATEGORIES = frozenset({"Mn", "Me", "Cf", "Cc"})
# 조합형 한글의 가운뎃소리·끝소리 자모(한글 자모, 한글 자모 확장-B). 첫소리 자모는 폭 2다.
JAMO_FOLLOWERS = ((0x1160, 0x11FF), (0xD7B0, 0xD7FF))
# ruff 의 `line-length` 기본값.
DEFAULT_LINE_LENGTH = 88
# 한 디렉터리 안에서 ruff 가 먼저 보는 순서.
RUFF_CONFIG_FILES = (".ruff.toml", "ruff.toml", "pyproject.toml")
LONE_CR = re.compile(r"\r(?!\n)")
COMMENT_HEAD = re.compile(r"[ \t]*#[ \t]*")
DOCSTRING_OPEN = re.compile(r"([ \t]*)[rRuU]?(\"\"\"|''')")
# ruff 가 E501 의 폭에서 빼는 줄 끝 지시 주석의 머리. `fmt:`·`mypy:`·`pragma:` 는 빼지 않는다(ruff
# 0.16.8, `.scratch/harness/probes/rewrap_width.py`).
RUFF_PRAGMAS = r"(?i:noqa)|nosec|(?:isort|type|pyright|pylint|flake8|ruff):"
RUFF_PRAGMA = re.compile(rf"#\s*(?:{RUFF_PRAGMAS})")
# 문단에 넣지 않는 주석. 도구가 읽는 꼴이다. `#!` 와 인코딩 표지(`# -*- coding`), SPDX 머리도 든다.
DIRECTIVE = re.compile(rf"{RUFF_PRAGMAS}|(?:fmt|mypy|pragma):|!|-\*-|SPDX-")
# 줄의 E501 을 끄는 noqa. 코드를 들지 않은 것과 E501 을 든 것.
NOQA_E501 = re.compile(r"#\s*(?i:noqa)(?!:)|#\s*(?i:noqa):.*\bE501\b")
# ruff 가 E501 에서 빼는 SPDX 머리 줄. `#` 뒤에 공백이 있어야 하고 다른 SPDX 태그는 들지 않는다(ruff
# 0.16.8, 프로브 `rewrap_width.py`).
SPDX = re.compile(r"[ \t]*#[ \t]+SPDX-(?:License-Identifier|FileCopyrightText):")
# doctest 의 입력 줄과 이어지는 줄.
DOCTEST = re.compile(r"(?:>>>|\.\.\.)(?: |$)")
FENCE = "```"
LIST_MARKER = re.compile(r"(?:[-*+]|\d+[.)]) +")
# 세 어절까지의 이름 뒤 쌍점. `https://` 와 `C:\` 는 쌍점 뒤가 공백이 아니라 들지 않는다.
LABEL = re.compile(r"[^\s:`]+(?: [^\s:`]+){0,2}:(?:\s|$)")
NOT_PROSE = "주석·독스트링 문단이 아니다(코드 줄은 커밋 전 `ruff format` 이 감는다)"
WORD_TOO_WIDE = "한 어절이 폭을 넘거나 머리만으로 폭이 찬다"
USAGE = "사용: uv run python tools/rewrap_comments.py <파일> [<파일> ...]"


@dataclass(frozen=True)
class Row:
    """문단에 들 수 있는 줄 하나. `head + text + tail` 이 줄이다."""

    index: int
    head: str
    text: str
    tail: str = ""
    # 독스트링의 여는 줄이면 그다음 줄들의 머리(따옴표를 뺀 들여쓰기).
    next_head: str | None = None
    # 문단에 넣지 않고 그대로 두는 주석(지시 주석, `#` 바로 뒤에 공백이 없는 주석).
    fixed: bool = False


@dataclass(frozen=True)
class Paragraph:
    rows: tuple[Row, ...]
    # 문단의 둘째 줄부터와 새로 낸 줄의 머리.
    continuation: str


@dataclass(frozen=True)
class RenderedLine:
    """새 소스의 줄 하나."""

    text: str
    # 그 줄의 CR. LF 로 끝나는 줄이면 빈 문자열이다.
    ending: str
    changed: bool


@dataclass(frozen=True)
class Rewrapped:
    source: str
    # 새 소스에서 바뀐 줄의 범위(1부터, 양끝 포함).
    wrapped: list[tuple[int, int]]
    # 감은 뒤에도 넘친 줄과 그 이유.
    remaining: list[tuple[int, str]]


def width(text: str) -> int:
    """ruff 의 E501 이 세는 폭."""
    total = 0
    for character in text:
        code = ord(character)
        if character == "\t":
            total += TAB_WIDTH
        elif unicodedata.category(character) in ZERO_WIDTH_CATEGORIES or any(
            low <= code <= high for low, high in JAMO_FOLLOWERS
        ):
            continue
        elif unicodedata.east_asian_width(character) in ("W", "F"):
            total += 2
        else:
            total += 1
    return total


def measured(line: str, comment: int | None = None) -> str | None:
    """ruff 가 E501 의 폭으로 재는 부분. `comment` 는 그 줄의 주석이 시작하는 열이다. 줄 끝 주석이
    ruff 의 지시 주석이면 그 앞의 코드만 재고, 그 줄의 E501 을 끄는 noqa 면 None."""
    if comment is None:
        return line
    trailing = line[comment:]
    if NOQA_E501.match(trailing):
        return None
    if RUFF_PRAGMA.match(trailing):
        return line[:comment].rstrip()
    return line


def overlong(line: str, limit: int, comment: int | None = None) -> bool:
    """ruff 가 E501 로 볼 줄인가. 덩어리가 하나인 줄, 줄 길이 안에서 시작한 URL 로 끝나는 줄, SPDX
    머리 줄은 아니다. `comment` 는 `measured` 와 같다."""
    part = measured(line, comment)
    if part is None or SPDX.match(line):
        return False
    total = width(part)
    if total <= limit:
        return False
    chunks = part.split()
    if len(chunks) < 2:
        return False
    return not ("://" in chunks[-1] and total - width(chunks[-1]) <= limit)


class _Pycodestyle(BaseModel):
    max_line_length: int | None = Field(default=None, alias="max-line-length")


class _Lint(BaseModel):
    pycodestyle: _Pycodestyle = Field(default_factory=_Pycodestyle)


class _Ruff(BaseModel):
    """ruff 설정 중 E501 의 줄 길이에 닿는 부분. 나머지 키는 지나친다."""

    line_length: int | None = Field(default=None, alias="line-length")
    lint: _Lint = Field(default_factory=_Lint)

    def e501_limit(self) -> int:
        if self.lint.pycodestyle.max_line_length is not None:
            return self.lint.pycodestyle.max_line_length
        return DEFAULT_LINE_LENGTH if self.line_length is None else self.line_length


class _Tool(BaseModel):
    ruff: _Ruff | None = None


class _Pyproject(BaseModel):
    tool: _Tool = Field(default_factory=_Tool)


def _ruff_config(path: Path) -> _Ruff | None:
    """`path` 가 ruff 설정이면 그 설정, 아니면 None. `pyproject.toml` 은 `tool.ruff` 표가 있어야
    설정이다(ruff 는 그 표가 없는 것을 지나쳐 위로 더 찾는다)."""
    if not path.is_file():
        return None
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    if path.name == "pyproject.toml":
        return _Pyproject.model_validate(config).tool.ruff
    return _Ruff.model_validate(config)


def line_length(path: Path) -> int | None:
    """`path` 를 다스리는 ruff 설정의 E501 줄 길이. 설정 밖이면 None. 설정을 읽지 못하거나 값이
    정수가 아니면 OSError·ValueError(pydantic 의 ValidationError 도 ValueError 다)."""
    for directory in path.resolve().parents:
        for name in RUFF_CONFIG_FILES:
            config = _ruff_config(directory / name)
            if config is not None:
                return config.e501_limit()
    return None


def _words(text: str) -> list[tuple[int, int]]:
    """어절의 (시작, 끝). 공백으로 가르되 코드 스팬 안의 공백에서는 가르지 않는다. 스팬은 같은 수의
    백틱끼리 닫힌다. 닫히지 않은 스팬은 줄 끝까지 한 어절이다."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    fence = 0
    position = 0
    while position < len(text):
        if text[position] == "`":
            end = position
            while end < len(text) and text[end] == "`":
                end += 1
            if not fence:
                fence = end - position
            elif fence == end - position:
                fence = 0
            start = position if start is None else start
            position = end
            continue
        if text[position].isspace() and not fence:
            if start is not None:
                spans.append((start, position))
                start = None
        elif start is None:
            start = position
        position += 1
    if start is not None:
        spans.append((start, len(text)))
    return spans


def _cut(head: str, text: str, limit: int) -> int | None:
    """`text` 를 어디서 끊어 꼬리를 넘길지. 한 어절은 반드시 넘긴다(끝 줄은 닫는 따옴표가 그
    어절을 따라간다). 역슬래시 바로 뒤에서는 끊지 않는다(비 raw 문자열에서 다음 줄과 이어 읽힌다).
    끊을 자리가 없으면 None."""
    spans = _words(text)
    fitting = 0
    for count, (_, end) in enumerate(spans[:-1], 1):
        if width(head + text[:end]) > limit:
            break
        if not text[:end].endswith("\\"):
            fitting = count
    return spans[fitting][0] if fitting else None


def comment_columns(source: str) -> dict[int, int]:
    """줄(0부터)마다 주석이 시작하는 열. 문자열 안의 `#` 를 가르려고 토큰으로 본다."""
    return {
        token.start[0] - 1: token.start[1]
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    }


def _comment_rows(lines: list[str], source: str) -> list[Row]:
    """앞이 공백뿐인 `#` 줄."""
    rows: list[Row] = []
    for index, column in sorted(comment_columns(source).items()):
        line = lines[index]
        head = COMMENT_HEAD.match(line)
        if line[:column].strip() or head is None:
            continue
        text = line[head.end() :]
        # `##` 제목과 `#:` 속성 설명은 `#` 바로 뒤에 공백이 없다. 머리가 `#` 하나로 같아 문단이
        # 합쳐지고 새 줄의 `#` 뒤 공백이 사라졌다(PR 직전 버그·성능 리뷰).
        fixed = DIRECTIVE.match(text) is not None or not head.group().endswith((" ", "\t"))
        rows.append(Row(index, head.group(), text, fixed=fixed))
    return rows


def _docstring_rows(lines: list[str], tree: ast.Module) -> list[list[Row]]:
    """문장 자리에 홀로 선 세 따옴표 문자열마다 그 줄들."""
    blocks: list[list[Row]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        first = node.lineno - 1
        last = (node.end_lineno or node.lineno) - 1
        opening = DOCSTRING_OPEN.match(lines[first])
        if opening is None or node.col_offset != len(opening.group(1)):
            continue
        quote = opening.group(2)
        closing = lines[last].rstrip()
        if not closing.endswith(quote) or "\n".join(lines[first : last + 1]).count(quote) != 2:
            continue
        rows: list[Row] = []
        for index in range(first, last + 1):
            line = closing if index == last else lines[index]
            if index == first:
                head, next_head = opening.group(), opening.group(1)
            else:
                head, next_head = line[: len(line) - len(line.lstrip(" \t"))], None
            text, tail = line[len(head) :], ""
            if index == last:
                text, tail = text[: -len(quote)], quote
            rows.append(Row(index, head, text, tail, next_head))
        blocks.append(rows)
    return blocks


def _blocks(source: str) -> list[list[Row]]:
    """주석은 이웃한 줄끼리, 독스트링은 하나씩 묶는다."""
    lines = _split(source)[0]
    blocks = _docstring_rows(lines, ast.parse(source))
    comments: list[Row] = []
    for row in _comment_rows(lines, source):
        if comments and row.index != comments[-1].index + 1:
            blocks.append(comments)
            comments = []
        comments.append(row)
    if comments:
        blocks.append(comments)
    return blocks


def _joinable(row: Row) -> bool:
    return (
        bool(row.text.strip())
        and not row.fixed
        and DOCTEST.match(row.text) is None
        and "\t" not in row.head + row.text
        and not row.text.rstrip().endswith("\\")
    )


def _opens(row: Row) -> bool:
    """목록 표지나 이름표로 시작해 새 문단을 여는 줄인가."""
    return LIST_MARKER.match(row.text) is not None or LABEL.match(row.text) is not None


def _continuation(row: Row) -> str:
    if row.next_head is not None:
        return row.next_head
    marker = LIST_MARKER.match(row.text)
    return row.head + " " * len(marker.group()) if marker else row.head


def _paragraphs(source: str) -> list[Paragraph]:
    """`source` 의 주석·독스트링 문단. 파싱하지 못하면 SyntaxError 등을 그대로 낸다."""
    found: list[Paragraph] = []
    for block in _blocks(source):
        rows: list[Row] = []
        continuation = ""
        fenced = False
        for row in block:
            # 코드 펜스의 여닫는 줄과 그 안의 줄은 문단에 넣지 않는다.
            fence = row.text.lstrip().startswith(FENCE)
            joinable = _joinable(row) and not fenced and not fence
            fenced = fenced != fence
            if rows and row.head == continuation and joinable and not _opens(row):
                rows.append(row)
                continue
            if rows:
                found.append(Paragraph(tuple(rows), continuation))
                rows = []
            if joinable:
                rows = [row]
                continuation = _continuation(row)
        if rows:
            found.append(Paragraph(tuple(rows), continuation))
    return sorted(found, key=lambda paragraph: paragraph.rows[0].index)


def _rewrap(paragraph: Paragraph, limit: int) -> tuple[list[str], list[str]]:
    """문단의 새 (머리, 글) 줄들. 닫는 따옴표는 끝 줄에 붙는다."""
    heads = [row.head for row in paragraph.rows]
    texts = [row.text for row in paragraph.rows]
    tail = paragraph.rows[-1].tail
    index = 0
    while index < len(texts):
        last = index == len(texts) - 1
        if overlong(heads[index] + texts[index] + (tail if last else ""), limit):
            cut = _cut(heads[index], texts[index], limit)
            if cut is not None:
                moved = texts[index][cut:].strip()
                texts[index] = texts[index][:cut].rstrip()
                if last:
                    heads.append(paragraph.continuation)
                    texts.append(moved)
                else:
                    texts[index + 1] = f"{moved} {texts[index + 1]}"
        index += 1
    return heads, texts


def _render(
    paragraph: Paragraph, lines: list[str], endings: list[str], limit: int
) -> list[RenderedLine]:
    """감은 문단의 줄들. 바뀌지 않은 줄은 원래 줄 그대로다. 원래 줄은 제 줄 끝을, 새 줄은 원래 끝
    줄의 줄 끝을 쓴다."""
    rows = paragraph.rows
    heads, texts = _rewrap(paragraph, limit)
    rendered: list[RenderedLine] = []
    for offset, (head, text) in enumerate(zip(heads, texts, strict=True)):
        original = rows[min(offset, len(rows) - 1)]
        ending = endings[original.index]
        if offset < len(rows) and text == original.text:
            rendered.append(RenderedLine(lines[original.index], ending, changed=False))
        else:
            tail = original.tail if offset == len(texts) - 1 else ""
            rendered.append(RenderedLine(head + text + tail, ending, changed=True))
    return rendered


def _split(source: str) -> tuple[list[str], list[str]]:
    """개행으로만 가른 줄과 줄마다의 CR. `"\\n".join(줄 + CR)` 이 원래 소스다."""
    lines: list[str] = []
    endings: list[str] = []
    for raw in source.split("\n"):
        carriage = raw.endswith("\r")
        lines.append(raw[:-1] if carriage else raw)
        endings.append("\r" if carriage else "")
    return lines, endings


def _remaining(source: str, limit: int) -> list[tuple[int, str]]:
    """`source` 에서 넘친 줄(1부터)과 그 이유."""
    prose = {row.index for paragraph in _paragraphs(source) for row in paragraph.rows}
    columns = comment_columns(source)
    return [
        (index + 1, WORD_TOO_WIDE if index in prose else NOT_PROSE)
        for index, line in enumerate(_split(source)[0])
        if overlong(line, limit, columns.get(index))
    ]


def rewrap_source(source: str, limit: int) -> Rewrapped:
    """`source` 의 주석·독스트링 문단에서 `limit` 을 넘긴 줄을 감는다. 파싱하지 못하거나 홀로 선
    CR 이 있으면 SyntaxError·ValueError·tokenize.TokenError 를 낸다."""
    bom = BOM if source.startswith(BOM) else ""
    body = source[len(bom) :]
    if LONE_CR.search(body):
        raise ValueError("홀로 선 CR 이 있다. 파이썬과 줄 번호가 갈려 감지 않는다")
    lines, endings = _split(body)
    starts = {paragraph.rows[0].index: paragraph for paragraph in _paragraphs(body)}
    out: list[RenderedLine] = []
    wrapped: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        paragraph = starts.get(index)
        if paragraph is None:
            out.append(RenderedLine(lines[index], endings[index], changed=False))
            index += 1
            continue
        changed: list[int] = []
        for rendered in _render(paragraph, lines, endings, limit):
            out.append(rendered)
            if rendered.changed:
                changed.append(len(out))
        if changed:
            wrapped.append((changed[0], changed[-1]))
        index = paragraph.rows[-1].index + 1
    new_body = "\n".join(line.text + line.ending for line in out)
    return Rewrapped(bom + new_body, wrapped, _remaining(new_body, limit))


def _fail(argument: str, reason: str) -> int:
    """감지 못한 까닭을 알리고 종료 코드 2를 돌려준다."""
    print(f"{argument}: {reason}")
    return 2


def _rewrap_file(argument: str) -> int:
    """파일 하나를 감아 고쳐 쓰고 알린다. 그 파일의 종료 코드(모듈 독스트링)를 돌려준다."""
    path = Path(argument)
    try:
        limit = line_length(path)
        data = path.read_bytes()
    except (OSError, ValueError) as error:
        return _fail(argument, f"파일이나 ruff 설정을 읽지 못했다({error})")
    if limit is None:
        return _fail(argument, "ruff 설정 밖이라 줄 길이를 모른다. 감지 않았다")
    try:
        result = rewrap_source(data.decode("utf-8"), limit)
    except (UnicodeDecodeError, SyntaxError, ValueError, tokenize.TokenError) as error:
        return _fail(argument, f"파이썬으로 읽지 못해 감지 않았다({error})")
    encoded = result.source.encode("utf-8")
    if encoded != data:
        try:
            path.write_bytes(encoded)
        except OSError as error:
            return _fail(argument, f"고쳐 쓰지 못했다({error})")
    for first, last in result.wrapped:
        print(f"{argument}:{first}: 감았다({last - first + 1}줄)")
    for row, reason in result.remaining:
        print(f"{argument}:{row}: 넘친 채 남았다: {reason}")
    return 1 if result.remaining else 0


def main(argv: list[str] | None = None) -> int:
    """인자의 파일마다 감아 고쳐 쓴다. 종료 코드는 파일마다의 코드 가운데 가장 큰 것이다."""
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        print(USAGE)
        return 2
    return max([_rewrap_file(argument) for argument in arguments])


if __name__ == "__main__":
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
