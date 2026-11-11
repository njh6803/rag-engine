"""실패한 시도를 마무리하는 자리(명세 "수집 파이프라인과 작업", 티켓 12).

일시 실패는 시도가 남아 있으면 백오프 뒤로 다시 예약하고(`reschedule`), 시도를 다 썼으면 재시도
소진으로 끝낸다(`exhaust`). 어느 갈래에도 들지 않는 예외(`internal_error`)는 같은 예외가 다시 날
것이라 다시 예약하지 않고 바로 재시도 소진으로 끝낸다. 두 작업 단위 모두 잠금 순서(문서 행, 그
문서의 그룹이 든 지식베이스 행, 작업 행)를 따르고 작업 행 조건을 본다. 조건이 어긋나면
`AttemptLostError`다.

다시 예약하는 작업 단위는 지식베이스 행을 `FOR SHARE`로 잠가 재색인 시작이 넣는 작업과 직렬화한다.
같은 문서에 다른 대기 작업이 있으면 다시 예약하지 않고 이번 오류 코드로 작업만 `failed`로 끝낸다.
그 대기 작업이 뒤에 첫째 단계부터 해 그때의 문서를 맡으므로 문서 쪽은 쓰지 않는다.

재시도 소진은 지식베이스 행을 `FOR UPDATE`로 잠가 재색인 시작이 쓴 `pending`과 작업을 보고
판정한다. 문서가 지워지지 않았고, 같은 문서를 처음부터 맡을 다른 작업이 없고, 세대가 마지막
시도가 올린 값 그대로일 때만(올린 값이 없으면 다른 작업만 본다) 지금 내용으로 색인되지 않은 살아
있는 판에서 그 문서의 조각을 지우고 색인 상태를 마지막 오류 코드로 `failed`로 쓴다. 문서 상태는
바꾸지 않는다.
"""

from collections.abc import Sequence
from uuid import UUID

from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.app.index_failure import mark_version_failed
from rag_engine.app.job_attempt import hold_attempt
from rag_engine.domain.entities import (
    Document,
    IndexStateStatus,
    IndexVersion,
    Job,
    JobStatus,
)
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.ports import JobOutcome, LockMode, Transaction


async def settle_transient_failure(
    deps: IndexDocumentDeps, job: Job, code: ErrorCode
) -> JobOutcome:
    """일시 실패한 시도를 다시 예약하거나 재시도 소진으로 끝낸다."""
    if deps.retry.is_exhausted(job.attempts):
        return await exhaust(deps, job, code)
    return await reschedule(deps, job, code)


async def reschedule(deps: IndexDocumentDeps, job: Job, code: ErrorCode) -> JobOutcome:
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.document_id)
        if document is not None:
            await _lock_knowledge_bases(transaction, document.group_id, LockMode.SHARE)
        await hold_attempt(transaction, job)
        run_after = deps.now() + deps.retry.backoff(job.attempts)
        if await transaction.jobs.reschedule(job, run_after, code):
            return JobOutcome(JobStatus.QUEUED, code)
        outcome = JobOutcome(JobStatus.FAILED, code)
        await transaction.jobs.finish(job, outcome, deps.now())
        return outcome


async def exhaust(deps: IndexDocumentDeps, job: Job, code: ErrorCode) -> JobOutcome:
    outcome = JobOutcome(JobStatus.FAILED, code)
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.document_id)
        versions: list[IndexVersion] = []
        if document is not None:
            versions = await _lock_knowledge_bases(transaction, document.group_id, LockMode.UPDATE)
        await hold_attempt(transaction, job)
        if document is not None and await _owns_failure(transaction, job, document):
            for version in versions:
                if await _is_stale(transaction, document, version):
                    await mark_version_failed(transaction, document.id, version, code, deps.now())
        await transaction.jobs.finish(job, outcome, deps.now())
    return outcome


async def _lock_knowledge_bases(
    transaction: Transaction, group_id: UUID, mode: LockMode
) -> list[IndexVersion]:
    """그 그룹이 든 지식베이스 행을 ID 순으로 잠그고, 잠근 뒤에 읽은 살아 있는 판을 낸다."""
    listed = await transaction.catalog.list_knowledge_bases_of_group(group_id)
    locked = await transaction.catalog.lock_knowledge_bases([row.id for row in listed], mode)
    return await _live_versions(transaction, [row.id for row in locked])


async def _live_versions(transaction: Transaction, ids: Sequence[UUID]) -> list[IndexVersion]:
    versions: list[IndexVersion] = []
    for knowledge_base_id in ids:
        versions.extend(await transaction.catalog.list_live_index_versions(knowledge_base_id))
    return versions


async def _owns_failure(transaction: Transaction, job: Job, document: Document) -> bool:
    """이 시도가 문서 쪽에 실패를 쓸 차례인가."""
    if document.deleted_at is not None or document.purged_at is not None:
        return False
    if await transaction.jobs.has_other_job_from_start(document.id, job.id):
        return False
    held = await transaction.jobs.get(job.id)
    raised = None if held is None else held.raised_generation
    return raised is None or raised == document.generation


async def _is_stale(transaction: Transaction, document: Document, version: IndexVersion) -> bool:
    """문서가 그 판에 지금 내용으로 색인되어 있지 않은가. 색인 상태가 `pending`이거나 없거나,
    `indexed`인데 만든 내용 해시가 문서의 내용 해시와 다르면 그렇다."""
    state = await transaction.index.get_state(document.id, version.id)
    if state is None or state.status is IndexStateStatus.PENDING:
        return True
    return (
        state.status is IndexStateStatus.INDEXED
        and state.built_content_hash != document.content_hash
    )
