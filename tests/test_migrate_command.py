"""`rag-engine migrate` 는 스키마를 올리고 기본 레코드를 설정값으로 보장한다(명세 "관리 명령").

시험은 빈 데이터베이스에서 시작한다. 판 요소의 비교로 "재색인 필요" 를 판정하는 것(관리 API의
`reindex_needed` 표시)은 core 14의 몫이라 여기서는 요소가 현재 판과 달라지는지까지만 본다.
"""

import asyncio
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from tools.run_checks import TEST_DATABASE_ENV

from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.adapters.postgres.bootstrap import migrate_database
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.postgres.vector_index import version_index_name
from rag_engine.adapters.settings import Settings
from rag_engine.domain.entities import (
    IndexVersion,
    IndexVersionStatus,
    KnowledgeBase,
)
from rag_engine.domain.errors import ConfigurationError
from rag_engine.domain.identifiers import new_id
from rag_engine.main import main

type SettingsFactory = Callable[..., Settings]


async def _read(settings: Settings) -> tuple[KnowledgeBase, list[IndexVersion]]:
    engine = create_engine(settings.database_url)
    try:
        async with PostgresUnitOfWork(engine).begin() as transaction:
            knowledge_base = await transaction.catalog.get_knowledge_base("default")
            assert knowledge_base is not None
            versions = await transaction.catalog.list_live_index_versions(knowledge_base.id)
    finally:
        await engine.dispose()
    return knowledge_base, versions


def _count(database_url: str, table: str) -> int:
    with psycopg.connect(database_url, autocommit=True) as connection:
        row = connection.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        ).fetchone()
    assert row is not None
    count: int = row[0]
    return count


async def test_빈_데이터베이스에_기본_원천과_그룹과_지식베이스와_첫_현재_판을_만든다(
    empty_database_url: str, make_settings: SettingsFactory
) -> None:
    settings = make_settings(empty_database_url)

    await asyncio.to_thread(migrate_database, settings)

    knowledge_base, versions = await _read(settings)
    assert (knowledge_base.name, knowledge_base.is_default) == ("default", True)
    assert knowledge_base.embedding_endpoint == "http://tei:80"
    assert knowledge_base.reranker_endpoint == "http://reranker:80"
    assert knowledge_base.reranker_model == "BAAI/bge-reranker-v2-m3"
    assert [version.status for version in versions] == [IndexVersionStatus.CURRENT]
    assert knowledge_base.current_index_version_id == versions[0].id
    assert versions[0].elements == compute_index_elements(
        "BAAI/bge-m3", 1024, knowledge_base.chunking
    )
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        assert connection.execute("SELECT name, kind FROM sources").fetchall() == [
            ("default", "push")
        ]
        assert connection.execute(
            "SELECT g.name FROM knowledge_base_groups l JOIN groups g ON g.id = l.group_id"
        ).fetchall() == [("default",)]
        assert connection.execute(
            "SELECT indexname FROM pg_indexes WHERE indexname = %s",
            [version_index_name(versions[0].id)],
        ).fetchall() == [(version_index_name(versions[0].id),)]


async def test_다시_돌려도_같은_상태이고_판은_하나뿐이다(
    empty_database_url: str, make_settings: SettingsFactory
) -> None:
    settings = make_settings(empty_database_url)
    await asyncio.to_thread(migrate_database, settings)
    first = await _read(settings)

    await asyncio.to_thread(migrate_database, settings)

    assert await _read(settings) == first
    assert [
        _count(empty_database_url, table) for table in ("sources", "groups", "index_versions")
    ] == [
        1,
        1,
        1,
    ]


async def test_설정을_바꾸고_다시_돌리면_지식베이스가_새_값을_들고_판_요소는_현재_판과_달라진다(
    empty_database_url: str, make_settings: SettingsFactory
) -> None:
    await asyncio.to_thread(migrate_database, make_settings(empty_database_url))
    changed = make_settings(
        empty_database_url,
        default_embedding_model="org/other-model",
        default_embedding_dimensions=768,
        default_chunk_tokens=256,
    )

    await asyncio.to_thread(migrate_database, changed)

    knowledge_base, versions = await _read(changed)
    assert (knowledge_base.embedding_model, knowledge_base.embedding_dimensions) == (
        "org/other-model",
        768,
    )
    assert knowledge_base.chunking.max_tokens == 256
    assert len(versions) == 1
    current = versions[0]
    wanted = compute_index_elements(
        knowledge_base.embedding_model, knowledge_base.embedding_dimensions, knowledge_base.chunking
    )
    assert wanted != current.elements
    assert wanted.embedding_model != current.elements.embedding_model
    assert wanted.chunking_hash != current.elements.chunking_hash


async def test_끝점만_바뀐_설정은_살아_있는_판의_끝점을_고치고_재색인_요소는_그대로다(
    empty_database_url: str, make_settings: SettingsFactory
) -> None:
    settings = make_settings(empty_database_url)
    await asyncio.to_thread(migrate_database, settings)
    knowledge_base, (current,) = await _read(settings)
    building = replace(current, id=new_id(), status=IndexVersionStatus.BUILDING)
    unrelated = replace(
        building, id=new_id(), embedding_model="org/other-model", embedding_dimensions=768
    )
    engine = create_engine(empty_database_url)
    try:
        async with PostgresUnitOfWork(engine).begin() as transaction:
            await transaction.catalog.add_index_version(building)
            await transaction.catalog.add_index_version(unrelated)
    finally:
        await engine.dispose()

    moved = make_settings(empty_database_url, default_embedding_url="http://new-tei:80")
    await asyncio.to_thread(migrate_database, moved)

    reloaded, versions = await _read(moved)
    endpoints = {version.id: version.embedding_endpoint for version in versions}
    assert reloaded.embedding_endpoint == "http://new-tei:80"
    assert endpoints == {
        current.id: "http://new-tei:80",
        building.id: "http://new-tei:80",
        unrelated.id: "http://tei:80",
    }
    wanted = compute_index_elements(
        reloaded.embedding_model, reloaded.embedding_dimensions, reloaded.chunking
    )
    assert all(
        version.elements == wanted
        for version in versions
        if version.id in (current.id, building.id)
    )
    assert knowledge_base.current_index_version_id == reloaded.current_index_version_id


async def test_차원이_2000을_넘으면_설정_오류로_지식베이스를_만들지도_고치지도_않는다(
    empty_database_url: str, make_settings: SettingsFactory
) -> None:
    too_large = make_settings(empty_database_url, default_embedding_dimensions=2001)

    with pytest.raises(ConfigurationError, match="2000"):
        await asyncio.to_thread(migrate_database, too_large)
    assert _count(empty_database_url, "knowledge_bases") == 0

    ok = make_settings(empty_database_url)
    await asyncio.to_thread(migrate_database, ok)
    before = await _read(ok)
    with pytest.raises(ConfigurationError, match="2000"):
        await asyncio.to_thread(migrate_database, too_large)
    assert await _read(ok) == before


async def test_2000차원은_받는다(empty_database_url: str, make_settings: SettingsFactory) -> None:
    settings = make_settings(empty_database_url, default_embedding_dimensions=2000)

    await asyncio.to_thread(migrate_database, settings)

    knowledge_base, _ = await _read(settings)
    assert knowledge_base.embedding_dimensions == 2000


@pytest.fixture
def command_environment(
    empty_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """명령은 환경 변수와 작업 폴더의 `.env`를 읽는다. 개발자 셸의 `RAG_*`와 `.env`가 시험을 바꾸지
    못하게 지우고 빈 작업 폴더에서 돈다(시험이 쓰는 `RAG_TEST_DATABASE_URL`은 남긴다)."""
    for name in [name for name in os.environ if name.startswith("RAG_")]:
        if name != TEST_DATABASE_ENV:
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAG_DATABASE_URL", empty_database_url)
    monkeypatch.setenv("RAG_DATA_DIR", "/data")
    monkeypatch.setenv("RAG_ALLOWED_HOSTS", "localhost")
    monkeypatch.setenv("RAG_DEFAULT_EMBEDDING_URL", "http://tei:80")


def test_migrate_명령은_성공하면_기본_지식베이스를_만들고_정상_종료한다(
    command_environment: None, empty_database_url: str
) -> None:
    main(["migrate"])

    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT k.name, v.status FROM knowledge_bases k"
            " JOIN index_versions v ON v.id = k.current_index_version_id"
        ).fetchall()
    assert rows == [("default", "current")]


def test_migrate_명령은_임베딩_끝점이_없으면_스키마를_올리기_전에_종료_코드_1이다(
    command_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    empty_database_url: str,
) -> None:
    monkeypatch.delenv("RAG_DEFAULT_EMBEDDING_URL")

    with pytest.raises(SystemExit) as caught:
        main(["migrate"])

    assert caught.value.code == 1
    assert "RAG_DEFAULT_EMBEDDING_URL" in capsys.readouterr().err
    with psycopg.connect(empty_database_url, autocommit=True) as connection:
        tables = connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
    assert tables == [(0,)]


def test_migrate_명령은_차원이_2000을_넘으면_종료_코드_1이다(
    command_environment: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RAG_DEFAULT_EMBEDDING_DIMENSIONS", "2001")

    with pytest.raises(SystemExit) as caught:
        main(["migrate"])

    assert caught.value.code == 1
    assert "2000" in capsys.readouterr().err


def test_migrate_명령은_필수_설정이_없으면_값을_찍지_않고_종료_코드_1이다(
    command_environment: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("RAG_ALLOWED_HOSTS")
    monkeypatch.setenv("RAG_DATABASE_URL", "postgresql://user:비밀번호@nowhere/db")

    with pytest.raises(SystemExit) as caught:
        main(["migrate"])

    error = capsys.readouterr().err
    assert caught.value.code == 1
    assert "RAG_ALLOWED_HOSTS" in error
    assert "비밀번호" not in error
