"""원천 삭제의 유스케이스(source-sync 명세 "원천 삭제와 되살리기", 티켓 11).

원천을 지우는 일은 둘로 나뉜다. 요청(`request_source_deletion`)은 작업 단위 하나에서 원천 행에 지움
표시를 쓰고, 다음 실행 시각을 비우고, 대기 중인 동기화 작업을 지우고(그 동기화 기록은 `failed`와
`source_deleted`로 닫는다), 원천 삭제 작업을 넣는다. 문서 행과 조각은 고치지 않는다. 지움 표시가 선
순간부터 그 원천의 문서는 검색, 문서 조회(`get_document`), 관리 API의 문서 조회와 목록에서
지워진 문서로 읽힌다. 문서 수를 세는 자리는 문서 행의 지운 시각만 본다.

문서를 실제로 옮기는 일은 작업자가 하는 원천 삭제 작업(`delete_source_documents`)이다. 지워지지
않은 문서를 `BATCH_SIZE`건씩 묶어 묶음마다 작업 단위 하나에서 문서 삭제와 같은 일을 한다. 묶음마다
맨 먼저 원천 행을 공유 잠금으로 잡고 지움 표시를 다시 본다. 표시가 걷혀 있으면(작업을 대기열에 직접
넣었다. 지우는 요청과 복구하는 요청은 서로의 작업이 끝나기 전에는 거절되므로 그 밖의 길로는
걷히지 않지만 묶음마다 다시 본다) 아무것도 옮기지 않고 성공으로 끝난다. 작업 단위의 잠금 순서는 원천
행, 문서 행(ID 순), 지식베이스 행(ID 순), 작업 행이다. 묶음 안의 문서와 지식베이스 행을 문서마다
차례로 잠그면 다른 작업 단위(색인 작업)와 서로의 행을 기다릴 수 있어서, 문서 행을 모두 잠근 뒤
지식베이스 행을 한꺼번에 잠근다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from rag_engine.app.default_records import DEFAULT_NAME, UPLOAD_NAME
from rag_engine.app.delete_document import delete_locked_document
from rag_engine.app.job_attempt import hold_attempt
from rag_engine.app.source_lookup import (
    ensure_no_change_in_progress,
    ensure_not_deleted,
    require_source,
)
from rag_engine.app.sync_source import fail_record
from rag_engine.domain.entities import Document, Job, JobKind, JobStatus
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import JobOutcome, LockMode, Transaction, UnitOfWork

# 원천 삭제 작업이 작업 단위 하나에서 옮기는 문서 수(명세 "원천 삭제와 되살리기").
BATCH_SIZE: Final = 50

# 지울 수 없는 원천. 수집 API가 기본으로 쓰는 둘이다.
PROTECTED_SOURCE_NAMES: Final = frozenset({DEFAULT_NAME, UPLOAD_NAME})


@dataclass(frozen=True, slots=True)
class SourceDeletionRequested:
    """원천 삭제 요청의 결과. 뒤에서 문서를 옮기는 작업의 식별자다."""

    job_id: UUID


async def request_source_deletion(
    unit_of_work: UnitOfWork, name: str, *, request_id: UUID, now: datetime
) -> SourceDeletionRequested:
    """원천에 지움 표시를 쓰고 원천 삭제 작업을 넣는다. `default`와 `upload`는 409
    `source_protected`이고, 이미 지운 원천은 409 `source_deleted`이고, 원천 삭제 작업이나 원천
    복구 작업이 끝나지 않았으면 409 `source_change_in_progress`다."""
    async with unit_of_work.begin() as transaction:
        source = await require_source(transaction, name)
        if source.name in PROTECTED_SOURCE_NAMES:
            raise RequestError(ErrorCode.SOURCE_PROTECTED, "지울 수 없는 원천이다")
        ensure_not_deleted(source)
        locked = await transaction.catalog.lock_source(source.id)
        if locked is None:
            raise RuntimeError("원천 행이 잠그는 사이에 사라졌다")
        ensure_not_deleted(locked)
        await ensure_no_change_in_progress(transaction, source.id)
        await transaction.catalog.mark_source_deleted(source.id, now)
        await _drop_queued_sync(transaction, source.id, now)
        job = await transaction.jobs.enqueue_source_job(
            JobKind.DELETE_SOURCE, source.id, {}, request_id, now
        )
        if job is None:
            raise RuntimeError("지움 표시가 없는 원천에 원천 삭제 작업이 이미 있다")
        return SourceDeletionRequested(job.id)


async def _drop_queued_sync(transaction: Transaction, source_id: UUID, now: datetime) -> None:
    """대기 중인 동기화 작업을 지우고 그 동기화 기록을 `failed`와 `source_deleted`로 닫는다. 이미
    꺼내 돌고 있는 동기화는 건드리지 않는다. 그 동기화가 지움 표시를 보고 스스로 끝난다."""
    queued = await transaction.jobs.lock_queued_source_job(source_id, JobKind.SYNC_SOURCE)
    if queued is None:
        return
    await fail_record(transaction, queued, ErrorCode.SOURCE_DELETED, now)
    await transaction.jobs.delete_queued_job(queued.id)


async def delete_source_documents(unit_of_work: UnitOfWork, job: Job) -> JobOutcome:
    """원천 삭제 작업 하나를 끝까지 돌린다. 지워지지 않은 문서가 없을 때까지 묶음을 되풀이한다.
    도중에 죽으면 다른 작업자가 지워지지 않은 문서(남은 것)부터 잇는다."""
    while await _delete_batch(unit_of_work, job):
        pass
    return JobOutcome(JobStatus.SUCCEEDED, None)


async def _delete_batch(unit_of_work: UnitOfWork, job: Job) -> bool:
    """묶음 하나를 옮긴다. 더 옮길 문서가 남았을 수 있으면 참이다."""
    async with unit_of_work.begin() as transaction:
        source = await transaction.catalog.lock_source_shared(job.target_source_id)
        if source is None:
            raise RuntimeError("원천 삭제 작업이 가리키는 원천이 없다")
        deleted_at = source.deleted_at
        if deleted_at is None:
            return False
        ids = await transaction.documents.list_undeleted_ids_of_source(source.id, BATCH_SIZE)
        if not ids:
            return False
        documents = await _lock_documents(transaction, ids)
        await _lock_knowledge_bases_of(transaction, documents)
        for document in documents:
            await delete_locked_document(transaction, document, deleted_at, with_source=True)
        await hold_attempt(transaction, job)
        return True


async def _lock_documents(transaction: Transaction, ids: Sequence[UUID]) -> list[Document]:
    """문서 행을 ID 순으로 잠그고, 그 사이 지워졌거나 사라진 문서는 뺀다."""
    locked: list[Document] = []
    for document_id in ids:
        document = await transaction.documents.lock(document_id)
        if document is not None and document.deleted_at is None:
            locked.append(document)
    return locked


async def _lock_knowledge_bases_of(transaction: Transaction, documents: Sequence[Document]) -> None:
    """묶음의 문서가 든 그룹의 지식베이스 행을 ID 순으로 한꺼번에 잠근다."""
    knowledge_base_ids: set[UUID] = set()
    for group_id in {document.group_id for document in documents}:
        for knowledge_base in await transaction.catalog.list_knowledge_bases_of_group(group_id):
            knowledge_base_ids.add(knowledge_base.id)
    await transaction.catalog.lock_knowledge_bases(sorted(knowledge_base_ids), LockMode.UPDATE)
