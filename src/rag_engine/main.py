"""관리 명령의 입구. `rag-engine serve` 가 HTTP 서버를 띄우고 `rag-engine migrate` 가 데이터베이스를
올리며 `rag-engine bootstrap-token` 이 첫 관리 토큰을 낸다."""

import argparse
import sys
from collections.abc import Callable, Sequence

import uvicorn

from rag_engine.adapters.postgres.bootstrap import issue_bootstrap_token, migrate_database
from rag_engine.adapters.settings import Settings, load_settings
from rag_engine.domain.errors import ConfigurationError
from rag_engine.server import create_app


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag-engine")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="HTTP 서버를 띄운다")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("migrate", help="스키마를 올리고 기본 레코드를 보장한다")
    bootstrap = commands.add_parser("bootstrap-token", help="첫 admin 토큰을 발급한다")
    bootstrap.add_argument("--name", default="bootstrap")
    args = parser.parse_args(argv)
    if args.command == "migrate":
        _exit_unless_ok(_migrate())
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


def _migrate() -> int:
    def run(settings: Settings) -> int:
        migrate_database(settings)
        return 0

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
