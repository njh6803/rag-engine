"""시간 간격을 두고 이어 보내는 응답을 내는 가짜 뒷단(프로브). `compose.sse.yml`이 서버 자리에
띄운다.

`POST /mcp`에 `text/event-stream`으로 사건 다섯을 1초 간격으로 보낸다. 질의 문자열에 `xab=1`이
있으면 실제 서버의 MCP 응답처럼 `X-Accel-Buffering: no` 머리를 싣고, 없으면 싣지 않는다. 프록시가
응답을 모으는지를 `run.py`가 사건이 닿은 시각으로 가른다. `/health`는 compose 의 상태 확인이 본다.
표준 라이브러리만 쓴다(서버 이미지의 파이썬으로 돈다).
"""

import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

EVENTS: Final = 5
GAP_SECONDS: Final = 1.0


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        body = b'{"status":"ok"}'
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        if "xab=1" in self.path:
            self.send_header("X-Accel-Buffering", "no")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for index in range(EVENTS):
            data = f"event: message\ndata: {index}\n\n".encode()
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
            self.wfile.flush()
            if index < EVENTS - 1:
                time.sleep(GAP_SECONDS)
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
