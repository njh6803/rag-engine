"""지식베이스 관리 API(명세 "관리 API", 스토리 33, 티켓 14).

`GET /api/v1/admin/knowledge-bases`와 `GET .../{name}`은 "재색인 필요"와 건설 중인 판의 진행을 내고,
`POST .../{name}/reindex`는 새 판을 만들어 202로 답한다. 실제 uvicorn 서버와 실제 작업자(한 번
돌기)를 쓰고 임베딩 서버만 스텁이다. 오류 응답은 `application/problem+json`이다.
"""

import httpx
from tests.harness import RunningServer
from tests.support.round_trip import RoundTrip

from rag_engine.server.admin_knowledge_base_models import (
    BuildProgressResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)

KNOWLEDGE_BASES = "/api/v1/admin/knowledge-bases"
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")
NEW_CHUNK_TOKENS = 64


def _headers(server: RunningServer, token: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or server.admin_token}"}


def _get(server: RunningServer, path: str) -> httpx.Response:
    return httpx.get(server.base_url + path, headers=_headers(server))


def _post(server: RunningServer, path: str, token: str | None = None) -> httpx.Response:
    return httpx.post(server.base_url + path, headers=_headers(server, token))


def _default(server: RunningServer) -> KnowledgeBaseResponse:
    response = _get(server, KNOWLEDGE_BASES)
    assert response.status_code == 200
    listed = KnowledgeBaseListResponse.model_validate(response.json())
    (default,) = (item for item in listed.knowledge_bases if item.name == "default")
    return default


async def test_목록은_이름_설명_문서_수_현재_판_재색인_필요_진행을_낸다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.ingest(*휴가)
    await round_trip.work()

    response = _get(round_trip.server, KNOWLEDGE_BASES)

    (raw,) = [item for item in response.json()["knowledge_bases"] if item["name"] == "default"]
    assert set(raw) == {
        "name",
        "description",
        "document_count",
        "current_index_version",
        "reindex_needed",
        "building",
    }
    assert set(raw["current_index_version"]) == {
        "id",
        "status",
        "schema_version",
        "embedding_endpoint",
        "embedding_model",
        "embedding_dimensions",
        "chunking",
        "chunking_hash",
        "tokenizer_version",
        "created_at",
        "retired_at",
    }
    default = _default(round_trip.server)
    assert (default.document_count, default.reindex_needed, default.building) == (1, False, None)
    assert default.current_index_version is not None
    assert default.current_index_version.status.value == "current"


async def test_지식베이스_설정이_현재_판과_다르면_재색인_필요가_참이다(
    round_trip: RoundTrip,
) -> None:
    round_trip.change_settings(NEW_CHUNK_TOKENS)

    needed = _default(round_trip.server).reindex_needed
    assert needed is True, f"설정을 바꿨는데 재색인 필요가 {needed}로 나왔다"


async def test_상세는_목록의_칸에_설정과_모든_색인_판을_더한다(round_trip: RoundTrip) -> None:
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    started = _post(round_trip.server, f"{KNOWLEDGE_BASES}/default/reindex")
    assert started.status_code == 202

    response = _get(round_trip.server, f"{KNOWLEDGE_BASES}/default")

    assert response.status_code == 200
    body = response.json()
    assert body["settings"]["chunking"] == {
        "strategy": "structure_first",
        "max_tokens": NEW_CHUNK_TOKENS,
        "overlap_tokens": 8,
    }
    assert [version["status"] for version in body["index_versions"]] == ["current", "retired"]
    assert body["index_versions"][0]["id"] == started.json()["index_version_id"]
    assert body["reindex_needed"] is False


async def test_재색인을_시작하면_202와_새_판_ID를_내고_진행을_센다(round_trip: RoundTrip) -> None:
    await round_trip.ingest(*휴가)
    await round_trip.ingest(*출장, filename="출장.docx")
    await round_trip.work()
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    assert _default(round_trip.server).reindex_needed is True

    response = _post(round_trip.server, f"{KNOWLEDGE_BASES}/default/reindex")

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"index_version_id", "jobs_enqueued"}
    assert body["jobs_enqueued"] == 2
    building = _default(round_trip.server).building
    assert building is not None
    assert (str(building.index_version_id), building.total) == (body["index_version_id"], 2)
    assert building == BuildProgressResponse(
        index_version_id=building.index_version_id, total=2, pending=2, indexed=0, failed=0
    )
    await round_trip.work()
    after = _default(round_trip.server)
    assert (after.building, after.reindex_needed) == (None, False)


async def test_건설_중인_판이_있으면_재색인은_409_reindex_in_progress다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.ingest(*휴가)
    await round_trip.work()
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    assert _post(round_trip.server, f"{KNOWLEDGE_BASES}/default/reindex").status_code == 202

    response = _post(round_trip.server, f"{KNOWLEDGE_BASES}/default/reindex")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "reindex_in_progress"


async def test_모르는_지식베이스는_404_knowledge_base_not_found다(round_trip: RoundTrip) -> None:
    server = round_trip.server

    for response in (
        _get(server, f"{KNOWLEDGE_BASES}/없음"),
        _post(server, f"{KNOWLEDGE_BASES}/없음/reindex"),
    ):
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "knowledge_base_not_found"


async def test_토큰이_없으면_401이고_reader_토큰은_403이다(round_trip: RoundTrip) -> None:
    server = round_trip.server
    reader = await round_trip.issue_reader("default")

    without = httpx.get(server.base_url + KNOWLEDGE_BASES)
    as_reader = httpx.get(server.base_url + KNOWLEDGE_BASES, headers=_headers(server, reader))
    reindex_as_reader = _post(server, f"{KNOWLEDGE_BASES}/default/reindex", reader)

    assert without.status_code == 401
    assert as_reader.status_code == 403
    assert reindex_as_reader.status_code == 403
