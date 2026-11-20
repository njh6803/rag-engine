"""단독 compose 시험. 운영자가 설치 안내대로 하는 일을 그대로 밟는다(release-image 03).

배포 파일 묶음을 풀고, `.env`를 채우고, 자체 서명 인증서를 만들고, 모델 폴더를 두고,
`docker compose up -d --wait --wait-timeout 1800`을 친다. 그 뒤 첫 인증 토큰을 내고, 표본 문서를
넣고, 공식 MCP SDK 클라이언트로 443에 접속해 검색한다. 진짜 임베딩 서버(묶음의 TEI 이미지)로 띄운다.
가짜로 바꾸면 compose의 `embedding` 서비스를 시험이 고쳐 써야 해, 운영자가 받는 compose와 시험하는
compose가 갈린다.

기본 수집에서 뺀다(`pyproject.toml`의 `norecursedirs`). 이미지와 임베딩 서버를 띄우는 데 몇 분이
걸리고 호스트의 443이 비어 있어야 해서다. 경로를 주어 칠 때만 모인다.

    uv run pytest tests/standalone -q

시작할 때 443이 비었는지 본다. 차 있으면 까닭을 적고 실패한다(건너뛰지 않는다. 원칙 I).

입력은 환경 변수 다섯이다. 08의 릴리스 워크플로가 같은 이름으로 부른다.

- `RAG_STANDALONE_NAMESPACE`, `RAG_STANDALONE_VERSION`: 이미지 이름공간과 번호. 둘 다 있으면 그
  이미지를 쓴다 (릴리스 워크플로가 방금 지은 이미지). 하나라도 없으면
  `deploy/images/docker-bake.hcl`로 직접 짓는다(이름공간 `rag-engine-test`, 번호 `0.1.0-rc.1`).
- `RAG_STANDALONE_BUNDLE`: 배포 파일 묶음(`rag-engine-<번호>.tar.gz`)의 경로. 없으면
  `tools/release.py bundle`로 `deploy/standalone/`에서 짓는다.
- `RAG_STANDALONE_MODELS`: 임베딩 모델이 이미 든 폴더(TEI의 `/data` 자리, `models--BAAI--bge-m3`가
  든 폴더). 있으면 묶음 안의 `models/embedding/`으로 복사한다. 없으면 빈 폴더를 만들고 임베딩 서버의
  첫 시작이 모델을 내려받는다.
- `RAG_STANDALONE_LOGS`: 컨테이너 로그를 남길 폴더. 없으면 pytest의 임시 폴더에만 남긴다.

운영자와 다르게 하는 일은 셋이다. 앞의 둘은 리눅스에서만 소유를 바꾸는 일이다.

1. 모델 폴더를 uid 10001에게 주는 `sudo chown -R 10001:10001 models` 대신 같은 일을 하는
   컨테이너(`chown`만 한다)를 쓴다. 러너에서 `sudo`를 시험이 칠 까닭이 없어서다. Windows의 Docker
   Desktop은 바인드 마운트의 소유를 흉내 내므로 이 단계를 건너뛴다. 이 단계의 소유 문제는 리눅스
   러너에서 처음 드러난다.
2. 인증서의 키 파일을 `root:101`, `0640`으로 두는 것도 같은 컨테이너로 한다(프록시가 uid 101로 돌아
   키를 읽는다). Windows에서는 건너뛴다.
3. `.env`의 `RAG_ENGINE_NAMESPACE`와 `RAG_ENGINE_VERSION`을 시험이 받은 이미지 이름공간과 번호로
   덮어쓴다. 운영자는 이 두 칸을 고치지 않는다(`.env.example`에 묶음을 만든 릴리스의 값이 이미
   적혀 있다). 시험은 러너에 싣는 시험용 이미지로 띄워야 해서 고친다. 묶음의 바이트는 그대로다.

끝나면 로그를 남기고 이 시험이 띄운 프로젝트만 볼륨째 내린다. 리눅스에서는 컨테이너가 바꾼 소유를
되돌려 pytest가 임시 폴더를 지울 수 있게 한다.

시험은 앞 시험이 만든 상태에 기댄다. 파일에 적힌 차례로 돈다. 마지막 셋은 서버를 죽이거나 다시
만들거나 멈춘다. 다시 만들거나 멈추는 둘은 `finally`에서 되돌리고, 죽이는 시험은 재시작 정책이
서버를 되살린다.
"""

import http.client
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import threading
import time
import warnings
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import TypeAdapter

ROOT: Final = Path(__file__).resolve().parents[2]

NAMESPACE_ENV: Final = "RAG_STANDALONE_NAMESPACE"
VERSION_ENV: Final = "RAG_STANDALONE_VERSION"
BUNDLE_ENV: Final = "RAG_STANDALONE_BUNDLE"
MODELS_ENV: Final = "RAG_STANDALONE_MODELS"
LOGS_ENV: Final = "RAG_STANDALONE_LOGS"
DEFAULT_NAMESPACE: Final = "rag-engine-test"
DEFAULT_VERSION: Final = "0.1.0-rc.1"

# 설치 안내(04)가 같은 명령을 적는다. 04의 정합 시험이 이 상수와 안내를 맞대어 본다. 띄우는 명령과
# 인증서 명령은 시험이 그대로 친다(띄우는 명령은 프로젝트 이름 `-p`와 작업 폴더를 더해서). 모델 폴더
# 명령은 안내용 기록일 뿐 시험이 치지 않는다. `mkdir`은 파이썬으로 하고 `sudo chown`은 모듈
# 독스트링의 "운영자와 다르게 하는 일" 1처럼 컨테이너로 한다.
UP_COMMAND: Final = ("docker", "compose", "up", "-d", "--wait", "--wait-timeout", "1800")
CERTIFICATE_COMMAND: Final = (
    "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "7",
    "-keyout", "tls/privkey.pem", "-out", "tls/fullchain.pem",
    "-subj", "/CN=rag.example.test",
    "-addext", "subjectAltName=DNS:rag.example.test,DNS:localhost,IP:127.0.0.1",
)  # fmt: skip
MODEL_FOLDER_COMMANDS: Final = (
    ("mkdir", "-p", "models/embedding"),
    ("sudo", "chown", "-R", "10001:10001", "models"),
)
# 프록시 컨테이너 안의 주 설정. compose의 `proxy` 서비스가 `command`의 `-c`로 주는 경로다. 설치
# 안내의 `nginx -t -c`와 `nginx -s reload -c`가 같은 경로를 쓴다.
PROXY_MAIN_CONFIG: Final = "/etc/rag-engine/proxy/nginx.conf"

HOST_NAME: Final = "rag.example.test"
OTHER_HOST: Final = "other.example.test"
PUBLISHED_PORT: Final = 443
PROJECT_PREFIX: Final = "rag-engine-e2e-"
# 이 서비스들의 1번 프로세스는 root가 아니어야 한다(PostgreSQL 이미지는 시작 뒤 사용자를 바꾸는 제
# 방식이 있어 뺀다).
NON_ROOT_SERVICES: Final = ("proxy", "server", "worker", "embedding")
REQUIRED_VALUES: Final = (
    "RAG_ENGINE_NAMESPACE",
    "RAG_ENGINE_VERSION",
    "RAG_ALLOWED_HOSTS",
    "POSTGRES_PASSWORD",
)
SAMPLE_DIR: Final = ROOT / "tests" / "fixtures"
QUERY: Final = "연차휴가"
EXPECTED: Final = "연차휴가는 입사 일 년 뒤부터 발생한다"
# 15초는 명세가 운영자에게 약속한 수치다(티켓 03, 명세 "단독 compose"). 그래서
# .claude/rules/tests.md의 "홀로 돌린 시간의 넉넉한 배수" 규칙을 따르지 못한다. 서버 프로세스를
# 죽이는 시험에서 개발 PC의 손으로 본 값이 8.0초와 9.5초였고(커밋하지 않은 임시 출력), 깨뜨린
# 사본으로 전체를 느리게 돌린 실행에서 19.2초가 나온 적이 있다(티켓 Comments의 "회복 시간"). 서버
# 컨테이너를 지우고 다시 만드는 시험의 값은 티켓에 적지 않았다. 러너에서 흔들리면 이 수치를 시험이
# 아니라 명세에서 다시 정한다.
RECOVERY_SECONDS: Final = 15.0

COMPOSE_TIMEOUT: Final = 300.0
UP_TIMEOUT: Final = 2100.0  # 띄우는 명령의 기다림(1800초)보다 길다
HTTP_TIMEOUT: Final = 60.0


# ------------------------------ 도우미 ------------------------------


@dataclass
class Stack:
    """시험이 띄운 단독 compose 하나."""

    project: str
    directory: Path
    namespace: str
    version: str
    token: str
    # 띄우는 명령이 돌아온 직후 첫 /health의 상태 코드(연결 오류면 None)와 걸린 초
    first_health: tuple[int | None, float]

    def image(self, target: str) -> str:
        return f"{self.namespace}/rag-engine-{target}:{self.version}"


class CommandFailed(subprocess.CalledProcessError):
    """종료 코드가 0이 아닌 명령. 메시지에 stdout과 stderr를 싣는다.

    기본 `CalledProcessError`는 명령과 종료 코드만 적는다. 첫 릴리스에서 `docker compose up`이 이
    예외로 실패했을 때 까닭(compose의 오류 문구)이 stderr에만 있어 로그에서 읽을 수 없었다.
    """

    def __str__(self) -> str:
        return f"{super().__str__()}\n--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"


def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    timeout: float = COMPOSE_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(
        list(args),
        cwd=cwd,
        env=None if env is None else dict(env),
        check=False,
        timeout=timeout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and done.returncode != 0:
        raise CommandFailed(done.returncode, list(args), done.stdout, done.stderr)
    return done


def env_values(namespace: str, version: str, password: str) -> dict[str, str]:
    """`.env`에서 시험이 채울 칸 넷.

    호스트 이름과 비밀번호는 운영자가 채우는 칸이다. 이미지 이름공간과 번호는 운영자가 고치지 않는
    칸(`.env.example`에 묶음을 만든 릴리스의 값이 이미 적혀 있다)인데, 시험은 받은 값으로 덮어쓴다.
    올릴 묶음의 이름공간(`njh6803` 등)과 릴리스 워크플로가 러너에 싣는 시험용 이미지의 이름공간
    (`rag-engine-release-test`)이 다르면, 덮어쓰지 않은 `.env`로 띄운 compose는 러너에 없는
    이미지를 레지스트리에서 받으려 한다. 이 PC에서 같은 입력으로 되풀이하자 `docker compose up`이
    `manifest for njh6803/rag-engine-server:0.1.0-rc.1 not found`로 멈췄다(티켓 Comments).
    묶음의 바이트는 그대로다.
    """
    return {
        "RAG_ENGINE_NAMESPACE": namespace,
        "RAG_ENGINE_VERSION": version,
        "RAG_ALLOWED_HOSTS": f"localhost,{HOST_NAME}",
        "POSTGRES_PASSWORD": password,
    }


def write_env(directory: Path, namespace: str, version: str, password: str) -> None:
    """묶음 폴더의 `.env.example`을 채워 `.env`로 쓴다. `stack` 픽스처가 이 함수로 쓴다.

    픽스처가 이 함수를 부르는지는 Docker로 띄우는 이 시험만 알 수 있다. Docker 없이 도는
    `tests/tools/test_standalone_env.py`는 이 함수가 채우는 값까지만 본다.
    """
    env_file = directory / ".env"
    env_file.write_text(
        fill_env(
            (directory / ".env.example").read_text(encoding="utf-8"),
            env_values(namespace, version, password),
        ),
        encoding="utf-8",
    )
    env_file.chmod(0o600)


def clean_environment() -> dict[str, str]:
    """compose가 자기 `.env`가 아니라 이 셸에서 값을 받지 않게 한다. 이 시험이 보는 값 넷과
    `COMPOSE_`로 시작하는 변수를 벗긴다."""
    return {
        name: value
        for name, value in os.environ.items()
        if name not in REQUIRED_VALUES
        and name != "RAG_ENGINE_SERVER_TMP_SIZE"
        and not name.startswith("COMPOSE_")
    }


def compose(
    stack: Stack,
    *args: str,
    check: bool = True,
    timeout: float = COMPOSE_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    return run(
        ["docker", "compose", "-p", stack.project, *args],
        cwd=stack.directory,
        env=clean_environment(),
        check=check,
        timeout=timeout,
    )


_OBJECT: Final = TypeAdapter(dict[str, object])
_OBJECTS: Final = TypeAdapter(list[dict[str, object]])


def json_object(text: str) -> dict[str, object]:
    return _OBJECT.validate_json(text)


def json_objects(text: str) -> list[dict[str, object]]:
    """`docker compose ps --format json`의 출력. 버전에 따라 줄마다 객체 하나거나 배열 하나다."""
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        return _OBJECTS.validate_json(text)
    return [json_object(line) for line in text.splitlines() if line.strip()]


def ensure_port_free() -> None:
    """호스트의 443에 이미 듣는 것이 있으면 실패한다. 단독 compose는 0.0.0.0:443을 고정으로 연다."""
    try:
        with socket.create_connection(("127.0.0.1", PUBLISHED_PORT), timeout=2):
            occupied = True
    except OSError:
        occupied = False
    if occupied:
        pytest.fail(
            f"호스트의 {PUBLISHED_PORT} 번 포트에 이미 듣는 것이 있다. 단독 compose는 프록시를"
            " 이 포트에 고정으로 연다(운영자가 받는 compose 그대로)."
            " 그 프로그램이나 컨테이너를 멈춘 뒤 다시 친다"
        )


def tidy_images() -> tuple[str, str]:
    """이미지의 이름공간과 번호. 환경 변수 둘이 있으면 그것이고, 없으면 bake 설정으로 직접
    짓는다."""
    namespace = os.environ.get(NAMESPACE_ENV)
    version = os.environ.get(VERSION_ENV)
    if namespace and version:
        return namespace, version
    revision = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).stdout.strip()
    run(
        ["docker", "buildx", "bake", "-f", "deploy/images/docker-bake.hcl", "--load"],
        cwd=ROOT,
        env=os.environ
        | {
            "NAMESPACE": DEFAULT_NAMESPACE,
            "TAG": DEFAULT_VERSION,
            "VERSION": DEFAULT_VERSION,
            "REVISION": revision,
        },
        timeout=1800,
    )
    return DEFAULT_NAMESPACE, DEFAULT_VERSION


def unpack_bundle(work: Path, namespace: str, version: str) -> Path:
    """배포 파일 묶음을 풀어 묶음 폴더(`rag-engine-<번호>/`)를 돌려준다. 환경 변수의 묶음이 있으면
    그것이고, 없으면 묶음을 짓는 도구로 짓는다."""
    given = os.environ.get(BUNDLE_ENV)
    if given:
        archive = Path(given)
    else:
        built = run(
            [
                sys.executable, "tools/release.py", "bundle",
                "--number", version, "--namespace", namespace, "--out", str(work),
            ],
            cwd=ROOT,
        )  # fmt: skip
        archive = Path(built.stdout.strip().splitlines()[-1])
    target = work / "unpacked"
    target.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(target, filter="data")
    folders = [entry for entry in target.iterdir() if entry.is_dir()]
    assert len(folders) == 1, [entry.name for entry in target.iterdir()]
    return folders[0]


def fill_env(example: str, values: Mapping[str, str]) -> str:
    """`.env.example`에서 이름이 같은 줄(주석 아닌 줄)의 값을 채운다. 없는 이름이 있으면
    실패한다."""
    lines: list[str] = []
    seen: set[str] = set()
    for line in example.splitlines():
        name, separator, _ = line.partition("=")
        if separator and name in values:
            lines.append(f"{name}={values[name]}")
            seen.add(name)
        else:
            lines.append(line)
    assert seen == set(values), f".env.example에 없는 칸: {sorted(set(values) - seen)}"
    return "\n".join(lines) + "\n"


def own(
    stack_directory: Path, namespace: str, version: str, paths: Sequence[str], owner: str
) -> None:
    """리눅스에서 컨테이너(`chown`만 한다)로 소유를 바꾼다. Windows는 건너뛴다(바인드 마운트의
    소유를 흉내 낸다)."""
    if sys.platform != "linux":
        return
    run(
        [
            "docker", "run", "--rm", "--user", "0", "--entrypoint", "chown",
            "-v", f"{stack_directory}:/work", f"{namespace}/rag-engine-server:{version}",
            "-R", owner, *[f"/work/{path}" for path in paths],
        ]
    )  # fmt: skip


def refuse_existing(project: str) -> None:
    """이 이름의 컨테이너나 볼륨이 이미 있으면 다시 쓰지 않고 실패한다."""
    containers = run(
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"]
    ).stdout.strip()
    volumes = run(["docker", "volume", "ls", "-q", "--filter", f"name={project}_"]).stdout.strip()
    assert not containers and not volumes, f"프로젝트 이름 {project}이 이미 쓰이고 있다"


def request(
    method: str,
    path: str,
    *,
    host: str = HOST_NAME,
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    cafile: Path,
) -> tuple[int, dict[str, str], bytes]:
    """프록시의 443으로 raw 요청 하나. Host 머리를 직접 정한다."""
    connection = http.client.HTTPSConnection(
        "127.0.0.1",
        PUBLISHED_PORT,
        context=ssl.create_default_context(cafile=str(cafile)),
        timeout=HTTP_TIMEOUT,
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


def get(
    stack: Stack, path: str, *, host: str = HOST_NAME, headers: Mapping[str, str] | None = None
) -> int:
    status, _, _ = request(
        "GET", path, host=host, headers=headers, cafile=stack.directory / "tls" / "fullchain.pem"
    )
    return status


def bearer(stack: Stack) -> dict[str, str]:
    return {"Authorization": f"Bearer {stack.token}"}


def until_ready(stack: Stack, limit: float) -> float | None:
    """프록시를 지나 `/health`가 200이 될 때까지 0.5초마다 묻는다. 처음 200까지의 초를 돌려주고,
    제한 안에 200이 없으면 None을 돌려준다. 제한은 다음 물음을 시작할지만 정하므로, 마지막 물음이
    제한을 넘긴 뒤에 200을 받으면 제한보다 큰 값이 돌아올 수 있다. 제한 안에 돌아와야 하는 단언은
    호출하는 쪽이 그 값을 제한과 다시 견주고, 결국 돌아오기만 보는 단언은 견주지 않는다."""
    started = time.monotonic()
    while time.monotonic() - started < limit:
        try:
            if get(stack, "/health") == 200:
                return round(time.monotonic() - started, 1)
        except OSError:
            pass
        time.sleep(0.5)
    return None


def issue_token(stack_directory: Path, project: str) -> str:
    done = run(
        [
            "docker",
            "compose",
            "-p",
            project,
            "exec",
            "-T",
            "server",
            "rag-engine",
            "bootstrap-token",
        ],
        cwd=stack_directory,
        env=clean_environment(),
    )
    # 로그는 JSON 줄이다. 토큰은 JSON이 아닌 마지막 줄이다.
    lines = [line for line in done.stdout.splitlines() if line.strip() and not line.startswith("{")]
    assert lines, done.stdout + done.stderr
    return lines[-1].strip()


def service_logs(stack: Stack, service: str) -> str:
    return compose(stack, "logs", "--no-color", "--no-log-prefix", service).stdout


async def search(stack: Stack) -> tuple[str, str, list[str], dict[str, object]]:
    """공식 MCP SDK 클라이언트로 443에 접속해 검색한다. 서버 정보의 이름과 번호, 도구 목록, 검색
    결과를 돌려준다."""
    cafile = stack.directory / "tls" / "fullchain.pem"
    url = f"https://localhost:{PUBLISHED_PORT}/mcp"
    async with httpx2.AsyncClient(
        headers=bearer(stack), verify=ssl.create_default_context(cafile=str(cafile))
    ) as http_client:
        async with Client(streamable_http_client(url, http_client=http_client)) as client:
            info = client.server_info
            assert info is not None
            tools = sorted(tool.name for tool in (await client.list_tools()).tools)
            result = await client.call_tool("search", {"query": QUERY})
    assert result.is_error is not True, result
    content = result.structured_content
    assert content is not None
    payload: dict[str, object] = dict(content)
    return info.name, info.version, tools, payload


def multipart(filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = "e2e-" + secrets.token_hex(8)
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), boundary


def server_fact(stack: Stack, template: str) -> str:
    container = compose(stack, "ps", "-q", "server").stdout.strip()
    return run(["docker", "inspect", "-f", template, container]).stdout.strip()


ADDRESS: Final = "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"
RESTART_COUNT: Final = "{{.RestartCount}}"


# ------------------------------ 한 번 띄우는 스택 ------------------------------


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Stack]:
    ensure_port_free()
    namespace, version = tidy_images()
    work = tmp_path_factory.mktemp("standalone")
    directory = unpack_bundle(work, namespace, version)
    project = PROJECT_PREFIX + secrets.token_hex(4)
    refuse_existing(project)
    built: Stack | None = None
    try:
        password = secrets.token_hex(24)
        write_env(directory, namespace, version, password)

        (directory / "tls").mkdir(exist_ok=True)
        run(list(CERTIFICATE_COMMAND), cwd=directory)
        own(directory, namespace, version, ["tls/privkey.pem"], "0:101")
        if sys.platform == "linux":
            run(["docker", "run", "--rm", "--user", "0", "--entrypoint", "chmod",
                 "-v", f"{directory}:/work", f"{namespace}/rag-engine-server:{version}",
                 "0640", "/work/tls/privkey.pem"])  # fmt: skip

        models = directory / "models" / "embedding"
        given = os.environ.get(MODELS_ENV)
        if given:
            shutil.copytree(given, models, symlinks=True)
        else:
            models.mkdir(parents=True)
        own(directory, namespace, version, ["models"], "10001:10001")

        built = Stack(project, directory, namespace, version, "", (None, 0.0))
        run(
            [*UP_COMMAND[:2], "-p", project, *UP_COMMAND[2:]],
            cwd=directory,
            env=clean_environment(),
            timeout=UP_TIMEOUT,
        )
        started = time.monotonic()
        try:
            first: int | None = get(built, "/health")
        except OSError:
            first = None
        built.first_health = (first, round(time.monotonic() - started, 2))
        built.token = issue_token(directory, project)
        ingested = compose(
            built, "run", "--rm", "--no-deps", "-T",
            "-v", f"{SAMPLE_DIR}:/sample:ro",
            "worker", "rag-engine", "ingest", "/sample", "--wait", "--timeout", "600",
            timeout=900,
        )  # fmt: skip
        assert any("\t" in line for line in ingested.stdout.splitlines()), ingested.stdout
        yield built
    finally:
        try:
            if built is not None:
                save_logs(built, tmp_path_factory)
        finally:
            # 로그를 남기다 실패해도 아래 정리는 반드시 돈다. 컨테이너와 볼륨이 남으면 다음 실행의
            # 443을 막는다.
            run(
                ["docker", "compose", "-p", project, "down", "-v", "--remove-orphans"],
                cwd=directory,
                env=clean_environment(),
                check=False,
            )
            leftovers = run(
                ["docker", "ps", "-aq", "--filter", f"name={project}-holder"], check=False
            ).stdout.split()
            if leftovers:
                run(["docker", "rm", "-f", *leftovers], check=False)
            own(
                directory,
                namespace,
                version,
                ["."],
                f"{os.getuid()}:{os.getgid()}" if sys.platform == "linux" else "",
            )


def save_logs(stack: Stack, tmp_path_factory: pytest.TempPathFactory) -> None:
    """컨테이너 로그를 파일로 남긴다. 실패한 실행을 되짚는 자리다."""
    folders = [tmp_path_factory.mktemp("logs")]
    given = os.environ.get(LOGS_ENV)
    if given:
        folders.append(Path(given))
    logs = compose(stack, "logs", "--no-color", "--timestamps", check=False).stdout
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "compose.log").write_text(logs, encoding="utf-8")


# ------------------------------ 띄우는 순간 ------------------------------


def test_빈_필수_값이면_compose_config가_종료_1이고_그_값의_이름을_적는다(stack: Stack) -> None:
    template = (stack.directory / ".env").read_text(encoding="utf-8")
    values = env_values(stack.namespace, stack.version, "x" * 8)
    for name in REQUIRED_VALUES:
        # 이름 하나만 비운 .env. 나머지 셋은 채워 둔다.
        empty = tmpfile(stack, {**values, name: ""}, template)
        done = run(
            ["docker", "compose", "-p", stack.project, "--env-file", str(empty), "config"],
            cwd=stack.directory,
            env=clean_environment(),
            check=False,
        )
        assert done.returncode == 1, (name, done.stdout, done.stderr)
        assert name in done.stderr, (name, done.stderr)


def tmpfile(stack: Stack, values: Mapping[str, str], template: str) -> Path:
    target = stack.directory / f".env.{secrets.token_hex(3)}"
    lines = [
        f"{line.partition('=')[0]}={values[line.partition('=')[0]]}"
        if line.partition("=")[0] in values and "=" in line
        else line
        for line in template.splitlines()
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def test_리랭커_프로필의_config가_종료_0이다(stack: Stack) -> None:
    done = compose(stack, "--profile", "reranker", "config", check=False)

    assert done.returncode == 0, done.stderr
    assert "reranker" in done.stdout


def test_띄우는_명령이_돌아온_직후의_첫_health가_502_없이_200이다(stack: Stack) -> None:
    status, seconds = stack.first_health

    assert status == 200, (status, seconds)


def test_띄우는_명령은_프록시가_TLS로_답한_뒤에_돌아온다(stack: Stack) -> None:
    # 프록시에 건강 검사가 없으면 `up --wait`는 컨테이너가 떴다는 것만 보고 돌아와, 위 시험이
    # nginx가 포트를 여는 속도에 기대게 된다.
    health = {
        str(service["Service"]): service.get("Health")
        for service in json_objects(compose(stack, "ps", "--format", "json").stdout)
    }

    assert health.get("proxy") == "healthy", health


def test_호스트에_열린_포트는_프록시의_443_하나다(stack: Stack) -> None:
    published: set[tuple[str, int]] = set()
    for service in json_objects(compose(stack, "ps", "--format", "json").stdout):
        publishers = service.get("Publishers")
        for publisher in _OBJECTS.validate_python(publishers or []):
            port = publisher.get("PublishedPort")
            if isinstance(port, int) and port:
                published.add((str(service["Service"]), port))

    assert published == {("proxy", PUBLISHED_PORT)}


def test_서버_작업자_프록시_임베딩_서버의_1번_프로세스는_root가_아니다(stack: Stack) -> None:
    for service in NON_ROOT_SERVICES:
        status = compose(
            stack, "exec", "-T", service, "grep", "-E", "^Uid", "/proc/1/status"
        ).stdout
        real_uid = int(status.split()[1])
        assert real_uid != 0, (service, status)


def test_두_이미지의_version_첫_줄이_넘긴_번호와_같다(stack: Stack) -> None:
    for target in ("server", "worker"):
        out = run(["docker", "run", "--rm", stack.image(target), "rag-engine", "--version"]).stdout
        assert out.splitlines()[0] == f"rag-engine {stack.version}", (target, out)


# ------------------------------ 검색 ------------------------------


async def test_MCP_검색_결과에_표본_문서의_문장이_들고_서버_정보의_번호가_넘긴_번호와_같다(
    stack: Stack,
) -> None:
    name, version, tools, found = await search(stack)

    assert (name, version) == ("rag-engine", stack.version)
    assert "search" in tools
    results = found["results"]
    assert isinstance(results, list) and results
    first = json_object(json.dumps(results[0]))
    assert EXPECTED in str(first["text"])


def test_허용하지_않은_이름의_MCP는_421_토큰_없으면_401이다(stack: Stack) -> None:
    initialize = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "e2e", "version": "0"},
            },
        }
    ).encode()
    headers = bearer(stack) | {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    cafile = stack.directory / "tls" / "fullchain.pem"

    allowed, answer_headers, _ = request(
        "POST", "/mcp", host=HOST_NAME, headers=headers, body=initialize, cafile=cafile
    )
    other, _, _ = request(
        "POST", "/mcp", host=OTHER_HOST, headers=headers, body=initialize, cafile=cafile
    )
    no_token, _, _ = request(
        "POST", "/mcp", headers={"Content-Type": "application/json"}, body=b"{}", cafile=cafile
    )

    assert (allowed, other, no_token) == (200, 421, 401)
    assert answer_headers["strict-transport-security"] == "max-age=31536000"


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/mcp/",
        "/api/v1/other",
        "/api/v1/ingest",
        "/api/v1/admin",
    ],
)
def test_허용_목록_밖_경로는_301_없이_404이다(stack: Stack, path: str) -> None:
    assert get(stack, path, headers=bearer(stack)) == 404


def test_nginx_t_c와_nginx_s_reload_c가_종료_코드_0이다(stack: Stack) -> None:
    checked = compose(
        stack, "exec", "-T", "proxy", "nginx", "-t", "-c", PROXY_MAIN_CONFIG, check=False
    )
    reloaded = compose(
        stack, "exec", "-T", "proxy", "nginx", "-s", "reload", "-c", PROXY_MAIN_CONFIG, check=False
    )

    assert checked.returncode == 0, checked.stderr
    assert reloaded.returncode == 0, reloaded.stderr
    assert until_ready(stack, 30) is not None


# ------------------------------ TLS ------------------------------


def handshake(cafile: Path, port: int, version: ssl.TLSVersion) -> str | None:
    """보안 수준을 낮춘(`SECLEVEL=0`) 클라이언트가 `version` 하나만 내밀어 손을 맺은 판. 거부되면
    None.

    수준을 낮추지 않으면 OpenSSL 3 클라이언트가 스스로 1.1을 거부해 서버의 설정과 상관없이 이 확인을
    지난다.
    """
    context = ssl.create_default_context(cafile=str(cafile))
    context.set_ciphers("DEFAULT:@SECLEVEL=0")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        context.minimum_version = version
        context.maximum_version = version
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname="localhost") as secured:
                return secured.version()
    except (ssl.SSLError, OSError):
        return None


def serve_only(directory: Path, version: ssl.TLSVersion) -> tuple[int, Path, threading.Thread]:
    """대조군. `version` 하나만 받는 서버를 루프백에 띄워 한 번 받는다. 이 클라이언트가 그 판을
    실제로 내밀 수 있다는 것을 보인다. 못 내밀면 프록시가 거부해도 서버의 설정과 상관없다.

    인증서는 `directory`에 새로 만든다. 스택의 키(`tls/privkey.pem`)는 리눅스에서 `root:101`,
    `0640`이라 시험을 돌리는 사용자가 읽지 못한다. 돌려주는 경로가 이 서버의 인증서다.
    """
    certificate = directory / "control-cert.pem"
    key = directory / "control-key.pem"
    run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-keyout", str(key), "-out", str(certificate), "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ]
    )  # fmt: skip
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.set_ciphers("DEFAULT:@SECLEVEL=0")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        context.minimum_version = version
        context.maximum_version = version
    context.load_cert_chain(str(certificate), str(key))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(15)
    port = listener.getsockname()[1]
    assert isinstance(port, int)

    def accept() -> None:
        try:
            connection, _ = listener.accept()
            with context.wrap_socket(connection, server_side=True):
                pass
        except (ssl.SSLError, OSError):
            pass
        finally:
            listener.close()

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    return port, certificate, thread


def test_TLS_1_1만_내밀면_맺지_못하고_1_2와_1_3은_맺는다(stack: Stack, tmp_path: Path) -> None:
    cafile = stack.directory / "tls" / "fullchain.pem"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        old = ssl.TLSVersion.TLSv1_1
    port, control_certificate, thread = serve_only(tmp_path, old)
    control = handshake(control_certificate, port, old)
    thread.join(timeout=20)

    assert control is not None, (
        "대조군: 이 클라이언트가 TLS 1.1을 내밀지 못한다. 확인이 서버와 상관없이 지난다"
    )
    # nginx 쪽 OpenSSL도 기본 보안 수준에서 1.1을 스스로 거절해, `ssl_protocols`에 1.1을 넣은
    # 사본으로도 아래 손 맺기가 거부된다(깨뜨린 사본으로 봤다). 그래서 설정이 정한 판 목록을 실행
    # 중인 프록시에서 직접 읽어 맞댄다.
    effective = compose(stack, "exec", "-T", "proxy", "nginx", "-T", "-c", PROXY_MAIN_CONFIG)
    protocols = [
        line.strip()
        for line in effective.stdout.splitlines()
        if line.strip().startswith("ssl_protocols")
    ]
    assert protocols == ["ssl_protocols TLSv1.2 TLSv1.3;"], protocols
    assert handshake(cafile, PUBLISHED_PORT, old) is None
    assert handshake(cafile, PUBLISHED_PORT, ssl.TLSVersion.TLSv1_2) == "TLSv1.2"
    assert handshake(cafile, PUBLISHED_PORT, ssl.TLSVersion.TLSv1_3) == "TLSv1.3"


# ------------------------------ 올리기와 로그 ------------------------------


def test_2MB_올리기가_202이다(stack: Stack) -> None:
    body, boundary = multipart("big2.pdf", b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024))
    status, _, _ = request(
        "POST",
        "/api/v1/ingest/documents",
        headers=bearer(stack) | {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        body=body,
        cafile=stack.directory / "tls" / "fullchain.pem",
    )

    assert status == 202


def marked_get(stack: Stack) -> tuple[str, int | None]:
    """질의 문자열에 표지를 실은 GET. 표지와 받은 상태 코드를 돌려준다. 연결 오류는 None이다."""
    marker = "e2e-key-" + secrets.token_hex(6)
    try:
        status = get(stack, f"/api/v1/admin/documents?key={marker}&limit=1", headers=bearer(stack))
    except OSError:
        status = None
    return marker, status


def test_질의_문자열의_표지가_프록시_로그에_남지_않는다(stack: Stack) -> None:
    marker, status = marked_get(stack)
    time.sleep(1)

    assert status == 200
    assert marker not in service_logs(stack, "proxy")
    assert "/api/v1/admin/documents" in service_logs(stack, "proxy")  # 요청 자체는 로그에 남았다


async def test_임베딩_서버와_PostgreSQL의_로그에_질의와_표본_문서의_글이_없다(stack: Stack) -> None:
    await search(stack)  # 이 시험을 홀로 돌려도 질의가 임베딩 서버를 지난다
    marker = "표지문장" + secrets.token_hex(4)
    script = (
        "import json, sys, urllib.error, urllib.request\n"
        "body = json.dumps({'inputs': [sys.argv[1]], 'normalize': sys.argv[1]},"
        " ensure_ascii=False).encode()\n"
        "request = urllib.request.Request('http://embedding:80/embed', data=body,"
        " headers={'Content-Type': 'application/json'})\n"
        "try:\n"
        "    print(urllib.request.urlopen(request, timeout=30).status)\n"
        "except urllib.error.HTTPError as error:\n"
        "    print(error.code)\n"
    )
    rejected = compose(stack, "exec", "-T", "server", "python", "-c", script, marker)

    # 꼴이 틀린 본문은 거절된다. 거절되지 않은 요청으로 초록이 되지 않게 먼저 본다.
    assert rejected.stdout.strip() == "422", rejected.stdout + rejected.stderr
    needles = (
        QUERY,
        EXPECTED,
        QUERY.encode("unicode_escape").decode(),
        marker,
        marker.encode("unicode_escape").decode(),
    )
    for service in ("embedding", "postgres"):
        log = service_logs(stack, service)
        assert log.strip(), f"{service}의 로그가 비어 있다. 없다는 단언이 빈 로그로 초록이 된다"
        assert [needle for needle in needles if needle in log] == [], service
    for service in ("server", "worker", "proxy"):
        assert stack.token not in service_logs(stack, service), service


# ------------------------------ 되살아나는 것(서버를 건드린다) ------------------------------


def test_서버_프로세스를_죽이면_컨테이너가_다시_떠_15초_안에_200이다(stack: Stack) -> None:
    before = int(server_fact(stack, RESTART_COUNT))
    # 컨테이너 안에서 1번 프로세스(tini)를 뺀 모든 프로세스를 죽인다. `docker kill`은 사람이 멈춘
    # 것으로 남아 재시작 정책이 돌지 않는다.
    compose(
        stack, "exec", "-T", "server", "python", "-c",
        "import os, signal; os.kill(-1, signal.SIGKILL)", check=False,
    )  # fmt: skip
    seconds = until_ready(stack, RECOVERY_SECONDS)

    assert int(server_fact(stack, RESTART_COUNT)) > before  # 재시작 정책이 실제로 다시 띄웠다
    assert seconds is not None and seconds <= RECOVERY_SECONDS, seconds


def occupy(stack: Stack, address: str, names: list[str]) -> bool:
    """서버가 비운 주소를 다른 컨테이너가 차지하게 한다. 띄운 컨테이너의 이름을 `names`에 더하고, 그
    주소를 받은 컨테이너가 있으면 참이다. 비운 주소가 여럿이면 하나만 띄운 컨테이너가 다른 주소를
    받으므로 옛 주소를 받은 컨테이너가 나올 때까지 여덟 개까지 띄운다."""
    for index in range(8):
        name = f"{stack.project}-holder-{index}"
        run(
            ["docker", "run", "-d", "--rm", "--name", name, "--network", f"{stack.project}_default",
             stack.image("server"), "sleep", "300"]
        )  # fmt: skip
        names.append(name)
        if run(["docker", "inspect", "-f", ADDRESS, name]).stdout.strip() == address:
            return True
    return False


def test_옛_주소를_다른_컨테이너가_차지한_채_서버_컨테이너를_다시_만들어도_15초_안에_200이다(
    stack: Stack,
) -> None:
    # 옛 주소가 비어 있으면 새 컨테이너가 같은 주소를 받을 수 있어, 이름을 시작할 때만 푸는 설정도
    # 이 확인을 지난다. 그래서 옛 주소를 차지하게 한다.
    old = server_fact(stack, ADDRESS)
    compose(stack, "rm", "-sf", "server")
    holders: list[str] = []
    try:
        taken = occupy(stack, old, holders)
        compose(stack, "up", "-d", "--no-deps", "--wait", "server")
        seconds = until_ready(stack, RECOVERY_SECONDS)
        moved = server_fact(stack, ADDRESS) != old
    finally:
        if holders:
            run(["docker", "rm", "-f", *holders], check=False)
        # 도우미를 띄우다 실패해 서버를 올리지 못한 채 끝나도 뒤의 시험이 서버가 있는 스택에서 돈다.
        # 정상 경로에서는 이미 떠 있어 아무것도 바꾸지 않는다.
        compose(stack, "up", "-d", "--no-deps", "--wait", "server", check=False)

    assert taken, "대조군: 옛 주소를 다른 컨테이너가 차지하지 못했다"
    assert moved
    assert seconds is not None and seconds <= RECOVERY_SECONDS, seconds


def test_서버가_멈춘_동안에도_질의_문자열의_표지가_프록시_로그에_남지_않는다(stack: Stack) -> None:
    compose(stack, "stop", "server")
    try:
        time.sleep(8)  # 서버의 이름이 DNS에서 빠질 때까지 기다린다
        marker, status = marked_get(stack)
        time.sleep(1)
        log = service_logs(stack, "proxy")
    finally:
        compose(stack, "start", "server")
        assert until_ready(stack, 60) is not None

    assert status in (502, 503, 504), status  # 서버가 멈춘 동안의 요청이 실제로 오류가 됐다
    assert marker not in log
