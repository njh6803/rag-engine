"""기준 보고서와의 견줌 규칙(티켓 search-eval 08, 명세 "CI 게이트와 기준 보고서").

보고서를 파일로 읽는 길은 `tests/tools/test_search_eval_compare.py`가 본다. 여기서는 읽어 낸 값
위에서 돌아가는 순수한 판정만 본다.
"""

import pytest

from rag_engine.app.eval_compare import (
    ComparableReport,
    Gate,
    MetricRow,
    compare_reports,
)
from rag_engine.domain.entities import JsonValue

CONFIG: dict[str, JsonValue] = {
    "embedding_model": "m",
    "chunking": {"strategy": "structure_first", "max_tokens": 512},
    "judge_model": "judge-a",
    "judge_prompt_version": "1",
}
FAST_FILES = {
    "records/chunk-embeddings.keys": "c1",
    "records/chunk-embeddings.f32": "c2",
    "records/query-embeddings.keys": "q1",
    "records/query-embeddings.f32": "q2",
    "records/records.json": "m1",
}
FULL_FILES = {**FAST_FILES, "records/rerank.jsonl": "r1"}


def _report(
    *,
    hit_at_5: float = 0.8,
    mrr: float = 0.5,
    stage: str = "fused",
    query_list: str = "human",
    content_hash: str = "h1",
    config: dict[str, JsonValue] | None = None,
    files: dict[str, str] | None = None,
) -> ComparableReport:
    return ComparableReport(
        content_hash=content_hash,
        config=CONFIG if config is None else config,
        record_files=FAST_FILES if files is None else files,
        rows=(MetricRow(query_list, stage, hit_at_5, mrr),),
    )


@pytest.mark.parametrize(
    ("baseline", "new"),
    [(0.82, 0.80), (0.80, 0.78), (0.9, 0.88), (0.5, 0.48), (1.0, 0.98), (0.7, 0.68)],
)
def test_상위_5_적중률이_정확히_하락폭만큼_떨어지면_통과한다(baseline: float, new: float) -> None:
    result = compare_reports(_report(hit_at_5=baseline), _report(hit_at_5=new), Gate.FAST)

    assert result.passed, f"기준 {baseline}, 새 값 {new}: {result.drops}"


@pytest.mark.parametrize("queries", [50, 100, 150, 300, 450, 1000])
def test_정수를_질의_수로_나눈_값끼리_정확히_2퍼센트포인트_떨어지면_통과한다(queries: int) -> None:
    """실제 보고서의 값은 `맞힌 수 / 질의 수`라서 마지막 자리에 표현 오차가 실린다. 질의 수마다 모든
    맞힌 수로 정확히 하락폭만큼 떨어진 쌍을 견주고, 하나라도 실패로 읽히면 어긋난다."""
    step = queries // 50  # 질의 수의 2%
    failed = [
        (hits, hits - step)
        for hits in range(step, queries + 1)
        if not compare_reports(
            _report(hit_at_5=hits / queries),
            _report(hit_at_5=(hits - step) / queries),
            Gate.FAST,
        ).passed
    ]

    assert failed == [], f"질의 {queries}개에서 정확히 2%p 떨어진 쌍이 실패로 읽혔다: {failed[:5]}"


@pytest.mark.parametrize("queries", [150, 300])
def test_질의_하나가_더_틀려_하락폭을_넘으면_실패한다(queries: int) -> None:
    step = queries // 50
    result = compare_reports(
        _report(hit_at_5=(step + 1) / queries), _report(hit_at_5=0.0), Gate.FAST
    )

    (drop,) = result.drops
    assert drop.metric == "hit_at_5"


@pytest.mark.parametrize(("baseline", "new"), [(0.82, 0.799), (0.5, 0.479), (1.0, 0.9799)])
def test_상위_5_적중률이_하락폭을_넘어_떨어지면_실패한다(baseline: float, new: float) -> None:
    result = compare_reports(_report(hit_at_5=baseline), _report(hit_at_5=new), Gate.FAST)

    (drop,) = result.drops
    assert (drop.query_list, drop.metric) == ("human", "hit_at_5")
    assert not result.passed


@pytest.mark.parametrize(("baseline", "new"), [(0.5, 0.48), (0.31, 0.29)])
def test_mrr이_정확히_하락폭만큼_떨어지면_통과한다(baseline: float, new: float) -> None:
    assert compare_reports(_report(mrr=baseline), _report(mrr=new), Gate.FAST).passed


def test_mrr이_하락폭을_넘어_떨어지면_실패한다() -> None:
    result = compare_reports(_report(mrr=0.5), _report(mrr=0.479), Gate.FAST)

    (drop,) = result.drops
    assert drop.metric == "mrr"
    assert drop.baseline == pytest.approx(0.5)
    assert drop.new == pytest.approx(0.479)
    assert drop.difference == pytest.approx(0.021)


def test_질의_목록마다_따로_견준다() -> None:
    baseline = ComparableReport(
        content_hash="h1",
        config=CONFIG,
        record_files=FAST_FILES,
        rows=(MetricRow("human", "fused", 0.8, 0.5), MetricRow("keyword", "fused", 0.7, 0.4)),
    )
    new = ComparableReport(
        content_hash="h1",
        config=CONFIG,
        record_files=FAST_FILES,
        rows=(MetricRow("human", "fused", 0.8, 0.5), MetricRow("keyword", "fused", 0.6, 0.4)),
    )

    result = compare_reports(baseline, new, Gate.FAST)

    assert [(drop.query_list, drop.metric) for drop in result.drops] == [("keyword", "hit_at_5")]


def test_하락폭을_넘어_오르면_통과하고_오른_숫자를_알린다() -> None:
    result = compare_reports(_report(hit_at_5=0.7), _report(hit_at_5=0.73), Gate.FAST)

    assert result.passed
    (rise,) = result.rises
    assert (rise.query_list, rise.metric) == ("human", "hit_at_5")


def test_정확히_하락폭만큼_오르면_알리지_않는다() -> None:
    result = compare_reports(_report(hit_at_5=0.78), _report(hit_at_5=0.80), Gate.FAST)

    assert result.passed
    assert result.rises == ()


def test_빠른_게이트는_합친_뒤_줄을_전체_게이트는_리랭크_뒤_줄을_본다() -> None:
    both = (MetricRow("human", "fused", 0.8, 0.5), MetricRow("human", "rerank", 0.9, 0.6))
    baseline = ComparableReport("h1", CONFIG, FULL_FILES, both)
    rerank_dropped = ComparableReport(
        "h1",
        CONFIG,
        FULL_FILES,
        (MetricRow("human", "fused", 0.8, 0.5), MetricRow("human", "rerank", 0.5, 0.6)),
    )

    assert compare_reports(baseline, rerank_dropped, Gate.FAST).passed
    (drop,) = compare_reports(baseline, rerank_dropped, Gate.FULL).drops
    assert drop.stage == "rerank"


def test_내용_해시가_다르면_숫자를_견주지_않고_견줄_수_없다고_낸다() -> None:
    result = compare_reports(
        _report(hit_at_5=0.9), _report(hit_at_5=0.1, content_hash="h2"), Gate.FAST
    )

    assert not result.passed
    assert result.drops == ()
    assert any("내용 해시" in reason for reason in result.incomparable)


def test_구성이_다르면_견줄_수_없다고_낸다() -> None:
    changed: dict[str, JsonValue] = {**CONFIG, "chunking": {"strategy": "x", "max_tokens": 256}}

    result = compare_reports(_report(), _report(config=changed), Gate.FAST)

    (reason,) = result.incomparable
    assert "구성" in reason
    assert "chunking" in reason


def test_판정_칸_둘만_다른_구성과는_견준다() -> None:
    judged: dict[str, JsonValue] = {
        **CONFIG,
        "judge_model": "judge-b",
        "judge_prompt_version": "2",
    }

    result = compare_reports(_report(), _report(config=judged), Gate.FAST)

    assert result.incomparable == ()
    assert result.passed


@pytest.mark.parametrize(
    "name",
    [
        "records/chunk-embeddings.keys",
        "records/chunk-embeddings.f32",
        "records/query-embeddings.keys",
        "records/query-embeddings.f32",
    ],
)
def test_빠른_게이트는_임베딩_기록_파일의_해시가_다르면_견줄_수_없다고_낸다(name: str) -> None:
    changed = {**FAST_FILES, name: "other"}

    result = compare_reports(_report(), _report(files=changed), Gate.FAST)

    (reason,) = result.incomparable
    assert name in reason


def test_빠른_게이트는_리랭크_기록과_기록_목록_파일의_해시를_보지_않는다() -> None:
    baseline = _report(files={**FULL_FILES})
    changed = _report(
        files={**FULL_FILES, "records/rerank.jsonl": "x", "records/records.json": "y"}
    )

    assert compare_reports(baseline, changed, Gate.FAST).incomparable == ()


def test_전체_게이트는_리랭크_기록의_해시도_본다() -> None:
    baseline = _report(stage="rerank", files=FULL_FILES)
    changed = _report(stage="rerank", files={**FULL_FILES, "records/rerank.jsonl": "x"})

    (reason,) = compare_reports(baseline, changed, Gate.FULL).incomparable

    assert "records/rerank.jsonl" in reason


def test_한쪽에만_기록_파일이_있으면_견줄_수_없다고_낸다() -> None:
    without = {name: digest for name, digest in FAST_FILES.items() if "chunk" not in name}

    result = compare_reports(_report(), _report(files=without), Gate.FAST)

    assert len(result.incomparable) == 2
    assert all("chunk-embeddings" in reason for reason in result.incomparable)
    assert all("새 없음" in reason for reason in result.incomparable)


def test_견줄_수_없는_까닭은_모두_모아_낸다() -> None:
    changed: dict[str, JsonValue] = {**CONFIG, "search_candidates": 10}

    result = compare_reports(
        _report(),
        _report(content_hash="h2", config=changed, files={**FAST_FILES, "records/x": "1"}),
        Gate.FAST,
    )

    assert len(result.incomparable) == 2


def test_새_보고서에_그_게이트가_보는_단계_줄이_없으면_견줄_수_없다고_낸다() -> None:
    result = compare_reports(_report(stage="rerank"), _report(stage="fused"), Gate.FULL)

    assert not result.passed
    assert any("rerank" in reason for reason in result.incomparable)


def test_기준_보고서에_그_게이트가_보는_단계_줄이_없으면_견줄_수_없다고_낸다() -> None:
    result = compare_reports(_report(stage="fused"), _report(stage="fused"), Gate.FULL)

    assert not result.passed, f"그 단계 줄이 없는데 통과했다: {result.incomparable}"
    assert any("기준 보고서" in reason for reason in result.incomparable)


def test_새_보고서에_기준_보고서의_질의_목록이_없으면_견줄_수_없다고_낸다() -> None:
    result = compare_reports(_report(query_list="human"), _report(query_list="keyword"), Gate.FAST)

    assert not result.passed
    assert any("human" in reason for reason in result.incomparable)
