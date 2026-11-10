"""청킹 시험이 끼우는 가짜 토큰 세기(명세 "청킹과 토큰 세기", 포트 `TokenMeter`).

실제 토크나이저 없이 글자 수로 센다. 시험이 기대하는 조각 경계를 글자 수 셈으로 손으로 따질 수 있다.
`special`은 글 하나를 임베딩할 때 붙는 특수 토큰의 수이고, 글 안의 글자 하나가 토큰 하나다.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharMeter:
    """글자 하나가 토큰 하나다. 글을 이어도 토큰 수는 더한 값 그대로다."""

    special: int = 0

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        return [self._count(text) for text in texts]

    async def special_token_count(self) -> int:
        return self.special

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        return [(index, index + 1) for index in range(len(text))]

    def _count(self, text: str) -> int:
        return len(text)


@dataclass(frozen=True, slots=True)
class RoundingUpMeter(CharMeter):
    """글자 열 개마다 토큰 하나가 더 붙는다. 글을 이으면 토큰 수가 각각 센 값의 합보다 늘 수 있어,
    조각마다 센 값으로 어림한 합이 실제 글 전체의 토큰 수보다 작아지는 토크나이저를 흉내 낸다."""

    def _count(self, text: str) -> int:
        return len(text) + len(text) // 10


@dataclass(frozen=True, slots=True)
class ShrinkingMeter(CharMeter):
    """글자 열 개가 토큰 아홉 개다(올림). 글을 이으면 각각 센 값의 합보다 토큰 수가 줄 수 있어,
    조각마다 센 값으로 어림한 합이 실제 글 전체의 토큰 수보다 커지는 토크나이저를 흉내 낸다."""

    def _count(self, text: str) -> int:
        return -(-len(text) * 9 // 10)
