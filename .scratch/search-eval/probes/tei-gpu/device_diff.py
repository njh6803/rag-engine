"""같은 글 32개의 임베딩과 같은 쌍 32개의 리랭크 점수가 장치와 실행에 따라 얼마나 다른지 잰다.

search-eval 티켓 14가 명세 "전체 게이트와 리랭커"의 값의 차 항목을 대는 프로브다. CPU 이미지에서 두
번 (컨테이너를 다시 띄우고 한 번 더), GPU 이미지에서 두 번 받아 둔 값을 `compare`로 견준다. 같은
장치에서 다시 계산한 값의 차(CPU 두 번, GPU 두 번)와 장치 사이의 차(CPU와 GPU)를 각각 낸다. 문턱은
명세의 어림이고, 어느 쪽이든 코사인 유사도의 최솟값이 0.999 아래이거나 점수 차의 최댓값이 0.01을
넘으면 `compare`가 종료 코드 1로 끝난다(그때 티켓은 멈춰 사용자에게 다시 묻는다).

글과 쌍은 `evals/public-docs/`에서 정해진 규칙으로 만들어 어느 실행에서나 같다. 글 j는 기대 근거
j~j+15(155개 순환)의 글귀를 공백으로 이은 것이다(이 묶음에서 `build`를 불러 재니 716~1211자, 중앙값
1064자였다. 조각 크기인 512토큰 안팎을 노린 것이고 토큰 수는 재지 않았다). 쌍 j의 질의는 j가 짝수면
근거 j의 사람 질문(글에 그 글귀가 들어 있어 점수가 높다), 홀수면 근거 (j+80)의 사람 질문(대개 무관해
점수가 낮다)이어서 점수가 여러 구간에 흩어진다. 요청 본문은 어댑터가 보내는 것과
같다(`src/rag_engine/adapters/tei.py`의 요청 모양을 읽었다). 임베딩은 `/v1/embeddings`에 `input`과
`model`, 리랭크는 `/rerank`에 `query`, `texts`와 `truncate=True`, `truncation_direction="Right"`,
`raw_scores=False`, `return_text=False`다. 글 32개는 TEI의 한 요청 상한 (`max_client_batch_size` 32)
하나로 보낸다.

    uv run python -X utf8 device_diff.py collect <URL> embed <모델> <묶음 폴더> <출력 JSON>
    uv run python -X utf8 device_diff.py collect <URL> rerank <모델> <묶음 폴더> <출력 JSON>
    uv run python -X utf8 device_diff.py compare <종류> <A JSON> <B JSON> [<이름>]

티켓 14는 받은 값을 작업 폴더에 `cpu_embed_1.json`, `cpu_embed_2.json`, `gpu_embed.json`,
`gpu_embed_2.json` (리랭크는 `cpu_rerank_1.json`, `cpu_rerank_2.json`, `gpu_rerank.json`,
`gpu_rerank_2.json`)로 두고 `compare`의 넷째 인자에 출력의 이름표("CPU 두 번(재기동 사이)" 따위)를
손으로 줬다. CPU 컨테이너를 내렸다 올리는 일도 손으로 했다. 값 JSON은 커밋하지 않았다.

표준 라이브러리만 쓴다.
"""

import json
import math
import sys
import time
import urllib.request
from pathlib import Path

COUNT = 32
PASSAGES_PER_TEXT = 16
IRRELEVANT_SHIFT = 80
MIN_COSINE = 0.999
MAX_SCORE_DIFF = 0.01


def read_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def build(bundle: Path) -> tuple[list[str], list[str]]:
    evidence = read_lines(bundle / "evidence.jsonl")
    queries = {
        str(row["evidence_id"]): str(row["query"])
        for row in read_lines(bundle / "queries-human.jsonl")
    }
    passages: list[list[str]] = []
    ids: list[str] = []
    for row in evidence:
        spans = row["evidence"]
        assert isinstance(spans, list)
        passages.append([str(span["passage"]) for span in spans if span["kind"] == "passage"])
        ids.append(str(row["id"]))
    total = len(evidence)
    texts = [
        " ".join(p for k in range(PASSAGES_PER_TEXT) for p in passages[(j + k) % total])
        for j in range(COUNT)
    ]
    pair_queries = [
        queries[ids[j % total]] if j % 2 == 0 else queries[ids[(j + IRRELEVANT_SHIFT) % total]]
        for j in range(COUNT)
    ]
    return texts, pair_queries


def post(url: str, path: str, body: dict[str, object]) -> object:
    request = urllib.request.Request(
        url + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=1800) as response:
        return json.loads(response.read())


def collect(url: str, kind: str, model: str, bundle: Path, out: Path) -> None:
    texts, queries = build(bundle)
    started = time.perf_counter()
    values: list[list[float]]
    if kind == "embed":
        rows = post(url, "/v1/embeddings", {"input": texts, "model": model})
        assert isinstance(rows, dict)
        data = sorted(rows["data"], key=lambda row: row["index"])
        values = [row["embedding"] for row in data]
    else:
        # 리랭크는 한 요청에 질의가 하나라 쌍마다 한 번씩 보낸다(글 하나씩).
        values = []
        for query, text in zip(queries, texts, strict=True):
            ranks = post(
                url,
                "/rerank",
                {
                    "query": query,
                    "texts": [text],
                    "truncate": True,
                    "truncation_direction": "Right",
                    "raw_scores": False,
                    "return_text": False,
                },
            )
            assert isinstance(ranks, list)
            values.append([ranks[0]["score"]])
    seconds = time.perf_counter() - started
    out.write_text(
        json.dumps({"kind": kind, "model": model, "seconds": seconds, "values": values}),
        encoding="utf-8",
    )
    print(kind, model, "count", len(values), "seconds", round(seconds, 1))


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def compare(kind: str, first: Path, second: Path, label: str) -> bool:
    a = json.loads(first.read_text(encoding="utf-8"))["values"]
    b = json.loads(second.read_text(encoding="utf-8"))["values"]
    identical = a == b
    worst = max(abs(x - y) for u, v in zip(a, b, strict=True) for x, y in zip(u, v, strict=True))
    line = f"{label}: {kind} 개수 {len(a)} 값이 같음 {identical} 최대 절대 차 {worst:.3e}"
    ok = True
    if kind == "embed":
        lowest = min(cosine(u, v) for u, v in zip(a, b, strict=True))
        line += f" 코사인 최솟값 {lowest:.9f}"
        ok = lowest >= MIN_COSINE
    else:
        scores = [v[0] for v in a]
        line += f" 점수 범위 {min(scores):.4f}~{max(scores):.4f}"
        ok = worst <= MAX_SCORE_DIFF
    print(line, "문턱 안" if ok else "문턱 밖")
    return ok


if __name__ == "__main__":
    if sys.argv[1] == "collect":
        collect(sys.argv[2], sys.argv[3], sys.argv[4], Path(sys.argv[5]), Path(sys.argv[6]))
    else:
        name = sys.argv[5] if len(sys.argv) > 5 else "비교"
        sys.exit(0 if compare(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), name) else 1)
