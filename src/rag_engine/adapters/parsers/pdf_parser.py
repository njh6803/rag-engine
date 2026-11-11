"""PDF 파서(pdfplumber). 내장 파서 셋의 하나이고 entry point 그룹 `rag_engine.parsers`에 등록한다.

쪽마다 글을 줄 단위로 읽어 빈 줄로 문단을 가르고(앞 줄과의 세로 간격이 앞 줄 높이의 0.75배를 넘으면
빈 줄이 낀 것으로 본다), 같은 문단의 줄은 줄바꿈으로 잇는다. 괘선이 있는 표는 pdfplumber의 표 추출로
표 블록(행마다 한 줄, 칸은 ` | `)을 내고, 표 안의 글은 문단으로 되풀이하지 않는다. 블록은 쪽
번호(1부터)를 달고 한 쪽 안에서는 위에서 아래 순서다. 글이 하나도 없으면 빈 목록이다(스캔본, OCR은
다음 판이다).

암호가 걸려 열리지 않는 PDF는 `EncryptedDocumentError`, 쪽 수가 한도를 넘으면 `TooManyPagesError`다.
쪽 수는 쪽을 만들기 전에 한도까지만 세어 보므로 쪽이 수만 장인 문서도 한도 뒤의 쪽은 읽지 않는다.
파서는 자식 프로세스에서 돌므로 상태를 들지 않는다.
"""

import io
from collections.abc import Sequence
from itertools import islice
from typing import Final

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError
from pdfminer.pdfpage import PDFPage
from pdfplumber.page import Page
from pdfplumber.pdf import PDF
from pdfplumber.utils.exceptions import PdfminerException

from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.media_types import PDF_MIME
from rag_engine.domain.parsing import (
    PARSER_INTERFACE_VERSION,
    EncryptedDocumentError,
    ParserLimits,
    TooManyPagesError,
)

_PARAGRAPH_GAP_RATIO: Final = 0.75
_CELL_SEPARATOR: Final = " | "

type _Box = tuple[float, float, float, float]
type _Item = tuple[float, BlockKind, str]


class PdfParser:
    @property
    def interface_version(self) -> str:
        return PARSER_INTERFACE_VERSION

    @property
    def mime_types(self) -> Sequence[str]:
        return (PDF_MIME,)

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        try:
            pdf = pdfplumber.open(io.BytesIO(data))
        except PdfminerException as error:
            # pdfplumber는 pdfminer의 예외를 이 예외에 담아 올린다. 암호 오류만 알리고 나머지는
            # 올린다.
            if any(isinstance(cause, PDFEncryptionError) for cause in error.args):
                raise EncryptedDocumentError from error
            raise
        with pdf:
            _check_page_count(pdf, limits.max_pages)
            blocks: list[Block] = []
            for number, page in enumerate(pdf.pages, start=1):
                for _, kind, text in _page_items(page):
                    blocks.append(Block(kind, text, level=None, page=number, ordinal=len(blocks)))
                page.flush_cache()
        return blocks


def _check_page_count(pdf: PDF, max_pages: int) -> None:
    """쪽을 만들지 않고 한도보다 한 쪽 더까지만 센다."""
    if sum(1 for _ in islice(PDFPage.create_pages(pdf.doc), max_pages + 1)) > max_pages:
        raise TooManyPagesError


def _page_items(page: Page) -> list[_Item]:
    tables = page.find_tables()
    boxes: list[_Box] = [table.bbox for table in tables]
    outside_tables = page.filter(lambda obj: not _is_char_inside(obj, boxes)) if boxes else page
    items = _paragraph_items(outside_tables)
    for table, box in zip(tables, boxes, strict=True):
        text = _table_text(table.extract())
        if text:
            items.append((box[1], BlockKind.TABLE, text))
    return sorted(items, key=lambda item: item[0])


def _is_char_inside(obj: dict[str, object], boxes: Sequence[_Box]) -> bool:
    """표 안에 있는 글자인가. 글자의 가운데가 표 상자 안이면 안에 있다."""
    if obj.get("object_type") != "char":
        return False
    center_x = (_number(obj, "x0") + _number(obj, "x1")) / 2
    center_y = (_number(obj, "top") + _number(obj, "bottom")) / 2
    return any(x0 <= center_x <= x1 and top <= center_y <= bottom for x0, top, x1, bottom in boxes)


def _number(obj: dict[str, object], key: str) -> float:
    value = obj[key]
    assert isinstance(value, int | float)
    return float(value)


def _paragraph_items(page: Page) -> list[_Item]:
    items: list[_Item] = []
    lines: list[str] = []
    first_top = 0.0
    previous_top = previous_bottom = 0.0
    for line in page.extract_text_lines(return_chars=False):
        text = str(line["text"]).strip()
        if not text:
            continue
        top, bottom = _number(line, "top"), _number(line, "bottom")
        if lines and top - previous_bottom > _PARAGRAPH_GAP_RATIO * (
            previous_bottom - previous_top
        ):
            items.append((first_top, BlockKind.PARAGRAPH, "\n".join(lines)))
            lines = []
        if not lines:
            first_top = top
        lines.append(text)
        previous_top, previous_bottom = top, bottom
    if lines:
        items.append((first_top, BlockKind.PARAGRAPH, "\n".join(lines)))
    return items


def _table_text(rows: Sequence[Sequence[str | None]]) -> str:
    lines = [_CELL_SEPARATOR.join(_cell_text(cell) for cell in row) for row in rows]
    return "\n".join(line for line in lines if line.strip(" |"))


def _cell_text(cell: str | None) -> str:
    return " ".join((cell or "").split())
