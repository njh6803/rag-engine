"""TEI 임베딩 어댑터(명세 "임베딩 서버와 리랭커 어댑터", ADR 0010).

컨테이너 하나가 모델 하나를 들고, 어댑터 하나가 끝점 하나를 맡는다. 끝점마다 첫 호출 전에 `/info`를
읽어 모델 이름과 최대 입력 길이를 확인하고(다르면 "설정 불일치"라 운영자가 고칠 때까지 일시 실패다),
`/v1/embeddings`와 `/tokenize`를 `RAG_TEI_BATCH_SIZE`개씩, 본문이 바이트 상한을 넘지 않게 묶어
부른다. `/tokenize`는 글 하나가 `max_input_length`의 250배 글자를 넘으면 잘라 주지 않고 거부하므로,
넘는 글은 어댑터가 글자 수로 잘라 따로 보내 센 뒤 이어 붙여 돌려준다. 서드파티 예외와 서버의 오류
메시지는 옮기지 않고 이 저장소가 쓴 글로 `domain`의 영구·일시 실패 예외를 올린다(원칙 V).
시간 초과는 `httpx.AsyncClient`의 `timeout`이 맡고 조립 쪽이 `RAG_TEI_TIMEOUT_SECONDS`로 정한다.
"""

import asyncio
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from rag_engine.adapters.utf8_offsets import Utf8Offsets
from rag_engine.domain.entities import IndexVersion, JsonValue
from rag_engine.domain.errors import ErrorCode, PermanentFailure, TransientFailure

logger = logging.getLogger(__name__)

# 서버가 요청 자체를 받지 못한다고 알리는 상태 코드. 같은 입력으로 다시 해도 같다. 다만 `/info`는
# 입력이 없는 조회라 이 코드가 와도 서버 쪽 문제로 보고 일시 실패로 옮긴다(`_send`).
_REJECTED_STATUSES: Final = frozenset({400, 413, 422})

# 특수 토큰 수를 재는 짧은 글. 빈 글은 TEI가 거부한다.
_PROBE_TEXT: Final = "가"

# TEI는 `/tokenize`의 글 하나가 `max_input_length` × 250자를 넘으면 잘라 주지 않고 검증 오류로
# 거부한다(상류 v1.9.4 `core/src/tokenization.rs`의 `MAX_CHAR_MULTIPLIER`와 `tokenize_input`을
# 웹 요약으로 읽었다. 프로브 `tei_tokenization_facts.py`는 그 상수의 값을 뽑지 않았다).
_CHARS_PER_INPUT_TOKEN: Final = 250

# 요청 본문 하나의 UTF-8 바이트 상한. TEI의 `--payload-limit` 기본값 2,000,000바이트(상류 v1.9.4
# `router/src/main.rs`, 웹 요약)의 절반이다. JSON 이스케이프와 다른 칸이 쓰는 몫을 남긴다.
_MAX_BODY_BYTES: Final = 1_000_000

# 글을 자를 때 조각 하나의 글자 수 상한. 글자 하나가 UTF-8로 최대 4바이트라 이 수만큼이면 본문
# 상한 안에 든다.
_MAX_SLICE_CHARS: Final = _MAX_BODY_BYTES // 4


class _Info(BaseModel):
    model_id: str
    served_model_name: str
    max_input_length: int
    max_client_batch_size: int
    auto_truncate: bool


class _EmbeddingItem(BaseModel):
    index: int
    embedding: list[float]


class _EmbeddingResponse(BaseModel):
    data: list[_EmbeddingItem]


class _Token(BaseModel):
    start: int | None = None
    stop: int | None = None


_TOKENIZE_RESPONSE: Final = TypeAdapter(list[list[_Token]])


@dataclass(frozen=True, slots=True)
class _Limits:
    """`/info`가 알린 값에서 끌어낸, 요청을 짜는 한도."""

    batch_size: int
    slice_chars: int


class TeiEmbedder:
    """`Embedder` 포트(`TokenMeter` 포함)의 TEI 어댑터. 끝점 하나, 모델 하나다."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        model: str,
        dimensions: int,
        max_chunk_tokens: int,
        batch_size: int,
    ) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._max_chunk_tokens = max_chunk_tokens
        self._configured_batch_size = batch_size
        self._limits: _Limits | None = None
        self._special_token_count: int | None = None
        self._check_lock = asyncio.Lock()

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        limits = await self._endpoint_limits()
        vectors: list[tuple[float, ...]] = []
        for batch in _batches(texts, size=limits.batch_size, max_bytes=_MAX_BODY_BYTES):
            content = await self._send(
                "POST", "/v1/embeddings", {"input": batch, "model": self._model}
            )
            vectors.extend(self._vectors(_parse(_EmbeddingResponse, content), len(batch)))
        return vectors

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        tokens = await self._tokenize(texts, add_special_tokens=False)
        return [len(text_tokens) for text_tokens in tokens]

    async def special_token_count(self) -> int:
        if self._special_token_count is None:
            with_special = await self._tokenize([_PROBE_TEXT], add_special_tokens=True)
            without_special = await self._tokenize([_PROBE_TEXT], add_special_tokens=False)
            self._special_token_count = len(with_special[0]) - len(without_special[0])
        return self._special_token_count

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        if not text:
            return []
        (tokens,) = await self._tokenize([text], add_special_tokens=False)
        offsets = Utf8Offsets(text)
        return [
            (offsets.char_index(token.start), offsets.char_index(token.stop))
            for token in tokens
            if token.start is not None and token.stop is not None
        ]

    def _vectors(
        self, response: _EmbeddingResponse, expected_count: int
    ) -> list[tuple[float, ...]]:
        items = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in items] != list(range(expected_count)):
            raise _malformed_response()
        if any(len(item.embedding) != self._dimensions for item in items):
            raise PermanentFailure(
                ErrorCode.EMBEDDING_DIMENSION_MISMATCH,
                "임베딩 벡터의 길이가 설정한 차원과 다르다",
            )
        return [tuple(item.embedding) for item in items]

    async def _tokenize(
        self, texts: Sequence[str], *, add_special_tokens: bool
    ) -> list[list[_Token]]:
        """글마다 토큰을 낸다. 빈 글은 TEI가 거부하므로 서버에 보내지 않고 토큰 없음으로 둔다.
        글자 수 상한을 넘는 글은 잘라 보내 센 토큰을 이어 붙인다. 자른 자리에 걸친 낱말은 둘로
        센다."""
        non_empty = [text for text in texts if text]
        if not non_empty:
            return [[] for _ in texts]
        limits = await self._endpoint_limits()
        pieces_of = [_slices(text, limits.slice_chars) for text in non_empty]
        pieces = [piece for text_pieces in pieces_of for piece in text_pieces]
        tokenized: list[list[_Token]] = []
        for batch in _batches(pieces, size=limits.batch_size, max_bytes=_MAX_BODY_BYTES):
            payload: Mapping[str, JsonValue] = {
                "inputs": batch,
                "add_special_tokens": add_special_tokens,
            }
            content = await self._send("POST", "/tokenize", payload)
            batch_tokens = _parse(_TOKENIZE_RESPONSE, content)
            if len(batch_tokens) != len(batch):
                raise _malformed_response()
            tokenized.extend(batch_tokens)
        remaining = iter(tokenized)
        joined = iter(
            _joined(text_pieces, [next(remaining) for _ in text_pieces])
            for text_pieces in pieces_of
        )
        return [next(joined) if text else [] for text in texts]

    async def _endpoint_limits(self) -> _Limits:
        """끝점마다 첫 호출 전에 `/info`를 확인하고 요청을 짜는 한도를 돌려준다. 실패하면 기억하지
        않아 다음 호출이 다시 본다."""
        async with self._check_lock:
            if self._limits is None:
                content = await self._send("GET", "/info", None)
                info = _parse(_Info, content)
                self._verify(info)
                logger.info(
                    "TEI 끝점을 확인했다: model=%s max_input_length=%d max_client_batch_size=%d"
                    " auto_truncate=%s",
                    info.model_id,
                    info.max_input_length,
                    info.max_client_batch_size,
                    info.auto_truncate,
                )
                self._limits = _Limits(
                    batch_size=max(1, min(self._configured_batch_size, info.max_client_batch_size)),
                    slice_chars=min(
                        info.max_input_length * _CHARS_PER_INPUT_TOKEN, _MAX_SLICE_CHARS
                    ),
                )
            return self._limits

    def _verify(self, info: _Info) -> None:
        if self._model not in (info.model_id, info.served_model_name):
            raise TransientFailure(
                ErrorCode.EMBEDDING_UNAVAILABLE,
                f"설정 불일치: 임베딩 서버의 모델({info.model_id})이"
                f" 설정한 모델({self._model})과 다르다",
            )
        if info.max_input_length < self._max_chunk_tokens:
            raise TransientFailure(
                ErrorCode.EMBEDDING_UNAVAILABLE,
                f"설정 불일치: 임베딩 서버의 최대 입력 길이({info.max_input_length})가"
                f" 조각 상한({self._max_chunk_tokens})보다 작다",
            )

    async def _send(self, method: str, path: str, payload: Mapping[str, JsonValue] | None) -> bytes:
        try:
            response = await self._client.request(method, path, json=payload)
        except httpx.RequestError:
            raise TransientFailure(
                ErrorCode.EMBEDDING_UNAVAILABLE, "임베딩 서버에 연결하지 못했거나 응답이 늦었다"
            ) from None
        if response.is_success:
            return response.content
        if path != "/info" and response.status_code in _REJECTED_STATUSES:
            raise PermanentFailure(
                ErrorCode.EMBEDDING_REJECTED,
                f"임베딩 서버가 요청을 거부했다(HTTP {response.status_code})",
            )
        raise TransientFailure(
            ErrorCode.EMBEDDING_UNAVAILABLE,
            f"임베딩 서버가 요청을 처리하지 못했다(HTTP {response.status_code})",
        )


class TeiEmbedderPool:
    """색인 판에 적힌 끝점·모델·차원으로 `TeiEmbedder`를 하나씩 만들어 돌려쓴다. 어댑터가 첫
    호출에서 `/info`를 확인하므로 판마다 새로 만들면 글 묶음마다 확인을 되풀이한다. 키가 판의 ID가
    아니라 그 네 값인 까닭은 `migrate`가 판에 적힌 끝점만 고칠 수 있어서다. 끝점 하나가 클라이언트
    하나(연결 풀)를 쓴다."""

    def __init__(self, client_for: Callable[[str], httpx.AsyncClient], *, batch_size: int) -> None:
        self._client_for = client_for
        self._batch_size = batch_size
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._embedders: dict[tuple[str, str, int, int], TeiEmbedder] = {}

    def __call__(self, version: IndexVersion) -> TeiEmbedder:
        key = (
            version.embedding_endpoint,
            version.embedding_model,
            version.embedding_dimensions,
            version.chunking.max_tokens,
        )
        embedder = self._embedders.get(key)
        if embedder is None:
            endpoint = version.embedding_endpoint
            client = self._clients.get(endpoint)
            if client is None:
                client = self._client_for(endpoint)
                self._clients[endpoint] = client
            embedder = TeiEmbedder(
                client,
                model=version.embedding_model,
                dimensions=version.embedding_dimensions,
                max_chunk_tokens=version.chunking.max_tokens,
                batch_size=self._batch_size,
            )
            self._embedders[key] = embedder
        return embedder

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()


def _batches(texts: Sequence[str], *, size: int, max_bytes: int) -> list[list[str]]:
    """순서를 지켜 글을 `size`개 이하이고 UTF-8 바이트 합이 `max_bytes` 이하인 묶음으로 가른다.
    글 하나가 `max_bytes`를 넘으면 그 글 혼자 한 묶음이다."""
    batches: list[list[str]] = []
    current: list[str] = []
    current_bytes = 0
    for text in texts:
        text_bytes = len(text.encode("utf-8"))
        if current and (len(current) >= size or current_bytes + text_bytes > max_bytes):
            batches.append(current)
            current, current_bytes = [], 0
        current.append(text)
        current_bytes += text_bytes
    if current:
        batches.append(current)
    return batches


def _slices(text: str, size: int) -> list[str]:
    return [text[start : start + size] for start in range(0, len(text), size)]


def _joined(pieces: Sequence[str], tokens_of: Sequence[list[_Token]]) -> list[_Token]:
    """조각마다 센 토큰을 글 전체의 것으로 잇는다. 토큰의 바이트 오프셋은 조각 안의 값이라 앞
    조각들의 UTF-8 바이트 길이만큼 밀어야 글 전체의 값이 된다."""
    if len(pieces) == 1:
        return tokens_of[0]
    joined: list[_Token] = []
    shift = 0
    for piece, tokens in zip(pieces, tokens_of, strict=True):
        joined.extend(
            _Token(
                start=None if token.start is None else token.start + shift,
                stop=None if token.stop is None else token.stop + shift,
            )
            for token in tokens
        )
        shift += len(piece.encode("utf-8"))
    return joined


def _parse[T](model: type[T] | TypeAdapter[T], content: bytes) -> T:
    adapter = model if isinstance(model, TypeAdapter) else TypeAdapter(model)
    try:
        return adapter.validate_json(content)
    except ValidationError:
        raise _malformed_response() from None


def _malformed_response() -> TransientFailure:
    return TransientFailure(
        ErrorCode.EMBEDDING_UNAVAILABLE, "임베딩 서버의 응답 형식이 맞지 않는다"
    )
