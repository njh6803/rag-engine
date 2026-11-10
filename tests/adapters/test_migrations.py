"""alembic 첫 판이 색인 형식을 만든다(명세 "데이터 모델과 스키마").

`upgrade_to_head`는 자기 이벤트 루프를 열어 도므로 이 시험들은 동기 함수다. 제약은 위반하는 행을
실제로 넣어 보는 것으로 확인한다.
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import psycopg
import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from psycopg import errors, sql
from psycopg.types.json import Jsonb

from rag_engine.adapters.postgres.migrate import async_database_url, upgrade_to_head
from rag_engine.adapters.postgres.tables import metadata
from rag_engine.domain.identifiers import new_id

EXPECTED_TABLES = {
    "sources",
    "groups",
    "knowledge_bases",
    "knowledge_base_groups",
    "index_versions",
    "documents",
    "document_contents",
    "document_index_states",
    "chunks",
    "archived_chunks",
    "jobs",
    "tokens",
}

NOW = datetime(2026, 11, 10, 9, 30, tzinfo=UTC)


@pytest.fixture
def migrated_url(empty_database_url: str) -> str:
    upgrade_to_head(empty_database_url)
    return empty_database_url


def _connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=True)


def _insert(connection: psycopg.Connection, table: str, **values: object) -> UUID:
    """행 하나를 넣고 식별자를 돌려준다. 식별자는 UUIDv7이고 파이썬에서 만든다."""
    row = {"id": new_id(), **values}
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in row),
        sql.SQL(", ").join(sql.Placeholder() for _ in row),
    )
    connection.execute(query, list(row.values()))
    identifier = row["id"]
    assert isinstance(identifier, UUID)
    return identifier


def _knowledge_base(connection: psycopg.Connection, name: str, *, is_default: bool) -> UUID:
    return _insert(
        connection,
        "knowledge_bases",
        name=name,
        embedding_endpoint="http://tei:80",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        chunking_strategy="structure_first",
        chunk_tokens=512,
        chunk_overlap_tokens=64,
        is_default=is_default,
    )


def _index_version(connection: psycopg.Connection, knowledge_base_id: UUID) -> UUID:
    return _insert(
        connection,
        "index_versions",
        knowledge_base_id=knowledge_base_id,
        schema_version=1,
        embedding_endpoint="http://tei:80",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        chunking_config=Jsonb({"strategy": "structure_first"}),
        chunking_hash="h",
        tokenizer_version="t",
        status="current",
        created_at=NOW,
    )


def _source(connection: psycopg.Connection, source_name: str = "default") -> UUID:
    return _insert(connection, "sources", name=source_name, kind="push")


def _group(connection: psycopg.Connection) -> UUID:
    return _insert(connection, "groups", name=f"group-{new_id()}")


def _document(
    connection: psycopg.Connection, source_id: UUID, group_id: UUID, key: str = "a.pdf"
) -> UUID:
    return _insert(
        connection,
        "documents",
        source_id=source_id,
        key=key,
        group_id=group_id,
        title="제목",
        mime="application/pdf",
        size_bytes=10,
        content_hash="h",
        blob_path="blobs/x",
        updated_at=NOW,
        status="received",
        generation=1,
        created_at=NOW,
        modified_at=NOW,
    )


def _job(connection: psycopg.Connection, document_id: UUID, status: str) -> UUID:
    return _insert(
        connection,
        "jobs",
        kind="index_document",
        document_id=document_id,
        status=status,
        run_after=NOW,
        request_id=new_id(),
        created_at=NOW,
    )


def _chunk(
    connection: psycopg.Connection,
    document_id: UUID,
    index_version_id: UUID,
    group_id: UUID,
    *,
    ordinal: int,
    embedding: str,
) -> None:
    connection.execute(
        "INSERT INTO chunks (id, document_id, index_version_id, ordinal, text, token_count,"
        " location, embedding, keywords, source_content_hash, group_id, updated_at)"
        " VALUES (%s, %s, %s, %s, '글', 1, %s, %s::vector, to_tsvector('simple', '글'), 'h',"
        " %s, %s)",
        [new_id(), document_id, index_version_id, ordinal, Jsonb({}), embedding, group_id, NOW],
    )


def test_첫_판은_표_열둘과_alembic_판_표를_만든다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
        version = connection.execute("SELECT version_num FROM alembic_version").fetchall()

    assert {name for (name,) in rows} == EXPECTED_TABLES | {"alembic_version"}
    assert version == [("0001",)]


def test_이미_오른_데이터베이스에_다시_올려도_오류가_없다(migrated_url: str) -> None:
    upgrade_to_head(migrated_url)

    with _connect(migrated_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("0001",)
        ]


def test_같은_원천에_같은_키의_문서는_둘_수_없다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _source(connection)
        group_id = _group(connection)
        _document(connection, source_id, group_id, key="a.pdf")

        with pytest.raises(errors.UniqueViolation) as caught:
            _document(connection, source_id, group_id, key="a.pdf")

    assert caught.value.diag.constraint_name == "uq_documents_source_id_key"


def test_다른_원천이면_같은_키를_쓸_수_있다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        first = _source(connection, "one")
        second = _source(connection, "two")
        group_id = _group(connection)

        _document(connection, first, group_id, key="a.pdf")
        _document(connection, second, group_id, key="a.pdf")


def test_기본_지식베이스는_하나뿐이고_기본이_아닌_지식베이스는_여럿이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        _knowledge_base(connection, "default", is_default=True)
        _knowledge_base(connection, "other-1", is_default=False)
        _knowledge_base(connection, "other-2", is_default=False)

        with pytest.raises(errors.UniqueViolation) as caught:
            _knowledge_base(connection, "second-default", is_default=True)

    assert caught.value.diag.constraint_name == "uq_knowledge_bases_is_default"


def test_같은_문서의_대기_작업은_하나뿐이고_실행_중_작업은_함께_둘_수_있다(
    migrated_url: str,
) -> None:
    with _connect(migrated_url) as connection:
        document_id = _document(connection, _source(connection), _group(connection))
        _job(connection, document_id, "queued")
        _job(connection, document_id, "running")
        _job(connection, document_id, "succeeded")

        with pytest.raises(errors.UniqueViolation) as caught:
            _job(connection, document_id, "queued")

    assert caught.value.diag.constraint_name == "uq_jobs_document_id_queued"


def test_작업의_종류와_상태는_정해진_값만_받는다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        document_id = _document(connection, _source(connection), _group(connection))

        with pytest.raises(errors.CheckViolation) as caught:
            _job(connection, document_id, "paused")

    assert caught.value.diag.constraint_name == "ck_jobs_status"


def test_문서의_메타데이터는_JSON_객체여야_한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _source(connection)
        group_id = _group(connection)

        with pytest.raises(errors.CheckViolation) as caught:
            connection.execute(
                "UPDATE documents SET metadata = '[1]'::jsonb WHERE id = %s",
                [_document(connection, source_id, group_id)],
            )

    assert caught.value.diag.constraint_name == "ck_documents_metadata_is_object"


def test_같은_색인_판의_같은_문서에_같은_순번의_조각은_둘_수_없다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        document_id = _document(connection, _source(connection), _group(connection))
        group_id = _group(connection)
        version_id = _index_version(connection, _knowledge_base(connection, "kb", is_default=True))
        _chunk(connection, document_id, version_id, group_id, ordinal=0, embedding="[1,2,3]")
        _chunk(connection, document_id, version_id, group_id, ordinal=1, embedding="[1,2,3]")

        with pytest.raises(errors.UniqueViolation) as caught:
            _chunk(connection, document_id, version_id, group_id, ordinal=0, embedding="[1,2,3]")

    assert caught.value.diag.constraint_name == "uq_chunks_index_version_id_document_id_ordinal"


def test_벡터_열은_차원을_적지_않아_다른_차원의_벡터를_함께_담는다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        document_id = _document(connection, _source(connection), _group(connection))
        group_id = _group(connection)
        version_id = _index_version(connection, _knowledge_base(connection, "kb", is_default=True))

        _chunk(connection, document_id, version_id, group_id, ordinal=0, embedding="[1,2,3]")
        _chunk(connection, document_id, version_id, group_id, ordinal=1, embedding="[1,2,3,4,5]")

        dimensions = connection.execute(
            "SELECT vector_dims(embedding) FROM chunks ORDER BY ordinal"
        ).fetchall()
    assert dimensions == [(3,), (5,)]


def test_지식베이스의_현재_판_참조는_실제_색인_판을_가리켜야_한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        knowledge_base_id = _knowledge_base(connection, "kb", is_default=True)
        version_id = _index_version(connection, knowledge_base_id)

        connection.execute(
            "UPDATE knowledge_bases SET current_index_version_id = %s WHERE id = %s",
            [version_id, knowledge_base_id],
        )
        with pytest.raises(errors.ForeignKeyViolation) as caught:
            connection.execute(
                "UPDATE knowledge_bases SET current_index_version_id = %s WHERE id = %s",
                [new_id(), knowledge_base_id],
            )

    assert (
        caught.value.diag.constraint_name
        == "fk_knowledge_bases_current_index_version_id_index_versions"
    )


def test_키워드의_GIN_색인은_조각_표_전체에_하나이고_HNSW_색인은_만들지_않는다(
    migrated_url: str,
) -> None:
    with _connect(migrated_url) as connection:
        definitions = {
            (table, name): definition
            for table, name, definition in connection.execute(
                "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'"
            ).fetchall()
        }

    gin = [key for key, definition in definitions.items() if "USING gin" in definition]
    assert gin == [("chunks", "ix_chunks_keywords")]
    assert [key for key, definition in definitions.items() if "hnsw" in definition] == []
    assert sorted(key for key in definitions if key[0] == "archived_chunks") == [
        ("archived_chunks", "ix_archived_chunks_document_id"),
        ("archived_chunks", "pk_archived_chunks"),
    ]


def test_이름_규칙이_제약과_색인_이름을_정한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        names = {
            name
            for (name,) in connection.execute(
                "SELECT conname FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
            ).fetchall()
        }

    assert {
        "pk_documents",
        "uq_documents_source_id_key",
        "fk_documents_source_id_sources",
        "ck_documents_status",
        "uq_chunks_index_version_id_document_id_ordinal",
        "fk_knowledge_bases_current_index_version_id_index_versions",
    } <= names


def test_표_정의가_마이그레이션이_만든_표와_어긋나지_않는다(migrated_url: str) -> None:
    engine = sa.create_engine(async_database_url(migrated_url))
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": False})
            differences = compare_metadata(context, metadata)
    finally:
        engine.dispose()

    assert differences == []


async def test_실행_중인_이벤트_루프_안에서는_부를_수_없고_스레드로_넘기면_오른다(
    empty_database_url: str,
) -> None:
    with pytest.raises(RuntimeError, match="asyncio.to_thread로 부른다"):
        upgrade_to_head(empty_database_url)

    await asyncio.to_thread(upgrade_to_head, empty_database_url)

    with _connect(empty_database_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("0001",)
        ]


def test_접속_문자열의_스킴을_비동기_엔진용으로_바꾼다() -> None:
    assert (
        async_database_url("postgresql://u:p%40ss@127.0.0.1:55432/db")
        == "postgresql+psycopg://u:p%40ss@127.0.0.1:55432/db"
    )


def test_postgresql이_아닌_스킴은_거부한다() -> None:
    with pytest.raises(ValueError, match="postgresql:// 로 시작해야 한다"):
        async_database_url("postgresql+psycopg://u:p@h/db")
