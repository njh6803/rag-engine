"""보이지 않는 줄 구분 문자 검사. 추적 텍스트 파일의 날것 U+2028·U+2029·U+0085 와 홀로 선 CR 을
잡고(대기열 22·52), `.py` 에서는 보이지 않는 공백·서식 문자도 잡는다(대기열 52). 텍스트 파일의
CRLF 줄 끝도 파일마다 한 줄로 잡는다(대기열 crlf-from-script-edits).

편집 도구가 테스트 소스의 U+2028·U+2029 이스케이프를 날것 문자로 저장했다(PR #58). pytest·ruff·
pyright 가 모두 초록이었고, 리뷰어는 문자가 보이지 않아 "U+2028 테스트가 없다" 는 오탐을 냈다.
파이썬의 `str.splitlines` 는 셋을 줄 끝으로 읽으므로 줄 단위로 보는 코드가 같은 파일을 다른 줄
수로 본다. 도구 호출의 역슬래시-r 도 날것 CR 로 바뀌어 `.md` 표에 들었다(일지 2026-09-29-05).
뒤에 LF 가 없는 CR 은 표 밖이면 조용히 줄을 가른다. CRLF 의 CR 은 홀로 선 CR 로 세지 않는다.
고정된 문자 패턴이라 규칙이 아니라 검사다. 선례는 `tools/check_type_escapes.py`.

CRLF 줄 끝은 따로 잡는다. `.gitattributes` 가 `* text=auto eol=lf` 라서 내 컴퓨터의 작업 사본이
CRLF 인 텍스트 파일은 늘 사고다. 처음에는 스크립트의 `write_text` 와 stdout 리다이렉트가 Windows
에서 LF 를 CRLF 로 바꿔 파일 아홉이 CRLF 가 됐다. 그때 이 검사는 CRLF 의 CR 을 줄 끝이라 보지 않아
0 이었고, `git add` 의 `CRLF will be replaced by LF` 경고로야 알았다(대기열 crlf-from-script-edits,
열한 번. 원인이 적힌 회차는 모두 스크립트나 리다이렉트이고 열한 번째는 원인을 가리지 못했다).
커밋은 git 이 LF 로 바꿔 담으므로 손상은 없지만, 바꾸기 전의 작업 사본을 읽는 도구는 CRLF 를
읽는다. 922 줄 파일이 922 줄의 출력을 내지 않도록 파일마다 한 줄이다: 첫 CRLF 의 줄·열과 CRLF 가 든
줄 수.

같은 세션에서 BOM·전각 공백·줄바꿈 없는 공백의 이스케이프도 날것이 되어 `.py` 에 남았고, 세 문자만
보던 이 검사는 잡지 못했다(대기열 52). 그래서 `.py` 에서는 ASCII 밖의 유니코드 일반 범주 Zs(공백
구분 문자)와 Cf(서식 문자)를 잡는다. 줄바꿈 없는 공백, 전각 공백, 폭 없는 공백·결합 문자, 방향
제어 문자, 파일 머리 뒤의 U+FEFF 가 여기 든다. 범위를 `.py` 로 둔 것은 한국어 문서의 전각 공백이
정당할 수 있어서다. 범주는 실행하는 파이썬의 `unicodedata` 가 정한다.

이 파일과 테스트는 그 문자를 이스케이프가 아니라 `chr()` 로 만든다. 이 검사를 쓰던 세션의 편집
도구가 역슬래시-u 이스케이프를 다시 날것으로 저장해 첫 실행에서 이 파일 자신이 잡혔다(2026-09-28).

텍스트 파일은 처음 8000 바이트에 NUL 이 없는 파일이다(git 의 `buffer_is_binary` 와 같은 경계).
UTF-8 BOM 은 벗기고 센다 — 편집기는 BOM 을 보이지 않으므로 열이 하나 밀린다. 파일 머리의 BOM 은
인코딩 표지라 `.py` 에서도 잡지 않는다. UTF-8 로 읽히지 않는
텍스트 파일과 읽을 수 없는 경로(없는 파일, 디렉터리)는 판정할 수 없어 어긋남으로 낸다 — 조용히
지나가면 훑지 않은 것이 초록이 된다. 인자 없이 부르면 인덱스의 일반 파일(모드 100644·100755)만
훑고, 작업 트리에서 지웠지만 아직 스테이지하지 않은 파일은 건너뛴다(볼 내용이 없다). 서브모듈과
심볼릭 링크는 대상이 아니다. 줄 번호는 개행(`\\n`)으로만, 열은 코드 포인트로 센다. `splitlines` 로
세면 잡으려는 문자가 줄을 늘려 자리가 틀린다.

못 보는 것: 이스케이프로 쓴 것(소스의 역슬래시-u 여섯 글자)은 날것이 아니라 잡지 않는다 — 그것이
맞는 꼴이다. 추적되지 않은 파일. 처음 8000 바이트 안에 NUL 이 든 이진 파일의 CRLF —
`evals/public-docs/` 의 PDF·HWPX·`.f32` 43 개는 CRLF 바이트를 가지지만 이진이라 텍스트 검사 밖이다.
8000 바이트 뒤에만 NUL 이 있는 파일은 이 검사가 텍스트로 보고 CRLF 를 센다. git 의 줄 끝 변환은
파일 전체의 NUL 을 보고 그런 파일을 이진으로 두어(`git ls-files --eol` 이 `-text` 로 낸다.
2026-11-21 git 2.32 에서 손으로 봤다) 바꾸지 않으므로, 이 경우 검사는 git 이 바꾸지 않는 CRLF 도
알린다. CRLF 가 정당한 텍스트 파일 — 이 저장소의 `.gitattributes` 는 LF 만 정하므로 가르지 않는다.
UTF-16 파일 — 대개 NUL 이 있어 이진으로 보고, NUL 이 없으면 UTF-8 로 잘못 읽는다. `.py` 밖의 파일에
든 보이지 않는 공백·서식 문자(TypeScript 소스도 여기 든다). Zs·Cf 밖의 보이지 않는 문자(결합 문자 Mn
인 이체 선택자 U+FE0F 등, 제어 문자 Cc 가운데 탭·개행·CR·U+0085 밖의 것 — NUL 은 이진 판정이 먼저
본다). 둘 다 테스트가 모든 코드 포인트를 훑어 고정한다. 확장자가 대문자인 파이썬 파일(`.PY`).

사용: `uv run python tools/check_line_separators.py [파일 ...]`. 인자가 없으면 추적 파일 전부.
pre-commit 은 스테이지된 텍스트 파일을 한 프로세스로 넘긴다(`types: [text]`, `require_serial`).
"""

from __future__ import annotations

import codecs
import io
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 이스케이프가 아니라 chr() 다. 편집 도구가 이스케이프를 날것으로 바꾸면 이 파일이 자기 검사에
# 걸린다(2026-09-28 실제로 그랬다). CR 은 뒤에 LF 가 없을 때만 잡는다(`_SEPARATOR`).
CR = chr(0x0D)
SEPARATORS = {
    chr(0x2028): "LINE SEPARATOR",
    chr(0x2029): "PARAGRAPH SEPARATOR",
    chr(0x0085): "NEXT LINE",
    CR: "CARRIAGE RETURN",
}
# `.py` 에서 잡는 유니코드 일반 범주. ASCII 에는 둘 다 공백(U+0020) 하나밖에 없어 ASCII 밖만 본다.
INVISIBLE_CATEGORIES = frozenset({"Zs", "Cf"})
SOURCE_SUFFIXES = frozenset({".py"})
_LF = chr(0x0A)
_CRLF = CR + _LF
_CRLF_PATTERN = re.compile(re.escape(_CRLF))
# CRLF 항목에 들어가는 낱말. 줄 구분 문자 항목의 ` U+` 와 겹치지 않아 안내가 갈린다.
CRLF_LABEL = "CRLF 줄 끝"
_SEPARATOR_PATTERN = "|".join(
    re.escape(each) + (f"(?!{_LF})" if each == CR else "") for each in SEPARATORS
)
_SEPARATOR = re.compile(_SEPARATOR_PATTERN)
# git 의 xdiff-interface.c `FIRST_FEW_BYTES`. 이 길이 안에 NUL 이 있으면 이진이다.
_TEXT_PROBE = 8000
# 인덱스에서 내용이 있는 일반 파일의 모드. 160000(서브모듈)과 120000(링크)은 뺀다.
_REGULAR_MODES = frozenset({"100644", "100755"})
# `git ls-files` 를 기다리는 초(대기열 342). 인자 없이 돌 때(pytest 의 저장소 상태 시험, 손으로 칠
# 때)만 부른다. pre-commit 훅은 파일 이름을 넘겨 이 호출에 닿지 않는다.
CALL_TIMEOUT = 60
HINT = (
    "소스에 그 문자가 필요하면 chr(0x2028) 처럼 만든다. "
    "이스케이프는 편집 도구가 날것으로 바꿀 수 있다. "
    "필요 없는 문자면 지우거나 공백은 ASCII 공백으로, 홀로 선 CR 은 개행으로 바꾼다."
)
CRLF_HINT = (
    "줄 끝이 Windows 식 줄바꿈(CR 문자 뒤에 LF 문자, CRLF)으로 저장됐다. 이 저장소는 "
    ".gitattributes 로 LF 하나만 쓰도록 정했다. 흔한 원인은 스크립트의 write_text 나 stdout "
    "리다이렉트가 Windows 에서 LF 를 CRLF 로 바꾼 것이다. 스크립트로 파일을 쓸 때는 newline 인자에 "
    "LF 를 주거나 바이트로 쓰고, 이미 CRLF 가 된 파일은 줄 끝의 CR 문자만 지워 LF 로 되돌린다."
)


def is_text(data: bytes) -> bool:
    """git 과 같은 판정. 처음 8000 바이트에 NUL 이 없으면 텍스트다."""
    return b"\0" not in data[:_TEXT_PROBE]


def _spots(text: str, pattern: re.Pattern[str]) -> Iterator[tuple[int, int, str]]:
    """`pattern` 이 맞은 문자마다 (줄, 열, 문자). 줄은 개행으로만 세고 열은 코드 포인트로 센다."""
    line, line_start, scanned = 1, 0, 0
    for match in pattern.finditer(text):
        start = match.start()
        newlines = text.count(_LF, scanned, start)
        if newlines:
            line += newlines
            line_start = text.rfind(_LF, scanned, start) + 1
        scanned = start
        yield line, start - line_start + 1, match.group()


def _invisible_name(character: str) -> str | None:
    """보이지 않는 공백·서식 문자면 그 이름, 아니면 None."""
    if unicodedata.category(character) in INVISIBLE_CATEGORIES:
        return unicodedata.name(character, "")
    return None


def _name(character: str) -> str | None:
    """잡는 문자면 그 이름. 어느 쪽을 잡을지는 정규식이 정한다."""
    return SEPARATORS.get(character) or _invisible_name(character)


def _invisible_class(text: str) -> str | None:
    """`text` 에 든 ASCII 밖의 Zs·Cf 문자만 담은 정규식 문자 클래스. 없으면 None.

    범주는 글자마다 물어야 한다. 한글이 많은 이 저장소에서 비 ASCII 글자마다 물으면 전체 훑기가
    줄 구분 문자만 보던 버전의 약 1.8배였고, 서로 다른 글자(`set`)에만 물으면 약 1.25배였다
    (`.scratch/harness/probes/line_separators_scan_time.py`, 2026-10-12).
    """
    found = sorted(
        each for each in set(text) if ord(each) > 0x7F and _invisible_name(each) is not None
    )
    return f"[{''.join(re.escape(each) for each in found)}]" if found else None


def _report(text: str, pattern: re.Pattern[str]) -> list[str]:
    """`pattern` 이 맞은 문자의 자리. 자리 순이다."""
    return [
        f"{line}:{column}: U+{ord(character):04X} {name}"
        for line, column, character in _spots(text, pattern)
        if (name := _name(character)) is not None
    ]


def separators_in(text: str) -> list[str]:
    """날것 줄 구분 문자와 홀로 선 CR 의 자리. 항목은 `"<줄>:<열>: U+XXXX <이름>"`."""
    return _report(text, _SEPARATOR)


def crlf_in(text: str) -> list[str]:
    """CRLF 줄 끝이 있으면 `"<줄>:<열>: CRLF 줄 끝 <수>줄"` 하나(첫 CRLF 의 CR 자리와 CRLF 의 수),
    없으면 빈 목록. 파일마다 한 줄이라 줄이 많은 파일도 출력이 길지 않다. 줄은 개행으로만, 열은
    코드 포인트로 센다. 뒤에 LF 가 없는 CR 은 `separators_in` 의 몫이다."""
    first = next(_spots(text, _CRLF_PATTERN), None)
    if first is None:
        return []
    line, column, _ = first
    return [f"{line}:{column}: {CRLF_LABEL} {text.count(_CRLF)}줄"]


def problems_in(data: bytes, suffix: str) -> list[str]:
    """확장자가 `suffix` 인 파일 하나의 어긋남. 텍스트가 아니면 비고, UTF-8 이 아니면 그 자체가
    어긋남이다. 보이지 않는 문자는 `SOURCE_SUFFIXES` 에서만 보고 줄 구분 문자와 자리 순으로
    섞는다. CRLF 줄 끝은 확장자와 상관없이 파일마다 한 줄이고 맨 끝에 붙는다."""
    if not is_text(data):
        return []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        # utf-8-sig 는 BOM 을 떼고 센 자리를 준다. 파일의 바이트 자리로 되돌린다.
        start = error.start + (len(codecs.BOM_UTF8) if data.startswith(codecs.BOM_UTF8) else 0)
        where = f"{error.reason}, 바이트 {start}"
        return [f"0:0: UTF-8 로 읽을 수 없어 판정하지 못했다 ({where})"]
    invisible = _invisible_class(text) if suffix in SOURCE_SUFFIXES else None
    if invisible is None:
        found = separators_in(text)
    else:
        found = _report(text, re.compile(f"{_SEPARATOR_PATTERN}|{invisible}"))
    return found + crlf_in(text)


def tracked_files(root: Path = ROOT) -> list[Path]:
    """인덱스의 일반 파일 중 작업 트리에 있는 것. 인자 없이 부를 때의 범위다. git 이 실패하거나
    `CALL_TIMEOUT` 초 안에 돌아오지 않으면 예외로 멈춘다."""
    listing = subprocess.run(
        ["git", "ls-files", "-s", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
        timeout=CALL_TIMEOUT,
    )
    files: list[Path] = []
    seen: set[str] = set()
    # UTF-8 이 아닌 경로 이름은 surrogateescape 로 살린다(열 때 읽을 수 없어 어긋남이 된다). 병합
    # 충돌 중에는 같은 경로가 단계 1·2·3 으로 세 번 나오므로 한 번만 훑는다.
    for entry in listing.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not entry:
            continue
        meta, name = entry.split("\t", 1)
        path = root / name
        if name not in seen and meta.split(" ", 1)[0] in _REGULAR_MODES and path.is_file():
            seen.add(name)
            files.append(path)
    return files


def _problems_of(path: Path) -> list[str]:
    try:
        data = path.read_bytes()
    except OSError as error:
        return [f"0:0: 파일을 읽을 수 없어 판정하지 못했다 ({error.strerror})"]
    return problems_in(data, path.suffix)


def main(paths: list[Path] | None = None, root: Path = ROOT) -> int:
    """`paths` 를(없으면 추적 파일 전부) 훑는다. 어긋남이 하나라도 있으면 1."""
    problems: list[str] = []
    found_separator = False
    found_crlf = False
    for path in paths if paths is not None else tracked_files(root):
        shown = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        found = _problems_of(path)
        found_separator = found_separator or any(" U+" in problem for problem in found)
        found_crlf = found_crlf or any(CRLF_LABEL in problem for problem in found)
        problems.extend(f"{shown}:{problem}" for problem in found)
    for problem in problems:
        print(problem)
    if found_separator:
        print(HINT)
    if found_crlf:
        print(CRLF_HINT)
    return 1 if problems else 0


if __name__ == "__main__":
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")
    raise SystemExit(main([Path(argument) for argument in sys.argv[1:]] or None))
