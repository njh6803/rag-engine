"""로그 포매터(ADR 0015, 명세 "로그, 요청 ID, 지연 기록"). JSON Lines를 stdout으로 낸다."""

import json
import logging

import pytest

from rag_engine.adapters.log_format import configure_logging, log_event, request_id_var
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id

SIX_FIELDS = ["time", "level", "logger", "event", "request_id", "duration_ms"]


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_한_줄이_JSON_객체이고_여섯_필드가_앞에_온다(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("json")
    request_id = new_id()

    log_event(
        logging.getLogger("rag_engine.시험"),
        "http_request",
        request_id=request_id,
        duration_ms=12.3456,
        method="GET",
        status=200,
    )

    (line,) = _lines(capsys)
    assert list(line)[:6] == SIX_FIELDS
    assert line["level"] == "info"
    assert line["logger"] == "rag_engine.시험"
    assert line["event"] == "http_request"
    assert line["request_id"] == str(request_id)
    assert line["duration_ms"] == 12.346
    assert (line["method"], line["status"]) == ("GET", 200)
    assert isinstance(line["time"], str)
    assert line["time"].endswith("Z")


def test_요청_ID와_지연이_없으면_null이다(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("json")

    logging.getLogger("rag_engine.시험").warning("시작")

    (line,) = _lines(capsys)
    assert (line["level"], line["event"]) == ("warning", "시작")
    assert (line["request_id"], line["duration_ms"]) == (None, None)


def test_요청_ID를_주지_않으면_지금_요청의_ID를_싣는다(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("json")
    request_id = new_id()
    token = request_id_var.set(request_id)
    try:
        logging.getLogger("uvicorn.error").info("다른 로거의 줄")
    finally:
        request_id_var.reset(token)

    (line,) = _lines(capsys)
    assert line["request_id"] == str(request_id)


def test_서드파티_예외의_메시지는_싣지_않고_타입과_프레임만_싣는다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("json")
    logger = logging.getLogger("rag_engine.시험")

    try:
        raise ValueError("질의 글: 비밀 조항")
    except ValueError:
        logger.exception("실패")

    output = capsys.readouterr().out
    assert "비밀 조항" not in output
    exception = json.loads(output)["exception"]
    assert exception["type"] == "builtins.ValueError"
    assert "message" not in exception
    assert exception["frames"][-1]["function"] == (
        "test_서드파티_예외의_메시지는_싣지_않고_타입과_프레임만_싣는다"
    )
    assert set(exception["frames"][-1]) == {"file", "line", "function"}


def test_이_저장소의_예외는_메시지도_싣는다(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("json")

    try:
        raise RequestError(ErrorCode.DOCUMENT_NOT_FOUND, "그 문서가 없다")
    except RequestError:
        logging.getLogger("rag_engine.시험").exception("실패")

    exception = json.loads(capsys.readouterr().out)["exception"]
    assert exception["type"] == "rag_engine.domain.errors.RequestError"
    assert exception["message"] == "그 문서가 없다"
    assert exception["frames"]


def test_text_형식은_사람이_읽는_한_줄이다(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("text")
    request_id = new_id()

    log_event(
        logging.getLogger("rag_engine.시험"),
        "http_request",
        request_id=request_id,
        duration_ms=3.0,
        status=404,
    )

    (line,) = capsys.readouterr().out.splitlines()
    assert not line.startswith("{")
    for part in ("INFO", "rag_engine.시험", "http_request", str(request_id), "status=404"):
        assert part in line


def test_uvicorn과_MCP_SDK의_로거가_우리_포매터를_지난다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # uvicorn은 기동할 때 자기 핸들러를 달고 상위 전파를 끈다. 우리가 그 로거들을 되찾는다.
    uvicorn_logger = logging.getLogger("uvicorn.error")
    uvicorn_logger.addHandler(logging.NullHandler())
    uvicorn_logger.propagate = False
    configure_logging("json")

    uvicorn_logger.info("서버 시작")
    logging.getLogger("uvicorn.access").info("접근")
    logging.getLogger("mcp.server.streamable_http").warning("SDK 경고")

    lines = _lines(capsys)
    assert [(line["logger"], line["event"]) for line in lines] == [
        ("uvicorn.error", "서버 시작"),
        ("uvicorn.access", "접근"),
        ("mcp.server.streamable_http", "SDK 경고"),
    ]
    assert all(list(line)[:6] == SIX_FIELDS for line in lines)


def test_다시_설정해도_줄이_겹쳐_나오지_않는다(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("json")
    configure_logging("json")

    logging.getLogger("rag_engine.시험").info("한 번")

    assert len(_lines(capsys)) == 1
