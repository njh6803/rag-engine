"""DOCX 파서(python-docx). 내장 파서 셋의 하나이고 entry point 그룹 `rag_engine.parsers`에 등록한다.

제목 스타일(`Heading N`)은 수준이 있는 제목 블록, 그 밖의 문단은 문단 블록, 표는 행마다 한 줄이고
칸을 ` | `로 잇는 표 블록이다. 쪽 번호는 없다(DOCX는 쪽을 렌더링해야 알 수 있다). 빈 문단은
건너뛴다. 가로로 합쳐진 칸은 한 번만 적고, 세로로 합쳐진 칸은 행마다 같은 글을 적는다. 파서는 자식
프로세스에서 돌므로 상태를 들지 않는다.
"""

import io
import re
from collections.abc import Sequence
from typing import Final

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.media_types import DOCX_MIME
from rag_engine.domain.parsing import PARSER_INTERFACE_VERSION, ParserLimits

_HEADING_STYLE: Final = re.compile(r"^Heading (\d)$")
_CELL_SEPARATOR: Final = " | "


class DocxParser:
    @property
    def interface_version(self) -> str:
        return PARSER_INTERFACE_VERSION

    @property
    def mime_types(self) -> Sequence[str]:
        return (DOCX_MIME,)

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        document = Document(io.BytesIO(data))
        blocks: list[Block] = []
        for item in document.iter_inner_content():
            block = _table_block(item, len(blocks)) if isinstance(item, Table) else None
            if isinstance(item, Paragraph):
                block = _paragraph_block(item, len(blocks))
            if block is not None:
                blocks.append(block)
        return blocks


def _paragraph_block(paragraph: Paragraph, ordinal: int) -> Block | None:
    text = paragraph.text.strip()
    if not text:
        return None
    style = paragraph.style
    heading = None if style is None else _HEADING_STYLE.match(style.name or "")
    if heading is None:
        return Block(BlockKind.PARAGRAPH, text, level=None, page=None, ordinal=ordinal)
    return Block(BlockKind.HEADING, text, level=max(int(heading[1]), 1), page=None, ordinal=ordinal)


def _table_block(table: Table, ordinal: int) -> Block | None:
    lines: list[str] = []
    for row in table.rows:
        # 가로로 합쳐진 칸은 `cells`가 칸마다 같은 칸을 되풀이해 내므로 이어 오는 같은 칸은
        # 건너뛴다.
        texts: list[str] = []
        previous = None
        for cell in row.cells:
            if cell != previous:
                texts.append(cell.text.strip())
            previous = cell
        line = _CELL_SEPARATOR.join(texts)
        if line.strip(" |"):
            lines.append(line)
    if not lines:
        return None
    return Block(BlockKind.TABLE, "\n".join(lines), level=None, page=None, ordinal=ordinal)
