"""TEI 스텁의 `/rerank`. 리랭커 어댑터(09)가 처음 밟기 전에 스텁이 흉내 내는 모양을 고정한다."""

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


async def test_rerank도_지정한_상태_코드로_실패시킬_수_있다() -> None:
    stub = TeiStub()
    stub.fail("/rerank", 503)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stub.app), base_url="http://tei.test"
    ) as client:
        response = await client.post("/rerank", json={"query": "가", "texts": ["나"]})

    assert response.status_code == 503
