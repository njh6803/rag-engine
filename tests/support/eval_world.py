"""평가 도구의 시험이 함께 쓰는 환경(티켓 search-eval 03, 04).

평가 도구는 평가 전용 이름 셋(`RAG_EVAL_*`)에서만 환경을 읽는다. 시험은 개발자 셸의 `RAG_*`를 지우고
그 셋을 줘서 도구를 `main(argv)`로 부른다. 데이터베이스는 `rag_eval_<난수>`로 짓는다.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

DATABASE_ENV: Final = "RAG_EVAL_DATABASE_URL"
DATA_DIR_ENV: Final = "RAG_EVAL_DATA_DIR"
EMBEDDING_ENV: Final = "RAG_EVAL_EMBEDDING_URL"
RERANKER_ENV: Final = "RAG_EVAL_RERANKER_URL"


@dataclass(frozen=True, slots=True)
class World:
    """평가 도구가 보는 환경. 평가 전용 이름 셋의 값과 시험이 도구를 부르는 작업 폴더다."""

    database_url: str
    data_dir: Path
    tei_url: str
    work_dir: Path
