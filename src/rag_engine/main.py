"""관리 명령의 입구. `rag-engine serve` 가 HTTP 서버를 띄우고 `rag-engine migrate` 가 데이터베이스를
올린다."""

import argparse
import sys
from collections.abc import Sequence

import uvicorn
from pydantic import ValidationError

from rag_engine.adapters.postgres.bootstrap import migrate_database
from rag_engine.adapters.settings import Settings
from rag_engine.domain.errors import ConfigurationError
from rag_engine.server import create_app


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag-engine")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="HTTP 서버를 띄운다")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("migrate", help="스키마를 올리고 기본 레코드를 보장한다")
    args = parser.parse_args(argv)
    if args.command == "migrate":
        exit_code = _migrate()
        if exit_code != 0:
            sys.exit(exit_code)
        return
    host: str = args.host
    port: int = args.port
    uvicorn.run(create_app(), host=host, port=port)


def _migrate() -> int:
    try:
        settings = Settings()
    except ValidationError as error:
        # 검증 오류의 메시지는 입력 값(연결 문자열의 비밀번호)을 싣는다. 칸 이름만 찍는다.
        for problem in error.errors():
            name = "RAG_" + ".".join(str(part) for part in problem["loc"]).upper()
            print(f"설정 오류: {name}: {problem['type']}", file=sys.stderr)
        return 1
    try:
        migrate_database(settings)
    except ConfigurationError as error:
        print(f"설정 오류: {error}", file=sys.stderr)
        return 1
    return 0
