"""release-image 명세의 프로브. 시제품 이미지 둘과 단독 compose 를 실제로 띄워 명세의 결정을 잰다.

    uv run python .scratch/release-image/probes/standalone/run.py --models-volume <볼륨> [단계 ...]

`--models-volume` 은 `BAAI/bge-m3` 가 이미 든 Docker 볼륨의 이름이다(TEI 의 `/data`). 프로브는
모델을 내려받지 않는다. 단계는 적은 차례대로 돌고, 생략하면
`build sse up accept checks recover down offline` 전부다.

- `build`   시제품 Dockerfile 로 서버와 작업자 이미지를 짓는다. 이미지 안의 번호, 사용자, 라벨,
            크기, 두 이미지가 함께 쓰는 층을 찍고, 번호 없이 지으면 실패하는지 본다.
- `sse`     서버 자리에 1초 간격으로 사건 다섯을 보내는 가짜 뒷단(`sse_stub.py`)을 띄워, 프록시
            설정 둘(`site.conf`, nginx 기본값인 `site.buffered.conf`)과 `X-Accel-Buffering` 머리의
            유무마다 사건이 닿은 시각을 잰다. 그 앞에, 몇 초 만에 뜨는 이 뒷단과 프록시를 함께
            띄워 프록시가 뒷단을 기다리지 않을 때와 기다릴 때 502 가 이어지는 시간을 잰다.
- `up`      단독 compose 전체(프록시, PostgreSQL, 임베딩 서버, 마이그레이션, 서버, 작업자)를 띄운다.
- `accept`  기능 계획의 수락을 그대로 밟는다. 관리 명령으로 첫 토큰을 내고 표본 문서를 넣은 뒤, 공식
            MCP SDK 클라이언트가 프록시의 HTTPS 포트로 접속해 검색한다.
- `checks`  밖으로 열린 포트, 컨테이너의 사용자, 허용 호스트 판정, 막힌 경로, TLS 의 판, 접근 로그,
            큰 파일 올리기, 임베딩 서버의 로그를 본다. 대조군은 둘이다. 접근 로그와 큰 파일은 nginx
            기본값 설정으로 프록시만 바꿔 띄워 보고, 큰 파일은 서버의 `/tmp` 를 뗀 채로도 본다.
- `recover` 프록시가 서버를 다시 찾는 데 걸리는 시간을 잰다. 서버를 다른 주소로 다시 만들 때(뒷단의
            이름을 시작할 때만 푸는 `site.static.conf` 가 대조군이다), 둘을 함께 다시 시작할 때,
            서버 프로세스가 죽을 때다. 서버가 멈춘 동안 프록시의 오류 로그에 요청의 질의 문자열이
            남는지도 본다. 끝으로 프록시가 서버를 기다리는 조건 셋(기다리지 않음, 시작하면,
            건강해지면)마다 처음 띄운 뒤 502 가 이어지는 시간을 잰다.
- `down`    띄운 것을 볼륨째 내린다(모델 볼륨은 바깥 볼륨이라 남는다).
- `offline` 바깥으로 나가는 길이 없는 네트워크에서 임베딩 서버가 모델 볼륨만으로 뜨는지를
            `HF_HUB_OFFLINE` 이 없을 때와 있을 때로 본다. 이어서 임베딩 서버를 root 가 아닌
            사용자(uid 10001)로, 루트와 모델 볼륨을 읽기 전용으로, 모델의 리비전을 고정해 띄운다.
            리비전은 `HF_HUB_OFFLINE` 이 없을 때와 있을 때로 본다. 대조군(볼륨에 없는 리비전, 빈
            볼륨)은 뜨지 못해야 한다.
- `download` 생략하면 돌지 않는다. 빈 모델 볼륨을 uid 10001 이 가질 때 임베딩 서버가 그 사용자로,
            루트를 읽기 전용으로 둔 채 처음 시작하며 모델을 바깥에서 내려받아 뜨는지 본다. 대조군은
            root 가 가진 빈 볼륨이다. 모델 볼륨 인자는 쓰지 않는다(이 단계가 볼륨을 만들고 지운다).

필요한 것: Docker Engine 과 Compose, `openssl`(자체 서명 인증서를 만든다), 저장소의 개발
의존성(`mcp`, `httpx2`). 127.0.0.1 의 빈 포트 하나를 쓴다. 바깥 네트워크는 바탕 이미지를 받을 때만
쓴다. 메모리는 임베딩 서버가 약 6.6GiB 를 쓴다(`compose.eval.yml` 의 머리 주석).

단계 사이의 상태(포트, 데이터베이스 비밀번호, 발급한 토큰)는 시스템 임시 폴더의
`ri-probe-standalone/state.json` 에 둔다. 리눅스에서는 소유자만 읽게(0600) 쓰고, Windows 는 권한
비트를 쓰지 않아 사용자마다 따로 있는 임시 폴더의 권한을 따른다. 토큰과 비밀번호는 출력에 찍지
않는다. 출력은 `run_out.txt` 로 커밋한다. 커밋한 출력은 상태 파일을 그렇게 좁히기 전에 Windows 에서
돈 실행이고, 좁힌 것은 재는 값에 닿지 않는다.
"""

import argparse
import asyncio
import http.client
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path
from typing import Final

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

HERE: Final = Path(__file__).resolve().parent
ROOT: Final = HERE.parents[3]
WORK: Final = Path(tempfile.gettempdir()) / "ri-probe-standalone"
STATE: Final = WORK / "state.json"
TLS: Final = WORK / "tls"
PROJECT: Final = "ri-probe-standalone"
OFFLINE_PROJECT: Final = "ri-probe-offline"
NAMESPACE: Final = "ri-probe"
VERSION: Final = "0.1.0-rc.1"
# 운영자가 정하는 서버의 이름 자리. `RAG_ALLOWED_HOSTS` 에 넣고 raw 요청의 Host 머리로 보낸다.
HOST_NAME: Final = "rag.example.test"
OTHER_HOST: Final = "other.example.test"
SAMPLE_DIR: Final = ROOT / "tests" / "fixtures"
QUERY: Final = "연차휴가"
EXPECTED: Final = "연차휴가는 입사 일 년 뒤부터 발생한다"
STAGES: Final = ("build", "sse", "up", "accept", "checks", "recover", "down", "offline")
# 생략하면 돌지 않는 단계. 모델(약 2.3GB)을 바깥에서 내려받는다.
EXTRA_STAGES: Final = ("download",)
DOWNLOAD_PROJECT: Final = "ri-probe-download"
# 모델 볼륨에 든 `BAAI/bge-m3` 의 리비전(`models--BAAI--bge-m3/refs/main`).
MODEL_REVISION: Final = "5617a9f61b028005a4858fdac845db406aefb181"


def say(text: str) -> None:
    print(text, flush=True)


def run(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
    timeout: float = 900,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        env=env,
        check=check,
        timeout=timeout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def image(target: str) -> str:
    return f"{NAMESPACE}/rag-engine-{target}:{VERSION}"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert isinstance(port, int)
    return port


def load_state() -> dict[str, str]:
    if STATE.exists():
        loaded = json.loads(STATE.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)
        return {str(key): str(value) for key, value in loaded.items()}
    WORK.mkdir(parents=True, exist_ok=True)
    state = {"port": str(free_port()), "password": secrets.token_hex(16)}
    save_state(state)
    return state


def save_state(state: dict[str, str]) -> None:
    """토큰과 비밀번호가 들어 있어 리눅스에서는 소유자만 읽고 쓰게(0600) 쓰고, 그 자리의 링크를
    따라가지 않는다(Windows 는 두 갈래 모두 건너뛴다).
    폴더(`WORK`)와 인증서 폴더(`TLS`)는 좁히지 않는다. 프록시 컨테이너(uid 101)가 인증서 폴더를
    바인드 마운트로 읽어야 해서다."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if sys.platform != "win32":
        flags |= os.O_NOFOLLOW
    descriptor = os.open(STATE, flags, 0o600)
    if sys.platform != "win32":
        os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(state))


def make_certificate() -> None:
    """설치 안내에 적을 명령과 같은 꼴의 자체 서명 인증서. 이름은 서버 이름, localhost, 127.0.0.1
    이다."""
    if (TLS / "fullchain.pem").exists():
        return
    TLS.mkdir(parents=True, exist_ok=True)
    run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "7",
            "-keyout", str(TLS / "privkey.pem"),
            "-out", str(TLS / "fullchain.pem"),
            "-subj", f"/CN={HOST_NAME}",
            "-addext", f"subjectAltName=DNS:{HOST_NAME},DNS:localhost,IP:127.0.0.1",
        ]
    )  # fmt: skip


def compose(
    state: dict[str, str],
    models: str,
    *args: str,
    overlays: tuple[str, ...] = (),
    site: str = "site.conf",
    project: str = PROJECT,
    check: bool = True,
    timeout: float = 1800,
) -> subprocess.CompletedProcess[str]:
    command = ["docker", "compose", "-p", project, "-f", str(HERE / "compose.yml")]
    for overlay in overlays:
        command += ["-f", str(HERE / overlay)]
    env = os.environ | {
        "PROBE_POSTGRES_PASSWORD": state["password"],
        "PROBE_ALLOWED_HOSTS": HOST_NAME,
        "PROBE_PORT": state["port"],
        "PROBE_NAMESPACE": NAMESPACE,
        "PROBE_VERSION": VERSION,
        "PROBE_WORK": str(WORK),
        "PROBE_MODELS_VOLUME": models,
        "PROBE_SITE_CONF": site,
    }
    return run([*command, *args], env=env, check=check, timeout=timeout)


def client_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=str(TLS / "fullchain.pem"))


def request(
    state: dict[str, str],
    method: str,
    path: str,
    *,
    host: str = HOST_NAME,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """프록시의 HTTPS 포트로 raw 요청 하나. Host 머리를 직접 정한다."""
    connection = http.client.HTTPSConnection(
        "127.0.0.1", int(state["port"]), context=client_context(), timeout=60
    )
    try:
        connection.request(method, path, body=body, headers={"Host": host, **(headers or {})})
        response = connection.getresponse()
        return (
            response.status,
            {name.lower(): value for name, value in response.getheaders()},
            response.read(),
        )
    finally:
        connection.close()


def bearer(state: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {state['token']}"}


def until_ready(state: dict[str, str], limit: float = 120) -> tuple[list[str], float]:
    """프록시를 지나 `/health` 가 200 이 될 때까지 0.5초마다 묻는다.

    돌려주는 것은 200 이전에 본 것(상태 코드나 연결 오류의 이름, 이어진 같은 값은 하나로)과 처음
    200 을 받을 때까지의 초다. 제한 안에 200 이 없으면 초는 -1 이다.
    """
    started = time.monotonic()
    before: list[str] = []
    while time.monotonic() - started < limit:
        try:
            status, _, _ = request(state, "GET", "/health")
            seen = str(status)
        except OSError as error:
            seen = type(error).__name__
        if seen == "200":
            return before, round(time.monotonic() - started, 1)
        if not before or before[-1] != seen:
            before.append(seen)
        time.sleep(0.5)
    return before, -1.0


# ------------------------------ build ------------------------------


def stage_build(state: dict[str, str], models: str) -> None:
    del state, models
    revision = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).stdout.strip()
    for target in ("server", "worker"):
        started = time.monotonic()
        run(
            [
                "docker", "build", "-f", str(HERE / "Dockerfile"),
                "--build-arg", f"APP_VERSION={VERSION}",
                "--build-arg", f"REVISION={revision}",
                "--target", target, "-t", image(target), str(ROOT),
            ],
            timeout=1800,
        )  # fmt: skip
        say(
            f"[build] {image(target)} 를 지었다"
            f"({time.monotonic() - started:.0f}초, 캐시에 따라 다르다)"
        )
    layers: dict[str, list[str]] = {}
    for target in ("server", "worker"):
        inspected = json.loads(run(["docker", "image", "inspect", image(target)]).stdout)[0]
        config = inspected["Config"]
        layers[target] = list(inspected["RootFS"]["Layers"])
        say(
            f"[build] {target}: 사용자 {config['User']}, 크기 {inspected['Size'] / 1e6:.0f}MB, "
            f"ENTRYPOINT {config['Entrypoint']}, CMD {config['Cmd']}, 라벨 {config['Labels']}"
        )
        inside = run(
            [
                "docker", "run", "--rm", "--entrypoint", "python", image(target), "-c",
                "import importlib.metadata as m, os; print(m.version('rag-engine'), os.getuid())",
            ]
        ).stdout.strip()  # fmt: skip
        say(f"[build] {target}: 이미지 안의 패키지 번호와 uid 는 {inside}")
    shared = sum(1 for a, b in zip(layers["server"], layers["worker"], strict=False) if a == b)
    say(
        f"[build] 층은 서버 {len(layers['server'])}개, 작업자 {len(layers['worker'])}개이고 "
        f"앞에서부터 {shared}개가 같다"
    )
    without = run(
        ["docker", "build", "-f", str(HERE / "Dockerfile"), "--target", "server", str(ROOT)],
        check=False,
        timeout=1800,
    )
    needle = "APP_VERSION 빌드 인자가 필요하다"
    say(
        f"[build] 번호 없이 지으면 종료 코드 {without.returncode}, "
        f"안내 문구가 출력에 {'있다' if needle in without.stderr else '없다'}"
    )


# ------------------------------ sse ------------------------------


def arrivals(state: dict[str, str], path: str) -> tuple[int, list[float]]:
    """응답의 상태 코드와, `data:` 줄이 닿은 시각(요청을 보낸 때부터의 초)."""
    connection = http.client.HTTPSConnection(
        "127.0.0.1", int(state["port"]), context=client_context(), timeout=60
    )
    try:
        started = time.monotonic()
        connection.request(
            "POST",
            path,
            body=b"{}",
            headers={
                "Host": HOST_NAME,
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        response = connection.getresponse()
        seen: list[float] = []
        while line := response.readline():
            if line.startswith(b"data:"):
                seen.append(round(time.monotonic() - started, 2))
        return response.status, seen
    finally:
        connection.close()


def stage_sse(state: dict[str, str], models: str) -> None:
    # 가짜 뒷단은 몇 초 만에 건강해진다. 프록시가 먼저 뜨면 뒷단의 이름을 다시 풀 때까지 502 를
    # 내는지 본다.
    for label, extra in (
        ("기다리지 않는다(depends_on 없음, 대조군)", ("compose.nowait.yml",)),
        ("뒷단이 건강해지면 뜬다(service_healthy)", ()),
    ):
        overlays = ("compose.sse.yml", *extra)
        started = time.monotonic()
        compose(state, models, "up", "-d", "--wait", "proxy", "server", overlays=overlays)
        waited = time.monotonic() - started
        try:
            before, seconds = until_ready(state)
            say(
                f"[sse] 빨리 뜨는 뒷단과 함께 띄움, 프록시가 {label}: up --wait {waited:.1f}초, "
                f"그 뒤 200 이전에 본 것 {before}, {seconds}초"
            )
        finally:
            compose(state, models, "down", "-v", overlays=overlays)
    for site in ("site.conf", "site.buffered.conf"):
        compose(
            state, models, "up", "-d", "--wait", "proxy", "server",
            overlays=("compose.sse.yml",), site=site,
        )  # fmt: skip
        try:
            until_ready(state)
            for header, path in (("없음", "/mcp"), ("있음", "/mcp?xab=1")):
                status, seen = arrivals(state, path)
                if status != 200 or not seen:
                    say(f"[sse] {site}, X-Accel-Buffering {header}: 재지 못했다(상태 {status})")
                    continue
                spread = seen[-1] - seen[0]
                verdict = "온 대로 넘겼다" if spread >= 3.0 else "모아서 넘겼다"
                say(
                    f"[sse] {site}, X-Accel-Buffering {header}: "
                    f"상태 {status}, 사건 {len(seen)}개가 {seen}초에 닿았다. "
                    f"첫 사건과 끝 사건의 사이 {spread:.2f}초. {verdict}"
                )
        finally:
            compose(state, models, "down", "-v", overlays=("compose.sse.yml",), site=site)


# ------------------------------ up ------------------------------


def stage_up(state: dict[str, str], models: str) -> None:
    started = time.monotonic()
    compose(state, models, "up", "-d", "--wait")
    say(
        f"[up] 단독 compose 가 떴다({time.monotonic() - started:.0f}초. "
        "임베딩 서버가 모델을 올리는 시간이 든다)"
    )
    before, seconds = until_ready(state)
    say(f"[up] up --wait 가 돌아온 직후 프록시의 /health: 200 이전에 본 것 {before}, {seconds}초")
    listed = compose(state, models, "ps", "--all", "--format", "json").stdout
    for line in listed.splitlines():
        service = json.loads(line)
        say(
            f"[up] {service['Service']}: {service['State']}"
            f"{' ' + service['Health'] if service['Health'] else ''}"
            f"{' 종료 코드 ' + str(service['ExitCode']) if service['State'] == 'exited' else ''}"
        )


# ------------------------------ accept ------------------------------


async def search(state: dict[str, str]) -> tuple[list[str], dict[str, object]]:
    url = f"https://localhost:{state['port']}/mcp"
    async with httpx2.AsyncClient(headers=bearer(state), verify=client_context()) as http_client:
        async with Client(streamable_http_client(url, http_client=http_client)) as client:
            tools = sorted(tool.name for tool in (await client.list_tools()).tools)
            result = await client.call_tool("search", {"query": QUERY})
    assert result.is_error is not True, result
    structured = result.structured_content
    assert isinstance(structured, dict)
    return tools, {str(key): value for key, value in structured.items()}


def stage_accept(state: dict[str, str], models: str) -> None:
    issued = compose(
        state, models, "exec", "-T", "server", "rag-engine", "bootstrap-token", check=False
    )
    lines = [line for line in issued.stdout.splitlines() if line and not line.startswith("{")]
    say(
        f"[accept] bootstrap-token 종료 코드 {issued.returncode}, "
        f"JSON 로그가 아닌 출력 줄 {len(lines)}개"
    )
    if issued.returncode == 0:
        state["token"] = lines[-1].strip()
        save_state(state)
    assert "token" in state, issued.stdout + issued.stderr
    ingested = compose(
        state, models, "run", "--rm", "--no-deps", "-T",
        "-v", f"{SAMPLE_DIR}:/sample:ro",
        "worker", "rag-engine", "ingest", "/sample", "--wait", "--timeout", "600",
        check=False,
    )  # fmt: skip
    actions = [line for line in ingested.stdout.splitlines() if "\t" in line]
    say(f"[accept] ingest 종료 코드 {ingested.returncode}, 찍은 줄 {actions}")
    assert ingested.returncode == 0, ingested.stdout + ingested.stderr
    tools, found = asyncio.run(search(state))
    results = found["results"]
    assert isinstance(results, list)
    first = results[0]
    assert isinstance(first, dict)
    say(f"[accept] MCP 도구 목록 {tools}")
    say(
        f"[accept] search('{QUERY}') 결과 {len(results)}개, "
        f"format_version {found['format_version']}, 첫 결과의 키 {first['key']}, "
        f"기대한 글이 {'들어 있다' if EXPECTED in str(first['text']) else '없다'}"
    )


# ------------------------------ checks ------------------------------


def initialize_body() -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ri-probe", "version": "0"},
            },
        }
    ).encode()


def mcp_headers(state: dict[str, str]) -> dict[str, str]:
    return bearer(state) | {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def handshake(state: dict[str, str], version: ssl.TLSVersion) -> str:
    context = client_context()
    # 옛 판을 클라이언트 쪽에서 막지 않게 보안 수준을 내린다. 거부는 서버가 해야 한다.
    context.set_ciphers("DEFAULT:@SECLEVEL=0")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        context.minimum_version = version
        context.maximum_version = version
    try:
        with socket.create_connection(("127.0.0.1", int(state["port"])), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname="localhost") as secured:
                return f"맺었다({secured.version()})"
    except (ssl.SSLError, OSError) as error:
        return f"거부됐다({type(error).__name__}: {error})"


def multipart(filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = "ri-probe-" + secrets.token_hex(8)
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), boundary


def reason(body: bytes) -> str:
    """응답 본문(JSON)에서 까닭이나 결과를 적은 칸 하나를 뽑는다. 문서의 글은 그 칸들에 없다.
    JSON 이 아닌 본문(nginx 의 오류 페이지)은 줄바꿈을 공백 하나로 접는다. 그 본문의 CRLF 가
    Windows 의 표준 출력을 지나며 CR 이 홀로 선 줄이 되어 줄 구분 문자 검사가 커밋을 막았다."""
    try:
        loaded = json.loads(body)
    except ValueError:
        return " ".join(body[:80].decode("utf-8", "replace").split())
    if not isinstance(loaded, dict):
        return str(loaded)[:80]
    for name in ("code", "action", "detail", "title"):
        if loaded.get(name):
            return f"{name}={str(loaded[name])[:80]}"
    return ""


def upload(state: dict[str, str], megabytes: int, label: str) -> str:
    """머리만 PDF 인 파일을 올린다. 0MB 는 1MiB 아래라 파서가 메모리로만 받는다."""
    body, boundary = multipart(
        f"big{megabytes}{label}.pdf", b"%PDF-1.4\n" + b"0" * (megabytes * 1024 * 1024)
    )
    status, _, answer = request(
        state,
        "POST",
        "/api/v1/ingest/documents",
        headers=bearer(state) | {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        body=body,
    )
    return f"{status} {reason(answer)}".strip()


def logged(state: dict[str, str], models: str, service: str) -> str:
    return compose(state, models, "logs", "--no-color", "--no-log-prefix", service).stdout


def query_marker(state: dict[str, str]) -> tuple[str, int]:
    marker = "probe-key-" + secrets.token_hex(6)
    status, _, _ = request(
        state, "GET", f"/api/v1/admin/documents?key={marker}&limit=1", headers=bearer(state)
    )
    return marker, status


def stage_checks(state: dict[str, str], models: str) -> None:
    published: list[str] = []
    for line in compose(state, models, "ps", "--format", "json").stdout.splitlines():
        service = json.loads(line)
        for publisher in service["Publishers"] or []:
            if publisher["PublishedPort"]:
                published.append(
                    f"{service['Service']} {publisher['URL']}:{publisher['PublishedPort']}"
                    f"->{publisher['TargetPort']}"
                )
    say(f"[checks] 호스트에 열린 포트: {published}")

    for service in ("proxy", "server", "worker", "postgres", "embedding"):
        uid = compose(state, models, "exec", "-T", service, "id", "-u", check=False)
        first = compose(
            state, models, "exec", "-T", service, "sh", "-c",
            "tr '\\0' ' ' </proc/1/cmdline; echo; grep -E '^Uid' /proc/1/status",
            check=False,
        )  # fmt: skip
        say(
            f"[checks] {service}: exec 의 uid {uid.stdout.strip() or uid.stderr.strip()}, "
            f"1번 프로세스 {' / '.join(first.stdout.split(chr(10))[:2]).strip()}"
        )

    for host in (HOST_NAME, OTHER_HOST):
        status, headers, _ = request(
            state, "POST", "/mcp", host=host, headers=mcp_headers(state), body=initialize_body()
        )
        say(
            f"[checks] POST /mcp, Host {host}: {status}, "
            f"content-type {headers.get('content-type')}, "
            f"x-accel-buffering {headers.get('x-accel-buffering')}, "
            f"strict-transport-security {headers.get('strict-transport-security')}"
        )
    status, _, _ = request(state, "POST", "/mcp", headers={"Content-Type": "application/json"})
    say(f"[checks] 토큰 없는 POST /mcp: {status}")

    for path in ("/health", "/", "/docs", "/openapi.json", "/redoc", "/mcp/", "/api/v1/other"):
        status, headers, _ = request(state, "GET", path, headers=bearer(state))
        say(f"[checks] GET {path}: {status}, server 머리 {headers.get('server')}")

    for version in (ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1, ssl.TLSVersion.TLSv1_2,
                    ssl.TLSVersion.TLSv1_3):  # fmt: skip
        say(f"[checks] {version.name} 로만 손을 내밀면 {handshake(state, version)}")

    marker, status = query_marker(state)
    proxy_log = logged(state, models, "proxy")
    say(
        f"[checks] site.conf: 질의 문자열에 표지를 실은 GET 이 {status}, 프록시 로그에 표지가 "
        f"{'남았다' if marker in proxy_log else '남지 않았다'}"
    )
    sample = [line for line in proxy_log.splitlines() if "/api/v1/admin/documents" in line][-1:]
    say(f"[checks] site.conf: 그 요청의 접근 로그 줄 {sample}")
    for megabytes in (0, 2, 20):
        say(f"[checks] site.conf: {megabytes}MB 올리기의 응답 {upload(state, megabytes, 'a')}")

    # 대조군: 프록시만 nginx 기본값 설정으로 바꿔 띄운다.
    compose(
        state, models, "up", "-d", "--no-deps", "--force-recreate", "proxy",
        site="site.buffered.conf",
    )  # fmt: skip
    time.sleep(2)
    marker, status = query_marker(state)
    proxy_log = compose(
        state, models, "logs", "--no-color", "--no-log-prefix", "proxy", site="site.buffered.conf"
    ).stdout
    say(
        f"[checks] site.buffered.conf(대조군): 같은 GET 이 {status}, 프록시 로그에 표지가 "
        f"{'남았다' if marker in proxy_log else '남지 않았다'}"
    )
    say(f"[checks] site.buffered.conf(대조군): 2MB 올리기의 응답 {upload(state, 2, 'b')}")
    compose(state, models, "up", "-d", "--no-deps", "--force-recreate", "proxy")
    time.sleep(2)

    embedding_log = logged(state, models, "embedding")
    needles = (QUERY, EXPECTED, "출장비", QUERY.encode("unicode_escape").decode())
    hits = [needle for needle in needles if needle in embedding_log]
    lines = embedding_log.splitlines()
    say(
        f"[checks] 임베딩 서버의 로그 {len(lines)}줄에서 질의와 문서의 글 {list(needles)} 가운데 "
        f"나온 것: {hits}"
    )
    for line in [line for line in lines if "embed" in line.lower()][-3:]:
        say(f"[checks] 임베딩 서버 로그의 요청 줄 표본: {line[:400]}")
    for service in ("server", "worker"):
        text = logged(state, models, service)
        # 나온 값이 아니라 항목 이름을 찍는다. 토큰이 새면 그 원문이 커밋하는 출력에 실리기
        # 때문이다.
        needles = {"질의": QUERY, "문서 키": "small_text.pdf", "토큰": state["token"]}
        leaked = [name for name, needle in needles.items() if needle in text]
        say(
            f"[checks] {service} 로그 {len(text.splitlines())}줄에서 "
            f"질의, 문서 키, 토큰 가운데 나온 것: {leaked}"
        )

    # 대조군: 서버의 /tmp 를 뗀다. 서버를 다시 만들면 그 로그가 사라지므로 로그를 본 뒤에 한다.
    recreate = ("up", "-d", "--no-deps", "--force-recreate", "--wait", "server")
    compose(state, models, *recreate, overlays=("compose.notmp.yml",))
    until_ready(state)
    for megabytes in (0, 2):
        say(
            f"[checks] 서버에 /tmp 가 없을 때(대조군): {megabytes}MB 올리기의 응답 "
            f"{upload(state, megabytes, 'c')}"
        )
    compose(state, models, *recreate)
    until_ready(state)


# ------------------------------ recover ------------------------------


def server_fact(state: dict[str, str], models: str, template: str) -> str:
    container = compose(state, models, "ps", "-q", "server").stdout.strip()
    return run(["docker", "inspect", "-f", template, container]).stdout.strip()


ADDRESS: Final = "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"


def marked_request(state: dict[str, str]) -> tuple[str, str]:
    """질의 문자열에 표지를 실은 GET. 표지와, 받은 상태 코드나 연결 오류의 이름을 돌려준다."""
    marker = "probe-key-" + secrets.token_hex(6)
    try:
        status, _, _ = request(
            state, "GET", f"/api/v1/admin/documents?key={marker}&limit=1", headers=bearer(state)
        )
    except OSError as error:
        return marker, type(error).__name__
    return marker, str(status)


def occupy(address: str, names: list[str]) -> bool:
    """서버가 비운 주소 `address` 를 다른 컨테이너가 차지하게 한다. 띄운 컨테이너의 이름을
    `names` 에 더하고, 그 주소를 받은 컨테이너가 있으면 참이다.

    비운 주소가 여럿이면 하나만 띄운 컨테이너가 다른 주소를 받아, 다시 만든 서버가 옛 주소를
    되받았다(앞 실행). 그래서 옛 주소를 받은 컨테이너가 나올 때까지 여덟 개까지 띄운다.
    """
    for index in range(8):
        name = f"{PROJECT}-holder-{index}"
        run(
            ["docker", "run", "-d", "--rm", "--name", name, "--network", f"{PROJECT}_default",
             image("server"), "sleep", "300"]
        )  # fmt: skip
        names.append(name)
        if run(["docker", "inspect", "-f", ADDRESS, name]).stdout.strip() == address:
            return True
    return False


def stage_recover(state: dict[str, str], models: str) -> None:
    """프록시가 서버를 다시 찾는 데 걸리는 시간과, 서버가 멈춘 동안의 오류 로그. `up` 뒤에 돈다."""
    # 서버를 지우고, 비운 주소를 다른 컨테이너가 먼저 차지하게 한 뒤 다시 만든다. 주소가 바뀐다.
    # 대조군(site.static.conf)은 뒷단의 이름을 시작할 때 한 번만 푼다. 60초 안에 200 이 없으면 -1
    # 이다.
    for site, label in (
        ("site.static.conf", "뒷단의 이름을 시작할 때만 푼다(대조군)"),
        ("site.conf", "뒷단의 이름을 다시 푼다"),
    ):
        compose(state, models, "up", "-d", "--no-deps", "--force-recreate", "proxy", site=site)
        until_ready(state)
        old = server_fact(state, models, ADDRESS)
        compose(state, models, "rm", "-sf", "server", site=site)
        holders: list[str] = []
        try:
            taken = occupy(old, holders)
            compose(state, models, "up", "-d", "--no-deps", "--wait", "server", site=site)
            before, seconds = until_ready(state, limit=60)
            say(
                f"[recover] {site}, {label}: 서버를 지우고 다시 만든 뒤(건강해진 때부터) 서버의 "
                f"주소 {old} -> {server_fact(state, models, ADDRESS)}"
                f"(옛 주소를 다른 컨테이너가 {'차지했다' if taken else '차지하지 못했다'}, "
                f"띄운 컨테이너 {len(holders)}개), 200 이전에 본 것 {before}, {seconds}초"
            )
        finally:
            for holder in holders:
                run(["docker", "rm", "-f", holder], check=False)

    compose(state, models, "restart", "proxy", "server")
    before, seconds = until_ready(state)
    say(
        "[recover] 프록시와 서버를 함께 다시 시작한 뒤(restart 가 돌아온 때부터): "
        f"200 이전에 본 것 {before}, {seconds}초"
    )

    # 컨테이너 안에서 1번 프로세스(tini)를 뺀 모든 프로세스를 죽인다. `docker kill` 은 사람이 멈춘
    # 것으로 남아 재시작 정책이 돌지 않는다.
    compose(
        state, models, "exec", "-T", "server",
        "python", "-c", "import os, signal; os.kill(-1, signal.SIGKILL)",
        check=False,
    )  # fmt: skip
    before, seconds = until_ready(state)
    say(
        "[recover] 서버 프로세스가 죽은 뒤(재시작 정책이 다시 띄운다. 다시 뜬 횟수 "
        f"{server_fact(state, models, '{{.RestartCount}}')}): "
        f"200 이전에 본 것 {before}, {seconds}초"
    )

    # 서버가 멈춘 동안 프록시의 오류 로그에 요청 줄이 남는지. 이름이 DNS 에서 빠질 때까지 기다린다.
    compose(state, models, "stop", "server")
    time.sleep(8)
    for site in ("site.conf", "site.buffered.conf"):
        if site != "site.conf":
            compose(state, models, "up", "-d", "--no-deps", "--force-recreate", "proxy", site=site)
            time.sleep(8)
        marker, seen = marked_request(state)
        time.sleep(1)
        log = compose(
            state, models, "logs", "--no-color", "--no-log-prefix", "proxy", site=site
        ).stdout
        lines = [line for line in log.splitlines() if marker in line]
        errors = [line for line in lines if "[error]" in line]
        say(
            f"[recover] 서버가 멈춘 동안 {site}: 표지를 실은 GET 이 {seen}, 프록시 로그에서 표지가 "
            f"든 줄 {len(lines)}개, 그 가운데 오류 로그 줄([error]) {len(errors)}개"
        )
    compose(state, models, "up", "-d", "--no-deps", "--force-recreate", "proxy")
    compose(state, models, "start", "server")
    before, seconds = until_ready(state)
    say(
        "[recover] 서버를 다시 켠 뒤(start 가 돌아온 때부터): "
        f"200 이전에 본 것 {before}, {seconds}초"
    )

    # 프록시가 서버를 기다리는 조건 셋. 앞의 둘이 대조군이다.
    for label, overlays, waits in (
        ("기다리지 않는다(depends_on 없음, 대조군)", ("compose.nowait.yml",), ""),
        ("서버 컨테이너가 시작하면 뜬다(service_started, 대조군)", (), "service_started"),
        ("서버가 건강해지면 뜬다(service_healthy)", (), "service_healthy"),
    ):
        compose(state, models, "rm", "-sf", "proxy", "server", overlays=overlays)
        if waits:
            os.environ["PROBE_PROXY_WAITS"] = waits
        try:
            started = time.monotonic()
            compose(state, models, "up", "-d", "--wait", "proxy", "server", overlays=overlays)
            waited = time.monotonic() - started
            before, seconds = until_ready(state)
        finally:
            os.environ.pop("PROBE_PROXY_WAITS", None)
        say(
            f"[recover] 프록시와 서버를 지우고 다시 띄움, 프록시가 {label}: "
            f"up --wait {waited:.1f}초, 그 뒤 200 이전에 본 것 {before}, {seconds}초"
        )


# ------------------------------ down, offline ------------------------------


def stage_down(state: dict[str, str], models: str) -> None:
    compose(state, models, "down", "-v", "--remove-orphans")
    state.pop("token", None)
    save_state(state)
    say("[down] 내렸다")


def stage_offline(state: dict[str, str], models: str) -> None:
    empty = "ri-probe-offline-empty"
    run(["docker", "volume", "create", empty])
    locked = ("compose.teiuser.yml", "compose.teilocked.yml")
    pinned = (*locked, "compose.teirevision.yml")
    pinned_offline = (*pinned, "compose.hfoffline.yml")
    try:
        for label, volume, extra, revision in (
            ("모델이 든 볼륨, HF_HUB_OFFLINE 없음", models, (), ""),
            ("모델이 든 볼륨, HF_HUB_OFFLINE=1", models, ("compose.hfoffline.yml",), ""),
            ("모델이 든 볼륨, uid 10001", models, ("compose.teiuser.yml",), ""),
            ("모델이 든 볼륨, uid 10001, 루트와 모델 볼륨이 읽기 전용", models, locked, ""),
            ("모델이 든 볼륨, uid 10001, 읽기 전용, 리비전 고정", models, pinned, MODEL_REVISION),
            ("모델이 든 볼륨, 볼륨에 없는 리비전(대조군)", models, pinned, "0" * 40),
            (
                "모델이 든 볼륨, 읽기 전용, 리비전 고정, HF_HUB_OFFLINE=1",
                models,
                pinned_offline,
                MODEL_REVISION,
            ),
            (
                "모델이 든 볼륨, 볼륨에 없는 리비전, HF_HUB_OFFLINE=1(대조군)",
                models,
                pinned_offline,
                "0" * 40,
            ),
            ("빈 볼륨, HF_HUB_OFFLINE=1(대조군)", empty, ("compose.hfoffline.yml",), ""),
        ):
            overlays = ("compose.offline.yml", *extra)
            os.environ["PROBE_TEI_REVISION"] = revision
            started = time.monotonic()
            up = compose(
                state, volume, "up", "-d", "--wait", "--wait-timeout", "240", "embedding",
                overlays=overlays, project=OFFLINE_PROJECT, check=False,
            )  # fmt: skip
            log = compose(
                state, volume, "logs", "--no-color", "--no-log-prefix", "--tail", "4", "embedding",
                overlays=overlays, project=OFFLINE_PROJECT, check=False,
            ).stdout  # fmt: skip
            tail = [line[-120:] for line in log.strip().splitlines()[-2:]]
            first = compose(
                state, volume, "exec", "-T", "embedding", "grep", "-E", "^Uid", "/proc/1/status",
                overlays=overlays, project=OFFLINE_PROJECT, check=False,
            )  # fmt: skip
            say(
                f"[offline] {label}: up --wait 종료 코드 {up.returncode}"
                f"({time.monotonic() - started:.0f}초), 1번 프로세스 "
                f"{' '.join(first.stdout.split()) or '없음'}. 로그 끝 두 줄의 끝 {tail}"
            )
            compose(
                state, volume, "down", "-v",
                overlays=overlays, project=OFFLINE_PROJECT, check=False,
            )  # fmt: skip
    finally:
        os.environ.pop("PROBE_TEI_REVISION", None)
        run(["docker", "volume", "rm", empty], check=False)


def stage_download(state: dict[str, str], models: str) -> None:
    """빈 모델 볼륨에서 임베딩 서버가 root 가 아닌 사용자로 처음 시작해 모델을 내려받는지 본다.
    `models` 는 쓰지 않는다. 볼륨은 이 단계가 만들고 지운다."""
    del models
    volume = "ri-probe-download-models"
    overlays = ("compose.teiuser.yml", "compose.teirootro.yml")
    for label, owner in (
        ("빈 볼륨을 uid 10001 이 가짐", "10001:10001"),
        ("빈 볼륨을 root 가 가짐(대조군)", ""),
    ):
        run(["docker", "volume", "create", volume])
        try:
            if owner:
                run(
                    ["docker", "run", "--rm", "--user", "0", "-v", f"{volume}:/d", image("server"),
                     "chown", owner, "/d"]
                )  # fmt: skip
            started = time.monotonic()
            up = compose(
                state, volume, "up", "-d", "--wait", "--wait-timeout", "1500", "embedding",
                overlays=overlays, project=DOWNLOAD_PROJECT, check=False,
            )  # fmt: skip
            seconds = time.monotonic() - started
            log = compose(
                state, volume, "logs", "--no-color", "--no-log-prefix", "--tail", "4", "embedding",
                overlays=overlays, project=DOWNLOAD_PROJECT, check=False,
            ).stdout  # fmt: skip
            tail = [line[-120:] for line in log.strip().splitlines()[-2:]]
            first = compose(
                state, volume, "exec", "-T", "embedding", "grep", "-E", "^Uid", "/proc/1/status",
                overlays=overlays, project=DOWNLOAD_PROJECT, check=False,
            )  # fmt: skip
            compose(
                state, volume, "down",
                overlays=overlays, project=DOWNLOAD_PROJECT, check=False,
            )  # fmt: skip
            # 내려받은 크기, 받은 리비전, 파일의 소유자. 받지 못했으면 빈 값이다.
            held = run(
                ["docker", "run", "--rm", "-v", f"{volume}:/d:ro", image("server"), "sh", "-c",
                 "du -sh /d | cut -f1;"
                 " cat /d/models--BAAI--bge-m3/refs/main 2>/dev/null;"
                 " stat -c '%u:%g' /d/models--BAAI--bge-m3 2>/dev/null"],
                check=False,
            ).stdout.split()  # fmt: skip
            say(
                f"[download] {label}: up --wait 종료 코드 {up.returncode}"
                f"({seconds:.0f}초), 1번 프로세스 {' '.join(first.stdout.split()) or '없음'},"
                f" 볼륨의 크기와 받은 리비전과 소유자 {held}. 로그 끝 두 줄의 끝 {tail}"
            )
        finally:
            compose(
                state, volume, "down",
                overlays=overlays, project=DOWNLOAD_PROJECT, check=False,
            )  # fmt: skip
            run(["docker", "volume", "rm", volume], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models-volume", required=True)
    parser.add_argument("stages", nargs="*", choices=[*STAGES, *EXTRA_STAGES, []], default=[])
    arguments = parser.parse_args()
    stages: list[str] = list(arguments.stages) or list(STAGES)
    models: str = arguments.models_volume
    state = load_state()
    make_certificate()
    versions = run(["docker", "version", "--format", "{{.Server.Version}}"]).stdout.strip()
    say(
        f"[판] Docker {versions}, {run(['docker', 'compose', 'version', '--short']).stdout.strip()}"
    )
    table = {
        "build": stage_build,
        "sse": stage_sse,
        "up": stage_up,
        "accept": stage_accept,
        "checks": stage_checks,
        "recover": stage_recover,
        "down": stage_down,
        "offline": stage_offline,
        "download": stage_download,
    }
    for stage in stages:
        table[stage](state, models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
