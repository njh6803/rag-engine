"""SQLAlchemy 2.x 비동기 엔진이 psycopg 3 방언으로 만들어지고 pgvector·alembic이 함께 import되는지
본다.

실행(저장소 밖 의존성을 임시로 얹는다):
    uv run --with "sqlalchemy[asyncio]" --with "psycopg[binary]" --with pgvector --with alembic \
        python .scratch/core/probes/sqlalchemy-async/probe.py
타입 검사:
    uv run --with "sqlalchemy[asyncio]" --with "psycopg[binary]" --with pgvector --with alembic \
        pyright .scratch/core/probes/sqlalchemy-async/probe.py
`uv run --with`는 Windows에서 greenlet 휠의 `.data` 디렉터리 잠금(os error 32)으로 두 번 실패해,
임시 가상환경 (`uv venv` + `uv pip install` 같은 네 패키지)의 python과
`uv run pyright --pythonpath <그 python>`으로
돌렸다(2026-11-09). 결과: is_async True, alembic 템플릿에 async·pyproject_async, 넷 다 py.typed,
greenlet 3.5.6(MIT AND PSF-2.0) 필요, pyright 0 오류.
저장소로 옮긴 뒤(2026-11-09) 다시 검사했다. 저장소 pyright 설정은 기본 exclude(`**/.*`)로
`.scratch` 아래를 건너뛰어 0 오류가 공허할 수 있으므로, exclude 를 비운 임시 pyrightconfig 를
`-p` 로, 위 가상환경의 python 을 `--pythonpath` 로 주고 `--outputjson` 으로 봤다.
filesAnalyzed 1, 0 오류(`pyright_out.json`). 임시 가상환경 실행의 표준 출력은 `probe_out.txt` 에
남겼다. 셀프 리뷰가 greenlet 의 판과 라이선스가 출력에 없다고 짚어 마지막 줄로 더하고 다시 돌렸다.
데이터베이스에 접속하지는 않는다. 엔진 생성과 방언의 비동기 여부, 패키지 판과 py.typed만 본다.
"""

from __future__ import annotations

import importlib.metadata as md
from pathlib import Path
from types import ModuleType

import alembic
import pgvector
import psycopg
import sqlalchemy
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def main() -> None:
    engine: AsyncEngine = create_async_engine("postgresql+psycopg://u:p@localhost:1/db")
    dialect = engine.dialect
    print("dialect", dialect.name, dialect.driver, "is_async", dialect.is_async)
    print("Vector", repr(Vector(1024)))
    templates = Path(alembic.__file__).parent / "templates"
    print("alembic templates", sorted(p.name for p in templates.iterdir()))
    modules: list[tuple[str, ModuleType]] = [
        ("sqlalchemy", sqlalchemy),
        ("psycopg", psycopg),
        ("pgvector", pgvector),
        ("alembic", alembic),
    ]
    for name, module in modules:
        typed = (Path(module.__file__ or "").parent / "py.typed").exists()
        print(name, md.version(name), "py.typed" if typed else "NO py.typed")
    greenlet = md.distribution("greenlet")
    print("greenlet", greenlet.version, "license", greenlet.metadata["License-Expression"])


if __name__ == "__main__":
    main()
