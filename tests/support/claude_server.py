"""`ClaudeStub`을 실제 HTTP 서버로 띄운다. `tei_server.serve_stub`과 같은 방식이다."""

import socket
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager

import uvicorn
from tests.support.claude_stub import ClaudeStub

STARTUP_TIMEOUT_SECONDS = 10


@contextmanager
def serve_claude_stub(stub: ClaudeStub) -> Generator[str]:
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
            raise TimeoutError("Claude 스텁 서버가 뜨지 않았다")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(STARTUP_TIMEOUT_SECONDS)
