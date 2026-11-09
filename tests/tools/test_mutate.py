"""tools/mutate.py 의 변이 도구.

러너는 가짜다. 가짜 러너가 불리는 순간의 파일 바이트를 기록해, 변이가 든 동안과 끝난 뒤를 따로
본다. 명령을 하위 프로세스로 부르는 실제 러너는 실제 실행으로 확인한다(`.claude/rules/tests.md`).
판정의 입력은 2026-10-01 에 본 실제 출력의 모양을 따른다(pytest 9, Vitest 5.0.2, tsc 5.9.3,
Playwright 의 `list` 리포터, 일지 2026-10-01-01). 색 코드를 넣거나 문구를 바꾼 사례는 그 모양을
비튼 것이다.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from tools.mutate import (
    MARKER_PREFIX,
    RESTORE_WAITS,
    ROOT,
    CommandResult,
    JudgeName,
    Judging,
    RestoreError,
    SpecError,
    changed_names,
    check,
    judge,
    load_spec,
    main,
    measure,
    read_spec,
    run_command,
    select,
)
from tools.run_hooks import hook_environment

from tools import mutate

_초록 = CommandResult(0, "1 passed in 0.01s\n")
_빨강 = CommandResult(1, "FAILED tests/test_x.py::test_x - AssertionError\n1 failed in 0.01s\n")

type 러너 = Callable[[Sequence[str], Path, int], CommandResult]


def _파일을_둔다(root: Path, 상대_경로: str, 내용: bytes) -> Path:
    path = root / 상대_경로
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(내용)
    return path


def _변이_파일(*, old: str, new: str, expect: str = "red", file: str = "src/m.py") -> str:
    return f"""
[[mutation]]
name = "하나"
tests = ["tests/test_x.py"]
expect = "{expect}"

[[mutation.edit]]
file = "{file}"
old = '''{old}'''
new = '''{new}'''
"""


_VITEST_러너 = """
[runner.vitest]
command = ["pnpm", "exec", "vitest", "run"]
cwd = "web"
judge = "vitest"
"""


def _vitest_변이(*, name: str = "하나", tests: str = '["a.test.ts"]', 줄: str = "") -> str:
    return f"""
[[mutation]]
name = "{name}"
runner = "vitest"
tests = {tests}
expect = "red"
{줄}
[[mutation.edit]]
file = "web/m.ts"
old = 'x = 1'
new = 'x = 2'
"""


def test_변이가_든_동안_러너는_바뀐_바이트를_보고_끝나면_원래_바이트로_돌아온다(
    tmp_path: Path,
) -> None:
    """CRLF 와 UTF-8 이 아닌 바이트까지 그대로다.

    텍스트로 되돌린 변이 스크립트가 줄 끝을 CRLF 로 바꿔 두 번 남겼다(대기열 29).
    """
    원래 = b"def f():\r\n    return 1\r\n# \xff\n"
    path = _파일을_둔다(tmp_path, "src/m.py", 원래)
    본_것: list[bytes] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        본_것.append(path.read_bytes())
        return _빨강 if b"return 2" in path.read_bytes() else _초록

    code = measure(
        load_spec(_변이_파일(old="return 1", new="return 2")),
        root=tmp_path,
        runner=러너,
        out=lambda _: None,
    )

    assert 본_것 == [원래, b"def f():\r\n    return 2\r\n# \xff\n"]
    assert path.read_bytes() == 원래
    assert code == 0


def test_빨강을_기대한_pytest_변이만_첫_실패에서_멈춘다(tmp_path: Path) -> None:
    """빨강은 실패 하나로 정해져 나머지 시험은 시간만 쓴다(대기열 231, 측정은 도구의 독스트링).
    기준선과 초록을 기대한 변이는 모든 시험이 지나야 해 끝까지 돈다."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\ny = 1\n")
    변이 = _변이_파일(old="x = 1", new="x = 2") + _변이_파일(
        old="y = 1", new="y = 2", expect="green"
    ).replace('name = "하나"', 'name = "둘"')
    받은: list[list[str]] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        받은.append(list(argv))
        return _빨강 if "-x" in argv else _초록

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert code == 0
    assert [argv[-2:] for argv in 받은] == [
        ["no:cacheprovider", "tests/test_x.py"],
        ["tests/test_x.py", "-x"],
        ["no:cacheprovider", "tests/test_x.py"],
    ]


@pytest.mark.parametrize(
    "러너_표",
    [
        _VITEST_러너,
        '[runner.vitest]\ncommand = ["uv", "run", "python", "tools/run_hooks.py"]\n'
        'judge = "pytest"\n',
    ],
    ids=["vitest", "pytest_판정을_빌린_명령"],
)
def test_표의_러너는_첫_실패에서_멈추는_인자를_받지_않는다(tmp_path: Path, 러너_표: str) -> None:
    """`-x` 는 pytest 의 인자다. vitest 에 넘기면 모르는 선택이고, pytest 판정을 빌린 명령(훅
    러너)도 pytest 가 아니다."""
    path = _파일을_둔다(tmp_path, "web/m.ts", b"x = 1\n")
    _파일을_둔다(tmp_path, "tools/run_hooks.py", b"")
    받은: list[list[str]] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        받은.append(list(argv))
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, "      Tests  1 failed (1)\n1 failed\n")
        return CommandResult(0, "      Tests  1 passed (1)\n1 passed\n")

    measure(load_spec(러너_표 + _vitest_변이()), root=tmp_path, runner=러너, out=lambda _: None)

    assert len(받은) == 2
    assert all("-x" not in argv for argv in 받은)


_뒤가_다른_시험 = (
    b"import time\n"
    b"from pathlib import Path\n"
    b"V = Path(__file__).with_name('v.txt').read_text()\n"
    b"def test_a(): assert V == '1'\n"
    b"def test_b():\n"
    b"    if V != '1':\n"
    b"        Path(__file__).with_name('b-ran').touch()\n"
    b"        print('MARKER' + '-B')\n"  # 표지가 원문에 글자 그대로 있으면 메아리다(대기열 502)
    b"        time.sleep(60)\n"
    b"    assert V == '1'\n"
)


def test_못_보는_것_첫_실패에서_멈춘_변이는_뒤의_시험만_찍는_표지를_놓쳐_어긋난다(
    tmp_path: Path,
) -> None:
    """뒤의 시험(test_b)만 찍는 표지는 `-x` 가 그 시험을 돌리지 않아 없다. 실제 pytest 로 본다."""
    _파일을_둔다(tmp_path, "v.txt", b"1")
    _파일을_둔다(tmp_path, "test_two.py", _뒤가_다른_시험)
    변이 = (
        _변이_파일(old="1", new="2", file="v.txt")
        .replace("tests/test_x.py", "test_two.py")
        .replace('expect = "red"', 'expect = "red"\nexpect_output = ["MARKER-B"]')
    )
    줄: list[str] = []

    code = measure(load_spec(변이), root=tmp_path, runner=run_command, out=줄.append)

    assert code == 1
    assert any("표지 없음" in 한줄 and "MARKER-B" in 한줄 for 한줄 in 줄)


def test_못_보는_것_뒤의_시험이_걸려도_첫_실패에서_멈춰_빨강이다(tmp_path: Path) -> None:
    """끝까지 돌았다면 test_b 가 60초를 자 시간 제한(40초)을 넘긴 오류였을 변이다. 실제 pytest 로
    본다. 멈춘 것은 test_b 가 자기 전에 남기는 파일이 없는 것으로 본다. 첫 판은 걸린 시간이
    20초 미만인지 봤는데, 그 안에 기준선과 변이로 pytest 를 두 번 띄우는 시간까지 들어 pytest 두
    벌을 동시에 돌린 부하 아래에서 20.3초와 21.6초로 빨갰다(ADR 0035의 부딪힘. 한 프로세스로는
    4.56초, xdist 8개 홀로는 10.60초였다. 원인이 부하의 지연이라는 것은 어림이다). 시간 제한은
    기동이 늘어도 남게 40초로 두되, test_b 의 60초 잠보다 짧아야 `-x` 가 빠진 변이가 시간 제한에
    걸려 빨개진다."""
    _파일을_둔다(tmp_path, "v.txt", b"1")
    _파일을_둔다(tmp_path, "test_two.py", _뒤가_다른_시험)
    변이 = (
        _변이_파일(old="1", new="2", file="v.txt")
        .replace("tests/test_x.py", "test_two.py")
        .replace('expect = "red"', 'expect = "red"\ntimeout = 40')
    )

    code = measure(load_spec(변이), root=tmp_path, runner=run_command, out=lambda _: None)

    assert code == 0
    assert not (tmp_path / "b-ran").exists()


def test_못_보는_것_exit_판정은_잡히지_않은_예외의_1_도_빨강이다() -> None:
    """node 는 잡히지 않은 예외에도 1 로 끝난다. 변이가 입력을 깨 검사기가 던진 것도 빨강이라,
    까닭은 표지가 가른다."""
    던짐 = CommandResult(1, "SyntaxError: Unexpected token } in JSON at position 10\n")

    assert judge(Judging("exit", red_exit=1), 던짐).outcome == "red"


def test_못_보는_것_첫_실패에서_멈춘_변이는_빨간_시험을_하나만_보인다(tmp_path: Path) -> None:
    """`-x` 뒤의 시험은 돌지 않아, 그 변이가 빨갛게 할 시험이 몇인지 출력에 남지 않는다. 실제
    pytest 로 본다.

    rag-engine 의 pytest-asyncio(1.4.1.post1)는 설정 없는 폴더에서
    `asyncio_default_fixture_loop_scope` 가 비었다는 경고를 stderr 에 낸다. 도구는 stdout 뒤에
    stderr 를 이어 마지막 줄을 요약으로 읽어, 그 경고가 pytest 의 요약 줄을 가린다. 이 저장소의
    루트는 `pyproject.toml` 이 그 값을 정해 경고가 없으므로, 시험 폴더에도 같은 값을 둔다. agent-os
    에서 이 시험이 초록이었던 것은 그 저장소의 1.4.0 이 이 경고를 내지 않아서라고 어림한다(재지
    않았다)."""
    _파일을_둔다(
        tmp_path, "pytest.ini", b"[pytest]\nasyncio_default_fixture_loop_scope = function\n"
    )
    _파일을_둔다(tmp_path, "v.txt", b"1")
    _파일을_둔다(
        tmp_path,
        "test_two.py",
        b"from pathlib import Path\n"
        b"V = Path(__file__).with_name('v.txt').read_text()\n"
        b"def test_a(): assert V == '1'\n"
        b"def test_b(): assert V == '1'\n",
    )
    변이 = _변이_파일(old="1", new="2", file="v.txt").replace("tests/test_x.py", "test_two.py")
    줄: list[str] = []

    code = measure(load_spec(변이), root=tmp_path, runner=run_command, out=줄.append)

    assert code == 0
    assert any("1 failed" in 한줄 for 한줄 in 줄 if 한줄.startswith("=="))
    assert "   test_two.py::test_a" in 줄
    assert "   test_two.py::test_b" not in 줄


def test_변이한_소스의_바이트코드_캐시는_변이_동안과_되돌린_뒤에_없다(tmp_path: Path) -> None:
    """캐시는 소스의 수정 시각(초)과 크기로만 맞춰 본다. 같은 크기의 변이가 같은 초에 쓰이면 원래
    바이트코드가 그대로 돌고, 거꾸로 변이 동안 생긴 캐시가 남으면 되돌린 원본이 변이된 바이트코드로
    돈다. pytest 의 assertion rewrite 캐시도 같은 자리에 같은 방식으로 산다. 이웃 소스의 캐시는
    건드리지 않는다(PR #89 CodeRabbit)."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    캐시 = [
        _파일을_둔다(tmp_path, "src/__pycache__/m.cpython-312.pyc", b"old"),
        _파일을_둔다(tmp_path, "src/__pycache__/m.cpython-312-pytest-9.1.1.pyc", b"old"),
    ]
    이웃 = _파일을_둔다(tmp_path, "src/__pycache__/mm.cpython-312.pyc", b"old")
    변이_동안: list[bool] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" not in path.read_bytes():
            return _초록
        변이_동안.extend(pyc.exists() for pyc in 캐시)
        for pyc in 캐시:  # 변이된 소스의 캐시를 누군가 남겼다
            pyc.write_bytes(b"mutated")
        return _빨강

    measure(
        load_spec(_변이_파일(old="x = 1", new="x = 2")),
        root=tmp_path,
        runner=러너,
        out=lambda _: None,
    )

    assert 변이_동안 == [False, False]
    assert [pyc.exists() for pyc in 캐시] == [False, False]
    assert 이웃.exists()


def test_러너가_예외를_던져도_원래_바이트로_돌아온다(tmp_path: Path) -> None:
    원래 = b"x = 1\r\n"
    path = _파일을_둔다(tmp_path, "src/m.py", 원래)

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            raise KeyboardInterrupt
        return _초록

    with pytest.raises(KeyboardInterrupt):
        measure(
            load_spec(_변이_파일(old="x = 1", new="x = 2")),
            root=tmp_path,
            runner=러너,
            out=lambda _: None,
        )

    assert path.read_bytes() == 원래


def test_시간_제한을_넘긴_변이는_오류이고_되돌린_뒤_다음_변이로_간다(tmp_path: Path) -> None:
    """검사 러너의 변이가 러너→pytest→러너로 되풀이하며 10분 넘게 돌았고, 손으로 죽이자 변이된 한
    줄이 파일에 남았다(대기열 139). 끝나지 않는 변이 하나가 표 전체를 멈추지 않는다."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    줄: list[str] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, "도는 중\n", timed_out_after=timeout)
        return _빨강 if b"x = 3" in path.read_bytes() else _초록

    변이 = _변이_파일(old="x = 1", new="x = 2").replace(
        'expect = "red"', 'expect = "red"\ntimeout = 5'
    ) + _변이_파일(old="x = 1", new="x = 3").replace('name = "하나"', 'name = "둘"')

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=줄.append)

    assert code == 1
    assert any("어긋남" in 한줄 and "하나" in 한줄 and "5초" in 한줄 for 한줄 in 줄)
    assert any(한줄.startswith("==") and "둘" in 한줄 for 한줄 in 줄)
    assert path.read_bytes() == b"x = 1\n"


def test_시간_제한을_넘기면_남은_반복을_돌지_않는다(tmp_path: Path) -> None:
    """끊긴 판정은 이미 기대와 어긋나, 남은 반복은 변이를 든 채 시간만 쓴다(셀프 리뷰)."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    변이에서_불린: list[int] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" not in path.read_bytes():
            return _초록
        변이에서_불린.append(timeout)
        return CommandResult(1, "", timed_out_after=timeout)

    변이 = _변이_파일(old="x = 1", new="x = 2").replace(
        'expect = "red"', 'expect = "red"\nrepeat = 3'
    )

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert code == 1
    assert 변이에서_불린 == [600]
    assert path.read_bytes() == b"x = 1\n"


@pytest.mark.parametrize("판정자", ["pytest", "vitest", "playwright", "tsc", "exit"])
def test_시간_제한을_넘긴_결과는_출력이_무엇이든_오류다(판정자: JudgeName) -> None:
    """끊기 전까지의 출력이 초록이나 빨강으로 읽혀도 끝까지 돌지 않은 판정은 재는 것이 없다."""
    끊긴 = CommandResult(1, "1 failed, 2 passed\n      Tests  1 failed (3)\n", timed_out_after=9)

    판정 = judge(Judging(판정자, diagnostic_in="a.ts"), 끊긴)

    assert 판정.outcome == "error"
    assert "9초" in 판정.summary


def test_러너는_변이의_시간_제한을_받고_기준선은_같은_짝의_가장_긴_것을_받는다(
    tmp_path: Path,
) -> None:
    """기준선은 러너와 인자의 짝마다 한 번이라 그 짝을 쓰는 변이 가운데 가장 긴 제한을 받는다.
    적지 않으면 600초다."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    받은: list[int] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        받은.append(timeout)
        return _초록

    변이 = _변이_파일(old="x = 1", new="x = 2", expect="green").replace(
        'expect = "green"', 'expect = "green"\ntimeout = 30'
    ) + _변이_파일(old="x = 1", new="x = 3", expect="green").replace('name = "하나"', 'name = "둘"')

    measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert 받은 == [600, 30, 600]


_손자 = """
import os, pathlib, sys, time
심장 = pathlib.Path(sys.argv[1])
심장.with_suffix(".pid").write_text(str(os.getpid()))
끝 = time.monotonic() + 60  # 아무도 끝내지 못해도 스스로 끝난다. 판정의 기한보다 길게 산다
while time.monotonic() < 끝:
    with 심장.open("ab") as f:
        f.write(b".")
    time.sleep(0.05)
"""

_자식 = """
import pathlib, subprocess, sys, time
심장 = pathlib.Path(sys.argv[2])
떠난다 = sys.argv[3] == "떠난다"
따로 = 떠난다 and sys.platform != "win32"  # POSIX: 손자가 제 세션을 따로 연다
손자 = [sys.executable, "-c", sys.argv[1], sys.argv[2]]
subprocess.Popen(손자, stdout=sys.stdout, stderr=sys.stderr, start_new_session=따로)
while not 심장.exists():
    time.sleep(0.05)
print("손자가 뛴다", flush=True)
심장.with_suffix(".printed").touch()
if 떠난다 and not 따로:
    sys.exit(0)  # 윈도우: 자식이 먼저 끝나 손자가 고아가 된다
time.sleep(60)
"""


_판정_기한_초 = 15
_손자가_산다 = f"러너가 돌아온 뒤 {_판정_기한_초}초 동안 손자의 기록 파일이 1초도 멈추지 않았다"
_손자가_끝났다 = f"{_판정_기한_초}초 동안 손자의 기록 파일이 자라지 않았다(남아야 할 손자가 끝났다)"


def _멈추는지(심장: Path) -> bool:
    """기한 안에 손자의 기록 파일이 1초 동안 자라지 않으면 참. 한 번만 견주지 않고 기한까지 거듭
    견준다(`tests/tools/test_run_checks.py` 의 `_stops_growing`). 부하에서는 `taskkill` 이 손자를
    끝냈다고 알리고 러너가 돌아온 뒤에도 손자가 잠깐 더 살아 기록 파일에 쓴 회차가 있었다. 러너가
    돌아온 직후 0.5초 사이를 한 번만 견주던 판은 그 쓰기를 산 손자로 읽었다(대기열 306, ADR 0035 의
    2026-10-18 이력. `taskkill /F` 가 끝내기를 시작만 하고 돌아오는 `TerminateProcess` 를 부른다는
    해석은 어림이다)."""
    끝 = time.monotonic() + _판정_기한_초
    while time.monotonic() < 끝:
        크기 = 심장.stat().st_size
        time.sleep(1)
        if 심장.stat().st_size == 크기:
            return True
    return False


def _자라는지(심장: Path) -> bool:
    """손자의 기록 파일이 기한 안에 한 번이라도 자라면 참이다. 부하로 손자가 늦게 돌아도 기한까지
    기다린다."""
    끝 = time.monotonic() + _판정_기한_초
    크기 = 심장.stat().st_size
    while time.monotonic() < 끝:
        time.sleep(0.05)
        if 심장.stat().st_size != 크기:
            return True
    return False


def _남았으면_끝낸다(심장: Path) -> None:
    """시험이 빨개져 손자가 남았으면 끝낸다. 손자는 판정의 기한보다 길게 살아, 빨간 회차에 그대로
    두면 그동안 `tmp_path` 에 쓴다. 기록 파일이 자라는 동안만 pid 를 손자의 것으로 믿는다. 끝난
    손자의 pid 는 다른 프로세스가 다시 받을 수 있어 자라지 않으면 끄지 않는다. 0.5초보다 오래 쉰
    손자는 끄지 못하고 스스로 끝나기를 둔다."""
    pid = 심장.with_suffix(".pid")
    if not 심장.exists() or not pid.exists():
        return
    크기 = 심장.stat().st_size
    time.sleep(0.5)
    if 심장.stat().st_size != 크기:
        with contextlib.suppress(OSError):  # 그사이 끝났으면 없다
            os.kill(int(pid.read_text()), signal.SIGTERM)


def _첫_기다림을_끊는다(
    monkeypatch: pytest.MonkeyPatch,
    끊는_예외: Callable[[subprocess.Popen[str], float], BaseException],
    준비됐다: Callable[[subprocess.Popen[str]], bool] = lambda _: True,
) -> None:
    """실제 러너의 첫 기다림(`communicate`)을 `준비됐다` 가 참이 된 뒤 `끊는_예외` 로 끊는다. 뒤의
    기다림(끊은 뒤 남은 출력을 읽는 것, `taskkill` 을 기다리는 것)은 그대로 둔다. 그것까지 끊으면
    끝내지 못한다. 시간 제한이 실제로 지나기를 기다리던 판은 시험 한 번 13초 가운데 10초를 썼고,
    부하에서 기동이 3초를 넘기면 손자가 뛰기 전에 끊겨 거짓 빨강이 날 수 있었다(대기열 203). 준비를
    30초 넘게 기다리면 그대로 끊어 시험이 단언에서 실패하게 둔다."""
    원래 = subprocess.Popen[str].communicate
    끊었다: list[bool] = []

    def 한_번_끊긴다(
        self: subprocess.Popen[str], 입력: str | None = None, timeout: float | None = None
    ) -> tuple[str, str]:
        if 끊었다:
            return 원래(self, 입력, timeout)
        끝 = time.monotonic() + 30
        while not 준비됐다(self) and time.monotonic() < 끝:
            time.sleep(0.05)
        끊었다.append(True)
        raise 끊는_예외(self, timeout or 0)

    monkeypatch.setattr(subprocess.Popen, "communicate", 한_번_끊긴다)


def _시간_제한(process: subprocess.Popen[str], timeout: float) -> BaseException:
    return subprocess.TimeoutExpired(process.args, timeout)


def _Ctrl_C(process: subprocess.Popen[str], timeout: float) -> BaseException:
    return KeyboardInterrupt()


def test_실제_러너는_시간_제한을_넘기면_손자_프로세스까지_끝내고_그때까지의_출력을_돌려준다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """하위 명령이 띄운 프로세스(pytest 가 띄운 러너)가 남으면 그것이 계속 돌고, 출력 파이프를 쥐어
    결과를 읽는 쪽도 끝나지 않는다(대기열 139). 손자는 자식의 출력 파이프를 물려받아 쥔다."""
    심장 = tmp_path / "heartbeat"
    _첫_기다림을_끊는다(monkeypatch, _시간_제한, lambda _: 심장.with_suffix(".printed").exists())
    시작 = time.monotonic()

    결과 = run_command([sys.executable, "-c", _자식, _손자, str(심장), "머문다"], tmp_path, 60)

    걸린 = time.monotonic() - 시작
    try:
        assert 결과.timed_out_after == 60
        assert "손자가 뛴다" in 결과.output
        # 자식과 손자를 띄우는 시간과 `taskkill` 까지 든다. 8초로 두던 판이 pytest 세 벌을 함께 띄운
        # 부하에서 13.6초로 빨갰다(ADR 0035 의 2026-10-18 이력)
        assert 걸린 < 30
        assert 심장.stat().st_size > 0
        assert _멈추는지(심장), _손자가_산다
    finally:
        _남았으면_끝낸다(심장)


def test_실제_러너는_시간_제한을_실제로_넘긴_명령을_끊는다(tmp_path: Path) -> None:
    """다른 실제 러너 시험은 첫 기다림에 시간 제한을 넣어, 시간 제한을 기다림에 넘기는 배관은 이
    시험만 잰다. 자식이 60초를 자므로 기동이 늦어도 1초 제한은 늘 먼저 오고, 러너가 자식이 끝나기를
    기다리는 회귀는 걸린 시간의 상한에서 빨갛다."""
    시작 = time.monotonic()

    결과 = run_command([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, 1)

    assert 결과.timed_out_after == 1
    # 자식을 띄우는 시간과 제한 1초, `taskkill` 이 든다. 8초로 두던 판이 CPU 를 태우는 프로세스 32개
    # 옆에서 60회차 가운데 7번 빨갰고(가장 긴 것 23.3초) 늘어난 몫은 모두 `taskkill` 이었다(ADR
    # 0035 의 2026-10-19 이력 "손자 없는 시간 제한 시험의 상한을 30초로 넓힌다")
    assert time.monotonic() - 시작 < 30


def test_실제_러너는_프로세스_트리를_끝내지_못해도_자식은_끝낸다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`taskkill` 을 띄우지 못하거나 프로세스 그룹을 끝내지 못한 채 자식이 남으면, 출력을 그만 읽은
    뒤에도 자식이 끝나기를 기다린다."""

    def 띄우지_못한다(*_: object, **__: object) -> subprocess.CompletedProcess[bytes]:
        raise OSError("taskkill 을 찾지 못했다")

    def 끝내지_못한다(*_: object) -> None:
        raise PermissionError

    monkeypatch.setattr(subprocess, "run", 띄우지_못한다)
    monkeypatch.setattr(os, "killpg", 끝내지_못한다, raising=False)
    monkeypatch.setattr("tools.mutate._DRAIN_SECONDS", 1)
    _첫_기다림을_끊는다(monkeypatch, _시간_제한)
    시작 = time.monotonic()

    결과 = run_command([sys.executable, "-c", "import time; time.sleep(20)"], tmp_path, 60)

    assert 결과.timed_out_after == 60
    assert time.monotonic() - 시작 < 8


def test_실제_러너는_기다리는_동안_Ctrl_C_가_나도_손자_프로세스까지_끝낸다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """끊긴 실행이 남긴 프로세스는 되돌린 파일 위에서 계속 돈다. 끊는 것은 처음 기다림 하나다."""
    심장 = tmp_path / "heartbeat"
    _첫_기다림을_끊는다(monkeypatch, _Ctrl_C, lambda _: 심장.with_suffix(".printed").exists())

    try:
        with pytest.raises(KeyboardInterrupt):
            run_command([sys.executable, "-c", _자식, _손자, str(심장), "머문다"], tmp_path, 60)

        assert _멈추는지(심장), _손자가_산다
    finally:
        _남았으면_끝낸다(심장)


def test_못_보는_것_고아가_되거나_제_세션을_연_손자는_남고_출력은_잠시만_기다린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """윈도우의 `taskkill /T` 는 부모를 따라 찾아 고아를 못 찾고, POSIX 의 프로세스 그룹은 제 세션을
    연 손자를 담지 않는다(독스트링의 못 보는 것). 남은 손자가 출력 파이프를 쥐어도 기다림은
    끝난다. 윈도우에서는 자식이 끝나 손자가 고아가 된 뒤에 끊는다. 그 전에 끊으면 `taskkill /T` 가
    자식을 따라 손자를 찾는다."""
    monkeypatch.setattr("tools.mutate._DRAIN_SECONDS", 1)
    심장 = tmp_path / "heartbeat"

    def 고아가_됐다(process: subprocess.Popen[str]) -> bool:
        찍었다 = 심장.with_suffix(".printed").exists()
        return 찍었다 and (sys.platform != "win32" or process.poll() is not None)

    _첫_기다림을_끊는다(monkeypatch, _시간_제한, 고아가_됐다)
    시작 = time.monotonic()

    결과 = run_command([sys.executable, "-c", _자식, _손자, str(심장), "떠난다"], tmp_path, 60)

    걸린 = time.monotonic() - 시작
    try:
        assert 결과.timed_out_after == 60
        assert "그만 읽었다" in 결과.output
        # 시간 제한 시험과 같은 자식과 손자를 띄우는 길이다. 8초로 두던 판이 pre-commit 에서 9.3초로
        # 빨갰다(일지 2026-10-17-04, ADR 0035 의 2026-10-18 이력)
        assert 걸린 < 30
        assert _자라는지(심장), _손자가_끝났다
    finally:
        _남았으면_끝낸다(심장)


_그룹을_여는_자식 = """
import pathlib, subprocess, sys, time
심장 = pathlib.Path(sys.argv[2])
손자 = [sys.executable, "-c", sys.argv[1], sys.argv[2]]
쥘_파이프 = {"stdout": sys.stdout, "stderr": sys.stderr}
if sys.platform == "win32":
    subprocess.Popen(손자, **쥘_파이프)
else:
    subprocess.Popen(손자, **쥘_파이프, process_group=0)  # 그룹만 따로 연다
while not 심장.exists():
    time.sleep(0.05)
print("손자가 뛴다", flush=True)
심장.with_suffix(".printed").touch()
time.sleep(60)
"""


def test_못_보는_것_프로세스_그룹만_따로_연_손자는_POSIX_에서_남는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`killpg` 는 자식이 이끄는 그룹만 끝내 그룹을 따로 연 손자를 담지 않는다. 윈도우에는 그 그룹이
    없고 `taskkill /T` 가 부모를 따라 찾아 끝낸다(독스트링의 못 보는 것,
    `.claude/rules/tools.md`)."""
    monkeypatch.setattr("tools.mutate._DRAIN_SECONDS", 1)
    심장 = tmp_path / "heartbeat"
    _첫_기다림을_끊는다(monkeypatch, _시간_제한, lambda _: 심장.with_suffix(".printed").exists())

    결과 = run_command([sys.executable, "-c", _그룹을_여는_자식, _손자, str(심장)], tmp_path, 60)

    try:
        assert 결과.timed_out_after == 60
        if sys.platform == "win32":
            assert _멈추는지(심장), _손자가_산다
        else:
            assert _자라는지(심장), _손자가_끝났다
    finally:
        _남았으면_끝낸다(심장)


def test_실제_러너는_시간_안에_끝난_명령의_종료_코드와_출력을_돌려준다(tmp_path: Path) -> None:
    결과 = run_command(
        [sys.executable, "-c", "import sys; print('나옴'); sys.exit(3)"], tmp_path, 60
    )

    assert (결과.exit_code, 결과.timed_out_after) == (3, None)
    assert "나옴" in 결과.output


def _변이면(path: Path, 표지: bytes, 변이: CommandResult) -> 러너:
    """파일에 표지가 있으면(변이가 들었으면) `변이`, 아니면 초록을 내는 러너."""

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        return 변이 if 표지 in path.read_bytes() else _초록

    return 러너


@pytest.mark.parametrize(
    ("expect", "변이_결과", "기대_코드"),
    [("red", _빨강, 0), ("red", _초록, 1), ("green", _초록, 0), ("green", _빨강, 1)],
)
def test_기대와_결과가_어긋나면_알리고_1을_돌려준다(
    tmp_path: Path, expect: str, 변이_결과: CommandResult, 기대_코드: int
) -> None:
    """빨강을 기대한 변이가 초록으로 지나간 것을 아무도 몰랐다(대기열 29의 5회차)."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    줄: list[str] = []

    code = measure(
        load_spec(_변이_파일(old="x = 1", new="x = 2", expect=expect)),
        root=tmp_path,
        runner=_변이면(path, b"x = 2", 변이_결과),
        out=줄.append,
    )

    assert code == 기대_코드
    assert any("어긋" in 한줄 for 한줄 in 줄) == (기대_코드 == 1)


def test_수집_오류는_빨강이_아니라_오류라서_빨강을_기대해도_어긋난다(tmp_path: Path) -> None:
    """문법 오류로 모든 것이 빨간 변이는 테스트의 이빨을 재지 않는다."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    줄: list[str] = []
    수집_오류 = CommandResult(2, "ERROR tests/test_x.py\nInterrupted: 1 error during collection\n")

    code = measure(
        load_spec(_변이_파일(old="x = 1", new="x = (")),
        root=tmp_path,
        runner=_변이면(path, b"x = (", 수집_오류),
        out=줄.append,
    )

    assert code == 1
    assert any("오류" in 한줄 for 한줄 in 줄)


def test_반복하면_매번_기대와_같아야_한다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    결과들 = iter([_빨강, _초록, _빨강])
    불린_횟수 = 0

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        nonlocal 불린_횟수
        if b"x = 2" not in path.read_bytes():
            return _초록
        불린_횟수 += 1
        return next(결과들)

    변이 = _변이_파일(old="x = 1", new="x = 2").replace(
        'expect = "red"', 'expect = "red"\nrepeat = 3'
    )

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert 불린_횟수 == 3
    assert code == 1


def test_기준선이_초록이_아니면_변이를_넣지_않는다(tmp_path: Path) -> None:
    """기준선이 빨간데 변이가 빨가면 그 빨강은 아무것도 말하지 않는다."""
    원래 = b"x = 1\n"
    path = _파일을_둔다(tmp_path, "src/m.py", 원래)
    본_것: list[bytes] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        본_것.append(path.read_bytes())
        return _빨강

    줄: list[str] = []
    code = measure(
        load_spec(_변이_파일(old="x = 1", new="x = 2")),
        root=tmp_path,
        runner=러너,
        out=줄.append,
    )

    assert code == 1
    assert 본_것 == [원래]
    assert any("기준선" in 한줄 for 한줄 in 줄)


def _부르면_안_되는_러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
    raise AssertionError("변이 파일 오류인데 테스트를 돌렸다")


@pytest.mark.parametrize("내용", [b"y = 1\n", b"x = 1\nx = 1\n"], ids=["없다", "두_번"])
def test_원문이_정확히_한_번이_아니면_아무_파일도_쓰지_않고_변이_파일_오류다(
    tmp_path: Path, 내용: bytes
) -> None:
    """앞의 변이가 맞아도 뒤의 변이가 틀리면 기준선도 돌지 않는다."""
    맞는_파일 = _파일을_둔다(tmp_path, "src/a.py", b"a = 1\n")
    _파일을_둔다(tmp_path, "src/m.py", 내용)
    변이 = _변이_파일(old="a = 1", new="a = 2", file="src/a.py") + _변이_파일(
        old="x = 1", new="x = 2"
    )

    with pytest.raises(SpecError, match="src/m.py"):
        measure(
            load_spec(변이.replace('name = "하나"', 'name = "둘"', 1)),
            root=tmp_path,
            runner=_부르면_안_되는_러너,
            out=lambda _: None,
        )

    assert 맞는_파일.read_bytes() == b"a = 1\n"


@pytest.mark.parametrize(
    ("old", "기대_코드"),
    [("x = 1\n", 2), ("x = 1", 0), ("x = 1 + 2\n", 0)],
    ids=["다음_줄에_닫은_줄의_일부", "같은_줄에_닫은_줄의_일부", "다음_줄에_닫은_온전한_줄"],
)
def test_닫는_따옴표를_다음_줄에_두면_그_앞의_줄바꿈도_원문에_든다(
    tmp_path: Path, old: str, 기대_코드: int
) -> None:
    """줄의 일부만 적고 닫는 `'''` 를 다음 줄에 둔 원문 넷이 `--check` 에서 걸렸다(대기열 152)."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1 + 2\n")
    변이 = _변이_파일(old=old, new="x = 3\n")
    줄: list[str] = []

    assert check(load_spec(변이), root=tmp_path, out=줄.append) == 기대_코드
    assert any("원문이 0번 있다" in 한줄 for 한줄 in 줄) == (기대_코드 == 2)


@pytest.mark.parametrize(
    ("내용", "원문", "까닭"),
    [
        (
            b"a = 1\r\nb = 2\r\n",
            r"a = 1\nb = 2",
            "줄 끝이 다르다(파일은 CRLF 뿐이다, 줄 끝을 맞추면 1번)",
        ),
        (
            b"a = 1\nb = 2\n",
            r"a = 1\r\nb = 2",
            "줄 끝이 다르다(파일은 LF 뿐이다, 줄 끝을 맞추면 1번)",
        ),
        (
            b"a = 1\r\nb = 2\nc = 3\r\n",
            r"a = 1\r\nb = 2\r\n",
            "줄 끝이 다르다(파일은 CRLF 와 LF 가 섞였다, 줄 끝을 맞추면 1번)",
        ),
        (
            b"a = 1\r\nb = 2\r\na = 1\r\nb = 2\r\n",
            r"a = 1\nb = 2",
            "줄 끝이 다르다(파일은 CRLF 뿐이다, 줄 끝을 맞추면 2번)",
        ),
        (b"a = 1\r\nb = 2\r\n", r"a = 1\nc = 2", None),
    ],
    ids=[
        "파일이_CRLF",
        "파일이_LF",
        "줄_끝이_섞였다",
        "줄_끝을_맞추면_두_번",
        "줄_끝을_맞춰도_없다",
    ],
)
def test_원문이_줄_끝만_달라_0번이면_그_까닭을_덧붙인다(
    tmp_path: Path, 내용: bytes, 원문: str, 까닭: str | None
) -> None:
    """패치 스크립트의 `Path.write_text` 가 윈도우에서 도구를 CRLF 로 바꿔 써, 원문 스무 개 남짓이
    "0번 있다" 고만 나왔다. 줄 끝이 까닭이라는 것은 HEAD 사본과 견주고서야 알았다(대기열 264). git
    은 커밋에서 LF 로 고쳐 diff 에 보이지 않았다. 줄 끝이 섞인 파일과 줄 끝을 맞추면 두 번인 원문도
    문구가 참이어야 한다(셀프 리뷰 표준 축)."""
    _파일을_둔다(tmp_path, "src/m.py", 내용)
    변이 = (
        _변이_파일(old="x", new="y")
        .replace("old = '''x'''", f'old = "{원문}"')
        .replace("new = '''y'''", 'new = "z"')
    )
    줄: list[str] = []

    assert check(load_spec(변이), root=tmp_path, out=줄.append) == 2
    assert any("원문이 0번 있다" in 한줄 for 한줄 in 줄), 줄
    if 까닭 is None:
        assert not any("줄 끝이 다르다" in 한줄 for 한줄 in 줄), 줄
    else:
        assert any(까닭 in 한줄 for 한줄 in 줄), 줄


def test_한_변이의_편집_여럿은_앞_편집의_결과_위에_차례로_들어간다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    본_것: list[bytes] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        본_것.append(path.read_bytes())
        return _초록 if len(본_것) == 1 else _빨강

    변이 = _변이_파일(old="x = 1", new="x = 2") + "\n".join(
        ["[[mutation.edit]]", 'file = "src/m.py"', "old = 'x = 2'", "new = 'x = 3'", ""]
    )

    measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert 본_것[1] == b"x = 3\n"
    assert path.read_bytes() == b"x = 1\n"


def test_저장소_밖을_가리키는_파일은_변이_파일_오류다(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    바깥 = _파일을_둔다(tmp_path, "outside.py", b"x = 1\n")

    with pytest.raises(SpecError, match="저장소 밖"):
        measure(
            load_spec(_변이_파일(old="x = 1", new="x = 2", file="../outside.py")),
            root=root,
            runner=_부르면_안_되는_러너,
            out=lambda _: None,
        )

    assert 바깥.read_bytes() == b"x = 1\n"


@pytest.mark.parametrize(
    ("바꿀_것", "바꾼_것"),
    [
        ('expect = "red"', 'expect = "빨강"'),
        ('expect = "red"', 'expect = "red"\nrepaet = 3'),
        ('tests = ["tests/test_x.py"]', 'tests = "tests/test_x.py"'),
        ('expect = "red"', 'expect = "red"\nrepeat = 0'),
    ],
    ids=["기대는_red_green_unhandled", "모르는_키", "tests_는_목록", "반복은_1_이상"],
)
def test_변이_파일의_모양이_틀리면_오류다(바꿀_것: str, 바꾼_것: str) -> None:
    with pytest.raises(SpecError):
        load_spec(_변이_파일(old="x = 1", new="x = 2").replace(바꿀_것, 바꾼_것))


def test_이름이_겹치면_변이_파일_오류다() -> None:
    """이름으로 골라 다시 돌리므로 이름이 변이 하나를 가리켜야 한다."""
    with pytest.raises(SpecError, match="하나"):
        load_spec(_변이_파일(old="x = 1", new="x = 2") * 2)


def test_이름으로_고른다() -> None:
    변이 = load_spec(
        _변이_파일(old="x = 1", new="x = 2")
        + _변이_파일(old="x = 1", new="x = 3").replace("하나", "둘")
    )

    assert [m.name for m in select(변이, ["둘"]).mutation] == ["둘"]
    assert select(변이, []) == 변이
    with pytest.raises(SpecError, match="셋"):
        select(변이, ["셋"])


def test_이름으로_고른_변이는_제_러너의_명령으로_돈다(tmp_path: Path) -> None:
    """고른 뒤에도 변이가 가리키는 러너를 찾을 수 있어야 한다."""
    _파일을_둔다(tmp_path, "web/m.ts", b"x = 1\n")
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    변이 = load_spec(_VITEST_러너 + _vitest_변이(name="둘") + _변이_파일(old="x = 1", new="x = 2"))
    불린_것: list[tuple[str, ...]] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        불린_것.append(tuple(argv))
        return CommandResult(0, "      Tests  1 passed (1)\n")

    measure(select(변이, ["둘"]), root=tmp_path, runner=러너, out=lambda _: None)

    assert 불린_것[0] == ("pnpm", "exec", "vitest", "run", "a.test.ts")


def _글자_변이(이름: str, 글자: str, *, expect: str = "red") -> str:
    """`src/m.py` 의 `글자 = 1` 을 `글자 = 2` 로 바꾸는 변이."""
    return _변이_파일(old=f"{글자} = 1", new=f"{글자} = 2", expect=expect).replace(
        'name = "하나"', f'name = "{이름}"'
    )


def _셋() -> str:
    return _글자_변이("하나", "x") + _글자_변이("둘", "y") + _글자_변이("셋", "z")


def test_번호로도_고르고_이름과_섞을_수_있다() -> None:
    """이름에 공백이 있으면 고를 때 따옴표 인자가 필요한데, 워크트리 가드가 그런 인자를 거부한 적이
    있어 표 전체를 돌렸다(대기열 193). 번호는 표에 적힌 차례이고 1부터다."""
    변이 = load_spec(_셋())

    assert [m.name for m in select(변이, ["3", "하나"]).mutation] == ["하나", "셋"]
    for 틀린 in ("0", "4"):
        with pytest.raises(SpecError, match=f"표 밖의 번호 {틀린}"):
            select(변이, [틀린])


def test_숫자만인_이름은_번호와_가를_수_없어_변이_파일_오류다() -> None:
    with pytest.raises(SpecError, match="이름이 숫자뿐이다: 12"):
        load_spec(_변이_파일(old="x", new="y").replace('name = "하나"', 'name = "12"'))


def test_바뀐_변이는_새로_더했거나_그_변이나_그_러너의_무엇이든_달라진_것이다() -> None:
    """원문이 옮겨 가 고친 것, 기대를 바꾼 것, 러너의 명령을 바꾼 것을 모두 다시 돌린다. 지운 변이는
    돌릴 것이 없다."""
    옛 = load_spec(_VITEST_러너 + _vitest_변이(name="러너") + _셋() + _글자_변이("지운", "w"))
    새 = load_spec(
        _VITEST_러너.replace('"run"]', '"run", "--bail=1"]')
        + _vitest_변이(name="러너")
        + _글자_변이("하나", "x")
        + _글자_변이("둘", "y").replace("y = 1", "y = 0")
        + _글자_변이("셋", "z", expect="green")
        + _글자_변이("넷", "v")
    )

    assert changed_names(옛, 새) == ["러너", "둘", "셋", "넷"]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _커밋한_표(tmp_path: Path, 내용: str) -> Path:
    """`tmp_path` 를 저장소로 만들어 `probes/m_mutations.toml` 에 `내용` 을 커밋한다."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\ny = 1\nz = 1\n")
    표 = tmp_path / "probes" / "m_mutations.toml"
    표.parent.mkdir()
    표.write_text(내용, encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "표")
    return 표


def test_since_는_그_커밋의_같은_표와_견주어_바뀌거나_더한_변이만_돌린다(tmp_path: Path) -> None:
    """원문이 바뀌거나 더한 변이가 2~5개인 판 둘에서도 표 전체(한 번에 29~34분)를 돌렸다(대기열
    193)."""
    표 = _커밋한_표(tmp_path, _글자_변이("하나", "x") + _글자_변이("둘", "y"))
    표.write_text(
        _글자_변이("하나", "x")
        + _글자_변이("둘", "y").replace("y = 2", "y = 9")
        + _글자_변이("셋", "z"),
        encoding="utf-8",
    )
    m = tmp_path / "src/m.py"
    본_것: list[bytes] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        본_것.append(m.read_bytes())
        return _초록 if len(본_것) == 1 else _빨강

    줄: list[str] = []
    code = main([str(표), "--since", "HEAD"], root=tmp_path, runner=러너, out=줄.append)

    assert code == 0, 줄
    assert 본_것[1:] == [b"x = 1\ny = 9\nz = 1\n", b"x = 1\ny = 1\nz = 2\n"]
    assert any(한줄.startswith("== 2. 둘:") for 한줄 in 줄)
    assert any(한줄.startswith("== 3. 셋:") for 한줄 in 줄)


def test_since_로_고를_것이_없으면_아무것도_돌리지_않고_2다(tmp_path: Path) -> None:
    """커밋을 잘못 주어 아무것도 고르지 않은 실행이 0 으로 끝나면 잰 것처럼 보인다."""
    표 = _커밋한_표(tmp_path, _셋())
    줄: list[str] = []

    code = main(
        [str(표), "--since", "HEAD"], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append
    )

    assert code == 2
    assert any("HEAD" in 한줄 and "바뀌거나 더한 변이가 없다" in 한줄 for 한줄 in 줄)


def test_못_보는_것_since_는_코드나_시험만_바뀐_판에서_고를_것이_없다(tmp_path: Path) -> None:
    """`--since` 는 표만 견준다. 코드만 바꿔 둘레가 바뀐 변이도, 시험을 더해 빨개질 수 있는 대조군도
    고르지 않는다(독스트링의 고르기 문단의 못 보는 것, `.claude/rules/tools.md`)."""
    표 = _커밋한_표(tmp_path, _셋())
    (tmp_path / "src/m.py").write_bytes(b"x = 1\ny = 1\nz = 1\nw = 1\n")
    _파일을_둔다(tmp_path, "tests/test_x.py", b"def test_more() -> None:\n    pass\n")
    줄: list[str] = []

    code = main(
        [str(표), "--since", "HEAD"], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append
    )

    assert code == 2
    assert any("바뀌거나 더한 변이가 없다" in 한줄 for 한줄 in 줄)


def test_since_의_커밋에_표가_없으면_모두_새로_더한_변이다(tmp_path: Path) -> None:
    _커밋한_표(tmp_path, _셋())
    새_표 = tmp_path / "probes" / "new_mutations.toml"
    새_표.write_text(_셋(), encoding="utf-8")
    불린_수: list[int] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        불린_수.append(1)
        return _초록 if len(불린_수) == 1 else _빨강

    code = main([str(새_표), "--since", "HEAD"], root=tmp_path, runner=러너, out=print)

    assert code == 0
    assert len(불린_수) == 4


def test_원문_확인도_since_로_고른_것만_본다(tmp_path: Path) -> None:
    """코드를 고친 뒤 원문을 고친 변이만 다시 보는 길이다. 고르지 않은 변이의 원문은 보지 않는다.
    커밋이 그 원문을 깨는지는 `--staged` 가 커밋마다 본다(대기열 312)."""
    # 표지 없는 빨강은 따로 알린다(대기열 350). 이 시험은 원문만 보려고 초록을 기대한다
    표 = _커밋한_표(
        tmp_path, _글자_변이("하나", "x", expect="green") + _글자_변이("둘", "y", expect="green")
    )
    (tmp_path / "src/m.py").write_bytes(b"y = 1\nz = 1\n")  # 하나의 원문이 사라졌다
    표.write_text(
        _글자_변이("하나", "x", expect="green")
        + _글자_변이("둘", "y", expect="green")
        + _글자_변이("셋", "z", expect="green"),
        encoding="utf-8",
    )
    줄: list[str] = []

    code = main(
        ["--check", str(표), "--since", "HEAD"],
        root=tmp_path,
        runner=_부르면_안_되는_러너,
        out=줄.append,
    )

    assert code == 0, 줄
    assert any("변이 1 모두" in 한줄 for 한줄 in 줄)


def test_since_의_표가_git_저장소_밖이면_그렇게_알리고_2다(tmp_path: Path) -> None:
    """저장소가 아닌 것을 커밋을 풀지 못한 것으로 알리면 엉뚱한 커밋을 찾게 된다(PR 직전 버그
    축)."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\ny = 1\nz = 1\n")
    경로 = _변이_파일을_쓴다(tmp_path, _셋())
    줄: list[str] = []

    code = main(
        [경로, "--since", "HEAD"], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append
    )

    assert code == 2
    assert any("git 저장소 안이 아니다" in 한줄 for 한줄 in 줄), 줄


def test_since_의_커밋을_풀지_못하면_2다(tmp_path: Path) -> None:
    표 = _커밋한_표(tmp_path, _셋())
    줄: list[str] = []

    code = main(
        [str(표), "--since", "없는-커밋"], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append
    )

    assert code == 2
    assert any("없는-커밋" in 한줄 and "커밋으로 풀지 못했다" in 한줄 for 한줄 in 줄)


def test_출력은_표의_번호를_달고_끝에_다시_돌릴_번호를_낸다(tmp_path: Path) -> None:
    """고른 뒤에도 번호는 표의 차례다. 어긋난 것만 따옴표 없이 다시 돌린다."""
    m = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\ny = 1\nz = 1\n")
    경로 = _변이_파일을_쓴다(tmp_path, _셋())
    줄: list[str] = []

    code = main([경로, "3", "1"], root=tmp_path, runner=_변이면(m, b"2", _초록), out=줄.append)

    assert code == 1
    assert any(한줄.startswith("!! 어긋남 — 1. 하나:") for 한줄 in 줄)
    assert any(한줄.startswith("!! 어긋남 — 3. 셋:") for 한줄 in 줄)
    assert not any("둘" in 한줄 for 한줄 in 줄)
    assert 줄[-1] == "다시 돌릴 번호: 1 3"


@pytest.mark.parametrize(
    "argv_끝",
    [["--since"], ["--since", "--check"], ["--since", "HEAD", "--since", "HEAD~1"]],
    ids=["커밋이_없다", "커밋_자리에_선택", "두_번"],
)
def test_main_은_since_뒤에_커밋이_하나가_아니면_2다(tmp_path: Path, argv_끝: list[str]) -> None:
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    경로 = _변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2"))
    줄: list[str] = []

    code = main([경로, *argv_끝], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append)

    assert code == 2
    assert any("--since 뒤에는 커밋" in 한줄 for 한줄 in 줄), 줄


@pytest.mark.parametrize(
    ("결과", "판정"),
    [
        (CommandResult(0, "3 passed in 0.10s\n"), "green"),
        (CommandResult(1, "1 failed, 2 passed in 0.10s\n"), "red"),
        (CommandResult(2, "Interrupted: 1 error during collection\n"), "error"),
        (CommandResult(4, "ERROR: file or directory not found: tests/x.py\n"), "error"),
        (CommandResult(5, "no tests ran in 0.01s\n"), "error"),
        (CommandResult(0, "2 passed, 1 skipped in 0.10s\n"), "error"),
    ],
    ids=["통과", "실패", "수집_오류", "없는_경로", "선택된_테스트_없음", "skip_이_섞였다"],
)
def test_pytest_의_종료_코드와_요약으로_판정한다(결과: CommandResult, 판정: str) -> None:
    """skip 이 섞인 초록은 초록이 아니다(원칙 I). 재지 않은 테스트가 있다."""
    assert judge(Judging("pytest"), 결과).outcome == 판정


def test_빨간_테스트의_노드_아이디를_짧은_요약에서_읽는다() -> None:
    결과 = CommandResult(
        1,
        "..F\n"
        "FAILED tests/a.py::test_x[1] - assert 0\n"
        "ERROR tests/b.py::test_y - fixture 'z' not found\n"
        "1 failed, 1 error in 0.10s\n",
    )

    assert judge(Judging("pytest"), 결과).failed == ("tests/a.py::test_x[1]", "tests/b.py::test_y")


_VITEST_실패 = """
 ❯ |node| packages/api-client/src/p.test.ts (3 tests | 1 failed) 8ms
   × 실패 한다 5ms

 Test Files  1 failed (1)
      Tests  1 failed | 2 passed (3)
   Duration  680ms

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  |node| packages/api-client/src/p.test.ts > 실패 한다
AssertionError: expected 'yes' to be 'no' // Object.is equality
"""

_VITEST_수집_오류 = """
 ❯ |node| packages/api-client/src/broken.test.ts (0 test)

 Test Files  1 failed | 1 passed (2)
      Tests  3 passed (3)

 FAIL  |node| packages/api-client/src/broken.test.ts [ packages/api-client/src/broken.test.ts ]
Error: Transform failed with 1 error:
\x1b[31m[PARSE_ERROR] \x1b[0mExpected `,` or `)` but found `;`
"""


@pytest.mark.parametrize(
    ("결과", "판정"),
    [
        (CommandResult(0, " Test Files  1 passed (1)\n      Tests  3 passed (3)\n"), "green"),
        (
            CommandResult(0, " Test Files  1 passed (1)\n      Tests  1 passed | 2 skipped (3)\n"),
            "green",
        ),
        (CommandResult(1, _VITEST_실패), "red"),
        (
            CommandResult(
                1,
                _VITEST_실패.replace("[", "\x1b[33m[\x1b[39m").replace(
                    "Tests", "\x1b[2mTests\x1b[22m"
                ),
            ),
            "red",
        ),
        (
            CommandResult(1, "      Tests  3 passed (3)\n     Errors  1 error\n"),
            "unhandled",
        ),
        (
            CommandResult(1, "      Tests  1 failed | 2 passed (3)\n     Errors  1 error\n"),
            "red",
        ),
        (CommandResult(1, _VITEST_수집_오류), "error"),
        (
            CommandResult(
                1, _VITEST_수집_오류.replace("Tests  3 passed", "Tests  1 failed | 2 passed")
            ),
            "error",
        ),
        (CommandResult(1, "No test files found, exiting with code 1\n"), "error"),
        (CommandResult(0, "      Tests  3 skipped (3)\n"), "error"),
    ],
    ids=[
        "통과",
        "이름으로_좁혀_나머지가_skip",
        "실패",
        "색이_섞인_실패",
        "처리하지_않은_에러만",
        "실패와_처리하지_않은_에러",
        "수집_오류",
        "수집_오류와_실패",
        "테스트_파일_없음",
        "통과한_테스트_없음",
    ],
)
def test_vitest_는_실패한_테스트가_셀_때만_빨강이다(결과: CommandResult, 판정: str) -> None:
    """종료 코드는 실패와 수집 오류와 처리하지 않은 에러가 모두 1 이다. 수집 오류(파일 단위의
    FAIL)가 하나라도 있으면 다른 파일의 실패가 있어도 오류다 — 깨진 파일이 재지 않은 테스트를
    남겼다. `-t` 로 좁히면 나머지가 skipped 로 세어지므로 skip 은 오류가 아니다(못 보는 것)."""
    assert judge(Judging("vitest"), 결과).outcome == 판정


def test_vitest_의_빨간_테스트는_FAIL_줄에서_읽는다() -> None:
    assert judge(Judging("vitest"), CommandResult(1, _VITEST_실패)).failed == (
        "|node| packages/api-client/src/p.test.ts > 실패 한다",
    )


_TSC_진단 = (
    "packages/api-client/src/clients.test-d.ts(12,3): error TS2578: Unused '@ts-expect-error'.\n"
    "packages/api-client/src/stream.ts(40,1): error TS1360: Type does not satisfy.\n"
)


@pytest.mark.parametrize(
    ("결과", "자리", "판정"),
    [
        (CommandResult(0, ""), "clients.test-d.ts", "green"),
        (CommandResult(2, _TSC_진단), "clients.test-d.ts", "red"),
        (CommandResult(2, _TSC_진단), "packages/api-client/src/stream.ts", "red"),
        (CommandResult(2, _TSC_진단), "clients.ts", "error"),
        (CommandResult(2, _TSC_진단), "test-d.ts", "error"),
        (
            CommandResult(1, "src/clients.ts(3,1): error TS2322: Type 'string'.\nundefined\n"),
            "clients.ts",
            "red",
        ),
        (
            CommandResult(1, "[ELIFECYCLE] Command failed with exit code 1.\n"),
            "clients.ts",
            "error",
        ),
        (CommandResult(2, "other/index.ts(1,1): error TS2322: x.\n"), "index.ts", "red"),
        (CommandResult(2, "other/index.ts(1,1): error TS2322: x.\n"), "src/index.ts", "error"),
    ],
    ids=[
        "진단_없음",
        "적은_파일의_진단",
        "경로로_적은_파일",
        "다른_파일만",
        "파일_이름의_끝만_같다",
        "pnpm_r_의_패키지_기준_경로",
        "진단_없이_실패",
        "못_보는_것_다른_디렉터리의_같은_이름",
        "디렉터리까지_적으면_가른다",
    ],
)
def test_tsc_는_적은_파일에서_진단이_날_때만_빨강이다(
    결과: CommandResult, 자리: str, 판정: str
) -> None:
    """tsc 의 종료 코드는 문법 오류와 타입 에러가 같고(2), 오류 번호로도 가를 수 없다(`satisfies` 의
    어긋남이 TS1360 이다). 그래서 빨강은 변이가 적은 파일의 진단이다(대기열 59의 첫 판정)."""
    assert judge(Judging("tsc", diagnostic_in=자리), 결과).outcome == 판정


def test_tsc_의_진단은_빨간_목록에_든다() -> None:
    판정 = judge(Judging("tsc", diagnostic_in="stream.ts"), CommandResult(2, _TSC_진단))

    assert 판정.failed == (
        "packages/api-client/src/clients.test-d.ts(12,3): error TS2578",
        "packages/api-client/src/stream.ts(40,1): error TS1360",
    )


def test_tsc_러너의_변이는_변이에_적은_진단_자리로_판정한다(tmp_path: Path) -> None:
    """진단 자리는 변이에, 판정은 러너에 적혀 측정이 둘을 묶어 넘긴다(PR #240 claude-review 의 판정
    인자 묶기). 기준선은 진단이 없어 초록이다."""
    path = _파일을_둔다(tmp_path, "web/m.ts", b"x = 1\n")
    변이 = _VITEST_러너.replace('judge = "vitest"', 'judge = "tsc"') + _vitest_변이(
        줄='diagnostic_in = "stream.ts"'
    )

    러너 = _변이면(path, b"x = 2", CommandResult(2, _TSC_진단))

    assert measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None) == 0


_PLAYWRIGHT_실패 = """
  1) [chromium] › e2e/decision.spec.ts:10:5 › 결정 › 꺼짐이 버튼을 막는다

    Error: expect(locator).toBeDisabled() failed

  1 failed
    [chromium] › e2e/decision.spec.ts:10:5 › 결정 › 꺼짐이 버튼을 막는다
  6 passed (41.2s)
"""


@pytest.mark.parametrize(
    ("결과", "판정"),
    [
        (CommandResult(0, "Running 7 tests using 1 worker\n\n  7 passed (40.1s)\n"), "green"),
        (CommandResult(1, _PLAYWRIGHT_실패), "red"),
        (CommandResult(1, "Error: No tests found\n"), "error"),
        (CommandResult(1, "Error: Timed out waiting 120000ms from config.webServer.\n"), "error"),
        (CommandResult(0, "  1 skipped\n  6 passed (40.1s)\n"), "error"),
        (CommandResult(0, "  7 ok (40.1s)\n"), "error"),
    ],
    ids=["통과", "실패", "테스트_없음", "서버가_뜨지_않음", "skip_이_섞였다", "요약을_읽지_못함"],
)
def test_playwright_는_실패한_테스트가_셀_때만_빨강이다(결과: CommandResult, 판정: str) -> None:
    """`--grep` 은 고르지 않은 테스트를 skip 으로 세지 않으므로 skip 은 pytest 처럼 오류다."""
    assert judge(Judging("playwright"), 결과).outcome == 판정


def test_playwright_의_빨간_테스트는_실패_요약_아래에서_읽는다() -> None:
    assert judge(Judging("playwright"), CommandResult(1, _PLAYWRIGHT_실패)).failed == (
        "[chromium] › e2e/decision.spec.ts:10:5 › 결정 › 꺼짐이 버튼을 막는다",
    )


@pytest.mark.parametrize(
    ("판정자", "결과", "판정"),
    [
        ("vitest", CommandResult(1, "      Tests  1 failure | 2 passes (3)\n"), "error"),
        ("playwright", CommandResult(1, "  1 failure\n  6 passes (41.2s)\n"), "error"),
        ("tsc", CommandResult(2, "src/clients.test-d.ts:12:3 - error TS2578: Unused.\n"), "error"),
        (
            "vitest",
            CommandResult(
                1, "      Tests  1 failed | 2 passed (3)\n FAIL  broken.test.ts (수집 실패)\n"
            ),
            "red",
        ),
        ("playwright", CommandResult(0, "  1 skip\n  6 passed (40.1s)\n"), "green"),
        ("pytest", CommandResult(0, "2 passed, 1 skip in 0.10s\n"), "green"),
    ],
    ids=[
        "vitest_실패_문구",
        "playwright_실패_문구",
        "tsc_pretty_형식",
        "못_보는_것_vitest_파일_단위_표지",
        "못_보는_것_playwright_skip_문구",
        "못_보는_것_pytest_skip_문구",
    ],
)
def test_요약_문구가_바뀌면_읽는_문구는_오류로_기울고_거르는_표지는_못_보고_지나간다(
    판정자: JudgeName, 결과: CommandResult, 판정: str
) -> None:
    """도구의 판이 문구를 바꾼 모양을 흉내 낸다. 독스트링의 못 보는 것이 이 여섯이다(셀프 리뷰가
    "빨강으로 기울지는 않는다"의 반례 둘을 찾았다)."""
    assert judge(Judging(판정자, diagnostic_in="clients.test-d.ts"), 결과).outcome == 판정


def test_러너를_적은_변이는_그_명령에_tests_를_붙여_그_자리에서_돈다(tmp_path: Path) -> None:
    """기준선은 러너와 인자의 짝마다 한 번이다. 변이마다 테스트 이름으로 좁히면(`-t`) 좁힌 선택이
    초록인지를 그 짝의 기준선이 본다."""
    _파일을_둔다(tmp_path, "web/m.ts", b"x = 1\n")
    불린_것: list[tuple[tuple[str, ...], Path]] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        불린_것.append((tuple(argv), cwd))
        return CommandResult(0, "      Tests  1 passed (1)\n")

    변이 = (
        _VITEST_러너
        + _vitest_변이(name="하나", tests='["a.test.ts", "-t", "이름 하나"]')
        + _vitest_변이(name="둘", tests='["a.test.ts", "-t", "이름 하나"]')
        + _vitest_변이(name="셋", tests='["b.test.ts"]')
    )

    measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    기본 = ("pnpm", "exec", "vitest", "run")
    assert 불린_것[:2] == [
        ((*기본, "a.test.ts", "-t", "이름 하나"), tmp_path / "web"),
        ((*기본, "b.test.ts"), tmp_path / "web"),
    ]
    assert len(불린_것) == 5


def test_러너를_적지_않은_변이는_내장_pytest_로_저장소_루트에서_돈다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    불린_것: list[tuple[tuple[str, ...], Path]] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        불린_것.append((tuple(argv), cwd))
        return _초록

    measure(
        load_spec(_변이_파일(old="x = 1", new="x = 2", expect="green")),
        root=tmp_path,
        runner=러너,
        out=lambda _: None,
    )

    argv, cwd = 불린_것[0]
    assert argv[1:] == ("-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_x.py")
    assert cwd == tmp_path


def test_처리하지_않은_에러를_기대한_변이는_그것만으로_기대대로다(tmp_path: Path) -> None:
    """가드가 막는 것이 처리하지 않은 에러뿐이면 그 변이는 빨강도 오류도 아니다. 오류와 갈라 셀 수
    있어야 한다(대기열 59의 5회차, 셀 수 없던 가드 변이)."""
    path = _파일을_둔다(tmp_path, "web/m.ts", b"x = 1\n")
    줄: list[str] = []
    처리하지_않은 = CommandResult(1, "      Tests  3 passed (3)\n     Errors  1 error\n")
    변이 = _VITEST_러너 + _vitest_변이().replace('expect = "red"', 'expect = "unhandled"')

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return 처리하지_않은
        return CommandResult(0, "      Tests  3 passed (3)\n")

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=줄.append)

    assert code == 0
    assert any("처리하지 않은 에러" in 한줄 for 한줄 in 줄)
    assert any(한줄.startswith("   |") and "Errors  1 error" in 한줄 for 한줄 in 줄)


_EXIT_러너 = """
[runner.checker]
command = ["node", "check.mjs"]
judge = "exit"
red_exit = 1
"""


def _exit_변이(*, 줄: str = "") -> str:
    return f"""
[[mutation]]
name = "하나"
runner = "checker"
expect = "red"
{줄}
[[mutation.edit]]
file = "m.json"
old = 'x = 1'
new = 'x = 2'
"""


@pytest.mark.parametrize(
    ("결과", "판정"),
    [
        (CommandResult(0, "모두 맞다\n"), "green"),
        (CommandResult(1, "이름이 없다: a\n"), "red"),
        (CommandResult(2, "읽을 파일이 없다\n"), "error"),
        (CommandResult(1, "", timed_out_after=5), "error"),
    ],
    ids=["0", "빨강_코드", "다른_코드", "시간_제한"],
)
def test_종료_코드_판정은_0_이면_초록_적은_코드면_빨강_나머지는_오류다(
    결과: CommandResult, 판정: str
) -> None:
    """종료 코드로 말하는 검사기(node 검사기)는 그 도구의 판정이 없어 변이를 따로 지었다(대기열
    253). 읽을 파일이 없다는 2 를 빨강으로 세면 아무것도 재지 않은 변이가 기대와 맞는다."""
    판정_하나 = judge(Judging("exit", red_exit=1), 결과)

    assert 판정_하나.outcome == 판정
    if 결과.timed_out_after is None:
        assert 판정_하나.summary == 결과.output.strip()


def test_표지를_적은_변이는_기대대로여도_출력에_표지가_없으면_어긋난다(tmp_path: Path) -> None:
    """빨강만 보면 엉뚱한 까닭의 빨강도 기대와 맞는다(`.claude/rules/probes.md` 의 표지 항목).
    스토리 변이는 실패한 스토리를 셀 뿐 afterEach 의 빨강과 axe 의 빨강을 가르지 못했다(대기열
    253). 표지는 색 코드를 벗긴 출력에서 찾는다."""
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    줄: list[str] = []
    변이 = _EXIT_러너 + _exit_변이(줄='expect_output = ["이름이 없다: a", "둘째 표지"]')

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, "\x1b[31m이름이 없다:\x1b[0m a\n다른 까닭\n")
        return CommandResult(0, "모두 맞다\n")

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=줄.append)

    assert code == 1
    assert any(한줄.startswith("!! 어긋남") and "빨강" in 한줄 for 한줄 in 줄)
    assert any("표지 없음" in 한줄 and "둘째 표지" in 한줄 for 한줄 in 줄)
    assert not any("표지 없음" in 한줄 and "이름이 없다" in 한줄 for 한줄 in 줄)
    assert any(한줄.startswith("   |") and "다른 까닭" in 한줄 for 한줄 in 줄)
    assert path.read_bytes() == b"x = 1\n"


_코드_조각 = "".join(f" {번호} |   const a{번호} = {번호};\n" for 번호 in range(12))
_실패_머리가_끝_밖에_있는_출력 = (
    " FAIL  p.test.ts > 실패 한다\n"
    "AssertionError: expected 'yes' to be 'no' // Object.is equality\n"
    "- Expected\n"
    "+ Received\n"
    "- no\n"
    "+ yes\n"
    "    Expected: 'no'\n"
    "    Received: 'yes'\n"
    f"{_코드_조각}"
)


def _표지가_없는_변이의_출력(tmp_path: Path, 출력: str) -> list[str]:
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    줄: list[str] = []
    변이 = _EXIT_러너 + _exit_변이(줄='expect_output = ["없는 표지"]')

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, 출력)
        return CommandResult(0, "모두 맞다\n")

    measure(load_spec(변이), root=tmp_path, runner=러너, out=줄.append)
    return 줄


def test_표지가_없으면_끝_밖에_있는_실패_머리_줄도_보인다(tmp_path: Path) -> None:
    """vitest 의 끝 10줄은 마지막 실패 블록의 코드 조각이라 고른 단언의 머리가 안 보였다(대기열
    455). 머리 줄은 `AssertionError` 처럼 `Error` 로 끝나는 낱말·`Expected`·`Received`·diff 의
    `-`/`+` 줄이다."""
    줄 = _표지가_없는_변이의_출력(tmp_path, _실패_머리가_끝_밖에_있는_출력)

    assert "   | AssertionError: expected 'yes' to be 'no' // Object.is equality" in 줄
    assert {"   | - Expected", "   | + Received", "   | - no", "   | + yes"} <= set(줄)
    assert 줄.count("   |     Expected: 'no'") == 1  # 들여쓴 줄도 머리다
    assert 줄.count("   |     Received: 'yes'") == 1
    assert 줄.index("   | - Expected") < 줄.index("   |  2 |   const a2 = 2;")  # 머리가 끝 앞이다
    assert not any("const a0 " in 한줄 for 한줄 in 줄)  # 머리 줄이 아닌 코드 조각은 끝 밖이면 뺀다


def test_끝_10줄에_이미_든_머리_줄은_되풀이하지_않는다(tmp_path: Path) -> None:
    출력 = _실패_머리가_끝_밖에_있는_출력 + "Error: 마지막 줄의 머리\n"

    줄 = _표지가_없는_변이의_출력(tmp_path, 출력)

    assert 줄.count("   | Error: 마지막 줄의 머리") == 1
    assert 줄.count("   | AssertionError: expected 'yes' to be 'no' // Object.is equality") == 1


def test_머리_줄은_Errors_요약_같은_다른_낱말을_머리로_읽지_않는다(tmp_path: Path) -> None:
    출력 = "     Errors  1 error\n-\n" + "".join(f" {번호} |   x\n" for 번호 in range(12))

    줄 = _표지가_없는_변이의_출력(tmp_path, 출력)

    assert "   |      Errors  1 error" not in 줄


def test_머리_줄은_pytest_의_E_접두_줄을_머리로_읽지_않는다(tmp_path: Path) -> None:
    """모듈 독스트링의 못 보는 것: `E       TypeError: x` 는 줄 머리가 `E` 라 받지 않는다."""
    출력 = "E       TypeError: x\nE       assert 1 == 2\n" + "".join(
        f" {번호} |   x\n" for 번호 in range(12)
    )

    줄 = _표지가_없는_변이의_출력(tmp_path, 출력)

    assert not any("TypeError" in 한줄 or "assert 1 == 2" in 한줄 for 한줄 in 줄)


def test_머리_줄은_스무_줄까지만_보인다(tmp_path: Path) -> None:
    출력 = "".join(f"- 값 {번호}\n" for 번호 in range(50)) + "".join(
        f" {번호} |  x\n" for 번호 in range(12)
    )

    줄 = _표지가_없는_변이의_출력(tmp_path, 출력)

    assert sum(한줄.startswith("   | - 값 ") for 한줄 in 줄) == 20


def test_표지가_모두_있으면_머리_줄을_더하지_않는다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    줄: list[str] = []
    변이 = _EXIT_러너 + _exit_변이(줄='expect_output = ["AssertionError"]')

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, _실패_머리가_끝_밖에_있는_출력)
        return CommandResult(0, "모두 맞다\n")

    assert measure(load_spec(변이), root=tmp_path, runner=러너, out=줄.append) == 0
    assert not any(한줄.startswith("   |") for 한줄 in 줄)


def test_표지가_모두_있으면_기대대로다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    변이 = _EXIT_러너 + _exit_변이(줄='expect_output = ["이름이 없다: a"]')

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, "이름이 없다: a\n")
        return CommandResult(0, "모두 맞다\n")

    assert measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None) == 0


def test_못_보는_것_표지는_다른_까닭의_줄에_든_같은_문구로도_맞는다(tmp_path: Path) -> None:
    """표지는 부분 문자열로 찾아 출력의 어느 줄에 있든 맞는다(독스트링의 못 보는 것)."""
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    변이 = _EXIT_러너 + _exit_변이(줄='expect_output = ["이름이 없다: a"]')

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, "다른 검사: 이름이 없다: ab\n")
        return CommandResult(0, "모두 맞다\n")

    assert measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None) == 0


def test_반복하는_변이는_매번_표지가_있어야_한다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    변이 = _EXIT_러너 + _exit_변이(줄='expect_output = ["표지"]\nrepeat = 2')
    출력 = iter(["다른 것\n", "표지\n"])  # 빠진 회차가 마지막이면 마지막만 봐도 잡힌다

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, next(출력))
        return CommandResult(0, "모두 맞다\n")

    assert measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None) == 1


def test_기준선의_표지가_출력에_없으면_기준선은_초록이_아니고_변이를_넣지_않는다(
    tmp_path: Path,
) -> None:
    """종료 코드 0 만으로는 검사기가 아무것도 읽지 않고 끝난 것과 가를 수 없다. 옮겨 온 검사기
    프로브도 기준선의 집계 줄을 봤다."""
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    줄: list[str] = []
    변이_동안: list[bool] = []
    변이 = _EXIT_러너 + 'baseline_output = ["집계 줄"]\n' + _exit_변이()

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        변이_동안.append(b"x = 2" in path.read_bytes())
        return CommandResult(0, "아무것도 읽지 않았다\n")

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=줄.append)

    assert code == 1
    assert 변이_동안 == [False]
    assert any(한줄.startswith("기준선") and "표지 없음" in 한줄 for 한줄 in 줄)
    assert any("집계 줄" in 한줄 for 한줄 in 줄)
    assert "   | 아무것도 읽지 않았다" in 줄  # 초록이어도 표지가 없으면 출력의 끝을 보인다


def test_기준선의_표지가_있으면_변이로_간다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "m.json", b"x = 1\n")
    _파일을_둔다(tmp_path, "check.mjs", b"")
    변이 = _EXIT_러너 + 'baseline_output = ["집계 줄"]\n' + _exit_변이()

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, "이름이 없다\n")
        return CommandResult(0, "집계 줄: 9\n")

    assert measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None) == 0


def test_표지가_바뀌면_바뀐_변이다() -> None:
    옛 = load_spec(_EXIT_러너 + _exit_변이(줄='expect_output = ["가"]'))
    새_변이 = load_spec(_EXIT_러너 + _exit_변이(줄='expect_output = ["나"]'))
    새_러너 = load_spec(
        _EXIT_러너 + 'baseline_output = ["집계"]\n' + _exit_변이(줄='expect_output = ["가"]')
    )

    assert changed_names(옛, 새_변이) == ["하나"]
    assert changed_names(옛, 새_러너) == ["하나"]


@pytest.mark.parametrize(
    ("변이", "문구"),
    [
        (_EXIT_러너.replace("red_exit = 1\n", "") + _exit_변이(), "red_exit"),
        (_VITEST_러너 + "red_exit = 1\n" + _vitest_변이(), "red_exit"),
        (_EXIT_러너.replace("red_exit = 1", "red_exit = 0") + _exit_변이(), "red_exit"),
        (_EXIT_러너 + _exit_변이(줄='expect_output = [""]'), "expect_output"),
        (_EXIT_러너 + 'baseline_output = [""]\n' + _exit_변이(), "baseline_output"),
    ],
    ids=["빨강_코드가_없다", "빨강_코드는_exit_만", "빨강_코드가_0", "빈_표지", "빈_기준선_표지"],
)
def test_종료_코드_판정과_표지의_짝이_틀리면_변이_파일_오류다(변이: str, 문구: str) -> None:
    """빈 표지는 어느 출력에나 있어 아무것도 가르지 않는다."""
    with pytest.raises(SpecError, match=문구):
        load_spec(변이)


@pytest.mark.parametrize(
    ("변이", "문구"),
    [
        (_vitest_변이(), "vitest"),
        (
            _VITEST_러너.replace("[runner.vitest]", "[runner.pytest]")
            + _변이_파일(old="x", new="y"),
            "내장",
        ),
        (
            _VITEST_러너.replace('judge = "vitest"', 'judge = "tsc"') + _vitest_변이(),
            "diagnostic_in",
        ),
        (_VITEST_러너 + _vitest_변이(줄='diagnostic_in = "a.ts"'), "diagnostic_in"),
        (_변이_파일(old="x", new="y", expect="unhandled"), "unhandled"),
        (_VITEST_러너.replace('judge = "vitest"', 'judge = "jest"') + _vitest_변이(), "judge"),
        (
            _VITEST_러너.replace('["pnpm", "exec", "vitest", "run"]', "[]") + _vitest_변이(),
            "command",
        ),
    ],
    ids=[
        "없는_러너",
        "pytest_는_내장이다",
        "tsc_는_진단_자리가_있어야",
        "진단_자리는_tsc_만",
        "처리하지_않은_에러는_vitest_만",
        "모르는_판정",
        "빈_명령",
    ],
)
def test_러너와_판정이_맞지_않으면_변이_파일_오류다(변이: str, 문구: str) -> None:
    with pytest.raises(SpecError, match=문구):
        load_spec(변이)


def test_러너의_자리가_저장소_밖이거나_없으면_변이_파일_오류다(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _파일을_둔다(root, "web/m.ts", b"x = 1\n")

    for 자리 in ("../elsewhere", "없는_자리"):
        (tmp_path / "elsewhere").mkdir(exist_ok=True)
        변이 = _VITEST_러너.replace('cwd = "web"', f'cwd = "{자리}"') + _vitest_변이()
        with pytest.raises(SpecError, match=자리.lstrip("./")):
            measure(load_spec(변이), root=root, runner=_부르면_안_되는_러너, out=lambda _: None)


def test_되돌릴_파일은_편집하지_않아도_돌린_뒤에_원래_바이트로_돌아온다(tmp_path: Path) -> None:
    """변이가 명령에게 파일을 고쳐 쓰게 하면(최신성 검사가 생성물을 덮어쓰는 변이) 그 파일도
    쥔다."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    생성물 = _파일을_둔다(tmp_path, "gen/out.ts", b"generated\r\n")
    쓰기_전: list[bytes] = []

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" not in path.read_bytes():
            return _초록
        쓰기_전.append(생성물.read_bytes())
        생성물.write_bytes(b"overwritten")
        return _빨강

    변이 = _변이_파일(old="x = 1", new="x = 2").replace(
        'expect = "red"', 'expect = "red"\nrestore = ["gen/out.ts"]'
    )

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert code == 0
    assert 쓰기_전 == [b"generated\r\n"]
    assert 생성물.read_bytes() == b"generated\r\n"
    assert path.read_bytes() == b"x = 1\n"


@pytest.mark.parametrize("자리", ["gen/없다.ts", "../outside.ts"], ids=["없다", "저장소_밖"])
def test_되돌릴_파일이_없거나_저장소_밖이면_변이_파일_오류다(tmp_path: Path, 자리: str) -> None:
    root = tmp_path / "repo"
    _파일을_둔다(root, "src/m.py", b"x = 1\n")
    _파일을_둔다(tmp_path, "outside.ts", b"x\n")
    변이 = _변이_파일(old="x = 1", new="x = 2").replace(
        'expect = "red"', f'expect = "red"\nrestore = ["{자리}"]'
    )

    with pytest.raises(SpecError, match="되돌릴"):
        measure(load_spec(변이), root=root, runner=_부르면_안_되는_러너, out=lambda _: None)


def _쓰기를_막는다(
    monkeypatch: pytest.MonkeyPatch,
    막을_파일: Path,
    막을_때: Callable[[bytes], bool],
    *,
    남는_앞부분: int = 0,
    번호: int = errno.EACCES,
) -> None:
    """그 파일에 `막을_때` 가 참인 바이트를 쓰면 앞의 `남는_앞부분` 바이트만 쓰고(0 이면 아무것도
    쓰지 않고) 오류 번호가 `번호` 인 `OSError` 를 낸다. 기본은 `PermissionError` 다.

    권한(`chmod` 읽기 전용)으로 막으면 root(uid 0)는 쓰기가 통해, 클라우드 컨테이너에서 되돌림 실패
    테스트 셋이 빨갰다(대기열 80, `.scratch/harness/probes/mutate_as_root.sh`).
    """
    원래_쓰기 = Path.write_bytes

    def 막힌_쓰기(self: Path, data: bytes) -> int:
        if self.resolve() == 막을_파일.resolve() and 막을_때(data):
            if 남는_앞부분:
                원래_쓰기(self, data[:남는_앞부분])
            raise OSError(번호, "쓰기를 막았다", str(self))
        return 원래_쓰기(self, data)

    monkeypatch.setattr(Path, "write_bytes", 막힌_쓰기)


def _잠그는_러너(잠글_파일: Path, 표지: bytes, monkeypatch: pytest.MonkeyPatch) -> 러너:
    """변이가 든 동안 그 파일의 쓰기를 막아, 되돌리는 쓰기가 `PermissionError` 가 되게 한다. 다시
    시도하는 수는 그대로 두고 기다림만 없앤다."""
    monkeypatch.setattr("tools.mutate.RESTORE_WAITS", tuple(0.0 for _ in RESTORE_WAITS))

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if 표지 not in 잠글_파일.read_bytes():
            return _초록
        _쓰기를_막는다(monkeypatch, 잠글_파일, lambda _: True)
        return _빨강

    return 러너


def _두_파일_변이(tmp_path: Path) -> tuple[Path, Path, str]:
    m = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    a = _파일을_둔다(tmp_path, "src/a.py", b"a = 1\n")
    변이 = _변이_파일(old="x = 1", new="x = 2") + "\n".join(
        ["[[mutation.edit]]", 'file = "src/a.py"', "old = 'a = 1'", "new = 'a = 2'", ""]
    )
    return m, a, 변이


def test_되돌리지_못한_파일이_있으면_RestoreError_이고_나머지는_되돌린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """되돌림 실패를 명세 오류로 알리면 변이된 채 남은 파일을 아무도 모른다(셀프 리뷰 Major)."""
    m, a, 변이 = _두_파일_변이(tmp_path)

    with pytest.raises(RestoreError, match="src/m.py.*쓰기를 막았다"):
        measure(
            load_spec(변이),
            root=tmp_path,
            runner=_잠그는_러너(m, b"x = 2", monkeypatch),
            out=lambda _: None,
        )

    assert a.read_bytes() == b"a = 1\n"
    assert m.read_bytes() == b"x = 2\n"


def _처음_몇_번만(횟수: int, 막을_바이트: bytes) -> tuple[Callable[[bytes], bool], list[bytes]]:
    """`막을_바이트` 를 쓰는 처음 `횟수` 번만 참인 판정과, 참이었던 바이트의 기록."""
    막은: list[bytes] = []

    def 막을_때(data: bytes) -> bool:
        if data != 막을_바이트 or len(막은) >= 횟수:
            return False
        막은.append(data)
        return True

    return 막을_때, 막은


def test_되돌리는_쓰기가_잠깐_막히면_기다렸다가_다시_써서_되돌린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """변이 87번째를 되돌리는 쓰기가 `[Errno 22] Invalid argument` 로 한 번 막혀 종료 3으로 멈추고
    변이가 도구 파일에 남았다(대기열 267). 무엇이 그 틈에 파일을 쥐었는지는 재지 않았다."""
    monkeypatch.setattr("tools.mutate.RESTORE_WAITS", (0.2, 0.2, 0.2))
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    막을_때, 막은 = _처음_몇_번만(2, b"x = 1\n")
    _쓰기를_막는다(monkeypatch, path, 막을_때, 번호=errno.EINVAL)
    줄: list[str] = []
    시작 = time.monotonic()

    code = measure(
        load_spec(_변이_파일(old="x = 1", new="x = 2")),
        root=tmp_path,
        runner=_변이면(path, b"x = 2", _빨강),
        out=줄.append,
    )

    assert code == 0
    assert path.read_bytes() == b"x = 1\n"
    assert len(막은) == 2
    # 시계의 해상도(이 PC 15.6ms)를 두고 0.2초 두 번보다 낮게 잡는다
    assert time.monotonic() - 시작 >= 0.3  # 막힐 때마다 기다렸다
    # 무엇이 그 틈에 파일을 쥐는지 다음에 잴 흔적
    assert any(
        "src/m.py — 2번 막혔다가 지났다" in 한줄 and "Errno 22" in 한줄 and "쓰기를 막았다" in 한줄
        for 한줄 in 줄
    ), 줄


def test_되돌리다_막혀_앞부분만_쓴_파일은_다시_쓸_때_다른_쓰기로_보지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """다른 쓰기는 처음 읽은 바이트로 한 번만 본다. 쓰다 막힌 뒤의 파일은 이 도구가 쓴 앞부분이라,
    다시 쓸 때마다 보면 일시적인 막힘이 덮지 않는 실패가 된다."""
    monkeypatch.setattr("tools.mutate.RESTORE_WAITS", (0.0,))
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    막을_때, 막은 = _처음_몇_번만(1, b"x = 1\n")
    _쓰기를_막는다(monkeypatch, path, 막을_때, 남는_앞부분=2, 번호=errno.EINVAL)

    code = measure(
        load_spec(_변이_파일(old="x = 1", new="x = 2")),
        root=tmp_path,
        runner=_변이면(path, b"x = 2", _빨강),
        out=lambda _: None,
    )

    assert code == 0
    assert 막은 == [b"x = 1\n"]
    assert path.read_bytes() == b"x = 1\n"


def test_못_보는_것_되돌리는_쓰기를_다시_시도하는_사이에_든_다른_쓰기는_덮는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """다른 쓰기는 처음 읽은 바이트로 한 번만 보므로, 쓰기가 막혀 기다리는 사이에 든 쓰기는 다시 쓸
    때 사라진다(독스트링의 못 보는 것, 셀프 리뷰 명세 축)."""
    monkeypatch.setattr("tools.mutate.RESTORE_WAITS", (0.0,))
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    끼운_뒤: list[bytes] = []

    def 다른_쓰기를_끼우고_한_번_막는다(data: bytes) -> bool:
        if data != b"x = 1\n" or 끼운_뒤:
            return False
        with path.open("ab") as f:  # 기다리는 사이 편집기가 저장했다
            f.write(b"# doc\n")
        끼운_뒤.append(path.read_bytes())
        return True

    _쓰기를_막는다(monkeypatch, path, 다른_쓰기를_끼우고_한_번_막는다, 번호=errno.EINVAL)

    code = measure(
        load_spec(_변이_파일(old="x = 1", new="x = 2")),
        root=tmp_path,
        runner=_변이면(path, b"x = 2", _빨강),
        out=lambda _: None,
    )

    assert code == 0
    assert 끼운_뒤 == [b"x = 2\n# doc\n"]
    assert path.read_bytes() == b"x = 1\n"


def test_되돌리는_쓰기가_끝내_막히면_기다림_수보다_한_번_더_시도하고_멈춘다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tools.mutate.RESTORE_WAITS", (0.0, 0.0))
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    막을_때, 막은 = _처음_몇_번만(99, b"x = 1\n")
    _쓰기를_막는다(monkeypatch, path, 막을_때, 번호=errno.EINVAL)

    with pytest.raises(RestoreError, match=r"src/m.py \(3번 막혔다: .*쓰기를 막았다"):
        measure(
            load_spec(_변이_파일(old="x = 1", new="x = 2")),
            root=tmp_path,
            runner=_변이면(path, b"x = 2", _빨강),
            out=lambda _: None,
        )

    assert len(막은) == 3
    assert path.read_bytes() == b"x = 2\n"


def test_막혔다가_지난_줄은_모두_되쓴_뒤에_내서_출력이_끊겨도_남은_파일을_되돌린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """출력이 줄 버퍼라 닫힌 파이프(`| head`)의 쓰기 오류가 그 줄을 내는 자리에서 난다. 되쓰는
    도중에 내면 뒤 파일이 변이된 채 남고, `main` 은 "변이는 되돌렸다" 고 거짓으로 알린다(PR 직전
    버그 리뷰)."""
    monkeypatch.setattr("tools.mutate.RESTORE_WAITS", (0.0,))
    m, a, 변이 = _두_파일_변이(tmp_path)
    막을_때, _ = _처음_몇_번만(1, b"x = 1\n")
    _쓰기를_막는다(monkeypatch, m, 막을_때, 번호=errno.EINVAL)

    def 끊긴_출력(줄: str) -> None:
        if 줄.startswith("되돌리기:"):
            raise BrokenPipeError(32, "파이프가 닫혔다")

    with pytest.raises(BrokenPipeError):
        measure(load_spec(변이), root=tmp_path, runner=_변이면(m, b"x = 2", _빨강), out=끊긴_출력)

    assert m.read_bytes() == b"x = 1\n"
    assert a.read_bytes() == b"a = 1\n"


def test_되쓰는_동안_끊겨도_남은_파일을_마저_되쓰고_끊긴_파일을_알린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """다시 시도하며 기다리는 동안(최대 3.7초) Ctrl+C 가 오면 뒤 파일을 되쓰지 않고 목록도 없이
    끝났다(PR 직전 버그 리뷰). 변이가 도구 파일에 남는 것은 대기열 267 이 막으려던 것이다."""
    m, a, 변이 = _두_파일_변이(tmp_path)
    _쓰기를_막는다(monkeypatch, m, lambda data: data == b"x = 1\n", 번호=errno.EINVAL)

    def 기다리다_끊긴다(_: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", 기다리다_끊긴다)

    # 놓친 Ctrl+C 는 pytest 전체를 멈추므로 함께 잡아 무엇이 나왔는지 단언한다
    with pytest.raises((RestoreError, KeyboardInterrupt)) as 잡힌:
        measure(load_spec(변이), root=tmp_path, runner=_변이면(m, b"x = 2", _빨강), out=print)

    assert isinstance(잡힌.value, RestoreError), repr(잡힌.value)
    assert "src/m.py (되쓰는 동안 끊겼다)" in str(잡힌.value)
    assert m.read_bytes() == b"x = 2\n"
    assert a.read_bytes() == b"a = 1\n"


def test_변이가_든_동안_다른_쓰기가_들어온_파일은_덮지_않고_알린다(tmp_path: Path) -> None:
    """되돌림이 변이 전 바이트를 그대로 쓰면 도는 동안 고친 것이 조용히 사라진다. 변이가 도는 동안
    더한 훅 독스트링 한 문장이 그렇게 사라졌다(대기열 77). 나머지 파일은 되돌린다."""
    m, a, 변이 = _두_파일_변이(tmp_path)

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" not in m.read_bytes():
            return _초록
        m.write_bytes(m.read_bytes() + b"# doc\n")  # 도는 동안 편집기가 저장했다
        return _빨강

    with pytest.raises(RestoreError, match="src/m.py.*다른 쓰기"):
        measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert m.read_bytes() == b"x = 2\n# doc\n"
    assert a.read_bytes() == b"a = 1\n"


def test_되돌릴_파일로_적은_편집_파일은_명령이_고쳐_써도_되돌린다(tmp_path: Path) -> None:
    """`restore` 는 명령이 고쳐 쓰는 파일이다. 그 쓰기는 다른 쓰기와 가를 수 없어 보지 않는다."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" not in path.read_bytes():
            return _초록
        path.write_bytes(b"x = 2\n# generated\n")
        return _빨강

    변이 = _변이_파일(old="x = 1", new="x = 2").replace(
        'expect = "red"', 'expect = "red"\nrestore = ["src/m.py"]'
    )

    code = measure(load_spec(변이), root=tmp_path, runner=러너, out=lambda _: None)

    assert code == 0
    assert path.read_bytes() == b"x = 1\n"


def test_변이를_쓰지_못한_파일은_다른_쓰기로_보지_않고_되돌린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """변이 바이트를 쓰다 실패한 파일은 쓰다 만 앞부분이 남아도 도구가 마지막으로 쓴 것이다. 그것을
    다른 쓰기로 알리면 쓰지 못한 원인이 가려지고 그 파일이 쓰다 만 채로 남는다."""
    m, a, 변이 = _두_파일_변이(tmp_path)
    _쓰기를_막는다(monkeypatch, a, lambda data: data == b"a = 2\n", 남는_앞부분=3)

    with pytest.raises(PermissionError):
        measure(
            load_spec(변이),
            root=tmp_path,
            runner=_변이면(m, b"x = 2", _빨강),
            out=lambda _: None,
        )

    assert m.read_bytes() == b"x = 1\n"
    assert a.read_bytes() == b"a = 1\n"


def test_못_보는_것_앞_파일의_변이_쓰기가_실패하면_아직_쓰지_않은_파일에_든_쓰기는_덮는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """변이를 쓰지 못한 파일은 쓴 변이 바이트가 없어 보지 않고 되돌린다. 처음 읽은 뒤 되돌리기까지의
    틈에 든 쓰기는 사라진다. 앞 파일의 쓰기가 실패하면 곧바로 되돌리므로 그 틈은 짧다(독스트링의 못
    보는 것, PR #115 claude-review)."""
    m, a, 변이 = _두_파일_변이(tmp_path)
    끼운_뒤: list[bytes] = []

    def 다른_쓰기를_끼우고_막는다(data: bytes) -> bool:
        if data != b"x = 2\n":
            return False
        with a.open("ab") as f:  # m 의 변이를 쓰는 사이 a 에 다른 쓰기가 든다
            f.write(b"# doc\n")
        끼운_뒤.append(a.read_bytes())
        return True

    _쓰기를_막는다(monkeypatch, m, 다른_쓰기를_끼우고_막는다)

    with pytest.raises(PermissionError):
        measure(
            load_spec(변이),
            root=tmp_path,
            runner=_변이면(m, b"x = 2", _빨강),
            out=lambda _: None,
        )

    assert 끼운_뒤 == [b"a = 1\n# doc\n"]
    assert a.read_bytes() == b"a = 1\n"


def _변이_파일을_쓴다(tmp_path: Path, 내용: str) -> str:
    path = tmp_path / "mutations.toml"
    path.write_text(내용, encoding="utf-8")
    return str(path)


def test_main_은_변이_파일을_읽지_못하면_아무것도_돌리지_않고_2다(tmp_path: Path) -> None:
    """UTF-8 이 아닌 변이 파일이 트레이스백의 1 이 되면 어긋남의 1 과 구별되지 않는다."""
    깨진_파일 = tmp_path / "broken.toml"
    깨진_파일.write_bytes(b'name = "\xff"\n')
    _파일을_둔다(tmp_path, "src/m.py", b"y = 1\n")
    원문_없음 = _변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2"))

    for argv in ([], ["--check"], [str(tmp_path / "없다.toml")], [str(깨진_파일)], [원문_없음]):
        code = main(argv, root=tmp_path, runner=_부르면_안_되는_러너, out=lambda _: None)
        assert code == 2, argv


def test_main_은_모르는_선택을_변이_이름으로_읽지_않고_알린다(tmp_path: Path) -> None:
    """`--chek` 이 변이 이름이 되면 "없는 이름" 으로 끝나 무엇을 잘못 쳤는지 가려진다."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    경로 = _변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2"))
    줄: list[str] = []

    code = main([경로, "--chek"], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append)

    assert code == 2
    assert any("모르는 선택: --chek" in 한줄 for 한줄 in 줄)
    assert any("번호(따옴표 없이" in 한줄 for 한줄 in 줄), 줄


def test_main_은_기대대로면_0_어긋나면_1이다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    변이 = _변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2"))

    assert main([변이], root=tmp_path, runner=_변이면(path, b"x = 2", _빨강), out=print) == 0
    assert main([변이], root=tmp_path, runner=_변이면(path, b"x = 2", _초록), out=print) == 1


def test_원문만_보면_명령을_돌리지_않고_틀린_원문을_모두_알린다(tmp_path: Path) -> None:
    """리팩터 한 번에 다른 러너의 원문 19가 조용히 옮겨 갔고, 돌리기 전에는 아무도 몰랐다(대기열
    59의 4회차). 첫 틀림에서 멈추면 열아홉을 한 번에 고칠 수 없다."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\ny = 1\ny = 1\n")
    변이 = (
        _변이_파일(old="x = 1", new="x = 2")
        + _변이_파일(old="z = 1", new="z = 2").replace("하나", "둘")
        + _변이_파일(old="y = 1", new="y = 2").replace("하나", "셋")
    )
    경로 = _변이_파일을_쓴다(tmp_path, 변이)
    줄: list[str] = []

    code = main(["--check", 경로], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append)

    assert code == 2
    assert any("둘:" in 한줄 and "0번" in 한줄 for 한줄 in 줄)
    assert any("셋:" in 한줄 and "2번" in 한줄 for 한줄 in 줄)
    assert not any("하나:" in 한줄 for 한줄 in 줄)
    assert not any("줄 끝이 다르다" in 한줄 for 한줄 in 줄)  # 두 번인 원문은 줄 끝 탓이 아니다
    # 표 하나만 넘겨도 어느 표가 틀렸는지 보인다
    assert all(한줄.startswith(f"{경로}: ") for 한줄 in 줄)


def test_원문만_보아_모두_맞으면_0이고_파일을_건드리지_않는다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    경로 = _변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2", expect="green"))
    줄: list[str] = []

    code = main(
        [경로, "--check", "하나"], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append
    )

    assert code == 0
    assert path.read_bytes() == b"x = 1\n"
    assert any("1" in 한줄 and "한 번" in 한줄 for 한줄 in 줄)


_이_도구 = "tools/mutate.py"


def _표를_쓴다(tmp_path: Path, 이름: str, 내용: str) -> str:
    path = tmp_path / 이름
    path.write_text(내용, encoding="utf-8")
    return str(path)


def test_원문만_볼_때는_변이_파일_여럿을_받아_틀린_파일을_가리킨다(tmp_path: Path) -> None:
    """변이 표 여럿을 한 번에 넘길 수 있다. 옛 pre-commit 이 커밋에 든 표를 이 모양으로
    넘겼다(대기열
    92. 지금은 `--staged` 를 띄운다). 앞 파일에서 멈추면 뒤 파일을 못 본다."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    맞는 = _표를_쓴다(tmp_path, "a_mutations.toml", _변이_파일(old="x = 1", new="x = 2"))
    틀린 = _표를_쓴다(tmp_path, "b_mutations.toml", _변이_파일(old="z = 1", new="z = 2"))
    줄: list[str] = []

    code = main(["--check", 틀린, 맞는], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append)

    assert code == 2
    assert any(틀린 in 한줄 and "0번" in 한줄 for 한줄 in 줄)
    assert any(맞는 in 한줄 and "한 번" in 한줄 for 한줄 in 줄)
    assert not any(맞는 in 한줄 and "!!" in 한줄 for 한줄 in 줄)


def test_원문만_볼_때_읽지_못한_변이_파일이_있어도_나머지_파일을_본다(tmp_path: Path) -> None:
    깨진 = tmp_path / "broken_mutations.toml"
    깨진.write_bytes(b'name = "\xff"\n')
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    틀린 = _표를_쓴다(tmp_path, "b_mutations.toml", _변이_파일(old="z = 1", new="z = 2"))
    줄: list[str] = []

    code = main(
        ["--check", str(깨진), 틀린], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append
    )

    assert code == 2
    assert any(str(깨진) in 한줄 for 한줄 in 줄)
    assert any(틀린 in 한줄 and "0번" in 한줄 for 한줄 in 줄)


def test_원문만_볼_때_여러_줄인_진단도_줄마다_표의_경로를_붙인다(tmp_path: Path) -> None:
    """변이 파일 오류는 문제를 줄바꿈으로 잇는다. 첫 줄에만 붙으면 표 여럿을 함께 볼 때 둘째 줄부터
    출처가 없다(PR #122 CodeRabbit)."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    러너_둘_없음 = _변이_파일(old="x = 1", new="x = 2").replace(
        'tests = ["tests/test_x.py"]', 'runner = "없다"\ntests = ["tests/test_x.py"]'
    )
    둘 = 러너_둘_없음 + 러너_둘_없음.replace('name = "하나"', 'name = "둘"')
    깨진 = _표를_쓴다(tmp_path, "a_mutations.toml", 둘)
    맞는 = _표를_쓴다(tmp_path, "b_mutations.toml", _변이_파일(old="x = 1", new="x = 2"))
    줄: list[str] = []

    code = main(["--check", 깨진, 맞는], root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append)

    출력 = "\n".join(줄).splitlines()
    assert code == 2
    assert sum("러너 없다" in 한줄 for 한줄 in 출력) == 2
    assert all(한줄.startswith((f"{깨진}: ", f"{맞는}: ")) for 한줄 in 출력)


def test_원문만_볼_때_변이_파일_여럿이_모두_맞으면_0이다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\ny = 1\n")
    가 = _표를_쓴다(tmp_path, "a_mutations.toml", _변이_파일(old="x = 1", new="x = 2"))
    나 = _표를_쓴다(tmp_path, "b_mutations.toml", _변이_파일(old="y = 1", new="y = 2"))

    code = main(["--check", 가, 나], root=tmp_path, runner=_부르면_안_되는_러너, out=print)

    assert code == 0


def test_변이_파일_여럿은_원문_확인에서만_받고_이름과_섞지_않는다(tmp_path: Path) -> None:
    """변이를 돌리는 것은 표 하나씩이다. 이름은 어느 표의 것인지 가를 수 없다."""
    _파일을_둔다(tmp_path, "src/m.py", b"x = 1\ny = 1\n")
    가 = _표를_쓴다(tmp_path, "a_mutations.toml", _변이_파일(old="x = 1", new="x = 2"))
    나 = _표를_쓴다(tmp_path, "b_mutations.toml", _변이_파일(old="y = 1", new="y = 2"))

    for argv in ([가, 나], ["--check", 가, 나, "하나"], ["--check", 가, 나, "--since", "HEAD"]):
        줄: list[str] = []
        code = main(argv, root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append)
        assert code == 2, argv
        assert any("변이 파일 여럿" in 한줄 for 한줄 in 줄), argv


def test_pre_commit_처럼_띄우면_틀린_표의_경로를_UTF_8_로_알린다(tmp_path: Path) -> None:
    """옛 pre-commit 은 표 경로를 인자 끝에 붙여 띄웠다(지금은 `--staged`). 훅 환경에 `PYTHONUTF8`
    이 있다고 가정하지 않는다 — 없으면 윈도우의 파이프는 cp949 라 한국어 출력이 깨지거나 인코딩
    오류로 끝난다. 자식의 `PYTHONIOENCODING` 을 cp949 로 두어, 로캘이 UTF-8 인 곳(리눅스 CI)에서도
    다시 열기를 빼면 빨갛게 한다(PR #122 CodeRabbit)."""
    맞는 = _표를_쓴다(
        tmp_path,
        "a_mutations.toml",
        _변이_파일(
            old="ROOT = Path(__file__).resolve().parent.parent", new="ROOT = Path()", file=_이_도구
        ),
    )
    틀린 = _표를_쓴다(
        tmp_path,
        "b_mutations.toml",
        _변이_파일(old="없는 원문 — 대기열 92", new="x", file=_이_도구).replace(
            "하나", "틀린 — 표"
        ),
    )

    done = subprocess.run(
        [sys.executable, "tools/mutate.py", "--check", 맞는, 틀린],
        cwd=ROOT,
        capture_output=True,
        env={**hook_environment(), "PYTHONIOENCODING": "cp949"},
        check=False,
        timeout=60,
    )
    stdout = done.stdout.decode("utf-8")

    assert done.returncode == 2, done.stderr.decode("utf-8", "replace")
    assert "틀린 — 표" in stdout
    assert 틀린 in stdout


_표_경로 = "probes/m_mutations.toml"
# 초록을 기대해 표지 없는 빨강의 알림(대기열 350)에 걸리지 않는다. 이 절의 시험은 원문만 본다
_맞는_표 = _변이_파일(old="x = 1", new="x = 2", expect="green")
_깬_커밋 = "부모 판에서 맞던 원문을 이 커밋이 깼다"


def _저장소(tmp_path: Path, 파일들: dict[str, str]) -> Path:
    """`tmp_path` 를 main 브랜치의 저장소로 만들어 `파일들` 을 커밋한다."""
    for 경로, 내용 in 파일들.items():
        _파일을_둔다(tmp_path, 경로, 내용.encode("utf-8"))
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "처음")
    return tmp_path


def _스테이지한다(root: Path, 상대_경로: str, 내용: bytes) -> None:
    _파일을_둔다(root, 상대_경로, 내용)
    _git(root, "add", 상대_경로)


def _색인_확인(root: Path) -> tuple[int, str]:
    줄: list[str] = []
    code = main(["--staged"], root=root, runner=_부르면_안_되는_러너, out=줄.append)
    return code, "\n".join(줄)


def test_색인_확인은_부모_판에서_맞던_원문을_이_커밋이_깨면_표가_커밋에_들지_않아도_알린다(
    tmp_path: Path,
) -> None:
    """표가 가리키는 코드만 바뀌고 표는 커밋에 들지 않으면, 커밋에 든 표만 보던 확인이 지나가
    원문이 0번인 표가 남았다(대기열 312)."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", _표_경로: _맞는_표})
    _스테이지한다(root, "src/m.py", b"x = 9\n")

    code, 출력 = _색인_확인(root)

    assert code == 2
    assert f"{_표_경로}: !! 하나: src/m.py 에 원문이 0번 있다" in 출력
    assert _깬_커밋 in 출력


def test_색인_확인은_부모_판에서도_맞지_않던_원문은_알리지_않는다(tmp_path: Path) -> None:
    """이 커밋 전부터 썩은 옛 표의 원문은 썩어도 된다(대기열 73·92). 표가 가리키는 파일을 고쳐도
    그 원문은 이 커밋이 깬 것이 아니다."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", _표_경로: _변이_파일(old="z = 1", new="z")})
    _스테이지한다(root, "src/m.py", b"x = 9\n")

    code, 출력 = _색인_확인(root)

    assert code == 0, 출력
    assert "문제 0" in 출력


def test_색인_확인은_표가_가리키지_않는_파일만_고친_커밋에서_변이를_보지_않는다(
    tmp_path: Path,
) -> None:
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", "src/o.py": "o = 1\n", _표_경로: _맞는_표})
    _스테이지한다(root, "src/o.py", b"o = 2\n")

    code, 출력 = _색인_확인(root)

    assert code == 0, 출력
    assert "커밋에 든 표 0, 고친 파일을 가리키는 다른 표의 변이 0, 문제 0" in 출력


def test_색인_확인은_커밋에_든_표의_원문을_모두_본다(tmp_path: Path) -> None:
    """고치거나 더한 표는 이 커밋이 고친 파일과 상관없이 모든 원문을 본다(대기열 92)."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n"})
    둘 = _변이_파일(old="z = 1", new="z = 2", expect="green").replace('"하나"', '"둘"')
    _스테이지한다(root, _표_경로, (_맞는_표 + 둘).encode("utf-8"))

    code, 출력 = _색인_확인(root)

    assert code == 2
    assert f"{_표_경로}: !! 둘: src/m.py 에 원문이 0번 있다" in 출력
    assert "!! 하나" not in 출력
    assert _깬_커밋 not in 출력


_읽히지_않는_표 = "[[mutation]]\nname = 1\n"


def test_색인_확인은_커밋에_든_표가_변이_파일로_읽히지_않으면_알린다(tmp_path: Path) -> None:
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n"})
    _스테이지한다(root, _표_경로, _읽히지_않는_표.encode("utf-8"))

    code, 출력 = _색인_확인(root)

    assert code == 2
    assert f"{_표_경로}: !! 변이 파일 오류" in 출력


def test_색인_확인은_커밋에_들지_않은_표가_읽히지_않아도_알리지_않는다(tmp_path: Path) -> None:
    """읽히지 않는 옛 표는 이 커밋이 깬 것이 아니다. 도구의 형식이 바뀌어 옛 표가 읽히지 않는 것은
    저장소 상태 시험(`test_이_저장소의_변이_파일은_지금의_도구로_모두_읽힌다`)이 본다."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", _표_경로: _읽히지_않는_표})
    _스테이지한다(root, "src/m.py", b"x = 9\n")

    code, 출력 = _색인_확인(root)

    assert code == 0, 출력
    assert "커밋에 든 표 0, 고친 파일을 가리키는 다른 표의 변이 0, 문제 0" in 출력


def test_색인_확인은_작업_트리가_아니라_커밋에_들_색인을_본다(tmp_path: Path) -> None:
    """pre-commit 은 스테이지하지 않은 변경을 치워 두고 돌지만, 손으로 쳐도 커밋에 들 판을 본다."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", _표_경로: _맞는_표})
    _스테이지한다(root, "src/m.py", b"x = 9\n")
    _파일을_둔다(root, "src/m.py", b"x = 1\n")

    assert _색인_확인(root)[0] == 2

    _git(root, "add", "src/m.py")
    _파일을_둔다(root, "src/m.py", b"x = 9\n")

    assert _색인_확인(root)[0] == 0


@pytest.mark.parametrize(
    "명령",
    [
        ("rm", "-q", "src/m.py"),
        ("mv", "src/m.py", "src/n.py"),
        ("rm", "-q", "--cached", "src/m.py"),
    ],
    ids=["지운다", "옮긴다", "추적만_끊는다"],
)
def test_색인_확인은_원문이_든_파일을_지우거나_옮긴_커밋도_알린다(
    tmp_path: Path, 명령: tuple[str, ...]
) -> None:
    """pre-commit 은 지운 파일을 훅에 넘기지 않고, 옮긴 파일은 새 이름만 넘긴다. 추적만 끊은 파일은
    작업 트리에 그대로 있어도 커밋에 들 판에 없다."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", _표_경로: _맞는_표})
    _git(root, *명령)

    code, 출력 = _색인_확인(root)

    assert code == 2
    assert "하나: src/m.py 를 읽지 못했다" in 출력
    assert _깬_커밋 in 출력


def test_색인_확인은_어느_판도_추적하지_않는_파일을_작업_트리에서_읽는다(tmp_path: Path) -> None:
    """변이 표가 추적하지 않는 생성물을 가리키면(design-card-build 티켓 04 가 지운
    `.scratch/design-refresh/probes/checker_mutations.toml` 이 `ds-bundle/` 을 가리켰다), 옛
    `--check` 처럼 그 파일이 있는 체크아웃에서 작업 트리를 읽는다. 색인만 읽으면 그 표를 고친 커밋이
    생성물이 있는 체크아웃에서도 막혔다."""
    root = _저장소(tmp_path, {".gitignore": "gen/\n", "src/m.py": "x = 1\n"})
    _파일을_둔다(root, "gen/m.py", b"x = 1\n")
    _스테이지한다(
        root,
        _표_경로,
        _변이_파일(old="x = 1", new="x = 2", file="gen/m.py", expect="green").encode("utf-8"),
    )

    code, 출력 = _색인_확인(root)

    assert code == 0, 출력
    assert "커밋에 든 표 1, 고친 파일을 가리키는 다른 표의 변이 0, 문제 0" in 출력

    (root / "gen/m.py").unlink()
    code, 출력 = _색인_확인(root)

    assert code == 2
    assert "하나: gen/m.py 를 읽지 못했다" in 출력


def _main_을_합친다(
    root: Path, *, 가지에서: Callable[[], None], main_에서: Callable[[], None]
) -> None:
    """지금 판에서 `topic` 을 따 `가지에서` 를, main 에서 `main_에서` 를 커밋한 뒤 topic 에 main 을
    합치되 합치는 커밋은 만들지 않는다."""
    _git(root, "checkout", "-q", "-b", "topic")
    가지에서()
    _git(root, "commit", "-q", "-m", "가지")
    _git(root, "checkout", "-q", "main")
    main_에서()
    _git(root, "commit", "-q", "-m", "main")
    _git(root, "checkout", "-q", "topic")
    _git(root, "merge", "-q", "--no-commit", "--no-ff", "main")


def test_색인_확인은_합칠_때_main_이_이미_깬_원문을_합치는_커밋의_탓으로_알리지_않는다(
    tmp_path: Path,
) -> None:
    """두 부모에 같은 표가 있으면 두 부모에서 모두 맞던 원문만 본다. main 을 합치는 커밋은
    가지의 HEAD 와 견주면 main 의 변경이 모두 든다."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", _표_경로: _맞는_표})

    _main_을_합친다(
        root,
        가지에서=lambda: _스테이지한다(root, "src/o.py", b"o = 2\n"),
        main_에서=lambda: _스테이지한다(root, "src/m.py", b"x = 9\n"),
    )

    code, 출력 = _색인_확인(root)
    assert code == 0, 출력


def test_색인_확인은_합친_결과가_가지에만_있는_표의_원문을_깨면_알린다(tmp_path: Path) -> None:
    """가지가 더한 표와 main 이 고친 코드는 따로는 맞았고, 합친 판에서 원문이 깨진다."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n"})

    _main_을_합친다(
        root,
        가지에서=lambda: _스테이지한다(root, _표_경로, _맞는_표.encode("utf-8")),
        main_에서=lambda: _스테이지한다(root, "src/m.py", b"x = 9\n"),
    )

    code, 출력 = _색인_확인(root)
    assert code == 2
    assert f"{_표_경로}: !! 하나: src/m.py 에 원문이 0번 있다" in 출력
    assert _깬_커밋 in 출력


def test_못_보는_것_색인_확인은_작업_트리의_줄_끝_변환을_거치지_않는다(tmp_path: Path) -> None:
    """`eol=crlf` 인 파일은 색인에 LF 로 든다. 작업 트리의 CRLF 로 적은 원문은 디스크에서는 맞고
    색인에서는 0번이다(잘못 막는다)."""
    root = _저장소(tmp_path, {".gitattributes": "*.py text eol=crlf\n"})
    _파일을_둔다(root, "src/m.py", b"x = 1\r\n")
    표 = _변이_파일(old="x = 1", new="x = 2").replace("old = '''x = 1'''", 'old = "x = 1\\r\\n"')
    _스테이지한다(root, _표_경로, 표.encode("utf-8"))
    _git(root, "add", "src/m.py")

    디스크 = main(
        ["--check", str(root / _표_경로)], root=root, runner=_부르면_안_되는_러너, out=print
    )
    색인_코드, 출력 = _색인_확인(root)

    assert 디스크 == 0
    assert 색인_코드 == 2
    assert "하나: src/m.py 에 원문이 0번 있다" in 출력


def test_못_보는_것_색인_확인은_amend_에서_고칠_커밋이_넣은_깨진_원문을_지나간다(
    tmp_path: Path,
) -> None:
    """`git commit --amend` 의 훅도 HEAD(고칠 커밋)를 부모로 본다. HEAD 가 훅을 건너뛰고 넣은 깨진
    원문은 부모 판에서도 맞지 않던 원문으로 읽힌다(놓친다)."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", _표_경로: _맞는_표})
    _스테이지한다(root, "src/m.py", b"x = 9\n")
    _git(root, "commit", "-q", "--no-verify", "-m", "훅을 건너뛰고 깬 커밋")
    _스테이지한다(root, "src/m.py", b"x = 9\ny = 1\n")

    code, 출력 = _색인_확인(root)

    assert code == 0, 출력
    assert "고친 파일을 가리키는 다른 표의 변이 1, 문제 0" in 출력


def test_색인_확인은_다른_인자와_섞지_않는다(tmp_path: Path) -> None:
    for argv in (["--staged", "a_mutations.toml"], ["--staged", "--check"]):
        줄: list[str] = []
        code = main(argv, root=tmp_path, runner=_부르면_안_되는_러너, out=줄.append)
        assert code == 2, argv
        assert any("--staged 는 다른 인자와 섞지 않는다" in 한줄 for 한줄 in 줄), argv


def test_색인_확인은_git_저장소_밖이면_그렇게_알리고_2다(tmp_path: Path) -> None:
    code, 출력 = _색인_확인(tmp_path)

    assert code == 2
    assert "git 저장소 안이 아니다" in 출력


def test_git_commit_의_훅으로_띄우면_그_커밋에_들_색인을_본다(tmp_path: Path) -> None:
    """`git commit <경로>` 는 HEAD 에 그 경로만 더한 임시 색인을 `GIT_INDEX_FILE` 로 훅에
    넘긴다. 스테이지한 다른 변경은 그 커밋에 들지 않는다. pre-commit 처럼 `PYTHONUTF8` 없이
    띄운다."""
    도구 = (ROOT / _이_도구).read_text(encoding="utf-8")
    파일들 = {"src/m.py": "x = 1\n", "src/o.py": "o = 1\n", _표_경로: _맞는_표, _이_도구: 도구}
    root = _저장소(tmp_path, 파일들)
    훅 = root / ".git" / "hooks" / "pre-commit"
    훅.parent.mkdir(exist_ok=True)
    파이썬 = Path(sys.executable).as_posix()
    훅.write_bytes(f'#!/bin/sh\nexec "{파이썬}" {_이_도구} --staged\n'.encode())
    훅.chmod(0o755)
    _스테이지한다(root, "src/m.py", b"x = 9\n")
    _파일을_둔다(root, "src/o.py", b"o = 2\n")

    def 커밋(*경로: str) -> tuple[int, str]:
        done = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
            + ["commit", "-q", "-m", "커밋", *경로],
            cwd=root,
            capture_output=True,
            env={**hook_environment(), "PYTHONIOENCODING": "cp949"},
            check=False,
            timeout=120,
        )
        return done.returncode, (done.stdout + done.stderr).decode("utf-8")

    부분_코드, 부분_출력 = 커밋("src/o.py")
    전부_코드, 전부_출력 = 커밋()

    assert 부분_코드 == 0, 부분_출력
    assert 전부_코드 != 0
    assert f"{_표_경로}: !! 하나: src/m.py 에 원문이 0번 있다" in 전부_출력


_신호를_기다린다 = """
import pathlib, sys, time
신호 = pathlib.Path(sys.argv[1])
끝 = time.monotonic() + 15
while not 신호.exists():
    if time.monotonic() > 끝:
        신호.with_suffix(".late").touch()
        break
    time.sleep(0.05)
sys.exit(1)
"""


def test_출력을_파이프로_받아도_도는_동안_줄마다_내보낸다(tmp_path: Path) -> None:
    """파이프와 파일은 블록 버퍼라, 출력을 파일로 돌린 실행은 도는 동안 로그가 비고 끊으면 결과가
    사라졌다(대기열 259). 둘째 기준선은 첫 기준선 줄을 읽은 뒤에야 끝나, 도구가 그 줄을 쥐고 있으면
    기다리다 늦음 표지를 남긴다. 둘째 기준선이 빨개 변이는 들지 않고, 들어도 원문과 같은
    바이트다."""
    신호 = tmp_path / "go"
    기다림 = tmp_path / "wait.py"
    기다림.write_text(_신호를_기다린다, encoding="utf-8")
    파이썬 = json.dumps(sys.executable)
    변이 = "".join(
        f"""
[runner.{이름}]
command = {명령}
judge = "exit"
red_exit = 1

[[mutation]]
name = "{이름}"
runner = "{이름}"
expect = "red"

[[mutation.edit]]
file = "{_이_도구}"
old = "ROOT = Path(__file__).resolve().parent.parent"
new = "ROOT = Path(__file__).resolve().parent.parent"
"""
        for 이름, 명령 in [
            ("fast", f'[{파이썬}, "-c", "pass"]'),
            ("slow", f"[{파이썬}, {json.dumps(str(기다림))}, {json.dumps(str(신호))}]"),
        ]
    )
    표 = _표를_쓴다(tmp_path, "pipe_mutations.toml", 변이)
    환경 = hook_environment()
    환경.pop("PYTHONUNBUFFERED", None)

    # 번호로 둘 다 고른다. 고르지 않은 전체 실행은 이 도구에 커밋하지 않은 변경이 있으면 시작 줄에
    # 알림을 내(대기열 359), 이 저장소의 작업 트리에 따라 첫 줄이 달라진다
    with subprocess.Popen(
        [sys.executable, _이_도구, 표, "1", "2"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=환경,
    ) as process:
        assert process.stdout is not None
        첫_줄 = process.stdout.readline().decode("utf-8")
        신호.touch()
        나머지, stderr = process.communicate(timeout=60)

    출력 = (첫_줄 + 나머지.decode("utf-8"), stderr.decode("utf-8", "replace"))
    assert 첫_줄.startswith("기준선 fast: 초록"), 출력
    assert not 신호.with_suffix(".late").exists()
    # 종료 1 의 까닭: 둘째 기준선이 빨개 변이를 넣지 않았다(도구가 죽은 1 이 아니다)
    assert process.returncode == 1, 출력
    assert "기준선 slow: 빨강" in 출력[0], 출력
    assert "기준선이 초록이 아니라 변이를 넣지 않았다" in 출력[0], 출력
    assert 출력[1] == "", 출력


def test_main_은_되돌리지_못하면_3이고_git_diff_를_가리킨다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m, _, 변이 = _두_파일_변이(tmp_path)
    줄: list[str] = []

    code = main(
        [_변이_파일을_쓴다(tmp_path, 변이)],
        root=tmp_path,
        runner=_잠그는_러너(m, b"x = 2", monkeypatch),
        out=줄.append,
    )

    assert code == 3
    assert any("git diff" in 한줄 and "src/m.py" in 한줄 for 한줄 in 줄)


def test_main_은_되돌리지_못했을_때_그_전에_난_예외도_알린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """되돌림 실패가 원인 예외(명령을 돌리지 못했다)를 가리면 왜 멈췄는지 아무도 모른다(PR #110
    claude-review)."""
    m, _, 변이 = _두_파일_변이(tmp_path)
    잠그는 = _잠그는_러너(m, b"x = 2", monkeypatch)

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        잠그는(argv, cwd, timeout)
        if b"x = 2" in m.read_bytes():
            raise FileNotFoundError("pnpm 이 없다")
        return _초록

    줄: list[str] = []
    code = main([_변이_파일을_쓴다(tmp_path, 변이)], root=tmp_path, runner=러너, out=줄.append)

    assert code == 3
    assert any("git diff" in 한줄 for 한줄 in 줄)
    assert any("pnpm 이 없다" in 한줄 for 한줄 in 줄)


def test_main_은_테스트를_돌리지_못하면_3이고_변이는_되돌렸다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            raise FileNotFoundError("python 이 없다")
        return _초록

    code = main(
        [_변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2"))],
        root=tmp_path,
        runner=러너,
        out=lambda _: None,
    )

    assert code == 3
    assert path.read_bytes() == b"x = 1\n"


# 커밋된 변이 파일. 도구의 형식이 바뀌면 옛 파일이 조용히 깨진다 — 2026-10-01 에 형식을
# 넓히며 일곱을 손으로 `--check` 했다(대기열 73). 이 시험은 원문을 보지 않는다. 커밋이 부모 판에서
# 맞던 원문을 깨는지는 pre-commit 의 `--staged` 가 보고(대기열 312), 부모 판에서도 맞지 않던 옛
# 원문은 썩어도 되어 다시 돌 때 `--check` 가 알린다.


def test_이_저장소의_변이_파일은_지금의_도구로_모두_읽힌다() -> None:
    경로들 = sorted(ROOT.glob(".scratch/**/*_mutations.toml"))
    문제: list[str] = []
    for 경로 in 경로들:
        try:
            read_spec(경로)
        except SpecError as error:
            문제.append(f"{경로.relative_to(ROOT).as_posix()}: {error}")

    # rag-engine 킥오프(2026-11-09)에는 커밋된 변이 표가 아직 없어, agent-os 의 단언("하나도 찾지
    # 못하면 빨강")을 glob 의 뿌리가 있는지로 바꿨다. 첫 변이 표를 커밋하는 PR 이 그 단언을 되살린다
    assert (ROOT / ".scratch").is_dir(), "변이 표를 찾을 .scratch 가 없다. glob 의 뿌리가 틀렸다"
    assert 문제 == []


# --- 판정 낱말뿐인 표지, 이스케이프 힌트, 시작 줄의 알림, 도는 동안의 표지 ---
# 대기열 313·317·359·358 의 차례다.


def _표지를_단_변이(러너_줄: str, 표지_줄: str) -> str:
    return 러너_줄 + _변이_파일(old="x", new="y").replace(
        'expect = "red"', f'expect = "red"\n{표지_줄}'
    )


@pytest.mark.parametrize(
    ("러너_줄", "표지_줄"),
    [
        ("", 'expect_output = ["failed"]'),
        ("", 'expect_output = ["1 failed"]'),
        ("", 'expect_output = ["FAILED"]'),
        ("", 'expect_output = ["test_x 가 실패", "passed"]'),
        (_VITEST_러너, 'runner = "vitest"\nexpect_output = ["FAIL"]'),
        (
            _VITEST_러너.replace('judge = "vitest"', 'judge = "playwright"'),
            'runner = "vitest"\nexpect_output = ["2 passed"]',
        ),
        (
            _VITEST_러너.replace('judge = "vitest"', 'judge = "pytest"')
            + 'baseline_output = ["passed"]\n',
            'runner = "vitest"',
        ),
    ],
    ids=["낱말", "수와_낱말", "대문자", "여럿_가운데_하나", "vitest", "playwright", "기준선"],
)
def test_러너가_어느_실패에나_찍는_판정_낱말뿐인_표지는_변이_파일_오류다(
    러너_줄: str, 표지_줄: str
) -> None:
    """`["failed"]` 는 pytest 의 요약 줄 `N failed` 와 단언 dict 의 `"type": "failed"` 에 늘 실려,
    고른 단언이 빨개졌다는 표지가 되지 못했다(대기열 313)."""
    with pytest.raises(SpecError, match="판정 낱말"):
        load_spec(_표지를_단_변이(러너_줄, 표지_줄))


@pytest.mark.parametrize(
    ("러너_줄", "표지_줄"),
    [
        ("", 'expect_output = ["test_x 가 실패"]'),
        ("", 'expect_output = ["failed to parse"]'),
        ("", 'expect_output = ["== 1"]'),
        (_EXIT_러너, 'runner = "checker"\nexpect_output = ["failed"]'),
    ],
    ids=[
        "판정_낱말이_없다",
        "못_보는_것_다른_낱말이_섞였다",
        "글자가_없다",
        "못_보는_것_exit_판정",
    ],
)
def test_판정_낱말이_아닌_낱말이_든_표지는_받는다(러너_줄: str, 표지_줄: str) -> None:
    """exit 판정은 출력의 요약을 읽지 않아 거를 낱말을 두지 않는다. 그 러너의 명령이 무엇이든
    `["failed"]` 를 받는다(독스트링의 못 보는 것)."""
    assert load_spec(_표지를_단_변이(러너_줄, 표지_줄)).mutation[0].expect_output


@pytest.mark.parametrize(
    ("내용", "원문", "까닭"),
    [
        (b"a = 1\nb = 2\n", r"a = 1\nb = 2", "이스케이프를 풀지 않는다(풀면 1번)"),
        (b"a = 1\n\tb = 2\n", r"a = 1\n\tb = 2", "이스케이프를 풀지 않는다(풀면 1번)"),
        (b"a = 1\nc = 2\n", r"a = 1\nb = 2", None),
        (b"a = 1\nb = 2\n", "a = 9", None),
        (b"a = 1\r\nb = 2\r\n", r"a = 1\nb = 2", None),
    ],
    ids=[
        "줄바꿈",
        "탭",
        "풀어도_없다",
        "글자_그대로의_이스케이프가_없다",
        "못_보는_것_줄_끝까지_맞춰야_찾히면_알리지_않는다",
    ],
)
def test_원문의_글자_그대로인_이스케이프를_풀어_찾히면_그_까닭을_덧붙인다(
    tmp_path: Path, 내용: bytes, 원문: str, 까닭: str | None
) -> None:
    """작은따옴표 문자열에 적은 `\\n` 이 풀리지 않아 원문이 0번이었고, 도구는 "0번 있다" 만
    알렸다(대기열 317)."""
    _파일을_둔다(tmp_path, "src/m.py", 내용)
    줄: list[str] = []

    assert check(load_spec(_변이_파일(old=원문, new="z")), root=tmp_path, out=줄.append) == 2
    assert any("원문이 0번 있다" in 한줄 for 한줄 in 줄), 줄
    if 까닭 is None:
        assert not any("이스케이프를 풀지 않는다" in 한줄 for 한줄 in 줄), 줄
    else:
        assert any(까닭 in 한줄 for 한줄 in 줄), 줄


def _시험이_든_저장소(root: Path, *, expect: str = "red") -> tuple[Path, str]:
    """`src/m.py` 와 그 시험 `tests/test_x.py` 와 변이 표 `mutations.toml` 을 커밋한 저장소."""
    표 = _변이_파일(old="x = 1", new="x = 2", expect=expect).replace(
        'tests = ["tests/test_x.py"]', 'tests = ["tests/test_x.py::test_x", "-q"]'
    )
    파일들 = {
        "src/m.py": "x = 1\n",
        "tests/test_x.py": "def test_x(): pass\n",
        "mutations.toml": 표,
    }
    _저장소(root, 파일들)
    return root, str(root / "mutations.toml")


def _시작_줄_알림(줄: Sequence[str]) -> list[str]:
    return [한줄 for 한줄 in 줄 if "커밋하지 않은 변경" in 한줄]


@pytest.mark.parametrize(
    "고친_파일",
    ["src/m.py", "tests/test_x.py", "mutations.toml", "src/new.py"],
    ids=["표가_가리키는_파일", "그_시험", "표_자체", "가리키지_않는_파일"],
)
def test_고르지_않은_전체_실행은_시작_줄에서_커밋하지_않은_변경을_알린다(
    tmp_path: Path, 고친_파일: str
) -> None:
    """셀프 리뷰 전에 새 표 둘의 전체를 돌렸고, 리뷰가 시험과 표지를 고쳐 두 표를 다시 돌았다
    (대기열 359). 표지는 표 자체에 있다. 알리기만 하고 막지 않는다."""
    root, 표 = _시험이_든_저장소(tmp_path)
    path = root / 고친_파일
    path.write_bytes(path.read_bytes() + b"# edited\n" if path.exists() else b"y = 1\n")
    러너 = _변이면(root / "src/m.py", b"x = 2", _빨강)
    줄: list[str] = []

    assert main([표], root=root, runner=러너, out=줄.append) == 0, 줄
    알림 = _시작_줄_알림(줄)
    if 고친_파일 == "src/new.py":
        assert 알림 == [], 줄
    else:
        assert len(알림) == 1, 줄
        assert 고친_파일 in 알림[0]
        기준선 = next(at for at, 한줄 in enumerate(줄) if 한줄.startswith("기준선"))
        assert 줄.index(알림[0]) < 기준선


@pytest.mark.parametrize("고르기", [["1"], ["--since", "HEAD"]], ids=["번호", "since"])
def test_고른_실행은_커밋하지_않은_변경을_알리지_않는다(tmp_path: Path, 고르기: list[str]) -> None:
    root, 표 = _시험이_든_저장소(tmp_path)
    (root / "src/m.py").write_bytes(b"x = 1\n# edited\n")
    if "--since" in 고르기:  # 표를 커밋했으니 바뀐 변이가 있어야 고른다
        path = Path(표)
        path.write_text(path.read_text(encoding="utf-8").replace('"하나"', '"바뀐 하나"'), "utf-8")
    러너 = _변이면(root / "src/m.py", b"x = 2", _빨강)
    줄: list[str] = []

    assert main([표, *고르기], root=root, runner=러너, out=줄.append) == 0, 줄
    assert _시작_줄_알림(줄) == [], 줄


def test_git_저장소_밖의_전체_실행은_알림_없이_돈다(tmp_path: Path) -> None:
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")
    표 = _변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2"))
    줄: list[str] = []

    assert main([표], root=tmp_path, runner=_변이면(path, b"x = 2", _빨강), out=줄.append) == 0
    assert _시작_줄_알림(줄) == [], 줄


def _표지를_보는_러너(git_디렉터리: Path, 원본: Path, 본_것: list[object]) -> 러너:
    """불릴 때마다 `git_디렉터리` 의 도는 표지를 읽어 `본_것` 에 쌓고, `원본` 에 변이가 들었으면
    빨강, 아니면 초록을 낸다."""
    판정 = _변이면(원본, b"x = 2", _빨강)

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        for 표지 in git_디렉터리.glob(f"{MARKER_PREFIX}*.json"):
            본_것.append(json.loads(표지.read_text(encoding="utf-8")))
        return 판정(argv, cwd, timeout)

    return 러너


def test_도는_동안_그_체크아웃의_git_디렉터리에_pid_와_표를_든_표지를_두고_끝나면_지운다(
    tmp_path: Path,
) -> None:
    """표 묶음을 `TaskStop` 으로 멈춘 뒤 남은 셸 스크립트가 다음 표를 이어 돌았고, 그 약 17분 동안
    변이가 든 체크아웃에서 도구와 시험을 고쳤다(대기열 358). 편집 훅이 이 표지를 본다."""
    root, 표 = _시험이_든_저장소(tmp_path)
    본_것: list[object] = []
    러너 = _표지를_보는_러너(root / ".git", root / "src/m.py", 본_것)

    assert main([표], root=root, runner=러너, out=print) == 0
    assert len(본_것) == 2, "기준선과 변이가 도는 동안 표지가 하나씩 있어야 한다"
    기대 = {
        "pid": os.getpid(),
        "table": str(Path(표).resolve()),
        "started": mutate.process_started(os.getpid()),
    }
    assert 본_것 == [기대, 기대]
    assert list((root / ".git").glob(f"{MARKER_PREFIX}*")) == []


def test_워크트리에서는_그_워크트리의_git_디렉터리에_표지를_둔다(tmp_path: Path) -> None:
    root, _ = _시험이_든_저장소(tmp_path / "main")
    옆 = tmp_path / "side"
    _git(root, "worktree", "add", "-q", "-b", "side", str(옆))
    표 = _변이_파일을_쓴다(tmp_path, _변이_파일(old="x = 1", new="x = 2"))
    git_디렉터리 = root / ".git" / "worktrees" / "side"
    본_것: list[object] = []
    러너 = _표지를_보는_러너(git_디렉터리, 옆 / "src/m.py", 본_것)

    assert main([표], root=옆, runner=러너, out=print) == 0
    assert len(본_것) == 2, "워크트리의 git 디렉터리에 표지가 없었다"
    assert list(git_디렉터리.glob(f"{MARKER_PREFIX}*")) == []
    assert list((root / ".git").glob(f"{MARKER_PREFIX}*")) == []


def test_테스트를_돌리지_못해도_표지는_지운다(tmp_path: Path) -> None:
    root, 표 = _시험이_든_저장소(tmp_path)

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        raise OSError("못 띄웠다")

    assert main([표], root=root, runner=러너, out=lambda _: None) == 3
    assert list((root / ".git").glob(f"{MARKER_PREFIX}*")) == []


def test_도구가_잡지_않는_예외로_끝나도_표지는_지운다(tmp_path: Path) -> None:
    """위 시험의 `OSError` 는 도구 안에서 잡혀 3으로 돌아온다. 잡히지 않고 빠져나가는 길도 지운다
    (셀프 리뷰 명세 축)."""
    root, 표 = _시험이_든_저장소(tmp_path)

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        raise RuntimeError("러너가 터졌다")

    with pytest.raises(RuntimeError, match="러너가 터졌다"):
        main([표], root=root, runner=러너, out=lambda _: None)
    assert list((root / ".git").glob(f"{MARKER_PREFIX}*")) == []


@pytest.mark.parametrize(
    "인자",
    [["--check"], ["--check", "1"], ["--staged"]],
    ids=["원문만", "골라_원문만", "색인"],
)
def test_원문만_볼_때는_표지를_두지_않는다(tmp_path: Path, 인자: list[str]) -> None:
    """파일을 쓰지 않는 확인은 변이와 겹칠 편집이 없다. 러너가 불리지 않으니 줄을 낼 때마다 git
    디렉터리를 본다(PR #308 claude-review: 도구 안의 이름을 갈아 끼우지 않고 행동으로 단언한다).
    고르지 않은 `--check` 와 고른 `--check` 는 다른 길로 간다. 초록을 기대해 표지 없는 빨강의
    알림(대기열 350)에 걸리지 않게 한다."""
    root, 표 = _시험이_든_저장소(tmp_path, expect="green")
    줄: list[str] = []
    본_표지: list[Path] = []

    def 내보내기(한줄: str) -> None:
        줄.append(한줄)
        본_표지.extend((root / ".git").glob(f"{MARKER_PREFIX}*"))

    argv = 인자 if 인자 == ["--staged"] else [표, *인자]

    assert main(argv, root=root, runner=_부르면_안_되는_러너, out=내보내기) == 0
    assert 줄, "줄이 하나도 나지 않으면 표지를 볼 자리가 없다"
    assert 본_표지 == []


# 대기열 417. 표지가 그 시험 파일의 원문에 글자 그대로 있으면, 실패 출력의 머리(시험 이름)나 실패 줄
# 둘레의 코드 조각에 늘 실려 고른 단언이 빨개졌다는 표지가 되지 못한다.

_메아리_시험 = """def test_x():
    assert f() == "기대한 값"


def test_y():
    assert g() == "옆 시험의 값"
"""


def _메아리_표(
    표지: str, *, expect: str = "red", tests: str = '["tests/test_x.py::test_x", "-q"]'
) -> str:
    return _변이_파일(old="x = 1", new="x = 2", expect=expect).replace(
        'tests = ["tests/test_x.py"]', f"tests = {tests}\nexpect_output = [{표지!r}]"
    )


def _메아리_저장소(root: Path, 표: str) -> tuple[Path, str]:
    _저장소(root, {"src/m.py": "x = 1\n", "tests/test_x.py": _메아리_시험, "mutations.toml": 표})
    return root, str(root / "mutations.toml")


def _원문_확인(root: Path, argv: list[str]) -> tuple[int, str]:
    줄: list[str] = []
    code = main(argv, root=root, runner=_부르면_안_되는_러너, out=줄.append)
    return code, "\n".join(줄)


_메아리 = "시험 원문에 글자 그대로 있다"


@pytest.mark.parametrize(
    "표지",
    ["test_x", "기대한 값", "옆 시험의 값"],
    ids=["시험_이름", "기대_값", "못_보는_것_옆_시험"],
)
def test_고른_원문_확인은_시험_원문에_글자_그대로_있는_표지를_알린다(
    tmp_path: Path, 표지: str
) -> None:
    """표지 스물여덟을 시험 함수 이름으로 골라 그 시험의 어느 단언이 빨개져도 맞았고, 셋째는 기대
    배열의 글자가 실패 줄 둘레의 코드 조각에 실렸다(대기열 417). 옆 시험에만 있는 글자도 알린다.
    그 시험이 빨개질 때는 실리지 않으니 거짓 양성이다(독스트링의 못 보는 것)."""
    root, 표 = _메아리_저장소(tmp_path, _메아리_표(표지))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 2, 출력
    assert f"하나: expect_output 의 표지 {표지!r} 가 tests/test_x.py 의 {_메아리}" in 출력


def test_고른_원문_확인은_시험_원문에_없는_표지를_받는다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _메아리_표("== 'x = 2'"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_고르지_않은_원문_확인은_옛_변이의_표지를_소급하지_않는다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _메아리_표("test_x"))

    code, 출력 = _원문_확인(root, ["--check", 표])

    assert code == 0, 출력


def test_since_로_고른_원문_확인은_바뀐_변이의_표지를_본다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _메아리_표("== 'x = 2'"))
    path = Path(표)
    path.write_text(path.read_text("utf-8").replace("== 'x = 2'", "test_x"), "utf-8")

    code, 출력 = _원문_확인(root, ["--check", 표, "--since", "HEAD"])

    assert code == 2, 출력
    assert _메아리 in 출력


def test_초록을_기대한_변이의_표지는_보지_않는다(tmp_path: Path) -> None:
    """초록의 출력은 실패 머리와 코드 조각을 찍지 않는다."""
    root, 표 = _메아리_저장소(tmp_path, _메아리_표("test_x", expect="green"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_못_보는_것_시험_인자가_폴더면_그_안의_파일을_보지_않는다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _메아리_표("test_x", tests='["tests"]'))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


@pytest.mark.parametrize(
    "고르기", [[], ["1"], ["--since", "HEAD~1"]], ids=["전체", "번호", "since"]
)
def test_변이를_돌리는_실행도_메아리에_걸리면_기준선_전에_끝낸다(
    tmp_path: Path, 고르기: list[str]
) -> None:
    """변이를 돌리는 실행은 메아리를 보지 않아, 표지 열여덟이 시험 함수 이름인 채로 표 전부를 돌고
    기대대로를 찍었다(대기열 502). 전체 실행은 옛 변이까지 본다. 다시 돌리면 지금 재는 것이다."""
    root, 표 = _메아리_저장소(tmp_path, _메아리_표("== 'x = 2'"))
    path = Path(표)
    path.write_text(path.read_text("utf-8").replace("== 'x = 2'", "test_x"), "utf-8")
    _git(root, "commit", "-qam", "메아리")
    줄: list[str] = []

    code = main([표, *고르기], root=root, runner=_부르면_안_되는_러너, out=줄.append)

    출력 = "\n".join(줄)
    assert code == 2, 출력
    assert f"하나: expect_output 의 표지 'test_x' 가 tests/test_x.py 의 {_메아리}" in 출력


def test_러너의_자리를_기준으로_시험_파일을_찾는다(tmp_path: Path) -> None:
    표 = _VITEST_러너 + _메아리_표("기대한 값", tests='["a.test.ts"]').replace(
        'expect = "red"', 'runner = "vitest"\nexpect = "red"'
    )
    _저장소(tmp_path, {"src/m.py": "x = 1\n", "web/a.test.ts": "expect(f()).toBe('기대한 값')\n"})
    경로 = _변이_파일을_쓴다(tmp_path, 표)

    code, 출력 = _원문_확인(tmp_path, ["--check", 경로, "1"])

    assert code == 2, 출력
    assert f"web/a.test.ts 의 {_메아리}" in 출력


def test_색인_확인은_커밋에_든_새_표의_메아리_표지를_알린다(tmp_path: Path) -> None:
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", "tests/test_x.py": _메아리_시험})
    _스테이지한다(root, _표_경로, _메아리_표("test_x").encode("utf-8"))

    code, 출력 = _색인_확인(root)

    assert code == 2, 출력
    assert f"{_표_경로}: !! 하나: expect_output 의 표지 'test_x'" in 출력


def test_색인_확인은_시험_파일을_커밋에_들_색인에서_읽는다(tmp_path: Path) -> None:
    """작업 트리의 시험이 표지를 들지 않아도 색인의 시험이 들면 알린다."""
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", "tests/test_x.py": _메아리_시험})
    _스테이지한다(root, _표_경로, _메아리_표("test_x").encode("utf-8"))
    (root / "tests/test_x.py").write_text("def test_z(): pass\n", encoding="utf-8")

    code, 출력 = _색인_확인(root)

    assert code == 2, 출력


def test_색인_확인은_표를_고친_커밋에서도_부모_판과_같은_변이의_표지는_소급하지_않는다(
    tmp_path: Path,
) -> None:
    옛_표 = _메아리_표("test_x")
    root = _저장소(
        tmp_path,
        {"src/m.py": "x = 1\n", "tests/test_x.py": _메아리_시험, _표_경로: 옛_표},
    )
    둘 = _메아리_표("== 'x = 2'").replace('"하나"', '"둘"')
    _스테이지한다(root, _표_경로, (옛_표 + 둘).encode("utf-8"))

    code, 출력 = _색인_확인(root)

    assert code == 0, 출력
    assert "문제 0" in 출력


def test_색인_확인은_고친_변이의_표지를_본다(tmp_path: Path) -> None:
    root = _저장소(
        tmp_path,
        {"src/m.py": "x = 1\n", "tests/test_x.py": _메아리_시험, _표_경로: _메아리_표("== 1")},
    )
    _스테이지한다(root, _표_경로, _메아리_표("기대한 값").encode("utf-8"))

    code, 출력 = _색인_확인(root)

    assert code == 2, 출력
    assert _메아리 in 출력


# 대기열 350·517·579. 표지의 품질을 셋 더 본다. 빨강을 기대했는데 표지가 없는 변이(350)와, 표지가
# pytest 가 단언을 풀어 쓴 줄인 변이(517), 그 줄에서 머리를 뗀 호출 한 토막인 변이(579). 고른
# `--check` 와 `--staged` 의 새 변이만 보고 옛 변이는 소급하지 않는다.

_표지_없음 = "빨강을 기대했는데 expect_output 이 없다"
_단언_풀이 = "pytest 가 단언을 풀어 쓴 줄이다"
_호출_토막 = "호출 한 토막(`이름(…)` 꼴)이다"


def _표지_표(표지: str | None, *, expect: str = "red") -> str:
    줄 = "" if 표지 is None else f"\nexpect_output = [{표지!r}]"
    return _변이_파일(old="x = 1", new="x = 2", expect=expect).replace(
        'tests = ["tests/test_x.py"]', f'tests = ["tests/test_x.py"]{줄}'
    )


def test_고른_원문_확인은_빨강을_기대했는데_표지가_없는_변이를_알린다(tmp_path: Path) -> None:
    """엉뚱한 까닭의 빨강도 기대와 맞아, `wait_ci` 변이 열다섯이 표지 없이 두 리뷰를 지났다(대기열
    350)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표(None))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 2, 출력
    assert f"하나: {_표지_없음}" in 출력


def test_since_로_고른_원문_확인은_표지를_뗀_변이를_알린다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _표지_표("== 'x = 2'"))
    Path(표).write_text(_표지_표(None), encoding="utf-8")

    code, 출력 = _원문_확인(root, ["--check", 표, "--since", "HEAD"])

    assert code == 2, 출력
    assert _표지_없음 in 출력


def test_초록을_기대한_변이는_표지가_없어도_알리지_않는다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _표지_표(None, expect="green"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_고르지_않은_원문_확인은_표지_없는_옛_변이를_소급하지_않는다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _표지_표(None))

    code, 출력 = _원문_확인(root, ["--check", 표])

    assert code == 0, 출력


@pytest.mark.parametrize(
    "표지",
    ["where 1 = run()", "assert 0 == 1", "E       assert 4 == 1", "+  where False = f(1)"],
    ids=["where", "assert", "E_접두", "더하기_접두"],
)
def test_고른_원문_확인은_pytest_가_단언을_풀어_쓴_줄인_표지를_알린다(
    tmp_path: Path, 표지: str
) -> None:
    """`where 1 = run()` 은 러너가 다른 까닭으로 멈춰도 실려 맞았다(대기열 517)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표(표지))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 2, 출력
    assert f"하나: expect_output 의 표지 {표지!r} 는 {_단언_풀이}" in 출력


@pytest.mark.parametrize(
    "표지",
    [
        "Received: 2",
        "거부 문구가 단언 메시지에 실렸다",
        "assert 만 있고 비교는 없다",
        "where 만 있다",
    ],
    ids=["받은_값_줄", "메시지_문구", "비교_없는_assert", "호출_없는_where"],
)
def test_고른_원문_확인은_단언_풀이_줄이_아닌_표지를_받는다(tmp_path: Path, 표지: str) -> None:
    root, 표 = _메아리_저장소(tmp_path, _표지_표(표지))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_pytest_가_아닌_판정의_표지는_단언_풀이_줄이어도_보지_않는다(tmp_path: Path) -> None:
    표 = _VITEST_러너 + _vitest_변이(줄='expect_output = ["assert 0 == 1"]')
    _저장소(tmp_path, {"web/m.ts": "x = 1\n"})
    경로 = _변이_파일을_쓴다(tmp_path, 표)

    code, 출력 = _원문_확인(tmp_path, ["--check", 경로, "1"])

    assert code == 0, 출력


def test_못_보는_것_줄_머리가_단언_풀이가_아니면_받는다(tmp_path: Path) -> None:
    """줄 머리만 본다. `AssertionError: assert 0 == 1` 처럼 앞에 낱말이 붙은 줄은 지나간다."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표("AssertionError: assert 0 == 1"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_처리하지_않은_에러를_기대한_변이는_표지가_없어도_알리지_않는다(tmp_path: Path) -> None:
    표 = _VITEST_러너 + _vitest_변이().replace('expect = "red"', 'expect = "unhandled"')
    _저장소(tmp_path, {"web/m.ts": "x = 1\n"})
    경로 = _변이_파일을_쓴다(tmp_path, 표)

    code, 출력 = _원문_확인(tmp_path, ["--check", 경로, "1"])

    assert code == 0, 출력


def test_못_보는_것_판정이_exit_인_러너는_명령이_pytest_여도_표지를_보지_않는다(
    tmp_path: Path,
) -> None:
    러너 = _EXIT_러너.replace('["node", "check.mjs"]', '["uv", "run", "pytest", "-q"]')
    변이 = _exit_변이(줄='expect_output = ["assert 0 == 1"]').replace("m.json", "src/m.py")
    root, 표 = _메아리_저장소(tmp_path, 러너 + 변이)

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


@pytest.mark.parametrize(
    "표지",
    ["assert 1 != 1", "assert 'a' in b", "assert x is None"],
    ids=["다름", "포함", "동일성"],
)
def test_못_보는_것_같음_비교가_아닌_단언_풀이_줄은_받는다(tmp_path: Path, 표지: str) -> None:
    """pytest 는 이 비교들도 풀어 쓰지만 `==` 만 본다(거짓 음성)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표(표지))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_못_보는_것_줄이_assert_로_시작하고_같음_비교를_든_메시지_문구도_알린다(
    tmp_path: Path,
) -> None:
    """단언에 싣는 메시지가 그런 줄이면 풀이 줄과 갈라 볼 수 없다(거짓 양성)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표("assert 결과 == 'done' 이어야 한다"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 2, 출력
    assert _단언_풀이 in 출력


@pytest.mark.parametrize(
    "표지",
    [
        "matches(server='other-server', tool='add')",
        "Rule(server=None, tool='*')",
        "marker_name('s1', 'agent-a')",
        "process_alive(4242)",
        "isinstance(Plan(arms=('A', 'B')), Halt)",
        "self.matches(x)",
        "+ Rule(server=None, tool='*')",
        "E   process_alive()",
    ],
    ids=[
        "이름과_인자",
        "값_생성자",
        "문자열_인자",
        "숫자_인자",
        "겹친_호출",
        "점_이름",
        "더하기_접두",
        "E_접두",
    ],
)
def test_고른_원문_확인은_줄_머리가_호출_한_토막인_표지를_알린다(tmp_path: Path, 표지: str) -> None:
    """변이 1·7·8·9의 표지 `matches(…)`·`Rule(…)` 는 `+  where False = matches(…)` 줄에 든 부분
    문자열이라 줄 머리 기준을 지났고, 표준 축 리뷰가 잡았다(대기열 579)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표(표지))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 2, 출력
    assert f"하나: expect_output 의 표지 {표지!r} 는 {_호출_토막}" in 출력


@pytest.mark.parametrize(
    "표지",
    [
        "rule = Rule(server=None, tool='*'), server = 'everything', tool = 'add'",
        "Received: Rule(server=None, tool='*')",
        "At index 0 diff: Hit(ident='0001', rounds=None)",
        "Left contains one more item: Hit(pattern='x', tool='Read')",
        "zeta(7회차) coderabbit-inline-size(5회차)",
        "DID NOT RAISE",
        "tool='*'",
    ],
    ids=[
        "인자_줄",
        "받은_값_줄",
        "차이_줄",
        "더_든_항목_줄",
        "목록_출력",
        "예외_문구",
        "인자_조각",
    ],
)
def test_고른_원문_확인은_인자_줄과_받은_값_줄은_호출_꼴이어도_받는다(
    tmp_path: Path, 표지: str
) -> None:
    """줄 머리가 `이름(` 이 아니면 호출 한 토막이 아니다. 고른 단언이 빨개질 때만 찍히는 줄이다."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표(표지))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_pytest_가_아닌_판정의_표지는_호출_한_토막이어도_보지_않는다(tmp_path: Path) -> None:
    표 = _VITEST_러너 + _vitest_변이(줄="expect_output = [\"Rule(server=None, tool='*')\"]")
    _저장소(tmp_path, {"web/m.ts": "x = 1\n"})
    경로 = _변이_파일을_쓴다(tmp_path, 표)

    code, 출력 = _원문_확인(tmp_path, ["--check", 경로, "1"])

    assert code == 0, 출력


def test_초록을_기대한_변이의_표지는_호출_한_토막이어도_보지_않는다(tmp_path: Path) -> None:
    root, 표 = _메아리_저장소(tmp_path, _표지_표("Rule(server=None, tool='*')", expect="green"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


def test_못_보는_것_값의_repr_인_호출_꼴_줄_머리도_알린다(tmp_path: Path) -> None:
    """`Hit(ident='0001', rounds=None` 이 비교 실패의 diff 줄이라면 고른 단언만 찍는 줄일 수 있다.
    줄 머리가 호출 꼴이면 풀이 줄과 갈라 볼 수 없어 알린다(거짓 양성)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표("Hit(ident='0001', rounds=None"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 2, 출력
    assert _호출_토막 in 출력


def test_못_보는_것_줄_머리가_아닌_호출_조각은_받는다(tmp_path: Path) -> None:
    """줄 머리만 본다. `AssertionError: matches('a')` 처럼 앞에 낱말이 붙은 줄은 지나간다(거짓
    음성)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표("AssertionError: matches('a')"))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


@pytest.mark.parametrize(
    "표지",
    ["f(1.5)", "f(b'x')", "f(f'x')", "f(*args)", "f(-x)", "f(x[0])", "f(안녕)", "Rule("],
    ids=["소수", "바이트_접두", "f_접두", "별표_인자", "음수_식별자", "첨자", "한글_인자", "줄_끝"],
)
def test_못_보는_것_인자가_정수_식별자_따옴표로_시작하지_않는_호출_조각은_받는다(
    tmp_path: Path, 표지: str
) -> None:
    """정규식이 받는 인자 꼴은 `)`, 따옴표나 괄호, 정수와 식별자 뒤의 `,` `)` 뿐이다(거짓
    음성)."""
    root, 표 = _메아리_저장소(tmp_path, _표지_표(표지))

    code, 출력 = _원문_확인(root, ["--check", 표, "1"])

    assert code == 0, 출력


@pytest.mark.parametrize("표지", [None, "where 1 = run()"], ids=["표지_없음", "단언_풀이"])
def test_변이를_돌리는_실행은_표지의_품질을_소급하지_않는다(
    tmp_path: Path, 표지: str | None
) -> None:
    """돌리는 실행에 걸면 옛 표를 다시 돌릴 때마다 멈춘다. 옛 표 3613 변이 가운데 표지 없는 빨강이
    1883, 단언 풀이 줄 표지가 176이다(티켓 041)."""
    path = _파일을_둔다(tmp_path, "src/m.py", b"x = 1\n")

    def 러너(argv: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
        if b"x = 2" in path.read_bytes():
            return CommandResult(1, "where 1 = run()\n1 failed\n")
        return _초록

    code = measure(load_spec(_표지_표(표지)), root=tmp_path, runner=러너, out=lambda _: None)

    assert code == 0


@pytest.mark.parametrize(
    ("표지", "알림"),
    [
        (None, _표지_없음),
        ("where 1 = run()", _단언_풀이),
        ("Rule(server=None, tool='*')", _호출_토막),
    ],
    ids=["표지_없음", "단언_풀이", "호출_토막"],
)
def test_색인_확인은_커밋에_든_새_표의_표지_품질을_알린다(
    tmp_path: Path, 표지: str | None, 알림: str
) -> None:
    root = _저장소(tmp_path, {"src/m.py": "x = 1\n", "tests/test_x.py": _메아리_시험})
    _스테이지한다(root, _표_경로, _표지_표(표지).encode("utf-8"))

    code, 출력 = _색인_확인(root)

    assert code == 2, 출력
    assert f"{_표_경로}: !! 하나:" in 출력
    assert 알림 in 출력


def test_색인_확인은_부모_판과_같은_변이의_표지_품질은_소급하지_않는다(tmp_path: Path) -> None:
    옛_표 = _표지_표(None)
    root = _저장소(
        tmp_path,
        {"src/m.py": "x = 1\n", "tests/test_x.py": _메아리_시험, _표_경로: 옛_표},
    )
    둘 = _표지_표("== 'x = 2'").replace('"하나"', '"둘"')
    _스테이지한다(root, _표_경로, (옛_표 + 둘).encode("utf-8"))

    code, 출력 = _색인_확인(root)

    assert code == 0, 출력
    assert "문제 0" in 출력
