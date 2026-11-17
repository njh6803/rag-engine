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
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
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
    CandidateScan,
    Chunk,
    ChunkLocation,
    DiagnosedHit,
    Document,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    SearchCandidates,
    SearchDiagnosis,
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


@dataclass(frozen=True, slots=True)
class _CandidateParts:
    """`search_sql`과 `diagnosis_sql`이 함께 쓰는 뼈대. 벡터 쪽과 키워드 쪽의 CTE, 둘을 잇는 글,
    조각 id와 RRF 점수와 키워드 순위를 내는 식이다. 두 문장이 다른 곳은 합친 뒤의 자르기와 마지막
    `SELECT`뿐이다(명세 "진단용 검색과 단계")."""

    ctes: list[str]
    joined: str
    chunk_id: str
    score: str
    keyword_rank: str


def _candidate_parts(query: SearchQuery) -> _CandidateParts:
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
    if not query.keywords:
        return _CandidateParts(
            ctes=ctes,
            joined="vec",
            chunk_id="vec.id",
            score=f"1.0 / ({_RRF_RANK_CONSTANT} + vec.rank)",
            keyword_rank="CAST(NULL AS bigint)",
        )
    ctes.append(
        "kw AS (SELECT c.id,"
        " row_number() OVER (ORDER BY ts_rank_cd(c.keywords, q.query) DESC, c.id) AS rank"
        " FROM chunks c, to_tsquery('simple', :keywords) AS q(query)"
        f" WHERE c.index_version_id = '{version}' AND c.keywords @@ q.query"
        f" AND {in_groups}{filters}"
        " ORDER BY ts_rank_cd(c.keywords, q.query) DESC, c.id LIMIT :candidates)"
    )
    return _CandidateParts(
        ctes=ctes,
        joined="vec FULL OUTER JOIN kw ON vec.id = kw.id",
        chunk_id="COALESCE(vec.id, kw.id)",
        score=(
            f"COALESCE(1.0 / ({_RRF_RANK_CONSTANT} + vec.rank), 0)"
            f" + COALESCE(1.0 / ({_RRF_RANK_CONSTANT} + kw.rank), 0)"
        ),
        keyword_rank="kw.rank",
    )


def _final_select(query: SearchQuery, extra_columns: str, order_by: str) -> str:
    """합친 `fused` CTE에 조각, 문서, 원천의 칸을 붙이고 질의한 판이 현재 판인지 읽는 마지막
    `SELECT`. 후보가 없어도 `is_current`를 읽도록 한 줄은 늘 나온다."""
    return (
        f" SELECT (SELECT current_index_version_id = '{query.index_version_id}'"
        f" FROM knowledge_bases WHERE id = '{query.knowledge_base_id}') AS is_current,"
        " c.id, c.document_id, s.name AS source, d.key, d.title, c.text, c.location,"
        " c.updated_at, c.effective_date, c.access_groups, d.metadata, f.score"
        + extra_columns
        + " FROM (SELECT 1) AS one LEFT JOIN fused f ON true"
        " LEFT JOIN chunks c ON c.id = f.id"
        " LEFT JOIN documents d ON d.id = c.document_id"
        " LEFT JOIN sources s ON s.id = d.source_id"
        f" ORDER BY {order_by}"
    )


def search_sql(query: SearchQuery) -> str:
    """후보를 모으는 문장. 매개변수는 `:vector`, `:candidates`, 키워드가 있을 때의 `:keywords`다."""
    parts = _candidate_parts(query)
    fused = (
        f"fused AS (SELECT {parts.chunk_id} AS id, ({parts.score})::float8 AS score"
        f" FROM {parts.joined} ORDER BY score DESC, id LIMIT :candidates)"
    )
    return f"WITH {', '.join([*parts.ctes, fused])}" + _final_select(
        query, "", "f.score DESC NULLS LAST, c.id"
    )


def diagnosis_sql(query: SearchQuery, scan: CandidateScan) -> str:
    """진단용 문장. 벡터와 키워드 후보의 합집합을 자르지 않고 단계마다의 순위를 싣는다. 점수가 같은
    줄은 `search_sql`과 같은 규칙(조각 id 순)으로 끊어 `fused_rank`를 매긴다. 매개변수는
    `search_sql`과 같다.

    글 앞에 `scan`을 적은 주석을 붙인다. 계획을 고르는 `enable_indexscan`은 `SET LOCAL`이라 문장
    글에 나타나지 않는다. psycopg는 같은 문장을 다섯 번 넘게 돌리면 서버에 준비시키고 서버는 그 뒤
    일반 계획을 쓰는데, 일반 계획은 그 설정이 바뀌어도 다시 짜지 않는다. 두 계획이 같은 글을 쓰면
    한쪽 계획이 다른 쪽 호출에 눌러앉아 `EXACT`가 색인을 탄다(같은 연결에서 번갈아 불러 재현했다).
    주석이 다르면 서버가 다른 문장으로 준비시켜 계획이 `scan`마다 따로 굳는다."""
    parts = _candidate_parts(query)
    scored = (
        f"scored AS (SELECT {parts.chunk_id} AS id, ({parts.score})::float8 AS score,"
        f" vec.rank AS vector_rank, {parts.keyword_rank} AS keyword_rank FROM {parts.joined})"
    )
    fused = (
        "fused AS (SELECT id, score, vector_rank, keyword_rank,"
        " row_number() OVER (ORDER BY score DESC, id) AS fused_rank FROM scored)"
    )
    return (
        f"/* scan={scan.value} */ WITH {', '.join([*parts.ctes, scored, fused])}"
        + _final_select(
            query,
            ", c.ordinal, f.vector_rank, f.keyword_rank, f.fused_rank",
            "f.fused_rank NULLS LAST, c.id",
        )
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

    async def _set_local(self, name: str, value: str) -> None:
        await self._connection.execute(sa.select(sa.func.set_config(name, value, sa.true())))

    async def _apply_search_settings(self, query: SearchQuery) -> None:
        """검색 문장과 진단 문장이 함께 거는 HNSW 설정. 트랜잭션 안에서만 바꾼다."""
        # `hnsw.ef_search`의 기본 40은 후보 50개를 채우지 못한다(명세 "검색 흐름").
        await self._set_local("hnsw.ef_search", str(query.candidates))
        if query.filter.is_active:
            # 필터가 좁으면 색인 스캔이 후보 수를 채우기 전에 끝난다. 반복 스캔이 더 읽게 한다.
            await self._set_local("hnsw.iterative_scan", "relaxed_order")

    @asynccontextmanager
    async def _scan_plan(self, scan: CandidateScan) -> AsyncGenerator[None]:
        """`EXACT`이면 몸통이 도는 동안 색인 스캔을 꺼 HNSW 색인을 쓰지 않는 계획을 고르게 한다.
        `SET LOCAL`은 트랜잭션이 끝날 때까지 남으므로 몸통이 끝나면 끄기 전 값으로 되돌려, 같은
        트랜잭션에서 뒤에 부른 검색이 HNSW 계획을 쓰게 한다. 몸통에서 데이터베이스 오류가 나면
        트랜잭션이 어차피 되돌려지므로 되돌리지 않고 오류를 그대로 올린다."""
        if scan is CandidateScan.INDEX:
            yield
            return
        previous = str(
            await self._connection.scalar(sa.select(sa.func.current_setting("enable_indexscan")))
        )
        await self._set_local("enable_indexscan", "off")
        yield
        await self._set_local("enable_indexscan", previous)

    async def search_candidates(self, query: SearchQuery) -> SearchCandidates:
        await self._apply_search_settings(query)
        result = await self._connection.execute(
            sa.text(search_sql(query)), _search_parameters(query)
        )
        rows = result.mappings().all()
        is_current: bool = rows[0]["is_current"] is True
        hits = tuple(self._hit(row) for row in rows if row["id"] is not None)
        return SearchCandidates(is_current=is_current, hits=hits)

    async def diagnose_candidates(
        self, query: SearchQuery, *, scan: CandidateScan
    ) -> SearchDiagnosis:
        await self._apply_search_settings(query)
        async with self._scan_plan(scan):
            result = await self._connection.execute(
                sa.text(diagnosis_sql(query, scan)), _search_parameters(query)
            )
            rows = result.mappings().all()
        is_current: bool = rows[0]["is_current"] is True
        lines = tuple(self._diagnosed_hit(row) for row in rows if row["id"] is not None)
        return SearchDiagnosis(is_current=is_current, hits=lines)

    async def explain_diagnosis(self, query: SearchQuery, *, scan: CandidateScan) -> str:
        """진단 문장의 계획을 글로 낸다. 시험이 `scan`마다 판의 HNSW 부분 색인을 쓰는지 본다.
        `INDEX`는 작은 표에서도 색인을 고르게 `explain_search`처럼 순차 스캔을 끄고 트랜잭션이
        끝날 때까지 그대로 둔다. `EXACT`는 실제 호출과 같은 설정으로 계획을 보려고 순차 스캔을
        끄지 않는다. 그래서 `INDEX`의 계획을 본 뒤 같은 트랜잭션에서 `EXACT`의 계획을 보면 안
        된다."""
        if scan is CandidateScan.INDEX:
            await self._connection.execute(sa.text("SET LOCAL enable_seqscan = off"))
        async with self._scan_plan(scan):
            rows = await self._connection.execute(
                sa.text("EXPLAIN " + diagnosis_sql(query, scan)), _search_parameters(query)
            )
            plan = "\n".join(row[0] for row in rows)
        return plan

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

    @classmethod
    def _diagnosed_hit(cls, row: sa.RowMapping) -> DiagnosedHit:
        return DiagnosedHit(
            hit=cls._hit(row),
            ordinal=row["ordinal"],
            vector_rank=row["vector_rank"],
            keyword_rank=row["keyword_rank"],
            fused_rank=row["fused_rank"],
        )

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
