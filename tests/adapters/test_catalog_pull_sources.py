"""가져오는 원천을 저장하는 어댑터(source-sync 티켓 06).

가져오는 원천의 일곱 칸이 왕복하고, 고치는 길은 설정과 제외 패턴과 일시 중지만 바꾼다. 폴더를 정하는
요청끼리는 자문 잠금이 차례로 지나게 한다. 잠금은 연결 둘로 본다. 한 연결 안에서는 같은 잠금을 다시
잡아도 막히지 않는다.
"""

import asyncio
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.entities import Group, Source, SourceKind
from rag_engine.domain.identifiers import new_id


async def _pull_source(unit_of_work: PostgresUnitOfWork, name: str = "wiki") -> Source:
    group = Group(new_id(), f"그룹-{name}", "")
    source = Source(
        new_id(),
        name,
        SourceKind.PULL,
        NOW,
        connector="server_path",
        config={"folder": "규정집"},
        group_id=group.id,
        exclude_patterns=("임시", "*_초안.docx"),
    )
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(group)
        await transaction.catalog.create_source(source)
    return source


async def test_가져오는_원천의_칸이_이름과_식별자로_다시_읽을_때_그대로다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    created = await _pull_source(unit_of_work)

    async with unit_of_work.begin() as transaction:
        by_name = await transaction.catalog.get_source("wiki")
        listed = [s for s in await transaction.catalog.list_sources() if s.name == "wiki"]

    assert by_name == created
    assert listed == [created]
    assert by_name is not None
    assert by_name.exclude_patterns == ("임시", "*_초안.docx")
    assert (by_name.schedule, by_name.next_run_at, by_name.paused) == (None, None, False)


async def test_가져오는_원천을_고치면_적은_칸만_바뀌고_이름과_커넥터와_그룹은_그대로다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    created = await _pull_source(unit_of_work)

    async with unit_of_work.begin() as transaction:
        await transaction.catalog.update_pull_source(
            created.id, config={"folder": "새폴더"}, exclude_patterns=None
        )
    async with unit_of_work.begin() as transaction:
        config_only = await transaction.catalog.get_source("wiki")
        await transaction.catalog.update_pull_source(
            created.id, config=None, exclude_patterns=("새패턴",)
        )
    async with unit_of_work.begin() as transaction:
        both = await transaction.catalog.get_source("wiki")

    assert config_only == replace(created, config={"folder": "새폴더"})
    assert both == replace(created, config={"folder": "새폴더"}, exclude_patterns=("새패턴",))


async def test_일시_중지는_일시_중지_칸만_바꿔_앞서_고친_설정과_제외_패턴을_되돌리지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    created = await _pull_source(unit_of_work)
    async with unit_of_work.begin() as pausing:
        # 일시 중지 요청이 원천을 읽은 뒤에 고치는 요청이 커밋하는 장면이다.
        read_before = await pausing.catalog.get_source("wiki")
        async with unit_of_work.begin() as editing:
            await editing.catalog.update_pull_source(
                created.id, config={"folder": "새폴더"}, exclude_patterns=("새패턴",)
            )
        assert read_before == created
        await pausing.catalog.set_source_paused(created.id, paused=True)

    async with unit_of_work.begin() as transaction:
        found = await transaction.catalog.get_source("wiki")

    assert found == replace(
        created, config={"folder": "새폴더"}, exclude_patterns=("새패턴",), paused=True
    )


async def test_고치는_길이_일시_중지_칸을_되돌리지_않는다(engine: AsyncEngine) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    created = await _pull_source(unit_of_work)
    async with unit_of_work.begin() as editing:
        await editing.catalog.get_source("wiki")
        async with unit_of_work.begin() as pausing:
            await pausing.catalog.set_source_paused(created.id, paused=True)
        await editing.catalog.update_pull_source(
            created.id, config={"folder": "새폴더"}, exclude_patterns=None
        )

    async with unit_of_work.begin() as transaction:
        found = await transaction.catalog.get_source("wiki")

    assert found == replace(created, config={"folder": "새폴더"}, paused=True)


async def test_폴더를_정하는_잠금은_다른_연결의_작업_단위가_끝날_때까지_다음을_기다리게_한다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = PostgresUnitOfWork(engine)
    first_holds = asyncio.Event()
    release_first = asyncio.Event()
    second_got_it = asyncio.Event()

    async def first() -> None:
        async with unit_of_work.begin() as transaction:
            await transaction.catalog.lock_source_folders()
            first_holds.set()
            await release_first.wait()

    async def second() -> None:
        await first_holds.wait()
        async with unit_of_work.begin() as transaction:
            await transaction.catalog.lock_source_folders()
            second_got_it.set()

    tasks = [asyncio.create_task(first()), asyncio.create_task(second())]
    await first_holds.wait()
    await asyncio.sleep(0.5)  # 둘째가 잠금에 닿았는데도 기다리는지 본다
    waited = not second_got_it.is_set()
    release_first.set()
    await asyncio.gather(*tasks)

    assert waited
    assert second_got_it.is_set()
