"""PDF 파서(pdfplumber, 티켓 08).

쪽마다 글을 줄 단위로 읽어 빈 줄로 문단을 가르고, 괘선이 있는 표는 pdfplumber의 표 추출로 표 블록을
내며, 쪽 번호는 1부터 붙는다. 암호 PDF는 `encrypted_document`, 쪽 수 초과는 `too_many_pages`다.
저장소의 `tests/fixtures/small_text.pdf`는 Edge(Skia/PDF)가 HTML에서 쓴 실제 PDF이고, 나머지는
`tests.support.pdf_files`가 손으로 쓴다.
"""

import io
from collections.abc import Sequence
from pathlib import Path

import pdfplumber
import pytest
from tests.support.pdf_files import (
    PdfPage,
    blank_pages_pdf,
    grid,
    merge,
    pdf_bytes,
    text_block,
)

from rag_engine.adapters.parsers.pdf_parser import PdfParser
from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.media_types import PDF_MIME
from rag_engine.domain.parsing import EncryptedDocumentError, ParserLimits, TooManyPagesError

FIXTURE = Path(__file__).parent.parent / "fixtures" / "small_text.pdf"


def _parse(data: bytes, *, max_pages: int = 1000) -> Sequence[Block]:
    return PdfParser().parse(data, PDF_MIME, ParserLimits(max_pages=max_pages))


def _shape(blocks: Sequence[Block]) -> list[tuple[BlockKind, str, int | None, int]]:
    return [(block.kind, block.text, block.page, block.ordinal) for block in blocks]


def test_실제_생산기가_쓴_PDF에서_문단과_표를_쪽_번호와_함께_뽑는다() -> None:
    blocks = _parse(FIXTURE.read_bytes())

    assert _shape(blocks) == [
        (BlockKind.PARAGRAPH, "제1조 연차휴가는 입사 일 년 뒤부터 발생한다.", 1, 0),
        (BlockKind.PARAGRAPH, "출장비는 실비로 정산한다.", 1, 1),
        (BlockKind.TABLE, "구분 | 일수\n연차 | 15", 1, 2),
    ]


def test_쪽마다_쪽_번호가_1부터_붙고_순번은_문서_안에서_이어진다() -> None:
    data = pdf_bytes(
        [PdfPage(text_block("첫 쪽이다.")), PdfPage(text_block("둘째 쪽이다.")), PdfPage()]
    )

    assert _shape(_parse(data)) == [
        (BlockKind.PARAGRAPH, "첫 쪽이다.", 1, 0),
        (BlockKind.PARAGRAPH, "둘째 쪽이다.", 2, 1),
    ]


def test_빈_줄이_문단을_가르고_같은_문단의_줄은_줄바꿈으로_잇는다() -> None:
    data = pdf_bytes([PdfPage(text_block("가나다", "라마바", None, "사아자"))])

    assert [block.text for block in _parse(data)] == ["가나다\n라마바", "사아자"]


def test_표와_문단은_위에서_아래_순서로_나오고_표_안의_글은_문단으로_되풀이되지_않는다() -> None:
    page = merge(
        text_block("위 문단이다.", top=740),
        grid([["구분", "일수"], ["연차", "15"]], top=700),
        text_block("아래 문단이다.", top=600),
    )

    assert _shape(_parse(pdf_bytes([page]))) == [
        (BlockKind.PARAGRAPH, "위 문단이다.", 1, 0),
        (BlockKind.TABLE, "구분 | 일수\n연차 | 15", 1, 1),
        (BlockKind.PARAGRAPH, "아래 문단이다.", 1, 2),
    ]


def test_표의_모두_빈_행은_건너뛴다() -> None:
    page = grid([["구분", "일수"], ["", ""]], top=700)

    assert [block.text for block in _parse(pdf_bytes([page]))] == ["구분 | 일수"]


def test_글이_없는_PDF는_빈_목록이다() -> None:
    assert _parse(blank_pages_pdf(2)) == []


def test_암호_PDF_도우미는_맞는_암호로_열려_글을_낸다() -> None:
    data = pdf_bytes([PdfPage(text_block("가나다"))], user_password="secret")

    with pdfplumber.open(io.BytesIO(data), password="secret") as pdf:
        assert pdf.pages[0].extract_text() == "가나다"


def test_암호가_걸려_열리지_않는_PDF는_암호_문서_예외다() -> None:
    data = pdf_bytes([PdfPage(text_block("가나다"))], user_password="secret")

    with pytest.raises(EncryptedDocumentError):
        _parse(data)


def test_쪽_수가_한도를_넘으면_쪽_수_초과_예외이고_한도와_같으면_파싱한다() -> None:
    data = pdf_bytes([PdfPage(text_block(f"{n}쪽")) for n in range(1, 5)])

    with pytest.raises(TooManyPagesError):
        _parse(data, max_pages=3)
    assert len(_parse(data, max_pages=4)) == 4
