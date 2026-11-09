"""pre-commit 의 always_run 검사를 함께 띄우고 결과를 모은다(ADR 0005 이력 2026-10-07).

pre-commit 은 훅을 하나씩 돈다(4.6.2 `commands/run.py` 의 `_run_hooks`). 커밋마다 도는 검사 일곱을
한꺼번에 띄우면 차례로 돌 때보다 Linux 와 Windows 모두 4할 남짓 줄었다(잰 시간과 프로브는
ADR 0005 의 2026-10-07 이력). 그래서
`.pre-commit-config.yaml` 은 이 검사들을 훅 하나로 두고 이 러너가 함께 띄운다. 잰 뒤에 워크플로
감사(zizmor, ADR 0027)가 더해져 여덟이다. 그 검사는 한 번에 0.3초 남짓이지만, 그 회귀 테스트가
그때 병목이던 pytest 에 1.5~6.7초를 더한다(손으로 봤다). 함께 띄운 벽시계 시간은 다시 재지 않았다.
그 뒤에 커밋 검사(`tools/check_ticket.py`, ADR 0037)가 더해져 아홉이다. 그 검사가 지금 색인을 보므로
일부 파일만 커밋할 때 git 이 훅에 준 임시 색인(`GIT_INDEX_FILE`)이 자식까지 그대로 가야 한다.
리눅스가 아닌 곳에서는 pyright 를 리눅스 플랫폼으로 한 번 더 돌아 열이다(`pyright_checks`, 대기열
403). 여기까지는 agent-os 의 수다. rag-engine 은 web 검사(`pnpm -C web verify`)를 옮기지 않아
여덟이고, 리눅스가 아닌 곳에서 아홉이다.
파일을 고치는 ruff 둘은 이 훅 앞에 따로 있어, 러너는 고친 뒤의 파일을 본다. 검사 목록의 원천은 여기
하나다. CI 는 잡마다 명령을 직접 돈다(`.github/workflows/ci.yml`).

pytest 는 pytest-xdist 로 논리 CPU 수의 절반만큼 프로세스를 나눠 돈다(ADR 0035). 함께 띄운 뒤에도
한 프로세스 pytest 가 가장 긴 막대라, 문서만 바꾼 커밋도 약 11.5분 걸렸다(대기열 309). 나누는
자리는 이 러너뿐이다. 손으로 치는 `uv run pytest`, `tools/mutate.py` 가 띄우는 pytest, LLM
테스트(`-m llm`), CI 는 한 프로세스로 돈다. 그래서 테스트끼리 부딪혀서 나는 실패는 이 러너에서만
나고, CI 의 빨강과 따로 읽는다. 변경을 마치고 손으로 전체를 볼 때도 이 러너를 친다(ADR 0035 이력
2026-10-19).

통과한 검사는 한 줄을, 실패한 검사는 그 줄 뒤에 모은 출력(stdout 과 stderr)을 끝난 차례로 찍는다.
하나라도 실패하면 1로 끝난다. pre-commit 의 `SKIP` 을 같은 id 로 읽어, `SKIP=pytest git commit` 이
검사마다 훅이 따로 있던 때처럼 통한다. 명령은 `shutil.which` 로 찾는다. Windows 에서 npm 전역
설치의 `pnpm` 은 `pnpm.cmd` 라 경로 없이는 띄우지 못한다. GitHub Actions 의 windows-latest 에서
`shutil.which` 는 그것을 찾았고 경로 없는 `subprocess` 는 WinError 2 였다(실행 37561588972, 일지
2026-10-07-07).

agent-os 에서 함께 돌 때 서로 보던 파일은 Vitest 판정자 테스트가 `web/judge-*` 에 쓰는 임시 트리
하나였다(일지 2026-10-07-05). rag-engine 에는 그 web 검사가 없다.

검사마다 시간 제한(`Check.timeout`, 기본 `CHECK_TIMEOUT_SECONDS`)이 있다. 넘기면 그 검사의
프로세스 트리(xdist 작업자까지)를 끝내고 "N초 시간 제한을 넘겼다"로 실패시킨다. 제한이 없던 때
pytest 작업 프로세스 여덟이 일을 받지 못한 채 약 11시간 남아 커밋을 붙잡았다(대기열 333,
`.claude/rules/tools.md` 의 기다리는 도구 항목). pre-commit 은 훅에 시간 제한을 두지 않는다.
기다리는 도중 Ctrl-C 가 나면 남은 검사의 트리를 끝내고 다시 던진다. POSIX 에서 자식은 제 세션을
이끌어 터미널의 Ctrl-C 를 받지 못하기 때문이다. 한 검사가 실패해도 지금은 나머지를 끝까지 기다린다.
곧바로 멈출지는 아직 정하지 않았다(대기열 192).

못 보는 것: 제한 안에서 멈춘 검사는 제한까지 러너를 붙잡는다. 시간 제한과 Ctrl-C 의 테스트가
윈도우의 `taskkill /T` 길은 이 PC 에서 재고, POSIX 의 프로세스 그룹 길은 CI 의 Linux 에서 잰다.
그룹을 떠난 손자(제 세션을 새로 연 것)는 POSIX 에서 끝내지 못한다. CPU 가
넷보다 적은 기계에서 함께 띄운 것이 차례로 돈 것보다 느린지는 재지 않았다. Windows 의
`pnpm.cmd` 길은 위 실행에서 한 번 봤을 뿐이고, 그 길을 거는 상설 테스트는 없다. CI 는 Linux 에서만
돈다. 세션 둘이 같은 시각에 커밋하면 pytest 프로세스가 두 배로 떠, 시간에 기댄 사례가 빨개질 수
있다. 잠금은 두지 않았다(두 벌 동시의 한 바퀴는 `.scratch/harness/probes/precommit_xdist/` 가 잰다).
절반 규칙은 이 PC(논리 CPU 16, 물리 코어 8)에서만 쟀고, `os.cpu_count()` 가 컨테이너의 CPU 한도를
반영하는지는 재지 않았다.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[1]
_NAME_WIDTH = 40
# agent-os pre-commit 의 관측 최대(xdist 전 한 프로세스 pytest 1,048초)의 네 배 남짓
CHECK_TIMEOUT_SECONDS = 4200
_KILL_SECONDS = 30  # 윈도우의 `taskkill` 을 기다리는 시간
_DRAIN_SECONDS = 10  # 끝낸 뒤 남은 출력을 기다리는 시간


@dataclass(frozen=True)
class Check:
    """검사 하나. id 는 `SKIP` 이 읽는 이름이고, 러너 전부터 있던 검사는 예전 훅 id 와 같다.
    timeout 은 초이고, 넘기면 그 검사의 프로세스 트리를 끝내고 실패로 센다."""

    id: str
    command: tuple[str, ...]
    timeout: float = CHECK_TIMEOUT_SECONDS


@dataclass(frozen=True)
class Outcome:
    check: Check
    passed: bool
    output: bytes
    seconds: float


def pytest_workers(cpu_count: int | None) -> int:
    """pytest 를 나눠 돌릴 프로세스 수. 논리 CPU 의 절반이고 1 아래로 내려가지 않는다(ADR 0035).

    `os.cpu_count()` 는 하드웨어 스레드 수라 물리 코어의 두 배일 수 있고, 값을 모르면 None 이다.
    """
    return max(1, (cpu_count or 1) // 2)


def pyright_checks(platform: str) -> tuple[Check, ...]:
    """pyright 검사. 리눅스가 아니면 `--pythonplatform Linux` 로 한 번 더 돈다.

    이 PC(윈도)의 pyright 와 러너가 초록인 시험 파일을 리눅스 CI 의 pyright 가
    `sys.platform == "win32"` 갈래에서만 쓴 가져오기로 빨갛게 냈다(대기열 403). 리눅스에서는 두
    검사가 같아 한 번만 돈다. 시험이 리눅스에서만 빨개지는 몫(281·318 의 꼴)은 이 검사가 잡지
    못하고 CI 가 잡는다. 둘째 검사는 id 가 따로라 `SKIP=pyright` 로는 빠지지 않는다. 둘 다 빼려면
    `SKIP=pyright,pyright-linux` 다(PR 직전 리뷰).
    """
    plain = Check("pyright", ("uv", "run", "pyright"))
    if platform == "linux":
        return (plain,)
    return (plain, Check("pyright-linux", ("uv", "run", "pyright", "--pythonplatform", "Linux")))


CHECKS: tuple[Check, ...] = (
    *pyright_checks(sys.platform),
    Check("lint-imports", ("uv", "run", "lint-imports")),
    Check("pytest", ("uv", "run", "pytest", "-q", "-n", str(pytest_workers(os.cpu_count())))),
    Check("check-instructions", ("uv", "run", "python", "tools/check_instructions.py")),
    Check("check-type-escapes", ("uv", "run", "python", "tools/check_type_escapes.py")),
    Check("run-hooks", ("uv", "run", "python", "tools/run_hooks.py")),
    Check("check-ticket", ("uv", "run", "python", "tools/check_ticket.py")),
    Check(
        "zizmor",
        ("uv", "run", "zizmor", "--offline", "--strict-collection")
        + ("--config", ".github/zizmor.yml", "."),
    ),
)


def skipped_ids(environ: Mapping[str, str]) -> frozenset[str]:
    """pre-commit 의 `_get_skips` 와 같은 모양으로 읽는다. 쉼표로 나누고 공백을 걷는다."""
    return frozenset(part.strip() for part in environ.get("SKIP", "").split(",") if part.strip())


def kill_tree(process: subprocess.Popen[bytes]) -> None:
    """자식과 그 자식이 띄운 프로세스(pytest 의 xdist 작업자)를 끝낸다. `tools/mutate.py` 의
    `_kill_tree` 와 같은 길이다. 윈도우는 `taskkill /T` 가 부모를 따라 찾고, POSIX 는 자식이
    이끄는 프로세스 그룹을 끝낸다. `taskkill` 을 띄우지 못했거나 시간을 넘겼어도, 그룹을 끝내지
    못했어도 자식은 끝낸다."""
    if sys.platform == "win32":
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=_KILL_SECONDS,
            )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    process.kill()


def _drain(process: subprocess.Popen[bytes]) -> bytes:
    """끝낸 뒤 남은 출력. 끝내지 못한 프로세스가 출력 파이프를 쥐고 있으면 `_DRAIN_SECONDS` 뒤에
    그만 읽는다."""
    try:
        output, _ = process.communicate(timeout=_DRAIN_SECONDS)
    except subprocess.TimeoutExpired:
        return (
            f"(출력 파이프가 {_DRAIN_SECONDS}초 안에 닫히지 않아 그만 읽었다."
            " 끝내지 못한 프로세스가 남았을 수 있다)\n"
        ).encode()
    return output


class Running:
    """작업 스레드가 기다리는 자식들. 주 스레드가 Ctrl-C 를 받으면 `stop` 으로 모두 끝낸다.
    `stop` 뒤에 띄운 자식은 `add` 가 받지 않아, 띄운 스레드가 곧바로 끝낸다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen[bytes]] = set()
        self._stopped = False

    def add(self, process: subprocess.Popen[bytes]) -> bool:
        with self._lock:
            if self._stopped:
                return False
            self._processes.add(process)
            return True

    def discard(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.discard(process)

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            processes = list(self._processes)
        for process in processes:
            kill_tree(process)


def run_one(check: Check, cwd: Path, running: Running | None = None) -> Outcome:
    """검사 하나를 띄워 끝나거나 `check.timeout` 을 넘길 때까지 기다린다. 명령을 찾거나 띄우지
    못하면 예외 대신 실패다. 넘기면 프로세스 트리를 끝내고 실패다. `running` 을 주면 기다리는
    동안 자식을 거기 두어, 주 스레드가 Ctrl-C 를 받았을 때 끝낼 수 있게 한다."""
    start = time.monotonic()
    executable = shutil.which(check.command[0])
    if executable is None:
        message = f"명령을 찾지 못했다: {check.command[0]}\n".encode()
        return Outcome(check, passed=False, output=message, seconds=time.monotonic() - start)
    try:
        process = subprocess.Popen(
            [executable, *check.command[1:]],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # POSIX 에서 자식이 제 프로세스 그룹을 이끈다
        )
    except OSError as error:
        message = f"명령을 띄우지 못했다: {executable}: {error}\n".encode()
        return Outcome(check, passed=False, output=message, seconds=time.monotonic() - start)
    if running is None:
        return _wait(check, process, start)
    if not running.add(process):
        kill_tree(process)
        _drain(process)
        process.wait()  # 시간 제한 없음: kill_tree 로 끝낸 자식을 거둔다
        message = "멈추는 중이라 띄운 검사를 곧바로 끝냈다\n".encode()
        return Outcome(check, passed=False, output=message, seconds=time.monotonic() - start)
    try:
        return _wait(check, process, start)
    finally:
        running.discard(process)


def _wait(check: Check, process: subprocess.Popen[bytes], start: float) -> Outcome:
    """띄운 검사가 끝나거나 `check.timeout` 을 넘길 때까지 기다린다."""
    try:
        output, _ = process.communicate(timeout=check.timeout)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        output = _drain(process)
        process.wait()  # 시간 제한 없음: kill_tree 로 끝낸 자식을 거둔다
        message = f"{check.timeout:g}초 시간 제한을 넘겼다. 프로세스 트리를 끝냈다\n".encode()
        if output and not output.endswith(b"\n"):
            output += b"\n"
        return Outcome(
            check, passed=False, output=output + message, seconds=time.monotonic() - start
        )
    return Outcome(
        check,
        passed=process.returncode == 0,
        output=output,
        seconds=time.monotonic() - start,
    )


def status_line(check_id: str, status: str) -> bytes:
    return f"{check_id:.<{_NAME_WIDTH}}{status}\n".encode()


def _report(futures: Sequence[Future[Outcome]], out: BinaryIO) -> bool:
    """끝난 차례로 찍는다. 하나라도 실패했으면 참."""
    failed = False
    for future in as_completed(futures):
        outcome = future.result()
        status = "Passed" if outcome.passed else "Failed"
        out.write(status_line(outcome.check.id, f"{status} ({outcome.seconds:.1f}s)"))
        if not outcome.passed:
            failed = True
            out.write(outcome.output)
            if not outcome.output.endswith(b"\n"):
                out.write(b"\n")
        out.flush()
    return failed


def run(checks: Sequence[Check], environ: Mapping[str, str], cwd: Path, out: BinaryIO) -> int:
    """SKIP 밖의 검사를 한꺼번에 띄우고 끝난 차례로 찍는다. 하나라도 실패하면 1.

    environ 은 SKIP 을 읽는 데만 쓴다. 자식은 이 프로세스의 환경을 그대로 물려받는다.
    """
    skips = skipped_ids(environ)
    to_run = [check for check in checks if check.id not in skips]
    for check in checks:
        if check.id in skips:
            out.write(status_line(check.id, "Skipped"))
    failed = False
    running = Running()
    if to_run:
        with ThreadPoolExecutor(max_workers=len(to_run)) as pool:
            # 이 try 는 with 안에 있어야 한다. 밖이면 with 를 나가며 남은 검사를 끝까지 기다린다.
            # 기다리며 찍는 동안 어디서 Ctrl-C 가 나도 받도록 _report 를 통째로 감싼다
            try:
                futures = [pool.submit(run_one, check, cwd, running) for check in to_run]
                failed = _report(futures, out)
            except BaseException:
                # POSIX 에서 자식은 제 세션을 이끌어 터미널의 Ctrl-C 를 받지 못한다
                running.stop()
                raise
    out.flush()
    return 1 if failed else 0


def main() -> int:
    return run(CHECKS, os.environ, ROOT, sys.stdout.buffer)


if __name__ == "__main__":
    sys.exit(main())
