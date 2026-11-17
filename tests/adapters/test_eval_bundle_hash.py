"""묶음의 내용 해시(티켓 search-eval 04, 명세 "보고서"의 내용 해시 항목).

같은 해시는 같은 검색 구성과 같은 질문을 뜻해야 한다. 판정 모델이나 지시문의 판만 바뀐 묶음은 같은
해시이고, 검색의 숫자에 닿는 입력이 바뀐 묶음은 다른 해시이다.
"""

import json
from pathlib import Path

import pytest
from tests.support.eval_bundle import (
    CONFIG,
    EVIDENCE,
    QUERIES_HUMAN,
    edit_json,
    write_bundle,
    write_json,
    write_jsonl,
)

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.eval_bundle_hash import bundle_content_hash
from rag_engine.adapters.eval_set_reader import read_eval_set
from rag_engine.domain.entities import JsonValue


def _hash(root: Path) -> str:
    paths = BundlePaths(root)
    return bundle_content_hash(paths, read_eval_set(paths))


def test_같은_묶음은_같은_해시이고_해시는_소문자_16진_예순네_글자다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")

    first = _hash(root)

    assert first == _hash(root)
    assert len(first) == 64
    assert first == first.lower()
    int(first, 16)


@pytest.mark.parametrize(
    "change",
    [{"judge_model": "다른-판정-모델"}, {"judge_prompt_version": "2"}],
    ids=["판정 모델", "판정 지시문의 판"],
)
def test_판정_모델과_지시문의_판만_바뀐_묶음은_같은_해시다(
    tmp_path: Path, change: dict[str, JsonValue]
) -> None:
    root = write_bundle(tmp_path / "bundle")
    before = _hash(root)

    edit_json(root / "config.json", change)

    assert _hash(root) == before


@pytest.mark.parametrize(
    "change",
    [
        {"tei_version": "1.10"},
        {"search_candidates": 20},
        {"embedding_model": "다른/모델"},
        {"chunking": {"strategy": "structure_first", "max_tokens": 256, "overlap_tokens": 64}},
    ],
    ids=["TEI 판", "후보 수", "임베딩 모델", "청킹"],
)
def test_검색의_숫자에_닿는_구성이_바뀐_묶음은_다른_해시다(
    tmp_path: Path, change: dict[str, JsonValue]
) -> None:
    root = write_bundle(tmp_path / "bundle")
    before = _hash(root)

    edit_json(root / "config.json", change)

    assert _hash(root) != before


def test_구성_파일의_칸_순서와_들여쓰기만_다르면_같은_해시다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")
    before = _hash(root)

    reordered = dict(reversed(list(CONFIG.items())))
    (root / "config.json").write_text(json.dumps(reordered, ensure_ascii=False), encoding="utf-8")

    assert _hash(root) == before


def test_질의의_글이_바뀐_묶음은_다른_해시다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")
    before = _hash(root)
    first = QUERIES_HUMAN[0]
    assert isinstance(first, dict)

    write_jsonl(
        root / "queries-human.jsonl", [{**first, "query": "다른 질문이다"}, *QUERIES_HUMAN[1:]]
    )

    assert _hash(root) != before


def test_기대_근거가_바뀐_묶음은_다른_해시다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")
    before = _hash(root)
    first = EVIDENCE[0]
    assert isinstance(first, dict)

    write_jsonl(root / "evidence.jsonl", [{**first, "tags": ["다른 표지"]}, EVIDENCE[1]])

    assert _hash(root) != before


def test_문서_목록이_바뀐_묶음은_다른_해시다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")
    before = _hash(root)
    entries: JsonValue = json.loads((root / "documents.json").read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    first = entries[0]
    assert isinstance(first, dict)

    write_json(root / "documents.json", [{**first, "title": "다른 제목"}, *entries[1:]])

    assert _hash(root) != before


def test_머리가_바뀐_묶음은_다른_해시다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")
    before = _hash(root)

    edit_json(root / "eval-set.json", {"name": "다른-이름"})

    assert _hash(root) != before
