"""수집의 갱신 갈래(티켓 10): 그룹 변경, `requeued`, 원본 정리를 HTTP 표면으로 본다(스토리 2, 8).

서버는 실제 uvicorn이고 검색과 문서 조회는 공식 MCP SDK의 클라이언트로 `/mcp`에 접속해 부른다.
작업자는 같은 설정으로 한 번 돈다. 임베딩 서버만 스텁이다. 둘째 그룹과 지식베이스는 `Catalog`
어댑터로 만든다(만드는 관리 API는 admin이 받는다).
"""

from pathlib import Path
from typing import LiteralString
from uuid import UUID

import psycopg
from tests.harness import RunningServer
from tests.support.docx_files import docx_bytes
from tests.support.pdf_files import PdfPage, pdf_bytes, text_block
from tests.support.round_trip import RoundTrip, document_output, output

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")


def _query(
    server: RunningServer, statement: LiteralString, *params: object
) -> list[tuple[object, ...]]:
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        return connection.execute(statement, list(params)).fetchall()


def _execute(server: RunningServer, statement: LiteralString) -> None:
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        connection.execute(statement)


def _document_row(server: RunningServer, document_id: str) -> tuple[str, str | None, int]:
    ((status, error_code, generation),) = _query(
        server,
        "SELECT status, error_code, generation FROM documents WHERE id = %s",
        UUID(document_id),
    )
    assert isinstance(status, str) and isinstance(generation, int)
    assert error_code is None or isinstance(error_code, str)
    return status, error_code, generation


def _blobs(server: RunningServer, document_id: str) -> list[Path]:
    root = server.settings.data_dir / "blobs" / document_id
    return sorted(path for path in root.rglob("*") if path.is_file())


def _fail_index(server: RunningServer) -> None:
    """앞선 색인이 실패한 모양을 만든다. 색인 상태가 `failed`이고 조각이 없다."""
    _execute(
        server,
        "UPDATE document_index_states SET status = 'failed', chunk_count = 0,"
        " built_content_hash = NULL, error_code = 'embedding_unavailable'",
    )
    _execute(server, "DELETE FROM chunks")


async def test_그룹을_바꿔_넣으면_옛_지식베이스에서_바로_빠지고_새_지식베이스는_작업_뒤에_찾는다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.add_group_with_knowledge_base("팀B", "b")
    data = docx_bytes(*휴가)
    first = await round_trip.ingest_bytes(data)
    await round_trip.work()
    assert [item.key for item in output(await round_trip.search("연차휴가")).results] == [
        "규정.docx"
    ]

    moved = await round_trip.ingest_bytes(data, fields={"group": "팀B"})

    assert moved.status_code == 202
    body = moved.json()
    assert (body["action"], body["document_id"]) == ("updated", first.json()["document_id"])
    assert body["job_id"] is not None
    assert output(await round_trip.search("연차휴가")).results == []
    assert output(await round_trip.search("연차휴가", knowledge_base="b")).results == []
    assert await round_trip.work() == 1
    found = output(await round_trip.search("연차휴가", knowledge_base="b"))
    assert [item.key for item in found.results] == ["규정.docx"]
    assert output(await round_trip.search("연차휴가")).results == []


async def test_내용과_그룹을_바꾼_직후_파싱_전의_get_document는_본문을_모두_null로_낸다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.add_group_with_knowledge_base("팀B", "b")
    first = await round_trip.ingest(*휴가)
    document_id = first.json()["document_id"]
    await round_trip.work()
    parsed = document_output(await round_trip.get_document(document_id, include_text=True))
    assert parsed.text is not None and "연차휴가" in parsed.text

    await round_trip.ingest(*출장, fields={"group": "팀B"})

    pending = document_output(await round_trip.get_document(document_id, include_text=True))
    assert (pending.text_length, pending.text, pending.next_offset) == (None, None, None)
    await round_trip.work()
    parsed_again = document_output(await round_trip.get_document(document_id, include_text=True))
    assert parsed_again.text is not None and "출장비" in parsed_again.text


async def test_파싱이_영구_실패한_문서를_같은_내용으로_다시_넣으면_requeued로_작업을_다시_넣는다(
    round_trip: RoundTrip,
) -> None:
    encrypted = pdf_bytes([PdfPage(text_block("제1조 휴가"))], user_password="secret")
    first = await round_trip.ingest_bytes(encrypted, "규정.pdf")
    document_id = first.json()["document_id"]
    assert await round_trip.work() == 1
    failed = _document_row(round_trip.server, document_id)
    assert failed[:2] == ("failed", "encrypted_document")

    again = await round_trip.ingest_bytes(encrypted, "규정.pdf")

    assert again.status_code == 202
    body = again.json()
    assert (body["action"], body["document_id"]) == ("requeued", document_id)
    assert body["job_id"] not in (None, first.json()["job_id"])
    assert _document_row(round_trip.server, document_id)[2] > failed[2]
    assert await round_trip.work() == 1
    assert _document_row(round_trip.server, document_id)[:2] == ("failed", "encrypted_document")


async def test_색인이_실패한_문서를_같은_내용으로_다시_넣으면_requeued로_다시_색인되어_검색된다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    data = docx_bytes(*휴가)
    await round_trip.ingest_bytes(data)
    await round_trip.work()
    _fail_index(round_trip.server)
    assert output(await round_trip.search("연차휴가")).results == []

    again = await round_trip.ingest_bytes(data)
    await round_trip.work()

    assert again.status_code == 202 and again.json()["action"] == "requeued"
    found = output(await round_trip.search("연차휴가"))
    assert [item.key for item in found.results] == ["규정.docx"]
    ((state,),) = _query(round_trip.server, "SELECT status FROM document_index_states")
    assert state == "indexed"


async def test_색인이_실패하지_않은_문서를_같은_내용으로_다시_넣으면_200으로_건너뛴다(
    round_trip: RoundTrip,
) -> None:
    data = docx_bytes(*휴가)
    await round_trip.ingest_bytes(data)
    await round_trip.work()

    again = await round_trip.ingest_bytes(data)

    assert again.status_code == 200
    assert (again.json()["action"], again.json()["job_id"]) == ("unchanged", None)


async def test_requeued와_그룹만_바뀐_갱신_뒤에는_새_원본이_남지_않는다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.add_group_with_knowledge_base("팀B", "b")
    data = docx_bytes(*휴가)
    first = await round_trip.ingest_bytes(data)
    document_id = first.json()["document_id"]
    await round_trip.work()
    (original,) = _blobs(round_trip.server, document_id)
    _fail_index(round_trip.server)

    requeued = await round_trip.ingest_bytes(data)
    assert requeued.json()["action"] == "requeued"
    assert _blobs(round_trip.server, document_id) == [original]
    await round_trip.work()
    moved = await round_trip.ingest_bytes(data, fields={"group": "팀B"})

    assert moved.json()["action"] == "updated"
    assert _blobs(round_trip.server, document_id) == [original]
    ((blob_path,),) = _query(
        round_trip.server, "SELECT blob_path FROM documents WHERE id = %s", UUID(document_id)
    )
    assert blob_path == f"blobs/{document_id}/{original.name}"
