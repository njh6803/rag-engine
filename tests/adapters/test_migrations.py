"""alembic 판이 색인 형식을 만든다(명세 "데이터 모델과 스키마", source-sync 명세 "데이터 모델과
스키마").

`upgrade_to_head`는 자기 이벤트 루프를 열어 도므로 이 시험들은 동기 함수다. 제약은 위반하는 행을
실제로 넣어 보는 것으로 확인한다.
"""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from psycopg import errors, sql
from psycopg.types.json import Jsonb
from sqlalchemy.exc import IntegrityError

from rag_engine.adapters.postgres.migrate import (
    MIGRATIONS_DIRECTORY,
    async_database_url,
    upgrade_to_head,
)
from rag_engine.adapters.postgres.tables import metadata
from rag_engine.domain.identifiers import new_id

# 0003까지의 표 열둘.
CORE_TABLES = {
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
# 0004가 동기화 기록 표를 더한다.
EXPECTED_TABLES = CORE_TABLES | {"sync_records"}

# 마이그레이션 판을 더하면 이 값이 마지막 판을 따라간다.
HEAD_REVISION = "0004"

NOW = datetime(2026, 11, 10, 9, 30, tzinfo=UTC)


@pytest.fixture
def migrated_url(empty_database_url: str) -> str:
    upgrade_to_head(empty_database_url)
    return empty_database_url


def _connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=True)


def _alembic(url: str, action: Literal["upgrade", "downgrade"], revision: str) -> None:
    """`upgrade_to_head`가 쓰는 설정으로 판 하나를 올리거나 내린다. 판을 지정해 옛 스키마에 데이터를
    만들어 두는 시험이 쓴다."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    config.attributes["url"] = async_database_url(url)
    if action == "upgrade":
        command.upgrade(config, revision)
    else:
        command.downgrade(config, revision)


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
    connection: psycopg.Connection,
    source_id: UUID,
    group_id: UUID,
    key: str = "a.pdf",
    **overrides: object,
) -> UUID:
    values: dict[str, object] = {
        "source_id": source_id,
        "key": key,
        "group_id": group_id,
        "title": "제목",
        "mime": "application/pdf",
        "size_bytes": 10,
        "content_hash": "h",
        "blob_path": "blobs/x",
        "updated_at": NOW,
        "status": "received",
        "generation": 1,
        "created_at": NOW,
        "modified_at": NOW,
    }
    values.update(overrides)
    return _insert(connection, "documents", **values)


def _job(connection: psycopg.Connection, document_id: UUID, status: str) -> UUID:
    return _job_row(connection, "index_document", status, document_id=document_id)


def _job_row(
    connection: psycopg.Connection,
    kind: str,
    status: str = "queued",
    *,
    document_id: UUID | None = None,
    source_id: UUID | None = None,
    **overrides: object,
) -> UUID:
    values: dict[str, object] = {
        "kind": kind,
        "document_id": document_id,
        "source_id": source_id,
        "status": status,
        "run_after": NOW,
        "request_id": new_id(),
        "created_at": NOW,
    }
    values.update(overrides)
    return _insert(connection, "jobs", **values)


def _pull_source(connection: psycopg.Connection, **overrides: object) -> UUID:
    values: dict[str, object] = {
        "name": "docs",
        "kind": "pull",
        "connector": "server_path",
        "config": Jsonb({"folder": "a"}),
        "group_id": _group(connection),
    }
    values.update(overrides)
    return _insert(connection, "sources", **values)


def _sync_record(connection: psycopg.Connection, source_id: UUID, **overrides: object) -> UUID:
    values: dict[str, object] = {
        "source_id": source_id,
        "trigger": "manual",
        "status": "queued",
        "created_at": NOW,
    }
    values.update(overrides)
    return _insert(connection, "sync_records", **values)


def _constraint_name(caught: pytest.ExceptionInfo[errors.IntegrityError]) -> str | None:
    return caught.value.diag.constraint_name


def _columns(connection: psycopg.Connection, table: str) -> Mapping[str, tuple[str, str]]:
    """칸 이름에서 (널 허용, 기본값 식)으로 가는 표."""
    rows = connection.execute(
        "SELECT column_name, is_nullable, column_default FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s",
        [table],
    ).fetchall()
    return {name: (nullable, default) for name, nullable, default in rows}


def _index_definition(connection: psycopg.Connection, name: str) -> str:
    row = connection.execute(
        "SELECT indexdef FROM pg_indexes WHERE indexname = %s", [name]
    ).fetchone()
    assert row is not None, f"{name} 색인이 없다"
    definition: str = row[0]
    return definition


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


def test_판을_모두_올리면_표_열셋과_alembic_판_표를_만든다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
        version = connection.execute("SELECT version_num FROM alembic_version").fetchall()

    assert {name for (name,) in rows} == EXPECTED_TABLES | {"alembic_version"}
    assert version == [(HEAD_REVISION,)]


def test_이미_오른_데이터베이스에_다시_올려도_오류가_없다(migrated_url: str) -> None:
    upgrade_to_head(migrated_url)

    with _connect(migrated_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (HEAD_REVISION,)
        ]


def test_작업_표는_문서별_진행_중_작업만_담는_부분_색인을_가진다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        definition = connection.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_jobs_document_id_active'"
        ).fetchone()

    assert definition is not None, "ix_jobs_document_id_active 색인이 없다"
    assert "(document_id)" in definition[0], f"색인 열이 document_id가 아니다: {definition[0]}"
    assert "queued" in definition[0] and "running" in definition[0], (
        f"술어가 대기·실행 중 작업이 아니다: {definition[0]}"
    )
    assert "succeeded" not in definition[0], f"끝난 작업까지 담는다: {definition[0]}"


def test_지식베이스의_최소_점수_칸은_널을_허용하고_안_주면_널이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        _knowledge_base(connection, "kb", is_default=True)
        column = connection.execute(
            "SELECT is_nullable, data_type FROM information_schema.columns"
            " WHERE table_name = 'knowledge_bases' AND column_name = 'min_score'"
        ).fetchone()
        stored = connection.execute("SELECT min_score FROM knowledge_bases").fetchall()

    assert column == ("YES", "double precision")
    assert stored == [(None,)]


@pytest.mark.parametrize("value", [0.0, 0.3, 1.0])
def test_최소_점수는_0_이상_1_이하의_값을_받는다(migrated_url: str, value: float) -> None:
    with _connect(migrated_url) as connection:
        _knowledge_base(connection, "kb", is_default=True)
        connection.execute("UPDATE knowledge_bases SET min_score = %s", [value])
        stored = connection.execute("SELECT min_score FROM knowledge_bases").fetchall()

    assert stored == [(value,)]


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_최소_점수가_범위_밖이거나_유한하지_않으면_제약이_막는다(
    migrated_url: str, value: float
) -> None:
    with _connect(migrated_url) as connection:
        _knowledge_base(connection, "kb", is_default=True)

        with pytest.raises(errors.CheckViolation) as caught:
            connection.execute("UPDATE knowledge_bases SET min_score = %s", [value])

    assert caught.value.diag.constraint_name == "ck_knowledge_bases_min_score_in_unit_range"


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


_PUSH_ONLY_EMPTY_COLUMNS = (
    "connector",
    "config",
    "group_id",
    "schedule",
    "next_run_at",
    "paused",
    "exclude_patterns",
)


def _value_for_push_column(connection: psycopg.Connection, column: str) -> object:
    values: dict[str, object] = {
        "connector": "server_path",
        "config": Jsonb({}),
        "group_id": _group(connection),
        "schedule": "0 2 * * *",
        "next_run_at": NOW,
        "paused": True,
        "exclude_patterns": ["~$*"],
    }
    return values[column]


def test_원천의_갈래는_밀어_넣기와_가져오기_둘이고_그_밖의_값은_거부한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        _pull_source(connection)
        with pytest.raises(errors.CheckViolation) as caught:
            _insert(connection, "sources", name="other", kind="mirror")

    assert _constraint_name(caught) == "ck_sources_kind"


@pytest.mark.parametrize("column", _PUSH_ONLY_EMPTY_COLUMNS)
def test_밀어_넣는_원천은_가져오는_원천의_칸_일곱이_비어_있어야_한다(
    migrated_url: str, column: str
) -> None:
    with _connect(migrated_url) as connection:
        value = _value_for_push_column(connection, column)

        with pytest.raises(errors.CheckViolation) as caught:
            _insert(connection, "sources", name="up", kind="push", **{column: value})

    assert _constraint_name(caught) == "ck_sources_push_columns_empty"


def test_밀어_넣는_원천은_칸을_주지_않으면_일시_중지가_거짓이고_제외_패턴이_빈_목록이다(
    migrated_url: str,
) -> None:
    with _connect(migrated_url) as connection:
        _insert(connection, "sources", name="up", kind="push")
        row = connection.execute("SELECT paused, exclude_patterns FROM sources").fetchone()

    assert row == (False, [])


@pytest.mark.parametrize("missing", ["connector", "group_id"])
def test_가져오는_원천은_커넥터_이름과_그룹이_있어야_한다(migrated_url: str, missing: str) -> None:
    with _connect(migrated_url) as connection:
        with pytest.raises(errors.CheckViolation) as caught:
            _pull_source(connection, **{missing: None})

    assert _constraint_name(caught) == "ck_sources_pull_columns_present"


def test_가져오는_원천의_설정은_JSON_객체여야_한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        with pytest.raises(errors.CheckViolation) as caught:
            _pull_source(connection, config=Jsonb(["a"]))

    assert _constraint_name(caught) == "ck_sources_config_is_object"


def test_가져오는_원천은_일정과_제외_패턴과_일시_중지를_들_수_있다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(
            connection,
            schedule="0 2 * * *",
            next_run_at=NOW,
            paused=True,
            exclude_patterns=["~$*", "*.tmp"],
        )
        row = connection.execute(
            "SELECT connector, schedule, paused, exclude_patterns, deleted_at FROM sources"
            " WHERE id = %s",
            [source_id],
        ).fetchone()

    assert row == ("server_path", "0 2 * * *", True, ["~$*", "*.tmp"], None)


def test_원천의_이름은_갈래와_지움_표시와_상관없이_하나뿐이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        _pull_source(connection, name="docs", deleted_at=NOW)

        with pytest.raises(errors.UniqueViolation) as caught:
            _insert(connection, "sources", name="docs", kind="push")

    assert _constraint_name(caught) == "uq_sources_name"


def test_원천의_만든_시각은_비울_수_없고_주지_않으면_지금이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        before = connection.execute("SELECT now()").fetchone()
        _insert(connection, "sources", name="up", kind="push")
        row = connection.execute("SELECT created_at FROM sources").fetchone()
        nullable = _columns(connection, "sources")["created_at"][0]

    assert before is not None
    assert row is not None
    assert row[0] >= before[0]
    assert nullable == "NO"


def test_이미_있는_원천의_만든_시각은_마이그레이션이_채운다(empty_database_url: str) -> None:
    _alembic(empty_database_url, "upgrade", "0003")
    with _connect(empty_database_url) as connection:
        _insert(connection, "sources", name="default", kind="push")
    _alembic(empty_database_url, "upgrade", "head")

    with _connect(empty_database_url) as connection:
        row = connection.execute("SELECT name, created_at IS NOT NULL FROM sources").fetchone()

    assert row == ("default", True)


@pytest.mark.parametrize("reason", ["encrypted", "no_text"])
def test_건너뜀_문서는_사유를_들고_다른_상태는_사유를_들_수_없다(
    migrated_url: str, reason: str
) -> None:
    with _connect(migrated_url) as connection:
        source_id = _source(connection)
        group_id = _group(connection)
        _document(
            connection, source_id, group_id, key="a.pdf", status="skipped", skip_reason=reason
        )

        with pytest.raises(errors.CheckViolation) as caught:
            _document(connection, source_id, group_id, key="b.pdf", skip_reason=reason)

    assert _constraint_name(caught) == "ck_documents_skip_reason"


def test_건너뜀_문서의_사유는_정해진_둘뿐이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _source(connection)
        group_id = _group(connection)

        with pytest.raises(errors.CheckViolation) as caught:
            _document(connection, source_id, group_id, status="skipped", skip_reason="empty")

    assert _constraint_name(caught) == "ck_documents_skip_reason"


def test_문서_상태는_건너뜀을_더한_넷이고_그_밖의_값은_거부한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _source(connection)
        group_id = _group(connection)
        for status in ("received", "parsed", "failed", "skipped"):
            _document(connection, source_id, group_id, key=f"{status}.pdf", status=status)

        with pytest.raises(errors.CheckViolation) as caught:
            _document(connection, source_id, group_id, key="x.pdf", status="deleted")

    assert _constraint_name(caught) == "ck_documents_status"


def test_문서의_새_칸은_변경_확인값과_사유가_비고_원천과_함께_지워졌다는_표시가_거짓이다(
    migrated_url: str,
) -> None:
    with _connect(migrated_url) as connection:
        _document(connection, _source(connection), _group(connection))
        row = connection.execute(
            "SELECT change_marker, skip_reason, deleted_with_source FROM documents"
        ).fetchone()
        columns = _columns(connection, "documents")

    assert row == (None, None, False)
    assert columns["deleted_with_source"][0] == "NO"
    assert columns["change_marker"][0] == "YES"


def test_가져오는_원천의_문서는_원본_경로가_비어_있을_수_있다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        document_id = _document(
            connection,
            _pull_source(connection),
            _group(connection),
            blob_path=None,
            change_marker="1700000000-42",
        )
        row = connection.execute(
            "SELECT blob_path, change_marker FROM documents WHERE id = %s", [document_id]
        ).fetchone()

    assert row == (None, "1700000000-42")


@pytest.mark.parametrize(
    "kind", ["index_document", "sync_source", "delete_source", "restore_source", "cleanup"]
)
def test_작업의_종류는_다섯이다(migrated_url: str, kind: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        document_id = _document(connection, _source(connection), _group(connection))
        references: dict[str, UUID | None] = {
            "index_document": document_id,
            "sync_source": source_id,
            "delete_source": source_id,
            "restore_source": source_id,
            "cleanup": None,
        }
        if kind == "index_document":
            _job_row(connection, kind, document_id=references[kind])
        else:
            _job_row(connection, kind, source_id=references[kind])

        count = connection.execute("SELECT count(*) FROM jobs WHERE kind = %s", [kind]).fetchone()

    assert count == (1,)


def test_모르는_종류의_작업은_거부한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        with pytest.raises(errors.CheckViolation) as caught:
            _job_row(connection, "reindex")

    assert _constraint_name(caught) == "ck_jobs_kind"


def test_색인_작업은_문서만_가리키고_원천을_가리키면_거부한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        document_id = _document(connection, _source(connection), _group(connection))

        with pytest.raises(errors.CheckViolation) as with_source:
            _job_row(connection, "index_document", document_id=document_id, source_id=source_id)
        with pytest.raises(errors.CheckViolation) as without_document:
            _job_row(connection, "index_document")

    assert _constraint_name(with_source) == "ck_jobs_references_match_kind"
    assert _constraint_name(without_document) == "ck_jobs_references_match_kind"


@pytest.mark.parametrize("kind", ["sync_source", "delete_source", "restore_source"])
def test_원천_단위_작업은_원천만_가리키고_문서를_가리키거나_원천이_없으면_거부한다(
    migrated_url: str, kind: str
) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        document_id = _document(connection, _source(connection), _group(connection))

        with pytest.raises(errors.CheckViolation) as with_document:
            _job_row(connection, kind, source_id=source_id, document_id=document_id)
        with pytest.raises(errors.CheckViolation) as without_source:
            _job_row(connection, kind)

    assert _constraint_name(with_document) == "ck_jobs_references_match_kind"
    assert _constraint_name(without_source) == "ck_jobs_references_match_kind"


def test_정리_작업은_원천도_문서도_가리키지_않는다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        document_id = _document(connection, _source(connection), _group(connection))

        with pytest.raises(errors.CheckViolation) as with_source:
            _job_row(connection, "cleanup", source_id=source_id)
        with pytest.raises(errors.CheckViolation) as with_document:
            _job_row(connection, "cleanup", document_id=document_id)

    assert _constraint_name(with_source) == "ck_jobs_references_match_kind"
    assert _constraint_name(with_document) == "ck_jobs_references_match_kind"


def test_작업이_가리키는_원천은_실제_원천이어야_한다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        with pytest.raises(errors.ForeignKeyViolation) as caught:
            _job_row(connection, "sync_source", source_id=new_id())

    assert _constraint_name(caught) == "fk_jobs_source_id_sources"


def test_작업의_옵션은_JSON_객체이고_주지_않으면_빈_객체다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        _job_row(connection, "sync_source", source_id=source_id, status="succeeded")
        stored = connection.execute("SELECT options FROM jobs").fetchone()

        with pytest.raises(errors.CheckViolation) as caught:
            _job_row(connection, "sync_source", source_id=source_id, options=Jsonb([1]))

    assert stored == ({},)
    assert _constraint_name(caught) == "ck_jobs_options_is_object"


def test_색인_작업의_문서_칸은_비울_수_있고_옛_부분_유일_색인은_그대로다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        columns = _columns(connection, "jobs")
        document_id = _document(connection, _source(connection), _group(connection))
        _job(connection, document_id, "queued")

        with pytest.raises(errors.UniqueViolation) as caught:
            _job(connection, document_id, "queued")

    assert columns["document_id"][0] == "YES"
    assert _constraint_name(caught) == "uq_jobs_document_id_queued"


def test_같은_원천의_같은_종류_작업은_대기_중이거나_실행_중이면_하나뿐이다(
    migrated_url: str,
) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        _job_row(connection, "sync_source", source_id=source_id, status="queued")

        with pytest.raises(errors.UniqueViolation) as queued_again:
            _job_row(connection, "sync_source", source_id=source_id, status="queued")
        with pytest.raises(errors.UniqueViolation) as running_with_queued:
            _job_row(connection, "sync_source", source_id=source_id, status="running")

    assert _constraint_name(queued_again) == "uq_jobs_source_id_kind_active"
    assert _constraint_name(running_with_queued) == "uq_jobs_source_id_kind_active"


def test_끝난_작업은_같은_원천의_같은_종류_새_작업을_막지_않는다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        _job_row(connection, "sync_source", source_id=source_id, status="succeeded")
        _job_row(connection, "sync_source", source_id=source_id, status="failed")
        _job_row(connection, "sync_source", source_id=source_id, status="running")

        with pytest.raises(errors.UniqueViolation):
            _job_row(connection, "sync_source", source_id=source_id, status="queued")


def test_다른_원천이나_다른_종류의_작업은_함께_둘_수_있다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        first = _pull_source(connection, name="first")
        second = _pull_source(connection, name="second")

        _job_row(connection, "sync_source", source_id=first)
        _job_row(connection, "sync_source", source_id=second)
        _job_row(connection, "delete_source", source_id=first)
        _job_row(connection, "restore_source", source_id=first)


def test_정리_작업은_대기_중이거나_실행_중이면_하나뿐이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        _job_row(connection, "cleanup", status="succeeded")
        _job_row(connection, "cleanup", status="queued")

        with pytest.raises(errors.UniqueViolation) as second:
            _job_row(connection, "cleanup", status="running")

    assert _constraint_name(second) == "uq_jobs_source_id_kind_active"


def test_원천이_빈_값끼리도_같은_값으로_보는_부분_유일_색인이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        definition = _index_definition(connection, "uq_jobs_source_id_kind_active")

    assert "UNIQUE" in definition
    assert "(source_id, kind)" in definition
    assert "NULLS NOT DISTINCT" in definition
    assert "document_id IS NULL" in definition
    assert "queued" in definition and "running" in definition
    assert "succeeded" not in definition


def _index_predicate(connection: psycopg.Connection, name: str) -> str:
    """부분 색인의 `WHERE` 술어만 읽는다. 색인 정의 전체의 글자를 찾으면 이름에 든 낱말과 잘못된
    비교 연산자도 맞아 버린다."""
    row = connection.execute(
        "SELECT pg_get_expr(indpred, indrelid) FROM pg_index WHERE indexrelid = to_regclass(%s)",
        [name],
    ).fetchone()
    assert row is not None, f"{name} 색인이 없다"
    predicate: str | None = row[0]
    assert predicate is not None, f"{name} 색인에 술어가 없다"
    return predicate


def test_꺼내기용_부분_색인은_색인_작업이_아닌_작업만_담는다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        definition = _index_definition(connection, "ix_jobs_not_index_document_run_after")
        predicate = _index_predicate(connection, "ix_jobs_not_index_document_run_after")

    assert "(run_after, id)" in definition
    assert "<> 'index_document'" in predicate
    assert "'queued'" in predicate
    assert "'running'" in predicate
    assert "succeeded" not in predicate


def test_동기화_기록은_목록_건수가_비어_있고_나머지_개수는_영이며_사유별_개수는_빈_객체다(
    migrated_url: str,
) -> None:
    with _connect(migrated_url) as connection:
        record_id = _sync_record(connection, _pull_source(connection))
        row = connection.execute(
            "SELECT job_id, options, listed, added, updated, deleted, unchanged, skipped,"
            " not_accepted, failed, failure_code, started_at, finished_at"
            " FROM sync_records WHERE id = %s",
            [record_id],
        ).fetchone()

    assert row == (None, {}, None, 0, 0, 0, 0, {}, {}, {}, None, None, None)


def test_동기화_기록의_상태는_다섯이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        for status in ("queued", "running", "succeeded", "failed", "not_started"):
            _sync_record(connection, source_id, status=status)

        with pytest.raises(errors.CheckViolation) as caught:
            _sync_record(connection, source_id, status="skipped")

    assert _constraint_name(caught) == "ck_sync_records_status"


def test_동기화_기록의_시작시킨_것은_일정과_손_둘이다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        _sync_record(connection, source_id, trigger="schedule")
        _sync_record(connection, source_id, trigger="manual")

        with pytest.raises(errors.CheckViolation) as caught:
            _sync_record(connection, source_id, trigger="webhook")

    assert _constraint_name(caught) == "ck_sync_records_trigger"


@pytest.mark.parametrize("column", ["options", "skipped", "not_accepted", "failed"])
def test_동기화_기록의_JSON_칸은_객체여야_한다(migrated_url: str, column: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)

        with pytest.raises(errors.CheckViolation) as caught:
            _sync_record(connection, source_id, **{column: Jsonb([1])})

    assert _constraint_name(caught) == f"ck_sync_records_{column}_is_object"


def test_동기화_기록은_실제_원천과_실제_작업만_가리킨다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        job_id = _job_row(connection, "sync_source", source_id=source_id)
        _sync_record(connection, source_id, job_id=job_id)

        with pytest.raises(errors.ForeignKeyViolation) as no_source:
            _sync_record(connection, new_id())
        with pytest.raises(errors.ForeignKeyViolation) as no_job:
            _sync_record(connection, source_id, job_id=new_id())

    assert _constraint_name(no_source) == "fk_sync_records_source_id_sources"
    assert _constraint_name(no_job) == "fk_sync_records_job_id_jobs"


def test_목록을_받았는데_0건이면_목록_건수가_영이고_받지_못했으면_비어_있다(
    migrated_url: str,
) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        empty = _sync_record(connection, source_id, listed=0)
        unlisted = _sync_record(connection, source_id)
        rows = dict(
            connection.execute(
                "SELECT id, listed FROM sync_records WHERE id IN (%s, %s)", [empty, unlisted]
            ).fetchall()
        )

    assert rows == {empty: 0, unlisted: None}


def test_작업_행을_지워도_동기화_기록은_남고_작업_칸만_빈다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        source_id = _pull_source(connection)
        job_id = _job_row(connection, "sync_source", source_id=source_id)
        record_id = _sync_record(connection, source_id, job_id=job_id)

        connection.execute("DELETE FROM jobs WHERE id = %s", [job_id])
        row = connection.execute(
            "SELECT job_id, source_id FROM sync_records WHERE id = %s", [record_id]
        ).fetchone()

    assert row == (None, source_id)


def test_동기화_기록은_원천마다_가장_최근_것을_찾는_색인을_가진다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        definition = _index_definition(connection, "ix_sync_records_source_id_created_at")

    assert "(source_id, created_at)" in definition


def test_동기화_기록은_작업_행을_지울_때_기록을_찾는_색인을_가진다(migrated_url: str) -> None:
    with _connect(migrated_url) as connection:
        definition = _index_definition(connection, "ix_sync_records_job_id")

    assert "ON public.sync_records" in definition
    assert "(job_id)" in definition


def test_마지막_판을_내리면_이_기능의_표와_칸과_제약이_모두_사라지고_다시_올라간다(
    empty_database_url: str,
) -> None:
    _alembic(empty_database_url, "upgrade", "head")
    _alembic(empty_database_url, "downgrade", "0003")

    with _connect(empty_database_url) as connection:
        tables = {
            name
            for (name,) in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ).fetchall()
        }
        sources = _columns(connection, "sources")
        jobs = _columns(connection, "jobs")
        documents = _columns(connection, "documents")
        version = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        source_id = _source(connection)
        document_id = _document(connection, source_id, _group(connection))
        with pytest.raises(errors.CheckViolation) as old_kind:
            _insert(connection, "sources", name="pull", kind="pull")
        with pytest.raises(errors.CheckViolation) as old_job_kind:
            _insert(
                connection,
                "jobs",
                kind="sync_source",
                document_id=document_id,
                status="queued",
                run_after=NOW,
                request_id=new_id(),
                created_at=NOW,
            )
        with pytest.raises(errors.CheckViolation) as old_status:
            _document(connection, source_id, _group(connection), key="s.pdf", status="skipped")

    assert tables == CORE_TABLES | {"alembic_version"}
    assert {"connector", "config", "group_id", "created_at"}.isdisjoint(sources)
    assert {"source_id", "options"}.isdisjoint(jobs)
    assert {"change_marker", "skip_reason", "deleted_with_source"}.isdisjoint(documents)
    assert jobs["document_id"][0] == "NO"
    assert documents["blob_path"][0] == "NO"
    assert version == [("0003",)]
    assert document_id
    assert _constraint_name(old_kind) == "ck_sources_kind"
    assert _constraint_name(old_job_kind) == "ck_jobs_kind"
    assert _constraint_name(old_status) == "ck_documents_status"

    _alembic(empty_database_url, "upgrade", "head")
    with _connect(empty_database_url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (HEAD_REVISION,)
        ]


def _assert_downgrade_halted_and_head_kept(url: str) -> None:
    """내리기가 멈췄고 한 트랜잭션이 되돌려져 판과 이 기능의 표가 그대로인지 본다."""
    with _connect(url) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        tables = {
            name
            for (name,) in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ).fetchall()
        }

    assert version == [(HEAD_REVISION,)]
    assert "sync_records" in tables


def test_가져오는_원천이_남아_있으면_판을_내리다_멈추고_판은_그대로다(
    empty_database_url: str,
) -> None:
    _alembic(empty_database_url, "upgrade", "head")
    with _connect(empty_database_url) as connection:
        _pull_source(connection)

    with pytest.raises(IntegrityError):
        _alembic(empty_database_url, "downgrade", "0003")

    _assert_downgrade_halted_and_head_kept(empty_database_url)


def test_색인이_아닌_작업이_남아_있으면_판을_내리다_멈추고_판은_그대로다(
    empty_database_url: str,
) -> None:
    _alembic(empty_database_url, "upgrade", "head")
    with _connect(empty_database_url) as connection:
        _job_row(connection, "cleanup")

    with pytest.raises(IntegrityError):
        _alembic(empty_database_url, "downgrade", "0003")

    _assert_downgrade_halted_and_head_kept(empty_database_url)


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
            (HEAD_REVISION,)
        ]


def test_접속_문자열의_스킴을_비동기_엔진용으로_바꾼다() -> None:
    assert (
        async_database_url("postgresql://u:p%40ss@127.0.0.1:55432/db")
        == "postgresql+psycopg://u:p%40ss@127.0.0.1:55432/db"
    )


def test_postgresql이_아닌_스킴은_거부한다() -> None:
    with pytest.raises(ValueError, match="postgresql:// 로 시작해야 한다"):
        async_database_url("postgresql+psycopg://u:p@h/db")
