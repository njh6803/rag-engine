"""평가가 순위를 따로 재는 단계(티켓 search-eval 04, 05, 06, 명세 "진단용 검색과 단계").

단계는 검색 흐름에서 순위를 따로 재는 네 자리다. 빠른 실행은 벡터만, 키워드만, 합친 뒤를 재고 전체
실행은 리랭크 뒤까지 잰다. 실행 모듈(`eval_run`)과 놓친 까닭 모듈(`eval_misses`)이 함께 쓰므로 따로
둔다.
"""

from enum import StrEnum
from typing import Final


class Stage(StrEnum):
    """검색 흐름에서 순위를 따로 재는 자리. 리랭크 뒤는 전체 실행만 잰다."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    FUSED = "fused"
    RERANK = "rerank"


FAST_STAGES: Final = (Stage.VECTOR, Stage.KEYWORD, Stage.FUSED)
FULL_STAGES: Final = (*FAST_STAGES, Stage.RERANK)
