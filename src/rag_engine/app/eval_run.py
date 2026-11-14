"""평가 유스케이스: 빠른 실행과 전체 실행(티켓 search-eval 04, 05, 06, 명세 "진단용 검색과 단계").

질의마다 실제 검색과 같은 준비를 한다. 기본 지식베이스의 현재 판에 적힌 모델·차원으로 질의를
임베딩하고, 같은 키워드 토크나이저로 토큰을 뽑고, 설정의 후보 수와 `CandidateScan.EXACT`로
`diagnose_candidates`를 한 번 부른다. 단계의 순위는 그 한 번의 결과에서 만든다. 벡터만은
`vector_rank` 순, 키워드만은 `keyword_rank` 순, 합친 뒤는 `fused_rank`가 후보 수 이하인 줄의 그
순위다. 키워드 토큰이 빈 질의는 키워드만 단계에서 결과가 없는 것으로 센다.

빠른 실행(`run_fast_evaluation`)은 여기까지다. 전체 실행(`run_full_evaluation`)은 합친 뒤의 후보
전부를 실제 검색과 같은 `Reranker` 포트로 채점해 리랭크 뒤 단계를 더한다. 그 순위는 점수 순이고
점수가 같으면 합친 순위 순이며, 리랭커에 보내는 글은 검색과 같이 절 경로를 붙인 글이다. 후보
전부의 점수와 닿았는지는 `QueryOutcome.scored`에 남아 점수 분포의 재료가 된다(빠른 실행은 `None`).

마지막 단계(빠른 실행은 합친 뒤, 전체 실행은 리랭크 뒤)의 상위 10개에 닿은 조각이 없는 질의에는
탈락 지점과 낱말 겹침(`QueryMiss`)을 붙인다(`eval_misses`). 필터가 붙은 질의는
`diagnose_candidates`를 `CandidateScan.INDEX`로 한 번 더 불러 HNSW 계획의 벡터 후보 수를
센다(`FilterScanProbe`). 정확 스캔도 후보를 채우지 못하는 경우(필터를 지나는 조각이 후보 수보다
적다)는 모자란 것으로 세지 않는다.

검색 유스케이스를 부르지 않고 같은 준비(지식베이스와 현재 판 읽기, 질의 임베딩)를 이 모듈에서
따로 한다. 검색 유스케이스는 `top_k`로 자른 결과만 돌려주어 단계의 순위를 주지 못하고, 시간
제한은 평가가 재는 것(품질)이 아니다. 지식베이스는 기본 지식베이스(`DEFAULT_NAME`)의 현재 판
하나다. 질의를 임베딩하는 끝점은 호출하는 쪽이 건넨 `embedder_for`가 정한다. 평가는 판에 적힌
끝점이 아니라 환경의 끝점을 쓴다. `inspect`(`eval_inspect`)는 `Evaluator`(`open_evaluator`)를
거쳐 같은 준비 함수(`read_evaluation_index`, `prepare_query`, `diagnose`, `rerank_candidates`)를
쓴다.

평가 도중 판이 전환되면(`is_current`가 거짓) 평가를 `EvalRunError`로 끝낸다. 평가는 고정된 색인
하나를 재는 일이라 다시 하지 않는다. 질의의 글과 조각의 글은 결과에 싣지 않고 식별자와 순위만
싣는다(원칙 V).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.app.eval_metrics import TOP_K, BlockPages, reaches
from rag_engine.app.eval_misses import (
    ChunkRef,
    MissCause,
    classify_miss,
    reaching_chunks,
    word_overlap,
)
from rag_engine.app.eval_stages import FAST_STAGES, Stage
from rag_engine.domain.entities import (
    CandidateScan,
    DiagnosedHit,
    IndexElements,
    IndexVersion,
    KnowledgeBase,
    SearchFilter,
    SearchQuery,
)
from rag_engine.domain.errors import PermanentFailure, TransientFailure
from rag_engine.domain.eval_set import (
    EvalFilter,
    EvalQuery,
    EvalSet,
    EvidenceItem,
    PageEvidence,
)
from rag_engine.domain.index_text import compose_index_text
from rag_engine.domain.ports import Embedder, EmbedderFor, KeywordTokenizer, Reranker, UnitOfWork

type Reach = tuple[frozenset[int], ...]


class EvalRunError(Exception):
    """평가를 끝까지 하지 못한 까닭. 메시지는 값이 아니라 까닭만 싣는다."""


@dataclass(frozen=True, slots=True)
class EvalRunDeps:
    unit_of_work: UnitOfWork
    embedder_for: EmbedderFor
    tokenize_keywords: KeywordTokenizer


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """리랭크 뒤 순위의 조각 하나. 리랭커가 매긴 점수와 그 조각이 기대 근거에 하나라도 닿았는지다.
    글이나 식별자는 싣지 않는다(원칙 V)."""

    score: float
    reached: bool


@dataclass(frozen=True, slots=True)
class QueryMiss:
    """마지막 단계의 상위 10개에 닿은 조각이 없는 질의의 탈락 지점과 낱말 겹침(값이 없으면
    `None`)이다."""

    cause: MissCause
    word_overlap: float | None


@dataclass(frozen=True, slots=True)
class FilterScanProbe:
    """필터가 붙은 질의 하나의 벡터 후보 수. `expected_vectors`는 정확 스캔이 낸 벡터 후보 수와 후보
    수 가운데 작은 값이고, `index_vectors`는 HNSW 색인 계획이 낸 벡터 후보 수다. 정확 스캔도 필터를
    지나는 조각이 후보 수보다 적어 후보를 채우지 못한 몫은 `expected_vectors`가 이미 덜어 낸다."""

    expected_vectors: int
    index_vectors: int

    @property
    def short(self) -> bool:
        return self.index_vectors < self.expected_vectors


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    """질의 하나의 단계별 결과. `reach[단계][i]`는 그 단계에서 순위 `i + 1`인 조각이 닿은 기대
    근거의 번호(질문의 기대 근거 안의 자리) 집합이다. `expected`는 그 질문의 기대 근거 수다.
    `scored`는 전체 실행에서만 있고(빠른 실행은 `None`, 후보가 하나도 없었던 전체 실행은 빈 튜플),
    합친 뒤의 후보 전부를 리랭크 뒤 순위 순으로 담는다. `miss`는 마지막 단계에서 놓친 질의에만 있고
    `filter_probe`는 필터가 붙은 질의에만 있다."""

    query_list: str
    evidence_id: str
    expected: int
    reach: dict[Stage, Reach]
    scored: tuple[ScoredCandidate, ...] | None = None
    miss: QueryMiss | None = None
    filter_probe: FilterScanProbe | None = None


@dataclass(frozen=True, slots=True)
class IndexSummary:
    """평가가 잰 색인. 현재 판의 요소와 조각 수다."""

    elements: IndexElements
    chunks: int


@dataclass(frozen=True, slots=True)
class EvalRunResult:
    index: IndexSummary
    outcomes: tuple[QueryOutcome, ...]


@dataclass(frozen=True, slots=True)
class EvaluationIndex:
    """평가가 재는 색인 하나: 기본 지식베이스와 그 현재 판, 기본 원천의 ID, 조각 수, 쪽으로 적은
    기대 근거가 가리키는 문서의 블록 쪽 번호다."""

    knowledge_base: KnowledgeBase
    version: IndexVersion
    source_id: UUID
    summary: IndexSummary
    pages: BlockPages


@dataclass(frozen=True, slots=True)
class PreparedQuery:
    """임베딩하고 키워드 토큰을 뽑은 질의. 정확 스캔과 색인 스캔이 같은 벡터를 쓴다."""

    query: EvalQuery
    vector: tuple[float, ...]
    keywords: tuple[str, ...]


async def run_fast_evaluation(
    deps: EvalRunDeps, eval_set: EvalSet, *, candidates: int
) -> EvalRunResult:
    """질의 목록의 모든 질의를 합친 뒤까지 평가한다. `candidates`는 `config.json`의
    `search_candidates`다."""
    return await _evaluate(deps, eval_set, candidates=candidates, reranker=None)


async def run_full_evaluation(
    deps: EvalRunDeps, reranker: Reranker, eval_set: EvalSet, *, candidates: int
) -> EvalRunResult:
    """질의 목록의 모든 질의를 리랭크 뒤까지 평가한다. 합친 뒤의 후보 전부를 실제 검색과 같은
    `Reranker` 포트로 채점한다. 리랭커의 모델은 지식베이스가 아니라 `config.json`의
    `reranker_model`이라, 포트를 지을 때 호출하는 쪽이 정한다."""
    return await _evaluate(deps, eval_set, candidates=candidates, reranker=reranker)


@dataclass(slots=True)
class _DocumentChunks:
    """놓친 질의가 기대한 문서의 조각 목록. 문서마다 한 번만 읽는다."""

    deps: EvalRunDeps
    index: EvaluationIndex
    cache: dict[str, list[ChunkRef]] = field(default_factory=dict[str, list[ChunkRef]])

    async def get(self, key: str) -> list[ChunkRef]:
        if key not in self.cache:
            self.cache[key] = await self._read(key)
        return self.cache[key]

    async def _read(self, key: str) -> list[ChunkRef]:
        async with self.deps.unit_of_work.begin() as transaction:
            document = await transaction.documents.get_by_key(self.index.source_id, key)
            if document is None or document.deleted_at is not None:
                return []
            stored = await transaction.index.list_chunks(document.id, self.index.version.id)
        return [ChunkRef(chunk.ordinal, chunk.text, chunk.location.block_range) for chunk in stored]


@dataclass(frozen=True, slots=True)
class RankedQuery:
    """질의 하나의 단계별 순위. `rankings[단계]`는 그 단계의 순위 순으로 늘어선 줄이고, `hits`는
    진단용 검색이 낸 줄 전부(벡터와 키워드 후보의 합집합)다. `scores`는 리랭크 뒤 순위
    (`rankings[Stage.RERANK]`)의 리랭크 점수이고 빠른 실행은 `None`이다."""

    prepared: PreparedQuery
    hits: tuple[DiagnosedHit, ...]
    rankings: dict[Stage, tuple[DiagnosedHit, ...]]
    scores: tuple[float, ...] | None


@dataclass(frozen=True, slots=True)
class Evaluator:
    """평가가 재는 색인 하나에 대해 질의를 평가한다. `reranker`가 없으면 합친 뒤까지, 있으면
    리랭크 뒤까지가 마지막 단계다. `inspect`도 같은 순위를 쓴다."""

    deps: EvalRunDeps
    index: EvaluationIndex
    embedder: Embedder
    reranker: Reranker | None
    candidates: int
    chunks: _DocumentChunks

    @property
    def last_stage(self) -> Stage:
        return Stage.FUSED if self.reranker is None else Stage.RERANK

    async def rank(self, query: EvalQuery) -> RankedQuery:
        """질의를 임베딩하고 진단용 검색을 한 번 불러 단계마다의 순위를 만든다."""
        prepared = await prepare_query(self.deps, self.embedder, query)
        hits = await diagnose(
            self.deps, self.index, prepared, candidates=self.candidates, scan=CandidateScan.EXACT
        )
        rankings = {
            stage: tuple(stage_ranking(hits, stage, prepared.keywords, self.candidates))
            for stage in FAST_STAGES
        }
        scores: tuple[float, ...] | None = None
        if self.reranker is not None:
            ranked = await rerank_candidates(self.reranker, query.query, rankings[Stage.FUSED])
            rankings[Stage.RERANK] = tuple(hit for hit, _ in ranked)
            scores = tuple(score for _, score in ranked)
        return RankedQuery(prepared, hits, rankings, scores)

    async def outcome(
        self, query_list: str, item: EvidenceItem, ranked: RankedQuery
    ) -> QueryOutcome:
        """순위에서 질의의 결과를 만든다. 마지막 단계에서 놓쳤으면 탈락 지점과 낱말 겹침을, 필터가
        붙은 질의면 HNSW 계획의 벡터 후보 수를 더한다."""
        pages = self.index.pages
        reach = {stage: _reach(item, ranking, pages) for stage, ranking in ranked.rankings.items()}
        scored: tuple[ScoredCandidate, ...] | None = None
        if ranked.scores is not None:
            scored = tuple(
                ScoredCandidate(score, bool(reached))
                for score, reached in zip(ranked.scores, reach[Stage.RERANK], strict=True)
            )
        query = ranked.prepared.query
        missed = not any(reach[self.last_stage][:TOP_K])
        return QueryOutcome(
            query_list=query_list,
            evidence_id=query.evidence_id,
            expected=len(item.evidence),
            reach=reach,
            scored=scored,
            miss=await self._analyze_miss(item, query.query, ranked.hits) if missed else None,
            filter_probe=await self._probe_filter(ranked.prepared, ranked.hits),
        )

    async def _analyze_miss(
        self, item: EvidenceItem, query: str, hits: Sequence[DiagnosedHit]
    ) -> QueryMiss:
        keys = dict.fromkeys(expectation.document for expectation in item.evidence)
        chunks = {key: await self.chunks.get(key) for key in keys}
        cause = classify_miss(
            reaching_chunks(item, chunks, self.index.pages),
            hits,
            candidates=self.candidates,
            last_stage=self.last_stage,
        )
        return QueryMiss(cause, word_overlap(item, query, self.deps.tokenize_keywords))

    async def _probe_filter(
        self, prepared: PreparedQuery, exact_hits: Sequence[DiagnosedHit]
    ) -> FilterScanProbe | None:
        if not _search_filter(prepared.query.filter).is_active:
            return None
        index_hits = await diagnose(
            self.deps, self.index, prepared, candidates=self.candidates, scan=CandidateScan.INDEX
        )
        return FilterScanProbe(
            expected_vectors=min(self.candidates, _vector_candidates(exact_hits)),
            index_vectors=_vector_candidates(index_hits),
        )


def _vector_candidates(hits: Sequence[DiagnosedHit]) -> int:
    return sum(1 for hit in hits if hit.vector_rank is not None)


async def open_evaluator(
    deps: EvalRunDeps, eval_set: EvalSet, *, candidates: int, reranker: Reranker | None
) -> Evaluator:
    """기본 지식베이스의 현재 판을 읽고 그 판의 모델로 질의를 임베딩하는 평가자를 만든다."""
    index = await read_evaluation_index(deps, eval_set)
    return Evaluator(
        deps=deps,
        index=index,
        embedder=deps.embedder_for(index.version),
        reranker=reranker,
        candidates=candidates,
        chunks=_DocumentChunks(deps, index),
    )


def find_evidence(eval_set: EvalSet, evidence_id: str) -> EvidenceItem:
    """질문의 기대 근거. 없으면 `EvalRunError`다."""
    for item in eval_set.evidence:
        if item.id == evidence_id:
            return item
    raise EvalRunError(f"질의의 기대 근거 {evidence_id}가 기대 근거 목록에 없다")


async def _evaluate(
    deps: EvalRunDeps, eval_set: EvalSet, *, candidates: int, reranker: Reranker | None
) -> EvalRunResult:
    evaluator = await open_evaluator(deps, eval_set, candidates=candidates, reranker=reranker)
    outcomes: list[QueryOutcome] = []
    for query_list in eval_set.query_lists:
        for query in query_list.queries:
            item = find_evidence(eval_set, query.evidence_id)
            ranked = await evaluator.rank(query)
            outcomes.append(await evaluator.outcome(query_list.name, item, ranked))
    return EvalRunResult(index=evaluator.index.summary, outcomes=tuple(outcomes))


async def prepare_query(deps: EvalRunDeps, embedder: Embedder, query: EvalQuery) -> PreparedQuery:
    """질의를 현재 판의 모델로 임베딩하고 키워드 토큰을 뽑는다."""
    try:
        (vector,) = await embedder.embed([query.query])
    except (TransientFailure, PermanentFailure):
        raise EvalRunError("질의를 임베딩하지 못했다") from None
    return PreparedQuery(query, vector, tuple(deps.tokenize_keywords(query.query)))


async def diagnose(
    deps: EvalRunDeps,
    index: EvaluationIndex,
    prepared: PreparedQuery,
    *,
    candidates: int,
    scan: CandidateScan,
) -> tuple[DiagnosedHit, ...]:
    """진단용 검색을 한 번 부른다. 판이 그사이 전환되었으면 `EvalRunError`다."""
    async with deps.unit_of_work.begin() as transaction:
        diagnosis = await transaction.index.diagnose_candidates(
            SearchQuery(
                knowledge_base_id=index.knowledge_base.id,
                index_version_id=index.version.id,
                dimensions=index.version.embedding_dimensions,
                vector=prepared.vector,
                keywords=prepared.keywords,
                candidates=candidates,
                filter=_search_filter(prepared.query.filter),
            ),
            scan=scan,
        )
    if not diagnosis.is_current:
        raise EvalRunError("평가하는 사이 색인 판이 바뀌었다. 평가는 다시 하지 않는다")
    return diagnosis.hits


async def rerank_candidates(
    reranker: Reranker, query: str, fused: Sequence[DiagnosedHit]
) -> list[tuple[DiagnosedHit, float]]:
    """합친 뒤의 후보 전부를 리랭크한다. 후보가 없으면 리랭커를 부르지 않는다. 실패하면 점수를
    조용히 비우지 않고 평가를 끝낸다. 서버의 오류 메시지는 옮기지 않는다."""
    if not fused:
        return []
    try:
        scores = await reranker.rerank(query, rerank_texts(fused))
    except (TransientFailure, PermanentFailure):
        raise EvalRunError("후보를 리랭크하지 못했다") from None
    return rerank_ranking(fused, scores)


async def read_evaluation_index(deps: EvalRunDeps, eval_set: EvalSet) -> EvaluationIndex:
    """기본 지식베이스와 그 현재 판과 조각 수를 읽는다. 판이 없으면 색인되지 않은 것이다. 쪽으로
    적은 기대 근거가 가리키는 문서는 최신 파싱 결과에서 블록의 쪽 번호도 읽는다."""
    page_keys = {
        expectation.document
        for item in eval_set.evidence
        for expectation in item.evidence
        if isinstance(expectation, PageEvidence)
    }
    pages: dict[str, dict[int, int | None]] = {}
    async with deps.unit_of_work.begin() as transaction:
        catalog = transaction.catalog
        knowledge_base = await catalog.get_knowledge_base(DEFAULT_NAME)
        source = await catalog.get_source(DEFAULT_NAME)
        current_id = None if knowledge_base is None else knowledge_base.current_index_version_id
        version = None if current_id is None else await catalog.get_index_version(current_id)
        if knowledge_base is None or source is None or version is None:
            raise EvalRunError("기본 지식베이스의 현재 판이 없다. 먼저 index를 친다")
        chunks = 0
        for listed in eval_set.documents:
            document = await transaction.documents.get_by_key(source.id, listed.key)
            if document is None or document.deleted_at is not None:
                continue
            chunks += await transaction.index.count_chunks(document.id, version.id)
            if listed.key in page_keys:
                content = await transaction.documents.get_content(document.id)
                if content is not None:
                    pages[listed.key] = {block.ordinal: block.page for block in content.blocks}
    return EvaluationIndex(
        knowledge_base=knowledge_base,
        version=version,
        source_id=source.id,
        summary=IndexSummary(elements=version.elements, chunks=chunks),
        pages=pages,
    )


def _search_filter(value: EvalFilter | None) -> SearchFilter:
    """그룹 필터는 이 판의 묶음이 거부하므로(`validate`) 옮기지 않는다."""
    if value is None:
        return SearchFilter()
    return SearchFilter(
        group_ids=None, updated_after=value.updated_after, updated_before=value.updated_before
    )


def stage_ranking(
    hits: Sequence[DiagnosedHit], stage: Stage, keywords: Sequence[str], candidates: int
) -> list[DiagnosedHit]:
    """단계의 순위 순으로 늘어선 줄. 합친 뒤는 `fused_rank`가 후보 수 이하인 줄만이다. 리랭크
    뒤는 점수가 있어야 만들 수 있어 `rerank_ranking`이 만든다."""
    if stage is Stage.RERANK:
        raise ValueError("리랭크 뒤 순위는 점수가 필요해 rerank_ranking이 만든다")
    if stage is Stage.VECTOR:
        vector = [hit for hit in hits if hit.vector_rank is not None]
        return sorted(vector, key=lambda hit: hit.vector_rank or 0)
    if stage is Stage.KEYWORD:
        if not keywords:
            return []
        keyword = [hit for hit in hits if hit.keyword_rank is not None]
        return sorted(keyword, key=lambda hit: hit.keyword_rank or 0)
    fused = [hit for hit in hits if hit.fused_rank <= candidates]
    return sorted(fused, key=lambda hit: hit.fused_rank)


def rerank_texts(hits: Sequence[DiagnosedHit]) -> list[str]:
    """리랭커에 보내는 글. 검색(`app/search.py`의 `_rerank`)과 같이 절 경로를 온전히 붙인 글이다."""
    return [compose_index_text(hit.hit.location.section, hit.hit.text) for hit in hits]


def rerank_ranking(
    fused: Sequence[DiagnosedHit], scores: Sequence[float]
) -> list[tuple[DiagnosedHit, float]]:
    """합친 뒤의 줄을 리랭크 점수가 큰 순서로 늘어놓는다. 점수가 같으면 합친 순위 순이다(명세
    "진단용 검색과 단계"). `scores`는 `fused`의 줄마다 하나다."""
    if len(scores) != len(fused):
        raise ValueError(f"점수 {len(scores)}개가 줄 {len(fused)}개와 맞지 않는다")
    return sorted(zip(fused, scores, strict=True), key=lambda pair: (-pair[1], pair[0].fused_rank))


def chunk_reach(item: EvidenceItem, hit: DiagnosedHit, pages: BlockPages) -> frozenset[int]:
    """조각 하나가 닿은 기대 근거의 번호(질문의 기대 근거 안의 자리) 집합."""
    return frozenset(
        number
        for number, expectation in enumerate(item.evidence)
        if reaches(expectation, hit.hit.key, hit.hit.text, hit.hit.location.block_range, pages)
    )


def _reach(item: EvidenceItem, ranked: Sequence[DiagnosedHit], pages: BlockPages) -> Reach:
    return tuple(chunk_reach(item, hit, pages) for hit in ranked)
