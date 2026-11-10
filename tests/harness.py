"""시험이 함께 쓰는 값 객체와 보조 함수. `conftest.py`의 픽스처가 만들고 시험이 받는다. 시험이
`conftest`를 직접 import하면 pytest가 읽은 것과 다른 모듈로 한 번 더 읽히므로 이 모듈에 둔다."""

import json
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import pytest

from rag_engine.adapters.settings import Settings


def replace_database(url: str, name: str) -> str:
    return urlsplit(url)._replace(path=f"/{name}").geturl()


@dataclass(frozen=True, slots=True)
class RunningServer:
    """실제 uvicorn 서버. `admin_token`은 서버를 띄우기 전에 `bootstrap-token`과 같은 길로 발급한
    토큰 원문이다."""

    base_url: str
    host: str
    port: int
    settings: Settings
    admin_token: str

    @property
    def mcp_url(self) -> str:
        return f"{self.base_url}/mcp"


class LogCapture:
    """서버 스레드가 stdout에 찍은 JSON Lines를 읽는다. 로그는 응답을 보낸 뒤에 찍히므로 기대한
    개수의 이벤트가 올 때까지 기다린다."""

    def __init__(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._capsys = capsys
        self._text = ""

    def text(self) -> str:
        self._text += self._capsys.readouterr().out
        return self._text

    def events(self, event: str, *, count: int, timeout: float = 10.0) -> list[dict[str, object]]:
        deadline = time.monotonic() + timeout
        while True:
            found = [
                line
                for line in (json.loads(raw) for raw in self.text().splitlines() if raw.strip())
                if line["event"] == event
            ]
            if len(found) >= count or time.monotonic() > deadline:
                return found
            time.sleep(0.02)

    def lines_containing(self, fragment: str, *, count: int, timeout: float = 10.0) -> list[str]:
        """JSON이 아닌 줄(`RAG_LOG_FORMAT=text`)에서 조각이 든 줄을 모은다."""
        deadline = time.monotonic() + timeout
        while True:
            found = [raw for raw in self.text().splitlines() if fragment in raw]
            if len(found) >= count or time.monotonic() > deadline:
                return found
            time.sleep(0.02)
