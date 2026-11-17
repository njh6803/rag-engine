"""`search` 유스케이스(명세 "검색 흐름", 티켓 07, 09).

입력을 검증한 뒤(빈 질의와 범위 밖 `top_k`는 `invalid_argument`) 아래를 `RAG_SEARCH_TIMEOUT_SECONDS`
안에서 한다. 지식베이스를 고르고(없거나 토큰 범위 밖이면 `knowledge_base_not_found`), 현재 판이
없으면 빈 결과를 낸다. 있으면 질의를 현재 판에 적힌 끝점·모델·차원으로 임베딩하고 키워드 토큰을
뽑아, SQL 하나로 필터(그룹, 갱신일 기간)를 단 벡터와 키워드 후보를 모아 RRF로 합친다. 같은 문장이
읽은 판이 그사이 전환되어 더는 현재 판이 아니면 결과를 버리고 처음부터 한 번 다시 하고, 다시 해도
아니면 `search_unavailable`이다. 지식베이스에 리랭커가 있으면 후보 전부를 리랭크해 점수 순으로
바꾸고, 리랭커가 실패해도 RRF로 대신하지 않고 `search_unavailable`이다. 시간 제한을 넘겨도 같다.

최소 점수(ADR 0017)는 리랭크 점수가 그 값보다 낮은 조각을 `top_k`로 자르기 앞에서 뺀다(같은 점수는
남는다). 요청 인자가 있으면 그 값이, 없으면 지식베이스의 기본값이, 둘 다 없으면 거르지 않는다. 0
이상 1 이하의 유한한 값만 받는다. 리랭커가 없는 지식베이스에 요청의 값을 주면(0도)
`invalid_argument`이고, 요청 인자 없이 리랭커가 빈 채 기본값이 있는 행은 `search_unavailable`이다.
남은 조각이 없으면 오류가 아니라 빈 결과다.

점수는 리랭크 점수이고 리랭커가 없으면 RRF 점수다. 순위는 1부터다. 질의 글은 어디에도 남기지 않는다
(원칙 V). 지연은 호출한 쪽이 로그로 남긴다.
"""

import asyncio
import time
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from rag_engine.app.scope import is_in_scope
from rag_engine.domain.entities import (
    IndexVersion,
    KnowledgeBase,
    SearchFilter,
    SearchHit,
    SearchQuery,
)
from rag_engine.domain.errors import (
    ErrorCode,
    PermanentFailure,
    RequestError,
    TransientFailure,
)
from rag_engine.domain.index_text import compose_index_text
from rag_engine.domain.ports import (
    Catalog,
    EmbedderFor,
    KeywordTokenizer,
    Reranker,
    RerankerFor,
    UnitOfWork,
)

_MS_PER_SECOND = 1000.0
# 판이 전환되어 결과를 버린 뒤 다시 하는 횟수. 한 번 다시 하고도 아니면 `search_unavailable`이다.
_REDO_LIMIT = 1


@dataclass(frozen=True, slots=True)
class SearchDeps:
    unit_of_work: UnitOfWork
    embedder_for: EmbedderFor
    reranker_for: RerankerFor
    tokenize_keywords: KeywordTokenizer
    candidates: int
    max_top_k: int
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """검색 요청. `allowed_knowledge_base_ids`가 비면 토큰 범위는 전부다.

    `groups`는 그룹 이름이다. `None`이나 빈 묶음이면 그룹으로 거르지 않고, 없는 이름은 아무
    문서에도 맞지 않는다. `updated_after`는 그 시각을 포함하고 `updated_before`는 포함하지 않으며
    오프셋이 있는 시각이다. `min_score`는 요청이 준 최소 점수이고 `None`이면 지식베이스의 기본값을
    따른다.
    """

    query: str
    top_k: int
    knowledge_base: str | None
    allowed_knowledge_base_ids: tuple[UUID, ...]
    groups: tuple[str, ...] | None = None
    updated_after: datetime | None = None
    updated_before: datetime | None = None
    min_score: float | None = None


@dataclass(frozen=True, slots=True)
class SearchTimings:
    """단계마다의 지연. 리랭커가 없으면 `rerank_ms`는 0이다."""

    embedding_ms: float
    sql_ms: float
    rerank_ms: float


@dataclass(frozen=True, slots=True)
class SearchResults:
    """쓴 지식베이스의 이름과 점수 순의 후보(`top_k`개까지). 순위는 목록의 자리에 1을 더한
    값이다."""

    knowledge_base: str
    hits: tuple[SearchHit, ...]
    timings: SearchTimings


async def search_documents(deps: SearchDeps, request: SearchRequest) -> SearchResults:
    _validate(deps, request)
    try:
        async with asyncio.timeout(deps.timeout_seconds):
            return await _search_within_limit(deps, request)
    except TimeoutError:
        raise RequestError(ErrorCode.SEARCH_UNAVAILABLE, "검색이 시간 제한을 넘겼다") from None


def _validate(deps: SearchDeps, request: SearchRequest) -> None:
    if not request.query.strip():
        raise RequestError(ErrorCode.INVALID_ARGUMENT, "질의가 비어 있다")
    if not 1 <= request.top_k <= deps.max_top_k:
        raise RequestError(
            ErrorCode.INVALID_ARGUMENT, f"top_k는 1 이상 {deps.max_top_k} 이하여야 한다"
        )
    # 범위를 긍정형으로 써야 `nan`이 걸린다. `nan`은 어느 비교도 거짓이라 `x < 0 or x > 1`은
    # 지나가고, `inf`도 이 식이 막는다. 오류에 값을 싣지 않는다.
    min_score = request.min_score
    if min_score is not None and not 0 <= min_score <= 1:
        raise RequestError(
            ErrorCode.INVALID_ARGUMENT, "min_score는 0 이상 1 이하의 유한한 수여야 한다"
        )


async def _search_within_limit(deps: SearchDeps, request: SearchRequest) -> SearchResults:
    embedding_ms = 0.0
    sql_ms = 0.0
    for _ in range(_REDO_LIMIT + 1):
        async with deps.unit_of_work.begin() as transaction:
            knowledge_base = await _pick_knowledge_base(transaction.catalog, request)
            version = await _current_version(transaction.catalog, knowledge_base)
            group_ids = await _group_ids(transaction.catalog, request.groups)
        reranker = deps.reranker_for(knowledge_base)
        min_score = _effective_min_score(request, knowledge_base, reranker)
        if version is None:
            return SearchResults(knowledge_base.name, (), SearchTimings(0.0, 0.0, 0.0))

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
                    filter=SearchFilter(
                        group_ids=group_ids,
                        updated_after=request.updated_after,
                        updated_before=request.updated_before,
                    ),
                )
            )
        sql_ms += (time.perf_counter() - started) * _MS_PER_SECOND
        if found.is_current:
            hits, rerank_ms = await _rank(reranker, request.query, found.hits)
            return SearchResults(
                knowledge_base.name,
                _at_least(hits, min_score)[: request.top_k],
                SearchTimings(embedding_ms, sql_ms, rerank_ms),
            )
    raise RequestError(ErrorCode.SEARCH_UNAVAILABLE, "색인 판이 바뀌는 중이라 검색하지 못했다")


def _effective_min_score(
    request: SearchRequest, knowledge_base: KnowledgeBase, reranker: Reranker | None
) -> float | None:
    """이 검색에 걸 최소 점수. 요청 인자가 지식베이스의 기본값을 이긴다(0도 이긴다). 최소 점수는
    리랭크 점수에 거는 값이라 리랭커가 없으면, 요청이 준 값은 `invalid_argument`로 거부하고(거른다고
    잘못 믿지 않게) 요청 인자 없이 기본값만 있는 행은 `search_unavailable`이다. 둘이 겹치면 요청
    인자 쪽을 먼저 거부한다."""
    if reranker is not None:
        given = request.min_score
        return knowledge_base.min_score if given is None else given
    if request.min_score is not None:
        raise RequestError(
            ErrorCode.INVALID_ARGUMENT, "리랭커가 없는 지식베이스에는 min_score를 줄 수 없다"
        )
    if knowledge_base.min_score is not None:
        raise RequestError(
            ErrorCode.SEARCH_UNAVAILABLE,
            "지식베이스에 최소 점수가 설정되어 있는데 리랭커가 없어 검색하지 못했다",
        )
    return None


def _at_least(hits: tuple[SearchHit, ...], min_score: float | None) -> tuple[SearchHit, ...]:
    """점수가 `min_score`보다 낮은 조각을 뺀다. 같은 점수는 남고 순서는 그대로다. `None`이면 거르지
    않는다."""
    if min_score is None:
        return hits
    return tuple(hit for hit in hits if hit.score >= min_score)


async def _rank(
    reranker: Reranker | None, query: str, hits: tuple[SearchHit, ...]
) -> tuple[tuple[SearchHit, ...], float]:
    """리랭커가 있으면 후보 전부를 리랭크해 점수 순으로 바꾸고 걸린 시간(ms)을 함께 낸다. 없으면 RRF
    순서 그대로이고 시간은 0이다."""
    if reranker is None or not hits:
        return hits, 0.0
    started = time.perf_counter()
    reranked = await _rerank(reranker, query, hits)
    return reranked, (time.perf_counter() - started) * _MS_PER_SECOND


async def _rerank(
    reranker: Reranker, query: str, hits: tuple[SearchHit, ...]
) -> tuple[SearchHit, ...]:
    """리랭커가 매긴 점수로 순서를 바꾼다. 점수가 같으면 RRF 순서를 지킨다. 실패하면 조용히 품질이
    바뀐 결과를 내지 않고 검색을 쓸 수 없다고 알린다. 서버의 오류 메시지는 옮기지 않는다."""
    texts = [compose_index_text(hit.location.section, hit.text) for hit in hits]
    try:
        scores = await reranker.rerank(query, texts)
    except (TransientFailure, PermanentFailure):
        raise RequestError(ErrorCode.SEARCH_UNAVAILABLE, "후보를 리랭크하지 못했다") from None
    scored = [replace(hit, rerank_score=score) for hit, score in zip(hits, scores, strict=True)]
    return tuple(sorted(scored, key=lambda hit: hit.score, reverse=True))


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
    if found is None or not is_in_scope(request.allowed_knowledge_base_ids, found.id):
        raise RequestError(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND, "지식베이스를 찾을 수 없다")
    return found


async def _current_version(catalog: Catalog, knowledge_base: KnowledgeBase) -> IndexVersion | None:
    current_id = knowledge_base.current_index_version_id
    if current_id is None:
        return None
    versions = await catalog.list_live_index_versions(knowledge_base.id)
    return next((version for version in versions if version.id == current_id), None)


async def _group_ids(catalog: Catalog, names: tuple[str, ...] | None) -> tuple[UUID, ...] | None:
    """그룹 이름을 식별자로 푼다. 없는 이름은 빠지고 아무 문서에도 맞지 않는다. 이름을 주지 않았거나
    빈 묶음이면 그룹으로 거르지 않는다(`None`)."""
    if not names:
        return None
    groups = [await catalog.get_group(name) for name in dict.fromkeys(names)]
    return tuple(group.id for group in groups if group is not None)


async def _embed_query(deps: SearchDeps, version: IndexVersion, query: str) -> tuple[float, ...]:
    """질의를 판에 적힌 끝점·모델·차원으로 임베딩한다. 임베딩 서버를 쓸 수 없으면 검색을 쓸 수
    없는 것이다. 서버의 오류 메시지는 옮기지 않는다."""
    try:
        (vector,) = await deps.embedder_for(version).embed([query])
    except (TransientFailure, PermanentFailure):
        raise RequestError(ErrorCode.SEARCH_UNAVAILABLE, "질의를 임베딩하지 못했다") from None
    return vector
