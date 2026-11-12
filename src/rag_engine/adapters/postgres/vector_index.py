"""`VectorIndex` 어댑터. 판마다의 HNSW 부분 색인과 조각, 색인 상태, 검색 질의를 맡는다(명세 "데이터
모델과 스키마", "검색 흐름").

벡터 열은 차원을 적지 않은 `vector`라서 색인은 판마다 부분 표현식 색인이다. 질의도 같은 캐스트
`embedding::vector(D)`를 써야 이 색인을 탄다. 거리는 코사인이다.

검색 질의는 판과 차원을 문장에 리터럴로 렌더링한다. PostgreSQL 18 문서의 부분 색인 절(11.8)은 색인의
술어를 계획 시점에 맞추므로 `index_version_id = $1`처럼 매개변수인 조건은 일반 계획에서 부분 색인을
쓰지 못한다. 문장 하나에 판 하나가 들어가면 psycopg가 같은 문장을 다섯 번 넘게 돌려 서버에
준비시키고 일반 계획을 골라도 술어가 상수라 색인을 쓴다. 판 UUID와 차원은 데이터베이스가 낸 UUID와
정수라 문자열에 바깥 글이 끼지 않는다. 질의 벡터와 키워드와 후보 수는 매개변수다.

보관 표(`archived_chunks`)는 조각 표의 칸에 보관 시각만 더한 것이다. 보관(`archive_chunks`)은 문서의
조각을 보관 표로 옮기고, 되돌림(`restore_archived_chunks`)은 만든 내용 해시가 같은 보관 조각을 복사
칸을 문서의 지금 값으로 쓰며 검색 표로 복사한다.
"""

import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from typing import Final
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, JsonValue
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from rag_engine.adapters.postgres import tables
from rag_engine.domain.entities import (
    BlockKind,
    Chunk,
    ChunkLocation,
    Document,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    SearchCandidates,
    SearchFilter,
    SearchHit,
    SearchQuery,
    StoredChunk,
)
from rag_engine.domain.errors import ErrorCode

# RRF의 순위 상수(명세 "검색 흐름"). 점수는 `1/(60+순위)`의 합이다.
_RRF_RANK_CONSTANT: Final = 60
# 한 `INSERT` 문장에 넣는 조각 수. 바인딩 값이 문장당 65535개까지이고 조각 하나가 열넷쯤 쓴다.
_INSERT_BATCH_CHUNKS: Final = 1000


def version_index_name(index_version_id: UUID) -> str:
    return f"ix_chunks_hnsw_{index_version_id.hex}"


def _tsquery(tokens: Sequence[str]) -> str:
    """토큰을 따옴표로 감싸 OR로 잇는다. 따옴표 안의 `'`와 `\\`는 겹쳐 쓴다."""
    quoted = ("'" + token.replace("\\", "\\\\").replace("'", "''") + "'" for token in tokens)
    return " | ".join(quoted)


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(value) for value in vector) + "]"


def search_sql(query: SearchQuery) -> str:
    """후보를 모으는 문장. 매개변수는 `:vector`, `:candidates`, 키워드가 있을 때의 `:keywords`다."""
    version = query.index_version_id
    knowledge_base = query.knowledge_base_id
    vector_expression = f"c.embedding::vector({query.dimensions})"
    # 볼 수 없는 문서의 조각을 내지 않는 방어 조건이다. 조각에 복사한 그룹이 지식베이스의 그룹
    # 집합에 든다(원칙 V).
    in_groups = (
        "c.group_id IN (SELECT group_id FROM knowledge_base_groups"
        f" WHERE knowledge_base_id = '{knowledge_base}')"
    )
    filters = _filter_conditions(query.filter)
    ctes = [
        "vec AS (SELECT c.id,"
        f" row_number() OVER (ORDER BY {vector_expression} <=> CAST(:vector AS vector)) AS rank"
        f" FROM chunks c WHERE c.index_version_id = '{version}' AND {in_groups}{filters}"
        f" ORDER BY {vector_expression} <=> CAST(:vector AS vector) LIMIT :candidates)"
    ]
    if query.keywords:
        ctes.append(
            "kw AS (SELECT c.id,"
            " row_number() OVER (ORDER BY ts_rank_cd(c.keywords, q.query) DESC, c.id) AS rank"
            " FROM chunks c, to_tsquery('simple', :keywords) AS q(query)"
            f" WHERE c.index_version_id = '{version}' AND c.keywords @@ q.query"
            f" AND {in_groups}{filters}"
            " ORDER BY ts_rank_cd(c.keywords, q.query) DESC, c.id LIMIT :candidates)"
        )
        joined = "vec FULL OUTER JOIN kw ON vec.id = kw.id"
        chunk_id = "COALESCE(vec.id, kw.id)"
        score = (
            f"COALESCE(1.0 / ({_RRF_RANK_CONSTANT} + vec.rank), 0)"
            f" + COALESCE(1.0 / ({_RRF_RANK_CONSTANT} + kw.rank), 0)"
        )
    else:
        joined = "vec"
        chunk_id = "vec.id"
        score = f"1.0 / ({_RRF_RANK_CONSTANT} + vec.rank)"
    ctes.append(
        f"fused AS (SELECT {chunk_id} AS id, ({score})::float8 AS score FROM {joined}"
        " ORDER BY score DESC, id LIMIT :candidates)"
    )
    return (
        f"WITH {', '.join(ctes)}"
        f" SELECT (SELECT current_index_version_id = '{version}' FROM knowledge_bases"
        f" WHERE id = '{knowledge_base}') AS is_current,"
        " c.id, c.document_id, s.name AS source, d.key, d.title, c.text, c.location,"
        " c.updated_at, c.effective_date, c.access_groups, d.metadata, f.score"
        " FROM (SELECT 1) AS one LEFT JOIN fused f ON true"
        " LEFT JOIN chunks c ON c.id = f.id"
        " LEFT JOIN documents d ON d.id = c.document_id"
        " LEFT JOIN sources s ON s.id = d.source_id"
        " ORDER BY f.score DESC NULLS LAST, c.id"
    )


def _filter_conditions(search_filter: SearchFilter) -> str:
    """사용자가 주는 필터를 두 쪽의 `WHERE`에 더하는 조건. 값은 모두 매개변수이고 필터가 비면 빈
    글이다. 그룹 집합의 방어 조건은 필터가 아니라 늘 든다."""
    conditions: list[str] = []
    if search_filter.group_ids is not None:
        conditions.append("c.group_id = ANY(CAST(:group_ids AS uuid[]))")
    if search_filter.updated_after is not None:
        conditions.append("c.updated_at >= :updated_after")
    if search_filter.updated_before is not None:
        conditions.append("c.updated_at < :updated_before")
    return "".join(f" AND {condition}" for condition in conditions)


def _search_parameters(query: SearchQuery) -> dict[str, object]:
    parameters: dict[str, object] = {
        "vector": _vector_literal(query.vector),
        "candidates": query.candidates,
    }
    if query.keywords:
        parameters["keywords"] = _tsquery(query.keywords)
    search_filter = query.filter
    if search_filter.group_ids is not None:
        parameters["group_ids"] = list(search_filter.group_ids)
    if search_filter.updated_after is not None:
        parameters["updated_after"] = search_filter.updated_after
    if search_filter.updated_before is not None:
        parameters["updated_before"] = search_filter.updated_before
    return parameters


class _LocationJson(BaseModel):
    """`chunks.location`(jsonb)의 모양. 읽고 쓰는 길이 하나라 모양이 어긋나지 않는다."""

    page: int | None
    section: list[str]
    block_kind: BlockKind
    block_range: tuple[int, int]


def _location(value: object) -> ChunkLocation:
    parsed = _LocationJson.model_validate(value)
    return ChunkLocation(
        page=parsed.page,
        section=tuple(parsed.section),
        block_kind=parsed.block_kind,
        block_range=parsed.block_range,
    )


def _location_json(location: ChunkLocation) -> dict[str, JsonValue]:
    return _LocationJson(
        page=location.page,
        section=list(location.section),
        block_kind=location.block_kind,
        block_range=location.block_range,
    ).model_dump(mode="json")


def _chunk_row(chunk: Chunk) -> dict[str, object]:
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "index_version_id": chunk.index_version_id,
        "ordinal": chunk.ordinal,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "location": _location_json(chunk.location),
        "embedding": list(chunk.embedding),
        "keywords": sa.func.to_tsvector(
            sa.literal_column("'simple'"), sa.cast(chunk.keyword_text, sa.Text)
        ),
        "source_content_hash": chunk.source_content_hash,
        "group_id": chunk.group_id,
        "updated_at": chunk.updated_at,
        "effective_date": chunk.effective_date,
        "access_groups": list(chunk.access_groups),
    }


def _sql_literal(value: object) -> str:
    """일반 계획을 보는 시험용 문장에 매개변수 값을 박는다. 값은 이 모듈이 만든 글과 정수뿐이다."""
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


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
        await self.delete_chunks(document_id, index_version_id)
        if not chunks:
            return
        # 키워드 칸은 SQL 함수 식이라 행마다 값을 나르는 `executemany`가 아니라 여러 행 `VALUES`로
        # 넣는다. 한 문장의 바인딩 값은 65535개까지이고 조각 하나가 열넷쯤 쓰므로 묶음으로 나눠
        # 넣는다. 같은 작업 단위 안이라 문서 단위 원자 교체는 그대로다.
        for start in range(0, len(chunks), _INSERT_BATCH_CHUNKS):
            await self._connection.execute(
                sa.insert(tables.chunks).values(
                    [_chunk_row(chunk) for chunk in chunks[start : start + _INSERT_BATCH_CHUNKS]]
                )
            )

    async def update_chunk_copies(self, document: Document) -> None:
        await self._connection.execute(
            sa.update(tables.chunks)
            .where(tables.chunks.c.document_id == document.id)
            .values(
                group_id=document.group_id,
                updated_at=document.updated_at,
                effective_date=document.effective_date,
                access_groups=list(document.access_groups),
            )
        )

    async def delete_chunks(self, document_id: UUID, index_version_id: UUID | None) -> None:
        conditions = [tables.chunks.c.document_id == document_id]
        if index_version_id is not None:
            conditions.append(tables.chunks.c.index_version_id == index_version_id)
        await self._connection.execute(sa.delete(tables.chunks).where(*conditions))

    async def archive_chunks(self, document_id: UUID, archived_at: datetime) -> None:
        # 보관 표는 조각 표의 칸에 보관 시각만 더한 것이라 칸 이름이 같다.
        names = [column.name for column in tables.chunks.c]
        stamp = sa.cast(sa.literal(archived_at), tables.archived_chunks.c.archived_at.type)
        await self._connection.execute(
            sa.insert(tables.archived_chunks).from_select(
                [*names, "archived_at"],
                sa.select(*(tables.chunks.c[name] for name in names), stamp).where(
                    tables.chunks.c.document_id == document_id
                ),
            )
        )
        await self.delete_chunks(document_id, None)

    async def restore_archived_chunks(
        self, document: Document, index_version_ids: Sequence[UUID]
    ) -> dict[UUID, int]:
        archived = tables.archived_chunks
        copies: dict[str, object] = {
            "group_id": document.group_id,
            "updated_at": document.updated_at,
            "effective_date": document.effective_date,
            "access_groups": list(document.access_groups),
        }
        names = [column.name for column in tables.chunks.c]
        # 복사 칸은 문서 행의 지금 값이다. 값이 비었을 수 있어 칸의 형으로 캐스트해야
        # `INSERT … SELECT`가 형을 정한다.
        selected = [
            sa.cast(sa.literal(copies[name]), tables.chunks.c[name].type)
            if name in copies
            else archived.c[name]
            for name in names
        ]
        result = await self._connection.execute(
            sa.insert(tables.chunks)
            .from_select(
                names,
                sa.select(*selected).where(
                    archived.c.document_id == document.id,
                    archived.c.index_version_id.in_(index_version_ids),
                    archived.c.source_content_hash == document.content_hash,
                ),
            )
            .returning(tables.chunks.c.index_version_id)
        )
        return dict(Counter(row[0] for row in result))

    async def delete_archived_chunks(self, document_id: UUID) -> None:
        await self._connection.execute(
            sa.delete(tables.archived_chunks).where(
                tables.archived_chunks.c.document_id == document_id
            )
        )

    async def count_chunks(self, document_id: UUID, index_version_id: UUID) -> int:
        chunks = tables.chunks
        count = await self._connection.scalar(
            sa.select(sa.func.count()).where(
                chunks.c.document_id == document_id, chunks.c.index_version_id == index_version_id
            )
        )
        return 0 if count is None else count

    async def list_chunks(self, document_id: UUID, index_version_id: UUID) -> list[StoredChunk]:
        chunks = tables.chunks
        rows = (
            (
                await self._connection.execute(
                    sa.select(chunks)
                    .where(
                        chunks.c.document_id == document_id,
                        chunks.c.index_version_id == index_version_id,
                    )
                    .order_by(chunks.c.ordinal)
                )
            )
            .mappings()
            .all()
        )
        return [
            StoredChunk(
                ordinal=row["ordinal"],
                text=row["text"],
                token_count=row["token_count"],
                location=_location(row["location"]),
                embedding=tuple(float(value) for value in row["embedding"]),
                source_content_hash=row["source_content_hash"],
            )
            for row in rows
        ]

    async def count_states(self, index_version_id: UUID) -> dict[IndexStateStatus, int]:
        states = tables.document_index_states
        rows = await self._connection.execute(
            sa.select(states.c.status, sa.func.count())
            .where(states.c.index_version_id == index_version_id)
            .group_by(states.c.status)
        )
        return {IndexStateStatus(status): count for status, count in rows}

    async def create_pending_states(
        self, index_version_id: UUID, document_ids: Sequence[UUID], now: datetime
    ) -> None:
        if not document_ids:
            return
        await self._connection.execute(
            insert(tables.document_index_states),
            [
                {
                    "document_id": document_id,
                    "index_version_id": index_version_id,
                    "status": IndexStateStatus.PENDING.value,
                    "chunk_count": 0,
                    "built_content_hash": None,
                    "error_code": None,
                    "updated_at": now,
                }
                for document_id in document_ids
            ],
        )

    async def get_state(self, document_id: UUID, index_version_id: UUID) -> IndexState | None:
        states = tables.document_index_states
        row = (
            (
                await self._connection.execute(
                    sa.select(states).where(
                        states.c.document_id == document_id,
                        states.c.index_version_id == index_version_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        error_code: str | None = row["error_code"]
        return IndexState(
            document_id=row["document_id"],
            index_version_id=row["index_version_id"],
            status=IndexStateStatus(row["status"]),
            chunk_count=row["chunk_count"],
            built_content_hash=row["built_content_hash"],
            error_code=None if error_code is None else ErrorCode(error_code),
            updated_at=row["updated_at"],
        )

    async def save_state(self, state: IndexState) -> None:
        values = {
            "status": state.status.value,
            "chunk_count": state.chunk_count,
            "built_content_hash": state.built_content_hash,
            "error_code": None if state.error_code is None else state.error_code.value,
            "updated_at": state.updated_at,
        }
        insertion = insert(tables.document_index_states).values(
            document_id=state.document_id, index_version_id=state.index_version_id, **values
        )
        await self._connection.execute(
            insertion.on_conflict_do_update(
                index_elements=["document_id", "index_version_id"], set_=values
            )
        )

    async def delete_state(self, document_id: UUID, index_version_id: UUID) -> None:
        states = tables.document_index_states
        await self._connection.execute(
            sa.delete(states).where(
                states.c.document_id == document_id, states.c.index_version_id == index_version_id
            )
        )

    async def delete_states(self, document_id: UUID) -> None:
        states = tables.document_index_states
        await self._connection.execute(sa.delete(states).where(states.c.document_id == document_id))

    async def search_candidates(self, query: SearchQuery) -> SearchCandidates:
        # `hnsw.ef_search`의 기본 40은 후보 50개를 채우지 못한다(명세 "검색 흐름"). 트랜잭션
        # 안에서만 바꾼다.
        await self._connection.execute(
            sa.select(sa.func.set_config("hnsw.ef_search", str(query.candidates), sa.true()))
        )
        if query.filter.is_active:
            # 필터가 좁으면 색인 스캔이 후보 수를 채우기 전에 끝난다. 반복 스캔이 더 읽게 한다.
            await self._connection.execute(
                sa.select(sa.func.set_config("hnsw.iterative_scan", "relaxed_order", sa.true()))
            )
        result = await self._connection.execute(
            sa.text(search_sql(query)), _search_parameters(query)
        )
        rows = result.mappings().all()
        is_current: bool = rows[0]["is_current"] is True
        hits = tuple(self._hit(row) for row in rows if row["id"] is not None)
        return SearchCandidates(is_current=is_current, hits=hits)

    async def explain_search(self, query: SearchQuery) -> str:
        """검색 문장의 계획을 글로 낸다. 시험이 판의 HNSW 부분 색인을 쓰는지 본다. 작은 표에서도
        색인을 고르게 순차 스캔을 끈다."""
        await self._connection.execute(sa.text("SET LOCAL enable_seqscan = off"))
        rows = await self._connection.execute(
            sa.text("EXPLAIN " + search_sql(query)), _search_parameters(query)
        )
        return "\n".join(row[0] for row in rows)

    async def explain_search_generic(self, query: SearchQuery) -> str:
        """`explain_search`와 같되 매개변수를 모르는 일반 계획이다. 같은 문장을 다섯 번 넘게 돌려
        서버가 준비시킨 뒤에 고르는 계획이 이것이다."""
        await self._connection.execute(sa.text("SET LOCAL enable_seqscan = off"))
        parameters = _search_parameters(query)
        types = {"vector": "text", "candidates": "int", "keywords": "text"}
        statement = search_sql(query)
        for position, name in enumerate(parameters, start=1):
            statement = re.sub(rf"(?<!:):{name}\b", f"${position}", statement)
        await self._connection.execute(sa.text("SET LOCAL plan_cache_mode = force_generic_plan"))
        declared = ", ".join(types[name] for name in parameters)
        await self._connection.execute(
            sa.text(f"PREPARE explain_search({declared}) AS {statement}")
        )
        arguments = ", ".join(_sql_literal(value) for value in parameters.values())
        rows = await self._connection.execute(
            sa.text(f"EXPLAIN EXECUTE explain_search({arguments})")
        )
        return "\n".join(row[0] for row in rows)

    @staticmethod
    def _hit(row: sa.RowMapping) -> SearchHit:
        return SearchHit(
            chunk_id=row["id"],
            document_id=row["document_id"],
            source=row["source"],
            key=row["key"],
            title=row["title"],
            text=row["text"],
            location=_location(row["location"]),
            updated_at=row["updated_at"],
            effective_date=row["effective_date"],
            access_groups=tuple(row["access_groups"]),
            metadata=row["metadata"],
            rrf_score=row["score"],
        )
