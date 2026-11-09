from fastapi.testclient import TestClient

from rag_engine.server import create_app


def test_빈_서버의_health는_ok를_돌려준다() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
