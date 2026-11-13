"""같은 TEI CPU 이미지에서 같은 글을 다시 계산한 값이 같은지 본다.

search-eval 티켓 세션(2026-11-13)의 명세 검토가 처음 지어 돌렸고, 명세의 추론 기록 절(같은
장치에서 다시 계산한 값의 항목)이 근거로 든다. 커밋하며 바꾼 것은 머리 주석을 이 독스트링으로 옮긴
것, 긴 문장 상수를 두 줄로 나눈 것(값은 같다), `mixed`를 `__main__` 앞으로 옮겨 명령줄로 부르게 한
것뿐이다. 검토는 `mixed`를 `importlib`로 모듈을 올려 불렀다.

띄우기(모델은 이미 받아 둔 볼륨에서 읽는다. 처음이면 `HF_HUB_OFFLINE=1`을 빼고 띄워 받는다):

    MSYS_NO_PATHCONV=1 docker run -d --name tei-repeat-embed --cpus=4 -p 127.0.0.1:18091:80 \
        -e HF_HUB_OFFLINE=1 -v rag-latency-probe_tei-data:/data \
        ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4 \
        --model-id BAAI/bge-m3 --max-batch-tokens 4096

돌리기(검토가 친 차례):

    uv run --no-project python -I tei_repeat.py collect \
        http://127.0.0.1:18091 embed BAAI/bge-m3 run1.json
    docker restart tei-repeat-embed
    uv run --no-project python -I tei_repeat.py collect \
        http://127.0.0.1:18091 embed BAAI/bge-m3 run2.json
    uv run --no-project python -I tei_repeat.py compare run1.json run2.json
    uv run --no-project python -I tei_repeat.py mixed http://127.0.0.1:18091 BAAI/bge-m3

`collect URL KIND MODEL OUT`: KIND 가 embed 면 `/v1/embeddings`, rerank 면 `/rerank` 를 부른다.
같은 글 8개를 같은 묶음 두 번, 순서를 뒤집은 묶음, 넷씩 나눈 묶음으로 보내 값을 파일에 쓴다.
`compare A B`: 두 파일의 같은 글끼리 같은지, 최대 절대 차, 코사인 최솟값을 찍는다. A 의 첫
묶음이 기준이다. `mixed URL MODEL`: 길이가 다른 짧은 글 셋을 한 묶음에 섞었을 때(패딩이 생긴다)
값이 달라지는지 본다. 표준 라이브러리만 쓴다.
"""

import json
import math
import sys
import time
import urllib.request

SENTENCE = (
    "제{n}조 이 규정에서 사용하는 용어의 뜻은 다음과 같으며, 관계 기관의 장은 소관 업무의 범위에서 "
    "필요한 사항을 따로 정하여 고시할 수 있고 그 결과를 지체 없이 공개하여야 한다. "
)
QUERY = "관계 기관의 장이 고시한 사항은 언제까지 공개해야 하나요"
COUNT = 8


def texts():
    return ["".join(SENTENCE.format(n=s * 100 + i) for i in range(9)) for s in range(COUNT)]


def post(url, path, body):
    data = json.dumps(body).encode("utf-8")
    headers = dict()
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url + path, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=1800) as response:
        return json.loads(response.read())


def wait(url):
    for _ in range(900):
        try:
            with urllib.request.urlopen(url + "/health", timeout=5):
                return
        except OSError:
            time.sleep(1)
    raise SystemExit("TEI did not come up")


def call(url, kind, model, batch):
    if kind == "embed":
        body = dict(input=batch, model=model)
        rows = post(url, "/v1/embeddings", body)["data"]
        return [row["embedding"] for row in sorted(rows, key=lambda row: row["index"])]
    body = dict(query=QUERY, texts=batch, truncate=True, truncation_direction="Right")
    body["raw_scores"] = False
    body["return_text"] = False
    ranks = post(url, "/rerank", body)
    return [[rank["score"]] for rank in sorted(ranks, key=lambda rank: rank["index"])]


def collect(url, kind, model, out):
    wait(url)
    items = texts()
    passes = dict()
    started = time.perf_counter()
    passes["same_1"] = call(url, kind, model, items)
    passes["same_2"] = call(url, kind, model, items)
    passes["reversed"] = list(reversed(call(url, kind, model, list(reversed(items)))))
    passes["halves"] = call(url, kind, model, items[:4]) + call(url, kind, model, items[4:])
    elapsed = time.perf_counter() - started
    with open(out, "w", encoding="utf-8") as stream:
        json.dump(dict(kind=kind, model=model, seconds=elapsed, passes=passes), stream)
    print(kind, model, "texts", len(items), "seconds", round(elapsed, 1))


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm


def diff(label, left, right):
    worst = max(
        abs(x - y) for a, b in zip(left, right, strict=True) for x, y in zip(a, b, strict=True)
    )
    identical = all(a == b for a, b in zip(left, right, strict=True))
    line = [label, "identical", identical, "max_abs_diff", worst]
    if len(left[0]) > 1:
        line += ["min_cosine", min(cosine(a, b) for a, b in zip(left, right, strict=True))]
    print(*line)


def compare(first, second):
    with open(first, encoding="utf-8") as stream:
        a = json.load(stream)
    with open(second, encoding="utf-8") as stream:
        b = json.load(stream)
    base = a["passes"]["same_1"]
    for name, values in a["passes"].items():
        diff("in-process same_1 vs " + name, base, values)
    for name, values in b["passes"].items():
        diff("restart same_1 vs " + name, base, values)


def mixed(url, model):
    # 길이가 다른 글을 한 묶음에 섞었을 때(패딩이 생긴다) 값이 달라지는지 본다.
    items = texts()
    short = [QUERY, "공개 기한", items[0][:40]]
    alone = call(url, "embed", model, items) + call(url, "embed", model, short)
    together = call(url, "embed", model, short + items)
    together = together[len(short) :] + together[: len(short)]
    diff("embed alone vs mixed-length batch", alone, together)


if __name__ == "__main__":
    if sys.argv[1] == "collect":
        collect(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif sys.argv[1] == "mixed":
        mixed(sys.argv[2], sys.argv[3])
    else:
        compare(sys.argv[2], sys.argv[3])
