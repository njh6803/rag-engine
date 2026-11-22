"""건너뜀이 HTTP 표면에서 보이는 모양(명세 "건너뜀", "수집 API", "관리 API", source-sync 티켓 02).

실제 uvicorn 서버와 실제 작업자(한 번 돌기)를 쓰고 임베딩 서버만 스텁이다. 암호가 걸린 PDF와 글자가
없는 PDF를 수집 API로 넣고, 관리 API의 문서 목록과 작업 조회, 검색(MCP)으로 밖에서 보이는 것을
판정한다.
"""

import httpx
from tests.harness import RunningServer
from tests.support.pdf_files import PdfPage, blank_pages_pdf, pdf_bytes, text_block
from tests.support.round_trip import RoundTrip, output

JOBS = "/api/v1/admin/jobs"
DOCUMENTS = "/api/v1/admin/documents"
암호_PDF = pdf_bytes([PdfPage(text_block("제1조 휴가"))], user_password="secret")
스캔본_PDF = blank_pages_pdf(1)
휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")


def _get(server: RunningServer, path: str, **params: object) -> httpx.Response:
    return httpx.get(
        server.base_url + path,
        headers={"Authorization": f"Bearer {server.admin_token}"},
        params={name: str(value) for name, value in params.items()},
    )


def _listed(server: RunningServer, status: str) -> dict[str, str | None]:
    """상태로 거른 문서 목록을 키에서 건너뜀 사유로 가는 표로 낸다."""
    response = _get(server, DOCUMENTS, status=status)
    assert response.status_code == 200
    return {item["key"]: item["skip_reason"] for item in response.json()["documents"]}


async def test_암호_PDF와_글자_없는_PDF는_실패가_아니라_건너뜀으로_목록에_나온다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.ingest_bytes(암호_PDF, "암호.pdf")
    await round_trip.ingest_bytes(스캔본_PDF, "스캔.pdf")

    assert await round_trip.work() == 2

    assert _listed(round_trip.server, "skipped") == {"암호.pdf": "encrypted", "스캔.pdf": "no_text"}
    assert _listed(round_trip.server, "failed") == {}
    assert _listed(round_trip.server, "parsed") == {}


async def test_건너뛴_문서의_작업은_succeeded이고_색인_상태는_조각_없는_indexed다(
    round_trip: RoundTrip,
) -> None:
    ingested = (await round_trip.ingest_bytes(암호_PDF, "암호.pdf")).json()
    await round_trip.work()

    body = _get(round_trip.server, f"{JOBS}/{ingested['job_id']}").json()

    assert (body["job"]["status"], body["job"]["last_error_code"]) == ("succeeded", None)
    document = body["document"]
    assert (document["status"], document["skip_reason"], document["error_code"]) == (
        "skipped",
        "encrypted",
        None,
    )
    (index,) = document["indexes"]
    assert (index["status"], index["chunk_count"], index["error_code"]) == ("indexed", 0, None)


async def test_건너뛰지_않은_문서의_응답은_skip_reason이_null이다(round_trip: RoundTrip) -> None:
    ingested = (await round_trip.ingest(*휴가)).json()
    await round_trip.work()

    document = _get(round_trip.server, f"{DOCUMENTS}/{ingested['document_id']}").json()

    assert (document["status"], document["skip_reason"]) == ("parsed", None)


async def test_건너뜀_문서와_같은_내용을_다시_보내면_200_unchanged이고_작업이_들어가지_않는다(
    round_trip: RoundTrip,
) -> None:
    first = await round_trip.ingest_bytes(암호_PDF, "암호.pdf")
    await round_trip.work()

    again = await round_trip.ingest_bytes(암호_PDF, "암호.pdf")

    assert again.status_code == 200
    body = again.json()
    assert (body["action"], body["document_id"], body["job_id"]) == (
        "unchanged",
        first.json()["document_id"],
        None,
    )
    assert await round_trip.work() == 0
    assert _listed(round_trip.server, "skipped") == {"암호.pdf": "encrypted"}


async def test_글이_검색되던_문서를_같은_키의_암호_PDF로_바꾸면_옛_글이_검색에_나오지_않는다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.ingest(*휴가, fields={"key": "규정"})
    await round_trip.work()
    assert [item.key for item in output(await round_trip.search("연차휴가")).results] == ["규정"]

    replaced = await round_trip.ingest_bytes(암호_PDF, "규정.pdf", fields={"key": "규정"})
    await round_trip.work()

    assert replaced.json()["action"] == "updated"
    assert _listed(round_trip.server, "skipped") == {"규정": "encrypted"}
    assert output(await round_trip.search("연차휴가")).results == []


async def test_건너뜀_문서에_글이_있는_내용을_보내면_건너뜀에서_빠져_검색된다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.ingest_bytes(암호_PDF, "규정.pdf", fields={"key": "규정"})
    await round_trip.work()
    assert _listed(round_trip.server, "skipped") == {"규정": "encrypted"}

    fixed = await round_trip.ingest(*휴가, fields={"key": "규정"})
    await round_trip.work()

    assert fixed.json()["action"] == "updated"
    assert _listed(round_trip.server, "skipped") == {}
    assert _listed(round_trip.server, "parsed") == {"규정": None}
    assert [item.key for item in output(await round_trip.search("연차휴가")).results] == ["규정"]
