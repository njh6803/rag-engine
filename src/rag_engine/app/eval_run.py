"""평가 유스케이스: 빠른 실행(티켓 search-eval 04, 명세 "진단용 검색과 단계").

질의마다 실제 검색과 같은 준비를 한다. 기본 지식베이스의 현재 판에 적힌 모델·차원으로 질의를
임베딩하고, 같은 키워드 토크나이저로 토큰을 뽑고, 설정의 후보 수와 `CandidateScan.EXACT`로
`diagnose_candidates`를 한 번 부른다. 단계의 순위는 그 한 번의 결과에서 만든다. 벡터만은
`vector_rank` 순, 키워드만은 `keyword_rank` 순, 합친 뒤는 `fused_rank`가 후보 수 이하인 줄의 그
순위다. 키워드 토큰이 빈 질의는 키워드만 단계에서 결과가 없는 것으로 센다.

검색 유스케이스를 부르지 않고 같은 준비(지식베이스와 현재 판 읽기, 질의 임베딩)를 이 모듈에서
따로 한다. 검색 유스케이스는 `top_k`로 자른 결과만 돌려주어 단계의 순위를 주지 못하고, 시간
제한은 평가가 재는 것(품질)이 아니다. 지식베이스는 기본 지식베이스(`DEFAULT_NAME`)의 현재 판
하나다. 질의를 임베딩하는 끝점은 호출하는 쪽이 건넨 `embedder_for`가 정한다. 평가는 판에 적힌
끝점이 아니라 환경의 끝점을 쓴다.

평가 도중 판이 전환되면(`is_current`가 거짓) 평가를 `EvalRunError`로 끝낸다. 평가는 고정된 색인
하나를 재는 일이라 다시 하지 않는다. 질의의 글과 조각의 글은 결과에 싣지 않고 식별자와 순위만
싣는다(원칙 V).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.app.eval_metrics import passage_reaches
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
    EvalSet,
    EvidenceItem,
    Expectation,
    PassageEvidence,
)
from rag_engine.domain.ports import EmbedderFor, KeywordTokenizer, UnitOfWork

type Reach = tuple[frozenset[int], ...]


class Stage(StrEnum):
    """검색 흐름에서 순위를 따로 재는 자리. 리랭크 뒤는 전체 실행이 더한다."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    FUSED = "fused"


class EvalRunError(Exception):
    """평가를 끝까지 하지 못한 까닭. 메시지는 값이 아니라 까닭만 싣는다."""


@dataclass(frozen=True, slots=True)
class EvalRunDeps:
    unit_of_work: UnitOfWork
    embedder_for: EmbedderFor
    tokenize_keywords: KeywordTokenizer


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    """질의 하나의 단계별 결과. `reach[단계][i]`는 그 단계에서 순위 `i + 1`인 조각이 닿은 기대
    근거의 번호(질문의 기대 근거 안의 자리) 집합이다. `expected`는 그 질문의 기대 근거 수다."""

    query_list: str
    evidence_id: str
    expected: int
    reach: dict[Stage, Reach]


@dataclass(frozen=True, slots=True)
class IndexSummary:
    """평가가 잰 색인. 현재 판의 요소와 조각 수다."""

    elements: IndexElements
    chunks: int


@dataclass(frozen=True, slots=True)
class EvalRunResult:
    index: IndexSummary
    outcomes: tuple[QueryOutcome, ...]


async def run_fast_evaluation(
    deps: EvalRunDeps, eval_set: EvalSet, *, candidates: int
) -> EvalRunResult:
    """질의 목록의 모든 질의를 합친 뒤까지 평가한다. `candidates`는 `config.json`의
    `search_candidates`다."""
    evidence = {item.id: item for item in eval_set.evidence}
    knowledge_base, version, summary = await _current_index(deps, eval_set)
    embedder = deps.embedder_for(version)
    outcomes: list[QueryOutcome] = []
    for query_list in eval_set.query_lists:
        for query in query_list.queries:
            item = evidence.get(query.evidence_id)
            if item is None:
                raise EvalRunError(f"질의의 기대 근거 {query.evidence_id}가 기대 근거 목록에 없다")
            try:
                (vector,) = await embedder.embed([query.query])
            except (TransientFailure, PermanentFailure):
                raise EvalRunError("질의를 임베딩하지 못했다") from None
            keywords = tuple(deps.tokenize_keywords(query.query))
            async with deps.unit_of_work.begin() as transaction:
                diagnosis = await transaction.index.diagnose_candidates(
                    SearchQuery(
                        knowledge_base_id=knowledge_base.id,
                        index_version_id=version.id,
                        dimensions=version.embedding_dimensions,
                        vector=vector,
                        keywords=keywords,
                        candidates=candidates,
                        filter=_search_filter(query.filter),
                    ),
                    scan=CandidateScan.EXACT,
                )
            if not diagnosis.is_current:
                raise EvalRunError("평가하는 사이 색인 판이 바뀌었다. 평가는 다시 하지 않는다")
            outcomes.append(
                QueryOutcome(
                    query_list=query_list.name,
                    evidence_id=query.evidence_id,
                    expected=len(item.evidence),
                    reach={
                        stage: _reach(
                            item, stage_ranking(diagnosis.hits, stage, keywords, candidates)
                        )
                        for stage in Stage
                    },
                )
            )
    return EvalRunResult(index=summary, outcomes=tuple(outcomes))


async def _current_index(
    deps: EvalRunDeps, eval_set: EvalSet
) -> tuple[KnowledgeBase, IndexVersion, IndexSummary]:
    """기본 지식베이스와 그 현재 판과 조각 수를 읽는다. 판이 없으면 색인되지 않은 것이다."""
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
            if document is not None and document.deleted_at is None:
                chunks += await transaction.index.count_chunks(document.id, version.id)
    return knowledge_base, version, IndexSummary(elements=version.elements, chunks=chunks)


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
    """단계의 순위 순으로 늘어선 줄. 합친 뒤는 `fused_rank`가 후보 수 이하인 줄만이다."""
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


def _reach(item: EvidenceItem, ranked: Sequence[DiagnosedHit]) -> Reach:
    return tuple(
        frozenset(
            number
            for number, expectation in enumerate(item.evidence)
            if _reaches(expectation, hit.hit.key, hit.hit.text)
        )
        for hit in ranked
    )


def _reaches(expectation: Expectation, hit_key: str, hit_text: str) -> bool:
    """글귀로 적은 기대 근거는 조각의 문서가 그 문서일 때만 닿는다. 쪽으로 적은 기대 근거의 적중은
    놓친 까닭을 다루는 티켓이 더한다."""
    return (
        isinstance(expectation, PassageEvidence)
        and hit_key == expectation.document
        and passage_reaches(expectation.passage, hit_text)
    )
