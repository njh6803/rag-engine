"""지운 문서의 되살림 본체(core 명세 "삭제, 되살림, 묘비", source-sync 명세 "원천 삭제와 되살리기").

수집이 같은 키로 돌아온 지운 문서를 되살릴 때(`ingest._restore`)와 원천 되살리기 작업이 원천과 함께
지워진 문서를 되살릴 때(`restore_source`)가 함께 쓴다. 두 쪽 모두 문서 행을 먼저 잠근 채 부른다.

대상 판은 문서의 그룹이 든 지식베이스의 살아 있는 판(현재 판과 건설 중인 판)이다. 삭제 보관함의 조각
가운데 대상 판의 것이면서 만든 내용 해시가 문서의 내용 해시와 같은 것만 검색 표로 되돌리고 그 판에
`indexed`를 쓴다. 보관 조각은 되돌렸든 아니든 모두 지운다. 되돌릴 조각이 없는 대상 판이 있으면(지운
뒤에 색인 판이 바뀌었거나, 지우기 전에 바뀐 내용이 아직 색인되지 않았다) 색인 작업을 넣는다. 그
판이 건설 중인 판이 아니면 `pending`도 쓴다. 건설 중인 판에 `pending`을 쓰면 그 문서의 작업이 끝날
때까지 판이 전환되지 않을 수 있다(명세 "재색인 시작" 항목).

건설 중인 판에 `indexed`를 써도 전환 검사를 부르지 않는다. 그 판에 색인 상태가 없던 문서의 `indexed`
한 행은 전환 조건(모든 색인 상태가 `indexed`나 `failed`)을 새로 채우지 못하고, 검사는 지식베이스
행을 `FOR UPDATE`로 올려 잠가야 해서 같은 지식베이스의 되살림끼리 서로를 기다릴 수 있다.

건너뜀 문서(`skipped`)는 조각이 없다. 대상 판마다 색인 상태 `indexed`(조각 0개)만 다시 쓰고 작업은
넣지 않는다(`restore_locked_document`).
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
    """내용이 같은 되살림이다. `document`는 되살린 값(지운 시각이 비고, 세대를 올렸고, 요청의 그룹과
    값을 담았다)이고 이 함수가 문서 행에 쓴다. 조각이 하나라도 돌아오면 그 조각은 같은 해시의 내용을
    파싱해 만든 것이므로 문서 상태를 `parsed`로 쓴다(갱신이 `received`로 쓴 뒤 색인 작업이 돌기 전에
    지운 문서는 작업이 지워져 상태를 고칠 작업이 없다). 넣은 색인 작업의 식별자를 낸다. 작업을 넣지
    않았으면 `None`이다."""
    await _lock_knowledge_bases_of(transaction, document.group_id)
    versions = await live_index_versions(transaction, document.group_id)
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


async def restore_locked_document(
    transaction: Transaction, deleted: Document, request_id: UUID, now: datetime
) -> UUID | None:
    """이미 잠근, 지운 문서를 문서 행의 그룹과 내용 그대로 되살린다. 지운 시각과 원천과 함께
    지워졌다는 표시를 비우고 세대를 올린다. 건너뜀 문서는 대상 판마다 색인 상태만 다시 쓰고 작업을
    넣지 않는다. 그 밖의 문서는 `restore_chunks`다."""
    revived = replace(
        deleted,
        deleted_at=None,
        deleted_with_source=False,
        generation=deleted.generation + 1,
        modified_at=now,
    )
    if revived.status is not DocumentStatus.SKIPPED:
        return await restore_chunks(transaction, revived, request_id, now)
    await _lock_knowledge_bases_of(transaction, revived.group_id)
    await transaction.documents.update(revived)
    await transaction.index.delete_archived_chunks(revived.id)
    for version in await live_index_versions(transaction, revived.group_id):
        await transaction.index.save_state(_restored_state(revived, version, 0, now))
    return None


async def _lock_knowledge_bases_of(transaction: Transaction, group_id: UUID) -> None:
    """문서가 드는 지식베이스 행을 ID 순으로 `FOR SHARE`로 잠근다. 같은 작업 단위가 이미 잡은
    잠금이면 그대로다."""
    knowledge_bases = await transaction.catalog.list_knowledge_bases_of_group(group_id)
    await transaction.catalog.lock_knowledge_bases(
        sorted(knowledge_base.id for knowledge_base in knowledge_bases), LockMode.SHARE
    )


def _restored_state(
    document: Document, version: IndexVersion, chunk_count: int, now: datetime
) -> IndexState:
    """보관 조각이 돌아온 판의 색인 상태다. 돌아온 조각이 만든 내용 해시는 문서의 것과 같다."""
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
