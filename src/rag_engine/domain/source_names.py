"""원천 이름의 규칙(source-sync 명세 "데이터 모델과 스키마").

1~63자이고 영문 소문자, 숫자, `-`, `_`만 쓰며 영문 소문자나 숫자로 시작한다. 관리 API의 경로와 수집
API의 칸에 그대로 들어가는 값이라 URL에서 바뀌지 않는 글자로 좁혔다. 원천 이름을 받는 입구(관리
API, 수집 API)가 이 규칙 하나를 쓴다. 기본 원천 `default`와 `upload`가 이 규칙에 맞는지는 시험이
본다.
"""

from typing import Final

SOURCE_NAME_MAX_LENGTH: Final = 63

# 전체 일치로 쓰는 값이다. `re.match`와 `re.search`는 `$`가 끝의 개행도 받으므로 `"abc\n"`을
# 통과시킨다. `re.fullmatch`와 pydantic의 `pattern`은 그 이름을 거절한다. 첫 글자 뒤에 올 수 있는
# 길이는 최대 길이에서 파생한다.
SOURCE_NAME_PATTERN: Final = rf"^[a-z0-9][a-z0-9_-]{{0,{SOURCE_NAME_MAX_LENGTH - 1}}}$"
