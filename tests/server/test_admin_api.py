"""작업·문서 조회의 관리 API(명세 "관리 API", 스토리 7, 8, 티켓 15).

`GET /api/v1/admin/jobs/{job_id}`는 작업 행에 그 문서의 결과와 같은 문서에 남은 작업이 있는지를
더해 낸다. 작업의 상태는 문서의 결과가 아니다. 실제 uvicorn 서버와 실제 작업자(한 번 돌기)를 쓰고
임베딩 서버만 스텁이다. 오류 응답은 `application/problem+json`이다.
"""

from uuid import UUID

import httpx
from tests.harness import RunningServer
from tests.support.round_trip import RoundTrip

JOBS = "/api/v1/admin/jobs"
DOCUMENTS = "/api/v1/admin/documents"
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")


def _get(server: RunningServer, path: str, **params: object) -> httpx.Response:
    return httpx.get(
        server.base_url + path,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        params={name: str(value) for name, value in params.items()},
    )


async def test_수집_직후의_작업_조회는_대기_작업과_받음_상태의_문서를_낸다(
    round_trip: RoundTrip,
) -> None:
    ingested = (await round_trip.ingest(*휴가)).json()

    response = _get(round_trip.server, f"{JOBS}/{ingested['job_id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"job", "document", "active_jobs_remain"}
    assert body["active_jobs_remain"] is True
    job = body["job"]
    assert set(job) == {
        "id",
        "kind",
        "document_id",
        "status",
        "attempts",
        "run_after",
        "leased_until",
        "worker_id",
        "last_error_code",
        "request_id",
        "created_at",
        "started_at",
        "finished_at",
    }
    assert (job["id"], job["kind"], job["status"]) == (
        ingested["job_id"],
        "index_document",
        "queued",
    )
    assert job["document_id"] == ingested["document_id"]
    assert job["created_at"].endswith("Z")
    document = body["document"]
    assert document["id"] == ingested["document_id"]
    assert (document["status"], document["error_code"]) == ("received", None)
    assert document["indexes"] == [
        {
            "knowledge_base": "default",
            "index_version": "current",
            "status": None,
            "chunk_count": 0,
            "error_code": None,
        }
    ]


async def test_색인이_끝난_작업_조회는_파싱됨_상태와_판의_조각_수를_낸다(
    round_trip: RoundTrip,
) -> None:
    ingested = (await round_trip.ingest(*휴가)).json()
    await round_trip.work()

    body = _get(round_trip.server, f"{JOBS}/{ingested['job_id']}").json()

    assert body["job"]["status"] == "succeeded"
    assert body["active_jobs_remain"] is False
    assert body["document"]["status"] == "parsed"
    (index,) = body["document"]["indexes"]
    assert (index["status"], index["error_code"]) == ("indexed", None)
    assert index["chunk_count"] > 0


async def test_파싱이_실패한_작업_조회는_작업과_문서와_판의_오류_코드를_낸다(
    round_trip: RoundTrip,
) -> None:
    broken = (await round_trip.ingest_bytes(b"PK\x03\x04 broken", "깨짐.docx")).json()
    await round_trip.work()

    body = _get(round_trip.server, f"{JOBS}/{broken['job_id']}").json()

    assert (body["job"]["status"], body["job"]["last_error_code"]) == ("failed", "parse_failed")
    assert (body["document"]["status"], body["document"]["error_code"]) == (
        "failed",
        "parse_failed",
    )
    (index,) = body["document"]["indexes"]
    assert (index["status"], index["error_code"]) == ("failed", "parse_failed")


async def test_앞선_작업이_succeeded여도_뒤_작업이_남았으면_남았다고_낸다(
    round_trip: RoundTrip,
) -> None:
    first = (await round_trip.ingest(*휴가)).json()
    await round_trip.work()
    second = (await round_trip.ingest(*출장)).json()
    assert second["document_id"] == first["document_id"]
    assert second["job_id"] != first["job_id"]

    body = _get(round_trip.server, f"{JOBS}/{first['job_id']}").json()

    assert body["job"]["status"] == "succeeded"
    assert body["active_jobs_remain"] is True
    assert body["document"]["status"] == "received"


async def test_없는_작업은_404_job_not_found_Problem_Details다(server: RunningServer) -> None:
    response = _get(server, f"{JOBS}/{UUID(int=0)}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert (body["code"], body["status"]) == ("job_not_found", 404)
    assert body["request_id"] == response.headers["x-request-id"]


async def test_작업_ID가_UUID가_아니면_422_validation_error와_errors를_낸다(
    server: RunningServer,
) -> None:
    response = _get(server, f"{JOBS}/아님")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    (issue,) = body["errors"]
    assert issue["loc"] == ["path", "job_id"]
    assert set(issue) == {"loc", "type", "msg"}


async def test_작업_목록은_최근_순이고_상태_한도_커서를_따른다(round_trip: RoundTrip) -> None:
    first = (await round_trip.ingest(*휴가, filename="휴가.docx")).json()
    await round_trip.work()
    second = (await round_trip.ingest(*출장, filename="출장.docx")).json()
    server = round_trip.server

    everything = _get(server, JOBS).json()
    queued = _get(server, JOBS, status="queued").json()
    page = _get(server, JOBS, limit=1).json()
    older = _get(server, JOBS, after=second["job_id"]).json()

    assert [job["id"] for job in everything["jobs"]] == [second["job_id"], first["job_id"]]
    assert [job["id"] for job in queued["jobs"]] == [second["job_id"]]
    assert [job["id"] for job in page["jobs"]] == [second["job_id"]]
    assert [job["id"] for job in older["jobs"]] == [first["job_id"]]


async def test_작업_목록의_잘못된_조건은_422다(server: RunningServer) -> None:
    for params in ({"status": "없는상태"}, {"limit": 0}, {"limit": 201}, {"after": "아님"}):
        response = _get(server, JOBS, **params)

        assert response.status_code == 422, params
        assert response.json()["code"] == "validation_error", params


async def test_문서_조회는_원천_그룹_메타데이터와_색인_상태를_낸다(round_trip: RoundTrip) -> None:
    ingested = (await round_trip.ingest(*휴가, fields={"metadata": '{"부서": "기획팀"}'})).json()
    await round_trip.work()

    response = _get(round_trip.server, f"{DOCUMENTS}/{ingested['document_id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "key",
        "title",
        "source",
        "group",
        "mime",
        "size_bytes",
        "status",
        "error_code",
        "metadata",
        "updated_at",
        "created_at",
        "deleted_at",
        "indexes",
    }
    assert (body["key"], body["source"], body["group"]) == ("규정.docx", "default", "default")
    assert body["metadata"] == {"부서": "기획팀"}
    assert body["status"] == "parsed"
    assert body["deleted_at"] is None
    assert body["updated_at"].endswith("Z")
    assert [(i["knowledge_base"], i["status"]) for i in body["indexes"]] == [("default", "indexed")]


async def test_그룹이_여러_지식베이스에_들면_지식베이스마다_색인_상태를_낸다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.add_group_with_knowledge_base("팀B", "b")
    round_trip.link_group("팀B", "default")
    ingested = (await round_trip.ingest(*휴가, fields={"group": "팀B"})).json()
    await round_trip.work()

    body = _get(round_trip.server, f"{DOCUMENTS}/{ingested['document_id']}").json()

    assert [(i["knowledge_base"], i["index_version"], i["status"]) for i in body["indexes"]] == [
        ("b", "current", "indexed"),
        ("default", "current", "indexed"),
    ]
    assert all(index["chunk_count"] > 0 for index in body["indexes"])


async def test_없는_문서는_404_document_not_found다(server: RunningServer) -> None:
    response = _get(server, f"{DOCUMENTS}/{UUID(int=0)}")

    assert response.status_code == 404
    body = response.json()
    assert (body["code"], body["status"]) == ("document_not_found", 404)


async def test_지운_문서는_삭제됨_상태이고_색인_상태가_없다(round_trip: RoundTrip) -> None:
    ingested = (await round_trip.ingest(*휴가)).json()
    await round_trip.work()
    assert (await round_trip.delete("규정.docx")).status_code == 204

    body = _get(round_trip.server, f"{DOCUMENTS}/{ingested['document_id']}").json()

    assert body["status"] == "deleted"
    assert body["deleted_at"].endswith("Z")
    assert body["indexes"] == []


async def test_문서_목록은_키_상태_그룹으로_거르고_최근_순이며_커서를_따른다(
    round_trip: RoundTrip,
) -> None:
    round_trip.add_group("팀B")
    first = (await round_trip.ingest(*휴가, filename="휴가.docx")).json()
    second = (await round_trip.ingest(*출장, filename="출장.docx", fields={"group": "팀B"})).json()
    await round_trip.work()
    await round_trip.delete("출장.docx")
    server = round_trip.server

    def ids(**params: object) -> list[str]:
        response = _get(server, DOCUMENTS, **params)
        assert response.status_code == 200
        return [document["id"] for document in response.json()["documents"]]

    assert ids() == [second["document_id"], first["document_id"]]
    assert ids(key="휴가.docx") == [first["document_id"]]
    assert ids(status="deleted") == [second["document_id"]]
    assert ids(status="parsed") == [first["document_id"]]
    assert ids(group="팀B") == [second["document_id"]]
    assert ids(group="없는 그룹") == []
    assert ids(limit=1) == [second["document_id"]]
    assert ids(after=second["document_id"]) == [first["document_id"]]


async def test_문서_목록의_잘못된_조건은_422다(server: RunningServer) -> None:
    for params in ({"status": "없는상태"}, {"limit": 0}, {"after": "아님"}):
        response = _get(server, DOCUMENTS, **params)

        assert response.status_code == 422, params
        assert response.json()["code"] == "validation_error", params


async def test_reader_토큰은_조회_경로에서_403이다(round_trip: RoundTrip) -> None:
    token = await round_trip.issue_reader()

    for path in (JOBS, DOCUMENTS):
        response = httpx.get(
            round_trip.server.base_url + path, headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"


async def test_토큰_없는_조회는_401이다(server: RunningServer) -> None:
    response = httpx.get(server.base_url + JOBS)

    assert response.status_code == 401
