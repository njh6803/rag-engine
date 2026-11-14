"""평가 데이터베이스를 읽는 조립(티켓 search-eval 03). `index`의 시작 판정과 `validate --indexed`.

`check_database`는 스키마를 올리기 전에 부른다. 스키마의 판 표(`alembic_version`)와 표 목록만 읽어
세 갈래로 가른다. 표가 하나도 없는 빈 데이터베이스는 지나가고, 표가 있는데 판 표가 없거나 판이 이
체크아웃이 올릴 판(`head_revision`)과 다르면 거부한다(평가 데이터베이스는 새로 만들면 된다). 판이
같으면 문서의 소속과 현재 판의 요소를 본다(`check_eval_database`). 읽기만 하고 아무것도 쓰지 않는다.

`check_indexed`는 `validate --indexed`의 몫이다. 판이 같지 않은 데이터베이스에서는 묶음의 모든
문서가 색인되어 있지 않은 것이다. 오류 문장은 연결 문자열이 아니라 오류의 종류만 싣는다(원칙 V).
"""

from enum import Enum, auto
from typing import Final

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from rag_engine.adapters.eval_environment import (
    EvalEnvironment,
    eval_embedder_for,
    eval_embedder_pool,
    eval_settings,
)
from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.migrate import head_revision
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.app.check_eval_database import (
    DATABASE_SUBJECT,
    check_default_records_input,
    check_eval_database,
)
from rag_engine.app.check_indexed_documents import check_indexed_documents
from rag_engine.domain.errors import RagEngineError
from rag_engine.domain.eval_set import EvalProblem, EvalSet

_VERSION_TABLE: Final = "alembic_version"


class SchemaState(Enum):
    EMPTY = auto()  # 표가 하나도 없다. 스키마를 올릴 수 있다.
    CURRENT = auto()  # 판 표가 있고 판이 이 체크아웃이 올릴 판과 같다.
    OTHER = auto()  # 그 밖이다. 표가 있는데 판 표가 없는 것도 든다.


async def read_schema_state(engine: AsyncEngine) -> SchemaState:
    """표 목록은 검색 경로(`search_path`) 전체에서 읽는다. 이어지는 `alembic_version`과 제품 표의
    비한정 이름이 검색 경로를 따라 풀리므로, 첫 스키마(`current_schema()`)만 보면 첫 스키마가 비어
    있을 때 뒤 스키마의 표를 보지 못한 채 빈 데이터베이스로 읽는다."""
    async with engine.connect() as connection:
        listed = await connection.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = ANY (current_schemas(false))"
            )
        )
        tables = {str(name) for name in listed.scalars()}
        if not tables:
            return SchemaState.EMPTY
        if _VERSION_TABLE not in tables:
            return SchemaState.OTHER
        recorded = await connection.execute(sa.text(f"SELECT version_num FROM {_VERSION_TABLE}"))
        revisions = [str(revision) for revision in recorded.scalars()]
    return SchemaState.CURRENT if revisions == [head_revision()] else SchemaState.OTHER


async def check_database(database_url: str, eval_set: EvalSet) -> tuple[EvalProblem, ...]:
    """`index`가 스키마를 올리기 전에 데이터베이스가 이 묶음의 것인지 본다. 문제가 없으면 빈
    튜플이다."""
    config_problems = check_default_records_input(eval_set, compute_index_elements)
    if config_problems:
        return config_problems
    engine = create_engine(database_url)
    try:
        state = await read_schema_state(engine)
        if state is SchemaState.EMPTY:
            return ()
        if state is SchemaState.OTHER:
            return (
                EvalProblem(
                    DATABASE_SUBJECT,
                    "스키마의 판이 이 체크아웃이 올리는 판과 다르거나 스키마의 판 표가 없다."
                    " 평가 데이터베이스는 새로 만든다",
                ),
            )
        return await check_eval_database(
            PostgresUnitOfWork(engine), eval_set, compute_index_elements
        )
    except (OSError, SQLAlchemyError) as error:
        return (
            EvalProblem(DATABASE_SUBJECT, f"데이터베이스를 읽지 못했다({type(error).__name__})"),
        )
    finally:
        await engine.dispose()


async def check_indexed(
    environment: EvalEnvironment, eval_set: EvalSet
) -> tuple[tuple[EvalProblem, ...], tuple[EvalProblem, ...]]:
    """`validate --indexed`의 판정. (오류, 경고)를 낸다."""
    settings = eval_settings(environment, eval_set.config)
    engine = create_engine(environment.database_url)
    pool = eval_embedder_pool(settings)
    # 평가는 판에 적힌 끝점이 아니라 환경의 끝점으로 센다.
    meter_for = eval_embedder_for(pool, environment)

    try:
        if await read_schema_state(engine) is not SchemaState.CURRENT:
            return (
                tuple(
                    EvalProblem(
                        document.key, "색인되어 있지 않다(스키마가 올라 있지 않은 데이터베이스다)"
                    )
                    for document in eval_set.documents
                ),
                (),
            )
        return await check_indexed_documents(PostgresUnitOfWork(engine), eval_set, meter_for)
    except (OSError, SQLAlchemyError, RagEngineError) as error:
        message = f"데이터베이스나 임베딩 끝점을 읽지 못했다({type(error).__name__})"
        return (EvalProblem(DATABASE_SUBJECT, message),), ()
    finally:
        await pool.aclose()
        await engine.dispose()
