"""이미 설치된 곳의 암호 실패 문서와 글이 없는 문서를 건너뜀으로 옮긴다(source-sync 티켓 02, 명세
"데이터 모델과 스키마"의 마지막 항목).

스키마는 바꾸지 않는다. 0004가 만든 상태 `skipped`와 건너뜀 사유 칸에 데이터만 옮긴다.
- 문서 상태가 `failed`이고 오류 코드가 `encrypted_document`인 문서는 `skipped`와 사유 `encrypted`로
  옮기고 오류 코드를 비운다.
- 저장된 파싱 결과에 글이 하나도 없는 문서(지금은 `parsed`이고 조각이 0개다. 공백만 있는 것도
  같다)는 `skipped`와 사유 `no_text`로 옮긴다. 고르는 조건은 조각 수가 아니라 저장된 파싱 결과의
  글(공백이 아닌 글자가 든 블록이 없다)이고, 그 파싱 결과가 문서의 현재 내용과 같은 것(해시가
  같다)만 본다. 받음이나 실패로 진행 중인 문서는 건드리지 않는다. 다음 색인 작업이 알아서 쓴다.
- 옮긴 문서의 색인 상태는 `indexed`, 조각 0개, 오류 코드 없음으로 맞춘다. 건너뜀 문서가 판 전환을
  막지 않게 하려는 것이다(전환 조건은 모든 색인 상태가 `indexed`나 `failed`다). 색인 상태 행이 없는
  판에는 새로 만들지 않는다. 재색인이 그 판에 `pending`을 쓴 뒤 색인 작업이 건너뜀으로 쓴다.
옮기지 않으면 같은 종류의 문서가 업그레이드 앞뒤로 다른 상태에 남아 문서 목록의 실패 수가 무엇을
세는지 설치마다 달라진다.

`SCHEMA_VERSION`(색인 형식)은 올리지 않는다. 색인 판의 요소(조각, 임베딩, 키워드)를 바꾸지 않는다.

내릴 때는 옮긴 문서를 옛 모양으로 되돌린다. 사유 `encrypted`는 `failed`와 `encrypted_document`(색인
상태도 `failed`와 같은 코드, 조각 0개)로, 사유 `no_text`는 `parsed`로 되돌리고 건너뜀 사유를 비운다.
그러면 0004를 내릴 때 건너뜀 문서가 남아 멈추는 일이 없다. 이 판이 올린 뒤에 들어온 건너뜀 문서도
같은 길로 되돌린다.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 파싱 결과에 글이 있는 블록이 하나도 없다. 색인 작업의 `_has_text`는 파이썬의 `str.strip()`으로
# 공백을 가르므로 같은 공백 집합을 적는다(`str.isspace`가 참인 글자: U+0009~U+000D,
# U+001C~U+0020, U+0085, U+00A0, U+1680, U+2000~U+200A, U+2028, U+2029, U+202F, U+205F,
# U+3000). PostgreSQL의 `\S`는 데이터베이스 설정에 따라 U+00A0 같은 글자를 공백으로 보지 않아
# 갈린다.
_PYTHON_SPACES = (
    "\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a"
    "\\u2028\\u2029\\u202f\\u205f\\u3000"
)
_NO_TEXT = f"""
    NOT EXISTS (
        SELECT 1 FROM jsonb_array_elements(c.blocks) AS block
        WHERE (block ->> 'text') ~ '[^{_PYTHON_SPACES}]'
    )
"""


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE documents SET status = 'skipped', skip_reason = 'encrypted', error_code = NULL"
            " WHERE status = 'failed' AND error_code = 'encrypted_document'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE documents AS d SET status = 'skipped', skip_reason = 'no_text',"
            " error_code = NULL FROM document_contents AS c"
            " WHERE c.document_id = d.id AND d.status = 'parsed'"
            " AND c.parsed_content_hash = d.content_hash AND " + _NO_TEXT
        )
    )
    op.execute(
        sa.text(
            "UPDATE document_index_states AS s SET status = 'indexed', chunk_count = 0,"
            " built_content_hash = d.content_hash, error_code = NULL, updated_at = now()"
            " FROM documents AS d WHERE s.document_id = d.id AND d.status = 'skipped'"
            " AND (s.status <> 'indexed' OR s.chunk_count <> 0 OR s.error_code IS NOT NULL"
            " OR s.built_content_hash IS DISTINCT FROM d.content_hash)"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE document_index_states AS s SET status = 'failed', chunk_count = 0,"
            " built_content_hash = NULL, error_code = 'encrypted_document', updated_at = now()"
            " FROM documents AS d WHERE s.document_id = d.id AND d.status = 'skipped'"
            " AND d.skip_reason = 'encrypted'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE documents SET status = 'failed', error_code = 'encrypted_document',"
            " skip_reason = NULL WHERE status = 'skipped' AND skip_reason = 'encrypted'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE documents SET status = 'parsed', skip_reason = NULL"
            " WHERE status = 'skipped' AND skip_reason = 'no_text'"
        )
    )
