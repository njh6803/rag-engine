"""기다리는 일 없이 항목을 끝없이 내는 비동기 반복을 서버가 받는 방식마다, 같은 이벤트 루프의 다른
일이 도는지와 받는 속도와 받은 항목을 쌓아 둘 때의 메모리를 잰다(source-sync 명세 "동기화의 차례"의
끝없는 목록 항목, 2026-11-22 명세 검토가 낸 물음).

명세는 동기화가 작업 담당 기록의 기한을 늘릴 때마다 원천의 지움 표시를 보게 정했다. 기한을 늘리는
일은 같은 이벤트 루프에서 따로 돈다. 커넥터의 `list()`가 기다리는 일 없이 항목을 곧바로 내면, 받는
쪽이 항목 사이에 루프로 돌아가지 않는 한 그 일이 돌지 못한다. 받는 방식 다섯을 견준다.
1. `async for` 그대로.
2. 항목마다 `asyncio.wait_for`.
3. 항목마다 `asyncio.timeout`.
4. 항목마다 따로 띄운 일(Task)을 취소하지 않고 `asyncio.wait`로 한도까지 기다린다(ADR 0023이 정한
   "취소하지 않고 둔다"를 따르는 꼴).
5. 항목마다 따로 띄운 일을 `asyncio.shield`로 감싸 `asyncio.wait_for`로 기다린다.
방식마다 두 번 돈다. 첫째는 속도와 다른 일이 돈 횟수를 재고, 둘째는 `tracemalloc`을 켜 받은 항목을
사전에 쌓아 둘 때 항목 하나가 늘리는 메모리를 잰다(`tracemalloc`은 받는 속도를 늦추므로 따로 돈다).
항목은 서버 경로 커넥터의 키와 변경 확인값과 크기를 흉내 낸 것이다. 다른 일은 0.1초마다 깨어나는
일 하나이고, 기한을 늘리는 일을 흉내 낸다.

실행(저장소 루트에서. 출력의 줄 끝은 이 파일이 LF 로 맞춘다):
    uv run python -I -X utf8 .scratch/source-sync/probes/endless-list/probe.py \
        > .scratch/source-sync/probes/endless-list/probe_out_windows.txt
리눅스는 지어 둔 제품 작업자 이미지에서 돈다(Git Bash 에서는 `MSYS_NO_PATHCONV=1` 을 앞에 둔다.
커밋한 출력은 `rag-engine-test/rag-engine-worker:0.1.0-rc.1` 에서 받았다):
    docker run --rm --entrypoint python \
        -v "<저장소>/.scratch/source-sync/probes/endless-list:/probe:ro" \
        <작업자 이미지> -I -X utf8 /probe/probe.py \
        > .scratch/source-sync/probes/endless-list/probe_out_linux.txt
네트워크는 쓰지 않는다. 한 번에 25초쯤 걸린다.
"""

from __future__ import annotations

import asyncio
import platform
import sys
import time
import tracemalloc
from collections.abc import AsyncIterator, Callable

RUN_SECONDS = 2.0
LIMIT_SECONDS = 600.0
TICK_SECONDS = 0.1

Item = tuple[str, str, int]
Way = Callable[[AsyncIterator[Item]], AsyncIterator[Item]]


def emit(line: str) -> None:
    """한 줄을 UTF-8 과 LF 로 적는다. Windows 의 표준 출력이 줄 끝을 CRLF 로 바꾸지 않게 한다."""
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


async def endless() -> AsyncIterator[Item]:
    """서버 경로 키와 변경 확인값 꼴의 항목을 기다리지 않고 낸다."""
    i = 0
    while True:
        yield (
            f"규정집/인사/2026/문서_{i:09d}.pdf",
            f"{1732012345678901234 + i}:{123456 + i}",
            123456,
        )
        i += 1


async def ticker(counter: list[int]) -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        counter[0] += 1


async def via_async_for(items: AsyncIterator[Item]) -> AsyncIterator[Item]:
    async for item in items:
        yield item


async def via_wait_for(items: AsyncIterator[Item]) -> AsyncIterator[Item]:
    while True:
        yield await asyncio.wait_for(anext(items), LIMIT_SECONDS)


async def via_timeout(items: AsyncIterator[Item]) -> AsyncIterator[Item]:
    while True:
        async with asyncio.timeout(LIMIT_SECONDS):
            item = await anext(items)
        yield item


async def via_task_wait(items: AsyncIterator[Item]) -> AsyncIterator[Item]:
    while True:
        task = asyncio.ensure_future(anext(items))
        done, _ = await asyncio.wait({task}, timeout=LIMIT_SECONDS)
        if not done:
            raise TimeoutError
        yield task.result()


async def via_shield(items: AsyncIterator[Item]) -> AsyncIterator[Item]:
    while True:
        task = asyncio.ensure_future(anext(items))
        yield await asyncio.wait_for(asyncio.shield(task), LIMIT_SECONDS)


async def run(name: str, way: Way, *, trace: bool) -> None:
    counter = [0]
    tick = asyncio.create_task(ticker(counter))
    await asyncio.sleep(0)
    seen: dict[str, tuple[str, int]] = {}
    if trace:
        tracemalloc.start()
    started = time.perf_counter()
    async for key, marker, size in way(endless()):
        if key in seen:
            raise RuntimeError("같은 키가 두 번 나왔다")
        seen[key] = (marker, size)
        if len(seen) % 2000 == 0 and time.perf_counter() - started >= RUN_SECONDS:
            break
    elapsed = time.perf_counter() - started
    tick.cancel()
    count = len(seen)
    if trace:
        current, _peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        emit(
            f"  {name} (tracemalloc): 항목 {count}개, 쌓인 메모리 {current / count:.0f}바이트/항목"
        )
    else:
        emit(
            f"  {name}: {elapsed:.2f}초에 항목 {count}개({count / elapsed:,.0f}개/초), "
            f"같은 루프의 {TICK_SECONDS}초 일이 돈 횟수 {counter[0]}"
        )


async def main() -> None:
    emit(f"Python {platform.python_version()} {sys.platform} {platform.machine()}")
    ways: list[tuple[str, Way]] = [
        ("1 async for 그대로", via_async_for),
        ("2 항목마다 wait_for", via_wait_for),
        ("3 항목마다 asyncio.timeout", via_timeout),
        ("4 항목마다 Task와 asyncio.wait", via_task_wait),
        ("5 항목마다 Task와 shield+wait_for", via_shield),
    ]
    emit(f"속도와 다른 일(받는 시간 {RUN_SECONDS}초쯤)")
    for name, way in ways:
        await run(name, way, trace=False)
    emit("받은 항목을 사전에 쌓을 때의 메모리")
    for name, way in ways:
        await run(name, way, trace=True)


asyncio.run(main())
