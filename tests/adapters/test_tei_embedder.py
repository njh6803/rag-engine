"""TEI 임베딩 어댑터. 스텁 서버에 붙여 `/info` 확인, 배치, 토큰 세기, 오류 번역을 본다(명세 "임베딩
서버와 리랭커 어댑터")."""

import logging
from collections.abc import AsyncIterator, Callable, Mapping, Sequence

import httpx
import pytest
from tests.support.tei_stub import SECRET_MESSAGE, TeiStub

from rag_engine.adapters.tei import TeiEmbedder
from rag_engine.domain.entities import JsonValue
from rag_engine.domain.errors import ErrorCode, PermanentFailure, TransientFailure

type EmbedderFactory = Callable[..., TeiEmbedder]

MODEL = "BAAI/bge-m3"


@pytest.fixture
async def make_embedder() -> AsyncIterator[EmbedderFactory]:
    clients: list[httpx.AsyncClient] = []

    def make(
        stub: TeiStub,
        *,
        dimensions: int = 16,
        batch_size: int = 32,
        max_chunk_tokens: int = 512,
        model: str = MODEL,
    ) -> TeiEmbedder:
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
        )
        clients.append(client)
        return TeiEmbedder(
            client,
            model=model,
            dimensions=dimensions,
            max_chunk_tokens=max_chunk_tokens,
            batch_size=batch_size,
        )

    yield make
    for client in clients:
        await client.aclose()


def _info_json(**overrides: object) -> dict[str, object]:
    info: dict[str, object] = {
        "model_id": MODEL,
        "served_model_name": MODEL,
        "model_type": {"embedding": {"pooling": "cls"}},
        "max_input_length": 8192,
        "max_client_batch_size": 32,
        "auto_truncate": True,
    }
    return info | overrides


def _embedder_over(handler: Callable[[httpx.Request], httpx.Response]) -> TeiEmbedder:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://tei.test", timeout=1
    )
    return TeiEmbedder(client, model=MODEL, dimensions=4, max_chunk_tokens=512, batch_size=8)


async def test_첫_호출_전에_info를_한_번만_읽는다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub()
    embedder = make_embedder(stub)

    await embedder.embed(["가나다"])
    await embedder.count_tokens(["가나다"])
    await embedder.embed(["라마바"])

    assert [request.path for request in stub.requests][0] == "/info"
    assert stub.count("/info") == 1


async def test_info의_모델이_다르면_설정_불일치로_일시_실패이고_임베딩을_부르지_않는다(
    make_embedder: EmbedderFactory,
) -> None:
    stub = TeiStub(model_id="other/model")

    with pytest.raises(TransientFailure) as caught:
        await make_embedder(stub).embed(["가나다"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "설정 불일치" in str(caught.value)
    assert stub.count("/v1/embeddings") == 0


async def test_served_model_name이_넘긴_모델과_같으면_통과한다(
    make_embedder: EmbedderFactory,
) -> None:
    stub = TeiStub(model_id="/data/local-copy", served_model_name=MODEL)

    assert len(await make_embedder(stub).embed(["가나다"])) == 1


async def test_info의_최대_입력_길이가_조각_상한보다_작으면_설정_불일치다(
    make_embedder: EmbedderFactory,
) -> None:
    stub = TeiStub(max_input_length=256)

    with pytest.raises(TransientFailure) as caught:
        await make_embedder(stub, max_chunk_tokens=512).embed(["가나다"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "설정 불일치" in str(caught.value)


async def test_info의_최대_입력_길이가_조각_상한과_같으면_통과한다(
    make_embedder: EmbedderFactory,
) -> None:
    stub = TeiStub(max_input_length=512)

    assert len(await make_embedder(stub, max_chunk_tokens=512).embed(["가나다"])) == 1


async def test_auto_truncate_값을_로그에_남긴다(
    make_embedder: EmbedderFactory, caplog: pytest.LogCaptureFixture
) -> None:
    stub = TeiStub(auto_truncate=True)

    with caplog.at_level(logging.INFO, logger="rag_engine.adapters.tei"):
        await make_embedder(stub).embed(["가나다"])

    assert any("auto_truncate=True" in record.getMessage() for record in caplog.records)


async def test_info가_실패하면_다음_호출에서_다시_확인한다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub()
    embedder = make_embedder(stub)
    stub.fail("/info", 503)

    with pytest.raises(TransientFailure) as caught:
        await embedder.embed(["가나다"])
    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    stub.forced_statuses.clear()

    assert len(await embedder.embed(["가나다"])) == 1
    assert stub.count("/info") == 2


async def test_임베딩은_배치_크기만큼씩_보내고_입력_순서대로_돌려준다(
    make_embedder: EmbedderFactory,
) -> None:
    stub = TeiStub()
    embedder = make_embedder(stub, batch_size=32)
    texts = [f"word{i}" for i in range(70)]

    vectors = await embedder.embed(texts)

    assert [_input_size(body) for body in stub.bodies("/v1/embeddings")] == [32, 32, 6]
    assert len(vectors) == 70
    # 배치 경계 앞뒤(31·32, 63·64)와 처음, 끝이 그 글을 따로 임베딩한 벡터와 같다.
    for position in (0, 31, 32, 63, 64, 69):
        assert vectors[position] == (await embedder.embed([texts[position]]))[0]


async def test_임베딩_요청에_모델_이름을_싣는다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub()

    await make_embedder(stub).embed(["가나다"])

    assert stub.bodies("/v1/embeddings")[0]["model"] == MODEL


async def test_info의_max_client_batch_size가_더_작으면_그_값으로_낮춘다(
    make_embedder: EmbedderFactory,
) -> None:
    stub = TeiStub(max_client_batch_size=10)
    embedder = make_embedder(stub, batch_size=32)

    await embedder.embed([f"word{i}" for i in range(25)])
    await embedder.count_tokens([f"word{i}" for i in range(25)])

    assert [_input_size(body) for body in stub.bodies("/v1/embeddings")] == [10, 10, 5]
    assert [_inputs_size(body) for body in stub.bodies("/tokenize")] == [10, 10, 5]


async def test_빈_입력은_서버를_부르지_않는다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub()
    embedder = make_embedder(stub)

    assert await embedder.embed([]) == []
    assert await embedder.count_tokens([]) == []
    assert stub.requests == []


async def test_벡터_길이가_설정_차원과_다르면_영구_실패다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub(dimensions=16)

    with pytest.raises(PermanentFailure) as caught:
        await make_embedder(stub, dimensions=8).embed(["가나다"])

    assert caught.value.code is ErrorCode.EMBEDDING_DIMENSION_MISMATCH


@pytest.mark.parametrize("status", [400, 413, 422])
async def test_거부_상태_코드는_영구_실패로_번역하고_서버_메시지를_옮기지_않는다(
    make_embedder: EmbedderFactory, status: int
) -> None:
    stub = TeiStub()
    stub.fail("/v1/embeddings", status)
    stub.fail("/tokenize", status)
    embedder = make_embedder(stub)

    with pytest.raises(PermanentFailure) as embed_error:
        await embedder.embed(["가나다"])
    with pytest.raises(PermanentFailure) as count_error:
        await embedder.count_tokens(["가나다"])

    for caught in (embed_error, count_error):
        assert caught.value.code is ErrorCode.EMBEDDING_REJECTED
        assert SECRET_MESSAGE not in str(caught.value)


@pytest.mark.parametrize("status", [424, 429, 500, 502, 503, 404])
async def test_일시_상태_코드는_일시_실패로_번역하고_서버_메시지를_옮기지_않는다(
    make_embedder: EmbedderFactory, status: int
) -> None:
    stub = TeiStub()
    stub.fail("/v1/embeddings", status)
    stub.fail("/tokenize", status)
    embedder = make_embedder(stub)

    with pytest.raises(TransientFailure) as embed_error:
        await embedder.embed(["가나다"])
    with pytest.raises(TransientFailure) as count_error:
        await embedder.count_tokens(["가나다"])

    for caught in (embed_error, count_error):
        assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
        assert SECRET_MESSAGE not in str(caught.value)


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("secret-host.internal"), httpx.ReadTimeout("secret-timeout")],
    ids=["연결_실패", "시간_초과"],
)
async def test_연결_실패와_시간_초과는_일시_실패로_번역하고_원인_메시지를_옮기지_않는다(
    error: httpx.TransportError,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(TransientFailure) as caught:
        await _embedder_over(handler).embed(["가나다"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "secret" not in str(caught.value)


async def test_응답의_임베딩_개수가_입력과_다르면_일시_실패다() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/info":
            return httpx.Response(200, json=_info_json())
        return httpx.Response(200, json={"object": "list", "data": [], "model": MODEL})

    with pytest.raises(TransientFailure) as caught:
        await _embedder_over(handler).embed(["가나다"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE


async def test_json이_아닌_응답은_일시_실패다() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>proxy error</html>")

    with pytest.raises(TransientFailure) as caught:
        await _embedder_over(handler).embed(["가나다"])

    assert caught.value.code is ErrorCode.EMBEDDING_UNAVAILABLE
    assert "proxy" not in str(caught.value)


async def test_토큰_수는_특수_토큰을_끄고_글마다_센다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub()

    counts = await make_embedder(stub).count_tokens(["검색 서버", "vector search 와 😀"])

    assert counts == [2, 4]
    assert stub.bodies("/tokenize")[0]["add_special_tokens"] is False


async def test_빈_글은_서버를_부르지_않고_토큰_0으로_센다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub()

    counts = await make_embedder(stub).count_tokens(["", "가나다", ""])

    assert counts == [0, 1, 0]
    assert [_inputs_size(body) for body in stub.bodies("/tokenize")] == [1]


@pytest.mark.parametrize("special_tokens", [0, 2, 4])
async def test_특수_토큰_수는_켠_호출과_끈_호출의_차이다(
    make_embedder: EmbedderFactory, special_tokens: int
) -> None:
    stub = TeiStub(special_tokens=special_tokens)
    embedder = make_embedder(stub)

    assert await embedder.special_token_count() == special_tokens
    assert await embedder.special_token_count() == special_tokens
    flags = [body["add_special_tokens"] for body in stub.bodies("/tokenize")]
    assert sorted(flags, key=str) == [False, True]


async def test_토큰_구간은_글자_인덱스로_바뀌어_원문의_조각과_맞는다(
    make_embedder: EmbedderFactory,
) -> None:
    text = "검색 서버😀 와 vector"
    stub = TeiStub()

    spans = await make_embedder(stub).token_spans(text)

    assert [text[start:end] for start, end in spans] == ["검색", "서버", "😀", "와", "vector"]
    assert stub.bodies("/tokenize")[0]["add_special_tokens"] is False


async def test_빈_글의_토큰_구간은_없다(make_embedder: EmbedderFactory) -> None:
    stub = TeiStub()

    assert await make_embedder(stub).token_spans("") == []
    assert stub.requests == []


async def test_글자_수_상한을_넘는_글은_잘라_세고_서버에는_상한_안의_글만_보낸다(
    make_embedder: EmbedderFactory,
) -> None:
    # 최대 입력 길이가 20이면 TEI는 글 하나가 5000자를 넘는 요청을 거부한다.
    stub = TeiStub(max_input_length=20)
    text = "가 " * 6000

    counts = await make_embedder(stub, max_chunk_tokens=10).count_tokens([text])

    assert counts == [6000]
    longest = max(len(piece) for body in stub.bodies("/tokenize") for piece in _inputs_of(body))
    assert longest <= 5000


async def test_잘라_센_긴_글의_토큰_구간은_글_전체의_글자_인덱스를_잇는다(
    make_embedder: EmbedderFactory,
) -> None:
    # 최대 입력 길이 24는 글 하나 6000자이고, 낱말마다 여섯 글자라 9000자는 6000자와 3000자로
    # 갈린다. 낱말이 서로 달라야 조각 뒤쪽의 오프셋이 밀리면 다른 글자가 잡힌다.
    stub = TeiStub(max_input_length=24)
    words = [f"가{number:04d}" for number in range(1500)]
    text = "".join(f"{word} " for word in words)

    spans = await make_embedder(stub, max_chunk_tokens=10).token_spans(text)

    assert [text[start:end] for start, end in spans] == words


async def test_요청_본문이_바이트_상한을_넘지_않도록_묶음을_나눈다(
    make_embedder: EmbedderFactory,
) -> None:
    # 글 여섯이 한 요청이면 1.2MB라 서버의 본문 상한(1.1MB)을 넘는다.
    stub = TeiStub(payload_limit=1_100_000)
    texts = ["a" * 200_000 for _ in range(6)]

    counts = await make_embedder(stub).count_tokens(texts)

    assert counts == [1] * 6
    assert [_inputs_size(body) for body in stub.bodies("/tokenize")] == [5, 1]


def _inputs_of(body: Mapping[str, JsonValue]) -> list[str]:
    inputs = body["inputs"]
    assert isinstance(inputs, Sequence)
    assert not isinstance(inputs, str)
    return [item for item in inputs if isinstance(item, str)]


def _input_size(body: Mapping[str, JsonValue]) -> int:
    return _list_size(body["input"])


def _inputs_size(body: Mapping[str, JsonValue]) -> int:
    return _list_size(body["inputs"])


def _list_size(value: JsonValue) -> int:
    assert isinstance(value, Sequence)
    assert not isinstance(value, str)
    return len(value)
