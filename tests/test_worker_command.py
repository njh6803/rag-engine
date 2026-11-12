"""`rag-engine worker`는 설정이 어긋나면 종료 코드 1로 끝나고, 설정이 맞으면 `NOTIFY`로 깨어나
작업을 처리하며 종료 신호에 종료 코드 0으로 나간다(명세 "수집 파이프라인과 작업"의 작업자 항목,
티켓 13). 진행 중인 작업을 끝내고 나가는 시점은 `tests/app/test_worker_service.py`가 같은 프로세스
안에서 본다.

프로세스를 실제로 띄워 보는 시험은 이 파일의 하나다. 종료 신호는 리눅스가 SIGTERM이고 Windows는
`CTRL_BREAK_EVENT`다(플랫폼 갈래이고 skip이 아니다). `RAG_WORKER_POLL_SECONDS`를 단언의 기한보다
크게 두어 작업이 폴링으로 지나가지 않고 알림으로 처리된다는 것을 보인다.
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import psycopg
import pytest
from tests.support.round_trip import RoundTrip, output

from rag_engine.main import main

STARTUP_TIMEOUT_SECONDS = 90
PROCESSING_TIMEOUT_SECONDS = 60
SHUTDOWN_TIMEOUT_SECONDS = 30
POLL_SECONDS = 300

휴가 = ("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")


def test_허용_호스트가_비면_종료_코드_1과_칸_이름을_내고_뜨지_않는다(
    seeded_command_environment: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RAG_ALLOWED_HOSTS", "")

    with pytest.raises(SystemExit) as caught:
        main(["worker"])

    output_text = capsys.readouterr()
    assert caught.value.code == 1
    assert "RAG_ALLOWED_HOSTS" in output_text.err
    assert seeded_command_environment not in output_text.err + output_text.out


class _Output:
    """하위 프로세스의 stdout을 다른 스레드에서 줄 단위로 모은다. 파이프를 읽지 않으면 가득 차
    자식이 멈춘다."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        assert process.stdout is not None
        self._stream = process.stdout
        self._lines: list[str] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        for raw in self._stream:
            with self._lock:
                self._lines.append(raw.decode(errors="replace"))

    def events(self) -> list[dict[str, object]]:
        with self._lock:
            lines = list(self._lines)
        parsed: list[dict[str, object]] = []
        for line in lines:
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return parsed

    def text(self) -> str:
        with self._lock:
            return "".join(self._lines)

    def wait_for(self, event: str, timeout: float, process: subprocess.Popen[bytes]) -> None:
        deadline = time.monotonic() + timeout
        while not any(each["event"] == event for each in self.events()):
            if process.poll() is not None:
                self._thread.join(5)
                code = process.returncode
                pytest.fail(f"{event}가 오기 전에 작업자가 끝났다(코드 {code}):\n{self.text()}")
            if time.monotonic() > deadline:
                pytest.fail(f"{event}가 {timeout}초 안에 오지 않았다:\n{self.text()}")
            time.sleep(0.1)


def _spawn_worker(round_trip: RoundTrip, work_dir: Path) -> subprocess.Popen[bytes]:
    settings = round_trip.server.settings
    # 개발자 셸의 `RAG_*`가 시험을 바꾸지 못하게 지우고 필요한 설정만 준다.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("RAG_")}
    environment |= {
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
        "RAG_DATABASE_URL": settings.database_url,
        "RAG_DATA_DIR": str(settings.data_dir),
        "RAG_ALLOWED_HOSTS": "localhost",
        "RAG_WORKER_POLL_SECONDS": str(POLL_SECONDS),
    }
    # Windows는 `CTRL_BREAK_EVENT`를 새 프로세스 그룹의 우두머리에게만 보낼 수 있다.
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; from rag_engine.main import main; main(sys.argv[1:])",
            "worker",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
        cwd=work_dir,
        creationflags=creationflags,
    )


def _request_stop(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        process.send_signal(signal.SIGTERM)


def _wait_for_job_status(database_url: str, status: str) -> None:
    deadline = time.monotonic() + PROCESSING_TIMEOUT_SECONDS
    while True:
        with psycopg.connect(database_url, autocommit=True) as connection:
            rows = connection.execute("SELECT status FROM jobs").fetchall()
        if [row[0] for row in rows] == [status]:
            return
        if time.monotonic() > deadline:
            pytest.fail(
                f"작업이 {PROCESSING_TIMEOUT_SECONDS}초 안에 {status}가 되지 않았다: {rows}"
            )
        time.sleep(0.2)


async def test_worker가_알림으로_깨어나_작업을_처리하고_종료_신호에_나간다(
    round_trip: RoundTrip, tmp_path: Path
) -> None:
    round_trip.drop_reranker()
    process = _spawn_worker(round_trip, tmp_path)
    logs = _Output(process)
    try:
        await asyncio.to_thread(logs.wait_for, "worker_started", STARTUP_TIMEOUT_SECONDS, process)
        ingested = await round_trip.ingest(*휴가)
        assert ingested.status_code == 202

        await asyncio.to_thread(
            _wait_for_job_status, round_trip.server.settings.database_url, "succeeded"
        )
        found = output(await round_trip.search("연차휴가"))
        _request_stop(process)
        exit_code = await asyncio.to_thread(process.wait, SHUTDOWN_TIMEOUT_SECONDS)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    events = logs.events()
    assert "연차휴가" in found.results[0].text
    assert exit_code == 0, logs.text()
    names = [each["event"] for each in events]
    assert (
        names.index("worker_started") < names.index("job_finished") < names.index("worker_stopped")
    )
    finished = [each for each in events if each["event"] == "job_finished"]
    assert [(each["result"], each["error_code"]) for each in finished] == [("succeeded", None)]
