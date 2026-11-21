"""원천과 동기화 기능의 스키마(source-sync 티켓 01, 명세 "데이터 모델과 스키마").

이 판 하나가 네 곳을 고친다.
- `sources`: `pull`(가져오기) 갈래와 커넥터·설정·그룹·일정·다음 실행 시각·일시 중지·제외 패턴·지움
  표시·만든 시각 칸을 더한다. 밀어 넣는 원천은 가져오기 전용 칸 일곱이 비어 있어야 하고, 가져오는
  원천은 커넥터 이름과 설정과 그룹이 있어야 한다. 이미 있는 원천의 만든 시각은 이 마이그레이션이
  지금 시각으로 채운다.
- `documents`: 변경 확인값(`change_marker`), 건너뜀 사유(`skip_reason`), 원천과 함께 지워졌다는
  표시(`deleted_with_source`)를 더하고 상태에 `skipped`를 더한다. 가져오는 원천의 문서는 원본을 따로
  보관하지 않으므로 `blob_path`가 빌 수 있다.
- `jobs`: 종류를 다섯으로 늘리고(`index_document`에 `sync_source`, `delete_source`,
  `restore_source`, `cleanup`을 더한다) 원천을
  가리키는 칸(`source_id`)과 옵션을 더한다. 색인 작업만 문서를 가리키므로 `document_id`가 빌 수
  있고, 종류마다 무엇을 가리키는지 CHECK 제약이 지킨다. 같은 원천의 같은 종류 작업은 대기 중이거나
  실행 중일 때 하나뿐이다(원천이 빈 정리 작업도 하나로 본다). 꺼내기용 부분 색인은 색인 작업이 아닌
  작업만 담는다.
- `sync_records`: 동기화 한 번의 기록 표를 새로 만든다.

`SCHEMA_VERSION`(색인 형식)은 올리지 않는다. 고치는 곳이 색인 판의 요소(조각, 임베딩, 키워드)가
아니라서 재색인이 필요 없다(0003과 같은 판단이다).

내릴 때는 이 판이 더한 칸과 표(`sync_records`)를 그 안의 값과 함께 지운다. 일시 중지, 제외 패턴,
지움 표시, 만든 시각, 변경 확인값, 원천과 함께 지워졌다는 표시, 동기화 기록은 되돌릴 수 없다. 다시
올리면 지운 원천은 지우지 않은 원천이 되고 이 칸들은 기본값이다. 옛 제약이 받지 않는 행, 곧
가져오는 원천, 건너뜀 문서, 원본 경로가 빈 문서, 색인이 아닌 작업이 남아 있으면 내리는 중에 멈추고
아무것도 바꾸지 않는다. 그 행을 먼저 치우고 내린다.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp() -> sa.TIMESTAMP:
    return sa.TIMESTAMP(timezone=True)


def _upgrade_sources() -> None:
    op.add_column("sources", sa.Column("connector", sa.Text))
    op.add_column("sources", sa.Column("config", JSONB))
    op.add_column("sources", sa.Column("group_id", sa.Uuid))
    op.add_column("sources", sa.Column("schedule", sa.Text))
    op.add_column("sources", sa.Column("next_run_at", _timestamp()))
    op.add_column(
        "sources", sa.Column("paused", sa.Boolean, nullable=False, server_default=sa.false())
    )
    op.add_column(
        "sources",
        sa.Column(
            "exclude_patterns", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    op.add_column("sources", sa.Column("deleted_at", _timestamp()))
    op.add_column(
        "sources",
        sa.Column("created_at", _timestamp(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_foreign_key(None, "sources", "groups", ["group_id"], ["id"])

    op.drop_constraint("ck_sources_kind", "sources")
    op.create_check_constraint("kind", "sources", "kind IN ('push', 'pull')")
    op.create_check_constraint(
        "push_columns_empty",
        "sources",
        "kind <> 'push' OR (connector IS NULL AND config IS NULL AND group_id IS NULL"
        " AND schedule IS NULL AND next_run_at IS NULL AND paused = false"
        " AND exclude_patterns = '{}')",
    )
    op.create_check_constraint(
        "pull_columns_present",
        "sources",
        "kind <> 'pull' OR (connector IS NOT NULL AND config IS NOT NULL AND group_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "config_is_object", "sources", "config IS NULL OR jsonb_typeof(config) = 'object'"
    )


def _upgrade_documents() -> None:
    op.add_column("documents", sa.Column("change_marker", sa.Text))
    op.add_column("documents", sa.Column("skip_reason", sa.Text))
    op.add_column(
        "documents",
        sa.Column("deleted_with_source", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.alter_column("documents", "blob_path", nullable=True)

    op.drop_constraint("ck_documents_status", "documents")
    op.create_check_constraint(
        "status", "documents", "status IN ('received', 'parsed', 'failed', 'skipped')"
    )
    op.create_check_constraint(
        "skip_reason",
        "documents",
        "skip_reason IS NULL OR (status = 'skipped' AND skip_reason IN ('encrypted', 'no_text'))",
    )


def _upgrade_jobs() -> None:
    op.add_column("jobs", sa.Column("source_id", sa.Uuid))
    op.add_column(
        "jobs",
        sa.Column("options", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.alter_column("jobs", "document_id", nullable=True)
    op.create_foreign_key(None, "jobs", "sources", ["source_id"], ["id"])

    op.drop_constraint("ck_jobs_kind", "jobs")
    op.create_check_constraint(
        "kind",
        "jobs",
        "kind IN ('index_document', 'sync_source', 'delete_source', 'restore_source', 'cleanup')",
    )
    op.create_check_constraint(
        "references_match_kind",
        "jobs",
        "(kind = 'index_document' AND document_id IS NOT NULL AND source_id IS NULL)"
        " OR (kind IN ('sync_source', 'delete_source', 'restore_source')"
        " AND source_id IS NOT NULL AND document_id IS NULL)"
        " OR (kind = 'cleanup' AND source_id IS NULL AND document_id IS NULL)",
    )
    op.create_check_constraint("options_is_object", "jobs", "jsonb_typeof(options) = 'object'")

    # 같은 원천의 같은 종류 작업은 대기 중이거나 실행 중일 때 하나뿐이다. 정리 작업은 원천이
    # 비어 있어서 `NULLS NOT DISTINCT`로 빈 값끼리도 같은 값으로 본다(PostgreSQL 15 이상).
    op.create_index(
        "uq_jobs_source_id_kind_active",
        "jobs",
        ["source_id", "kind"],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("document_id IS NULL AND status IN ('queued', 'running')"),
    )
    # 색인 작업이 아닌 작업을 꺼내는 질의(`run_after` 순)를 받는다.
    op.create_index(
        "ix_jobs_not_index_document_run_after",
        "jobs",
        ["run_after", "id"],
        postgresql_where=sa.text("kind <> 'index_document' AND status IN ('queued', 'running')"),
    )


def _create_sync_records() -> None:
    op.create_table(
        "sync_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.Uuid, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("job_id", sa.Uuid, sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("options", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", _timestamp(), nullable=False),
        sa.Column("started_at", _timestamp()),
        sa.Column("finished_at", _timestamp()),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("failure_code", sa.Text),
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
    )
    # 원천마다 가장 최근 기록을 찾는다.
    op.create_index(
        "ix_sync_records_source_id_created_at", "sync_records", ["source_id", "created_at"]
    )
    # 작업 행을 지우면 `ON DELETE SET NULL`이 그 작업의 기록을 찾는다. 색인이 없으면 지울 때마다
    # 기록 표를 처음부터 끝까지 훑는다.
    op.create_index("ix_sync_records_job_id", "sync_records", ["job_id"])


def upgrade() -> None:
    _upgrade_sources()
    _upgrade_documents()
    _upgrade_jobs()
    _create_sync_records()


def downgrade() -> None:
    op.drop_table("sync_records")

    op.drop_index("ix_jobs_not_index_document_run_after", "jobs")
    op.drop_index("uq_jobs_source_id_kind_active", "jobs")
    op.drop_constraint("ck_jobs_options_is_object", "jobs")
    op.drop_constraint("ck_jobs_references_match_kind", "jobs")
    op.drop_constraint("ck_jobs_kind", "jobs")
    op.drop_constraint("fk_jobs_source_id_sources", "jobs", type_="foreignkey")
    op.drop_column("jobs", "options")
    op.drop_column("jobs", "source_id")
    op.alter_column("jobs", "document_id", nullable=False)
    op.create_check_constraint("kind", "jobs", "kind IN ('index_document')")

    op.drop_constraint("ck_documents_skip_reason", "documents")
    op.drop_constraint("ck_documents_status", "documents")
    op.drop_column("documents", "deleted_with_source")
    op.drop_column("documents", "skip_reason")
    op.drop_column("documents", "change_marker")
    op.alter_column("documents", "blob_path", nullable=False)
    op.create_check_constraint("status", "documents", "status IN ('received', 'parsed', 'failed')")

    op.drop_constraint("ck_sources_config_is_object", "sources")
    op.drop_constraint("ck_sources_pull_columns_present", "sources")
    op.drop_constraint("ck_sources_push_columns_empty", "sources")
    op.drop_constraint("ck_sources_kind", "sources")
    op.drop_constraint("fk_sources_group_id_groups", "sources", type_="foreignkey")
    for column in (
        "created_at",
        "deleted_at",
        "exclude_patterns",
        "paused",
        "next_run_at",
        "schedule",
        "group_id",
        "config",
        "connector",
    ):
        op.drop_column("sources", column)
    op.create_check_constraint("kind", "sources", "kind IN ('push')")
