"""정리 작업의 유스케이스(source-sync 명세 "정리 작업", 티켓 14, ADR 0022).

작업자가 하루에 한 번 돌리는 작업(`cleanup`) 하나가 다섯 단계를 차례로 마친다.

1. 보관 기간(`RAG_DELETED_RETENTION_DAYS`)이 지난 임시 삭제 문서를 `BATCH_SIZE`건씩 작업 단위
   하나에서 완전히 지운다. 문서 행을 잠그고 아직 지워져 있고 기간이 지났는지 다시 본 뒤 삭제
   보관함의 조각과 파싱 결과를 지우고, 원본 경로를 비우고 완전히 지운 시각을 적는다(그 행이 삭제
   기록으로 남는다). 원천과 함께 지워졌다는 표시가 있는 문서는 건드리지 않는다. 원천을 되살리면
   작업자가 되살리고, 원천을 지우면 둘째 단계가 함께 지운다. 원본 파일은 그 작업 단위를 커밋한
   뒤에 지운다.
2. 보관 기간이 지난 지운 원천을 지운다. 원천 행을 잠그고 그 원천의 문서(삭제 기록 행까지)를
   `BATCH_SIZE`건씩 지운 뒤, 마지막 묶음과 같은 작업 단위에서 그 원천의 작업, 동기화 기록, 원천
   행을 지운다. 이름은 그때부터 다시 쓸 수 있다. 되살리는 요청이 그사이 끼어들면 원천 행 잠금이
   차례를 정한다. 원천 삭제 작업이 멈춰 지워지지 않은 문서가 남았어도 같이 지우므로, 그 문서의
   색인 상태가 사라져 판이 전환될 수 있는 건설 중인 판마다 전환 검사를 부른다.
3. 어느 문서 행도 가리키지 않고 쓴 지 24시간이 지난 원본 파일을 치운다. 데이터 폴더의 원본
   폴더(`blobs/`) 아래만 훑는다. 서버 폴더(`RAG_SOURCES_DIR`)와 그 밖의 파일은 건드리지 않는다.
4. 끝난 지 `RAG_SYNC_RECORD_RETENTION_DAYS`가 지난 동기화 기록을 지운다. 끝나지 않은 기록과
   원천마다 가장 최근 기록 하나는 남긴다.
5. 재시도를 다 쓰고 멈춘 원천 삭제 작업과 원천 되살리기 작업을 다시 넣는다. 지운 원천은 지워지지
   않은 문서가 남았을 때, 지우지 않은 원천은 원천과 함께 지워졌다는 표시가 남은 문서가 있거나
   가장 나중 원천 되살리기 작업이 실패로 끝났을 때다. 대기 중이거나 실행 중인 작업이 있으면 넣지
   않는다.

작업 단위의 잠금 순서는 원천 행, 문서 행(ID 순), 지식베이스 행(ID 순), 작업 행이다. 쓰는 작업
단위는 끝에서 `hold_attempt`로 작업 담당 기록을 잃지 않았는지 보고, 잃었으면 그 작업 단위를
롤백한다. 정리 작업의 뒤 단계는 앞 단계가 끝나야 의미가 있어서 단계 사이에는 작업 단위를 이어
쓰지 않는다. 한 단계가 일시 실패로 멈추면 작업이 다시 예약되고, 이미 끝낸 묶음은 다시 고르지
않는다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Final
from uuid import UUID

from rag_engine.app.delete_document import check_building_versions
from rag_engine.app.job_attempt import hold_attempt
from rag_engine.domain.entities import Document, Job, JobKind, JobStatus, KnowledgeBase
from rag_engine.domain.errors import TransientFailure
from rag_engine.domain.ports import BlobStore, LockMode, Transaction, UnitOfWork

# 작업 단위 하나에서 지우는 문서 수(명세 "정리 작업").
BATCH_SIZE: Final = 50
# 동기화 기록은 가벼운 행이라 한 번에 더 많이 지운다.
_RECORD_BATCH_SIZE: Final = 500
# 원본이 쓰인 뒤 문서 행이 가리키기까지 기다려 주는 시간(수집 요청이 원본을 쓰고 커밋하는 사이).
_ORPHAN_GRACE: Final = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class CleanupDeps:
    """정리 작업이 부르는 포트와 시계, 보관 기간(날수)."""

    unit_of_work: UnitOfWork
    blob_store: BlobStore
    now: Callable[[], datetime]
    deleted_retention_days: int
    sync_record_retention_days: int


@dataclass(frozen=True, slots=True)
class CleanupCounts:
    """정리 작업이 한 일의 수. 작업자 로그가 싣는다. 둘째 단계가 원천과 함께 지운 문서는
    `documents_purged`에 세지 않는다."""

    documents_purged: int
    sources_purged: int
    blobs_removed: int
    sync_records_deleted: int
    jobs_requeued: int


class _Batch(Enum):
    """원천을 지우는 작업 단위 하나의 끝. `MORE`는 문서가 더 남았을 수 있고, `DONE`은 원천 행까지
    지웠고, `RACED`는 그사이 원천이 되살아났거나 사라진 것이다."""

    MORE = auto()
    DONE = auto()
    RACED = auto()


async def run_cleanup(deps: CleanupDeps, job: Job) -> CleanupCounts:
    """다섯 단계를 차례로 돌려 한 일의 수를 낸다. 작업 담당 기록을 잃으면 `AttemptLostError`를
    올린다."""
    documents_purged = await _purge_documents(deps, job)
    sources_purged = await _purge_sources(deps, job)
    blobs_removed = await _sweep_orphan_blobs(deps)
    sync_records_deleted = await _delete_old_sync_records(deps, job)
    jobs_requeued = await _requeue_stalled_jobs(deps, job)
    return CleanupCounts(
        documents_purged=documents_purged,
        sources_purged=sources_purged,
        blobs_removed=blobs_removed,
        sync_records_deleted=sync_records_deleted,
        jobs_requeued=jobs_requeued,
    )


# 첫째 단계 ---------------------------------------------------------------------------------


async def _purge_documents(deps: CleanupDeps, job: Job) -> int:
    cutoff = deps.now() - timedelta(days=deps.deleted_retention_days)
    purged = 0
    while True:
        batch = await _purge_document_batch(deps, job, cutoff)
        if batch == 0:
            return purged
        purged += batch


async def _purge_document_batch(deps: CleanupDeps, job: Job, cutoff: datetime) -> int:
    """묶음 하나를 지우고 지운 수를 낸다. 고른 문서가 모두 그사이 되살아났으면 0이다."""
    async with deps.unit_of_work.begin() as transaction:
        ids = await transaction.documents.list_purgeable_ids(cutoff, BATCH_SIZE)
        documents = await _lock_documents(
            transaction, ids, keep=lambda document: _is_purgeable(document, cutoff)
        )
        if not documents:
            return 0
        for document in documents:
            await transaction.index.delete_archived_chunks(document.id)
            await transaction.documents.purge(document, deps.now())
        await hold_attempt(transaction, job)
        paths = _blob_paths(documents)
    await _remove_blobs(deps.blob_store, paths)
    return len(documents)


def _is_purgeable(document: Document, cutoff: datetime) -> bool:
    """잠근 뒤에 다시 보는 조건. 고른 뒤에 되살아났거나 원천과 함께 지워졌다고 표시된 문서는
    지우지 않는다."""
    return (
        document.deleted_at is not None
        and document.deleted_at <= cutoff
        and document.purged_at is None
        and not document.deleted_with_source
    )


# 둘째 단계 ---------------------------------------------------------------------------------


async def _purge_sources(deps: CleanupDeps, job: Job) -> int:
    cutoff = deps.now() - timedelta(days=deps.deleted_retention_days)
    purged = 0
    while True:
        async with deps.unit_of_work.begin() as transaction:
            ids = await transaction.catalog.list_purgeable_source_ids(cutoff, 1)
        if not ids:
            return purged
        if await _purge_source(deps, job, ids[0], cutoff):
            purged += 1


async def _purge_source(deps: CleanupDeps, job: Job, source_id: UUID, cutoff: datetime) -> bool:
    """원천 하나를 끝까지 지운다. 지웠으면 참이다. 그사이 되살아났거나 사라졌으면 거짓이고, 그
    원천은 다음에 고르지 않는다."""
    while True:
        batch = await _purge_source_batch(deps, job, source_id, cutoff)
        if batch is not _Batch.MORE:
            return batch is _Batch.DONE


async def _purge_source_batch(
    deps: CleanupDeps, job: Job, source_id: UUID, cutoff: datetime
) -> _Batch:
    async with deps.unit_of_work.begin() as transaction:
        source = await transaction.catalog.lock_source(source_id)
        if source is None or source.deleted_at is None or source.deleted_at > cutoff:
            return _Batch.RACED
        ids = await transaction.documents.list_ids_of_source(source_id, BATCH_SIZE)
        documents = await _lock_documents(transaction, ids)
        live = [document for document in documents if document.deleted_at is None]
        knowledge_bases = await _lock_knowledge_bases_of(transaction, live)
        for document in documents:
            await transaction.index.delete_chunks(document.id, None)
            await transaction.index.delete_archived_chunks(document.id)
            await transaction.index.delete_states(document.id)
        document_ids = [document.id for document in documents]
        await transaction.jobs.delete_jobs_of_documents(document_ids)
        await transaction.documents.delete_documents(document_ids)
        await check_building_versions(transaction, knowledge_bases)
        last = len(ids) < BATCH_SIZE
        if last:
            # 마지막 묶음과 같은 작업 단위에서 원천 행까지 지운다. 문서 행이 커밋 전까지 보이는
            # 동안 끼어든 요청은 원천 행 잠금에서 기다리다 사라진 원천을 본다.
            await transaction.jobs.delete_jobs_of_source(source_id)
            await transaction.sync_records.delete_of_source(source_id)
            await transaction.catalog.delete_source(source_id)
        await hold_attempt(transaction, job)
        paths = _blob_paths(documents)
    await _remove_blobs(deps.blob_store, paths)
    return _Batch.DONE if last else _Batch.MORE


# 셋째 단계 ---------------------------------------------------------------------------------


async def _sweep_orphan_blobs(deps: CleanupDeps) -> int:
    written = await deps.blob_store.list_written_before(deps.now() - _ORPHAN_GRACE)
    if not written:
        return 0
    async with deps.unit_of_work.begin() as transaction:
        referenced = await transaction.documents.referenced_blob_paths(written)
    removed = 0
    for path in written:
        if path not in referenced and await _remove_blob(deps.blob_store, path):
            removed += 1
    return removed


# 넷째 단계 ---------------------------------------------------------------------------------


async def _delete_old_sync_records(deps: CleanupDeps, job: Job) -> int:
    cutoff = deps.now() - timedelta(days=deps.sync_record_retention_days)
    total = 0
    while True:
        async with deps.unit_of_work.begin() as transaction:
            deleted = await transaction.sync_records.delete_finished_before(
                cutoff, _RECORD_BATCH_SIZE
            )
            if deleted > 0:
                await hold_attempt(transaction, job)
        total += deleted
        if deleted < _RECORD_BATCH_SIZE:
            return total


# 다섯째 단계 -------------------------------------------------------------------------------


async def _requeue_stalled_jobs(deps: CleanupDeps, job: Job) -> int:
    async with deps.unit_of_work.begin() as transaction:
        sources = await transaction.catalog.list_sources()
    requeued = 0
    for source in sources:
        if await _requeue_if_stalled(deps, job, source.id):
            requeued += 1
    return requeued


async def _requeue_if_stalled(deps: CleanupDeps, job: Job, source_id: UUID) -> bool:
    """원천 하나의 멈춘 작업을 다시 넣었으면 참이다. 원천 행을 잠가 지우는 요청과 되살리는
    요청이 끼어들지 못하게 한다."""
    async with deps.unit_of_work.begin() as transaction:
        source = await transaction.catalog.lock_source(source_id)
        if source is None:
            return False
        if source.deleted_at is not None:
            kind = JobKind.DELETE_SOURCE
            stalled = await transaction.documents.has_undeleted_documents(source.id)
        else:
            kind = JobKind.RESTORE_SOURCE
            stalled = await transaction.documents.has_documents_deleted_with_source(
                source.id
            ) or await _last_job_failed(transaction, source.id, kind)
        if not stalled:
            return False
        # 대기 중이거나 실행 중인 작업이 있으면 `enqueue_source_job`이 넣지 않고 `None`을 낸다.
        queued = await transaction.jobs.enqueue_source_job(
            kind, source.id, {}, job.request_id, deps.now()
        )
        if queued is None:
            return False
        await hold_attempt(transaction, job)
        return True


async def _last_job_failed(transaction: Transaction, source_id: UUID, kind: JobKind) -> bool:
    """그 원천의 그 종류 작업 가운데 가장 나중에 만든 것이 재시도를 다 쓰고 실패로 끝났는가. 문서를
    모두 되살린 뒤 색인이 멈춘 문서를 잇는 단계에서 실패한 작업은 표시가 남은 문서가 없어 이것으로
    찾는다."""
    latest = await transaction.jobs.latest_source_job(source_id, kind)
    return latest is not None and latest.status is JobStatus.FAILED


# 함께 쓰는 것 ------------------------------------------------------------------------------


async def _lock_documents(
    transaction: Transaction,
    ids: Sequence[UUID],
    *,
    keep: Callable[[Document], bool] | None = None,
) -> list[Document]:
    """문서 행을 ID 순으로 잠그고, 그사이 사라졌거나 `keep`을 지나지 못한 문서는 뺀다."""
    locked: list[Document] = []
    for document_id in ids:
        document = await transaction.documents.lock(document_id)
        if document is not None and (keep is None or keep(document)):
            locked.append(document)
    return locked


async def _lock_knowledge_bases_of(
    transaction: Transaction, documents: Sequence[Document]
) -> list[KnowledgeBase]:
    """문서가 든 그룹의 지식베이스 행을 ID 순으로 한꺼번에 `FOR UPDATE`로 잠그고 낸다. 문서마다
    차례로 잠그면 다른 작업 단위와 서로의 행을 기다릴 수 있다."""
    found: dict[UUID, KnowledgeBase] = {}
    for group_id in {document.group_id for document in documents}:
        for knowledge_base in await transaction.catalog.list_knowledge_bases_of_group(group_id):
            found[knowledge_base.id] = knowledge_base
    ordered = [found[knowledge_base_id] for knowledge_base_id in sorted(found)]
    await transaction.catalog.lock_knowledge_bases(
        [knowledge_base.id for knowledge_base in ordered], LockMode.UPDATE
    )
    return ordered


def _blob_paths(documents: Sequence[Document]) -> list[str]:
    return [document.blob_path for document in documents if document.blob_path is not None]


async def _remove_blobs(blob_store: BlobStore, paths: Sequence[str]) -> None:
    for path in paths:
        await _remove_blob(blob_store, path)


async def _remove_blob(blob_store: BlobStore, path: str) -> bool:
    """원본 하나를 지운다. 지우지 못해도(일시 실패) 정리 작업은 이어 간다. 문서 행은 이미 그
    경로를 비웠으므로, 남은 파일은 셋째 단계가 묵은 주인 없는 원본으로 치운다."""
    try:
        await blob_store.delete(path)
    except TransientFailure:
        return False
    return True
