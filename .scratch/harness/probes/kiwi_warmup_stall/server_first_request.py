"""fixture 가 돌려준 서버의 첫 요청이 Kiwi 예열에 얼마나 멈추는지 잰다. 세 갈래다.

- `원인_재현`: fixture 의 사전 적재를 no-op 으로 바꾸고 모델 캐시를 비워, 앱 lifespan 의 예열
  스레드가 기동 뒤에 모델을 처음 적재하는 옛 모양을 만든다.
- `예열_없음`: 앱의 예열을 no-op 으로 바꾼 대조군.
- `지금_fixture`: 모델 캐시를 비운 뒤 손대지 않은 지금 fixture(기동 전에 시험 스레드에서 적재한다)로
  띄운다. 고침의 확인이다.

세 갈래를 한 프로세스로 돌리므로 앞 갈래가 채운 모델 캐시가 뒤 갈래에 남지 않게 갈래마다 캐시를
비운다. 비우지 않으면 뒤의 두 갈래는 더운 캐시로 돌아 고침 없이도 빠르다(넷째 커밋의 셀프 리뷰
명세 축이 잡았다).

실행: 테스트 PostgreSQL 과 `RAG_TEST_DATABASE_URL` 이 필요하고, `tests/conftest.py` 의 fixture 를
플러그인으로 싣는다. 저장소 루트에서 이 파일을 `uv run pytest` 에 주고 뒤에
`-p tests.conftest -p no:xdist -q -s` 를 붙인다.

결과는 `server_first_request_out.txt`. 2026-11-11 이 PC 에서 다른 세션의 검사가 돌던 때(CPU 50%)의
값이라 한가한 때는 짧다.
"""

import socket
import time

import pytest
from tests.harness import RunningServer

import rag_engine.adapters.kiwi as kiwi_module
import rag_engine.server.app as app_module


def _t(label: str, start: float) -> None:
    print(f"[probe] {label}: {time.perf_counter() - start:.3f}s")


async def _noop_warmup() -> None:
    return None


def _noop_tokenize(_text: str) -> list[str]:
    return []


@pytest.fixture
def 원인_재현(monkeypatch: pytest.MonkeyPatch) -> None:
    kiwi_module._kiwi.cache_clear()
    monkeypatch.setattr(kiwi_module, "tokenize_keywords", _noop_tokenize)


@pytest.fixture
def 예열_없음(monkeypatch: pytest.MonkeyPatch) -> None:
    kiwi_module._kiwi.cache_clear()
    monkeypatch.setattr(app_module, "_warm_up_kiwi", _noop_warmup)


@pytest.fixture
def 지금_fixture() -> None:
    kiwi_module._kiwi.cache_clear()


def _first_request(server: RunningServer, label: str) -> None:
    t = time.perf_counter()
    sock = socket.create_connection((server.host, server.port), timeout=30)
    _t(f"{label} raw connect", t)
    t = time.perf_counter()
    sock.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
    first = sock.recv(64)
    _t(f"{label} raw GET /health first byte ({first[:12]!r})", t)
    sock.close()
    t = time.perf_counter()
    import httpx

    httpx.Client().close()
    _t(f"{label} httpx.Client() construction", t)


def test_원인_재현(원인_재현: None, server: RunningServer) -> None:
    _first_request(server, "원인 재현(기동 뒤 예열 스레드가 적재)")


def test_예열_없음(예열_없음: None, server: RunningServer) -> None:
    _first_request(server, "예열 없음(대조)")


def test_지금_fixture(지금_fixture: None, server: RunningServer) -> None:
    _first_request(server, "지금 fixture(기동 전 적재)")
