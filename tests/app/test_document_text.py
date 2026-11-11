"""`get_document`의 전문과 창 계산(명세 "MCP 도구", 티켓 09).

데이터베이스 없이 블록 배열만으로 전문의 모양(제목 `#` 표시, 빈 줄 이음), 길이(코드 포인트 수),
창을 자르는 규칙(블록 경계, 긴 블록, 경계 위의 시작)을 본다.
"""

import pytest

from rag_engine.app.document_text import block_text, text_length, text_window
from rag_engine.domain.entities import Block, BlockKind


def _paragraph(text: str, ordinal: int) -> Block:
    return Block(BlockKind.PARAGRAPH, text, None, None, ordinal)


def _paragraphs(*texts: str) -> tuple[Block, ...]:
    return tuple(_paragraph(text, ordinal) for ordinal, text in enumerate(texts))


def _full(*texts: str) -> str:
    return "\n\n".join(texts)


@pytest.mark.parametrize("level", [1, 2, 6, 7])
def test_제목_블록의_글은_수준만큼_샵을_붙이고_공백_하나를_둔다(level: int) -> None:
    heading = Block(BlockKind.HEADING, "제1조 휴가", level, None, 0)

    assert block_text(heading) == "#" * level + " 제1조 휴가"


@pytest.mark.parametrize("kind", [BlockKind.PARAGRAPH, BlockKind.TABLE, BlockKind.LIST_ITEM])
def test_제목이_아닌_블록의_글은_그대로다(kind: BlockKind) -> None:
    block = Block(kind, "# 샵으로 시작하는 문단", None, None, 0)

    assert block_text(block) == "# 샵으로 시작하는 문단"


def test_전문의_길이는_블록_글을_빈_줄로_이은_글의_코드_포인트_수다() -> None:
    blocks = (
        Block(BlockKind.HEADING, "제목", 2, None, 0),
        _paragraph("가나다", 1),
        _paragraph("😀", 2),
    )

    assert text_length(blocks) == len("## 제목\n\n가나다\n\n😀")
    assert text_length(_paragraphs("😀")) == 1


def test_블록이_없으면_전문의_길이는_0이고_창은_빈_글이다() -> None:
    assert text_length(()) == 0
    assert text_window((), 0, 10) == ("", None)


def test_남은_글이_max_chars_안이면_남은_글_전부이고_next_offset은_null이다() -> None:
    blocks = _paragraphs("가나다", "라마바")

    assert text_window(blocks, 0, 8) == (_full("가나다", "라마바"), None)
    assert text_window(blocks, 3, 5) == ("\n\n라마바", None)


def test_넘치면_max_chars_안의_마지막_블록_경계에서_자르고_다음_창은_그_빈_줄로_시작한다() -> None:
    blocks = _paragraphs("aaaa", "bbbb", "cccc")  # 전문 길이 16, 경계(빈 줄의 시작)는 4와 10

    first = text_window(blocks, 0, 12)
    second = text_window(blocks, 10, 12)

    assert first == ("aaaa\n\nbbbb", 10)
    assert second == ("\n\ncccc", None)


def test_한_블록이_창보다_길면_offset_더하기_max_chars에서_자른다() -> None:
    blocks = _paragraphs("a" * 10, "b")

    assert text_window(blocks, 0, 4) == ("aaaa", 4)
    assert text_window(blocks, 4, 4) == ("aaaa", 8)


def test_offset이_경계의_시작이면_그_경계는_창의_끝이_되지_않고_다음_경계를_찾는다() -> None:
    blocks = _paragraphs("aaaa", "b" * 10, "c")  # 경계는 4와 16

    # 4 < 끝 <= 7인 경계가 없어 7에서 자른다. 경계 4에서 자르면 글자 없이 같은 자리를 되돌려 준다.
    assert text_window(blocks, 4, 3) == ("\n\nb", 7)


def test_offset이_전문의_길이와_같으면_빈_글과_null이다() -> None:
    blocks = _paragraphs("가나다")

    assert text_window(blocks, 3, 5) == ("", None)


def test_창을_차례로_이으면_전문과_글자_그대로_같고_창마다_max_chars_안이다() -> None:
    texts = ("제목", "가" * 7, "😀나다", "", "라마바사", "x")
    blocks = _paragraphs(*texts)
    full = _full(*texts)

    for max_chars in range(1, len(full) + 3):
        pieces: list[str] = []
        offset: int | None = 0
        while offset is not None:
            text, next_offset = text_window(blocks, offset, max_chars)
            assert len(text) <= max_chars
            if next_offset is not None:
                assert next_offset == offset + len(text)
                assert next_offset > offset
            pieces.append(text)
            offset = next_offset
        assert "".join(pieces) == full, max_chars
