"""TEI 리랭커 어댑터. 스텁 서버에 붙여 `/info` 확인, 요청 칸, 묶음, 점수 합치기, 오류 번역을
본다(명세 "임베딩 서버와 리랭커 어댑터", 티켓 09)."""

import json
import logging
from collections.abc import AsyncIterator, Callable

import httpx
import pytest
from tests.support.tei_stub import SECRET_MESSAGE, TeiStub

from rag_engine.adapters.tei import TeiReranker
from rag_engine.domain.errors import ErrorCode, PermanentFailure, TransientFailure

type RerankerFactory = Callable[..., TeiReranker]

MODEL = "BAAI/bge-reranker-v2-m3"


@pytest.fixture
async def make_reranker() -> AsyncIterator[RerankerFactory]:
    clients: list[httpx.AsyncClient] = []

    def make(
        stub: TeiStub, *, batch_size: int = 32, model: str = MODEL, max_chunk_tokens: int = 512
    ) -> TeiReranker:
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
        )
        clients.append(client)
        return TeiReranker(
            client, model=model, batch_size=batch_size, max_chunk_tokens=max_chunk_tokens
        )

    yield make
    for client in clients:
        await client.aclose()


def _batch_sizes(stub: TeiStub) -> list[int]:
    sizes: list[int] = []
    for body in stub.bodies("/rerank"):
        texts = body["texts"]
        assert isinstance(texts, list)
        sizes.append(len(texts))
    return sizes


async def test_첫_호출_전에_info를_한_번만_읽는다(make_reranker: RerankerFactory) -> None:
    stub = TeiStub(model_id=MODEL)
    reranker = make_reranker(stub)

    await reranker.rerank("연차휴가", ["연차휴가 규정"])
    await reranker.rerank("출장비", ["출장비 정산"])

    assert [request.path for request in stub.requests][0] == "/info"
    assert stub.count("/info") == 1


async def test_info의_모델이_다르면_설정_불일치로_일시_실패이고_리랭크를_부르지_않는다(
    make_reranker: RerankerFactory,
) -> None:
    stub = TeiStub(model_id="other/model")

    with pytest.raises(TransientFailure) as caught:
        await make_reranker(stub).rerank("연차휴가", ["연차휴가 규정"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "설정 불일치" in str(caught.value)
    assert stub.count("/rerank") == 0


async def test_info의_최대_입력_길이가_조각_상한보다_작으면_설정_불일치로_일시_실패다(
    make_reranker: RerankerFactory,
) -> None:
    stub = TeiStub(model_id=MODEL, max_input_length=100)

    with pytest.raises(TransientFailure) as caught:
        await make_reranker(stub, max_chunk_tokens=512).rerank("연차휴가", ["연차휴가 규정"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "설정 불일치" in str(caught.value)
    assert "최대 입력 길이(100)" in str(caught.value)
    assert stub.count("/rerank") == 0


async def test_info의_최대_입력_길이가_조각_상한과_같으면_받는다(
    make_reranker: RerankerFactory,
) -> None:
    stub = TeiStub(model_id=MODEL, max_input_length=512)

    scores = await make_reranker(stub, max_chunk_tokens=512).rerank("연차휴가", ["연차휴가 규정"])

    assert len(scores) == 1


async def test_리랭커_끝점의_auto_truncate_값을_로그에_남긴다(
    make_reranker: RerankerFactory, caplog: pytest.LogCaptureFixture
) -> None:
    stub = TeiStub(model_id=MODEL, auto_truncate=False)

    with caplog.at_level(logging.INFO, logger="rag_engine.adapters.tei"):
        await make_reranker(stub).rerank("연차휴가", ["연차휴가 규정"])

    assert any("auto_truncate=False" in record.getMessage() for record in caplog.records)


async def test_요청은_질의와_글과_잘라_쓰는_칸을_싣는다(make_reranker: RerankerFactory) -> None:
    stub = TeiStub(model_id=MODEL)

    await make_reranker(stub).rerank("연차휴가", ["가 글", "나 글"])

    assert stub.bodies("/rerank") == [
        {
            "query": "연차휴가",
            "texts": ["가 글", "나 글"],
            "truncate": True,
            "truncation_direction": "Right",
            "raw_scores": False,
            "return_text": False,
        }
    ]


async def test_점수는_서버가_점수_순으로_돌려줘도_입력_순서로_나온다(
    make_reranker: RerankerFactory,
) -> None:
    stub = TeiStub(model_id=MODEL)

    scores = await make_reranker(stub).rerank("연차 휴가", ["출장 비", "연차 휴가", "연차 비"])

    assert scores == [0.0, 1.0, 0.5]


async def test_글이_많으면_묶음으로_나눠_보내고_점수를_입력_순서로_합친다(
    make_reranker: RerankerFactory,
) -> None:
    stub = TeiStub(model_id=MODEL)
    texts = ["연차", "휴가", "연차 휴가", "출장", "연차 출장"]

    scores = await make_reranker(stub, batch_size=2).rerank("연차 휴가", texts)

    assert (_batch_sizes(stub), scores) == ([2, 2, 1], [0.5, 0.5, 1.0, 0.0, 0.5])


async def test_info의_최대_묶음이_설정보다_작으면_그_값으로_낮춘다(
    make_reranker: RerankerFactory,
) -> None:
    stub = TeiStub(model_id=MODEL, max_client_batch_size=2)

    await make_reranker(stub, batch_size=32).rerank("연차", ["가", "나", "다", "라", "마"])

    assert _batch_sizes(stub) == [2, 2, 1]


async def test_글이_없으면_서버를_부르지_않는다(make_reranker: RerankerFactory) -> None:
    stub = TeiStub(model_id=MODEL)

    assert await make_reranker(stub).rerank("연차", []) == []
    assert stub.requests == []


@pytest.mark.parametrize(
    ("status", "failure", "code"),
    [
        (422, PermanentFailure, ErrorCode.EMBEDDING_REJECTED),
        (429, TransientFailure, ErrorCode.EMBEDDING_UNAVAILABLE),
        (503, TransientFailure, ErrorCode.EMBEDDING_UNAVAILABLE),
    ],
)
async def test_서버_오류는_메시지를_옮기지_않고_영구_일시_실패로_번역한다(
    make_reranker: RerankerFactory,
    status: int,
    failure: type[Exception],
    code: ErrorCode,
) -> None:
    stub = TeiStub(model_id=MODEL)
    stub.fail("/rerank", status)

    with pytest.raises(failure) as caught:
        await make_reranker(stub).rerank("연차", ["가"])

    assert getattr(caught.value, "code") is code  # noqa: B009
    assert SECRET_MESSAGE not in str(caught.value)


async def test_응답의_순번이_글과_맞지_않으면_일시_실패다() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/info":
            return httpx.Response(
                200,
                json={
                    "model_id": MODEL,
                    "served_model_name": MODEL,
                    "max_input_length": 512,
                    "max_client_batch_size": 32,
                    "auto_truncate": True,
                },
            )
        json.loads(request.content)
        return httpx.Response(200, json=[{"index": 0, "score": 0.5}])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://tei.test")
    reranker = TeiReranker(client, model=MODEL, batch_size=8, max_chunk_tokens=512)

    with pytest.raises(TransientFailure) as caught:
        await reranker.rerank("연차", ["가", "나"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "응답 형식" in str(caught.value)
    await client.aclose()


@pytest.mark.parametrize("non_finite", ["NaN", "Infinity", "-Infinity"])
async def test_점수가_유한하지_않으면_순위를_정할_수_없어_일시_실패다(non_finite: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/info":
            return httpx.Response(
                200,
                json={
                    "model_id": MODEL,
                    "served_model_name": MODEL,
                    "max_input_length": 512,
                    "max_client_batch_size": 32,
                    "auto_truncate": True,
                },
            )
        body = f'[{{"index": 0, "score": {non_finite}}}, {{"index": 1, "score": 0.5}}]'
        return httpx.Response(
            200, content=body.encode(), headers={"content-type": "application/json"}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://tei.test")
    reranker = TeiReranker(client, model=MODEL, batch_size=8, max_chunk_tokens=512)

    with pytest.raises(TransientFailure) as caught:
        await reranker.rerank("연차", ["가", "나"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "응답 형식" in str(caught.value)
    await client.aclose()
