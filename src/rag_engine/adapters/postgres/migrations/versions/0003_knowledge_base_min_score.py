"""지식베이스에 검색의 최소 점수 기본값 칸을 더한다(ADR 0017, 티켓 search-eval 20).

`knowledge_bases.min_score`는 널을 허용하는 실수 칸이다. 널이면 거르지 않고(옛 행이 모두 그렇다),
값이 있으면 `search`가 요청 인자 없이 불릴 때 리랭크 점수가 그 값보다 낮은 조각을 뺀다. CHECK 제약이
0 이상 1 이하만 받는다. 비교 결과가 널이면 제약은 통과하므로 널은 막지 않는다. 지식베이스 행의
설정일 뿐 색인 판의 요소가 아니라 `SCHEMA_VERSION`을 올리지 않고 재색인도 필요 없다(0002처럼 색인을
바꾸지 않는 마이그레이션이다).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("min_score", sa.Float))
    op.create_check_constraint(
        "min_score_in_unit_range", "knowledge_bases", "min_score >= 0 AND min_score <= 1"
    )


def downgrade() -> None:
    op.drop_constraint("ck_knowledge_bases_min_score_in_unit_range", "knowledge_bases")
    op.drop_column("knowledge_bases", "min_score")
