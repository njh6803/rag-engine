"""모델이 계산한 결과를 기록 파일로 저장해 다시 쓰는 어댑터(명세 search-eval "추론 기록", 티켓 07).

`Embedder`와 `Reranker` 포트를 감싼다. 감싼 포트를 부르기 전에 기록을 보고, 없으면 감싼 포트를 불러
결과를 쓴다. 토큰 세기(`count_tokens`, `special_token_count`, `token_spans`)는 기록하지 않고 감싼
포트로 그대로 넘긴다. 평가 도구의 조립만 이것을 쓰고 서버와 작업자의 조립은 쓰지 않는다(작업자의
조립은 임베딩 포트를 감싸는 걸이만 연다).

열쇠는 모델 이름과 글에서 낸다. 임베딩은 `sha256(모델 이름, NUL, 글의 UTF-8 바이트)`이고 리랭크는
`sha256(모델 이름, NUL, 질의, NUL, 글)`이다. 모델 이름은 `config.json`의 것이라 모델이 다르면 기록의
값을 쓰지 않는다.

기록 방식은 셋이다. `read`는 기록 파일을 고치지 않는다. 새로 계산한 임베딩이 상한(100개)을 넘으면
계산을 멈춘다. `write`는 상한 없이 계산하고, 명령이 끝나면 그 명령이 주인인 파일만 이번 실행이 쓴
열쇠 전부로 다시 쓴다. `off`는 기록을 읽지도 쓰지도 않는다(호출하는 쪽이 감싸지 않는다).

상한을 넘으면 감싼 포트가 `PermanentFailure`를 올려 호출한 쪽(작업자의 작업, 평가 유스케이스)이
멈추게 하고, 기록기가 그 사실(`exceeded`, `unavailable`)을 남긴다. 호출한 명령은 끝난 뒤 그것을 읽어
어느 명령을 `--records write`로 다시 돌려 어느 파일을 커밋하는지 알린다(`RecordsRun.notices`).
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.inference_record_files import (
    FORMAT_VERSION,
    MANIFEST_NAME,
    RECORDS_FOLDER,
    Manifest,
    RecordEntry,
    RecordKind,
    check_writable,
    read_embedding_values,
    read_manifest,
    read_rerank_values,
    record_files,
    render_embedding_files,
    render_rerank_file,
    write_record_files,
)
from rag_engine.adapters.tei import EMBEDDING_REQUEST, RERANK_REQUEST
from rag_engine.app.eval_report import RecordsSummary
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.eval_set import EvalConfig
from rag_engine.domain.ports import Embedder, EmbedderFor, Reranker

# `read`에서 새로 계산해도 되는 임베딩의 수. 코어 4개에서 약 200초다(명세 "추론 기록").
READ_COMPUTE_LIMIT: Final = 100
_NUL: Final = b"\0"
_TOOL_COMMAND: Final = "uv run python tools/search_eval.py"
_DEVICE_OPTION: Final = "--records write --tei-device <cpu|gpu>"


class RecordMode(StrEnum):
    READ = "read"
    WRITE = "write"
    OFF = "off"


@dataclass(frozen=True, slots=True)
class RecordsOptions:
    """`--records`와 `--tei-device`. `device`는 `write`가 `records.json`에 적는 장치다."""

    mode: RecordMode
    device: str | None = None


def embedding_key(model: str, text: str) -> str:
    return hashlib.sha256(model.encode() + _NUL + text.encode("utf-8")).hexdigest()


def rerank_key(model: str, query: str, text: str) -> str:
    material = model.encode() + _NUL + query.encode("utf-8") + _NUL + text.encode("utf-8")
    return hashlib.sha256(material).hexdigest()


class EmbeddingRecorder:
    """임베딩 기록 하나(`index`의 조각이나 `run`의 질의). `known`은 기록 파일에서 읽은 값이고
    `used`는 이번 실행이 쓴 열쇠의 값이다. `limit`은 새로 계산해도 되는 열쇠의 수이고 `None`이면
    상한이 없다. `read_count`와 `computed_count`는 열쇠의 수다."""

    def __init__(
        self,
        *,
        model: str,
        dimensions: int,
        known: Mapping[str, tuple[float, ...]],
        limit: int | None,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._known = known
        self._limit = limit
        self.used: dict[str, tuple[float, ...]] = {}
        self.read_count = 0
        self.computed_count = 0
        self.exceeded = False

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def wrap(self, inner: Embedder) -> "RecordingEmbedder":
        return RecordingEmbedder(self, inner)

    def wrap_factory(self, embedder_for: EmbedderFor) -> EmbedderFor:
        """색인 판으로 임베더를 내는 함수를 감싼다. 작업자의 조립이 걸이로 받는다."""
        return lambda version: self.wrap(embedder_for(version))

    async def embed(self, inner: Embedder, texts: Sequence[str]) -> list[tuple[float, ...]]:
        keys = [embedding_key(self._model, text) for text in texts]
        missing: dict[str, str] = {}
        for key, text in zip(keys, texts, strict=True):
            if key in self.used or key in missing:
                continue
            known = self._known.get(key)
            if known is None:
                missing[key] = text
            else:
                self.used[key] = known
                self.read_count += 1
        if missing:
            if self.exceeded or (
                self._limit is not None and self.computed_count + len(missing) > self._limit
            ):
                self.exceeded = True
                raise PermanentFailure(
                    ErrorCode.EMBEDDING_REJECTED,
                    "추론 기록에 없는 임베딩이 상한을 넘어 계산하지 않는다",
                )
            self.computed_count += len(missing)
            vectors = await inner.embed(list(missing.values()))
            self.used.update(zip(missing, vectors, strict=True))
        return [self.used[key] for key in keys]


class RecordingEmbedder:
    """`Embedder` 포트. 임베딩은 기록기를 거치고 토큰 세기는 감싼 임베더로 넘긴다."""

    def __init__(self, recorder: EmbeddingRecorder, inner: Embedder) -> None:
        self._recorder = recorder
        self._inner = inner

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        return await self._recorder.embed(self._inner, texts)

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        return await self._inner.count_tokens(texts)

    async def special_token_count(self) -> int:
        return await self._inner.special_token_count()

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        return await self._inner.token_spans(text)


class RerankRecorder:
    """리랭크 기록. `inner`가 없는 포트(리랭커의 끝점을 주지 않은 전체 실행)는 기록에 없는 쌍
    하나에도 실패하고 `unavailable`을 남긴다. 리랭크는 상한이 없다."""

    def __init__(self, *, model: str, known: Mapping[str, float]) -> None:
        self._model = model
        self._known = known
        self.used: dict[str, float] = {}
        self.read_count = 0
        self.computed_count = 0
        self.unavailable = False

    def wrap(self, inner: Reranker | None) -> "RecordingReranker":
        return RecordingReranker(self, inner)

    async def rerank(self, inner: Reranker | None, query: str, texts: Sequence[str]) -> list[float]:
        keys = [rerank_key(self._model, query, text) for text in texts]
        missing: dict[str, str] = {}
        for key, text in zip(keys, texts, strict=True):
            if key in self.used or key in missing:
                continue
            known = self._known.get(key)
            if known is None:
                missing[key] = text
            else:
                self.used[key] = known
                self.read_count += 1
        if missing:
            if inner is None:
                self.unavailable = True
                raise PermanentFailure(
                    ErrorCode.EMBEDDING_REJECTED,
                    "리랭크 기록에 없는 쌍이 있고 리랭커의 끝점이 없다",
                )
            self.computed_count += len(missing)
            scores = await inner.rerank(query, list(missing.values()))
            self.used.update(zip(missing, scores, strict=True))
        return [self.used[key] for key in keys]


class RecordingReranker:
    """`Reranker` 포트."""

    def __init__(self, recorder: RerankRecorder, inner: Reranker | None) -> None:
        self._recorder = recorder
        self._inner = inner

    async def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        return await self._recorder.rerank(self._inner, query, texts)


class RecordsRun:
    """명령 하나가 기록을 쓰는 한 번. 그 명령이 주인인 기록 파일(`owned`)의 기록기를 짓고, 명령이
    끝난 뒤 보고서의 `records` 칸과 안내와 쓰기를 맡는다. `read`와 `write`에서 `records.json`과 주인
    파일을 읽는다. 형식이 틀렸으면 `RecordsFormatError`이고 경로가 묶음 밖을 가리키면
    `BundlePathError`다. `write`는 장치(`options.device`)가 있어야 한다."""

    def __init__(
        self,
        paths: BundlePaths,
        config: EvalConfig,
        options: RecordsOptions,
        *,
        owned: Sequence[RecordKind],
    ) -> None:
        if options.mode is RecordMode.WRITE and not options.device:
            raise ValueError("--records write는 장치(--tei-device)가 있어야 한다")
        self._paths = paths
        self._config = config
        self._options = options
        self._owned = tuple(owned)
        if options.mode is RecordMode.WRITE:
            # 앞 종류를 쓴 뒤 뒤 종류의 경로에서 거부해 반쪽만 쓰는 일을 막는다.
            for kind in self._owned:
                check_writable(paths, kind)
        self._manifest = None if options.mode is RecordMode.OFF else read_manifest(paths)
        self._embeddings: dict[RecordKind, EmbeddingRecorder] = {}
        self._rerank: RerankRecorder | None = None
        if options.mode is RecordMode.OFF:
            return
        for kind in self._owned:
            if kind is RecordKind.RERANK:
                self._rerank = RerankRecorder(
                    model=config.reranker_model, known=self._known_scores(kind)
                )
            else:
                self._embeddings[kind] = EmbeddingRecorder(
                    model=config.embedding_model,
                    dimensions=config.embedding_dimensions,
                    known=self._known_vectors(kind),
                    limit=READ_COMPUTE_LIMIT if options.mode is RecordMode.READ else None,
                )

    @property
    def mode(self) -> RecordMode:
        return self._options.mode

    def embedding(self, kind: RecordKind) -> EmbeddingRecorder | None:
        """`off`이거나 이 명령이 주인이 아닌 종류이면 `None`이다."""
        return self._embeddings.get(kind)

    @property
    def rerank(self) -> RerankRecorder | None:
        return self._rerank

    def notices(self) -> list[str]:
        """계산을 멈춘 기록마다 어느 명령을 다시 돌려 어느 파일을 커밋하는지 알리는 글."""
        found = [_notice(kind) for kind, recorder in self._embeddings.items() if recorder.exceeded]
        if self._rerank is not None and self._rerank.unavailable:
            found.append(_notice(RecordKind.RERANK))
        return found

    def summary(self) -> RecordsSummary:
        """보고서의 `records` 칸. 읽은 수와 새로 계산한 수, 이번 실행의 값이 나온 기록 파일마다의
        sha256이다. `write`는 다시 쓸 파일의 해시다. `off`는 비었다."""
        recorders = [*self._embeddings.values(), *([self._rerank] if self._rerank else [])]
        return RecordsSummary(
            read=sum(recorder.read_count for recorder in recorders),
            computed=sum(recorder.computed_count for recorder in recorders),
            files=self._file_hashes(),
        )

    def commit(self) -> None:
        """`write`이면 주인 파일을 이번 실행이 쓴 열쇠 전부로 다시 쓴다. 명령이 종료 코드 0으로 끝날
        때만 부른다."""
        if self._options.mode is not RecordMode.WRITE:
            return
        for kind in self._owned:
            contents, entry = self._rendered(kind)
            write_record_files(self._paths, kind, contents, entry)

    def _model(self, kind: RecordKind) -> str:
        if kind is RecordKind.RERANK:
            return self._config.reranker_model
        return self._config.embedding_model

    def _usable_entry(self, kind: RecordKind) -> RecordEntry | None:
        """기록의 값을 쓸 수 있는 항목. 모델 이름이나 차원이 구성과 다르면 쓰지 않는다. `write`는
        요청 지문이나 TEI의 판이 다른 파일의 옛 값도 옮기지 않는다."""
        entry = None if self._manifest is None else self._manifest.files.get(kind.value)
        if entry is None or entry.model != self._model(kind):
            return None
        if kind is not RecordKind.RERANK and entry.dimensions != self._config.embedding_dimensions:
            return None
        if self._options.mode is RecordMode.WRITE and (
            entry.request_fingerprint != request_fingerprint(kind)
            or entry.tei_version != self._config.tei_version
        ):
            return None
        return entry

    def _known_vectors(self, kind: RecordKind) -> dict[str, tuple[float, ...]]:
        entry = self._usable_entry(kind)
        return {} if entry is None else read_embedding_values(self._paths, kind, entry)

    def _known_scores(self, kind: RecordKind) -> dict[str, float]:
        entry = self._usable_entry(kind)
        return {} if entry is None else read_rerank_values(self._paths, kind)

    def _rendered(self, kind: RecordKind) -> tuple[dict[str, bytes], RecordEntry]:
        """다시 쓸 파일의 바이트와 `records.json`의 항목."""
        if kind is RecordKind.RERANK:
            assert self._rerank is not None
            used = self._rerank.used
            (name,) = record_files(kind)
            contents = {name: render_rerank_file(used)}
            dimensions = None
        else:
            vectors = self._embeddings[kind].used
            keys, data = render_embedding_files(
                vectors, dimensions=self._config.embedding_dimensions
            )
            keys_name, data_name = record_files(kind)
            contents = {keys_name: keys, data_name: data}
            used = vectors
            dimensions = self._config.embedding_dimensions
        entry = RecordEntry(
            model=self._model(kind),
            dimensions=dimensions,
            count=len(used),
            tei_version=self._config.tei_version,
            device=self._options.device or "",
            request_fingerprint=request_fingerprint(kind),
        )
        return contents, entry

    def _file_hashes(self) -> dict[str, str]:
        if self._options.mode is RecordMode.OFF:
            return {}
        hashes: dict[str, str] = {}
        if self._options.mode is RecordMode.WRITE:
            files = {} if self._manifest is None else dict(self._manifest.files)
            for kind in self._owned:
                contents, entry = self._rendered(kind)
                files[kind.value] = entry
                for name, data in contents.items():
                    hashes[f"{RECORDS_FOLDER}/{name}"] = hashlib.sha256(data).hexdigest()
            manifest = Manifest(format_version=FORMAT_VERSION, files=files)
            hashes[f"{RECORDS_FOLDER}/{MANIFEST_NAME}"] = hashlib.sha256(
                manifest.render()
            ).hexdigest()
            return dict(sorted(hashes.items()))
        if self._manifest is None:
            return {}
        for kind in self._owned:
            if self._usable_entry(kind) is None:
                continue
            for name in record_files(kind):
                path = self._paths.resolve(f"{RECORDS_FOLDER}/{name}")
                hashes[f"{RECORDS_FOLDER}/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes:
            manifest_path = self._paths.resolve(f"{RECORDS_FOLDER}/{MANIFEST_NAME}")
            hashes[f"{RECORDS_FOLDER}/{MANIFEST_NAME}"] = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
        return dict(sorted(hashes.items()))


def request_fingerprint(kind: RecordKind) -> str:
    """이 체크아웃의 어댑터가 그 종류의 추론 요청에 대해 내는 요청 지문."""
    shape = RERANK_REQUEST if kind is RecordKind.RERANK else EMBEDDING_REQUEST
    return shape.fingerprint()


def rebuild_command(kind: RecordKind) -> str:
    """그 종류의 기록 파일을 다시 만드는 명령(`--records write`)."""
    if kind is RecordKind.CHUNK_EMBEDDINGS:
        return f"데이터베이스를 새로 만들고 `{_TOOL_COMMAND} index <묶음 폴더> {_DEVICE_OPTION}`"
    if kind is RecordKind.QUERY_EMBEDDINGS:
        return f"`{_TOOL_COMMAND} run --through fused <묶음 폴더> --out <폴더> {_DEVICE_OPTION}`"
    return (
        "GPU가 있는 기계에서 리랭커를 띄우고"
        f" `{_TOOL_COMMAND} run --through rerank <묶음 폴더> --out <폴더> {_DEVICE_OPTION}`"
    )


def _notice(kind: RecordKind) -> str:
    files = ", ".join(f"{RECORDS_FOLDER}/{name}" for name in record_files(kind))
    command = rebuild_command(kind)
    if kind is RecordKind.RERANK:
        return (
            "리랭크 기록에 없는 쌍이 있고 리랭커의 끝점(RAG_EVAL_RERANKER_URL)이 없어"
            f" 멈췄다. {command}로 다시 돌려 {files}와 {RECORDS_FOLDER}/{MANIFEST_NAME}을 커밋한다"
        )
    return (
        f"추론 기록에 없는 임베딩이 {READ_COMPUTE_LIMIT}개를 넘어 계산을 멈췄다."
        f" {command}로 다시 돌려 {files}와 {RECORDS_FOLDER}/{MANIFEST_NAME}을 커밋한다"
    )
