"""시험이 임시 폴더에 짓는 작은 평가 세트 묶음과 폴더 링크(티켓 search-eval 02).

묶음의 형식은 명세 "평가 세트의 형식"과 "공공 문서 묶음"이 정한다. 문서 파일은 어떤 바이트여도
되므로(`validate`는 파싱하지 않는다) 짧은 글로 둔다. 링크는 그 플랫폼에서 권한 없이 만들 수 있는
폴더 링크로 짓는다(윈도는 junction, 그 밖은 심볼릭 링크).
"""

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from rag_engine.domain.entities import JsonValue

KB = 1024

BODY_A = "연차휴가는 입사 일 년 뒤부터 발생한다.".encode()
BODY_B = "출장비는 실비로 정산한다.".encode()

PASSAGE = "연차휴가는 입사 일 년 뒤부터 발생한다"
LICENSE = "법령 등(저작권법 제7조)"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document_entry(
    key: str, data: bytes, *, updated_at: str = "2026-01-15"
) -> dict[str, JsonValue]:
    return {
        "key": key,
        "title": f"제목 {key}",
        "publisher": "행정안전부",
        "source_url": f"https://example.invalid/{key}",
        "license": LICENSE,
        "license_evidence": "문서 1쪽",
        "downloaded_at": "2026-11-13",
        "sha256": sha256_of(data),
        "bytes": len(data),
        "updated_at": updated_at,
    }


CONFIG: dict[str, JsonValue] = {
    "embedding_model": "BAAI/bge-m3",
    "embedding_dimensions": 1024,
    "reranker_model": "BAAI/bge-reranker-v2-m3",
    "chunking": {"strategy": "structure_first", "max_tokens": 512, "overlap_tokens": 64},
    "search_candidates": 50,
    "tei_version": "1.9",
    "judge_model": "none",
    "judge_prompt_version": "1",
}

HEADER: dict[str, JsonValue] = {
    "format_version": "1.0.0",
    "name": "tiny",
    "documents": "documents.json",
    "evidence": "evidence.jsonl",
    "query_lists": [
        {"name": "human", "style": "question", "file": "queries-human.jsonl"},
        {"name": "keyword", "style": "keyword", "file": "queries-keyword.jsonl"},
    ],
}

EVIDENCE: list[JsonValue] = [
    {
        "id": "q1",
        "evidence": [{"kind": "passage", "document": "a.docx", "passage": PASSAGE}],
        "tags": ["table"],
    },
    {
        "id": "q2",
        "evidence": [{"kind": "page", "document": "sub/b.pdf", "page": 2}],
        "tags": [],
    },
]

QUERIES_HUMAN: list[JsonValue] = [
    {"evidence_id": "q1", "query": "입사하고 언제부터 연차가 생기나요"},
    {
        "evidence_id": "q2",
        "query": "출장비는 어떻게 정산하나요",
        "filter": {"updated_after": "2026-01-01T00:00:00+09:00"},
    },
]

QUERIES_KEYWORD: list[JsonValue] = [{"evidence_id": "q1", "query": "연차 발생 시기"}]


def write_json(path: Path, value: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> JsonValue:
    value: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    return value


def write_bundle(root: Path) -> Path:
    """문제 없는 묶음을 `root`에 짓는다. 문서는 `a.docx`, `sub/b.pdf` 둘이다."""
    (root / "documents" / "sub").mkdir(parents=True)
    (root / "documents" / "a.docx").write_bytes(BODY_A)
    (root / "documents" / "sub" / "b.pdf").write_bytes(BODY_B)
    write_json(root / "eval-set.json", HEADER)
    write_json(root / "config.json", CONFIG)
    write_json(
        root / "documents.json",
        [document_entry("a.docx", BODY_A), document_entry("sub/b.pdf", BODY_B)],
    )
    write_jsonl(root / "evidence.jsonl", EVIDENCE)
    write_jsonl(root / "queries-human.jsonl", QUERIES_HUMAN)
    write_jsonl(root / "queries-keyword.jsonl", QUERIES_KEYWORD)
    return root


def edit_json(path: Path, change: Mapping[str, JsonValue]) -> None:
    """JSON 객체 파일의 칸을 바꾼다. 값이 `None`인 칸은 지운다."""
    value = read_json(path)
    assert isinstance(value, dict)
    merged = {key: item for key, item in {**value, **change}.items() if item is not None}
    write_json(path, merged)


def make_folder_link(link: Path, target: Path) -> None:
    """`link`를 `target` 폴더로 가는 링크로 짓는다. 권한이 없어도 만들 수 있는 링크만 쓴다."""
    if sys.platform == "win32":
        done = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert done.returncode == 0, done.stderr
    else:
        os.symlink(target, link, target_is_directory=True)
