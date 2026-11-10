"""색인 판 요소 넷을 설정에서 계산하는 함수(명세 "데이터 모델과 스키마"의 색인 판 요소)."""

from dataclasses import replace
from importlib.metadata import version

import pytest

from rag_engine.adapters import index_elements
from rag_engine.adapters.index_elements import compute_index_elements
from rag_engine.domain.entities import ChunkingConfig
from rag_engine.domain.errors import ConfigurationError

CHUNKING = ChunkingConfig(strategy="structure_first", max_tokens=512, overlap_tokens=64)


def _newer_version(distribution: str) -> str:
    return "9.9.9"


def test_같은_설정은_같은_요소를_낸다() -> None:
    assert compute_index_elements("BAAI/bge-m3", 1024, CHUNKING) == compute_index_elements(
        "BAAI/bge-m3", 1024, CHUNKING
    )


def test_스키마_판과_임베딩_모델과_차원을_요소에_싣는다() -> None:
    elements = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)

    assert elements.schema_version == 1
    assert elements.embedding_model == "BAAI/bge-m3"
    assert elements.embedding_dimensions == 1024


@pytest.mark.parametrize(
    "changed",
    [
        replace(CHUNKING, max_tokens=256),
        replace(CHUNKING, overlap_tokens=32),
    ],
    ids=["상한", "겹침"],
)
def test_청킹_설정이_바뀌면_청킹_해시가_바뀐다(changed: ChunkingConfig) -> None:
    before = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)
    after = compute_index_elements("BAAI/bge-m3", 1024, changed)

    assert after.chunking_hash != before.chunking_hash
    assert after.tokenizer_version == before.tokenizer_version


def test_토크나이저_판은_kiwipiepy와_모델과_키워드_규칙의_판을_붙인다() -> None:
    elements = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)

    assert version("kiwipiepy") in elements.tokenizer_version
    assert version("kiwipiepy_model") in elements.tokenizer_version
    assert f"keyword-rules {index_elements.KEYWORD_RULES_VERSION}" in elements.tokenizer_version


def test_문장_분리기_판이_바뀌면_청킹_해시가_바뀐다(monkeypatch: pytest.MonkeyPatch) -> None:
    before = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)
    monkeypatch.setattr(index_elements, "_installed_version", _newer_version)

    after = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)

    assert after.chunking_hash != before.chunking_hash
    assert after.tokenizer_version != before.tokenizer_version


def test_구조_우선_전략의_구현_판이_바뀌면_청킹_해시만_바뀐다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)
    monkeypatch.setattr(index_elements, "STRUCTURE_FIRST_VERSION", "2")

    after = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)

    assert after.chunking_hash != before.chunking_hash
    assert after.tokenizer_version == before.tokenizer_version


def test_키워드_규칙의_판이_바뀌면_토크나이저_판만_바뀐다(monkeypatch: pytest.MonkeyPatch) -> None:
    before = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)
    monkeypatch.setattr(index_elements, "KEYWORD_RULES_VERSION", "2")

    after = compute_index_elements("BAAI/bge-m3", 1024, CHUNKING)

    assert after.tokenizer_version != before.tokenizer_version
    assert after.chunking_hash == before.chunking_hash


def test_모르는_청킹_전략은_설정_오류다() -> None:
    with pytest.raises(ConfigurationError, match="청킹 전략"):
        compute_index_elements("BAAI/bge-m3", 1024, replace(CHUNKING, strategy="unknown"))
