"""tools/check_adr_pointers.py. ADR 본문의 `(바뀜: ...)` 포인터를 이력 제목과 대조한다(대기열 97).

포인터 규약은 `.claude/rules/adr.md`다. 여기서 고정하는 것은 프로브(PR #124)가 겪은 자리들이다 —
번호 뒤 공백이 빠진 모양을 맞는 것으로 넘긴 정규식(CodeRabbit 1회차), `## 이력` 밖의 `###` 줄을
이력 제목으로 모은 것(CodeRabbit 2회차), 첫 판이 세지 않은 `(바뀜: ADR NNNN)` 모양. 그리고 옮기는
판의 셀프 리뷰가 찾은 셋 — 번호가 겹친 ADR 하나를 판정하지 않던 것, ADR이 0개여도 초록이던 것,
코드 스팬으로 적은 포인터 예시와 펜스 안의 `## 이력`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from tools.check_adr_pointers import ROOT, history_titles, main, problems_in

OWN = """# 결정

본문 문장이다. {pointer}

## 이력

### 2026-01-02 있는 제목

이력 본문.
"""
OTHER_TITLES = {"0016": {"2026-09-25 다른 ADR의 제목"}}
MALFORMED = "3: 모양이 맞지 않는 `(바뀜:`가 있다"


def _어긋남(pointer: str) -> list[str]:
    return problems_in(OWN.format(pointer=pointer), OTHER_TITLES.get)


def test_자기_이력_제목을_가리키는_포인터는_통과한다() -> None:
    assert _어긋남('(바뀜: 이력 2026-01-02 "있는 제목")') == []


def test_다른_ADR의_이력과_본문을_가리키는_포인터는_통과한다() -> None:
    assert _어긋남('(바뀜: ADR 0016 이력 2026-09-25 "다른 ADR의 제목") (바뀜: ADR 0016)') == []


def test_제목이_글자_그대로_다르면_잡는다() -> None:
    assert _어긋남('(바뀜: 이력 2026-01-02 "있는 제목이다")') == [
        '3: (바뀜: 이력 2026-01-02 "있는 제목이다") — 가리킨 이력 제목이 없다'
    ]


def test_날짜가_다르면_잡는다() -> None:
    assert _어긋남('(바뀜: 이력 2026-01-03 "있는 제목")') == [
        '3: (바뀜: 이력 2026-01-03 "있는 제목") — 가리킨 이력 제목이 없다'
    ]


def test_다른_ADR의_제목이_다르면_잡는다() -> None:
    assert _어긋남('(바뀜: ADR 0016 이력 2026-09-25 "없는 제목")') == [
        '3: (바뀜: ADR 0016 이력 2026-09-25 "없는 제목") — 가리킨 이력 제목이 없다'
    ]


def test_없는_ADR을_가리키면_잡는다() -> None:
    assert _어긋남("(바뀜: ADR 0098)") == ["3: (바뀜: ADR 0098) — ADR 0098이 없다"]


def test_모양이_틀린_포인터를_잡는다() -> None:
    malformed = [
        '(바뀜: ADR 0016이력 2026-09-25 "다른 ADR의 제목")',
        "(바뀜: ADR 0016 )",
        "(바뀜: ADR 16)",
        "(바뀜: )",
        '(바뀜:이력 2026-01-02 "있는 제목")',
        '(바뀜: 이력  2026-01-02 "있는 제목")',
        '(바뀜: 이력 2026-1-2 "있는 제목")',
        "(바뀜: 이력 2026-01-02 있는 제목)",
    ]
    for pointer in malformed:
        assert _어긋남(pointer) == [MALFORMED], pointer


def test_한_줄의_모양_틀림은_여럿이어도_한_번_알린다() -> None:
    assert _어긋남("(바뀜: ) (바뀜: ADR 16)") == [MALFORMED]


def test_한_줄의_포인터를_모두_센다() -> None:
    pointer = '(바뀜: 이력 2026-01-02 "있는 제목") (바뀜: ADR 0098)'
    assert _어긋남(pointer) == ["3: (바뀜: ADR 0098) — ADR 0098이 없다"]


def test_코드_스팬으로_적은_포인터_예시는_포인터가_아니다() -> None:
    assert _어긋남('모양은 `(바뀜: 이력 YYYY-MM-DD "제목")`이고 예는 `(바뀜: ADR 0098)`이다.') == []


def test_펜스_안의_줄은_포인터도_절_제목도_아니고_펜스_뒤는_다시_본다() -> None:
    """더 짧은 펜스 줄은 펜스를 닫지 못한다. 그 안의 `## 이력` 은 절을 바꾸지 않는다."""
    text = (
        "# 결정\n\n````\n## 이력\n```\n(바뀜: ADR 0098)\n````\n\n"
        '본문. (바뀜: 이력 2026-01-02 "있는 제목") (바뀜: ADR 0097)\n\n'
        "## 이력\n\n### 2026-01-02 있는 제목\n"
    )
    assert problems_in(text, OTHER_TITLES.get) == ["9: (바뀜: ADR 0097) — ADR 0097이 없다"]


def test_이력_절_안의_포인터는_잡는다() -> None:
    text = OWN.format(pointer="") + '\n(바뀜: 이력 2026-01-02 "있는 제목")\n'
    assert problems_in(text, OTHER_TITLES.get) == [
        '11: (바뀜: 이력 2026-01-02 "있는 제목") — 이력 절 안에 있다'
    ]


def test_이력_절_밖의_같은_모양_줄은_이력_제목이_아니다() -> None:
    text = (
        '# 결정\n\n본문. (바뀜: 이력 2026-01-01 "본문의 제목")\n\n'
        "## Consequences\n\n### 2026-01-01 본문의 제목\n\n## 이력\n\n### 2026-01-02 있는 제목\n"
    )
    assert history_titles(text) == {"2026-01-02 있는 제목"}
    assert problems_in(text, OTHER_TITLES.get) == [
        '3: (바뀜: 이력 2026-01-01 "본문의 제목") — 가리킨 이력 제목이 없다'
    ]


def test_이력_절은_제목이_정확히_이력인_절이고_다음_절에서_끝난다() -> None:
    """0006 의 `## 개정 이력` 은 이력 절이 아니다. `## 이력` 뒤에 `##` 절이 오면 다시 본문이다."""
    text = (
        "# 결정\n\n## 개정 이력\n\n"
        '- 2.2.0. (바뀜: 이력 2026-01-02 "있는 제목")\n\n'
        "## 이력\n\n### 2026-01-02 있는 제목\n\n## 덧붙임\n\n"
        '- 문장. (바뀜: 이력 2026-01-02 "있는 제목")\n'
    )
    assert problems_in(text, OTHER_TITLES.get) == []


def test_어긋난_ADR이_있으면_실패하고_파일과_줄을_찍는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    own = OWN.format(pointer='(바뀜: 이력 2026-01-02 "있는 제목")')
    (tmp_path / "0001-a.md").write_text(own, encoding="utf-8")
    (tmp_path / "0002-b.md").write_text(OWN.format(pointer="(바뀜: ADR 0001)"), encoding="utf-8")
    assert main(tmp_path) == 0
    assert capsys.readouterr().out == ""

    (tmp_path / "0003-c.md").write_text(OWN.format(pointer="(바뀜: ADR 0009)"), encoding="utf-8")
    assert main(tmp_path) == 1
    assert capsys.readouterr().out == "0003-c.md:3: (바뀜: ADR 0009) — ADR 0009이 없다\n"


def test_번호가_겹친_ADR은_둘_다_판정하고_겹침을_알린다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "0016-a.md").write_text(OWN.format(pointer="(바뀜: ADR 0099)"), encoding="utf-8")
    second = OWN.format(pointer="").replace("2026-01-02 있는 제목", "2026-03-03 둘째 제목")
    (tmp_path / "0016-b.md").write_text(second, encoding="utf-8")
    cites_first = '(바뀜: ADR 0016 이력 2026-01-02 "있는 제목")'
    (tmp_path / "0017-c.md").write_text(OWN.format(pointer=cites_first), encoding="utf-8")
    assert main(tmp_path) == 1
    assert capsys.readouterr().out.splitlines() == [
        "0016-a.md:0: ADR 번호 0016이 다른 파일과 겹친다",
        "0016-a.md:3: (바뀜: ADR 0099) — ADR 0099이 없다",
        "0016-b.md:0: ADR 번호 0016이 다른 파일과 겹친다",
    ]


def test_ADR이_하나도_없으면_디렉터리를_잘못_가리킨_것이라_실패한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(tmp_path / "없다") == 1
    assert "ADR 파일이 하나도 없다" in capsys.readouterr().out


def test_CLI가_인자로_받은_디렉터리를_판정하고_어긋남을_찍는다(tmp_path: Path) -> None:
    (tmp_path / "0001-a.md").write_text(OWN.format(pointer="(바뀜: ADR 0009)"), encoding="utf-8")
    process = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_adr_pointers.py"), str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    assert process.returncode == 1
    assert "0001-a.md:3: (바뀜: ADR 0009) — ADR 0009이 없다" in process.stdout


def test_이_저장소의_ADR_포인터는_전부_이력_제목과_맞는다() -> None:
    assert main() == 0
