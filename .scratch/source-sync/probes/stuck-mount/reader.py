"""끊긴 네트워크 공유 폴더에서 파이썬의 읽기 호출이 어떻게 되는지를 컨테이너 안에서 재는 쪽이다
(source-sync 명세 "동기화의 차례"의 돌아오지 않는 호출 규칙, 2026-11-21 설계 인터뷰).

`probe.sh` 가 "서버 기계" 노릇을 하는 Docker-in-Docker 컨테이너에 복사하고, `inner.sh` 가 그 안에서
띄운 컨테이너(제품의 작업자 이미지, uid 10001)에서 돌린다. 혼자서는 돌리지 않는다. 무엇을 재는지와
실행 명령은 `probe.sh` 의 머리 설명에 있다. 첫 인자는 칸의 이름(서버 기계에서 `ps` 로 볼 때 이 칸의
프로세스를 가르는 표지)이고 둘째 인자가 명령이다.
- suite <마운트> <ctl 폴더> <한도(초)>: 한 칸의 측정을 차례로 돈다. 이 프로세스는 마운트를 직접
  건드리지 않고 아래 명령을 자식 프로세스로 띄워 기다린다. 서버를 끊고 다시 잇는 일은 `inner.sh` 가
  하고, ctl 폴더의 빈 파일로 때를 주고받는다(ready, t_fail, want_restore, t_restore).
- once <호출> <경로> <한도(초)>: 호출 하나를 자식으로 띄워 결과를 사람이 읽는 한 줄로 낸다.
- call <호출> <경로> <plain|handler>: `os.listdir`, `os.stat`, `open(...).read()` 가운데 하나를 주
  스레드에서 한 번 부른다. handler 면 SIGTERM 처리기를 단다.
- preopened <경로> <ctl 폴더> <준비 파일 이름>: 서버가 살아 있을 때 파일을 열어 두고, 끊긴 뒤에
  읽는다.
- shape <경로> <초>: 제품이 쓰려는 모양이다. daemon 스레드 하나가 읽고, 주 스레드는 그 초만큼 있다가
  그냥 끝난다.
- worker <경로> <daemon-thread|main-thread>: 컨테이너의 주 프로세스로 뜨는 모양이다. 작업자처럼
  SIGTERM 처리기가 멈춤 표지를 세우고 주 스레드는 표지를 보고 끝난다. main-thread 면 읽기를 주
  스레드가 직접 해서 처리기가 돌 틈이 없다.

대상은 공유 폴더 맨 위의 `t001` ~ `t250` 이다. 측정마다 새 번호를 써서, 그 폴더 이름부터가
클라이언트가 한 번도 본 적 없는 이름이 되게 한다. 같은 번호를 여러 프로세스가 함께 보는 것은 일부러
그렇게 한 시험(t040, t060)뿐이다. 101 부터는 `inner.sh` 가 컨테이너 시험에 쓴다.

자식이 부모에게 내는 줄은 탭으로 가른 칸이다(start, end, handler, thread-start, thread-end,
main-end).
"""

from __future__ import annotations

import errno
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType

POLL_SECONDS = 0.05
FIRST_AT = 1.0
SIGNAL_AT = 5.0
SHAPE_MAIN_SECONDS = 12.0
SHARED_AT = 12.0
MARK_AT = 120.0
LATE_NEW_AT = 195.0
LATE_AT = 200.0
LATE_NEEDS_LIMIT = 270.0
SIGNAL_WAIT_SECONDS = 8.0
HANDLER_WAIT_SECONDS = 10.0
END_WAIT_SECONDS = 20.0
RESTORE_WATCH_SECONDS = 120.0
RESTORE_SECOND_AT = 30.0
FIRST = "첫 묶음"
PREOPENED = "미리 열어 둔 파일"
CALL_NAMES = {
    "listdir": "os.listdir",
    "stat": "os.stat",
    "read": "open().read()",
    "preopened": "read()",
}

type Batches = list[tuple[float, str, list[tuple[str, str]]]]

TIMED_BATCHES: Batches = [
    (
        FIRST_AT,
        FIRST,
        [("listdir", "t001/sub"), ("stat", "t002/a.txt"), ("read", "t003/a.txt")],
    ),
    (FIRST_AT, "다른 컨테이너(w4)가 볼 폴더를 먼저 본 호출", [("stat", "t060/b.txt")]),
    (30.0, "30초 묶음", [("stat", "t010/a.txt"), ("read", "t011/a.txt")]),
    (90.0, "90초 묶음", [("listdir", "t012/sub"), ("read", "t013/a.txt")]),
]
AFTER_FIRST_RETURN: Batches = [
    (0.5, "첫 묶음이 돌아온 직후 묶음", [("stat", "t020/a.txt"), ("read", "t021/a.txt")]),
    (30.0, "첫 묶음이 돌아오고 30초 뒤 묶음", [("stat", "t022/a.txt"), ("read", "t023/a.txt")]),
    (90.0, "첫 묶음이 돌아오고 90초 뒤 묶음", [("stat", "t024/a.txt"), ("read", "t025/a.txt")]),
]
AFTER_RESTORE: Batches = [
    (
        2.0,
        "서버를 다시 이은 뒤 묶음",
        [("listdir", "t030/sub"), ("stat", "t031/a.txt"), ("read", "t032/a.txt")],
    ),
    (
        RESTORE_SECOND_AT,
        "서버를 다시 잇고 30초 뒤 묶음",
        [("stat", "t033/a.txt"), ("read", "t034/a.txt")],
    ),
]

_OUT_LOCK = threading.Lock()


def emit(line: str) -> None:
    """한 줄을 UTF-8 로 적고 바로 내보낸다."""
    with _OUT_LOCK:
        sys.stdout.buffer.write(f"{line}\n".encode())
        sys.stdout.buffer.flush()


def report(*fields: str) -> None:
    """자식이 부모에게 내는 줄. 신호 처리기에서도 부르므로 잠금 없이 한 번에 쓴다."""
    os.write(1, ("\t".join(fields) + "\n").encode())


def stamp() -> str:
    return f"{time.time():.3f}"


def clock() -> str:
    """사람이 읽는 시각(UTC). 컨테이너 로그에 쓴다."""
    seconds = time.time()
    return time.strftime("%H:%M:%S", time.gmtime(seconds)) + f".{int(seconds * 1000) % 1000:03d}"


def do_call(kind: str, path: str) -> str:
    if kind == "listdir":
        return f"항목 {len(os.listdir(path))}개"
    if kind == "stat":
        return f"크기 {os.stat(path).st_size}바이트"
    with open(path, "rb") as handle:
        return f"{len(handle.read())}바이트"


def failure(error: OSError) -> list[str]:
    number = error.errno or 0
    return ["err", str(number), errno.errorcode.get(number, "?"), error.strerror or ""]


def attempt(kind: str, path: str) -> list[str]:
    """호출 하나를 한다. 성공이면 ["ok", 설명], OSError 면 ["err", 번호, 이름, 풀이]를 낸다."""
    try:
        detail = do_call(kind, path)
    except OSError as error:
        return failure(error)
    return ["ok", detail]


def describe(result: list[str]) -> str:
    if result[:1] == ["ok"]:
        return f"성공({result[1]})"
    if result[:1] == ["err"]:
        return f"OSError errno {result[1]} {result[2]}({result[3]})"
    return f"알 수 없는 결과 {result}"


def wait_for_file(path: Path, limit: float) -> bool:
    deadline = time.time() + limit
    while not path.exists():
        if time.time() > deadline:
            return False
        time.sleep(0.02)
    return True


def run_call(kind: str, path: str, mode: str) -> None:
    def on_term(signum: int, frame: FrameType | None) -> None:
        report("handler", stamp())
        raise SystemExit(0)

    if mode == "handler":
        signal.signal(signal.SIGTERM, on_term)
    report("start", stamp())
    result = attempt(kind, path)
    report("end", stamp(), *result)


def run_preopened(path: str, ctl: str, ready: str) -> None:
    with open(path, "rb") as handle:
        Path(ctl, ready).touch()
        wait_for_file(Path(ctl, "t_fail"), 3600.0)
        time.sleep(FIRST_AT)
        report("start", stamp())
        try:
            result = ["ok", f"{len(handle.read())}바이트"]
        except OSError as error:
            result = failure(error)
        report("end", stamp(), *result)


def run_shape(path: str, main_seconds: float) -> None:
    def stuck() -> None:
        report("thread-start", stamp())
        result = attempt("read", path)
        report("thread-end", stamp(), *result)

    thread = threading.Thread(target=stuck, daemon=True, name="connector-call")
    thread.start()
    time.sleep(main_seconds)
    report("main-end", stamp(), "alive" if thread.is_alive() else "done")


def run_worker(path: str, where: str) -> None:
    stop = threading.Event()
    received: list[str] = []

    def on_term(signum: int, frame: FrameType | None) -> None:
        received.append(clock())
        stop.set()

    def read_once() -> None:
        emit(f"{clock()} 읽기를 시작한다({where})")
        # 결과를 먼저 받은 뒤에 시각을 찍는다. 한 줄의 f-string 안에서 부르면 시각이 호출보다 먼저
        # 셈돼 시작한 때가 찍힌다(probe_out.txt 와 probe_out_cifs_soft.txt 의 이 줄이 그렇게
        # 찍혔다).
        result = describe(attempt("read", path))
        emit(f"{clock()} 읽기가 돌아왔다: {result}")

    signal.signal(signal.SIGTERM, on_term)
    emit(f"{clock()} 떴다(pid {os.getpid()}, 부모 pid {os.getppid()}, uid {os.getuid()})")
    if where == "main-thread":
        read_once()
    else:
        threading.Thread(target=read_once, daemon=True, name="connector-call").start()
    while not stop.wait(0.2):
        pass
    emit(f"{clock()} SIGTERM 처리기가 {received[0]} 에 돌았고 주 스레드가 끝난다")


def thread_states(pid: int) -> str:
    """프로세스의 스레드마다 `/proc` 의 상태 글자(`ps` 의 STAT)를 낸다. 주 스레드가 맨 앞이다."""
    try:
        tasks = sorted(Path(f"/proc/{pid}/task").iterdir(), key=lambda task: int(task.name))
        letters = [(task / "stat").read_text().rsplit(")", 1)[1].split()[0] for task in tasks]
    except (OSError, IndexError):
        return "(프로세스가 없다)"
    return ",".join(letters)


@dataclass
class Child:
    """띄운 자식 하나와 그 자식이 지금까지 낸 줄."""

    process: subprocess.Popen[str]
    lines: list[str] = field(default_factory=lambda: [])
    pumps: list[threading.Thread] = field(default_factory=lambda: [])

    def settle(self) -> None:
        """끝난 자식이 낸 줄을 다 받을 때까지 잠깐 기다린다."""
        for thread in self.pumps:
            thread.join(2.0)

    def row(self, key: str) -> list[str] | None:
        for line in list(self.lines):
            parts = line.split("\t")
            if parts[0] == key:
                return parts[1:]
        return None


def pump(child: Child) -> None:
    stream = child.process.stdout
    if stream is None:
        return
    for line in stream:
        child.lines.append(line.rstrip("\n"))


def launch(tag: str, *arguments: str) -> Child:
    process = subprocess.Popen(
        [sys.executable, "-u", __file__, tag, *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    child = Child(process)
    child.pumps.append(threading.Thread(target=pump, args=(child,), daemon=True))
    child.pumps[0].start()
    return child


def run_once(tag: str, kind: str, path: str, limit: float) -> None:
    child = launch(tag, "call", kind, path, "plain")
    started = time.monotonic()
    while child.row("end") is None and child.process.poll() is None:
        if time.monotonic() - started > limit:
            child.process.kill()
            emit(f"{CALL_NAMES[kind]}({path}): {limit:.0f}초 안에 돌아오지 않아 죽였다")
            return
        time.sleep(0.01)
    elapsed = time.monotonic() - started
    child.process.wait(END_WAIT_SECONDS)
    child.settle()
    end = child.row("end")
    outcome = describe(end[1:]) if end is not None else f"결과 줄 없이 끝났다 {child.lines}"
    emit(f"{CALL_NAMES[kind]}({path}): {outcome}, {elapsed:.2f}초")


@dataclass
class Call:
    """시간표에 올린 호출 하나."""

    batch: str
    kind: str
    target: str
    child: Child
    assumed_start: float
    returned_at: float | None = None
    slow_exit_noted: bool = False
    exited: bool = False


@dataclass
class Planned:
    due: float
    batch: str
    calls: list[tuple[str, str]]


class Suite:
    def __init__(self, tag: str, root: str, ctl: str, limit: float) -> None:
        self.tag = tag
        self.root = root
        self.ctl = Path(ctl)
        self.limit = limit
        self.t0 = 0.0
        self.t_restore: float | None = None
        self.calls: list[Call] = []
        self.pending: list[Planned] = []
        self.children: list[Child] = []
        self.helpers: list[threading.Thread] = []
        self.first_return_seen = False

    def at(self, moment: float) -> str:
        return f"[끊고 {moment - self.t0:6.1f}초]"

    def say(self, line: str) -> None:
        emit(f"  {self.at(time.time())} {line}")

    def start_child(self, *arguments: str) -> Child:
        child = launch(self.tag, *arguments)
        self.children.append(child)
        return child

    def start_call(self, kind: str, target: str, mode: str = "plain") -> Child:
        return self.start_child("call", kind, f"{self.root}/{target}", mode)

    def sleep_until(self, offset: float) -> None:
        remaining = self.t0 + offset - time.time()
        if remaining > 0:
            time.sleep(remaining)

    def plan(self, base: float, batches: Batches) -> None:
        for offset, batch, calls in batches:
            self.pending.append(Planned(base + offset, batch, calls))

    def fire_due(self, now: float) -> None:
        for planned in [each for each in self.pending if each.due <= now]:
            self.pending.remove(planned)
            names: list[str] = []
            for kind, target in planned.calls:
                child = self.start_call(kind, target)
                self.calls.append(Call(planned.batch, kind, target, child, time.time()))
                names.append(f"{CALL_NAMES[kind]}({target})")
            self.say(f"{planned.batch}을 띄웠다: {', '.join(names)}")

    def describe_return(self, call: Call, end: list[str]) -> str:
        ended = float(end[0])
        start = call.child.row("start")
        started = float(start[0]) if start is not None else call.assumed_start
        line = (
            f"{self.at(ended)} {call.batch} {CALL_NAMES[call.kind]}({call.target}): "
            f"{describe(end[1:])}, 부른 지 {ended - started:.1f}초 뒤"
        )
        if self.t_restore is not None and ended >= self.t_restore:
            line += f"(서버를 다시 잇는 명령을 친 지 {ended - self.t_restore:.1f}초 뒤)"
        return line

    def collect(self, now: float) -> None:
        for call in self.calls:
            if call.exited:
                continue
            code = call.child.process.poll()
            if code is not None:
                call.child.settle()
            end = call.child.row("end")
            if call.returned_at is None and end is not None:
                call.returned_at = float(end[0])
                emit(f"  {self.describe_return(call, end)}")
                if call.batch == FIRST and not self.first_return_seen and self.t_restore is None:
                    self.first_return_seen = True
                    self.plan(call.returned_at, AFTER_FIRST_RETURN)
            name = f"{call.batch} {CALL_NAMES[call.kind]}({call.target})"
            if code is None:
                slow = call.returned_at is not None and now - call.returned_at > 2.0
                if slow and not call.slow_exit_noted:
                    call.slow_exit_noted = True
                    self.say(f"{name}: 호출은 돌아왔는데 프로세스가 2초가 지나도 끝나지 않았다")
                continue
            call.exited = True
            if call.returned_at is None:
                call.returned_at = now
                self.say(f"{name}: 결과 줄 없이 끝났다(종료 코드 {code}, 출력 {call.child.lines})")
            elif call.slow_exit_noted:
                late = now - call.returned_at
                self.say(f"{name}: 프로세스가 끝났다(호출이 돌아온 지 {late:.1f}초 뒤)")

    def note_waiting(self, title: str) -> None:
        now = time.time()
        for call in self.calls:
            if call.returned_at is None:
                start = call.child.row("start")
                started = float(start[0]) if start is not None else call.assumed_start
                self.say(
                    f"{title} {call.batch} {CALL_NAMES[call.kind]}({call.target}): 아직 돌아오지 "
                    f"않았다(부른 지 {now - started:.1f}초째, 스레드 상태 "
                    f"{thread_states(call.child.process.pid)})"
                )

    def send(self, child: Child, signum: signal.Signals, title: str, wait: float) -> bool:
        """막힌 자식에게 신호를 보내고 끝나는지 본다. 끝났으면 True 다."""
        end = child.row("end")
        if end is not None or child.process.poll() is not None:
            outcome = describe(end[1:]) if end is not None else "결과 줄 없음"
            self.say(f"{title}: 보내기 전에 호출이 이미 돌아와 있었다({outcome})")
            return True
        before = thread_states(child.process.pid)
        started = time.monotonic()
        child.process.send_signal(signum)
        try:
            code = child.process.wait(wait)
        except subprocess.TimeoutExpired:
            time.sleep(0.2)
            handler = "돌았다" if child.row("handler") is not None else "돌지 않았다"
            self.say(
                f"{title}: {wait:.0f}초 안에 끝나지 않았다(보내기 전 스레드 상태 {before}, 지금 "
                f"{thread_states(child.process.pid)}, 파이썬 처리기는 {handler})"
            )
            return False
        elapsed = time.monotonic() - started
        child.settle()
        handler = ", 파이썬 처리기가 돌았다" if child.row("handler") is not None else ""
        self.say(
            f"{title}: {elapsed:.3f}초 뒤 끝났다(종료 코드 {code}, 보내기 전 스레드 상태 {before}"
            f"{handler})"
        )
        return True

    def signal_phase(self, preopened: Child) -> None:
        """막힌 프로세스에 SIGTERM 과 SIGKILL 을 보낸다. 대상 폴더는 프로세스마다 다르다."""
        self.sleep_until(FIRST_AT)
        plain_term = self.start_call("read", "t004/a.txt")
        plain_kill = self.start_call("read", "t005/a.txt")
        handled = self.start_call("read", "t006/a.txt", "handler")
        self.say("신호를 보낼 프로세스 셋을 띄웠다(주 스레드의 open().read(). t004, t005, t006)")
        self.sleep_until(SIGNAL_AT)
        wait = SIGNAL_WAIT_SECONDS
        self.send(plain_term, signal.SIGTERM, "SIGTERM 처리기를 달지 않은 프로세스에 SIGTERM", wait)
        self.send(plain_kill, signal.SIGKILL, "같은 모양의 프로세스에 SIGKILL", wait)
        self.send(
            preopened, signal.SIGKILL, "미리 열어 둔 파일(big2.bin)을 읽는 프로세스에 SIGKILL", wait
        )
        ended = self.send(
            handled, signal.SIGTERM, "SIGTERM 처리기를 단 프로세스에 SIGTERM", HANDLER_WAIT_SECONDS
        )
        if not ended:
            self.send(handled, signal.SIGKILL, "그 프로세스에 이어서 SIGKILL", wait)

    def shape_phase(self) -> None:
        """daemon 스레드가 막힌 채 주 스레드가 그냥 끝나는 프로세스가 사라지는지 본다."""
        self.sleep_until(FIRST_AT)
        target = "t007/a.txt"
        child = self.start_child("shape", f"{self.root}/{target}", str(SHAPE_MAIN_SECONDS))
        pid = child.process.pid
        self.say(
            f"제품의 모양을 띄웠다(daemon 스레드가 open().read()({target}) 를 부르고 주 스레드는 "
            f"{SHAPE_MAIN_SECONDS:.0f}초 뒤 그냥 끝난다)"
        )
        self.sleep_until(FIRST_AT + SHAPE_MAIN_SECONDS - 4.0)
        before = thread_states(pid)
        self.say(f"제품의 모양: 주 스레드가 끝나기 전 스레드 상태(주, daemon 순서) {before}")
        try:
            code = child.process.wait(SHAPE_MAIN_SECONDS + 40.0)
        except subprocess.TimeoutExpired:
            self.say(
                "제품의 모양: 주 스레드가 끝날 때를 40초 넘겨도 프로세스가 남아 있다(스레드 상태 "
                f"{thread_states(pid)})"
            )
            return
        gone = time.time()
        child.settle()
        main_end = child.row("main-end")
        thread_end = child.row("thread-end")
        if main_end is None:
            self.say(f"제품의 모양: main-end 줄 없이 끝났다(종료 코드 {code}, 출력 {child.lines})")
            return
        daemon = (
            "읽기에 막혀 있었다"
            if thread_end is None
            else f"이미 돌아와 있었다({describe(thread_end[1:])})"
        )
        self.say(
            f"제품의 모양: 주 스레드가 끝난 지 {gone - float(main_end[0]):.3f}초 뒤 프로세스가 "
            f"사라졌다(종료 코드 {code}). 그때 daemon 스레드는 {daemon}"
        )

    def shared_test(self, folder: str) -> None:
        """한 번도 본 적 없는 같은 폴더를 프로세스 셋이 함께 볼 때 누가 SIGKILL 에 끝나는지 본다."""
        first = self.start_call("stat", f"{folder}/a.txt")
        time.sleep(1.0)
        second = self.start_call("stat", f"{folder}/b.txt")
        third = self.start_call("read", f"{folder}/sub/x.txt")
        self.say(
            f"같은 폴더 {folder} 를 처음 보는 프로세스 셋을 띄웠다(먼저 a.txt 의 os.stat, 1초 뒤 "
            "b.txt 의 os.stat 과 sub/x.txt 의 open().read())"
        )
        time.sleep(3.0)
        wait = SIGNAL_WAIT_SECONDS
        ended = self.send(second, signal.SIGKILL, f"{folder} 를 나중에 본 b.txt 쪽에 SIGKILL", wait)
        self.send(first, signal.SIGKILL, f"{folder} 를 먼저 본 a.txt 쪽에 SIGKILL", wait)
        if not ended:
            started = time.monotonic()
            try:
                code = second.process.wait(END_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                self.say(f"앞서 SIGKILL 을 받은 {folder}/b.txt 쪽: a.txt 쪽이 죽어도 남아 있다")
            else:
                elapsed = time.monotonic() - started
                self.say(
                    f"앞서 SIGKILL 을 받은 {folder}/b.txt 쪽: a.txt 쪽이 죽은 지 "
                    f"{elapsed:.3f}초 안에 끝났다(종료 코드 {code})"
                )
        self.send(third, signal.SIGKILL, f"{folder} 를 나중에 본 sub/x.txt 쪽에 SIGKILL", wait)

    def shared_phase(self) -> None:
        self.sleep_until(SHARED_AT)
        self.shared_test("t040")

    def late_phase(self) -> None:
        """끊고 200초 뒤(커널이 서버를 죽었다고 본 뒤)에도 SIGTERM 과 SIGKILL 이 듣는지 본다."""
        self.sleep_until(FIRST_AT)
        old_term = self.start_call("stat", "t051/a.txt")
        old_kill = self.start_call("read", "t050/a.txt")
        self.sleep_until(LATE_NEW_AT)
        new_kill = self.start_call("read", "t052/a.txt")
        self.say(
            f"늦은 신호 시험: 끊고 {FIRST_AT:.0f}초에 띄워 둔 프로세스 둘(t050, t051)에 더해 새 "
            "프로세스(t052)를 띄웠다"
        )
        self.sleep_until(LATE_AT)
        wait = SIGNAL_WAIT_SECONDS
        self.send(old_term, signal.SIGTERM, "늦은 신호 시험: 처음부터 막힌 t051 쪽에 SIGTERM", wait)
        self.send(old_kill, signal.SIGKILL, "늦은 신호 시험: 처음부터 막힌 t050 쪽에 SIGKILL", wait)
        self.send(new_kill, signal.SIGKILL, "늦은 신호 시험: 5초 전에 띄운 t052 쪽에 SIGKILL", wait)
        self.shared_test("t041")

    def idle(self) -> bool:
        waiting = any(call.returned_at is None for call in self.calls)
        busy = any(helper.is_alive() for helper in self.helpers)
        return not self.pending and not waiting and not busy

    def kill_leftovers(self) -> None:
        left = [child for child in self.children if child.process.poll() is None]
        for child in left:
            child.process.kill()
        stuck = 0
        for child in left:
            try:
                child.process.wait(END_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                stuck += 1
        self.say(f"끝에 남은 자식 {len(left)}개에 SIGKILL 을 보냈다. 그래도 끝나지 않은 수 {stuck}")

    def prepare(self) -> Child:
        """서버가 살아 있을 때 파일 둘을 열어 둔다. 둘째는 신호 시험에 쓴다."""
        read_later = self.start_child("preopened", f"{self.root}/big1.bin", str(self.ctl), "pre1")
        kill_later = self.start_child("preopened", f"{self.root}/big2.bin", str(self.ctl), "pre2")
        for name, child in (("pre1", read_later), ("pre2", kill_later)):
            if not wait_for_file(self.ctl / name, 60.0):
                emit(f"  파일을 미리 열지 못했다({name}): {child.lines}")
        (self.ctl / "ready").touch()
        wait_for_file(self.ctl / "t_fail", 3600.0)
        self.t0 = time.time()
        self.calls.append(Call(PREOPENED, "preopened", "big1.bin", read_later, self.t0 + FIRST_AT))
        return kill_later

    def run(self) -> None:
        kill_later = self.prepare()
        self.plan(self.t0, TIMED_BATCHES)
        self.helpers = [
            threading.Thread(target=self.signal_phase, args=(kill_later,), daemon=True),
            threading.Thread(target=self.shape_phase, daemon=True),
            threading.Thread(target=self.shared_phase, daemon=True),
        ]
        if self.limit >= LATE_NEEDS_LIMIT:
            self.helpers.append(threading.Thread(target=self.late_phase, daemon=True))
        for helper in self.helpers:
            helper.start()
        asked = False
        marks = sorted({mark for mark in (MARK_AT, self.limit) if mark <= self.limit})
        while True:
            now = time.time()
            self.fire_due(now)
            self.collect(now)
            if marks and now >= self.t0 + marks[0] and self.t_restore is None:
                self.note_waiting(f"{marks.pop(0):.0f}초 시점:")
            if self.t_restore is None:
                if not asked and (now >= self.t0 + self.limit or self.idle()):
                    asked = True
                    (self.ctl / "want_restore").touch()
                if (self.ctl / "t_restore").exists():
                    self.t_restore = time.time()
                    self.say("서버를 다시 잇는 명령을 친다(inner.sh)")
                    self.pending.clear()
                    self.plan(self.t_restore, AFTER_RESTORE)
            elif now >= self.t_restore + RESTORE_WATCH_SECONDS:
                break
            elif self.idle() and now >= self.t_restore + RESTORE_SECOND_AT + 1.0:
                break
            time.sleep(POLL_SECONDS)
        self.note_waiting("끝:")
        self.kill_leftovers()


def main() -> None:
    tag, command, arguments = sys.argv[1], sys.argv[2], sys.argv[3:]
    if command == "suite":
        Suite(tag, arguments[0], arguments[1], float(arguments[2])).run()
    elif command == "once":
        run_once(tag, arguments[0], arguments[1], float(arguments[2]))
    elif command == "call":
        run_call(arguments[0], arguments[1], arguments[2])
    elif command == "preopened":
        run_preopened(arguments[0], arguments[1], arguments[2])
    elif command == "shape":
        run_shape(arguments[0], float(arguments[1]))
    elif command == "worker":
        run_worker(arguments[0], arguments[1])
    else:
        raise SystemExit(f"모르는 명령: {command}")


if __name__ == "__main__":
    main()
