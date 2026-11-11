"""[probe] 다른 스레드가 Kiwi를 처음 적재하는 동안 주 스레드가 얼마나 멈추는지 잰다(GIL).

저장소 루트에서 `uv run python .scratch/harness/probes/kiwi_warmup_stall/gil_stall.py`로
돌린다. 결과는 `gil_stall_out.txt`에 있고 요약은 그 파일의 끝 문단이다. 스레드는
`threading.Thread`다. 앱 lifespan이 쓰는 `asyncio.to_thread` 길은 `server_first_request.py`의
원인 재현 갈래가 잰다.
"""

import threading
import time

from rag_engine.adapters.kiwi import tokenize_keywords

load_seconds = [0.0]


def load() -> None:
    t = time.perf_counter()
    tokenize_keywords("준비")
    load_seconds[0] = time.perf_counter() - t


thread = threading.Thread(target=load)
started = time.perf_counter()
thread.start()
max_gap = 0.0
gaps_over_100ms = 0
while thread.is_alive():
    t = time.perf_counter()
    time.sleep(0.01)
    gap = time.perf_counter() - t
    max_gap = max(max_gap, gap)
    if gap > 0.1:
        gaps_over_100ms += 1
thread.join()
print(f"[probe] kiwi cold load in thread: {load_seconds[0]:.3f}s")
print(
    f"[probe] main thread max stall while loading: {max_gap:.3f}s (gaps>100ms: {gaps_over_100ms})"
)
t = time.perf_counter()
tokenize_keywords("준비")
print(f"[probe] warm tokenize: {time.perf_counter() - t:.3f}s")
