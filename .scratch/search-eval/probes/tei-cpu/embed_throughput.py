"""CPU 4개로 묶은 TEI(임베딩)가 조각 크기의 한국어 글을 1초에 몇 개 임베딩하는지 잰다.

search-eval 명세가 빠른 게이트의 시간 한도와 "CI 가 색인을 매번 새로 만들 수 있는가"를 정하는
근거다. GitHub 의 공개 저장소용 표준 러너(ubuntu-latest)는 CPU 4개라, 컨테이너를 `--cpus=4` 로 묶어
흉내 낸다. 이 PC 의 코어는 러너의 코어와 달라 자릿수를 보는 어림이고, CI 러너에서의 값은 게이트를
넣는 티켓이 잰다.

띄우기(모델은 처음 띄울 때 Hugging Face 에서 받는다. 약 2.3GB):

    docker run -d --name search-eval-tei-probe --cpus=4 -p 127.0.0.1:18080:80 \
        -v search-eval-tei-probe-data:/data \
        ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4 --model-id BAAI/bge-m3

돌리기:

    uv run python -X utf8 .scratch/search-eval/probes/tei-cpu/embed_throughput.py http://127.0.0.1:18080

보는 것: `/info` 의 모델과 배치 상한, 글 하나의 토큰 수(`/tokenize`), 조각 크기(약 500토큰)의 글을
배치 32로 `/embed` 에 보낸 처리량(글/초), 질의 크기(짧은 글)를 하나씩 보낸 지연. 표준 라이브러리만
쓴다.
"""

import json
import os
import platform
import statistics
import sys
import time
import urllib.request
from typing import TypedDict

# 법령 조문 모양의 한국어 문장. 조각 하나(약 500토큰)가 되도록 이어 붙이고 번호를 섞어 글마다 다르게
# 한다.
SENTENCE = (
    "제{n}조(정의) 이 규정에서 사용하는 용어의 뜻은 다음과 같으며, "
    "관계 기관의 장은 소관 업무의 범위에서 필요한 사항을 따로 정하여 "
    "고시할 수 있고 그 결과를 지체 없이 공개하여야 한다. "
)
QUERY = "관계 기관의 장이 고시한 사항은 언제까지 공개해야 하나요 {n}"
BATCH_SIZE = 32
CHUNK_BATCHES = 6
QUERY_COUNT = 30
SENTENCES_PER_CHUNK = 9


class Info(TypedDict):
    model_id: str
    max_client_batch_size: int
    max_input_length: int


def post(url: str, payload: dict[str, object]) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
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
    condition = sys.argv[2] if len(sys.argv) > 2 else "컨테이너는 --cpus=4"
    print(f"platform: {platform.platform()}, 논리 코어 {os.cpu_count()} ({condition})")
    print(
        f"model_id: {info['model_id']}, max_client_batch_size: {info['max_client_batch_size']},"
        f" max_input_length: {info['max_input_length']}"
    )

    tokens: list[list[object]] = json.loads(
        post(f"{base}/tokenize", {"inputs": chunk_text(0), "add_special_tokens": True})
    )
    print(f"조각 글 하나: {len(chunk_text(0))}자, {len(tokens[0])}토큰(특수 토큰 포함)")

    # 첫 배치는 준비(스레드, 메모리)를 포함하므로 버린다.
    post(f"{base}/embed", {"inputs": [chunk_text(-1 - i) for i in range(BATCH_SIZE)]})

    seconds: list[float] = []
    for batch in range(CHUNK_BATCHES):
        texts = [chunk_text(batch * BATCH_SIZE + i) for i in range(BATCH_SIZE)]
        started = time.perf_counter()
        post(f"{base}/embed", {"inputs": texts})
        seconds.append(time.perf_counter() - started)
    total = sum(seconds)
    count = BATCH_SIZE * CHUNK_BATCHES
    print(
        f"조각 임베딩: {count}개를 배치 {BATCH_SIZE}로 {total:.1f}s, {count / total:.2f}개/s"
        f" (배치마다 {min(seconds):.1f}~{max(seconds):.1f}s)"
    )
    for chunks in (1000, 3000, 6000):
        print(f"  어림: 조각 {chunks}개면 {chunks / (count / total) / 60:.1f}분")

    latencies: list[float] = []
    for n in range(QUERY_COUNT):
        started = time.perf_counter()
        post(f"{base}/embed", {"inputs": [QUERY.format(n=n)]})
        latencies.append((time.perf_counter() - started) * 1000)
    print(
        f"질의 임베딩: {QUERY_COUNT}개를 하나씩, 중앙값 {statistics.median(latencies):.0f}ms,"
        f" 최대 {max(latencies):.0f}ms"
    )


if __name__ == "__main__":
    main()
