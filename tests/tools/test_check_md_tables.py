"""tools/check_md_tables.py. GFM 에서 표가 깨지는 자리를 잡는 검사(대기열 44).

검사는 cmark-gfm 의 블록 파싱을 옮긴 것이고, 표의 모양이 cmark-gfm 과 같은지는 차분 대조
`.scratch/harness/probes/md_tables_vs_cmark.py` 가 잰다. 여기서 고정하는 것은 적대 검증·차분
대조·셀프 리뷰가 찾은 자리들이다 — 칸 스캐너(역슬래시 바로 뒤의 `|` 는 몇 개든 내용),
컨테이너(목록 항목·인용·각주의 들여쓰기와 게으른 줄, 빠뜨린 행), HTML 블록과 펜스, 그리고 차분
대조가 찾은 다섯(cmark 의 버릇 셋 — 게으른 줄의 앞 공백이 칸이 된다, 표 시도에 실패한 문단은
다시 표를 열지 않는다, 목록 표식 뒤의 수직 탭은 여백이 아니다 — 과 GitHub 이 켠 기능 둘 — 각주
정의, 참조 정의만의 문단 아래 밑줄).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tools.check_md_tables import (
    CALL_TIMEOUT,
    ROOT,
    main,
    parse,
    problems_in,
    row_cells,
    tracked_markdown,
)

TABLE = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
CUT = "표 바로 아래에 빈 줄이 없다 — 여기서 표가 끊긴다"
# 비 ASCII 문자는 chr() 로 만든다. 편집 도구가 역슬래시-u 이스케이프를 날것으로 저장한다.
IDEOGRAPHIC_SPACE = chr(0x3000)
BOM = chr(0xFEFF)


def test_칸_수가_맞는_표는_통과한다() -> None:
    assert problems_in(TABLE) == []
    assert problems_in(TABLE + "\n산문\n") == []
    assert problems_in("| a | b |\n| --- | --- |\n| 1 | 2 |") == []


def test_행의_칸_수가_머리_행과_다르면_잡는다() -> None:
    problems = problems_in("| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n| 1 |\n")

    assert problems == ["3: 칸 3, 머리 행 2", "4: 칸 1, 머리 행 2"]


def test_코드_스팬_안의_파이프도_칸_구분이다() -> None:
    """GFM: 코드 스팬은 파이프를 보호하지 않는다. plan.md 를 두 번째로 깨뜨린 모양."""
    assert problems_in("| a | b |\n| --- | --- |\n| 1 | `x|y` |\n") == ["3: 칸 3, 머리 행 2"]


def test_역슬래시_바로_뒤의_파이프는_역슬래시가_몇_개든_내용이다() -> None:
    r"""칸 스캐너는 `(escaped_char|[^|\r\n])+` 의 최장 일치다. `\\|` 의 파이프도 칸 안이다.

    CommonMark 의 "역슬래시가 역슬래시를 이스케이프한다" 는 인라인 단계 규칙이라 칸 나누기에
    닿지 않는다(적대 검증이 cmark-gfm 과 GitHub 렌더로 쟀다).
    """
    for escaped in ("x\\|y", "x\\\\|y", "x\\\\\\|y", "`x\\|y`"):
        assert problems_in(f"| a | b |\n| --- | --- |\n| 1 | {escaped} |\n") == []


@pytest.mark.parametrize(
    ("line", "cells"),
    [
        ("| a | b |", 2),
        ("a | b", 2),
        ("| a | b", 2),
        ("a | b |", 2),
        ("| a | |", 2),
        ("||", 1),
        ("| |", 1),
        ("|", 0),
        ("  | a |", 2),
        (f"{IDEOGRAPHIC_SPACE}| a |", 2),
    ],
)
def test_칸_수는_cmark_gfm_의_row_from_string_과_같다(line: str, cells: int) -> None:
    """앞뒤 파이프는 세지 않는다. 앞 공백·전각 공백은 칸이다(게으른 줄이 머리 행일 때 생긴다)."""
    assert row_cells(line) == cells


def test_파이프_없는_줄은_칸_하나짜리_행이다() -> None:
    """GFM 은 빈 줄이 오기 전까지 파이프 없는 줄도 행으로 읽는다. 칸 안의 줄바꿈이 깨지는 자리."""
    assert problems_in(TABLE + "이어지는 산문\n") == ["4: 칸 1, 머리 행 2"]
    assert problems_in(TABLE + IDEOGRAPHIC_SPACE + "\n") == ["4: 칸 1, 머리 행 2"]


def test_표_아래에_빈_줄_없이_다른_블록이_오면_끊긴_자리를_잡는다() -> None:
    """목록·제목·인용·펜스·HTML·들여쓴 코드, 그리고 칸이 없는 `|` 가 표를 끊는다(MD058)."""
    cutters = ("- 목록\n| 3 | 4 |", "## 제목", "> 인용", "```\ncode\n```", "<div>", "|", "    x")
    for after in cutters:
        assert problems_in(TABLE + after + "\n") == [f"4: {CUT}"], after


def test_바깥_컨테이너가_끝나서_닫힌_표는_끊긴_것이_아니다() -> None:
    """다음 목록 항목이나 인용 밖의 문단은 표를 뜻한 줄이 아니다."""
    assert problems_in("- | a |\n  | --- |\n- 다음 항목\n") == []
    assert problems_in("> | a |\n> | --- |\n인용 밖\n") == []
    assert problems_in("> | a |\n> | --- |\n>\n> 인용 안\n") == []


def test_컨테이너_밖으로_나온_줄이_칸을_나누면_빠뜨린_행이다() -> None:
    """`>` 나 목록 들여쓰기를 빠뜨린 행은 cmark 가 표 밖 문단으로 떨어뜨린다(셀프 리뷰)."""
    quoted = "> | a | b |\n> | --- | --- |\n> | 1 | 2 |\n| 3 | 4 |\n"
    listed = "- | a | b |\n  | --- | --- |\n| 3 | 4 |\n"

    assert problems_in(quoted) == [f"4: {CUT}"]
    assert problems_in(listed) == [f"3: {CUT}"]


def test_목록_표식_뒤의_수직_탭은_여백이_아니다() -> None:
    """`-\\v| a |` 는 목록 항목이 아니라 칸 둘의 머리 행이다(차분 대조가 찾은 cmark 의 동작)."""
    vertical_tab = chr(0x0B)

    assert problems_in(f"-{vertical_tab}| a |\n| --- | --- |\n| 1 |\n") == ["3: 칸 1, 머리 행 2"]
    assert problems_in(f"-{chr(0x0C)}| a |\n| --- | --- |\n| 1 |\n") == ["3: 칸 1, 머리 행 2"]


def test_인라인_HTML_로_시작하는_줄은_행이다() -> None:
    """`<` 로 시작해도 HTML 블록의 시작 일곱에 들지 않으면 행이다(GitHub 은 행으로 렌더한다)."""
    assert problems_in(TABLE + "<b>x</b> | 2\n< 3 | 2\n<kbd>Ctrl</kbd> | key\n") == []


def test_HTML_블록과_주석_안의_표는_보지_않는다() -> None:
    broken = "| a | b |\n| --- | --- |\n| 1 |\n"

    assert problems_in("<!--\n" + broken + "-->\n") == []
    assert problems_in("<div>\n" + broken) == []
    assert problems_in("<!-- 한 줄 -->\n\n" + broken) == ["5: 칸 1, 머리 행 2"]


def test_펜스_안의_표는_보지_않고_펜스_뒤는_다시_본다() -> None:
    broken = "| a | b |\n| --- | --- |\n| 1 |\n"

    assert problems_in("```md\n" + broken + "```\n") == []
    assert problems_in("~~~\n" + broken + "~~~\n") == []
    indented = "".join(f"  {line}\n" for line in broken.splitlines())
    assert problems_in("- 목록 안\n  ```\n" + indented + "  ```\n") == []
    assert problems_in("```\ncode\n```\n\n" + broken) == ["7: 칸 1, 머리 행 2"]


def test_목록_항목_안의_펜스는_들여쓰기가_모자란_줄에서_닫힌다() -> None:
    """항목의 들여쓰기 밖 줄은 펜스 밖이다. cmark 도 그 표를 깨진 채 렌더한다(5행을 채운다)."""
    broken = "| a | b |\n| --- | --- |\n| 1 |\n"

    assert problems_in("- 목록 안\n  ```\n" + broken + "  ```\n") == [
        "5: 칸 1, 머리 행 2",
        f"6: {CUT}",
    ]


def test_네_칸_들여쓴_펜스_줄은_펜스가_아니다() -> None:
    """닫는 펜스는 세 칸까지만 들여쓴다. 맨 위의 네 칸 ``` 은 들여쓴 코드다."""
    broken = "| a | b |\n| --- | --- |\n| 1 |\n"

    assert problems_in("```\n" + broken + "    ```\n") == []
    assert problems_in("    ```\n\n" + broken) == ["5: 칸 1, 머리 행 2"]


def test_머리_행에_파이프가_없어도_구분_행과_칸_수가_같으면_표다() -> None:
    assert problems_in("Header\n| --- |\n| 1 | 2 |\n") == ["3: 칸 2, 머리 행 1"]


def test_목록_항목과_각주_안의_표도_본다() -> None:
    assert problems_in("- | a | b |\n  | --- | --- |\n  | 1 |\n") == ["3: 칸 1, 머리 행 2"]
    nested = "- 항목\n\n    | a | b |\n    | --- | --- |\n    | 1 |\n"
    assert problems_in(nested) == ["5: 칸 1, 머리 행 2"]
    footnote = "[^1]: 글\n\n    | a | b |\n    | --- | --- |\n    | 1 |\n"
    assert problems_in(footnote) == ["5: 칸 1, 머리 행 2"]


def test_표처럼_보이지만_표가_되지_않는_자리를_잡는다() -> None:
    lazy = "앞 목록·인용 문단의 게으른 연속이다 — 표로 읽히지 않는다"
    assert problems_in("| a | b |\n| --- |\n") == [
        "1: 머리 행 2칸, 구분 행 1칸 — 표로 읽히지 않는다"
    ]
    assert problems_in("- 항목\n| a | b |\n| --- | --- |\n") == [f"2: {lazy}"]
    assert problems_in("> | a | b |\n| --- | --- |\n") == [f"1: {lazy}"]
    assert problems_in("| a | b |\n    | --- | --- |\n") == [
        "1: 구분 행이 네 칸 이상 들여써졌다 — 표로 읽히지 않는다"
    ]
    assert problems_in(f"| a | b |\n| ---{IDEOGRAPHIC_SPACE}| --- |\n") == [
        "1: 구분 행에 ASCII 가 아닌 공백이 있다 — 표로 읽히지 않는다"
    ]
    assert problems_in(f"{IDEOGRAPHIC_SPACE}| a | b |\n| --- | --- |\n") == [
        "1: 머리 행 3칸, 구분 행 2칸 — 표로 읽히지 않는다"
    ]


def test_게으른_머리_행의_앞_공백은_빈_칸_하나다() -> None:
    """cmark 는 게으른 줄을 앞 공백째 문단에 넣는다. `  | a |` 는 칸 둘이라 표가 된다."""
    assert problems_in("> 글\n  | a |\n> | --- | --- |\n") == []
    assert problems_in("> 글\n| a |\n> | --- | --- |\n") == [
        "2: 머리 행 1칸, 구분 행 2칸 — 표로 읽히지 않는다"
    ]


def test_표_시도에_실패한_문단은_다시_표를_열지_않는다() -> None:
    """cmark-gfm 은 구분 행 모양의 줄이 칸 수로 실패한 문단에 표시를 달고 다시 시도하지 않는다."""
    problems = problems_in("x | y\n| --- |\n| a |\n| --- |\n")

    assert problems[0] == "1: 머리 행 2칸, 구분 행 1칸 — 표로 읽히지 않는다"
    assert problems[1].startswith("3: 같은 문단에서 앞 구분 행이 표를 열지 못해")
    assert parse("x | y\n| --- |\n\n| a |\n| --- |\n")[0] != []


def test_빈_줄_없이_붙은_표_둘의_둘째_구분_행을_잡는다() -> None:
    problems = problems_in("| a |\n| --- |\n| b |\n| --- |\n")

    assert problems == ["4: 표 안의 구분 행 — 빈 줄 없이 붙은 표 둘이 하나가 됐다"]


def test_제목_밑줄은_표가_아니고_참조_정의만의_문단_아래_밑줄은_글이다() -> None:
    assert parse("| a | b |\n---\n") == ([], [])
    tables, _ = parse("[a]: /url\n---\n| --- |\n")
    assert [table.delimiter_line for table in tables] == [3]


def test_BOM_과_CRLF_와_탭을_GFM_처럼_읽는다() -> None:
    assert problems_in(BOM + TABLE) == []
    assert problems_in(TABLE.replace("\n", "\r\n") + "| 1 |\r\n") == ["4: 칸 1, 머리 행 2"]
    assert problems_in(TABLE + "\t| 3 | 4 |\n") == [f"4: {CUT}"]


def _seconds(text: str) -> float:
    started = time.perf_counter()
    problems_in(text)
    return time.perf_counter() - started


# 옛 코드는 아래 입력마다 2~4초가 걸렸다(PR #96 대체 리뷰가 쟀다). 지금은 밀리초라 1초는 넉넉하다.
LIMIT_SECONDS = 1.0


def test_대괄호로_시작하는_긴_줄_아래의_밑줄이_선형이다() -> None:
    """참조 정의 판정(_REFERENCE)이 `]` 없는 긴 라벨에서 되감지 않는다."""
    assert _seconds("[" + "a" * 16000 + "\n===\n") < LIMIT_SECONDS


def test_구분_행_모양_뒤의_긴_공백이_선형이다() -> None:
    """구분 행 판정(_TABLE_START)이 끝 공백을 두 반복으로 나눠 갖지 않는다. 탭은 네 칸으로 편다."""
    assert _seconds("글\n--" + "\t" * 6000 + "x\n") < LIMIT_SECONDS


def test_한_줄에_겹친_목록_표식이_선형이다() -> None:
    """수평선 판정이 끊긴 자리를 기억한다(cmark 의 thematic_break_kill_pos)."""
    assert _seconds("- " * 8000 + "a\n") < LIMIT_SECONDS


def test_깊은_중첩_뒤의_들여쓴_줄이_선형이다() -> None:
    """첫 비공백 자리를 한 줄 안에서 캐시한다(cmark 의 first_nonspace)."""
    text = "- " * 2000 + "a\n" + (" " * 4000 + "x\n") * 10

    assert _seconds(text) < LIMIT_SECONDS


def test_순서_목록의_번호는_ASCII_숫자만이다() -> None:
    """전각 숫자 `１.` 은 목록 표식이 아니라 머리 행의 글이다."""
    text = f"{chr(0xFF11)}. | a |\n| --- | --- |\n"

    assert problems_in(text) == []
    assert len(parse(text)[0]) == 1


def test_HTML_태그_이름의_대소문자_무시는_ASCII_만이다() -> None:
    """`<ſcript>`(U+017F) 는 HTML 블록이 아니라 칸 하나짜리 행이다."""
    line = f"<{chr(0x017F)}cript>"

    assert problems_in(TABLE + line + "\n") == ["4: 칸 1, 머리 행 2"]


def test_이_저장소의_표는_전부_GFM_에서_깨지지_않는다() -> None:
    assert main() == 0


def test_깨진_표가_있는_파일이_섞이면_실패한다(tmp_path: Path) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text(TABLE, encoding="utf-8", newline="\n")
    broken = tmp_path / "broken.md"
    broken.write_text("| a | b |\n| --- | --- |\n| 1 |\n", encoding="utf-8", newline="\n")

    assert main([clean]) == 0
    assert main([clean, broken]) == 1


def test_읽을_수_없는_파일은_트레이스백이_아니라_어긋남이고_나머지는_판정한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cp949 = tmp_path / "cp949.md"
    cp949.write_bytes("| 한 | 글 |".encode("cp949"))
    broken = tmp_path / "broken.md"
    broken.write_text("| a | b |\n| --- | --- |\n| 1 |\n", encoding="utf-8", newline="\n")

    assert main([tmp_path / "없다.md", cp949, broken], root=tmp_path) == 1

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("없다.md:0: 파일을 읽을 수 없어")
    assert lines[1].startswith("cp949.md:0: UTF-8 로 읽을 수 없어")
    assert lines[2] == "broken.md:3: 칸 1, 머리 행 2"


def _git(repo: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", *arguments], cwd=repo, capture_output=True, text=True, check=True
    )
    return process.stdout.strip()


def test_인자_없는_범위는_훅과_같은_확장자이고_지운_파일은_건너뛴다(tmp_path: Path) -> None:
    """pre-commit 은 identify 가 markdown 으로 본 파일(`.md`·`.markdown`, 대소문자 무관)을
    넘긴다. 인자 없는 범위도 같아야 한다."""
    _git(tmp_path, "init", "-q")
    for name in ("a.md", "b.MARKDOWN", "c.txt", "gone.md"):
        (tmp_path / name).write_text(TABLE, encoding="utf-8", newline="\n")
    _git(tmp_path, "add", ".")
    (tmp_path / "gone.md").unlink()

    assert tracked_markdown(tmp_path) == [tmp_path / "a.md", tmp_path / "b.MARKDOWN"]
    assert main(root=tmp_path) == 0


def test_git_목록이_시간을_넘기면_예외로_멈춘다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """빈 범위로 읽어 초록으로 지나가지 않는다. `check=True` 의 실패와 같은 갈래다(대기열 342)."""
    seen: list[object] = []

    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, 1)

    monkeypatch.setattr(subprocess, "run", stuck)

    with pytest.raises(subprocess.TimeoutExpired):
        tracked_markdown(tmp_path)
    assert seen == [CALL_TIMEOUT]


def test_CLI_진입점이_인자로_받은_파일의_깨진_표를_출력한다(tmp_path: Path) -> None:
    """pre-commit 이 부르는 진입점 그대로 — 파일 경로를 인자로 받는다(tests.md)."""
    broken = tmp_path / "broken.md"
    broken.write_text("| a | b |\n| --- | --- |\n| 1 |\n", encoding="utf-8", newline="\n")

    process = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_md_tables.py"), str(broken)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )

    assert process.returncode == 1
    assert "broken.md:3: 칸 1, 머리 행 2" in process.stdout
