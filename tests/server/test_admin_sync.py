"""지금 동기화와 동기화 기록을 보는 관리 API(source-sync 티켓 07, 명세 "관리 API", "동기화 기록").

실제 uvicorn 서버와 실제 파일 시스템을 쓴다. 작업자는 돌리지 않으므로 동기화 작업은 대기열에
`queued`로 남는다. 앞 동기화가 끝난 뒤의 기록(목록의 쪽 나누기)을 보려면 그 작업 행을
데이터베이스에서 직접 `succeeded`로 바꾼다.
"""

from pathlib import Path
from uuid import UUID

import httpx
import pytest
import sqlalchemy as sa
from tests.harness import RunningServer
from tests.support.pull_source_http import SOURCES, create_pull, request

JOBS = "/api/v1/admin/jobs"
RECORD_FIELDS = {
    "id",
    "source",
    "job_id",
    "trigger",
    "options",
    "status",
    "failure_code",
    "created_at",
    "started_at",
    "finished_at",
    "listed",
    "added",
    "updated",
    "deleted",
    "unchanged",
    "skipped",
    "not_accepted",
    "failed",
}


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sources"
    (path / "규정집").mkdir(parents=True)
    (path / "회의록").mkdir()
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


def _sync(server: RunningServer, name: str = "wiki", **options: object) -> httpx.Response:
    return request(server, "POST", f"{SOURCES}/{name}/sync", **options)


def _finish_queued_sync_jobs(server: RunningServer) -> None:
    """작업자가 없어도 앞 동기화가 끝난 상태를 만든다(겹침 판정은 대기 중이거나 실행 중인 작업만
    본다)."""
    engine = sa.create_engine(server.settings.database_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE jobs SET status = 'succeeded', finished_at = now()"
                " WHERE kind = 'sync_source' AND status = 'queued'"
            )
        )
    engine.dispose()


@pytest.fixture
def wiki(server: RunningServer, parent: Path) -> RunningServer:
    assert create_pull(server, "wiki", "규정집").status_code == 201
    return server


def test_지금_동기화는_202와_기록_식별자와_작업_식별자를_내고_기록은_queued다(
    wiki: RunningServer,
) -> None:
    response = _sync(wiki)

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"sync_record_id", "job_id"}
    record = request(wiki, "GET", f"{SOURCES}/wiki/sync-records/{body['sync_record_id']}").json()
    assert set(record) == RECORD_FIELDS
    assert (record["source"], record["job_id"]) == ("wiki", body["job_id"])
    assert (record["trigger"], record["status"], record["options"]) == ("manual", "queued", {})
    assert (record["failure_code"], record["started_at"], record["finished_at"]) == (
        None,
        None,
        None,
    )
    assert record["listed"] is None
    assert record["skipped"] == record["not_accepted"] == record["failed"] == {}
    assert [record[key] for key in ("added", "updated", "deleted", "unchanged")] == [0, 0, 0, 0]


def test_켠_옵션은_기록의_옵션_칸에_남는다(wiki: RunningServer) -> None:
    response = _sync(wiki, apply_empty=True, reread=True)

    assert response.status_code == 202
    record = request(
        wiki, "GET", f"{SOURCES}/wiki/sync-records/{response.json()['sync_record_id']}"
    ).json()
    assert record["options"] == {"apply_empty": True, "reread": True}


def test_알_수_없는_옵션은_422다(wiki: RunningServer) -> None:
    assert _sync(wiki, 모두=True).status_code == 422
    assert request(wiki, "GET", f"{SOURCES}/wiki/sync-records").json() == {"sync_records": []}


def test_앞_동기화가_대기_중이면_409_sync_in_progress이고_기록이_늘지_않는다(
    wiki: RunningServer,
) -> None:
    first = _sync(wiki)

    second = _sync(wiki)

    assert (second.status_code, second.json()["code"]) == (409, "sync_in_progress")
    records = request(wiki, "GET", f"{SOURCES}/wiki/sync-records").json()["sync_records"]
    assert [record["id"] for record in records] == [first.json()["sync_record_id"]]


def test_앞_동기화가_끝나면_다시_받는다(wiki: RunningServer) -> None:
    assert _sync(wiki).status_code == 202
    _finish_queued_sync_jobs(wiki)

    assert _sync(wiki).status_code == 202


def test_일시_중지한_원천도_받는다(wiki: RunningServer) -> None:
    request(wiki, "POST", f"{SOURCES}/wiki/pause")

    assert _sync(wiki).status_code == 202


def test_밀어_넣는_원천은_409_wrong_source_kind다(server: RunningServer) -> None:
    response = _sync(server, "default")

    assert (response.status_code, response.json()["code"]) == (409, "wrong_source_kind")


def test_없는_원천은_404_source_not_found다(server: RunningServer) -> None:
    response = _sync(server, "없는원천")

    assert (response.status_code, response.json()["code"]) == (404, "source_not_found")


def test_기록_목록은_최근_것부터_내고_한도와_커서를_따른다(wiki: RunningServer) -> None:
    ids: list[str] = []
    for _ in range(3):
        ids.append(_sync(wiki).json()["sync_record_id"])
        _finish_queued_sync_jobs(wiki)

    everything = request(wiki, "GET", f"{SOURCES}/wiki/sync-records").json()["sync_records"]
    page = request(wiki, "GET", f"{SOURCES}/wiki/sync-records?limit=2").json()["sync_records"]
    rest = request(
        wiki, "GET", f"{SOURCES}/wiki/sync-records?limit=2&after={page[-1]['id']}"
    ).json()["sync_records"]

    assert [record["id"] for record in everything] == ids[::-1]
    assert [record["id"] for record in page] == ids[::-1][:2]
    assert [record["id"] for record in rest] == ids[:1]


def test_없는_원천의_기록은_404_source_not_found다(server: RunningServer) -> None:
    listed = request(server, "GET", f"{SOURCES}/없는원천/sync-records")
    one = request(server, "GET", f"{SOURCES}/없는원천/sync-records/{UUID(int=1)}")

    assert [(r.status_code, r.json()["code"]) for r in (listed, one)] == [
        (404, "source_not_found"),
        (404, "source_not_found"),
    ]


def test_없는_기록과_다른_원천의_기록은_404_sync_record_not_found다(
    wiki: RunningServer,
) -> None:
    assert create_pull(wiki, "minutes", "회의록").status_code == 201
    mine = _sync(wiki).json()["sync_record_id"]

    missing = request(wiki, "GET", f"{SOURCES}/wiki/sync-records/{UUID(int=1)}")
    foreign = request(wiki, "GET", f"{SOURCES}/minutes/sync-records/{mine}")

    assert [(r.status_code, r.json()["code"]) for r in (missing, foreign)] == [
        (404, "sync_record_not_found"),
        (404, "sync_record_not_found"),
    ]


def test_원천_보기의_last_sync는_가장_최근_기록이고_기록이_없으면_null이다(
    wiki: RunningServer,
) -> None:
    assert request(wiki, "GET", f"{SOURCES}/wiki").json()["last_sync"] is None
    _sync(wiki)
    _finish_queued_sync_jobs(wiki)
    latest = _sync(wiki).json()["sync_record_id"]

    shown = request(wiki, "GET", f"{SOURCES}/wiki").json()["last_sync"]
    listed = next(
        found["last_sync"]
        for found in request(wiki, "GET", SOURCES).json()["sources"]
        if found["name"] == "wiki"
    )

    assert shown["id"] == listed["id"] == latest
    assert set(shown) == RECORD_FIELDS


def test_작업_조회는_동기화_작업을_종류와_원천_이름으로_보이고_문서_식별자는_null이다(
    wiki: RunningServer,
) -> None:
    job_id = _sync(wiki).json()["job_id"]

    listed = request(wiki, "GET", JOBS).json()["jobs"]
    one = request(wiki, "GET", f"{JOBS}/{job_id}").json()

    (job,) = listed
    assert (job["id"], job["kind"], job["document_id"], job["source"]) == (
        job_id,
        "sync_source",
        None,
        "wiki",
    )
    assert (job["status"], job["attempts"]) == ("queued", 0)
    assert one["job"] == job
    assert (one["document"], one["active_jobs_remain"]) == (None, False)
