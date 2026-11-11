"""시험이 python-hwpx로 만드는 HWPX 픽스처. 저장소에 바이너리를 두지 않는다(티켓 08)."""

import io
from collections.abc import Sequence
from dataclasses import dataclass

from hwpx import HwpxDocument


@dataclass(frozen=True, slots=True)
class HwpxHeading:
    text: str
    level: int


@dataclass(frozen=True, slots=True)
class HwpxParagraph:
    text: str


@dataclass(frozen=True, slots=True)
class HwpxTable:
    rows: Sequence[Sequence[str]]


def hwpx_bytes(*items: HwpxHeading | HwpxParagraph | HwpxTable) -> bytes:
    """항목을 차례로 쓴 HWPX 바이트. 문단은 앞 문단의 문단 모양을 이어받지 않는다(개요 수준이 번지지
    않게)."""
    document = HwpxDocument.new()
    for item in items:
        if isinstance(item, HwpxHeading):
            document.add_heading(item.text, level=item.level)
        elif isinstance(item, HwpxParagraph):
            document.add_paragraph(item.text, inherit_style=False)
        else:
            table = document.add_table(len(item.rows), max(len(row) for row in item.rows))
            for row_index, row in enumerate(item.rows):
                for column_index, cell in enumerate(row):
                    table.set_cell_text(row_index, column_index, cell)
    buffer = io.BytesIO()
    document.save_to_stream(buffer)
    return buffer.getvalue()
