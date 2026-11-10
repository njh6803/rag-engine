"""UTF-8 바이트 오프셋을 글자 인덱스로 바꾸는 변환(명세 "청킹과 토큰 세기", ADR 0010)."""

import pytest

from rag_engine.adapters.utf8_offsets import Utf8Offsets

# 한국어(3바이트), 영문(1바이트), 이모지(4바이트), 결합 없는 라틴 악센트(2바이트)가 섞인 글.
TEXT = "가a😀é나"
# 글자별 바이트 길이 3, 1, 4, 2, 3 → 글자 시작 바이트 0, 3, 4, 8, 10, 끝 13.
STARTS = [0, 3, 4, 8, 10]
TOTAL_BYTES = 13


@pytest.mark.parametrize(
    ("byte_offset", "char_index"),
    [(0, 0), (3, 1), (4, 2), (8, 3), (10, 4), (13, 5)],
    ids=["처음", "한글_뒤", "영문_뒤", "이모지_뒤", "악센트_뒤", "끝"],
)
def test_글자_경계의_바이트_오프셋은_그_글자_인덱스가_된다(
    byte_offset: int, char_index: int
) -> None:
    assert Utf8Offsets(TEXT).char_index(byte_offset) == char_index


@pytest.mark.parametrize(
    ("byte_offset", "char_index"),
    [(1, 0), (2, 0), (5, 2), (6, 2), (7, 2), (9, 3), (11, 4), (12, 4)],
    ids=[
        "한글_안_1",
        "한글_안_2",
        "이모지_안_1",
        "이모지_안_2",
        "이모지_안_3",
        "악센트_안",
        "나_안_1",
        "나_안_2",
    ],
)
def test_글자_중간에_떨어진_바이트_오프셋은_그_글자의_앞_경계로_내린다(
    byte_offset: int, char_index: int
) -> None:
    assert Utf8Offsets(TEXT).char_index(byte_offset) == char_index


def test_글자가_시작하는_바이트_오프셋은_그_글자의_인덱스가_된다() -> None:
    offsets = Utf8Offsets(TEXT)

    assert [offsets.char_index(start) for start in STARTS] == [0, 1, 2, 3, 4]
    assert offsets.char_index(TOTAL_BYTES) == len(TEXT)


def test_글자_수를_넘는_바이트_오프셋은_글의_끝으로_모은다() -> None:
    assert Utf8Offsets(TEXT).char_index(TOTAL_BYTES + 50) == len(TEXT)


def test_음수_바이트_오프셋은_글의_처음으로_모은다() -> None:
    index = Utf8Offsets(TEXT).char_index(-1)

    assert index == 0, f"음수 오프셋이 낸 글자 위치 {index}"


def test_빈_글은_어느_오프셋이든_0이다() -> None:
    assert Utf8Offsets("").char_index(0) == 0
    assert Utf8Offsets("").char_index(5) == 0


def test_토큰_구간을_글자_인덱스로_바꾸면_글의_조각과_맞는다() -> None:
    text = "검색 서버😀 와 vector"
    raw = text.encode()
    # TEI가 주는 모양: 토큰마다 입력의 UTF-8 바이트 [start, stop).
    byte_spans = [(0, 6), (7, 13), (13, 17), (18, 21), (22, 28)]
    offsets = Utf8Offsets(text)

    pieces = [
        text[offsets.char_index(start) : offsets.char_index(stop)] for start, stop in byte_spans
    ]

    assert pieces == ["검색", "서버", "😀", "와", "vector"]
    assert [raw[start:stop].decode() for start, stop in byte_spans] == pieces
