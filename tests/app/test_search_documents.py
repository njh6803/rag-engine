"""`search_documents` 유스케이스의 판 전환 대응과 임베딩 실패(명세 "검색 흐름", 티켓 07).

실제 테스트 PostgreSQL과 실제 청커·Kiwi 위에서 돈다. 질의를 임베딩하는 순간에 현재 판이 바뀌거나
임베딩 서버가 죽는 상황은 임베더를 바꿔 끼워 만든다.
"""

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import timedelta

import pytest
from tests.records import NOW
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import LEASE_SECONDS, Pipeline

from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.app.search import SearchDeps, SearchRequest, SearchResults, search_documents
from rag_engine.domain.entities import Group, IndexVersion
from rag_engine.domain.errors import (
    ErrorCode,
    PermanentFailure,
    RagEngineError,
    TransientFailure,
)
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.index_text import compose_index_text
from rag_engine.domain.ports import Embedder, KeywordTokenizer, Reranker
from rag_engine.worker.processing import run_once

# 한 쪽이 다른 쪽을 기다리다 이 시간을 넘기면 둘이 함께 진행하지 않는 것이다.
_WAIT_SECONDS = 5

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")


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


_REQUEST = SearchRequest(
    query="연차휴가", top_k=5, knowledge_base=None, allowed_knowledge_base_ids=()
)
_MAX_TOP_K = 8


class _ScriptedReranker:
    """점수를 정해진 함수로 매기고 받은 질의와 글을 기억한다."""

    def __init__(
        self, score_of: Callable[[int], float], failure: Exception | None = None, delay: float = 0
    ) -> None:
        self._score_of = score_of
        self._failure = failure
        self._delay = delay
        self.calls: list[tuple[str, list[str]]] = []

    async def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        self.calls.append((query, list(texts)))
        if self._failure is not None:
            raise self._failure
        await asyncio.sleep(self._delay)
        return [self._score_of(index) for index in range(len(texts))]


async def _search(
    pipeline: Pipeline,
    embedder: Embedder,
    tokenize: KeywordTokenizer = tokenize_keywords,
    *,
    request: SearchRequest = _REQUEST,
    reranker: Reranker | None = None,
    timeout_seconds: float = 30.0,
) -> SearchResults:
    deps = SearchDeps(
        unit_of_work=pipeline.unit_of_work,
        embedder_for=lambda _version: embedder,
        reranker_for=lambda _knowledge_base: reranker,
        tokenize_keywords=tokenize,
        candidates=20,
        max_top_k=_MAX_TOP_K,
        timeout_seconds=timeout_seconds,
    )
    return await search_documents(deps, request)


async def _two_documents(pipeline: Pipeline) -> None:
    await pipeline.ingest(휴가, "휴가.docx")
    await pipeline.ingest(출장, "출장.docx")
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)


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


def _embedder(pipeline: Pipeline) -> _HookedEmbedder:
    return _HookedEmbedder(pipeline.pool(pipeline.version))


@pytest.mark.parametrize("query", ["", "   "])
async def test_빈_질의는_임베딩_서버를_부르지_않고_잘못된_인자로_거절한다(
    pipeline: Pipeline, query: str
) -> None:
    embedder = _embedder(pipeline)

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, embedder, request=replace(_REQUEST, query=query))

    assert (caught.value.code, embedder.calls) == (ErrorCode.INVALID_ARGUMENT, 0)


@pytest.mark.parametrize("top_k", [0, -1, _MAX_TOP_K + 1])
async def test_범위_밖_top_k는_잘못된_인자로_거절한다(pipeline: Pipeline, top_k: int) -> None:
    embedder = _embedder(pipeline)

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, embedder, request=replace(_REQUEST, top_k=top_k))

    assert (caught.value.code, embedder.calls) == (ErrorCode.INVALID_ARGUMENT, 0)


async def test_top_k의_양_끝_값은_받는다(pipeline: Pipeline) -> None:
    await _two_documents(pipeline)

    smallest = await _search(pipeline, _embedder(pipeline), request=replace(_REQUEST, top_k=1))
    largest = await _search(
        pipeline, _embedder(pipeline), request=replace(_REQUEST, top_k=_MAX_TOP_K)
    )

    assert (len(smallest.hits), len(largest.hits)) == (1, 2)


async def test_리랭커가_없으면_RRF_점수_그대로_순서를_정한다(pipeline: Pipeline) -> None:
    await _two_documents(pipeline)

    found = await _search(pipeline, _embedder(pipeline))

    assert [hit.score for hit in found.hits] == [hit.rrf_score for hit in found.hits]
    assert found.timings.rerank_ms == 0.0


async def test_리랭커가_있으면_후보_전부를_절_경로가_든_글로_리랭크해_점수_순으로_바꾼다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)
    before = await _search(pipeline, _embedder(pipeline))
    reranker = _ScriptedReranker(lambda index: float(index))

    found = await _search(pipeline, _embedder(pipeline), reranker=reranker)

    assert reranker.calls == [
        (
            "연차휴가",
            [compose_index_text(hit.location.section, hit.text) for hit in before.hits],
        )
    ]
    assert [hit.chunk_id for hit in found.hits] == [hit.chunk_id for hit in reversed(before.hits)]
    assert [hit.score for hit in found.hits] == [1.0, 0.0]
    assert found.timings.rerank_ms >= 0.0


async def test_top_k는_리랭크_뒤에_자르고_후보_전부를_리랭크한다(pipeline: Pipeline) -> None:
    await _two_documents(pipeline)
    before = await _search(pipeline, _embedder(pipeline))
    reranker = _ScriptedReranker(lambda index: float(index))

    found = await _search(
        pipeline,
        _embedder(pipeline),
        reranker=reranker,
        request=replace(_REQUEST, top_k=1),
    )

    assert [hit.chunk_id for hit in found.hits] == [before.hits[-1].chunk_id]
    assert [len(texts) for _, texts in reranker.calls] == [len(before.hits)]


@pytest.mark.parametrize(
    "failure",
    [
        TransientFailure(ErrorCode.EMBEDDING_UNAVAILABLE, "http://reranker.internal 설정 불일치"),
        PermanentFailure(ErrorCode.EMBEDDING_REJECTED, "http://reranker.internal 거부"),
    ],
)
async def test_리랭커가_실패하면_RRF로_대신하지_않고_서버_메시지를_옮기지_않고_알린다(
    pipeline: Pipeline, failure: RagEngineError
) -> None:
    await _two_documents(pipeline)
    reranker = _ScriptedReranker(lambda index: 0.0, failure=failure)

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, _embedder(pipeline), reranker=reranker)

    assert caught.value.code is ErrorCode.SEARCH_UNAVAILABLE
    assert "reranker.internal" not in str(caught.value)


async def test_전체_시간_제한을_넘으면_검색을_쓸_수_없다고_알린다(pipeline: Pipeline) -> None:
    await _two_documents(pipeline)

    async def stall(_call: int) -> None:
        await asyncio.sleep(_WAIT_SECONDS * 4)

    embedder = _HookedEmbedder(pipeline.pool(pipeline.version), on_call=stall)
    started = time.monotonic()

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, embedder, timeout_seconds=0.3)

    assert caught.value.code is ErrorCode.SEARCH_UNAVAILABLE
    assert time.monotonic() - started < _WAIT_SECONDS


async def test_리랭크가_느려_전체_시간_제한을_넘어도_검색을_쓸_수_없다고_알린다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)
    reranker = _ScriptedReranker(lambda index: 0.0, delay=_WAIT_SECONDS * 4)

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, _embedder(pipeline), reranker=reranker, timeout_seconds=0.5)

    assert caught.value.code is ErrorCode.SEARCH_UNAVAILABLE


async def _add_group(pipeline: Pipeline, name: str) -> Group:
    group = Group(new_id(), name, "")
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.add_group(group)
        await transaction.catalog.add_group_to_knowledge_base(pipeline.knowledge_base.id, group.id)
    return group


async def _keys_found(pipeline: Pipeline, **filter_fields: object) -> set[str]:
    request = replace(_REQUEST, query="연차휴가 출장비", **filter_fields)
    found = await _search(pipeline, _embedder(pipeline), request=request)
    return {hit.key for hit in found.hits}


async def test_그룹_필터는_그_그룹의_문서만_내고_없는_그룹_이름은_아무_문서에도_맞지_않는다(
    pipeline: Pipeline,
) -> None:
    await _add_group(pipeline, "인사")
    await pipeline.ingest(휴가, "휴가.docx")
    await pipeline.ingest(출장, "출장.docx", group="인사")
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)

    unfiltered = await _keys_found(pipeline)
    only_personnel = await _keys_found(pipeline, groups=("인사",))
    mixed = await _keys_found(pipeline, groups=("default", "없는그룹"))
    unknown = await _keys_found(pipeline, groups=("없는그룹",))
    empty_list = await _keys_found(pipeline, groups=())

    assert unfiltered == {"휴가.docx", "출장.docx"}
    assert only_personnel == {"출장.docx"}
    assert mixed == {"휴가.docx"}
    assert unknown == set()
    assert empty_list == unfiltered


async def test_갱신일_기간은_시작을_포함하고_끝을_제외한다(pipeline: Pipeline) -> None:
    await pipeline.ingest(휴가, "휴가.docx", updated_at=NOW - timedelta(days=2))
    await pipeline.ingest(출장, "출장.docx", updated_at=NOW - timedelta(days=1))
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)
    yesterday = NOW - timedelta(days=1)

    from_yesterday = await _keys_found(pipeline, updated_after=yesterday)
    before_yesterday = await _keys_found(pipeline, updated_before=yesterday)
    both = await _keys_found(
        pipeline, updated_after=NOW - timedelta(days=2), updated_before=yesterday
    )

    assert (from_yesterday, before_yesterday, both) == ({"출장.docx"}, {"휴가.docx"}, {"휴가.docx"})
