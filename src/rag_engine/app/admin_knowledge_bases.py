"""지식베이스 관리 조회의 유스케이스(명세 "관리 API"의 지식베이스 목록과 조회, 스토리 33).

지식베이스마다 이름, 설명, 문서 수, 현재 색인 판, "재색인 필요", 건설 중인 판의 진행을 낸다.
"재색인 필요"는 지식베이스의 지금 설정에서 계산한 판 요소 넷이 현재 판의 넷과 다른가로 정한다
(ADR 0008). 현재 판이 아직 없으면 필요하다. 진행은 건설 중인 판의 색인 상태 표를 상태마다 세어 낸다.
조회는 토큰의 지식베이스 범위를 보지 않는다. 관리 API는 `admin` 토큰의 몫이다.
"""

from dataclasses import dataclass

from rag_engine.domain.entities import (
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    KnowledgeBase,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import ComputeIndexElements, Transaction, UnitOfWork


@dataclass(frozen=True, slots=True)
class BuildProgress:
    """건설 중인 판에서 문서의 색인 상태를 센 값. `total`은 색인 상태 행의 수다. 재색인을 시작한
    뒤에 지식베이스에 든 문서는 색인 상태가 없어 세지 않는다."""

    version: IndexVersion
    pending: int
    indexed: int
    failed: int

    @property
    def total(self) -> int:
        return self.pending + self.indexed + self.failed


@dataclass(frozen=True, slots=True)
class KnowledgeBaseReport:
    knowledge_base: KnowledgeBase
    document_count: int
    current: IndexVersion | None
    building: BuildProgress | None
    reindex_needed: bool


@dataclass(frozen=True, slots=True)
class KnowledgeBaseDetail:
    """목록의 칸에 모든 색인 판(물러난 판 포함, 최근 순)을 더한 것."""

    report: KnowledgeBaseReport
    versions: tuple[IndexVersion, ...]


async def list_knowledge_base_reports(
    unit_of_work: UnitOfWork, compute_elements: ComputeIndexElements
) -> list[KnowledgeBaseReport]:
    async with unit_of_work.begin() as transaction:
        return [
            await _report(transaction, compute_elements, knowledge_base)
            for knowledge_base in await transaction.catalog.list_knowledge_bases()
        ]


async def get_knowledge_base_detail(
    unit_of_work: UnitOfWork, compute_elements: ComputeIndexElements, name: str
) -> KnowledgeBaseDetail:
    async with unit_of_work.begin() as transaction:
        knowledge_base = await transaction.catalog.get_knowledge_base(name)
        if knowledge_base is None:
            raise RequestError(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND, "지식베이스를 찾을 수 없다")
        return KnowledgeBaseDetail(
            report=await _report(transaction, compute_elements, knowledge_base),
            versions=tuple(await transaction.catalog.list_index_versions(knowledge_base.id)),
        )


async def _report(
    transaction: Transaction, compute_elements: ComputeIndexElements, knowledge_base: KnowledgeBase
) -> KnowledgeBaseReport:
    live = await transaction.catalog.list_live_index_versions(knowledge_base.id)
    current = next((v for v in live if v.status is IndexVersionStatus.CURRENT), None)
    building = next((v for v in live if v.status is IndexVersionStatus.BUILDING), None)
    wanted = compute_elements(
        knowledge_base.embedding_model, knowledge_base.embedding_dimensions, knowledge_base.chunking
    )
    return KnowledgeBaseReport(
        knowledge_base=knowledge_base,
        document_count=await transaction.documents.count_live_documents(knowledge_base.id),
        current=current,
        building=None if building is None else await _progress(transaction, building),
        reindex_needed=current is None or current.elements != wanted,
    )


async def _progress(transaction: Transaction, version: IndexVersion) -> BuildProgress:
    counts = await transaction.index.count_states(version.id)
    return BuildProgress(
        version=version,
        pending=counts.get(IndexStateStatus.PENDING, 0),
        indexed=counts.get(IndexStateStatus.INDEXED, 0),
        failed=counts.get(IndexStateStatus.FAILED, 0),
    )
