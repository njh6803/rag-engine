"""작업 표에 문서별 진행 중 작업 색인을 더한다.

`has_active_job`(작업 조회 API와 `ingest --wait`의 기다림)은 `document_id = ? AND status IN
('queued', 'running')`로 묻는다. 0001의 부분 유일 색인은 `status = 'queued'`일 때만 쓰여 이 질의를
받지 못하고, 외래 키 열에는 색인이 자동으로 생기지 않아 작업 표를 처음부터 끝까지 읽는다. 이 색인은
술어를 질의와 같게 두어 진행 중인 작업만 담으므로 끝난 작업이 쌓여도 커지지 않는다. 칸과 제약은
바꾸지 않는다.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_document_id_active",
        "jobs",
        ["document_id"],
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_document_id_active", table_name="jobs")
