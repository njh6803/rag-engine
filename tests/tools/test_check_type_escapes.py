"""tools/check_type_escapes.py. 원칙 II의 파이썬 판정자.

`Any`·`cast`·`type: ignore`·`pyright: ignore`를 pyright strict 도 지금의 ruff select 도 잡지
않는다. 교정 루프의 사다리("타입 → 린터·훅 → 아키텍처 테스트 → 지침 → 리뷰")에서 헌법 원칙 하나가
맨 아래 층에 있던 것을 훅 층으로 올린 것이다.

이 테스트가 고정하는 것은 **판정자가 무엇을 보고 무엇을 보지 않는가**다. 양쪽 다 고정한다 —
문자열과 주석을 가르지 못하면 이 저장소의 산문이 통째로 빨개지고, 문자열로 쓴 주해를 열지 못하면
`Any` 가 따옴표 하나로 빠져나간다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from tools.check_type_escapes import ROOT, escapes_in, main, scanned_roots


def _가짜_저장소(root: Path, *, mode: str = "strict", include: str = '["src"]') -> None:
    """검사 범위를 정하는 것은 그 트리의 pyright 설정이다. 테스트 트리도 자기 것을 갖는다."""
    (root / "pyproject.toml").write_text(
        f'[tool.pyright]\ninclude = {include}\ntypeCheckingMode = "{mode}"\n',
        encoding="utf-8",
        newline="\n",
    )
    (root / "src").mkdir(exist_ok=True)


def test_Any_를_쓰면_잡는다() -> None:
    source = "from typing import Any\n\n\ndef f(x: Any) -> None: ...\n"

    문제 = escapes_in(source)

    assert 문제 != []
    assert all("Any" in 한줄 for 한줄 in 문제)


def test_점으로_부른_Any_도_잡는다() -> None:
    source = "import typing\n\n\ndef f(x: typing.Any) -> None: ...\n"

    assert escapes_in(source) != []


def test_별칭으로_import_한_typing_도_잡는다() -> None:
    source = "import typing as tp\n\n\ndef f(x: tp.Any) -> None: ...\n"

    assert escapes_in(source) != []


def test_문자열로_쓴_주해_안의_Any_도_잡는다() -> None:
    """따옴표 하나로 빠져나가는 자리. AST에서는 이름이 아니지만 pyright 는 Any 로 읽는다."""
    source = 'import typing\n\n\ndef f(x: "typing.Any") -> None: ...\n'

    문제 = escapes_in(source)

    assert len(문제) == 1
    assert 문제[0].startswith("4:")


def test_주해_안쪽에_끼워_넣은_문자열도_잡는다() -> None:
    source = 'from typing import Any\n\n\nx: dict[str, "Any"] = {}\n'

    assert any(한줄.startswith("4:") for 한줄 in escapes_in(source))


def test_cast_호출을_잡는다() -> None:
    source = "from typing import cast\n\n\ndef f(x: object) -> str:\n    return cast(str, x)\n"

    문제 = escapes_in(source)

    assert 문제 != []
    assert all("cast" in 한줄 for 한줄 in 문제)


def test_별칭으로_import_한_cast_는_import_에서_잡힌다() -> None:
    source = "from typing import cast as c\n\n\nx = c(int, 1)\n"

    assert escapes_in(source) != []


def test_남의_모듈에서_같은_이름을_들여오는_것은_잡지_않는다() -> None:
    """`from sqlalchemy import cast` 는 흔한 import 다. 출처를 안 보면 게이트가 그것을 막는다."""
    source = "from sqlalchemy import cast as sql_cast\n\n\nx = sql_cast(1)\n"

    assert escapes_in(source) == []


def test_남의_이름을_그대로_쓰면_쓰는_자리에서_잡힌다() -> None:
    """들여오는 자리를 좁혀도 구멍이 아니다. 이름 그대로면 이름 규칙이 잡는다."""
    source = "from sqlalchemy import cast\n\n\nx = cast(1)\n"

    assert escapes_in(source) != []


def test_typing_이_아닌_것의_cast_속성은_잡지_않는다() -> None:
    """남의 `cast` 메서드까지 잡으면 하드 게이트가 거짓 양성 기계가 된다."""
    source = 'def f(col: object) -> object:\n    return col.cast("int")\n'

    assert escapes_in(source) == []


def test_진짜_억제_주석을_잡는다() -> None:
    source = "x: int = 1\ny: str = x  # type: ignore[assignment]\n"

    문제 = escapes_in(source)

    assert len(문제) == 1
    assert 문제[0].startswith("2:")


def test_pyright_ignore_주석을_잡는다() -> None:
    source = "x: int = 1\ny: str = x  # pyright: ignore[reportAssignmentType]\n"

    assert len(escapes_in(source)) == 1


def test_파일_전체에_거는_pyright_basic_도_잡는다() -> None:
    """`basic` 은 억제가 아니지만 파일 하나의 strict 를 끄는 같은 종류의 우회다."""
    assert escapes_in("# pyright: basic\nx: int = 1\n") != []


def test_조이는_쪽의_지시문은_지나간다() -> None:
    assert escapes_in("# pyright: strict\nx: int = 1\n") == []


def test_쉼표로_이은_지시문도_잡는다() -> None:
    """꼴을 열거하면 그 목록이 곧 구멍이 된다. 본문이 `strict` 하나인지만 본다."""
    assert escapes_in("# pyright: basic, reportMissingImports=false\nx = 1\n") != []


def test_규칙을_조이는_지시문도_잡는다() -> None:
    """`reportX=error` 는 조이지만 그 파일만 다른 규칙으로 판정된다. 통과하는 것은 strict 하나다."""
    assert escapes_in("# pyright: reportGeneralTypeIssues=error\nx = 1\n") != []


def test_설명이_뒤에_붙은_억제_주석도_잡는다() -> None:
    """pyright 실측: 뒤에 설명이 붙어도 억제는 그대로 걸린다. 산문처럼 보여도 억제는 억제다."""
    source = "x: int = 1\ny: str = x  # type: ignore[assignment] 이유를 적는다\n"

    assert len(escapes_in(source)) == 1


def test_지시문이_맨_앞이_아니면_잡지_않는다() -> None:
    """pyright 실측: 맨 앞이 아니면 억제하지 않는다. 이 저장소가 규칙을 설명할 때 쓰는 꼴이다."""
    source = "# 타입 억제(type: ignore)는 금지다\n# 이것도 pyright: ignore 를 말할 뿐이다\nx = 1\n"

    assert escapes_in(source) == []


def test_Literal_안의_문자열은_타입이_아니다() -> None:
    """`Literal["cast", "keep"]` 은 정상 코드다. 전부 다시 파싱하면 하드 게이트가 그것을 막는다."""
    source = 'from typing import Literal\n\n\ndef f(m: Literal["cast", "keep"]) -> None: ...\n'

    assert escapes_in(source) == []


def test_Annotated_의_메타데이터는_타입이_아니다() -> None:
    source = 'from typing import Annotated\n\nx: Annotated[str, "cast"] = ""\n'

    assert escapes_in(source) == []


def test_Annotated_의_첫_인자는_타입이라_본다() -> None:
    source = 'import typing\n\nx: typing.Annotated["typing.Any", "meta"] = 1\n'

    assert escapes_in(source) != []


def test_문자열과_독스트링_안의_같은_말은_잡지_않는다() -> None:
    """grep 판정자와 갈리는 자리."""
    source = (
        '"""원칙 II 는 Any 와 cast 를 금한다. type: ignore 도 마찬가지다."""\n'
        "\n"
        '금지 = ("Any", "cast")\n'
        '설명 = "pyright: ignore 를 달지 않는다"\n'
    )

    assert escapes_in(source) == []


def test_깨끗한_소스는_통과한다() -> None:
    assert escapes_in("def f(x: int) -> str:\n    return str(x)\n") == []


def test_파싱되지_않는_소스는_문제로_남는다() -> None:
    """판정할 수 없는 파일을 조용히 통과시키지 않는다. ruff 가 먼저 잡겠지만 여기도 닫아 둔다."""
    assert escapes_in("def f(\n") != []


def test_검사_범위가_pyright_의_include_와_같다() -> None:
    """범위를 손으로 두 곳에 적지 않는다. 티켓 01 이 판정자 둘로 갈려 겪은 것과 같은 종류다."""
    설정 = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert list(scanned_roots()) == 설정["tool"]["pyright"]["include"]


def test_strict_가_아니면_멈춘다(tmp_path: Path) -> None:
    """파일 하나에 거는 지시문을 잡으면서 저장소 전체를 끄는 설정 한 줄을 지나치지 않는다."""
    _가짜_저장소(tmp_path, mode="basic")

    with pytest.raises(ValueError, match="typeCheckingMode"):
        scanned_roots(tmp_path)


def test_include_가_문자열_목록이_아니면_멈춘다(tmp_path: Path) -> None:
    _가짜_저장소(tmp_path, include="[1, 2]")

    with pytest.raises(ValueError, match="include"):
        scanned_roots(tmp_path)


def test_include_에_디렉터리가_아닌_것이_있으면_멈춘다(tmp_path: Path) -> None:
    """pyright 는 파일과 glob 도 받는다. 조용히 건너뛰면 훑은 것이 없는데 0건으로 초록이 된다."""
    _가짜_저장소(tmp_path, include='["src", "src/**/*.py"]')

    with pytest.raises(ValueError, match="디렉터리가 아니다"):
        main(tmp_path)


def test_이_저장소에_지금_타입_우회가_0건이다() -> None:
    assert main() == 0


def test_스텁_파일의_우회도_잡는다(tmp_path: Path) -> None:
    """pyright 는 `.pyi` 도 분석하면서 거기서도 `Any` 를 잡지 않는다. 스텁이 조용한 우회로다."""
    _가짜_저장소(tmp_path)
    (tmp_path / "src" / "stub.pyi").write_text(
        "from typing import Any\n\ndef f(x: Any) -> Any: ...\n", encoding="utf-8", newline="\n"
    )

    assert main(tmp_path) == 1


def test_우회가_있는_파일이_섞이면_실패한다(tmp_path: Path) -> None:
    _가짜_저장소(tmp_path)
    (tmp_path / "src" / "clean.py").write_text("x: int = 1\n", encoding="utf-8", newline="\n")
    (tmp_path / "src" / "dirty.py").write_text(
        "from typing import Any\n\nx: Any = 1\n", encoding="utf-8", newline="\n"
    )

    assert main(tmp_path) == 1


def test_CLI_진입점이_임시_트리의_우회를_출력한다(tmp_path: Path) -> None:
    """pre-commit 이 부르는 진입점 그대로 — 루트를 첫 인자로 주면 그 트리를 본다(tests.md)."""
    _가짜_저장소(tmp_path)
    (tmp_path / "src" / "dirty.py").write_text(
        "from typing import Any\n\nx: Any = 1\n", encoding="utf-8", newline="\n"
    )

    process = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_type_escapes.py"), str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )

    assert process.returncode == 1
    assert "src/dirty.py" in process.stdout
