"""수집 API의 `source` 칸(source-sync 03, 스토리 2, 3, 4)을 HTTP 표면으로 본다.

수집 API는 원칙 VII가 든 계약이다. 이 칸을 더한 것은 칸을 더하는 변경이라 버전을 올리지 않았으므로,
이후 변경에서 이 칸이 조용히 사라지지 않게 한 장면씩 여기서 판정한다. 서버는 실제 uvicorn이고 검색은
공식 MCP SDK의 클라이언트로 `/mcp`에 접속해 부른다. 작업자는 같은 설정으로 한 번 돈다. 임베딩 서버만
스텁이다. 원천을 만드는 관리 API는 `admin` 토큰이 받는다.
"""

import httpx
from tests.harness import RunningServer
from tests.support.docx_files import docx_bytes
from tests.support.round_trip import RoundTrip, output

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")


def _create_push_source(server: RunningServer, name: str) -> None:
    response = httpx.post(
        server.base_url + "/api/v1/admin/sources",
        headers={"Authorization": f"Bearer {server.admin_token}"},
        json={"name": name, "kind": "push"},
    )
    assert response.status_code == 201


async def test_같은_키가_두_원천에_따로_남고_한_원천만_지우면_다른_원천은_검색에_남는다(
    round_trip: RoundTrip,
) -> None:
    _create_push_source(round_trip.server, "a")
    _create_push_source(round_trip.server, "b")
    content = docx_bytes(*휴가)
    first = await round_trip.ingest_bytes(content, "k.docx", {"key": "k", "source": "a"})
    second = await round_trip.ingest_bytes(content, "k.docx", {"key": "k", "source": "b"})
    assert first.json()["document_id"] != second.json()["document_id"]
    await round_trip.work()
    found = output(await round_trip.search("연차휴가")).results
    assert {item.source for item in found} == {"a", "b"}

    deleted = await round_trip.delete("k", source="a")

    assert deleted.status_code == 204
    left = output(await round_trip.search("연차휴가")).results
    assert {item.source for item in left} == {"b"}


async def test_없는_원천의_이름을_적으면_404_source_not_found로_거절한다(
    round_trip: RoundTrip,
) -> None:
    response = await round_trip.ingest(*휴가, fields={"source": "nothing"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "source_not_found"
