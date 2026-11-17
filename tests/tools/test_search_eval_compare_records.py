"""`compare`와 진짜 `run`의 보고서가 만나는 길(티켓 search-eval 08, 07의 한계).

07의 `run` 보고서는 그 명령이 읽은 기록 파일의 해시만 실었고, 조각 임베딩(`index`가 읽는다)은
없었다. 그래서 조각 임베딩 기록을 손으로 고쳐도 `compare`가 알지 못했다. 여기서는 실제 테스트
PostgreSQL과 TEI 스텁으로 `index`와 `run`을 돌려, 보고서에 조각 임베딩 파일의 해시가 실리고 그
파일이 바뀌면 `compare`가 견주지 않고 실패하는지 본다.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.eval_bundle import (
    PASSAGE,
    PASSAGE_B,
    passage_evidence,
    read_json,
    write_indexable_bundle,
    write_jsonl,
)
from tests.support.eval_world import World

from rag_engine.domain.entities import JsonValue
from tools import search_eval

DOCUMENTS = {
    "a.docx": docx_bytes("휴가", PASSAGE + "."),
    "sub/b.docx": docx_bytes("출장", PASSAGE_B + "."),
}
EVIDENCE = [
    passage_evidence("q1", "a.docx", PASSAGE),
    passage_evidence("q2", "sub/b.docx", PASSAGE_B),
]
HUMAN: list[JsonValue] = [
    {"evidence_id": "q1", "query": f"휴가 {PASSAGE}."},
    {"evidence_id": "q2", "query": f"출장 {PASSAGE_B}."},
]
CHUNK_FILES = ("chunk-embeddings.keys", "chunk-embeddings.f32")
QUERY_FILES = ("query-embeddings.keys", "query-embeddings.f32")
DEVICE = ["--tei-device", "cpu"]


def _bundle(tmp_path: Path) -> Path:
    root = write_indexable_bundle(tmp_path / "bundle", DOCUMENTS, EVIDENCE)
    write_jsonl(root / "queries-human.jsonl", HUMAN)
    return root


def _run(bundle: Path, out: Path, *extra: str) -> int:
    return search_eval.main(["run", str(bundle), "--through", "fused", "--out", str(out), *extra])


def _files_of(out: Path) -> dict[str, str]:
    report = read_json(out / "report.json")
    assert isinstance(report, dict)
    records = report["records"]
    assert isinstance(records, dict)
    files = records["files"]
    assert isinstance(files, dict)
    return {name: str(digest) for name, digest in files.items()}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_everything(bundle: Path, tmp_path: Path) -> None:
    """조각과 질의의 기록을 `write`로 만든다."""
    assert search_eval.main(["index", str(bundle), "--records", "write", *DEVICE]) == 0
    assert _run(bundle, tmp_path / "written", "--records", "write", *DEVICE) == 0


def test_run의_보고서는_읽지_않은_조각_임베딩_기록_파일의_해시도_싣는다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    _record_everything(bundle, tmp_path)

    assert _run(bundle, tmp_path / "read") == 0

    files = _files_of(tmp_path / "read")
    for name in (*CHUNK_FILES, *QUERY_FILES):
        assert files[f"records/{name}"] == _sha256(bundle / "records" / name), name
    del world


def test_write로_돈_run의_보고서도_조각_임베딩_기록_파일의_해시를_싣는다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    assert search_eval.main(["index", str(bundle), "--records", "write", *DEVICE]) == 0

    assert _run(bundle, tmp_path / "out", "--records", "write", *DEVICE) == 0

    files = _files_of(tmp_path / "out")
    for name in CHUNK_FILES:
        assert files[f"records/{name}"] == _sha256(bundle / "records" / name), name
    del world


def test_기록을_끈_run의_보고서는_기록_파일의_해시를_싣지_않는다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    _record_everything(bundle, tmp_path)

    assert _run(bundle, tmp_path / "off", "--records", "off") == 0

    assert _files_of(tmp_path / "off") == {}
    del world


def test_조각_임베딩_기록을_고치면_compare가_견주지_않고_실패한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    _record_everything(bundle, tmp_path)
    assert _run(bundle, tmp_path / "base") == 0
    shutil.copyfile(tmp_path / "base" / "report.json", bundle / "baseline-fast.json")
    again = ["compare", "--gate", "fast", str(tmp_path / "base"), str(bundle)]
    assert search_eval.main(again) == 0
    capsys.readouterr()

    chunk_values = bundle / "records" / "chunk-embeddings.f32"
    chunk_values.write_bytes(chunk_values.read_bytes() + b"\0\0\0\0")
    assert _run(bundle, tmp_path / "tampered") == 0
    code = search_eval.main(["compare", "--gate", "fast", str(tmp_path / "tampered"), str(bundle)])

    err = capsys.readouterr().err
    assert code == 1
    assert "records/chunk-embeddings.f32" in err
    assert "records/chunk-embeddings.keys" not in err
    json.loads((tmp_path / "tampered" / "report.json").read_text(encoding="utf-8"))
    del world


def test_기록이_그대로이면_같은_묶음의_두_실행은_compare를_통과한다(
    world: World, tmp_path: Path
) -> None:
    bundle = _bundle(tmp_path)
    _record_everything(bundle, tmp_path)
    assert _run(bundle, tmp_path / "base") == 0
    shutil.copyfile(tmp_path / "base" / "report.json", bundle / "baseline-fast.json")

    assert _run(bundle, tmp_path / "again") == 0

    compared = search_eval.main(["compare", "--gate", "fast", str(tmp_path / "again"), str(bundle)])
    assert compared == 0
    del world
