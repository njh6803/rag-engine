"""TEI OpenAPI 문서에서 /tokenize·/embed·/v1/embeddings의 칸을 뽑는다. 인자: openapi.json 경로.

보는 것: 문서의 `info.version`, 경로 목록, 요청 스키마(TokenizeRequest, TokenizeInput, SimpleToken,
EmbedRequest, OpenAICompatRequest, TruncationDirection)의 필수 칸과 속성, `/tokenize` 의 응답 코드.
임베딩·리랭커를 TEI 컨테이너에 맡기는 결정(ADR 0010)에서 토큰 수 세기와 임베딩 요청의 칸을 적는 데
썼다.

입력은 옮기지 않았다. 다시 받으려면(저장소 밖 폴더에):
    curl -sSL -o <폴더>/openapi.json https://huggingface.github.io/text-embeddings-inference/openapi.json
실행: uv run python -I .scratch/core/probes/facts/tei_openapi_fields.py <폴더>/openapi.json
(저장소 루트에서. 표준 라이브러리만 쓴다. 네트워크는 curl 만 쓴다.)

2026-11-09에 돌려 표준 출력으로 읽었다. 그날 받은 문서의 `info.version` 은 1.9.4 였다(옮기며 같은
파일을 `uv run python -I -c` 로 다시 읽어 손으로 봤다. 경로는 /decode, /embed, /embed_all,
/embed_sparse, /health, /info, /metrics, /predict, /rerank, /similarity, /tokenize, /v1/embeddings).
첫 실행의 출력 파일은 남기지 않았다. 옮긴 뒤 같은 파일로 다시 돌린 출력이
`tei_openapi_fields_out.txt` 다.
"""

import json
import sys

doc = json.load(open(sys.argv[1], encoding="utf-8"))
print("version", doc["info"]["version"])
print("paths", sorted(doc["paths"]))
schemas = doc["components"]["schemas"]


def show(name: str) -> None:
    s = schemas[name]
    print(f"--- {name} required={s.get('required')}")
    for k, v in s.get("properties", {}).items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:220]}")


for n in (
    "TokenizeRequest",
    "TokenizeInput",
    "SimpleToken",
    "EmbedRequest",
    "OpenAICompatRequest",
    "TruncationDirection",
):
    if n in schemas:
        show(n)
    else:
        print("--- missing", n)
tok = doc["paths"]["/tokenize"]["post"]
print("tokenize responses", {k: v.get("description") for k, v in tok["responses"].items()})
