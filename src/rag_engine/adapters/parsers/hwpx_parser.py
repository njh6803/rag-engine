"""HWPX 파서(python-hwpx). 내장 파서 셋의 하나이고 entry point 그룹 `rag_engine.parsers`에 등록한다.

본문의 문단을 문서 순서대로 읽는다. 문단의 문단 모양이 개요 수준(`OUTLINE`)을 가지면 제목 블록이고
수준은 1부터다(HWPX의 개요 수준은 0부터라 1을 더한다). 그 밖의 문단은 문단 블록이다. 문단 안의 표는
행마다 한 줄이고 칸을 ` | `로 잇는 표 블록이다. 쪽 번호는 없다(쪽은 렌더링해야 안다). 빈 문단은
건너뛰고, 글이 하나도 없으면 빈 목록이다. 파서는 자식 프로세스에서 돌므로 상태를 들지 않는다.
"""

import io
from collections.abc import Sequence
from typing import Final

from hwpx import HwpxDocument

from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.media_types import HWPX_MIME
from rag_engine.domain.parsing import PARSER_INTERFACE_VERSION, ParserLimits

_CELL_SEPARATOR: Final = " | "
_OUTLINE: Final = "OUTLINE"


class HwpxParser:
    @property
    def interface_version(self) -> str:
        return PARSER_INTERFACE_VERSION

    @property
    def mime_types(self) -> Sequence[str]:
        return (HWPX_MIME,)

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        document = HwpxDocument.open(io.BytesIO(data))
        try:
            blocks: list[Block] = []
            # 라이브러리의 문단 모양 조회는 부를 때마다 헤더의 모든 문단 모양을 훑으므로 모양마다
            # 한 번만 찾는다.
            levels: dict[str | int | None, int | None] = {}
            for paragraph in document.paragraphs:
                text = paragraph.text.strip()
                if text:
                    ref = paragraph.para_pr_id_ref
                    if ref not in levels:
                        levels[ref] = _outline_level(document, ref)
                    level = levels[ref]
                    kind = BlockKind.PARAGRAPH if level is None else BlockKind.HEADING
                    blocks.append(Block(kind, text, level, page=None, ordinal=len(blocks)))
                for table in paragraph.tables:
                    lines = [
                        _CELL_SEPARATOR.join(" ".join(cell.text.split()) for cell in row.cells)
                        for row in table.rows
                    ]
                    table_text = "\n".join(line for line in lines if line.strip(" |"))
                    if table_text:
                        blocks.append(
                            Block(BlockKind.TABLE, table_text, None, page=None, ordinal=len(blocks))
                        )
            return blocks
        finally:
            document.close()


def _outline_level(document: HwpxDocument, para_pr_id_ref: str | int | None) -> int | None:
    properties = document.styles.paragraph_property(para_pr_id_ref)
    if properties is None or properties.heading is None or properties.heading.type != _OUTLINE:
        return None
    return (properties.heading.level or 0) + 1
