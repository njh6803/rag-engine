"""서버 기동 때의 Kiwi 예열(티켓 07). 예열은 기동을 막지 않게 스레드에서 돌고, 실패해도 서버가
뜨고 실패를 로그에 남긴다."""

from collections.abc import Callable

import pytest
from tests.harness import LogCapture, RunningServer


def test_예열이_실패해도_서버는_뜨고_실패를_로그에_남긴다(
    monkeypatch: pytest.MonkeyPatch,
    log_capture: LogCapture,
    run_server: Callable[..., RunningServer],
) -> None:
    def failing(_text: str) -> list[str]:
        raise RuntimeError("모델 적재 실패")

    monkeypatch.setattr("rag_engine.server.app.tokenize_keywords", failing)

    run_server()

    events = log_capture.events("kiwi_warmup_failed", count=1)
    assert [event["level"] for event in events] == ["error"]
