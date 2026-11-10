"""색인 형식의 첫 판: 표 열둘과 칸·제약(명세 "데이터 모델과 스키마").

`vector` 확장을 켜고(슈퍼유저 역할이 필요하다. compose의 기본 역할이 그렇다) 표를 만든다. 판마다의
HNSW 부분 색인은 색인 판 행을 만드는 쪽(재색인 시작, `migrate`의 첫 판)이 만든다.

제약 이름은 `tables.NAMING_CONVENTION`이 짓는다(env.py가 `target_metadata`로 넘긴다).

Revision ID: 0001
Revises:
Create Date: 2026-11-10
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[UUID]:
    return sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True)


def _timestamp() -> sa.TIMESTAMP:
    return sa.TIMESTAMP(timezone=True)


def _chunk_columns() -> list[sa.Column[object]]:
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


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        _id(),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.CheckConstraint("kind IN ('push')", name="kind"),
    )
    op.create_table(
        "groups",
        _id(),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )
    # 지식베이스와 색인 판이 서로를 가리켜서 현재 판 참조의 외래 키는 두 표를 만든 뒤에 단다.
    op.create_table(
        "knowledge_bases",
        _id(),
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
        sa.Column("current_index_version_id", sa.Uuid),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    # 기본 지식베이스 표시가 참인 행은 하나뿐이다.
    op.create_index(
        "uq_knowledge_bases_is_default",
        "knowledge_bases",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_table(
        "knowledge_base_groups",
        sa.Column(
            "knowledge_base_id", sa.Uuid, sa.ForeignKey("knowledge_bases.id"), primary_key=True
        ),
        sa.Column("group_id", sa.Uuid, sa.ForeignKey("groups.id"), primary_key=True),
    )
    op.create_table(
        "index_versions",
        _id(),
        sa.Column(
            "knowledge_base_id", sa.Uuid, sa.ForeignKey("knowledge_bases.id"), nullable=False
        ),
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
    op.create_foreign_key(
        None, "knowledge_bases", "index_versions", ["current_index_version_id"], ["id"]
    )

    op.create_table(
        "documents",
        _id(),
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
    op.create_table(
        "document_contents",
        sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id"), primary_key=True),
        sa.Column("parser_name", sa.Text, nullable=False),
        sa.Column("parser_interface_version", sa.Text, nullable=False),
        sa.Column("parser_library_version", sa.Text, nullable=False),
        sa.Column("blocks", JSONB, nullable=False),
        sa.Column("parsed_content_hash", sa.Text, nullable=False),
        sa.Column("text_hash", sa.Text, nullable=False),
        sa.Column("parsed_at", _timestamp(), nullable=False),
    )
    op.create_table(
        "document_index_states",
        sa.Column("document_id", sa.Uuid, sa.ForeignKey("documents.id"), primary_key=True),
        sa.Column(
            "index_version_id", sa.Uuid, sa.ForeignKey("index_versions.id"), primary_key=True
        ),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("built_content_hash", sa.Text),
        sa.Column("error_code", sa.Text),
        sa.Column("updated_at", _timestamp(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'indexed', 'failed')", name="status"),
    )

    op.create_table(
        "chunks",
        *_chunk_columns(),
        sa.UniqueConstraint("index_version_id", "document_id", "ordinal"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    # 키워드의 GIN 색인은 표 전체에 하나다. 조건에 색인 판 참조가 함께 들어 GIN 뒤의 필터로
    # 좁혀진다.
    op.create_index("ix_chunks_keywords", "chunks", ["keywords"], postgresql_using="gin")
    op.create_table(
        "archived_chunks",
        *_chunk_columns(),
        sa.Column("archived_at", _timestamp(), nullable=False),
    )
    op.create_index("ix_archived_chunks_document_id", "archived_chunks", ["document_id"])

    op.create_table(
        "jobs",
        _id(),
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
    )
    # 같은 문서의 대기 작업은 하나다(ADR 0009).
    op.create_index(
        "uq_jobs_document_id_queued",
        "jobs",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'queued'"),
    )

    op.create_table(
        "tokens",
        _id(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column(
            "knowledge_base_ids", ARRAY(sa.Uuid), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("expires_at", _timestamp()),
        sa.Column("revoked_at", _timestamp()),
        sa.Column("created_at", _timestamp(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'reader')", name="role"),
    )


def downgrade() -> None:
    raise NotImplementedError("첫 판은 되돌리지 않는다")
