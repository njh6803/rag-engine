"""대상 사양에서 검색 지연을 재는 프로브(티켓 core 16, 명세 Testing Decisions의 마지막 항목).

실제 TEI(CPU 이미지 둘)와 규칙으로 지은 표본 문서(`corpus.py`)로 한 번에 아래를 재고, 사람이 읽는
보고를 표준 출력에 낸다(저장한 출력은 `probe_out.txt`).

1. 기계 사양과 컨테이너 사양, 잰 판.
2. 표본을 `rag-engine ingest --wait`로 넣는 시간과 작업자 로그(`job_finished`)의 단계별 지연(파싱,
   임베딩, 쓰기), 조각 수와 토큰 수.
3. 표본마다 파서를 자식 프로세스에서 돌린 시간과 최대 메모리(파싱 한도 넷이 표본을 막는지), 한도
   근처의 큰 PDF 하나.
4. TEI에 직접 건 임베딩과 리랭크의 배치 크기별 처리량(`RAG_TEI_BATCH_SIZE` 판단).
5. `/mcp`의 `search`에 동시 요청 수를 달리해 건 지연. 설정 조합(`RAG_SEARCH_CANDIDATES`,
   `RAG_TEI_BATCH_SIZE`)마다 서버를 새로 띄운다. 단계별 지연(임베딩, SQL, 리랭크)은 서버 로그의
   `search` 이벤트에서 모은다.

띄우는 법(저장소 루트에서. 첫 기동은 모델 둘을 허깅페이스에서 받고, TEI 이미지는
`ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4`다). 둘을 한꺼번에 올리면 Docker VM
15.6GiB에서 임베딩이 메모리 부족으로 죽으므로 임베딩이 `/health` 200을 낸 뒤 리랭커를 올린다
(`compose.yml` 머리 주석):

    docker compose -f compose.test.yml up -d --wait
    docker compose -f .scratch/core/probes/search-latency/compose.yml up -d embedding
    docker compose -f .scratch/core/probes/search-latency/compose.yml up -d reranker
    uv run python -X utf8 .scratch/core/probes/search-latency/probe.py > out.txt

127.0.0.1:55432의 테스트 PostgreSQL(`pgvector/pgvector:0.8.7-pg18-trixie`)에 `rag_latency_probe`
데이터베이스를 새로 만들고(있으면 지운다), TEI는 127.0.0.1:18081(임베딩)·18082(리랭커), 서버는
127.0.0.1:18090에 띄운다. 서버와 작업자는 이 저장소의 `rag-engine` 명령을 하위 프로세스로 돌려 서버
쪽 시간이 실제 서버의 것이게 한다. 표본과 로그는 `--work-dir`(기본: 임시 폴더 아래)에 쓴다.

기본값 판정 기준(첫 전체 실행 전에 이 독스트링에 적었다. 커밋 전이라 이력으로는 확인되지 않는다.
실행 뒤에 바꾼 것은 아래 "기준을 바꾼 것"에 적는다). 이 프로브의 "대상 사양"은 설계가 정한 메모리
32GB 기준의 CPU 기계(ADR 0010)를 이 개발 PC(보고의 기계 사양)로 대신한 것이다. 후보 수는 동시 4건의
서버 `search` 지연 p95가 `RAG_SEARCH_TIMEOUT_SECONDS`(20초)의 절반(10초) 이하이고 오류가 없는 가장
큰 값을 고르며(50이 그렇다면 그대로 둔다), 배치 크기는 TEI 직접 처리량이 16과 32에서 10% 안으로
같으면 32를 두고 32가 더 느리면 낮춘다. 배치 기준은 임베딩 처리량만 본다.

잴 수 없는 것(보고도 같은 말을 적는다). 서버와 작업자와 클라이언트가 TEI와 한 기계에서 CPU를 나눠
쓴다. 파서는 이 기계의 운영체제(Windows)에서 돌고 컨테이너(리눅스)에서의 메모리 한도(`RLIMIT_AS`)는
걸리지 않는다. 표본이 작아(조각 수천 개 미만) SQL 단계는 HNSW 색인이 작은 표에서 잰 값이다. 표본은
규칙으로 지은 글이라 검색 품질(search-eval의 몫)은 재지 않는다. 호스트가 다른 세션의 작업과 CPU를
나눠 써서(보고의 호스트 CPU가 늘 90~100%) 같은 호출의 시간이 실행마다 크게 달랐다(리랭크 1개 호출은
저장한 실행에서 40초, 저장하지 않은 두 실행에서 3.4초와 68초). 절대 시간은 이 PC의 이 시각의 값이고,
아래 판정은 크기의 차수와 단계 사이의 비율에만 기댄다. 측정용으로 TEI 시간 제한을 1800초, 검색 시간
제한을 3600초로 늘려 돌렸고(기본이면 느린 호출이 오류로 잘려 단계별 시간을 못 잰다), TEI는
`--max-batch-tokens 4096`이다(`compose.yml` 머리 주석).

결과 요약(`probe_out.txt`, 2026-11-13, 표본 12개·조각 91개·토큰 3.4만. 크기와 설정마다 한 번씩만
쟀다. 같은 호출이 실행마다 크게 흔들렸으므로 아래 수는 이 실행의 값이다):
- 리랭커 없이(후보 50)는 동시 4건의 서버 `search` p95가 1.05초, 동시 8건이 3.2초이고 오류가 없다.
- 리랭커를 켜면 후보 5개가 단건 15.5~17.3초(기본 한도 20초 안), 동시 4건 p95 281초(네 건 모두 20초
  초과)다. 후보 10개와 50개는 동시 1건만 쟀고 각각 94초와 130초다. 시간은 거의 모두 `rerank_ms`다
  (임베딩 0.1~0.8초, SQL 0.01~0.16초). 리랭커 컨테이너의 TEI 로그가 `model.onnx` 없음과
  `model.safetensors` 내려받기를 찍는다. 느린 까닭이 candle 폴백이라는 것은 로그를 읽은 추정이다.
- 임베딩은 한 호출 16개와 32개의 처리량이 296과 290 토큰/s로 2% 안이다. 32개 한 호출은 53.2초로
  `RAG_TEI_TIMEOUT_SECONDS`(60초)에 가깝다. 리랭크는 32개 한 호출이 100.6초로 60초를 넘었다(8개
  41.6초). 같은 표본의 수집 작업 12개는 파싱이 합 82초, 임베딩이 합 382초(조각당 4.2초)다.
- 파싱: 작업자 로그의 `parse_ms`는 원본 읽기부터 파싱 결과 저장까지(`index_document.py`의 한 구간)
  라서 `RAG_PARSE_TIMEOUT_SECONDS`가 세는 구간(자식을 띄운 때부터 메시지를 받을 때까지)보다 넓다.
  표본 12개에서 p50 5.8초, 최대 11.9초다. 표본마다 파서만 잰 시간은 0.3초 이하라 20~40배 차이가
  나는데 원인을 가르지 않았다(자식 프로세스의 시작과 import, 결과의 직렬화와 검증, 데이터베이스
  저장, 작업자 동시 2개, 호스트 100% 점유가 후보다). 한도 근처 PDF(1000쪽)는 파서만 65초이고 표본의
  `parse_ms` 최대를 더해도 300초 안이다(조각 수에 비례해 늘어나는 저장 몫은 표본이 작아 재지
  못했다). 최대 메모리는 표본 12개가 102MiB, 1000쪽 PDF가 작업 집합 1475MiB다. 이 값은 리눅스
  `RLIMIT_AS`(가상 메모리) 2GiB와 같은 값이 아니라서 2GiB 한도 안인지는 확인하지 못했다.
- 백분위: 서버 `search` p95는 건수가 20 미만이라 최댓값과 같다(동시 4건 p95 1.05초는 n=12의 최대).

기준을 바꾼 것. 후보 수 기준은 리랭커 유무를 가르지 않고 적었다. 글자 그대로 적용하면 리랭커 없이
후보 50, 동시 4건의 p95 1.05초가 통과하므로 50을 둔다. 그러나 이 서버의 기본 구성은 리랭커가 켜진
것이라 기준을 리랭커를 켠 구성에 걸어 다시 읽었고(이 한정은 결과를 본 뒤 더했다), 그 구성에서는 잰
조합(후보 5·10·50)이 모두 못 맞춰 고를 값이 없었다. 두 읽기가 같은 결론(기본값 50 유지)이라 기준을
풀어 값을 바꾸지 않았다. 후보 4 이하와 후보 10·50의 동시 4건은 재지 않아, 후보 수를 줄이면 맞는지는
알 수 없고 5에서 이미 단건이 한도에 닿는다. 배치 기준은 임베딩 처리량만 보았다. 리랭크 32개 한
호출이 TEI 시간 제한을 넘은 것은 기준에 없었고, 리랭커를 켠 기본 후보 50의 검색은 어차피 위의
이유로 20초를 넘으므로 결론을 바꾸지 않았다(수집은 임베딩만 쓴다). 또 `--max-batch-tokens 4096`이면
조각 약 490토큰이 한 배치에 8개쯤 들어 8개 이상에서 처리량이 평평한 것이 이 한도의 결과일 수 있다.
그러면 16과 32의 2% 안이라는 판정은 이 구성에서 둘을 가르지 못한 것이고, 기본 16384에서의 배치
효과는 재지 못했다(TEI의 배치 규칙은 소스로 확인하지 않았다). 까닭과 남은 결정은 일지에 적었다.

`probe_out.txt`를 낸 뒤 고친 것(측정 절차는 그대로이고 다시 돌리지 않았다). TEI 최대 메모리 줄이
컨테이너 둘의 이름을 다 `probe`로 찍었다(앞의 값이 임베딩, 뒤의 값이 리랭커이고 이제 이름을 찍는다).
클라이언트 오류는 건수만 찍던 것에 첫 줄을 더했다. 기본값을 `settings.py`에서 읽는다. 서버를 띄운
설정 조합이 예외로 끝나도 리랭커를 다시 켠다. 기계 사양 절의 "기동 직후 유휴" 라벨은 "프로브를
시작할 때의"로 고쳤다(출력의 값은 컨테이너를 다시 띄운 뒤 시작한 프로브의 시작 시점 값이다).
컨테이너 메모리와 CPU를 보는 `DockerSampler`는 저장한 실행에서 쉬지 않고 `docker stats`를 돌려
측정 대상에 부하를 더했다(이제 2초 쉬고 컨테이너 둘만 본다). 부하는 시간을 늘리는 쪽이라 후보 50,
리랭커 없음의 통과 결론은 보수적이다. 오류가 난 호출은 지연 목록에서 뺀다(저장한 출력은 오류 0건이라
같다). `--skip-ingest` 플래그는 토큰을 얻지 못해 지웠다. `bootstrap-token`과 `ingest`의 실패는 종료
코드를 보고 멈춘다.

손으로 본 것(이 프로브가 다시 내지 않는다). 처음 전체 실행(출력을 저장하지 않았다)에서 리랭커
컨테이너가 리랭크 32개 호출 중 종료 코드 139(분할 오류)로 죽었다(`docker ps -a`와 `docker inspect`로
봤다). 저장한 실행에서는 같은 호출이 성공했다. 기본 시간 제한(TEI 60초)으로 돌린 시험 수집에서는
작업 둘이 `queued`로 남았고 임베딩이 작업당 65초쯤 걸렸다(시간 제한 탓으로 추정했을 뿐 원인을 가르지
않았다).
"""

import argparse
import asyncio
import json
import math
import os
import platform
import random
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum
from importlib import metadata
from pathlib import Path

import httpx
import httpx2
import psycopg
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from rag_engine.adapters.settings import Settings

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus  # noqa: E402

ADMIN_DATABASE_URL = "postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test"
PROBE_DATABASE = "rag_latency_probe"
EMBEDDING_URL = "http://127.0.0.1:18081"
RERANKER_URL = "http://127.0.0.1:18082"
SERVER_PORT = 18090
EMBEDDING_CONTAINER = "rag-latency-probe-embedding-1"
RERANKER_CONTAINER = "rag-latency-probe-reranker-1"
# 한도(명세 설정 절의 기본값). 표본이 이 값에 얼마나 닿는지를 본다.
PARSE_LIMITS = {"pages": 1000, "seconds": 300, "memory_mb": 2048, "text_mb": 64, "upload_mb": 100}
CLI = "from rag_engine.main import main; main()"
# 기본값은 `settings.py`에서 읽어 한 곳에만 둔다(`Settings`는 환경 변수 없이 클래스에서 읽는다).
DEFAULTS = {
    name: int(Settings.model_fields[name].default)
    for name in (
        "search_candidates",
        "tei_batch_size",
        "tei_timeout_seconds",
        "search_timeout_seconds",
    )
}
DEFAULT_TEI_TIMEOUT_SECONDS = DEFAULTS["tei_timeout_seconds"]
DEFAULT_SEARCH_TIMEOUT_SECONDS = DEFAULTS["search_timeout_seconds"]
MEASUREMENT_LIMITS = {
    "RAG_TEI_TIMEOUT_SECONDS": "1800",
    "RAG_SEARCH_TIMEOUT_SECONDS": "3600",
}


def say(text: str = "") -> None:
    print(text, flush=True)


def section(title: str) -> None:
    say()
    say(f"== {title} ==")


def percentile(values: list[float], fraction: float) -> float:
    """가까운 순위 방식의 백분위. 값이 없으면 nan이다."""
    if not values:
        return math.nan
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def summary(values: list[float]) -> str:
    if not values:
        return "값 없음"
    return (
        f"p50 {percentile(values, 0.5):.0f} / p95 {percentile(values, 0.95):.0f} / "
        f"max {max(values):.0f} ms (n={len(values)})"
    )


# --- 기계 사양 -------------------------------------------------------------------------------


def cpu_name() -> str:
    if sys.platform == "win32":
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        )
        with key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def total_memory_gib() -> float:
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("load", ctypes.c_ulong),
                ("total_phys", ctypes.c_ulonglong),
                ("avail_phys", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong),
                ("avail_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("avail_virtual", ctypes.c_ulonglong),
                ("avail_extended", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.total_phys / 2**30
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal"):
            return int(line.split()[1]) / 2**20
    return math.nan


def cpu_times() -> tuple[int, int]:
    """호스트 전체의 (한가한 시간, 전체 시간). 단위는 운영체제의 틱이고 차이만 쓴다."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        ctypes.WinDLL("kernel32").GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        )

        def ticks(value: wintypes.FILETIME) -> int:
            return (value.dwHighDateTime << 32) | value.dwLowDateTime

        return ticks(idle), ticks(kernel) + ticks(user)
    fields = [int(part) for part in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    return fields[3] + fields[4], sum(fields)


class HostLoad:
    """구간 동안 호스트 전체의 CPU 점유율 평균(%). 이 프로브의 서버와 클라이언트와 TEI 컨테이너뿐
    아니라 같은 기계에서 도는 다른 프로세스의 몫도 든다. 측정값이 다른 부하에 얼마나 흔들렸는지
    읽으려는 것이다."""

    def __init__(self) -> None:
        self._start = cpu_times()

    def percent(self) -> float:
        idle, total = cpu_times()
        span = total - self._start[1]
        return 100.0 * (1 - (idle - self._start[0]) / span) if span > 0 else math.nan


def docker_output(*args: str) -> str:
    done = subprocess.run(
        ["docker", *args], capture_output=True, text=True, encoding="utf-8", check=False
    )
    return (done.stdout + done.stderr).strip()


def report_machine() -> None:
    section("기계 사양")
    say(f"운영체제: {platform.platform()}")
    say(f"CPU: {cpu_name()} (논리 코어 {os.cpu_count()})")
    say(f"메모리: {total_memory_gib():.1f} GiB")
    say(f"Python: {platform.python_version()}")
    docker_info = docker_output("info", "--format", "{{.ServerVersion}} / {{.OperatingSystem}}")
    docker_cpu = docker_output("info", "--format", "{{.NCPU}} CPU, {{.MemTotal}} bytes")
    say(f"Docker: {docker_info}; VM {docker_cpu}")
    for container in (EMBEDDING_CONTAINER, RERANKER_CONTAINER):
        image = docker_output("inspect", "--format", "{{.Config.Image}}", container)
        command = docker_output("inspect", "--format", "{{json .Config.Cmd}}", container)
        idle = docker_output(
            "stats", "--no-stream", "--format", "{{.MemUsage}} / CPU {{.CPUPerc}}", container
        )
        say(f"{container}: {image} {command}")
        say(f"  프로브를 시작할 때의 메모리·CPU: {idle}")
        logs = docker_output("logs", container)
        for line in logs.splitlines():
            clean = re.sub(r"\x1b\[[0-9;]*m", "", line)
            if re.search(
                r"Starting .*backend|Could not start|Downloading `model|Starting \d+ tok", clean
            ):
                say(f"  TEI 로그: {clean[-150:]}")
    packages = (
        "rag-engine",
        "kiwipiepy",
        "pdfplumber",
        "python-docx",
        "python-hwpx",
        "mcp",
        "psycopg",
    )
    say("판: " + ", ".join(f"{name} {metadata.version(name)}" for name in packages))
    candidates, batch = DEFAULTS["search_candidates"], DEFAULTS["tei_batch_size"]
    say(f"설정 기본값(settings.py): RAG_SEARCH_CANDIDATES={candidates}, RAG_TEI_BATCH_SIZE={batch}")


# --- 환경과 하위 프로세스 ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path

    @property
    def corpus(self) -> Path:
        return self.root / "corpus"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def runs(self) -> Path:
        return self.root / "runs"


def probe_database_url() -> str:
    return ADMIN_DATABASE_URL.rsplit("/", 1)[0] + "/" + PROBE_DATABASE


def command_env(workspace: Workspace, **extra: str) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("RAG_")}
    env.update(
        {
            "PYTHONUTF8": "1",
            "RAG_DATABASE_URL": probe_database_url(),
            "RAG_DATA_DIR": str(workspace.data),
            "RAG_ALLOWED_HOSTS": "127.0.0.1",
            "RAG_DEFAULT_EMBEDDING_URL": EMBEDDING_URL,
            "RAG_DEFAULT_RERANKER_URL": RERANKER_URL,
            "RAG_LOG_FORMAT": "json",
            # 측정용으로만 늘린 시간 제한(기본은 60초, 20초). 기본값 그대로면 느린 호출이 오류로
            # 잘려 단계별 소요 시간을 잴 수 없다. 기본 한도에 드는지는 소요 시간을 한도와 맞댄다.
            **MEASUREMENT_LIMITS,
        }
    )
    env.update(extra)
    return env


def run_cli(workspace: Workspace, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", CLI, *args],
        env=command_env(workspace, **extra),
        cwd=workspace.root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def start_cli(
    workspace: Workspace, log: Path, *args: str, **extra: str
) -> tuple[subprocess.Popen[bytes], object]:
    handle = log.open("wb")
    process = subprocess.Popen(
        [sys.executable, "-c", CLI, *args],
        env=command_env(workspace, **extra),
        cwd=workspace.root,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    return process, handle


def stop(process: subprocess.Popen[bytes], handle: object) -> None:
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    close = getattr(handle, "close", None)
    if callable(close):
        close()


def log_events(log: Path, event: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("{") and f'"event": "{event}"' in raw:
            found.append(json.loads(raw))
    return found


def number(event: dict[str, object], name: str) -> float:
    value = event.get(name)
    return float(value) if isinstance(value, int | float) else math.nan


def recreate_database() -> None:
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as connection:
        connection.execute(f"DROP DATABASE IF EXISTS {PROBE_DATABASE} WITH (FORCE)")
        connection.execute(f"CREATE DATABASE {PROBE_DATABASE}")


def wait_http(url: str, *, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise SystemExit(f"{url}이 {seconds:.0f}초 안에 응답하지 않았다")


# --- 수집 ------------------------------------------------------------------------------------


def ingest(workspace: Workspace, samples: list[corpus.SampleFile]) -> str:
    """데이터베이스를 새로 만들고 표본을 `ingest --wait`로 넣는다. 관리 토큰 원문을 낸다."""
    section("수집(ingest --wait)")
    recreate_database()
    migrate(workspace)
    issued = run_cli(workspace, "bootstrap-token")
    token = issued.stdout.strip()
    if issued.returncode != 0 or not token:
        raise SystemExit(f"bootstrap-token 실패: {issued.stderr[-500:]}")
    log = workspace.runs / "worker.log"
    worker, handle = start_cli(workspace, log, "worker")
    try:
        load = HostLoad()
        started = time.perf_counter()
        done = run_cli(workspace, "ingest", str(workspace.corpus), "--wait", "--timeout", "7200")
        wall = time.perf_counter() - started
        host_cpu = load.percent()
    finally:
        stop(worker, handle)
    say(
        f"종료 코드 {done.returncode}, 벽시계 {wall:.1f}s, 표본 {len(samples)}개, "
        f"호스트 CPU 평균 {host_cpu:.0f}%"
    )
    if done.returncode != 0:
        raise SystemExit(f"ingest 실패: {done.stderr[-500:]} (작업자 로그 {log})")
    say(f"측정용 시간 제한: {MEASUREMENT_LIMITS}(기본은 TEI 60초, 검색 20초)")
    finished = [e for e in log_events(log, "job_finished") if e.get("kind") is not None]
    results: dict[str, int] = {}
    for event in finished:
        results[str(event.get("result"))] = results.get(str(event.get("result")), 0) + 1
    say(f"작업 {len(finished)}개: {results}")
    for name in ("parse_ms", "embedding_ms", "write_ms", "duration_ms"):
        values = [number(e, name) for e in finished]
        total = sum(values)
        say(f"  {name}: 합 {total / 1000:.1f}s, " + summary(values))
    with psycopg.connect(probe_database_url()) as connection:
        count, tokens, longest = connection.execute(
            "SELECT count(*), coalesce(sum(token_count), 0), coalesce(max(token_count), 0) "
            "FROM chunks"
        ).fetchone() or (0, 0, 0)
        counts = connection.execute(
            "SELECT token_count FROM chunks ORDER BY token_count"
        ).fetchall()
    token_counts = [float(row[0]) for row in counts]
    say(
        f"조각 {count}개, 토큰 합 {tokens}, 최대 {longest}, 중앙값 "
        f"{statistics.median(token_counts) if token_counts else 0:.0f}"
    )
    if count:
        say(f"조각당 임베딩 {sum(number(e, 'embedding_ms') for e in finished) / count:.0f} ms")
    return token


# --- 파싱 한도 -------------------------------------------------------------------------------


def peak_memory_mb() -> float:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("page_faults", wintypes.DWORD),
                ("peak_working_set", ctypes.c_size_t),
                ("working_set", ctypes.c_size_t),
                ("quota_peak_paged", ctypes.c_size_t),
                ("quota_paged", ctypes.c_size_t),
                ("quota_peak_nonpaged", ctypes.c_size_t),
                ("quota_nonpaged", ctypes.c_size_t),
                ("pagefile", ctypes.c_size_t),
                ("peak_pagefile", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel32 = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            raise OSError("GetProcessMemoryInfo 실패")
        return counters.peak_working_set / 2**20
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def parse_child(path: Path) -> None:
    """자식 프로세스의 입구. 파서만 돌려 시간과 최대 메모리를 JSON 한 줄로 낸다."""
    from rag_engine.adapters.parsers.docx_parser import DocxParser
    from rag_engine.adapters.parsers.hwpx_parser import HwpxParser
    from rag_engine.adapters.parsers.pdf_parser import PdfParser
    from rag_engine.domain.media_types import DOCX_MIME, HWPX_MIME, PDF_MIME
    from rag_engine.domain.parsing import ParserLimits

    parsers = {
        ".pdf": (PdfParser(), PDF_MIME),
        ".docx": (DocxParser(), DOCX_MIME),
        ".hwpx": (HwpxParser(), HWPX_MIME),
    }
    parser, mime = parsers[path.suffix]
    data = path.read_bytes()
    baseline = peak_memory_mb()
    started = time.perf_counter()
    blocks = parser.parse(data, mime, ParserLimits(max_pages=PARSE_LIMITS["pages"]))
    elapsed = time.perf_counter() - started
    text_bytes = sum(len(block.text.encode()) for block in blocks)
    say(
        json.dumps(
            {
                "seconds": elapsed,
                "blocks": len(blocks),
                "text_bytes": text_bytes,
                "baseline_mb": baseline,
                "peak_mb": peak_memory_mb(),
            }
        )
    )


def measure_parse(path: Path) -> dict[str, float]:
    done = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--parse-child", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    if done.returncode != 0:
        raise SystemExit(f"{path.name} 파싱 자식 실패: {done.stderr[-500:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def report_parsing(workspace: Workspace, samples: list[corpus.SampleFile]) -> None:
    section("파싱 시간과 메모리(표본마다 새 프로세스, 파서만)")
    if sys.platform == "win32":
        say("(Windows 에서 돌아 `RLIMIT_AS`는 걸리지 않는다. 최대 메모리는 프로세스 전체의")
        say(" 최대 작업 집합이고 `base`는 import 직후의 값이라 둘의 차가 파싱이 더한 몫이다.)")
    else:
        say("(최대 메모리는 프로세스의 최대 상주 집합이고 `RLIMIT_AS`(가상 메모리)와는 다르다.)")
    by_kind: dict[str, list[dict[str, float]]] = {}
    for sample in samples:
        by_kind.setdefault(sample.kind, []).append(measure_parse(sample.path))
    for kind, rows in by_kind.items():
        seconds = [row["seconds"] for row in rows]
        peaks = [row["peak_mb"] for row in rows]
        bases = [row["baseline_mb"] for row in rows]
        size = max(row["text_bytes"] for row in rows)
        say(
            f"  {kind}: {len(rows)}개, 파싱 최대 {max(seconds):.2f}s"
            f"(중앙값 {statistics.median(seconds):.2f}s), 최대 메모리 {max(peaks):.0f}MiB"
            f"(base {statistics.median(bases):.0f}MiB), 글 최대 {size / 2**20:.3f}MiB"
        )
    big = workspace.root / "stress" / "pdf_1000_pages.pdf"
    big.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    pages = corpus.pdf_pages(rng, "보안", pages=PARSE_LIMITS["pages"])
    big.write_bytes(corpus.pdf_bytes(pages))
    row = measure_parse(big)
    say(
        f"  한도 근처 PDF(쪽 {len(pages)}, {big.stat().st_size / 2**20:.1f}MiB): "
        f"파싱 {row['seconds']:.1f}s, 최대 메모리 {row['peak_mb']:.0f}MiB, "
        f"글 {row['text_bytes'] / 2**20:.2f}MiB, 블록 {row['blocks']:.0f}"
    )
    say(
        f"  한도: 쪽 {PARSE_LIMITS['pages']}, 시간 {PARSE_LIMITS['seconds']}s, "
        f"메모리 {PARSE_LIMITS['memory_mb']}MiB, 글 {PARSE_LIMITS['text_mb']}MiB, "
        f"업로드 {PARSE_LIMITS['upload_mb']}MiB"
    )


# --- TEI 직접 ---------------------------------------------------------------------------------


def chunk_rows(limit: int) -> list[tuple[str, int]]:
    """조각 글과 토큰 수. 표가 작으면 되풀이해 `limit`개를 채운다."""
    with psycopg.connect(probe_database_url()) as connection:
        rows = connection.execute(
            "SELECT text, token_count FROM chunks ORDER BY token_count DESC LIMIT %s", (limit,)
        ).fetchall()
    found = [(str(row[0]), int(row[1])) for row in rows]
    return (found * math.ceil(limit / max(1, len(found))))[:limit]


def timed_post(url: str, body: dict[str, object]) -> tuple[float, str]:
    """소요 시간과 오류 설명(성공이면 빈 글)을 돌려준다. 오류도 보고에 남겨 다음 단계로 간다."""
    started = time.perf_counter()
    try:
        response = httpx.post(url, json=body, timeout=3600)
        response.raise_for_status()
    except httpx.HTTPError as error:
        return time.perf_counter() - started, f"{type(error).__name__}: {error}"[:100]
    return time.perf_counter() - started, ""


def ensure_tei() -> None:
    """응답하지 않는 TEI 컨테이너를 `docker start`로 되살린다(죽은 일은 보고에 적는다)."""
    for name, url in ((EMBEDDING_CONTAINER, EMBEDDING_URL), (RERANKER_CONTAINER, RERANKER_URL)):
        try:
            alive = httpx.get(f"{url}/health", timeout=5).status_code == 200
        except httpx.HTTPError:
            alive = False
        if not alive:
            state = docker_output(
                "inspect",
                name,
                "--format",
                "종료 코드 {{.State.ExitCode}}, OOM {{.State.OOMKilled}}",
            )
            say(f"  ! {name} 가 응답하지 않는다({state}). docker start 로 되살린다")
            docker_output("start", name)
            wait_http(f"{url}/health", seconds=1800)


def report_tei_direct(sizes: tuple[int, ...], rerank_sizes: tuple[int, ...]) -> None:
    section("TEI 직접(한 호출에 보내는 글의 수별 소요 시간. 크기마다 한 번)")
    rows = chunk_rows(32)
    texts = [text for text, _ in rows]
    tokens = [count for _, count in rows]
    median_chars = statistics.median(len(text) for text in texts)
    say(
        f"조각 글 {len(texts)}개(토큰 수 상위), 글당 토큰 중앙값 {statistics.median(tokens):.0f}"
        f"(특수 토큰 제외), 글자 수 중앙값 {median_chars:.0f}"
    )
    limit = DEFAULT_TEI_TIMEOUT_SECONDS
    say(f"기본 한도 비교: 한 호출이 {limit}초(RAG_TEI_TIMEOUT_SECONDS)를 넘으면 x")
    query = "신입사원 연차휴가 처리 기한이 얼마나 되나요"
    rerank_fixed = {
        "query": query,
        "truncate": True,
        "truncation_direction": "Right",
        "raw_scores": False,
        "return_text": False,
    }
    for label, url, label_sizes in (
        ("임베딩", f"{EMBEDDING_URL}/v1/embeddings", sizes),
        ("리랭크", f"{RERANKER_URL}/rerank", rerank_sizes),
    ):
        for size in label_sizes:
            body: dict[str, object] = (
                {"input": texts[:size], "model": "BAAI/bge-m3"}
                if label == "임베딩"
                else {**rerank_fixed, "texts": texts[:size]}
            )
            load = HostLoad()
            elapsed, error = timed_post(url, body)
            if error:
                say(f"  {label} {size:>2}개 한 호출: 실패({elapsed:.1f}s 뒤) {error}")
                ensure_tei()
                continue
            flag = "x" if elapsed > DEFAULT_TEI_TIMEOUT_SECONDS else " "
            say(
                f"  {label} {size:>2}개 한 호출: {elapsed:6.1f}s {flag} "
                f"글당 {elapsed / size:.2f}s, "
                f"{sum(tokens[:size]) / elapsed:.0f} 토큰/s, 호스트 CPU {load.percent():.0f}%"
            )


# --- 검색 부하 --------------------------------------------------------------------------------


@dataclass(slots=True)
class DockerSampler:
    """TEI 컨테이너 둘의 메모리와 CPU를 2초 쉬며 본다(`docker stats` 한 번이 1초 넘게 걸린다)."""

    memory: dict[str, float]
    cpu: dict[str, float]
    running: bool = True

    def poll(self) -> None:
        while self.running:
            out = docker_output(
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}",
                EMBEDDING_CONTAINER,
                RERANKER_CONTAINER,
            )
            for line in out.splitlines():
                name, usage, cpu = (line.split("|") + ["", ""])[:3]
                if name in (EMBEDDING_CONTAINER, RERANKER_CONTAINER):
                    used = usage.split("/")[0].strip()
                    value = self._number(re.sub(r"[^0-9.]", "", used))
                    if used.endswith("GiB"):
                        value *= 1024
                    self.memory[name] = max(self.memory.get(name, 0.0), value)
                    self.cpu[name] = max(self.cpu.get(name, 0.0), self._number(cpu.strip("%")))
            time.sleep(2)

    @staticmethod
    def _number(text: str) -> float:
        """기동 중에 Docker가 `--`를 찍는 칸은 0으로 읽는다."""
        try:
            return float(text)
        except ValueError:
            return 0.0


async def call_search(
    client: Client, queries: list[str], offset: int, calls: int
) -> tuple[list[float], list[str]]:
    latencies: list[float] = []
    failures: list[str] = []
    for index in range(calls):
        query = queries[(offset + index) % len(queries)]
        started = time.perf_counter()
        try:
            result = await client.call_tool("search", {"query": query, "top_k": 10})
        except Exception as error:  # noqa: BLE001 (오류를 세어 보고하고 재기를 잇는다)
            failures.append(f"{type(error).__name__}: {error}"[:100])
            continue
        if result.is_error:
            failures.append("tool_error")
        else:
            latencies.append((time.perf_counter() - started) * 1000)
    return latencies, failures


async def one_client(
    token: str, queries: list[str], offset: int, calls: int
) -> tuple[list[float], list[str]]:
    """클라이언트 하나가 `calls`번 부른다. 연결을 못 열어도 예외를 올리지 않고 오류 하나로 센다."""
    try:
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, timeout=3600
        ) as http:
            url = f"http://127.0.0.1:{SERVER_PORT}/mcp"
            async with Client(streamable_http_client(url, http_client=http)) as client:
                return await call_search(client, queries, offset, calls)
    except Exception as error:  # noqa: BLE001 (연결 실패도 오류로 세고 다음 설정으로 잇는다)
        return [], [f"connect {type(error).__name__}: {error}"[:100]]


async def run_level(
    token: str, queries: list[str], concurrency: int, calls: int
) -> tuple[list[float], list[str]]:
    outcomes = await asyncio.gather(
        *(one_client(token, queries, worker * 3, calls) for worker in range(concurrency))
    )
    latencies = [value for outcome in outcomes for value in outcome[0]]
    return latencies, [message for outcome in outcomes for message in outcome[1]]


class Reranking(Enum):
    ON = "리랭크 있음"
    OFF = "리랭커 없음(임베딩과 SQL만)"


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """서버를 새로 띄워 재는 설정 한 조합. `levels`는 (동시 요청 수, 클라이언트마다 보낸 횟수)다."""

    candidates: int
    batch: int
    rerank: Reranking
    levels: tuple[tuple[int, int], ...]


def migrate(workspace: Workspace, **extra: str) -> None:
    done = run_cli(workspace, "migrate", **extra)
    if done.returncode != 0:
        raise SystemExit(f"migrate 실패: {done.stderr[-500:]}")


def set_reranker(workspace: Workspace, rerank: Reranking) -> None:
    """지식베이스의 리랭커를 켜거나 끈다. `migrate`가 기본 지식베이스를 설정값으로 고치므로
    `RAG_DEFAULT_RERANKER_URL`을 비워 다시 돌리면 리랭커가 없는 지식베이스가 된다."""
    migrate(workspace, RAG_DEFAULT_RERANKER_URL=RERANKER_URL if rerank is Reranking.ON else "")


def report_search(
    workspace: Workspace, token: str, queries: list[str], config: SearchConfig
) -> None:
    section(
        f"search 지연: RAG_SEARCH_CANDIDATES={config.candidates}, "
        f"RAG_TEI_BATCH_SIZE={config.batch}, {config.rerank.value}"
    )
    set_reranker(workspace, config.rerank)
    name_tail = f"c{config.candidates}_b{config.batch}_{config.rerank.name.lower()}"
    log = workspace.runs / f"server_{name_tail}.log"
    server, handle = start_cli(
        workspace,
        log,
        "serve",
        "--port",
        str(SERVER_PORT),
        RAG_SEARCH_CANDIDATES=str(config.candidates),
        RAG_TEI_BATCH_SIZE=str(config.batch),
    )
    try:
        wait_http(f"http://127.0.0.1:{SERVER_PORT}/health", seconds=60)
        asyncio.run(run_level(token, queries, 1, 1))  # 첫 호출의 `/info` 확인과 연결을 데운다
        seen = len(log_events(log, "search"))
        for concurrency, calls in config.levels:
            sampler = DockerSampler({}, {})
            thread = threading.Thread(target=sampler.poll, daemon=True)
            thread.start()
            load = HostLoad()
            started = time.perf_counter()
            latencies, failures = asyncio.run(run_level(token, queries, concurrency, calls))
            wall = time.perf_counter() - started
            host_cpu = load.percent()
            sampler.running = False
            thread.join(timeout=15)
            time.sleep(0.5)
            events = log_events(log, "search")[seen:]
            seen += len(events)
            say(
                f"- 동시 {concurrency:>2} × {calls}회 = {concurrency * calls}건, "
                f"오류 {len(failures)}, "
                f"처리량 {concurrency * calls / wall:.3f}건/s, 호스트 CPU 평균 {host_cpu:.0f}%"
            )
            if failures:
                say(f"    오류 첫 줄: {failures[0]}")
            say(f"    클라이언트 왕복: {summary(latencies)}")
            say(f"    서버 search 전체: {summary([number(e, 'duration_ms') for e in events])}")
            for name in ("embedding_ms", "sql_ms", "rerank_ms"):
                say(f"      {name}: {summary([number(e, name) for e in events])}")
            usage = [
                f"{label} {sampler.memory.get(name, math.nan):.0f} / "
                f"{sampler.cpu.get(name, math.nan):.0f}"
                for label, name in (
                    ("임베딩", EMBEDDING_CONTAINER),
                    ("리랭커", RERANKER_CONTAINER),
                )
            ]
            say("    TEI 최대 메모리 MiB / CPU %: " + ", ".join(usage))
            limit = DEFAULT_SEARCH_TIMEOUT_SECONDS * 1000
            over = sum(1 for e in events if number(e, "duration_ms") > limit)
            default_limit = DEFAULT_SEARCH_TIMEOUT_SECONDS
            say(f"    기본 시간 제한 {default_limit}초를 넘은 건: {over}/{len(events)}")
    finally:
        stop(server, handle)
        set_reranker(workspace, Reranking.ON)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--parse-child", type=Path, help="내부용: 파서 하나를 돌려 JSON 한 줄을 낸다"
    )
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--per-kind", type=int, default=4, help="형식(PDF, DOCX, HWPX)마다 표본 수")
    parser.add_argument("--sections", type=int, default=6, help="표본 하나의 장 수")
    parser.add_argument("--seed", type=int, default=20261113)
    parser.add_argument(
        "--quick", action="store_true", help="설정 조합 하나, 동시 1·2만 재는 동작 확인용"
    )
    args = parser.parse_args()
    if args.parse_child is not None:
        parse_child(args.parse_child)
        return

    root = args.work_dir or Path(tempfile.mkdtemp(prefix="rag_latency_probe_"))
    workspace = Workspace(root)
    for folder in (workspace.data, workspace.runs):
        folder.mkdir(parents=True, exist_ok=True)
    say(f"작업 폴더: {workspace.root}")
    wait_http(f"{EMBEDDING_URL}/health", seconds=1800)
    wait_http(f"{RERANKER_URL}/health", seconds=1800)
    report_machine()

    if workspace.corpus.exists():
        raise SystemExit(
            f"{workspace.corpus}이(가) 이미 있어 지우지 않고 멈춘다. 다른 --work-dir을 준다."
        )
    samples = corpus.write_corpus(
        workspace.corpus, seed=args.seed, per_kind=args.per_kind, sections=args.sections
    )
    section("표본")
    say(f"형식마다 {args.per_kind}개, 문서마다 {args.sections}장, 시드 {args.seed}")
    for kind in ("pdf", "docx", "hwpx"):
        files = [s for s in samples if s.kind == kind]
        kib = sum(s.path.stat().st_size for s in files) / 1024
        chars = sum(s.characters for s in files)
        say(f"  {kind}: {len(files)}개, 파일 크기 합 {kib:.0f}KiB, 본문 글자 수 합 {chars}")
    queries = corpus.queries(random.Random(args.seed + 1), 24)
    say(f"질의 {len(queries)}개(예: {queries[0]} / {queries[5]})")

    token = ingest(workspace, samples)
    report_parsing(workspace, samples)
    if args.quick:
        report_tei_direct((1, 4), (1, 4))
    else:
        report_tei_direct((1, 4, 8, 16, 32), (1, 8, 32))
    plan = [
        SearchConfig(5, 32, rerank=Reranking.ON, levels=((1, 2), (4, 1))),
        SearchConfig(10, 32, rerank=Reranking.ON, levels=((1, 1),)),
        SearchConfig(50, 32, rerank=Reranking.ON, levels=((1, 1),)),
        SearchConfig(50, 32, rerank=Reranking.OFF, levels=((1, 4), (4, 3), (8, 2))),
        SearchConfig(10, 8, rerank=Reranking.ON, levels=((1, 1),)),
    ]
    if args.quick:
        plan = [SearchConfig(5, 32, rerank=Reranking.ON, levels=((1, 1),))]
    for config in plan:
        ensure_tei()
        report_search(workspace, token, queries, config)


if __name__ == "__main__":
    main()
