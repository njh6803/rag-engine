"""`DocumentStore` 어댑터. 문서 행을 맡는다(명세 "포트 열셋과 그 값", 잠금 규칙).

문서 행은 `FOR NO KEY UPDATE`로 잠근다. `FOR UPDATE`는 재색인 시작이 색인 상태·작업 행을 넣으며
문서 행에 거는 `FOR KEY SHARE`를 막아 교착을 만든다(명세 "수집 파이프라인과 작업"의 잠금 규칙).
같은 (원천, 키)를 동시에 넣으면 두 번째 `INSERT`가 먼저 넣은 쪽의 커밋을 기다린 뒤 유일 제약
위반을 내고, 그것을 `DocumentAlreadyExistsError`로 바꿔 올린다.

파싱 결과(`get_content`, `save_content`)의 메서드는 이 어댑터에 아직 없다.
"""

from typing import Final
from uuid import UUID

import psycopg.errors
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from rag_engine.adapters.postgres import tables
from rag_engine.domain.entities import Document, DocumentContent, DocumentStatus
from rag_engine.domain.errors import DocumentAlreadyExistsError, ErrorCode

_NOT_YET: Final = "이 어댑터에 아직 없다"


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
        raise NotImplementedError(_NOT_YET)

    async def save_content(self, content: DocumentContent) -> None:
        raise NotImplementedError(_NOT_YET)

    async def _select_one(
        self, *conditions: sa.ColumnElement[bool], lock: bool = False
    ) -> Document | None:
        query = sa.select(tables.documents).where(*conditions)
        if lock:
            query = query.with_for_update(key_share=True)
        row = (await self._connection.execute(query)).mappings().one_or_none()
        return None if row is None else _document(row)
