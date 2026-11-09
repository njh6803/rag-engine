"""관리 명령의 입구. `rag-engine serve` 가 HTTP 서버를 띄운다."""

import argparse
from collections.abc import Sequence

import uvicorn

from rag_engine.server import create_app


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag-engine")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="HTTP 서버를 띄운다")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    host: str = args.host
    port: int = args.port
    uvicorn.run(create_app(), host=host, port=port)
