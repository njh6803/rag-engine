"""`VectorIndex` 어댑터. 판마다의 HNSW 부분 색인을 만든다(명세 "데이터 모델과 스키마").

벡터 열은 차원을 적지 않은 `vector`라서 색인은 판마다 부분 표현식 색인이다. 질의도 같은 캐스트
`embedding::vector(D)`를 써야 이 색인을 탄다. 거리는 코사인이다.

조각 쓰기, 보관, 색인 상태의 메서드는 이 어댑터에 아직 없다(`NotImplementedError`).
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from rag_engine.domain.entities import Chunk, IndexState, IndexVersion

_NOT_YET = "이 어댑터에 아직 없다"


def version_index_name(index_version_id: UUID) -> str:
    return f"ix_chunks_hnsw_{index_version_id.hex}"


class PostgresVectorIndex:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def create_version_index(self, version: IndexVersion) -> None:
        # DDL은 바인딩 값을 받지 못한다. 차원은 정수, 판은 UUID라 문자열에 바깥 글이 끼지 않는다.
        await self._connection.execute(
            sa.text(
                f'CREATE INDEX "{version_index_name(version.id)}" ON chunks'
                f" USING hnsw ((embedding::vector({version.embedding_dimensions}))"
                " vector_cosine_ops)"
                f" WHERE index_version_id = '{version.id}'"
            )
        )

    async def replace_chunks(
        self, document_id: UUID, index_version_id: UUID, chunks: Sequence[Chunk]
    ) -> None:
        raise NotImplementedError(_NOT_YET)

    async def delete_chunks(self, document_id: UUID, index_version_id: UUID | None) -> None:
        raise NotImplementedError(_NOT_YET)

    async def archive_chunks(self, document_id: UUID) -> None:
        raise NotImplementedError(_NOT_YET)

    async def get_state(self, document_id: UUID, index_version_id: UUID) -> IndexState | None:
        raise NotImplementedError(_NOT_YET)

    async def save_state(self, state: IndexState) -> None:
        raise NotImplementedError(_NOT_YET)
