"""tools/run_checks.py 의 테스트 데이터베이스 준비(core 01).

서버가 답하는지는 진짜 소켓으로 본다. PostgreSQL 은 연결 첫머리에 SSL 요청(8바이트)을 받으면 한
글자(`S`나 `N`)로 답한다. Docker 의 포트 전달은 안쪽 서버가 없어도 연결을 받고 바로 끊으므로,
연결만 되는지가 아니라 이 답을 본다. 띄우기는 가짜 `docker` 실행 파일로 인자와 실패 갈래를 본다.
진짜 Docker 로 띄우는 길은 손으로 커밋 훅을 돌려 확인한다(티켓 01).
"""

from __future__ import annotations

import contextlib
import os
import re
import socket
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Generator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from tools.run_checks import (
    CHECKS,
    COMPOSE_FILE,
    TEST_DATABASE_ENV,
    TEST_DATABASE_URL,
    DatabaseNotReady,
    Outcome,
    compose_up,
    database_problem,
    prepare_test_database,
    server_answers,
)

from tools import run_checks

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "pgvector/pgvector:0.8.7-pg18-trixie"


@contextlib.contextmanager
def _답하는_서버(reply: bytes | None) -> Generator[int]:
    """연결마다 8바이트를 읽고 `reply` 로 답하는 서버. `reply` 가 None 이면 읽지 않고 끊는다
    (안쪽 서버가 없는 Docker 의 포트 전달). 열린 포트를 내고, 나갈 때 닫는다."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    server.settimeout(0.2)
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conn:
                if reply is None:
                    continue
                conn.settimeout(2)
                with contextlib.suppress(OSError):
                    conn.recv(8)
                    conn.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield server.getsockname()[1]
    finally:
        stop.set()
        server.close()
        thread.join(timeout=5)


def _닫힌_포트() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _주소(port: int) -> str:
    return f"postgresql://rag_test:rag_test@127.0.0.1:{port}/rag_test"


def _글(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def _CI_python_잡() -> str:
    match = re.search(
        r"^  python:\n(.*?)^  image:",
        _글(".github", "workflows", "ci.yml"),
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "python 잡을 찾지 못했다"
    return match.group(1)


@pytest.mark.parametrize("reply", [b"S", b"N"])
def test_SSL_요청에_한_글자로_답하는_서버는_답하는_서버다(reply: bytes) -> None:
    with _답하는_서버(reply) as port:
        assert server_answers("127.0.0.1", port)


def test_연결을_받고_바로_끊는_포트는_답하는_서버가_아니다() -> None:
    """Docker 의 포트 전달은 컨테이너가 준비되기 전에도 연결을 받는다."""
    with _답하는_서버(None) as port:
        assert not server_answers("127.0.0.1", port)


def test_닫힌_포트는_답하는_서버가_아니다() -> None:
    assert not server_answers("127.0.0.1", _닫힌_포트())


def test_PostgreSQL_이_아닌_글자로_답하는_서버는_답하는_서버가_아니다() -> None:
    with _답하는_서버(b"HTTP/1.1 400 Bad Request\r\n") as port:
        assert not server_answers("127.0.0.1", port)


@pytest.mark.parametrize("host", ["a..b", "x" * 70 + ".example"])
def test_이름_풀이가_거절하는_호스트는_예외가_아니라_답하지_않는_서버다(host: str) -> None:
    """IDNA 인코딩이 빈 레이블이나 64자 넘는 레이블을 `UnicodeError` 로 거절한다."""
    assert not server_answers(host, 5432)


def test_기본_주소는_compose_와_같은_판의_이미지_역할_포트를_가리킨다() -> None:
    """compose 파일과 기본 주소가 따로 늙지 않게 한다. 둘 다 사람이 쓰므로 글자로 맞댄다."""
    compose = _글(COMPOSE_FILE)
    parts = urlsplit(TEST_DATABASE_URL)

    assert f"image: {IMAGE}" in compose
    assert f"POSTGRES_USER: {parts.username}" in compose
    assert f"POSTGRES_PASSWORD: {parts.password}" in compose
    assert f"POSTGRES_DB: {parts.path.removeprefix('/')}" in compose
    assert f'"127.0.0.1:{parts.port}:5432"' in compose
    assert parts.hostname == "127.0.0.1"


def test_compose_에_기다릴_준비_신호가_있다() -> None:
    """`up --wait` 는 준비 신호가 없으면 기다리지 않고 돌아온다. 역할이 데이터베이스를 만들 수
    있는지는 `tests/test_test_database.py` 가 서버에 붙어 본다."""
    assert "healthcheck:" in _글(COMPOSE_FILE)


def test_준비_신호는_TCP_로_본다() -> None:
    """`pg_isready` 의 기본은 유닉스 소켓이다. 이미지가 처음 초기화하는 동안 뜨는 임시 서버가 그
    소켓으로 답해, 진짜 서버가 TCP 로 뜨기 전에 healthy 가 되고 `up --wait` 가 돌아왔다(러너로 첫
    띄움에서 손으로 봤다). 서비스 컨테이너의 CI 도 같다."""
    assert "pg_isready -h 127.0.0.1" in _글(COMPOSE_FILE)
    assert "pg_isready -h 127.0.0.1" in _CI_python_잡()


def test_CI_의_python_잡은_같은_이미지를_서비스_컨테이너로_띄우고_주소를_넘긴다() -> None:
    job = _CI_python_잡()
    parts = urlsplit(TEST_DATABASE_URL)
    database = parts.path.removeprefix("/")

    assert "services:" in job
    assert f"image: {IMAGE}" in job
    assert f"POSTGRES_USER: {parts.username}" in job
    assert f"POSTGRES_PASSWORD: {parts.password}" in job
    assert f"POSTGRES_DB: {database}" in job
    assert "--health-cmd" in job, "서비스 컨테이너가 준비되기 전에 pytest 가 시작한다"
    expected = f"{TEST_DATABASE_ENV}: postgresql://{parts.username}:{parts.password}@127.0.0.1:5432"
    assert f"{expected}/{database}" in job


def test_데이터베이스_문제가_없으면_None_이다() -> None:
    with _답하는_서버(b"N") as port:
        assert database_problem({TEST_DATABASE_ENV: _주소(port)}) is None


def test_주소가_없으면_띄우는_길을_한_줄로_알린다() -> None:
    problem = database_problem({})

    assert problem is not None
    assert "\n" not in problem
    assert TEST_DATABASE_ENV in problem
    assert COMPOSE_FILE in problem
    assert "tools/run_checks.py" in problem


def test_서버가_답하지_않으면_주소와_띄우는_길을_한_줄로_알린다() -> None:
    port = _닫힌_포트()

    problem = database_problem({TEST_DATABASE_ENV: _주소(port)})

    assert problem is not None
    assert "\n" not in problem
    assert f"127.0.0.1:{port}" in problem
    assert COMPOSE_FILE in problem
    assert "tools/run_checks.py" in problem


def test_포트_0_은_기본_포트로_바꾸지_않고_그_포트로_알린다() -> None:
    problem = database_problem({TEST_DATABASE_ENV: "postgresql://u:p@127.0.0.1:0/x"})

    assert problem is not None
    assert "127.0.0.1:0 " in problem


def test_주소의_모양이_틀리면_그_값을_밝히지_않고_모양이_틀리다고_알린다() -> None:
    """값에 비밀번호가 들 수 있다(원칙 V)."""
    problem = database_problem({TEST_DATABASE_ENV: "비밀번호가 든 엉뚱한 글자"})

    assert problem is not None
    assert "비밀번호가 든 엉뚱한 글자" not in problem
    assert TEST_DATABASE_ENV in problem


def _순서대로_답하는(sequence: list[bool]) -> Callable[[str, int], bool]:
    """부를 때마다 `sequence` 의 다음 값으로 답한다. 다 쓰면 마지막 값을 되풀이한다."""
    calls = iter(sequence)
    last = sequence[-1]

    def answers(host: str, port: int) -> bool:
        return next(calls, last)

    return answers


def _띄우기_기록() -> tuple[list[str], Callable[[], None]]:
    started: list[str] = []
    return started, lambda: started.append("띄움")


def test_준비는_주소가_가리키는_서버가_답하면_띄우지_않고_그_주소를_돌려준다() -> None:
    started, start = _띄우기_기록()
    url = "postgresql://u:p@db.example:6543/x"

    result = prepare_test_database(
        {TEST_DATABASE_ENV: url}, start_server=start, is_up=_순서대로_답하는([True])
    )

    assert result == url
    assert started == []


def test_준비는_주소가_없고_기본_서버가_답하면_기본_주소를_돌려준다() -> None:
    started, start = _띄우기_기록()

    result = prepare_test_database({}, start_server=start, is_up=_순서대로_답하는([True]))

    assert result == TEST_DATABASE_URL
    assert started == []


def test_준비는_기본_서버가_안_보이면_compose_로_띄우고_준비되면_주소를_돌려준다() -> None:
    started, start = _띄우기_기록()

    result = prepare_test_database({}, start_server=start, is_up=_순서대로_답하는([False, True]))

    assert result == TEST_DATABASE_URL
    assert started == ["띄움"]


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test/",
        "postgresql://rag_test:rag_test@localhost:55432/rag_test",
        "postgresql://rag_test:rag_test@127.0.0.1:55432/다른_데이터베이스",
        "postgres://u:p@127.0.0.1:55432",
    ],
)
def test_준비는_compose_가_여는_서버를_다르게_적은_주소도_안_보이면_띄운다(url: str) -> None:
    """끝 슬래시, `localhost`, 데이터베이스 이름은 달라도 같은 서버다."""
    started, start = _띄우기_기록()

    result = prepare_test_database(
        {TEST_DATABASE_ENV: url}, start_server=start, is_up=_순서대로_답하는([False, True])
    )

    assert result == url
    assert started == ["띄움"]


def test_준비는_띄우기가_실패하면_그_이유를_그대로_알린다() -> None:
    def start() -> None:
        raise DatabaseNotReady("Docker 를 켠다")

    with pytest.raises(DatabaseNotReady, match="^Docker 를 켠다$"):
        prepare_test_database({}, start_server=start, is_up=_순서대로_답하는([False]))


def test_준비는_띄웠는데도_서버가_안_보이면_실패다() -> None:
    started, start = _띄우기_기록()

    with pytest.raises(DatabaseNotReady) as info:
        prepare_test_database({}, start_server=start, is_up=_순서대로_답하는([False, False]))

    assert started == ["띄움"]
    assert "\n" not in str(info.value)
    assert "127.0.0.1:55432" in str(info.value)


def test_준비는_다른_주소가_안_보이면_띄우지_않고_그_주소가_안_보인다고_알린다() -> None:
    """compose 가 띄우는 서버는 한 곳이다. 남의 주소가 안 보이는 것을 고치지 못한다."""
    started, start = _띄우기_기록()
    url = "postgresql://u:secret@db.example:6543/x"

    with pytest.raises(DatabaseNotReady) as info:
        prepare_test_database(
            {TEST_DATABASE_ENV: url}, start_server=start, is_up=_순서대로_답하는([False])
        )

    assert started == []
    assert "\n" not in str(info.value)
    assert "db.example:6543" in str(info.value)
    assert "secret" not in str(info.value)


def test_준비는_모양이_틀린_주소의_값을_밝히지_않고_실패한다() -> None:
    with pytest.raises(DatabaseNotReady) as info:
        prepare_test_database(
            {TEST_DATABASE_ENV: "mysql://u:secret@h/x"},
            start_server=lambda: None,
            is_up=_순서대로_답하는([True]),
        )

    assert "secret" not in str(info.value)
    assert TEST_DATABASE_ENV in str(info.value)


def _가짜_docker(directory: Path, *, code: int, output: str) -> Path:
    """PATH 에 둘 가짜 `docker`. 받은 인자를 `args.txt` 에 한 줄로 적고 `output` 을 찍고 `code` 로
    끝난다. 윈도는 `.cmd`, 그 밖은 실행 권한이 있는 sh 다."""
    script = directory / "fake_docker.py"
    record = directory / "args.txt"
    script.write_text(
        "import pathlib, sys\n"
        f"pathlib.Path({str(record)!r}).write_text(' '.join(sys.argv[1:]), encoding='utf-8')\n"
        f"print({output!r})\n"
        f"sys.exit({code})\n",
        encoding="utf-8",
    )
    if sys.platform == "win32":
        launcher = directory / "docker.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="ascii")
    else:
        launcher = directory / "docker"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    return record


def test_띄우기는_compose_test_yml_을_백그라운드로_띄우고_준비를_기다린다(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 한국어 테스트 이름이 든 tmp_path 는 윈도의 .cmd 가 읽지 못한다
    docker_dir = tmp_path_factory.mktemp("docker")
    record = _가짜_docker(docker_dir, code=0, output="Container ready")
    monkeypatch.setenv("PATH", str(docker_dir))

    compose_up()

    assert record.read_text(encoding="utf-8") == f"compose -f {COMPOSE_FILE} up -d --wait"


def test_띄우기는_이미지를_받을_시간을_주되_끝없이_기다리지_않는다(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    docker_dir = tmp_path_factory.mktemp("docker")
    _가짜_docker(docker_dir, code=0, output="")
    monkeypatch.setenv("PATH", str(docker_dir))
    seen: list[float] = []

    def run_one(check: run_checks.Check, cwd: Path) -> Outcome:
        seen.append(check.timeout)
        return Outcome(check, passed=True, output=b"", seconds=0.0)

    monkeypatch.setattr(run_checks, "run_one", run_one)

    compose_up()

    assert len(seen) == 1
    assert 300 <= seen[0] <= 1800


def test_띄우기가_실패하면_마지막_출력_줄과_점검할_것을_한_줄로_알린다(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    docker_dir = tmp_path_factory.mktemp("docker")
    _가짜_docker(docker_dir, code=1, output="앞 줄\nCannot connect to the Docker daemon")
    monkeypatch.setenv("PATH", str(docker_dir))

    with pytest.raises(DatabaseNotReady) as info:
        compose_up()

    message = str(info.value)
    assert "\n" not in message
    assert "Docker 가 켜져 있는지" in message
    assert "포트" in message
    assert "Cannot connect to the Docker daemon" in message
    assert "앞 줄" not in message


def test_docker_명령이_없으면_설치하고_켜라고_한_줄로_알린다(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path_factory.mktemp("empty")))

    with pytest.raises(DatabaseNotReady) as info:
        compose_up()

    assert "\n" not in str(info.value)
    assert "docker 명령을 찾지 못했다" in str(info.value)


def _러너_CLI(env: dict[str, str], skips: list[str]) -> subprocess.CompletedProcess[str]:
    """러너 CLI 를 부른다. PATH 를 빈 디렉터리로 두어 `uv` 를 찾지 못하는 검사는 곧바로 실패하고
    진짜 검사를 띄우지 않는다(test_run_checks.py `_cli`)."""
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_checks.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, **env, "SKIP": ",".join(skips)},
        check=False,
        timeout=120,
    )


def _pytest_말고_전부() -> list[str]:
    return [check.id for check in CHECKS if check.id != "pytest"]


def test_CLI_는_pytest_를_돌릴_때_서버가_안_보이면_test_db_실패를_찍고_1로_끝난다(
    tmp_path: Path,
) -> None:
    port = _닫힌_포트()
    env = {"PATH": str(tmp_path), TEST_DATABASE_ENV: f"postgresql://u:p@localhost:{port}/x"}

    process = _러너_CLI(env, _pytest_말고_전부())

    assert process.returncode == 1, process.stdout + process.stderr
    assert any(
        line.startswith("test-db") and "Failed" in line for line in process.stdout.splitlines()
    ), process.stdout
    assert f"localhost:{port}" in process.stdout


def test_CLI_는_서버가_답하면_test_db_통과를_찍고_pytest_는_다른_이유로_빨갛다(
    tmp_path: Path,
) -> None:
    with _답하는_서버(b"N") as port:
        process = _러너_CLI(
            {"PATH": str(tmp_path), TEST_DATABASE_ENV: _주소(port)}, _pytest_말고_전부()
        )

    lines = process.stdout.splitlines()
    assert any(line.startswith("test-db") and "Passed" in line for line in lines), process.stdout
    assert not any(line.startswith("test-db") and "Failed" in line for line in lines)
    assert any(line.startswith("pytest") and "Failed" in line for line in lines)
    assert "명령을 찾지 못했다: uv" in process.stdout, "uv 가 없어서 빨개져야 배관이 지나간 것이다"


def test_CLI_는_pytest_를_건너뛰면_데이터베이스를_보지_않는다(tmp_path: Path) -> None:
    port = _닫힌_포트()

    process = _러너_CLI(
        {"PATH": str(tmp_path), TEST_DATABASE_ENV: _주소(port)}, [check.id for check in CHECKS]
    )

    assert process.returncode == 0, process.stdout + process.stderr
    assert "test-db" not in process.stdout


def test_main_은_준비한_주소를_검사들이_물려받을_환경에_넣는다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """자식 pytest 는 이 프로세스의 환경을 물려받는다. 주소가 없어 기본 서버를 쓴 커밋에서도 세션
    픽스처가 같은 주소를 보려면 준비한 값이 환경에 있어야 한다."""
    monkeypatch.delenv("SKIP", raising=False)
    monkeypatch.setenv(TEST_DATABASE_ENV, "postgresql://before/x")
    seen: list[str | None] = []

    def 환경을_기록하고_통과한다(*_: object) -> int:
        seen.append(os.environ.get(TEST_DATABASE_ENV))
        return 0

    def 준비된_주소(*_: object) -> str:
        return "postgresql://ready/x"

    monkeypatch.setattr(run_checks, "prepare_test_database", 준비된_주소)
    monkeypatch.setattr(run_checks, "run", 환경을_기록하고_통과한다)

    assert run_checks.main() == 0
    assert seen == ["postgresql://ready/x"]


def _중첩_pytest(extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """데이터베이스 시험 하나만 담은 파일로 pytest 를 한 번 더 띄운다. 세션 픽스처 `database_url` 이
    skip 이 아니라 실패하는지, 종료 코드와 안내를 밖에서 본다."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != TEST_DATABASE_ENV and not key.startswith("PYTEST_XDIST")
    }
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_test_database.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**env, **extra},
        check=False,
        timeout=300,
    )


def test_주소가_없으면_데이터베이스_시험은_skip_이_아니라_실패하고_띄우는_길을_알린다() -> None:
    process = _중첩_pytest({})

    assert process.returncode == 1, process.stdout + process.stderr
    assert "skipped" not in process.stdout
    assert "1 error" in process.stdout
    assert f"{TEST_DATABASE_ENV} 가 없다" in process.stdout
    assert COMPOSE_FILE in process.stdout


def test_서버가_안_보이면_데이터베이스_시험은_skip_이_아니라_실패하고_그_주소를_알린다() -> None:
    port = _닫힌_포트()

    process = _중첩_pytest({TEST_DATABASE_ENV: _주소(port)})

    assert process.returncode == 1, process.stdout + process.stderr
    assert "skipped" not in process.stdout
    assert "1 error" in process.stdout
    assert f"127.0.0.1:{port} 가 답하지 않는다" in process.stdout
    assert COMPOSE_FILE in process.stdout
