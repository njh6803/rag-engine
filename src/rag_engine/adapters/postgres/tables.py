"""표 열셋의 정의(SQLAlchemy Core). 색인 형식의 원천은 alembic 마이그레이션이고 이 파일은 그 모양을
코드에 둔다.

칸과 제약은 명세 "데이터 모델과 스키마" 절이다. 마이그레이션과 표·칸의 이름, 널 허용, 색인·유일·
외래 키가 어긋나지 않는지는 시험이 대 본다(`tests/adapters/test_migrations.py`). 칸의 타입, 서버
기본값, CHECK 제약은 그 비교가 보지 않으므로 마이그레이션을 고칠 때 이 파일도 손으로 맞춘다.

제약 이름의 규칙(`NAMING_CONVENTION`)은 마이그레이션이 이름을 짓는 데도 쓰인다. 이미 적용된 판과
이름이 달라지므로 바꾸지 않는다.

벡터 열은 차원을 적지 않은 `vector`이고 판마다의 HNSW 부분 색인은 판을 만드는 쪽이 만든다(명세).
키워드 열의 GIN 색인은 표 전체에 하나다.
"""

from typing import Final
from uuid import UUID

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

NAMING_CONVENTION: Final = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


def _timestamp() -> sa.TIMESTAMP:
    return sa.TIMESTAMP(timezone=True)


def _id_column() -> sa.Column[UUID]:
    return sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True)


sources = sa.Table(
    "sources",
    metadata,
    _id_column(),
    sa.Column("name", sa.Text, nullable=False, unique=True),
    sa.Column("kind", sa.Text, nullable=False),
    # 아래 일곱 칸은 가져오는(`pull`) 원천만 쓴다(마이그레이션 0004).
    sa.Column("connector", sa.Text),
    sa.Column("config", JSONB),
    sa.Column("group_id", sa.Uuid, sa.ForeignKey("groups.id")),
    sa.Column("schedule", sa.Text),
    sa.Column("next_run_at", _timestamp()),
    sa.Column("paused", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("exclude_patterns", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("deleted_at", _timestamp()),
    sa.Column("created_at", _timestamp(), nullable=False, server_default=sa.text("now()")),
    sa.CheckConstraint("kind IN ('push', 'pull')", name="kind"),
    sa.CheckConstraint(
        "kind <> 'push' OR (connector IS NULL AND config IS NULL AND group_id IS NULL"
        " AND schedule IS NULL AND next_run_at IS NULL AND paused = false"
        " AND exclude_patterns = '{}')",
        name="push_columns_empty",
    ),
    sa.CheckConstraint(
        "kind <> 'pull' OR (connector IS NOT NULL AND config IS NOT NULL AND group_id IS NOT NULL)",
        name="pull_columns_present",
    ),
    sa.CheckConstraint(
        "config IS NULL OR jsonb_typeof(config) = 'object'", name="config_is_object"
    ),
)

groups = sa.Table(
    "groups",
    metadata,
    _id_column(),
    sa.Column("name", sa.Text, nullable=False, unique=True),
    sa.Column("description", sa.Text, nullable=False, server_default=""),
)

knowledge_bases = sa.Table(
    "knowledge_bases",
    metadata,
    _id_column(),
    sa.Column("name", sa.Text, nullable=False, unique=True),
    sa.Column("description", sa.Text, nullable=False, server_default=""),
    sa.Column("embedding_endpoint", sa.Text, nullable=False),
    sa.Column("embedding_model", sa.Text, nullable=False),
    sa.Column("embedding_dimensions", sa.Integer, nullable=False),
    sa.Column("reranker_endpoint", sa.Text),
    sa.Column("reranker_model", sa.Text),
    sa.Column("chunking_strategy", sa.Text, nullable=False),
    sa.Column("chunk_tokens", sa.Integer, nullable=False),
    sa.Column("chunk_overlap_tokens", sa.Integer, nullable=False),
    sa.Column(
        "current_index_version_id",
        sa.Uuid,
        sa.ForeignKey("index_versions.id", use_alter=True),
    ),
    sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
    # 검색의 최소 점수 기본값. 널이면 거르지 않는다(마이그레이션 0003).
    sa.Column("min_score", sa.Float),
    sa.CheckConstraint("min_score >= 0 AND min_score <= 1", name="min_score_in_unit_range"),
    # 기본 지식베이스 표시가 참인 행은 하나뿐이다.
    sa.Index(
        "uq_knowledge_bases_is_default",
        "is_default",
        unique=True,
        postgresql_where=sa.text("is_default"),
    ),
)

knowledge_base_groups = sa.Table(
    "knowledge_base_groups",
    metadata,
    sa.Column("knowledge_base_id", sa.Uuid, sa.ForeignKey("knowledge_bases.id"), primary_key=True),
    sa.Column("group_id", sa.Uuid, sa.ForeignKey("groups.id"), primary_key=True),
)

index_versions = sa.Table(
    "index_versions",
    metadata,
    _id_column(),
    sa.Column("knowledge_base_id", sa.Uuid, sa.ForeignKey("knowledge_bases.id"), nullable=False),
    sa.Column("schema_version", sa.Integer, nullable=False),
    sa.Column("embedding_endpoint", sa.Text, nullable=False),
    sa.Column("embedding_model", sa.Text, nullable=False),
    sa.Column("embedding_dimensions", sa.Integer, nullable=False),
    sa.Column("chunking_config", JSONB, nullable=False),
    sa.Column("chunking_hash", sa.Text, nullable=False),
    sa.Column("tokenizer_version", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("created_at", _timestamp(), nullable=False),
    sa.Column("retired_at", _timestamp()),
    sa.CheckConstraint("status IN ('building', 'current', 'retired')", name="status"),
)

documents = sa.Table(
    "documents",
    metadata,
    _id_column(),
    sa.Column("source_id", sa.Uuid, sa.ForeignKey("sources.id"), nullable=False),
    sa.Column("key", sa.Text, nullable=False),
    sa.Column("group_id", sa.Uuid, sa.ForeignKey("groups.id"), nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("mime", sa.Text, nullable=False),
    sa.Column("size_bytes", sa.BigInteger, nullable=False),
    sa.Column("content_hash", sa.Text, nullable=False),
    # 가져오는 원천의 문서는 원본을 따로 보관하지 않아 비어 있다(마이그레이션 0004).
    sa.Column("blob_path", sa.Text),
    sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("updated_at", _timestamp(), nullable=False),
    sa.Column("effective_date", sa.Date),
    sa.Column("access_groups", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("error_code", sa.Text),
    sa.Column("generation", sa.BigInteger, nullable=False),
    sa.Column("deleted_at", _timestamp()),
    sa.Column("purged_at", _timestamp()),
    sa.Column("created_at", _timestamp(), nullable=False),
    sa.Column("modified_at", _timestamp(), nullable=False),
    sa.Column("change_marker", sa.Text),
    sa.Column("skip_reason", sa.Text),
    sa.Column("deleted_with_source", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.UniqueConstraint("source_id", "key"),
    sa.CheckConstraint("status IN ('received', 'parsed', 'failed', 'skipped')", name="status"),
    sa.CheckConstraint(
        "skip_reason IS NULL OR (status = 'skipped' AND skip_reason IN ('encrypted', 'no_text'))",
        name="skip_reason",
    ),
    sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_is_object"),
)

document_contents = sa.Table(
    "document_contents",
    metadata,
    sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id"), primary_key=True),
    sa.Column("parser_name", sa.Text, nullable=False),
    sa.Column("parser_interface_version", sa.Text, nullable=False),
    sa.Column("parser_library_version", sa.Text, nullable=False),
    sa.Column("blocks", JSONB, nullable=False),
    sa.Column("parsed_content_hash", sa.Text, nullable=False),
    sa.Column("text_hash", sa.Text, nullable=False),
    sa.Column("parsed_at", _timestamp(), nullable=False),
)

document_index_states = sa.Table(
    "document_index_states",
    metadata,
    sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id"), primary_key=True),
    sa.Column("index_version_id", sa.Uuid, sa.ForeignKey("index_versions.id"), primary_key=True),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("chunk_count", sa.Integer, nullable=False),
    sa.Column("built_content_hash", sa.Text),
    sa.Column("error_code", sa.Text),
    sa.Column("updated_at", _timestamp(), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'indexed', 'failed')", name="status"),
)


def _chunk_columns() -> list[sa.Column[object]]:
    """조각과 보관 조각이 함께 쓰는 칸. 복사한 칸(그룹, 갱신일, 시행일, 접근 그룹)을 든다."""
    return [
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("index_version_id", sa.Uuid, sa.ForeignKey("index_versions.id"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("location", JSONB, nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("keywords", TSVECTOR, nullable=False),
        sa.Column("source_content_hash", sa.Text, nullable=False),
        sa.Column("group_id", sa.Uuid, sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("updated_at", _timestamp(), nullable=False),
        sa.Column("effective_date", sa.Date),
        sa.Column("access_groups", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
    ]


chunks = sa.Table(
    "chunks",
    metadata,
    *_chunk_columns(),
    sa.UniqueConstraint("index_version_id", "document_id", "ordinal"),
    sa.Index("ix_chunks_document_id", "document_id"),
    # 키워드의 GIN 색인은 표 전체에 하나다. 조건에 색인 판 참조가 함께 들어 GIN 뒤의 필터로
    # 좁혀진다.
    sa.Index("ix_chunks_keywords", "keywords", postgresql_using="gin"),
)

# 삭제 보관함은 같은 칸에 보관 시각을 더한 것이고 벡터·키워드 색인은 없다.
archived_chunks = sa.Table(
    "archived_chunks",
    metadata,
    *_chunk_columns(),
    sa.Column("archived_at", _timestamp(), nullable=False),
    sa.Index("ix_archived_chunks_document_id", "document_id"),
)

jobs = sa.Table(
    "jobs",
    metadata,
    _id_column(),
    sa.Column("kind", sa.Text, nullable=False),
    # 색인 작업만 문서를 가리키고 원천 단위 작업은 원천을 가리킨다(마이그레이션 0004).
    sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id")),
    sa.Column("source_id", sa.Uuid, sa.ForeignKey("sources.id")),
    sa.Column("options", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("run_after", _timestamp(), nullable=False),
    sa.Column("leased_until", _timestamp()),
    sa.Column("worker_id", sa.Text),
    sa.Column("raised_generation", sa.BigInteger),
    sa.Column("last_error_code", sa.Text),
    sa.Column("request_id", sa.Uuid, nullable=False),
    sa.Column("created_at", _timestamp(), nullable=False),
    sa.Column("started_at", _timestamp()),
    sa.Column("finished_at", _timestamp()),
    sa.CheckConstraint(
        "kind IN ('index_document', 'sync_source', 'delete_source', 'restore_source', 'cleanup')",
        name="kind",
    ),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="status"),
    sa.CheckConstraint(
        "(kind = 'index_document' AND document_id IS NOT NULL AND source_id IS NULL)"
        " OR (kind IN ('sync_source', 'delete_source', 'restore_source')"
        " AND source_id IS NOT NULL AND document_id IS NULL)"
        " OR (kind = 'cleanup' AND source_id IS NULL AND document_id IS NULL)",
        name="references_match_kind",
    ),
    sa.CheckConstraint("jsonb_typeof(options) = 'object'", name="options_is_object"),
    # 같은 문서의 대기 작업은 하나다(ADR 0009).
    sa.Index(
        "uq_jobs_document_id_queued",
        "document_id",
        unique=True,
        postgresql_where=sa.text("status = 'queued'"),
    ),
    # 문서에 대기·실행 중인 작업이 있는지 묻는 질의(`has_active_job`)를 받는다. 술어가 질의의
    # `IN` 목록과 같아야 플래너가 쓴다.
    sa.Index(
        "ix_jobs_document_id_active",
        "document_id",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    ),
    # 같은 원천의 같은 종류 작업은 대기 중이거나 실행 중일 때 하나뿐이다. 원천이 빈 정리 작업도
    # 하나로 보려고 빈 값끼리 같은 값으로 친다.
    sa.Index(
        "uq_jobs_source_id_kind_active",
        "source_id",
        "kind",
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("document_id IS NULL AND status IN ('queued', 'running')"),
    ),
    # 색인 작업이 아닌 작업을 꺼내는 질의를 받는다.
    sa.Index(
        "ix_jobs_not_index_document_run_after",
        "run_after",
        "id",
        postgresql_where=sa.text("kind <> 'index_document' AND status IN ('queued', 'running')"),
    ),
)

# 동기화 한 번의 기록(마이그레이션 0004).
sync_records = sa.Table(
    "sync_records",
    metadata,
    _id_column(),
    sa.Column("source_id", sa.Uuid, sa.ForeignKey("sources.id"), nullable=False),
    # 작업 행을 지워도(원천 삭제가 대기 중인 동기화 작업을 지운다) 기록은 남는다.
    sa.Column("job_id", sa.Uuid, sa.ForeignKey("jobs.id", ondelete="SET NULL")),
    sa.Column("trigger", sa.Text, nullable=False),
    sa.Column("options", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", _timestamp(), nullable=False),
    sa.Column("started_at", _timestamp()),
    sa.Column("finished_at", _timestamp()),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("failure_code", sa.Text),
    # 목록을 받지 못한 실패에서는 비어 있고 받았는데 0건이면 0이다(명세 "동기화 기록").
    sa.Column("listed", sa.Integer),
    sa.Column("added", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("updated", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("deleted", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("unchanged", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("skipped", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("not_accepted", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("failed", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.CheckConstraint(
        "status IN ('queued', 'running', 'succeeded', 'failed', 'not_started')", name="status"
    ),
    sa.CheckConstraint("trigger IN ('schedule', 'manual')", name="trigger"),
    sa.CheckConstraint("jsonb_typeof(options) = 'object'", name="options_is_object"),
    sa.CheckConstraint("jsonb_typeof(skipped) = 'object'", name="skipped_is_object"),
    sa.CheckConstraint("jsonb_typeof(not_accepted) = 'object'", name="not_accepted_is_object"),
    sa.CheckConstraint("jsonb_typeof(failed) = 'object'", name="failed_is_object"),
    # 원천마다 가장 최근 기록을 찾는다.
    sa.Index("ix_sync_records_source_id_created_at", "source_id", "created_at"),
    # 작업 행을 지우면 `ON DELETE SET NULL`이 그 작업의 기록을 찾는다.
    sa.Index("ix_sync_records_job_id", "job_id"),
)

tokens = sa.Table(
    "tokens",
    metadata,
    _id_column(),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("token_hash", sa.Text, nullable=False, unique=True),
    sa.Column("role", sa.Text, nullable=False),
    sa.Column("knowledge_base_ids", ARRAY(sa.Uuid), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("expires_at", _timestamp()),
    sa.Column("revoked_at", _timestamp()),
    sa.Column("created_at", _timestamp(), nullable=False),
    sa.CheckConstraint("role IN ('admin', 'reader')", name="role"),
)
