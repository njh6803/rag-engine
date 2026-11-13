"""평가 세트 묶음의 파일 판정(명세 "평가 세트의 형식"의 `validate`가 보는 것, 티켓 search-eval 02).

데이터베이스 없이 묶음의 폴더만 본다. 문서 목록의 모든 파일이 `documents/`에 있고 해시가 맞는지,
목록에 없는 파일이 `documents/`에 없는지, 문서 파일의 합이 30MB 이하인지, 도구가 묶음에서 여는
이름이 정해진 파일(`records/`와 그 안의 기록 파일, `judgments.jsonl`, 기준 보고서)이 묶음 밖을
가리키지 않는지다. 읽는 파일만이 아니라 쓸 파일도 같은 판정을 지난다(`BundlePaths`).

문서의 해시는 원본 바이트의 sha256 16진 소문자 글이고 글자 그대로 견준다(수집이 내는 내용 해시와
같은 표기다. `src/rag_engine/app/ingest.py`). `documents/` 안의 링크는 따라가지 않는다. 링크 자체를
오류로 알리고 그 안의 파일은 세지 않는다.

못 보는 것. 파일의 글(글귀가 문서의 본문에 드는지)은 파싱이 필요해 `--indexed`가 본다. 해시를 낸 뒤
파일이 바뀌는 경쟁은 막지 않는다.
"""

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.domain.eval_set import MAX_DOCUMENT_BYTES, EvalDocument, EvalProblem, EvalSet

DOCUMENTS_FOLDER: Final = "documents"
_CHUNK_BYTES: Final = 1024 * 1024
# 도구가 묶음에서 여는 이름이 정해진 파일이다. 읽지 않는 것도 쓰는 하위 명령이 있으므로 함께
# 판정한다.
_NAMED_FILES: Final = (
    "config.json",
    "miss-review.jsonl",
    "judgments.jsonl",
    "baseline-fast.json",
    "baseline-full.json",
)
_RECORDS_FOLDER: Final = "records"


def check_bundle_files(paths: BundlePaths, eval_set: EvalSet) -> tuple[EvalProblem, ...]:
    """묶음 폴더의 파일 오류를 모두 낸다. 문제가 없으면 빈 튜플이다."""
    checked = [_check_document(paths, document) for document in eval_set.documents]
    total = sum(size for size, _ in checked)
    problems = [problem for _, found in checked for problem in found]
    problems.extend(_undeclared(paths, {document.key for document in eval_set.documents}))
    if total > MAX_DOCUMENT_BYTES:
        problems.append(
            EvalProblem(
                f"{DOCUMENTS_FOLDER}/",
                f"문서 파일의 합 {total}바이트가 상한 30MB({MAX_DOCUMENT_BYTES}바이트)를 넘는다",
            )
        )
    problems.extend(_named_file_problems(paths))
    return tuple(problems)


def _check_document(paths: BundlePaths, document: EvalDocument) -> tuple[int, list[EvalProblem]]:
    """파일의 크기와 오류. 경로가 거부되었거나 파일이 없으면 크기는 0이다."""
    try:
        path = paths.resolve(document.key, under=DOCUMENTS_FOLDER)
    except BundlePathError as error:
        return 0, [EvalProblem(document.key, str(error))]
    try:
        if not path.is_file():
            return 0, [EvalProblem(document.key, "문서 파일이 없다")]
        digest, size = _digest(path)
    except OSError:
        return 0, [EvalProblem(document.key, "문서 파일을 읽지 못했다")]
    if digest != document.sha256:
        return size, [
            EvalProblem(
                document.key,
                f"문서 파일의 해시가 목록과 다르다(목록 {document.sha256}, 파일 {digest})",
            )
        ]
    return size, []


def _digest(path: Path) -> tuple[str, int]:
    """파일의 sha256 16진 소문자 글과 바이트 수. 한 번에 올리지 않고 조각으로 읽는다."""
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_BYTES):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def _undeclared(paths: BundlePaths, declared: set[str]) -> list[EvalProblem]:
    """`documents/`의 파일 가운데 목록에 없는 것과, 따라가지 않은 링크를 낸다."""
    try:
        folder = paths.resolve(DOCUMENTS_FOLDER)
    except BundlePathError as error:
        return [EvalProblem(DOCUMENTS_FOLDER, str(error))]
    problems: list[EvalProblem] = []
    unreadable: list[str] = []
    entries = list(_entries(folder, "", unreadable))
    problems.extend(EvalProblem(name, "폴더를 읽을 수 없다") for name in unreadable)
    for relative, is_link in entries:
        if is_link:
            problems.append(
                EvalProblem(
                    relative,
                    "링크이다. 따라가지 않는다. 문서는 documents/ 안의 실제 파일이어야 한다",
                )
            )
        elif relative not in declared:
            problems.append(
                EvalProblem(
                    relative,
                    "목록에 없는 파일이다. documents/의 파일은 문서 목록에 모두 올라야 한다",
                )
            )
    return problems


def _entries(folder: Path, prefix: str, unreadable: list[str]) -> Iterator[tuple[str, bool]]:
    """`folder` 아래의 파일과 링크를 (documents/ 기준 POSIX 경로, 링크인가)로 낸다. 링크는 내려가지
    않는다. 폴더가 없으면 아무것도 내지 않고, 있는데 읽지 못하면 그 이름을 `unreadable`에 더한다."""
    try:
        with os.scandir(folder) as scan:
            entries = sorted(scan, key=lambda entry: entry.name)
    except (FileNotFoundError, NotADirectoryError):
        return
    except OSError:
        unreadable.append(f"{DOCUMENTS_FOLDER}/{prefix}".rstrip("/"))
        return
    for entry in entries:
        relative = prefix + entry.name
        if entry.is_symlink() or entry.is_junction():
            yield relative, True
        elif entry.is_dir(follow_symlinks=False):
            yield from _entries(Path(entry.path), relative + "/", unreadable)
        else:
            yield relative, False


def _named_file_problems(paths: BundlePaths) -> list[EvalProblem]:
    """이름이 정해진 파일과 `records/`의 파일이 묶음 밖을 가리키는지 본다."""
    names = [*_NAMED_FILES, _RECORDS_FOLDER]
    try:
        records = paths.resolve(_RECORDS_FOLDER)
    except BundlePathError:
        records = None  # 아래 반복이 같은 까닭의 오류를 낸다
    problems: list[EvalProblem] = []
    if records is not None and records.is_dir():
        try:
            children = sorted(records.iterdir())
        except OSError:
            problems.append(EvalProblem(_RECORDS_FOLDER, "폴더를 읽을 수 없다"))
        else:
            names.extend(f"{_RECORDS_FOLDER}/{child.name}" for child in children)
    for name in names:
        try:
            paths.resolve(name)
        except BundlePathError as error:
            problems.append(EvalProblem(name, str(error)))
    return problems
