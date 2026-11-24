"""원천을 만들고 세는 어댑터(source-sync 티켓 03).

`Catalog.create_source`는 같은 이름이 있으면 `SourceAlreadyExistsError`를 올리고, `list_sources`는
만든 차례로 낸다. `DocumentStore.count_documents_of_source`는 지워지지 않은 문서를 문서 상태로 세고,
`list_documents`는 원천으로 거른다. 표의 행은 이 파일만 직접 읽고 쓴다.
"""

import asyncio
from dataclasses import replace
from datetime import timedelta

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW, make_document, seed_source_and_group

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import (
    DocumentCounts,
    DocumentQuery,
    DocumentStatus,
    Source,
    SourceKind,
)
from rag_engine.domain.errors import SourceAlreadyExistsError
from rag_engine.domain.identifiers import new_id


def _source(name: str, **overrides: object) -> Source:
    return replace(Source(new_id(), name, SourceKind.PUSH, NOW), **overrides)


async def test_만든_원천은_이름과_식별자로_찾고_만든_시각이_실리며_지운_시각은_비어_있다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    created = _source("groupware")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(created)

    async with unit_of_work.begin() as transaction:
        found = await transaction.catalog.get_source("groupware")
        by_id = await transaction.catalog.get_source_by_id(created.id)

    assert found == created
    assert by_id == created
    assert found is not None and (found.created_at, found.deleted_at) == (NOW, None)


async def test_지운_시각이_있는_원천도_목록에_들고_그_시각이_실린다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    deleted_at = NOW + timedelta(days=1)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(_source("kept"))
        await transaction.catalog.create_source(
            _source("removed", created_at=NOW + timedelta(hours=1), deleted_at=deleted_at)
        )

    async with unit_of_work.begin() as transaction:
        listed = await transaction.catalog.list_sources()

    assert [(source.name, source.deleted_at) for source in listed] == [
        ("kept", None),
        ("removed", deleted_at),
    ]


async def test_같은_이름의_원천을_다시_만들면_SourceAlreadyExistsError를_올린다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(_source("wiki"))

    with pytest.raises(SourceAlreadyExistsError):
        async with unit_of_work.begin() as transaction:
            await transaction.catalog.create_source(_source("wiki"))

    async with unit_of_work.begin() as transaction:
        assert [source.name for source in await transaction.catalog.list_sources()] == ["wiki"]


async def test_이름이_겹친_두_요청이_동시에_오면_하나만_만들어지고_나머지는_오류다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    first_inserted = asyncio.Event()

    async def first() -> None:
        async with unit_of_work.begin() as transaction:
            try:
                await transaction.catalog.create_source(_source("race"))
            finally:
                first_inserted.set()
            await asyncio.sleep(0.3)

    async def second() -> None:
        await first_inserted.wait()
        async with unit_of_work.begin() as transaction:
            await transaction.catalog.create_source(_source("race"))

    outcomes = await asyncio.gather(first(), second(), return_exceptions=True)

    assert outcomes[0] is None
    assert isinstance(outcomes[1], SourceAlreadyExistsError)
    async with unit_of_work.begin() as transaction:
        assert [source.name for source in await transaction.catalog.list_sources()] == ["race"]


async def test_원천_목록은_만든_시각_순이고_같은_시각이면_식별자_순이다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(
            _source("late", created_at=NOW + timedelta(hours=1))
        )
        await transaction.catalog.create_source(_source("tie-first"))
        await transaction.catalog.create_source(_source("tie-second"))
        await transaction.catalog.create_source(
            _source("early", created_at=NOW - timedelta(hours=1))
        )

    async with unit_of_work.begin() as transaction:
        names = [source.name for source in await transaction.catalog.list_sources()]

    assert names == ["early", "tie-first", "tie-second", "late"]


async def test_기본_원천을_더하는_길은_같은_이름이_있으면_아무것도_하지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    first = _source("default")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_source(first)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_source(_source("default"))

    async with unit_of_work.begin() as transaction:
        assert await transaction.catalog.get_source("default") == first


async def test_문서_수는_지워지지_않은_문서를_문서_상태로_센다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    other = _source("other")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(other)
        for key in ("받음", "파싱됨", "실패", "건너뜀", "지움"):
            await transaction.documents.add(make_document(source, group, key))
        await transaction.documents.add(make_document(other, group, "다른 원천"))
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        connection.execute("UPDATE documents SET status = 'parsed' WHERE key = '파싱됨'")
        connection.execute("UPDATE documents SET status = 'failed' WHERE key = '실패'")
        connection.execute("UPDATE documents SET status = 'skipped' WHERE key = '건너뜀'")
        connection.execute("UPDATE documents SET deleted_at = now() WHERE key = '지움'")

    async with unit_of_work.begin() as transaction:
        counts = await transaction.documents.count_documents_of_source(source.id)
        other_counts = await transaction.documents.count_documents_of_source(other.id)

    assert counts == DocumentCounts(total=4, failed=1, skipped=1)
    assert other_counts == DocumentCounts(total=1, failed=0, skipped=0)


async def test_삭제_반영_대상의_키는_살아_있는_문서와_원천과_함께_지운_문서만_원천마다_나온다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    other = _source("other")
    live = make_document(source, group, "살아 있음")
    with_source = make_document(source, group, "원천과 함께 지움")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(other)
        await transaction.documents.add(live)
        await transaction.documents.add(make_document(source, group, "따로 지움"))
        await transaction.documents.add(with_source)
        await transaction.documents.add(make_document(other, group, "다른 원천"))
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        connection.execute("UPDATE documents SET deleted_at = now() WHERE key = '따로 지움'")
        connection.execute(
            "UPDATE documents SET deleted_at = now(), deleted_with_source = true "
            "WHERE key = '원천과 함께 지움'"
        )

    async with unit_of_work.begin() as transaction:
        mine = await transaction.documents.list_held_keys_of_source(source.id)
        theirs = await transaction.documents.list_held_keys_of_source(other.id)
        nothing = await transaction.documents.list_held_keys_of_source(new_id())

    assert mine == {"살아 있음": live.id, "원천과 함께 지움": with_source.id}
    assert list(theirs) == ["다른 원천"]
    assert nothing == {}


async def test_빈_목록_판정이_셀_문서는_살아_있는_문서와_원천과_함께_지워졌다는_표시가_남은_문서다(
    engine: AsyncEngine, empty_database_url: str
) -> None:
    """원천마다 문서를 하나씩 두고 그 문서의 상태만 달리해 본다."""
    unit_of_work = PostgresUnitOfWork(engine)
    _, group = await seed_source_and_group(unit_of_work)
    names = ("살아 있음", "따로 지움", "원천과 함께 지움", "삭제 기록", "문서 없음")
    sources = {name: _source(name) for name in names}
    async with unit_of_work.begin() as transaction:
        for name, source in sources.items():
            await transaction.catalog.create_source(source)
            if name != "문서 없음":
                await transaction.documents.add(make_document(source, group, name))
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        connection.execute("UPDATE documents SET deleted_at = now() WHERE key = '따로 지움'")
        connection.execute(
            "UPDATE documents SET deleted_at = now(), deleted_with_source = true"
            " WHERE key = '원천과 함께 지움'"
        )
        connection.execute(
            "UPDATE documents SET deleted_at = now(), deleted_with_source = true,"
            " purged_at = now() WHERE key = '삭제 기록'"
        )

    async with unit_of_work.begin() as transaction:
        held = {
            name: await transaction.documents.has_documents_held_by_source(source.id)
            for name, source in sources.items()
        }

    assert held == {
        "살아 있음": True,
        "따로 지움": False,
        "원천과 함께 지움": True,
        "삭제 기록": False,
        "문서 없음": False,
    }


async def test_문서가_없는_원천의_문서_수는_모두_0이다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    empty = _source("empty")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(empty)

    async with unit_of_work.begin() as transaction:
        assert await transaction.documents.count_documents_of_source(empty.id) == DocumentCounts(
            total=0, failed=0, skipped=0
        )


async def test_문서_목록은_원천으로_거르고_다른_조건과_함께_쓴다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    source, group = await seed_source_and_group(unit_of_work)
    other = _source("other")
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(other)
        mine = make_document(source, group, "같은 키")
        theirs = make_document(other, group, "같은 키")
        failed = make_document(other, group, "실패", status=DocumentStatus.FAILED)
        for document in (mine, theirs, failed):
            await transaction.documents.add(document)

    async with unit_of_work.begin() as transaction:
        base = DocumentQuery(state=None, group_id=None, key=None, limit=50, after=None)
        of_source = await transaction.documents.list_documents(replace(base, source_id=other.id))
        of_key = await transaction.documents.list_documents(replace(base, key="같은 키"))
        of_both = await transaction.documents.list_documents(
            replace(base, source_id=other.id, key="같은 키")
        )

    assert {document.id for document in of_source} == {theirs.id, failed.id}
    assert {document.id for document in of_key} == {mine.id, theirs.id}
    assert [document.id for document in of_both] == [theirs.id]
