"""tools/hook_journal_retro.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

발동 조건은 대기열 28 의 것을 좁힌 것이다 — Write 의 content 나 Edit 의 new_string 이 `## 다음` 을
담을 때. 경로만 보던 동안 인용 하나를 고친 Edit 마다 계기가 울렸다(대기열 28 의 5회차와 일지 둘).
그 뒤 대기열 62·74 로 더 좁혔다. 제목은 줄 머리의 것만이고, 절이 비었거나 자리 표시뿐이거나 Edit 가
앞뒤에 같은 절을 옮겼을 뿐이거나 일지에 회고 절이 이미 있으면 단계를 닫은 것이 아니다.

새 일지 파일의 이름 꼴(ADR 0045 결정 7)은 파일 이름만 본다. 자식 프로세스를 띄우지 않으므로 순수
함수 시험과, 실제 훅 입력 표(`tools/hook_payloads.toml`)를 러너로 돌리는 확인이 전부다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tools.hook_journal_retro import (
    CLOSING_HEADING,
    NAME_LEAD,
    context_for,
    created_journal,
    is_journal,
    name_context,
    read_journal,
    section_body,
)

JOURNAL = "C:\\project\\agent\\docs\\journal\\2026-09-21-first-slice.md"
NEW = "C:\\x\\docs\\journal\\2026-11-07-0930-hooks.md"


def test_다음_절을_담은_Write_는_retro_계기_문장을_돌려준다() -> None:
    context = context_for("Write", JOURNAL, "# 일지\n\n## 다음\n\n- web-admin 설계")

    assert context is not None
    assert "retro" in context


def test_다음_절이_없는_Write_는_계기가_아니다() -> None:
    """세션 첫머리에 일지를 새로 쓰는 Write 는 단계를 닫는 것이 아니다(PR #91 리뷰)."""
    assert context_for("Write", JOURNAL, "# 일지\n\n## 감사\n") is None
    assert context_for("Write", JOURNAL, None) is None


def test_다음_절을_담은_Edit_도_계기다() -> None:
    assert context_for("Edit", JOURNAL, "## 다음\n\n- web-admin 설계") is not None


def test_다음_절을_건드리지_않은_Edit_는_계기가_아니다() -> None:
    """인용 하나를 원문으로 고친 Edit 에 계기가 울리던 자리다(대기열 28, 5회차)."""
    assert context_for("Edit", JOURNAL, '"화면이 없어도 시스템이 돌고"') is None
    assert context_for("Edit", JOURNAL, None) is None


def test_산문의_코드_스팬_속_다음_은_제목이_아니다() -> None:
    """일지 2026-10-01-02 의 한 줄이 부분 문자열 검사에 걸렸다(대기열 74)."""
    prose = (
        "# 일지\n\n## 잰 것\n\n- 임시 일지에\n"
        "  `## 다음`을 Write로, 이어서 Edit로 쓰자 둘 다 문구가 이 세션에 닿았다\n"
    )

    assert context_for("Write", JOURNAL, prose) is None
    assert context_for("Edit", JOURNAL, "`## 다음`을 Write로 쓰자") is None


def test_제목_줄_끝의_공백과_CR_은_제목이다() -> None:
    assert context_for("Write", JOURNAL, "# 일지\n\n## 다음  \n\n- web-admin 설계") is not None
    assert context_for("Write", JOURNAL, "# 일지\r\n\r\n## 다음\r\n\r\n- web-admin\r\n") is not None


@pytest.mark.parametrize(
    "본문",
    [
        pytest.param("# 일지\n\n## 다음\n", id="제목만"),
        pytest.param("# 일지\n\n## 다음\n\n\n", id="빈_줄뿐"),
        pytest.param("# 일지\n\n## 다음\n\n(회고 뒤에 채운다)\n", id="괄호_한_줄"),
        pytest.param("# 일지\n\n## 다음\n\n- (회고 뒤에 채운다)\n", id="불릿_괄호"),
        pytest.param("# 일지\n\n## 다음\n\n（회고 뒤에）\n", id="전각_괄호"),
    ],
)
def test_비었거나_자리_표시뿐인_다음_절은_계기가_아니다(본문: str) -> None:
    """자리 표시로 절을 먼저 두자 단계를 닫은 것으로 보고 retro 를 요구했다(대기열 62). 원래의 자리
    표시 문구는 남지 않아 여기 문구는 행의 "괄호 한 줄짜리" 를 따라 지었다."""
    assert context_for("Write", JOURNAL, 본문) is None


@pytest.mark.parametrize(
    "줄",
    [
        pytest.param("(04 가 먼저다) 05 는 03 과 04 를 기다린다", id="괄호로_닫히지_않는다"),
        pytest.param("(web-admin) 04 가 다음이다 (05~08 의 임계 경로)", id="괄호_둘"),
    ],
)
def test_괄호_한_쌍으로_감싼_한_줄이_아니면_내용이다(줄: str) -> None:
    assert context_for("Write", JOURNAL, f"# 일지\n\n## 다음\n\n{줄}\n") is not None


@pytest.mark.parametrize("줄", ["TBD", "…", "1. (채운다)"])
def test_못_보는_것_괄호_한_쌍_밖의_자리_표시는_내용으로_본다(줄: str) -> None:
    assert context_for("Write", JOURNAL, f"# 일지\n\n## 다음\n\n{줄}\n") is not None


def test_못_보는_것_펜스를_가리지_않는다() -> None:
    """펜스 안의 `## 다음` 은 제목으로, 절 안 펜스의 `# ` 줄은 절의 끝으로 본다."""
    in_fence = "# 일지\n\n```md\n## 다음\n\n- 예시\n```\n"
    comment_in_fence = "## 다음\n\n```sh\n# 주석\n- a\n```\n"

    assert section_body(in_fence, CLOSING_HEADING) == "- 예시\n```"
    assert section_body(comment_in_fence, CLOSING_HEADING) == "```sh"


def test_다음_절은_뒤의_제목에서_끝난다() -> None:
    """뒤 절의 줄은 이 절의 내용이 아니다. 하위 제목(`###`)은 절 안이다."""
    assert context_for("Write", JOURNAL, "## 다음\n\n(채운다)\n\n## 부록\n\n- 표") is None
    assert context_for("Write", JOURNAL, "## 다음\n\n(채운다)\n\n# 끝\n\n- 표") is None
    assert context_for("Write", JOURNAL, "## 다음\n\n### 남은 것\n\n- 04") is not None


def test_자리_표시를_채운_Edit_는_계기다() -> None:
    assert (
        context_for(
            "Edit",
            JOURNAL,
            "## 다음\n\n- web-admin의 04가 다음이다.",
            "## 다음\n\n(회고 뒤에 채운다)",
        )
        is not None
    )


def test_다음_절을_그대로_옮긴_Edit_는_계기가_아니다() -> None:
    """회고를 "다음" 앞에 적어 넣는 Edit 는 흔히 그 절을 닻으로 old_string 에 담고 new_string 에
    그대로 옮긴다. 절은 그대로라 단계를 다시 닫은 것이 아니다(대기열 62, 둘째 울림). 끝 줄바꿈의
    차이는 같은 절이다."""
    old = "## 다음\n\n- web-admin의 04가 다음이다.\n"
    new = "## 회고\n\n- 62(새로)\n\n## 다음\n\n- web-admin의 04가 다음이다."

    assert context_for("Edit", JOURNAL, new, old) is None


def test_다음_절을_고친_Edit_는_계기다() -> None:
    old = "## 다음\n\n- web-admin의 04가 다음이다."
    new = "## 다음\n\n- web-admin의 05가 다음이다."

    assert context_for("Edit", JOURNAL, new, old) is not None


@pytest.mark.parametrize(
    "제목",
    ["## 회고", "## 회고 (2026-09-21, 슬라이스를 닫은 뒤)", "## 회고\r"],
)
def test_일지에_회고_절이_이미_있으면_계기가_아니다(제목: str) -> None:
    """retro 를 먼저 돌고 "다음" 을 적은 편집에도 울렸다(일지 2026-09-30-02, 2026-10-01-03). 회고
    절은 retro 가 돈 흔적이다(사용자 결정 2026-10-01)."""
    closing = "## 다음\n\n- web-admin의 04가 다음이다.\n"
    journal = f"# 일지\n\n{제목}\n\n- 62(새로)\n\n{closing}"

    assert context_for("Edit", JOURNAL, closing, None, journal) is None
    assert context_for("Write", JOURNAL, journal, None, journal) is None


def test_회고_절이_여럿이면_하나라도_쓴_것이_있으면_계기가_아니다() -> None:
    """첫 절이 자리 표시뿐이고 뒤의 날짜 붙은 절에 내용이 있는 일지(PR #113 CodeRabbit)."""
    journal = (
        "# 일지\n\n## 회고\n\n(retro 뒤에)\n\n## 한 것\n\n- 04\n\n"
        "## 회고 (2026-10-01, 단계를 닫은 뒤)\n\n- 62(새로)\n\n## 다음\n\n- 05\n"
    )

    assert context_for("Edit", JOURNAL, "## 다음\n\n- 05", None, journal) is None


@pytest.mark.parametrize(
    "일지",
    [
        pytest.param("# 일지\n\n## 회고\n\n## 다음\n\n- 04\n", id="빈_회고_절"),
        pytest.param("# 일지\n\n## 회고\n\n(retro 뒤에)\n\n## 다음\n\n- 04\n", id="자리_표시"),
        pytest.param(
            "# 일지\n\n## 한 것\n\n- `## 회고` 는 아직이다\n\n## 다음\n\n- 04\n", id="코드_스팬"
        ),
        pytest.param("# 일지\n\n## 회고록\n\n- 읽은 것\n\n## 다음\n\n- 04\n", id="다른_제목"),
    ],
)
def test_쓴_회고_절이_없는_일지는_계기다(일지: str) -> None:
    assert context_for("Edit", JOURNAL, "## 다음\n\n- 04", None, 일지) is not None


def test_일지를_읽지_못하면_None_이다(tmp_path: Path) -> None:
    """None 이면 회고 절이 없는 것으로 판정한다(위의 일지 없는 사례들)."""
    journal = tmp_path / "docs" / "journal" / "2026-10-01-04-x.md"
    journal.parent.mkdir(parents=True)

    assert read_journal(str(journal)) is None
    journal.write_bytes(b"## \xff\n")
    assert read_journal(str(journal)) is None
    journal.write_text("## 회고\n\n- 62\n", encoding="utf-8")
    assert read_journal(str(journal)) == "## 회고\n\n- 62\n"


def test_일지가_아닌_파일은_도구가_무엇이든_None이다() -> None:
    assert context_for("Write", "docs/adr/0008-x.md", None) is None
    assert context_for("Edit", "docs/adr/0008-x.md", "## 다음") is None
    assert not is_journal("docs/journal/notes.txt")
    assert not is_journal("journal/2026-09-21.md")


@pytest.mark.parametrize(
    "이름",
    ["2026-11-07-0930-hooks.md", "2026-11-07-0000-a.md", "2026-12-31-2359-year-end.md"],
)
def test_시각_꼴_이름이면_알리지_않는다(이름: str) -> None:
    assert name_context(f"C:\\x\\docs\\journal\\{이름}") is None


@pytest.mark.parametrize(
    "이름",
    [
        "2026-11-07-03-hooks.md",
        "2026-11-07-hooks.md",
        "2026-11-07-093-hooks.md",
        "2026-11-07-09300-hooks.md",
        "20261107-0930-hooks.md",
        "2026-11-07-0930.md",
        "notes.md",
    ],
)
def test_시각_꼴이_아닌_이름은_짓는_명령과_원천을_알린다(이름: str) -> None:
    context = name_context(f"C:\\x\\docs\\journal\\{이름}")

    assert context is not None
    assert context.startswith(NAME_LEAD)
    assert f"`{이름}`" in context
    assert "date +%Y-%m-%d-%H%M" in context
    assert "Get-Date -Format yyyy-MM-dd-HHmm" in context
    assert "docs/constitution/operations.md" in context
    assert "mv <옛> <새>" in context
    assert "인용" in context


def test_슬래시_경로의_이름도_파일_이름만_본다() -> None:
    assert name_context("docs/journal/2026-11-07-0930-hooks.md") is None
    assert name_context("docs/journal/2026-11-07-03-hooks.md") is not None


def test_새_일지를_만든_Write_만_이름_꼴을_본다() -> None:
    """Write 의 결과 `type` 이 새 파일과 덮어쓰기를 가른다. Edit 의 결과에는 그 값이 없다(2026-10-16
    claude 2.1.300, `.scratch/harness/probes/journal_number_hook/run.py` 의 A)."""
    assert created_journal("Write", NEW, {"type": "create", "originalFile": None})
    assert not created_journal("Write", NEW, {"type": "update", "originalFile": "# x\n"})
    assert not created_journal("Edit", NEW, {"filePath": NEW, "originalFile": "# x\n"})
    assert not created_journal("Write", "C:\\x\\docs\\adr\\0034-x.md", {"type": "create"})
    assert not created_journal("Write", NEW, None)
    assert not created_journal("Write", NEW, {})
