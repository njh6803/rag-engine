"""평가 세트 묶음의 값(명세 "평가 세트의 형식"과 "공공 문서 묶음", ADR 0018).

묶음은 평가 세트 하나가 든 폴더 전체다. 이 모듈은 파일에서 읽어 온 뒤의 값만 둔다. 읽고 쓰는 코드는
`adapters`에, 값끼리의 판정은 `app`에 있다. 시각은 오프셋이 있는 `datetime`이고, 문서 목록의 날짜
`YYYY-MM-DD`는 어댑터가 그날 00:00 한국 표준시로 바꿔 둔다.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Final

from rag_engine.domain.entities import JsonValue

# 도구가 받는 묶음 형식의 major다. major가 다른 판의 묶음은 거부한다.
SUPPORTED_FORMAT_MAJOR: Final = 1

# 문서 파일의 합 상한이다(명세 "공공 문서 묶음"의 규모. 30MB).
MAX_DOCUMENT_BYTES: Final = 30 * 1024 * 1024

# 유형 표지의 낱말 넷(명세 "평가 세트의 형식").
EVIDENCE_TAGS: Final = frozenset({"table", "figure", "multi_document", "no_context"})

# 사람 판정의 까닭 낱말 다섯(명세 "놓친 까닭").
MISS_CAUSES: Final = frozenset(
    {"no_context", "table_or_figure", "vocabulary", "multi_document", "other"}
)


class QueryStyle(StrEnum):
    """질의 목록의 문체. 사람이 묻는 문장이거나 키워드형이다."""

    QUESTION = "question"
    KEYWORD = "keyword"


@dataclass(frozen=True, slots=True)
class EvalProblem:
    """묶음의 오류 하나. `where`는 파일(과 줄)이나 항목이고 `reason`은 까닭이다."""

    where: str
    reason: str

    def __str__(self) -> str:
        return f"{self.where}: {self.reason}"


@dataclass(frozen=True, slots=True)
class PassageEvidence:
    """문서 안의 원문 글귀로 가리키는 기대 근거."""

    document: str
    passage: str


@dataclass(frozen=True, slots=True)
class PageEvidence:
    """문서의 쪽 번호로 가리키는 기대 근거."""

    document: str
    page: int


type Expectation = PassageEvidence | PageEvidence


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """질문 하나의 기대 근거. `evidence`는 하나 이상이고 `tags`는 비어도 된다."""

    id: str
    evidence: tuple[Expectation, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvalFilter:
    """질의에 붙는 필터. 모양은 검색 도구의 `filter`와 같다(시각은 오프셋이 있는 값)."""

    groups: tuple[str, ...] | None
    updated_after: datetime | None
    updated_before: datetime | None


@dataclass(frozen=True, slots=True)
class EvalQuery:
    evidence_id: str
    query: str
    filter: EvalFilter | None


@dataclass(frozen=True, slots=True)
class QueryList:
    name: str
    style: QueryStyle
    queries: tuple[EvalQuery, ...]


@dataclass(frozen=True, slots=True)
class EvalDocument:
    """문서 목록의 문서 하나. `key`는 `documents/` 기준 POSIX 상대 경로다."""

    key: str
    title: str
    publisher: str
    source_url: str
    license: str
    license_evidence: str
    downloaded_at: date
    sha256: str
    bytes: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    strategy: str
    max_tokens: int
    overlap_tokens: int


@dataclass(frozen=True, slots=True)
class EvalConfig:
    """평가가 재는 색인과 검색의 설정(`config.json`). 끝점 주소와 키는 들지 않는다."""

    embedding_model: str
    embedding_dimensions: int
    reranker_model: str
    chunking: ChunkingConfig
    search_candidates: int
    tei_version: str
    judge_model: str
    judge_prompt_version: str


def search_config_values(config: EvalConfig) -> dict[str, JsonValue]:
    """검색의 숫자에 닿는 구성의 칸. 묶음의 내용 해시와 `compare`의 구성 비교가 쓴다. 판정 칸
    (`judge_model`, `judge_prompt_version`)은 검색의 숫자에 닿지 않는 참고 숫자의 열쇠라서 뺀다."""
    return {
        "embedding_model": config.embedding_model,
        "embedding_dimensions": config.embedding_dimensions,
        "reranker_model": config.reranker_model,
        "chunking": {
            "strategy": config.chunking.strategy,
            "max_tokens": config.chunking.max_tokens,
            "overlap_tokens": config.chunking.overlap_tokens,
        },
        "search_candidates": config.search_candidates,
        "tei_version": config.tei_version,
    }


def config_values(config: EvalConfig) -> dict[str, JsonValue]:
    """보고서의 `config` 칸. 검색 구성의 칸에 판정 칸을 더한다."""
    return {
        **search_config_values(config),
        "judge_model": config.judge_model,
        "judge_prompt_version": config.judge_prompt_version,
    }


@dataclass(frozen=True, slots=True)
class MissReview:
    """사람 판정 한 줄(`miss-review.jsonl`)."""

    query_list: str
    evidence_id: str
    cause: str
    confirmed: bool


@dataclass(frozen=True, slots=True)
class EvalSet:
    """읽어 온 묶음 하나. 문서 파일의 바이트는 들지 않고 목록만 든다."""

    format_version: str
    name: str
    config: EvalConfig
    documents: tuple[EvalDocument, ...]
    evidence: tuple[EvidenceItem, ...]
    query_lists: tuple[QueryList, ...]
    miss_reviews: tuple[MissReview, ...]
