"""토큰이 닿는 지식베이스의 범위 판정. 읽기 유스케이스가 함께 쓴다(명세 "인증과 권한")."""

from collections.abc import Sequence
from uuid import UUID


def is_in_scope(allowed_knowledge_base_ids: Sequence[UUID], knowledge_base_id: UUID) -> bool:
    """범위가 비면 토큰은 모든 지식베이스에 닿는다."""
    return not allowed_knowledge_base_ids or knowledge_base_id in allowed_knowledge_base_ids
