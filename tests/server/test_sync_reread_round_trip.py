"""수정 시각과 크기가 그대로인 채 내용만 바뀐 파일을 "모두 다시 읽기"로 따라잡는 왕복(source-sync
티켓 09, 명세 "Testing Decisions"의 주 이음매).

실제 uvicorn 서버, 실제 `server_path` 커넥터와 임시 폴더(`RAG_SOURCES_DIR`), 실제 작업자(한 번
돌기), 공식 MCP 클라이언트의 `search`를 쓴다. 임베딩 서버만 스텁이다. 변경 확인값이 수정 시각과
크기이므로, 같은 크기로 맞춘 새 내용을 쓰고 수정 시각을 되돌려 놓으면 보통 동기화는 바뀐 줄 모른다.
"""

import os
from pathlib import Path

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.pull_source_http import SOURCES, create_pull, request
from tests.support.round_trip import RoundTrip, output

FOLDER = "규정집"
KEY = "규정.docx"
# 새 내용을 같은 크기로 맞추려고 옛 내용이 더 크게 쓴다.
OLD_TEXT = "연차휴가는 입사 일 년 뒤에 생긴다. " * 3


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sources"
    (path / FOLDER).mkdir(parents=True)
    (path / FOLDER / KEY).write_bytes(docx_bytes("제1조 휴가", OLD_TEXT))
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


async def _sync_and_work(round_trip: RoundTrip, **options: object) -> dict[str, object]:
    """HTTP로 지금 동기화를 요청하고 작업자가 비울 때까지 돌린 뒤 그 기록을 HTTP로 읽는다."""
    accepted = request(round_trip.server, "POST", f"{SOURCES}/wiki/sync", **options)
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


async def _texts(round_trip: RoundTrip) -> str:
    """검색에 나온 조각 글을 모두 이은 것."""
    return " ".join(item.text for item in output(await round_trip.search("휴가")).results)


def _replace_keeping_marker(path: Path, data: bytes) -> None:
    """같은 크기로 맞춘 새 내용을 쓰고 수정 시각을 옛 값으로 되돌린다. 크기를 맞추는 덧붙임은 압축
    파일의 끝에 붙는 0바이트다(파서가 읽는 데 지장이 없다)."""
    before = path.stat()
    old = path.read_bytes()
    assert len(data) <= len(old), "새 내용이 옛 내용보다 크다. 옛 내용을 더 크게 쓴다"
    path.write_bytes(data + b"\x00" * (len(old) - len(data)))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size


async def test_모두_다시_읽기를_켜야_수정_시각과_크기가_그대로인_채_바뀐_내용을_따라잡는다(
    parent: Path, round_trip: RoundTrip
) -> None:
    assert create_pull(round_trip.server, "wiki", FOLDER).status_code == 201
    assert (await _sync_and_work(round_trip))["status"] == "succeeded"
    assert "연차휴가는 입사 일 년 뒤" in await _texts(round_trip)
    _replace_keeping_marker(parent / FOLDER / KEY, docx_bytes("제1조 휴가", "특별휴가가 생겼다."))

    plain = await _sync_and_work(round_trip)

    assert (plain["updated"], plain["unchanged"]) == (0, 1)
    assert "특별휴가" not in await _texts(round_trip)

    reread = await _sync_and_work(round_trip, reread=True)

    assert (reread["status"], reread["updated"], reread["unchanged"]) == ("succeeded", 1, 0)
    assert reread["options"] == {"reread": True}
    texts = await _texts(round_trip)
    assert "특별휴가" in texts
    assert "연차휴가는 입사 일 년 뒤" not in texts
