"""서버가 둘이어도 겹치는 폴더의 원천이 둘 다 만들어지지 않는다(source-sync 티켓 06, 명세의 서버
경로 커넥터 잠금 항목).

프로세스 안의 잠금은 서버마다 따로라 서버 둘 사이의 차례는 데이터베이스의 자문 잠금이 세운다.
`PullSources`를 둘 만들어 서버 둘을 흉내 낸다(둘은 프로세스 안 잠금을 나누지 않는다). 첫째를
겹침 확인을 지난 뒤 저장하기 전에 붙잡아 두지 않으면 두 요청이 저절로 차례로 지나 자문 잠금이
없어도 시험이 초록이 된다.
"""

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW
from tests.support.schedule_sources import SEOUL_CALCULATOR

from rag_engine.adapters.connectors.registry import EntryPointConnectorRegistry
from rag_engine.adapters.postgres.catalog import PostgresCatalog
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.pull_sources import PullSources
from rag_engine.domain.entities import Group, JsonValue, Source
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id

GROUP = "모임"
WAIT_SECONDS = 15


async def _create(server: PullSources, name: str, folder: str) -> None:
    await server.create(
        name=name,
        connector="server_path",
        config={"folder": folder},
        group=GROUP,
        exclude_patterns=(),
        schedule=None,
        now=NOW,
    )


async def test_서버_둘이_겹치는_폴더를_동시에_만들면_하나만_만들어지고_다른_하나는_겹침이다(
    engine: AsyncEngine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "sources"
    (parent / "a" / "b").mkdir(parents=True)
    monkeypatch.setenv("RAG_SOURCES_DIR", str(parent))
    unit_of_work = PostgresUnitOfWork(engine)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(Group(new_id(), GROUP, ""))
    entered = asyncio.Event()
    release = asyncio.Event()
    real_create_source = PostgresCatalog.create_source

    async def create_source(self: PostgresCatalog, source: Source) -> None:
        if source.name == "first":
            entered.set()
            await release.wait()
        await real_create_source(self, source)

    monkeypatch.setattr(PostgresCatalog, "create_source", create_source)
    registry = EntryPointConnectorRegistry()
    first_server = PullSources(unit_of_work, registry, SEOUL_CALCULATOR)
    second_server = PullSources(unit_of_work, registry, SEOUL_CALCULATOR)

    first = asyncio.create_task(_create(first_server, "first", "a"))
    await asyncio.wait_for(entered.wait(), WAIT_SECONDS)
    second = asyncio.create_task(_create(second_server, "second", "a/b"))
    await asyncio.sleep(1.0)  # 둘째가 확인을 지나 먼저 끝나지 않고 첫째를 기다리는지 본다
    waited = not second.done()
    release.set()
    await asyncio.wait_for(first, WAIT_SECONDS)
    with pytest.raises(RequestError) as raised:
        await asyncio.wait_for(second, WAIT_SECONDS)

    assert waited
    assert raised.value.code is ErrorCode.SOURCE_FOLDER_OVERLAP
    async with unit_of_work.begin() as transaction:
        names = [source.name for source in await transaction.catalog.list_sources()]
    assert "first" in names
    assert "second" not in names


async def test_서버_둘에서_폴더를_고치는_요청과_겹치는_폴더를_만드는_요청은_차례로_지나간다(
    engine: AsyncEngine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "sources"
    (parent / "a").mkdir(parents=True)
    (parent / "x" / "y").mkdir(parents=True)
    monkeypatch.setenv("RAG_SOURCES_DIR", str(parent))
    unit_of_work = PostgresUnitOfWork(engine)
    async with unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(Group(new_id(), GROUP, ""))
    registry = EntryPointConnectorRegistry()
    first_server = PullSources(unit_of_work, registry, SEOUL_CALCULATOR)
    second_server = PullSources(unit_of_work, registry, SEOUL_CALCULATOR)
    await _create(first_server, "first", "a")
    entered = asyncio.Event()
    release = asyncio.Event()
    real_update = PostgresCatalog.update_pull_source

    async def update_pull_source(
        self: PostgresCatalog,
        source_id: UUID,
        *,
        config: Mapping[str, JsonValue] | None,
        exclude_patterns: Sequence[str] | None,
    ) -> None:
        entered.set()
        await release.wait()
        await real_update(self, source_id, config=config, exclude_patterns=exclude_patterns)

    monkeypatch.setattr(PostgresCatalog, "update_pull_source", update_pull_source)

    first = asyncio.create_task(
        first_server.update(
            "first", config={"folder": "x/y"}, exclude_patterns=None, schedule=None, now=NOW
        )
    )
    await asyncio.wait_for(entered.wait(), WAIT_SECONDS)
    second = asyncio.create_task(_create(second_server, "second", "x"))
    await asyncio.sleep(1.0)  # 둘째가 확인을 지나 먼저 끝나지 않고 첫째를 기다리는지 본다
    waited = not second.done()
    release.set()
    await asyncio.wait_for(first, WAIT_SECONDS)
    with pytest.raises(RequestError) as raised:
        await asyncio.wait_for(second, WAIT_SECONDS)

    assert waited
    assert raised.value.code is ErrorCode.SOURCE_FOLDER_OVERLAP
    async with unit_of_work.begin() as transaction:
        names = [source.name for source in await transaction.catalog.list_sources()]
    assert "second" not in names
