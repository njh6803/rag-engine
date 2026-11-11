"""PostgreSQL 드라이버 예외를 일시 실패로 가르는 자리(명세 "수집 파이프라인과 작업"의 오류 번역).

일시 실패는 연결 실패(SQLSTATE 클래스 `08`과, 서버에 닿지 못하거나 연결이 닫혀 SQLSTATE 없이 올라온
연결 오류), 직렬화 실패 `40001`, 교착 `40P01`, 관리자 종료 `57P01`~`57P03`이다. 오류 코드는
`database_unavailable`이다. `DataError`와 `IntegrityError` 같은 나머지는 같은 입력으로 다시 해도
같은 결과라서 일시 실패가 아니다. 드라이버 예외의 메시지에는 SQL 조각과 연결 정보가 들 수 있어(원칙
V) 번역한 예외는 이 저장소가 쓴 글만 담는다.
"""

from typing import Final

import psycopg
from sqlalchemy.exc import DBAPIError

from rag_engine.domain.errors import ErrorCode, TransientFailure

_CONNECTION_CLASS: Final = "08"
_TRANSIENT_SQLSTATES: Final = frozenset({"40001", "40P01", "57P01", "57P02", "57P03"})


def is_transient(error: DBAPIError) -> bool:
    original = error.orig
    if not isinstance(original, psycopg.Error):
        return error.connection_invalidated
    sqlstate = original.sqlstate
    if sqlstate is None:
        # 서버에 닿지 못했거나 연결이 닫힌 오류다. 보내기 전에 거부한 `DataError`도 SQLSTATE가
        # 없어서 연결 오류의 종류로만 가른다.
        return isinstance(original, psycopg.OperationalError | psycopg.InterfaceError)
    return sqlstate.startswith(_CONNECTION_CLASS) or sqlstate in _TRANSIENT_SQLSTATES


def translate(error: DBAPIError) -> TransientFailure | None:
    """일시 오류면 메시지를 옮기지 않은 일시 실패를 낸다. 아니면 `None`이다."""
    if not is_transient(error):
        return None
    return TransientFailure(ErrorCode.DATABASE_UNAVAILABLE, "데이터베이스를 잠시 쓸 수 없다")
