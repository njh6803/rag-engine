"""평가 도구 `tools/search_eval.py`의 `run --through fused`(티켓 search-eval 04).

뒤에는 실제 테스트 PostgreSQL과 TEI 스텁을 붙이고 도구의 `main(argv)`를 부른다. 보고서의 숫자는
스텁의 결정적 벡터(낱말 주머니)로 기대 근거의 순위가 정해지는 작은 묶음에서 손으로 계산한 값과
견준다. 문서가 둘이고 조각이 하나씩이라(짧은 글) 단계의 순위는 이렇다. 질의가 문서 `a`의 글과 같은
낱말이면 `a`의 조각이 벡터 1위이고 `b`의 조각이 2위다. 키워드는 그 질의의 토큰이 든 조각만 후보가
되고, 합친 뒤는 두 쪽의 합집합을 RRF 순서로 줄 세운다(두 쪽에 다 든 조각이 앞선다).
"""

import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path

import psycopg
import pytest
from pydantic import BaseModel, ConfigDict
from tests.support.docx_files import docx_bytes
from tests.support.eval_bundle import (
    HEADER,
    HEADER_QUERY_LISTS,
    INDEX_CONFIG,
    PASSAGE,
    PASSAGE_B,
    passage_evidence,
    write_indexable_bundle,
    write_json,
    write_jsonl,
)
from tests.support.eval_world import DATA_DIR_ENV, DATABASE_ENV, EMBEDDING_ENV, World
from tests.support.tei_server import serve_stub
from tests.support.tei_stub import TeiStub

from rag_engine.adapters.ingest_command import ingest_path
from rag_engine.adapters.settings import Settings
from rag_engine.domain.entities import JsonValue
from tools import search_eval

DOCUMENT_A = docx_bytes("휴가", PASSAGE + ".")
DOCUMENT_B = docx_bytes("출장", PASSAGE_B + ".")
DOCUMENTS = {"a.docx": DOCUMENT_A, "sub/b.docx": DOCUMENT_B}
# 문서의 제목과 글을 그대로 옮긴 질의: 낱말 주머니가 그 문서의 조각과 같아 그 조각이 벡터 1위다.
QUERY_A = f"휴가 {PASSAGE}."
QUERY_B = f"출장 {PASSAGE_B}."
EVIDENCE = [
    passage_evidence("q1", "a.docx", PASSAGE),
    passage_evidence("q2", "sub/b.docx", PASSAGE_B),
]
HUMAN = [
    {"evidence_id": "q1", "query": QUERY_A},
    {"evidence_id": "q2", "query": QUERY_B},
]
EMBEDDINGS = "/v1/embeddings"


class _Strict(BaseModel):
    """보고서의 칸을 모두 이름으로 받는다. 모르는 칸이 있으면 검증이 실패해 칸의 목록을 고정한다."""

    model_config = ConfigDict(extra="forbid")


class _EvalSet(_Strict):
    name: str
    format_version: str
    content_hash: str
    documents: int
    questions: int
    queries: int


class _Index(_Strict):
    schema_version: int
    embedding_model: str
    embedding_dimensions: int
    chunking_hash: str
    tokenizer_version: str
    chunks: int


class _Row(_Strict):
    query_list: str
    stage: str
    queries: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    hit_at_10: float
    mrr: float
    recall: float
    ndcg_at_10: float
    ndcg_truncated: int


class _Meta(_Strict):
    run_at: str
    commit: str | None


class _Report(_Strict):
    format_version: str
    eval_set: _EvalSet
    config: dict[str, JsonValue]
    index: _Index
    stages: list[str]
    rows: list[_Row]
    meta: _Meta

    def row(self, query_list: str, stage: str) -> _Row:
        (found,) = [r for r in self.rows if r.query_list == query_list and r.stage == stage]
        return found


def _bundle(
    tmp_path: Path,
    name: str = "bundle",
    *,
    documents: dict[str, bytes] | None = None,
    evidence: Sequence[JsonValue] = EVIDENCE,
    human: Sequence[JsonValue] = HUMAN,
    keyword: Sequence[JsonValue] | None = None,
    config: dict[str, JsonValue] | None = None,
) -> Path:
    root = write_indexable_bundle(
        tmp_path / name,
        DOCUMENTS if documents is None else documents,
        evidence,
        config=INDEX_CONFIG if config is None else config,
    )
    write_jsonl(root / "queries-human.jsonl", human)
    if keyword is not None:
        write_json(root / "eval-set.json", {**HEADER, "query_lists": HEADER_QUERY_LISTS})
        write_jsonl(root / "queries-keyword.jsonl", keyword)
    return root


def _index(bundle: Path) -> int:
    return search_eval.main(["index", str(bundle)])


def _run(bundle: Path, out: Path, *extra: str) -> int:
    return search_eval.main(["run", str(bundle), "--through", "fused", "--out", str(out), *extra])


def _report(out: Path) -> _Report:
    return _Report.model_validate_json((out / "report.json").read_text(encoding="utf-8"))


def _indexed_run(world: World, bundle: Path, out: Path) -> _Report:
    del world
    assert _index(bundle) == 0
    assert _run(bundle, out) == 0
    return _report(out)


def test_index_뒤_run이_질의_목록마다_단계별_줄을_내고_리랭크_뒤_줄은_없다(
    world: World, tmp_path: Path
) -> None:
    human = [*HUMAN, {"evidence_id": "q3", "query": QUERY_A}]
    evidence = [*EVIDENCE, passage_evidence("q3", "sub/b.docx", PASSAGE_B)]
    keyword = [{"evidence_id": "q1", "query": "연차휴가 입사 발생"}]
    bundle = _bundle(tmp_path, evidence=evidence, human=human, keyword=keyword)

    report = _indexed_run(world, bundle, tmp_path / "out")

    assert report.format_version == "1.0.0"
    assert report.stages == ["vector", "keyword", "fused"]
    assert [(row.query_list, row.stage) for row in report.rows] == [
        (name, stage) for name in ("human", "keyword") for stage in report.stages
    ]
    assert report.eval_set.name == "tiny"
    assert (report.eval_set.documents, report.eval_set.questions, report.eval_set.queries) == (
        2,
        3,
        4,
    )
    assert report.index.chunks == 2
    assert report.config["search_candidates"] == 50
    assert (tmp_path / "out" / "report.md").is_file()


def test_지표는_손으로_계산한_값과_같다(world: World, tmp_path: Path) -> None:
    """q1과 q2는 질의가 자기 문서의 글이라 벡터 1위다. q3는 `a`의 글로 `b`의 글귀를 묻는다. `a`의
    조각이 1위이고 기대 근거에 닿는 `b`의 조각은 벡터 2위다. `b`의 조각에는 질의의 키워드 토큰이
    없어 키워드 후보에 들지 못한다. 합친 뒤는 두 쪽에 다 든 `a`가 1위, 벡터에만 든 `b`가 2위다."""
    human = [*HUMAN, {"evidence_id": "q3", "query": QUERY_A}]
    evidence = [*EVIDENCE, passage_evidence("q3", "sub/b.docx", PASSAGE_B)]
    bundle = _bundle(tmp_path, evidence=evidence, human=human)

    report = _indexed_run(world, bundle, tmp_path / "out")

    second_gain = 1 / 1.5849625007211563  # 1 / log2(3)
    for stage in ("vector", "fused"):
        row = report.row("human", stage)
        assert row.queries == 3
        assert row.hit_at_1 == pytest.approx(2 / 3)
        assert row.hit_at_3 == pytest.approx(1.0)
        assert row.hit_at_10 == pytest.approx(1.0)
        assert row.mrr == pytest.approx((1 + 1 + 1 / 2) / 3)
        assert row.recall == pytest.approx(1.0)
        assert row.ndcg_at_10 == pytest.approx((1 + 1 + second_gain) / 3)
        assert row.ndcg_truncated == 0
    keyword = report.row("human", "keyword")
    assert keyword.queries == 3
    assert keyword.hit_at_1 == pytest.approx(2 / 3)
    assert keyword.hit_at_10 == pytest.approx(2 / 3)
    assert keyword.mrr == pytest.approx(2 / 3)
    assert keyword.recall == pytest.approx(2 / 3)
    assert keyword.ndcg_at_10 == pytest.approx(2 / 3)


def test_키워드_토큰이_빈_질의는_키워드만_단계에서_놓친_것으로_센다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path, human=[{"evidence_id": "q1", "query": "!!!"}])

    report = _indexed_run(world, bundle, tmp_path / "out")

    assert report.row("human", "keyword").queries == 1
    assert report.row("human", "keyword").hit_at_10 == 0.0
    # 같은 질의가 벡터에서는 두 조각을 모두 후보로 얻어 기대 근거에 닿는다.
    assert report.row("human", "vector").hit_at_10 == 1.0
    assert report.row("human", "fused").hit_at_10 == 1.0


def test_글귀가_조각의_경계에서_갈리면_놓친_것으로_센다(world: World, tmp_path: Path) -> None:
    words = [f"항목{number}번" for number in range(40)]
    spanning = " ".join(words[5:25])
    short = " ".join(words[:4])
    document = docx_bytes("휴가", " ".join(words))
    bundle = _bundle(
        tmp_path,
        documents={"a.docx": document},
        evidence=[
            passage_evidence("q1", "a.docx", spanning),
            passage_evidence("q2", "a.docx", short),
        ],
        human=[{"evidence_id": "q1", "query": spanning}, {"evidence_id": "q2", "query": short}],
        config={
            **INDEX_CONFIG,
            "chunking": {"strategy": "structure_first", "max_tokens": 16, "overlap_tokens": 4},
        },
    )

    report = _indexed_run(world, bundle, tmp_path / "out")

    assert report.index.chunks > 1
    for stage in ("vector", "fused"):
        # 긴 글귀는 어느 조각에도 통째로 들지 못해 놓치고, 짧은 글귀는 첫 조각에 든다.
        assert report.row("human", stage).hit_at_10 == pytest.approx(0.5)
        assert report.row("human", stage).recall == pytest.approx(0.5)


def test_공백과_줄바꿈과_NFC가_달라도_글귀가_닿는다(world: World, tmp_path: Path) -> None:
    decomposed = unicodedata.normalize("NFD", PASSAGE).replace(" ", "\t\n")
    bundle = _bundle(
        tmp_path,
        evidence=[passage_evidence("q1", "a.docx", decomposed), EVIDENCE[1]],
        human=HUMAN,
    )

    report = _indexed_run(world, bundle, tmp_path / "out")

    assert report.row("human", "fused").hit_at_1 == pytest.approx(1.0)


def test_다른_문서의_같은_글귀는_닿지_않는다(world: World, tmp_path: Path) -> None:
    """기대 근거는 `b`의 글귀인데 그 글귀는 `a`의 본문에만 있다. `a`의 조각이 후보 첫 자리에 올라도
    문서가 달라 닿지 않는다."""
    bundle = _bundle(
        tmp_path,
        evidence=[passage_evidence("q1", "sub/b.docx", PASSAGE)],
        human=[{"evidence_id": "q1", "query": QUERY_A}],
    )

    report = _indexed_run(world, bundle, tmp_path / "out")

    for stage in ("vector", "keyword", "fused"):
        assert report.row("human", stage).hit_at_10 == 0.0


def test_조각_하나가_기대_근거_둘에_닿아_nDCG가_잘린_질의가_잘린_수에_세어진다(
    world: World, tmp_path: Path
) -> None:
    second = "출장비는 실비로 정산한다"
    both = {
        "id": "q1",
        "evidence": [
            {"kind": "passage", "document": "a.docx", "passage": PASSAGE},
            {"kind": "passage", "document": "a.docx", "passage": second},
        ],
        "tags": [],
    }
    bundle = _bundle(
        tmp_path,
        documents={"a.docx": docx_bytes("휴가", PASSAGE + ".", second + ".")},
        evidence=[both],
        human=[{"evidence_id": "q1", "query": f"휴가 {PASSAGE}. {second}."}],
    )

    report = _indexed_run(world, bundle, tmp_path / "out")

    row = report.row("human", "fused")
    assert row.recall == pytest.approx(1.0)
    assert row.ndcg_at_10 == pytest.approx(1.0)
    assert row.ndcg_truncated == 1


def test_report_md는_report_json의_판과_해시와_질의_목록을_표로_옮긴다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path, keyword=[{"evidence_id": "q1", "query": "연차휴가 입사 발생"}])

    report = _indexed_run(world, bundle, tmp_path / "out")

    markdown = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert report.format_version in markdown
    assert report.eval_set.content_hash in markdown
    for name in ("human", "keyword"):
        assert f"`{name}`" in markdown
    for stage in report.stages:
        assert stage in markdown


def test_보고서에_질의의_글과_조각의_글이_없다(world: World, tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _indexed_run(world, bundle, tmp_path / "out")

    for name in ("report.json", "report.md"):
        text = (tmp_path / "out" / name).read_text(encoding="utf-8")
        assert QUERY_A not in text
        assert PASSAGE not in text
        assert PASSAGE_B not in text
        assert "연차휴가" not in text
    # 식별자만 있다.
    assert "human" in (tmp_path / "out" / "report.md").read_text(encoding="utf-8")


def test_작업_폴더의_env가_있어도_보고서가_같다(world: World, tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    before = _indexed_run(world, bundle, tmp_path / "before")
    (world.work_dir / ".env").write_text(
        "RAG_PARSE_MAX_PAGES=1\nRAG_DEFAULT_CHUNK_TOKENS=64\nRAG_SEARCH_CANDIDATES=1\n",
        encoding="utf-8",
    )

    assert _run(bundle, tmp_path / "after") == 0

    after = _report(tmp_path / "after")
    assert after.model_copy(update={"meta": before.meta}) == before


def test_run은_판에_적힌_끝점이_아니라_RAG_EVAL_EMBEDDING_URL로_질의를_임베딩한다(
    world: World, tei_stub: TeiStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    indexed_requests = tei_stub.count(EMBEDDINGS)
    other = TeiStub()
    with serve_stub(other) as other_url:
        monkeypatch.setenv(EMBEDDING_ENV, other_url)

        assert _run(bundle, tmp_path / "out") == 0

    assert other.count(EMBEDDINGS) == len(HUMAN)
    assert tei_stub.count(EMBEDDINGS) == indexed_requests
    del world


def test_평가_도중_판이_바뀌면_보고서를_쓰지_않고_1이다(
    world: World,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """판을 바꾸는 걸이는 TEI 스텁의 응답 순번이다. 평가의 둘째 질의를 임베딩하는 요청을 받을 때
    현재 판을 없애, 그 질의의 진단용 검색이 `is_current` 거짓을 읽게 한다."""
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    switching = TeiStub()
    seen: list[int] = []

    def switch_on_second_query(count: int) -> None:
        seen.append(count)
        if count == 2:
            with psycopg.connect(world.database_url, autocommit=True) as connection:
                connection.execute("UPDATE knowledge_bases SET current_index_version_id = NULL")

    switching.on_embeddings = switch_on_second_query
    capsys.readouterr()
    with serve_stub(switching) as url:
        monkeypatch.setenv(EMBEDDING_ENV, url)

        code = _run(bundle, tmp_path / "out")

    assert code == 1
    assert seen[:2] == [1, 2]
    assert "판이 바뀌었다" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("missing", [DATABASE_ENV, DATA_DIR_ENV, EMBEDDING_ENV])
def test_평가_전용_이름이_없으면_제품의_환경이_있어도_돌지_않고_빠진_이름을_알린다(
    world: World,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing: str,
) -> None:
    bundle = _bundle(tmp_path)
    monkeypatch.delenv(missing)
    monkeypatch.setenv("RAG_DATABASE_URL", world.database_url)
    monkeypatch.setenv("RAG_DEFAULT_EMBEDDING_URL", world.tei_url)

    assert _run(bundle, tmp_path / "out") == 1

    assert missing in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_이름이_rag_eval로_시작하지_않는_주소는_연결_오류가_아니라_이름의_규칙이_나온다(
    world: World,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del world
    monkeypatch.setenv(DATABASE_ENV, "postgresql://user:secret-value@127.0.0.1:1/product")

    assert _run(_bundle(tmp_path), tmp_path / "out") == 1

    err = capsys.readouterr().err
    assert "rag_eval" in err
    assert "secret-value" not in err
    assert "127.0.0.1" not in err


def test_스키마가_올라_있지_않은_데이터베이스에서는_평가하지_않고_1이다(
    world: World, tei_stub: TeiStub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del world

    assert _run(_bundle(tmp_path), tmp_path / "out") == 1

    assert "index" in capsys.readouterr().err
    assert tei_stub.requests == []
    assert not (tmp_path / "out").exists()


def test_묶음_밖의_문서가_든_데이터베이스에서는_질의를_임베딩하지_않고_1이다(
    world: World,
    tei_stub: TeiStub,
    tmp_path: Path,
    make_settings: Callable[..., Settings],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "other.docx").write_bytes(docx_bytes("다른", "묶음에 없는 문서의 글이다."))
    settings = make_settings(world.database_url)
    assert ingest_path(settings, foreign, group=None, wait_timeout_seconds=None) == 0
    capsys.readouterr()
    requests_before = len(tei_stub.requests)

    assert _run(bundle, tmp_path / "out") == 1

    assert "묶음에 없는 문서" in capsys.readouterr().err
    assert len(tei_stub.requests) == requests_before
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "through",
    [[], ["fused", "rerank"], ["fused", "fused"]],
    ids=["없다", "둘", "같은 값 둘"],
)
def test_through가_하나가_아니면_아무것도_읽지_않고_2다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], through: list[str]
) -> None:
    arguments = [value for item in through for value in ("--through", item)]

    code = search_eval.main(["run", str(tmp_path), *arguments, "--out", str(tmp_path / "out")])

    assert code == 2
    assert "한 번만 받는다" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_through_rerank는_아직_없다고_알리고_보고서를_쓰지_않고_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    capsys.readouterr()

    code = search_eval.main(
        ["run", str(bundle), "--through", "rerank", "--out", str(tmp_path / "out")]
    )

    assert code == 1
    assert "티켓 05" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
    del world


@pytest.mark.parametrize(
    "change",
    [
        {"embedding_model": "다른/모델"},
        {"embedding_dimensions": 8},
        {"chunking": {"strategy": "structure_first", "max_tokens": 256, "overlap_tokens": 64}},
    ],
    ids=["임베딩 모델", "차원", "청킹"],
)
def test_현재_판의_요소가_구성과_다르면_평가하지_않고_1이다(
    world: World,
    tei_stub: TeiStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    change: dict[str, JsonValue],
) -> None:
    assert _index(_bundle(tmp_path)) == 0
    other = _bundle(tmp_path, "other", config={**INDEX_CONFIG, **change})
    capsys.readouterr()
    requests_before = len(tei_stub.requests)

    assert _run(other, tmp_path / "out") == 1

    assert "config.json" in capsys.readouterr().err
    assert len(tei_stub.requests) == requests_before
    assert not (tmp_path / "out").exists()
    del world


def test_키는_같고_내용_해시가_다른_문서가_든_데이터베이스에서는_질의를_임베딩하지_않고_1이다(
    world: World, tei_stub: TeiStub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _index(_bundle(tmp_path)) == 0
    changed = docx_bytes("휴가", "같은 이름의 문서지만 내용이 다르다.")
    other = _bundle(tmp_path, "other", documents={"a.docx": changed, "sub/b.docx": DOCUMENT_B})
    capsys.readouterr()
    requests_before = len(tei_stub.requests)

    assert _run(other, tmp_path / "out") == 1

    assert "a.docx" in capsys.readouterr().err
    assert len(tei_stub.requests) == requests_before
    assert not (tmp_path / "out").exists()
    del world
