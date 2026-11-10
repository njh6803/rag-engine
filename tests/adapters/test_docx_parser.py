"""DOCX 파서(명세 "파싱의 격리와 자원 한도"의 파서가 내는 블록의 최소 규칙).

제목 스타일은 제목 블록(수준 포함), 문단은 문단 블록, 표는 행마다 한 줄이고 칸을 ` | `로 잇는
표 블록이다. 쪽 번호는 없고 순번은 문서 안에서 0부터다. 픽스처 문서는 시험이 python-docx로 만든다.
"""

import io
from collections.abc import Callable

from docx import Document
from docx.document import Document as DocxDocument

from rag_engine.adapters.parsers.docx_parser import DocxParser
from rag_engine.domain.entities import BlockKind
from rag_engine.domain.media_types import DOCX_MIME
from rag_engine.domain.parsing import PARSER_INTERFACE_VERSION, ParserLimits

LIMITS = ParserLimits(max_pages=1000)


def _docx(build: Callable[[DocxDocument], None]) -> bytes:
    document = Document()
    build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _규정(document: DocxDocument) -> None:
    document.add_heading("제1장 총칙", level=1)
    document.add_paragraph("연차휴가는 입사 일 년 뒤부터 발생한다.")
    document.add_heading("제2조 정의", level=2)
    document.add_paragraph("")
    document.add_paragraph("연차는 유급 휴가를 말한다.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "구분"
    table.cell(0, 1).text = "일수"
    table.cell(1, 0).text = "기본"
    table.cell(1, 1).text = "15일"


def test_파서는_DOCX_MIME을_받고_인터페이스_판을_밝힌다() -> None:
    parser = DocxParser()

    assert list(parser.mime_types) == [DOCX_MIME]
    assert parser.interface_version == PARSER_INTERFACE_VERSION


def test_제목은_수준을_가진_제목_블록이_되고_문단과_표가_문서_순서로_따른다() -> None:
    blocks = DocxParser().parse(_docx(_규정), DOCX_MIME, LIMITS)

    assert [(block.kind, block.level, block.text) for block in blocks] == [
        (BlockKind.HEADING, 1, "제1장 총칙"),
        (BlockKind.PARAGRAPH, None, "연차휴가는 입사 일 년 뒤부터 발생한다."),
        (BlockKind.HEADING, 2, "제2조 정의"),
        (BlockKind.PARAGRAPH, None, "연차는 유급 휴가를 말한다."),
        (BlockKind.TABLE, None, "구분 | 일수\n기본 | 15일"),
    ]


def test_순번은_0부터_빈_문단을_건너뛴_채_이어지고_쪽_번호는_없다() -> None:
    blocks = DocxParser().parse(_docx(_규정), DOCX_MIME, LIMITS)

    assert [block.ordinal for block in blocks] == [0, 1, 2, 3, 4]
    assert [block.page for block in blocks] == [None] * 5


def test_가로로_합쳐진_칸은_한_번만_적는다() -> None:
    def build(document: DocxDocument) -> None:
        table = document.add_table(rows=2, cols=2)
        merged = table.cell(0, 0).merge(table.cell(0, 1))
        merged.text = "합친 제목"
        table.cell(1, 0).text = "가"
        table.cell(1, 1).text = "나"

    (block,) = DocxParser().parse(_docx(build), DOCX_MIME, LIMITS)

    assert block.text == "합친 제목\n가 | 나"


def test_세로로_합쳐진_칸은_행마다_같은_글을_적는다() -> None:
    def build(document: DocxDocument) -> None:
        table = document.add_table(rows=2, cols=2)
        merged = table.cell(0, 0).merge(table.cell(1, 0))
        merged.text = "세로 합침"
        table.cell(0, 1).text = "가"
        table.cell(1, 1).text = "나"

    (block,) = DocxParser().parse(_docx(build), DOCX_MIME, LIMITS)

    assert block.text == "세로 합침 | 가\n세로 합침 | 나"


def test_글이_하나도_없는_문서는_빈_목록을_낸다() -> None:
    assert list(DocxParser().parse(_docx(lambda document: None), DOCX_MIME, LIMITS)) == []
