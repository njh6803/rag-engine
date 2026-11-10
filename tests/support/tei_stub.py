"""TEI 스텁. 시험이 쓰는 작은 ASGI 앱 하나가 TEI 1.9.4의 끝점 넷을 흉내 낸다(명세 Testing
Decisions).

`/info`, `/v1/embeddings`, `/tokenize`, `/rerank`를 낸다. 실제 모델의 품질은 search-eval의 몫이라
여기서는 결정적으로만 흉내 낸다.

- 임베딩: 글을 낱말(`\\w+` 또는 기호 하나)로 갈라 낱말 해시로 정한 차원에 부호를 더한 뒤 정규화한
  단어 주머니 벡터다. 같은 글은 같은 벡터이고 낱말이 겹치면 가까운 벡터다.
- 토큰 세기: 같은 낱말 단위에 입력의 UTF-8 바이트 오프셋을 붙인다. `add_special_tokens`가 참이면
  앞뒤에 오프셋이 null인 특수 토큰을 더한다. 빈 글은 TEI처럼 거부한다.
- 리랭크: 질의 낱말 가운데 글에 든 비율을 점수로 내고 점수가 큰 순서로 돌려준다.
- 입력 상한: `/tokenize`는 글 하나가 `max_input_length`의 250배 글자를 넘으면 422로, 요청 본문이
  `payload_limit` 바이트를 넘으면 413으로 거부한다(상류 v1.9.4의 `MAX_CHAR_MULTIPLIER`와
  `--payload-limit`을 웹 요약으로 읽었다).

요청 횟수와 본문은 `requests`에 남아 시험이 배치 크기나 `truncate` 같은 칸을 단언한다. `fail`로
끝점이 주는 응답을 상태 코드로 바꿀 수 있다. 서버 메시지는 시험이 어댑터가 옮기지 않음을 보려고
`SECRET_MESSAGE`를 담는다. 선례는 `.scratch/core/probes/embedding/fake_server.py`다.
"""

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from rag_engine.domain.entities import JsonValue

SECRET_MESSAGE: Final = "SERVER-SIDE-DETAIL-MUST-NOT-LEAK"
MAX_CHAR_MULTIPLIER: Final = 250

_WORD: Final = re.compile(r"\w+|[^\w\s]")


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    path: str
    body: Mapping[str, JsonValue]


@dataclass(slots=True)
class TeiStub:
    """설정값으로 `/info`가 알리는 값을 정하고, 만든 뒤 `app`을 `httpx.ASGITransport`에 건넨다."""

    model_id: str = "BAAI/bge-m3"
    served_model_name: str | None = None
    max_input_length: int = 8192
    auto_truncate: bool = True
    max_client_batch_size: int = 32
    payload_limit: int = 2_000_000
    dimensions: int = 16
    special_tokens: int = 2
    requests: list[RecordedRequest] = field(default_factory=lambda: [])
    forced_statuses: dict[str, int] = field(default_factory=lambda: {})
    app: FastAPI = field(init=False)

    def __post_init__(self) -> None:
        self.app = FastAPI()
        self.app.add_api_route("/info", self._info, methods=["GET"])
        self.app.add_api_route("/v1/embeddings", self._embeddings, methods=["POST"])
        self.app.add_api_route("/tokenize", self._tokenize, methods=["POST"])
        self.app.add_api_route("/rerank", self._rerank, methods=["POST"])

    def fail(self, path: str, status: int) -> None:
        """그 끝점이 앞으로 모든 요청에 이 상태 코드로 답하게 한다."""
        self.forced_statuses[path] = status

    def bodies(self, path: str) -> list[Mapping[str, JsonValue]]:
        return [request.body for request in self.requests if request.path == path]

    def count(self, path: str) -> int:
        return len(self.bodies(path))

    def _forced(self, path: str) -> Response | None:
        status = self.forced_statuses.get(path)
        if status is None:
            return None
        return _error(status, SECRET_MESSAGE)

    async def _record(self, request: Request) -> Mapping[str, JsonValue] | None:
        """본문을 남기고 돌려준다. 본문이 `payload_limit`을 넘으면 남기지 않고 `None`이다."""
        raw = await request.body()
        if len(raw) > self.payload_limit:
            return None
        body: dict[str, JsonValue] = json.loads(raw)
        self.requests.append(RecordedRequest(request.url.path, body))
        return body

    async def _info(self) -> Response:
        self.requests.append(RecordedRequest("/info", {}))
        if (forced := self._forced("/info")) is not None:
            return forced
        return JSONResponse(
            {
                "model_id": self.model_id,
                "model_dtype": "float16",
                "served_model_name": self.served_model_name or self.model_id,
                "model_type": {"embedding": {"pooling": "cls"}},
                "max_concurrent_requests": 128,
                "max_input_length": self.max_input_length,
                "max_batch_tokens": 16384,
                "max_client_batch_size": self.max_client_batch_size,
                "auto_truncate": self.auto_truncate,
                "tokenization_workers": 4,
                "version": "1.9.4",
            }
        )

    async def _embeddings(self, request: Request) -> Response:
        body = await self._record(request)
        if body is None:
            return _error(413, "payload too large")
        if (forced := self._forced("/v1/embeddings")) is not None:
            return forced
        texts = _texts(body.get("input"))
        if len(texts) > self.max_client_batch_size:
            return _error(422, f"batch size {len(texts)} > {self.max_client_batch_size}")
        for text in texts:
            if len(_units(text)) + self.special_tokens > self.max_input_length:
                return _error(413, f"`inputs` must have less than {self.max_input_length} tokens")
        data = [
            {"object": "embedding", "index": i, "embedding": _vector(text, self.dimensions)}
            for i, text in enumerate(texts)
        ]
        return JSONResponse(
            {
                "object": "list",
                "data": data,
                "model": body.get("model", self.model_id),
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            }
        )

    async def _tokenize(self, request: Request) -> Response:
        body = await self._record(request)
        if body is None:
            return _error(413, "payload too large")
        if (forced := self._forced("/tokenize")) is not None:
            return forced
        inputs = _texts(body.get("inputs"))
        if any(text == "" for text in inputs):
            return _error(422, "`inputs` cannot be empty")
        char_limit = self.max_input_length * MAX_CHAR_MULTIPLIER
        if any(len(text) > char_limit for text in inputs):
            return _error(422, f"`inputs` must have less than {char_limit} characters")
        with_special = body.get("add_special_tokens", True) is True
        return JSONResponse([self._tokens(text, with_special=with_special) for text in inputs])

    async def _rerank(self, request: Request) -> Response:
        body = await self._record(request)
        if body is None:
            return _error(413, "payload too large")
        if (forced := self._forced("/rerank")) is not None:
            return forced
        query = body.get("query")
        texts = _texts(body.get("texts"))
        query_words = {unit.text for unit in _units(query if isinstance(query, str) else "")}
        ranks = [
            {"index": i, "score": _overlap(query_words, {unit.text for unit in _units(text)})}
            for i, text in enumerate(texts)
        ]
        ranks.sort(key=lambda rank: rank["score"], reverse=True)
        return JSONResponse(ranks)

    def _tokens(self, text: str, *, with_special: bool) -> list[dict[str, JsonValue]]:
        tokens: list[dict[str, JsonValue]] = [
            {
                "id": 1000 + i,
                "text": unit.text,
                "special": False,
                "start": unit.start,
                "stop": unit.stop,
            }
            for i, unit in enumerate(_units(text))
        ]
        if not with_special:
            return tokens
        leading = [_special(f"<s{i}>") for i in range((self.special_tokens + 1) // 2)]
        trailing = [_special(f"</s{i}>") for i in range(self.special_tokens // 2)]
        return [*leading, *tokens, *trailing]


@dataclass(frozen=True, slots=True)
class _Unit:
    text: str
    start: int
    stop: int


def _units(text: str) -> list[_Unit]:
    # 바이트 오프셋은 글 처음부터 그 낱말 앞까지 UTF-8로 인코딩한 길이다.
    return [
        _Unit(
            match.group(),
            len(text[: match.start()].encode()),
            len(text[: match.end()].encode()),
        )
        for match in _WORD.finditer(text)
    ]


def _special(text: str) -> dict[str, JsonValue]:
    return {"id": 0, "text": text, "special": True, "start": None, "stop": None}


def _texts(value: JsonValue) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [item for item in value if isinstance(item, str)]
    return []


def _vector(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for unit in _units(text):
        digest = hashlib.sha256(unit.text.lower().encode()).digest()
        vector[int.from_bytes(digest[:4]) % dimensions] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def _overlap(query_words: set[str], text_words: set[str]) -> float:
    return len(query_words & text_words) / len(query_words) if query_words else 0.0


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "error_type": "Validation"}, status_code=status)
