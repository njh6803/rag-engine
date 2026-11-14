"""평가의 LLM 관련성 판정 유스케이스(티켓 search-eval 12, ADR 0019, 명세 "LLM 관련성 판정").

세 가지를 한다. 하나, 판정 파일에 아직 없는 쌍을 고른다(`pending_pairs`). 둘, 판정 파일의 줄로
보고서의 `llm` 숫자를 센다(`llm_summary`). 셋, 고른 쌍을 판정기 포트로 판정한다(`judge_pairs`).
판정기는 포트(`RelevanceJudge`)로만 부른다. 판정 파일을 읽고 쓰는 일과 끝점에 붙는 일은
`adapters`의 몫이다.

판정의 열쇠는 질의 글의 해시, 판정기에 보낸 글의 해시, 모델, 지시문의 판 넷이다. 질의의 글이나
조각의 글이 바뀌거나 모델이나 판이 바뀌면 옛 판정은 열쇠가 달라져 판정 없음으로 센다.

숫자의 분모. 관련 비율과 기대 근거에 닿은 조각의 일치 비율은 판정이 있는 조합만이 분모이고, 판정
없음의 비율은 판정 여부와 관계없이 마지막 단계의 상위 10개 조합 전체가 분모다(PR #38 봇 첫 회차의
지적). 상위 10개에 닿은 조각이 없는 질의만 판정되어 있으면 일치 비율은 값이 없다(`None`).

판정 쌍은 질의의 글과 조각의 글을 메모리에만 든다. 보고서는 질의 목록 이름, 기대 근거의 `id`, 문서의
키, 조각의 순번으로만 가리킨다(원칙 V).
"""

import asyncio
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final

from rag_engine.app.eval_run import QueryOutcome
from rag_engine.domain.errors import PermanentFailure, TransientFailure
from rag_engine.domain.ports import RelevanceJudge

# 명세 "LLM 관련성 판정"이 정한 값이다. 동시 호출 넷, 일시 실패는 세 번까지 다시 한다.
JUDGE_CONCURRENCY: Final = 4
JUDGE_RETRIES: Final = 3
# 다시 하기 전 기다림의 처음 값(초). 시도마다 두 배가 된다.
RETRY_DELAY_SECONDS: Final = 0.25
# ADR 0019의 어림이다. 3,000건(질문 150, 질의 목록 2, 상위 10)에 Opus 5.5로 약 26달러다.
_ADR_COUNT: Final = 3000
_ADR_DOLLARS: Final = 26.0
JUDGMENTS_FILE: Final = "judgments.jsonl"

type JudgmentKey = tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class Judgment:
    """판정 파일의 줄 하나. 글은 없고 해시만 있다."""

    query_sha256: str
    text_sha256: str
    relevant: bool
    model: str
    prompt_version: str
    judged_at: date

    @property
    def key(self) -> JudgmentKey:
        return (self.query_sha256, self.text_sha256, self.model, self.prompt_version)


@dataclass(frozen=True, slots=True)
class JudgmentPair:
    """판정기에 보낼 쌍 하나. 글은 `repr`에서 뺀다(원칙 V)."""

    query_sha256: str
    text_sha256: str
    query: str = field(repr=False)
    text: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class MissingCandidate:
    """기대 근거에 닿지 않았는데 LLM이 관련 있다고 본 조각. 식별자로만 가리킨다."""

    query_list: str
    evidence_id: str
    document: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class LlmNumbers:
    """보고서의 `llm` 칸. `pairs`는 마지막 단계의 상위 10개 조합 전체, `judged`는 그 가운데 판정이
    있는 조합이다. 비율은 분모가 0이면 `None`이다(판정 없음의 비율만 항상 값이 있다)."""

    pairs: int
    judged: int
    relevant_rate: float | None
    agreement_rate: float | None
    unjudged_rate: float
    missing_candidates: tuple[MissingCandidate, ...]


@dataclass(frozen=True, slots=True)
class LlmUnavailable:
    """숫자를 낼 수 없는 까닭. 보고서가 `llm`을 `null`로 두고 이 글을 싣는다."""

    reason: str


class JudgeRunError(Exception):
    """판정을 끝까지 받지 못한 까닭. 메시지는 이 저장소가 쓴 글만 싣는다(원칙 V). 판정기의 실패
    메시지도 이 저장소가 쓴 글이다(`RelevanceJudge`의 약속)."""


def pending_pairs(
    outcomes: Iterable[QueryOutcome],
    judgments: Iterable[Judgment],
    *,
    model: str,
    prompt_version: str,
) -> list[JudgmentPair]:
    """상위 10개의 쌍 가운데 판정 파일에 지금의 모델과 지시문 판으로 없는 것을 첫 등장 순으로
    중복 없이 낸다. 같은 질의의 글과 같은 조각의 글은 질의 목록이 달라도 한 쌍이다."""
    known = {judgment.key for judgment in judgments}
    seen: set[tuple[str, str]] = set()
    pairs: list[JudgmentPair] = []
    for outcome in outcomes:
        for passage in outcome.top:
            identity = (passage.query_sha256, passage.text_sha256)
            if identity in seen or (*identity, model, prompt_version) in known:
                continue
            seen.add(identity)
            pairs.append(JudgmentPair(*identity, query=passage.query, text=passage.text))
    return pairs


def llm_summary(
    outcomes: Sequence[QueryOutcome],
    judgments: Sequence[Judgment] | None,
    *,
    model: str,
    prompt_version: str,
) -> LlmNumbers | LlmUnavailable:
    """보고서의 `llm`. `judgments`는 판정 파일의 모든 줄이고 파일이 없으면 `None`이다."""
    if judgments is None:
        return LlmUnavailable(f"{JUDGMENTS_FILE}이 없다. judge로 판정을 쌓은 뒤에 run을 다시 친다")
    verdicts = {
        judgment.key: judgment.relevant
        for judgment in judgments
        if judgment.model == model and judgment.prompt_version == prompt_version
    }
    if not verdicts:
        return LlmUnavailable(
            f"{JUDGMENTS_FILE}에 config.json의 judge_model과 judge_prompt_version에 맞는 줄이"
            " 없다. 모델이나 지시문의 판을 바꿨으면 judge로 다시 판정한다"
        )
    pairs = judged = relevant = reached_judged = reached_relevant = 0
    missing: dict[MissingCandidate, None] = {}
    for outcome in outcomes:
        for passage in outcome.top:
            pairs += 1
            verdict = verdicts.get(
                (passage.query_sha256, passage.text_sha256, model, prompt_version)
            )
            if verdict is None:
                continue
            judged += 1
            relevant += verdict
            if passage.reached:
                reached_judged += 1
                reached_relevant += verdict
            elif verdict:
                candidate = MissingCandidate(
                    outcome.query_list, outcome.evidence_id, passage.document, passage.ordinal
                )
                missing[candidate] = None
    return LlmNumbers(
        pairs=pairs,
        judged=judged,
        relevant_rate=relevant / judged if judged else None,
        agreement_rate=reached_relevant / reached_judged if reached_judged else None,
        unjudged_rate=(pairs - judged) / pairs if pairs else 0.0,
        missing_candidates=tuple(missing),
    )


def estimate_dollars(count: int) -> float:
    """`count`건을 판정하는 비용의 어림(달러). ADR 0019의 3,000건 약 26달러에 건수를 비례시킨
    값이다."""
    return count * _ADR_DOLLARS / _ADR_COUNT


async def judge_pairs(
    judge: RelevanceJudge,
    pairs: Sequence[JudgmentPair],
    *,
    model: str,
    prompt_version: str,
    today: date,
    record: Callable[[Judgment], None],
    retry_delay_seconds: float = RETRY_DELAY_SECONDS,
) -> int:
    """쌍을 동시에 `JUDGE_CONCURRENCY`개까지 판정하고, 하나를 받을 때마다 `record`에 넘긴다. 받은
    판정의 수를 낸다. 일시 실패는 `JUDGE_RETRIES`번까지 다시 하고 영구 실패는 다시 하지 않는다.
    어느 쪽이든 끝내 실패하면 남은 쌍을 더 부르지 않고(호출 중인 것은 끝까지 기다린다) 첫 실패를
    `JudgeRunError`로 올린다. 이미 `record`에 넘긴 판정은 남는다."""
    queue = deque(pairs)
    failures: list[JudgeRunError] = []
    received = 0

    async def worker() -> None:
        nonlocal received
        while queue and not failures:
            pair = queue.popleft()
            try:
                relevant = await _judge_with_retries(judge, pair, retry_delay_seconds)
                record(
                    Judgment(
                        query_sha256=pair.query_sha256,
                        text_sha256=pair.text_sha256,
                        relevant=relevant,
                        model=model,
                        prompt_version=prompt_version,
                        judged_at=today,
                    )
                )
            except JudgeRunError as error:
                failures.append(error)
                return
            except OSError:
                failures.append(JudgeRunError(f"판정을 {JUDGMENTS_FILE}에 쓰지 못했다"))
                return
            received += 1

    await asyncio.gather(*(worker() for _ in range(min(JUDGE_CONCURRENCY, len(queue)))))
    if failures:
        raise failures[0]
    return received


async def _judge_with_retries(
    judge: RelevanceJudge, pair: JudgmentPair, retry_delay_seconds: float
) -> bool:
    attempt = 0
    while True:
        try:
            return await judge.judge(pair.query, pair.text)
        except TransientFailure as error:
            if attempt >= JUDGE_RETRIES:
                raise JudgeRunError(
                    f"판정기의 일시 실패가 다시 {JUDGE_RETRIES}번을 해도 풀리지 않았다: {error}"
                ) from None
            await asyncio.sleep(retry_delay_seconds * 2**attempt)
            attempt += 1
        except PermanentFailure as error:
            raise JudgeRunError(f"판정기가 요청을 받아들이지 않았다: {error}") from None
