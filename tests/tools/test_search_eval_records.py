"""평가 도구 `tools/search_eval.py`의 추론 기록(티켓 search-eval 07, 명세 "추론 기록").

뒤에는 실제 테스트 PostgreSQL과 TEI 스텁을 붙이고 도구의 `main(argv)`를 부른다. 기록에 있는 글을
다시 계산하지 않는지는 스텁이 받은 요청의 글 수로 본다. "기록 파일을 고치지 않는다"와 "주인 파일만
다시 쓴다"는 파일의 바이트로 본다. 기록을 만든 뒤 데이터베이스를 비워(`_reset`) 새 데이터베이스에서
기록만으로 색인하는 길을 잰다.
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import psycopg
import pytest
from tests.support.docx_files import docx_bytes
from tests.support.eval_bundle import (
    PASSAGE,
    PASSAGE_B,
    edit_json,
    make_folder_link,
    passage_evidence,
    read_json,
    write_indexable_bundle,
    write_jsonl,
)
from tests.support.eval_world import RERANKER_ENV, World
from tests.support.tei_stub import TeiStub

from rag_engine.domain.entities import JsonValue
from tools import search_eval

DOCUMENTS = {
    "a.docx": docx_bytes("휴가", PASSAGE + "."),
    "sub/b.docx": docx_bytes("출장", PASSAGE_B + "."),
}
QUERY_A = f"휴가 {PASSAGE}."
QUERY_B = f"출장 {PASSAGE_B}."
EVIDENCE = [
    passage_evidence("q1", "a.docx", PASSAGE),
    passage_evidence("q2", "sub/b.docx", PASSAGE_B),
]
HUMAN: list[JsonValue] = [
    {"evidence_id": "q1", "query": QUERY_A},
    {"evidence_id": "q2", "query": QUERY_B},
]
EMBEDDINGS = "/v1/embeddings"
RERANK = "/rerank"
CHUNK_FILES = ("chunk-embeddings.keys", "chunk-embeddings.f32")
QUERY_FILES = ("query-embeddings.keys", "query-embeddings.f32")
RERANK_FILE = "rerank.jsonl"
DEVICE = ["--tei-device", "cpu"]


def _bundle(tmp_path: Path, *, human: Sequence[JsonValue] = HUMAN) -> Path:
    root = write_indexable_bundle(tmp_path / "bundle", DOCUMENTS, EVIDENCE)
    write_jsonl(root / "queries-human.jsonl", human)
    return root


def _index(bundle: Path, *extra: str) -> int:
    return search_eval.main(["index", str(bundle), *extra])


def _run(bundle: Path, out: Path, *extra: str, through: str = "fused") -> int:
    return search_eval.main(["run", str(bundle), "--through", through, "--out", str(out), *extra])


def _reset(world: World) -> None:
    """데이터베이스를 새로 만든 것과 같게 비운다. 스키마와 원본 파일을 지운다."""
    with psycopg.connect(world.database_url, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    for path in sorted(world.data_dir.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()


def _snapshot(bundle: Path) -> dict[str, bytes]:
    """`records/`의 모든 파일의 바이트."""
    folder = bundle / "records"
    if not folder.is_dir():
        return {}
    return {path.name: path.read_bytes() for path in sorted(folder.iterdir())}


def _only(snapshot: dict[str, bytes], names: Sequence[str]) -> dict[str, bytes]:
    return {name: snapshot[name] for name in names}


def _embedded_texts(stub: TeiStub) -> int:
    """스텁이 받은 임베딩 요청의 글 수."""
    total = 0
    for body in stub.bodies(EMBEDDINGS):
        texts = body["input"]
        assert isinstance(texts, list)
        total += len(texts)
    return total


def _manifest(bundle: Path) -> dict[str, JsonValue]:
    value = read_json(bundle / "records" / "records.json")
    assert isinstance(value, dict)
    return value


def _entries(bundle: Path) -> dict[str, JsonValue]:
    files = _manifest(bundle)["files"]
    assert isinstance(files, dict)
    return files


def _report(out: Path) -> dict[str, JsonValue]:
    value = read_json(out / "report.json")
    assert isinstance(value, dict)
    return value


def _records_of(out: Path) -> dict[str, JsonValue]:
    records = _report(out)["records"]
    assert isinstance(records, dict)
    return records


def _write_all(bundle: Path, out: Path, reranker_url: str) -> None:
    """조각, 질의, 리랭크의 기록을 모두 만든다."""
    del reranker_url
    assert _index(bundle, "--records", "write", *DEVICE) == 0
    assert _run(bundle, out, "--records", "write", *DEVICE, through="rerank") == 0


def test_write가_기록을_만들고_장치와_판과_요청_지문을_records_json에_적는다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)

    assert _index(bundle, "--records", "write", *DEVICE) == 0
    assert _run(bundle, tmp_path / "out", "--records", "write", *DEVICE) == 0

    assert sorted(_snapshot(bundle)) == sorted([*CHUNK_FILES, *QUERY_FILES, "records.json"])
    assert _manifest(bundle)["format_version"] == "1.0.0"
    chunk = _entries(bundle)["chunk-embeddings"]
    assert isinstance(chunk, dict)
    assert chunk["model"] == "BAAI/bge-m3"
    assert chunk["dimensions"] == 16
    assert chunk["count"] == 2
    assert chunk["tei_version"] == "1.9.4"
    assert chunk["device"] == "cpu"
    assert isinstance(chunk["request_fingerprint"], str)
    assert len(str(chunk["request_fingerprint"])) == 64
    del world


def test_write는_장치를_받지_않으면_아무것도_하지_않고_2다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)

    assert _index(bundle, "--records", "write") == 2

    assert "--tei-device" in capsys.readouterr().err
    assert _snapshot(bundle) == {}
    del world


def test_기록이_있으면_새_데이터베이스의_index가_조각을_임베딩_서버에_보내지_않는다(
    world: World, tei_stub: TeiStub, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle, "--records", "write", *DEVICE) == 0
    assert _embedded_texts(tei_stub) == 2
    written = _snapshot(bundle)
    _reset(world)
    tei_stub.requests.clear()

    assert _index(bundle) == 0

    sent = _embedded_texts(tei_stub)
    assert sent == 0, f"기록이 있는데 조각으로 서버에 간 글 수: {sent}"
    assert _snapshot(bundle) == written
    assert search_eval.main(["validate", str(bundle), "--indexed"]) == 0


def test_기록이_있으면_run이_질의를_임베딩_서버에_보내지_않고_같은_보고서를_낸다(
    world: World, tei_stub: TeiStub, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    assert _run(bundle, tmp_path / "computed", "--records", "write", *DEVICE) == 0
    assert _embedded_texts(tei_stub) > 0
    tei_stub.requests.clear()

    assert _run(bundle, tmp_path / "recorded") == 0

    sent = _embedded_texts(tei_stub)
    assert sent == 0, f"기록이 있는데 질의로 서버에 간 글 수: {sent}"
    assert _report(tmp_path / "recorded")["rows"] == _report(tmp_path / "computed")["rows"]
    del world


def test_read에서_새로_계산할_임베딩이_100개를_넘으면_1과_안내가_나오고_기록_파일이_그대로다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle, "--records", "write", *DEVICE) == 0
    assert _run(bundle, tmp_path / "first", "--records", "write", *DEVICE) == 0
    written = _snapshot(bundle)
    # 질의마다 기대 근거가 하나씩 필요하므로 근거도 101개를 더한다.
    evidence = [passage_evidence(f"n{number}", "a.docx", PASSAGE) for number in range(101)]
    write_jsonl(bundle / "evidence.jsonl", [*EVIDENCE, *evidence])
    write_jsonl(
        bundle / "queries-human.jsonl",
        [*HUMAN, *[{"evidence_id": f"n{n}", "query": f"새 질의 {n}"} for n in range(101)]],
    )
    capsys.readouterr()

    code = _run(bundle, tmp_path / "second")

    err = capsys.readouterr().err
    assert code == 1
    assert "--records write" in err
    assert "records/query-embeddings.keys" in err
    assert "records/query-embeddings.f32" in err
    assert not (tmp_path / "second").exists()
    assert _snapshot(bundle) == written
    del world


def test_read에서_새로_계산한_임베딩이_100개_이하이면_기록_파일을_고치지_않고_돈다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    assert _snapshot(bundle) == {}

    assert _run(bundle, tmp_path / "out") == 0

    assert _snapshot(bundle) == {}
    records = _records_of(tmp_path / "out")
    assert records["read"] == 0
    assert records["computed"] == 2
    assert records["files"] == {}
    del world


def test_리랭커의_끝점이_없는_전체_실행은_기록에_없는_쌍_하나에도_실패한다(
    world: World,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    monkeypatch.delenv(RERANKER_ENV, raising=False)
    capsys.readouterr()

    code = _run(bundle, tmp_path / "out", through="rerank")

    err = capsys.readouterr().err
    assert code == 1
    assert "--records write" in err
    assert "records/rerank.jsonl" in err
    assert not (tmp_path / "out").exists()
    assert _snapshot(bundle) == {}
    del world


def test_리랭크_기록이_있으면_리랭커의_끝점_없이_전체_실행이_돈다(
    world: World,
    reranker_stub: TeiStub,
    reranker_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    _write_all(bundle, tmp_path / "written", reranker_url)
    monkeypatch.delenv(RERANKER_ENV)
    reranker_stub.requests.clear()

    code = _run(bundle, tmp_path / "recorded", through="rerank")

    assert code == 0, f"끝점 없이 기록으로 돈 전체 실행의 종료 코드: {code}"
    assert reranker_stub.count(RERANK) == 0
    assert _report(tmp_path / "recorded")["rows"] == _report(tmp_path / "written")["rows"]
    del world


def test_off이고_리랭커의_끝점이_없는_전체_실행은_빠진_이름을_알리고_1이다(
    world: World,
    tei_stub: TeiStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    monkeypatch.delenv(RERANKER_ENV, raising=False)
    capsys.readouterr()
    requests_before = len(tei_stub.requests)

    assert _run(bundle, tmp_path / "out", "--records", "off", through="rerank") == 1

    assert RERANKER_ENV in capsys.readouterr().err
    assert len(tei_stub.requests) == requests_before
    del world


def test_write는_그_명령이_주인인_파일만_다시_쓰고_다른_파일은_바이트_그대로_둔다(
    world: World, reranker_url: str, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    _write_all(bundle, tmp_path / "out", reranker_url)
    written = _snapshot(bundle)
    folder = bundle / "records"
    # 주인이 아닌 파일은 같은 내용을 다시 써도 바이트가 같으므로, 덧붙여 바꿔 놓고 건드렸는지 본다.
    with (folder / RERANK_FILE).open("ab") as stream:
        stream.write(b'{"key":"zz","score":0.5}\n')
    tampered_rerank = (folder / RERANK_FILE).read_bytes()
    _reset(world)

    assert _index(bundle, "--records", "write", *DEVICE) == 0

    after_index = _snapshot(bundle)
    assert after_index[RERANK_FILE] == tampered_rerank
    assert _only(after_index, QUERY_FILES) == _only(written, QUERY_FILES)
    assert _only(after_index, CHUNK_FILES) == _only(written, CHUNK_FILES)
    with (folder / CHUNK_FILES[0]).open("ab") as stream:
        stream.write(b"zz\n")
    tampered_chunks = _only(_snapshot(bundle), CHUNK_FILES)

    assert _run(bundle, tmp_path / "fast", "--records", "write", *DEVICE) == 0

    after_run = _snapshot(bundle)
    assert after_run[RERANK_FILE] == tampered_rerank
    assert _only(after_run, CHUNK_FILES) == tampered_chunks
    assert _only(after_run, QUERY_FILES) == _only(written, QUERY_FILES)


def test_write는_이번_실행이_쓰지_않은_열쇠를_지우고_같은_내용이면_같은_바이트를_쓴다(
    world: World, tmp_path: Path
) -> None:
    extra_evidence = passage_evidence("q3", "sub/b.docx", PASSAGE_B)
    bundle = _bundle(tmp_path, human=[*HUMAN, {"evidence_id": "q3", "query": "여분의 질의"}])
    write_jsonl(bundle / "evidence.jsonl", [*EVIDENCE, extra_evidence])
    assert _index(bundle) == 0
    assert _run(bundle, tmp_path / "wide", "--records", "write", *DEVICE) == 0
    assert _entries(bundle)["query-embeddings"] is not None
    wide = _snapshot(bundle)
    write_jsonl(bundle / "queries-human.jsonl", HUMAN)

    assert _run(bundle, tmp_path / "narrow", "--records", "write", *DEVICE) == 0

    narrow = _snapshot(bundle)
    assert len(narrow["query-embeddings.keys"].splitlines()) == 2
    assert len(wide["query-embeddings.keys"].splitlines()) == 3
    assert _run(bundle, tmp_path / "again", "--records", "write", *DEVICE) == 0
    assert _snapshot(bundle) == narrow
    del world


def test_index_write가_문서가_든_데이터베이스에서는_기록_파일을_그대로_두고_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle, "--records", "write", *DEVICE) == 0
    written = _snapshot(bundle)
    capsys.readouterr()

    code = _index(bundle, "--records", "write", *DEVICE)

    assert code == 1, f"문서가 든 데이터베이스의 index write 종료 코드: {code}"
    assert "새로 만든" in capsys.readouterr().err
    assert _snapshot(bundle) == written
    del world


def test_index_write가_문서_목록과_해시가_다른_문서가_있으면_스키마를_올리지_않고_1이다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle, "--records", "write", *DEVICE) == 0
    written = _snapshot(bundle)
    _reset(world)
    (bundle / "documents" / "a.docx").write_bytes("바뀐 문서".encode())

    assert _index(bundle, "--records", "write", *DEVICE) == 1

    assert _snapshot(bundle) == written
    with psycopg.connect(world.database_url, autocommit=True) as connection:
        tables = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
    assert tables == []


def test_off는_기록을_읽지도_쓰지도_않는다(world: World, tei_stub: TeiStub, tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle, "--records", "write", *DEVICE) == 0
    written = _snapshot(bundle)
    _reset(world)
    tei_stub.requests.clear()

    assert _index(bundle, "--records", "off") == 0

    assert _embedded_texts(tei_stub) == 2
    assert _snapshot(bundle) == written
    tei_stub.requests.clear()
    assert _run(bundle, tmp_path / "out", "--records", "off") == 0
    assert _embedded_texts(tei_stub) == 2
    assert _snapshot(bundle) == written
    records = _records_of(tmp_path / "out")
    # `off`는 기록 계층을 거치지 않아 읽은 수도 새로 계산한 수도 세지 않는다.
    assert records == {"read": 0, "computed": 0, "files": {}}


def test_모델_이름이_다르면_기록의_값을_쓰지_않고_다시_계산한다(
    world: World, tei_stub: TeiStub, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    assert _run(bundle, tmp_path / "written", "--records", "write", *DEVICE) == 0
    entry = _entries(bundle)["query-embeddings"]
    assert isinstance(entry, dict)
    entries = _entries(bundle)
    entries["query-embeddings"] = {**entry, "model": "다른/모델"}
    (bundle / "records" / "records.json").write_text(
        json.dumps({"format_version": "1.0.0", "files": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    tei_stub.requests.clear()

    assert _run(bundle, tmp_path / "out") == 0

    assert _embedded_texts(tei_stub) == 2
    del world


def test_write는_요청_지문이_다른_파일의_옛_값을_옮기지_않고_다시_계산한다(
    world: World, tei_stub: TeiStub, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    assert _run(bundle, tmp_path / "first", "--records", "write", *DEVICE) == 0
    entries = _entries(bundle)
    entry = entries["query-embeddings"]
    assert isinstance(entry, dict)
    entries["query-embeddings"] = {**entry, "request_fingerprint": "옛-지문"}
    (bundle / "records" / "records.json").write_text(
        json.dumps({"format_version": "1.0.0", "files": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    tei_stub.requests.clear()

    assert _run(bundle, tmp_path / "second", "--records", "write", *DEVICE) == 0

    sent = _embedded_texts(tei_stub)
    assert sent == 2, f"요청 지문이 다른 기록 뒤 다시 계산한 글 수: {sent}"
    rewritten = _entries(bundle)["query-embeddings"]
    assert isinstance(rewritten, dict)
    assert rewritten["request_fingerprint"] != "옛-지문"
    del world


def test_tei_판만_바꾼_뒤의_write는_그_파일의_옛_값을_옮기지_않는다(
    world: World, tei_stub: TeiStub, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    assert _run(bundle, tmp_path / "first", "--records", "write", *DEVICE) == 0
    edit_json(bundle / "config.json", {"tei_version": "1.9.5"})
    tei_stub.requests.clear()

    assert _run(bundle, tmp_path / "second", "--records", "write", *DEVICE) == 0

    # 그 실행이 쓴 열쇠의 수(질의 둘)만큼 다시 계산한다.
    sent = _embedded_texts(tei_stub)
    assert sent == 2, f"TEI 판이 다른 기록 뒤 다시 계산한 글 수: {sent}"
    entry = _entries(bundle)["query-embeddings"]
    assert isinstance(entry, dict)
    assert entry["tei_version"] == "1.9.5"
    del world


def test_write로_돈_index가_1로_끝나면_주인_파일이_바이트_그대로다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle, "--records", "write", *DEVICE) == 0
    written = _snapshot(bundle)
    _reset(world)
    broken = {"a.docx": DOCUMENTS["a.docx"], "bad.docx": "docx가 아닌 바이트".encode()}
    broken_bundle = write_indexable_bundle(
        tmp_path / "broken",
        broken,
        [passage_evidence("q1", "a.docx", PASSAGE)],
    )
    (broken_bundle / "records").mkdir()
    for name, data in written.items():
        (broken_bundle / "records" / name).write_bytes(data)

    code = _index(broken_bundle, "--records", "write", *DEVICE)

    assert code == 1, f"깨진 묶음의 index write 종료 코드: {code}"
    assert _snapshot(broken_bundle) == written


def test_write로_돈_run이_1로_끝나면_주인_파일이_바이트_그대로다(
    world: World, reranker_stub: TeiStub, reranker_url: str, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    _write_all(bundle, tmp_path / "written", reranker_url)
    written = _snapshot(bundle)
    entries = _entries(bundle)
    entry = entries["rerank"]
    assert isinstance(entry, dict)
    entries["rerank"] = {**entry, "tei_version": "0.0.1"}
    (bundle / "records" / "records.json").write_text(
        json.dumps({"format_version": "1.0.0", "files": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    stale = _snapshot(bundle)
    reranker_stub.fail(RERANK, 500)

    assert _run(bundle, tmp_path / "out", "--records", "write", *DEVICE, through="rerank") == 1

    assert _snapshot(bundle) == stale
    assert stale != written
    del world


def test_보고서가_읽은_기록_파일의_해시와_읽은_수를_싣는다(world: World, tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    assert _run(bundle, tmp_path / "written", "--records", "write", *DEVICE) == 0

    assert _run(bundle, tmp_path / "out") == 0

    records = _records_of(tmp_path / "out")
    expected = {
        f"records/{name}": hashlib.sha256((bundle / "records" / name).read_bytes()).hexdigest()
        for name in (*QUERY_FILES, "records.json")
    }
    assert records == {"read": 2, "computed": 0, "files": expected}
    markdown = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "추론 기록" in markdown
    assert expected["records/query-embeddings.keys"] in markdown
    del world


def test_write의_보고서는_다시_쓴_기록_파일의_해시를_싣는다(world: World, tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0

    assert _run(bundle, tmp_path / "out", "--records", "write", *DEVICE) == 0

    records = _records_of(tmp_path / "out")
    assert records["computed"] == 2
    files = records["files"]
    assert isinstance(files, dict)
    assert files == {
        f"records/{name}": hashlib.sha256((bundle / "records" / name).read_bytes()).hexdigest()
        for name in (*QUERY_FILES, "records.json")
    }
    del world


def test_빠른_실행의_write는_리랭크_기록을_건드리지_않고_보고서에도_싣지_않는다(
    world: World, reranker_url: str, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    _write_all(bundle, tmp_path / "full", reranker_url)
    rerank_before = (bundle / "records" / RERANK_FILE).read_bytes()

    assert _run(bundle, tmp_path / "fast", "--records", "write", *DEVICE) == 0

    rerank_after = (bundle / "records" / RERANK_FILE).read_bytes()
    assert rerank_after == rerank_before, (
        f"빠른 실행 뒤 리랭크 기록의 바이트 수: {len(rerank_after)}, 전: {len(rerank_before)}"
    )
    files = _records_of(tmp_path / "fast")["files"]
    assert isinstance(files, dict)
    listed = "records/rerank.jsonl" in files
    assert not listed, f"빠른 실행 보고서에 리랭크 기록이 실렸는지: {listed}"
    del world


@pytest.mark.parametrize("command", ["index", "run"])
def test_records가_묶음_밖을_가리키는_링크이면_쓰지_않고_1이고_링크가_가리킨_파일이_그대로다(
    world: World, tmp_path: Path, command: str
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"keep")
    make_folder_link(bundle / "records", outside)

    if command == "index":
        _reset(world)
        code = _index(bundle, "--records", "write", *DEVICE)
    else:
        code = _run(bundle, tmp_path / "out", "--records", "write", *DEVICE)

    assert code == 1
    assert sorted(path.name for path in outside.iterdir()) == ["keep.txt"]
    assert (outside / "keep.txt").read_bytes() == b"keep"
    del world


def test_validate는_기록이_있는_묶음에서_초록이다(
    world: World, reranker_url: str, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    _write_all(bundle, tmp_path / "out", reranker_url)

    code = search_eval.main(["validate", str(bundle)])

    assert code == 0, f"기록이 있는 묶음의 validate 종료 코드: {code}"
    del world


def test_validate는_요청_지문이_다르면_실패하고_다시_만들_기록_파일을_알린다(
    world: World, reranker_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    _write_all(bundle, tmp_path / "out", reranker_url)
    entries = _entries(bundle)
    entry = entries["rerank"]
    assert isinstance(entry, dict)
    entries["rerank"] = {**entry, "request_fingerprint": "옛-지문"}
    (bundle / "records" / "records.json").write_text(
        json.dumps({"format_version": "1.0.0", "files": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    capsys.readouterr()

    code = search_eval.main(["validate", str(bundle)])

    assert code == 1, f"요청 지문이 다른 기록의 validate 종료 코드: {code}"
    err = capsys.readouterr().err
    assert "요청 지문" in err
    assert "records/rerank.jsonl" in err
    assert "--records write" in err
    assert "query-embeddings" not in err
    del world


def test_validate는_records_json의_tei_판이_구성과_다르면_실패한다(
    world: World, reranker_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    _write_all(bundle, tmp_path / "out", reranker_url)
    edit_json(bundle / "config.json", {"tei_version": "1.9.5"})
    capsys.readouterr()

    assert search_eval.main(["validate", str(bundle)]) == 1

    err = capsys.readouterr().err
    assert "tei_version" in err
    assert "records/chunk-embeddings" in err
    del world


def test_validate는_구성의_tei_판이_compose의_이미지_태그와_다르면_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    edit_json(bundle / "config.json", {"tei_version": "1.9.5"})

    assert search_eval.main(["validate", str(bundle)]) == 1

    err = capsys.readouterr().err
    assert "compose.eval.yml" in err
    assert "1.9.5" in err


def test_validate는_기록의_합이_20MB를_넘으면_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "records").mkdir()
    (bundle / "records" / "padding.bin").write_bytes(b"0" * (20 * 1024 * 1024 + 1))

    code = search_eval.main(["validate", str(bundle)])

    assert code == 1, f"20MB를 넘는 기록의 validate 종료 코드: {code}"
    assert "20MB" in capsys.readouterr().err


def test_validate는_기록이_없는_묶음도_통과한다(tmp_path: Path) -> None:
    assert search_eval.main(["validate", str(_bundle(tmp_path))]) == 0
