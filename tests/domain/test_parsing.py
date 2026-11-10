"""파서 인터페이스 1.0.0과 블록의 모양(명세 "파싱의 격리와 자원 한도", "데이터 모델과 스키마")."""

from collections.abc import Sequence

import pytest

from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.parsing import (
    PARSER_INTERFACE_VERSION,
    EncryptedDocumentError,
    Parser,
    ParserLimits,
    TooManyPagesError,
)


class _FakeParser:
    """Protocol 을 채우는지 보는 최소 구현."""

    interface_version = PARSER_INTERFACE_VERSION
    mime_types: Sequence[str] = ("application/pdf",)

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        return [Block(BlockKind.PARAGRAPH, data.decode(), None, 1, 0)]


def test_파서_인터페이스의_판은_1_0_0이다() -> None:
    assert PARSER_INTERFACE_VERSION == "1.0.0"


def test_받는_MIME_목록과_바이트_MIME_한도를_받아_블록을_내는_구현이_파서다() -> None:
    parser: Parser = _FakeParser()

    blocks = parser.parse("본문".encode(), "application/pdf", ParserLimits(max_pages=10))

    assert parser.mime_types == ("application/pdf",)
    assert [block.text for block in blocks] == ["본문"]


def test_암호_문서_예외는_encrypted_document_코드를_든_영구_실패다() -> None:
    error = EncryptedDocumentError()

    assert isinstance(error, PermanentFailure)
    assert error.code is ErrorCode.ENCRYPTED_DOCUMENT


def test_쪽_수_초과_예외는_too_many_pages_코드를_든_영구_실패다() -> None:
    error = TooManyPagesError()

    assert isinstance(error, PermanentFailure)
    assert error.code is ErrorCode.TOO_MANY_PAGES


def test_제목_블록은_수준을_들고_다른_블록은_수준이_없다() -> None:
    assert Block(BlockKind.HEADING, "제1장", 1, None, 0).level == 1
    assert Block(BlockKind.TABLE, "가 | 나", None, 2, 1).level is None


def test_제목_블록에_수준이_없으면_거부한다() -> None:
    with pytest.raises(ValueError, match="제목 블록에는 늘 있다"):
        Block(BlockKind.HEADING, "제1장", None, None, 0)


def test_제목이_아닌_블록에_수준을_주면_거부한다() -> None:
    with pytest.raises(ValueError, match="제목 블록에만 있고"):
        Block(BlockKind.PARAGRAPH, "본문", 1, None, 0)


def test_제목_수준은_1부터다() -> None:
    with pytest.raises(ValueError, match="제목 수준은 1부터"):
        Block(BlockKind.HEADING, "제목", 0, None, 0)


def test_쪽_번호는_1부터_순번은_0부터다() -> None:
    with pytest.raises(ValueError, match="쪽 번호는 1부터"):
        Block(BlockKind.PARAGRAPH, "본문", None, 0, 0)
    with pytest.raises(ValueError, match="블록 순번은 0부터"):
        Block(BlockKind.PARAGRAPH, "본문", None, 1, -1)
    assert Block(BlockKind.PARAGRAPH, "본문", None, 1, 0).ordinal == 0
