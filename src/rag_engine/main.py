"""관리 명령의 입구. `rag-engine serve` 가 HTTP 서버를 띄우고 `rag-engine worker` 가 수집 작업자를
띄우며 `rag-engine migrate` 가 데이터베이스를 올리고 `rag-engine bootstrap-token` 이 첫 관리 토큰을
내며 `rag-engine ingest` 가 파일이나 폴더를 서버 없이 수집한다."""

import argparse
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import uvicorn

from rag_engine.adapters.ingest_command import ingest_path
from rag_engine.adapters.postgres.bootstrap import issue_bootstrap_token, migrate_database
from rag_engine.adapters.postgres.engine import run_in_selector_loop
from rag_engine.adapters.settings import Settings, load_settings
from rag_engine.domain.errors import ConfigurationError
from rag_engine.server import create_app
from rag_engine.worker.assembly import run_worker


def _seconds(text: str) -> float:
    """`nan`은 모든 비교가 거짓이라 제한 시간이 영영 오지 않으므로 인자 단계에서 거른다."""
    try:
        seconds = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"초를 숫자로 적는다: {text}") from None
    if math.isnan(seconds):
        raise argparse.ArgumentTypeError(f"초를 숫자로 적는다: {text}")
    return seconds


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag-engine")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="HTTP 서버를 띄운다")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("migrate", help="스키마를 올리고 기본 레코드를 보장한다")
    commands.add_parser("worker", help="수집 작업자를 띄운다")
    bootstrap = commands.add_parser("bootstrap-token", help="첫 admin 토큰을 발급한다")
    bootstrap.add_argument("--name", default="bootstrap")
    ingest = commands.add_parser("ingest", help="파일이나 폴더를 서버 없이 수집한다")
    ingest.add_argument("path", type=Path, help="수집할 파일이나 폴더")
    ingest.add_argument("--group", default=None, help="문서를 넣을 접근 그룹의 이름")
    ingest.add_argument("--wait", action="store_true", help="색인이 끝날 때까지 기다린다")
    ingest.add_argument(
        "--timeout",
        type=_seconds,
        default=0.0,
        help="--wait와 함께 쓰는 제한 시간(초). 0 이하면 끝까지 기다린다",
    )
    args = parser.parse_args(argv)
    if args.command == "ingest":
        path: Path = args.path
        group: str | None = args.group
        wait: bool = args.wait
        timeout: float = args.timeout
        _exit_unless_ok(_ingest(path, group, timeout if wait else None))
        return
    if args.command == "migrate":
        _exit_unless_ok(_migrate())
        return
    if args.command == "worker":
        _exit_unless_ok(_worker())
        return
    if args.command == "bootstrap-token":
        name: str = args.name
        _exit_unless_ok(_bootstrap_token(name))
        return
    host: str = args.host
    port: int = args.port
    _exit_unless_ok(_serve(host, port))


def _exit_unless_ok(exit_code: int) -> None:
    if exit_code != 0:
        sys.exit(exit_code)


def _with_settings(command: Callable[[Settings], int]) -> int:
    """설정을 읽어 명령을 돌린다. 설정 오류는 칸 이름만 알리고 종료 코드 1로 끝낸다(오류 메시지는
    값이 아니라 칸 이름만 싣는다, `load_settings`)."""
    try:
        return command(load_settings())
    except ConfigurationError as error:
        print(f"설정 오류: {error}", file=sys.stderr)
        return 1


def _serve(host: str, port: int) -> int:
    def run(settings: Settings) -> int:
        # 접근 로그는 쿼리 문자열이 든 경로를 남기므로 끄고(요청마다 `http_request` 이벤트가 경로
        # 템플릿으로 남긴다), uvicorn의 로그 설정은 로거를 자기 핸들러로 바꾸므로 끄고 우리
        # 포매터(`create_app`)를 쓴다. psycopg 비동기는 Windows의 기본 ProactorEventLoop과 맞지
        # 않아 Selector 루프를 고른다(ADR 0011).
        uvicorn.run(
            create_app(settings),
            host=host,
            port=port,
            access_log=False,
            log_config=None,
            loop="asyncio:SelectorEventLoop",
        )
        return 0

    return _with_settings(run)


def _worker() -> int:
    def run(settings: Settings) -> int:
        # psycopg 비동기는 Windows의 기본 ProactorEventLoop과 맞지 않아 Selector 루프를 고른다
        # (ADR 0011).
        return run_in_selector_loop(run_worker(settings))

    return _with_settings(run)


def _migrate() -> int:
    def run(settings: Settings) -> int:
        migrate_database(settings)
        return 0

    return _with_settings(run)


def _ingest(path: Path, group: str | None, wait_timeout_seconds: float | None) -> int:
    def run(settings: Settings) -> int:
        return ingest_path(settings, path, group=group, wait_timeout_seconds=wait_timeout_seconds)

    return _with_settings(run)


def _bootstrap_token(name: str) -> int:
    def run(settings: Settings) -> int:
        issued = issue_bootstrap_token(settings, name)
        if issued is None:
            print(
                "살아 있는 admin 토큰이 이미 있어 발급하지 않았다. 잃어버렸다면 데이터베이스의"
                " tokens 표에서 그 토큰의 revoked_at을 적고 다시 돌린다",
                file=sys.stderr,
            )
            return 1
        print(issued.raw)
        print("이 토큰은 다시 볼 수 없다. 안전한 곳에 보관한다", file=sys.stderr)
        return 0

    return _with_settings(run)
