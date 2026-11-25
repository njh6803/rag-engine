"""관리 API로 원천을 만들고 지금 동기화를 눌러 검색까지 닿는 왕복(source-sync 티켓 07, 명세 "Testing
Decisions"의 주 이음매).

실제 uvicorn 서버, 실제 `server_path` 커넥터와 임시 폴더(`RAG_SOURCES_DIR`), 실제 작업자(한 번
돌기), 공식 MCP 클라이언트의 `search`를 쓴다. 임베딩 서버만 스텁이다. 폴더에 PDF, DOCX, HWPX를 두면
세 문서가 검색에 나오고, 파일 하나를 고치면 두 번째 동기화가 그 하나만 고쳐 넣는다.
"""

from pathlib import Path

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.hwpx_files import HwpxHeading, HwpxParagraph, hwpx_bytes
from tests.support.pdf_files import PdfPage, pdf_bytes, text_block
from tests.support.pull_source_http import SOURCES, create_pull, request
from tests.support.round_trip import RoundTrip, output

FOLDER = "규정집"


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sources"
    folder = path / FOLDER
    (folder / "하위").mkdir(parents=True)
    (folder / "규정.pdf").write_bytes(
        pdf_bytes([PdfPage(text_block("제1조 휴가", "연차휴가는 있다."))])
    )
    (folder / "하위" / "지침.docx").write_bytes(
        docx_bytes("제2조 휴가", "휴가는 사흘 전에 신청한다.")
    )
    (folder / "안내.hwpx").write_bytes(
        hwpx_bytes(HwpxHeading("제3조 휴가", 1), HwpxParagraph("휴가 일수는 연 열다섯 날이다."))
    )
    (folder / ".숨김.docx").write_bytes(docx_bytes("숨김", "받지 않는다."))
    (folder / "메모.txt").write_text("글자 파일이다.", encoding="utf-8")
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


async def _sync_and_work(round_trip: RoundTrip) -> dict[str, object]:
    """HTTP로 지금 동기화를 요청하고 작업자가 비울 때까지 돌린 뒤 그 기록을 HTTP로 읽는다."""
    accepted = request(round_trip.server, "POST", f"{SOURCES}/wiki/sync")
    assert accepted.status_code == 202
    await round_trip.work()
    record = request(
        round_trip.server,
        "GET",
        f"{SOURCES}/wiki/sync-records/{accepted.json()['sync_record_id']}",
    )
    assert record.status_code == 200
    body: dict[str, object] = record.json()
    return body


async def _found(round_trip: RoundTrip) -> dict[str, str]:
    """검색에 나온 문서의 키마다 그 조각 글을 이은 글을 낸다."""
    results = output(await round_trip.search("휴가")).results
    assert {item.source for item in results} == {"wiki"}
    texts: dict[str, str] = {}
    for item in results:
        texts[item.key] = texts.get(item.key, "") + item.text
    return texts


async def test_폴더의_세_형식은_동기화_한_번으로_검색에_나오고_바뀐_파일만_다시_들어간다(
    parent: Path, round_trip: RoundTrip
) -> None:
    assert create_pull(round_trip.server, "wiki", FOLDER).status_code == 201

    first = await _sync_and_work(round_trip)

    assert first["status"] == "succeeded"
    assert (first["listed"], first["added"], first["updated"], first["unchanged"]) == (5, 3, 0, 0)
    assert first["not_accepted"] == {"excluded": 1, "unsupported_type": 1}
    assert set(await _found(round_trip)) == {"규정.pdf", "하위/지침.docx", "안내.hwpx"}

    (parent / FOLDER / "하위" / "지침.docx").write_bytes(
        docx_bytes("제2조 휴가 개정", "휴가는 이레 전에 신청한다. 고친 내용이다.")
    )
    second = await _sync_and_work(round_trip)

    assert second["status"] == "succeeded"
    assert (second["added"], second["updated"], second["unchanged"]) == (0, 1, 2)
    texts = await _found(round_trip)
    assert set(texts) == {"규정.pdf", "하위/지침.docx", "안내.hwpx"}
    assert "고친 내용" in texts["하위/지침.docx"]
    assert "사흘" not in texts["하위/지침.docx"]
