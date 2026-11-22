"""원천 이름을 받는 입구(관리 API의 만들기 본문, 수집 API의 폼과 쿼리)가 함께 쓰는 형식. 규칙은
`rag_engine.domain.source_names`가 정한다."""

from typing import Annotated

from pydantic import Field

from rag_engine.domain.source_names import SOURCE_NAME_MAX_LENGTH, SOURCE_NAME_PATTERN

type SourceName = Annotated[
    str,
    Field(
        max_length=SOURCE_NAME_MAX_LENGTH,
        pattern=SOURCE_NAME_PATTERN,
        description="원천 이름. 1~63자이고 영문 소문자, 숫자, `-`, `_`만 쓰며 영문 소문자나 숫자로"
        " 시작한다",
    ),
]
