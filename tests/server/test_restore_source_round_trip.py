"""원천 복구의 왕복(source-sync 티켓 12, 명세 "Testing Decisions"의 주 이음매).

실제 uvicorn 서버와 실제 작업자(한 번 돌기), 공식 MCP 클라이언트의 `search`를 쓰고 임베딩 서버만
스텁이다. 지운 원천을 복구하고 작업자를 돌리면 문서가 임베딩을 다시 하지 않고 검색에 돌아오고,
복구하고 지우는 요청이 서로 엇갈리지 않는다.
"""

import httpx
import psycopg
from tests.harness import RunningServer
from tests.support.round_trip import RoundTrip, error_body, output

SOURCES = "/api/v1/admin/sources"
DOCUMENTS = "/api/v1/admin/documents"
JOBS = "/api/v1/admin/jobs"
EMBEDDINGS = "/v1/embeddings"
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출산 = ("제1조 휴가", "배우자 출산휴가는 열흘이다.")


def _admin(server: RunningServer, method: str, path: str, **body: object) -> httpx.Response:
    return httpx.request(
        method,
        server.base_url + path,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json=body if body else None,
        timeout=60,
    )


def _create_push(server: RunningServer, name: str) -> None:
    assert _admin(server, "POST", SOURCES, name=name, kind="push").status_code == 201


async def _found(round_trip: RoundTrip, query: str = "휴가") -> dict[str, str]:
    """검색에 나온 문서의 키와 글."""
    return {item.key: item.text for item in output(await round_trip.search(query)).results}


async def _seed(round_trip: RoundTrip) -> dict[str, str]:
    """원천 `wiki`에 문서 둘, `default`에 문서 하나를 넣고 색인까지 끝낸다. 문서 ID를 키로 낸다."""
    _create_push(round_trip.server, "wiki")
    ids: dict[str, str] = {}
    for key, source in (("a.docx", "wiki"), ("b.docx", "wiki"), ("d.docx", "default")):
        response = await round_trip.ingest(*휴가, fields={"key": key, "source": source})
        assert response.status_code == 202
        ids[key] = response.json()["document_id"]
    await round_trip.work()
    assert set(await _found(round_trip)) == {"a.docx", "b.docx", "d.docx"}
    return ids


async def _delete_and_drain(round_trip: RoundTrip) -> None:
    assert _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki").status_code == 202
    await round_trip.work()


async def test_지운_원천을_복구하고_작업자를_돌리면_임베딩_없이_검색에_돌아온다(
    round_trip: RoundTrip,
) -> None:
    await _seed(round_trip)
    separate = await round_trip.delete("a.docx", source="wiki")
    assert separate.status_code == 204
    await _delete_and_drain(round_trip)
    assert set(await _found(round_trip)) == {"d.docx"}
    embeddings = round_trip.stub.count(EMBEDDINGS)

    restored = _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore")
    assert restored.status_code == 202
    job = _admin(round_trip.server, "GET", f"{JOBS}/{restored.json()['job_id']}").json()["job"]
    assert (job["kind"], job["status"], job["source"]) == ("restore_source", "queued", "wiki")
    # 표시를 걷은 순간부터 원천은 다시 요청을 받는다. 문서는 작업자가 복구하는 대로 돌아온다.
    shown = _admin(round_trip.server, "GET", f"{SOURCES}/wiki").json()
    assert shown["deleted_at"] is None
    assert restored.json()["connection_check"] is None
    await round_trip.work()
    # 검색은 질의를 임베딩하므로 개수는 검색 전에 잰다. 문서 조각은 다시 임베딩하지 않는다.
    assert round_trip.stub.count(EMBEDDINGS) == embeddings

    # 원천을 지우기 전에 따로 지운 a.docx는 돌아오지 않는다.
    assert set(await _found(round_trip)) == {"b.docx", "d.docx"}
    with psycopg.connect(round_trip.server.settings.database_url) as connection:
        jobs = connection.execute(
            "SELECT status, last_error_code FROM jobs WHERE kind = 'restore_source'"
        ).fetchall()
        marks = connection.execute(
            "SELECT key, deleted_at IS NOT NULL, deleted_with_source FROM documents"
            " WHERE source_id = (SELECT id FROM sources WHERE name = 'wiki') ORDER BY key"
        ).fetchall()
    assert jobs == [("succeeded", None)]
    assert marks == [("a.docx", True, False), ("b.docx", False, False)]


async def test_복구한_원천은_작업자를_돌리기_전에도_수집을_받는다(round_trip: RoundTrip) -> None:
    await _seed(round_trip)
    await _delete_and_drain(round_trip)
    assert _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore").status_code == 202

    accepted = await round_trip.ingest(*휴가, fields={"key": "c.docx", "source": "wiki"})

    assert accepted.status_code == 202
    await round_trip.work()
    assert set(await _found(round_trip)) == {"a.docx", "b.docx", "c.docx", "d.docx"}


async def test_복구하는_요청_뒤에_수집_API로_지운_문서는_돌아오지_않는다(
    round_trip: RoundTrip,
) -> None:
    ids = await _seed(round_trip)
    await _delete_and_drain(round_trip)
    assert _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore").status_code == 202

    removed = await round_trip.delete("a.docx", source="wiki")
    await round_trip.work()

    assert removed.status_code == 204
    assert set(await _found(round_trip)) == {"b.docx", "d.docx"}
    document = _admin(round_trip.server, "GET", f"{DOCUMENTS}/{ids['a.docx']}").json()
    assert document["status"] == "deleted"
    with psycopg.connect(round_trip.server.settings.database_url) as connection:
        row = connection.execute(
            "SELECT deleted_with_source FROM documents WHERE id = %s", [ids["a.docx"]]
        ).fetchone()
    assert row == (False,)


async def test_내용을_바꿔_넣고_색인이_돌기_전에_지웠다_복구하면_새_내용이_나온다(
    round_trip: RoundTrip,
) -> None:
    _create_push(round_trip.server, "wiki")
    first = await round_trip.ingest(*휴가, fields={"key": "a.docx", "source": "wiki"})
    assert first.status_code == 202
    await round_trip.work()
    changed = await round_trip.ingest(*출산, fields={"key": "a.docx", "source": "wiki"})
    assert changed.status_code == 202
    await _delete_and_drain(round_trip)

    assert _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore").status_code == 202
    await round_trip.work()
    await round_trip.work()

    texts = await _found(round_trip)
    assert set(texts) == {"a.docx"}
    assert "출산휴가" in texts["a.docx"]
    assert "연차휴가" not in texts["a.docx"]


async def test_지우는_작업이_끝나기_전의_복구와_복구하는_작업이_끝나기_전의_지우기는_409다(
    round_trip: RoundTrip,
) -> None:
    await _seed(round_trip)
    assert _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki").status_code == 202

    early = _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore")

    assert (early.status_code, early.json()["code"]) == (409, "source_change_in_progress")
    assert _admin(round_trip.server, "GET", f"{SOURCES}/wiki").json()["deleted_at"] is not None
    await round_trip.work()
    assert _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore").status_code == 202

    again = _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki")

    assert (again.status_code, again.json()["code"]) == (409, "source_change_in_progress")
    assert _admin(round_trip.server, "GET", f"{SOURCES}/wiki").json()["deleted_at"] is None
    await round_trip.work()
    # 작업이 끝난 뒤에는 요청을 받는다.
    assert _admin(round_trip.server, "DELETE", f"{SOURCES}/wiki").status_code == 202


async def test_지워지지_않은_원천과_없는_원천은_409와_404다(round_trip: RoundTrip) -> None:
    _create_push(round_trip.server, "wiki")

    alive = _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore")
    missing = _admin(round_trip.server, "POST", f"{SOURCES}/nothing/restore")

    assert (alive.status_code, alive.json()["code"]) == (409, "source_not_deleted")
    assert (missing.status_code, missing.json()["code"]) == (404, "source_not_found")


async def test_보관_기간이_지난_지운_원천은_복구할_수_없고_지운_채다(round_trip: RoundTrip) -> None:
    await _seed(round_trip)
    await _delete_and_drain(round_trip)
    with psycopg.connect(round_trip.server.settings.database_url, autocommit=True) as connection:
        connection.execute(
            "UPDATE sources SET deleted_at = now() - interval '31 days' WHERE name = 'wiki'"
        )

    refused = _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore")

    assert (refused.status_code, refused.json()["code"]) == (409, "source_retention_expired")
    assert _admin(round_trip.server, "GET", f"{SOURCES}/wiki").json()["deleted_at"] is not None
    assert set(await _found(round_trip)) == {"d.docx"}


async def test_default와_upload는_지운_적이_없어_복구하면_source_not_deleted다(
    round_trip: RoundTrip,
) -> None:
    for name in ("default", "upload"):
        response = _admin(round_trip.server, "POST", f"{SOURCES}/{name}/restore")

        assert (response.status_code, response.json()["code"]) == (409, "source_not_deleted")


async def test_복구한_원천의_문서는_문서_조회에_다시_읽힌다(round_trip: RoundTrip) -> None:
    # 지운 원천은 문서 조회에서 지워진 것으로 읽힌다(티켓 11). 복구하면 다시 읽힌다.
    ids = await _seed(round_trip)
    await _delete_and_drain(round_trip)
    hidden = error_body(await round_trip.get_document(ids["a.docx"]))
    assert hidden["code"] == "document_not_found"

    assert _admin(round_trip.server, "POST", f"{SOURCES}/wiki/restore").status_code == 202
    await round_trip.work()

    shown = await round_trip.get_document(ids["a.docx"])
    assert shown.is_error is not True
