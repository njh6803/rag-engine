"""삭제 유스케이스(명세 "삭제, 되살림, 묘비", 티켓 11).

임시 삭제다. 작업 단위 하나에서 문서 행을 잠그고 그 문서의 그룹이 든 지식베이스 행을
`FOR UPDATE`로 잠근 뒤(잠금 순서는 문서 행, 지식베이스 행, 작업 행이다) 세대를 올리며 `deleted_at`을
쓰고, 모든 색인 판의 조각을 삭제 보관함으로 옮기고, 그 문서의 색인 상태를 모두 지우고, 대기 작업을
지운다. 지식베이스에 건설 중인 판이 있으면 색인 상태가 사라져 판이 전환될 수 있으므로 전환 검사를
부른다. 그래서 문서는 이 커밋으로 검색에서 빠진다.

실행 중인 작업은 건드리지 않는다. 첫째 단계에서 지워진 문서를 보면 성공으로 끝나고, 그 뒤에
지워졌으면 셋째 단계의 세대 대조가 막는다. 이미 지운 문서의 삭제는 아무것도 바꾸지 않는다. 다만
원천과 함께 지워졌다는 표시가 남은 문서는 표시를 걷어 따로 지운 문서로 만든다(원천 되살리기
작업이 되살리지 않게 한다). 키가 없거나 정리 작업이 물리 삭제해 삭제 기록 행만 남은 문서는
`document_not_found`다.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from rag_engine.app.source_lookup import require_push_source
from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.entities import Document, IndexVersionStatus, KnowledgeBase
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import LockMode, Transaction, UnitOfWork


async def delete_document(
    unit_of_work: UnitOfWork, key: str, *, source_name: str | None, now: datetime
) -> None:
    """`source_name`은 지울 문서가 든 원천의 이름이고 `None`이면 `default`다. 없는 원천은
    `source_not_found`다."""
    async with unit_of_work.begin() as transaction:
        source = await require_push_source(transaction, source_name)
        found = await transaction.documents.get_by_key(source.id, key)
        if found is None or found.purged_at is not None:
            raise RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "그 키의 문서가 없다")
        document = await transaction.documents.lock(found.id)
        if document is None:
            raise RuntimeError("문서 행이 잠그는 사이에 사라졌다")
        if document.deleted_at is not None:
            if holds_source_deletion_mark(document):
                await detach_from_source_deletion(transaction, document, now)
            return
        await delete_locked_document(transaction, document, now)


def holds_source_deletion_mark(document: Document) -> bool:
    """원천과 함께 지워졌다는 표시가 남은 문서인가. 원천 되살리기 작업이 아직 되살리지 않은
    문서다."""
    return document.deleted_at is not None and document.deleted_with_source


async def detach_from_source_deletion(
    transaction: Transaction, document: Document, now: datetime
) -> None:
    """원천과 함께 지워졌다는 표시가 남은 문서의 표시를 걷고 따로 지운 문서로 만든다. 지운 시각은
    `now`로 다시 쓴다. 그 문서를 되살리지 말라는 요청(수집 API의 삭제, 동기화의 삭제 반영)이 뒤따라
    오는 원천 되살리기 작업을 막는 길이다. 부르는 쪽이 `holds_source_deletion_mark`로 표시가 있는
    문서임을 문서 행을 잠근 채 먼저 확인한다."""
    await transaction.documents.update(
        replace(document, deleted_at=now, deleted_with_source=False, modified_at=now)
    )


async def delete_locked_document(
    transaction: Transaction, document: Document, now: datetime, *, with_source: bool = False
) -> None:
    """이미 잠근, 아직 지워지지 않은 문서를 임시 삭제한다. 작업 단위 하나가 문서 하나를 지우는
    규칙이고 수집 API의 삭제와 동기화의 삭제 반영과 원천 삭제 작업이 함께 쓴다. 부르는 쪽이 문서
    행을 먼저 잠그고, 작업 행은 이 함수 뒤에 잠근다(잠금 순서). `with_source`는 원천 삭제 작업이
    준다. 원천과 함께 지워졌다는 표시를 세워, 뒤에 원천을 되살릴 때 따로 지운 문서와 가른다."""
    knowledge_bases = await transaction.catalog.list_knowledge_bases_of_group(document.group_id)
    await transaction.catalog.lock_knowledge_bases(
        [knowledge_base.id for knowledge_base in knowledge_bases], LockMode.UPDATE
    )
    await transaction.documents.update(
        replace(
            document,
            deleted_at=now,
            generation=document.generation + 1,
            modified_at=now,
            deleted_with_source=with_source,
        )
    )
    await transaction.index.archive_chunks(document.id, now)
    await transaction.index.delete_states(document.id)
    await transaction.jobs.delete_queued(document.id)
    await check_building_versions(transaction, knowledge_bases)


async def check_building_versions(
    transaction: Transaction, knowledge_bases: Sequence[KnowledgeBase]
) -> None:
    """색인 상태가 사라진 건설 중인 판마다 전환 검사를 부른다. 지식베이스 행은 잠긴 채다. 문서를
    지우는 작업 단위(삭제, 정리 작업의 원천 지우기)가 함께 쓴다."""
    for knowledge_base in knowledge_bases:
        for version in await transaction.catalog.list_live_index_versions(knowledge_base.id):
            if version.status is IndexVersionStatus.BUILDING:
                await check_version_switch(transaction, version)
