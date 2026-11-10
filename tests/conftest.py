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
import logging
import os
import socket
import sys
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import uvicorn
from psycopg import sql
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.harness import LogCapture, RunningServer, replace_database
from tests.support.pipeline import Pipeline, build_pipeline
from tests.support.round_trip import RoundTrip, new_stub, point_default_version_at
from tests.support.tei_server import serve_stub
from tools.run_checks import TEST_DATABASE_ENV, database_problem

from rag_engine.adapters.postgres.bootstrap import issue_bootstrap_token, migrate_database
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.migrate import upgrade_to_head
from rag_engine.adapters.settings import Settings
from rag_engine.server import create_app
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


@pytest.fixture
async def engine(empty_database_url: str) -> AsyncIterator[AsyncEngine]:
    """스키마만 올린 빈 데이터베이스에 붙은 엔진. `migrate`의 기본 레코드는 없다."""
    await asyncio.to_thread(upgrade_to_head, empty_database_url)
    created = create_engine(empty_database_url)
    try:
        yield created
    finally:
        await created.dispose()


@pytest.fixture
def round_trip(server: RunningServer) -> Iterator[RoundTrip]:
    """수집 → 작업자 한 번 → `search`의 왕복 도우미. 임베딩 스텁을 실제 포트에 띄우고 서버의
    기본 판이 그 주소를 쓰게 한다(`tests/support/round_trip.py`)."""
    stub = new_stub()
    with serve_stub(stub) as endpoint:
        point_default_version_at(server, endpoint)
        yield RoundTrip(server, stub)


@pytest.fixture
async def pipeline(engine: AsyncEngine, tmp_path: Path) -> AsyncIterator[Pipeline]:
    """수집에서 색인까지 이어 보는 세계(`tests/support/pipeline.py`). 임베딩 서버만 스텁이다."""
    built = await build_pipeline(engine, tmp_path)
    try:
        yield built
    finally:
        await built.pool.aclose()


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


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    """`create_app`과 `configure_logging`이 루트 로거와 uvicorn·MCP 로거를 바꾼다. 시험이 끝나면
    되돌려 다른 시험에 핸들러가 남지 않게 한다."""
    names = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "mcp")
    saved = [(logging.getLogger(name), list(logging.getLogger(name).handlers)) for name in names]
    levels = [(logger, logger.level, logger.propagate) for logger, _ in saved]
    yield
    for logger, handlers in saved:
        logger.handlers[:] = handlers
    for logger, level, propagate in levels:
        logger.setLevel(level)
        logger.propagate = propagate


STARTUP_TIMEOUT_SECONDS = 10


@pytest.fixture
def run_server(
    seeded_database_url: str, make_settings: Callable[..., Settings]
) -> Iterator[Callable[..., RunningServer]]:
    """`run_server(칸=값, …)`이 기본 레코드가 든 데이터베이스에 붙은 서버를 127.0.0.1의 빈 포트에
    띄운다. 서버는 스레드에서 돌고 시험이 끝나면 내린다. 세션 없는 SDK 클라이언트와 httpx가 실제
    HTTP로 접속한다(`.claude/rules/tests.md`). 시험 하나에서 서버는 하나만 띄운다. 관리 토큰을
    `bootstrap-token`과 같은 길로 발급하므로, 살아 있는 `admin`이 이미 있으면(`server`와 함께 받거나
    두 번 부르면) 발급이 없어 `assert`로 실패한다."""
    running: list[tuple[uvicorn.Server, threading.Thread]] = []

    def start(**overrides: object) -> RunningServer:
        # 서버가 붙을 데이터베이스는 덮어쓸 수 있다. 토큰은 언제나 시드 데이터베이스에서 낸다.
        server_database_url = overrides.pop("database_url", seeded_database_url)
        assert isinstance(server_database_url, str)
        settings = make_settings(server_database_url, **overrides)
        # 토큰은 언제나 기본 레코드가 든 데이터베이스에 발급한다. 서버가 다른 데이터베이스를
        # 가리키게 한 시험도 쓸 토큰 원문을 얻는다.
        issued = issue_bootstrap_token(make_settings(seeded_database_url), "시험")
        assert issued is not None
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        # uvicorn의 로그 설정은 로거를 자기 핸들러로 바꾸므로 끄고, `create_app`이 우리 포매터를
        # 단다.
        config = uvicorn.Config(
            create_app(settings),
            log_config=None,
            access_log=False,
            loop="asyncio:SelectorEventLoop",
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        running.append((server, thread))
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while not server.started:
            if time.monotonic() > deadline:
                pytest.fail(f"uvicorn 이 {STARTUP_TIMEOUT_SECONDS}초 안에 뜨지 않았다")
            time.sleep(0.01)
        return RunningServer(
            base_url=f"http://127.0.0.1:{port}",
            host="127.0.0.1",
            port=port,
            settings=settings,
            admin_token=issued.raw,
        )

    yield start
    for server, thread in running:
        server.should_exit = True
        thread.join(STARTUP_TIMEOUT_SECONDS)


@pytest.fixture
def server(run_server: Callable[..., RunningServer]) -> RunningServer:
    """기본 설정의 서버 하나."""
    return run_server()


@pytest.fixture
def log_capture(capsys: pytest.CaptureFixture[str]) -> Iterator[LogCapture]:
    """서버가 stdout에 찍는 로그를 읽는다. 서버를 띄우는 픽스처보다 먼저 받으면 기동 로그부터
    든다. 서버와 시험 클라이언트가 한 프로세스라 클라이언트 로거(`httpx`)가 요청 URL을 같은
    stdout에 남기므로 서버 로그만 남도록 그 로거를 WARNING으로 올린다."""
    client_loggers = [logging.getLogger(name) for name in ("httpx", "httpcore")]
    levels = [logger.level for logger in client_loggers]
    for logger in client_loggers:
        logger.setLevel(logging.WARNING)
    yield LogCapture(capsys)
    for logger, level in zip(client_loggers, levels, strict=True):
        logger.setLevel(level)


def _apply_command_environment(
    database_url: str, monkeypatch: pytest.MonkeyPatch, work_dir: Path
) -> None:
    """관리 명령은 환경 변수와 작업 폴더의 `.env`를 읽는다. 개발자 셸의 `RAG_*`와 `.env`가 시험을
    바꾸지 못하게 지우고 빈 작업 폴더에서 돈다(시험이 쓰는 `RAG_TEST_DATABASE_URL`은 남긴다)."""
    for name in [name for name in os.environ if name.startswith("RAG_")]:
        if name != TEST_DATABASE_ENV:
            monkeypatch.delenv(name)
    monkeypatch.chdir(work_dir)
    monkeypatch.setenv("RAG_DATABASE_URL", database_url)
    monkeypatch.setenv("RAG_DATA_DIR", "/data")
    monkeypatch.setenv("RAG_ALLOWED_HOSTS", "localhost")
    monkeypatch.setenv("RAG_DEFAULT_EMBEDDING_URL", "http://tei:80")


@pytest.fixture
def command_environment(
    empty_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """빈 데이터베이스를 가리키는 관리 명령의 환경."""
    _apply_command_environment(empty_database_url, monkeypatch, tmp_path)


@pytest.fixture
def seeded_command_environment(
    seeded_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> str:
    """기본 레코드가 든 데이터베이스를 가리키는 관리 명령의 환경. 그 데이터베이스의 주소를 낸다."""
    _apply_command_environment(seeded_database_url, monkeypatch, tmp_path)
    return seeded_database_url


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
