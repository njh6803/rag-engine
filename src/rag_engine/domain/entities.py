"""엔티티. 불변 데이터클래스이고 식별자는 표준 라이브러리 `uuid.UUID`다(명세 "층, 패키지, 조립").

식별자는 UUIDv7이고 파이썬에서 만든다. 만드는 일은 서드파티(uuid6)를 쓰는 `identifiers` 모듈이 맡고
이 모듈은 값의 모양만 안다. 시각은 시간대가 붙은 `datetime`(UTC)이다(ADR 0015).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from rag_engine.domain.errors import ErrorCode

type JsonValue = None | bool | int | float | str | Sequence[JsonValue] | Mapping[str, JsonValue]

# `vector` 열의 HNSW 색인이 받는 차원의 상한이다(명세 "데이터 모델과 스키마").
MAX_EMBEDDING_DIMENSIONS: Final = 2000


class SourceKind(StrEnum):
    """원천의 종류. 첫 판은 밀어 넣기 하나다."""

    PUSH = "push"


class IndexVersionStatus(StrEnum):
    """색인 판의 상태. 현재 판과 건설 중인 판을 합쳐 살아 있는 판이라 부른다(GLOSSARY.md)."""

    BUILDING = "building"
    CURRENT = "current"
    RETIRED = "retired"


class DocumentStatus(StrEnum):
    RECEIVED = "received"
    PARSED = "parsed"
    FAILED = "failed"


class IndexStateStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class JobKind(StrEnum):
    INDEX_DOCUMENT = "index_document"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TokenRole(StrEnum):
    ADMIN = "admin"
    READER = "reader"


class BlockKind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST_ITEM = "list_item"


@dataclass(frozen=True, slots=True)
class Source:
    id: UUID
    name: str
    kind: SourceKind


@dataclass(frozen=True, slots=True)
class Group:
    id: UUID
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """청킹 설정의 원본. 색인 판은 해시만이 아니라 이 원본도 적어 둔다."""

    strategy: str
    max_tokens: int
    overlap_tokens: int


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    id: UUID
    name: str
    description: str
    embedding_endpoint: str
    embedding_model: str
    embedding_dimensions: int
    reranker_endpoint: str | None
    reranker_model: str | None
    chunking: ChunkingConfig
    current_index_version_id: UUID | None
    is_default: bool


@dataclass(frozen=True, slots=True)
class IndexElements:
    """색인 판의 요소 넷. 지식베이스의 현재 설정에서 계산한 넷이 현재 판의 넷과 다르면 "재색인
    필요"다(ADR 0008). 임베딩 끝점은 요소가 아니다."""

    schema_version: int
    embedding_model: str
    embedding_dimensions: int
    chunking_hash: str
    tokenizer_version: str


@dataclass(frozen=True, slots=True)
class IndexVersion:
    """색인 판. 요소 넷은 스키마 판, 임베딩 모델과 차원, 청킹 설정 해시, 토크나이저 판이다."""

    id: UUID
    knowledge_base_id: UUID
    schema_version: int
    embedding_endpoint: str
    embedding_model: str
    embedding_dimensions: int
    chunking: ChunkingConfig
    chunking_hash: str
    tokenizer_version: str
    status: IndexVersionStatus
    created_at: datetime
    retired_at: datetime | None

    @property
    def elements(self) -> IndexElements:
        return IndexElements(
            schema_version=self.schema_version,
            embedding_model=self.embedding_model,
            embedding_dimensions=self.embedding_dimensions,
            chunking_hash=self.chunking_hash,
            tokenizer_version=self.tokenizer_version,
        )


@dataclass(frozen=True, slots=True)
class Document:
    id: UUID
    source_id: UUID
    key: str
    group_id: UUID
    title: str
    mime: str
    size_bytes: int
    content_hash: str
    blob_path: str
    metadata: Mapping[str, JsonValue]
    updated_at: datetime
    effective_date: date | None
    access_groups: tuple[str, ...]
    status: DocumentStatus
    error_code: ErrorCode | None
    generation: int
    deleted_at: datetime | None
    purged_at: datetime | None
    created_at: datetime
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class Block:
    """파서가 내는 블록. 표 블록의 글은 행마다 한 줄이고 칸은 ` | `로 잇는다.

    `level`은 제목 블록에만 있다(1부터). `page`는 쪽 번호(1부터)이고 쪽이 없는 형식은 `None`이다.
    `ordinal`은 문서 안의 순번(0부터)이다.
    """

    kind: BlockKind
    text: str
    level: int | None
    page: int | None
    ordinal: int

    def __post_init__(self) -> None:
        if (self.kind is BlockKind.HEADING) != (self.level is not None):
            raise ValueError("제목 수준은 제목 블록에만 있고 제목 블록에는 늘 있다")
        if self.level is not None and self.level < 1:
            raise ValueError("제목 수준은 1부터다")
        if self.page is not None and self.page < 1:
            raise ValueError("쪽 번호는 1부터다")
        if self.ordinal < 0:
            raise ValueError("블록 순번은 0부터다")


@dataclass(frozen=True, slots=True)
class DocumentContent:
    """문서의 최신 파싱 결과(문서마다 한 행)."""

    document_id: UUID
    parser_name: str
    parser_interface_version: str
    parser_library_version: str
    blocks: tuple[Block, ...]
    parsed_content_hash: str
    text_hash: str
    parsed_at: datetime


@dataclass(frozen=True, slots=True)
class ChunkLocation:
    """조각의 근거 위치. 조각이 덮는 블록들에서 만든다(명세 "청킹과 토큰 세기").

    `page`는 첫 블록의 쪽 번호이고 없으면 `None`이다. `section`은 절 경로의 제목 글을 바깥에서
    안쪽 순으로 담고 절이 없으면 빈 튜플이다. `block_kind`는 첫 블록의 종류이고 `block_range`는
    덮은 블록 순번의 처음과 끝(0부터, 양 끝 포함)이다.
    """

    page: int | None
    section: tuple[str, ...]
    block_kind: BlockKind
    block_range: tuple[int, int]


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """청킹이 낸 조각. 임베딩과 키워드는 아직 없다.

    `text`는 조각 글만이고 온전한 절 경로는 `location`에 있다. `index_text`는 임베딩과 키워드에 넣는
    글 전체다(상한 안으로 줄인 절 경로 줄, 빈 줄, 조각 글. `compose_index_text`가 짓는다). 줄인 절
    경로는 토큰 수로 정해져 `location`만으로 되짓지 못해 청킹이 글을 같이 낸다. `token_count`는
    `index_text`의 토큰 수에 특수 토큰 수를 더한 값, 곧 상한과 견준 값이다.
    """

    text: str
    index_text: str
    token_count: int
    location: ChunkLocation


@dataclass(frozen=True, slots=True)
class Chunk:
    """색인 판 하나에 든 조각. 필터를 위해 문서에서 복사한 칸(그룹, 갱신일, 시행일, 접근 그룹)을
    든다."""

    id: UUID
    document_id: UUID
    index_version_id: UUID
    ordinal: int
    text: str
    token_count: int
    location: ChunkLocation
    embedding: tuple[float, ...]
    keyword_text: str
    source_content_hash: str
    group_id: UUID
    updated_at: datetime
    effective_date: date | None
    access_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndexState:
    """문서 하나가 색인 판 하나에 반영됐는지 적은 값. `built_content_hash`는 `indexed`일 때만
    있다."""

    document_id: UUID
    index_version_id: UUID
    status: IndexStateStatus
    chunk_count: int
    built_content_hash: str | None
    error_code: ErrorCode | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Job:
    """작업 대기열의 작업. `raised_generation`은 이번 시도가 첫째 단계에서 올린 문서의 세대다."""

    id: UUID
    kind: JobKind
    document_id: UUID
    status: JobStatus
    attempts: int
    run_after: datetime
    leased_until: datetime | None
    worker_id: str | None
    raised_generation: int | None
    last_error_code: ErrorCode | None
    request_id: UUID
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class Token:
    """인증 토큰. 원문은 두지 않고 sha256 해시만 둔다. `knowledge_base_ids`가 비면 전부다."""

    id: UUID
    name: str
    token_hash: str
    role: TokenRole
    knowledge_base_ids: tuple[UUID, ...]
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
