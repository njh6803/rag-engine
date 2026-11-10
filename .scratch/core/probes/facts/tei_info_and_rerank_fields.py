"""TEI v1.9.4 OpenAPI 원문에서 `/info` 응답, `/rerank` 요청·응답, `/tokenize` 입력의 칸을 뽑는다.

근거로 드는 곳은 ADR 0010 과 명세다. `facts/tei_openapi_fields.py` 는 `/tokenize`·`/embed`·
`/v1/embeddings` 의 요청 칸을 봤다. 명세는 그 위에 셋이 더 필요하다. 임베딩 어댑터가 기동 때 모델
이름과 입력 상한을 확인할 `/info` 응답의 칸, 리랭커 어댑터가 보낼 `/rerank` 요청의 칸과 받을 응답의
칸, `/tokenize` 의 `inputs` 가 문자열 배열을 받는지다.

실행(저장소 루트에서. GitHub raw 의 태그 고정 문서 하나만 받는다. 표준 라이브러리만):
    uv run python -I -X utf8 .scratch/core/probes/facts/tei_info_and_rerank_fields.py <폴더>
`<폴더>` 는 저장소 밖(세션 스크래치패드)이다.
출력은 `tei_info_and_rerank_fields_out.txt` 로 남겼다(2026-11-10). 문서의 모양은 TypedDict 로
선언해 받는다(원칙 II 를 지키려는 것이지 문서를 검사하려는 것이 아니다).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import TypedDict

TAG = "v1.9.4"
URL = f"https://raw.githubusercontent.com/huggingface/text-embeddings-inference/{TAG}/docs/openapi.json"


class Schema(TypedDict, total=False):
    type: str
    enum: list[str]
    required: list[str]
    properties: dict[str, object]
    oneOf: list[object]
    anyOf: list[object]
    allOf: list[object]


class Operation(TypedDict, total=False):
    responses: dict[str, object]


class Components(TypedDict):
    schemas: dict[str, Schema]


class OpenApi(TypedDict):
    info: dict[str, str]
    paths: dict[str, dict[str, Operation]]
    components: Components


def fetch(dest: Path) -> OpenApi:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"tei-openapi-{TAG}.json"
    if not target.exists():
        with urllib.request.urlopen(URL, timeout=60) as resp:
            target.write_bytes(resp.read())
    loaded: OpenApi = json.loads(target.read_text(encoding="utf-8"))
    return loaded


def show_schema(schemas: dict[str, Schema], name: str) -> None:
    schema = schemas.get(name)
    if schema is None:
        print(f"--- {name}: (없음)")
        return
    print(f"--- {name} type={schema.get('type')} required={schema.get('required')}")
    enum = schema.get("enum")
    if enum is not None:
        print(f"  enum: {json.dumps(enum, ensure_ascii=False)}")
    for key, value in schema.get("properties", {}).items():
        print(f"  {key}: {json.dumps(value, ensure_ascii=False)[:200]}")
    for alt_key in ("oneOf", "anyOf", "allOf"):
        alt = schema.get(alt_key)
        if alt is not None:
            print(f"  {alt_key}: {json.dumps(alt, ensure_ascii=False)[:300]}")


def main() -> None:
    doc = fetch(Path(sys.argv[1]))
    print("version", doc["info"]["version"])
    schemas = doc["components"]["schemas"]
    for name in (
        "Info",
        "ModelType",
        "RerankRequest",
        "RerankResponse",
        "Rank",
        "TruncationDirection",
        "TokenizeInput",
        "TokenizeResponse",
        "OpenAICompatResponse",
        "OpenAICompatEmbedding",
        "OpenAICompatUsage",
        "ErrorResponse",
        "ErrorType",
    ):
        show_schema(schemas, name)
    for path in ("/info", "/rerank", "/tokenize", "/v1/embeddings"):
        for method, op in doc["paths"][path].items():
            codes = sorted(op.get("responses", {}))
            print(f"{method.upper()} {path} responses={codes}")


if __name__ == "__main__":
    main()
