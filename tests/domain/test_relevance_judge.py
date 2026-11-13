"""`RelevanceJudge` 포트와 시험 지원의 가짜 판정기(ADR 0019, 명세 "LLM 관련성 판정").

포트는 `judge(query, text)` 하나이고 관련 있으면 참이다. 다시 해 볼 만한 실패는 `TransientFailure`,
그 밖은 `PermanentFailure`로 올린다는 규칙은 포트의 독스트링이 적고 Claude 구현(12)이 지킨다.
"""

import pytest
from tests.support.fake_judge import FakeRelevanceJudge

from rag_engine.domain.errors import ErrorCode, PermanentFailure, TransientFailure
from rag_engine.domain.ports import RelevanceJudge


async def test_가짜_판정기는_정해_둔_글만_관련_있다고_하고_나머지는_관련_없다고_한다() -> None:
    judge: RelevanceJudge = FakeRelevanceJudge({"연차 규정": True, "식단표": False})

    verdicts = [await judge.judge("질문", text) for text in ("연차 규정", "식단표", "새 글")]

    assert verdicts == [True, False, False]


async def test_가짜_판정기는_받은_질문과_글을_순서대로_기억한다() -> None:
    fake = FakeRelevanceJudge()

    await fake.judge("질문 하나", "글 가")
    await fake.judge("질문 둘", "글 나")

    assert fake.calls == [("질문 하나", "글 가"), ("질문 둘", "글 나")]


@pytest.mark.parametrize(
    "failure",
    [
        TransientFailure(ErrorCode.EMBEDDING_UNAVAILABLE, "일시 실패의 대역"),
        PermanentFailure(ErrorCode.EMBEDDING_REJECTED, "영구 실패의 대역"),
    ],
    ids=["일시_실패", "영구_실패"],
)
async def test_가짜_판정기에_실패를_주면_모든_호출이_그_예외를_올린다(failure: Exception) -> None:
    fake = FakeRelevanceJudge(failure=failure)

    with pytest.raises(type(failure)) as raised:
        await fake.judge("질문", "글")

    assert raised.value is failure
    assert fake.calls == [("질문", "글")]
