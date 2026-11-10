"""UTF-8 바이트 오프셋을 글자 인덱스로 바꾼다(명세 "청킹과 토큰 세기", ADR 0010).

TEI `/tokenize`가 주는 토큰의 `start`·`stop`은 입력의 UTF-8 바이트 오프셋이다. 파이썬 문자열을
자르려면 글자 인덱스가 필요해서 글자마다 UTF-8 바이트 길이의 누적 합을 만들고 이분 탐색으로 옮긴다.
"""

from bisect import bisect_right
from itertools import accumulate


class Utf8Offsets:
    """글 하나의 바이트 오프셋 표. 같은 글에서 토큰 여럿을 바꿀 때 표를 한 번만 만든다."""

    def __init__(self, text: str) -> None:
        # `_starts[i]`는 i번째 글자가 시작하는 바이트이고 마지막 칸은 글 전체의 바이트 길이다.
        self._starts = [0, *accumulate(len(char.encode()) for char in text)]

    def char_index(self, byte_offset: int) -> int:
        """바이트 오프셋이 글자 중간에 떨어지면 그 글자의 앞 경계로 내린다. 글 끝을 넘으면 끝이고
        음수면 처음이다."""
        index = bisect_right(self._starts, byte_offset) - 1
        return max(0, min(index, len(self._starts) - 1))
