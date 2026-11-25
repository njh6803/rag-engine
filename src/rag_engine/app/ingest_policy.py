"""수집 정책(source-sync 명세 "수집 정책"). 가져오는 원천이 낸 파일 하나를 문서로 받을지 가른다.

커넥터는 원천에 있는 것을 그대로 내고, 서버가 이 정책을 적용해 사유별 개수를 센다. 차례는 제외
패턴(`excluded`), 형식(`unsupported_type`), 크기(`too_large`)이고 파일 하나는 처음 걸린 사유
하나로만 센다.

기본 제외는 끌 수 없다. 키의 어느 토막이든 `.`으로 시작하는 것(숨김 파일과 폴더)과 마지막
토막이 `~$`로 시작하는 것(오피스 임시 파일)이다. 원천의 제외 패턴은 glob이다. `*`는 `/`를 뺀
글자 여럿, `?`는 `/`를 뺀 글자 하나, `**`는 `/`를 넘는 글자 여럿에 맞는다. 패턴에 `/`가 없으면
키의 토막(폴더 이름과 파일 이름)마다 대 보고 어느 토막에든 맞으면 제외한다. `/`가 있으면 키
전체에 댄다. 대소문자를 가린다. 표준 라이브러리의 `fnmatch`는 `*`가 `/`를 넘으므로 쓰지 않고
정규식을 쓰지 않고 직접 맞춘다(`_glob_matches`). 형식은 키의 확장자만으로 가르고 대소문자를 가리지
않는다.
"""

import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Final

from rag_engine.domain.media_types import SUPPORTED_EXTENSIONS

_SEPARATOR: Final = "/"
_STARS: Final = frozenset({"*", "**"})
_OFFICE_TEMP_PREFIX: Final = "~$"


class RejectReason(StrEnum):
    """수집 정책에 걸린 사유. 동기화 기록의 `not_accepted` 키로 쓰인다."""

    EXCLUDED = "excluded"
    UNSUPPORTED_TYPE = "unsupported_type"
    TOO_LARGE = "too_large"


@lru_cache(maxsize=256)
def _tokens(pattern: str) -> tuple[str, ...]:
    """glob 패턴을 토큰으로 나눈다. 토큰은 `*`(`/`를 뺀 글자 여럿), `**`(`/`를 넘는 글자 여럿),
    `?`(`/`를 뺀 글자 하나), 글자 하나(그 글자 그대로)다. 이어진 `*`는 둘 이상이면 `**` 하나로
    묶는다. `[`와 그 밖의 글자는 글자 그대로 맞춘다."""
    tokens: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            end = index
            while end < len(pattern) and pattern[end] == "*":
                end += 1
            tokens.append("**" if end - index >= 2 else "*")
            index = end
            continue
        tokens.append(char)
        index += 1
    return tuple(tokens)


def _skip_wildcards(tokens: tuple[str, ...], states: set[int]) -> set[int]:
    """`*`나 `**` 앞에 선 상태는 그 토큰이 아무 글자도 먹지 않은 채 다음 토큰으로 넘어갈 수 있다."""
    reached = set(states)
    for state in states:
        position = state
        while position < len(tokens) and tokens[position] in _STARS:
            position += 1
            reached.add(position)
    return reached


def _advance(tokens: tuple[str, ...], states: set[int], char: str) -> set[int]:
    next_states: set[int] = set()
    for state in states:
        if state == len(tokens):
            continue
        token = tokens[state]
        if token == "**":
            next_states.add(state)
        elif token == "*":
            if char != _SEPARATOR:
                next_states.add(state)
        elif token == "?":
            if char != _SEPARATOR:
                next_states.add(state + 1)
        elif token == char:
            next_states.add(state + 1)
    return _skip_wildcards(tokens, next_states)


def _glob_matches(pattern: str, text: str) -> bool:
    """패턴이 글 전체에 맞는가. 되짚지 않고 맞을 수 있는 패턴 위치의 집합을 글자마다 밀고 간다.
    비용은 글의 길이와 패턴의 길이의 곱이 한계다. 정규식으로 옮기면 `*a*a*a…*b` 꼴이 지수 시간으로
    느려져 작업자를 세운다."""
    tokens = _tokens(pattern)
    states = _skip_wildcards(tokens, {0})
    for char in text:
        states = _advance(tokens, states, char)
        if not states:
            return False
    return len(tokens) in states


def _matches_pattern(key: str, pattern: str) -> bool:
    """키 자체는 디스크의 이름 그대로 두고, 맞춰 볼 때만 둘을 NFC로 맞춘다. macOS가 풀어 적은
    한글 폴더에도 운영자가 입력한 패턴이 맞게 하기 위해서다."""
    folded_pattern = unicodedata.normalize("NFC", pattern)
    folded_key = unicodedata.normalize("NFC", key)
    if _SEPARATOR in folded_pattern:
        return _glob_matches(folded_pattern, folded_key)
    return any(_glob_matches(folded_pattern, segment) for segment in folded_key.split(_SEPARATOR))


def _is_default_excluded(key: str) -> bool:
    segments = key.split(_SEPARATOR)
    return any(segment.startswith(".") for segment in segments) or segments[-1].startswith(
        _OFFICE_TEMP_PREFIX
    )


def matches_exclude(key: str, patterns: Sequence[str]) -> bool:
    """키가 기본 제외나 원천의 제외 패턴에 맞는가."""
    return _is_default_excluded(key) or any(_matches_pattern(key, pattern) for pattern in patterns)


def reject_reason(
    key: str, size_bytes: int | None, *, exclude_patterns: Sequence[str], max_bytes: int
) -> RejectReason | None:
    """수집 정책에 걸린 사유 하나를 낸다. 걸리지 않으면 `None`이다. 크기를 모르면(`None`) 크기로는
    거르지 않는다. 크기 상한과 같은 파일은 받는다."""
    if matches_exclude(key, exclude_patterns):
        return RejectReason.EXCLUDED
    if PurePosixPath(key).suffix.lower() not in SUPPORTED_EXTENSIONS:
        return RejectReason.UNSUPPORTED_TYPE
    if size_bytes is not None and size_bytes > max_bytes:
        return RejectReason.TOO_LARGE
    return None
