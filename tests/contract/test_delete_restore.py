"""삭제, 되살림, 묘비를 HTTP 표면으로 본다(티켓 11, 스토리 5, 6).

서버는 실제 uvicorn이고 검색과 문서 조회는 공식 MCP SDK의 클라이언트로 `/mcp`에 접속해 부른다.
작업자는 같은 설정으로 한 번 돈다. 임베딩 서버만 스텁이다. 판 전환을 사이에 둔 되살림은 14가 본다.
"""

from pathlib import Path
from typing import LiteralString
from uuid import UUID

import psycopg
from tests.harness import RunningServer
from tests.support.docx_files import docx_bytes
from tests.support.round_trip import (
    RoundTrip,
    error_body,
    knowledge_bases_output,
    output,
)

from rag_engine.server.tool_models import SearchResult

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")
EMBEDDINGS = "/v1/embeddings"


def _query(
    server: RunningServer, statement: LiteralString, *params: object
) -> list[tuple[object, ...]]:
    with psycopg.connect(server.settings.database_url, autocommit=True) as connection:
        return connection.execute(statement, list(params)).fetchall()


def _blobs(server: RunningServer, document_id: str) -> list[Path]:
    root = server.settings.data_dir / "blobs" / document_id
    return sorted(path for path in root.rglob("*") if path.is_file())


async def _found(
    round_trip: RoundTrip, query: str, knowledge_base: str | None
) -> list[SearchResult]:
    """지식베이스를 주지 않으면 기본 지식베이스에서 찾는다."""
    if knowledge_base is None:
        return output(await round_trip.search(query)).results
    return output(await round_trip.search(query, knowledge_base=knowledge_base)).results


async def _keys(
    round_trip: RoundTrip, query: str, *, knowledge_base: str | None = None
) -> list[str]:
    return [item.key for item in await _found(round_trip, query, knowledge_base)]


async def _texts(round_trip: RoundTrip, query: str, knowledge_base: str | None = None) -> list[str]:
    """찾은 조각의 글. 벡터 검색은 키워드가 맞지 않아도 가장 가까운 조각을 내므로, 옛 글이 안
    나온다는 것은 결과가 없다는 것이 아니라 옛 글이 든 조각이 없다는 것으로 본다."""
    return [item.text for item in await _found(round_trip, query, knowledge_base)]


async def _default_document_count(round_trip: RoundTrip) -> int:
    summaries = knowledge_bases_output(await round_trip.list_knowledge_bases()).knowledge_bases
    (default,) = (summary for summary in summaries if summary.name == "default")
    return default.document_count


async def test_삭제하면_그_커밋으로_검색에서_빠지고_문서_조회와_문서_수에서도_사라진다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    first = await round_trip.ingest(*휴가)
    document_id = first.json()["document_id"]
    await round_trip.work()
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]
    assert await _default_document_count(round_trip) == 1

    deleted = await round_trip.delete("규정.docx")

    assert (deleted.status_code, deleted.content) == (204, b"")
    assert await _keys(round_trip, "연차휴가") == []
    missing = error_body(await round_trip.get_document(document_id))
    assert missing["code"] == "document_not_found"
    assert await _default_document_count(round_trip) == 0
    ((deleted_at,),) = _query(
        round_trip.server, "SELECT deleted_at FROM documents WHERE id = %s", UUID(document_id)
    )
    assert deleted_at is not None


async def test_이미_지운_문서의_삭제는_204이고_없는_키의_삭제는_404_document_not_found다(
    round_trip: RoundTrip,
) -> None:
    await round_trip.ingest(*휴가)
    assert (await round_trip.delete("규정.docx")).status_code == 204

    again = await round_trip.delete("규정.docx")
    unknown = await round_trip.delete("없는.docx")

    assert again.status_code == 204
    assert unknown.status_code == 404
    assert unknown.headers["content-type"].startswith("application/problem+json")
    assert unknown.json()["code"] == "document_not_found"


async def test_reader_토큰의_삭제는_403이고_문서는_그대로다(round_trip: RoundTrip) -> None:
    await round_trip.ingest(*휴가)
    reader = await round_trip.issue_reader()

    forbidden = await round_trip.delete("규정.docx", token=reader)

    assert forbidden.status_code == 403
    ((deleted_at,),) = _query(round_trip.server, "SELECT deleted_at FROM documents")
    assert deleted_at is None


async def test_슬래시와_한글이_든_키를_URL_인코딩한_쿼리로_지운다(round_trip: RoundTrip) -> None:
    await round_trip.ingest(*휴가, fields={"key": "인사/규정 2026.docx"})

    deleted = await round_trip.delete("인사/규정 2026.docx")

    assert deleted.status_code == 204
    ((deleted_at,),) = _query(round_trip.server, "SELECT deleted_at FROM documents")
    assert deleted_at is not None


async def test_같은_내용으로_되살리면_작업_없이_바로_검색되고_새_원본이_남지_않는다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    data = docx_bytes(*휴가)
    first = await round_trip.ingest_bytes(data)
    document_id = first.json()["document_id"]
    await round_trip.work()
    await round_trip.delete("규정.docx")
    embeddings = round_trip.stub.count(EMBEDDINGS)

    restored = await round_trip.ingest_bytes(data)

    assert restored.status_code == 202
    body = restored.json()
    assert (body["action"], body["document_id"], body["job_id"]) == ("restored", document_id, None)
    assert round_trip.stub.count(EMBEDDINGS) == embeddings
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]
    assert await round_trip.work() == 0
    assert len(_blobs(round_trip.server, document_id)) == 1
    assert await _default_document_count(round_trip) == 1


async def test_다른_그룹으로_되살리면_새_그룹의_지식베이스에_작업_뒤에_검색된다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.add_group_with_knowledge_base("팀B", "b")
    data = docx_bytes(*휴가)
    first = await round_trip.ingest_bytes(data)
    await round_trip.work()
    await round_trip.delete("규정.docx")

    restored = await round_trip.ingest_bytes(data, fields={"group": "팀B"})

    body = restored.json()
    assert (body["action"], body["document_id"]) == ("restored", first.json()["document_id"])
    assert body["job_id"] is not None
    assert await _keys(round_trip, "연차휴가") == []
    assert await _keys(round_trip, "연차휴가", knowledge_base="b") == []
    assert await round_trip.work() == 1
    assert await _keys(round_trip, "연차휴가", knowledge_base="b") == ["규정.docx"]
    assert await _keys(round_trip, "연차휴가") == []


async def test_갱신한_내용이_색인되기_전에_지웠다_같은_내용으로_되살려도_옛_글은_나오지_않는다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.add_group_with_knowledge_base("팀B", "b")
    await round_trip.ingest(*휴가)
    await round_trip.work()
    new_data = docx_bytes(*출장)
    await round_trip.ingest_bytes(new_data, fields={"group": "팀B"})
    await round_trip.delete("규정.docx")

    restored = await round_trip.ingest_bytes(new_data, fields={"group": "팀B"})

    assert restored.json()["action"] == "restored" and restored.json()["job_id"] is not None
    for knowledge_base in ("default", "b"):
        assert await _keys(round_trip, "연차휴가", knowledge_base=knowledge_base) == []
        assert await _keys(round_trip, "출장비", knowledge_base=knowledge_base) == []
    assert await round_trip.work() == 1
    assert await _keys(round_trip, "출장비", knowledge_base="b") == ["규정.docx"]
    assert not any("연차휴가" in text for text in await _texts(round_trip, "연차휴가", "b"))
    assert await _keys(round_trip, "출장비") == []


async def test_다른_내용으로_되살리면_갱신한_내용이_색인되고_옛_원본이_남지_않는다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    first = await round_trip.ingest(*휴가)
    document_id = first.json()["document_id"]
    await round_trip.work()
    await round_trip.delete("규정.docx")

    restored = await round_trip.ingest(*출장)

    assert restored.json()["action"] == "restored" and restored.json()["job_id"] is not None
    assert await _keys(round_trip, "연차휴가") == []
    assert await round_trip.work() == 1
    assert await _keys(round_trip, "출장비") == ["규정.docx"]
    assert not any("연차휴가" in text for text in await _texts(round_trip, "연차휴가"))
    assert len(_blobs(round_trip.server, document_id)) == 1


async def test_묘비_행과_같은_키가_오면_그_행의_UUID를_이어_created로_다시_쓴다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    first = await round_trip.ingest(*휴가)
    document_id = first.json()["document_id"]
    await round_trip.work()
    await round_trip.delete("규정.docx")
    _query(round_trip.server, "DELETE FROM archived_chunks RETURNING 1")
    _query(round_trip.server, "DELETE FROM jobs RETURNING 1")
    _query(round_trip.server, "DELETE FROM document_contents RETURNING 1")
    _query(round_trip.server, "UPDATE documents SET purged_at = deleted_at RETURNING 1")

    created = await round_trip.ingest(*출장)

    assert created.status_code == 202
    body = created.json()
    assert (body["action"], body["document_id"]) == ("created", document_id)
    assert body["job_id"] is not None
    assert await round_trip.work() == 1
    assert await _keys(round_trip, "출장비") == ["규정.docx"]
    ((deleted_at, purged_at),) = _query(
        round_trip.server, "SELECT deleted_at, purged_at FROM documents"
    )
    assert (deleted_at, purged_at) == (None, None)
