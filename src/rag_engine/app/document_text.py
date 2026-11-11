"""`get_document`가 내는 문서 전문과 전문 창의 계산(명세 "MCP 도구", 티켓 09).

전문은 파싱 결과의 블록을 순번대로 블록 글로 바꿔 빈 줄로 이은 글이다. 제목 블록의 글은 수준만큼
`#`을 앞에 붙이고 공백 하나를 둔 한 줄이고, 그 밖의 블록은 블록의 글 그대로다. 길이와 자리는 모두
유니코드 코드 포인트 수다(파이썬 `str`의 길이). 서버만 자리를 셈하고 클라이언트는 받은 값을 돌려
주기만 하므로 클라이언트가 UTF-16 단위와의 차이를 셈하지 않는다.
"""

from collections.abc import Sequence
from typing import Final

from rag_engine.domain.entities import Block, BlockKind

# 블록 글 사이의 구분. 블록 사이는 빈 줄이다.
BLOCK_SEPARATOR: Final = "\n\n"


def block_text(block: Block) -> str:
    """블록 하나가 전문에서 차지하는 글. 제목은 ATX 제목 모양이고, 수준이 6을 넘어도 그 수만큼
    `#`을 붙인다."""
    if block.kind is BlockKind.HEADING and block.level is not None:
        return "#" * block.level + " " + block.text
    return block.text


def text_length(blocks: Sequence[Block]) -> int:
    """전문의 길이. 전문을 짓지 않고 블록 글의 길이만 더한다."""
    return sum(len(block_text(block)) for block in blocks) + len(BLOCK_SEPARATOR) * max(
        len(blocks) - 1, 0
    )


def text_window(blocks: Sequence[Block], offset: int, max_chars: int) -> tuple[str, int | None]:
    """전문의 `offset`부터 시작하는 창의 글과 다음 창의 `offset`(전문이 여기서 끝나면 `None`).

    `offset`은 0 이상 전문의 길이 이하여야 한다(부르는 쪽이 보장한다). 남은 글이 `max_chars`
    안이면 남은 글 전부다. 넘치면 창의 끝은 `offset`보다 크고 `offset + max_chars` 이하인 블록 경계
    (블록 사이 빈 줄의 시작) 가운데 마지막 것이고, 그런 경계가 없으면(남은 블록 하나가 창보다 길다)
    `offset + max_chars`다. 경계에서 잘린 다음 창은 그 빈 줄로 시작한다. 창을 차례로 이으면 전문과
    글자 그대로 같다.
    """
    parts = [block_text(block) for block in blocks]
    full = BLOCK_SEPARATOR.join(parts)
    limit = offset + max_chars
    if len(full) <= limit:
        return full[offset:], None
    end = limit
    position = 0
    for part in parts[:-1]:
        position += len(part)
        if position > limit:
            break
        if position > offset:
            end = position
        position += len(BLOCK_SEPARATOR)
    return full[offset:end], end
