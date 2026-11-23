"""지운 파일과 빈 폴더를 관리 API와 검색으로 보는 왕복(source-sync 티켓 08, 명세 "Testing
Decisions"의 주 이음매).

실제 uvicorn 서버, 실제 `server_path` 커넥터와 임시 폴더(`RAG_SOURCES_DIR`), 실제 작업자(한 번
돌기), 공식 MCP 클라이언트의 `search`를 쓴다. 임베딩 서버만 스텁이다. 파일을 지운 뒤 동기화하면 그
문서가 검색에서 빠지고, 폴더가 비었거나 없거나 문서가 될 파일이 하나도 없으면 아무것도 지우지 않고
실패하며, "빈 목록도 반영"을 켜야 지운다.
"""

import shutil
from pathlib import Path

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.pull_source_http import SOURCES, create_pull, request
from tests.support.round_trip import RoundTrip, output

FOLDER = "규정집"


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "sources"
    folder = path / FOLDER
    (folder / "초안").mkdir(parents=True)
    (folder / "규정.docx").write_bytes(docx_bytes("제1조 휴가", "연차휴가는 있다."))
    (folder / "지침.docx").write_bytes(docx_bytes("제2조 휴가", "휴가는 사흘 전에 신청한다."))
    (folder / "초안" / "메모.docx").write_bytes(docx_bytes("제3조 휴가", "휴가 초안 메모다."))
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


async def _found(round_trip: RoundTrip) -> set[str]:
    """검색에 나온 문서의 키."""
    results = output(await round_trip.search("휴가")).results
    return {item.key for item in results}


@pytest.fixture
async def synced(parent: Path, round_trip: RoundTrip) -> RoundTrip:
    """세 문서를 동기화해 검색에 올려 둔다. `parent`가 만든 폴더를 쓰므로 인자로 받아 둔다."""
    assert parent.is_dir()
    assert create_pull(round_trip.server, "wiki", FOLDER).status_code == 201
    first = await _sync_and_work(round_trip)
    assert first["status"] == "succeeded"
    assert await _found(round_trip) == {"규정.docx", "지침.docx", "초안/메모.docx"}
    return round_trip


async def test_폴더에서_지운_파일의_문서는_다음_동기화_뒤_검색에서_빠진다(
    parent: Path, synced: RoundTrip
) -> None:
    (parent / FOLDER / "규정.docx").unlink()

    record = await _sync_and_work(synced)

    assert record["status"] == "succeeded"
    assert (record["listed"], record["deleted"], record["unchanged"]) == (2, 1, 2)
    assert await _found(synced) == {"지침.docx", "초안/메모.docx"}


async def test_제외_패턴을_더하면_그_패턴에_맞는_문서가_검색에서_빠진다(synced: RoundTrip) -> None:
    patched = request(synced.server, "PATCH", f"{SOURCES}/wiki", exclude_patterns=["초안"])
    assert patched.status_code == 200

    record = await _sync_and_work(synced)

    assert record["status"] == "succeeded"
    assert (record["deleted"], record["not_accepted"]) == (1, {"excluded": 1})
    assert await _found(synced) == {"규정.docx", "지침.docx"}


async def test_폴더를_비우면_실패하고_문서는_검색에_그대로며_옵션을_켜면_빠진다(
    parent: Path, synced: RoundTrip
) -> None:
    shutil.rmtree(parent / FOLDER)
    (parent / FOLDER).mkdir()

    failed = await _sync_and_work(synced)

    assert (failed["status"], failed["failure_code"]) == ("failed", "source_unreadable")
    assert (failed["listed"], failed["deleted"]) == (0, 0)
    assert await _found(synced) == {"규정.docx", "지침.docx", "초안/메모.docx"}

    forced = await _sync_and_work(synced, apply_empty=True)

    assert forced["status"] == "succeeded"
    assert forced["deleted"] == 3
    assert forced["options"] == {"apply_empty": True}
    assert await _found(synced) == set()


async def test_폴더가_없으면_옵션을_켜도_실패하고_문서는_검색에_그대로다(
    parent: Path, synced: RoundTrip
) -> None:
    shutil.rmtree(parent / FOLDER)

    plain = await _sync_and_work(synced)
    forced = await _sync_and_work(synced, apply_empty=True)

    for record in (plain, forced):
        assert (record["status"], record["failure_code"]) == ("failed", "source_unreadable")
        assert record["listed"] is None
    assert await _found(synced) == {"규정.docx", "지침.docx", "초안/메모.docx"}


async def test_문서_파일을_모두_치우고_걸릴_파일만_두면_nothing_accepted로_실패한다(
    parent: Path, synced: RoundTrip
) -> None:
    folder = parent / FOLDER
    for key in ("규정.docx", "지침.docx", "초안/메모.docx"):
        (folder / key).unlink()
    (folder / ".숨김.docx").write_bytes(docx_bytes("숨김", "받지 않는다."))
    (folder / "메모.txt").write_text("글자 파일이다.", encoding="utf-8")

    failed = await _sync_and_work(synced)

    assert (failed["status"], failed["failure_code"]) == ("failed", "nothing_accepted")
    assert (failed["listed"], failed["deleted"]) == (2, 0)
    assert failed["not_accepted"] == {"excluded": 1, "unsupported_type": 1}
    assert await _found(synced) == {"규정.docx", "지침.docx", "초안/메모.docx"}

    forced = await _sync_and_work(synced, apply_empty=True)
    later = await _sync_and_work(synced)

    assert (forced["status"], forced["deleted"]) == ("succeeded", 3)
    assert await _found(synced) == set()
    assert later["status"] == "succeeded"
