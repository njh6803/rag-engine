"""종료 신호를 받으면 멈춤 표지를 세우는 자리(`stop_on_signals`, 티켓 13).

SIGTERM과 SIGINT를, Windows는 SIGBREAK(`CTRL_BREAK_EVENT`가 이 신호로 온다)를 같은 뜻으로 받는다. 이
시험은 프로세스에 신호를 직접 일으켜 표지가 서는지와 블록을 나간 뒤 원래 처리기가 돌아오는지 본다.
실제 하위 프로세스에 신호를 보내 끝나는 것은 `test_worker_command.py`가 본다.
"""

import asyncio
import signal
import threading
import time

import pytest

from rag_engine.worker.signals import STOP_SIGNALS, stop_on_signals

SIGNAL_DELAY_SECONDS = 0.3
WAKE_LIMIT_SECONDS = 10


@pytest.mark.parametrize("stop_signal", STOP_SIGNALS)
async def test_종료_신호를_받으면_멈춤_표지가_선다(stop_signal: signal.Signals) -> None:
    stop = asyncio.Event()

    with stop_on_signals(stop):
        signal.raise_signal(stop_signal)
        async with asyncio.timeout(5):
            await stop.wait()

    assert stop.is_set()


@pytest.mark.parametrize("stop_signal", STOP_SIGNALS)
async def test_이벤트_루프가_소켓을_기다리는_동안_온_신호도_루프를_깨운다(
    stop_signal: signal.Signals,
) -> None:
    stop = asyncio.Event()
    # 신호를 다른 스레드에서 일으키면 처리기는 메인 스레드가 깨어난 뒤에야 돈다. 깨움 fd가 없으면
    # 루프는 아무것도 오지 않는 채 기한까지 잠들어 있다.
    sender = threading.Timer(SIGNAL_DELAY_SECONDS, signal.raise_signal, [stop_signal])
    started = time.monotonic()

    with stop_on_signals(stop):
        sender.start()
        try:
            async with asyncio.timeout(WAKE_LIMIT_SECONDS):
                await stop.wait()
        finally:
            sender.cancel()

    assert time.monotonic() - started < WAKE_LIMIT_SECONDS / 2


async def test_블록을_나가면_원래_신호_처리기로_돌아온다() -> None:
    before = {each: signal.getsignal(each) for each in STOP_SIGNALS}

    with stop_on_signals(asyncio.Event()):
        during = {each: signal.getsignal(each) for each in STOP_SIGNALS}

    assert {each: signal.getsignal(each) for each in STOP_SIGNALS} == before
    assert all(during[each] != before[each] for each in STOP_SIGNALS)


async def test_신호가_없으면_멈춤_표지는_서지_않는다() -> None:
    stop = asyncio.Event()

    with stop_on_signals(stop):
        await asyncio.sleep(0.05)

    assert not stop.is_set()
