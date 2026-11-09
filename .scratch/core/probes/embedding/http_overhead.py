"""Measure localhost HTTP round-trip overhead for an embedding-shaped request (no model).

Server: FastAPI/uvicorn returning a fixed 1024-float vector per input.
Client: httpx with keep-alive (and once without keep-alive).

임베딩을 별도 컨테이너(TEI)에 HTTP 로 맡길 때 모델 추론을 뺀 HTTP 왕복 자체의 비용을 잰다. 서버는
같은 폴더의 `fake_server.py`(처음에는 이 스크립트가 써 내던 파일을 그대로 커밋했다)이고, 쿼리
하나(1×1024 벡터)와 문서 32개(32×1024 벡터)를 keep-alive 로, 쿼리 하나를 연결마다 새로 맺어 잰다.

실행: uv run python .scratch/core/probes/embedding/http_overhead.py
(저장소 루트에서. fastapi·uvicorn·httpx 는 저장소 의존성에 있다. 127.0.0.1:18765 에 서버를 띄우고
바깥 네트워크는 쓰지 않는다.)

2026-11-09에 이 PC(Windows)에서 돌려 표준 출력으로 읽었다. 쿼리 하나 keep-alive 의 p50 이 2.69ms
였다 (ADR 0010 이 드는 수). 그 출력 파일은 남기지 않았고, 수는 그날 그 PC 의 것이다. 저장소로
옮긴 뒤 같은 날 다시 돌린 출력은 `http_overhead_out.txt` 다(쿼리 하나 keep-alive p50 2.96ms,
문서 32개 p50 53.69ms, 연결마다 새로 맺기 p50 17.40ms).

저장소로 옮기며(2026-11-09) 서버 코드 문자열을 써 내던 자리를 지우고(커밋한 `fake_server.py` 를
그대로 띄운다), `payload: dict` 에 타입 인자를 붙였다. 측정 코드는 그대로다.
"""

import pathlib
import statistics
import subprocess
import sys
import time

import httpx

PORT = 18765
HERE = pathlib.Path(__file__).parent


def run(
    client: httpx.Client, url: str, label: str, payload: dict[str, str | list[str]], n: int
) -> None:
    for _ in range(20):
        client.post(url, json=payload)
    lat: list[float] = []
    resp_bytes = 0
    for _ in range(n):
        t0 = time.perf_counter()
        r = client.post(url, json=payload)
        r.raise_for_status()
        r.json()
        lat.append((time.perf_counter() - t0) * 1000)
        resp_bytes = len(r.content)
    lat.sort()
    p50 = statistics.median(lat)
    p95 = lat[int(n * 0.95)]
    print(
        f"{label}: n={n} p50={p50:.2f} ms p95={p95:.2f} ms min={lat[0]:.2f} ms"
        f" resp_bytes={resp_bytes}"
    )


def main() -> None:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "fake_server:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
        "--log-level",
        "error",
    ]
    proc = subprocess.Popen(cmd, cwd=HERE)
    url = f"http://127.0.0.1:{PORT}/v1/embeddings"
    try:
        with httpx.Client(timeout=10) as c:
            for _ in range(100):
                try:
                    c.post(url, json={"input": "warm"})
                    break
                except httpx.ConnectError:
                    time.sleep(0.1)
            run(
                c,
                url,
                "1 query -> 1 x 1024-d vector (keep-alive)",
                {"input": "한국어 질의 하나 " * 4},
                300,
            )
            run(
                c,
                url,
                "32 docs -> 32 x 1024-d vectors (keep-alive)",
                {"input": ["문서 조각 " * 50] * 32},
                100,
            )
        lat: list[float] = []
        for _ in range(100):
            with httpx.Client(timeout=10) as c3:
                t0 = time.perf_counter()
                c3.post(url, json={"input": "q"})
                lat.append((time.perf_counter() - t0) * 1000)
        lat.sort()
        print(
            "1 query, new TCP connection per call:"
            f" p50={statistics.median(lat):.2f} ms p95={lat[95]:.2f} ms"
        )
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
