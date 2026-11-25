"""원천 관리의 유스케이스(source-sync 명세 "관리 API", 스토리 1). 밀어 넣는 원천을 만들고, 목록과
하나를 본다.

원천 이름의 규칙(`rag_engine.domain.source_names`)은 입구가 판정한다. 같은 이름이 이미 있으면(지운
원천 포함) 409 `source_already_exists`다. 보기에는 지워지지 않은 문서를 문서 상태로 센 수가 든다.
"""

from dataclasses import dataclass
from datetime import datetime

from rag_engine.app.source_lookup import require_source
from rag_engine.domain.entities import DocumentCounts, Source, SourceKind, SyncRecord
from rag_engine.domain.errors import ErrorCode, RequestError, SourceAlreadyExistsError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import Transaction, UnitOfWork


@dataclass(frozen=True, slots=True)
class SourceReport:
    """원천 보기. `group`은 가져오는 원천의 그룹 이름이고 밀어 넣는 원천에서는 `None`이다."""

    source: Source
    documents: DocumentCounts
    group: str | None = None
    last_sync: SyncRecord | None = None


async def create_push_source(unit_of_work: UnitOfWork, name: str, *, now: datetime) -> SourceReport:
    source = Source(new_id(), name, SourceKind.PUSH, now)
    try:
        async with unit_of_work.begin() as transaction:
            await transaction.catalog.create_source(source)
    except SourceAlreadyExistsError:
        raise RequestError(
            ErrorCode.SOURCE_ALREADY_EXISTS, "같은 이름의 원천이 이미 있다"
        ) from None
    return SourceReport(source, DocumentCounts(total=0, failed=0, skipped=0))


async def list_source_reports(
    unit_of_work: UnitOfWork, *, include_deleted: bool = False
) -> list[SourceReport]:
    """지운 원천은 `include_deleted`를 켜야 낸다."""
    async with unit_of_work.begin() as transaction:
        return [
            await source_report(transaction, source)
            for source in await transaction.catalog.list_sources()
            if include_deleted or source.deleted_at is None
        ]


async def get_source_report(unit_of_work: UnitOfWork, name: str) -> SourceReport:
    async with unit_of_work.begin() as transaction:
        return await source_report(transaction, await require_source(transaction, name))


async def source_report(transaction: Transaction, source: Source) -> SourceReport:
    group = (
        None
        if source.group_id is None
        else await transaction.catalog.get_group_by_id(source.group_id)
    )
    return SourceReport(
        source,
        await transaction.documents.count_documents_of_source(source.id),
        None if group is None else group.name,
        await transaction.sync_records.latest_for_source(source.id),
    )
