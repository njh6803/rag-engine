"""요청이 가리킨 원천을 찾는다(source-sync 명세 "수집 API", "관리 API"). 이름을 주지 않은 요청은
기본 원천 `default`다. 없는 이름은 404 `source_not_found`이고, 이름을 주지 않았는데 `default`가
없으면 `migrate`를 돌리지 않은 설치라 요청의 잘못이 아니다."""

from uuid import UUID

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.domain.entities import JobKind, Source, SourceKind
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.ports import Transaction


async def require_source(transaction: Transaction, name: str | None) -> Source:
    source = await transaction.catalog.get_source(DEFAULT_NAME if name is None else name)
    if source is not None:
        return source
    if name is None:
        raise RuntimeError("기본 원천이 없다. migrate를 돌려야 한다")
    raise RequestError(ErrorCode.SOURCE_NOT_FOUND, "그 이름의 원천이 없다")


def ensure_not_deleted(source: Source) -> None:
    """지움 표시가 선 원천이면 409 `source_deleted`다."""
    if source.deleted_at is not None:
        raise RequestError(ErrorCode.SOURCE_DELETED, "지운 원천이다")


async def require_push_source(transaction: Transaction, name: str | None) -> Source:
    """수집 API가 가리킨 원천. 가져오는 원천에는 넣거나 지울 수 없어 409 `wrong_source_kind`이고,
    지운 원천은 409 `source_deleted`다."""
    source = await require_source(transaction, name)
    ensure_not_deleted(source)
    if source.kind is not SourceKind.PUSH:
        raise RequestError(ErrorCode.WRONG_SOURCE_KIND, "밀어 넣는 원천이 아니다")
    return source


async def require_pull_source(transaction: Transaction, name: str) -> Source:
    """관리 API의 고치기, 연결 확인, 지금 동기화, 일시 중지, 다시 시작이 가리킨 원천. 밀어 넣는
    원천이면 409 `wrong_source_kind`이고, 지운 원천은 409 `source_deleted`다."""
    source = await require_source(transaction, name)
    ensure_not_deleted(source)
    if source.kind is not SourceKind.PULL:
        raise RequestError(ErrorCode.WRONG_SOURCE_KIND, "가져오는 원천이 아니다")
    return source


async def ensure_no_change_in_progress(transaction: Transaction, source_id: UUID) -> None:
    """원천 삭제 작업이나 원천 되살리기 작업이 대기 중이거나 실행 중이면 409
    `source_change_in_progress`다. 지우는 요청과 되살리는 요청이 원천 행을 잠근 뒤에 부른다. 두
    작업이 같은 원천의 문서를 서로 반대쪽으로 옮기지 못하게 한다."""
    busy = await transaction.jobs.has_active_source_job(
        source_id, (JobKind.DELETE_SOURCE, JobKind.RESTORE_SOURCE)
    )
    if busy:
        raise RequestError(
            ErrorCode.SOURCE_CHANGE_IN_PROGRESS,
            "원천을 지우거나 되살리는 작업이 아직 끝나지 않았다",
        )


async def lock_live_source(transaction: Transaction, source_id: UUID) -> Source:
    """문서를 넣는 작업 단위가 맨 먼저 부른다. 원천 행을 공유 잠금으로 잡고 지움 표시를 다시
    본다. 표시가 서 있으면 409 `source_deleted`다(잠금 순서는 원천 행, 문서 행, 지식베이스 행, 작업
    행이다)."""
    source = await transaction.catalog.lock_source_shared(source_id)
    if source is None:
        raise RuntimeError("문서가 가리키는 원천이 없다")
    ensure_not_deleted(source)
    return source
