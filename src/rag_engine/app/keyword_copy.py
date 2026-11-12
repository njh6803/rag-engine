"""토크나이저 판만 다른 `building` 판의 조각 복사(명세 "수집 파이프라인과 작업"의 셋째 단계).

건설 중인 판이 같은 지식베이스의 현재 판과 판 스키마, 임베딩 모델, 차원, 청킹 해시가 같으면(키워드
규칙만 바꾼 재색인) 청킹과 임베딩을 하지 않는다. 임베딩 끝점은 보지 않는다. 현재 판의 그 문서 조각
가운데 만든 내용 해시가 첫째 단계에서 기억한 해시와 같은 것의 글, 위치, 임베딩을 그대로 쓰고
키워드만 다시 만든다. 그런 조각이 없으면(현재 판이 아직 옛 내용이면) 다른 판처럼 청킹과 임베딩을
한다.

키워드는 조각 글이 아니라 색인 때의 글(`index_text`: 줄인 절 경로, 빈 줄, 조각 글)로 만든다.
저장하는 조각에는 조각 글과 온전한 절 경로만 있으므로, 절 경로를 상한 안으로 줄이는
규칙(`fit_section`, 청킹도 같은 함수를 쓴다)을 같은 토크나이저로 되풀이해 글을 되짓는다. 토큰 수를
세는 일은 임베딩이 아니다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from rag_engine.domain.entities import (
    ChunkDraft,
    IndexVersion,
    IndexVersionStatus,
    StoredChunk,
)
from rag_engine.domain.index_text import compose_index_text, fit_section, section_candidates
from rag_engine.domain.ports import Embedder, KeywordTokenizer, Transaction


@dataclass(frozen=True, slots=True)
class CopiedMaterial:
    """복사로 얻은 판 하나의 조각 재료. 조각 순번은 목록 순서다."""

    drafts: list[ChunkDraft]
    embeddings: list[tuple[float, ...]]
    keyword_texts: list[str]


def copy_source_of(version: IndexVersion, live: Sequence[IndexVersion]) -> IndexVersion | None:
    """`version`이 조각을 복사해 올 현재 판. 건설 중인 판이고 같은 지식베이스의 현재 판과 판 스키마,
    임베딩 모델, 차원, 청킹 해시가 같을 때만 있다."""
    if version.status is not IndexVersionStatus.BUILDING:
        return None
    for source in live:
        if (
            source.status is IndexVersionStatus.CURRENT
            and source.knowledge_base_id == version.knowledge_base_id
            and source.schema_version == version.schema_version
            and source.embedding_model == version.embedding_model
            and source.embedding_dimensions == version.embedding_dimensions
            and source.chunking_hash == version.chunking_hash
        ):
            return source
    return None


async def read_copy_sources(
    transaction: Transaction, live: Sequence[IndexVersion], document_id: UUID, content_hash: str
) -> dict[UUID, list[StoredChunk]]:
    """복사할 수 있는 판마다 복사해 올 조각을 판 ID로 묶어 낸다. 복사할 조각이 없는 판은 키로 들지
    않는다."""
    sources: dict[UUID, list[StoredChunk]] = {}
    for version in live:
        current = copy_source_of(version, live)
        if current is None:
            continue
        stored = await transaction.index.list_chunks(document_id, current.id)
        usable = [chunk for chunk in stored if chunk.source_content_hash == content_hash]
        if usable:
            sources[version.id] = usable
    return sources


async def rebuild_keywords(
    embedder: Embedder,
    tokenize_keywords: KeywordTokenizer,
    version: IndexVersion,
    stored: Sequence[StoredChunk],
) -> CopiedMaterial:
    """복사한 조각의 색인 때 글을 되짓고 키워드만 다시 만든다."""
    lines = sorted(
        {line for chunk in stored for line in section_candidates(chunk.location.section)}
    )
    counts = await embedder.count_tokens(lines) if lines else []
    line_tokens = dict(zip(lines, counts, strict=True))
    drafts = [
        ChunkDraft(
            text=chunk.text,
            index_text=compose_index_text(
                fit_section(chunk.location.section, version.chunking.max_tokens, line_tokens),
                chunk.text,
            ),
            token_count=chunk.token_count,
            location=chunk.location,
        )
        for chunk in stored
    ]
    return CopiedMaterial(
        drafts=drafts,
        embeddings=[chunk.embedding for chunk in stored],
        keyword_texts=[" ".join(tokenize_keywords(draft.index_text)) for draft in drafts],
    )
