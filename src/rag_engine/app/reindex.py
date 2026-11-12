"""재색인 시작(명세 "수집 파이프라인과 작업"의 재색인 시작 항목, 티켓 14).

먼저 트랜잭션 밖에서 그 지식베이스의 물러난 판에 남은 정리를 한다. 그 뒤 작업 단위 하나에서
지식베이스 행을 `FOR UPDATE`로 잠그고(잠금 순서는 문서 행, 지식베이스 행, 작업 행이다. 이 작업
단위는 문서 행을 잠그지 않는다) 건설 중인 판이 있으면 `reindex_in_progress`다. 없으면 지식베이스의
지금 설정을 적은 새 판을 `building`으로 만들고, 그 지식베이스의 그룹에 든 살아 있는 문서마다 색인
상태 `pending`을 쓰고 `index_document` 작업을 넣은 뒤 그 판의 HNSW 부분 색인을 만든다.

문서 행을 `FOR UPDATE`로 잠그지 않는 까닭은 색인 상태와 작업 행을 넣을 때 외래 키 검사가 문서 행에
`FOR KEY SHARE`를 걸기 때문이다. 대기 작업이 이미 있는 문서는 그 작업 행을 잠가 두고 새 작업을 넣지
않는다. 작업자가 꺼낼 때의 `SKIP LOCKED`는 잠긴 작업을 이 작업 단위가 커밋될 때까지 건너뛰므로, 그
작업은 새 판도 대상 판으로 읽는다. 지운 문서에는 `pending`도 작업도 넣지 않는다. 문서가 하나도
없으면 색인을 만든 뒤 같은 작업 단위에서 전환한다.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rag_engine.app.retire_cleanup import clean_retired_versions
from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.entities import IndexVersion, IndexVersionStatus
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import ComputeIndexElements, IndexMaintenance, LockMode, UnitOfWork


@dataclass(frozen=True, slots=True)
class ReindexStarted:
    """시작한 재색인. `jobs_enqueued`는 새로 넣은 작업 수다(대기 작업이 이미 있던 문서는 그 작업이
    맡아 세지 않는다)."""

    index_version_id: UUID
    jobs_enqueued: int


async def start_reindex(
    unit_of_work: UnitOfWork,
    maintenance: IndexMaintenance,
    compute_elements: ComputeIndexElements,
    name: str,
    *,
    request_id: UUID,
    now: datetime,
) -> ReindexStarted:
    async with unit_of_work.begin() as transaction:
        found = await transaction.catalog.get_knowledge_base(name)
    if found is None:
        raise RequestError(ErrorCode.KNOWLEDGE_BASE_NOT_FOUND, "지식베이스를 찾을 수 없다")
    await clean_retired_versions(maintenance, found.id)
    async with unit_of_work.begin() as transaction:
        (knowledge_base,) = await transaction.catalog.lock_knowledge_bases(
            [found.id], LockMode.UPDATE
        )
        live = await transaction.catalog.list_live_index_versions(knowledge_base.id)
        if any(version.status is IndexVersionStatus.BUILDING for version in live):
            raise RequestError(ErrorCode.REINDEX_IN_PROGRESS, "이 지식베이스는 재색인 중이다")
        elements = compute_elements(
            knowledge_base.embedding_model,
            knowledge_base.embedding_dimensions,
            knowledge_base.chunking,
        )
        version = IndexVersion(
            id=new_id(),
            knowledge_base_id=knowledge_base.id,
            schema_version=elements.schema_version,
            embedding_endpoint=knowledge_base.embedding_endpoint,
            embedding_model=elements.embedding_model,
            embedding_dimensions=elements.embedding_dimensions,
            chunking=knowledge_base.chunking,
            chunking_hash=elements.chunking_hash,
            tokenizer_version=elements.tokenizer_version,
            status=IndexVersionStatus.BUILDING,
            created_at=now,
            retired_at=None,
        )
        await transaction.catalog.add_index_version(version)
        document_ids = await transaction.documents.list_live_document_ids(knowledge_base.id)
        await transaction.index.create_pending_states(version.id, document_ids, now)
        queued = await transaction.jobs.lock_queued_documents(document_ids)
        enqueued = 0
        for document_id in document_ids:
            if document_id not in queued:
                await transaction.jobs.enqueue(document_id, request_id, now)
                enqueued += 1
        await transaction.index.create_version_index(version)
        await check_version_switch(transaction, version)
    return ReindexStarted(version.id, enqueued)
