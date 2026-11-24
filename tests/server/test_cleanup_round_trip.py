"""정리 작업의 왕복(source-sync 티켓 14, 명세 "Testing Decisions"의 주 이음매).

실제 uvicorn 서버와 실제 작업자(한 번 돌기), 공식 MCP 클라이언트의 `search`를 쓰고 임베딩 서버만
스텁이다. 시각은 데이터베이스의 지운 시각을 31일 전으로 옮겨 보관 기간(30일)을 넘긴다. 정리 작업은
작업 행을 직접 넣어 시작한다(일정 확인은 작업자가 상시로 돌 때만 돈다). 정리 작업이 지운 문서는
되살리는 요청이 404가 되고, 지운 원천의 이름은 다시 쓸 수 있고, 주인 없는 원본만 치워지며, 서버
폴더의 파일은 그대로다.
"""

import os
import time
from pathlib import Path
from typing import LiteralString

import httpx
import psycopg
from tests.harness import RunningServer
from tests.support.round_trip import RoundTrip, output

SOURCES = "/api/v1/admin/sources"
DOCUMENTS = "/api/v1/admin/documents"
EMBEDDINGS = "/v1/embeddings"
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
DAY_AND_A_HOUR = 25 * 60 * 60


def _admin(server: RunningServer, method: str, path: str, **body: object) -> httpx.Response:
    return httpx.request(
        method,
        server.base_url + path,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json=body if body else None,
        timeout=60,
    )


def _sql(server: RunningServer, query: LiteralString, *params: object) -> list[tuple[object, ...]]:
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        cursor = connection.execute(query, list(params))
        return cursor.fetchall() if cursor.description else []


def _start_cleanup(server: RunningServer) -> None:
    """정리 작업을 하나 넣는다. 같이 대기 중인 다른 작업보다 먼저 꺼내지도록 시각을 하루 앞에
    둔다."""
    _sql(
        server,
        "INSERT INTO jobs (id, kind, status, run_after, request_id, created_at)"
        " VALUES (gen_random_uuid(), 'cleanup', 'queued', now() - interval '1 day',"
        " gen_random_uuid(), now())",
    )


async def _seed(round_trip: RoundTrip) -> dict[str, str]:
    """원천 `wiki`에 문서 둘을 넣고 색인까지 끝낸다. 문서 ID를 키로 낸다."""
    assert _admin(round_trip.server, "POST", SOURCES, name="wiki", kind="push").status_code == 201
    ids: dict[str, str] = {}
    for key in ("a.docx", "b.docx"):
        response = await round_trip.ingest(*휴가, fields={"key": key, "source": "wiki"})
        assert response.status_code == 202
        ids[key] = response.json()["document_id"]
    await round_trip.work()
    return ids


def _blob_path(server: RunningServer, document_id: str) -> Path:
    [(path,)] = _sql(server, "SELECT blob_path FROM documents WHERE id = %s", document_id)
    assert isinstance(path, str)
    return server.settings.data_dir / path


async def test_보관_기간이_지난_지운_문서는_되살리는_요청이_404이고_원본_파일도_사라진다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    ids = await _seed(round_trip)
    blob = _blob_path(server, ids["a.docx"])
    assert (await round_trip.delete("a.docx", source="wiki")).status_code == 204
    assert blob.exists()
    _sql(
        server,
        "UPDATE documents SET deleted_at = now() - interval '31 days' WHERE id = %s",
        ids["a.docx"],
    )

    _start_cleanup(server)
    await round_trip.work()

    refused = _admin(server, "POST", f"{DOCUMENTS}/{ids['a.docx']}/restore")
    assert (refused.status_code, refused.json()["code"]) == (404, "document_not_found")
    assert not blob.exists()
    # 지우지 않은 문서는 그대로 검색에 나온다.
    assert {item.key for item in output(await round_trip.search("휴가")).results} == {"b.docx"}


async def test_보관_기간이_지난_지운_원천은_이름을_다시_쓸_수_있다(round_trip: RoundTrip) -> None:
    server = round_trip.server
    ids = await _seed(round_trip)
    assert _admin(server, "DELETE", f"{SOURCES}/wiki").status_code == 202
    await round_trip.work()
    _sql(server, "UPDATE sources SET deleted_at = now() - interval '31 days' WHERE name = 'wiki'")
    taken = _admin(server, "POST", SOURCES, name="wiki", kind="push")
    assert (taken.status_code, taken.json()["code"]) == (409, "source_already_exists")

    _start_cleanup(server)
    await round_trip.work()

    again = _admin(server, "POST", SOURCES, name="wiki", kind="push")
    assert again.status_code == 201
    for document_id in ids.values():
        gone = _admin(server, "GET", f"{DOCUMENTS}/{document_id}")
        assert (gone.status_code, gone.json()["code"]) == (404, "document_not_found")


async def test_주인_없는_묵은_원본만_치우고_서버_폴더와_그_밖의_파일은_그대로다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    ids = await _seed(round_trip)
    owned = _blob_path(server, ids["a.docx"])
    old = time.time() - DAY_AND_A_HOUR
    files = {
        "old": server.settings.data_dir / "blobs" / "orphan-document" / "old-blob",
        "fresh": server.settings.data_dir / "blobs" / "orphan-document" / "fresh-blob",
        "source_folder": server.settings.data_dir / "sources" / "규정집" / "규정.pdf",
        "other": server.settings.data_dir / "notes.txt",
    }
    for path in files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    for name in ("old", "source_folder", "other"):
        os.utime(files[name], (old, old))
    os.utime(owned, (old, old))

    _start_cleanup(server)
    await round_trip.work()

    assert not files["old"].exists()
    assert files["fresh"].exists()
    assert files["source_folder"].exists()
    assert files["other"].exists()
    assert owned.exists()


async def test_되살리는_요청만_보낸_원천의_문서는_정리_작업이_지우지_않고_작업자가_되살린다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    await _seed(round_trip)
    assert _admin(server, "DELETE", f"{SOURCES}/wiki").status_code == 202
    await round_trip.work()
    assert _admin(server, "POST", f"{SOURCES}/wiki/restore").status_code == 202
    # 되살리는 작업이 돌기 전에 문서의 지운 시각만 보관 기간 밖으로 옮긴다. 정리 작업이 먼저 돈다.
    _sql(
        server,
        "UPDATE documents SET deleted_at = now() - interval '31 days' WHERE deleted_with_source",
    )
    embeddings = round_trip.stub.count(EMBEDDINGS)

    _start_cleanup(server)
    await round_trip.work()

    assert round_trip.stub.count(EMBEDDINGS) == embeddings
    kinds = _sql(
        server, "SELECT kind, status FROM jobs WHERE kind IN ('cleanup', 'restore_source')"
    )
    assert sorted(kinds) == [("cleanup", "succeeded"), ("restore_source", "succeeded")]
    assert {item.key for item in output(await round_trip.search("휴가")).results} == {
        "a.docx",
        "b.docx",
    }
