"""일정 시험이 함께 쓰는 도우미(source-sync 티켓 10): 일정이 적힌 가져오는 원천을 세우고, 동기화
작업과 동기화 기록을 읽는다."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW

from rag_engine.adapters.schedule import CronsimScheduleCalculator
from rag_engine.domain.entities import Group, Source, SourceKind, SyncRecord
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import UnitOfWork

SEOUL_CALCULATOR = CronsimScheduleCalculator(ZoneInfo("Asia/Seoul"))
EVERY_HOUR = "0 * * * *"
# 일정 시험의 "지금". 한국 시간으로 2026-11-21 06:43이다.
CHECK_TIME = datetime(2026, 11, 20, 21, 43, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SyncJobRow:
    id: UUID
    source_id: UUID
    status: str
    options: object
    request_id: UUID


async def add_scheduled_source(
    unit_of_work: UnitOfWork,
    name: str,
    *,
    schedule: str | None = EVERY_HOUR,
    next_run_at: datetime | None,
    paused: bool = False,
) -> Source:
    """그룹 하나에 묶인 가져오는 원천을 만든다. 다음 실행 시각은 시험이 적는다."""
    group = Group(new_id(), f"그룹-{name}", "")
    source = Source(
        new_id(),
        name,
        SourceKind.PULL,
        NOW,
        connector="server_path",
        config={"folder": name},
        group_id=group.id,
        schedule=schedule,
        next_run_at=next_run_at,
        paused=paused,
    )
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(group)
        await transaction.catalog.create_source(source)
    return source


async def sync_jobs(engine: AsyncEngine, source: Source | None = None) -> list[SyncJobRow]:
    """동기화 작업 행을 만든 순서로 읽는다. `source`를 주면 그 원천의 것만 읽는다."""
    query = sa.text(
        "SELECT id, source_id, status, options, request_id FROM jobs"
        " WHERE kind = 'sync_source' AND (CAST(:source AS uuid) IS NULL OR source_id = :source)"
        " ORDER BY id"
    )
    async with engine.connect() as connection:
        rows = await connection.execute(query, {"source": None if source is None else source.id})
        return [
            SyncJobRow(row.id, row.source_id, row.status, row.options, row.request_id)
            for row in rows
        ]


async def set_sync_job_status(engine: AsyncEngine, status: str) -> None:
    """모든 동기화 작업 행의 상태를 바꾼다. 앞 동기화가 실행 중이거나 끝난 상태를 만든다."""
    async with engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE jobs SET status = :status WHERE kind = 'sync_source'"),
            {"status": status},
        )


async def records_of(unit_of_work: UnitOfWork, source: Source) -> list[SyncRecord]:
    """그 원천의 동기화 기록을 오래된 것부터 읽는다."""
    async with unit_of_work.begin() as transaction:
        newest_first = await transaction.sync_records.list_for_source(source.id, 1000, None)
    return list(reversed(newest_first))


async def source_named(unit_of_work: UnitOfWork, name: str) -> Source:
    async with unit_of_work.begin() as transaction:
        found = await transaction.catalog.get_source(name)
    assert found is not None
    return found


async def mark_deleted(engine: AsyncEngine, source: Source) -> None:
    """지움 표시를 직접 세운다. 원천을 지우는 관리 API는 이 티켓의 몫이 아니다."""
    async with engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE sources SET deleted_at = :at WHERE id = :id"),
            {"at": NOW, "id": source.id},
        )
