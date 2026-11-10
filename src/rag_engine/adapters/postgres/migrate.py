"""`alembic upgrade head`를 코드에서 돌린다. 관리 명령 `migrate`와 시험이 같은 길을 쓴다(ADR 0011).

접속 문자열은 하나(`RAG_DATABASE_URL`, ADR 0002)이고 스킴은 `postgresql://`(psycopg 직접
접속용)이다. SQLAlchemy 엔진은 `postgresql+psycopg://`가 필요해 여기서 바꾼다.

alembic 환경이 자기 이벤트 루프를 열므로(`migrations/env.py`) 실행 중인 이벤트 루프 안에서는 부를 수
없다. 비동기 코드에서는 스레드로 넘겨 부른다.
"""

import asyncio
from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config

MIGRATIONS_DIRECTORY: Final = Path(__file__).parent / "migrations"

_SYNC_SCHEME: Final = "postgresql://"
_ASYNC_SCHEME: Final = "postgresql+psycopg://"


def async_database_url(database_url: str) -> str:
    """`postgresql://` 주소를 비동기 SQLAlchemy 엔진의 주소로 바꾼다. 다른 스킴은 거부한다."""
    if not database_url.startswith(_SYNC_SCHEME):
        raise ValueError("접속 문자열은 postgresql:// 로 시작해야 한다")
    return _ASYNC_SCHEME + database_url.removeprefix(_SYNC_SCHEME)


def upgrade_to_head(database_url: str) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "실행 중인 이벤트 루프 안에서는 부를 수 없다. asyncio.to_thread로 부른다"
        )
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    config.attributes["url"] = async_database_url(database_url)
    command.upgrade(config, "head")
