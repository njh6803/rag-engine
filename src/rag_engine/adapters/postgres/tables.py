"""표 열둘의 정의(SQLAlchemy Core). 색인 형식의 원천은 alembic 마이그레이션이고 이 파일은 그 모양을
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
    sa.CheckConstraint("kind IN ('push')", name="kind"),
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
    sa.Column("blob_path", sa.Text, nullable=False),
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
    sa.UniqueConstraint("source_id", "key"),
    sa.CheckConstraint("status IN ('received', 'parsed', 'failed')", name="status"),
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

# 보관 표는 같은 칸에 보관 시각을 더한 것이고 벡터·키워드 색인은 없다.
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
    sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id"), nullable=False),
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
    sa.CheckConstraint("kind IN ('index_document')", name="kind"),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="status"),
    # 같은 문서의 대기 작업은 하나다(ADR 0009).
    sa.Index(
        "uq_jobs_document_id_queued",
        "document_id",
        unique=True,
        postgresql_where=sa.text("status = 'queued'"),
    ),
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
