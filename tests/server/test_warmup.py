"""서버 기동 때의 Kiwi 예열(티켓 07). 예열은 기동을 막지 않게 스레드에서 돌고, 실패해도 서버가
뜨고 실패를 로그에 남긴다. 시험의 서버 fixture는 그 적재가 기동 직후 서버를 멈추게 하지 않도록
기동 전에 적재한다(harness 티켓 fixture-preloads-kiwi). 그 회귀 시험도 여기 둔다."""

import threading
from collections.abc import Callable

import pytest
from tests.harness import LogCapture, RunningServer


def test_서버_fixture는_기동_전에_시험_스레드에서_Kiwi를_적재한다(
    monkeypatch: pytest.MonkeyPatch, run_server: Callable[..., RunningServer]
) -> None:
    """예열 스레드의 모델 적재가 GIL을 쥐어 기동 직후 서버 루프와 시험 스레드가 함께 수 초 멈췄고,
    첫 요청의 시간 단언(만료 토큰의 2초 여유)이 그 멈춤에 깨졌다. fixture가 서버를 띄우기 전에
    시험 스레드에서 적재를 마쳐 그 멈춤을 없앤다(`.scratch/harness/probes/kiwi_warmup_stall/`)."""
    threads: list[str] = []

    def recording(_text: str) -> list[str]:
        threads.append(threading.current_thread().name)
        return []

    monkeypatch.setattr("rag_engine.adapters.kiwi.tokenize_keywords", recording)
    monkeypatch.setattr("rag_engine.server.app.tokenize_keywords", recording)

    run_server()

    # 첫 기록이 시험 스레드여야 앱의 예열 스레드보다 먼저, 곧 기동 전에 적재한 것이다.
    assert threads[0] == threading.current_thread().name
    assert threads.count(threading.current_thread().name) == 1


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
