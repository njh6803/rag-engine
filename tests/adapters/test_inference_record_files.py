"""추론 기록 파일의 형식과 읽기·쓰기(명세 search-eval "추론 기록", 티켓 07).

`.keys`는 열쇠를 사전 순으로 한 줄에 하나씩, `.f32`는 같은 순서의 벡터를 float32 리틀 엔디언으로
이어 붙인 것, `rerank.jsonl`은 열쇠 순의 열쇠와 점수다. 정렬해 쓰므로 같은 내용은 같은 바이트다.
"""

import struct
from pathlib import Path

import pytest
from tests.support.eval_bundle import make_folder_link

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.adapters.inference_record_files import (
    FORMAT_VERSION,
    Manifest,
    RecordEntry,
    RecordKind,
    RecordsFormatError,
    read_embedding_values,
    read_manifest,
    read_rerank_values,
    render_embedding_files,
    render_rerank_file,
    write_record_files,
)


def _entry(kind: RecordKind, count: int, *, dimensions: int | None = 3) -> RecordEntry:
    return RecordEntry(
        model="모델",
        dimensions=None if kind is RecordKind.RERANK else dimensions,
        count=count,
        tei_version="1.9.4",
        device="cpu",
        request_fingerprint="지문",
    )


def test_임베딩_파일은_열쇠를_사전_순으로_벡터를_float32_리틀_엔디언으로_이어_붙인다() -> None:
    values = {"b": (0.5, 1.0, 2.0), "a": (3.0, 4.0, 5.0)}

    keys, vectors = render_embedding_files(values, dimensions=3)

    assert keys == b"a\nb\n"
    assert vectors == struct.pack("<6f", 3.0, 4.0, 5.0, 0.5, 1.0, 2.0)


def test_리랭크_파일은_열쇠_순의_열쇠와_점수다() -> None:
    text = render_rerank_file({"b": 0.25, "a": 0.5}).decode()

    assert text.splitlines() == ['{"key":"a","score":0.5}', '{"key":"b","score":0.25}']


def test_같은_내용은_넣은_순서와_무관하게_같은_바이트다() -> None:
    forward = render_embedding_files({"a": (1.0, 2.0, 3.0), "b": (4.0, 5.0, 6.0)}, dimensions=3)
    reverse = render_embedding_files({"b": (4.0, 5.0, 6.0), "a": (1.0, 2.0, 3.0)}, dimensions=3)

    assert forward == reverse
    assert render_rerank_file({"a": 1.0, "b": 2.0}) == render_rerank_file({"b": 2.0, "a": 1.0})


def test_차원이_다른_벡터는_쓰지_않는다() -> None:
    with pytest.raises(ValueError, match="차원"):
        render_embedding_files({"a": (1.0, 2.0)}, dimensions=3)


def test_쓴_임베딩_파일을_읽으면_float32로_둥글린_같은_값이_나온다(tmp_path: Path) -> None:
    paths = BundlePaths(tmp_path)
    values = {"a": (0.1, 0.2, 0.3), "b": (1.0, -2.0, 3.5)}
    keys, vectors = render_embedding_files(values, dimensions=3)
    entry = _entry(RecordKind.QUERY_EMBEDDINGS, 2)
    write_record_files(
        paths,
        RecordKind.QUERY_EMBEDDINGS,
        {"query-embeddings.keys": keys, "query-embeddings.f32": vectors},
        entry,
    )

    read = read_embedding_values(paths, RecordKind.QUERY_EMBEDDINGS, entry)

    assert set(read) == {"a", "b"}
    assert read["b"] == (1.0, -2.0, 3.5)
    assert read["a"] == pytest.approx((0.1, 0.2, 0.3), abs=1e-6)
    # 읽은 값을 다시 쓰면 같은 바이트다. float32로 둥글린 값은 다시 둥글려도 같다.
    assert render_embedding_files(read, dimensions=3) == (keys, vectors)


def test_쓴_리랭크_파일을_읽으면_같은_점수가_나온다(tmp_path: Path) -> None:
    paths = BundlePaths(tmp_path)
    entry = _entry(RecordKind.RERANK, 2)
    scores = {"a": 0.123456789, "b": 1.0}
    write_record_files(
        paths, RecordKind.RERANK, {"rerank.jsonl": render_rerank_file(scores)}, entry
    )

    assert read_rerank_values(paths, RecordKind.RERANK) == {"a": 0.123456789, "b": 1.0}


def test_records_json은_파일마다_항목을_두고_다른_파일의_항목은_그대로_둔다(tmp_path: Path) -> None:
    paths = BundlePaths(tmp_path)
    keys, vectors = render_embedding_files({"a": (1.0, 2.0, 3.0)}, dimensions=3)
    write_record_files(
        paths,
        RecordKind.CHUNK_EMBEDDINGS,
        {"chunk-embeddings.keys": keys, "chunk-embeddings.f32": vectors},
        _entry(RecordKind.CHUNK_EMBEDDINGS, 1),
    )
    write_record_files(
        paths,
        RecordKind.RERANK,
        {"rerank.jsonl": render_rerank_file({"a": 1.0})},
        _entry(RecordKind.RERANK, 1),
    )

    manifest = read_manifest(paths)

    assert manifest is not None
    assert manifest.format_version == FORMAT_VERSION
    assert set(manifest.files) == {"chunk-embeddings", "rerank"}
    assert manifest.files["rerank"].dimensions is None


def test_records_json이_없으면_없음으로_읽는다(tmp_path: Path) -> None:
    assert read_manifest(BundlePaths(tmp_path)) is None


def test_major가_다른_records_json은_거부한다(tmp_path: Path) -> None:
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "records.json").write_text(
        '{"format_version": "2.0.0", "files": {}}', encoding="utf-8"
    )

    with pytest.raises(RecordsFormatError, match="판"):
        read_manifest(BundlePaths(tmp_path))


def test_형식이_틀린_records_json은_내용을_싣지_않고_거부한다(tmp_path: Path) -> None:
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "records.json").write_text("비밀-내용", encoding="utf-8")

    with pytest.raises(RecordsFormatError) as caught:
        read_manifest(BundlePaths(tmp_path))

    assert "비밀-내용" not in str(caught.value)


def test_항목의_수와_맞지_않는_파일은_거부한다(tmp_path: Path) -> None:
    paths = BundlePaths(tmp_path)
    keys, vectors = render_embedding_files({"a": (1.0, 2.0, 3.0)}, dimensions=3)
    entry = _entry(RecordKind.QUERY_EMBEDDINGS, 5)
    write_record_files(
        paths,
        RecordKind.QUERY_EMBEDDINGS,
        {"query-embeddings.keys": keys, "query-embeddings.f32": vectors},
        entry,
    )

    with pytest.raises(RecordsFormatError, match="수"):
        read_embedding_values(paths, RecordKind.QUERY_EMBEDDINGS, entry)


def test_records_json이_가리키는_파일이_없으면_거부한다(tmp_path: Path) -> None:
    paths = BundlePaths(tmp_path)
    write_record_files(
        paths,
        RecordKind.RERANK,
        {"rerank.jsonl": render_rerank_file({})},
        _entry(RecordKind.RERANK, 0),
    )
    (tmp_path / "records" / "rerank.jsonl").unlink()

    with pytest.raises(RecordsFormatError, match="없다"):
        read_rerank_values(paths, RecordKind.RERANK)


def test_쓰기는_묶음_밖을_가리키는_records_링크를_거부하고_링크가_가리킨_폴더를_그대로_둔다(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "rerank.jsonl").write_bytes("밖의 파일".encode())
    make_folder_link(bundle / "records", outside)

    with pytest.raises(BundlePathError):
        write_record_files(
            BundlePaths(bundle),
            RecordKind.RERANK,
            {"rerank.jsonl": render_rerank_file({"a": 1.0})},
            _entry(RecordKind.RERANK, 1),
        )

    assert sorted(path.name for path in outside.iterdir()) == ["rerank.jsonl"]
    assert (outside / "rerank.jsonl").read_bytes() == "밖의 파일".encode()


def test_쓰기는_임시_파일이_묶음_밖을_가리키는_링크여도_거부하고_아무것도_쓰지_않는다(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "records").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    make_folder_link(bundle / "records" / "rerank.jsonl.tmp", outside)

    with pytest.raises(BundlePathError):
        write_record_files(
            BundlePaths(bundle),
            RecordKind.RERANK,
            {"rerank.jsonl": render_rerank_file({"a": 1.0})},
            _entry(RecordKind.RERANK, 1),
        )

    assert list(outside.iterdir()) == []
    assert not (bundle / "records" / "rerank.jsonl").exists()
    assert not (bundle / "records" / "records.json").exists()


def test_쓰기는_임시_파일이_묶음_안의_다른_자리를_가리키는_링크여도_거부하고_아무것도_쓰지_않는다(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "records").mkdir(parents=True)
    documents = bundle / "documents"
    documents.mkdir()
    make_folder_link(bundle / "records" / "rerank.jsonl.tmp", documents)

    with pytest.raises(BundlePathError, match="임시 파일"):
        write_record_files(
            BundlePaths(bundle),
            RecordKind.RERANK,
            {"rerank.jsonl": render_rerank_file({"a": 1.0})},
            _entry(RecordKind.RERANK, 1),
        )

    assert list(documents.iterdir()) == []
    assert not (bundle / "records" / "rerank.jsonl").exists()
    assert not (bundle / "records" / "records.json").exists()


def test_manifest는_파일_이름_순으로_정렬해_쓴다() -> None:
    manifest = Manifest(
        format_version=FORMAT_VERSION,
        files={
            "rerank": _entry(RecordKind.RERANK, 0),
            "chunk-embeddings": _entry(RecordKind.CHUNK_EMBEDDINGS, 0),
        },
    )

    text = manifest.render().decode()

    assert text.index("chunk-embeddings") < text.index("rerank")
    assert text.endswith("\n")
