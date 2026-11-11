"""읽기 도구 `get_document`와 `list_knowledge_bases`의 유스케이스(명세 "MCP 도구", 티켓 09).

두 도구 모두 토큰 범위 밖 지식베이스를 드러내지 않는다. 문서는 지워졌거나 그 그룹이 든 지식베이스가
토큰 범위 안에 하나도 없으면(그룹이 든 지식베이스가 아예 없는 경우도 같다) `document_not_found`다.
파싱 결과의 글은 문서의 지금 내용으로 파싱한 것일 때만 낸다. 옛 내용의 글은 원천의 지금 내용이
아니고(원칙 VI), 그룹을 바꾼 문서면 옛 그룹의 지식베이스에서만 볼 수 있던 글이 새 그룹의 토큰에
나간다(원칙 V).
"""

from dataclasses import dataclass
from uuid import UUID

from rag_engine.app.document_text import text_length, text_window
from rag_engine.app.scope import is_in_scope
from rag_engine.domain.entities import Block, Document, KnowledgeBase
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import Transaction, UnitOfWork


@dataclass(frozen=True, slots=True)
class DocumentView:
    """`get_document`가 내는 문서. `chunk_counts`는 토큰 범위 안 지식베이스의 이름마다 현재 판의
    조각 수다. `text_length`는 지금 내용의 파싱 결과가 있을 때만 있고, `text`와 `next_offset`은
    거기에 글을 요청했을 때만 있다(`next_offset`은 전문이 그 창에서 끝나면 `None`)."""

    document: Document
    source: str
    group: str
    chunk_counts: dict[str, int]
    text_length: int | None
    text: str | None
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class KnowledgeBaseView:
    knowledge_base: KnowledgeBase
    document_count: int


async def get_document(
    unit_of_work: UnitOfWork,
    document_id: UUID,
    *,
    allowed_knowledge_base_ids: tuple[UUID, ...],
    include_text: bool,
    offset: int = 0,
    max_chars: int | None = None,
    max_text_chars: int,
) -> DocumentView:
    """`max_chars`를 주지 않으면 창의 크기는 `max_text_chars`(설정의 상한)다. `offset`과
    `max_chars`의 범위는 글을 요청하지 않아도 문서와 상관없이 본다. 글을 요청했는데 `offset`이
    전문의 길이를 넘는 것은 문서를 찾고 범위를 확인한 뒤에 본다. 볼 수 없는 문서의 길이를
    드러내지 않기 위해서다."""
    window_size = max_text_chars if max_chars is None else max_chars
    if not 1 <= window_size <= max_text_chars:
        raise RequestError(ErrorCode.INVALID_ARGUMENT, "max_chars가 범위 밖이다")
    if offset < 0:
        raise RequestError(ErrorCode.INVALID_ARGUMENT, "offset이 0보다 작다")
    async with unit_of_work.begin() as transaction:
        document = await transaction.documents.get(document_id)
        if document is None or document.deleted_at is not None:
            raise _not_found()
        visible = [
            knowledge_base
            for knowledge_base in await transaction.catalog.list_knowledge_bases_of_group(
                document.group_id
            )
            if is_in_scope(allowed_knowledge_base_ids, knowledge_base.id)
        ]
        if not visible:
            raise _not_found()
        source = await transaction.catalog.get_source_by_id(document.source_id)
        group = await transaction.catalog.get_group_by_id(document.group_id)
        if source is None or group is None:
            raise RuntimeError("문서가 가리키는 원천이나 그룹이 없다")
        blocks = await _parsed_blocks(transaction, document)
        length = None if blocks is None else text_length(blocks)
        text: str | None = None
        next_offset: int | None = None
        if include_text and blocks is not None and length is not None:
            if offset > length:
                raise RequestError(ErrorCode.INVALID_ARGUMENT, "offset이 전문의 길이를 넘는다")
            text, next_offset = text_window(blocks, offset, window_size)
        return DocumentView(
            document=document,
            source=source.name,
            group=group.name,
            chunk_counts=await _chunk_counts(transaction, document, visible),
            text_length=length,
            text=text,
            next_offset=next_offset,
        )


async def list_knowledge_bases(
    unit_of_work: UnitOfWork, *, allowed_knowledge_base_ids: tuple[UUID, ...]
) -> list[KnowledgeBaseView]:
    async with unit_of_work.begin() as transaction:
        return [
            KnowledgeBaseView(
                knowledge_base,
                await transaction.documents.count_live_documents(knowledge_base.id),
            )
            for knowledge_base in await transaction.catalog.list_knowledge_bases()
            if is_in_scope(allowed_knowledge_base_ids, knowledge_base.id)
        ]


def _not_found() -> RequestError:
    return RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "문서를 찾을 수 없다")


async def _chunk_counts(
    transaction: Transaction, document: Document, knowledge_bases: list[KnowledgeBase]
) -> dict[str, int]:
    """지식베이스마다 현재 판의 조각 수다. 현재 판이 없는 지식베이스는 0이다."""
    counts: dict[str, int] = {}
    for knowledge_base in knowledge_bases:
        version_id = knowledge_base.current_index_version_id
        counts[knowledge_base.name] = (
            0
            if version_id is None
            else await transaction.index.count_chunks(document.id, version_id)
        )
    return counts


async def _parsed_blocks(transaction: Transaction, document: Document) -> tuple[Block, ...] | None:
    """문서의 지금 내용으로 파싱한 결과의 블록. 파싱 결과가 없거나 다른 내용의 것이면 `None`이다."""
    content = await transaction.documents.get_content(document.id)
    if content is None or content.parsed_content_hash != document.content_hash:
        return None
    return content.blocks
