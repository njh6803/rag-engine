"""`search` 유스케이스(명세 "검색 흐름", 티켓 07).

지식베이스를 고르고(없거나 토큰 범위 밖이면 `knowledge_base_not_found`), 현재 판이 없으면 빈 결과를
낸다. 있으면 질의를 현재 판에 적힌 끝점·모델·차원으로 임베딩하고 키워드 토큰을 뽑아, SQL 하나로
벡터와 키워드 후보를 모아 RRF로 합친다. 같은 문장이 읽은 판이 그사이 전환되어 더는 현재 판이
아니면 결과를 버리고 처음부터 한 번 다시 하고, 다시 해도 아니면 `search_unavailable`이다.

리랭크, 필터, 전체 시간 제한, 입력 검증은 09가 채운다. 점수는 RRF 점수이고 순위는 1부터다. 질의
글은 어디에도 남기지 않는다(원칙 V). 지연은 호출한 쪽이 로그로 남긴다.
"""

import asyncio
import time
from dataclasses import dataclass
from uuid import UUID

from rag_engine.domain.entities import (
    IndexVersion,
    KnowledgeBase,
    SearchHit,
    SearchQuery,
)
from rag_engine.domain.errors import (
    ErrorCode,
    PermanentFailure,
    RequestError,
    TransientFailure,
)
from rag_engine.domain.ports import Catalog, EmbedderFor, KeywordTokenizer, UnitOfWork

_MS_PER_SECOND = 1000.0
# 판이 전환되어 결과를 버린 뒤 다시 하는 횟수. 한 번 다시 하고도 아니면 `search_unavailable`이다.
_REDO_LIMIT = 1


@dataclass(frozen=True, slots=True)
class SearchDeps:
    unit_of_work: UnitOfWork
    embedder_for: EmbedderFor
    tokenize_keywords: KeywordTokenizer
    candidates: int


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """검색 요청. `allowed_knowledge_base_ids`가 비면 토큰 범위는 전부다."""

    query: str
    top_k: int
    knowledge_base: str | None
    allowed_knowledge_base_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class SearchTimings:
    embedding_ms: float
    sql_ms: float


@dataclass(frozen=True, slots=True)
class SearchResults:
    """쓴 지식베이스의 이름과 점수 순의 후보(`top_k`개까지). 순위는 목록의 자리에 1을 더한
    값이다."""

    knowledge_base: str
    hits: tuple[SearchHit, ...]
    timings: SearchTimings


async def search_documents(deps: SearchDeps, request: SearchRequest) -> SearchResults:
    embedding_ms = 0.0
    sql_ms = 0.0
    for _ in range(_REDO_LIMIT + 1):
        async with deps.unit_of_work.begin() as transaction:
            knowledge_base = await _pick_knowledge_base(transaction.catalog, request)
            version = await _current_version(transaction.catalog, knowledge_base)
        if version is None:
            return SearchResults(knowledge_base.name, (), SearchTimings(0.0, 0.0))

        # 임베딩은 서버를 기다리고 토큰화는 CPU를 쓰므로 함께 진행한다. 토큰화는 스레드로 넘긴다.
        # 한쪽이 실패해도 다른 쪽은 끝까지 돌고, 정확성에는 영향이 없다.
        started = time.perf_counter()
        vector, keywords = await asyncio.gather(
            _embed_query(deps, version, request.query),
            asyncio.to_thread(deps.tokenize_keywords, request.query),
        )
        embedding_ms += (time.perf_counter() - started) * _MS_PER_SECOND

        started = time.perf_counter()
        async with deps.unit_of_work.begin() as transaction:
            found = await transaction.index.search_candidates(
                SearchQuery(
                    knowledge_base_id=knowledge_base.id,
                    index_version_id=version.id,
                    dimensions=version.embedding_dimensions,
                    vector=vector,
                    keywords=tuple(keywords),
                    candidates=deps.candidates,
                )
            )
        sql_ms += (time.perf_counter() - started) * _MS_PER_SECOND
        if found.is_current:
            return SearchResults(
                knowledge_base.name,
                found.hits[: request.top_k],
                SearchTimings(embedding_ms, sql_ms),
            )
    raise RequestError(ErrorCode.SEARCH_UNAVAILABLE, "색인 판이 바뀌는 중이라 검색하지 못했다")


async def _pick_knowledge_base(catalog: Catalog, request: SearchRequest) -> KnowledgeBase:
    """이름이 없으면 기본 지식베이스다. 없거나 토큰 범위 밖이면 같은 오류를 내 범위 밖 지식베이스의
    존재를 드러내지 않는다."""
    if request.knowledge_base is not None:
        found = await catalog.get_knowledge_base(request.knowledge_base)
    else:
        found = next(
            (
                candidate
                for candidate in await catalog.list_knowledge_bases()
                if candidate.is_default
            ),
            None,
        )
    scope = request.allowed_knowledge_base_ids
    if found is None or (scope and found.id not in scope):
        raise RequestError(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND, "지식베이스를 찾을 수 없다")
    return found


async def _current_version(catalog: Catalog, knowledge_base: KnowledgeBase) -> IndexVersion | None:
    current_id = knowledge_base.current_index_version_id
    if current_id is None:
        return None
    versions = await catalog.list_live_index_versions(knowledge_base.id)
    return next((version for version in versions if version.id == current_id), None)


async def _embed_query(deps: SearchDeps, version: IndexVersion, query: str) -> tuple[float, ...]:
    """질의를 판에 적힌 끝점·모델·차원으로 임베딩한다. 임베딩 서버를 쓸 수 없으면 검색을 쓸 수
    없는 것이다. 서버의 오류 메시지는 옮기지 않는다."""
    try:
        (vector,) = await deps.embedder_for(version).embed([query])
    except (TransientFailure, PermanentFailure):
        raise RequestError(ErrorCode.SEARCH_UNAVAILABLE, "질의를 임베딩하지 못했다") from None
    return vector
