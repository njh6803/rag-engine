"""놓친 질의의 탈락 지점과 낱말 겹침(티켓 search-eval 06, 명세 "놓친 까닭").

마지막 단계의 상위 10개에 닿은 조각이 없는 질의마다 탈락 지점 하나를 붙인다. 아래 넷을 차례로 보아
처음 맞는 것이고, 닿는 조각 가운데 가장 멀리 간 것을 기준으로 삼는 셈이다.

- `no_matching_chunk`: 기대한 문서의 현재 판 조각 가운데 어느 것도 기대 근거에 닿지 않는다(글귀가
  조각의 경계에서 갈렸거나, 파싱이 그 글을 내지 못했거나, 문서가 색인되지 않았다).
- `not_in_candidates`: 닿는 조각이 색인에 있는데 벡터 후보에도 키워드 후보에도 들지 못했다.
- `lost_in_fusion`: 닿는 조각이 어느 한쪽 후보에는 들었는데 합치기에서 밀렸다. 빠른 실행에서는 합친
  순위가 10 안인 것이 없다는 뜻이고, 전체 실행에서는 합친 순위가 후보 수 안인 것이 없어 리랭커에
  들어가지 못했다는 뜻이다.
- `lost_in_rerank`: 전체 실행에서만 난다. 닿는 조각이 리랭커에 들어갔는데 리랭크 뒤 순위가 10
  밖이다.

닿는 조각은 문서의 키와 조각 순번 쌍으로 가리킨다. 진단용 검색의 줄(`DiagnosedHit`)과 색인의 조각
목록(`VectorIndex.list_chunks`)이 같은 순번을 쓴다.

낱말 겹침은 글귀로 적은 기대 근거에만 낸다. 질의의 키워드 토큰 가운데 글귀의 키워드 토큰에 든 것의
비율이다. 같은 토큰은 한 번으로 센다. 기대 근거가 글귀 여럿이면 글귀들의 토큰을 합쳐 견주고,
질의에서 키워드 토큰이 하나도 나오지 않거나 글귀로 적은 기대 근거가 없으면 값이 없다(`None`).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from rag_engine.app.eval_metrics import BlockPages, reaches
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.entities import DiagnosedHit
from rag_engine.domain.eval_set import EvidenceItem, PassageEvidence
from rag_engine.domain.ports import KeywordTokenizer

type ChunkId = tuple[str, int]


class MissCause(StrEnum):
    """놓친 질의가 검색 흐름의 어디에서 떨어졌는지(탈락 지점)."""

    NO_MATCHING_CHUNK = "no_matching_chunk"
    NOT_IN_CANDIDATES = "not_in_candidates"
    LOST_IN_FUSION = "lost_in_fusion"
    LOST_IN_RERANK = "lost_in_rerank"


@dataclass(frozen=True, slots=True)
class ChunkRef:
    """색인의 조각 하나를 가리키는 값. 글과 덮은 블록의 범위만 든다(벡터는 들지 않는다)."""

    ordinal: int
    text: str
    block_range: tuple[int, int]


def reaching_chunks(
    item: EvidenceItem, chunks: Mapping[str, Sequence[ChunkRef]], pages: BlockPages
) -> frozenset[ChunkId]:
    """`chunks`(문서의 키마다 그 문서의 조각)에서 기대 근거 어느 하나에라도 닿는 조각을 (키, 순번)
    쌍으로 모은다."""
    return frozenset(
        (key, chunk.ordinal)
        for key, listed in chunks.items()
        for chunk in listed
        if any(
            reaches(expectation, key, chunk.text, chunk.block_range, pages)
            for expectation in item.evidence
        )
    )


def classify_miss(
    reaching: frozenset[ChunkId],
    hits: Sequence[DiagnosedHit],
    *,
    candidates: int,
    last_stage: Stage,
) -> MissCause:
    """마지막 단계의 상위 10개에 닿은 조각이 없는 질의의 탈락 지점. `reaching`은 색인에서 닿는
    조각, `hits`는 진단용 검색의 줄(벡터와 키워드 후보의 합집합), `last_stage`는 평가의 마지막
    단계(`Stage.FUSED`나 `Stage.RERANK`)다."""
    if not reaching:
        return MissCause.NO_MATCHING_CHUNK
    candidate_hits = [hit for hit in hits if (hit.hit.key, hit.ordinal) in reaching]
    if not candidate_hits:
        return MissCause.NOT_IN_CANDIDATES
    reranked = any(hit.fused_rank <= candidates for hit in candidate_hits)
    if last_stage is Stage.RERANK and reranked:
        return MissCause.LOST_IN_RERANK
    return MissCause.LOST_IN_FUSION


def word_overlap(item: EvidenceItem, query: str, tokenize: KeywordTokenizer) -> float | None:
    """질의의 키워드 토큰 가운데 글귀의 키워드 토큰에 든 것의 비율. 값이 없으면 `None`이다."""
    passages = [
        expectation.passage
        for expectation in item.evidence
        if isinstance(expectation, PassageEvidence)
    ]
    query_tokens = set(tokenize(query))
    if not passages or not query_tokens:
        return None
    passage_tokens = {token for passage in passages for token in tokenize(passage)}
    return len(query_tokens & passage_tokens) / len(query_tokens)
