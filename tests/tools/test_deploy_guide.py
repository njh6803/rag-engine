"""설치 안내(`deploy/standalone/README.md`)가 배포 파일 묶음의 다른 파일과 어긋나지 않는지 보는
저장소 상태 시험(release-image 04).

안내는 운영자가 따라 치는 명령과 채울 파일 이름을 적는다. 그 이름과 소유가 compose 파일, 프록시
설정, `.env.example`, 단독 compose 시험과 어긋나면 운영자가 안내대로 하고도 컨테이너가 서지
않는다(예: 키 파일의 그룹이 프록시가 도는 사용자와 다르면 프록시가 시작에서 끝난다). 이 시험은
Docker 없이 그 정합이 깨지지 않는지만 잠근다. 안내의 명령을 실제로 쳐 본 결과는 티켓 Comments에
있다.

agent-os의 `tests/tools/test_deploy_guide.py`(기점 `b74a8adf2`)를 옮기며 뺀 것은 이 저장소에 없는
것들이다. 위젯 테스트 페이지의 개인 키와 설정(`portal/`), 사이트 파일(`site/`), 관리 화면에 닿는 SSH
포트 포워딩, 플러그인·기록 볼륨과 `npx`, `calc` 에이전트, IPv4 레코드(A, AAAA)와 `userland-proxy`의
말, 80번 포트, Engine의 루프백 포트 경고 둘(`DOCKER_INSECURE_NO_IPTABLES_RAW`, 28.0.0 이전
버전)이다. 이 저장소의 단독 compose는 루프백에만 여는 포트가 없고 밖에 여는 포트가 프록시의 443
하나다. 더한 것은 모델 폴더(소유와 리비전), 리랭커 켜기, 서버 `/tmp` 크기, 프록시 설정을 고친 뒤의
두 명령이다. 안내의 띄우는 명령, 인증서를 만드는 명령, 모델 폴더의 명령이 단독 compose
시험(`tests/standalone/test_standalone_compose.py`)이 치는 것과 같은지도 본다(시험은 안내대로
밟는다고 정했으므로 둘을 대는 검사가 없으면 한쪽만 고친 PR이 지난다).
"""

from __future__ import annotations

import ast
import re
import shlex
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from tools.release import build_bundle

REPO = Path(__file__).resolve().parents[2]
STANDALONE = REPO / "deploy" / "standalone"
GUIDE = STANDALONE / "README.md"
TLS_NOTE = STANDALONE / "tls" / "README.txt"
MODELS_NOTE = STANDALONE / "models" / "README.txt"
STANDALONE_TEST = REPO / "tests" / "standalone" / "test_standalone_compose.py"

# 명세 "설치 안내"와 03의 일지가 넘긴 문장에서 안내가 반드시 가져야 할 낱말. 낱말마다 그 낱말이
# 지키는 항목을 적는다.
REQUIRED: dict[str, str] = {
    "28.3.3": "지원하는 Docker Engine의 최소 버전",
    "2.20.2": "지원하는 Docker Compose의 최소 버전",
    "29.9.2": "잰 Docker Engine의 버전",
    "5.6.1": "잰 Docker Compose의 버전",
    "재지 않았": "최소 버전에서는 재지 않았다는 말",
    "Podman": "보증하는 환경 밖",
    "ARM": "보증하는 환경 밖",
    "GPU": "GPU 이미지로 바꾸는 설치는 다루지 않는다는 말",
    "rootless": "rootless 모드는 보증하는 환경이 아니라는 말",
    "32GB": "메모리의 기준",
    "16GB": "메모리의 최소",
    "chmod 600 .env": "환경 변수 파일은 운영자만 읽게 둘 것",
    "openssl rand -hex 24": "데이터베이스 비밀번호를 만드는 명령",
    "openssl req -x509": "자체 서명 인증서를 만드는 명령",
    "클라이언트마다": "자체 서명 인증서를 믿게 하는 방법은 클라이언트마다 다르다는 말",
    "root:101": "프록시 키 파일의 소유",
    "chmod 640": "프록시 키 파일의 권한",
    "mkdir -p models/embedding": "모델 폴더를 만드는 명령",
    "sudo chown -R 10001:10001 models": "모델 폴더의 소유",
    "refs/main": "받은 모델의 리비전을 읽는 자리",
    "5617a9f61b028005a4858fdac845db406aefb181": "시험한 리비전",
    "docker compose up -d --wait --wait-timeout 1800": "띄우기",
    "같은 명령을 다시": "첫 시작이 기다림을 넘겼을 때 같은 명령을 다시 치라는 말",
    "docker compose ps": "컨테이너 상태 확인",
    "rag-engine bootstrap-token": "첫 인증 토큰",
    "rag-engine ingest": "문서 넣기",
    "Authorization: Bearer": "MCP 클라이언트가 토큰을 싣는 머리",
    "--profile reranker": "리랭커를 프로필로 켜는 명령",
    "models/reranker": "리랭커의 모델 폴더",
    "RAG_DEFAULT_RERANKER_URL=http://reranker:80": "리랭커의 끝점",
    "docker compose run --rm migrate": "리랭커를 켠 뒤 마이그레이션을 다시 돌리는 명령",
    "11GiB": "리랭커를 켠 설치의 메모리",
    "RAG_SEARCH_TIMEOUT_SECONDS": "리랭커를 켠 설치의 검색 시간 제한",
    "RAG_SEARCH_CANDIDATES": "리랭커를 켠 설치의 후보 수",
    "RAG_MAX_UPLOAD_MB": "올리는 파일의 상한",
    "RAG_ENGINE_SERVER_TMP_SIZE": "상한을 올리는 설치가 함께 올릴 서버 /tmp의 크기",
    "proxy_read_timeout": "검색의 시간 제한을 올리는 설치가 함께 올릴 프록시의 기다림",
    "약 10초": "서버를 다시 시작하는 동안 오류가 나는 시간",
    "docker compose logs server": "서버에 닿지 못한 까닭은 서버 로그에서 찾는다는 말",
    "nginx -t -c": "프록시 설정을 고친 뒤 먼저 문법을 볼 것",
    "nginx -s reload -c": "프록시 설정을 고친 뒤 다시 읽힐 것",
    "rag-engine_postgres": "지우면 안 되는 볼륨",
    "rag-engine_data": "지우면 안 되는 볼륨",
    "docker save": "인터넷이 막힌 곳의 반입",
    "docker load": "인터넷이 막힌 곳의 반입",
    "sha256sum": "인터넷이 막힌 곳의 반입의 해시 대조",
    "docker image inspect": "대조할 해시가 이미지의 ID라는 것",
    "compose.override.yaml": "반입한 이미지의 로컬 이름을 쓰게 하는 파일",
    "100회": "Docker Hub의 받는 횟수 제한(로그인하지 않은 때)",
    "200회": "Docker Hub의 받는 횟수 제한(무료 개인 계정)",
    "docker login": "받는 횟수 제한에 걸렸을 때 할 일",
    "업그레이드할 때 할 일": "버전을 바꾸기 전에 릴리스 노트의 그 절을 먼저 본다는 것",
    "find proxy -mindepth 1 -delete": "업그레이드가 proxy 폴더 안을 비우는 명령",
    "docker compose stop server worker": "업그레이드가 옛 서버와 작업자를 먼저 멈추는 명령",
    "--remove-orphans": "스키마 단계가 실패했을 때 되돌리는 명령",
    "RAG_ENGINE_VERSION": "업그레이드가 바꾸는 번호의 칸",
    "proxy/. proxy/": "업그레이드가 새 proxy 파일을 비운 폴더 안으로 복사하는 명령",
    "--pull never": "폐쇄망에서 이미지를 받으러 나가지 않게 하는 띄우기 옵션",
    "docker compose ps -a": "끝난 마이그레이션 컨테이너까지 보는 명령",
    "rm -rf proxy.old": "지난 업그레이드의 복사본을 치워 덮어쓰기가 안으로 들어가지 않게 하는 명령",
    "compose.override.yaml.old": "폐쇄망 설치의 되돌리기가 옛 이름을 복원하게 하는 백업",
    "--numeric-owner": "받는 기계와 싣는 기계의 이름이 달라도 소유가 번호로 남게 하는 tar 옵션",
    "1GiB": "서버 /tmp의 기본 상한",
}

# 운영자는 쓰지 않는 저장소 안의 말. 안내와 두 폴더의 설명에 새면 운영자가 뜻을 알 수 없다.
INTERNAL_WORDS = (
    ".scratch",
    "ADR",
    "티켓",
    "docs/",
    "release-image",
    "명세",
    "CLAUDE.md",
    "probes",
    "세션",
    "원칙",
)

# 설치 안내의 `docker compose` 명령이 서비스 이름을 받는 동사와, 그 동사가 값을 받는 옵션.
SERVICE_VERBS = ("exec", "run", "stop", "logs", "restart")
VALUE_OPTIONS = ("-v", "-e", "--user", "-u", "--entrypoint", "-p", "-f", "--profile")


def 없는_항목(guide: str) -> list[str]:
    """안내에 없는 필수 낱말과 그 낱말이 지키는 항목."""
    return [f"{word}: {item}" for word, item in REQUIRED.items() if word not in guide]


def 샌_안의_말(text: str) -> list[str]:
    """글에 샌 저장소 안의 말."""
    return [word for word in INTERNAL_WORDS if word in text]


def 안내의_명령(guide: str) -> list[str]:
    """안내의 ```bash 블록에 적힌 명령. 줄 끝의 `\\`로 이어진 줄은 한 명령으로 잇는다."""
    commands: list[str] = []
    for block in re.findall(r"```bash\n(.*?)```", guide, flags=re.DOTALL):
        joined = re.sub(r"\\\n\s*", "", block)
        commands.extend(line.strip() for line in joined.splitlines() if line.strip())
    return commands


def 시험의_노드(name: str) -> ast.expr:
    """단독 compose 시험 파일의 최상위 상수 하나의 값 식. 파일을 불러오지 않고 문법 트리에서
    읽는다."""
    tree = ast.parse(STANDALONE_TEST.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return node.value
    raise AssertionError(f"단독 compose 시험에 상수 {name} 이 없다")


def 글_값(node: ast.expr) -> str:
    assert isinstance(node, ast.Constant), "글 상수가 아니다"
    assert isinstance(node.value, str), "글 상수가 아니다"
    return node.value


def 글_튜플(node: ast.expr) -> tuple[str, ...]:
    assert isinstance(node, ast.Tuple), "글의 튜플이 아니다"
    return tuple(글_값(item) for item in node.elts)


def 시험의_명령(name: str) -> tuple[str, ...]:
    return 글_튜플(시험의_노드(name))


def 시험의_명령_여럿(name: str) -> list[tuple[str, ...]]:
    node = 시험의_노드(name)
    assert isinstance(node, ast.Tuple), f"{name} 이 명령의 튜플이 아니다"
    return [글_튜플(item) for item in node.elts]


def 시험의_글(name: str) -> str:
    return 글_값(시험의_노드(name))


def 자체_서명_명령의_틀(tokens: list[str]) -> list[str]:
    """인증서 명령에서 운영자가 이름을 바꾸는 값(기간, 서버 이름, 대체 이름)을 자리 표지로 바꾼
    꼴."""
    shape: list[str] = []
    replace_next = {"-days": "<기간>", "-subj": "<주체>", "-addext": "<대체 이름>"}
    pending: str | None = None
    for token in tokens:
        if pending is not None:
            shape.append(pending)
            pending = None
        elif token in replace_next:
            shape.append(token)
            pending = replace_next[token]
        else:
            shape.append(token)
    return shape


def 명령_어긋남(guide: str) -> list[str]:
    """안내의 명령이 단독 compose 시험이 치는 명령과 다른 곳."""
    commands = 안내의_명령(guide)
    problems: list[str] = []

    up = " ".join(시험의_명령("UP_COMMAND"))
    if up not in commands:
        problems.append(f"띄우는 명령이 시험과 다르다: {up}")

    for folder_command in 시험의_명령_여럿("MODEL_FOLDER_COMMANDS"):
        line = " ".join(folder_command)
        if line not in commands:
            problems.append(f"모델 폴더의 명령이 시험과 다르다: {line}")

    certificates = [c for c in commands if c.startswith("openssl req -x509")]
    if len(certificates) != 1:
        problems.append(f"자체 서명 인증서 명령이 하나가 아니다: {len(certificates)}")
    else:
        mine = shlex.split(certificates[0])
        theirs = list(시험의_명령("CERTIFICATE_COMMAND"))
        if 자체_서명_명령의_틀(mine) != 자체_서명_명령의_틀(theirs):
            problems.append(f"인증서 명령이 시험과 다르다: {certificates[0]}")
        options = dict(zip(mine, mine[1:], strict=False))
        days = options.get("-days", "")
        if not days.isdigit() or int(days) <= 0:
            problems.append(f"인증서의 유효 기간이 양의 정수가 아니다: {days!r}")
        subject = options.get("-subj", "")
        names = options.get("-addext", "")
        host = subject.removeprefix("/CN=")
        if not subject.startswith("/CN=") or f"DNS:{host}" not in names:
            problems.append(f"인증서의 서버 이름이 대체 이름에 없다: {subject} {names}")
        for extra in ("DNS:localhost", "IP:127.0.0.1"):
            if extra not in names:
                problems.append(f"인증서의 대체 이름에 {extra} 가 없다: {names}")

    main_config = 시험의_글("PROXY_MAIN_CONFIG")
    for verb in ("nginx -t -c", "nginx -s reload -c"):
        if f"{verb} {main_config}" not in guide:
            problems.append(f"프록시 명령이 주 설정 경로를 주지 않는다: {verb} {main_config}")
    return problems


def compose의_서비스(compose: str) -> set[str]:
    """compose 파일의 서비스 이름."""
    block = re.search(r"^services:\n(.*?)^\S", compose, flags=re.DOTALL | re.MULTILINE)
    assert block is not None, "compose 에 services 가 없다"
    return set(re.findall(r"^  ([a-z]+):\s*$", block.group(1), flags=re.MULTILINE))


def compose의_user(compose: str, service: str) -> str:
    """compose 파일에서 서비스 하나의 `user:` 값. 없으면 빈 글. 값 뒤의 `# 주석`은 값에 넣지
    않는다."""
    block = re.search(rf"^  {service}:\n((?:    .*\n|\n)+)", compose, flags=re.MULTILINE)
    assert block is not None, f"compose 에 서비스 {service} 가 없다"
    user = re.search(
        r'^    user:\s*"?([^"\n#]+?)"?\s*(?:#.*)?$', block.group(1), flags=re.MULTILINE
    )
    return "" if user is None else user.group(1)


def 안내가_부르는_서비스(guide: str) -> set[str]:
    """안내의 `docker compose` 명령이 이름으로 부르는 서비스."""
    called: set[str] = set()
    for command in 안내의_명령(guide):
        tokens = shlex.split(command)
        if tokens[:2] != ["docker", "compose"]:
            continue
        rest = tokens[2:]
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            index += 2 if rest[index] in VALUE_OPTIONS else 1
        if index >= len(rest) or rest[index] not in SERVICE_VERBS:
            continue
        verb = rest[index]
        words = rest[index + 1 :]
        position = 0
        while position < len(words):
            word = words[position]
            if word.startswith("-"):
                position += 2 if word in VALUE_OPTIONS else 1
                continue
            called.add(word)
            if verb in ("exec", "run"):
                break
            position += 1
    return called


def test_이_저장소의_설치_안내는_넘겨받은_항목을_모두_싣는다() -> None:
    missing = 없는_항목(GUIDE.read_text(encoding="utf-8"))
    assert missing == [], f"안내에 없는 항목: {missing}"


def test_필수_낱말_하나가_빠진_안내를_잡는다() -> None:
    guide = GUIDE.read_text(encoding="utf-8").replace("sha256sum", "")
    missing = 없는_항목(guide)
    assert missing != []
    assert all(entry.startswith("sha256sum:") for entry in missing)


def test_이_저장소의_설치_안내와_두_폴더의_설명은_저장소_안의_말을_쓰지_않는다() -> None:
    for path in (GUIDE, TLS_NOTE, MODELS_NOTE):
        leaked = 샌_안의_말(path.read_text(encoding="utf-8"))
        assert leaked == [], f"{path.relative_to(REPO)} 에 샌 저장소 안의 말: {leaked}"


def test_저장소_안의_말이_샌_글을_잡는다() -> None:
    assert 샌_안의_말("자세한 것은 ADR 0020을 본다") == ["ADR"]


def test_안내의_명령은_단독_compose_시험이_치는_명령과_같다() -> None:
    assert 명령_어긋남(GUIDE.read_text(encoding="utf-8")) == []


def test_시험과_다른_명령을_적은_안내를_잡는다() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    cases = {
        "띄우는 명령": guide.replace("--wait-timeout 1800", "--wait-timeout 600"),
        "모델 폴더": guide.replace("sudo chown -R 10001:10001 models", "sudo chown -R 1000 models"),
        "인증서 옵션": guide.replace("-newkey rsa:2048", "-newkey rsa:4096"),
        "인증서 이름": guide.replace("DNS:localhost", "DNS:otherhost"),
        "프록시 주 설정": guide.replace("nginx -t -c", "nginx -t"),
    }
    for label, changed in cases.items():
        assert changed != guide, f"{label}: 바꿀 글이 안내에 없다"
        assert 명령_어긋남(changed) != [], f"{label}: 어긋남을 못 잡았다"


def test_안내의_명령이_하나도_모이지_않으면_실패한다() -> None:
    assert 안내의_명령(GUIDE.read_text(encoding="utf-8")) != []
    assert 안내의_명령("명령 없는 글") == []


def test_안내가_이름으로_부르는_서비스는_모두_compose에_있다() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    compose = (STANDALONE / "compose.yaml").read_text(encoding="utf-8")
    called = 안내가_부르는_서비스(guide)
    assert {"proxy", "server", "worker", "migrate"} <= called, f"안내가 부르는 서비스: {called}"
    assert called - compose의_서비스(compose) == set()


def test_안내가_모르는_서비스를_부르는_명령을_잡는다() -> None:
    assert 안내가_부르는_서비스("```bash\ndocker compose exec nope nginx -t\n```\n") == {"nope"}
    assert 안내가_부르는_서비스("```bash\ndocker compose stop a b\n```\n") == {"a", "b"}
    run = "```bash\ndocker compose run --rm -v <폴더>:/import:ro worker x\n```\n"
    assert 안내가_부르는_서비스(run) == {"worker"}


class 묶음_파일(NamedTuple):
    """정합을 대는 파일들의 글. 시험이 파일을 읽어 이 값을 만들고, 변이 시험은 한 칸만 바꾼 사본을
    낸다."""

    guide: str
    compose: str
    site: str
    nginx_conf: str
    template: str
    tls_note: str
    models_note: str
    bake: str


def 묶음_파일_읽기() -> 묶음_파일:
    def read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    return 묶음_파일(
        guide=read(GUIDE),
        compose=read(STANDALONE / "compose.yaml"),
        site=read(STANDALONE / "proxy" / "site.conf"),
        nginx_conf=read(STANDALONE / "proxy" / "nginx.conf"),
        template=read(STANDALONE / ".env.example"),
        tls_note=read(TLS_NOTE),
        models_note=read(MODELS_NOTE),
        bake=read(REPO / "deploy" / "images" / "docker-bake.hcl"),
    )


def 인증서_이름_어긋남(files: 묶음_파일) -> list[str]:
    """안내와 인증서 폴더 설명이 적은 인증서와 키의 이름이 프록시 설정이 읽는 이름과 어긋난 곳."""
    problems: list[str] = []
    if "ssl_certificate /etc/nginx/tls/fullchain.pem;" not in files.site:
        problems.append("프록시 설정이 읽는 인증서 이름이 fullchain.pem 이 아니다")
    if "ssl_certificate_key /etc/nginx/tls/privkey.pem;" not in files.site:
        problems.append("프록시 설정이 읽는 키 이름이 privkey.pem 이 아니다")
    if "./tls:/etc/nginx/tls:ro" not in files.compose:
        problems.append("compose 가 tls/ 폴더를 프록시에 얹지 않는다")
    for label, text in (("안내", files.guide), ("tls/README.txt", files.tls_note)):
        for name in ("fullchain.pem", "privkey.pem"):
            if name not in text:
                problems.append(f"{label} 에 {name} 이 없다")
    return problems


def 주_설정_어긋남(files: 묶음_파일) -> list[str]:
    """프록시 주 설정의 경로가 compose 가 프록시에 주는 경로와 어긋난 곳."""
    problems: list[str] = []
    main_config = 시험의_글("PROXY_MAIN_CONFIG")
    if f'"-c", "{main_config}"' not in files.compose:
        problems.append(f"compose 가 프록시에 -c {main_config} 를 주지 않는다")
    if "./proxy:/etc/rag-engine/proxy:ro" not in files.compose:
        problems.append("compose 가 proxy/ 폴더를 읽기 전용으로 얹지 않는다")
    if files.nginx_conf.strip() == "":
        problems.append("proxy/nginx.conf 가 비었다")
    return problems


def 환경_변수_칸_어긋남(files: 묶음_파일) -> list[str]:
    """`.env.example` 의 칸 가운데 안내에 없는 것."""
    names = re.findall(r"^#?\s*([A-Z][A-Z0-9_]*)=", files.template, flags=re.MULTILINE)
    if len(names) < 6:
        return [f".env.example 에서 칸을 거의 못 읽었다: {names}"]
    return [f"안내에 없는 환경 변수 칸: {name}" for name in names if name not in files.guide]


def 소유_어긋남(files: 묶음_파일) -> list[str]:
    """안내가 적은 소유의 uid 와 gid 가 그 컨테이너가 도는 사용자와 어긋난 곳."""
    problems: list[str] = []
    proxy_user = compose의_user(files.compose, "proxy")
    if ":" not in proxy_user:
        return [f"프록시의 user 가 uid:gid 꼴이 아니다: {proxy_user!r}"]
    proxy_gid = proxy_user.split(":")[1]
    if f"sudo chown root:{proxy_gid} tls/privkey.pem" not in files.guide:
        problems.append(f"안내가 키 파일의 그룹을 프록시의 {proxy_gid} 로 주지 않는다")
    if f"root:{proxy_gid}" not in files.tls_note:
        problems.append(f"tls/README.txt 가 키 파일의 그룹 {proxy_gid} 를 적지 않는다")
    for service in ("embedding", "reranker"):
        user = compose의_user(files.compose, service)
        if user == "":
            problems.append(f"{service} 에 user 가 없다")
        elif f"sudo chown -R {user} models" not in files.guide:
            problems.append(f"안내가 {service} 의 소유 {user} 를 모른다")
    if "mkdir -p models/reranker" not in files.guide:
        problems.append("안내가 models/reranker 를 만들지 않는다")
    if "10001:10001" not in files.models_note:
        problems.append("models/README.txt 가 10001:10001 을 적지 않는다")
    return problems


def 리비전_어긋남(files: 묶음_파일) -> list[str]:
    """안내와 모델 폴더 설명이 적은 모델 리비전이 어긋난 곳."""
    problems: list[str] = []
    if REVISION not in files.guide:
        problems.append("안내에 시험한 리비전이 없다")
    for word in (REVISION, "refs/main", "models/embedding", "models/reranker"):
        if word not in files.models_note:
            problems.append(f"models/README.txt 에 {word} 가 없다")
    return problems


def 폴더_설명_어긋남(files: 묶음_파일) -> list[str]:
    """두 폴더 설명이 적어야 할 낱말 가운데 빠진 것."""
    problems: list[str] = []
    models_words = ("내려받", "폐쇄망", "docker compose up -d --wait --wait-timeout 1800")
    for word in models_words:
        if word not in files.models_note:
            problems.append(f"models/README.txt 에 없는 낱말: {word}")
    for word in ("fullchain.pem", "privkey.pem", "root:101", "640"):
        if word not in files.tls_note:
            problems.append(f"tls/README.txt 에 없는 낱말: {word}")
    return problems


def 고치지_말_것_어긋남(files: 묶음_파일) -> list[str]:
    """안내가 고치지 말라고 한 것을 compose 가 지키지 않는 곳."""
    problems: list[str] = []
    blocks = re.findall(r"^    ports:\n((?:      - .*\n?)+)", files.compose, flags=re.MULTILINE)
    published = [line.strip().removeprefix("- ") for block in blocks for line in block.splitlines()]
    if published != ['"0.0.0.0:443:8443"']:
        problems.append(f"compose 가 밖에 여는 포트가 프록시의 443 하나가 아니다: {published}")
    if "enable_ipv6: false" not in files.compose:
        problems.append("compose 가 안쪽 네트워크의 IPv6 를 끄지 않는다")
    if "고치지" not in files.guide:
        problems.append("안내에 compose 를 고치지 말라는 말이 없다")
    return problems


def 대응표_어긋남(files: 묶음_파일) -> list[str]:
    """서비스와 이미지의 대응표가 compose 의 서비스와 이미지 줄을 모두 싣지 않는 곳."""
    table = [line for line in files.guide.splitlines() if line.startswith("|")]
    if not table:
        return ["안내에 대응표가 없다"]
    text = "\n".join(table)
    services = compose의_서비스(files.compose)
    if not services:
        return ["compose 에서 서비스를 하나도 읽지 못했다"]
    problems = [
        f"대응표에 서비스 {service} 가 없다"
        for service in sorted(services)
        if f"`{service}`" not in text
    ]
    repositories = re.findall(r"\}/(rag-engine-[a-z]+):", files.compose)
    if sorted(repositories) != ["rag-engine-server", "rag-engine-server", "rag-engine-worker"]:
        problems.append(f"compose 의 우리 이미지가 서버 둘과 작업자 하나가 아니다: {repositories}")
    for repository in sorted(set(repositories)):
        if f"<이름공간>/{repository}" not in text:
            problems.append(f"대응표에 이미지 {repository} 가 없다")
        if f"/{repository}:" not in files.bake:
            problems.append(f"bake 설정에 저장소 {repository} 가 없다")
    for image in re.findall(r"^    image: (?!\$)(\S+)", files.compose, flags=re.MULTILINE):
        repository = re.split(r"[:@]", image, maxsplit=1)[0]
        if ("/" in repository or repository == "nginx") and repository not in text:
            problems.append(f"대응표에 바깥 이미지 {repository} 가 없다")
    return problems


REVISION = "5617a9f61b028005a4858fdac845db406aefb181"

# 이름이 정합을 대는 쪽이고, 변이 시험이 같은 이름의 검사가 걸리는지 본다.
정합_검사: dict[str, Callable[[묶음_파일], list[str]]] = {
    "인증서 이름": 인증서_이름_어긋남,
    "프록시 주 설정": 주_설정_어긋남,
    "환경 변수 칸": 환경_변수_칸_어긋남,
    "소유": 소유_어긋남,
    "리비전": 리비전_어긋남,
    "폴더 설명": 폴더_설명_어긋남,
    "고치지 말 것": 고치지_말_것_어긋남,
    "대응표": 대응표_어긋남,
}

# (걸려야 할 검사, 바꿀 칸, 바꿀 글, 바꾼 글). 칸마다 한 글자라도 어긋나면 그 검사가 걸린다.
정합_변이: tuple[tuple[str, str, str, str], ...] = (
    ("인증서 이름", "site", "fullchain.pem", "chain.pem"),
    ("프록시 주 설정", "compose", "./proxy:/etc/rag-engine/proxy:ro", "./proxy:/x:ro"),
    ("환경 변수 칸", "guide", "POSTGRES_PASSWORD", "DB_PASSWORD"),
    ("소유", "guide", "sudo chown root:101 tls/privkey.pem", "sudo chown root:100 tls/privkey.pem"),
    ("리비전", "models_note", REVISION, "0" * 40),
    ("소유", "guide", "sudo chown -R 10001:10001 models", "sudo chown -R 10001:10002 models"),
    ("인증서 이름", "site", "privkey.pem", "key.pem"),
    ("인증서 이름", "compose", "./tls:/etc/nginx/tls:ro", "./tls:/x:ro"),
    ("폴더 설명", "tls_note", "640", "600"),
    ("폴더 설명", "models_note", "폐쇄망", "오프라인"),
    ("고치지 말 것", "guide", "고치지", "건드리지"),
    (
        "고치지 말 것",
        "compose",
        '      - "0.0.0.0:443:8443"\n',
        '      - "0.0.0.0:443:8443"\n      - "5432:5432"\n',
    ),
    ("대응표", "guide", "| `reranker` |", "| `rerank` |"),
)


def test_이_저장소의_설치_안내는_묶음의_다른_파일과_어긋나지_않는다() -> None:
    files = 묶음_파일_읽기()
    for label, check in 정합_검사.items():
        assert check(files) == [], f"{label}: {check(files)}"


def test_한_칸만_어긋난_안내와_묶음의_파일을_잡는다() -> None:
    files = 묶음_파일_읽기()
    assert set(label for label, *_ in 정합_변이) == set(정합_검사)
    for label, field, old, new in 정합_변이:
        original: str = getattr(files, field)
        assert old in original, f"{label}: 바꿀 글이 {field} 에 없다"
        changed = files._replace(**{field: original.replace(old, new)})
        assert 정합_검사[label](changed) != [], f"{label}: 어긋남을 못 잡았다"


def 바깥_이미지(compose: str) -> list[str]:
    """compose 가 digest 로 고정한 바깥 이미지. 같은 이미지는 한 번만, 나온 차례로 센다."""
    found = re.findall(r"^    image: (\S+@sha256:[0-9a-f]{64})\s*$", compose, flags=re.MULTILINE)
    return list(dict.fromkeys(found))


def 서비스의_바깥_이미지(compose: str) -> dict[str, str]:
    """digest 로 고정한 바깥 이미지를 쓰는 compose 서비스와 그 이미지."""
    pattern = r"^  ([a-z]+):\n(?:    .*\n|\n)*?    image: (\S+@sha256:[0-9a-f]{64})\s*$"
    return dict(re.findall(pattern, compose, flags=re.MULTILINE))


def 폐쇄망_어긋남(guide: str, compose: str) -> list[str]:
    """폐쇄망 절이 적은 로컬 이름이 compose 가 고정한 digest 와 어긋난 곳. 로컬 이름의 태그는
    digest 의 앞 12자이고, `docker tag` 줄과 담는 목록과 `compose.override.yaml` 이 같은 이름을
    써야 한다."""
    problems: list[str] = []
    commands = 안내의_명령(guide)
    override = dict(
        re.findall(r"^  ([a-z]+):\n    image: (rag-engine-offline/\S+)$", guide, flags=re.MULTILINE)
    )
    images = 바깥_이미지(compose)
    if len(images) != 3:
        problems.append(f"바깥 이미지가 셋이 아니다: {len(images)}")
    save_lines = [line for line in commands if line.startswith("IMAGES=")]
    local_names: dict[str, str] = {}
    for image in images:
        digest = image.rsplit("sha256:", 1)[1][:12]
        tagged = [
            line
            for line in commands
            if line.startswith(f"docker tag {image} rag-engine-offline/")
            and line.endswith(f":{digest}")
        ]
        if len(tagged) != 1:
            problems.append(f"digest 앞 12자를 태그로 단 docker tag 줄이 하나가 아니다: {image}")
            continue
        name = tagged[0].rsplit(" ", 1)[1]
        local_names[image] = name
        if not any(name in line for line in save_lines):
            problems.append(f"담는 목록(IMAGES)에 로컬 이름이 없다: {name}")
    outside = 서비스의_바깥_이미지(compose)
    expected = {"proxy", "postgres", "embedding", "reranker"}
    if set(outside) != expected:
        problems.append(f"바깥 이미지를 쓰는 서비스가 {sorted(expected)} 가 아니다")
    if set(override) != expected:
        problems.append(f"안내의 override 가 {sorted(expected)} 를 덮지 않는다: {sorted(override)}")
    for service, image in outside.items():
        name = local_names.get(image, "")
        if override.get(service) != name:
            problems.append(f"compose.override.yaml 의 {service} 가 {name!r} 을 쓰지 않는다")
    return problems


def test_이_저장소의_폐쇄망_절은_compose가_고정한_digest의_로컬_이름을_쓴다() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    compose = (STANDALONE / "compose.yaml").read_text(encoding="utf-8")
    assert 폐쇄망_어긋남(guide, compose) == []


def test_digest와_다른_로컬_이름을_적은_폐쇄망_절을_잡는다() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    compose = (STANDALONE / "compose.yaml").read_text(encoding="utf-8")
    first = 바깥_이미지(compose)[0]
    digest = first.rsplit("sha256:", 1)[1][:12]
    assert digest in guide
    broken = guide.replace(f":{digest}", ":000000000000")
    assert 폐쇄망_어긋남(broken, compose) != []
    other_end = "1" if first.endswith("0") else "0"
    assert 폐쇄망_어긋남(guide, compose.replace(first, first[:-1] + other_end)) != []
    swapped = guide.replace(
        "  proxy:\n    image: rag-engine-offline/nginx:583b7f2fce1c",
        "  proxy:\n    image: rag-engine-offline/tei:2538ea1c9640",
    )
    assert swapped != guide
    assert 폐쇄망_어긋남(swapped, compose) != []


def test_배포_파일_묶음에_안내와_두_폴더의_설명이_든다(tmp_path: Path) -> None:
    built = build_bundle(STANDALONE, tmp_path, "0.1.0-rc.1", "njh6803")
    with tarfile.open(built) as archive:
        names = set(archive.getnames())
        root = "rag-engine-0.1.0-rc.1"
        for relative, source in (
            ("README.md", GUIDE),
            ("tls/README.txt", TLS_NOTE),
            ("models/README.txt", MODELS_NOTE),
        ):
            assert f"{root}/{relative}" in names, f"묶음에 {relative} 가 없다"
            member = archive.extractfile(f"{root}/{relative}")
            assert member is not None
            assert member.read().decode("utf-8") == source.read_text(encoding="utf-8")
        assert f"{root}/models/embedding" not in names
