"""내용이 같은 되살림(명세 "삭제, 되살림, 묘비", source-sync 명세 "문서 되살리기")이 조각을 되돌리는
단계. 수집 API의 같은 키 되살림(`ingest`)과 관리 API의 문서 되살리기(`restore_document`)가 함께
쓴다.

부르는 쪽이 문서 행을 먼저 잠그고(밀어 넣는 원천이면 그 앞에 원천 행을 공유 잠금으로 잡는다), 되살릴
문서(`deleted_at`을 비우고 세대와 수정 시각을 올린 것)를 준다. 이 단계가 지식베이스 행을
`FOR SHARE`로 잠그고 문서 행을 쓴다. 잠금 순서는 원천 행, 문서 행, 지식베이스 행, 작업 행이다.
"""

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from rag_engine.app.live_versions import live_index_versions
from rag_engine.domain.entities import (
    Document,
    DocumentStatus,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
)
from rag_engine.domain.ports import LockMode, Transaction


async def restore_chunks(
    transaction: Transaction, document: Document, request_id: UUID, now: datetime
) -> UUID | None:
    """대상 판은 문서의 그룹이 든 지식베이스의 살아 있는 판이다. 만든 내용 해시가 같은 보관 조각을
    대상 판의 검색 표로 되돌리고 그 판에 `indexed`를 쓴다. 보관 조각은 되돌렸든 아니든 모두 지운다.
    되돌릴 조각이 없는 대상 판이 있으면 작업을 넣고, 그 판이 건설 중인 판이 아니면 `pending`을
    쓴다(건설 중인 판에 `pending`을 쓰면 그 문서의 작업이 끝날 때까지 판이 전환되지 않을 수 있다.
    명세 "재색인 시작" 항목). 건설 중인 판에 `indexed`를 써도 전환 검사를 부르지 않는다. 그 판에
    색인 상태가 없던 문서의 `indexed` 한 행은 전환 조건(모든 색인 상태가 `indexed`나 `failed`)을
    새로 채우지 못하고, 검사는 지식베이스 행을 `FOR UPDATE`로 올려 잠가야 해서 같은 지식베이스의
    되살림끼리 서로를 기다릴 수 있다. 조각이 하나라도 돌아오면 그 조각은 같은 해시의 내용을 파싱해
    만든 것이므로 문서 상태를 `parsed`로 쓴다(갱신이 `received`로 쓴 뒤 색인 작업이 돌기 전에 지운
    문서는 작업이 지워져 상태를 고칠 작업이 없다).

    건너뜀 문서는 조각이 없어 되돌릴 것이 없다. 작업을 넣지 않고 대상 판마다 조각 0개인 `indexed`만
    다시 쓴다(건설 중인 판도 같다. source-sync 명세 "문서 되살리기"가 정한 길이다. 그래서 재색인
    도중에 되살린 건너뜀 문서는 그 재색인의 다시 보기를 받지 않고, 다음 재색인이 본다).

    문서 행은 새 원본을 가리키지 않는다. 낸 값은 넣은 작업의 식별자이고 작업이 없으면 `None`이다."""
    knowledge_bases = await transaction.catalog.list_knowledge_bases_of_group(document.group_id)
    await transaction.catalog.lock_knowledge_bases(
        [knowledge_base.id for knowledge_base in knowledge_bases], LockMode.SHARE
    )
    versions = await live_index_versions(transaction, document.group_id)
    if document.status is DocumentStatus.SKIPPED:
        await transaction.documents.update(document)
        await transaction.index.delete_archived_chunks(document.id)
        for version in versions:
            await transaction.index.save_state(_restored_state(document, version, 0, now))
        return None
    restored = await transaction.index.restore_archived_chunks(
        document, [version.id for version in versions]
    )
    if restored:
        document = replace(document, status=DocumentStatus.PARSED, skip_reason=None)
    await transaction.documents.update(document)
    await transaction.index.delete_archived_chunks(document.id)
    for version in versions:
        if version.id in restored:
            await transaction.index.save_state(
                _restored_state(document, version, restored[version.id], now)
            )
    unrestored = [version for version in versions if version.id not in restored]
    if not unrestored:
        return None
    for version in unrestored:
        if version.status is not IndexVersionStatus.BUILDING:
            await transaction.index.save_state(_pending_state(document, version, now))
    return (await transaction.jobs.enqueue(document.id, request_id, now)).id


def _restored_state(
    document: Document, version: IndexVersion, chunk_count: int, now: datetime
) -> IndexState:
    """조각이 돌아온 판(건너뜀 문서는 조각 0개)의 색인 상태다. 만든 내용 해시는 문서의 것과 같다."""
    return IndexState(
        document_id=document.id,
        index_version_id=version.id,
        status=IndexStateStatus.INDEXED,
        chunk_count=chunk_count,
        built_content_hash=document.content_hash,
        error_code=None,
        updated_at=now,
    )


def _pending_state(document: Document, version: IndexVersion, now: datetime) -> IndexState:
    return IndexState(
        document_id=document.id,
        index_version_id=version.id,
        status=IndexStateStatus.PENDING,
        chunk_count=0,
        built_content_hash=None,
        error_code=None,
        updated_at=now,
    )
