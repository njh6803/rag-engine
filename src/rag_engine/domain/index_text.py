"""임베딩, 키워드, 리랭크에 넣는 글을 짓는 함수 하나(명세 "청킹과 토큰 세기").

조각 쓰기(07)와 리랭크의 `texts`(09)는 이 함수만 쓴다. 절 경로가 임베딩에 들어야 "제3조 정의"처럼
제목에만 있는 말로도 찾는다. 검색 결과의 `text`는 조각 글만이고 절 경로는 `location.section`에
따로 싣는다.
"""

from collections.abc import Sequence
from typing import Final

SECTION_SEPARATOR: Final = " > "


def compose_index_text(section: Sequence[str], text: str) -> str:
    """절 경로를 ` > `로 이은 한 줄, 빈 줄, 조각 글이다. 절 경로가 비면 조각 글만 낸다."""
    if not section:
        return text
    return f"{section_line(section)}\n\n{text}"


def section_line(section: Sequence[str]) -> str:
    return SECTION_SEPARATOR.join(section)
