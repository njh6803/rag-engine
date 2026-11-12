"""포트. `typing.Protocol`이고 `app`의 유스케이스는 이 모양만 부른다(ADR 0007, 명세 "포트 열셋과 그
값").

작업 단위 안에서 얻는 포트는 `Catalog`, `DocumentStore`, `VectorIndex`, `JobQueue` 넷뿐이고 한
연결의 한 트랜잭션을 공유한다. 나머지는 트랜잭션 밖에서 부른다. 서드파티 예외는 어댑터가 `domain`의
영구·일시 실패 예외(`rag_engine.domain.errors`)로 바꿔 올리고 메시지는 옮기지 않는다.

`Parser`는 플러그인 자리라 인터페이스 판과 함께 `rag_engine.domain.parsing`에 있다. `Connector`와
`Transform`의 Protocol은 처음 쓰는 source-sync가 만든다(명세 Further Notes).
"""

from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rag_engine.domain.entities import (
    Block,
    Chunk,
    ChunkDraft,
    ChunkingConfig,
    Document,
    DocumentContent,
    Group,
    IndexElements,
    IndexState,
    IndexVersion,
    Job,
    JobStatus,
    KnowledgeBase,
    SearchCandidates,
    SearchQuery,
    Source,
    Token,
)
from rag_engine.domain.errors import ErrorCode

# 지식베이스의 임베딩 모델, 차원, 청킹 설정에서 색인 판의 요소 넷을 계산한다. 청킹 해시와 토크나이저
# 판이 문장 분리기와 키워드 토크나이저의 판을 읽으므로 구현은 `adapters`에 있다.
type ComputeIndexElements = Callable[[str, int, ChunkingConfig], IndexElements]

# 글에서 키워드 토큰을 뽑는다(명세 "키워드 토큰"). 조각과 질의가 같은 함수를 지나야 같은 토큰을
# 낸다. 형태소 분석기는 `adapters`에 있어 `app`은 이 모양으로만 부른다.
type KeywordTokenizer = Callable[[str], list[str]]

# 색인 판에 적힌 끝점·모델·차원으로 임베딩하는 자를 낸다(명세 "수집 파이프라인과 작업" 셋째 단계).
# 같은 판은 같은 자를 돌려써 끝점 확인(`/info`)을 한 번만 한다. 구현은 `adapters`에 있다.
type EmbedderFor = Callable[[IndexVersion], Embedder]

# 청킹 전략의 이름으로 청커를 고른다.
type ChunkerFor = Callable[[str], Chunker]

# 지식베이스 설정의 리랭커 끝점·모델로 리랭커를 낸다. 리랭커가 없는 지식베이스는 `None`이다. 같은
# 설정은 같은 자를 돌려써 끝점 확인(`/info`)을 한 번만 한다. 구현은 `adapters`에 있다.
type RerankerFor = Callable[[KnowledgeBase], Reranker | None]


class LockMode(StrEnum):
    """지식베이스 행의 잠금(명세 잠금 규칙). 재색인 시작·삭제·판 전환은 `UPDATE`이고, 수집은 문서가
    드는 지식베이스를 `SHARE`로, 그룹이 바뀌어 문서가 빠지는 지식베이스를 `UPDATE`로 잠근다."""

    SHARE = "share"
    UPDATE = "update"


class TokenMeter(Protocol):
    """모델이 글을 읽는 토큰을 세는 자. 청킹은 상한 안인지 가리는 데만 쓴다. `Embedder`가 이 모양을
    채우고, 청킹 시험에서는 글자 수로 세는 가짜를 끼운다."""

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        """글마다 토큰 수를 입력 순서대로 낸다(특수 토큰은 뺀다)."""
        ...

    async def special_token_count(self) -> int:
        """글 하나를 임베딩할 때 모델이 앞뒤에 붙이는 특수 토큰의 수."""
        ...

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        """글의 토큰마다 글자 인덱스의 [처음, 끝) 구간을 낸다(특수 토큰은 뺀다)."""
        ...


class Chunker(Protocol):
    """청킹 전략. 교체 경계가 아니라 층을 위한 포트다. 결정적이라 시험은 실제 전략으로 한다."""

    async def chunk(
        self, blocks: Sequence[Block], config: ChunkingConfig, tokens: TokenMeter
    ) -> list[ChunkDraft]: ...


class Embedder(TokenMeter, Protocol):
    """임베딩 서버의 경계. 끝점 하나, 모델 하나다. 토큰 세기는 이 포트에 맡긴다."""

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...


class Reranker(Protocol):
    """리랭커의 경계. 글마다 점수를 입력 순서대로 낸다."""

    async def rerank(self, query: str, texts: Sequence[str]) -> list[float]: ...


class BlobStore(Protocol):
    """원본의 파일 저장소. 키는 `blobs/<문서 UUID>/<원본 UUID>`다. 입출력 오류는 일시 실패다."""

    async def write(self, key: str, data: bytes) -> None: ...

    async def read(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class Catalog(Protocol):
    """원천, 그룹, 지식베이스(그룹과의 다대다 포함), 색인 판 레코드. 작업 단위 안에서 얻는다."""

    async def add_source(self, source: Source) -> None:
        """같은 이름의 원천이 이미 있으면 아무것도 하지 않는다(`migrate`가 겹쳐 돌아도 멱등이다)."""
        ...

    async def get_source(self, name: str) -> Source | None: ...

    async def add_group(self, group: Group) -> None:
        """같은 이름의 그룹이 이미 있으면 아무것도 하지 않는다."""
        ...

    async def get_group(self, name: str) -> Group | None: ...

    async def get_source_by_id(self, source_id: UUID) -> Source | None: ...

    async def get_group_by_id(self, group_id: UUID) -> Group | None: ...

    async def add_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        """같은 이름의 지식베이스가 이미 있으면 아무것도 하지 않는다."""
        ...

    async def update_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        """이름과 현재 판 참조를 뺀 설정을 고친다. 현재 판 참조는 `switch_current_version`의
        몫이다."""
        ...

    async def add_group_to_knowledge_base(self, knowledge_base_id: UUID, group_id: UUID) -> None:
        """이미 들어 있으면 아무것도 하지 않는다."""
        ...

    async def get_knowledge_base(self, name: str) -> KnowledgeBase | None: ...

    async def list_knowledge_bases(self) -> list[KnowledgeBase]: ...

    async def list_knowledge_bases_of_group(self, group_id: UUID) -> list[KnowledgeBase]: ...

    async def lock_knowledge_bases(
        self, knowledge_base_ids: Sequence[UUID], mode: LockMode
    ) -> list[KnowledgeBase]:
        """ID 순으로 잠그고 잠근 뒤의 행을 낸다(잠금 순서는 문서 행, 지식베이스 행, 작업 행이다)."""
        ...

    async def list_live_index_versions(self, knowledge_base_id: UUID) -> list[IndexVersion]:
        """현재 판과 건설 중인 판을 낸다."""
        ...

    async def add_index_version(self, version: IndexVersion) -> None: ...

    async def update_index_version_endpoint(self, version_id: UUID, endpoint: str) -> None:
        """판에 적어 둔 임베딩 끝점만 고친다. 끝점은 판의 요소가 아니라 주소다."""
        ...

    async def switch_current_version(self, knowledge_base_id: UUID, new_version_id: UUID) -> None:
        """현재 판 참조를 새 판으로 바꾸고 새 판을 `current`, 옛 판을 `retired`로 쓴다."""
        ...


class DocumentStore(Protocol):
    """문서와 최신 파싱 결과. 작업 단위 안에서 얻는다."""

    async def get(self, document_id: UUID) -> Document | None: ...

    async def get_by_key(self, source_id: UUID, key: str) -> Document | None: ...

    async def lock(self, document_id: UUID) -> Document | None:
        """문서 행을 `FOR NO KEY UPDATE`로 잠그고 잠근 뒤의 행을 낸다."""
        ...

    async def add(self, document: Document) -> None:
        """같은 (원천, 키)의 문서가 있으면 `DocumentAlreadyExistsError`를 올린다. 있던 문서를
        커밋한 트랜잭션이 끝나기를 기다린 뒤 판정하므로 같은 키를 동시에 넣은 두 요청이
        직렬화된다."""
        ...

    async def update(self, document: Document) -> None:
        """문서 행의 고칠 수 있는 칸을 모두 새 값으로 덮는다(원천 참조, 키, 식별자, 만든 시각은
        그대로다). 부르기 전에 `lock`으로 잠근다."""
        ...

    async def get_content(self, document_id: UUID) -> DocumentContent | None: ...

    async def save_content(self, content: DocumentContent) -> None: ...

    async def count_live_documents(self, knowledge_base_id: UUID) -> int:
        """그 지식베이스의 그룹 집합에 드는 그룹의, 지워지지 않은 문서 수. 색인 상태와 상관없다."""
        ...


class VectorIndex(Protocol):
    """조각, 보관 조각, 색인 상태. 색인 판마다의 HNSW 부분 색인을 맡는다. 작업 단위 안에서
    얻는다."""

    async def create_version_index(self, version: IndexVersion) -> None:
        """판의 HNSW 부분 색인을 만든다(판 행을 만드는 작업 단위의 커밋 직전)."""
        ...

    async def replace_chunks(
        self, document_id: UUID, index_version_id: UUID, chunks: Sequence[Chunk]
    ) -> None:
        """그 (문서, 판)의 옛 조각을 지우고 새 조각을 넣는다."""
        ...

    async def update_chunk_copies(self, document: Document) -> None:
        """그 문서의 모든 판의 조각(물러난 판의 것도)에서 복사 칸(그룹, 갱신일, 시행일, 접근 그룹)을
        문서 행의 지금 값으로 고친다. 보관 표는 되살림이 문서 행의 값으로 다시 쓰므로 건드리지
        않는다."""
        ...

    async def delete_chunks(self, document_id: UUID, index_version_id: UUID | None) -> None:
        """그 문서의 조각을 지운다. 판을 주지 않으면 모든 판의 것이다."""
        ...

    async def archive_chunks(self, document_id: UUID, archived_at: datetime) -> None:
        """그 문서의 모든 판의 조각을 보관 표로 옮긴다. 검색 표에는 남기지 않는다."""
        ...

    async def restore_archived_chunks(
        self, document: Document, index_version_ids: Sequence[UUID]
    ) -> dict[UUID, int]:
        """보관 조각 가운데 `index_version_ids`의 판의 것이면서 만든 내용 해시가 문서의 내용 해시와
        같은 것을 복사 칸(그룹, 갱신일, 시행일, 접근 그룹)을 문서의 지금 값으로 쓴 채 검색 표로
        되돌리고, 조각이 돌아온 판마다 돌아온 수를 낸다. 돌아온 판만 키로 든다. 보관 표는 건드리지
        않는다(`delete_archived_chunks`가 지운다). 되돌리는 일과 센 수가 한 문장이어야 해서 조회와
        변경을 나누지 않고 수를 돌려준다."""
        ...

    async def delete_archived_chunks(self, document_id: UUID) -> None:
        """그 문서의 보관 조각을 모두 지운다."""
        ...

    async def count_chunks(self, document_id: UUID, index_version_id: UUID) -> int:
        """그 (문서, 판)의 조각 수."""
        ...

    async def get_state(self, document_id: UUID, index_version_id: UUID) -> IndexState | None: ...

    async def save_state(self, state: IndexState) -> None:
        """(문서, 판)의 색인 상태를 쓴다. 이미 있으면 덮는다."""
        ...

    async def delete_state(self, document_id: UUID, index_version_id: UUID) -> None:
        """(문서, 판)의 색인 상태를 지운다. 없으면 아무것도 하지 않는다."""
        ...

    async def delete_states(self, document_id: UUID) -> None:
        """그 문서의 색인 상태를 모든 판에서 지운다(물러난 판의 것도)."""
        ...

    async def search_candidates(self, query: SearchQuery) -> SearchCandidates:
        """벡터와 키워드 후보를 SQL 하나로 모아 RRF로 합친다. 같은 문장에서 질의한 판이 아직
        현재 판인지도 읽는다. 벡터 질의는 판의 HNSW 부분 색인을 탄다."""
        ...


@dataclass(frozen=True, slots=True)
class JobOutcome:
    """한 시도가 끝나고 작업이 놓인 상태(`succeeded`, `failed`, 다시 예약했으면 `queued`). 작업의
    상태는 그 시도의 결과이지 문서의 색인 결과가 아니다."""

    status: JobStatus
    error_code: ErrorCode | None


class JobQueue(Protocol):
    """작업 표의 대기열. 작업 단위 안에서 얻고, 알림(`NOTIFY`)은 PostgreSQL이 커밋 때 보낸다."""

    async def enqueue(self, document_id: UUID, request_id: UUID, now: datetime) -> Job:
        """같은 문서의 대기 작업이 있으면 새 행 없이 그것을 다시 써서 낸다. 있는지 보는 일과 넣는
        일이 한 번에 이뤄져야 해서 조회와 변경을 나누지 않고 `Job`을 돌려준다."""
        ...

    async def delete_queued(self, document_id: UUID) -> None:
        """그 문서의 대기(`queued`) 작업을 지운다. 실행 중인 작업과 끝난 작업은 건드리지 않는다."""
        ...

    async def get(self, job_id: UUID) -> Job | None: ...

    async def claim(self, worker_id: str, now: datetime, lease_seconds: float) -> Job | None:
        """`SKIP LOCKED`로 꺼낼 수 있는 작업 하나를 `running`으로 바꿔 낸다. 꺼내는 일과 바꾸는 일을
        나누면 두 작업자가 같은 작업을 잡으므로 한 번에 하고 `Job`을 돌려준다."""
        ...

    async def hold_attempt(self, job: Job) -> bool:
        """작업 행을 잠그고 작업자 ID와 시도 횟수가 이 시도가 꺼낼 때 쓴 값 그대로인지 본다(작업 행
        조건). 아니면 임대가 끝나 다른 작업자가 가져간 것이라 `False`이고, 부른 쪽은 아무것도
        쓰지 않고 작업 단위를 롤백한다. 문서 행과 지식베이스 행을 잠근 뒤 마지막에 부른다."""
        ...

    async def record_raised_generation(self, job: Job, generation: int) -> None:
        """이번 시도가 첫째 단계에서 올린 문서의 세대를 작업 행에 적는다."""
        ...

    async def finish(self, job: Job, outcome: JobOutcome, now: datetime) -> None:
        """작업을 끝낸 상태로 쓴다. 이 시도가 쓴 작업 행이 아니면(임대가 끝나 다른 작업자가
        가져갔다) 아무것도 쓰지 않고 `AttemptLostError`를 올린다. 부른 쪽이 끝난 줄 알고 지나가지
        못하게 반환값이 아니라 예외로 알린다."""
        ...

    async def reschedule(self, job: Job, run_after: datetime, error_code: ErrorCode) -> bool:
        """일시 실패한 시도의 작업을 `queued`로 되돌려 `run_after`와 마지막 오류 코드를 두고 임대와
        작업자와 올린 세대를 비운다(시도 횟수는 둔다). 같은 문서에 다른 대기 작업이 있거나 이
        시도가 쓴 작업 행이 아니면 아무것도 쓰지 않고 `False`다. 같은 문서의 대기 작업은 부분 유일
        색인으로 하나라서, 되돌리는 일과 다른 대기 작업을 보는 일이 한 문장이어야 해 조회와 변경을
        나누지 않는다(`CODING_STANDARDS.md`의 CQS에 대한 의도한 예외다). 문서 행과 지식베이스
        행(`SHARE`)을 잠근 뒤 `hold_attempt` 다음에 부른다."""
        ...

    async def has_other_job_from_start(self, document_id: UUID, excluding_job_id: UUID) -> bool:
        """그 문서를 처음부터 맡을 다른 작업이 있는지 본다. 대기 작업과, 실행 중이면서 올린 세대가
        빈 작업이다. 올린 세대가 채워진 실행 중 작업은 세지 않는다(재시도 소진의 판정)."""
        ...

    async def extend_lease(self, job: Job, leased_until: datetime) -> None:
        """임대 만료를 `leased_until`로 늘린다. 작업 행 조건을 지날 때만 쓰고, 아니면 임대가 끝나
        다른 작업자가 가져간 것이라 아무것도 쓰지 않고 `AttemptLostError`를 올린다(부른 쪽은 그
        시도를 버린다). 문서 행을 잠그지 않고 작업 행 하나만 쓰므로 잠금 순서를 거스르지 않는다."""
        ...


class TokenStore(Protocol):
    """인증 토큰. 다른 표와 한 트랜잭션에 들 일이 없어 작업 단위 밖에서 부른다."""

    async def add(self, token: Token) -> None: ...

    async def get(self, token_id: UUID) -> Token | None: ...

    async def get_by_hash(self, token_hash: str) -> Token | None: ...

    async def list_tokens(self) -> list[Token]:
        """만든 순서로 낸다. 회수된 토큰도 든다."""
        ...

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        """회수 시각을 적는다. 이미 회수된 토큰이면 처음 시각을 그대로 둔다."""
        ...

    async def has_live_admin(self, now: datetime) -> bool:
        """회수·만료되지 않은 `admin` 토큰이 있는지 본다."""
        ...


class Transaction(Protocol):
    """작업 단위 안에서 얻는 네 포트. 한 연결의 한 트랜잭션을 공유한다."""

    @property
    def catalog(self) -> Catalog: ...

    @property
    def documents(self) -> DocumentStore: ...

    @property
    def index(self) -> VectorIndex: ...

    @property
    def jobs(self) -> JobQueue: ...


class UnitOfWork(Protocol):
    """트랜잭션의 경계. 블록을 예외 없이 나가면 커밋이고 예외로 나가면 롤백이다.

    명시적 `commit()`은 두지 않는다. 두 길이 있으면 한쪽을 잊는다. 산문에서는 "작업 단위"라 쓰고
    대기열의 "작업"과 가른다(GLOSSARY.md 작업 항목).
    """

    def begin(self) -> AbstractAsyncContextManager[Transaction]: ...
