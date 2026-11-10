"""수집 API의 요청·응답 모델(명세 "수집 API")."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from rag_engine.server.ingest_models import IngestAction, IngestFields, IngestResponse

_ID = UUID("0198f4a0-0000-7000-8000-000000000003")


def test_action은_다섯이다() -> None:
    assert {action.value for action in IngestAction} == {
        "created",
        "updated",
        "unchanged",
        "restored",
        "requeued",
    }


def test_job_id는_null일_수_있다() -> None:
    response = IngestResponse(action=IngestAction.UNCHANGED, document_id=_ID, job_id=None)

    assert response.model_dump(mode="json") == {
        "action": "unchanged",
        "document_id": str(_ID),
        "job_id": None,
    }


def test_job_id가_있는_응답은_문서와_작업_식별자를_함께_낸다() -> None:
    response = IngestResponse(action=IngestAction.CREATED, document_id=_ID, job_id=_ID)

    assert response.job_id == _ID


def test_폼_칸은_모두_선택이다() -> None:
    fields = IngestFields()

    assert (fields.key, fields.group, fields.metadata, fields.updated_at) == (None, None, {}, None)


def test_metadata는_JSON_객체_문자열을_받는다() -> None:
    fields = IngestFields.model_validate({"metadata": '{"title": "휴가 규정", "쪽": 3}'})

    assert fields.metadata == {"title": "휴가 규정", "쪽": 3}


@pytest.mark.parametrize("raw", ["[1, 2]", '"문자열"', "42", "{", ""])
def test_metadata가_JSON_객체가_아니면_거부한다(raw: str) -> None:
    with pytest.raises(ValidationError, match="JSON 객체 문자열이어야 한다"):
        IngestFields.model_validate({"metadata": raw})


@pytest.mark.parametrize(
    "raw", ['{"a": NaN}', '{"a": [1, Infinity]}', '{"a": {"b": -Infinity}}', '{"a": 1e999}']
)
def test_metadata에_NaN이나_무한대가_있으면_거부한다(raw: str) -> None:
    with pytest.raises(ValidationError, match="NaN이나 무한대를 담을 수 없다"):
        IngestFields.model_validate({"metadata": raw})


def test_metadata가_객체로_들어와도_NaN을_거부한다() -> None:
    with pytest.raises(ValidationError, match="NaN이나 무한대를 담을 수 없다"):
        IngestFields.model_validate({"metadata": {"a": float("nan")}})


@pytest.mark.parametrize(
    "raw",
    [r'{"a": "x\u0000y"}', r'{"k\u0000": 1}', r'{"a": [{"b": "\u0000"}]}'],
)
def test_metadata의_값과_키에_NUL이_있으면_거부한다(raw: str) -> None:
    with pytest.raises(ValidationError, match="NUL 문자"):
        IngestFields.model_validate({"metadata": raw})


@pytest.mark.parametrize("name", ["key", "group"])
def test_key와_group에_NUL이_있으면_거부한다(name: str) -> None:
    with pytest.raises(ValidationError, match="NUL 문자"):
        IngestFields.model_validate({name: "a\x00b"})


def test_updated_at은_오프셋이_있는_ISO_8601을_받는다() -> None:
    fields = IngestFields.model_validate({"updated_at": "2026-11-10T09:30:00+09:00"})

    assert fields.updated_at == datetime(2026, 11, 10, 0, 30, tzinfo=UTC)


def test_updated_at에_오프셋이_없으면_거부한다() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        IngestFields.model_validate({"updated_at": "2026-11-10T09:30:00"})
