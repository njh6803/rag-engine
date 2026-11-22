"""원천 이름의 규칙(source-sync 명세 "데이터 모델과 스키마"): 1~63자이고 영문 소문자, 숫자, `-`,
`_`만 쓰며 영문 소문자나 숫자로 시작한다. 관리 API의 경로와 수집 API의 칸에 그대로 들어가는 값이라
URL에서 바뀌지 않는 글자로 좁혔다."""

import re

import pytest

from rag_engine.app.default_records import DEFAULT_NAME, UPLOAD_NAME
from rag_engine.domain.source_names import SOURCE_NAME_PATTERN


def is_valid_source_name(name: str) -> bool:
    """입구가 쓰는 판정과 같은 전체 일치다(pydantic `pattern`은 `re.fullmatch`처럼 본다)."""
    return re.fullmatch(SOURCE_NAME_PATTERN, name) is not None


@pytest.mark.parametrize(
    "name",
    ["a", "0", "groupware", "wiki-2", "hr_system", "9-x", "a" * 63, "default", "upload"],
)
def test_규칙에_맞는_이름은_받는다(name: str) -> None:
    assert is_valid_source_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "Groupware",
        "A",
        "a" * 64,
        "-wiki",
        "_wiki",
        "wiki system",
        "그룹웨어",
        "wiki.v2",
        "wiki/v2",
        "wiki\n",
        " wiki",
    ],
)
def test_규칙에_어긋나는_이름은_받지_않는다(name: str) -> None:
    assert not is_valid_source_name(name)


def test_migrate가_만드는_기본_원천_둘의_이름은_규칙에_맞는다() -> None:
    assert (DEFAULT_NAME, UPLOAD_NAME) == ("default", "upload")
    assert is_valid_source_name(DEFAULT_NAME)
    assert is_valid_source_name(UPLOAD_NAME)
