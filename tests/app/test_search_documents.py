"""`search_documents` 유스케이스의 판 전환 대응과 임베딩 실패(명세 "검색 흐름", 티켓 07).

실제 테스트 PostgreSQL과 실제 청커·Kiwi 위에서 돈다. 질의를 임베딩하는 순간에 현재 판이 바뀌거나
임베딩 서버가 죽는 상황은 임베더를 바꿔 끼워 만든다.
"""

import asyncio
import threading
from collections.abc import Awaitable, Callable, Sequence

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import LEASE_SECONDS, Pipeline

from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.app.search import SearchDeps, SearchRequest, SearchResults, search_documents
from rag_engine.domain.entities import IndexVersion
from rag_engine.domain.errors import ErrorCode, RagEngineError, TransientFailure
from rag_engine.domain.ports import Embedder, KeywordTokenizer
from rag_engine.worker.processing import run_once

# 한 쪽이 다른 쪽을 기다리다 이 시간을 넘기면 둘이 함께 진행하지 않는 것이다.
_WAIT_SECONDS = 5

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")


class _HookedEmbedder:
    """질의를 임베딩할 때마다 호출 횟수를 세고, 정해진 일을 하거나 실패한다."""

    def __init__(
        self,
        inner: Embedder,
        on_call: Callable[[int], Awaitable[None]] | None = None,
        failure: Exception | None = None,
    ) -> None:
        self._inner = inner
        self._on_call = on_call
        self._failure = failure
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        self.calls += 1
        if self._failure is not None:
            raise self._failure
        if self._on_call is not None:
            await self._on_call(self.calls)
        return await self._inner.embed(texts)

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        return await self._inner.count_tokens(texts)

    async def special_token_count(self) -> int:
        return await self._inner.special_token_count()

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        return await self._inner.token_spans(text)


async def _search(
    pipeline: Pipeline, embedder: Embedder, tokenize: KeywordTokenizer = tokenize_keywords
) -> SearchResults:
    deps = SearchDeps(
        unit_of_work=pipeline.unit_of_work,
        embedder_for=lambda _version: embedder,
        tokenize_keywords=tokenize,
        candidates=20,
    )
    request = SearchRequest(
        query="연차휴가", top_k=5, knowledge_base=None, allowed_knowledge_base_ids=()
    )
    return await search_documents(deps, request)


async def _switch_to(pipeline: Pipeline, version: IndexVersion) -> None:
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.switch_current_version(pipeline.knowledge_base.id, version.id)


async def _index_everything(pipeline: Pipeline) -> None:
    await pipeline.ingest(휴가)
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)


async def test_질의를_임베딩하는_사이_현재_판이_바뀌면_한_번_다시_해_새_판의_결과를_낸다(
    pipeline: Pipeline,
) -> None:
    building = await pipeline.add_building_version()
    await _index_everything(pipeline)

    async def switch(call: int) -> None:
        if call == 1:
            await _switch_to(pipeline, building)

    embedder = _HookedEmbedder(pipeline.pool(pipeline.version), on_call=switch)

    found = await _search(pipeline, embedder)

    assert [embedder.calls] == [2]
    assert [hit.text for hit in found.hits] == await pipeline.chunk_texts(
        found.hits[0].document_id, building
    )


async def test_다시_해도_판이_바뀌면_검색을_쓸_수_없다고_알린다(pipeline: Pipeline) -> None:
    second = await pipeline.add_building_version()
    third = await pipeline.add_building_version()
    await _index_everything(pipeline)

    async def switch(call: int) -> None:
        await _switch_to(pipeline, second if call == 1 else third)

    embedder = _HookedEmbedder(pipeline.pool(pipeline.version), on_call=switch)

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, embedder)

    assert caught.value.code is ErrorCode.SEARCH_UNAVAILABLE
    assert embedder.calls == 2


async def test_임베딩_서버를_쓸_수_없으면_서버의_메시지를_옮기지_않고_검색을_쓸_수_없다고_알린다(
    pipeline: Pipeline,
) -> None:
    await _index_everything(pipeline)
    secret = "http://tei.internal:8080 연결 거부"
    embedder = _HookedEmbedder(
        pipeline.pool(pipeline.version),
        failure=TransientFailure(ErrorCode.EMBEDDING_UNAVAILABLE, secret),
    )

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, embedder)

    assert caught.value.code is ErrorCode.SEARCH_UNAVAILABLE
    assert secret not in str(caught.value)


async def test_질의_임베딩과_키워드_토큰화가_함께_진행된다(pipeline: Pipeline) -> None:
    await _index_everything(pipeline)
    tokenizing = threading.Event()
    embedding = threading.Event()

    def tokenize(text: str) -> list[str]:
        tokenizing.set()
        assert embedding.wait(_WAIT_SECONDS)
        return tokenize_keywords(text)

    async def wait_for_tokenizer(_call: int) -> None:
        embedding.set()
        assert await asyncio.to_thread(tokenizing.wait, _WAIT_SECONDS)

    embedder = _HookedEmbedder(pipeline.pool(pipeline.version), on_call=wait_for_tokenizer)

    found = await _search(pipeline, embedder, tokenize)

    assert [embedder.calls, len(found.hits) > 0] == [1, True]
