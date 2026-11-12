"""임베딩, 키워드, 리랭크에 넣는 글을 짓는 함수 하나(명세 "청킹과 토큰 세기").

조각 쓰기(07)와 리랭크의 `texts`(09)는 이 함수만 쓴다. 절 경로가 임베딩에 들어야 "제3조 정의"처럼
제목에만 있는 말로도 찾는다. 검색 결과의 `text`는 조각 글만이고 절 경로는 `location.section`에
따로 싣는다.
"""

from collections.abc import Mapping, Sequence
from typing import Final

SECTION_SEPARATOR: Final = " > "

# 절 경로 줄은 조각 상한의 4분의 1 안이다(청킹 규칙 일곱).
_SECTION_SHARE: Final = 4


def section_token_limit(max_tokens: int) -> int:
    """절 경로 줄이 가질 수 있는 토큰 수의 상한."""
    return max_tokens // _SECTION_SHARE


def section_candidates(full: Sequence[str]) -> list[str]:
    """바깥 제목부터 하나씩 뺀 절 경로 줄 후보들. 토큰 수를 세어 `fit_section`에 건넨다."""
    return [section_line(full[start:]) for start in range(len(full))]


def fit_section(
    full: tuple[str, ...], max_tokens: int, line_tokens: Mapping[str, int]
) -> tuple[str, ...]:
    """절 경로 줄이 상한의 4분의 1 안이 될 때까지 바깥 제목부터 뺀다. 안쪽 제목 하나는 늘 남는다.
    `line_tokens`는 `section_candidates`가 낸 줄의 토큰 수다. 청킹이 조각을 지을 때와 토크나이저
    판만 다른 판이 조각을 복사하며 글을 되지을 때 같은 규칙을 쓰도록 한 자리에 둔다."""
    limit = section_token_limit(max_tokens)
    for start in range(len(full)):
        candidate = full[start:]
        if line_tokens[section_line(candidate)] <= limit or start == len(full) - 1:
            return candidate
    return ()


def compose_index_text(section: Sequence[str], text: str) -> str:
    """절 경로를 ` > `로 이은 한 줄, 빈 줄, 조각 글이다. 절 경로가 비면 조각 글만 낸다."""
    if not section:
        return text
    return f"{section_line(section)}\n\n{text}"


def section_line(section: Sequence[str]) -> str:
    return SECTION_SEPARATOR.join(section)
