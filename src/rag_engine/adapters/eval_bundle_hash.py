"""묶음의 내용 해시(티켓 search-eval 04, 명세 "보고서"의 내용 해시 항목).

머리, 구성, 문서 목록, 기대 근거, 질의 목록 파일로 계산한다. 문서 파일은 문서 목록의 `sha256`이
대신한다. 구성은 파일의 바이트가 아니라 `judge_model`과 `judge_prompt_version`을 뺀 칸을 정렬한
JSON으로 넣는다. 두 칸은 검색의 숫자에 닿지 않는 참고 숫자(LLM 관련성 판정)의 열쇠라서, 넣으면 판정
모델이나 지시문의 판만 바꿔도 기준 보고서가 모두 거부된다. 그래서 같은 해시는 같은 검색 구성과 같은
질문을 뜻한다.

머리를 읽는 `read_eval_set`이 이미 형식을 판정했으므로 여기서는 파일 이름만 꺼낸다. 파일은 그
판정과 따로 한 번 더 읽는다.
"""

import hashlib
import json
from typing import Final

from pydantic import BaseModel, ConfigDict

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.eval_set_reader import HEADER_FILE
from rag_engine.domain.eval_set import EvalSet, search_config_values

_SEPARATOR: Final = b"\0"


class _QueryListRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    file: str


class _Header(BaseModel):
    model_config = ConfigDict(extra="ignore")

    documents: str
    evidence: str
    query_lists: list[_QueryListRef]


def bundle_content_hash(paths: BundlePaths, eval_set: EvalSet) -> str:
    """묶음의 내용 해시(sha256 16진 소문자). 파일을 읽지 못하면 `OSError`나 경로 오류를 올린다."""
    head = paths.resolve(HEADER_FILE).read_bytes()
    header = _Header.model_validate_json(head)
    config = json.dumps(
        search_config_values(eval_set.config),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    parts = [
        ("head", head),
        ("config", config),
        ("documents", _read(paths, header.documents)),
        ("evidence", _read(paths, header.evidence)),
        *((f"query-list:{ref.name}", _read(paths, ref.file)) for ref in header.query_lists),
    ]
    digest = hashlib.sha256()
    for label, data in parts:
        # 이름과 길이를 앞에 붙여, 파일을 옮겨 이어 붙여도 같은 해시가 나오지 않게 한다.
        digest.update(label.encode() + _SEPARATOR + str(len(data)).encode() + _SEPARATOR + data)
    return digest.hexdigest()


def _read(paths: BundlePaths, relative: str) -> bytes:
    return paths.resolve(relative).read_bytes()
