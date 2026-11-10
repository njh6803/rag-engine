"""식별자는 UUIDv7이고 표준 라이브러리 `uuid.UUID`다(ADR 0015, 명세 "데이터 모델과 스키마")."""

from uuid import UUID

from rag_engine.domain.identifiers import new_id


def test_새_식별자는_UUIDv7이다() -> None:
    identifier = new_id()

    assert isinstance(identifier, UUID)
    assert identifier.version == 7


def test_연속해서_만든_식별자는_시간순으로_늘어난다() -> None:
    identifiers = [new_id() for _ in range(1000)]

    assert identifiers == sorted(identifiers)
    assert len(set(identifiers)) == len(identifiers)
