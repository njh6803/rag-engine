"""문서가 드는 살아 있는 색인 판(명세 "수집 파이프라인과 작업"의 대상 판)."""

from uuid import UUID

from rag_engine.domain.entities import IndexVersion
from rag_engine.domain.ports import Transaction


async def live_index_versions(transaction: Transaction, group_id: UUID) -> list[IndexVersion]:
    """그 그룹이 든 모든 지식베이스의 현재 판과 건설 중인 판."""
    versions: list[IndexVersion] = []
    for knowledge_base in await transaction.catalog.list_knowledge_bases_of_group(group_id):
        versions.extend(await transaction.catalog.list_live_index_versions(knowledge_base.id))
    return versions
