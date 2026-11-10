"""TEI 스텁의 `/rerank`와 입력 상한. 리랭커 어댑터(09)가 처음 밟기 전에 스텁이 흉내 내는 모양을
고정하고, 임베딩 어댑터가 피해 가야 할 두 거부(글자 수 상한 422, 본문 상한 413)를 고정한다."""

import httpx
from tests.support.tei_stub import TeiStub


async def test_rerank는_질의와_낱말이_겹치는_비율이_높은_글부터_돌려준다() -> None:
    stub = TeiStub()
    texts = ["바나나 우유", "사과 배 주스", "사과"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
    ) as client:
        response = await client.post("/rerank", json={"query": "사과 배", "texts": texts})

    ranks = response.json()
    assert [rank["index"] for rank in ranks] == [1, 2, 0]
    assert [rank["score"] for rank in ranks] == [1.0, 0.5, 0.0]


async def test_rerank는_요청_횟수와_마지막_본문을_기억한다() -> None:
    stub = TeiStub()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
    ) as client:
        await client.post("/rerank", json={"query": "첫째", "texts": ["가"]})
        await client.post("/rerank", json={"query": "둘째", "texts": ["나", "다"]})

    assert stub.count("/rerank") == 2
    assert stub.bodies("/rerank")[-1] == {"query": "둘째", "texts": ["나", "다"]}


async def test_tokenize는_글_하나가_최대_입력_길이의_250배_글자를_넘으면_422로_거부한다() -> None:
    stub = TeiStub(max_input_length=20)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
    ) as client:
        within = await client.post("/tokenize", json={"inputs": ["a" * 5000]})
        beyond = await client.post("/tokenize", json={"inputs": ["a" * 5001]})

    assert (within.status_code, beyond.status_code) == (200, 422)


async def test_요청_본문이_payload_limit_바이트를_넘으면_413으로_거부하고_기억하지_않는다() -> None:
    stub = TeiStub(payload_limit=1000)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
    ) as client:
        response = await client.post("/tokenize", json={"inputs": ["a" * 1000]})

    assert response.status_code == 413
    assert stub.requests == []


async def test_rerank도_지정한_상태_코드로_실패시킬_수_있다() -> None:
    stub = TeiStub()
    stub.fail("/rerank", 503)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
    ) as client:
        response = await client.post("/rerank", json={"query": "가", "texts": ["나"]})

    assert response.status_code == 503
