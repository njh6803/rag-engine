"""겹침 판정의 두 갈래(source-sync 티켓 06, 명세 "서버 경로 커넥터와 원천 폴더").

폴더가 실제로 있고 답하는 원천과는 실제 폴더의 열쇠(장치 번호, 파일 번호)로 견주고, 답하지 않는
원천과는 저장해 둔 경로의 글자로 견준다. 열쇠를 파일 시스템 없이 정할 수 있게 가짜 레지스트리를
쓴다. 이름이 대소문자만 다른 두 경로가 같은 폴더가 되는 파일 시스템이 이 PC에도 CI에도 같은 꼴로
있지 않아서다.
"""

import unicodedata
from collections.abc import Mapping, Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.records import NOW
from tests.support.fake_connectors import create_fake

from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.pull_sources import PullSources
from rag_engine.domain.connectors import (
    Connector,
    ConnectorUnavailableError,
    FolderId,
    FolderLocation,
    FolderTarget,
    SourceReader,
)
from rag_engine.domain.entities import Group, JsonValue, Source, SourceKind
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id

GROUP = "모임"


class _FolderRegistry:
    """폴더 글자마다 정해 둔 위치를 돌려주는 레지스트리. `survey_folders`는 `answering`에 든
    원천의 폴더만 답하고 나머지는 답하지 않은 것(`None`)으로 둔다."""

    def __init__(self, locations: Mapping[str, FolderLocation], answering: frozenset[str]) -> None:
        self._locations = locations
        self._answering = answering

    def create(self, name: str, config: Mapping[str, JsonValue]) -> Connector:
        return create_fake(config)

    def open_reader(
        self,
        name: str,
        config: Mapping[str, JsonValue],
        *,
        source: str,
        timeout_seconds: float,
    ) -> SourceReader:
        raise ConnectorUnavailableError

    async def locate_folder(self, name: str, config: Mapping[str, JsonValue]) -> FolderLocation:
        folder = config.get("folder")
        if not isinstance(folder, str) or folder not in self._locations:
            raise ConnectorUnavailableError
        return self._locations[folder]

    async def survey_folders(self, targets: Sequence[FolderTarget]) -> list[FolderLocation | None]:
        found: list[FolderLocation | None] = []
        for target in targets:
            folder = target.config.get("folder")
            answered = isinstance(folder, str) and target.source in self._answering
            found.append(self._locations.get(str(folder)) if answered else None)
        return found

    async def check_connection(
        self, name: str, config: Mapping[str, JsonValue], source: str
    ) -> None:
        return None


def _chain(*files: int) -> tuple[FolderId, ...]:
    return tuple((7, number) for number in files)


async def _existing(engine: AsyncEngine, name: str, folder: str) -> PostgresUnitOfWork:
    unit_of_work = PostgresUnitOfWork(engine)
    async with unit_of_work.begin() as transaction:
        found = await transaction.catalog.get_group(GROUP)
        if found is None:
            group = Group(new_id(), GROUP, "")
            await transaction.catalog.add_group(group)
            group_id = group.id
        else:
            group_id = found.id
        await transaction.catalog.create_source(
            Source(
                new_id(),
                name,
                SourceKind.PULL,
                NOW,
                connector="server_path",
                config={"folder": folder},
                group_id=group_id,
                exclude_patterns=(),
            )
        )
    return unit_of_work


async def _create(server: PullSources, name: str, folder: str) -> None:
    await server.create(
        name=name,
        connector="server_path",
        config={"folder": folder},
        group=GROUP,
        exclude_patterns=(),
        now=NOW,
    )


async def test_글자가_달라도_같은_폴더를_가리키면_겹침이다(engine: AsyncEngine) -> None:
    unit_of_work = await _existing(engine, "old", "docs")
    registry = _FolderRegistry(
        {
            "docs": FolderLocation("docs", _chain(1, 2)),
            "Docs": FolderLocation("Docs", _chain(1, 2)),
        },
        answering=frozenset({"old"}),
    )

    with pytest.raises(RequestError) as raised:
        await _create(PullSources(unit_of_work, registry), "new", "Docs")

    assert raised.value.code is ErrorCode.SOURCE_FOLDER_OVERLAP


async def test_답하는_원천은_글자가_겹쳐_보여도_다른_폴더면_겹치지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = await _existing(engine, "old", "docs")
    registry = _FolderRegistry(
        {
            "docs": FolderLocation("docs", _chain(1, 2)),
            "docs/a": FolderLocation("docs/a", _chain(1, 3, 4)),
        },
        answering=frozenset({"old"}),
    )

    await _create(PullSources(unit_of_work, registry), "new", "docs/a")

    async with unit_of_work.begin() as transaction:
        names = {source.name for source in await transaction.catalog.list_sources()}
    assert "new" in names


async def test_답하지_않는_원천과는_저장된_글자를_NFC로_맞춰_견주어_겹친다(
    engine: AsyncEngine,
) -> None:
    decomposed = unicodedata.normalize("NFD", "한글/문서")
    composed = unicodedata.normalize("NFC", "한글/문서/하위")
    unit_of_work = await _existing(engine, "old", decomposed)
    registry = _FolderRegistry(
        {composed: FolderLocation(composed, _chain(1, 2, 3, 4))}, answering=frozenset()
    )

    with pytest.raises(RequestError) as raised:
        await _create(PullSources(unit_of_work, registry), "new", composed)

    assert raised.value.code is ErrorCode.SOURCE_FOLDER_OVERLAP


async def test_답하지_않는_원천과는_토막_단위로_견주어_이름이_앞머리만_같으면_겹치지_않는다(
    engine: AsyncEngine,
) -> None:
    unit_of_work = await _existing(engine, "old", "docs")
    registry = _FolderRegistry(
        {"docs2": FolderLocation("docs2", _chain(1, 5))}, answering=frozenset()
    )

    await _create(PullSources(unit_of_work, registry), "new", "docs2")

    async with unit_of_work.begin() as transaction:
        names = {source.name for source in await transaction.catalog.list_sources()}
    assert "new" in names
