"""http_overhead.py 가 띄우는 가짜 임베딩 서버. 입력마다 고정 1024차원 벡터를 OpenAI 호환 모양으로
돌려준다.

모델 추론 없이 HTTP 왕복 비용만 재려는 것이라 벡터는 시작할 때 한 번 만든 난수다.
처음(2026-11-09)에는 http_overhead.py 가 이 내용을 파일로 써 내고 `uvicorn fake_server:app` 으로
띄웠고, 저장소로 옮기며 그 파일을 그대로 커밋하고 ruff 서식만 맞췄다. 혼자 띄우려면:
    uv run python -m uvicorn fake_server:app --host 127.0.0.1 --port 18765
(이 폴더에서.)
"""

import random

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
VEC = [random.random() for _ in range(1024)]


class Req(BaseModel):
    input: str | list[str]
    model: str = "x"


@app.post("/v1/embeddings")
def emb(req: Req):
    texts = [req.input] if isinstance(req.input, str) else req.input
    data = [{"object": "embedding", "index": i, "embedding": VEC} for i in range(len(texts))]
    return {
        "object": "list",
        "data": data,
        "model": req.model,
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }
