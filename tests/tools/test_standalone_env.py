"""단독 compose 시험(`tests/standalone/`)의 `.env` 채우기와 실패 메시지를 Docker 없이 본다.

그 시험은 기본 수집에서 빠지고 이미지를 띄워야 돌아서(`pyproject.toml`의 `norecursedirs`), 이름공간
이 다른 경로(릴리스 워크플로가 부르는 길)는 GitHub 러너에서 처음 돌았고 거기서 실패했다(핫픽스
standalone-test-fills-image-namespace). 이 파일은 `tests/tools/`에 두고, 순수한 부분만 경로로 불러
본다. 기본 수집에 드는 자리가 여기뿐이어서다.
"""

import importlib.util
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest
from tools.release import NAMESPACE_MARKER, VERSION_MARKER

ROOT: Final = Path(__file__).resolve().parents[2]
STANDALONE: Final = ROOT / "tests" / "standalone" / "test_standalone_compose.py"
ENV_EXAMPLE: Final = ROOT / "deploy" / "standalone" / ".env.example"

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
