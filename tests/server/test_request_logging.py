"""요청 ID와 로그(명세 "로그, 요청 ID, 지연 기록", 스토리 37·38, ADR 0004·0015).

`http_request` 이벤트가 요청마다 한 줄 남고, 토큰 원문과 질의·문서 글은 어떤 줄에도 없다. 서버는
스레드에서 돌고 로그는 시험의 stdout으로 나온다.
"""

from collections.abc import Callable

import httpx
from tests.harness import LogCapture, RunningServer, replace_database

PATH = "/api/v1/admin/tokens"


def _auth(server: RunningServer) -> dict[str, str]:
    return {"Authorization": f"Bearer {server.admin_token}"}


def test_요청마다_http_request_한_줄이_응답_헤더의_요청_ID와_함께_남는다(
    server: RunningServer, log_capture: LogCapture
) -> None:
    log_capture.text()

    response = httpx.get(server.base_url + PATH, headers=_auth(server))

    (line,) = log_capture.events("http_request", count=1)
    assert line["request_id"] == response.headers["x-request-id"]
    assert (line["method"], line["path"], line["status"]) == ("GET", PATH, 200)
    assert isinstance(line["duration_ms"], float)
    assert line["duration_ms"] >= 0


def test_경로는_템플릿으로_남고_실제_id와_쿼리_문자열은_남지_않는다(
    server: RunningServer, log_capture: LogCapture
) -> None:
    token_id = "01960000-0000-7000-8000-000000000000"
    log_capture.text()

    httpx.delete(f"{server.base_url}{PATH}/{token_id}", headers=_auth(server))
    httpx.get(server.base_url + "/health?key=비밀_문서_키")
    httpx.get(server.base_url + "/없는/경로/비밀")

    lines = log_capture.events("http_request", count=3)
    assert [(line["status"], line["path"]) for line in lines] == [
        (404, f"{PATH}/{{token_id}}"),
        (200, "/health"),
        (401, "unmatched"),
    ]
    text = log_capture.text()
    assert token_id not in text
    assert "비밀" not in text


def test_인증에_실패한_요청도_요청_ID와_상태가_로그에_남는다(
    server: RunningServer, log_capture: LogCapture
) -> None:
    log_capture.text()

    response = httpx.get(server.base_url + PATH)

    (line,) = log_capture.events("http_request", count=1)
    assert (line["request_id"], line["status"], line["path"]) == (
        response.headers["x-request-id"],
        401,
        PATH,
    )


def test_로그에_토큰_원문이_없다(server: RunningServer, log_capture: LogCapture) -> None:
    log_capture.text()
    wrong = "rag_wrong_token_value"
    created = httpx.post(
        server.base_url + PATH, headers=_auth(server), json={"name": "원문", "role": "reader"}
    ).json()
    own = {"Authorization": f"Bearer {created['token']}"}
    httpx.get(server.base_url + PATH, headers={"Authorization": f"Bearer {wrong}"})
    httpx.get(server.base_url + PATH, headers=own)
    httpx.post(server.mcp_url, headers={**own, "Host": "evil.example.com"}, json={})

    assert len(log_capture.events("http_request", count=4)) == 4
    text = log_capture.text()
    for secret in (wrong, created["token"], server.admin_token):
        assert secret not in text


def test_text_형식은_JSON이_아닌_한_줄이다(
    run_server: Callable[..., RunningServer], log_capture: LogCapture
) -> None:
    server = run_server(log_format="text")
    log_capture.text()

    httpx.get(server.base_url + "/health")

    (line,) = log_capture.lines_containing("http_request", count=1)
    assert not line.startswith("{")
    assert "path=/health" in line
    assert "status=200" in line


def test_처리하지_못한_오류는_500_internal_error이고_연결_정보와_원인_메시지를_남기지_않는다(
    run_server: Callable[..., RunningServer],
    seeded_database_url: str,
    log_capture: LogCapture,
) -> None:
    server = run_server(database_url=replace_database(seeded_database_url, "rag_no_such_database"))
    log_capture.text()

    response = httpx.get(server.base_url + PATH, headers=_auth(server))

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert (body["code"], body["request_id"]) == (
        "internal_error",
        response.headers["x-request-id"],
    )
    assert "detail" not in body
    (failure,) = log_capture.events("request_failed", count=1)
    assert failure["request_id"] == response.headers["x-request-id"]
    assert (failure["level"], failure["status"]) == ("error", 500)
    text = log_capture.text()
    assert "rag_no_such_database" not in text
    assert "rag_test" not in text
