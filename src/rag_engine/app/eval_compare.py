"""보고서와 기준 보고서의 견줌(티켓 search-eval 08, 명세 "CI 게이트와 기준 보고서"의 `compare`의
판정).

읽어 낸 값 위의 순수한 판정이다. 보고서 파일을 읽고 종료 코드를 내는 일은 `adapters`와 명령줄 도구가
맡는다. 이 유스케이스를 admin이 평가를 화면으로 열 때 함께 쓴다(명세 "자리와 층").

게이트는 둘이다. 빠른 게이트(`Gate.FAST`)는 합친 뒤 줄을, 전체 게이트(`Gate.FULL`)는 리랭크 뒤 줄을
본다. 질의 목록마다 상위 5 적중률이 2%p, MRR이 0.02를 넘어 떨어지면 실패다. 경계는 넘을 때만
실패라서 정확히 그만큼 떨어진 값은 통과한다. 보고서의 숫자는 `정수/질의 수` 같은 부동소수점이라
마지막 자리에 표현 오차(1e-16 쯤)가 실린다. 그래서 차는 보고서에 적힌 소수 글자 그대로 `Decimal`로
뺀 뒤 소수 아홉째 자리로 반올림해서 하락폭과 견준다. 질의가 3만 개를 넘지 않는 한 실제 차이는 그보다
훨씬 크므로 반올림이 실제 하락을 가리지 않고, 질의 수가 150이나 300인 보고서에서 정확히 2%p 떨어진
값도 통과한다.

숫자를 견주기 전에 견줄 수 있는 보고서인지를 본다. 묶음의 내용 해시, 구성(`judge_model`과
`judge_prompt_version`을 뺀 칸), 그 게이트가 읽는 기록 파일의 해시 가운데 하나라도 다르면 숫자를
견주지 않는다. 기준 보고서를 갱신하고 승인을 받아야 하는 변경이기 때문이다. 보고서의 `meta`(실행
시각과 커밋)는 견줌에 들지 않는다.

못 보는 것. 기록 파일의 요청 지문과 TEI의 판은 보지 않는다. 보고서가 싣지 않는 값이고, 그 불일치는
`validate`의 몫이다(빠른 게이트의 잡이 `validate`를 `run`보다 앞에 두는 것은 명세 "CI 게이트와 기준
보고서"가 정하고, 그 잡을 짓는 티켓 11이 지킨다).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from rag_engine.app.eval_stages import Stage
from rag_engine.domain.entities import JsonValue
from rag_engine.domain.eval_set import JUDGE_CONFIG_KEYS

HIT_AT_5_DROP: Final = Decimal("0.02")
MRR_DROP: Final = Decimal("0.02")
_GAP_PRECISION: Final = Decimal("1e-9")
_RECORDS_FOLDER: Final = "records"
_EMBEDDING_FILES: Final = tuple(
    f"{_RECORDS_FOLDER}/{kind}.{extension}"
    for kind in ("chunk-embeddings", "query-embeddings")
    for extension in ("keys", "f32")
)
_RERANK_FILE: Final = f"{_RECORDS_FOLDER}/rerank.jsonl"
_HASH_PREVIEW: Final = 12


class Gate(StrEnum):
    """게이트의 종류. 값은 `compare --gate`의 인자다."""

    FAST = "fast"
    FULL = "full"

    @property
    def stage(self) -> Stage:
        """그 게이트가 보는 줄의 단계."""
        return Stage.RERANK if self is Gate.FULL else Stage.FUSED

    @property
    def baseline_file(self) -> str:
        """묶음 폴더에 커밋하는 기준 보고서의 이름."""
        return f"baseline-{self.value}.json"

    @property
    def record_files(self) -> tuple[str, ...]:
        """그 게이트가 읽는 기록 파일(묶음 폴더 기준 경로). 빠른 게이트는 조각과 질의의 임베딩이고
        전체 게이트는 거기에 리랭크 점수가 더해진다."""
        return (*_EMBEDDING_FILES, _RERANK_FILE) if self is Gate.FULL else _EMBEDDING_FILES


@dataclass(frozen=True, slots=True)
class MetricRow:
    """질의 목록과 단계 하나의 상위 5 적중률과 MRR."""

    query_list: str
    stage: str
    hit_at_5: float
    mrr: float


@dataclass(frozen=True, slots=True)
class ComparableReport:
    """견줌에 필요한 칸만 든 보고서. `config`는 보고서의 `config` 칸 그대로이고, `record_files`는
    `records.files`(묶음 폴더 기준 경로 → sha256)다."""

    content_hash: str
    config: Mapping[str, JsonValue]
    record_files: Mapping[str, str]
    rows: tuple[MetricRow, ...]


@dataclass(frozen=True, slots=True)
class MetricChange:
    """질의 목록 하나의 지표 하나가 기준에서 바뀐 것. `difference`는 기준값에서 새 값을 뺀
    차다(떨어지면 양수)."""

    query_list: str
    stage: str
    metric: str
    baseline: float
    new: float

    @property
    def difference(self) -> float:
        return float(_gap(self.baseline, self.new))


@dataclass(frozen=True, slots=True)
class CompareResult:
    """견줌의 결과. `incomparable`이 비어 있지 않으면 숫자를 견주지 않았고 `drops`와 `rises`는
    비었다."""

    incomparable: tuple[str, ...]
    drops: tuple[MetricChange, ...]
    rises: tuple[MetricChange, ...]

    @property
    def passed(self) -> bool:
        return not self.incomparable and not self.drops


def compare_reports(baseline: ComparableReport, new: ComparableReport, gate: Gate) -> CompareResult:
    """`new`를 `baseline`과 `gate`가 보는 줄로 견준다."""
    reasons = _incomparable(baseline, new, gate)
    if reasons:
        return CompareResult(tuple(reasons), (), ())
    reasons = _missing_rows(baseline, new, gate)
    if reasons:
        return CompareResult(tuple(reasons), (), ())
    drops: list[MetricChange] = []
    rises: list[MetricChange] = []
    new_rows = {(row.query_list, row.stage): row for row in new.rows}
    for row in baseline.rows:
        if row.stage != gate.stage.value:
            continue
        current = new_rows[(row.query_list, row.stage)]
        for metric, threshold, before, after in (
            ("hit_at_5", HIT_AT_5_DROP, row.hit_at_5, current.hit_at_5),
            ("mrr", MRR_DROP, row.mrr, current.mrr),
        ):
            change = MetricChange(row.query_list, row.stage, metric, before, after)
            gap = _gap(before, after)
            if gap > threshold:
                drops.append(change)
            elif -gap > threshold:
                rises.append(change)
    return CompareResult((), tuple(drops), tuple(rises))


def _gap(baseline: float, new: float) -> Decimal:
    """기준값에서 새 값을 뺀 차(떨어지면 양수). 보고서에 적힌 소수 글자 그대로 `Decimal`로 빼고
    소수 아홉째 자리로 반올림한다. 글자 그대로만으로는 `정수/질의 수`로 나온 값끼리의 차가 하락폭
    언저리에서 1e-16쯤 어긋나, 정확히 2%p 떨어진 값이 하락폭을 넘는 것으로 읽힌다."""
    exact = Decimal(repr(baseline)) - Decimal(repr(new))
    return exact.quantize(_GAP_PRECISION)


def _incomparable(baseline: ComparableReport, new: ComparableReport, gate: Gate) -> list[str]:
    reasons: list[str] = []
    if baseline.content_hash != new.content_hash:
        reasons.append(
            "묶음의 내용 해시가 다르다"
            f"(기준 {_preview(baseline.content_hash)}, 새 {_preview(new.content_hash)})"
        )
    baseline_config = _search_config(baseline.config)
    new_config = _search_config(new.config)
    changed = [
        f"{name}(기준 {_show(baseline_config.get(name))}, 새 {_show(new_config.get(name))})"
        for name in sorted({*baseline_config, *new_config})
        if baseline_config.get(name) != new_config.get(name)
    ]
    if changed:
        reasons.append("구성이 다르다: " + ", ".join(changed))
    for name in gate.record_files:
        before = baseline.record_files.get(name)
        after = new.record_files.get(name)
        if before is None:
            reasons.append(
                f"기록 파일 {name}의 해시가 기준 보고서에 없어 견줄 수 없다"
                f"(기준 {_preview(before)}, 새 {_preview(after)})."
                " 기록을 읽거나 쓴 실행(--records read|write)의 보고서로 기준을 갱신한다"
            )
        elif before != after:
            reasons.append(
                f"기록 파일 {name}의 해시가 다르다(기준 {_preview(before)}, 새 {_preview(after)})"
            )
    return reasons


def _missing_rows(baseline: ComparableReport, new: ComparableReport, gate: Gate) -> list[str]:
    stage = gate.stage.value
    expected = [row.query_list for row in baseline.rows if row.stage == stage]
    if not expected:
        return [f"기준 보고서에 {stage} 단계 줄이 없다. 다른 게이트의 기준 보고서가 아닌지 본다"]
    present = {row.query_list for row in new.rows if row.stage == stage}
    return [
        f"새 보고서에 질의 목록 {name}의 {stage} 단계 줄이 없다."
        " 이 게이트에 맞는 실행의 보고서인지 본다"
        for name in expected
        if name not in present
    ]


def _search_config(config: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """검색의 숫자에 닿는 구성의 칸. 판정 칸 둘은 참고 숫자의 열쇠라서 뺀다."""
    return {name: value for name, value in config.items() if name not in JUDGE_CONFIG_KEYS}


def _preview(value: str | None) -> str:
    return "없음" if value is None else value[:_HASH_PREVIEW]


def _show(value: JsonValue | None) -> str:
    return "없음" if value is None else str(value)
