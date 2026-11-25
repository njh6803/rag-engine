"""포트. `typing.Protocol`이고 `app`의 유스케이스는 이 모양만 부른다(ADR 0007, 명세 "포트 열셋과 그
값").

작업 단위 안에서 얻는 포트는 `Catalog`, `DocumentStore`, `VectorIndex`, `JobQueue`,
`SyncRecordStore` 다섯뿐이고 한 연결의 한 트랜잭션을 공유한다. 나머지는 트랜잭션 밖에서 부른다.
서드파티 예외는 어댑터가 `domain`의 영구·일시 실패 예외(`rag_engine.domain.errors`)로 바꿔 올리고
메시지는 옮기지 않는다.

`Parser`는 플러그인 자리라 인터페이스 버전과 함께 `rag_engine.domain.parsing`에 있고, `Connector`도
같은 까닭으로 `rag_engine.domain.connectors`에 있다. `Transform`의 Protocol은 db-source가
만든다(변환 인터페이스는 db-source로 넘어갔다. ADR 0021 "이번에 짓지 않는 것").
"""

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rag_engine.domain.connectors import Connector, FolderLocation, FolderTarget, SourceReader
from rag_engine.domain.entities import (
    Block,
    CandidateScan,
    Chunk,
    ChunkDraft,
    ChunkingConfig,
    Document,
    DocumentContent,
    DocumentCounts,
    DocumentQuery,
    Group,
    IndexElements,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    Job,
    JobKind,
    JobStatus,
    JsonValue,
    KnowledgeBase,
    SearchCandidates,
    SearchDiagnosis,
    SearchQuery,
    Source,
    StoredChunk,
    SyncRecord,
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

# 임베더를 내는 함수를 감싸 다른 임베더를 내는 함수를 낸다. 작업자의 조립이 걸이로 받고, 평가
# 도구가 추론 기록을 끼울 때 쓴다(명세 search-eval "추론 기록"). 작업자는 무엇을 감싸는지 모른다.
type EmbedderWrapper = Callable[[EmbedderFor], EmbedderFor]

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


class RelevanceJudge(Protocol):
    """검색 평가의 관련성 판정기(ADR 0019). 질문과 조각의 글을 받아 관련 있으면 참을 낸다. 판정기는
    트랜잭션 밖에서 부른다. 다시 해 볼 만한 실패(연결 실패, 요청 한도, 서버 오류)는
    `TransientFailure`로, 그 밖의 실패(인증 실패, 읽을 수 없는 응답)는 `PermanentFailure`로
    올린다. 실패의 메시지에는 서드파티 예외와 서버가 보낸 오류의 글을 옮기지 않는다(질문과 조각의
    글이 들 수 있다. 원칙 V)."""

    async def judge(self, query: str, text: str) -> bool: ...


class BlobStore(Protocol):
    """원본의 파일 저장소. 키는 `blobs/<문서 UUID>/<원본 UUID>`다. 입출력 오류는 일시 실패다."""

    async def write(self, key: str, data: bytes) -> None: ...

    async def read(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def list_written_before(self, cutoff: datetime) -> list[str]:
        """원본의 키(`blobs/…`) 가운데 쓴 시각이 `cutoff`보다 앞서는 것을 낸다. 원본 폴더 밖의
        파일(서버 폴더와 데이터 폴더의 다른 파일)은 열거하지 않는다. 정리 작업이 어느 문서도
        가리키지 않는 원본을 찾는 데 쓴다."""
        ...


class Catalog(Protocol):
    """원천, 그룹, 지식베이스(그룹과의 다대다 포함), 색인 판 레코드. 작업 단위 안에서 얻는다."""

    async def add_source(self, source: Source) -> None:
        """같은 이름의 원천이 이미 있으면 아무것도 하지 않는다(`migrate`가 겹쳐 돌아도 멱등이다)."""
        ...

    async def create_source(self, source: Source) -> None:
        """같은 이름의 원천이 있으면(지운 원천 포함) `SourceAlreadyExistsError`를 올린다. 이름이
        겹친 두 요청이 동시에 오면 나중에 넣는 쪽이 먼저 넣은 쪽의 커밋을 기다린 뒤 판정하므로
        하나만 만들어진다(이름의 유일 제약이 판정한다)."""
        ...

    async def lock_source_folders(self) -> None:
        """폴더를 정하는 요청(원천 만들기, 폴더 고치기)끼리 차례로 지나게 하는 트랜잭션 수준
        자문 잠금을 잡는다. 겹침 확인 앞에서 맨 먼저 부르고, 작업 단위가 끝나면 풀린다."""
        ...

    async def update_pull_source(
        self,
        source_id: UUID,
        *,
        config: Mapping[str, JsonValue] | None,
        exclude_patterns: Sequence[str] | None,
    ) -> None:
        """가져오는 원천의 `config`와 `exclude_patterns` 가운데 `None`이 아닌 칸만 바꾼다. 다른
        칸은 읽어 둔 값으로 다시 쓰지 않으므로, 같은 원천을 동시에 바꾸는 다른 요청(일시 중지 등)이
        커밋한 칸을 되돌리지 않는다. 이름, 갈래, 커넥터, 그룹은 바꾸지 않는다."""
        ...

    async def set_source_paused(self, source_id: UUID, *, paused: bool) -> None:
        """가져오는 원천의 `paused` 칸만 바꾼다. 다른 칸은 건드리지 않는다."""
        ...

    async def set_source_schedule(self, source_id: UUID, schedule: str | None) -> None:
        """가져오는 원천의 `schedule` 칸만 바꾼다. `None`이면 일정을 없앤다. 다음 실행 시각은
        `set_next_run_at`이 따로 쓴다."""
        ...

    async def set_next_run_at(self, source_id: UUID, next_run_at: datetime | None) -> None:
        """가져오는 원천의 `next_run_at` 칸만 바꾼다. `None`이면 비운다."""
        ...

    async def lock_source(self, source_id: UUID) -> Source | None:
        """그 원천의 행을 `FOR NO KEY UPDATE`로 잠그고 잠근 뒤의 값을 낸다. 일정, 일시 중지, 다음
        실행 시각을 읽고 고치는 요청이 서로의 칸을 되돌리지 않게 차례로 지나게 한다. 다른 연결이
        잡고 있으면 풀릴 때까지 기다린다. 외래 키 확인이 거는 `FOR KEY SHARE`와는 부딪치지
        않으므로, 그 원천에 작업이나 기록을 넣는 요청은 막지 않는다."""
        ...

    async def lock_source_shared(self, source_id: UUID) -> Source | None:
        """그 원천의 행을 `FOR SHARE`로 잠그고 잠근 뒤의 값을 낸다. 문서를 넣거나 옮기는
        작업 단위(수집 API, 동기화, 원천 삭제 작업, 색인 작업의 첫째 단계)가 맨 먼저 부르고 지움
        표시를 본다. 여럿이 함께 잡을 수 있고, `lock_source`와 지움 표시를 쓰는 갱신은 이 잠금이
        풀리기를 기다린다. 그래서 지움 표시가 선 뒤에 그 원천의 문서를 새로 넣는 작업 단위는
        없다(잠금 순서는 원천 행, 문서 행, 지식베이스 행, 작업 행이다)."""
        ...

    async def mark_source_deleted(self, source_id: UUID, deleted_at: datetime) -> None:
        """원천 행에 지움 표시를 쓰고 다음 실행 시각을 비운다. 다른 칸은 건드리지 않는다. 부르기
        전에 `lock_source`로 잠근다."""
        ...

    async def mark_source_restored(self, source_id: UUID, next_run_at: datetime | None) -> None:
        """원천 행의 지움 표시를 걷고 다음 실행 시각을 `next_run_at`으로 쓴다. 다른 칸은 건드리지
        않는다. 부르기 전에 `lock_source`로 잠근다."""
        ...

    async def lock_due_sources(self, now: datetime) -> list[Source]:
        """다음 실행 시각이 `now` 이전이거나 같고 일시 중지도 지움 표시도 없는 가져오는 원천의 행을
        `FOR NO KEY UPDATE SKIP LOCKED`로 잠가 낸다. 다른 연결이 잡은 행은 기다리지 않고
        건너뛰므로, 작업자를 여럿 띄워도 같은 원천을 두 연결이 함께 잡지 않고, 일정을 고치는
        요청이 잡은 원천은 이번 확인에서 건너뛴다. 다음 실행 시각과 식별자 순이다."""
        ...

    async def get_source(self, name: str) -> Source | None: ...

    async def list_sources(self) -> list[Source]:
        """지운 원천까지 모두 만든 시각 순으로 낸다. 같은 시각이면 ID 순이다."""
        ...

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

    async def get_index_version(self, version_id: UUID) -> IndexVersion | None: ...

    async def list_index_versions(self, knowledge_base_id: UUID) -> list[IndexVersion]:
        """물러난 판까지 모든 판을 만든 순서의 역순(ID의 내림차순)으로 낸다."""
        ...

    async def add_index_version(self, version: IndexVersion) -> None: ...

    async def update_index_version_endpoint(self, version_id: UUID, endpoint: str) -> None:
        """판에 적어 둔 임베딩 끝점만 고친다. 끝점은 판의 요소가 아니라 주소다."""
        ...

    async def switch_current_version(self, knowledge_base_id: UUID, new_version_id: UUID) -> None:
        """현재 판 참조를 새 판으로 바꾸고 새 판을 `current`, 옛 판을 `retired`로 쓴다."""
        ...

    async def list_purgeable_source_ids(self, deleted_before: datetime, limit: int) -> list[UUID]:
        """지움 표시의 시각이 `deleted_before` 이전이거나 같은 원천의 ID를 ID 순으로 `limit`개까지
        낸다. 정리 작업이 보관 기간이 지난 원천을 고르는 데 쓴다. 원천을 지우면 다음에 부를 때
        빠지므로 되풀이해 부르면 끝에 이른다."""
        ...

    async def delete_source(self, source_id: UUID) -> None:
        """원천 행을 지운다. 그 원천을 가리키는 문서, 작업, 동기화 기록은 먼저 지워 둔다. 부르기
        전에 `lock_source`로 잠근다."""
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

    async def list_live_document_ids(self, knowledge_base_id: UUID) -> list[UUID]:
        """`count_live_documents`가 세는 문서의 ID를 낸다. 재색인 시작이 문서마다 `pending`을
        쓴다."""
        ...

    async def list_documents(self, query: DocumentQuery) -> list[Document]:
        """조건에 맞는 문서를 최근 순(ID의 내림차순)으로 낸다. 지운 문서와 삭제 기록 행도 든다."""
        ...

    async def count_documents_of_source(self, source_id: UUID) -> DocumentCounts:
        """그 원천의, 지워지지 않은 문서를 문서 상태로 센다."""
        ...

    async def list_undeleted_ids_of_source(self, source_id: UUID, limit: int) -> list[UUID]:
        """그 원천의, 지워지지 않은 문서(삭제 기록 행이 아닌 것)의 ID를 ID 순으로 `limit`개까지
        낸다. 원천 삭제 작업이 묶음을 고르는 데 쓴다. 지운 문서는 다음에 부를 때 빠지므로 되풀이해
        부르면 끝에 이른다."""
        ...

    async def list_held_keys_of_source(self, source_id: UUID) -> dict[str, UUID]:
        """그 원천의, 지워지지 않은 문서와 원천과 함께 지워졌다는 표시가 남은 문서(원천 되살리기
        작업이 아직 되살리지 않은 문서)의 키마다 문서 ID를 낸다. 동기화가 삭제 반영 대상을 고르는 데
        쓴다. 표시가 남은 문서도 원천 폴더에 파일이 없으면 따로 지운 문서가 되어야 하기 때문이다."""
        ...

    async def list_ids_deleted_with_source(self, source_id: UUID, limit: int) -> list[UUID]:
        """그 원천의, 원천과 함께 지워졌다는 표시가 남은 문서(삭제 기록 행이 아닌 것)의 ID를 ID
        순으로 `limit`개까지 낸다. 원천 되살리기 작업이 묶음을 고르는 데 쓴다. 되살린 문서는 다음에
        부를 때 빠지므로 되풀이해 부르면 끝에 이른다."""
        ...

    async def list_stalled_ids_of_source(self, source_id: UUID, limit: int) -> list[UUID]:
        """그 원천의, 지워지지 않은 문서 가운데 색인이 멈춘 문서의 ID를 ID 순으로 `limit`개까지
        낸다. 색인이 멈춘 문서는 대상 판(그룹이 든 지식베이스의 현재 판과 건설 중인 판) 가운데 그
        문서의 지금 내용으로 색인되지 않은 판이 있는데 그 문서의 색인 작업이 대기 중도 실행 중도
        아닌 문서다. 지금 내용으로 색인되지 않은 판은 색인 상태가 `pending`이거나 상태 행이 없거나,
        `indexed`인데 만든 내용 해시가 문서의 내용 해시와 다른 판이다. `failed`는 정착한 것으로
        본다. 색인 작업을 넣으면 다음에 부를 때 빠진다."""
        ...

    async def has_documents_held_by_source(self, source_id: UUID) -> bool:
        """그 원천에 빈 목록 판정이 있는 문서로 셀 문서가 하나라도 있는가. 지워지지 않은 문서와,
        원천과 함께 지워졌다는 표시가 남은 문서(원천 되살리기 작업이 아직 되살리지 않은 문서)를
        센다. 완전히 지워져 삭제 기록 행만 남은 문서는 세지 않는다."""
        ...

    async def has_documents_deleted_with_source(self, source_id: UUID) -> bool:
        """그 원천에 원천과 함께 지워졌다는 표시가 남은 문서(삭제 기록 행이 아닌 것)가 있는가.
        정리 작업이 멈춘 원천 되살리기 작업을 찾는 데 쓴다."""
        ...

    async def has_undeleted_documents(self, source_id: UUID) -> bool:
        """그 원천에 지워지지 않은 문서가 하나라도 있는가. 정리 작업이 멈춘 원천 삭제 작업을 찾는 데
        쓴다."""
        ...

    async def list_purgeable_ids(self, deleted_before: datetime, limit: int) -> list[UUID]:
        """보관 기간이 지난 임시 삭제 문서의 ID를 ID 순으로 `limit`개까지 낸다. 지운 시각이
        `deleted_before` 이전이거나 같고, 완전히 지우지 않았고, 원천과 함께 지워졌다는 표시가 없는
        문서다. 표시가 있는 문서는 원천을 완전히 지울 때 함께 지우거나 원천 되살리기 작업이
        되살린다. 문서를 지우면 다음에 부를 때 빠지므로 되풀이해 부르면 끝에 이른다."""
        ...

    async def purge(self, document: Document, purged_at: datetime) -> None:
        """잠근 문서를 삭제 기록으로 바꾼다. 파싱 결과를 지우고 원본 경로를 비우고 완전히 지운
        시각을 적는다. 조각과 삭제 보관함의 조각은 `VectorIndex`가 지운다."""
        ...

    async def list_ids_of_source(self, source_id: UUID, limit: int) -> list[UUID]:
        """그 원천의 문서(삭제 기록 행까지 모두)의 ID를 ID 순으로 `limit`개까지 낸다. 정리 작업이
        원천을 지울 때 쓴다. 문서를 지우면 다음에 부를 때 빠지므로 되풀이해 부르면 끝에 이른다."""
        ...

    async def delete_documents(self, document_ids: Sequence[UUID]) -> None:
        """문서 행과 파싱 결과를 지운다. 그 문서를 가리키는 조각, 삭제 보관함의 조각, 색인 상태,
        작업은 먼저 지워 둔다."""
        ...

    async def referenced_blob_paths(self, paths: Sequence[str]) -> set[str]:
        """`paths` 가운데 어느 문서 행이 원본 경로로 가리키는 것을 낸다."""
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
        문서 행의 지금 값으로 고친다. 삭제 보관함은 되살림이 문서 행의 값으로 다시 쓰므로 건드리지
        않는다."""
        ...

    async def delete_chunks(self, document_id: UUID, index_version_id: UUID | None) -> None:
        """그 문서의 조각을 지운다. 판을 주지 않으면 모든 판의 것이다."""
        ...

    async def archive_chunks(self, document_id: UUID, archived_at: datetime) -> None:
        """그 문서의 모든 판의 조각을 삭제 보관함으로 옮긴다. 검색 표에는 남기지 않는다."""
        ...

    async def restore_archived_chunks(
        self, document: Document, index_version_ids: Sequence[UUID]
    ) -> dict[UUID, int]:
        """보관 조각 가운데 `index_version_ids`의 판의 것이면서 만든 내용 해시가 문서의 내용 해시와
        같은 것을 복사 칸(그룹, 갱신일, 시행일, 접근 그룹)을 문서의 지금 값으로 쓴 채 검색 표로
        되돌리고, 조각이 돌아온 판마다 돌아온 수를 낸다. 돌아온 판만 키로 든다. 삭제 보관함은
        건드리지 않는다(`delete_archived_chunks`가 지운다). 되돌리는 일과 센 수가 한 문장이어야
        해서 조회와 변경을 나누지 않고 수를 돌려준다."""
        ...

    async def delete_archived_chunks(self, document_id: UUID) -> None:
        """그 문서의 보관 조각을 모두 지운다."""
        ...

    async def count_chunks(self, document_id: UUID, index_version_id: UUID) -> int:
        """그 (문서, 판)의 조각 수."""
        ...

    async def list_chunks(self, document_id: UUID, index_version_id: UUID) -> list[StoredChunk]:
        """그 (문서, 판)의 조각을 순번 순으로 낸다(토크나이저 판만 다른 판이 복사해 갈 재료)."""
        ...

    async def count_states(self, index_version_id: UUID) -> dict[IndexStateStatus, int]:
        """그 판의 색인 상태를 상태마다 센다. 행이 없는 상태는 키로 들지 않는다(재색인의 진행과
        전환 검사)."""
        ...

    async def create_pending_states(
        self, index_version_id: UUID, document_ids: Sequence[UUID], now: datetime
    ) -> None:
        """그 판에 문서마다 색인 상태 `pending`을 쓴다(재색인 시작)."""
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

    async def diagnose_candidates(
        self, query: SearchQuery, *, scan: CandidateScan
    ) -> SearchDiagnosis:
        """`search_candidates`와 같은 SQL 뼈대로 벡터 후보와 키워드 후보의 합집합 전부를 낸다.
        줄마다 벡터·키워드·합친 순위가 붙고, 합친 순위가 후보 수 이하인 줄이 `search_candidates`의
        후보와 같다. `scan`이 `EXACT`이면 같은 트랜잭션에서 HNSW 색인을 쓰지 않는 계획으로 돌고, 그
        계획 설정은 호출이 성공하면 끝에 되돌려져 밖으로 새지 않는다(데이터베이스 오류로 끝나면
        트랜잭션이 되돌려진다). 평가가 단계의 순위를 재는 데만 쓰고 MCP로는 열지
        않는다 (원칙 IV, ADR 0018)."""
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

    async def enqueue_source_job(
        self,
        kind: JobKind,
        source_id: UUID,
        options: Mapping[str, JsonValue],
        request_id: UUID,
        now: datetime,
    ) -> Job | None:
        """원천 단위 작업(`sync_source`, `delete_source`, `restore_source`)을 넣는다. 같은 원천의
        같은 종류 작업이 대기 중이거나 실행 중이면 아무것도 넣지 않고 `None`을 낸다. 있는지 보는
        일과 넣는 일이 한 문장(`INSERT … ON CONFLICT DO NOTHING`)이어야 같은 원천에 동시에 넣어도
        하나만 들어가므로 조회와 변경을 나누지 않고 `Job`이나 `None`을
        돌려준다(`CODING_STANDARDS.md`의 CQS에 대한 의도한 예외다)."""
        ...

    async def enqueue_cleanup(self, since: datetime, request_id: UUID, now: datetime) -> Job | None:
        """정리 작업(`cleanup`)을 넣는다. `since` 이후에 넣은 정리 작업이 있거나(끝났어도 그렇다),
        대기 중이거나 실행 중인 정리 작업이 있으면 아무것도 넣지 않고 `None`을 낸다. 있는지 보는
        일과 넣는 일이 한 문장(`INSERT … SELECT … WHERE NOT EXISTS … ON CONFLICT DO NOTHING`)이어야
        일정 확인이 겹쳐 돌아도 하나만 들어가므로 조회와 변경을 나누지 않고 `Job`이나 `None`을
        돌려준다(`CODING_STANDARDS.md`의 CQS에 대한 의도한 예외다)."""
        ...

    async def latest_source_job(self, source_id: UUID, kind: JobKind) -> Job | None:
        """그 원천의 그 종류 작업 가운데 가장 나중에 만든 것(ID의 내림차순 첫째). 없으면
        `None`이다."""
        ...

    async def delete_jobs_of_documents(self, document_ids: Sequence[UUID]) -> None:
        """그 문서들을 가리키는 작업 행을 상태와 상관없이 모두 지운다. 작업 표가 문서를 가리키는
        외래 키에는 지울 때의 동작이 없어, 문서 행을 지우기 전에 부른다. 그 작업을 가리키던 동기화
        기록은 작업 참조만 비고 남는다."""
        ...

    async def delete_jobs_of_source(self, source_id: UUID) -> None:
        """그 원천을 가리키는 작업 행(동기화, 원천 삭제, 원천 되살리기)을 상태와 상관없이 모두
        지운다. 원천 행을 지우기 전에 부른다."""
        ...

    async def delete_queued(self, document_id: UUID) -> None:
        """그 문서의 대기(`queued`) 작업을 지운다. 실행 중인 작업과 끝난 작업은 건드리지 않는다."""
        ...

    async def lock_queued_source_job(self, source_id: UUID, kind: JobKind) -> Job | None:
        """그 원천의 그 종류 대기(`queued`) 작업 행을 `FOR UPDATE`로 잠가 낸다. 없으면 `None`이다.
        작업자가 막 꺼내 `running`이 된 작업은 대기 작업이 아니다."""
        ...

    async def delete_queued_job(self, job_id: UUID) -> None:
        """잠가 둔 대기 작업 행을 지운다. 그 작업을 가리키던 동기화 기록은 작업 참조만 비고
        남는다."""
        ...

    async def lock_queued_documents(self, document_ids: Sequence[UUID]) -> set[UUID]:
        """`document_ids` 가운데 대기 작업이 있는 문서의 대기 작업 행을 `FOR UPDATE`로 잠그고 그
        문서들을 낸다(재색인 시작이 잠근 문서에는 새 작업을 넣지 않는다). 작업자가 꺼낼 때의
        `SKIP LOCKED`는 잠긴 행을 건너뛴다. 작업자가 막 꺼내 `running`이 된 행은 잠금을 기다린 뒤
        조건에 맞지 않아 들지 않는다."""
        ...

    async def get(self, job_id: UUID) -> Job | None: ...

    async def list_jobs(
        self, status: JobStatus | None, limit: int, after: UUID | None
    ) -> list[Job]:
        """작업을 최근 순(ID의 내림차순)으로 낸다. `status`를 주면 그 상태의 작업만이고, `after`는
        마지막으로 본 작업의 ID다."""
        ...

    async def has_active_job(self, document_id: UUID) -> bool:
        """그 문서에 대기(`queued`)나 실행 중(`running`)인 작업이 있는지 본다."""
        ...

    async def has_active_source_job(self, source_id: UUID, kinds: Sequence[JobKind]) -> bool:
        """그 원천에 `kinds` 가운데 한 종류의 작업이 대기(`queued`)나 실행 중(`running`)인지
        본다. 원천을 지우거나 되살리는 요청이 앞의 작업이 끝났는지 볼 때 쓴다."""
        ...

    async def claim(self, worker_id: str, now: datetime, lease_seconds: float) -> Job | None:
        """`SKIP LOCKED`로 꺼낼 수 있는 작업 하나를 `running`으로 바꿔 낸다. 꺼내는 일과 바꾸는 일을
        나누면 두 작업자가 같은 작업을 잡으므로 한 번에 하고 `Job`을 돌려준다. 두 번 묻는다. 색인
        작업이 아닌 작업이 있으면 그 가운데 예약 시각과 식별자 순으로 먼저 꺼내고, 없을 때만 색인
        작업을 같은 순서로 꺼낸다(명세 "작업 대기열")."""
        ...

    async def hold_attempt(self, job: Job) -> bool:
        """작업 행을 잠그고 작업자 ID와 시도 횟수가 이 시도가 꺼낼 때 쓴 값 그대로인지 본다(작업 행
        조건). 아니면 작업 담당 기록의 기한이 끝나 다른 작업자가 가져간 것이라 `False`이고, 부른
        쪽은 아무것도 쓰지 않고 작업 단위를 롤백한다. 문서 행과 지식베이스 행을 잠근 뒤 마지막에
        부른다."""
        ...

    async def record_raised_generation(self, job: Job, generation: int) -> None:
        """이번 시도가 첫째 단계에서 올린 문서의 세대를 작업 행에 적는다."""
        ...

    async def finish(self, job: Job, outcome: JobOutcome, now: datetime) -> None:
        """작업을 끝낸 상태로 쓴다. 이 시도가 쓴 작업 행이 아니면(작업 담당 기록의 기한이 끝나 다른
        작업자가 가져갔다) 아무것도 쓰지 않고 `AttemptLostError`를 올린다. 부른 쪽이 끝난 줄 알고
        지나가지 못하게 반환값이 아니라 예외로 알린다."""
        ...

    async def reschedule(self, job: Job, run_after: datetime, error_code: ErrorCode) -> bool:
        """일시 실패한 시도의 작업을 `queued`로 되돌려 `run_after`와 마지막 오류 코드를 두고 작업
        담당 기록과 작업자와 올린 세대를 비운다(시도 횟수는 둔다). 같은 문서에 다른 대기 작업이
        있거나 이 시도가 쓴 작업 행이 아니면 아무것도 쓰지 않고 `False`다. 같은 문서의 대기 작업은
        부분 유일 색인으로 하나라서, 되돌리는 일과 다른 대기 작업을 보는 일이 한 문장이어야 해
        조회와 변경을 나누지 않는다(`CODING_STANDARDS.md`의 CQS에 대한 의도한 예외다). 문서 행과
        지식베이스 행(`SHARE`)을 잠근 뒤 `hold_attempt` 다음에 부른다."""
        ...

    async def has_other_job_from_start(self, document_id: UUID, excluding_job_id: UUID) -> bool:
        """그 문서를 처음부터 맡을 다른 작업이 있는지 본다. 대기 작업과, 실행 중이면서 올린 세대가
        빈 작업이다. 올린 세대가 채워진 실행 중 작업은 세지 않는다(재시도 소진의 판정)."""
        ...

    async def extend_lease(self, job: Job, leased_until: datetime) -> None:
        """작업 담당 기록의 만료 시각을 `leased_until`로 늘린다. 작업 행 조건을 지날 때만 쓰고,
        아니면 그 기한이 끝나 다른 작업자가 가져간 것이라 아무것도 쓰지 않고 `AttemptLostError`를
        올린다(부른 쪽은 그 시도를 버린다). 문서 행을 잠그지 않고 작업 행 하나만 쓰므로 잠금 순서를
        거스르지 않는다."""
        ...


class IndexMaintenance(Protocol):
    """물러난 판의 정리. 작업 단위 밖에서 부른다. `DROP INDEX CONCURRENTLY`는 트랜잭션 안에서 부를
    수 없고(`25001`), 조각은 묶음마다 별도 트랜잭션에서 지워 큰 지식베이스에서도 한 트랜잭션을 길게
    하지 않는다(명세 "수집 파이프라인과 작업"의 판 전환 항목). 정리는 여러 작업자가 겹쳐 돌아도
    안전하다."""

    async def list_versions_to_clean(
        self, knowledge_base_id: UUID | None = None
    ) -> list[IndexVersion]:
        """물러난 판 가운데 HNSW 색인이나 조각이 남은 것. 지식베이스를 주면 그 지식베이스의
        것만이다."""
        ...

    async def drop_version_index(self, index_version_id: UUID) -> None:
        """판의 HNSW 부분 색인을 `DROP INDEX CONCURRENTLY IF EXISTS`로 지운다."""
        ...

    async def delete_version_chunks(self, index_version_id: UUID, limit: int) -> int:
        """판의 조각을 최대 `limit`개 지우고 지운 수를 낸다. 한 번이 한 트랜잭션이다."""
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


class ConnectorRegistry(Protocol):
    """커넥터의 이름과 원천의 설정을 받아 커넥터를 만들고 인터페이스 버전을 판정한다(source-sync
    명세 "층과 포트"). 트랜잭션 밖에서 부른다. 메서드의 모양은 처음 쓰는 티켓이 바꿀 수 있다."""

    def create(self, name: str, config: Mapping[str, JsonValue]) -> Connector:
        """그 이름의 커넥터를 원천의 설정으로 만든다. 원천에 닿지 않는다. 설치되지 않은 이름이거나
        인터페이스 버전의 major가 1이 아닌 커넥터는 `ConnectorUnavailableError`로 거부한다. 만드는
        함수가 설정이 틀렸다고 알리면 그 `ConnectorError`(사유 `invalid_config`)를 그대로 올린다."""
        ...

    async def locate_folder(self, name: str, config: Mapping[str, JsonValue]) -> FolderLocation:
        """서버 경로 커넥터(`SERVER_PATH_CONNECTOR`)의 폴더를 찾고 확인한다. 인터페이스 밖에서
        서버가 부르는 확인이다. 적은 글자 그대로 찾고, 없으면 NFC로 맞춘 이름이 같은 폴더가 하나뿐일
        때만 그 폴더로 본다. 낸 저장 경로는 글자 그대로 찾은 토막이면 적은 글자이고, NFC로 맞춰
        찾은 토막만 디스크의 이름이다. 호출 장치를 지나고 한도를 넘기거나
        막혀도 폴더를 읽을 수 없다는 `ConnectorError`(사유 `unreadable`)다. 없는 폴더는 `not_found`,
        링크나 폴더가 아닌 것은 `rejected`, 모양이 틀린 설정은 `invalid_config`다."""
        ...

    async def survey_folders(self, targets: Sequence[FolderTarget]) -> list[FolderLocation | None]:
        """이미 있는 원천의 폴더를 한꺼번에 확인한다. 대상마다 따로 내보내 같은 한도 동안 함께
        기다린다. 폴더가 없거나 읽을 수 없거나 한도 안에 답하지 않거나 막힌 대상은 `None`이다.
        부르는 쪽이 그 원천과는 저장 경로의 글자로 견준다."""
        ...

    def open_reader(
        self,
        name: str,
        config: Mapping[str, JsonValue],
        *,
        source: str,
        timeout_seconds: float,
    ) -> SourceReader:
        """작업자가 원천을 읽는 길을 낸다. 커넥터를 만들고(`create`와 같은 예외) 그 `list()`와
        `fetch`를 호출 장치에 태운다. 호출 하나는 `timeout_seconds`까지만 기다린다. `source`는
        한도를 넘긴 호출의 로그 줄에 싣는 원천의 이름이다."""
        ...

    async def check_connection(
        self, name: str, config: Mapping[str, JsonValue], source: str
    ) -> None:
        """커넥터의 `check()`를 호출 장치를 지나 부른다. `source`는 로그에 싣는 원천의 이름이다.
        만들 수 없으면 `ConnectorUnavailableError`나 `ConnectorError`(`invalid_config`)를, 커넥터의
        `ConnectorError`는 그대로, 한도를 넘기면 `ConnectorCallTimedOutError`를, 같은 설정의 호출이
        남아 있으면 `ConnectorCallBlockedError`를, 인터페이스에 없는 예외는 `ConnectorBrokenError`를
        올린다."""
        ...


class ScheduleCalculator(Protocol):
    """일정 표현식(cron 다섯 칸)을 확인하고 다음 실행 시각을 낸다(source-sync 명세 "일정과 일정
    확인"). 두 메서드 모두 받지 않는 표현식에 `InvalidScheduleError`를 올린다."""

    def validate(self, expression: str) -> None:
        """표현식을 받으면 그대로 돌아오고, 칸 수가 다섯이 아니거나 값이 틀리거나 오지 않는
        날짜이면 `InvalidScheduleError`를 올린다."""
        ...

    def next_run(self, expression: str, after: datetime) -> datetime:
        """`after`보다 뒤인 첫 실행 시각을 UTC로 낸다. `after`와 같은 시각은 넘긴다. 표현식의 시각은
        설치 전체에 하나인 시간대 설정으로 읽는다."""
        ...


class SyncRecordStore(Protocol):
    """동기화 기록의 저장소. 동기화 기록을 동기화 작업을 넣는 같은 작업 단위에서 만들기 때문에 작업
    단위 안에서 얻는 포트다(`Transaction.sync_records`)."""

    async def add(self, record: SyncRecord) -> None: ...

    async def get(self, record_id: UUID) -> SyncRecord | None: ...

    async def get_by_job(self, job_id: UUID) -> SyncRecord | None:
        """그 동기화 작업이 쓰는 기록. 작업자가 기록을 찾는 데 쓴다."""
        ...

    async def update(self, record: SyncRecord) -> None:
        """같은 식별자의 기록을 이 값으로 바꾼다. 개수와 상태와 끝 시각을 쓰는 데 쓴다."""
        ...

    async def list_for_source(
        self, source_id: UUID, limit: int, after: UUID | None
    ) -> list[SyncRecord]:
        """그 원천의 기록을 최근 것부터(ID의 내림차순) 낸다. `after`는 마지막으로 본 기록의 ID다."""
        ...

    async def latest_for_source(self, source_id: UUID) -> SyncRecord | None:
        """그 원천의 가장 최근 기록. 없으면 `None`이다."""
        ...

    async def delete_of_source(self, source_id: UUID) -> None:
        """그 원천의 동기화 기록을 모두 지운다. 원천 행을 지우기 전에 정리 작업이 부른다."""
        ...

    async def delete_finished_before(self, cutoff: datetime, limit: int) -> int:
        """끝난 시각이 `cutoff` 이전이거나 같은 기록을 `limit`건까지 지우고 지운 수를 낸다. 끝나지
        않은 기록과, 원천마다 가장 최근 기록(ID가 가장 큰 것) 하나는 지우지 않는다. 지운 수가
        `limit`보다 적으면 더 지울 기록이 없다."""
        ...


class Transaction(Protocol):
    """작업 단위 안에서 얻는 다섯 포트. 한 연결의 한 트랜잭션을 공유한다."""

    @property
    def catalog(self) -> Catalog: ...

    @property
    def documents(self) -> DocumentStore: ...

    @property
    def index(self) -> VectorIndex: ...

    @property
    def jobs(self) -> JobQueue: ...

    @property
    def sync_records(self) -> SyncRecordStore: ...


class UnitOfWork(Protocol):
    """트랜잭션의 경계. 블록을 예외 없이 나가면 커밋이고 예외로 나가면 롤백이다.

    명시적 `commit()`은 두지 않는다. 두 길이 있으면 한쪽을 잊는다. 산문에서는 "작업 단위"라 쓰고
    대기열의 "작업"과 가른다(GLOSSARY.md 작업 항목).
    """

    def begin(self) -> AbstractAsyncContextManager[Transaction]: ...
