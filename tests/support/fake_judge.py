"""평가 시험이 끼우는 가짜 관련성 판정기(ADR 0019, 포트 `RelevanceJudge`).

글마다 정해 둔 판정을 낸다. 정하지 않은 글은 관련 없음이다. 받은 호출을 순서대로 기억해서 시험이
판정기에 무엇이 갔는지 본다. `failure`를 주면 모든 호출이 그 예외를 올린다. 포트가 말하는
`TransientFailure`와 `PermanentFailure`가 평가에 닿는 길을 시험하는 데 쓴다. Claude 구현은
search-eval 12가 짓는다.
"""

from collections.abc import Mapping


class FakeRelevanceJudge:
    def __init__(
        self, relevant_texts: Mapping[str, bool] | None = None, *, failure: Exception | None = None
    ) -> None:
        self._verdicts = dict(relevant_texts or {})
        self._failure = failure
        self.calls: list[tuple[str, str]] = []

    async def judge(self, query: str, text: str) -> bool:
        self.calls.append((query, text))
        if self._failure is not None:
            raise self._failure
        return self._verdicts.get(text, False)
