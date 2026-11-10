"""`TeiStub`을 실제 HTTP 서버로 띄운다. 서버와 작업자가 각자 클라이언트로 접속하는 왕복 시험이 쓴다.

uvicorn을 스레드에서 돌리고 빈 포트를 고른다(`tests/conftest.py`의 `run_server`와 같은 방식).
"""

import socket
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager

import uvicorn
from tests.support.tei_stub import TeiStub

STARTUP_TIMEOUT_SECONDS = 10


@contextmanager
def serve_stub(stub: TeiStub) -> Generator[str]:
    """스텁의 기본 주소(`http://127.0.0.1:포트`)를 낸다. 블록을 나가면 내린다."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(stub.app, log_config=None, access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline:
            raise TimeoutError("TEI 스텁 서버가 뜨지 않았다")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(STARTUP_TIMEOUT_SECONDS)
