"""평가 세트 묶음의 파일을 읽어 도메인 값으로 바꾼다(명세 "평가 세트의 형식", 티켓 search-eval 02).

읽는 파일은 머리 `eval-set.json`(`format_version`의 major가 다르면 거부한다), 구성 `config.json`,
문서 목록, 기대 근거(JSON Lines), 질의 목록(JSON Lines), 사람 판정 `miss-review.jsonl`(없으면 빈
목록)이다. 칸의 이름과 꼴은 pydantic 모델이 판정하고 모르는 칸은 거부한다. 오류 문장은 칸의 위치와
모델의 메시지만 싣는다. 입력한 값(질문, 글귀)은 싣지 않는다(원칙 V). 모든 경로는 `BundlePaths`를
지난다.

묶음의 파일이 서로 독립이므로 한 파일이 틀려도 나머지를 읽어 오류를 함께 낸다. 머리가 틀리면 다른
파일의 이름을 알 수 없어 거기서 멈춘다. 오류가 하나라도 있으면 `EvalSetFormatError`를 올린다.

날짜 바꾸기 `kst_midnight`는 문서 목록의 `updated_at`(`YYYY-MM-DD`)을 그날 00:00 한국 표준시
(`+09:00`)의 시각으로 바꾼다. 법령과 공공기관 문서의 공포일과 발행일이 한국의 날짜이기 때문이다.
03의 `index`가 같은 함수로 수집의 갱신일을 만든다.
"""

import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Final, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, ValidationError

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.domain.eval_set import (
    SUPPORTED_FORMAT_MAJOR,
    ChunkingConfig,
    EvalConfig,
    EvalDocument,
    EvalFilter,
    EvalProblem,
    EvalQuery,
    EvalSet,
    EvidenceItem,
    Expectation,
    MissReview,
    PageEvidence,
    PassageEvidence,
    QueryList,
    QueryStyle,
)

KST: Final = timezone(timedelta(hours=9))
HEADER_FILE: Final = "eval-set.json"
CONFIG_FILE: Final = "config.json"
MISS_REVIEW_FILE: Final = "miss-review.jsonl"
_DATE_FORM: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# 자릿수를 묶는다. 4300자리를 넘는 수는 `int()`가 오류로 죽기 때문이다.
_VERSION_FORM: Final = re.compile(r"([0-9]{1,9})\.([0-9]{1,9})\.([0-9]{1,9})")
_DATE_MESSAGE: Final = "날짜는 YYYY-MM-DD 꼴이어야 한다"


class EvalSetFormatError(Exception):
    """묶음의 파일을 읽지 못했다. `problems`에 오류가 하나 이상 든다."""

    def __init__(self, problems: tuple[EvalProblem, ...]) -> None:
        super().__init__("; ".join(str(problem) for problem in problems))
        self.problems = problems


def kst_midnight(text: str) -> datetime:
    """`YYYY-MM-DD`를 그날 00:00 `+09:00`의 시각으로 바꾼다. 날짜 꼴이 아니면 `ValueError`다."""
    if not _DATE_FORM.fullmatch(text):
        raise ValueError(_DATE_MESSAGE)
    try:
        day = date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{_DATE_MESSAGE}. 달력에 없는 날이다") from None
    return datetime(day.year, day.month, day.day, tzinfo=KST)


def _updated_at(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError(_DATE_MESSAGE)
    return kst_midnight(value)


def _downloaded_at(value: object) -> date:
    return _updated_at(value).date()


def _offset_time(value: object) -> datetime:
    """오프셋이 붙은 ISO 8601 시각이다. 검색 도구의 필터가 받는 모양과 같다."""
    if not isinstance(value, str):
        raise ValueError("시각은 오프셋이 붙은 ISO 8601 글이어야 한다")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("시각을 ISO 8601로 읽을 수 없다") from None
    if parsed.utcoffset() is None:
        raise ValueError("시각에 오프셋이 없다. 오프셋(+09:00 같은)이 붙어야 한다")
    return parsed


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _QueryListRef(_Model):
    name: str
    style: Literal["question", "keyword"]
    file: str


class _Header(_Model):
    format_version: str
    name: str
    documents: str
    evidence: str
    query_lists: list[_QueryListRef]


class _Chunking(_Model):
    strategy: str
    max_tokens: Annotated[int, Field(gt=0)]
    overlap_tokens: Annotated[int, Field(ge=0)]


class _Config(_Model):
    embedding_model: str
    embedding_dimensions: Annotated[int, Field(gt=0)]
    reranker_model: str
    chunking: _Chunking
    search_candidates: Annotated[int, Field(gt=0)]
    tei_version: str
    judge_model: str
    judge_prompt_version: str


class _Document(_Model):
    key: str
    title: str
    publisher: str
    source_url: str
    license: str
    license_evidence: str
    downloaded_at: Annotated[date, BeforeValidator(_downloaded_at)]
    sha256: str
    bytes: Annotated[int, Field(ge=0)]
    updated_at: Annotated[datetime, BeforeValidator(_updated_at)]


class _Passage(_Model):
    kind: Literal["passage"]
    document: str
    passage: str


class _Page(_Model):
    kind: Literal["page"]
    document: str
    page: Annotated[int, Field(ge=1)]


class _Evidence(_Model):
    id: str
    evidence: list[Annotated[_Passage | _Page, Field(discriminator="kind")]]
    tags: list[str]


class _Filter(_Model):
    groups: list[str] | None = None
    updated_after: Annotated[datetime, BeforeValidator(_offset_time)] | None = None
    updated_before: Annotated[datetime, BeforeValidator(_offset_time)] | None = None


class _Query(_Model):
    evidence_id: str
    query: str
    filter: _Filter | None = None


class _Miss(_Model):
    query_list: str
    evidence_id: str
    cause: str
    confirmed: bool


def read_eval_set(paths: BundlePaths) -> EvalSet:
    """묶음을 읽는다. 하나라도 틀리면 모든 오류를 든 `EvalSetFormatError`를 올린다."""
    header = _read_header(paths)
    config, config_problems = _attempt(lambda: _read_config(paths))
    documents, document_problems = _attempt(lambda: _read_documents(paths, header.documents))
    evidence, evidence_problems = _attempt(lambda: _read_evidence(paths, header.evidence))
    reviews, review_problems = _attempt(lambda: _read_miss_reviews(paths))
    lists = [
        _attempt(lambda ref=ref, index=index: _read_query_list(paths, ref, index))
        for index, ref in enumerate(header.query_lists)
    ]
    problems = (
        *config_problems,
        *document_problems,
        *evidence_problems,
        *review_problems,
        *(problem for _, list_problems in lists for problem in list_problems),
    )
    query_lists = tuple(read for read, _ in lists if read is not None)
    if (
        config is None
        or documents is None
        or evidence is None
        or reviews is None
        or len(query_lists) != len(lists)
    ):
        raise EvalSetFormatError(problems)
    return EvalSet(
        format_version=header.format_version,
        name=header.name,
        config=config,
        documents=documents,
        evidence=evidence,
        query_lists=query_lists,
        miss_reviews=reviews,
    )


def _attempt[T](read: Callable[[], T]) -> tuple[T | None, tuple[EvalProblem, ...]]:
    try:
        return read(), ()
    except EvalSetFormatError as error:
        return None, error.problems


def _fail(where: str, reason: str) -> EvalSetFormatError:
    return EvalSetFormatError((EvalProblem(where, reason),))


def _read_header(paths: BundlePaths) -> _Header:
    header = _parse(HEADER_FILE, _read_text(paths, HEADER_FILE, None), _Header)
    major = _major_of(header.format_version)
    if major is None:
        raise _fail(HEADER_FILE, f"format_version {header.format_version}은(는) 판 꼴이 아니다")
    if major != SUPPORTED_FORMAT_MAJOR:
        raise _fail(
            HEADER_FILE,
            f"format_version {header.format_version}은(는) 이 도구가 읽는 판이 아니다."
            f" major {SUPPORTED_FORMAT_MAJOR}의 판만 읽는다",
        )
    return header


def _major_of(version: str) -> int | None:
    matched = _VERSION_FORM.fullmatch(version)
    return int(matched.group(1)) if matched else None


def _read_config(paths: BundlePaths) -> EvalConfig:
    config = _parse(CONFIG_FILE, _read_text(paths, CONFIG_FILE, None), _Config)
    return EvalConfig(
        embedding_model=config.embedding_model,
        embedding_dimensions=config.embedding_dimensions,
        reranker_model=config.reranker_model,
        chunking=ChunkingConfig(
            strategy=config.chunking.strategy,
            max_tokens=config.chunking.max_tokens,
            overlap_tokens=config.chunking.overlap_tokens,
        ),
        search_candidates=config.search_candidates,
        tei_version=config.tei_version,
        judge_model=config.judge_model,
        judge_prompt_version=config.judge_prompt_version,
    )


def _read_documents(paths: BundlePaths, relative: str) -> tuple[EvalDocument, ...]:
    text = _read_text(paths, relative, "documents")
    try:
        rows = _DOCUMENTS.validate_json(text)
    except ValidationError as error:
        raise EvalSetFormatError(_problems(relative, error)) from None
    return tuple(
        EvalDocument(
            key=row.key,
            title=row.title,
            publisher=row.publisher,
            source_url=row.source_url,
            license=row.license,
            license_evidence=row.license_evidence,
            downloaded_at=row.downloaded_at,
            sha256=row.sha256,
            bytes=row.bytes,
            updated_at=row.updated_at,
        )
        for row in rows
    )


def _read_evidence(paths: BundlePaths, relative: str) -> tuple[EvidenceItem, ...]:
    rows = _parse_lines(relative, _read_text(paths, relative, "evidence"), _Evidence)
    return tuple(
        EvidenceItem(
            id=row.id,
            evidence=tuple(_expectation(entry) for entry in row.evidence),
            tags=tuple(row.tags),
        )
        for row in rows
    )


def _expectation(entry: _Passage | _Page) -> Expectation:
    if isinstance(entry, _Passage):
        return PassageEvidence(document=entry.document, passage=entry.passage)
    return PageEvidence(document=entry.document, page=entry.page)


def _read_query_list(paths: BundlePaths, ref: _QueryListRef, index: int) -> QueryList:
    text = _read_text(paths, ref.file, f"query_lists[{index}].file")
    rows = _parse_lines(ref.file, text, _Query)
    return QueryList(
        name=ref.name,
        style=QueryStyle(ref.style),
        queries=tuple(
            EvalQuery(evidence_id=row.evidence_id, query=row.query, filter=_filter(row.filter))
            for row in rows
        ),
    )


def _filter(value: _Filter | None) -> EvalFilter | None:
    if value is None:
        return None
    return EvalFilter(
        groups=None if value.groups is None else tuple(value.groups),
        updated_after=value.updated_after,
        updated_before=value.updated_before,
    )


def _read_miss_reviews(paths: BundlePaths) -> tuple[MissReview, ...]:
    """사람 판정 파일이 아직 없으면 빈 목록이다(검수 전의 묶음)."""
    try:
        present = paths.resolve(MISS_REVIEW_FILE).exists()
    except BundlePathError as error:
        raise _fail(MISS_REVIEW_FILE, str(error)) from None
    except OSError:
        raise _fail(MISS_REVIEW_FILE, "파일을 읽지 못했다") from None
    if not present:
        return ()
    rows = _parse_lines(MISS_REVIEW_FILE, _read_text(paths, MISS_REVIEW_FILE, None), _Miss)
    return tuple(
        MissReview(
            query_list=row.query_list,
            evidence_id=row.evidence_id,
            cause=row.cause,
            confirmed=row.confirmed,
        )
        for row in rows
    )


def _read_text(paths: BundlePaths, relative: str, field: str | None) -> str:
    """경로 판정을 지난 파일의 글. `field`는 머리의 칸 이름이고, 이름이 정해진 파일이면
    `None`이다."""
    try:
        path = paths.resolve(relative)
    except BundlePathError as error:
        if field is None:
            raise _fail(relative, str(error)) from None
        raise _fail(HEADER_FILE, f"{field}: {error}") from None
    try:
        # 폴더나 FIFO를 열면 읽기가 돌아오지 않을 수 있어 열기 전에 일반 파일인지 본다.
        if path.exists() and not path.is_file():
            raise _fail(relative, "일반 파일이 아니다")
        data = path.read_bytes()
    except FileNotFoundError:
        raise _fail(relative, "파일이 없다") from None
    except OSError:
        raise _fail(relative, "파일을 읽지 못했다") from None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise _fail(relative, "UTF-8 글이 아니다") from None


def _parse[M: BaseModel](where: str, text: str, model: type[M]) -> M:
    try:
        return model.model_validate_json(text)
    except ValidationError as error:
        raise EvalSetFormatError(_problems(where, error)) from None


def _parse_lines[M: BaseModel](where: str, text: str, model: type[M]) -> list[M]:
    """JSON Lines의 줄마다 읽는다. 빈 줄은 건너뛰고, 틀린 줄은 모두 모아 올린다.

    줄은 `\\n`으로만 가른다(끝의 `\\r`은 벗긴다). `splitlines()`는 U+2028 같은 문자도 줄 경계로
    읽어 JSON 문자열 안의 그 문자가 든 올바른 줄을 둘로 쪼갠다.
    """
    rows: list[M] = []
    problems: list[EvalProblem] = []
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.removesuffix("\r")
        if not line.strip():
            continue
        try:
            rows.append(model.model_validate_json(line))
        except ValidationError as error:
            problems.extend(_problems(f"{where}:{number}", error))
    if problems:
        raise EvalSetFormatError(tuple(problems))
    return rows


def _problems(where: str, error: ValidationError) -> tuple[EvalProblem, ...]:
    """모델의 오류를 칸의 위치와 메시지로만 옮긴다. 질문과 글귀 같은 입력한 값은 싣지 않는다.

    모르는 칸의 이름과 판별 태그의 값은 pydantic의 메시지에 실려 오류 문장에 나올 수 있다.
    """
    return tuple(
        EvalProblem(where, _reason(".".join(str(part) for part in item["loc"]), item["msg"]))
        for item in error.errors(include_url=False, include_context=False, include_input=False)
    )


def _reason(location: str, message: str) -> str:
    return f"{location}: {message}" if location else message


_DOCUMENTS: Final = TypeAdapter(list[_Document])
