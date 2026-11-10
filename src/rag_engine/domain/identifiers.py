"""식별자 생성. UUIDv7을 파이썬에서 만든다(ADR 0015).

PostgreSQL 18의 `uuidv7()`을 쓰지 않아 식별자 생성이 데이터베이스 판과 무관하다. uuid6 의 값은 표준
라이브러리 `uuid.UUID` 의 하위 타입이라 SQLAlchemy `Uuid` 열과 pydantic `UUID` 칸에 변환 없이
들어간다 (명세 "데이터 모델과 스키마", 프로브 `uuid/probe_sqlalchemy.py`).
"""

from uuid import UUID

from uuid6 import uuid7


def new_id() -> UUID:
    return uuid7()
