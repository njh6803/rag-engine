"""HWPX 파서(python-hwpx, 티켓 08).

문단과 표를 문서 순서대로 내고, 개요 수준이 있는 문단은 제목 블록이다. HWPX에는 쪽 번호가 없다. 글이
없는 문서는 빈 목록이다(`parsed`이고 조각이 0개).
"""

from collections.abc import Sequence

from tests.support.hwpx_files import HwpxHeading, HwpxParagraph, HwpxTable, hwpx_bytes

from rag_engine.adapters.parsers.hwpx_parser import HwpxParser
from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.media_types import HWPX_MIME
from rag_engine.domain.parsing import ParserLimits


def _parse(data: bytes) -> Sequence[Block]:
    return HwpxParser().parse(data, HWPX_MIME, ParserLimits(max_pages=1000))


def _shape(blocks: Sequence[Block]) -> list[tuple[BlockKind, str, int | None, int]]:
    return [(block.kind, block.text, block.level, block.ordinal) for block in blocks]


def test_제목과_문단과_표를_문서_순서대로_내고_쪽_번호는_없다() -> None:
    data = hwpx_bytes(
        HwpxHeading("제1조 휴가", level=1),
        HwpxParagraph("연차휴가는 입사 일 년 뒤부터 발생한다."),
        HwpxTable([["구분", "일수"], ["연차", "15"]]),
        HwpxParagraph("표 아래 문단이다."),
    )

    blocks = _parse(data)

    assert _shape(blocks) == [
        (BlockKind.HEADING, "제1조 휴가", 1, 0),
        (BlockKind.PARAGRAPH, "연차휴가는 입사 일 년 뒤부터 발생한다.", None, 1),
        (BlockKind.TABLE, "구분 | 일수\n연차 | 15", None, 2),
        (BlockKind.PARAGRAPH, "표 아래 문단이다.", None, 3),
    ]
    assert [block.page for block in blocks] == [None] * 4


def test_개요_수준이_제목_수준이_된다() -> None:
    data = hwpx_bytes(
        HwpxHeading("1장", level=1),
        HwpxHeading("1.1절", level=2),
        HwpxHeading("1.1.1항", level=3),
    )

    assert [(block.text, block.level) for block in _parse(data)] == [
        ("1장", 1),
        ("1.1절", 2),
        ("1.1.1항", 3),
    ]


def test_빈_문단은_건너뛴다() -> None:
    data = hwpx_bytes(HwpxParagraph(""), HwpxParagraph("  "), HwpxParagraph("본문이다."))

    assert [block.text for block in _parse(data)] == ["본문이다."]


def test_글이_없는_문서는_빈_목록이다() -> None:
    assert _parse(hwpx_bytes()) == []
