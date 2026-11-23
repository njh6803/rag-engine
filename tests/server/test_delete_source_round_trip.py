"""원천 삭제의 왕복(source-sync 티켓 11, 명세 "Testing Decisions"의 주 이음매).

실제 uvicorn 서버와 실제 작업자(한 번 돌기), 공식 MCP 클라이언트의 `search`와 `get_document`를 쓰고
임베딩 서버만 스텁이다. 원천을 지운 순간(작업자를 돌리기 전)부터 그 원천의 문서가 검색, 문서 조회,
관리 API에서 지워진 것으로 읽히고, 지운 원천은 수집과 관리 요청을 409로 거절하며, 작업자를 돌리면
문서가 삭제 보관함으로 옮겨진다.
"""

import httpx
import psycopg
from tests.harness import RunningServer
from tests.support.round_trip import RoundTrip, document_output, error_body, output

SOURCES = "/api/v1/admin/sources"
DOCUMENTS = "/api/v1/admin/documents"
JOBS = "/api/v1/admin/jobs"
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")


def _admin(server: RunningServer, method: str, path: str, **body: object) -> httpx.Response:
    return httpx.request(
        method,
        server.base_url + path,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json=body if body else None,
        timeout=60,
    )


def _documents(server: RunningServer, **params: str) -> list[dict[str, object]]:
    """관리 API의 문서 목록. `params`는 쿼리 매개변수다."""
    response = httpx.get(
        server.base_url + DOCUMENTS,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        params=params,
        timeout=60,
    )
    assert response.status_code == 200
    found: list[dict[str, object]] = response.json()["documents"]
    return found


def _create_push(server: RunningServer, name: str) -> None:
    assert _admin(server, "POST", SOURCES, name=name, kind="push").status_code == 201


async def _found(round_trip: RoundTrip) -> set[str]:
    """검색에 나온 문서의 키."""
    return {item.key for item in output(await round_trip.search("휴가")).results}


async def _seed(round_trip: RoundTrip) -> dict[str, str]:
    """원천 `wiki`에 문서 둘, `default`에 문서 하나를 넣고 색인까지 끝낸다. 문서 ID를 키로 낸다."""
    _create_push(round_trip.server, "wiki")
    ids: dict[str, str] = {}
    for key, source in (("a.docx", "wiki"), ("b.docx", "wiki"), ("d.docx", "default")):
        response = await round_trip.ingest(*휴가, fields={"key": key, "source": source})
        assert response.status_code == 202
        ids[key] = response.json()["document_id"]
    await round_trip.work()
    assert await _found(round_trip) == {"a.docx", "b.docx", "d.docx"}
    return ids


async def test_원천을_지운_직후에는_검색과_문서_조회에서_빠지고_수집은_409다(
    round_trip: RoundTrip,
) -> None:
    ids = await _seed(round_trip)

    deleted = _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki")

    assert deleted.status_code == 202
    job = _admin(round_trip.server, "GET", f"{JOBS}/{deleted.json()['job_id']}").json()["job"]
    assert (job["kind"], job["status"], job["source"]) == ("delete_source", "queued", "wiki")
    assert await _found(round_trip) == {"d.docx"}
    hidden = error_body(await round_trip.get_document(ids["a.docx"]))
    assert hidden["code"] == "document_not_found"
    assert document_output(await round_trip.get_document(ids["d.docx"])).key == "d.docx"
    document = _admin(round_trip.server, "GET", f"{DOCUMENTS}/{ids['a.docx']}").json()
    assert (document["status"], document["indexes"]) == ("deleted", [])
    assert document["deleted_at"] is not None
    listed = _documents(round_trip.server, source="wiki", status="deleted")
    assert {found["key"] for found in listed} == {"a.docx", "b.docx"}
    assert _documents(round_trip.server, source="wiki", status="parsed") == []
    refused = await round_trip.ingest(*휴가, fields={"key": "c.docx", "source": "wiki"})
    assert refused.status_code == 409
    assert refused.json()["code"] == "source_deleted"
    removed = await round_trip.delete("a.docx", source="wiki")
    assert (removed.status_code, removed.json()["code"]) == (409, "source_deleted")


async def test_작업자를_돌리면_문서가_삭제_보관함으로_옮겨져_검색에_없고_표시가_선다(
    round_trip: RoundTrip,
) -> None:
    ids = await _seed(round_trip)
    separate = await round_trip.delete("a.docx", source="wiki")
    assert separate.status_code == 204
    _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki")

    await round_trip.work()

    assert await _found(round_trip) == {"d.docx"}
    with psycopg.connect(round_trip.server.settings.database_url) as connection:
        rows = connection.execute(
            "SELECT key, deleted_at IS NOT NULL, deleted_with_source FROM documents"
            " WHERE source_id = (SELECT id FROM sources WHERE name = 'wiki') ORDER BY key"
        ).fetchall()
        archived = connection.execute(
            "SELECT count(DISTINCT document_id) FROM archived_chunks WHERE document_id = %s",
            [ids["b.docx"]],
        ).fetchone()
        jobs = connection.execute(
            "SELECT status, last_error_code FROM jobs WHERE kind = 'delete_source'"
        ).fetchall()
    # 원천을 지우기 전에 따로 지운 문서는 원천과 함께 지워졌다는 표시가 서지 않는다.
    assert rows == [("a.docx", True, False), ("b.docx", True, True)]
    assert archived == (1,)
    assert jobs == [("succeeded", None)]


async def test_default와_upload는_지울_수_없다(round_trip: RoundTrip) -> None:
    for name in ("default", "upload"):
        response = _admin(round_trip.server, "DELETE", f"{SOURCES}/{name}")

        assert response.status_code == 409
        assert response.json()["code"] == "source_protected"
    listed = _admin(round_trip.server, "GET", SOURCES).json()["sources"]
    assert {(found["name"], found["deleted_at"]) for found in listed} == {
        ("default", None),
        ("upload", None),
    }
    with psycopg.connect(round_trip.server.settings.database_url) as connection:
        assert connection.execute("SELECT count(*) FROM jobs").fetchone() == (0,)


async def test_없는_원천과_이미_지운_원천을_지우면_404와_409다(round_trip: RoundTrip) -> None:
    _create_push(round_trip.server, "wiki")
    assert _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki").status_code == 202

    again = _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki")
    missing = _admin(round_trip.server, "DELETE", f"{SOURCES}/nothing")

    assert (again.status_code, again.json()["code"]) == (409, "source_deleted")
    assert (missing.status_code, missing.json()["code"]) == (404, "source_not_found")


async def test_지운_원천과_같은_이름으로_원천을_만들_수_없다(round_trip: RoundTrip) -> None:
    _create_push(round_trip.server, "wiki")
    _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki")

    response = _admin(round_trip.server, "POST", SOURCES, name="wiki", kind="push")

    assert response.status_code == 409
    assert response.json()["code"] == "source_already_exists"


async def test_원천_목록은_include_deleted를_켜야_지운_원천을_낸다(round_trip: RoundTrip) -> None:
    _create_push(round_trip.server, "wiki")
    _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki")

    plain = _admin(round_trip.server, "GET", SOURCES).json()["sources"]
    with_deleted = _admin(round_trip.server, "GET", f"{SOURCES}?include_deleted=true").json()
    one = _admin(round_trip.server, "GET", f"{SOURCES}/wiki")

    assert "wiki" not in {found["name"] for found in plain}
    deleted = {found["name"]: found["deleted_at"] for found in with_deleted["sources"]}
    assert deleted["wiki"] is not None
    assert one.status_code == 200
    assert one.json()["deleted_at"] is not None


async def test_지운_원천은_보기와_동기화_기록_보기만_받고_나머지는_409다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    # 이 시험은 커넥터 설정의 확인이 아니라 지운 원천의 거절을 본다. 폴더를 확인하는 만들기 요청
    # 대신 가져오는 원천의 행을 데이터베이스에 직접 둔다.
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO sources (id, name, kind, connector, config, group_id)"
            " SELECT gen_random_uuid(), 'pulled', 'pull', 'server_path',"
            " '{\"folder\": \"x\"}'::jsonb, id FROM groups WHERE name = 'default'"
        )
    assert _admin(server, "DELETE", f"{SOURCES}/pulled").status_code == 202

    refused = [
        _admin(server, "PATCH", f"{SOURCES}/pulled", exclude_patterns=["x"]),
        _admin(server, "DELETE", f"{SOURCES}/pulled"),
        _admin(server, "POST", f"{SOURCES}/pulled/check"),
        _admin(server, "POST", f"{SOURCES}/pulled/sync"),
        _admin(server, "POST", f"{SOURCES}/pulled/pause"),
        _admin(server, "POST", f"{SOURCES}/pulled/resume"),
    ]

    assert [(response.status_code, response.json()["code"]) for response in refused] == [
        (409, "source_deleted")
    ] * 6
    assert _admin(server, "GET", f"{SOURCES}/pulled").status_code == 200
    assert _admin(server, "GET", f"{SOURCES}/pulled/sync-records").status_code == 200


async def test_지운_밀어_넣는_원천에_가져오는_원천용_요청을_보내도_source_deleted다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    _create_push(server, "wiki")
    _admin(server, "DELETE", f"{SOURCES}/wiki")

    response = _admin(server, "POST", f"{SOURCES}/wiki/sync")

    assert (response.status_code, response.json()["code"]) == (409, "source_deleted")


async def test_원천을_지워도_다른_원천의_문서와_색인은_그대로다(round_trip: RoundTrip) -> None:
    await _seed(round_trip)
    _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki")
    await round_trip.work()
    fresh = await round_trip.ingest("제2조 휴가", "휴가는 사흘 전에 신청한다.")

    assert fresh.status_code == 202
    await round_trip.work()
    assert await _found(round_trip) == {"d.docx", "규정.docx"}
