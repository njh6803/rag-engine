"""원천 되살리기의 유스케이스(source-sync 명세 "원천 삭제와 되살리기", 티켓 12).

원천을 되살리는 일은 둘로 나뉜다. 요청은 작업 단위 하나에서 원천 행을 잠그고 지움 표시를 걷고,
다음 실행 시각을 다시 채우고, 원천 되살리기 작업을 넣는다. 표시를 걷은 순간부터 그 원천은 다시
수집과 동기화를 받는다. 문서는 작업자가 되살리는 대로 검색에 돌아온다. 가져오는 원천은 같은 검사와
적용 사이에 폴더 겹침 확인을 끼워야 해서 `PullSources.restore`가 `lock_restorable_source`와
`apply_restoration`을 따로 부른다.

거절하는 경우는 순서대로 셋이다. 지워지지 않은 원천은 409 `source_not_deleted`, 보관 기간
(`RAG_DELETED_RETENTION_DAYS`)이 지난 지운 원천은 정리 작업이 아직 지우지 않았어도 409
`source_retention_expired`, 그 원천의 원천 삭제 작업이나 원천 되살리기 작업이 대기 중이거나 실행
중이면 409 `source_change_in_progress`다(지우는 요청도 같다. 두 작업이 같은 원천의 문서를 서로
반대쪽으로 옮기지 않게 한다). 작업이 재시도를 다 쓰고 실패로 끝난 뒤에는 요청을 받는다.

문서를 되살리는 일은 작업자가 하는 원천 되살리기 작업(`restore_source_documents`)이다. 원천과 함께
지워졌다는 표시가 있는 문서를 `BATCH_SIZE`건씩 묶어 묶음마다 작업 단위 하나에서 되살린다. 묶음마다
맨 먼저 원천 행을 공유 잠금으로 잡고 지움 표시가 없는지 다시 본다. 표시가 서 있으면(작업을
대기열에 직접 넣었다. 지우는 요청과 되살리는 요청은 서로의 작업이 끝나기 전에는 거절되므로 그 밖의
길로는 서지 않지만 묶음마다 다시 본다) 아무것도 되살리지 않고 성공으로 끝난다. 문서를 모두
되살린 뒤에는 그 원천의 지워지지 않은 문서 가운데 색인이 멈춘 문서에 색인 작업을 넣는다. 원천 삭제
작업이 재시도를 다 쓰고 실패로 끝난 원천을 되살리면 지움 표시가 선 동안 색인 작업이 아무것도 쓰지
않고 끝난 문서가 남아 있고, 이 단계가 그 문서를 다시 잇는다. 작업 단위의 잠금 순서는 원천 행, 문서
행(ID 순), 지식베이스 행(ID 순), 작업 행이다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from rag_engine.app.job_attempt import hold_attempt
from rag_engine.app.restore_chunks import restore_locked_document
from rag_engine.app.source_lookup import (
    ensure_no_change_in_progress,
    require_source,
)
from rag_engine.domain.entities import Document, Job, JobKind, JobStatus, Source, SourceKind
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import JobOutcome, LockMode, Transaction, UnitOfWork

# 원천 되살리기 작업이 작업 단위 하나에서 되살리는 문서 수(명세 "원천 삭제와 되살리기").
BATCH_SIZE: Final = 50


@dataclass(frozen=True, slots=True)
class SourceRestorationRequested:
    """원천 되살리기 요청의 결과. 뒤에서 문서를 되살리는 작업의 식별자다."""

    job_id: UUID


async def source_kind_of(unit_of_work: UnitOfWork, name: str) -> SourceKind:
    """이름의 원천의 갈래. 없는 이름은 404 `source_not_found`다. 되살리기 경로가 갈래로 길을
    가른다."""
    async with unit_of_work.begin() as transaction:
        return (await require_source(transaction, name)).kind


async def request_source_restoration(
    unit_of_work: UnitOfWork,
    name: str,
    *,
    request_id: UUID,
    now: datetime,
    retention_days: int,
) -> SourceRestorationRequested:
    """밀어 넣는 원천의 지움 표시를 걷고 원천 되살리기 작업을 넣는다."""
    async with unit_of_work.begin() as transaction:
        source = await lock_restorable_source(
            transaction, name, now=now, retention_days=retention_days
        )
        return await apply_restoration(
            transaction, source, next_run_at=None, request_id=request_id, now=now
        )


async def lock_restorable_source(
    transaction: Transaction, name: str, *, now: datetime, retention_days: int
) -> Source:
    """원천 행을 잠그고 되살릴 수 있는지 본다. 잠근 뒤의 원천을 낸다. 지워지지 않았으면 409
    `source_not_deleted`, 보관 기간이 지났으면 409 `source_retention_expired`, 원천 삭제 작업이나
    원천 되살리기 작업이 끝나지 않았으면 409 `source_change_in_progress`다. 이름으로 읽은 뒤 잠그기
    전에 정리 작업이 그 원천을 지웠으면 404 `source_not_found`다."""
    source = await require_source(transaction, name)
    locked = await transaction.catalog.lock_source(source.id)
    if locked is None:
        raise RequestError(ErrorCode.SOURCE_NOT_FOUND, "그 이름의 원천이 없다")
    if locked.deleted_at is None:
        raise RequestError(ErrorCode.SOURCE_NOT_DELETED, "지워지지 않은 원천이다")
    if locked.deleted_at + timedelta(days=retention_days) <= now:
        raise RequestError(ErrorCode.SOURCE_RETENTION_EXPIRED, "보관 기간이 지나 되살릴 수 없다")
    await ensure_no_change_in_progress(transaction, locked.id)
    return locked


async def apply_restoration(
    transaction: Transaction,
    source: Source,
    *,
    next_run_at: datetime | None,
    request_id: UUID,
    now: datetime,
) -> SourceRestorationRequested:
    """`lock_restorable_source`가 낸 원천의 지움 표시를 걷고 다음 실행 시각을 쓰고 원천 되살리기
    작업을 넣는다."""
    await transaction.catalog.mark_source_restored(source.id, next_run_at)
    job = await transaction.jobs.enqueue_source_job(
        JobKind.RESTORE_SOURCE, source.id, {}, request_id, now
    )
    if job is None:
        raise RuntimeError("원천 되살리기 작업이 이미 있는데 되살리기 요청이 지나갔다")
    return SourceRestorationRequested(job.id)


async def restore_source_documents(
    unit_of_work: UnitOfWork, job: Job, now: Callable[[], datetime]
) -> JobOutcome:
    """원천 되살리기 작업 하나를 끝까지 돌린다. 표시가 남은 문서가 없을 때까지 묶음을 되풀이하고,
    이어서 색인이 멈춘 문서에 색인 작업을 넣는다. 도중에 죽으면 다른 작업자가 남은 것부터
    잇는다. 이미 되살린 문서는 표시가 없어 다시 고르지 않는다."""
    while await _restore_batch(unit_of_work, job, now):
        pass
    while await _requeue_stalled(unit_of_work, job, now):
        pass
    return JobOutcome(JobStatus.SUCCEEDED, None)


async def _restore_batch(unit_of_work: UnitOfWork, job: Job, now: Callable[[], datetime]) -> bool:
    """묶음 하나를 되살린다. 더 되살릴 문서가 남았을 수 있으면 참이다."""
    async with unit_of_work.begin() as transaction:
        source = await transaction.catalog.lock_source_shared(job.target_source_id)
        if source is None:
            raise RuntimeError("원천 되살리기 작업이 가리키는 원천이 없다")
        if source.deleted_at is not None:
            return False
        ids = await transaction.documents.list_ids_deleted_with_source(source.id, BATCH_SIZE)
        if not ids:
            return False
        documents = await _lock_deleted_with_source(transaction, ids)
        if not documents:
            return True
        await _lock_knowledge_bases_of(transaction, documents)
        moment = now()
        for document in documents:
            await restore_locked_document(transaction, document, job.request_id, moment)
        await hold_attempt(transaction, job)
        return True


async def _requeue_stalled(unit_of_work: UnitOfWork, job: Job, now: Callable[[], datetime]) -> bool:
    """색인이 멈춘 문서 한 묶음에 색인 작업을 넣는다. 더 있을 수 있으면 참이다."""
    async with unit_of_work.begin() as transaction:
        source = await transaction.catalog.lock_source_shared(job.target_source_id)
        if source is None:
            raise RuntimeError("원천 되살리기 작업이 가리키는 원천이 없다")
        if source.deleted_at is not None:
            return False
        ids = await transaction.documents.list_stalled_ids_of_source(source.id, BATCH_SIZE)
        if not ids:
            return False
        documents = await _lock_live(transaction, ids)
        await _lock_knowledge_bases_of(transaction, documents)
        moment = now()
        for document in documents:
            # 읽은 뒤에 다른 요청이 색인 작업을 넣었을 수 있다. 문서 행을 잠근 채 다시 본다.
            if not await transaction.jobs.has_active_job(document.id):
                await transaction.jobs.enqueue(document.id, job.request_id, moment)
        await hold_attempt(transaction, job)
        return True


async def _lock_deleted_with_source(
    transaction: Transaction, ids: Sequence[UUID]
) -> list[Document]:
    """문서 행을 ID 순으로 잠그고, 그 사이 되살아났거나 따로 지운 문서(표시가 걷힌 것)는 뺀다."""
    locked: list[Document] = []
    for document_id in ids:
        document = await transaction.documents.lock(document_id)
        if (
            document is not None
            and document.deleted_at is not None
            and document.deleted_with_source
        ):
            locked.append(document)
    return locked


async def _lock_live(transaction: Transaction, ids: Sequence[UUID]) -> list[Document]:
    """문서 행을 ID 순으로 잠그고, 그 사이 지워진 문서는 뺀다."""
    locked: list[Document] = []
    for document_id in ids:
        document = await transaction.documents.lock(document_id)
        if document is not None and document.deleted_at is None:
            locked.append(document)
    return locked


async def _lock_knowledge_bases_of(transaction: Transaction, documents: Sequence[Document]) -> None:
    """묶음의 문서가 든 그룹의 지식베이스 행을 ID 순으로 한꺼번에 `FOR SHARE`로 잠근다. 문서마다
    차례로 잠그면 다른 작업 단위와 서로의 행을 기다릴 수 있다."""
    knowledge_base_ids: set[UUID] = set()
    for group_id in {document.group_id for document in documents}:
        for knowledge_base in await transaction.catalog.list_knowledge_bases_of_group(group_id):
            knowledge_base_ids.add(knowledge_base.id)
    await transaction.catalog.lock_knowledge_bases(sorted(knowledge_base_ids), LockMode.SHARE)
