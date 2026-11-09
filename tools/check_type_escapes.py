"""타입 우회 검사. 헌법 원칙 II의 파이썬 판정자(`docs/constitution/principles.md`).

원칙 II는 `Any`, `cast`, `type: ignore`, `pyright: ignore`를 금하는데 **pyright strict는 그 넷을
하나도 잡지 않는다.** 명시적 `Any`는 Unknown이 아니고, `cast`는 정상 API이며, 억제 주석은 정의상
억제된다. ruff의 지금 select도 마찬가지다. 그래서 헌법 원칙 하나가 교정 루프 사다리("타입 →
린터·훅 → 아키텍처 테스트 → 지침 → 리뷰")의 맨 아래 층에 있었다.

pre-commit과 CI가 돌린다. 판정자는 이 파일 하나다 — ruff 규칙 일부(ANN401, PGH003)와 pyright 설정
일부(`enableTypeIgnoreComments`)를 함께 켜면 넷을 부분씩 나눠 보는 판정자가 둘 이상 생기고, 그것이
티켓 01에서 같은 패턴 문자열을 엔진 둘이 다르게 읽어 계약 결함이 검사 넷을 통과한 모양이다.

**grep이 아니라 파싱이다.** 이 저장소의 문서·주석·테스트는 금지된 이름을 계속 입에 올린다(이 파일이
그 예다). 이름은 AST에서, 억제 지시문은 주석 토큰에서만 본다. 거짓 양성을 줄인 자리가 셋이다.

- 속성 접근은 `typing`을 가리키는 이름 뒤일 때만 본다. 남의 `cast` 메서드를 잡지 않는다.
- 주석은 지시문이 **맨 앞일 때만** 본다. 뒤에 설명이 붙어도 억제는 걸리므로 뒤는 닫지 않는다(실측).
- 주해 안의 문자열 중 **타입으로 읽히는 것만** 다시 파싱한다. `Literal["cast"]`의 값과
  `Annotated[str, "cast"]`의 메타데이터는 타입이 아니다.
- 반대로 **문자열로 쓴 주해는 다시 파싱한다.** `x: "typing.Any"`는 AST에서 이름이 아니지만 pyright가
  `Any`로 읽으므로 그것이 곧 우회다.

이름은 문맥을 가리지 않는다. `cast`라는 지역 변수도 잡히고 비용은 개명 한 번이다. 대입과 읽기를
가르면 `cast = 3`은 통과하고 `print(cast)`는 걸리는, 설명할 수 없는 규칙이 된다.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
import tomllib
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 쓰면 안 되는 이름 둘. 어디서 왔든(typing 의 속성이든 import 한 이름이든) 같게 본다.
BANNED_NAMES = frozenset({"Any", "cast"})

# 속성 접근을 볼 기준이 되는 모듈. 별칭으로 import 하면 그 별칭도 여기에 붙는다.
_TYPING_MODULES = frozenset({"typing", "typing_extensions"})

_STRICT = "strict"

# pyright 가 분석하는 확장자 둘. 스텁도 `Any` 를 담고 pyright 는 거기서도 그것을 잡지 않는다.
_SOURCE_GLOBS = ("*.py", "*.pyi")

# 지시문이 주석의 맨 앞일 때만 억제다. **뒤에 설명이 붙어도 억제는 그대로 걸린다**(pyright 실측:
# `# type: ignore[assignment] 이유를 적는다` 로 오류가 0 이 된다). 그래서 뒤를 닫지 않는다.
# 반대로 지시문이 맨 앞이 아니면 억제하지 않으므로(`# 타입 억제(type: ignore)는 금지다` 는 오류가
# 그대로 난다) 그런 산문은 지나간다. 이 줄의 근거는 전부 pyright 를 돌려 잰 것이다.
_TYPE_IGNORE = re.compile(r"^#\s*type:\s*ignore(?![A-Za-z0-9_])")
# pyright 지시문은 꼴을 열거하지 않고 본문이 `strict` 하나인지만 본다. 열거하면 목록이 곧
# 구멍이 된다 — `# pyright: basic, reportX=false` 처럼 쉼표로 이은 것이 실제로 새어 나갔다.
_PYRIGHT_DIRECTIVE = re.compile(r"^#\s*pyright:\s*(?P<rest>\S.*?)\s*$")
# 파일 하나에만 거는 pyright 지시문은 저장소 설정과 갈린다. 조이는 쪽이라도 그 파일만 다른
# 규칙으로 판정되므로 억제도, basic 도, reportX=... 도 같게 본다.


def scanned_roots(root: Path = ROOT) -> tuple[str, ...]:
    """검사할 디렉터리. `[tool.pyright]`의 `include`를 그대로 읽는다.

    범위를 손으로 두 곳에 적지 않는다. 타입체커가 보지 않는 곳에서 우회를 금해도 뜻이 없고,
    타입체커가 보는 곳이 늘었는데 이 판정자가 모르면 그 구간이 조용히 열린다.

    `typeCheckingMode`가 strict가 아니면 멈춘다. 파일 하나에 거는 `pyright` 지시문을 잡으면서
    저장소 전체를 끄는 설정 한 줄을 지나치면, 더 센 우회가 더 조용한 우회가 된다.
    """
    설정 = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    모드: object = 설정["tool"]["pyright"]["typeCheckingMode"]
    if 모드 != _STRICT:
        raise ValueError(f"[tool.pyright] typeCheckingMode 가 {_STRICT!r} 가 아니다: {모드!r}")
    include: list[object] = 설정["tool"]["pyright"]["include"]
    디렉터리 = tuple(항목 for 항목 in include if isinstance(항목, str))
    if len(디렉터리) != len(include):
        raise ValueError("[tool.pyright] include 가 문자열 목록이 아니다")
    return 디렉터리


def escapes_in(source: str) -> list[str]:
    """소스 하나에서 찾은 우회. 항목은 `"<줄번호>: <무엇>"`이고 줄 순서다."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"{error.lineno or 0}: 파싱할 수 없어 판정하지 못했다 ({error.msg})"]

    찾은것 = _banned_names(tree) + _suppression_comments(source)
    return [한줄 for _, 한줄 in sorted(찾은것, key=lambda 짝: 짝[0])]


def _banned_names(tree: ast.Module) -> list[tuple[int, str]]:
    """AST에서만 본다. 문자열 리터럴과 독스트링에 같은 말이 있어도 이름이 아니다."""
    별칭 = _typing_aliases(tree)
    찾은것: list[tuple[int, str]] = _banned_imports(tree)
    for node in _every_node(tree):
        자리 = _named(node, 별칭)
        if 자리 is not None and 자리[1] in BANNED_NAMES:
            줄, 이름 = 자리
            찾은것.append((줄, f"{줄}: `{이름}` 은 원칙 II 가 금한다"))
    return 찾은것


def _typing_aliases(tree: ast.Module) -> frozenset[str]:
    """이 파일에서 typing 모듈을 가리키게 된 이름들. `import typing as tp` 의 `tp` 도 포함한다."""
    이름들 = set(_TYPING_MODULES)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name in _TYPING_MODULES and alias.asname is not None:
                이름들.add(alias.asname)
    return frozenset(이름들)


def _every_node(tree: ast.Module) -> Iterator[ast.AST]:
    """AST의 모든 노드. 문자열로 쓴 주해는 표현식으로 다시 파싱해 그 안까지 연다."""
    for node in ast.walk(tree):
        yield node
        for 주해 in _annotations_of(node):
            yield from _reparsed_strings(주해)


def _annotations_of(node: ast.AST) -> list[ast.expr]:
    """주해가 실리는 자리. 문자열이 타입으로 읽히는 곳은 여기뿐이다."""
    match node:
        case ast.AnnAssign(annotation=주해):
            return [주해]
        case ast.arg(annotation=ast.expr() as 주해):
            return [주해]
        case ast.FunctionDef(returns=ast.expr() as 주해):
            return [주해]
        case ast.AsyncFunctionDef(returns=ast.expr() as 주해):
            return [주해]
        case _:
            return []


def _reparsed_strings(주해: ast.expr) -> Iterator[ast.AST]:
    """주해 안의 전방 참조를 표현식으로 파싱한 노드들. 줄번호는 그 문자열이 있던 줄로 맞춘다."""
    for node, 원문 in _forward_refs(주해):
        try:
            안 = ast.parse(원문, mode="eval")
        except SyntaxError:
            continue
        for 속 in ast.walk(안.body):
            yield ast.copy_location(속, node)


def _forward_refs(node: ast.expr) -> Iterator[tuple[ast.Constant, str]]:
    """주해 안에서 **타입으로 읽히는** 문자열만. 주해 안의 모든 문자열이 타입인 것은 아니다.

    `Literal["Any"]` 의 문자열은 리터럴 값이고 `Annotated[str, "cast"]` 의 둘째부터는 메타데이터다.
    전부 다시 파싱하면 `Literal["cast", "keep"]` 같은 정상 코드가 하드 게이트에 막힌다.
    """
    match node:
        case ast.Constant(value=str() as 원문):
            yield (node, 원문)
        case ast.Subscript(value=밑, slice=속):
            yield from _forward_refs(밑)
            이름 = _attr_name(밑)
            if 이름 == "Literal":
                return
            if 이름 == "Annotated":
                첫 = _first_element(속)
                if 첫 is not None:
                    yield from _forward_refs(첫)
                return
            yield from _forward_refs(속)
        case ast.Tuple(elts=원소들) | ast.List(elts=원소들):
            for 원소 in 원소들:
                yield from _forward_refs(원소)
        case ast.BinOp(left=왼, right=오른):
            yield from _forward_refs(왼)
            yield from _forward_refs(오른)
        case _:
            return


def _attr_name(node: ast.expr) -> str | None:
    """`Literal` 도 `typing.Literal` 도 같은 이름으로 본다."""
    match node:
        case ast.Name(id=이름):
            return 이름
        case ast.Attribute(attr=이름):
            return 이름
        case _:
            return None


def _first_element(속: ast.expr) -> ast.expr | None:
    """`Annotated[X, ...]` 에서 타입인 것은 X 하나다."""
    if isinstance(속, ast.Tuple):
        return 속.elts[0] if 속.elts else None
    return 속


def _named(node: ast.AST, 별칭: frozenset[str]) -> tuple[int, str] | None:
    """이름을 가진 노드의 줄번호와 이름. 나머지는 None."""
    match node:
        case ast.Name(lineno=줄, id=이름):
            return (줄, 이름)
        case ast.Attribute(lineno=줄, attr=이름, value=ast.Name(id=모듈)) if 모듈 in 별칭:
            return (줄, 이름)
        case _:
            return None


def _banned_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """`from typing import cast as c` 처럼 이름을 바꿔 들여오는 길. **출처가 typing 일 때만 본다.**

    이름을 바꾸면 쓰는 자리가 `c(...)` 라서 이름 규칙에 걸리지 않으므로 들여오는 자리에서 잡는다.
    출처를 보지 않으면 `from sqlalchemy import cast` 같은 남의 흔한 이름이 하드 게이트에 막힌다.
    바꾸지 않고 들여온 것은 쓰는 자리에서 이름 규칙이 잡으므로 여기서 놓쳐도 구멍이 아니다.
    """
    찾은것: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module not in _TYPING_MODULES:
            continue
        for alias in node.names:
            if alias.name in BANNED_NAMES:
                줄 = alias.lineno
                찾은것.append((줄, f"{줄}: `{alias.name}` 은 원칙 II 가 금한다"))
    return 찾은것


def _suppression_comments(source: str) -> list[tuple[int, str]]:
    """주석 토큰에서만 본다. 지시문의 꼴을 온전히 갖춘 것만 억제로 센다."""
    찾은것: list[tuple[int, str]] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        줄 = token.start[0]
        if _TYPE_IGNORE.match(token.string) is not None:
            찾은것.append((줄, f"{줄}: 타입 억제 주석은 원칙 II 가 금한다"))
        지시문 = _PYRIGHT_DIRECTIVE.match(token.string)
        if 지시문 is not None and 지시문.group("rest") != _STRICT:
            찾은것.append(
                (줄, f"{줄}: 파일 하나에만 거는 pyright 지시문은 두지 않는다(strict 제외)")
            )
    return 찾은것


def main(root: Path = ROOT) -> int:
    """`root` 아래의 검사 범위를 전부 훑는다. 범위는 그 트리의 pyright 설정이 정한다."""
    문제: list[str] = []
    for 디렉터리 in scanned_roots(root):
        기준 = root / 디렉터리
        if not 기준.is_dir():
            raise ValueError(
                f"[tool.pyright] include 의 {디렉터리!r} 가 디렉터리가 아니다."
                " pyright 는 파일과 glob 패턴도 받지만 이 판정자는 아직 디렉터리만 다룬다."
                " 조용히 건너뛰면 훑은 것이 없는데 0건으로 초록이 된다"
            )
        파일들 = {경로 for 무늬 in _SOURCE_GLOBS for 경로 in 기준.rglob(무늬)}
        for path in sorted(파일들):
            상대 = path.relative_to(root).as_posix()
            문제.extend(f"{상대}:{한줄}" for 한줄 in escapes_in(path.read_text(encoding="utf-8")))
    for 한줄 in 문제:
        print(한줄)
    return 1 if 문제 else 0


if __name__ == "__main__":
    # 첫 인자는 검사 루트(임시 트리에서 빨강을 재는 CLI 테스트). pre-commit 은 인자 없이 부른다.
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT))
