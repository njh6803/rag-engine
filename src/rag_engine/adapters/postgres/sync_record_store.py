"""`SyncRecordStore` 어댑터. 동기화 기록 표(`sync_records`)를 읽고 쓴다(source-sync 명세 "동기화
기록").

기록은 동기화 작업을 대기열에 넣는 같은 작업 단위에서 만들어지므로 작업 단위 안의 포트다.
개수 가운데 `skipped`, `not_accepted`, `failed`는 사유를 키로 하는 JSON 객체이고 실패 사유는 닫힌
코드만 싣는다(원칙 V).
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from rag_engine.adapters.postgres import tables
from rag_engine.domain.entities import SyncRecord, SyncRecordStatus, SyncTrigger


def _record(row: sa.RowMapping) -> SyncRecord:
    return SyncRecord(
        id=row["id"],
        source_id=row["source_id"],
        job_id=row["job_id"],
        trigger=SyncTrigger(row["trigger"]),
        options=row["options"],
        status=SyncRecordStatus(row["status"]),
        failure_code=row["failure_code"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        listed=row["listed"],
        added=row["added"],
        updated=row["updated"],
        deleted=row["deleted"],
        unchanged=row["unchanged"],
        skipped=row["skipped"],
        not_accepted=row["not_accepted"],
        failed=row["failed"],
    )


def _values(record: SyncRecord) -> dict[str, object]:
    """고칠 수 있는 칸. 식별자와 원천, 시작시킨 것, 만든 시각은 바뀌지 않는다."""
    return {
        "job_id": record.job_id,
        "options": dict(record.options),
        "status": record.status.value,
        "failure_code": record.failure_code,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "listed": record.listed,
        "added": record.added,
        "updated": record.updated,
        "deleted": record.deleted,
        "unchanged": record.unchanged,
        "skipped": dict(record.skipped),
        "not_accepted": dict(record.not_accepted),
        "failed": dict(record.failed),
    }


class PostgresSyncRecordStore:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, record: SyncRecord) -> None:
        await self._connection.execute(
            sa.insert(tables.sync_records).values(
                id=record.id,
                source_id=record.source_id,
                trigger=record.trigger.value,
                created_at=record.created_at,
                **_values(record),
            )
        )

    async def get(self, record_id: UUID) -> SyncRecord | None:
        return await self._select_one(tables.sync_records.c.id == record_id)

    async def get_by_job(self, job_id: UUID) -> SyncRecord | None:
        return await self._select_one(tables.sync_records.c.job_id == job_id)

    async def update(self, record: SyncRecord) -> None:
        await self._connection.execute(
            sa.update(tables.sync_records)
            .where(tables.sync_records.c.id == record.id)
            .values(**_values(record))
        )

    async def list_for_source(
        self, source_id: UUID, limit: int, after: UUID | None
    ) -> list[SyncRecord]:
        query = (
            sa.select(tables.sync_records)
            .where(tables.sync_records.c.source_id == source_id)
            .order_by(tables.sync_records.c.id.desc())
            .limit(limit)
        )
        if after is not None:
            query = query.where(tables.sync_records.c.id < after)
        rows = (await self._connection.execute(query)).mappings().all()
        return [_record(row) for row in rows]

    async def latest_for_source(self, source_id: UUID) -> SyncRecord | None:
        rows = await self.list_for_source(source_id, 1, None)
        return rows[0] if rows else None

    async def delete_of_source(self, source_id: UUID) -> None:
        await self._connection.execute(
            sa.delete(tables.sync_records).where(tables.sync_records.c.source_id == source_id)
        )

    async def delete_finished_before(self, cutoff: datetime, limit: int) -> int:
        records = tables.sync_records
        # 원천마다 ID가 가장 큰 기록이 가장 최근 기록이다(`latest_for_source`와 같은 기준). 같은
        # 원천에 더 큰 ID의 기록이 있으면 가장 최근 기록이 아니다.
        newer = tables.sync_records.alias("newer")
        has_newer = sa.exists().where(
            newer.c.source_id == records.c.source_id, newer.c.id > records.c.id
        )
        doomed = (
            sa.select(records.c.id)
            .where(
                records.c.finished_at.is_not(None),
                records.c.finished_at <= cutoff,
                has_newer,
            )
            .order_by(records.c.id)
            .limit(limit)
        )
        deleted = await self._connection.execute(
            sa.delete(records).where(records.c.id.in_(doomed)).returning(records.c.id)
        )
        return len(deleted.all())

    async def _select_one(self, *conditions: sa.ColumnElement[bool]) -> SyncRecord | None:
        row = (
            (await self._connection.execute(sa.select(tables.sync_records).where(*conditions)))
            .mappings()
            .one_or_none()
        )
        return None if row is None else _record(row)
