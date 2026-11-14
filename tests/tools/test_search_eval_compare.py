"""평가 도구 `tools/search_eval.py compare`의 표면 시험(티켓 search-eval 08, 명세 "CI 게이트와 기준
보고서"의 `compare`).

손으로 지은 보고서 파일을 `main(argv)`에 넘겨 종료 코드와 표준 출력, 표준 오류를 본다.
데이터베이스와 TEI는 쓰지 않는다. 기록 파일의 해시가 진짜 `run`에서 나오는 길은
`test_search_eval_compare_records.py`가 본다.
"""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from tests.support.eval_bundle import make_folder_link

from rag_engine.domain.entities import JsonValue
from tools import search_eval

CONFIG: dict[str, JsonValue] = {
    "embedding_model": "m",
    "embedding_dimensions": 16,
    "reranker_model": "r",
    "chunking": {"strategy": "structure_first", "max_tokens": 512, "overlap_tokens": 64},
    "search_candidates": 50,
    "tei_version": "1.9.4",
    "judge_model": "judge-a",
    "judge_prompt_version": "1",
}
RECORD_FILES = {
    "records/chunk-embeddings.keys": "c1",
    "records/chunk-embeddings.f32": "c2",
    "records/query-embeddings.keys": "q1",
    "records/query-embeddings.f32": "q2",
    "records/records.json": "m1",
}
FULL_RECORD_FILES = {**RECORD_FILES, "records/rerank.jsonl": "r1"}


def _row(query_list: str, stage: str, hit_at_5: float, mrr: float) -> dict[str, JsonValue]:
    return {"query_list": query_list, "stage": stage, "hit_at_5": hit_at_5, "mrr": mrr}


def _report(
    rows: Sequence[dict[str, JsonValue]],
    *,
    content_hash: str = "h1" * 32,
    config: dict[str, JsonValue] | None = None,
    files: dict[str, str] | None = None,
    commit: str | None = "abc",
) -> dict[str, JsonValue]:
    """`run`이 쓰는 보고서에서 `compare`가 읽는 칸과, 읽지 않는다는 것을 보이려는 몇 칸."""
    return {
        "format_version": "1.0.0",
        "eval_set": {"name": "set", "content_hash": content_hash},
        "config": CONFIG if config is None else config,
        "rows": list(rows),
        "records": {
            "read": 4,
            "computed": 0,
            "files": FULL_RECORD_FILES if files is None else files,
        },
        "meta": {"run_at": "2026-11-15T00:00:00+00:00", "commit": commit},
    }


def _write(path: Path, value: JsonValue) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _compare(gate: str, report: Path, bundle: Path) -> int:
    return search_eval.main(["compare", "--gate", gate, str(report), str(bundle)])


def _setup(
    tmp_path: Path,
    baseline: dict[str, JsonValue] | None,
    new: dict[str, JsonValue],
    *,
    gate: str = "fast",
) -> tuple[Path, Path]:
    """묶음 폴더와 새 보고서 파일의 경로. `baseline`이 `None`이면 기준 보고서 파일을 두지 않는다."""
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    if baseline is not None:
        _write(bundle / f"baseline-{gate}.json", baseline)
    return bundle, _write(tmp_path / "out" / "report.json", new)


FUSED_80 = [_row("human", "fused", 0.8, 0.5), _row("keyword", "fused", 0.7, 0.4)]


def test_하락폭_안의_하락은_통과한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rows = [_row("human", "fused", 0.79, 0.49), _row("keyword", "fused", 0.7, 0.4)]
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(rows))

    code = _compare("fast", report, bundle)

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "통과" in captured.out


@pytest.mark.parametrize(
    ("baseline_value", "new_value"),
    [(0.82, 0.80), (0.5, 0.48), (1.0, 0.98)],
)
def test_상위_5_적중률이_정확히_하락폭만큼_떨어지면_통과한다(
    tmp_path: Path, baseline_value: float, new_value: float
) -> None:
    bundle, report = _setup(
        tmp_path,
        _report([_row("human", "fused", baseline_value, 0.5)]),
        _report([_row("human", "fused", new_value, 0.5)]),
    )

    assert _compare("fast", report, bundle) == 0


def test_mrr이_정확히_하락폭만큼_떨어지면_통과한다(tmp_path: Path) -> None:
    bundle, report = _setup(
        tmp_path,
        _report([_row("human", "fused", 0.8, 0.31)]),
        _report([_row("human", "fused", 0.8, 0.29)]),
    )

    assert _compare("fast", report, bundle) == 0


def test_하락폭을_넘는_하락은_실패하고_질의_목록과_지표와_값과_차를_표준_오류에_찍는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [_row("human", "fused", 0.8, 0.5), _row("keyword", "fused", 0.64, 0.4)]
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(rows))

    code = _compare("fast", report, bundle)

    captured = capsys.readouterr()
    assert code == 1, f"하락폭을 넘는 하락의 종료 코드: {code}"
    lines = captured.err.splitlines()
    assert "| 질의 목록 | 지표 | 기준값 | 새 값 | 차 |" in lines
    assert "| keyword | hit_at_5 | 0.7 | 0.64 | 0.06 |" in lines
    assert "human" not in captured.err, "하락하지 않은 질의 목록은 표에 싣지 않는다"


def test_mrr이_하락폭을_넘어_떨어지면_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, report = _setup(
        tmp_path,
        _report([_row("human", "fused", 0.8, 0.5)]),
        _report([_row("human", "fused", 0.8, 0.479)]),
    )

    code = _compare("fast", report, bundle)

    assert code == 1
    assert "mrr" in capsys.readouterr().err


def test_하락폭을_넘어_오르면_통과하고_기준_보고서를_갱신하라고_알린다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [_row("human", "fused", 0.9, 0.5), _row("keyword", "fused", 0.7, 0.4)]
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(rows))

    code = _compare("fast", report, bundle)

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "baseline-fast.json" in captured.out
    assert "갱신" in captured.out
    assert "human" in captured.out


def test_오르지_않은_보고서는_갱신_안내를_내지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))

    assert _compare("fast", report, bundle) == 0
    assert "갱신" not in capsys.readouterr().out


OTHER_CHUNKING: dict[str, JsonValue] = {"strategy": "x", "max_tokens": 1, "overlap_tokens": 0}


@pytest.mark.parametrize(
    ("content_hash", "config", "expected"),
    [
        ("h2" * 32, CONFIG, "내용 해시"),
        ("h1" * 32, {**CONFIG, "search_candidates": 10}, "search_candidates"),
        ("h1" * 32, {**CONFIG, "chunking": OTHER_CHUNKING}, "chunking"),
    ],
)
def test_묶음의_해시나_구성이_다르면_숫자가_같아도_견주지_않고_실패한다(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    content_hash: str,
    config: dict[str, JsonValue],
    expected: str,
) -> None:
    changed = _report(FUSED_80, content_hash=content_hash, config=config)
    bundle, report = _setup(tmp_path, _report(FUSED_80), changed)

    code = _compare("fast", report, bundle)

    err = capsys.readouterr().err
    assert code == 1
    assert expected in err
    assert "기준 보고서를 갱신" in err
    assert "baseline-fast.json" in err


def test_판정_칸_둘만_다른_구성의_보고서와는_견준다(tmp_path: Path) -> None:
    judged = {**CONFIG, "judge_model": "judge-b", "judge_prompt_version": "9"}
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80, config=judged))

    assert _compare("fast", report, bundle) == 0


def test_보고서의_meta는_견주지_않는다(tmp_path: Path) -> None:
    bundle, report = _setup(
        tmp_path, _report(FUSED_80, commit="aaa"), _report(FUSED_80, commit=None)
    )

    assert _compare("fast", report, bundle) == 0


def test_기준_보고서가_없으면_견주지_않고_실패하며_만드는_길을_알린다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, report = _setup(tmp_path, None, _report(FUSED_80))

    code = _compare("fast", report, bundle)

    err = capsys.readouterr().err
    assert code == 1
    assert "baseline-fast.json" in err
    assert "없다" in err


@pytest.mark.parametrize(
    "name",
    [
        "records/chunk-embeddings.keys",
        "records/chunk-embeddings.f32",
        "records/query-embeddings.keys",
        "records/query-embeddings.f32",
    ],
)
def test_빠른_게이트는_임베딩_기록_파일의_해시가_다르면_견주지_않고_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    changed = _report(FUSED_80, files={**FULL_RECORD_FILES, name: "tampered"})
    bundle, report = _setup(tmp_path, _report(FUSED_80), changed)

    code = _compare("fast", report, bundle)

    err = capsys.readouterr().err
    assert code == 1
    assert name in err
    assert "기록 파일" in err


def test_조각_임베딩_기록의_해시가_기준_보고서에_없으면_견주지_않고_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """07이 남긴 한계: 조각 임베딩의 해시가 없던 때의 기준 보고서는 갱신해야 한다."""
    without = {name: value for name, value in RECORD_FILES.items() if "chunk" not in name}
    bundle, report = _setup(tmp_path, _report(FUSED_80, files=without), _report(FUSED_80))

    code = _compare("fast", report, bundle)

    err = capsys.readouterr().err
    assert code == 1
    assert "records/chunk-embeddings.keys" in err
    assert "기준 없음" in err


def test_빠른_게이트는_리랭크_기록의_해시를_보지_않고_전체_게이트는_본다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rerank_changed = {**FULL_RECORD_FILES, "records/rerank.jsonl": "other"}
    both = [_row("human", "fused", 0.8, 0.5), _row("human", "rerank", 0.9, 0.6)]
    fast_bundle, fast_report = _setup(
        tmp_path / "fast", _report(both), _report(both, files=rerank_changed)
    )
    full_bundle, full_report = _setup(
        tmp_path / "full", _report(both), _report(both, files=rerank_changed), gate="full"
    )

    assert _compare("fast", fast_report, fast_bundle) == 0
    code = _compare("full", full_report, full_bundle)

    err = capsys.readouterr().err
    assert code == 1
    assert "records/rerank.jsonl" in err


def test_게이트마다_자기_기준_파일과_자기_단계_줄을_본다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = [_row("human", "fused", 0.8, 0.5), _row("human", "rerank", 0.9, 0.6)]
    fused_dropped = [_row("human", "fused", 0.5, 0.5), _row("human", "rerank", 0.9, 0.6)]
    rerank_dropped = [_row("human", "fused", 0.8, 0.5), _row("human", "rerank", 0.6, 0.6)]
    fast_bundle, fast_report = _setup(
        tmp_path / "a", _report(baseline), _report(rerank_dropped), gate="fast"
    )
    full_bundle, full_report = _setup(
        tmp_path / "b", _report(baseline), _report(fused_dropped), gate="full"
    )
    # 한 묶음에 두 기준 파일이 모두 있어도 게이트가 제 파일만 읽는다.
    _write(fast_bundle / "baseline-full.json", _report(fused_dropped))
    _write(full_bundle / "baseline-fast.json", _report(rerank_dropped))

    assert _compare("fast", fast_report, fast_bundle) == 0
    assert _compare("full", full_report, full_bundle) == 0
    capsys.readouterr()
    # 하락은 각 게이트가 보는 줄에서만 난다. 표에 그 줄의 기준값과 새 값이 찍힌다.
    assert _compare("full", fast_report, fast_bundle) == 1
    assert "| human | hit_at_5 | 0.9 | 0.6 | 0.3 |" in capsys.readouterr().err
    assert _compare("fast", full_report, full_bundle) == 1
    assert "| human | hit_at_5 | 0.8 | 0.5 | 0.3 |" in capsys.readouterr().err


def test_새_보고서에_게이트가_보는_단계가_없으면_견주지_않고_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = _report([_row("human", "rerank", 0.9, 0.6)])
    bundle, report = _setup(tmp_path, baseline, _report(FUSED_80), gate="full")

    code = _compare("full", report, bundle)

    err = capsys.readouterr().err
    assert code == 1
    assert "rerank" in err


def test_보고서_자리에_보고서_폴더를_주면_그_안의_report_json을_읽는다(tmp_path: Path) -> None:
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))

    code = _compare("fast", report.parent, bundle)

    assert code == 0, f"보고서 폴더를 준 실행의 종료 코드: {code}"


def test_compare는_묶음의_records_json을_읽지_않는다(tmp_path: Path) -> None:
    """요청 지문과 TEI 판의 불일치는 `validate`의 몫이다(빠른 게이트는 `validate`를 `run`보다
    앞에 둔다). `compare`는 보고서에 적힌 기록 파일의 해시만 견준다."""
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))
    (bundle / "records").mkdir()
    (bundle / "records" / "records.json").write_text("이것은 JSON이 아니다", encoding="utf-8")

    assert _compare("fast", report, bundle) == 0


def test_기준_보고서가_묶음_밖을_가리키는_링크이면_읽지_않고_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, report = _setup(tmp_path, None, _report(FUSED_80))
    outside = tmp_path / "outside"
    outside.mkdir()
    make_folder_link(bundle / "baseline-fast.json", outside)

    code = _compare("fast", report, bundle)

    err = capsys.readouterr().err
    assert code == 1
    assert "묶음 폴더 밖" in err


def test_묶음_폴더가_없으면_실패한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, report = _setup(tmp_path, None, _report(FUSED_80))

    code = _compare("fast", report, tmp_path / "없는-묶음")

    assert code == 1
    assert "묶음 폴더" in capsys.readouterr().err


def test_보고서_파일이_없으면_실패한다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle, _ = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))

    code = _compare("fast", tmp_path / "없는" / "report.json", bundle)

    assert code == 1
    err = capsys.readouterr().err
    assert "읽지 못했다(FileNotFoundError)" in err
    assert "기준 보고서" not in err.split("읽지 못했다")[0]


@pytest.mark.parametrize("text", ["JSON이 아니다", "[]", '{"format_version": "1.0.0"}'])
def test_읽을_수_없는_보고서는_숫자를_견주지_않고_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))
    report.write_text(text, encoding="utf-8")

    code = _compare("fast", report, bundle)

    assert code == 1
    assert "읽지 못했다" in capsys.readouterr().err


@pytest.mark.parametrize("metric", ["hit_at_5", "mrr"])
def test_숫자가_NaN인_보고서는_형식이_맞지_않아_읽지_못한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], metric: str
) -> None:
    row = _row("human", "fused", 0.8, 0.5)
    row[metric] = float("nan")
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report([row]))

    code = _compare("fast", report, bundle)

    assert code == 1
    assert "읽지 못했다(`run`이 쓴 보고서의 형식이 아니다)" in capsys.readouterr().err


@pytest.mark.parametrize(("baseline_hits", "new_hits", "queries"), [(4, 1, 150), (8, 2, 300)])
def test_맞힌_수를_질의_수로_나눈_값이_정확히_하락폭만큼_떨어지면_통과한다(
    tmp_path: Path, baseline_hits: int, new_hits: int, queries: int
) -> None:
    """보고서 파일에 적힌 `k/n` 꼴의 값(끝자리에 표현 오차가 있는 값)을 파일로 읽는 길로 본다."""
    bundle, report = _setup(
        tmp_path,
        _report([_row("human", "fused", baseline_hits / queries, 0.5)]),
        _report([_row("human", "fused", new_hits / queries, 0.5)]),
    )

    assert _compare("fast", report, bundle) == 0


def test_읽을_수_없는_기준_보고서도_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))
    (bundle / "baseline-fast.json").write_text("{", encoding="utf-8")

    code = _compare("fast", report, bundle)

    assert code == 1
    assert "baseline-fast.json" in capsys.readouterr().err


@pytest.mark.parametrize("gate_arguments", [[], ["--gate", "slow"]])
def test_게이트가_없거나_잘못되면_종료_코드_2다(tmp_path: Path, gate_arguments: list[str]) -> None:
    bundle, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))

    assert search_eval.main(["compare", *gate_arguments, str(report), str(bundle)]) == 2


def test_보고서와_묶음_폴더_인자가_모자라면_종료_코드_2다(tmp_path: Path) -> None:
    _, report = _setup(tmp_path, _report(FUSED_80), _report(FUSED_80))

    assert search_eval.main(["compare", "--gate", "fast", str(report)]) == 2
