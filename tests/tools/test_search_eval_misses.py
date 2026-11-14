"""평가 도구 `tools/search_eval.py`의 놓친 까닭, 유형 표지와 필터 질의의 지표, `inspect`, `--config`
(티켓 search-eval 06).

뒤에는 실제 테스트 PostgreSQL과 TEI 스텁을 붙이고 도구의 `main(argv)`를 부른다. 놓친 질의의 탈락
지점은 스텁이 정하는 순위로 손으로 만든다. 조각이 열 개를 넘는 긴 문서에서 정답 조각은 질의와
직교하는 벡터(`_scripted`)나 가장 낮은 리랭크 점수를 받아 열 밖으로 밀린다.
"""

import json
from pathlib import Path

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.eval_bundle import (
    INDEX_CONFIG,
    PASSAGE,
    PASSAGE_B,
    passage_evidence,
    write_json,
    write_jsonl,
)
from tests.support.eval_run_support import (
    EVIDENCE,
    HUMAN,
    QUERY_A,
    QUERY_B,
    indexed_fast_report,
    indexed_full_report,
    make_bundle,
    prefer_b,
    read_report,
    run_fast,
    run_index,
)
from tests.support.eval_world import RERANKER_ENV, World
from tests.support.pdf_files import PdfPage, pdf_bytes, text_block
from tests.support.tei_stub import TeiStub

from rag_engine.domain.entities import JsonValue
from tools import search_eval

WORDS = [f"항목{number}번" for number in range(200)]
TARGET = WORDS[-1]
LONG_DOCUMENT = docx_bytes("휴가", " ".join(WORDS))
SPLIT_CONFIG: dict[str, JsonValue] = {
    **INDEX_CONFIG,
    "chunking": {"strategy": "structure_first", "max_tokens": 16, "overlap_tokens": 4},
}
ONE_CANDIDATE: dict[str, JsonValue] = {**INDEX_CONFIG, "search_candidates": 1}


def _scripted(text: str) -> list[float]:
    """정답 조각(`TARGET`이 든 글)은 질의와 직교하고 나머지는 질의와 같은 방향이라, 정답 조각이
    벡터 순위의 꼴찌가 된다."""
    vector = [0.0] * 16
    vector[1 if TARGET in text else 0] = 1.0
    return vector


def _long_bundle(tmp_path: Path) -> Path:
    return make_bundle(
        tmp_path,
        documents={"a.docx": LONG_DOCUMENT},
        evidence=[passage_evidence("q1", "a.docx", TARGET)],
        human=[{"evidence_id": "q1", "query": "질의"}],
        config=SPLIT_CONFIG,
    )


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def test_글귀가_조각의_경계에서_갈리면_no_matching_chunk이고_낱말_겹침을_함께_낸다(
    world: World, tmp_path: Path
) -> None:
    spanning = " ".join(WORDS[5:25])
    document = docx_bytes("휴가", " ".join(WORDS[:40]))
    bundle = make_bundle(
        tmp_path,
        documents={"a.docx": document},
        evidence=[
            passage_evidence("q1", "a.docx", spanning),
            passage_evidence("q2", "a.docx", spanning),
            passage_evidence("q3", "a.docx", spanning),
        ],
        human=[
            {"evidence_id": "q1", "query": spanning},
            {"evidence_id": "q2", "query": "!!!"},
            {"evidence_id": "q3", "query": "전혀 다른 말씀"},
        ],
        config=SPLIT_CONFIG,
    )

    report = indexed_fast_report(bundle, tmp_path / "out")

    assert report.index.chunks > 1
    assert [(row.evidence_id, row.cause) for row in report.misses] == [
        ("q1", "no_matching_chunk"),
        ("q2", "no_matching_chunk"),
        ("q3", "no_matching_chunk"),
    ]
    # 질의가 글귀 그대로면 겹침이 1이고, 키워드 토큰이 없으면 값이 없고, 겹치는 토큰이 없으면 0이다.
    assert report.miss("human", "q1").word_overlap == 1.0
    assert report.miss("human", "q2").word_overlap is None
    assert report.miss("human", "q3").word_overlap == 0.0
    # 겹침이 없는(null) 질의는 낱말 겹침이 0인 질의로 세지 않는다.
    assert report.miss_counts.missed == 3
    assert report.miss_counts.causes["no_matching_chunk"] == 3
    assert report.miss_counts.zero_overlap == 1
    # 보고서에는 식별자와 수만 실리고 질의나 글귀의 글은 실리지 않는다(원칙 V).
    text = (tmp_path / "out" / "report.json").read_text(encoding="utf-8")
    assert spanning not in text
    assert "전혀 다른 말씀" not in text


def test_후보_수를_줄인_구성은_후보에_들지_못한_조각을_not_in_candidates로_센다(
    world: World, tmp_path: Path
) -> None:
    """q3는 `a`의 글로 `b`의 글귀를 묻는다. 후보가 50이면 `b`의 조각이 벡터 2위로 닿고, 후보가 1이면
    `a`의 조각만 후보라 `b`의 조각이 후보에 들지 못한다."""
    human = [*HUMAN, {"evidence_id": "q3", "query": QUERY_A}]
    evidence = [*EVIDENCE, passage_evidence("q3", "sub/b.docx", PASSAGE_B)]
    bundle = make_bundle(tmp_path, evidence=evidence, human=human)
    assert run_index(bundle) == 0
    write_json(tmp_path / "one-candidate.json", ONE_CANDIDATE)

    assert run_fast(bundle, tmp_path / "default") == 0
    assert run_fast(bundle, tmp_path / "one", "--config", str(tmp_path / "one-candidate.json")) == 0

    default = read_report(tmp_path / "default")
    one = read_report(tmp_path / "one")
    assert default.config["search_candidates"] == 50
    assert one.config["search_candidates"] == 1
    assert default.eval_set.content_hash != one.eval_set.content_hash
    assert default.miss_counts.missed == 0
    assert default.row("human", "fused").hit_at_10 == pytest.approx(1.0)
    assert one.row("human", "fused").hit_at_10 == pytest.approx(2 / 3)
    assert [(row.evidence_id, row.cause) for row in one.misses] == [("q3", "not_in_candidates")]
    assert one.miss_counts.causes["not_in_candidates"] == 1


def test_config_파일이_없으면_색인도_평가도_하지_않고_1을_낸다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = make_bundle(tmp_path)
    missing = str(tmp_path / "없는-구성.json")

    assert run_index(bundle, "--config", missing) == 1
    assert "--config" in capsys.readouterr().err
    assert run_fast(bundle, tmp_path / "out", "--config", missing) == 1
    assert "--config" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_합친_순위가_열_밖이면_lost_in_fusion이다(
    world: World, tei_stub: TeiStub, tmp_path: Path
) -> None:
    """정답 조각은 벡터 후보에는 들지만 질의와 직교해 벡터 꼴찌다. 키워드 후보는 없어 합친 순위가
    벡터 순위와 같고, 조각이 열 개를 넘어 정답 조각이 열 밖이다."""
    tei_stub.embed_with = _scripted

    report = indexed_fast_report(_long_bundle(tmp_path), tmp_path / "out")

    assert report.index.chunks > 10
    assert report.row("human", "fused").hit_at_10 == 0.0
    assert [(row.evidence_id, row.cause) for row in report.misses] == [("q1", "lost_in_fusion")]
    assert report.miss_counts.causes["lost_in_fusion"] == 1
    assert report.miss_counts.causes["lost_in_rerank"] == 0


def test_리랭크_뒤_열_밖이면_lost_in_rerank이다(
    world: World, reranker_stub: TeiStub, reranker_url: str, tmp_path: Path
) -> None:
    """합친 뒤의 후보는 조각 전부(후보 수 50 이내)라 정답 조각도 리랭커에 들어간다. 리랭커가 정답
    조각에 가장 낮은 점수를 주면 리랭크 뒤 순위가 열 밖이다."""
    reranker_stub.score_with = lambda query, text: 0.0 if TARGET in text else 0.5
    del reranker_url

    report = indexed_full_report(_long_bundle(tmp_path), tmp_path / "out")

    assert report.index.chunks > 10
    assert report.row("human", "rerank").hit_at_10 == 0.0
    assert [(row.evidence_id, row.cause) for row in report.misses] == [("q1", "lost_in_rerank")]
    assert report.miss_counts.causes["lost_in_rerank"] == 1


def test_쪽으로_적은_기대_근거는_그_쪽을_덮은_조각에_닿고_없는_쪽은_낱말_겹침이_없다(
    world: World, tmp_path: Path
) -> None:
    pdf = pdf_bytes(
        [
            PdfPage(text_block("휴가 규정은 연차를 준다")),
            PdfPage(text_block("출장 규정은 실비를 준다")),
        ]
    )
    bundle = make_bundle(
        tmp_path,
        documents={"p.pdf": pdf},
        evidence=[
            {
                "id": "q1",
                "evidence": [{"kind": "page", "document": "p.pdf", "page": 2}],
                "tags": [],
            },
            {
                "id": "q2",
                "evidence": [{"kind": "page", "document": "p.pdf", "page": 3}],
                "tags": [],
            },
        ],
        human=[
            {"evidence_id": "q1", "query": "출장 규정은 실비를 준다"},
            {"evidence_id": "q2", "query": "출장 규정은 실비를 준다"},
        ],
    )

    report = indexed_fast_report(bundle, tmp_path / "out")

    # 2쪽에 걸친 조각이 있으니 q1은 닿는다. 3쪽은 없어 어떤 조각도 닿지 않는다.
    assert [(row.evidence_id, row.cause) for row in report.misses] == [("q2", "no_matching_chunk")]
    assert report.miss("human", "q2").word_overlap is None
    assert report.miss_counts.zero_overlap == 0
    assert report.row("human", "fused").hit_at_1 == pytest.approx(0.5)


def test_유형_표지와_필터_질의의_지표는_전체_지표와_따로_나온다(
    world: World, tmp_path: Path
) -> None:
    """q1에는 표지 `table`이 붙고 `b`의 글로 `a`의 글귀를 물어 `a`의 조각이 합친 순위 2위다. q2에는
    모든 문서를 지나는 필터가 붙고 자기 문서가 1위다. 마지막 단계(합친 뒤)의 전체 지표는 두 질의,
    표지 줄은 q1 하나, 필터 줄은 q2 하나만 센다."""
    evidence = [
        {
            "id": "q1",
            "evidence": [{"kind": "passage", "document": "a.docx", "passage": PASSAGE}],
            "tags": ["table"],
        },
        passage_evidence("q2", "sub/b.docx", PASSAGE_B),
    ]
    human = [
        {"evidence_id": "q1", "query": QUERY_B},
        {
            "evidence_id": "q2",
            "query": QUERY_B,
            "filter": {"updated_after": "2026-01-01T00:00:00+09:00"},
        },
    ]
    bundle = make_bundle(tmp_path, evidence=evidence, human=human)

    report = indexed_fast_report(bundle, tmp_path / "out")

    assert report.row("human", "fused").queries == 2
    assert report.row("human", "fused").hit_at_1 == pytest.approx(0.5)
    (tagged,) = report.by_tag
    assert (tagged.query_list, tagged.tag, tagged.stage, tagged.queries) == (
        "human",
        "table",
        "fused",
        1,
    )
    assert tagged.hit_at_1 == 0.0
    assert tagged.hit_at_3 == pytest.approx(1.0)
    (filtered,) = report.filtered
    assert (filtered.query_list, filtered.stage, filtered.queries) == ("human", "fused", 1)
    assert filtered.hit_at_1 == pytest.approx(1.0)
    # 필터를 지나는 조각이 둘뿐이라 정확 스캔도 후보 수(50)를 채우지 못한다. 그 몫은 모자란 것이
    # 아니다.
    assert (filtered.vector_short, filtered.vector_short_rate) == (0, 0.0)
    assert report.misses == []
    markdown = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    for heading in ("## 유형 표지별 지표", "## 필터가 붙은 질의", "## 놓친 질의", "## 사람 판정"):
        assert heading in markdown


def test_사람_판정은_확인된_줄만_까닭마다_센다(world: World, tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    write_jsonl(
        bundle / "miss-review.jsonl",
        [
            {"query_list": "human", "evidence_id": "q1", "cause": "vocabulary", "confirmed": True},
            {"query_list": "human", "evidence_id": "q2", "cause": "other", "confirmed": False},
        ],
    )

    report = indexed_fast_report(bundle, tmp_path / "out")

    assert report.human_causes == {
        "multi_document": 0,
        "no_context": 0,
        "other": 0,
        "table_or_figure": 0,
        "vocabulary": 1,
    }


def test_inspect는_질의와_근거와_단계별_상위_조각의_글을_표준_출력에만_찍는다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = make_bundle(tmp_path)
    assert run_index(bundle) == 0
    before = _snapshot(tmp_path)
    capsys.readouterr()

    assert search_eval.main(["inspect", str(bundle), "human", "q1"]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    for expected in (QUERY_A, PASSAGE, "## vector", "## keyword", "## fused"):
        assert expected in captured.out
    assert "## rerank" not in captured.out
    assert "마지막 단계에서 닿았다" in captured.out
    assert "1. 닿음" in captured.out
    # 질의와 조각의 글은 표준 출력에만 가고 파일은 하나도 새로 쓰지 않는다.
    assert _snapshot(tmp_path) == before


def test_inspect_through_rerank는_리랭크_뒤_순위와_점수를_더한다(
    world: World,
    reranker_stub: TeiStub,
    reranker_url: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reranker_stub.score_with = prefer_b
    del reranker_url
    bundle = make_bundle(tmp_path)
    assert run_index(bundle) == 0
    capsys.readouterr()

    assert search_eval.main(["inspect", str(bundle), "human", "q1", "--through", "rerank"]) == 0

    out = capsys.readouterr().out
    assert "## rerank" in out
    # 리랭커가 `b`의 조각을 높이 쳐 q1이 기대하는 `a`의 조각은 2위로 밀린다.
    assert "1. 닿지 않음 점수 0.900" in out
    assert "2. 닿음 점수 0.200" in out


def test_inspect_through_rerank는_리랭커_끝점이_없으면_이름을_알리고_1을_낸다(
    world: World,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = make_bundle(tmp_path)
    assert run_index(bundle) == 0
    monkeypatch.delenv(RERANKER_ENV, raising=False)
    capsys.readouterr()

    assert search_eval.main(["inspect", str(bundle), "human", "q1", "--through", "rerank"]) == 1

    captured = capsys.readouterr()
    assert RERANKER_ENV in captured.err
    assert captured.out == ""


def test_inspect는_없는_질의를_이유와_함께_1로_거부하고_아무것도_찍지_않는다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = make_bundle(tmp_path)
    assert run_index(bundle) == 0
    capsys.readouterr()

    assert search_eval.main(["inspect", str(bundle), "human", "q9"]) == 1

    captured = capsys.readouterr()
    assert "q9" in captured.err
    assert captured.out == ""


def test_inspect도_config의_후보_수를_따르고_놓친_까닭을_찍는다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    human = [*HUMAN, {"evidence_id": "q3", "query": QUERY_A}]
    evidence = [*EVIDENCE, passage_evidence("q3", "sub/b.docx", PASSAGE_B)]
    bundle = make_bundle(tmp_path, evidence=evidence, human=human)
    assert run_index(bundle) == 0
    write_json(tmp_path / "one-candidate.json", ONE_CANDIDATE)
    capsys.readouterr()

    assert search_eval.main(["inspect", str(bundle), "human", "q3"]) == 0
    assert "마지막 단계에서 닿았다" in capsys.readouterr().out
    config = str(tmp_path / "one-candidate.json")
    assert search_eval.main(["inspect", str(bundle), "human", "q3", "--config", config]) == 0

    assert "놓친 까닭: not_in_candidates" in capsys.readouterr().out


def test_인자_없는_inspect와_알_수_없는_through는_사용법_오류_2다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert search_eval.main(["inspect"]) == 2
    assert search_eval.main(["inspect", "묶음", "human", "q1", "--through", "vector"]) == 2
    assert capsys.readouterr().err != ""


def test_report_json의_config는_쓴_구성이고_묶음의_파일은_바뀌지_않는다(
    world: World, tmp_path: Path
) -> None:
    bundle = make_bundle(tmp_path)
    assert run_index(bundle) == 0
    before = (bundle / "config.json").read_bytes()
    write_json(tmp_path / "one-candidate.json", ONE_CANDIDATE)

    assert run_fast(bundle, tmp_path / "out", "--config", str(tmp_path / "one-candidate.json")) == 0

    raw: JsonValue = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    config = raw["config"]
    assert isinstance(config, dict)
    assert config["search_candidates"] == 1
    assert (bundle / "config.json").read_bytes() == before
