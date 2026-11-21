"""돌아오지 않는 호출을 스레드와 자식 프로세스가 각각 어떻게 다룰 수 있는지를 잰다(source-sync 명세
"동기화의 차례"의 돌아오지 않는 호출 규칙, 2026-11-21 설계 인터뷰).

명세가 PR 95 에서 더한 규칙은 커넥터 호출을 스레드에서 돌리고, 한도를 넘기면 기다리기를 그만둔다.
그 규칙을 둘지 줄일지를 고르기 전에, 규칙이 기대는 파이썬의 사실과 다른 길(커넥터를 자식
프로세스에서 부르고 한도에 죽인다)이 치르는 값을 잰다. 막힌 읽기는 쓰는 쪽을 닫지 않은 빈 파이프의
`os.read` 로 흉내 낸다. 끊긴 공유 폴더의 읽기가 커널 안에서 어떻게 막히는지는 이 프로브가 재지
않는다. 그것은 파일 시스템과 커널에 달렸다. 보는 것 일곱.
A. `asyncio.wait_for` 가 한도에 돌아오는지와, 그 뒤에 막힌 스레드가 살아 있는지. 기본 풀
   (`asyncio.to_thread`)과 전용 daemon 스레드 둘 다.
B. 돌고 있는 일의 `Future.cancel()` 이 무엇을 내는지.
C. 스레드에 예외를 밖에서 넣는 길(`PyThreadState_SetAsyncExc`)이 읽기에 막힌 스레드를 끝내는지.
   파이썬 코드를 돌고 있는 스레드와 견준다.
D. 막힌 스레드가 남은 프로세스가 스스로 내려가는지. daemon 스레드, `ThreadPoolExecutor` 의 스레드,
   `asyncio.to_thread` 의 스레드, 전용 daemon 스레드를 쓴 asyncio 프로그램 넷을 따로 띄워
   8초 안에 끝나는지 본다.
E. 자식 프로세스(spawn)를 띄우는 데 걸리는 시간, 읽기에 막힌 자식을 `terminate()` 와 `kill()` 로
   끝내는 데 걸리는 시간, 자식이 든 100MB 를 파이프로 넘겨받는 시간, 떠 있는 자식과 64KiB 를
   주고받는 왕복 하나의 시간.
F. 읽기에 막힌 daemon 스레드 500개를 띄우는 시간과 그 스레드들이 쥐는 메모리. 메모리는 리눅스의
   `/proc/self/status` 에서만 읽는다.
G. 비동기 함수가 스레드로 넘기지 않고 이벤트 루프 안에서 막힐 때(잘못 만든 커넥터) 한도가
   지켜지는지와, 그동안 같은 루프의 다른 일이 도는지.

실행(저장소 루트에서. 출력의 줄 끝은 이 파일이 LF 로 맞춘다):
    uv run python -I -X utf8 .scratch/source-sync/probes/stuck-calls/probe.py \
        > .scratch/source-sync/probes/stuck-calls/probe_out_windows.txt
리눅스는 지어 둔 제품 작업자 이미지에서 돈다(Git Bash 에서는 `MSYS_NO_PATHCONV=1` 을 앞에 둔다.
커밋한 출력은 `rag-engine-test/rag-engine-worker:0.1.0-rc.1` 에서 받았다):
    docker run --rm --entrypoint python \
        -v "<저장소>/.scratch/source-sync/probes/stuck-calls:/probe:ro" \
        <작업자 이미지> -I -X utf8 /probe/probe.py \
        > .scratch/source-sync/probes/stuck-calls/probe_out_linux.txt
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import ctypes
import multiprocessing
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from asyncio import constants as asyncio_constants
from collections.abc import Awaitable, Callable
from multiprocessing.connection import Connection
from pathlib import Path

LIMIT_SECONDS = 1.0
SETTLE_SECONDS = 1.0
SCENARIO_WAIT_SECONDS = 8.0
PAYLOAD_BYTES = 100 * 1024 * 1024
ROUND_TRIP_BYTES = 64 * 1024
ROUND_TRIPS = 200
SPAWN_ROUNDS = 5
STUCK_THREADS = 500
LOOP_BLOCK_SECONDS = 3.0
TICK_SECONDS = 0.1
READY = b"ready"


def emit(line: str) -> None:
    """한 줄을 UTF-8 과 LF 로 적는다. Windows 의 표준 출력이 줄 끝을 CRLF 로 바꾸지 않게 한다."""
    sys.stdout.buffer.write(f"{line}\n".encode())
    sys.stdout.buffer.flush()


class Blocker:
    """막힌 읽기 하나. `release()` 를 부르기 전에는 `read()` 가 돌아오지 않는다."""

    def __init__(self) -> None:
        self._read_end, self._write_end = os.pipe()

    def read(self) -> bytes:
        return os.read(self._read_end, 1)

    def release(self, readers: int = 1) -> None:
        os.write(self._write_end, b"x" * readers)


async def timed_wait(awaitable: Awaitable[bytes]) -> tuple[str, float]:
    """한도까지만 기다리고, 무엇으로 끝났는지와 걸린 시간을 낸다."""
    started = time.perf_counter()
    try:
        await asyncio.wait_for(awaitable, LIMIT_SECONDS)
    except TimeoutError:
        return "TimeoutError", time.perf_counter() - started
    return "돌아왔다", time.perf_counter() - started


def start_dedicated(
    loop: asyncio.AbstractEventLoop, blocker: Blocker
) -> tuple[threading.Thread, asyncio.Future[bytes]]:
    """기본 풀을 쓰지 않고 전용 daemon 스레드에서 읽는다. 결과는 루프의 future 로 건넨다."""
    future: asyncio.Future[bytes] = loop.create_future()

    def deliver(data: bytes) -> None:
        if not future.done():
            future.set_result(data)

    def run() -> None:
        loop.call_soon_threadsafe(deliver, blocker.read())

    thread = threading.Thread(target=run, daemon=True, name="connector-call")
    thread.start()
    return thread, future


def new_threads(before: set[threading.Thread]) -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread not in before]


async def part_a() -> None:
    emit("A. 한도에 돌아오는지와 그 뒤의 스레드")
    blocker = Blocker()
    before = set(threading.enumerate())
    outcome, elapsed = await timed_wait(asyncio.to_thread(blocker.read))
    stuck = new_threads(before)
    await asyncio.sleep(SETTLE_SECONDS)
    alive = [thread.is_alive() for thread in stuck]
    daemon = [thread.daemon for thread in stuck]
    emit(f"  기본 풀(asyncio.to_thread): 한도 {LIMIT_SECONDS}초, {outcome}, {elapsed:.2f}초")
    emit(f"    한도를 넘기고 1초 뒤 그 스레드가 살아 있다: {alive}, daemon: {daemon}")
    blocker.release()
    await asyncio.sleep(SETTLE_SECONDS)
    alive = [thread.is_alive() for thread in stuck]
    emit(f"    읽기가 돌아온 뒤 살아 있다: {alive}(풀의 스레드는 다음 일을 기다리며 남는다)")

    blocker = Blocker()
    thread, future = start_dedicated(asyncio.get_running_loop(), blocker)
    outcome, elapsed = await timed_wait(future)
    await asyncio.sleep(SETTLE_SECONDS)
    emit(f"  전용 daemon 스레드: 한도 {LIMIT_SECONDS}초, {outcome}, {elapsed:.2f}초")
    emit(f"    한도를 넘기고 1초 뒤 그 스레드가 살아 있다: {thread.is_alive()}")
    blocker.release()
    await asyncio.sleep(SETTLE_SECONDS)
    emit(f"    읽기가 돌아온 뒤 살아 있다: {thread.is_alive()}")


def part_b() -> None:
    emit("B. 돌고 있는 일을 취소할 수 있는지")
    blocker = Blocker()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(blocker.read)
    time.sleep(SETTLE_SECONDS)
    emit(f"  running(): {future.running()}, cancel(): {future.cancel()}")
    emit(f"  cancel() 뒤 done(): {future.done()}")
    blocker.release()
    pool.shutdown(wait=True)
    emit(f"  읽기가 돌아온 뒤 done(): {future.done()}")


def inject_exception(thread: threading.Thread) -> int:
    """스레드에 SystemExit 를 밖에서 넣는다. 고쳐진 스레드 상태의 수를 낸다."""
    ident = thread.ident
    if ident is None:
        raise RuntimeError("스레드가 아직 뜨지 않았다")
    changed = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(ident), ctypes.py_object(SystemExit)
    )
    return int(changed)


def spin(stop: threading.Event) -> None:
    """파이썬 코드를 돌며 기다린다. 막힌 읽기와 견주는 쪽이다."""
    while not stop.is_set():
        time.sleep(0.01)


def part_c() -> None:
    emit("C. 스레드에 예외를 밖에서 넣기(PyThreadState_SetAsyncExc)")
    stop = threading.Event()
    spinning = threading.Thread(target=spin, args=(stop,), daemon=True)
    spinning.start()
    changed = inject_exception(spinning)
    time.sleep(SETTLE_SECONDS)
    alive = spinning.is_alive()
    emit(f"  파이썬 코드를 도는 스레드: 고쳐진 수 {changed}, 1초 뒤 살아 있다: {alive}")
    stop.set()

    blocker = Blocker()
    blocked = threading.Thread(target=blocker.read, daemon=True)
    blocked.start()
    time.sleep(SETTLE_SECONDS)
    changed = inject_exception(blocked)
    time.sleep(SETTLE_SECONDS)
    alive = blocked.is_alive()
    emit(f"  읽기에 막힌 스레드: 고쳐진 수 {changed}, 1초 뒤 살아 있다: {alive}")
    blocker.release()
    blocked.join(SETTLE_SECONDS)
    emit(f"    읽기가 돌아온 뒤 살아 있다: {blocked.is_alive()}")


def scenario_daemon() -> None:
    threading.Thread(target=Blocker().read, daemon=True).start()
    time.sleep(0.2)
    emit("main 이 끝났다")


def scenario_pool() -> None:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    pool.submit(Blocker().read)
    time.sleep(0.2)
    emit("main 이 끝났다")


def scenario_to_thread() -> None:
    async def main() -> None:
        outcome, elapsed = await timed_wait(asyncio.to_thread(Blocker().read))
        emit(f"wait_for: {outcome} {elapsed:.2f}초")

    asyncio.run(main())
    emit("asyncio.run 이 끝났다")


def scenario_dedicated() -> None:
    async def main() -> None:
        future = start_dedicated(asyncio.get_running_loop(), Blocker())[1]
        outcome, elapsed = await timed_wait(future)
        emit(f"wait_for: {outcome} {elapsed:.2f}초")

    asyncio.run(main())
    emit("asyncio.run 이 끝났다")


SCENARIO_TITLES: dict[str, str] = {
    "daemon": "막힌 daemon 스레드 하나",
    "pool": "ThreadPoolExecutor 의 막힌 스레드 하나",
    "to_thread": "asyncio.to_thread 가 한도를 넘긴 뒤",
    "dedicated": "전용 daemon 스레드가 한도를 넘긴 뒤",
}
SCENARIOS: dict[str, Callable[[], None]] = {
    "daemon": scenario_daemon,
    "pool": scenario_pool,
    "to_thread": scenario_to_thread,
    "dedicated": scenario_dedicated,
}


def run_scenario(name: str) -> tuple[str, float, str]:
    """시나리오 하나를 새 인터프리터에서 돌려, 끝났는지와 걸린 시간과 그 출력을 낸다."""
    command = [sys.executable, "-I", "-X", "utf8", __file__, "scenario", name]
    started = time.perf_counter()
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8"
    )
    try:
        process.wait(SCENARIO_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        verdict = f"{SCENARIO_WAIT_SECONDS}초 안에 끝나지 않아 죽였다"
    else:
        verdict = f"스스로 끝났다(종료 코드 {process.returncode})"
    elapsed = time.perf_counter() - started
    output, _ = process.communicate()
    return verdict, elapsed, " / ".join(output.splitlines())


def part_d() -> None:
    emit("D. 막힌 스레드가 남은 프로세스가 스스로 내려가는지")
    join_timeout = asyncio_constants.THREAD_JOIN_TIMEOUT
    emit(f"  asyncio.run 이 기본 풀을 기다리는 한도(THREAD_JOIN_TIMEOUT): {join_timeout}초")
    for name, title in SCENARIO_TITLES.items():
        verdict, elapsed, output = run_scenario(name)
        emit(f"  {title}: {verdict}, {elapsed:.2f}초")
        emit(f"    그 프로세스의 출력: {output}")


def child_ready(conn: Connection) -> None:
    conn.send_bytes(READY)
    conn.close()


def child_blocked(conn: Connection) -> None:
    conn.send_bytes(READY)
    Blocker().read()


def child_payload(conn: Connection, size: int) -> None:
    data = bytes(size)
    conn.send_bytes(READY)
    conn.send_bytes(data)
    conn.close()


def child_round_trips(conn: Connection) -> None:
    """받은 수만큼의 바이트를 돌려준다. 0 을 받으면 끝난다."""
    conn.send_bytes(READY)
    while size := int.from_bytes(conn.recv_bytes(), "big"):
        conn.send_bytes(bytes(size))
    conn.close()


def measure_spawn() -> list[float]:
    context = multiprocessing.get_context("spawn")
    times: list[float] = []
    for _ in range(SPAWN_ROUNDS):
        parent, child = context.Pipe(duplex=False)
        started = time.perf_counter()
        process = context.Process(target=child_ready, args=(child,))
        process.start()
        child.close()
        parent.recv_bytes()
        times.append(time.perf_counter() - started)
        process.join()
        parent.close()
    return times


def measure_end(method: str) -> tuple[float, int | None]:
    """읽기에 막힌 자식을 `terminate` 나 `kill` 로 끝내고, 걸린 시간과 종료 코드를 낸다."""
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=child_blocked, args=(child,))
    process.start()
    child.close()
    parent.recv_bytes()
    time.sleep(SETTLE_SECONDS)
    started = time.perf_counter()
    if method == "kill":
        process.kill()
    else:
        process.terminate()
    process.join(SCENARIO_WAIT_SECONDS)
    elapsed = time.perf_counter() - started
    parent.close()
    return elapsed, process.exitcode


def measure_payload() -> tuple[str, float]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=child_payload, args=(child, PAYLOAD_BYTES))
    process.start()
    child.close()
    parent.recv_bytes()
    started = time.perf_counter()
    try:
        data = parent.recv_bytes()
    except EOFError:
        outcome = "자식이 보내지 못하고 끝났다"
    else:
        outcome = f"{len(data)}바이트를 받았다"
    elapsed = time.perf_counter() - started
    process.join()
    parent.close()
    return outcome, elapsed


def measure_round_trips() -> list[float]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(target=child_round_trips, args=(child,))
    process.start()
    child.close()
    parent.recv_bytes()
    times: list[float] = []
    for _ in range(ROUND_TRIPS):
        started = time.perf_counter()
        parent.send_bytes(ROUND_TRIP_BYTES.to_bytes(8, "big"))
        parent.recv_bytes()
        times.append(time.perf_counter() - started)
    parent.send_bytes((0).to_bytes(8, "big"))
    process.join()
    parent.close()
    return times


def part_e() -> None:
    emit("E. 자식 프로세스(spawn)")
    spawn = measure_spawn()
    middle, low, high = statistics.median(spawn), min(spawn), max(spawn)
    emit(f"  띄워서 첫 응답까지({SPAWN_ROUNDS}회): 가운데 {middle:.3f}초, {low:.3f}~{high:.3f}초")
    for method in ("terminate", "kill"):
        elapsed, exitcode = measure_end(method)
        emit(f"  읽기에 막힌 자식을 {method}(): {elapsed:.3f}초 뒤 끝났다, 종료 코드 {exitcode}")
    outcome, elapsed = measure_payload()
    megabytes = PAYLOAD_BYTES // (1024 * 1024)
    emit(f"  자식이 든 {megabytes}MB 를 파이프로 받기: {outcome}, {elapsed:.3f}초")
    trips = [seconds * 1000 for seconds in measure_round_trips()]
    middle, high = statistics.median(trips), max(trips)
    kibibytes = ROUND_TRIP_BYTES // 1024
    emit(f"  떠 있는 자식과 {kibibytes}KiB 왕복({ROUND_TRIPS}회): 가운데 {middle:.3f}밀리초")
    emit(f"    가장 길게 {high:.3f}밀리초")


def resident_kilobytes() -> int | None:
    """이 프로세스가 실제로 쥔 메모리(VmRSS, kB). 리눅스가 아니면 None 이다."""
    try:
        status = Path("/proc/self/status").read_text(encoding="ascii")
    except OSError:
        return None
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


def part_f() -> None:
    emit(f"F. 읽기에 막힌 daemon 스레드 {STUCK_THREADS}개")
    blocker = Blocker()
    threads = [threading.Thread(target=blocker.read, daemon=True) for _ in range(STUCK_THREADS)]
    before = resident_kilobytes()
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    elapsed = time.perf_counter() - started
    time.sleep(SETTLE_SECONDS)
    after = resident_kilobytes()
    alive = sum(thread.is_alive() for thread in threads)
    emit(f"  띄우는 데 {elapsed:.3f}초, 1초 뒤 살아 있는 수 {alive}")
    if before is None or after is None:
        emit("  메모리는 리눅스에서만 잰다(/proc/self/status 의 VmRSS)")
    else:
        each = (after - before) / STUCK_THREADS
        emit(f"  실제로 쥔 메모리(VmRSS): {before}kB 에서 {after}kB, 스레드 하나에 {each:.1f}kB")
    blocker.release(STUCK_THREADS)
    for thread in threads:
        thread.join(SETTLE_SECONDS)
    alive = sum(thread.is_alive() for thread in threads)
    emit(f"  읽기가 돌아온 뒤 살아 있는 수 {alive}")


async def block_the_loop() -> bytes:
    """스레드로 넘기지 않고 이벤트 루프 안에서 기다린다. 잘못 만든 커넥터를 흉내 낸다."""
    time.sleep(LOOP_BLOCK_SECONDS)
    return b""


async def count_ticks(ticks: list[float]) -> None:
    """같은 루프에서 0.1초마다 한 번씩 도는 다른 일이다. 돈 시각을 적는다."""
    while True:
        await asyncio.sleep(TICK_SECONDS)
        ticks.append(time.perf_counter())


async def part_g() -> None:
    emit("G. 비동기 함수가 이벤트 루프 안에서 막힐 때")
    ticks: list[float] = []
    ticker = asyncio.create_task(count_ticks(ticks))
    await asyncio.sleep(TICK_SECONDS * 3)
    started = time.perf_counter()
    outcome, elapsed = await timed_wait(block_the_loop())
    during = sum(1 for tick in ticks if started < tick < started + elapsed)
    ticker.cancel()
    emit(f"  루프를 {LOOP_BLOCK_SECONDS}초 막는 호출: 한도 {LIMIT_SECONDS}초, {outcome}")
    emit(f"    걸린 시간 {elapsed:.2f}초, 그동안 같은 루프의 다른 일(0.1초마다)이 돈 횟수 {during}")


def main() -> None:
    if sys.argv[1:2] == ["scenario"]:
        SCENARIOS[sys.argv[2]]()
        return
    emit(f"Python {platform.python_version()}, {platform.platform()}, CPU {os.cpu_count()}개")
    asyncio.run(part_a())
    part_b()
    part_c()
    part_d()
    part_e()
    part_f()
    asyncio.run(part_g())


if __name__ == "__main__":
    main()
