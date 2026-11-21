"""단독 compose 시험(`tests/standalone/`)의 `.env` 채우기와 실패 메시지를 Docker 없이 본다.

그 시험은 기본 수집에서 빠지고 이미지를 띄워야 돌아서(`pyproject.toml`의 `norecursedirs`), 이름공간
이 다른 경로(릴리스 워크플로가 부르는 길)는 GitHub 러너에서 처음 돌았고 거기서 실패했다(핫픽스
standalone-test-fills-image-namespace). 이 파일은 `tests/tools/`에 두고, 순수한 부분만 경로로 불러
본다. 기본 수집에 드는 자리가 여기뿐이어서다.
"""

import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Final

import pytest
from tools.release import NAMESPACE_MARKER, VERSION_MARKER

ROOT: Final = Path(__file__).resolve().parents[2]
STANDALONE: Final = ROOT / "tests" / "standalone" / "test_standalone_compose.py"
ENV_EXAMPLE: Final = ROOT / "deploy" / "standalone" / ".env.example"
PROXY_DIR: Final = ROOT / "deploy" / "standalone" / "proxy"
PROXY_SITE: Final = PROXY_DIR / "site.conf"

# nginx의 proxy_connect_timeout과 proxy_read_timeout 기본값. 설정이 정하지 않으므로 이 값이다.
PROXY_UPSTREAM_TIMEOUT: Final = 60.0

# 릴리스 워크플로가 방금 지어 러너에 실은 시험용 이미지의 이름공간과 올릴 묶음의 이름공간
TEST_NAMESPACE: Final = "rag-engine-release-test"
SHIPPED_NAMESPACE: Final = "njh6803"
VERSION: Final = "0.1.0-rc.1"


def load_standalone() -> ModuleType:
    spec = importlib.util.spec_from_file_location("standalone_compose_under_test", STANDALONE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


STANDALONE_MODULE: Final = load_standalone()
env_values: Callable[[str, str, str], Mapping[str, str]] = STANDALONE_MODULE.env_values
fill_env: Callable[[str, Mapping[str, str]], str] = STANDALONE_MODULE.fill_env
run: Callable[..., subprocess.CompletedProcess[str]] = STANDALONE_MODULE.run
write_env: Callable[[Path, str, str, str], None] = STANDALONE_MODULE.write_env


def shipped_example() -> str:
    """`tools/release.py bundle`이 묶음에 싣는 `.env.example`.

    두 표지를 올릴 이름공간과 번호로 바꾼다. 표지는 그 도구의 상수를 쓴다.
    """
    return (
        ENV_EXAMPLE.read_text(encoding="utf-8")
        .replace(NAMESPACE_MARKER, SHIPPED_NAMESPACE)
        .replace(VERSION_MARKER, VERSION)
    )


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        name, separator, value = line.partition("=")
        if separator and not name.startswith("#"):
            values[name] = value
    return values


def test_시험이_받은_이름공간과_번호가_올릴_묶음의_env에_들어간다() -> None:
    filled = fill_env(shipped_example(), env_values(TEST_NAMESPACE, VERSION, "password"))

    parsed = parse_env(filled)
    assert parsed["RAG_ENGINE_NAMESPACE"] == TEST_NAMESPACE
    assert parsed["RAG_ENGINE_VERSION"] == VERSION


def test_픽스처가_쓰는_함수가_묶음_폴더의_env를_시험용_이름공간으로_쓴다(tmp_path: Path) -> None:
    # `stack` 픽스처가 부르는 함수를 직접 부른다. 픽스처가 이 함수를 부르는지는 단독 시험을
    # 띄워야 알 수 있어 이 시험이 지키지 않는다. 여기서는 함수가 `.env`에 이름공간과 번호를
    # 채우는 것만 본다.
    (tmp_path / ".env.example").write_text(shipped_example(), encoding="utf-8")

    write_env(tmp_path, TEST_NAMESPACE, VERSION, "password")

    parsed = parse_env((tmp_path / ".env").read_text(encoding="utf-8"))
    assert parsed["RAG_ENGINE_NAMESPACE"] == TEST_NAMESPACE
    assert parsed["RAG_ENGINE_VERSION"] == VERSION
    assert parsed["POSTGRES_PASSWORD"] == "password"


def test_채울_칸은_필수_값_넷과_같다() -> None:
    assert set(env_values(TEST_NAMESPACE, VERSION, "password")) == set(
        STANDALONE_MODULE.REQUIRED_VALUES
    )


def test_실패한_명령의_stderr와_종료_코드가_예외_메시지에_있다() -> None:
    marker = "cause-marker-7f3a"
    # 표지가 명령 줄에 그대로 들면 예외 메시지의 명령 부분만으로 단언이 지난다. 두 토막으로 쪼개
    # 파이썬이 이어 붙인 stderr에만 온전한 표지가 있게 한다. PYTHONUTF8이 없는 Windows 셸에서는
    # 자식의 stderr가 cp949로 나가 한글 표지가 깨지므로 표지는 ASCII로 둔다.
    script = "import sys; sys.stderr.write('cause-' + 'marker-7f3a'); sys.exit(3)"

    with pytest.raises(subprocess.CalledProcessError) as caught:
        run([sys.executable, "-c", script])

    assert marker in str(caught.value)
    assert "exit status 3" in str(caught.value)
    assert caught.value.returncode == 3


def test_검사_없이_부르면_실패해도_예외_없이_돌려준다() -> None:
    done = run([sys.executable, "-c", "import sys; sys.exit(4)"], check=False)

    assert done.returncode == 4


def timeout_directives(config_text: str) -> list[str]:
    """nginx 설정 글에서 주석을 뺀 뒤 `proxy_…timeout` 낱말을 모두 찾는다.

    줄 머리에 기대지 않아 `location /slow { proxy_read_timeout 120s; }`처럼 블록과 같은 줄에 쓴
    지시문도 잡는다. 못 보는 것: 따옴표 안의 `#`를 주석으로 읽어 그 뒤를 버리는 것, `include`로
    들어오는 다른 파일의 지시문(이 폴더의 `.conf`는 모두 따로 훑는다), 변수 `$proxy_…timeout`을
    지시문으로 잘못 세는 것.
    """
    return re.findall(r"\bproxy_\w*timeout\b", re.sub(r"#[^\n]*", "", config_text))


def test_프록시는_뒷단_제한_시간을_따로_정하지_않아_nginx_기본_60초가_그대로다() -> None:
    # 서버가 멈춘 동안의 요청이 504로 끝나기까지의 시간이 60초라는 전제가 이 파일의 시험이 기대는
    # 값이다. 설정이 `proxy_*_timeout`을 정하면 그 전제가 틀어지므로 먼저 이 시험이 빨개진다.
    configs = sorted(PROXY_DIR.glob("*.conf"))
    assert PROXY_SITE in configs, configs  # 훑은 범위가 비면 아래 단언이 조용히 초록이 된다
    directives = [
        f"{config.name}: {name}"
        for config in configs
        for name in timeout_directives(config.read_text(encoding="utf-8"))
    ]

    assert directives == []


def test_블록과_같은_줄에_쓴_제한_시간_지시문을_잡는다() -> None:
    text = "server {\n    location /slow { proxy_read_timeout 120s; }\n}\n"

    assert timeout_directives(text) == ["proxy_read_timeout"]


def test_주석에만_적힌_제한_시간은_지시문으로_세지_않는다() -> None:
    text = "server {\n    # 답을 기다리는 시간(proxy_read_timeout)은 기본값 그대로 둔다.\n}\n"

    assert timeout_directives(text) == []


def test_서버가_멈춘_동안의_기다림은_프록시가_504를_내는_시간보다_길다() -> None:
    # 같으면 프록시가 504를 내기 직전에 시험 클라이언트가 먼저 끊고 상태 코드를 못 받는다. 첫
    # 릴리스의 첫 시도에서 서버 정지 시험이 그렇게 졌다(프록시 504가 60.026초, 클라이언트 제한이
    # 60.0초). 러너가 느려도 504를 받도록 10초 이상 더 준다.
    assert STANDALONE_MODULE.STOPPED_SERVER_TIMEOUT >= PROXY_UPSTREAM_TIMEOUT + 10


def fake_stack() -> object:
    return STANDALONE_MODULE.Stack(
        project="p",
        directory=Path("."),
        namespace="n",
        version="v",
        token="t",
        first_health=(200, 0.0),
    )


def test_기다림_제한을_주면_요청까지_그대로_전해진다(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float] = []

    def fake_request(*args: object, **kwargs: float) -> tuple[int, dict[str, str], bytes]:
        seen.append(kwargs["timeout"])
        return 504, {}, b""

    monkeypatch.setattr(STANDALONE_MODULE, "request", fake_request)
    stack = fake_stack()

    status = STANDALONE_MODULE.get(stack, "/x", timeout=123.0)
    default = STANDALONE_MODULE.get(stack, "/x")

    assert (status, default) == (504, 504)
    assert seen == [123.0, STANDALONE_MODULE.HTTP_TIMEOUT]


def test_표지_요청도_기다림_제한을_get까지_전한다(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float] = []

    def fake_get(*args: object, **kwargs: float) -> int:
        seen.append(kwargs["timeout"])
        return 504

    monkeypatch.setattr(STANDALONE_MODULE, "get", fake_get)
    stack = fake_stack()

    _, status = STANDALONE_MODULE.marked_get(stack, timeout=7.0)
    _, default_status = STANDALONE_MODULE.marked_get(stack)

    assert (status, default_status) == (504, 504)
    assert seen == [7.0, STANDALONE_MODULE.HTTP_TIMEOUT]


def test_서버_정지_시험은_표지_요청에_긴_기다림을_준다(monkeypatch: pytest.MonkeyPatch) -> None:
    # 서버 정지 시험 함수를 Docker 없이 가짜 의존물로 직접 불러, 표지 요청이 받은 기다림을 본다.
    # 누가 이 인자를 빼면 같은 간헐 실패가 돌아오는데, 위 두 시험은 초록으로 남기 때문이다.
    seen: list[float] = []

    def fake_marked_get(stack: object, *, timeout: float) -> tuple[str, int]:
        seen.append(timeout)
        return "marker", 504

    def fake_compose(*args: object, **kwargs: object) -> None:
        return None

    def fake_sleep(seconds: float) -> None:
        return None

    def fake_service_logs(stack: object, service: str) -> str:
        return ""

    def fake_until_ready(stack: object, limit: float) -> float:
        return 0.0

    monkeypatch.setattr(STANDALONE_MODULE, "compose", fake_compose)
    monkeypatch.setattr(STANDALONE_MODULE, "time", SimpleNamespace(sleep=fake_sleep))
    monkeypatch.setattr(STANDALONE_MODULE, "marked_get", fake_marked_get)
    monkeypatch.setattr(STANDALONE_MODULE, "service_logs", fake_service_logs)
    monkeypatch.setattr(STANDALONE_MODULE, "until_ready", fake_until_ready)

    STANDALONE_MODULE.test_서버가_멈춘_동안에도_질의_문자열의_표지가_프록시_로그에_남지_않는다(
        fake_stack()
    )

    assert seen == [STANDALONE_MODULE.STOPPED_SERVER_TIMEOUT]
