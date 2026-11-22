"""가져오는 원천을 만지는 관리 API 시험이 함께 쓰는 요청 도우미. 시험 서버(`RunningServer`)에
`admin` 토큰으로 요청한다."""

import httpx
from tests.harness import RunningServer

SOURCES = "/api/v1/admin/sources"


def request(server: RunningServer, method: str, path: str, **body: object) -> httpx.Response:
    return httpx.request(
        method,
        server.base_url + path,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json=body if body else None,
        timeout=60,
    )


def create_pull(
    server: RunningServer, name: str, folder: str, *, connector: str = "server_path"
) -> httpx.Response:
    return request(
        server,
        "POST",
        SOURCES,
        name=name,
        kind="pull",
        connector=connector,
        config={"folder": folder},
    )


def errors(response: httpx.Response) -> list[tuple[object, object]]:
    """422 응답의 오류 목록에서 (`loc`의 마지막 토막, `type`)을 뽑는다."""
    return [(issue["loc"][-1], issue["type"]) for issue in response.json()["errors"]]
