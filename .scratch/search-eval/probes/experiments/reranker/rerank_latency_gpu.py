"""GPU 리랭커(TEI turing-1.9.4)가 후보 수마다 리랭크 한 번에 걸리는 시간을 잰다(티켓 search-eval
17).

core 16의 지연 프로브(CPU, 후보 50개에 130초)와 견주려고, 제품 어댑터와 같은 방식으로 쌍을 32개씩
`/rerank`에 차례로 보낸다(`TeiReranker.rerank`가 `RAG_TEI_BATCH_SIZE`=32개씩 차례로 부른다. 읽었다).
글은 `tei-cpu/rerank_throughput.py`와 같은 합성 글(그 스크립트가 조각 크기로 적은 길이이고 이
스크립트는 토큰 수를 재지 않았다)이며 실제 조각이 아니다.
후보 수마다 3번 재고 중앙값과 최솟값·최댓값을 찍는다. 제품의 `search` 전체가 아니라 리랭크
호출만이다.

    uv run python -X utf8 -I rerank_latency_gpu.py http://127.0.0.1:18094

표준 라이브러리만 쓴다.
"""

import json
import statistics
import sys
import time
import urllib.request
from collections.abc import Mapping

SENTENCE = (
    "제{n}조(정의) 이 규정에서 사용하는 용어의 뜻은 다음과 같으며, "
    "관계 기관의 장은 소관 업무의 범위에서 필요한 사항을 따로 정하여 "
    "고시할 수 있고 그 결과를 지체 없이 공개하여야 한다. "
)
QUERY = "관계 기관의 장이 고시한 사항은 언제까지 공개해야 하나요 {n}"
BATCH_SIZE = 32
SENTENCES_PER_CHUNK = 9
CANDIDATE_COUNTS = (5, 10, 20, 50, 100)
REPEATS = 3


def post(url: str, payload: Mapping[str, object]) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        response.read()


def chunk_text(seed: int) -> str:
    return "".join(SENTENCE.format(n=seed * 100 + i) for i in range(SENTENCES_PER_CHUNK))


def rerank_once(base: str, query: str, texts: list[str]) -> float:
    started = time.perf_counter()
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        payload = {
            "query": query,
            "texts": batch,
            "truncate": True,
            "truncation_direction": "Right",
            "raw_scores": False,
            "return_text": False,
        }
        post(f"{base}/rerank", payload)
    return time.perf_counter() - started


def main(argv: list[str]) -> int:
    base = argv[0].rstrip("/")
    rerank_once(base, QUERY.format(n=0), [chunk_text(i) for i in range(4)])
    print("후보 수 | 호출 수 | 걸린 시간(초, 3번) | 중앙값 | 쌍/초(중앙값)")
    for count in CANDIDATE_COUNTS:
        times: list[float] = []
        for repeat in range(REPEATS):
            texts = [chunk_text(repeat * 1000 + i) for i in range(count)]
            times.append(rerank_once(base, QUERY.format(n=repeat + 1), texts))
        median = statistics.median(times)
        calls = -(-count // BATCH_SIZE)
        shown = ", ".join(f"{t:.1f}" for t in times)
        print(f"{count} | {calls} | {shown} | {median:.1f} | {count / median:.2f}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("사용법: rerank_latency_gpu.py <리랭커 끝점 주소>")
    raise SystemExit(main(sys.argv[1:]))
