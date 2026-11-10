from collections.abc import Callable

from fastapi.testclient import TestClient

from rag_engine.adapters.settings import Settings
from rag_engine.server import create_app


def test_빈_서버의_health는_토큰_없이_ok를_돌려준다(make_settings: Callable[..., Settings]) -> None:
    # /health 는 데이터베이스를 보지 않는다. 닿지 않는 주소를 줘도 답한다.
    settings = make_settings("postgresql://rag:rag@127.0.0.1:1/rag")

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
