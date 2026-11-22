"""수집 API의 원천 이름(source-sync 명세 "수집 API", 스토리 2, 3, 4).

넣기 요청의 폼과 지우기 요청의 쿼리에 `source`를 적으면 그 원천에 넣고 지운다. 적지 않으면
`default`다. 원천이 다르면 같은 키가 서로 다른 문서로 남는다. 실제 서버와 실제 작업자(한 번 돌기)를
쓰고 임베딩 서버만 스텁이다.
"""

import httpx
import psycopg
import pytest
from tests.harness import RunningServer
from tests.support.docx_files import docx_bytes
from tests.support.round_trip import RoundTrip, output

SOURCES = "/api/v1/admin/sources"
DOCUMENTS = "/api/v1/admin/documents"
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")


def _create_source(server: RunningServer, name: str) -> None:
    response = httpx.post(
        server.base_url + SOURCES,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json={"name": name, "kind": "push"},
    )
    assert response.status_code == 201


def _documents(server: RunningServer, **params: str) -> list[dict[str, object]]:
    response = httpx.get(
        server.base_url + DOCUMENTS,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        params=params,
    )
    assert response.status_code == 200
    found: list[dict[str, object]] = response.json()["documents"]
    return found


def _source_of(server: RunningServer, document_id: object) -> object:
    (document,) = [found for found in _documents(server) if found["id"] == document_id]
    return document["source"]


async def test_원천_a와_b에_같은_키의_파일을_넣으면_서로_다른_문서_둘로_남는다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    _create_source(server, "a")
    _create_source(server, "b")
    content = docx_bytes(*휴가)

    first = await round_trip.ingest_bytes(content, "규정.docx", {"key": "k", "source": "a"})
    second = await round_trip.ingest_bytes(content, "규정.docx", {"key": "k", "source": "b"})

    assert (first.status_code, first.json()["action"]) == (202, "created")
    assert (second.status_code, second.json()["action"]) == (202, "created")
    first_id, second_id = first.json()["document_id"], second.json()["document_id"]
    assert first_id != second_id
    assert [found["id"] for found in _documents(server, source="a")] == [first_id]
    assert [found["id"] for found in _documents(server, source="b")] == [second_id]
    assert {found["source"] for found in _documents(server, key="k")} == {"a", "b"}


async def test_같은_원천에_같은_키를_다시_넣으면_원천_안에서는_같은_문서다(
    round_trip: RoundTrip,
) -> None:
    _create_source(round_trip.server, "a")
    content = docx_bytes(*휴가)
    first = await round_trip.ingest_bytes(content, "규정.docx", {"key": "k", "source": "a"})

    again = await round_trip.ingest_bytes(content, "규정.docx", {"key": "k", "source": "a"})

    assert again.json()["action"] == "unchanged"
    assert again.json()["document_id"] == first.json()["document_id"]


async def test_source를_적지_않으면_default로_upload를_적으면_upload로_들어간다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server

    plain = (await round_trip.ingest(*휴가, fields={"key": "plain"})).json()
    explicit = (await round_trip.ingest(*휴가, fields={"key": "up", "source": "upload"})).json()

    assert _source_of(server, plain["document_id"]) == "default"
    assert _source_of(server, explicit["document_id"]) == "upload"


async def test_없는_원천의_이름을_적으면_404_source_not_found이고_문서도_작업도_만들지_않는다(
    round_trip: RoundTrip,
) -> None:
    response = await round_trip.ingest(*휴가, fields={"source": "nothing"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "source_not_found"
    assert _documents(round_trip.server) == []
    with psycopg.connect(round_trip.server.settings.database_url) as connection:
        assert connection.execute("SELECT count(*) FROM jobs").fetchone() == (0,)


async def test_원천에_넣은_문서는_작업자를_한_번_돌린_뒤_검색에_나오고_원천_이름이_실린다(
    round_trip: RoundTrip,
) -> None:
    _create_source(round_trip.server, "groupware")
    await round_trip.ingest(*휴가, fields={"key": "휴가.docx", "source": "groupware"})

    await round_trip.work()

    (found,) = output(await round_trip.search("연차휴가")).results
    assert (found.source, found.key) == ("groupware", "휴가.docx")


@pytest.mark.parametrize("name", ["Groupware", "a" * 64, "-wiki", "wiki system"])
async def test_규칙에_어긋나는_이름을_수집_API의_source에_적으면_422다(
    round_trip: RoundTrip, name: str
) -> None:
    response = await round_trip.ingest(*휴가, fields={"source": name})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert [issue["loc"][-1] for issue in body["errors"]] == ["source"]
    assert _documents(round_trip.server) == []


@pytest.mark.parametrize("name", ["", "Groupware", "a" * 64, "-wiki", "wiki system"])
async def test_규칙에_어긋나는_이름을_지우기_요청의_source에_적으면_422다(
    round_trip: RoundTrip, name: str
) -> None:
    async with httpx.AsyncClient() as http:
        response = await http.delete(
            round_trip.server.base_url + "/api/v1/ingest/documents",
            headers=round_trip.auth(),
            params={"key": "k", "source": name},
        )

    assert response.status_code == 422
    assert [issue["loc"][-1] for issue in response.json()["errors"]] == ["source"]


async def test_지우기_요청은_source로_그_원천의_문서만_지운다(round_trip: RoundTrip) -> None:
    server = round_trip.server
    _create_source(server, "a")
    _create_source(server, "b")
    content = docx_bytes(*휴가)
    in_a = (await round_trip.ingest_bytes(content, "k.docx", {"key": "k", "source": "a"})).json()
    in_b = (await round_trip.ingest_bytes(content, "k.docx", {"key": "k", "source": "b"})).json()
    in_default = (await round_trip.ingest_bytes(content, "k.docx", {"key": "k"})).json()
    await round_trip.work()

    response = await round_trip.delete("k", source="a")

    assert response.status_code == 204
    status_of = {found["id"]: found["status"] for found in _documents(server, key="k")}
    assert status_of[in_a["document_id"]] == "deleted"
    assert status_of[in_b["document_id"]] == "parsed"
    assert status_of[in_default["document_id"]] == "parsed"
    assert {found.source for found in output(await round_trip.search("연차휴가")).results} == {
        "b",
        "default",
    }


async def test_지우기_요청이_source를_적지_않으면_default의_문서를_지운다(
    round_trip: RoundTrip,
) -> None:
    _create_source(round_trip.server, "a")
    content = docx_bytes(*휴가)
    in_a = (await round_trip.ingest_bytes(content, "k.docx", {"key": "k", "source": "a"})).json()
    in_default = (await round_trip.ingest_bytes(content, "k.docx", {"key": "k"})).json()

    response = await round_trip.delete("k")

    assert response.status_code == 204
    status_of = {found["id"]: found["status"] for found in _documents(round_trip.server, key="k")}
    assert status_of[in_default["document_id"]] == "deleted"
    assert status_of[in_a["document_id"]] == "received"


async def test_지우기_요청에_없는_원천을_적으면_404_source_not_found다(
    round_trip: RoundTrip,
) -> None:
    response = await round_trip.delete("k", source="nothing")

    assert response.status_code == 404
    assert response.json()["code"] == "source_not_found"


async def test_지우기_요청의_원천에_그_키의_문서가_없으면_404_document_not_found다(
    round_trip: RoundTrip,
) -> None:
    _create_source(round_trip.server, "a")
    await round_trip.ingest(*휴가, fields={"key": "k"})

    response = await round_trip.delete("k", source="a")

    assert response.status_code == 404
    assert response.json()["code"] == "document_not_found"


async def test_문서_목록의_source는_원천_이름으로_거르고_없는_원천은_빈_목록이다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    await round_trip.ingest(*휴가, fields={"key": "k"})

    assert [found["source"] for found in _documents(server, source="default")] == ["default"]
    assert _documents(server, source="upload") == []
    assert _documents(server, source="nothing") == []


async def test_key만_적으면_모든_원천에서_그_키의_문서를_찾는다(round_trip: RoundTrip) -> None:
    server = round_trip.server
    _create_source(server, "a")
    await round_trip.ingest(*휴가, fields={"key": "k"})
    await round_trip.ingest(*휴가, fields={"key": "k", "source": "a"})
    await round_trip.ingest(*휴가, fields={"key": "other", "source": "a"})

    found = _documents(server, key="k")

    assert sorted(str(document["source"]) for document in found) == ["a", "default"]


async def test_원천_보기의_문서_수는_지워지지_않은_문서를_상태별로_센다(
    round_trip: RoundTrip,
) -> None:
    server = round_trip.server
    _create_source(server, "a")
    for key in ("one", "two", "three"):
        await round_trip.ingest(*휴가, fields={"key": key, "source": "a"})
    await round_trip.work()
    await round_trip.delete("three", source="a")
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute("UPDATE documents SET status = 'failed' WHERE key = 'two'")

    response = httpx.get(
        server.base_url + f"{SOURCES}/a", headers={"Authorization": f"Bearer {server.admin_token}"}
    )

    assert response.json()["documents"] == {"total": 2, "failed": 1, "skipped": 0}
