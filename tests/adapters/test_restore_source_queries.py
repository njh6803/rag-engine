"""원천 되살리기가 쓰는 포트의 PostgreSQL 구현(source-sync 티켓 12).

원천 되살리기 요청이 쓰는 `mark_source_restored`와 `has_active_source_job`, 원천 되살리기 작업이
묶음을 고르는 `list_ids_deleted_with_source`와 `list_stalled_ids_of_source`를 본다.
"""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import psycopg
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import (
    NOW,
    make_document,
    make_index_version,
    make_knowledge_base,
    seed_source_and_group,
)

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import (
    Group,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    JobKind,
    JobStatus,
    Source,
    SourceKind,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import JobOutcome

LEASE_SECONDS = 600.0
DIMENSIONS = 3


async def test_원천_되살리기는_지움_표시를_걷고_다음_실행_시각을_쓴다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    _, group = await seed_source_and_group(unit_of_work)
    # 다음 실행 시각은 가져오는 원천만 가질 수 있다(밀어 넣는 원천은 제약이 막는다).
    source = Source(
        new_id(),
        "공유",
        SourceKind.PULL,
        NOW,
        connector="server_path",
        config={"folder": "공유"},
        group_id=group.id,
        exclude_patterns=(),
    )
    later = NOW + timedelta(hours=3)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(source)
        await transaction.catalog.mark_source_deleted(source.id, NOW)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.mark_source_restored(source.id, later)
    async with unit_of_work.begin() as transaction:
        restored = await transaction.catalog.get_source(source.name)
    assert restored is not None
    assert (restored.deleted_at, restored.next_run_at) == (None, later)

    async with unit_of_work.begin() as transaction:
        await transaction.catalog.mark_source_deleted(source.id, NOW)
        await transaction.catalog.mark_source_restored(source.id, None)
    async with unit_of_work.begin() as transaction:
        again = await transaction.catalog.get_source(source.name)
    assert again is not None
    assert (again.deleted_at, again.next_run_at) == (None, None)


async def test_원천_삭제나_되살리기_작업이_대기나_실행_중인지_원천_종류마다_본다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    kinds = (JobKind.DELETE_SOURCE, JobKind.RESTORE_SOURCE)

    async with unit_of_work.begin() as transaction:
        before = await transaction.jobs.has_active_source_job(source.id, kinds)
        await transaction.jobs.enqueue_source_job(JobKind.SYNC_SOURCE, source.id, {}, new_id(), NOW)
        other_kind = await transaction.jobs.has_active_source_job(source.id, kinds)
        await transaction.jobs.enqueue_source_job(
            JobKind.DELETE_SOURCE, source.id, {}, new_id(), NOW
        )
        queued = await transaction.jobs.has_active_source_job(source.id, kinds)
        elsewhere = await transaction.jobs.has_active_source_job(new_id(), kinds)
        only_restore = await transaction.jobs.has_active_source_job(
            source.id, (JobKind.RESTORE_SOURCE,)
        )

    assert (before, other_kind, queued, elsewhere, only_restore) == (
        False,
        False,
        True,
        False,
        False,
    )


async def test_끝난_작업은_대기나_실행_중이_아니므로_다음_요청을_막지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, _group = await seed_source_and_group(unit_of_work)
    kinds = (JobKind.DELETE_SOURCE, JobKind.RESTORE_SOURCE)
    async with unit_of_work.begin() as transaction:
        await transaction.jobs.enqueue_source_job(
            JobKind.RESTORE_SOURCE, source.id, {}, new_id(), NOW
        )
    async with unit_of_work.begin() as transaction:
        claimed = await transaction.jobs.claim("작업자-1", NOW, LEASE_SECONDS)
        assert claimed is not None
        running = await transaction.jobs.has_active_source_job(source.id, kinds)
        await transaction.jobs.finish(claimed, JobOutcome(JobStatus.FAILED, None), NOW)
    async with unit_of_work.begin() as transaction:
        finished = await transaction.jobs.has_active_source_job(source.id, kinds)

    assert (running, finished) == (True, False)


async def test_원천과_함께_지운_문서의_ID는_ID_순으로_한도까지_나오고_되살리면_빠진다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    documents = [make_document(source, group, f"문서{number}") for number in range(4)]
    async with unit_of_work.begin() as transaction:
        for document in documents:
            await transaction.documents.add(document)
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        connection.execute(
            "UPDATE documents SET deleted_at = now(), deleted_with_source = true"
            " WHERE key IN ('문서0', '문서1', '문서2')"
        )
        connection.execute("UPDATE documents SET purged_at = now() WHERE key = '문서2'")
    expected = sorted(document.id for document in documents[:2])

    async with unit_of_work.begin() as transaction:
        found = await transaction.documents.list_ids_deleted_with_source(source.id, 10)
        limited = await transaction.documents.list_ids_deleted_with_source(source.id, 1)
        nothing = await transaction.documents.list_ids_deleted_with_source(new_id(), 10)
        revived = await transaction.documents.lock(documents[0].id)
        assert revived is not None
        await transaction.documents.update(
            replace(revived, deleted_at=None, deleted_with_source=False)
        )
        after = await transaction.documents.list_ids_deleted_with_source(source.id, 10)

    assert found == expected
    assert limited == expected[:1]
    assert nothing == []
    assert after == [documents[1].id]


async def _knowledge_base(
    unit_of_work: PostgresUnitOfWork, group: Group, status: IndexVersionStatus
) -> IndexVersion:
    knowledge_base = replace(make_knowledge_base(f"kb-{new_id()}"), embedding_dimensions=DIMENSIONS)
    version = replace(make_index_version(knowledge_base, status), embedding_dimensions=DIMENSIONS)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_knowledge_base(knowledge_base)
        await transaction.catalog.add_group_to_knowledge_base(knowledge_base.id, group.id)
        await transaction.catalog.add_index_version(version)
        await transaction.index.create_version_index(version)
    return version


def _state(
    document_id: UUID,
    version: IndexVersion,
    status: IndexStateStatus,
    built_content_hash: str | None = None,
) -> IndexState:
    return IndexState(
        document_id=document_id,
        index_version_id=version.id,
        status=status,
        chunk_count=0,
        built_content_hash=built_content_hash,
        error_code=None,
        updated_at=NOW,
    )


async def test_색인이_멈춘_문서는_정착하지_않은_판이_있는데_색인_작업이_없는_문서다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    current = await _knowledge_base(unit_of_work, group, IndexVersionStatus.CURRENT)
    building = await _knowledge_base(unit_of_work, group, IndexVersionStatus.BUILDING)
    names = (
        "상태없음",
        "모두색인됨",
        "건설판만빠짐",
        "대기중",
        "작업있음",
        "실패는정착",
        "옛내용색인",
        "지움",
    )
    documents = {name: make_document(source, group, name) for name in names}
    async with unit_of_work.begin() as transaction:
        for document in documents.values():
            await transaction.documents.add(document)
        for name in ("모두색인됨", "건설판만빠짐", "대기중", "작업있음", "실패는정착"):
            document = documents[name]
            await transaction.index.save_state(
                _state(document.id, current, IndexStateStatus.INDEXED, document.content_hash)
            )
        for name, status in (
            ("모두색인됨", IndexStateStatus.INDEXED),
            ("대기중", IndexStateStatus.PENDING),
            ("작업있음", IndexStateStatus.PENDING),
            ("실패는정착", IndexStateStatus.FAILED),
        ):
            document = documents[name]
            built = document.content_hash if status is IndexStateStatus.INDEXED else None
            await transaction.index.save_state(_state(document.id, building, status, built))
        # 내용을 바꿔 넣었는데 색인 작업이 사라져, 두 판 모두 옛 내용의 해시로 색인된 채 남은
        # 문서다.
        for version in (current, building):
            await transaction.index.save_state(
                _state(
                    documents["옛내용색인"].id, version, IndexStateStatus.INDEXED, "옛 내용의 해시"
                )
            )
        await transaction.jobs.enqueue(documents["작업있음"].id, new_id(), NOW)
    with_deleted = documents["지움"]
    async with unit_of_work.begin() as transaction:
        locked = await transaction.documents.lock(with_deleted.id)
        assert locked is not None
        await transaction.documents.update(replace(locked, deleted_at=NOW))

    async with unit_of_work.begin() as transaction:
        stalled = await transaction.documents.list_stalled_ids_of_source(source.id, 10)
        limited = await transaction.documents.list_stalled_ids_of_source(source.id, 1)

    assert sorted(stalled) == sorted(
        documents[name].id for name in ("상태없음", "건설판만빠짐", "대기중", "옛내용색인")
    )
    assert limited == sorted(stalled)[:1]
