"""tools/run_checks.py — 검사를 함께 띄우고 결과를 모으는 러너(ADR 0005 이력 2026-10-07).

함께 띄우는지는 시간으로 재지 않는다. 두 검사가 서로의 표지 파일을 기다리게 해, 하나씩 돌면 앞의
것이 기다리다 실패하고 함께 돌아야만 둘 다 통과한다. 배관은 SKIP 으로 모든 검사를 건너뛴 CLI 를
실제로 불러 본다. 진짜 검사를 띄우면 이 테스트가 pytest 를 다시 띄워 돌고 돌아서, CLI 테스트는
PATH 를 비워 둔다.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tools.run_checks import (
    CHECKS,
    Check,
    Running,
    pyright_checks,
    pytest_workers,
    run,
    run_one,
    skipped_ids,
)

ROOT = Path(__file__).resolve().parents[2]


def _python(check_id: str, code: str) -> Check:
    return Check(check_id, (sys.executable, "-c", code))


def _waits_for(mine: Path, other: Path) -> str:
    return (
        "import pathlib, sys, time\n"
        f"pathlib.Path({str(mine)!r}).touch()\n"
        "deadline = time.monotonic() + 20\n"
        "while time.monotonic() < deadline:\n"
        f"    if pathlib.Path({str(other)!r}).exists():\n"
        "        sys.exit(0)\n"
        "    time.sleep(0.05)\n"
        "sys.exit(1)\n"
    )


def test_SKIP_을_pre_commit_처럼_쉼표로_나누고_공백을_걷는다() -> None:
    assert skipped_ids({"SKIP": " pytest, zizmor ,,"}) == {"pytest", "zizmor"}
    assert skipped_ids({}) == frozenset()


@pytest.mark.parametrize(
    ("cpu_count", "workers"),
    [(16, 8), (15, 7), (2, 1), (1, 1), (None, 1)],
)
def test_pytest_프로세스_수는_논리_CPU_의_절반이고_1_아래로_내려가지_않는다(
    cpu_count: int | None, workers: int
) -> None:
    """ADR 0035. `os.cpu_count()` 는 값을 알아내지 못하면 None 이다."""
    assert pytest_workers(cpu_count) == workers


def test_러너의_pytest_는_계산한_프로세스_수로_나눠_돈다() -> None:
    """`-n` 은 러너에만 둔다(손으로 치는 pytest, mutate, CI 는 한 프로세스로 둔다는 결정, ADR
    0035)."""
    (pytest_check,) = [check for check in CHECKS if check.id == "pytest"]
    command = pytest_check.command

    assert command[:4] == ("uv", "run", "pytest", "-q")
    assert "-n" in command
    assert command[command.index("-n") + 1] == str(pytest_workers(os.cpu_count()))


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_리눅스가_아닌_곳의_pyright_는_리눅스_플랫폼으로_한_번_더_돈다(platform: str) -> None:
    """이 PC(윈도)의 pyright 가 초록인 시험 파일을 리눅스 CI 의 pyright 가 빨갛게
    냈다(대기열 403)."""
    checks = pyright_checks(platform)

    assert [check.id for check in checks] == ["pyright", "pyright-linux"]
    assert checks[0].command == ("uv", "run", "pyright")
    assert checks[1].command == ("uv", "run", "pyright", "--pythonplatform", "Linux")


def test_리눅스의_pyright_는_한_번만_돈다() -> None:
    """리눅스에서는 두 검사가 같아 한 번 더 돌 몫이 없다."""
    assert [check.id for check in pyright_checks("linux")] == ["pyright"]


def test_러너의_pyright_는_이_플랫폼의_검사다() -> None:
    expected = [check.id for check in pyright_checks(sys.platform)]

    assert [check.id for check in CHECKS if check.id.startswith("pyright")] == expected


def test_검사를_함께_띄운다(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    checks = (_python("a", _waits_for(a, b)), _python("b", _waits_for(b, a)))
    out = io.BytesIO()

    code = run(checks, {}, tmp_path, out)

    assert code == 0, out.getvalue().decode()


def test_실패한_검사의_출력만_찍고_1로_끝난다(tmp_path: Path) -> None:
    checks = (
        _python("loud", "import sys; print('boom'); sys.exit(3)"),
        _python("calm", "print('quiet')"),
    )
    out = io.BytesIO()

    code = run(checks, {}, tmp_path, out)

    text = out.getvalue().decode()
    assert code == 1
    assert "boom" in text
    assert "quiet" not in text
    assert any(line.startswith("loud") and "Failed" in line for line in text.splitlines())
    assert any(line.startswith("calm") and "Passed" in line for line in text.splitlines())


def test_SKIP_에_든_검사는_띄우지_않는다(tmp_path: Path) -> None:
    mark = tmp_path / "ran"
    checks = (_python("pytest", f"import pathlib; pathlib.Path({str(mark)!r}).touch()"),)
    out = io.BytesIO()

    code = run(checks, {"SKIP": "pytest"}, tmp_path, out)

    assert code == 0
    assert not mark.exists()
    assert "Skipped" in out.getvalue().decode()


def test_명령을_찾지_못하면_실패로_알린다(tmp_path: Path) -> None:
    checks = (Check("ghost", ("agent-os-no-such-command",)),)
    out = io.BytesIO()

    code = run(checks, {}, tmp_path, out)

    assert code == 1
    assert "agent-os-no-such-command" in out.getvalue().decode()


def test_띄우지_못한_명령도_실패로_알린다(tmp_path: Path) -> None:
    """찾았지만 띄울 수 없는 파일(실행 형식이 아니다)도 traceback 이 아니라 실패 한 줄이다."""
    program = tmp_path / "not-a-program"
    program.write_bytes(b"\x00\x01 not an executable")
    program.chmod(0o755)
    out = io.BytesIO()

    code = run((Check("broken", (str(program),)),), {}, tmp_path, out)

    assert code == 1
    assert "not-a-program" in out.getvalue().decode()


def _stops_growing(path: Path, within: float) -> bool:
    """`within` 초 안에 파일이 1초 동안 자라지 않으면 참. 끝내기가 늦은 것과 끝내지 못한 것을
    가르려고, 한 번만 견주지 않고 기한까지 거듭 견준다(대기열 306)."""
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        before = path.stat().st_size
        time.sleep(1)
        if path.stat().st_size == before:
            return True
    return False


def test_시간_제한을_넘긴_검사는_손자까지_끝내고_실패로_알린다(tmp_path: Path) -> None:
    """pytest 작업 프로세스 여덟이 약 11시간 남아 커밋을 붙잡았다(대기열 333). 검사는 손자를
    띄우고 120초 잔다. 손자는 검사의 출력 파이프를 물려받은 채 0.1초마다 표지 파일을 키운다.

    제한(5초)은 부모와 손자가 뜨는 시간보다, 경과의 상한(60초)은 제한과 끝내기를 홀로 잰 시간보다
    한참 넉넉하게 둔다(tests.md).
    """
    beat = tmp_path / "beat"
    grandchild = (
        "import pathlib, time\n"
        "while True:\n"
        f"    with pathlib.Path({str(beat)!r}).open('a') as f:\n"
        "        f.write('.')\n"
        "    time.sleep(0.1)\n"
    )
    parent = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}])\n"
        "time.sleep(120)\n"
    )
    check = Check("stuck", (sys.executable, "-c", parent), timeout=5)
    out = io.BytesIO()
    start = time.monotonic()

    code = run((check,), {}, tmp_path, out)

    elapsed = time.monotonic() - start
    text = out.getvalue().decode()
    assert code == 1
    assert "5초 시간 제한을 넘겼다" in text
    assert elapsed < 60, f"돌아오기까지 {elapsed:.1f}초"
    assert beat.exists(), "손자가 뜨기 전에 끊었다. 손자를 끝냈는지 재지 못한다"
    assert _stops_growing(beat, within=15), "시간 제한 뒤에도 손자가 돈다"


class _InterruptingOut(io.BytesIO):
    """첫 줄을 쓰는 순간 Ctrl-C 처럼 `KeyboardInterrupt` 를 던지는 출력."""

    def write(self, data: object, /) -> int:
        raise KeyboardInterrupt


def test_기다리는_도중_Ctrl_C_가_나면_남은_검사의_손자까지_끝낸다(tmp_path: Path) -> None:
    """POSIX 에서 자식은 제 세션을 이끌어 터미널의 Ctrl-C 를 받지 못한다. 그래서 러너가 끝낸다.

    빠른 검사는 손자의 표지 파일이 생긴 뒤에 끝나고, 그 결과를 찍는 순간 Ctrl-C 가 난다. 그래서
    손자가 떴는지를 시간에 기대지 않고 안다. 멈춘 검사의 제한(45초)은 러너가 끝내지 않을 때도
    시험이 그때 돌아와 경과의 상한(30초)으로 빨개지게 하려는 것이다. 30초는 홀로 돈 이 시험의
    경과보다 한참 넉넉하다(tests.md).
    """
    beat = tmp_path / "beat"
    grandchild = (
        "import pathlib, time\n"
        "while True:\n"
        f"    with pathlib.Path({str(beat)!r}).open('a') as f:\n"
        "        f.write('.')\n"
        "    time.sleep(0.1)\n"
    )
    stuck = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}])\n"
        "time.sleep(120)\n"
    )
    waits = (
        "import pathlib, time\n"
        f"while not pathlib.Path({str(beat)!r}).exists():\n"
        "    time.sleep(0.1)\n"
    )
    checks = (
        Check("stuck", (sys.executable, "-c", stuck), timeout=45),
        Check("quick", (sys.executable, "-c", waits)),
    )
    start = time.monotonic()

    with pytest.raises(KeyboardInterrupt):
        run(checks, {}, tmp_path, _InterruptingOut())

    elapsed = time.monotonic() - start
    assert elapsed < 30, f"Ctrl-C 뒤 돌아오기까지 {elapsed:.1f}초"
    assert _stops_growing(beat, within=15), "Ctrl-C 뒤에도 손자가 돈다"


def test_멈춘_뒤에_띄운_검사는_곧바로_끝내고_실패로_알린다(tmp_path: Path) -> None:
    """Ctrl-C 로 `stop` 한 뒤 띄워진 검사는 `add` 가 받지 않아 띄운 스레드가 끝낸다. 남은 출력은
    `_drain` 으로 읽어, 트리를 떠난 손자가 파이프를 쥐어도 기다림이 끝난다. 그 손자는 띄운 직후
    끝내는 순서라 시험으로 만들지 못해, 여기서는 그 갈래가 120초 자는 검사를 곧바로 끝내는지만 본다.
    경과의 상한(30초)은 홀로 돈 경과보다 한참 넉넉하다(tests.md)."""
    running = Running()
    running.stop()
    check = Check("late", (sys.executable, "-c", "import time; time.sleep(120)"))
    start = time.monotonic()

    outcome = run_one(check, tmp_path, running)

    elapsed = time.monotonic() - start
    assert not outcome.passed
    assert "멈추는 중이라 띄운 검사를 곧바로 끝냈다" in outcome.output.decode()
    assert elapsed < 30, f"돌아오기까지 {elapsed:.1f}초"


def test_검사의_시간_제한은_관측_최대의_네_배_이상이다() -> None:
    """관측 최대는 agent-os 에서 xdist 전 한 프로세스 pre-commit pytest 의 1,048초다(대기열 333).
    그보다 짧으면 부하 아래의 정상 실행을 멈춘 검사로 끊는다."""
    assert CHECKS, "검사 목록이 비었다"
    assert all(check.timeout >= 4 * 1048 for check in CHECKS)


def _cli(path_dir: Path, skips: list[str]) -> subprocess.CompletedProcess[str]:
    """CLI 를 PATH 를 비운 채 부른다.

    PATH 가 빈 디렉터리라 SKIP 이 깨져도 uv 를 찾지 못해 곧바로 끝난다. 그러지 않으면 러너가
    띄운 pytest 가 이 테스트를 다시 불러 러너를 또 띄운다(변이 표를 처음 돌릴 때 그렇게 돌았다).
    """
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_checks.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PATH": str(path_dir), "SKIP": ",".join(skips)},
        check=False,
    )


def test_CLI_진입점이_SKIP_으로_모든_검사를_건너뛴다(tmp_path: Path) -> None:
    """main 의 배관(검사 목록, SKIP)을 진짜 검사를 띄우지 않고 지난다."""
    process = _cli(tmp_path, [check.id for check in CHECKS])

    assert process.returncode == 0, process.stdout + process.stderr
    assert process.stdout.count("Skipped") == len(CHECKS)


def test_CLI_진입점이_알려진_빨강을_종료_코드와_출력으로_낸다(tmp_path: Path) -> None:
    """검사 하나만 남기고 PATH 를 비우면 그 명령을 찾지 못한다. 종료 코드가 main 밖으로 나가는지
    본다."""
    target = CHECKS[-1]
    process = _cli(tmp_path, [check.id for check in CHECKS if check is not target])

    assert process.returncode == 1, process.stdout + process.stderr
    assert target.command[0] in process.stdout
    assert any(
        line.startswith(target.id) and "Failed" in line for line in process.stdout.splitlines()
    )


def test_이_저장소의_pre_commit_은_러너의_검사를_따로_등록하지_않는다() -> None:
    """같은 검사를 러너와 훅에 함께 두면 커밋마다 두 번 돈다(대기열 118과 같은 낭비).

    글자 그대로의 명령과 같은 id 만 본다. 옵션을 바꿔 적은 명령(`uv run pytest` 처럼 `-q` 를 뺀
    것)은 못 본다.
    """
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    lines = [line.strip() for line in config.splitlines()]
    entries = {line.removeprefix("entry:").strip() for line in lines if line.startswith("entry:")}
    hook_ids = {line.removeprefix("- id:").strip() for line in lines if line.startswith("- id:")}

    assert "uv run python tools/run_checks.py" in entries
    assert CHECKS
    for check in CHECKS:
        assert " ".join(check.command) not in entries, check.id
        assert check.id not in hook_ids, check.id
