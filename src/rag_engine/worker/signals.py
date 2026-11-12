"""종료 신호를 받으면 멈춤 표지를 세운다(명세 "수집 파이프라인과 작업"의 작업자 항목, 티켓 13).

SIGTERM과 SIGINT를 받는다. Python은 Windows에서 다른 프로세스에 SIGTERM을 보낼
때(`Popen.send_signal`, `os.kill`) 신호를 전달하지 않고 `TerminateProcess`로 프로세스를 바로 끝내
처리기가 돌지 않는다. 그래서 SIGBREAK(`CTRL_BREAK_EVENT`가 이 신호로 온다)를 같은 뜻으로 받는다.

asyncio의 `add_signal_handler`는 Windows에서 쓸 수 없다. 그래서 `signal.signal`로 처리기를 달고,
처리기는 `call_soon_threadsafe`로 표지를 세운다. 다만 이벤트 루프가 소켓을 기다리며 멈춰 있을
때(Windows의 Selector 루프는 열린 소켓 연결이 하나도 없으면 신호로 깨지 않는다) 처리기가 늦게
돌므로, 신호가 오면 소켓 쌍에 한 바이트를 쓰는 깨움 fd를 달아 루프를 깨운다. 소켓 쌍을 루프에
`add_reader`로 달아야 하므로 Selector 루프(ADR 0011)에서만 부를 수 있다. Windows의 기본
ProactorEventLoop에서는 `NotImplementedError`가 난다.

처리기가 하는 일은 표지를 세우는 것뿐이라 신호가 몇 번 와도 같다. 진행 중인 작업이 길면 그만큼
뒤에 나가고, 바로 끊으려면 프로세스를 강제로 끝내야 한다. 그렇게 끊긴 작업은 임대 기간이 끝날
때까지 `running`으로 남다가 다른 작업자가 인수한다.
"""

import asyncio
import signal
import socket
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from types import FrameType
from typing import Final

type _Handler = Callable[[int, FrameType | None], object] | int | signal.Handlers | None

_DRAIN_BYTES: Final = 1024

STOP_SIGNALS: Final[tuple[signal.Signals, ...]] = (
    (signal.SIGINT, signal.SIGTERM, signal.SIGBREAK)
    if sys.platform == "win32"
    else (signal.SIGINT, signal.SIGTERM)
)


@contextmanager
def stop_on_signals(stop: asyncio.Event) -> Generator[None]:
    """블록 안에서 종료 신호를 받으면 `stop`을 세운다. 블록을 나가면 원래 처리기를 되돌린다. 메인
    스레드의 실행 중인 이벤트 루프 안에서만 부를 수 있다."""
    loop = asyncio.get_running_loop()
    reader, writer = socket.socketpair()
    reader.settimeout(0)
    writer.settimeout(0)

    def request_stop(signum: int, frame: FrameType | None) -> None:
        loop.call_soon_threadsafe(stop.set)

    def drain() -> None:
        try:
            reader.recv(_DRAIN_BYTES)
        except OSError:
            pass

    previous_handlers: list[tuple[signal.Signals, _Handler]] = []
    previous_fd = -1
    try:
        loop.add_reader(reader.fileno(), drain)
        previous_fd = signal.set_wakeup_fd(writer.fileno(), warn_on_full_buffer=False)
        for each in STOP_SIGNALS:
            previous_handlers.append((each, signal.signal(each, request_stop)))
        yield
    finally:
        for each, handler in previous_handlers:
            signal.signal(each, signal.SIG_DFL if handler is None else handler)
        signal.set_wakeup_fd(previous_fd)
        loop.remove_reader(reader.fileno())
        reader.close()
        writer.close()
