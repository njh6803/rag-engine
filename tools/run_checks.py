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

테스트 데이터베이스(core 01). core 부터 pytest 가 PostgreSQL(pgvector)을 쓴다. pytest 를 돌리는
러너는 검사를 띄우기 전에 `RAG_TEST_DATABASE_URL`(없으면 `compose.test.yml` 의 기본 주소)의 서버가
답하는지 본다. 안 보이고 그 주소가 compose 가 여는 곳(이 PC 의 55432 포트)이면
`docker compose -f compose.test.yml up -d --wait` 로 띄우고 준비 신호를 기다린 뒤 그 주소를 자식에게
넘긴다. 그 밖의 주소가 안 보이는 것은 compose 가 고치지 못하므로 띄우지 않고 그렇다고 알린다. 이
준비의 결과는 `test-db` 줄로 찍고, 실패해도 나머지 검사는 돌려 한 번에 본다(이어서 pytest 는
데이터베이스 시험에서 세션 픽스처의 같은 안내로 빨개진다). `SKIP=pytest` 면 보지 않는다.
- 띄운 컨테이너는 내리지 않고 남긴다. 커밋마다 내리고 올리면 매번 시간이 든다(손으로 봤다: 내린 뒤
  `prepare_test_database` 가 다시 올리는 데 5.6~6.8초, 세 번, 커밋하지 않은 스크래치 스크립트).
  컨테이너 이름이 프로젝트 이름(`rag-engine-test`)으로 고정이라 워크트리와 세션이 서버 하나를 함께
  쓴다. 데이터는 tmpfs 라 내리거나 Docker 를 다시 시작하면 사라진다. 내리려면
  `docker compose -f compose.test.yml down`. 서버 하나를 여럿이 쓰므로 템플릿 데이터베이스 같은
  이름이 있는 것은 세션마다 이름이 달라야 한다(core 03).
- 서버가 답하는지는 TCP 연결이 아니라 PostgreSQL 의 SSL 요청(8바이트)에 한 글자로 답하는지로 본다.
  Docker 의 포트 전달은 안쪽 서버가 준비되기 전에도 연결을 받는다.
- 문서만 바뀐 커밋에서도 pytest 를 건너뛰지 않는다(core 01 결정). pytest 에 문서를 읽는 저장소 상태
  시험이 있어(`tests/test_plan_status.py`, 문서 표·ADR 인용·티켓 검사의 시험) 문서만 고친 커밋이 그
  시험을 깰 수 있고, 건너뛰는 판정이 부분 커밋의 색인(`GIT_INDEX_FILE`)과 파일 분류를 새로 따져야
  한다. CI 는 어차피 전부 돌아 로컬에서 건너뛰면 빨강이 PR 로 늦게 올 뿐이다. 대가는 Docker 가 없고
  닿는 PostgreSQL 도 없는 세션이 커밋을 못 한다는 것이고, next-session 결정표가 그 갈래를 적는다.
  `SKIP=pytest` 우회는 막지 않는다. 판정은 CI 의 `verify` 가 하고, 이 우회로 난 사고를 일지와 대기열
  항목에서 찾지 못했으며(`SKIP=pytest` 를 grep 했다) 막는 훅은 교정 루프(CLAUDE.md)의 문턱 전이다.
- 테스트 데이터베이스 준비가 못 보는 것. (1) SSL 요청에 답한 서버가 `RAG_TEST_DATABASE_URL` 의
  역할과 데이터베이스까지 맞는지는 모른다. 55432 포트를 다른 PostgreSQL 이 쓰고 있으면 compose 를
  띄우지 않고, 이어서 시험이 인증 오류로 빨개질 것으로 어림한다. (2) 호스트 이름
  풀이(`getaddrinfo`)는 소켓의 시간 제한이 막지 않는다는 것을 코드를 읽어 알 뿐 재지 않았다. 안
  풀리는 이름은 러너를 오래 붙잡을 수 있다. (3) 기다리는 도중 Ctrl-C 가 띄우는 docker 를 끝내는지
  는 POSIX 에서만 코드를 읽어 안다(자식이 제 세션을 이끌어 Ctrl-C 를 받지 않는다). Windows 에서는
  재지 않았고, 같은 콘솔의 docker 가 Ctrl-C 를 받아 띄우기가 중단될 수 있다. (4) 러너 둘이 동시에
  `up -d --wait` 를 치는 경우는 테스트로 고정하지 않았다. 리뷰 서브에이전트가 복사본 compose 로 한
  번 본 것(둘 다 종료 0)이 전부다. (5) 서버가 답하는지만 보므로 `localhost` 와 `127.0.0.1` 은 같은
  곳으로 본다. IPv6 만 듣는 서버는 이 판정에서 다르게 읽힐 수 있고 재지 않았다. (6) 주소의 쿼리
  (`?host=`, `?port=`, `hostaddr`)가 접속처를 덮어쓰는 libpq 의 규칙, 쉼표로 이은 다중 호스트,
  유닉스 소켓 주소는 읽지 않는다. 앞의 둘은 권한부의 호스트와 포트를 접속처로 읽고(`urlsplit` 의
  동작을 돌려 보지는 않았다), 뒤의 둘은 "접속 주소 모양이 아니다"로 거절한다. (7) 프로젝트 이름이
  고정이라 `compose.test.yml` 을 바꾼 브랜치(이미지 판, command, 환경)가 `up -d --wait` 를 치면
  compose 가 컨테이너를 다시 만들어, 다른 워크트리에서 돌던 시험의 연결과 tmpfs 의 데이터가 사라질
  수 있다. 재지 않았다. (1)(2)(3)(4)(6)(7)은 테스트로 고정하지 않았다. 55432 를 차지하는 가짜 서버나
  Docker 의 재생성을 시험에서 다루려면 이 PC 의 실제 서버와 부딪히거나 Docker 가 필요하다.

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
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
_NAME_WIDTH = 40
# agent-os pre-commit 의 관측 최대(xdist 전 한 프로세스 pytest 1,048초)의 네 배 남짓
CHECK_TIMEOUT_SECONDS = 4200
_KILL_SECONDS = 30  # 윈도우의 `taskkill` 을 기다리는 시간
_DRAIN_SECONDS = 10  # 끝낸 뒤 남은 출력을 기다리는 시간

TEST_DATABASE_ENV = "RAG_TEST_DATABASE_URL"
# compose.test.yml 이 띄우는 서버의 주소. 파일과 맞는지는 tests/tools/test_run_checks_database.py 가
# 본다
TEST_DATABASE_URL = "postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test"
COMPOSE_FILE = "compose.test.yml"
# 첫 실행은 이미지를 받는다(설계 일지는 164MB 로 어림했다)
_COMPOSE_UP_SECONDS = 600
_PROBE_SECONDS = 2.0
# PostgreSQL 의 SSLRequest: 길이 8, 요청 코드 80877103. 서버는 `S` 나 `N` 한 글자로 답한다
_SSL_REQUEST = bytes.fromhex("0000000804d2162f")


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


class DatabaseNotReady(Exception):
    """테스트 서버를 준비하지 못했다. 메시지는 사용자에게 그대로 보이는 한 줄이다."""


def server_answers(host: str, port: int) -> bool:
    """host:port 의 서버가 PostgreSQL 프로토콜로 답하는지. 연결만 되는 것은 답이 아니다(Docker 의
    포트 전달은 안쪽 서버가 없어도 연결을 받고 끊는다)."""
    try:
        with socket.create_connection((host, port), timeout=_PROBE_SECONDS) as connection:
            connection.sendall(_SSL_REQUEST)
            return connection.recv(1) in (b"S", b"N")
    except (OSError, UnicodeError):
        # 빈 레이블이나 64자를 넘는 레이블이 든 호스트 이름은 IDNA 인코딩이 OSError 가 아닌
        # UnicodeError 로 거절한다.
        return False


def _address(url: str) -> tuple[str, int] | None:
    """접속 주소의 호스트와 포트. 모양이 맞지 않으면 None. 비밀번호가 들 수 있어 호출하는 쪽은 주소
    원문을 메시지에 싣지 않는다(원칙 V)."""
    try:
        parts = urlsplit(url)
        port = 5432 if parts.port is None else parts.port
    except ValueError:
        return None
    if parts.scheme not in ("postgresql", "postgres") or not parts.hostname:
        return None
    return parts.hostname, port


def _opens_compose_server(host: str, port: int) -> bool:
    """compose 가 여는 서버(이 PC 의 55432 포트)를 가리키는 주소인지. 끝 슬래시, `localhost`,
    데이터베이스 이름은 달라도 같은 서버다."""
    compose = _address(TEST_DATABASE_URL)
    return compose is not None and port == compose[1] and host in ("127.0.0.1", "localhost")


def _how_to_start() -> str:
    return (
        "테스트 PostgreSQL 은 검사 러너(uv run python tools/run_checks.py)가 띄우거나"
        f" `docker compose -f {COMPOSE_FILE} up -d --wait` 로 띄우고,"
        f" {TEST_DATABASE_ENV} 는 {TEST_DATABASE_URL} 로 둔다"
    )


def _bad_url_message() -> str:
    return (
        f"{TEST_DATABASE_ENV} 가 postgresql:// 로 시작하고 호스트가 든 접속 주소가 아니다"
        " (값에 비밀번호가 들 수 있어 적지 않는다)"
    )


def _not_answering(host: str, port: int) -> str:
    return f"{TEST_DATABASE_ENV} 가 가리키는 {host}:{port} 가 답하지 않는다."


def database_problem(environ: Mapping[str, str]) -> str | None:
    """데이터베이스를 쓰는 시험이 시작해도 되는지. 안 되면 띄우는 길을 알리는 한 줄을 돌려준다.

    세션 픽스처 `database_url`(tests/conftest.py)이 첫 데이터베이스 시험 전에 부른다. 시험이 skip 이
    아니라 실패하게 하는 판정이다(원칙 I). 띄우지는 않는다. 손으로 친 pytest 에서 서버를 준비하는
    것은 개발자의 몫이다.
    """
    url = environ.get(TEST_DATABASE_ENV)
    if not url:
        return f"{TEST_DATABASE_ENV} 가 없다. {_how_to_start()}"
    address = _address(url)
    if address is None:
        return _bad_url_message()
    if server_answers(*address):
        return None
    return f"{_not_answering(*address)} {_how_to_start()}"


def compose_up(cwd: Path = ROOT) -> None:
    """`compose.test.yml` 을 띄우고 준비 신호까지 기다린다. 못 하면 이유 한 줄로 `DatabaseNotReady`.

    띄우는 명령은 검사와 같은 `run_one` 이 돌려, 시간 제한을 넘기면 프로세스 트리를 끝내고 출력
    파이프를 붙잡고 기다리지 않는다(docker 는 compose 플러그인을 자식으로 띄운다).
    """
    if shutil.which("docker") is None:
        raise DatabaseNotReady("docker 명령을 찾지 못했다. Docker 를 설치하고 켠 뒤 다시 친다")
    command = ("docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--wait")
    outcome = run_one(Check("test-db-up", command, timeout=_COMPOSE_UP_SECONDS), cwd)
    if outcome.passed:
        return
    lines = [line.strip() for line in outcome.output.decode(errors="replace").splitlines()]
    last = next((line for line in reversed(lines) if line), "(출력 없음)")
    raise DatabaseNotReady(
        f"`docker compose -f {COMPOSE_FILE} up -d --wait` 가 실패했다. Docker 가 켜져 있는지,"
        f" 포트를 다른 것이 쓰지 않는지 본다: {last}"
    )


def prepare_test_database(
    environ: Mapping[str, str],
    start_server: Callable[[], None] = compose_up,
    is_up: Callable[[str, int], bool] = server_answers,
) -> str:
    """pytest 를 돌리기 전에 테스트 서버가 답하게 하고, 시험이 쓸 접속 주소를 돌려준다. 못 하면 이유
    한 줄로 `DatabaseNotReady`(core 01, 모듈 독스트링의 테스트 데이터베이스 절).

    주소는 environ 의 값이고 없으면 compose 의 기본 주소다. 서버가 답하면 그대로 쓴다. 안 답하는데
    compose 가 여는 곳이면 띄운다. 그 밖의 주소는 띄우지 않는다. 남의 서버를 compose 가 대신하지
    못한다.
    """
    url = environ.get(TEST_DATABASE_ENV) or TEST_DATABASE_URL
    address = _address(url)
    if address is None:
        raise DatabaseNotReady(_bad_url_message())
    if is_up(*address):
        return url
    if not _opens_compose_server(*address):
        raise DatabaseNotReady(
            f"{_not_answering(*address)} 그 서버를 켜거나, 값을 지우면"
            f" 러너가 {COMPOSE_FILE} 로 띄운다"
        )
    start_server()
    if not is_up(*address):
        raise DatabaseNotReady(
            f"{COMPOSE_FILE} 를 띄웠는데도 {address[0]}:{address[1]} 가 답하지 않는다."
            f" `docker compose -f {COMPOSE_FILE} logs` 를 본다"
        )
    return url


def main() -> int:
    out = sys.stdout.buffer
    prepared = True
    if "pytest" not in skipped_ids(os.environ):
        start = time.monotonic()
        problem = ""
        try:
            os.environ[TEST_DATABASE_ENV] = prepare_test_database(os.environ)
        except DatabaseNotReady as error:
            prepared = False
            problem = f"{error}\n"
        status = "Passed" if prepared else "Failed"
        out.write(status_line("test-db", f"{status} ({time.monotonic() - start:.1f}s)"))
        out.write(problem.encode())
        out.flush()
    code = run(CHECKS, os.environ, ROOT, out)
    return code if prepared else 1


if __name__ == "__main__":
    sys.exit(main())
