"""`ingest --wait`의 기다림(명세 "관리 명령", 스토리 9).

넣은 문서마다 그 문서의 대기·실행 중인 작업이 없어질 때까지 폴링하고, 그때 색인이 실패한 문서를
낸다. 작업이 없는 `unchanged`·`restored`의 문서도 센다. 앞서 넣은 작업이 아직 돌 수 있기 때문이다.
넣은 작업의 상태로 판정하지 않는다. 작업의 상태는 문서의 결과가 아니어서(수집 파이프라인의 넷째
단계) 넣은 작업이 세대 대조에 걸려 `succeeded`로 끝나도 같은 문서의 뒤 작업이 실패할 수 있고,
`failed`로 끝나도 뒤 작업이 문서를 색인할 수 있다. 판정은 수집의 `requeued` 조건과 같다
(`index_failure_code`). 그사이 지워진 문서나 없는 문서는 끝난 것으로 보고 실패로 세지 않는다.

잠과 시계는 호출하는 쪽이 건넨다. 시험이 폴링 사이에 작업자를 돌린다.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from uuid import UUID

from rag_engine.app.document_outcome import index_failure_code
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.ports import Transaction, UnitOfWork


class WaitStatus(Enum):
    FINISHED = auto()
    TIMED_OUT = auto()


@dataclass(frozen=True, slots=True)
class FailedDocument:
    document_id: UUID
    error_code: ErrorCode


@dataclass(frozen=True, slots=True)
class WaitResult:
    """`failed`는 시간 초과로 돌아와도 그때까지 끝난 문서의 실패를 든다."""

    status: WaitStatus
    failed: tuple[FailedDocument, ...]


async def wait_for_documents(
    unit_of_work: UnitOfWork,
    document_ids: Sequence[UUID],
    *,
    poll_seconds: float,
    timeout_seconds: float,
    sleep: Callable[[float], Awaitable[None]],
    monotonic: Callable[[], float],
) -> WaitResult:
    """`timeout_seconds`가 0이면 끝날 때까지 기다린다."""
    deadline = None if timeout_seconds <= 0 else monotonic() + timeout_seconds
    pending = list(dict.fromkeys(document_ids))
    failed: list[FailedDocument] = []
    while True:
        pending, newly_failed = await _poll(unit_of_work, pending)
        failed.extend(newly_failed)
        if not pending:
            return WaitResult(WaitStatus.FINISHED, tuple(failed))
        pause = poll_seconds
        if deadline is not None:
            remaining = deadline - monotonic()
            if remaining <= 0:
                return WaitResult(WaitStatus.TIMED_OUT, tuple(failed))
            pause = min(poll_seconds, remaining)
        await sleep(pause)


async def _poll(
    unit_of_work: UnitOfWork, pending: Sequence[UUID]
) -> tuple[list[UUID], list[FailedDocument]]:
    """아직 작업이 남은 문서와, 이번에 끝난 문서 가운데 색인이 실패한 문서를 낸다."""
    still_running: list[UUID] = []
    failed: list[FailedDocument] = []
    async with unit_of_work.begin() as transaction:
        for document_id in pending:
            if await _is_busy(transaction, document_id):
                still_running.append(document_id)
                continue
            failure = await _failure(transaction, document_id)
            if failure is not None:
                failed.append(failure)
    return still_running, failed


async def _is_busy(transaction: Transaction, document_id: UUID) -> bool:
    document = await transaction.documents.get(document_id)
    if document is None or document.deleted_at is not None:
        return False
    return await transaction.jobs.has_active_job(document_id)


async def _failure(transaction: Transaction, document_id: UUID) -> FailedDocument | None:
    document = await transaction.documents.get(document_id)
    if document is None or document.deleted_at is not None:
        return None
    code = await index_failure_code(transaction, document)
    return None if code is None else FailedDocument(document_id, code)
