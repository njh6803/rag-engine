"""정리 작업(source-sync 티켓 14, 명세 "정리 작업").

실제 테스트 PostgreSQL과 실제 파일 저장소를 쓰고, 시계는 파이프라인의 시계다. 시험이 시각을
옮겨 정리 작업을 한 번 돌린다. 여기서 보는 것은 앞의 네 단계다. 보관 기간이 지난 지운 문서를
완전히 지우는 것(원천과 함께 지워졌다는 표시가 있는 문서는 건드리지 않는다), 보관 기간이 지난
지운 원천을 지우는 것, 주인 없는 원본을 치우는 것, 오래된 동기화 기록을 지우는 것이다. 멈춘 원천
삭제와 복구를 다시 잇는 다섯째 단계는 `test_cleanup_resume.py`가 본다.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from tests.records import NOW, make_document
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import MAX_UPLOAD_BYTES, Pipeline

from rag_engine.app.cleanup import BATCH_SIZE, CleanupCounts, CleanupDeps, run_cleanup
from rag_engine.app.delete_document import delete_document
from rag_engine.app.delete_source import request_source_deletion
from rag_engine.app.ingest import IngestRequest, ingest_document
from rag_engine.app.restore_source import request_source_restoration
from rag_engine.domain.entities import (
    IndexState,
    IndexStateStatus,
    IndexVersionStatus,
    Job,
    JobStatus,
    Source,
    SourceKind,
    SyncRecord,
    SyncRecordStatus,
    SyncTrigger,
)
from rag_engine.domain.errors import AttemptLostError, TransientFailure
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome, UnitOfWork
from rag_engine.worker.processing import run_once

RETENTION_DAYS = 30
RECORD_RETENTION_DAYS = 90


def _docx(title: str = "규정") -> bytes:
    return docx_bytes(title, "휴가는 연차로 쓴다.")


def cleanup_deps(pipeline: Pipeline, *, unit_of_work: UnitOfWork | None = None) -> CleanupDeps:
    return CleanupDeps(
        unit_of_work=unit_of_work or pipeline.unit_of_work,
        blob_store=pipeline.blob_store,
        now=lambda: pipeline.clock[0],
        deleted_retention_days=RETENTION_DAYS,
        sync_record_retention_days=RECORD_RETENTION_DAYS,
    )


async def claim_cleanup(pipeline: Pipeline) -> Job:
    """정리 작업을 하나 넣고, 그 작업만 꺼낸 모양(`running`)으로 만들어 낸다. 대기 중인 다른 작업과
    섞이지 않는다."""
    now = pipeline.clock[0]
    async with pipeline.unit_of_work.begin() as transaction:
        queued = await transaction.jobs.enqueue_cleanup(now + timedelta(days=1), new_id(), now)
    assert queued is not None
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text(
                "UPDATE jobs SET status = 'running', attempts = 1, worker_id = 'worker-cleanup',"
                " leased_until = :until, started_at = :now WHERE id = :id"
            ),
            {"until": now + timedelta(hours=1), "now": now, "id": queued.id},
        )
    async with pipeline.unit_of_work.begin() as transaction:
        job = await transaction.jobs.get(queued.id)
    assert job is not None
    return job


async def run_cleanup_at(
    pipeline: Pipeline, *, days_later: float = 0.0, at: datetime | None = None
) -> CleanupCounts:
    """시계를 옮기고(`at`이 없으면 `NOW`에서 `days_later`일 뒤) 정리 작업을 하나 넣어 한 번
    돌린다."""
    pipeline.clock[0] = at or NOW + timedelta(days=days_later)
    job = await claim_cleanup(pipeline)
    counts = await run_cleanup(cleanup_deps(pipeline), job)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.jobs.finish(job, JobOutcome(JobStatus.SUCCEEDED, None), pipeline.clock[0])
    return counts


async def drain(pipeline: Pipeline) -> None:
    """꺼낼 작업이 없을 때까지 작업자를 돌린다."""
    while await run_once(pipeline.deps(), worker_id="worker-cleanup", lease_seconds=600.0) > 0:
        pass


async def push_source(pipeline: Pipeline, name: str) -> Source:
    source = Source(new_id(), name, SourceKind.PUSH, NOW)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(source)
    return source


async def ingest_into(pipeline: Pipeline, source: Source, key: str) -> UUID:
    result = await ingest_document(
        pipeline.unit_of_work,
        pipeline.blob_store,
        IngestRequest(
            filename=key,
            data=_docx(key),
            key=None,
            group=None,
            metadata={},
            updated_at=None,
            source=source.name,
        ),
        request_id=new_id(),
        now=pipeline.clock[0],
        max_upload_bytes=MAX_UPLOAD_BYTES,
    )
    return result.document_id


async def delete_source_and_drain(pipeline: Pipeline, source: Source) -> None:
    await request_source_deletion(
        pipeline.unit_of_work, source.name, request_id=new_id(), now=pipeline.clock[0]
    )
    await drain(pipeline)


async def scalar(pipeline: Pipeline, query: str, **parameters: object) -> object:
    async with pipeline.engine.connect() as connection:
        return (await connection.execute(sa.text(query), parameters)).scalar_one()


async def blob_exists(pipeline: Pipeline, path: str) -> bool:
    try:
        await pipeline.blob_store.read(path)
    except TransientFailure:
        return False
    return True


async def blob_path_of(pipeline: Pipeline, document_id: UUID) -> str:
    path = await scalar(pipeline, "SELECT blob_path FROM documents WHERE id = :id", id=document_id)
    assert isinstance(path, str)
    return path


@dataclass(frozen=True, slots=True)
class Leftovers:
    """문서 하나에 남은 것."""

    blob_path: str | None
    purged: bool
    deleted: bool
    archived_chunks: int
    chunks: int
    contents: int


async def leftovers(pipeline: Pipeline, document_id: UUID) -> Leftovers:
    async with pipeline.engine.connect() as connection:
        row = (
            await connection.execute(
                sa.text(
                    "SELECT blob_path, purged_at IS NOT NULL AS purged,"
                    " deleted_at IS NOT NULL AS deleted,"
                    " (SELECT count(*) FROM archived_chunks WHERE document_id = :id) AS archived,"
                    " (SELECT count(*) FROM chunks WHERE document_id = :id) AS chunks,"
                    " (SELECT count(*) FROM document_contents WHERE document_id = :id) AS contents"
                    " FROM documents WHERE id = :id"
                ),
                {"id": document_id},
            )
        ).one()
    return Leftovers(row.blob_path, row.purged, row.deleted, row.archived, row.chunks, row.contents)


def make_recent(root: Path, path: str, *, run_at: datetime) -> None:
    """원본을 정리 작업이 도는 시각의 한 시간 전에 쓴 파일로 만든다. 셋째 단계(주인 없는 원본
    치우기)는 스물네 시간이 안 된 파일을 건드리지 않으므로, 문서나 원천을 지우는 단계가 직접 지워야
    사라진다."""
    stamp = (run_at - timedelta(hours=1)).timestamp()
    os.utime(root / path, (stamp, stamp))


async def test_보관_기간이_지난_지운_문서는_삭제_기록만_남기고_지운다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    gone = await pipeline.ingest(_docx("지움"), "지움.docx")
    kept = await pipeline.ingest(_docx("남김"), "남김.docx")
    await drain(pipeline)
    gone_path = await blob_path_of(pipeline, gone.document_id)
    kept_path = await blob_path_of(pipeline, kept.document_id)
    make_recent(tmp_path, gone_path, run_at=NOW + timedelta(days=RETENTION_DAYS))
    await pipeline.delete("지움.docx")
    # 하루 늦게 지운 문서는 보관 기간이 하루 더 남는다.
    pipeline.clock[0] = NOW + timedelta(days=1)
    await pipeline.delete("남김.docx")

    counts = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS)

    after = await leftovers(pipeline, gone.document_id)
    assert (after.blob_path, after.purged, after.deleted) == (None, True, True)
    assert (after.archived_chunks, after.chunks, after.contents) == (0, 0, 0)
    assert not await blob_exists(pipeline, gone_path)
    still = await leftovers(pipeline, kept.document_id)
    assert (still.purged, still.deleted, still.contents) == (False, True, 1)
    assert still.archived_chunks > 0
    assert await blob_exists(pipeline, kept_path)
    assert counts.documents_purged == 1


async def test_지운_시각에서_보관_일수가_꼭_지난_문서부터_지운다(pipeline: Pipeline) -> None:
    # 복구하는 요청이 `삭제 시각 + 보관 일수 <= 지금`이면 거절하는 것과 같은 경계다.
    result = await pipeline.ingest(_docx(), "경계.docx")
    await pipeline.delete("경계.docx")

    early = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS - 0.001)
    on_boundary = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS)

    assert early.documents_purged == 0
    assert on_boundary.documents_purged == 1
    assert (await leftovers(pipeline, result.document_id)).purged


async def test_묶음_크기를_넘는_문서도_모두_지운다(pipeline: Pipeline) -> None:
    total = BATCH_SIZE + 5
    async with pipeline.unit_of_work.begin() as transaction:
        for number in range(total):
            await transaction.documents.add(
                make_document(
                    pipeline.source,
                    pipeline.group,
                    f"문서{number}.pdf",
                    blob_path=None,
                    deleted_at=NOW,
                )
            )

    counts = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS)

    assert counts.documents_purged == total
    assert await scalar(pipeline, "SELECT count(*) FROM documents WHERE purged_at IS NULL") == 0


async def test_이미_삭제_기록이_된_문서는_다시_세지_않는다(pipeline: Pipeline) -> None:
    await pipeline.ingest(_docx(), "기록.docx")
    await pipeline.delete("기록.docx")
    await run_cleanup_at(pipeline, days_later=RETENTION_DAYS)

    again = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS + 1)

    assert again.documents_purged == 0


async def test_원천과_함께_지운_표시가_남은_문서는_보관_기간이_지나도_지우지_않는다(
    pipeline: Pipeline,
) -> None:
    source = await push_source(pipeline, "복구")
    document_id = await ingest_into(pipeline, source, "규정.docx")
    await drain(pipeline)
    await delete_source_and_drain(pipeline, source)
    # 지운 원천을 복구하는 요청만 보내고 작업자는 아직 돌리지 않았다. 문서는 표시가 남은 채
    # 숨어 있다.
    await request_source_restoration(
        pipeline.unit_of_work,
        source.name,
        request_id=new_id(),
        now=pipeline.clock[0],
        retention_days=RETENTION_DAYS,
    )

    counts = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS + 5)

    assert not (await leftovers(pipeline, document_id)).purged
    assert (counts.documents_purged, counts.sources_purged, counts.jobs_requeued) == (0, 0, 0)
    # 이어서 작업자가 돌면 문서가 돌아온다.
    await drain(pipeline)
    assert not (await leftovers(pipeline, document_id)).deleted


async def test_작업_담당_기록을_잃은_정리_작업은_아무것도_지우지_않는다(pipeline: Pipeline) -> None:
    result = await pipeline.ingest(_docx(), "규정.docx")
    await pipeline.delete("규정.docx")
    pipeline.clock[0] = NOW + timedelta(days=RETENTION_DAYS)
    claimed = await claim_cleanup(pipeline)
    # 기한이 끝나 다른 작업자가 가져간 것처럼 시도 횟수를 올린다.
    async with pipeline.engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE jobs SET attempts = attempts + 1 WHERE id = :id"), {"id": claimed.id}
        )

    with pytest.raises(AttemptLostError):
        await run_cleanup(cleanup_deps(pipeline), claimed)

    assert not (await leftovers(pipeline, result.document_id)).purged


async def test_보관_기간이_지난_지운_원천은_딸린_것을_모두_지우고_이름을_다시_쓸_수_있다(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    source = await push_source(pipeline, "위키")
    together = await ingest_into(pipeline, source, "가.docx")
    earlier = await ingest_into(pipeline, source, "나.docx")
    await drain(pipeline)
    together_path = await blob_path_of(pipeline, together)
    make_recent(tmp_path, together_path, run_at=NOW + timedelta(days=RETENTION_DAYS))
    # 원천보다 먼저 따로 지운 문서는 표시가 없어 첫째 단계가 먼저 삭제 기록으로 만든다.
    await delete_document(pipeline.unit_of_work, "나.docx", source_name="위키", now=NOW)
    await delete_source_and_drain(pipeline, source)
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.sync_records.add(sync_record(source, created=NOW, finished=NOW))

    counts = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS)

    assert (counts.documents_purged, counts.sources_purged) == (1, 1)
    assert await scalar(pipeline, "SELECT count(*) FROM sources WHERE name = '위키'") == 0
    for table in ("documents", "jobs", "sync_records"):
        remaining = await scalar(
            pipeline, f"SELECT count(*) FROM {table} WHERE source_id = :id", id=source.id
        )
        assert remaining == 0, table
    document_jobs = await scalar(
        pipeline, "SELECT count(*) FROM jobs WHERE document_id IN (:a, :b)", a=together, b=earlier
    )
    assert document_jobs == 0
    assert not await blob_exists(pipeline, together_path)
    await push_source(pipeline, "위키")


async def test_보관_기간이_남은_지운_원천은_그대로_둔다(pipeline: Pipeline) -> None:
    source = await push_source(pipeline, "위키")
    await ingest_into(pipeline, source, "가.docx")
    await drain(pipeline)
    await delete_source_and_drain(pipeline, source)

    counts = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS - 1)

    assert counts.sources_purged == 0
    assert await scalar(pipeline, "SELECT count(*) FROM sources WHERE name = '위키'") == 1


async def test_지운_원천에_묶음_크기를_넘는_문서가_있어도_모두_지운다(pipeline: Pipeline) -> None:
    source = await push_source(pipeline, "많음")
    async with pipeline.unit_of_work.begin() as transaction:
        for number in range(BATCH_SIZE + 5):
            await transaction.documents.add(
                make_document(source, pipeline.group, f"문서{number}.pdf", blob_path=None)
            )
    await delete_source_and_drain(pipeline, source)

    counts = await run_cleanup_at(pipeline, days_later=RETENTION_DAYS)

    assert counts.sources_purged == 1
    remaining = await scalar(
        pipeline, "SELECT count(*) FROM documents WHERE source_id = :id", id=source.id
    )
    assert remaining == 0


async def test_옮기지_못한_문서의_색인_상태가_사라지면_건설_중인_판이_전환된다(
    pipeline: Pipeline,
) -> None:
    stuck = await push_source(pipeline, "멈춤")
    held = await ingest_into(pipeline, stuck, "멈춤.docx")
    other = (await pipeline.ingest(_docx("다른"), "다른.docx")).document_id
    await drain(pipeline)
    version = await pipeline.add_building_version()
    async with pipeline.unit_of_work.begin() as transaction:
        # 지움 표시가 선 동안 시작한 재색인이다. 멈춘 원천의 문서는 새 판에서 `pending`으로
        # 남았고 다른 문서의 새 판 색인은 끝났다. 원천 삭제 작업은 재시도를 다 쓰고 실패해
        # 문서가 그대로다.
        for document_id, status in (
            (held, IndexStateStatus.PENDING),
            (other, IndexStateStatus.INDEXED),
        ):
            document = await transaction.documents.get(document_id)
            assert document is not None
            indexed = status is IndexStateStatus.INDEXED
            await transaction.index.save_state(
                IndexState(
                    document_id=document_id,
                    index_version_id=version.id,
                    status=status,
                    chunk_count=0,
                    built_content_hash=document.content_hash if indexed else None,
                    error_code=None,
                    updated_at=NOW,
                )
            )
        await transaction.catalog.lock_source(stuck.id)
        await transaction.catalog.mark_source_deleted(stuck.id, NOW)

    await run_cleanup_at(pipeline, days_later=RETENTION_DAYS)

    assert await scalar(pipeline, "SELECT count(*) FROM sources WHERE name = '멈춤'") == 0
    held_chunks = await scalar(
        pipeline, "SELECT count(*) FROM chunks WHERE document_id = :id", id=held
    )
    assert held_chunks == 0
    async with pipeline.unit_of_work.begin() as transaction:
        switched = await transaction.catalog.get_index_version(version.id)
    assert switched is not None
    assert switched.status is IndexVersionStatus.CURRENT


def write_blob(root: Path, key: str, *, written: datetime) -> Path:
    """`root` 아래에 파일을 쓰고 쓴 시각(수정 시각)을 `written`으로 맞춘다."""
    path = root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"orphan")
    os.utime(path, (written.timestamp(), written.timestamp()))
    return path


async def test_하루_넘게_묵은_주인_없는_원본만_치운다(pipeline: Pipeline, tmp_path: Path) -> None:
    now = datetime.now(UTC)
    result = await pipeline.ingest(_docx(), "주인.docx")
    owned = await blob_path_of(pipeline, result.document_id)
    # 주인이 있는 원본은 아무리 묵어도 남는다.
    stamp = (now - timedelta(days=2)).timestamp()
    os.utime(tmp_path / owned, (stamp, stamp))
    old = "blobs/00000000-0000-7000-8000-000000000001/00000000-0000-7000-8000-000000000002"
    fresh = "blobs/00000000-0000-7000-8000-000000000003/00000000-0000-7000-8000-000000000004"
    write_blob(tmp_path, old, written=now - timedelta(hours=25))
    write_blob(tmp_path, fresh, written=now - timedelta(hours=1))
    # 서버 폴더와 데이터 폴더의 다른 파일은 아무리 묵어도 건드리지 않는다.
    outside = [
        write_blob(tmp_path, "sources/규정.pdf", written=now - timedelta(days=200)),
        write_blob(tmp_path, "notes.txt", written=now - timedelta(days=200)),
    ]

    counts = await run_cleanup_at(pipeline, at=now)

    assert counts.blobs_removed == 1
    assert not await blob_exists(pipeline, old)
    assert await blob_exists(pipeline, fresh)
    assert await blob_exists(pipeline, owned)
    assert all(path.exists() for path in outside)


def sync_record(source: Source, *, created: datetime, finished: datetime | None) -> SyncRecord:
    return SyncRecord(
        id=new_id(),
        source_id=source.id,
        job_id=None,
        trigger=SyncTrigger.MANUAL,
        options={},
        status=SyncRecordStatus.RUNNING if finished is None else SyncRecordStatus.SUCCEEDED,
        failure_code=None,
        created_at=created,
        started_at=created,
        finished_at=finished,
        listed=0,
        added=0,
        updated=0,
        deleted=0,
        unchanged=0,
        skipped={},
        not_accepted={},
        failed={},
    )


async def test_오래된_동기화_기록은_지우되_원천마다_가장_최근_기록_하나는_남긴다(
    pipeline: Pipeline,
) -> None:
    busy = await push_source(pipeline, "바쁨")
    quiet = await push_source(pipeline, "한가함")
    long_ago = NOW - timedelta(days=RECORD_RETENTION_DAYS + 110)
    recent = NOW - timedelta(days=1)
    # 기록의 ID는 만든 순서로 커지므로 오래된 것부터 만든다.
    plan = [
        ("old_busy", busy, long_ago, long_ago),
        ("unfinished_busy", busy, long_ago + timedelta(days=1), None),
        ("recent_busy", busy, recent, recent),
        ("old_quiet", quiet, long_ago, long_ago),
        ("newest_quiet", quiet, long_ago + timedelta(days=2), long_ago + timedelta(days=2)),
    ]
    ids: dict[str, UUID] = {}
    async with pipeline.unit_of_work.begin() as transaction:
        for name, source, created, finished in plan:
            record = sync_record(source, created=created, finished=finished)
            ids[name] = record.id
            await transaction.sync_records.add(record)

    counts = await run_cleanup_at(pipeline)

    async with pipeline.engine.connect() as connection:
        rows = await connection.execute(sa.text("SELECT id FROM sync_records"))
        left = {row.id for row in rows}
    # 끝나지 않은 기록은 기간이 지나도 지우지 않는다. 원천마다 가장 최근 기록 하나는 남는다.
    assert left == {ids["unfinished_busy"], ids["recent_busy"], ids["newest_quiet"]}
    assert counts.sync_records_deleted == 2


async def test_동기화_기록_보관_기간의_경계는_끝난_시각에서_꼭_지난_것부터다(
    pipeline: Pipeline,
) -> None:
    source = await push_source(pipeline, "경계")
    finished = NOW - timedelta(days=RECORD_RETENTION_DAYS)
    async with pipeline.unit_of_work.begin() as transaction:
        # 둘 다 가장 최근 기록이 아니도록 최근 기록 하나를 더 둔다.
        await transaction.sync_records.add(sync_record(source, created=finished, finished=finished))
        await transaction.sync_records.add(
            sync_record(
                source,
                created=finished + timedelta(seconds=1),
                finished=finished + timedelta(seconds=1),
            )
        )
        await transaction.sync_records.add(sync_record(source, created=NOW, finished=NOW))

    counts = await run_cleanup_at(pipeline)

    assert counts.sync_records_deleted == 1
