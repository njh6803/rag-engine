"""헌법 환경 규약: 한국어 출력이 cp949로 깨지지 않게 stdout을 UTF-8로 고정한다.

원칙 I: 환경 부재로 skip된 테스트는 초록이 아니다. skip 이 하나라도 있으면 세션을 실패로 끝낸다.

pre-commit 이 워크트리에서 훅을 돌리면 git 이 `GIT_DIR` 같은 저장소 위치 변수를 자식에
내보낸다. 그 값이 남으면 테스트의 `git init` 이 임시 디렉터리가 아니라 이 저장소를 재초기화한다
(agent-os 2026-09-28 실측. 공유 config 의 core.bare 가 true 가 되어 체크아웃 전부가 work tree 를
잃었다). 저장소를 가리키는 변수만 벗긴다. 목록은 `tools/run_hooks.py` 가 원천이다 — 러너도 자식
훅에서 같은 것을 벗긴다.

pre-commit 은 `SKIP` 에 든 훅을 건너뛰고, 그 값은 검사 러너와 pytest 를 거쳐 시험이 임시 저장소에서
띄우는 pre-commit 까지 이어진다. 그러면 시험 안의 그 훅이 파일이 없어서가 아니라 `SKIP` 때문에
건너뛰어져 출력이 달라진다(rag-engine 2026-11-09 킥오프 첫 커밋의 `SKIP=check-constitution-version`
이 헌법 판 검사의 시험 하나를 깨뜨렸다). 그래서 `SKIP` 도 벗긴다.

`rag_engine` 은 테스트와 같은 체크아웃의 `src` 에서 불려야 한다. `.venv` 의 editable 설치는 절대
경로라, 다른 체크아웃의 `.venv` 인터프리터(주 체크아웃의 것, IDE 가 잡은 것, 활성화된 셸의 것)로
워크트리의 테스트를 돌리면 테스트와 `tools` 는 이 체크아웃 것이 돌고 `rag_engine` 은 그쪽 `src` 가
불려 브랜치의 코드가 검사되지 않는다(agent-os 2026-10-05, 그렇게 돌린 테스트가 조용히 초록이었다).
그래서 세션을 시작하기 전에 멈춘다. 체크아웃은 `tools` 를 불러온 자리로 정한다.
`uv run pytest` 는 그 체크아웃의 `.venv` 를 쓰므로 걸리지 않는다.

매개변수 id 는 `pyproject.toml` 의 옵션이 이스케이프를 꺼 한국어를 그대로 둔다. 그 옵션은 줄바꿈
같은 인쇄되지 않는 문자도 그대로 두어 그런 값의 id 가 출력 줄을 갈랐다. 문자열 값에 그런 문자가
있으면 그 문자만 `\\n` 꼴로 되돌린다. 바이트 값은 그 옵션이 켜지면 pytest 가 문자열로 바꾸지 않아
수집이 죽으므로 언제나 `\\xff` 꼴의 문자열로 바꿔 같은 길로 보낸다. 손으로 준 id(`ids=` 의 목록과
함수, `pytest.param(id=...)`)는 이 훅을 거치지 않아 보지 않는다.
"""

import asyncio
import importlib.util
import io
import os
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from tools.run_checks import TEST_DATABASE_ENV, database_problem

from rag_engine.adapters.postgres.bootstrap import migrate_database
from rag_engine.adapters.settings import Settings
from tools import run_hooks

CHECKOUT = Path(run_hooks.__file__).resolve().parents[1]

for stream in (sys.stdout, sys.stderr):
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")

for name in run_hooks.REPO_LOCATION_VARS:
    os.environ.pop(name, None)
os.environ.pop("SKIP", None)


def pytest_configure(config: pytest.Config) -> None:
    spec = importlib.util.find_spec("rag_engine")
    origin = None if spec is None or spec.origin is None else Path(spec.origin).resolve()
    if origin is not None and origin.is_relative_to(CHECKOUT / "src"):
        return
    raise pytest.UsageError(
        f"rag_engine 이 이 체크아웃({CHECKOUT})의 src 가 아니라 {origin} 에서 불린다. 다른"
        " 체크아웃의 .venv 인터프리터다. 이 체크아웃에서 uv run pytest 로 돌린다"
    )


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    """psycopg 비동기는 Windows 의 기본 ProactorEventLoop 과 맞지 않아 Selector 루프를 쓴다
    (ADR 0011)."""
    return {"selector": asyncio.SelectorEventLoop}


def pytest_make_parametrize_id(config: pytest.Config, val: object, argname: str) -> str | None:
    if isinstance(val, bytes):
        text = val.decode("ascii", "backslashreplace")
    elif isinstance(val, str) and not val.isprintable():
        text = val
    else:
        return None
    return "".join(
        ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii") for ch in text
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    """테스트 PostgreSQL 의 접속 주소(`RAG_TEST_DATABASE_URL`). 데이터베이스를 쓰는 시험이 받는다.

    값이 없거나 서버가 답하지 않으면 skip 이 아니라 실패하고, 메시지가 띄우는 길을 알린다(원칙 I).
    세션에서 한 번 판정하고 그 시험들이 모두 같은 이유로 빨개진다.
    """
    problem = database_problem(os.environ)
    if problem is not None:
        pytest.fail(problem, pytrace=False)
    return os.environ[TEST_DATABASE_ENV]


def replace_database(url: str, name: str) -> str:
    return urlsplit(url)._replace(path=f"/{name}").geturl()


def _create_database(admin_url: str, name: str, template: str | None = None) -> None:
    query = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
    if template is not None:
        query += sql.SQL(" TEMPLATE {}").format(sql.Identifier(template))
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(query)


def _drop_database(admin_url: str, name: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )


def build_test_settings(database_url: str, data_dir: Path, **overrides: object) -> Settings:
    """시험의 설정 객체. `.env` 를 읽지 않고, 환경 변수는 아무도 쓰지 않는 접두로 읽어 개발자
    셸의 `RAG_*` 가 시험을 바꾸지 못한다. 값은 `overrides` 가 덮고, 없는 칸 이름은 거부한다."""
    unknown = set(overrides) - set(Settings.model_fields)
    if unknown:
        raise ValueError(f"설정에 없는 칸이다: {sorted(unknown)}")
    values: dict[str, object] = {
        "database_url": database_url,
        "data_dir": data_dir,
        "allowed_hosts": ["localhost"],
        "default_embedding_url": "http://tei:80",
        "default_reranker_url": "http://reranker:80",
        **overrides,
    }
    return Settings(_env_file=None, _env_prefix="RAG_TEST_UNUSED_", **values)


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    """`make_settings(database_url, 칸=값, …)` 으로 시험의 설정 객체를 짓는다."""

    def make(database_url: str, **overrides: object) -> Settings:
        return build_test_settings(database_url, tmp_path, **overrides)

    return make


@pytest.fixture
def empty_database_url(database_url: str) -> Iterator[str]:
    """시험마다 빈 데이터베이스를 하나 만들고 끝나면 지운다. 이름에 무작위 토막을 붙이는 까닭은
    테스트 서버 하나를 워크트리와 세션이 함께 쓰기 때문이다(core 01)."""
    name = f"rag_empty_{uuid4().hex}"
    _create_database(database_url, name)
    try:
        yield replace_database(database_url, name)
    finally:
        _drop_database(database_url, name)


@pytest.fixture(scope="session")
def template_database_name(
    database_url: str, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[str]:
    """세션(xdist 작업자마다 한 번)에 템플릿 데이터베이스를 만들고 alembic 과 기본 레코드
    보장을 돌린다. 끝나면 지운다(명세 "테스트 데이터베이스와 이미지 판")."""
    name = f"rag_template_{uuid4().hex}"
    _create_database(database_url, name)
    try:
        settings = build_test_settings(
            replace_database(database_url, name), tmp_path_factory.mktemp("data")
        )
        migrate_database(settings)
        yield name
    finally:
        _drop_database(database_url, name)


@pytest.fixture
def make_seeded_database(
    database_url: str, template_database_name: str
) -> Iterator[Callable[[], str]]:
    """부를 때마다 템플릿에서 복제한 데이터베이스(기본 레코드가 든다)의 주소를 낸다. 시험이 끝나면
    만든 것을 모두 지운다."""
    created: list[str] = []

    def make() -> str:
        name = f"rag_test_{uuid4().hex}"
        _create_database(database_url, name, template=template_database_name)
        created.append(name)
        return replace_database(database_url, name)

    try:
        yield make
    finally:
        for name in created:
            _drop_database(database_url, name)


@pytest.fixture
def seeded_database_url(make_seeded_database: Callable[[], str]) -> str:
    """기본 레코드가 든 데이터베이스 하나. 시험마다 새로 복제하고 끝나면 지운다."""
    return make_seeded_database()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if not isinstance(reporter, pytest.TerminalReporter):
        return
    skipped = reporter.stats.get("skipped", [])
    if not skipped:
        return
    reporter.write_line(
        f"skip {len(skipped)}건. skip된 테스트는 초록이 아니다(원칙 I). -rs 로 이유를 본다",
        red=True,
    )
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
