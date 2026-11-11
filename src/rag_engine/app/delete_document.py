"""삭제 유스케이스(명세 "삭제, 되살림, 묘비", 티켓 11).

소프트 삭제다. 작업 단위 하나에서 문서 행을 잠그고 그 문서의 그룹이 든 지식베이스 행을
`FOR UPDATE`로 잠근 뒤(잠금 순서는 문서 행, 지식베이스 행, 작업 행이다) 세대를 올리며 `deleted_at`을
쓰고, 모든 색인 판의 조각을 보관 표로 옮기고, 그 문서의 색인 상태를 모두 지우고, 대기 작업을 지운다.
지식베이스에 건설 중인 판이 있으면 색인 상태가 사라져 판이 전환될 수 있으므로 전환 검사를 부른다.
그래서 문서는 이 커밋으로 검색에서 빠진다.

실행 중인 작업은 건드리지 않는다. 첫째 단계에서 지워진 문서를 보면 성공으로 끝나고, 그 뒤에
지워졌으면 셋째 단계의 세대 대조가 막는다. 이미 지운 문서의 삭제는 아무것도 바꾸지 않는다. 키가
없거나 정리 작업이 물리 삭제해 묘비 행만 남은 문서는 `document_not_found`다.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.entities import IndexVersionStatus, KnowledgeBase
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import LockMode, Transaction, UnitOfWork


async def delete_document(unit_of_work: UnitOfWork, key: str, *, now: datetime) -> None:
    async with unit_of_work.begin() as transaction:
        source = await transaction.catalog.get_source(DEFAULT_NAME)
        if source is None:
            raise RuntimeError("기본 원천이 없다. migrate를 돌려야 한다")
        found = await transaction.documents.get_by_key(source.id, key)
        if found is None or found.purged_at is not None:
            raise RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "그 키의 문서가 없다")
        document = await transaction.documents.lock(found.id)
        if document is None:
            raise RuntimeError("문서 행이 잠그는 사이에 사라졌다")
        if document.deleted_at is not None:
            return
        knowledge_bases = await transaction.catalog.list_knowledge_bases_of_group(document.group_id)
        await transaction.catalog.lock_knowledge_bases(
            [knowledge_base.id for knowledge_base in knowledge_bases], LockMode.UPDATE
        )
        await transaction.documents.update(
            replace(document, deleted_at=now, generation=document.generation + 1, modified_at=now)
        )
        await transaction.index.archive_chunks(document.id, now)
        await transaction.index.delete_states(document.id)
        await transaction.jobs.delete_queued(document.id)
        await _check_building_versions(transaction, knowledge_bases)


async def _check_building_versions(
    transaction: Transaction, knowledge_bases: Sequence[KnowledgeBase]
) -> None:
    """색인 상태가 사라진 건설 중인 판마다 전환 검사를 부른다. 지식베이스 행은 잠긴 채다."""
    for knowledge_base in knowledge_bases:
        for version in await transaction.catalog.list_live_index_versions(knowledge_base.id):
            if version.status is IndexVersionStatus.BUILDING:
                await check_version_switch(transaction, version)
