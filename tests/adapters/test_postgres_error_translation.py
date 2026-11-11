"""PostgreSQL 오류 번역(명세 "수집 파이프라인과 작업", 티켓 12).

작업 단위가 데이터베이스의 일시 오류(연결 실패와 끊김, 직렬화 실패, 교착, 관리자 종료)를 일시 실패
`database_unavailable`로 바꿔 올린다. `DataError`와 `IntegrityError` 같은 나머지는 일시 실패가
아니라서 그대로 올라간다. 서드파티 예외의 메시지(SQL 조각이나 연결 정보가 들 수 있다)는 옮기지
않는다.
"""

import psycopg
import pytest
import sqlalchemy as sa
from psycopg import errors as pg_errors
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.domain.errors import ErrorCode, TransientFailure

SECRET = "SECRET-PASSWORD-MUST-NOT-LEAK"


def _wrapped(sqlstate: str) -> DBAPIError:
    """그 SQLSTATE를 든 psycopg 예외를 SQLAlchemy가 감싼 모양."""
    original = pg_errors.lookup(sqlstate)(SECRET)
    return OperationalError("SELECT 1", None, original)


@pytest.mark.parametrize(
    "sqlstate",
    [
        pytest.param("08000", id="연결 예외"),
        pytest.param("08006", id="연결 실패"),
        pytest.param("08001", id="연결을 열지 못함"),
        pytest.param("40001", id="직렬화 실패"),
        pytest.param("40P01", id="교착"),
        pytest.param("57P01", id="관리자 종료"),
        pytest.param("57P02", id="충돌 종료"),
        pytest.param("57P03", id="지금은 연결을 받지 않음"),
    ],
)
async def test_일시_오류의_SQLSTATE는_database_unavailable로_바뀌고_메시지를_옮기지_않는다(
    engine: AsyncEngine, sqlstate: str
) -> None:
    with pytest.raises(TransientFailure) as raised:
        async with PostgresUnitOfWork(engine).begin():
            raise _wrapped(sqlstate)

    assert raised.value.code is ErrorCode.DATABASE_UNAVAILABLE
    assert SECRET not in str(raised.value)


@pytest.mark.parametrize(
    ("sqlstate", "kind"),
    [
        pytest.param("23505", IntegrityError, id="유일 제약 위반"),
        pytest.param("22P05", DataError, id="번역할 수 없는 문자"),
        pytest.param("42P01", ProgrammingError, id="없는 표"),
    ],
)
async def test_나머지_데이터베이스_오류는_일시_실패로_바꾸지_않는다(
    engine: AsyncEngine, sqlstate: str, kind: type[DBAPIError]
) -> None:
    original = pg_errors.lookup(sqlstate)(SECRET)

    with pytest.raises(kind):
        async with PostgresUnitOfWork(engine).begin():
            raise kind("SELECT 1", None, original)


async def test_SQLSTATE가_없는_연결_오류는_일시_실패다(engine: AsyncEngine) -> None:
    """서버에 닿지 못하거나 연결이 닫힌 오류는 psycopg가 SQLSTATE 없이 올린다."""
    with pytest.raises(TransientFailure) as raised:
        async with PostgresUnitOfWork(engine).begin():
            raise OperationalError("SELECT 1", None, psycopg.OperationalError(SECRET))

    assert raised.value.code is ErrorCode.DATABASE_UNAVAILABLE


async def test_SQLSTATE가_없는_DataError는_일시_실패가_아니다(engine: AsyncEngine) -> None:
    """글 칸의 NUL은 psycopg가 보내기 전에 SQLSTATE 없이 `DataError`로 거부한다."""
    with pytest.raises(DataError):
        async with PostgresUnitOfWork(engine).begin() as transaction:
            await transaction.catalog.get_group("가\x00나")


async def test_쿼리_도중_관리자가_연결을_끊으면_일시_실패다(engine: AsyncEngine) -> None:
    with pytest.raises(TransientFailure) as raised:
        async with PostgresUnitOfWork(engine).begin() as transaction:
            await transaction.catalog.get_group("default")
            async with engine.connect() as admin:
                await admin.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                        " WHERE datname = current_database() AND pid <> pg_backend_pid()"
                    )
                )
            await transaction.catalog.get_group("default")

    assert raised.value.code is ErrorCode.DATABASE_UNAVAILABLE
    assert "terminating" not in str(raised.value)


async def test_서버에_닿지_못하면_일시_실패이고_연결_정보를_옮기지_않는다() -> None:
    unreachable = create_engine(f"postgresql://user:{SECRET}@127.0.0.1:1/nothing?connect_timeout=2")

    try:
        with pytest.raises(TransientFailure) as raised:
            async with PostgresUnitOfWork(unreachable).begin():
                pass
    finally:
        await unreachable.dispose()

    assert raised.value.code is ErrorCode.DATABASE_UNAVAILABLE
    assert SECRET not in str(raised.value)
