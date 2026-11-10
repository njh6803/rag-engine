"""`DocumentStore` 어댑터(명세 "데이터 모델과 스키마", "수집 파이프라인과 작업"의 잠금 규칙).

같은 키를 동시에 넣는 두 요청은 (원천, 키) 유일 제약으로 직렬화되고, 문서 행의 잠금은 잠근 뒤의 행을
낸다. 동시성은 연결 둘로 한쪽 작업 단위를 열어 둔 채 다른 쪽을 돌려 본다.
"""

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import DocumentStatus
from rag_engine.domain.errors import DocumentAlreadyExistsError, ErrorCode
from rag_engine.domain.identifiers import new_id

WAIT_SECONDS = 0.5


async def test_문서를_넣으면_키와_식별자로_같은_문서를_읽는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    document = make_document(
        source,
        group,
        metadata={"title": "규정", "중첩": {"쪽": [1, 2.5, None, True]}},
        access_groups=("a", "b"),
        error_code=ErrorCode.PARSE_FAILED,
        status=DocumentStatus.FAILED,
    )

    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(document)

    async with unit_of_work.begin() as transaction:
        assert await transaction.documents.get(document.id) == document
        assert await transaction.documents.get_by_key(source.id, document.key) == document
        assert await transaction.documents.get_by_key(source.id, "없는 키") is None
        assert await transaction.documents.get(new_id()) is None


async def test_같은_원천과_키로_다시_넣으면_이미_있다고_알린다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(make_document(source, group))

    with pytest.raises(DocumentAlreadyExistsError):
        async with unit_of_work.begin() as transaction:
            await transaction.documents.add(make_document(source, group))


async def test_같은_키를_동시에_넣으면_진_쪽이_이긴_쪽의_커밋을_기다린_뒤_이미_있다고_알린다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    winner_added = asyncio.Event()
    winner_may_commit = asyncio.Event()

    async def winner() -> None:
        async with unit_of_work.begin() as transaction:
            await transaction.documents.add(make_document(source, group))
            winner_added.set()
            await winner_may_commit.wait()

    async def loser() -> None:
        async with unit_of_work.begin() as transaction:
            await transaction.documents.add(make_document(source, group))

    winner_task = asyncio.create_task(winner())
    await winner_added.wait()
    loser_task = asyncio.create_task(loser())
    await asyncio.sleep(WAIT_SECONDS)
    assert not loser_task.done()

    winner_may_commit.set()
    await winner_task
    with pytest.raises(DocumentAlreadyExistsError):
        await loser_task


async def test_같은_원천의_다른_키는_서로_막지_않는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)

    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(make_document(source, group, "a.pdf"))
        await transaction.documents.add(make_document(source, group, "b.pdf"))

    async with unit_of_work.begin() as transaction:
        assert await transaction.documents.get_by_key(source.id, "a.pdf") is not None
        assert await transaction.documents.get_by_key(source.id, "b.pdf") is not None


async def test_고친_칸은_저장되고_식별자와_키와_만든_시각은_그대로다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    original = make_document(source, group)
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(original)

    changed = replace(
        original,
        title="새 제목",
        mime="application/pdf",
        size_bytes=99,
        content_hash="b" * 64,
        blob_path="blobs/doc/new",
        metadata={"부서": "총무팀"},
        updated_at=NOW + timedelta(days=1),
        status=DocumentStatus.PARSED,
        generation=2,
        modified_at=NOW + timedelta(days=2),
    )
    async with unit_of_work.begin() as transaction:
        await transaction.documents.update(changed)

    async with unit_of_work.begin() as transaction:
        assert await transaction.documents.get(original.id) == changed


async def test_잠그면_잠근_뒤에_커밋된_고침을_본_행을_낸다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    original = make_document(source, group)
    async with unit_of_work.begin() as transaction:
        await transaction.documents.add(original)
    first_locked = asyncio.Event()
    first_may_commit = asyncio.Event()

    async def first() -> None:
        async with unit_of_work.begin() as transaction:
            locked = await transaction.documents.lock(original.id)
            assert locked is not None
            first_locked.set()
            await first_may_commit.wait()
            await transaction.documents.update(replace(locked, title="첫째가 고침", generation=2))

    async def second() -> str:
        async with unit_of_work.begin() as transaction:
            locked = await transaction.documents.lock(original.id)
            assert locked is not None
            return locked.title

    first_task = asyncio.create_task(first())
    await first_locked.wait()
    second_task = asyncio.create_task(second())
    await asyncio.sleep(WAIT_SECONDS)
    assert not second_task.done()

    first_may_commit.set()
    await first_task
    assert await second_task == "첫째가 고침"


async def test_없는_문서를_잠그면_아무것도_없다(engine: AsyncEngine) -> None:
    async with PostgresUnitOfWork(engine).begin() as transaction:
        assert await transaction.documents.lock(new_id()) is None
