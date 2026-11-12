"""재색인과 판 전환을 HTTP 표면으로 본다(스토리 33, 티켓 14).

서버는 실제 uvicorn이고, 재색인은 관리 API로 시작하며, 검색은 공식 MCP SDK의 클라이언트로 `/mcp`에
접속해 부른다. 작업자는 같은 설정으로 한 번 돈다. 임베딩 서버만 스텁이다. 지식베이스 설정의 청킹
크기를 고쳐 "재색인 필요"를 만들고, 키워드 규칙 판 상수를 바꿔 토크나이저 판만 다른 재색인을 만든다.
"""

import httpx
import pytest
from tests.support.docx_files import docx_bytes
from tests.support.round_trip import RoundTrip, output

from rag_engine.adapters import index_elements
from rag_engine.server.admin_knowledge_base_models import KnowledgeBaseDetailResponse

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = ("제2조 출장", "출장비는 실비로 정산한다.")
복지 = ("제3조 복지", "복지 포인트는 매년 연초에 지급한다.")
EMBEDDINGS = "/v1/embeddings"
NEW_CHUNK_TOKENS = 64


async def _keys(round_trip: RoundTrip, query: str, knowledge_base: str | None = None) -> list[str]:
    """찾은 조각 가운데 글에 질의어가 든 것의 문서 키(중복 없이). 벡터 검색은 키워드가 맞지 않아도
    가장 가까운 조각을 내므로, 문서가 찾힌다는 것은 질의어가 든 조각이 있다는 것으로 본다."""
    if knowledge_base is None:
        found = output(await round_trip.search(query))
    else:
        found = output(await round_trip.search(query, knowledge_base=knowledge_base))
    return list(dict.fromkeys(item.key for item in found.results if query in item.text))


async def _top_text(round_trip: RoundTrip, query: str) -> str:
    return output(await round_trip.search(query)).results[0].text


def _detail(round_trip: RoundTrip, name: str = "default") -> KnowledgeBaseDetailResponse:
    response = httpx.get(
        round_trip.server.base_url + f"/api/v1/admin/knowledge-bases/{name}",
        headers=round_trip.auth(),
    )
    assert response.status_code == 200
    return KnowledgeBaseDetailResponse.model_validate(response.json())


async def test_전환_전에는_옛_판으로_찾고_전환_뒤에는_새_판으로_찾는다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    paragraphs = [f"{n}번째 규정은 연차휴가의 신청 절차와 승인 기준이다." for n in range(40)]
    await round_trip.ingest("제1조 휴가", *paragraphs)
    await round_trip.work()
    before = await _top_text(round_trip, "연차휴가")
    round_trip.change_settings(NEW_CHUNK_TOKENS)

    started = await round_trip.reindex()

    assert started.status_code == 202
    assert _detail(round_trip).building is not None
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]
    assert await _top_text(round_trip, "연차휴가") == before
    await round_trip.work()
    detail = _detail(round_trip)
    assert (detail.building, detail.reindex_needed) == (None, False)
    assert detail.current_index_version is not None
    assert str(detail.current_index_version.id) == started.json()["index_version_id"]
    assert detail.current_index_version.chunking.max_tokens == NEW_CHUNK_TOKENS
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]
    assert len(await _top_text(round_trip, "연차휴가")) < len(before)


async def test_재색인_중_지운_문서는_전환을_막지_않는다(round_trip: RoundTrip) -> None:
    round_trip.drop_reranker()
    await round_trip.ingest(*휴가)
    await round_trip.ingest(*출장, filename="출장.docx")
    await round_trip.work()
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    assert (await round_trip.reindex()).status_code == 202

    assert (await round_trip.delete("출장.docx")).status_code == 204
    await round_trip.work()

    detail = _detail(round_trip)
    assert (detail.building, detail.document_count) == (None, 1)
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]
    assert await _keys(round_trip, "출장비") == []


async def test_재색인_중_그룹을_바꿔_빠진_문서는_전환을_막지_않는다(round_trip: RoundTrip) -> None:
    round_trip.drop_reranker()
    await round_trip.add_group_with_knowledge_base("팀B", "b")
    data = docx_bytes(*휴가)
    await round_trip.ingest_bytes(data)
    await round_trip.work()
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    assert (await round_trip.reindex()).status_code == 202
    assert _detail(round_trip).building is not None

    moved = await round_trip.ingest_bytes(data, fields={"group": "팀B"})

    assert moved.status_code == 202
    # 문서가 빠져 pending이 사라진 순간 같은 작업 단위에서 판이 전환됐다. 작업을 돌리기 전이다.
    detail = _detail(round_trip)
    assert (detail.building, detail.reindex_needed) == (None, False)
    assert await _keys(round_trip, "연차휴가") == []
    await round_trip.work()
    assert await _keys(round_trip, "연차휴가", "b") == ["규정.docx"]


async def test_재색인_중_그_지식베이스에_든_새_문서는_전환을_막지_않고_새_현재_판에_든다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.ingest(*휴가)
    await round_trip.work()
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    assert (await round_trip.reindex()).status_code == 202

    await round_trip.ingest(*복지, filename="복지.docx")
    await round_trip.work()

    assert _detail(round_trip).building is None
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]
    assert await _keys(round_trip, "복지") == ["복지.docx"]


async def test_재색인_중_되돌릴_조각_없이_되살린_문서는_전환을_막지_않고_새_현재_판에_든다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    await round_trip.ingest(*휴가)
    await round_trip.work()
    data = docx_bytes(*출장)
    await round_trip.ingest_bytes(data, "출장.docx")
    assert (await round_trip.delete("출장.docx")).status_code == 204
    await round_trip.work()
    round_trip.change_settings(NEW_CHUNK_TOKENS)
    assert (await round_trip.reindex()).status_code == 202

    restored = await round_trip.ingest_bytes(data, "출장.docx")

    assert restored.json()["action"] == "restored"
    await round_trip.work()
    assert _detail(round_trip).building is None
    assert await _keys(round_trip, "출장비") == ["출장.docx"]


async def test_판_전환을_사이에_둔_되살림은_작업_뒤_새_현재_판에서_찾는다(
    round_trip: RoundTrip,
) -> None:
    round_trip.drop_reranker()
    data = docx_bytes(*휴가)
    await round_trip.ingest_bytes(data)
    await round_trip.work()
    assert (await round_trip.delete("규정.docx")).status_code == 204
    round_trip.change_settings(NEW_CHUNK_TOKENS)

    started = await round_trip.reindex()

    # 살아 있는 문서가 없어 새 판은 시작하자마자 현재 판이 됐다. 지운 문서의 보관 조각은 옛 판에
    # 있다.
    assert (started.status_code, started.json()["jobs_enqueued"]) == (202, 0)
    assert _detail(round_trip).building is None
    restored = await round_trip.ingest_bytes(data)
    assert restored.json()["action"] == "restored"
    await round_trip.work()
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]


async def test_토크나이저_판만_바뀐_재색인은_조각의_임베딩을_다시_부르지_않는다(
    round_trip: RoundTrip, monkeypatch: pytest.MonkeyPatch
) -> None:
    round_trip.drop_reranker()
    await round_trip.ingest(*휴가)
    await round_trip.work()
    embedded_before = round_trip.stub.count(EMBEDDINGS)
    monkeypatch.setattr(index_elements, "KEYWORD_RULES_VERSION", "2")
    round_trip.point_knowledge_bases_at_stub()
    assert _detail(round_trip).reindex_needed is True

    assert (await round_trip.reindex()).status_code == 202
    await round_trip.work()

    detail = _detail(round_trip)
    assert (detail.building, detail.reindex_needed) == (None, False)
    # 작업은 살아 있는 판마다 재료를 만들므로 현재 판은 평소대로 임베딩을 한 번 부른다. 복사하는
    # 건설 중인 판은 부르지 않는다.
    assert round_trip.stub.count(EMBEDDINGS) == embedded_before + 1
    assert await _keys(round_trip, "연차휴가") == ["규정.docx"]


async def test_토크나이저_판만_바뀐_재색인_중_바뀐_문서는_옛_조각을_복사하지_않는다(
    round_trip: RoundTrip, monkeypatch: pytest.MonkeyPatch
) -> None:
    round_trip.drop_reranker()
    await round_trip.ingest(*휴가)
    await round_trip.work()
    monkeypatch.setattr(index_elements, "KEYWORD_RULES_VERSION", "2")
    round_trip.point_knowledge_bases_at_stub()
    assert (await round_trip.reindex()).status_code == 202

    await round_trip.ingest(*출장)
    await round_trip.work()

    assert _detail(round_trip).building is None
    assert await _keys(round_trip, "출장비") == ["규정.docx"]
    found = output(await round_trip.search("연차휴가")).results
    assert all("연차휴가" not in item.text for item in found)
