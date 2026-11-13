"""코어 4개만 보이는 TEI(리랭커)가 질의와 조각 크기 글의 쌍을 1초에 몇 개 채점하는지 잰다.

search-eval 명세가 전체 게이트(리랭크 뒤 줄)를 CI 에서 매번 새로 계산할 수 있는지를 정하는 근거다.
평가 한 번은 질의마다 후보 50개를 리랭크하므로 쌍의 수가 질의 수의 50배다. `embed_throughput.py` 와
이미지와 글을 만드는 방식이 같다. 다른 것은 둘이다. 코어를 묶는 방법이 다르고(그쪽의 저장한 출력은
`--cpus=4`, 이쪽은 `--cpuset-cpus=4-7`), 그쪽은 첫 배치를 준비 비용으로 버리지만 이쪽은 버리지 않아
총 시간에 첫 배치의 준비가 들어 있다. 이 PC 의 코어는 러너의 코어와 달라 자릿수를 보는 어림이다.

띄우기(모델은 처음 띄울 때 Hugging Face 에서 받는다. 약 2.3GB):

    docker run -d --name search-eval-rerank-probe --cpuset-cpus=4-7 -p 127.0.0.1:18081:80 \
        -v search-eval-tei-probe-data:/data \
        ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4 --model-id BAAI/bge-reranker-v2-m3

돌리기:

    uv run python -X utf8 .scratch/search-eval/probes/tei-cpu/rerank_throughput.py http://127.0.0.1:18081

보는 것: `/info` 의 모델, 질의 하나와 조각 크기(약 470토큰)의 글 32개를 `/rerank` 에 보낸
처리량(쌍/초). 표준 라이브러리만 쓴다.
"""

import json
import os
import platform
import sys
import time
import urllib.request
from typing import TypedDict

SENTENCE = (
    "제{n}조(정의) 이 규정에서 사용하는 용어의 뜻은 다음과 같으며, "
    "관계 기관의 장은 소관 업무의 범위에서 필요한 사항을 따로 정하여 "
    "고시할 수 있고 그 결과를 지체 없이 공개하여야 한다. "
)
QUERY = "관계 기관의 장이 고시한 사항은 언제까지 공개해야 하나요 {n}"
BATCH_SIZE = 32
BATCHES = 3
SENTENCES_PER_CHUNK = 9
QUERIES = 300
CANDIDATES = 50


class Info(TypedDict):
    model_id: str
    max_client_batch_size: int


def post(url: str, payload: dict[str, object]) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        body: bytes = response.read()
    return body


def chunk_text(seed: int) -> str:
    return "".join(SENTENCE.format(n=seed * 100 + i) for i in range(SENTENCES_PER_CHUNK))


def main() -> None:
    base = sys.argv[1].rstrip("/")
    with urllib.request.urlopen(f"{base}/info", timeout=30) as response:
        info: Info = json.loads(response.read())
    # 둘째 인자는 컨테이너를 띄운 조건이다. GPU 이미지로 다시 잴 때 출력의 머리 줄을 가르려고
    # 받는다.
    condition = sys.argv[2] if len(sys.argv) > 2 else "컨테이너는 코어 4개"
    print(f"platform: {platform.platform()}, 논리 코어 {os.cpu_count()} ({condition})")
    print(f"model_id: {info['model_id']}, max_client_batch_size: {info['max_client_batch_size']}")

    seconds: list[float] = []
    for batch in range(BATCHES):
        texts = [chunk_text(batch * BATCH_SIZE + i) for i in range(BATCH_SIZE)]
        started = time.perf_counter()
        post(f"{base}/rerank", {"query": QUERY.format(n=batch), "texts": texts})
        seconds.append(time.perf_counter() - started)
    total = sum(seconds)
    count = BATCH_SIZE * BATCHES
    rate = count / total
    print(
        f"리랭크: 쌍 {count}개를 배치 {BATCH_SIZE}로 {total:.1f}s, {rate:.2f}쌍/s"
        f" (배치마다 {min(seconds):.1f}~{max(seconds):.1f}s)"
    )
    pairs = QUERIES * CANDIDATES
    print(
        f"  어림: 질의 {QUERIES}개에 후보 {CANDIDATES}개씩 쌍 {pairs}개면 {pairs / rate / 60:.0f}분"
    )


if __name__ == "__main__":
    main()
