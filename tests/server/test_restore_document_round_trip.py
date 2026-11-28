"""문서 복구의 왕복(source-sync 티켓 13, 명세 "Testing Decisions"의 주 이음매).

실제 uvicorn 서버와 실제 작업자(한 번 돌기), 공식 MCP 클라이언트의 `search`를 쓰고 임베딩 서버만
스텁이다. 지운 문서를 관리 API 호출 하나로 복구하면 임베딩을 다시 하지 않고 검색에 돌아오고, 그사이
색인 판이 바뀌었으면 색인 작업이 들어가 작업자를 돌린 뒤 검색에 나온다. 거절 넷도 HTTP로 본다.
"""

import httpx
import psycopg
from tests.harness import RunningServer
from tests.support.round_trip import RoundTrip, output

DOCUMENTS = "/api/v1/admin/documents"
SOURCES = "/api/v1/admin/sources"
JOBS = "/api/v1/admin/jobs"
EMBEDDINGS = "/v1/embeddings"
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
NEW_CHUNK_TOKENS = 48


def _post(server: RunningServer, path: str, token: str | None = None) -> httpx.Response:
    return httpx.post(
        server.base_url + path,
        headers={"Authorization": f"Bearer {token or server.admin_token}"},
        timeout=60,
    )


def _restore(server: RunningServer, document_id: object) -> httpx.Response:
    return _post(server, f"{DOCUMENTS}/{document_id}/restore")


def _create_push(server: RunningServer, name: str) -> None:
    response = httpx.post(
        server.base_url + SOURCES,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json={"name": name, "kind": "push"},
        timeout=60,
    )
    assert response.status_code == 201


async def _found(round_trip: RoundTrip) -> set[str]:
    return {item.key for item in output(await round_trip.search("연차휴가")).results}


async def test_지운_문서를_복구하면_임베딩_없이_검색에_돌아온다(round_trip: RoundTrip) -> None:
    round_trip.drop_reranker()
    ingested = await round_trip.ingest(*휴가)
    document_id = ingested.json()["document_id"]
    await round_trip.work()
    assert (await round_trip.delete("규정.docx")).status_code == 204
    assert await _found(round_trip) == set()
    embeddings = round_trip.stub.count(EMBEDDINGS)

    restored = _restore(round_trip.server, document_id)

    assert restored.status_code == 200
    body = restored.json()
    assert body["job_id"] is None
    assert (body["document"]["id"], body["document"]["status"]) == (document_id, "parsed")
    assert body["document"]["deleted_at"] is None
    assert [index["status"] for index in body["document"]["indexes"]] == ["indexed"]
    assert round_trip.stub.count(EMBEDDINGS) == embeddings
    assert await _found(round_trip) == {"규정.docx"}
    assert await round_trip.work() == 0


async def test_그_사이_색인_판이_바뀌었으면_색인_작업이_들어가고_작업자_뒤에_검색에_나온다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    first = await round_trip.ingest(*휴가)
    document_id = first.json()["document_id"]
    await round_trip.work()
    # 살아 있는 문서가 하나 더 있어야 재색인이 새 판을 건설 중으로 두고 작업을 넣는다.
    await round_trip.ingest(*휴가, fields={"key": "남는.docx"})
    await round_trip.work()
    assert (await round_trip.delete("규정.docx")).status_code == 204
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    assert (await round_trip.reindex()).status_code == 202

    restored = _restore(round_trip.server, document_id)

    assert restored.status_code == 200
    job_id = restored.json()["job_id"]
    assert job_id is not None
    job = httpx.get(
        round_trip.server.base_url + f"{JOBS}/{job_id}",
        headers={"Authorization": f"Bearer {round_trip.server.admin_token}"},
        timeout=60,
    ).json()["job"]
    assert (job["kind"], job["status"], job["document_id"]) == (
        "index_document",
        "queued",
        document_id,
    )
    await round_trip.work()
    assert "규정.docx" in await _found(round_trip)


async def test_지워지지_않은_문서는_409_document_not_deleted다(round_trip: RoundTrip) -> None:
    ingested = await round_trip.ingest(*휴가)

    refused = _restore(round_trip.server, ingested.json()["document_id"])

    assert (refused.status_code, refused.json()["code"]) == (409, "document_not_deleted")
    assert refused.headers["content-type"].startswith("application/problem+json")


async def test_없는_식별자는_404_document_not_found다(round_trip: RoundTrip) -> None:
    refused = _restore(round_trip.server, "00000000-0000-7000-8000-000000000000")

    assert (refused.status_code, refused.json()["code"]) == (404, "document_not_found")


async def test_가져오는_원천의_지운_문서는_409_wrong_source_kind다(round_trip: RoundTrip) -> None:
    _create_push(round_trip.server, "wiki")
    ingested = await round_trip.ingest(*휴가, fields={"source": "wiki"})
    document_id = ingested.json()["document_id"]
    assert (await round_trip.delete("규정.docx", source="wiki")).status_code == 204
    # 가져오는 원천을 만드는 요청은 폴더를 확인하므로, 지운 문서가 든 원천 행의 종류를 직접 바꾼다.
    with psycopg.connect(round_trip.server.settings.database_url, autocommit=True) as connection:
        connection.execute(
            "UPDATE sources SET kind = 'pull', connector = 'server_path',"
            ' config = \'{"folder": "x"}\'::jsonb,'
            " group_id = (SELECT id FROM groups WHERE name = 'default') WHERE name = 'wiki'"
        )

    refused = _restore(round_trip.server, document_id)

    assert (refused.status_code, refused.json()["code"]) == (409, "wrong_source_kind")


async def test_지운_원천의_문서는_409_source_deleted다(round_trip: RoundTrip) -> None:
    _create_push(round_trip.server, "wiki")
    ingested = await round_trip.ingest(*휴가, fields={"source": "wiki"})
    document_id = ingested.json()["document_id"]
    await round_trip.work()
    assert (await round_trip.delete("규정.docx", source="wiki")).status_code == 204
    removed = httpx.delete(
        round_trip.server.base_url + f"{SOURCES}/wiki",
        headers={"Authorization": f"Bearer {round_trip.server.admin_token}"},
        timeout=60,
    )
    assert removed.status_code == 202

    refused = _restore(round_trip.server, document_id)

    assert (refused.status_code, refused.json()["code"]) == (409, "source_deleted")


async def test_reader_토큰의_복구는_403이고_문서는_그대로다(round_trip: RoundTrip) -> None:
    ingested = await round_trip.ingest(*휴가)
    await round_trip.delete("규정.docx")
    reader = await round_trip.issue_reader()

    forbidden = _post(
        round_trip.server, f"{DOCUMENTS}/{ingested.json()['document_id']}/restore", reader
    )

    assert forbidden.status_code == 403
    with psycopg.connect(round_trip.server.settings.database_url) as connection:
        ((deleted_at,),) = connection.execute("SELECT deleted_at FROM documents").fetchall()
    assert deleted_at is not None
