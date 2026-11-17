"""`validate`의 추론 기록 판정(티켓 search-eval 07, 명세 "추론 기록").

데이터베이스도 TEI 끝점도 쓰지 않고 묶음의 파일과 이 체크아웃의 코드, `compose.eval.yml`만 읽는다.
오류는 까닭을 알리고 파일의 내용은 싣지 않는다(원칙 V). 요청 지문과 TEI 판의 오류(3, 4)는 다시 만들
기록 파일과 명령도 알린다.

1. `records/`의 파일 크기 합이 20MB 이하인지(`records.json` 포함).
2. `records.json`의 판이 이 도구가 읽는 판인지.
3. 기록 파일마다의 요청 지문이 이 체크아웃의 어댑터가 내는 값과 같은지. 다르면 그 기록 파일을
   다시 만든다.
4. `records.json`의 TEI 판이 `config.json`의 `tei_version`과 같은지.
5. `compose.eval.yml`의 TEI 이미지 태그(장치를 가리키는 머리를 뗀 것)가 `tei_version`과 같은지.
   기록이 없는 묶음에도 적용한다. 구성이 어느 TEI로 기록을 만들지 정하기 때문이다.

못 보는 것. 기록 파일의 값 자체가 그 TEI와 모델이 낸 것인지는 알 수 없다. 기록 파일 안의 형식(열쇠의
수, 벡터의 크기, `records.json`의 `count`와의 일치)도 이 판정은 보지 않는다. 어긋난 기록은 읽을
때(`read_embedding_values`와 `read_rerank_values`) `RecordsFormatError`로 막히고, `validate`는 그
상태에서도 통과한다(2026-11-14 셀프 리뷰가 손으로 만든 어긋남에서 문제 0을 확인했다).
"""

import re
from pathlib import Path
from typing import Final

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.adapters.inference_record_files import (
    MANIFEST_NAME,
    MAX_RECORDS_BYTES,
    RECORDS_FOLDER,
    RecordKind,
    RecordsFormatError,
    read_manifest,
    record_files,
    records_size,
)
from rag_engine.adapters.inference_records import rebuild_command, request_fingerprint
from rag_engine.domain.eval_set import EvalConfig, EvalProblem

COMPOSE_NAME: Final = "compose.eval.yml"
_MEGABYTE: Final = 1024 * 1024
_IMAGE: Final = re.compile(r"text-embeddings-inference:(?P<tag>[A-Za-z0-9._-]+)")
# 태그는 `<장치>-<판>`(`cpu-1.9.4`, `turing-1.9.4`, `89-1.9.4`)이거나 머리가 없는 `<판>`이다.
_TAG: Final = re.compile(r"^(?:[A-Za-z0-9]+-)?(?P<version>\d+(?:\.\d+)*)$")


def check_records(
    paths: BundlePaths, config: EvalConfig, compose_file: Path
) -> tuple[EvalProblem, ...]:
    """추론 기록의 오류를 모두 낸다. 문제가 없으면 빈 튜플이다."""
    problems = [*_check_size(paths), *_check_manifest(paths, config)]
    problems.extend(_check_compose(compose_file, config.tei_version))
    return tuple(problems)


def _check_size(paths: BundlePaths) -> list[EvalProblem]:
    try:
        size = records_size(paths)
    except (BundlePathError, OSError):
        return [
            EvalProblem(
                RECORDS_FOLDER, "기록 폴더를 읽지 못했다(묶음 밖을 가리키는 경로이거나 읽기 오류다)"
            )
        ]
    if size > MAX_RECORDS_BYTES:
        limit = MAX_RECORDS_BYTES // _MEGABYTE
        return [
            EvalProblem(
                RECORDS_FOLDER, f"기록 파일의 크기 합이 {size}바이트로 {limit}MB 상한을 넘는다"
            )
        ]
    return []


def _check_manifest(paths: BundlePaths, config: EvalConfig) -> list[EvalProblem]:
    subject = f"{RECORDS_FOLDER}/{MANIFEST_NAME}"
    try:
        manifest = read_manifest(paths)
    except RecordsFormatError as error:
        return [EvalProblem(subject, str(error))]
    except (BundlePathError, OSError):
        return []  # 경로 오류는 크기 판정이 이미 알렸다.
    if manifest is None:
        return []
    problems: list[EvalProblem] = []
    for name, entry in sorted(manifest.files.items()):
        try:
            kind = RecordKind(name)
        except ValueError:
            problems.append(EvalProblem(subject, f"알 수 없는 기록 종류 {name}이(가) 적혀 있다"))
            continue
        files = ", ".join(f"{RECORDS_FOLDER}/{file}" for file in record_files(kind))
        rebuild = f"{files}을(를) {rebuild_command(kind)}로 다시 만든다"
        if entry.request_fingerprint != request_fingerprint(kind):
            problems.append(
                EvalProblem(files, f"요청 지문이 이 체크아웃의 어댑터와 다르다. {rebuild}")
            )
        if entry.tei_version != config.tei_version:
            problems.append(
                EvalProblem(
                    files,
                    f"{MANIFEST_NAME}의 tei_version {entry.tei_version}이 config.json의"
                    f" {config.tei_version}과 다르다. {rebuild}",
                )
            )
    return problems


def _check_compose(compose_file: Path, tei_version: str) -> list[EvalProblem]:
    try:
        text = compose_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [
            EvalProblem(COMPOSE_NAME, "읽지 못했다. TEI 이미지 태그를 config.json과 견주지 못한다")
        ]
    tags = _IMAGE.findall(text)
    if not tags:
        return [EvalProblem(COMPOSE_NAME, "TEI 이미지 줄(text-embeddings-inference:<태그>)이 없다")]
    problems: list[EvalProblem] = []
    for tag in dict.fromkeys(tags):
        matched = _TAG.match(tag)
        if matched is None:
            problems.append(
                EvalProblem(COMPOSE_NAME, f"TEI 이미지 태그 {tag}에서 판을 읽지 못했다")
            )
        elif matched.group("version") != tei_version:
            problems.append(
                EvalProblem(
                    COMPOSE_NAME,
                    f"TEI 이미지 태그 {tag}의 판 {matched.group('version')}이 config.json의"
                    f" tei_version {tei_version}과 다르다",
                )
            )
    return problems
