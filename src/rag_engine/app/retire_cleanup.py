"""물러난 판의 정리(명세 "수집 파이프라인과 작업"의 판 전환 항목).

전환을 커밋한 뒤 작업자가 트랜잭션 밖에서 한다. HNSW 색인을 먼저 지우고(그래야 조각을 지울 때 색인을
함께 고치지 않는다), 조각은 상수 크기의 묶음마다 별도 트랜잭션에서 지운다. 큰 지식베이스에서 한
트랜잭션을 길게 하지 않기 위해서다. 정리는 멱등이고 겹쳐 돌아도 안전하다. 그 사이에 작업자가 죽거나,
전환 전에 대상 판을 읽은 작업이 정리 뒤에 그 판에 조각을 써서 남은 것은 검색에 보이지 않으며, 다음
정리가 다시 지운다.
"""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from rag_engine.domain.ports import IndexMaintenance

# 조각을 한 번에 지우는 수. 한 트랜잭션이 잡는 행 잠금과 걸리는 시간을 일정하게 묶는다.
CLEAN_BATCH_CHUNKS: Final = 1000


@dataclass(frozen=True, slots=True)
class CleanedVersion:
    """정리한 물러난 판 하나와 지운 조각 수."""

    index_version_id: UUID
    knowledge_base_id: UUID
    chunks_deleted: int


async def clean_retired_versions(
    maintenance: IndexMaintenance,
    knowledge_base_id: UUID | None = None,
    *,
    batch_chunks: int = CLEAN_BATCH_CHUNKS,
) -> list[CleanedVersion]:
    """남은 색인이나 조각이 있는 물러난 판을 정리해 판마다 결과를 낸다. 지식베이스를 주면 그
    지식베이스의 물러난 판만이다."""
    cleaned: list[CleanedVersion] = []
    for version in await maintenance.list_versions_to_clean(knowledge_base_id):
        await maintenance.drop_version_index(version.id)
        deleted = 0
        while batch := await maintenance.delete_version_chunks(version.id, batch_chunks):
            deleted += batch
        cleaned.append(CleanedVersion(version.id, version.knowledge_base_id, deleted))
    return cleaned
