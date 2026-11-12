"""`DocumentStore` 어댑터. 문서 행을 맡는다(명세 "포트 열셋과 그 값", 잠금 규칙).

문서 행은 `FOR NO KEY UPDATE`로 잠근다. `FOR UPDATE`는 재색인 시작이 색인 상태·작업 행을 넣으며
문서 행에 거는 `FOR KEY SHARE`를 막아 교착을 만든다(명세 "수집 파이프라인과 작업"의 잠금 규칙).
같은 (원천, 키)를 동시에 넣으면 두 번째 `INSERT`가 먼저 넣은 쪽의 커밋을 기다린 뒤 유일 제약
위반을 내고, 그것을 `DocumentAlreadyExistsError`로 바꿔 올린다.

파싱 결과(문서마다 한 행)는 `save_content`가 덮어쓰고 `get_content`가 읽는다.
"""

from typing import Final
from uuid import UUID

import psycopg.errors
import sqlalchemy as sa
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from rag_engine.adapters.postgres import tables
from rag_engine.domain.entities import (
    Block,
    BlockKind,
    Document,
    DocumentContent,
    DocumentQuery,
    DocumentState,
    DocumentStatus,
)
from rag_engine.domain.errors import DocumentAlreadyExistsError, ErrorCode


class _BlockJson(BaseModel):
    """`document_contents.blocks`(jsonb)의 블록 하나. 읽고 쓰는 길이 이 모델 하나다."""

    kind: BlockKind
    text: str
    level: int | None
    page: int | None
    ordinal: int

    @staticmethod
    def of(block: Block) -> "_BlockJson":
        return _BlockJson(
            kind=block.kind,
            text=block.text,
            level=block.level,
            page=block.page,
            ordinal=block.ordinal,
        )

    def to_block(self) -> Block:
        return Block(self.kind, self.text, self.level, self.page, self.ordinal)


_BLOCK_LIST: Final = TypeAdapter(list[_BlockJson])


def _document(row: sa.RowMapping) -> Document:
    error_code: str | None = row["error_code"]
    return Document(
        id=row["id"],
        source_id=row["source_id"],
        key=row["key"],
        group_id=row["group_id"],
        title=row["title"],
        mime=row["mime"],
        size_bytes=row["size_bytes"],
        content_hash=row["content_hash"],
        blob_path=row["blob_path"],
        metadata=row["metadata"],
        updated_at=row["updated_at"],
        effective_date=row["effective_date"],
        access_groups=tuple(row["access_groups"]),
        status=DocumentStatus(row["status"]),
        error_code=None if error_code is None else ErrorCode(error_code),
        generation=row["generation"],
        deleted_at=row["deleted_at"],
        purged_at=row["purged_at"],
        created_at=row["created_at"],
        modified_at=row["modified_at"],
    )


def _mutable_values(document: Document) -> dict[str, object]:
    """고칠 수 있는 칸. 식별자, 원천 참조, 키, 만든 시각은 바뀌지 않는다."""
    return {
        "group_id": document.group_id,
        "title": document.title,
        "mime": document.mime,
        "size_bytes": document.size_bytes,
        "content_hash": document.content_hash,
        "blob_path": document.blob_path,
        "metadata": dict(document.metadata),
        "updated_at": document.updated_at,
        "effective_date": document.effective_date,
        "access_groups": list(document.access_groups),
        "status": document.status.value,
        "error_code": None if document.error_code is None else document.error_code.value,
        "generation": document.generation,
        "deleted_at": document.deleted_at,
        "purged_at": document.purged_at,
        "modified_at": document.modified_at,
    }


class PostgresDocumentStore:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get(self, document_id: UUID) -> Document | None:
        return await self._select_one(tables.documents.c.id == document_id)

    async def get_by_key(self, source_id: UUID, key: str) -> Document | None:
        return await self._select_one(
            tables.documents.c.source_id == source_id, tables.documents.c.key == key
        )

    async def lock(self, document_id: UUID) -> Document | None:
        return await self._select_one(tables.documents.c.id == document_id, lock=True)

    async def add(self, document: Document) -> None:
        values = {
            "id": document.id,
            "source_id": document.source_id,
            "key": document.key,
            "created_at": document.created_at,
            **_mutable_values(document),
        }
        try:
            await self._connection.execute(sa.insert(tables.documents).values(**values))
        except IntegrityError as error:
            if isinstance(error.orig, psycopg.errors.UniqueViolation):
                raise DocumentAlreadyExistsError("같은 원천과 키의 문서가 이미 있다") from None
            raise

    async def update(self, document: Document) -> None:
        await self._connection.execute(
            sa.update(tables.documents)
            .where(tables.documents.c.id == document.id)
            .values(**_mutable_values(document))
        )

    async def get_content(self, document_id: UUID) -> DocumentContent | None:
        contents = tables.document_contents
        row = (
            (
                await self._connection.execute(
                    sa.select(contents).where(contents.c.document_id == document_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        blocks = tuple(_BLOCK_LIST.validate_python(row["blocks"]))
        return DocumentContent(
            document_id=row["document_id"],
            parser_name=row["parser_name"],
            parser_interface_version=row["parser_interface_version"],
            parser_library_version=row["parser_library_version"],
            blocks=tuple(block.to_block() for block in blocks),
            parsed_content_hash=row["parsed_content_hash"],
            text_hash=row["text_hash"],
            parsed_at=row["parsed_at"],
        )

    async def save_content(self, content: DocumentContent) -> None:
        values = {
            "parser_name": content.parser_name,
            "parser_interface_version": content.parser_interface_version,
            "parser_library_version": content.parser_library_version,
            "blocks": [_BlockJson.of(block).model_dump(mode="json") for block in content.blocks],
            "parsed_content_hash": content.parsed_content_hash,
            "text_hash": content.text_hash,
            "parsed_at": content.parsed_at,
        }
        insertion = insert(tables.document_contents).values(
            document_id=content.document_id, **values
        )
        await self._connection.execute(
            insertion.on_conflict_do_update(index_elements=["document_id"], set_=values)
        )

    async def count_live_documents(self, knowledge_base_id: UUID) -> int:
        documents = tables.documents
        groups_of_knowledge_base = sa.select(tables.knowledge_base_groups.c.group_id).where(
            tables.knowledge_base_groups.c.knowledge_base_id == knowledge_base_id
        )
        count = await self._connection.scalar(
            sa.select(sa.func.count())
            .select_from(documents)
            .where(
                documents.c.deleted_at.is_(None), documents.c.group_id.in_(groups_of_knowledge_base)
            )
        )
        return 0 if count is None else count

    async def list_documents(self, query: DocumentQuery) -> list[Document]:
        documents = tables.documents
        statement = sa.select(documents).order_by(documents.c.id.desc()).limit(query.limit)
        if query.state is DocumentState.DELETED:
            statement = statement.where(documents.c.deleted_at.is_not(None))
        elif query.state is not None:
            statement = statement.where(
                documents.c.deleted_at.is_(None), documents.c.status == query.state.value
            )
        if query.group_id is not None:
            statement = statement.where(documents.c.group_id == query.group_id)
        if query.key is not None:
            statement = statement.where(documents.c.key == query.key)
        if query.after is not None:
            statement = statement.where(documents.c.id < query.after)
        rows = (await self._connection.execute(statement)).mappings().all()
        return [_document(row) for row in rows]

    async def _select_one(
        self, *conditions: sa.ColumnElement[bool], lock: bool = False
    ) -> Document | None:
        query = sa.select(tables.documents).where(*conditions)
        if lock:
            query = query.with_for_update(key_share=True)
        row = (await self._connection.execute(query)).mappings().one_or_none()
        return None if row is None else _document(row)
