"""`rag-engine serve`는 설정이 어긋나면 서버를 띄우지 않고 종료 코드 1로 끝나고, 설정이 맞으면 같은
설정으로 앱을 띄워 우리 포매터로만 로그를 낸다(ADR 0014, 명세 "로그, 요청 ID, 지연 기록")."""

import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from rag_engine.main import main

STARTUP_TIMEOUT_SECONDS = 30
SHUTDOWN_TIMEOUT_SECONDS = 15


def test_허용_호스트가_비면_종료_코드_1과_칸_이름을_내고_뜨지_않는다(
    seeded_command_environment: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RAG_ALLOWED_HOSTS", "")

    with pytest.raises(SystemExit) as caught:
        main(["serve"])

    output = capsys.readouterr()
    assert caught.value.code == 1
    assert "RAG_ALLOWED_HOSTS" in output.err
    assert seeded_command_environment not in output.err + output.out


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def test_serve가_뜨면_JSON_Lines만_남기고_접근_로그에_쿼리_문자열을_싣지_않는다(
    seeded_command_environment: str,
) -> None:
    port = _free_port()
    # 자식은 부모 환경(`RAG_*`가 시험용으로 정리된 것)을 이어받는다. 파이프로 나가는 stdout이
    # UTF-8이고 버퍼 없이 나가야 강제로 끝내도 로그가 남는다.
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; from rag_engine.main import main; main(sys.argv[1:])",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while True:
            if process.poll() is not None:
                _, error = process.communicate(timeout=SHUTDOWN_TIMEOUT_SECONDS)
                pytest.fail(f"serve가 떠 있기 전에 끝났다: {error.decode()}")
            try:
                if httpx.get(f"{base_url}/health").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if time.monotonic() > deadline:
                pytest.fail(f"serve가 {STARTUP_TIMEOUT_SECONDS}초 안에 뜨지 않았다")
            time.sleep(0.2)
        httpx.get(f"{base_url}/health?key=비밀_문서_키")
        unauthenticated = httpx.get(f"{base_url}/api/v1/admin/tokens")
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=SHUTDOWN_TIMEOUT_SECONDS)

    lines = [json.loads(line) for line in output.decode().splitlines() if line.strip()]
    assert unauthenticated.status_code == 401
    assert "uvicorn.access" not in {line["logger"] for line in lines}
    requests = [line for line in lines if line["event"] == "http_request"]
    assert [line["path"] for line in requests][-3:] == [
        "/health",
        "/health",
        "/api/v1/admin/tokens",
    ]
    assert "비밀" not in output.decode()
    assert seeded_command_environment not in output.decode()
