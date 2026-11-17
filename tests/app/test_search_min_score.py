"""`search_documents`의 최소 점수(스토리 34~36, 38, ADR 0017, 티켓 search-eval 20).

실제 테스트 PostgreSQL 위에서 돈다. 리랭커는 점수를 정해 주는 가짜이고, 지식베이스의 기본값은
`update_knowledge_base`로 행에 써 넣는다. 문서 둘이 검색되고 리랭크 점수는 RRF 순서대로 0.5, 0.2다.
"""

import math
from collections.abc import Sequence
from dataclasses import replace

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import LEASE_SECONDS, Pipeline

from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.app.search import SearchDeps, SearchRequest, SearchResults, search_documents
from rag_engine.domain.errors import ErrorCode, RagEngineError
from rag_engine.domain.ports import Embedder, Reranker
from rag_engine.worker.processing import run_once

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")

_REQUEST = SearchRequest(
    query="연차휴가", top_k=5, knowledge_base=None, allowed_knowledge_base_ids=()
)
# 후보가 RRF 순서대로 이 점수를 받는다. 둘의 RRF 점수는 0.1보다 훨씬 작아 리랭크 점수와 구분된다.
_SCORES = (0.5, 0.2)


class _CountingEmbedder:
    """질의 임베딩을 부른 횟수를 센다. 거절한 요청이 임베딩 서버까지 가지 않았는지 본다."""

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        self.calls += 1
        return await self._inner.embed(texts)

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        return await self._inner.count_tokens(texts)

    async def special_token_count(self) -> int:
        return await self._inner.special_token_count()

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        return await self._inner.token_spans(text)


class _FixedReranker:
    async def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        return [_SCORES[index] for index in range(len(texts))]


_RERANKER = _FixedReranker()


async def _two_documents(pipeline: Pipeline) -> None:
    await pipeline.ingest(휴가, "휴가.docx")
    await pipeline.ingest(출장, "출장.docx")
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)
    await run_once(pipeline.deps(), worker_id="worker-1", lease_seconds=LEASE_SECONDS)


async def _set_default(pipeline: Pipeline, min_score: float | None) -> None:
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.update_knowledge_base(
            replace(pipeline.knowledge_base, min_score=min_score)
        )


async def _search(
    pipeline: Pipeline,
    min_score: float | None,
    *,
    reranker: Reranker | None = _RERANKER,
    embedder: _CountingEmbedder | None = None,
) -> SearchResults:
    counting = embedder or _CountingEmbedder(pipeline.pool(pipeline.version))
    deps = SearchDeps(
        unit_of_work=pipeline.unit_of_work,
        embedder_for=lambda _version: counting,
        reranker_for=lambda _knowledge_base: reranker,
        tokenize_keywords=tokenize_keywords,
        candidates=20,
        max_top_k=8,
        timeout_seconds=30.0,
    )
    return await search_documents(deps, replace(_REQUEST, min_score=min_score))


async def _scores(pipeline: Pipeline, min_score: float | None) -> list[float]:
    return [hit.score for hit in (await _search(pipeline, min_score)).hits]


async def test_리랭크_점수가_최소_점수보다_낮은_조각은_빠지고_같은_점수는_남는다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)

    assert await _scores(pipeline, 0.3) == [0.5]
    assert await _scores(pipeline, 0.5) == [0.5]
    assert await _scores(pipeline, 0.2) == [0.5, 0.2]


async def test_최소_점수는_리랭크_점수와_맞대고_RRF_점수로는_거르지_않는다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)

    assert await _scores(pipeline, 0.1) == [0.5, 0.2]


async def test_남은_조각이_없으면_오류가_아니라_쓴_지식베이스를_밝힌_빈_결과를_낸다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)

    found = await _search(pipeline, 0.9)

    assert (found.knowledge_base, found.hits) == ("default", ())


async def test_요청_인자가_없으면_지식베이스의_기본값으로_거르고_둘_다_없으면_거르지_않는다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)
    without_default = await _scores(pipeline, None)
    await _set_default(pipeline, 0.3)

    with_default = await _scores(pipeline, None)

    assert (without_default, with_default) == ([0.5, 0.2], [0.5])


async def test_요청_인자가_지식베이스의_기본값을_이기고_0은_기본값을_덮어_거르지_않는다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)
    await _set_default(pipeline, 0.9)

    assert await _scores(pipeline, None) == []
    assert await _scores(pipeline, 0.3) == [0.5]
    assert await _scores(pipeline, 0.0) == [0.5, 0.2]


@pytest.mark.parametrize(("min_score", "expected"), [(0.0, [0.5, 0.2]), (1.0, [])])
async def test_범위의_양_끝_값은_받는다(
    pipeline: Pipeline, min_score: float, expected: list[float]
) -> None:
    await _two_documents(pipeline)

    found = await _search(pipeline, min_score)

    assert [hit.score for hit in found.hits] == expected


@pytest.mark.parametrize("min_score", [-0.01, 1.01, 1.7, math.nan, math.inf, -math.inf])
async def test_범위_밖이거나_유한하지_않은_값은_임베딩_서버를_부르지_않고_잘못된_인자다(
    pipeline: Pipeline, min_score: float
) -> None:
    embedder = _CountingEmbedder(pipeline.pool(pipeline.version))

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, min_score, embedder=embedder)

    assert (caught.value.code, embedder.calls) == (ErrorCode.INVALID_ARGUMENT, 0)
    assert str(min_score) not in str(caught.value)


@pytest.mark.parametrize("min_score", [0.0, 0.5, 1.0])
async def test_리랭커가_없는_지식베이스에_요청의_min_score를_주면_0도_잘못된_인자다(
    pipeline: Pipeline, min_score: float
) -> None:
    await _two_documents(pipeline)
    embedder = _CountingEmbedder(pipeline.pool(pipeline.version))

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, min_score, reranker=None, embedder=embedder)

    assert (caught.value.code, embedder.calls) == (ErrorCode.INVALID_ARGUMENT, 0)


async def test_리랭커가_없는데_기본값이_있는_행에_요청_인자를_안_주면_검색을_쓸_수_없다고_알린다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)
    await _set_default(pipeline, 0.3)
    embedder = _CountingEmbedder(pipeline.pool(pipeline.version))

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, None, reranker=None, embedder=embedder)

    assert (caught.value.code, embedder.calls) == (ErrorCode.SEARCH_UNAVAILABLE, 0)
    assert "0.3" not in str(caught.value)


async def test_리랭커가_없고_기본값도_있는데_요청_인자까지_주면_요청_인자_쪽을_먼저_거부한다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)
    await _set_default(pipeline, 0.3)

    with pytest.raises(RagEngineError) as caught:
        await _search(pipeline, 0.5, reranker=None)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


async def test_리랭커가_없고_기본값도_없으면_지금_동작대로_RRF_점수로_낸다(
    pipeline: Pipeline,
) -> None:
    await _two_documents(pipeline)

    found = await _search(pipeline, None, reranker=None)

    assert [hit.score for hit in found.hits] == [hit.rrf_score for hit in found.hits]
    assert len(found.hits) == 2
