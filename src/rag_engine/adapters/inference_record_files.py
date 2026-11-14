"""추론 기록 파일의 형식과 읽기·쓰기(명세 search-eval "추론 기록", 티켓 07).

묶음의 `records/` 폴더에 기록 파일 셋과 그것을 설명하는 `records.json`이 든다.

- `chunk-embeddings.keys`·`.f32`: 조각의 임베딩. 주인은 `index`다.
- `query-embeddings.keys`·`.f32`: 질의의 임베딩. 주인은 `run`이다.
- `rerank.jsonl`: 리랭크 점수. 주인은 전체 실행의 `run`이다.

`.keys`는 열쇠를 사전 순으로 한 줄에 하나씩, `.f32`는 같은 순서의 벡터를 float32 리틀 엔디언으로
이어 붙인 것, `rerank.jsonl`은 열쇠 순의 열쇠와 점수다. 정렬해 쓰므로 같은 내용은 같은 바이트다.
`records.json`은 `format_version`(첫 판 `"1.0.0"`)과 기록 파일마다의 항목(모델 이름, 차원, 수, 만든
TEI의 판과 장치, 요청 지문)을 정렬해 적는다. 임베딩 값은 float32로 쓰이므로 계산한 값과 읽은 값이
조금 다르다. 읽은 값은 다시 써도 같은 바이트다.

기록 파일을 읽고 쓰는 경로는 임시 파일(`<이름>.tmp`)까지 묶음의 경로 판정(`BundlePaths`)을 지난다.
`records/`의 크기를 세는 `records_size`만 자식 파일을 판정 없이 훑고 크기만 읽는다. 오류 문장은
파일의 내용이 아니라 까닭만 싣는다(원칙 V).
"""

import json
import os
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths

RECORDS_FOLDER: Final = "records"
MANIFEST_NAME: Final = "records.json"
FORMAT_VERSION: Final = "1.0.0"
SUPPORTED_MAJOR: Final = "1"
# 기록 파일의 합 상한이다(`records.json` 포함. 명세 "추론 기록").
MAX_RECORDS_BYTES: Final = 20 * 1024 * 1024
TEMPORARY_SUFFIX: Final = ".tmp"
_FLOAT32_BYTES: Final = 4


class RecordKind(StrEnum):
    """기록 파일의 종류. 값은 파일 이름의 머리이고 `records.json`의 `files` 열쇠다."""

    CHUNK_EMBEDDINGS = "chunk-embeddings"
    QUERY_EMBEDDINGS = "query-embeddings"
    RERANK = "rerank"


class RecordsFormatError(Exception):
    """기록 파일이나 `records.json`의 형식이 맞지 않는다. 메시지는 까닭이고 내용은 싣지 않는다."""


def failure_reason(error: Exception) -> str:
    """기록을 읽거나 쓰지 못한 까닭. 형식 오류는 까닭이 적힌 문장이고, 그 밖의 오류는 종류만 싣는다
    (경로나 내용을 싣지 않는다, 원칙 V)."""
    return str(error) if isinstance(error, RecordsFormatError) else type(error).__name__


class RecordEntry(BaseModel):
    """`records.json`의 기록 파일 하나. `dimensions`는 임베딩만 갖는다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    dimensions: int | None
    count: int
    tei_version: str
    device: str
    request_fingerprint: str


class Manifest(BaseModel):
    """`records.json`의 값."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: str
    files: Mapping[str, RecordEntry]

    def render(self) -> bytes:
        """정렬해 쓴 글. 같은 내용은 같은 바이트다."""
        values = {
            "format_version": self.format_version,
            "files": {name: entry.model_dump() for name, entry in sorted(self.files.items())},
        }
        return (json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class _RerankRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    score: float


def record_files(kind: RecordKind) -> tuple[str, ...]:
    """종류마다 `records/` 안의 파일 이름."""
    if kind is RecordKind.RERANK:
        return (f"{kind.value}.jsonl",)
    return (f"{kind.value}.keys", f"{kind.value}.f32")


def read_manifest(paths: BundlePaths) -> Manifest | None:
    """`records.json`을 읽는다. 없으면 `None`이다. 형식이 틀렸거나 major가 다른 판이면
    `RecordsFormatError`이고, 경로가 묶음 밖을 가리키면 `BundlePathError`다."""
    path = paths.resolve(f"{RECORDS_FOLDER}/{MANIFEST_NAME}")
    if not path.is_file():
        return None
    try:
        manifest = Manifest.model_validate_json(path.read_bytes())
    except ValidationError:
        raise RecordsFormatError(f"{MANIFEST_NAME}의 형식이 맞지 않는다") from None
    if manifest.format_version.split(".")[0] != SUPPORTED_MAJOR:
        raise RecordsFormatError(
            f"{MANIFEST_NAME}의 판 {manifest.format_version}은"
            f" 이 도구가 읽는 판(major {SUPPORTED_MAJOR})이 아니다"
        )
    return manifest


def read_embedding_values(
    paths: BundlePaths, kind: RecordKind, entry: RecordEntry
) -> dict[str, tuple[float, ...]]:
    """임베딩 기록 파일의 값을 읽는다. 항목의 수와 차원에 맞지 않는 파일은 거부한다."""
    keys_name, vectors_name = record_files(kind)
    dimensions = entry.dimensions
    if dimensions is None or dimensions <= 0:
        raise RecordsFormatError(f"{kind.value}의 항목에 차원이 없다")
    keys_text = _read_record_bytes(paths, keys_name).decode("utf-8", errors="replace")
    vectors = _read_record_bytes(paths, vectors_name)
    keys = keys_text.splitlines()
    step = dimensions * _FLOAT32_BYTES
    if len(keys) != entry.count or len(vectors) != entry.count * step:
        raise RecordsFormatError(
            f"{kind.value}의 파일이 {MANIFEST_NAME}에 적힌 수와 차원에 맞지 않는다"
        )
    unpack = struct.Struct(f"<{dimensions}f").unpack_from
    offsets = range(0, len(vectors), step)
    return {key: tuple(unpack(vectors, offset)) for key, offset in zip(keys, offsets, strict=True)}


def read_rerank_values(paths: BundlePaths, kind: RecordKind) -> dict[str, float]:
    """리랭크 기록 파일의 점수를 읽는다."""
    (name,) = record_files(kind)
    values: dict[str, float] = {}
    for line in _read_record_bytes(paths, name).decode("utf-8", errors="replace").splitlines():
        try:
            row = _RerankRow.model_validate_json(line)
        except ValidationError:
            raise RecordsFormatError(f"{kind.value}의 줄 형식이 맞지 않는다") from None
        values[row.key] = row.score
    return values


def render_embedding_files(
    values: Mapping[str, Sequence[float]], *, dimensions: int
) -> tuple[bytes, bytes]:
    """(`.keys`의 바이트, `.f32`의 바이트). 열쇠 순으로 정렬한다."""
    ordered = sorted(values)
    pack = struct.Struct(f"<{dimensions}f").pack
    chunks: list[bytes] = []
    for key in ordered:
        vector = values[key]
        if len(vector) != dimensions:
            raise ValueError(f"벡터의 차원 {len(vector)}이 {dimensions}과 다르다")
        chunks.append(pack(*vector))
    keys = "".join(f"{key}\n" for key in ordered).encode()
    return keys, b"".join(chunks)


def render_rerank_file(values: Mapping[str, float]) -> bytes:
    """열쇠 순의 열쇠와 점수. 줄마다 JSON 하나다."""
    lines = (
        json.dumps({"key": key, "score": values[key]}, separators=(",", ":"))
        for key in sorted(values)
    )
    return "".join(f"{line}\n" for line in lines).encode()


def write_record_files(
    paths: BundlePaths, kind: RecordKind, contents: Mapping[str, bytes], entry: RecordEntry
) -> None:
    """기록 파일들을 쓰고 `records.json`의 그 종류 항목만 `entry`로 바꾼다. 다른 종류의 파일과
    항목은 건드리지 않는다. 자료 파일을 먼저 쓰고 `records.json`을 마지막에 쓴다. 파일마다 임시
    파일에 쓴 뒤 바꿔 넣어 중간에 끊겨도 반쪽 파일이 남지 않는다. 경로가 묶음 밖을 가리키면
    아무것도 쓰기 전에 `BundlePathError`다."""
    targets = [_target(paths, name, data) for name, data in contents.items()]
    manifest_target = _target(paths, MANIFEST_NAME, b"")
    current = read_manifest(paths)
    files = {} if current is None else dict(current.files)
    files[kind.value] = entry
    manifest = Manifest(format_version=FORMAT_VERSION, files=files)
    for target in targets:
        _replace(target)
    _replace(_Target(manifest_target.path, manifest_target.temporary, manifest.render()))


def check_writable(paths: BundlePaths, kind: RecordKind) -> None:
    """`kind`의 기록 파일과 `records.json`을 쓸 경로(임시 파일 포함)가 묶음 안이고 임시 파일이
    최종 파일 바로 옆인지 본다. 아니면 `BundlePathError`다. 아무것도 쓰지 않는다. 종류가 여럿인
    명령이 첫 종류를 쓴 뒤에 다음 종류의 경로에서 거부해 반쪽만 쓰는 일을 막으려고, 쓰기 전에 모두
    부른다."""
    for name in (*record_files(kind), MANIFEST_NAME):
        _target(paths, name, b"")


def records_size(paths: BundlePaths) -> int:
    """`records/`의 파일 크기의 합. 폴더가 없으면 0이다. 쓰다 끊겨 남은 임시 파일(`.tmp`)은 세지
    않는다."""
    folder = paths.resolve(RECORDS_FOLDER)
    if not folder.is_dir():
        return 0
    return sum(
        child.stat().st_size
        for child in folder.iterdir()
        if child.is_file() and child.suffix != TEMPORARY_SUFFIX
    )


def _read_record_bytes(paths: BundlePaths, name: str) -> bytes:
    path = paths.resolve(f"{RECORDS_FOLDER}/{name}")
    if not path.is_file():
        raise RecordsFormatError(f"{RECORDS_FOLDER}/{name}이(가) 없다")
    try:
        return path.read_bytes()
    except OSError:
        raise RecordsFormatError(f"{RECORDS_FOLDER}/{name}을(를) 읽지 못했다") from None


@dataclass(frozen=True)
class _Target:
    """쓸 파일 하나: 최종 경로와 임시 파일 경로(둘 다 묶음 안임을 판정했다)와 내용."""

    path: Path
    temporary: Path
    data: bytes


def _target(paths: BundlePaths, name: str, data: bytes) -> _Target:
    """`records/<name>`과 그 임시 파일 경로를 묶음의 경로 판정에 건다. 임시 파일이 링크이면 그 링크
    로 쓰게 되므로, 묶음 밖을 가리키면 최종 경로와 똑같이 거부하고, 묶음 안이어도 풀린 경로가
    최종 경로 바로 옆의 `<이름>.tmp`가 아니면(최종 파일이나 문서 파일 같은 다른 자리로 풀리면)
    거부한다. 그대로 쓰면 그 다른 자리를 덮어쓰고 끝의 `unlink`가 지운다."""
    path = paths.resolve(f"{RECORDS_FOLDER}/{name}")
    temporary = paths.resolve(f"{RECORDS_FOLDER}/{name}{TEMPORARY_SUFFIX}")
    if temporary != path.with_name(f"{path.name}{TEMPORARY_SUFFIX}"):
        raise BundlePathError(
            f"{RECORDS_FOLDER}/{name}{TEMPORARY_SUFFIX}은(는) 링크를 풀면 다른 자리를 가리킨다."
            " 기록의 임시 파일은 최종 파일 바로 옆이어야 한다"
        )
    return _Target(path, temporary, data)


def _replace(target: _Target) -> None:
    target.path.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.temporary.write_bytes(target.data)
        os.replace(target.temporary, target.path)
    finally:
        target.temporary.unlink(missing_ok=True)
