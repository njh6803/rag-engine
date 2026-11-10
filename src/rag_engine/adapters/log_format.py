"""로그 포매터(ADR 0015, 명세 "로그, 요청 ID, 지연 기록").

표준 라이브러리 logging에 우리 포매터를 붙여 JSON Lines를 stdout으로 낸다. 줄마다 `time`(UTC),
`level`, `logger`, `event`, `request_id`, `duration_ms` 여섯 필드가 앞에 오고, 이벤트가 더 싣는 값이
그 뒤에 온다. 예외는 `exception` 필드에 타입과 프레임(파일, 줄, 함수)을 싣고, 메시지는 이 저장소가
정의한 예외일 때만 싣는다. 서드파티 예외의 메시지에는 입력 값(질의, 문서 내용)이 실릴 수 있어서다
(원칙 V).

이 저장소가 남기는 `event`에는 상수 문자열만 둔다(`log_event`). 질의 글, 문서의 키와 제목, 토큰
원문은 어떤 필드에도 싣지 않는다. 외래 로거(uvicorn, MCP SDK)의 메시지는 그대로 `event`가 되므로 그
로거들이 Host 헤더나 세션 ID를 싣는 것은 막지 못한다.
"""

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from types import TracebackType
from typing import Final, Literal, TypeGuard
from uuid import UUID

type FieldValue = str | int | float | bool | None

# 지금 처리 중인 요청의 ID. 요청 ID를 직접 주지 않은 줄(uvicorn, MCP SDK의 로거)이 이 값을 싣는다.
request_id_var: ContextVar[UUID | None] = ContextVar("request_id", default=None)

_BASE_FIELDS: Final = ("time", "level", "logger", "event", "request_id", "duration_ms")
_FIELDS_ATTRIBUTE: Final = "event_fields"
# 우리가 되찾을 외부 로거. uvicorn은 기동할 때 자기 핸들러를 달고 상위 전파를 끈다.
_FOREIGN_LOGGERS: Final = ("uvicorn", "uvicorn.error", "uvicorn.access", "mcp")
_OWN_PACKAGE: Final = "rag_engine"


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    request_id: UUID | None = None,
    duration_ms: float | None = None,
    exception: BaseException | None = None,
    **fields: FieldValue,
) -> None:
    logger.log(
        level,
        event,
        exc_info=exception,
        extra={"request_id": request_id, "duration_ms": duration_ms, _FIELDS_ATTRIBUTE: fields},
    )


def _record_request_id(record: logging.LogRecord) -> UUID | None:
    explicit: object = getattr(record, "request_id", None)
    return explicit if isinstance(explicit, UUID) else request_id_var.get()


def _record_duration_ms(record: logging.LogRecord) -> float | None:
    duration: object = getattr(record, "duration_ms", None)
    return round(duration, 3) if isinstance(duration, int | float) else None


def _is_field_map(value: object) -> TypeGuard[dict[str, FieldValue]]:
    # `log_event`만 이 속성을 쓰고 그 값은 키워드 인자라 키가 문자열이다.
    return isinstance(value, dict)


def _record_fields(record: logging.LogRecord) -> dict[str, FieldValue]:
    fields: object = getattr(record, _FIELDS_ATTRIBUTE, None)
    return fields if _is_field_map(fields) else {}


def _format_time(created: float) -> str:
    moment = datetime.fromtimestamp(created, UTC)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _exception_payload(
    exc_type: type[BaseException], exc: BaseException, trace: TracebackType | None
) -> dict[str, object]:
    payload: dict[str, object] = {"type": f"{exc_type.__module__}.{exc_type.__qualname__}"}
    if exc_type.__module__.split(".")[0] == _OWN_PACKAGE:
        payload["message"] = str(exc)
    payload["frames"] = [
        {"file": frame.filename, "line": frame.lineno, "function": frame.name}
        for frame in traceback.extract_tb(trace)
    ]
    return payload


def _payload(record: logging.LogRecord) -> dict[str, object]:
    request_id = _record_request_id(record)
    payload: dict[str, object] = {
        "time": _format_time(record.created),
        "level": record.levelname.lower(),
        "logger": record.name,
        "event": record.getMessage(),
        "request_id": None if request_id is None else str(request_id),
        "duration_ms": _record_duration_ms(record),
    }
    payload.update(_record_fields(record))
    exc_info = record.exc_info
    if exc_info is not None and exc_info[0] is not None:
        payload["exception"] = _exception_payload(*exc_info)
    return payload


class JsonLinesFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(_payload(record), ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """사람이 읽는 한 줄. 같은 내용을 `시각 수준 로거 이벤트 키=값 …`으로 낸다."""

    def format(self, record: logging.LogRecord) -> str:
        payload = _payload(record)
        head = f"{payload['time']} {record.levelname:<7} {record.name} {payload['event']}"
        details = [
            f"{key}={_text_value(value)}"
            for key, value in payload.items()
            if key not in _BASE_FIELDS[:4] and value is not None
        ]
        return " ".join([head, *details])


def _text_value(value: object) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


class _StdoutHandler(logging.Handler):
    """호출 때의 `sys.stdout`에 쓴다. 시험이 stdout을 바꿔 끼워도 닫힌 스트림에 쓰지 않는다."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
            sys.stdout.flush()
        except Exception:
            # 로깅 실패가 요청을 죽이지 않게 logging의 관례대로 넘긴다.
            self.handleError(record)


def configure_logging(log_format: Literal["json", "text"]) -> None:
    """루트 로거에 우리 핸들러 하나를 단다. 여러 번 불러도 하나만 남는다. MCPServer를 만들기 전에
    부른다. uvicorn과 MCP SDK의 로거는 핸들러를 비우고 상위로 전파해 같은 핸들러를 지나게 한다."""
    handler = _StdoutHandler()
    handler.setFormatter(JsonLinesFormatter() if log_format == "json" else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h for h in root.handlers if not isinstance(h, _StdoutHandler)]
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for name in _FOREIGN_LOGGERS:
        foreign = logging.getLogger(name)
        foreign.handlers.clear()
        foreign.propagate = True
