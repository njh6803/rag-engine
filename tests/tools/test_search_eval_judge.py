"""평가 도구 `tools/search_eval.py`의 `judge`와 `run`의 `llm` 칸(티켓 search-eval 12).

뒤에는 실제 테스트 PostgreSQL과 TEI 스텁, Claude 가짜 끝점(`tests/support/claude_stub.py`)을 붙이고
도구의 `main(argv)`를 부른다. 묶음은 `test_search_eval_run.py`와 같다. 문서가 둘(`a`, `b`)이고
조각이 하나씩이며 질의가 둘이라, 합친 뒤의 상위 10개는 질의마다 조각 둘이다. 판정할 쌍은 질의의 글
둘과 조각의 글 둘을 곱한 넷이다. 가짜 끝점은 `a`의 글이 든 조각만 관련 있다고 답한다. 그 판정으로
손으로 센 값은 이렇다.

- q1(`QUERY_A`)의 상위 10개는 `a`(닿음, 관련), `b`(닿지 않음, 관련 없음)이다.
- q2(`QUERY_B`)의 상위 10개는 `b`(닿음, 관련 없음), `a`(닿지 않음, 관련)이다.
- 관련 비율 2/4, 기대 근거에 닿은 조각의 일치 비율 1/2(닿은 둘 가운데 q1의 `a`만 관련), 판정 없음
  0, 빠진 정답 후보는 q2의 `a`(기대 근거에 없는데 관련 있다고 본 조각) 하나다.
"""

import hashlib
import json
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict
from tests.support.claude_stub import (
    JUDGE_API_KEY,
    JUDGE_API_KEY_ENV,
    JUDGE_MODEL,
    JUDGE_MODEL_ENV,
    JUDGE_URL_ENV,
    SECRET_MESSAGE,
    ClaudeStub,
)
from tests.support.docx_files import docx_bytes
from tests.support.eval_bundle import (
    INDEX_CONFIG,
    PASSAGE,
    PASSAGE_B,
    make_folder_link,
    passage_evidence,
    write_indexable_bundle,
    write_jsonl,
)
from tests.support.eval_world import DATABASE_ENV, World
from tests.support.tei_stub import TeiStub

from rag_engine.adapters.ingest_command import ingest_path
from rag_engine.adapters.settings import Settings
from rag_engine.domain.entities import JsonValue
from tools import search_eval

DOCUMENT_A = docx_bytes("휴가", PASSAGE + ".")
DOCUMENT_B = docx_bytes("출장", PASSAGE_B + ".")
DOCUMENTS = {"a.docx": DOCUMENT_A, "sub/b.docx": DOCUMENT_B}
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
# 판정기에 보내는 글은 리랭커에 보내는 글과 같다(절 경로를 붙인 조각의 글).
TEXT_A = f"휴가\n\n{PASSAGE}."
TEXT_B = f"출장\n\n{PASSAGE_B}."
PAIRS = {(QUERY_A, TEXT_A), (QUERY_A, TEXT_B), (QUERY_B, TEXT_A), (QUERY_B, TEXT_B)}
JUDGE_CONFIG: dict[str, JsonValue] = {
    **INDEX_CONFIG,
    "judge_model": JUDGE_MODEL,
    "judge_prompt_version": "1",
}
JUDGMENTS = "judgments.jsonl"
OTHER_MODEL = "claude-other-model"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Line(_Strict):
    """판정 파일의 줄 하나. 칸의 목록을 고정한다(글이 없다)."""

    query_sha256: str
    text_sha256: str
    relevant: bool
    model: str
    prompt_version: str
    judged_at: date

    def key(self) -> tuple[str, str, str, str]:
        return (self.query_sha256, self.text_sha256, self.model, self.prompt_version)


class _Missing(_Strict):
    query_list: str
    evidence_id: str
    document: str
    ordinal: int


class _Llm(_Strict):
    pairs: int
    judged: int
    relevant_rate: float | None
    agreement_rate: float | None
    unjudged_rate: float
    missing_candidates: list[_Missing]


class _Report(BaseModel):
    """보고서에서 이 티켓의 칸만 읽는다. 다른 칸은 다른 시험이 고정한다."""

    model_config = ConfigDict(extra="ignore")

    llm: _Llm | None
    llm_unavailable: str | None = None


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _a_is_relevant(query: str, passage: str) -> bool:
    del query
    return PASSAGE in passage


def _bundle(
    tmp_path: Path,
    name: str = "bundle",
    *,
    documents: dict[str, bytes] | None = None,
    evidence: Sequence[JsonValue] = EVIDENCE,
    human: Sequence[JsonValue] = HUMAN,
    config: dict[str, JsonValue] | None = None,
) -> Path:
    root = write_indexable_bundle(
        tmp_path / name,
        DOCUMENTS if documents is None else documents,
        evidence,
        config=JUDGE_CONFIG if config is None else config,
    )
    write_jsonl(root / "queries-human.jsonl", human)
    return root


def _single_pair_bundle(tmp_path: Path) -> Path:
    """조각이 하나이고 질의가 하나라 판정할 쌍이 하나다. 재시도 횟수를 정확히 센다."""
    return _bundle(
        tmp_path, documents={"a.docx": DOCUMENT_A}, evidence=[EVIDENCE[0]], human=[HUMAN[0]]
    )


def _index(bundle: Path) -> int:
    return search_eval.main(["index", str(bundle)])


def _judge(bundle: Path, *extra: str, through: str = "fused") -> int:
    return search_eval.main(["judge", str(bundle), "--through", through, *extra])


def _run(bundle: Path, out: Path, *, through: str = "fused") -> int:
    return search_eval.main(["run", str(bundle), "--through", through, "--out", str(out)])


def _lines(bundle: Path) -> list[_Line]:
    text = (bundle / JUDGMENTS).read_text(encoding="utf-8")
    return [_Line.model_validate_json(line) for line in text.splitlines()]


def _report(out: Path) -> _Report:
    return _Report.model_validate_json((out / "report.json").read_text(encoding="utf-8"))


def _write_lines(bundle: Path, lines: Sequence[dict[str, JsonValue]]) -> None:
    write_jsonl(bundle / JUDGMENTS, list(lines))


def _line(query: str, text: str, **change: JsonValue) -> dict[str, JsonValue]:
    return {
        "query_sha256": _sha(query),
        "text_sha256": _sha(text),
        "relevant": True,
        "model": JUDGE_MODEL,
        "prompt_version": "1",
        "judged_at": "2026-11-14",
        **change,
    }


def _prepared(tmp_path: Path, claude_stub: ClaudeStub, bundle: Path | None = None) -> Path:
    """색인하고 `a`의 글이 든 조각만 관련 있다고 답하는 가짜 끝점을 준비한 묶음."""
    claude_stub.relevant_when = _a_is_relevant
    made = _bundle(tmp_path) if bundle is None else bundle
    assert _index(made) == 0
    return made


def _judged(tmp_path: Path, claude_stub: ClaudeStub) -> Path:
    bundle = _prepared(tmp_path, claude_stub)
    assert _judge(bundle, "--yes") == 0
    return bundle


def test_yes_없이는_건수와_비용만_찍고_가짜_끝점을_부르지_않고_0이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    capsys.readouterr()

    assert _judge(bundle) == 0

    out = capsys.readouterr().out
    assert "4건" in out
    assert "달러" in out
    assert "--yes" in out
    assert claude_stub.count() == 0
    assert not (bundle / JUDGMENTS).exists()
    del world, claude_url


def test_yes를_주면_쌍마다_한_번씩_불러_해시만_든_줄을_열쇠_순으로_쌓는다(
    world: World, claude_url: str, claude_stub: ClaudeStub, tmp_path: Path
) -> None:
    bundle = _prepared(tmp_path, claude_stub)

    assert _judge(bundle, "--yes") == 0

    assert claude_stub.count() == 4
    assert {request.pair() for request in claude_stub.requests} == PAIRS
    for request in claude_stub.requests:
        assert request.headers["authorization"] == f"Bearer {JUDGE_API_KEY}"
        assert request.body["model"] == JUDGE_MODEL
    lines = _lines(bundle)
    assert [line.key() for line in lines] == sorted(line.key() for line in lines)
    assert {(line.query_sha256, line.text_sha256): line.relevant for line in lines} == {
        (_sha(query), _sha(text)): PASSAGE in text for query, text in PAIRS
    }
    assert {(line.model, line.prompt_version) for line in lines} == {(JUDGE_MODEL, "1")}
    assert all(abs((datetime.now(UTC).date() - line.judged_at).days) <= 1 for line in lines)
    raw = (bundle / JUDGMENTS).read_text(encoding="utf-8")
    for secret in (QUERY_A, QUERY_B, PASSAGE, PASSAGE_B):
        assert secret not in raw
    del world, claude_url


def test_이미_판정한_쌍은_다시_부르지_않아_같은_명령을_또_쳐도_요청이_늘지_않는다(
    world: World, claude_url: str, claude_stub: ClaudeStub, tmp_path: Path
) -> None:
    bundle = _judged(tmp_path, claude_stub)
    before = (bundle / JUDGMENTS).read_bytes()

    assert _judge(bundle, "--yes") == 0

    assert claude_stub.count() == 4
    assert (bundle / JUDGMENTS).read_bytes() == before
    del world, claude_url


def test_끊긴_뒤_다시_돌리면_이미_받은_조합을_부르지_않는다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """셋째 요청부터 서버가 계속 5xx를 내면 앞의 둘만 파일에 남고 도구는 1로 끝난다. 서버를 되돌려
    다시 치면 모자란 둘만 부른다."""
    bundle = _prepared(tmp_path, claude_stub)
    claude_stub.fail_from(3, 503)
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    assert len(_lines(bundle)) == 2
    claude_stub.heal()
    before = claude_stub.count()
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 0

    assert claude_stub.count() == before + 2
    assert len(_lines(bundle)) == 4
    del world, claude_url


@pytest.mark.parametrize("status", [429, 500, 503, 529])
def test_일시_실패_한_번은_다시_불러_받는다(
    world: World, claude_url: str, claude_stub: ClaudeStub, tmp_path: Path, status: int
) -> None:
    bundle = _prepared(tmp_path, claude_stub, _single_pair_bundle(tmp_path))
    claude_stub.fail_next(status)

    assert _judge(bundle, "--yes") == 0

    assert claude_stub.count() == 2
    assert len(_lines(bundle)) == 1
    del world, claude_url


def test_일시_실패가_계속되면_다시_부르기를_셋까지_하고_1이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub, _single_pair_bundle(tmp_path))
    claude_stub.fail_from(1, 503)
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    # 처음 한 번에 다시 셋이다.
    assert claude_stub.count() == 4
    err = capsys.readouterr().err
    assert "판정" in err
    assert SECRET_MESSAGE not in err
    assert not (bundle / JUDGMENTS).exists()
    del world, claude_url


@pytest.mark.parametrize("status", [400, 401, 403])
def test_영구_실패는_다시_부르지_않고_1이며_서버와_요청의_글이_표준_오류에_없다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    status: int,
) -> None:
    bundle = _prepared(tmp_path, claude_stub, _single_pair_bundle(tmp_path))
    claude_stub.fail_next(status)
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    assert claude_stub.count() == 1
    captured = capsys.readouterr()
    for text in (captured.out, captured.err):
        for secret in (SECRET_MESSAGE, JUDGE_API_KEY, QUERY_A, PASSAGE):
            assert secret not in text
    assert "판정" in captured.err
    del world, claude_url


def test_쌍_하나가_영구_실패여도_그_쌍만_건너뛰고_나머지를_판정해_0이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    claude_stub.fail_next(400)
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 0

    assert claude_stub.count() == 4
    assert len(_lines(bundle)) == 3
    captured = capsys.readouterr()
    assert "건너뛴 쌍 1건" in captured.err
    for text in (captured.out, captured.err):
        for secret in (SECRET_MESSAGE, JUDGE_API_KEY, QUERY_A, PASSAGE):
            assert secret not in text
    del world, claude_url


def test_SDK의_디버그_로그를_켜도_로그와_출력에_키와_요청_응답의_본문이_없다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SDK의 로거(`anthropic`)는 DEBUG에서 요청 본문을 싣는다. 환경 변수 `ANTHROPIC_LOG=debug`가
    그 로거를 DEBUG로 두는 것과 같은 상태에서 돌려, 어댑터가 그 수준을 되돌리는지 본다."""
    bundle = _prepared(tmp_path, claude_stub)
    capsys.readouterr()
    caplog.set_level(logging.DEBUG, logger="anthropic")
    logging.getLogger("anthropic").setLevel(logging.DEBUG)

    assert _judge(bundle, "--yes") == 0

    captured = capsys.readouterr()
    for text in (captured.out, captured.err, caplog.text):
        for secret in (JUDGE_API_KEY, QUERY_A, QUERY_B, PASSAGE, PASSAGE_B):
            assert secret not in text
    del world, claude_url


def test_설정_셋이_모두_없으면_판정기를_조립하지_않고_세_이름을_알리고_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    err = capsys.readouterr().err
    for name in (JUDGE_URL_ENV, JUDGE_MODEL_ENV, JUDGE_API_KEY_ENV):
        assert name in err
    del world


@pytest.mark.parametrize("missing", [JUDGE_URL_ENV, JUDGE_MODEL_ENV, JUDGE_API_KEY_ENV])
def test_설정이_일부만_있으면_부르지_않고_빠진_이름만_알리고_값은_찍지_않고_1이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    monkeypatch.delenv(missing)
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    err = capsys.readouterr().err
    assert missing in err
    for present in {JUDGE_URL_ENV, JUDGE_MODEL_ENV, JUDGE_API_KEY_ENV} - {missing}:
        assert present not in err
    for value in (claude_url, JUDGE_MODEL, JUDGE_API_KEY):
        assert value not in err
    assert claude_stub.count() == 0
    del world


def test_RAG_JUDGE_MODEL이_config의_judge_model과_다르면_부르지_않고_어긋난_둘의_이름을_낸다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    monkeypatch.setenv(JUDGE_MODEL_ENV, "다른-모델")
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    err = capsys.readouterr().err
    assert JUDGE_MODEL_ENV in err
    assert "judge_model" in err
    assert claude_stub.count() == 0
    assert not (bundle / JUDGMENTS).exists()
    del world, claude_url


def test_지시문의_판이_config의_judge_prompt_version과_다르면_부르지_않고_이름을_낸다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    other = {**JUDGE_CONFIG, "judge_prompt_version": "2"}
    bundle = _prepared(tmp_path, claude_stub, _bundle(tmp_path, config=other))
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    assert "judge_prompt_version" in capsys.readouterr().err
    assert claude_stub.count() == 0
    del world, claude_url


def test_prune은_지금의_모델과_지시문_판에_맞지_않는_줄만_지우고_고르지_않으면_두는_것이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    keep = _line(QUERY_A, TEXT_A)
    _write_lines(
        bundle,
        [
            _line(QUERY_B, TEXT_B, model="다른-모델"),
            keep,
            _line(QUERY_B, TEXT_A, prompt_version="0"),
        ],
    )
    before = (bundle / JUDGMENTS).read_bytes()

    assert _judge(bundle) == 0
    assert (bundle / JUDGMENTS).read_bytes() == before
    capsys.readouterr()

    assert _judge(bundle, "--prune") == 0

    assert [line.key() for line in _lines(bundle)] == [
        (_sha(QUERY_A), _sha(TEXT_A), JUDGE_MODEL, "1")
    ]
    assert "2줄" in capsys.readouterr().out
    assert claude_stub.count() == 0
    del world, claude_url


def test_판정_파일이_묶음_밖을_가리키는_링크이면_쓰지_않고_부르지도_않고_1이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    outside = tmp_path / "outside"
    outside.mkdir()
    make_folder_link(bundle / JUDGMENTS, outside)
    capsys.readouterr()

    assert _run(bundle, tmp_path / "out") == 1
    assert "링크를 풀면 묶음 폴더 밖을 가리킨다" in capsys.readouterr().err
    assert _judge(bundle, "--yes") == 1

    assert "링크를 풀면 묶음 폴더 밖을 가리킨다" in capsys.readouterr().err
    assert claude_stub.count() == 0
    assert list(outside.iterdir()) == []
    del world, claude_url


def test_묶음_밖의_문서가_든_데이터베이스에서는_부르지_않고_판정_파일을_쓰지_않고_1이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    make_settings: Callable[..., Settings],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "other.docx").write_bytes(docx_bytes("다른", "묶음에 없는 문서의 글이다."))
    assert (
        ingest_path(
            make_settings(world.database_url), foreign, group=None, wait_timeout_seconds=None
        )
        == 0
    )
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    assert "묶음에 없는 문서" in capsys.readouterr().err
    assert claude_stub.count() == 0
    assert not (bundle / JUDGMENTS).exists()
    del claude_url


def test_키는_같고_내용_해시가_다른_문서가_든_데이터베이스에서는_부르지_않고_1이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepared(tmp_path, claude_stub)
    changed = docx_bytes("휴가", "같은 이름의 문서지만 내용이 다르다.")
    other = _bundle(tmp_path, "other", documents={"a.docx": changed, "sub/b.docx": DOCUMENT_B})
    capsys.readouterr()

    assert _judge(other, "--yes") == 1

    assert "a.docx" in capsys.readouterr().err
    assert claude_stub.count() == 0
    assert not (other / JUDGMENTS).exists()
    del world, claude_url


@pytest.mark.parametrize(
    "through",
    [[], ["fused", "rerank"]],
    ids=["없다", "둘"],
)
def test_judge도_through가_하나가_아니면_아무것도_읽지_않고_2다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], through: list[str]
) -> None:
    arguments = [value for item in through for value in ("--through", item)]

    assert search_eval.main(["judge", str(tmp_path), *arguments]) == 2

    assert "한 번만 받는다" in capsys.readouterr().err


def test_전체_실행의_judge는_리랭크_뒤_순위의_상위_10개를_판정한다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    reranker_stub: TeiStub,
    reranker_url: str,
    tmp_path: Path,
) -> None:
    bundle = _prepared(tmp_path, claude_stub)

    assert _judge(bundle, "--yes", through="rerank") == 0

    assert len(reranker_stub.bodies("/rerank")) == len(HUMAN)
    assert {request.pair() for request in claude_stub.requests} == PAIRS
    del world, claude_url, reranker_url


def test_run은_판정_파일이_없고_설정도_없으면_llm을_null과_까닭으로_낸다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0

    assert _run(bundle, tmp_path / "out") == 0

    report = _report(tmp_path / "out")
    raw = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert raw["llm"] is None
    assert report.llm_unavailable is not None
    assert JUDGMENTS in report.llm_unavailable
    del world


def test_run은_판정기의_설정이_없어도_판정_파일로_손으로_센_값을_낸다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _judged(tmp_path, claude_stub)
    for name in (JUDGE_URL_ENV, JUDGE_MODEL_ENV, JUDGE_API_KEY_ENV):
        monkeypatch.delenv(name)
    requests_before = claude_stub.count()

    assert _run(bundle, tmp_path / "out") == 0

    llm = _report(tmp_path / "out").llm
    assert llm is not None
    assert (llm.pairs, llm.judged) == (4, 4)
    assert llm.relevant_rate == pytest.approx(0.5)
    assert llm.agreement_rate == pytest.approx(0.5)
    assert llm.unjudged_rate == 0.0
    assert llm.missing_candidates == [
        _Missing(query_list="human", evidence_id="q2", document="a.docx", ordinal=0)
    ]
    assert claude_stub.count() == requests_before
    del world, claude_url


def test_run의_보고서에도_질의의_글과_조각의_글과_해시가_없고_report_md에_llm_표가_있다(
    world: World, claude_url: str, claude_stub: ClaudeStub, tmp_path: Path
) -> None:
    bundle = _judged(tmp_path, claude_stub)

    assert _run(bundle, tmp_path / "out") == 0

    for name in ("report.json", "report.md"):
        text = (tmp_path / "out" / name).read_text(encoding="utf-8")
        for secret in (QUERY_A, QUERY_B, PASSAGE, PASSAGE_B, _sha(QUERY_A), _sha(TEXT_A)):
            assert secret not in text
    markdown = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "LLM" in markdown
    assert "a.docx" in markdown
    del world, claude_url


def test_run은_질의의_글이_바뀐_쌍을_판정_없음으로_세고_분모는_판정이_있는_조합만이다(
    world: World, claude_url: str, claude_stub: ClaudeStub, tmp_path: Path
) -> None:
    """q1의 질의 글을 바꾸면 q1의 두 쌍은 열쇠가 달라져 판정이 없다. q2의 두 쌍만 남는다. 판정
    없음의 비율은 전체 넷 가운데 둘(1/2)이고, 관련 비율은 판정된 둘 가운데 `a`뿐이라 1/2이며,
    닿은 조각의 일치 비율은 닿은 `b`가 관련 없다고 판정되어 0/1이다."""
    bundle = _judged(tmp_path, claude_stub)
    write_jsonl(
        bundle / "queries-human.jsonl",
        [{"evidence_id": "q1", "query": QUERY_A + " 규정"}, HUMAN[1]],
    )

    assert _run(bundle, tmp_path / "out") == 0

    llm = _report(tmp_path / "out").llm
    assert llm is not None
    assert (llm.pairs, llm.judged) == (4, 2)
    assert llm.unjudged_rate == pytest.approx(0.5)
    assert llm.relevant_rate == pytest.approx(0.5)
    assert llm.agreement_rate == pytest.approx(0.0)
    assert llm.missing_candidates == [
        _Missing(query_list="human", evidence_id="q2", document="a.docx", ordinal=0)
    ]
    del world, claude_url


def test_run은_지시문의_판이_바뀌면_옛_판정을_쓰지_않고_llm이_null이다(
    world: World, claude_url: str, claude_stub: ClaudeStub, tmp_path: Path
) -> None:
    bundle = _judged(tmp_path, claude_stub)
    config_path = bundle / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["judge_prompt_version"] = "2"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    assert _run(bundle, tmp_path / "out") == 0

    report = _report(tmp_path / "out")
    assert report.llm is None
    assert report.llm_unavailable is not None
    assert "judge_prompt_version" in report.llm_unavailable
    del world, claude_url


def test_run은_전체_실행이면_리랭크_뒤_상위_10개로_세고_빠진_정답_후보를_식별자로_싣는다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    reranker_stub: TeiStub,
    reranker_url: str,
    tmp_path: Path,
) -> None:
    del reranker_stub
    bundle = _prepared(tmp_path, claude_stub)
    assert _judge(bundle, "--yes", through="rerank") == 0

    assert _run(bundle, tmp_path / "out", through="rerank") == 0

    llm = _report(tmp_path / "out").llm
    assert llm is not None
    assert (llm.pairs, llm.judged) == (4, 4)
    assert [item.evidence_id for item in llm.missing_candidates] == ["q2"]
    del world, claude_url, reranker_url


def test_판정_파일의_줄이_형식에_맞지_않으면_run도_judge도_줄_번호를_알리고_1이다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    text = json.dumps(_line(QUERY_A, TEXT_A), ensure_ascii=False) + "\n" + "{깨진 줄\n"
    (bundle / JUDGMENTS).write_text(text, encoding="utf-8")
    capsys.readouterr()

    assert _run(bundle, tmp_path / "out") == 1
    assert JUDGMENTS in capsys.readouterr().err
    assert _judge(bundle, "--yes") == 1
    err = capsys.readouterr().err
    assert "2번째 줄" in err
    assert claude_stub.count() == 0
    assert not (tmp_path / "out").exists()
    del world, claude_url


def test_judge는_평가_전용_이름이_빠지면_부르지_않고_빠진_이름을_알린다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    monkeypatch.delenv(DATABASE_ENV)
    capsys.readouterr()

    assert _judge(bundle, "--yes") == 1

    assert DATABASE_ENV in capsys.readouterr().err
    assert claude_stub.count() == 0
    del world, claude_url


def test_config로_준_구성의_판정_모델이_판정_파일의_열쇠가_되고_구성_없이는_어긋난다(
    world: World,
    claude_url: str,
    claude_stub: ClaudeStub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _prepared(tmp_path, claude_stub)
    other = tmp_path / "other-config.json"
    other.write_text(json.dumps({**JUDGE_CONFIG, "judge_model": OTHER_MODEL}), encoding="utf-8")
    monkeypatch.setenv(JUDGE_MODEL_ENV, OTHER_MODEL)
    capsys.readouterr()

    assert _judge(bundle, "--yes", "--config", str(other)) == 0

    assert {(line.model, line.prompt_version) for line in _lines(bundle)} == {(OTHER_MODEL, "1")}
    assert all(request.body["model"] == OTHER_MODEL for request in claude_stub.requests)
    capsys.readouterr()
    assert _judge(bundle, "--yes") == 1
    assert "judge_model" in capsys.readouterr().err
    del world, claude_url
