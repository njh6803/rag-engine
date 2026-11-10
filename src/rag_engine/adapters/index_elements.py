"""색인 판의 요소 넷을 계산한다(명세 "데이터 모델과 스키마", ADR 0008).

`migrate`, 재색인 필요 판정, 재색인 시작이 모두 이 함수를 쓴다. 요소는 스키마 판, 임베딩 모델과
차원, 청킹 설정 해시, 토크나이저 판이다. 청킹 해시와 토크나이저 판에 드는 코드 상수 둘
(`STRUCTURE_FIRST_VERSION`, `KEYWORD_RULES_VERSION`)은 이 곁에 한 자리로 두고, 청킹과 키워드
구현은 그 이름을 쓴다. 상수를 올리면 그 구현이 바뀐 코드가 도는 설치에서 "재색인 필요"로 드러난다.

문장 분리기의 판은 청킹이 문장 경계를 얻는 kiwipiepy와 kiwipiepy_model의 판이다. 설치된 배포판의
메타데이터에서 읽으므로 Kiwi를 올리면 청킹 해시와 토크나이저 판이 함께 바뀐다.
"""

import hashlib
import json
from importlib.metadata import version
from typing import Final

from rag_engine.domain.entities import ChunkingConfig, IndexElements
from rag_engine.domain.errors import ConfigurationError

# 첫 판의 스키마 판이다. alembic이 올리는 형식을 바꾸면 함께 올린다.
SCHEMA_VERSION: Final = 1

# 청킹 전략 구현의 판. 전략 이름마다 하나다.
STRUCTURE_FIRST_VERSION: Final = "1"

# 키워드 규칙(품사 집합, 전처리)의 판(명세 "키워드 토큰").
KEYWORD_RULES_VERSION: Final = "1"


def _installed_version(distribution: str) -> str:
    # 시험이 설치 판을 바꿔 판 요소가 달라지는 것을 보려고 이 자리를 monkeypatch한다.
    return version(distribution)


def _strategy_version(strategy: str) -> str:
    if strategy == "structure_first":
        return STRUCTURE_FIRST_VERSION
    raise ConfigurationError(f"모르는 청킹 전략이다: {strategy}")


def _kiwi_versions() -> tuple[str, str]:
    return _installed_version("kiwipiepy"), _installed_version("kiwipiepy_model")


def compute_index_elements(
    embedding_model: str, embedding_dimensions: int, chunking: ChunkingConfig
) -> IndexElements:
    kiwipiepy, kiwipiepy_model = _kiwi_versions()
    chunking_identity = json.dumps(
        {
            "strategy": chunking.strategy,
            "max_tokens": chunking.max_tokens,
            "overlap_tokens": chunking.overlap_tokens,
            "strategy_version": _strategy_version(chunking.strategy),
            "kiwipiepy": kiwipiepy,
            "kiwipiepy_model": kiwipiepy_model,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return IndexElements(
        schema_version=SCHEMA_VERSION,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        chunking_hash=hashlib.sha256(chunking_identity.encode()).hexdigest(),
        tokenizer_version=(
            f"kiwipiepy {kiwipiepy}; kiwipiepy_model {kiwipiepy_model};"
            f" keyword-rules {KEYWORD_RULES_VERSION}"
        ),
    )
