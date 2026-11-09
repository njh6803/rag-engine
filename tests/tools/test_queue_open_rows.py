"""tools/queue_open_rows.py 검증. 항목 모양은 `.scratch/retro-queue/`의 실제 항목 파일을 줄여
옮겼다."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from tools.queue_open_rows import (
    APPROVAL_HEAD,
    APPROVAL_TAIL,
    HEAD_CHARS,
    QUEUE,
    Hit,
    HitState,
    Item,
    by_target,
    item_name,
    item_path,
    label_problem,
    main,
    paths_in,
    read_folder,
    read_items,
    read_ref_folder,
    render,
    render_hits,
    search,
)

from tools import queue_open_rows

ROOT = Path(__file__).resolve().parents[2]
TODAY = date(2026, 10, 19)
GIT_TIMEOUT = 60


def item(
    ident: str, what: str, where: str = "", approval: str = "", status: str = "열림"
) -> tuple[str, str]:
    """(파일 이름, 내용). `what`의 첫 줄이 머리이고 나머지가 본문이다."""
    head, _, body = what.partition("\n")
    text = f"# {ident}: {head}\n\n**상태:** {status}\n**어디로:** {where}\n**승인:** {approval}\n"
    if body:
        text += f"\n{body}\n"
    return f"{ident}.md", text


def folder(*items: tuple[str, str]) -> dict[str, str]:
    return dict(items)


def entry(
    ident: int | str,
    rounds: int | None,
    *targets: str,
    cited: tuple[str, ...] = (),
    last: date | None = None,
    human: bool = False,
) -> Item:
    name = f"{ident:04d}" if isinstance(ident, int) else ident
    cell = "승인" if rounds is not None else None
    return Item(name, rounds, cell, targets, cited, last, human)


def test_닫힘과_만료_상태의_항목은_세지_않는다() -> None:
    items, broken = read_items(
        folder(
            item("0001", "닫힌 일", "`a.md`", "사용자 승인, 3회차", "닫힘 (반영: PR #1)"),
            item("0002", "열린 일", "`b.md`", "사용자 승인, 1회차"),
            item("0003", "열린 일", "`c.md`", "사용자 승인, 1회차"),
            item("0004", "만료된 일", "`d.md`", "자체 승인, 1회차", "만료 2026-10-01 (14일)"),
            item("0005", "부분 반영한 일", "`e.md`", "자체 승인, 1회차", "열림 (부분 반영)"),
        )
    )
    assert [one.ident for one in items] == ["0002", "0003", "0005"]
    assert broken == []


def test_회차는_승인_줄에서_먼저_찾는다() -> None:
    items, _ = read_items(
        folder(item("0005", "일. 2회차의 근거", "`a.md`", "자체 승인, 1회차, 일지"))
    )
    assert items[0].rounds == 1
    assert items[0].round_cell == "승인"


def test_승인_줄에_회차가_없으면_머리와_본문에서_찾는다() -> None:
    """대기열 167의 사건: 회차를 무엇 칸에 적은 옛 행(17)이 손으로 센 목록에서 빠졌다."""
    items, _ = read_items(
        folder(
            item(
                "0017", "회귀 시험이 없다. **근거 추가**: 근거. **3회차**: 근거", "`x.ps1`", "승인"
            ),
            item("0018", "머리\n본문에 **4회차**를 적었다", "`y.ps1`", "승인"),
        )
    )
    assert [(one.rounds, one.round_cell) for one in items] == [(3, "무엇"), (4, "무엇")]


def test_머리와_본문에도_없으면_어디로_줄에서_찾는다() -> None:
    items, _ = read_items(folder(item("0019", "일", "`z.py` 2회차", "승인")))
    assert (items[0].rounds, items[0].round_cell) == (2, "어디로")


def test_못_보는_것_본문이_다른_항목의_회차를_인용해도_그_항목의_회차로_센다() -> None:
    items, _ = read_items(folder(item("0020", "일\n대기열 17의 3회차를 잇는다", "`a.md`", "승인")))
    assert (items[0].rounds, items[0].round_cell) == (3, "무엇")


def test_못_보는_것_이름이_번호도_슬러그도_아니어도_라벨_줄이_맞으면_항목이다() -> None:
    """이름 규칙은 저장소 상태 시험(tests/test_retro_queue_names.py)이 본다."""
    items, broken = read_items(folder(item("Foo", "일", "`a.md`", "1회차")))
    assert broken == []
    assert [one.ident for one in items] == ["Foo"]


def test_한_줄에_회차가_여럿이면_가장_큰_것을_쓴다() -> None:
    items, _ = read_items(
        folder(item("0009", "일. **2회차**: 근거. **3회차**: 근거", "`a.md`", "승인"))
    )
    assert items[0].rounds == 3


def test_어느_줄에도_회차가_없으면_모른다() -> None:
    items, _ = read_items(folder(item("0004", "일", "`a.md`", "일지 06")))
    assert items[0].rounds is None
    assert "회차를 찾지 못한 항목: 4" in render(items, [])


def test_괄호_밖의_경로는_대상이고_괄호_안의_경로는_인용이다() -> None:
    """옛 스크래치 스크립트는 둘을 가르지 않아 `.claude/rules/tools.md`가 대상 아홉으로 나왔다."""
    targets, citations = paths_in(
        "`tools/hook_x.py`와 그 시험, `tools/hook_payloads.toml`. 어겨지면 막는 훅"
        "(`.claude/rules/tools.md`의 계기·막는 훅 가름)"
    )
    assert targets == ("tools/hook_x.py", "tools/hook_payloads.toml")
    assert citations == (".claude/rules/tools.md",)


def test_겹친_괄호_안도_인용이고_닫힌_뒤는_다시_대상이다() -> None:
    targets, citations = paths_in("(가름(`a/b.md`) 뒤 `c/d.md`) 그리고 `e/f.md`")
    assert targets == ("e/f.md",)
    assert citations == ("a/b.md", "c/d.md")


def test_코드_스팬_안의_괄호는_깊이를_바꾸지_않는다() -> None:
    targets, citations = paths_in("`f(x)` 를 고친다 `a/b.py`")
    assert targets == ("a/b.py",)
    assert citations == ()


def test_경로가_아닌_코드_스팬은_세지_않는다() -> None:
    """식별자, 옵션, 스킬 이름, 슬래시 명령, 자리표시가 든 URL 은 파일이 아니다."""
    targets, _ = paths_in(
        "`_PUSH_LONG`과 `--update`, `next-session`, `/security-review`, "
        "`repos/{owner}/{repo}/logs`, `${KEY}`, `uv.lock`, `CODING_STANDARDS.md`, `docs/adr/`"
    )
    assert targets == ("uv.lock", "CODING_STANDARDS.md", "docs/adr/")


def test_같은_줄에서_대상이면서_인용인_경로는_대상으로만_센다() -> None:
    targets, citations = paths_in("`a/b.md` 한 줄(`a/b.md`의 절, `c/d.md`)")
    assert targets == ("a/b.md",)
    assert citations == ("c/d.md",)


def test_대상과_인용을_가르지_못하는_자리를_고정한다() -> None:
    """못 보는 것 둘. 본문의 인용은 대상으로, 괄호 안의 대상은 인용으로 센다(대기열 286·141)."""
    targets, _ = paths_in("판정 고침. 지우는 길이라 `.claude/rules/tools.md`의 반박 시험을 거친다")
    assert targets == (".claude/rules/tools.md",)
    targets, citations = paths_in("`a/rule.md`에 한 항목, 사용처(`tools/hook.py`)의 클라우드 길")
    assert targets == ("a/rule.md",)
    assert citations == ("tools/hook.py",)


def test_고칠_파일이_아닌_경로_모양도_대상으로_센다() -> None:
    """못 보는 것. git 이 만드는 잠금 파일(293), 훅이 지켜보는 경로(227), 부분 반영 항목의 끝난
    몫(141)."""
    items, _ = read_items(
        folder(
            item(
                "0293",
                "일",
                "`tools/`의 훅. 커밋이 돌면(그 git 디렉터리의 `index.lock`) 알린다. "
                "`index.lock`을 잰다",
                "2회차",
            ),
            item("0227", "일", "새 훅: `docs/adr/`에 더한 줄이면 알린다", "1회차"),
            item("0141", "일", "`.claude/rules/tools.md`에 한 항목", "1회차 **부분 반영: 더했다**"),
        )
    )
    assert [one.targets for one in items] == [
        (".claude/rules/tools.md",),
        ("docs/adr/",),
        ("tools/", "index.lock"),
    ]


def test_사용자가_순서를_올린_항목은_표지가_없어_세지_않는다() -> None:
    """못 보는 것. 결정표의 둘째 조건은 항목에서 읽지 않는다."""
    approval = "사용자가 순서를 올렸다, 1회차, 2026-10-18"
    items, _ = read_items(folder(item("0005", "일", "`a.md`", approval)))
    out = render(items, [], TODAY)
    assert "회차 5 이상: (없음)" in out
    assert "만료할 항목(승인 줄의 가장 늦은 날짜가 2026-10-05 전): (없음)" in out
    assert "날짜를 찾지 못한 항목" not in out


def test_회차를_말로만_적은_항목은_모른다고_센다() -> None:
    """못 보는 것. `<수>회차`만 읽는다."""
    items, _ = read_items(folder(item("0006", "일", "`a.md`", "사용자 승인, 세 번째 반복")))
    assert items[0].rounds is None


def test_같은_파일을_다른_이름으로_적으면_다른_대상이다() -> None:
    """못 보는 것. 이름을 풀지 않아 짧은 이름과 긴 경로, 디렉터리와 그 아래 파일이 갈린다."""
    items, _ = read_items(
        folder(
            item("0001", "일", "`operations.md`", "1회차"),
            item("0002", "일", "`docs/constitution/operations.md`", "1회차"),
            item("0003", "일", "`tools/`", "1회차"),
            item("0004", "일", "`tools/a.py`", "1회차"),
        )
    )
    assert list(by_target(items)) == [
        "docs/constitution/operations.md",
        "operations.md",
        "tools/",
        "tools/a.py",
    ]


def test_라벨_줄이_빠진_항목은_빠뜨리지_않고_알린다() -> None:
    files = folder(
        item("0008", "일", "`b.md`", "1회차"),
        ("0007.md", "# 0007: 일\n\n**어디로:** `a.md`\n**승인:** 승인\n"),
        ("0006.md", "# 0006: 일\n\n**상태:** 열림\n**승인:** 승인\n**어디로:** `a.md`\n"),
        ("0005.md", "# 0004: 일\n\n**상태:** 열림\n**어디로:** `a.md`\n**승인:** 승인\n"),
        ("0004.md", "일\n\n**상태:** 열림\n**어디로:** `a.md`\n**승인:** 승인\n"),
        item("0003", "일", "`a.md`", "승인", "보류"),
        ("0002.md", ""),
    )
    items, broken = read_items(files)
    assert [one.ident for one in items] == ["0008"]
    assert broken == ["0002.md", "0003.md", "0004.md", "0005.md", "0006.md", "0007.md"]
    assert "**상태:**" in str(label_problem("0007.md", files["0007.md"]))
    assert "**어디로:**" in str(label_problem("0006.md", files["0006.md"]))
    assert "첫 줄" in str(label_problem("0005.md", files["0005.md"]))
    assert "첫 줄" in str(label_problem("0004.md", files["0004.md"]))
    assert "상태 값" in str(label_problem("0003.md", files["0003.md"]))
    assert label_problem("0008.md", files["0008.md"]) is None
    shown = render(items, ["0007.md (빠진 줄: **상태:**)"]).splitlines()
    assert "라벨 줄이 빠진 항목: (세지 않았다. 항목 파일의 라벨 줄을 고치고 다시 센다)" in shown
    assert "  0007.md (빠진 줄: **상태:**)" in shown


def test_라벨_줄_사이와_앞의_빈_줄은_건너뛴다() -> None:
    text = "# 0001: 일\n\n\n**상태:** 열림\n\n**어디로:** `a.md`\n**승인:** 1회차\n\n본문\n"
    items, broken = read_items({"0001.md": text})
    assert broken == []
    assert [(one.ident, one.rounds, one.targets) for one in items] == [("0001", 1, ("a.md",))]


def row_dates() -> dict[str, str]:
    return folder(
        item(
            "0001",
            "일",
            "`a.md`",
            "자체 승인 2026-10-01, 2회차, 일지 2026-10-03-02-journal-number-uniqueness.md·"
            "2026-10-02-04",
        ),
        item("0002", "일", "사람 몫: 주 체크아웃에서 정리한다", "사용자 승인 2026-10-13, 11회차"),
        item("0003", "일", "`b.md`", "승인, 1회차"),
    )


def test_승인_줄의_가장_늦은_날짜와_사람_몫을_읽는다() -> None:
    items, _ = read_items(row_dates())
    assert [(one.ident, one.last, one.human) for one in items] == [
        ("0001", date(2026, 10, 3), False),
        ("0002", date(2026, 10, 13), True),
        ("0003", None, False),
    ]


def test_사람_몫은_어디로_줄이_사람_몫과_쌍점으로_시작할_때만이고_굵게_써도_읽는다() -> None:
    """셀프 리뷰: `사람 몫`으로만 견주자 `사람 몫이 아닌 …`이 사람 몫이 되고 `**사람 몫:**`은
    빠졌다."""
    items, _ = read_items(
        folder(
            item("0001", "일", "**사람 몫:** 정리한다", "1회차"),
            item("0002", "일", "사람 몫이 아닌 `tools/y.py`", "1회차"),
        )
    )
    assert [(one.ident, one.human) for one in items] == [("0001", True), ("0002", False)]


def test_회차_5_이상인_항목은_반영할_때까지_만료하지_않는다() -> None:
    """셀프 리뷰: chore 를 기능 뒤에만 여니 문턱을 넘은 항목이 반영을 기다리다 14일을 넘겨 닫힐 수
    있었다. 문턱이 3에서 5로 올랐으니 회차 4 항목은 보호선 밖이라 만료 후보다(ADR 0036 이력
    2026-11-06)."""
    out = render(
        [
            entry(1, 5, last=date(2026, 9, 1)),
            entry(2, 4, last=date(2026, 9, 1)),
            entry(3, 2, last=date(2026, 9, 1)),
        ],
        [],
        TODAY,
    )
    assert "회차 5 이상: 1(5회차)" in out
    expired = "만료할 항목(승인 줄의 가장 늦은 날짜가 2026-10-05 전): 2(2026-09-01) 3(2026-09-01)"
    assert expired in out.splitlines()


def test_사람_몫_항목은_회차_5_이상에_넣지_않고_따로_적는다() -> None:
    """대기열 238: 사람이 할 일을 세션마다 다시 보며 회차가 11까지 쌓여 chore 계기가 됐다."""
    out = render([entry(238, 11, human=True), entry(306, 9)], [], TODAY)
    assert "회차 5 이상: 306(9회차)" in out
    assert "사람 몫(회차를 chore 계기로 세지 않고 만료하지 않는다): 238" in out


def test_승인_줄의_가장_늦은_날짜가_14일_넘게_지난_항목을_만료로_적는다() -> None:
    out = render(
        [
            entry(1, 1, last=date(2026, 10, 4)),
            entry(2, 2, last=date(2026, 10, 5)),
            entry(3, 1, last=date(2026, 10, 18)),
            entry(4, 1, last=date(2026, 9, 1), human=True),
        ],
        [],
        TODAY,
    )
    assert (
        "만료할 항목(승인 줄의 가장 늦은 날짜가 2026-10-05 전): 1(2026-10-04)" in out.splitlines()
    )


def test_없는_날짜는_넘고_남은_날짜에서_가장_늦은_것을_고른다() -> None:
    items, _ = read_items(
        folder(item("0001", "일", "`a.md`", "자체 승인 2026-10-01, 1회차, 반영 2026-02-30"))
    )
    assert items[0].last == date(2026, 10, 1)


def test_만료할_항목이_없으면_없다고_적고_날짜가_없는_항목은_따로_적는다() -> None:
    out = render([entry(1, 1, last=date(2026, 10, 18)), entry(4, None)], [], TODAY)
    assert "만료할 항목(승인 줄의 가장 늦은 날짜가 2026-10-05 전): (없음)" in out
    assert "날짜를 찾지 못한 항목: 4" in out


def test_날짜가_없어도_회차_5_이상인_항목은_날짜를_찾지_못한_항목에_적지_않는다() -> None:
    """PR 직전 버그 축: 만료하지 않는 항목까지 적어, retro 가 그 항목의 날짜를 git 에서 찾게
    했다."""
    out = render([entry(1, 5), entry(4, 1)], [], TODAY)
    assert "날짜를 찾지 못한 항목: 4" in out.splitlines()


def test_못_보는_것_회차가_아닌_날짜도_가장_늦은_날짜로_센다() -> None:
    """부분 반영을 적은 날이 늦으면 새 회차가 없어도 만료하지 않는다."""
    approval = "자체 승인 2026-09-21, 1회차, 일지 2026-09-21-01. 반영 2026-10-18"
    items, _ = read_items(folder(item("0001", "일", "`a.md`", approval)))
    out = render(items, [], TODAY)
    assert "만료할 항목(승인 줄의 가장 늦은 날짜가 2026-10-05 전): (없음)" in out


def test_못_보는_것_머리와_본문과_어디로_줄의_날짜는_보지_않는다() -> None:
    items, _ = read_items(
        folder(item("0001", "2026-10-18 에 난 일\n본문 2026-10-17", "`a.md`(2026-10-18)", "1회차"))
    )
    assert items[0].last is None


def test_결정표의_조건을_모은다() -> None:
    """`next-session` 결정표의 chore 배치 조건은 회차 5 이상이다. 같은 대상 파일 셋 이상은
    계기가 아니라 배치를 고른 뒤 함께 묶을 항목이다(ADR 0036)."""
    out = render(
        [
            entry(167, 5, "tools/"),
            entry(238, 7),
            entry(68, 1, "CODING_STANDARDS.md"),
            entry(71, 2, "CODING_STANDARDS.md"),
            entry(107, 1, "CODING_STANDARDS.md"),
            entry(64, 1, "web/a.mjs"),
            entry(65, 1, "web/a.mjs"),
        ],
        [],
    )
    assert "열린 항목 7개" in out
    assert "회차 5 이상: 238(7회차) 167(5회차)" in out
    assert "`CODING_STANDARDS.md`: 68 71 107" in out
    assert "web/a.mjs" not in out


def test_숫자_식별자는_앞의_0을_떼고_슬러그는_그대로_찍고_번호가_먼저_놓인다() -> None:
    """정렬 키는 (-회차, 숫자 ID 오름차순이 먼저, 그다음 슬러그 오름차순)이다."""
    out = render(
        [
            entry("coderabbit-inline-size", 5, "a.md"),
            entry(573, 5, "a.md"),
            entry("alpha", 5, "a.md"),
            entry(100, 5, "a.md"),
            entry("zeta", 7),
        ],
        [],
    )
    expected = (
        "회차 5 이상: zeta(7회차) 100(5회차) 573(5회차) alpha(5회차) coderabbit-inline-size(5회차)"
    )
    assert expected in out
    assert "`a.md`: 100 573 alpha coderabbit-inline-size" in out
    assert "0573" not in out


def test_날짜가_같은_만료_후보도_같은_키로_놓인다() -> None:
    day = date(2026, 9, 1)
    out = render(
        [entry("beta", 1, last=day), entry(9, 1, last=day), entry("alpha", 1, last=day)], [], TODAY
    )
    assert "9(2026-09-01) alpha(2026-09-01) beta(2026-09-01)" in out


def test_만료된_번호_항목을_잇는_슬러그_항목의_회차_5가_회차_5_이상에_든다() -> None:
    """사용자 스토리 6: 만료된 `0435`(4회차)가 다시 일어나면 슬러그 항목이 5회차로 잇는다."""
    items, broken = read_items(
        folder(
            item("0435", "옛 일", "`tools/a.py`", "자체 승인 2026-09-01, 4회차", "만료 2026-09-20"),
            item(
                "retro-again",
                "옛 일이 다시 났다",
                "`tools/a.py`",
                "자체 승인 2026-11-07, 5회차(0435의 4회차를 잇는다)",
            ),
        )
    )
    assert broken == []
    assert [one.ident for one in items] == ["retro-again"]
    assert "회차 5 이상: retro-again(5회차)" in render(items, [], date(2026, 11, 7))


def test_디렉터리와_패턴은_같은_대상_파일_조건에_세지_않고_따로_찍는다() -> None:
    """표준 축 리뷰: `tools/`가 여덟 항목을 묶어 결정표의 셋째 조건이 늘 켜졌다."""
    out = render(
        [
            entry(1, 1, "tools/", "a/*.toml"),
            entry(2, 1, "tools/", "a/*.toml"),
            entry(3, 1, "tools/", "a/*.toml"),
        ],
        [],
    )
    shared, rest = out.split("디렉터리·패턴 대상")
    assert "같은 대상 파일이 3개 항목 이상: (없음)" in shared
    assert "`tools/`: 1 2 3" in rest
    assert "`a/*.toml`: 1 2 3" in rest


def test_괄호_안의_인용도_항목_번호와_함께_기본_출력에_찍는다() -> None:
    """명세 축 리뷰: 인용으로 넘긴 진짜 대상(141)을 사람이 가르려면 기본 출력에 있어야 한다."""
    out = render([entry(141, 1, "a/rule.md", cited=("tools/hook.py",)), entry(2, 1)], [])
    assert "괄호 안의 인용으로 센 경로" in out
    assert "`tools/hook.py`: 141" in out


def test_조건에_드는_것이_없으면_없다고_적는다() -> None:
    out = render([entry(1, 1, "a.md")], [])
    assert "회차 5 이상: (없음)" in out
    assert "같은 대상 파일이 3개 항목 이상: (없음)" in out


def test_573과_0573은_같은_파일로_풀리고_슬러그는_그_이름의_파일로_풀린다() -> None:
    assert item_name("573") == item_name("0573") == "0573.md"
    assert item_name("1") == "0001.md"
    assert item_name("coderabbit-inline-size") == "coderabbit-inline-size.md"
    assert item_path("573") == item_path("0573") == QUEUE / "0573.md"
    assert item_path("coderabbit-inline-size") == QUEUE / "coderabbit-inline-size.md"


def test_틀린_식별자는_값_오류다() -> None:
    for wrong in ("", "0001x", "Coderabbit", "-lead", "9slug", "a_b", "a b", "../0001", "0573.md"):
        with pytest.raises(ValueError):
            item_name(wrong)


def test_폴더를_읽을_때_README와_하위_폴더와_다른_확장자는_항목이_아니다(tmp_path: Path) -> None:
    """못 보는 것: README.md 는 항목이 아니고 하위 폴더의 항목은 보지 않는다."""
    (tmp_path / "0001.md").write_text("a", encoding="utf-8")
    (tmp_path / "slug-item.md").write_text("b", encoding="utf-8")
    (tmp_path / "README.md").write_text("c", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("d", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "0002.md").write_text("e", encoding="utf-8")
    (tmp_path / "dir.md").mkdir()
    assert read_folder(tmp_path) == {"0001.md": "a", "slug-item.md": "b"}


def test_README만_든_폴더와_README_이름의_항목은_열린_항목에_들지_않는다() -> None:
    items, broken = read_items({"README.md": "# 규칙\n"})
    assert (items, broken) == ([], [])


def write_folder(path: Path, files: dict[str, str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (path / name).write_text(text, encoding="utf-8")


def test_main을_실제로_불러_임시_대기열의_조건을_찍는다(tmp_path: Path) -> None:
    write_folder(
        tmp_path / "queue",
        folder(
            item("0009", "일", "`a.md`", "5회차"),
            ("0010.md", "# 0010: 일\n\n**어디로:** `a.md`\n**승인:** 1회차\n"),
        ),
    )
    done = subprocess.run(
        [sys.executable, "tools/queue_open_rows.py", "--queue", str(tmp_path / "queue")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=GIT_TIMEOUT,
        check=False,
    )
    assert done.returncode == 1, done.stderr
    assert "열린 항목 1개" in done.stdout
    assert "회차 5 이상: 9(5회차)" in done.stdout
    assert "라벨 줄이 빠진 항목" in done.stdout
    assert (tmp_path / "queue" / "0010.md").as_posix() in done.stdout
    assert "**상태:**" in done.stdout


def test_main은_today를_기준일로_만료할_항목을_찍는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_folder(tmp_path, folder(item("0009", "일", "`a.md`", "자체 승인 2026-09-01, 1회차")))
    assert main(["--queue", str(tmp_path), "--today", "2026-09-15"]) == 0
    assert (
        "만료할 항목(승인 줄의 가장 늦은 날짜가 2026-09-01 전): (없음)" in capsys.readouterr().out
    )
    assert main(["--queue", str(tmp_path), "--today", "2026-09-16"]) == 0
    assert "2026-09-02 전): 9(2026-09-01)" in capsys.readouterr().out
    assert main(["--queue", str(tmp_path), "--today", "어제"]) == 2


def test_main은_없는_폴더거나_폴더가_아니면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--queue", str(tmp_path / "없다")]) == 2
    assert "대기열을 읽지 못했다" in capsys.readouterr().err
    (tmp_path / "file.md").write_text("x", encoding="utf-8")
    assert main(["--queue", str(tmp_path / "file.md")]) == 2


def test_main은_rows를_주면_항목마다의_줄을_기본_출력_뒤에_찍는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_folder(tmp_path, folder(item("0009", "일", "`a/b.md`(`c/d.md`)", "3회차")))
    assert main(["--queue", str(tmp_path)]) == 0
    assert "항목마다:" not in capsys.readouterr().out
    assert main(["--queue", str(tmp_path), "--rows"]) == 0
    out = capsys.readouterr().out
    assert out.index("열린 항목 1개") < out.index("항목마다:")
    assert "  9 3회차(승인) 대상: a/b.md / 인용: c/d.md" in out


def test_main은_인자가_틀리면_쓰임을_내고_2로_끝난다(capsys: pytest.CaptureFixture[str]) -> None:
    for argv in (["--queue"], ["--모름"], ["--queue", "a", "--ref", "HEAD"]):
        assert main(argv) == 2
        assert "쓰임: uv run python tools/queue_open_rows.py" in capsys.readouterr().err
    assert "--queue <폴더>" in queue_open_rows.USAGE


def test_main은_대시로_시작하는_ref를_git에_넘기지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PR 직전 버그 리뷰: `--ref --output=<경로>` 는 git 이 옵션으로 읽어 파일을 쓰려 했다.

    git 이 그 경로를 열지 못해도 2로 끝나므로, git 까지 가지 않고 사용법 오류로 막혔는지를 본다.
    """
    written = tmp_path / "x"
    assert main(["--ref", f"--output={written}"]) == 2
    assert "쓰임:" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_main은_UTF8이_아닌_항목_파일이면_2로_끝난다(tmp_path: Path) -> None:
    """PR 직전 버그 리뷰: 해독 실패가 트레이스백의 1로 끝나 라벨 줄 오류와 섞였다."""
    name, text = item("0001", "일", "`a.md`", "1회차")
    (tmp_path / name).write_bytes(text.encode("cp949"))
    assert main(["--queue", str(tmp_path)]) == 2
    assert main(["--queue", str(tmp_path), "--search", "일"]) == 2


def test_닫히지_않은_백틱_뒤의_경로는_세지_않는다() -> None:
    """못 보는 것."""
    targets, _ = paths_in("`a/b.md`와 `열림 `c/d.md`")
    assert targets == ("a/b.md",)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "queue_open_rows.py"), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=GIT_TIMEOUT,
        check=False,
    )


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=GIT_TIMEOUT)


def _commit(cwd: Path, message: str) -> None:
    _git(cwd, "add", "-A")
    _git(cwd, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message)


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    _git(tmp_path, "init", "-q")
    write_folder(tmp_path / QUEUE, files)
    return tmp_path


def test_ref로_커밋의_폴더를_읽고_모두_읽으면_0으로_끝난다(tmp_path: Path) -> None:
    """워크트리에서 병합한 뒤 `--ref origin/main`으로 다른 PR이 더한 항목까지 센다(독스트링의
    쓰임)."""
    repo = _repo(
        tmp_path,
        {
            **folder(
                item("0001", "일", "`a.md`", "5회차"),
                item("0002", "일", "`b.md`", "1회차"),
                item("coderabbit-inline-size", "일", "`c.md`", "6회차"),
            ),
            "README.md": "# 대기열 규칙\n",
        },
    )
    _commit(repo, "q")
    write_folder(repo / QUEUE, folder(item("0003", "일", "`d.md`", "1회차")))
    (repo / QUEUE / "0001.md").unlink()
    from_ref = _run("--ref", "HEAD", cwd=repo)
    assert from_ref.returncode == 0, from_ref.stderr
    assert "열린 항목 3개" in from_ref.stdout
    assert "회차 5 이상: coderabbit-inline-size(6회차) 1(5회차)" in from_ref.stdout
    from_disk = _run(cwd=repo)
    assert from_disk.returncode == 0, from_disk.stderr
    assert "회차 5 이상: coderabbit-inline-size(6회차)" in from_disk.stdout
    assert "열린 항목 3개" in from_disk.stdout
    missing = _run("--ref", "없는-커밋", cwd=repo)
    assert missing.returncode == 2
    assert "대기열을 읽지 못했다" in missing.stderr


def test_ref는_README와_하위_폴더_파일을_읽지_않는다(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        {
            **folder(item("0001", "일", "`a.md`", "1회차")),
            "README.md": "# 규칙\n",
            "notes.txt": "x",
        },
    )
    write_folder(repo / QUEUE / "sub", {"0002.md": "깨진 파일"})
    _commit(repo, "q")
    done = _run("--ref", "HEAD", cwd=repo)
    assert done.returncode == 0, done.stderr
    assert "열린 항목 1개" in done.stdout
    assert "라벨 줄이 빠진 항목" not in done.stdout


def test_이행_전_커밋은_옛_파일이_있어도_2로_끝난다(tmp_path: Path) -> None:
    """`--ref` 는 폴더가 없는 커밋을 받으면 옛 `.scratch/retro-queue.md` 로 돌아가지 않는다."""
    _git(tmp_path, "init", "-q")
    old = tmp_path / ".scratch" / "retro-queue.md"
    old.parent.mkdir(parents=True)
    old.write_text(
        "| # | 무엇 | 어디로 | 승인 |\n|---|---|---|---|\n| 1 | 일 | `a.md` | 1회차 |\n", "utf-8"
    )
    _commit(tmp_path, "old")
    done = _run("--ref", "HEAD", cwd=tmp_path)
    assert done.returncode == 2
    assert "대기열을 읽지 못했다" in done.stderr
    assert done.stdout == ""
    searched = _run("--ref", "HEAD", "--search", "일", cwd=tmp_path)
    assert searched.returncode == 2
    assert "맞은 항목" not in searched.stdout


def test_ref는_UTF8이_아닌_항목_파일이면_2로_끝난다(tmp_path: Path) -> None:
    name, text = item("0001", "일", "`a.md`", "1회차")
    repo = _repo(tmp_path, {})
    (repo / QUEUE / name).write_bytes(text.encode("cp949"))
    _commit(repo, "q")
    done = _run("--ref", "HEAD", cwd=repo)
    assert done.returncode == 2
    assert "대기열을 읽지 못했다" in done.stderr


def test_ref는_항목마다_git을_띄우지_않고_두_번에_받는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(
        tmp_path, folder(*(item(f"{n:04d}", "일", "`a.md`", "1회차") for n in range(1, 8)))
    )
    _commit(repo, "q")
    monkeypatch.chdir(repo)
    calls: list[list[str]] = []
    real = queue_open_rows.git_bytes

    def counting(args: list[str], stdin: bytes | None = None) -> bytes:
        calls.append(args)
        return real(args, stdin)

    monkeypatch.setattr(queue_open_rows, "git_bytes", counting)
    files = read_ref_folder("HEAD")
    assert sorted(files) == [f"{n:04d}.md" for n in range(1, 8)]
    assert [call[0] for call in calls] == ["ls-tree", "cat-file"]


def find(files: dict[str, str], *patterns: str) -> list[Hit]:
    return search(files, [re.compile(pattern) for pattern in patterns])


def test_search는_닫힌_항목까지_파일_원문에_맞춰_경로와_함께_찾는다() -> None:
    """대기열 425: retro 5단계의 항목 찾기는 닫힌 항목도 찾아야 4단계의 회차대로 잇는다."""
    hits = find(
        folder(
            item("0001", "닫힌 일", "`tools/a.py`", "자체 승인 2026-10-01, 2회차", "닫힘 (반영)"),
            item("0002", "열린 일", "`tools/b.py`", "자체 승인 2026-10-02, 1회차"),
            item("0003", "맞지 않는 일", "`c.md`", "1회차"),
            item("0004", "만료한 일", "`tools/d.py`", "1회차", "만료 2026-10-20"),
        ),
        "tools/",
    )
    assert [(hit.ident, hit.state, hit.rounds) for hit in hits] == [
        ("0001", HitState.CLOSED, 2),
        ("0002", HitState.OPEN, 1),
        ("0004", HitState.CLOSED, 1),
    ]
    assert hits[0].path == ".scratch/retro-queue/0001.md"


def test_search를_여러_번_주면_하나라도_맞은_항목을_찾는다() -> None:
    files = folder(
        item("0001", "일", "`a.md`", "1회차"),
        item("0002", "일", "`b.md`", "1회차"),
        item("0003", "일", "`c.md`", "1회차"),
    )
    assert [hit.ident for hit in find(files, r"a\.md", r"c\.md")] == ["0001", "0003"]


def test_맞은_항목은_번호가_먼저고_그다음_슬러그_순서다() -> None:
    files = folder(
        item("zeta", "일", "`a.md`", "1회차"),
        item("0573", "일", "`a.md`", "1회차"),
        item("alpha", "일", "`a.md`", "1회차"),
        item("0100", "일", "`a.md`", "1회차"),
    )
    assert [hit.ident for hit in find(files, r"a\.md")] == ["0100", "0573", "alpha", "zeta"]


def test_머리는_머리_줄의_글이고_길면_자르고_자른_글자_수를_적는다() -> None:
    exact = "가" * HEAD_CHARS
    (hit,) = find(folder(item("0001", exact, "`a.md`", "1회차")), r"a\.md")
    assert hit.head == exact
    (hit,) = find(folder(item("0001", f"{exact}나다", "`a.md`", "1회차")), r"a\.md")
    assert hit.head == f"{exact} …(2자 줄임)"
    (hit,) = find(folder(item("0001", "**굵은** 머리\n본문", "`a.md`", "1회차")), r"a\.md")
    assert hit.head == "**굵은** 머리"


def test_승인_줄이_길면_가운데를_줄이고_줄인_글자_수를_적는다() -> None:
    """승인 줄은 첫 승인으로 시작해 회차와 닫힘을 뒤에 덧붙여 가므로 앞(첫 승인)과 끝(가장 늦게
    덧붙인 글의 꼬리)을 남긴다."""
    exact = "승" * (APPROVAL_HEAD + APPROVAL_TAIL)
    (hit,) = find(folder(item("0001", "일", "`a.md`", exact)), r"a\.md")
    assert hit.approval == exact
    approval = "앞" * APPROVAL_HEAD + "가운데" + "끝" * APPROVAL_TAIL
    (hit,) = find(folder(item("0001", "일", "`a.md`", approval)), r"a\.md")
    assert hit.approval == "앞" * APPROVAL_HEAD + " …(가운데 3자 줄임)… " + "끝" * APPROVAL_TAIL


def test_회차는_줄이기_전의_승인_줄에서_찾는다() -> None:
    """덧붙인 글이 길면 회차가 줄인 가운데에 들 수 있다."""
    approval = "앞" * APPROVAL_HEAD + " 7회차 " + "끝" * APPROVAL_TAIL
    (hit,) = find(folder(item("0001", "일", "`a.md`", approval)), r"a\.md")
    assert hit.rounds == 7
    assert "7회차" not in hit.approval


def test_render_hits는_열린_항목과_닫힌_항목을_세고_항목마다_한_줄을_찍는다() -> None:
    hits = find(
        folder(
            item(
                "0001",
                "닫힌 일",
                "`a.md`",
                "자체 승인 2026-10-01, 2회차 **만료 2026-10-20**",
                "닫힘 (반영)",
            ),
            item("coderabbit-inline-size", "열린 일", "`a.md`", "자체 승인"),
        ),
        r"a\.md",
    )
    assert render_hits(hits).splitlines() == [
        "맞은 항목 2개(열린 항목 1개, 닫힌 항목 1개)."
        " 같은 일로 보이는 항목은 그 파일을 Read 로 연다:",
        "  .scratch/retro-queue/0001.md 닫힘 2회차 머리: 닫힌 일 / 승인: "
        "자체 승인 2026-10-01, 2회차 **만료 2026-10-20**",
        "  .scratch/retro-queue/coderabbit-inline-size.md 열림 회차 모름"
        " 머리: 열린 일 / 승인: 자체 승인",
    ]


def test_render_hits는_줄_번호나_offset을_찍지_않는다() -> None:
    out = render_hits(find(folder(item("0001", "일", "`a.md`", "1회차")), r"a\.md"))
    assert "줄 " not in out
    assert "offset" not in out


def test_render_hits는_맞은_항목이_없으면_없다고_적는다() -> None:
    assert render_hits([]) == "맞은 항목 없음"


def test_맞은_항목의_라벨_줄이_빠졌으면_경로를_알리고_머리_줄에_따로_센다() -> None:
    files = folder(
        ("0007.md", "# 0007: 일\n\n**어디로:** `a.md`\n**승인:** 승인\n"),
        item("0008", "일", "`a.md`", "1회차"),
    )
    hits = find(files, r"a\.md")
    assert [(hit.ident, hit.state) for hit in hits] == [
        ("0007", HitState.BROKEN),
        ("0008", HitState.OPEN),
    ]
    out = render_hits(hits)
    assert "맞은 항목 2개(열린 항목 1개, 닫힌 항목 0개, 라벨 줄이 빠진 항목 1개)." in out
    assert "  .scratch/retro-queue/0007.md 라벨 줄이 빠졌다" in out


def test_못_보는_것_어디에_맞았는지는_찍지_않는다() -> None:
    """어디로 줄이나 본문이나 잘린 자리에서만 맞은 항목도 찍지만, 맞은 낱말은 출력에 없다."""
    hits = find(folder(item("0001", "머리", "`tools/숨은.py`", "1회차")), "숨은")
    out = render_hits(hits)
    assert "  .scratch/retro-queue/0001.md 열림 1회차 머리: 머리 / 승인: 1회차" in out
    assert "숨은" not in out
    approval = "앞" * APPROVAL_HEAD + "숨은" + "끝" * APPROVAL_TAIL
    out = render_hits(
        find(folder(item("0002", "머리\n본문의 숨은 글", "`a.md`", approval)), "숨은")
    )
    assert "  .scratch/retro-queue/0002.md 열림 회차 모름 머리: 머리 / 승인: " in out
    assert "숨은" not in out


def test_못_보는_것_번호로_찾으면_네_자리_머리와_본문의_인용이_따로_맞는다() -> None:
    """파일 원문 전체에 맞춘다. 번호 425 의 파일 머리는 `0425` 라 `(?<!\\d)425` 에 맞지 않고,
    다른 항목의 `대기열 425` 인용은 `0425` 에 맞지 않는다. 둘 다 찾으려면 `(?<!\\d)0?425(?!\\d)`.
    `\\b` 는 수와 한글 사이를 경계로 보지 않아 `425의` 를 놓친다."""
    files = folder(
        item("0425", "일", "`a.md`", "1회차"),
        item("1425", "일", "`b.md`", "1회차"),
        item("0007", "일\n대기열 425의 2회차", "`c.md`", "2회차"),
    )
    assert [hit.ident for hit in find(files, "425")] == ["0007", "0425", "1425"]
    assert [hit.ident for hit in find(files, r"(?<!\d)425(?!\d)")] == ["0007"]
    assert [hit.ident for hit in find(files, r"(?<!\d)0425(?!\d)")] == ["0425"]
    assert [hit.ident for hit in find(files, r"(?<!\d)0?425(?!\d)")] == ["0007", "0425"]
    assert find(files, r"\b425\b") == []


def test_못_보는_것_README와_하위_폴더_파일과_다른_확장자는_찾지_않는다(tmp_path: Path) -> None:
    write_folder(tmp_path, folder(item("0001", "일", "`a.md`", "1회차")))
    (tmp_path / "README.md").write_text("a.md 규칙\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("a.md\n", encoding="utf-8")
    write_folder(tmp_path / "sub", {"0002.md": "a.md\n"})
    hits = search(read_folder(tmp_path), [re.compile(r"a\.md")], tmp_path)
    assert [hit.ident for hit in hits] == ["0001"]


def test_main은_search를_주면_맞은_항목만_찍고_기본_출력을_내지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """라벨 줄이 온전한 항목만 둔다. 빠진 항목이 있으면 기본 출력도 1로 끝나, 기본 출력을 낸 판이
    출력 단언에 닿기 전에 종료 코드 단언에서 빨개진다."""
    write_folder(
        tmp_path,
        folder(item("0001", "일", "`a.md`", "5회차"), item("0002", "일", "`b.md`", "1회차")),
    )
    assert main(["--queue", str(tmp_path), "--search", r"a\.md"]) == 0
    out = capsys.readouterr().out
    assert f"  {(tmp_path / '0001.md').as_posix()} 열림 5회차" in out
    assert "0002.md" not in out
    assert "회차 5 이상" not in out


def test_main은_search에_라벨_줄이_빠진_항목이_맞으면_1로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_folder(
        tmp_path,
        folder(
            item("0001", "일", "`a.md`", "3회차"),
            ("0002.md", "# 0002: 일\n\n**상태:** 열림\n**어디로:** `b.md`\n"),
        ),
    )
    assert main(["--queue", str(tmp_path), "--search", r"b\.md"]) == 1
    assert f"  {(tmp_path / '0002.md').as_posix()} 라벨 줄이 빠졌다" in capsys.readouterr().out


def test_main은_search의_인자가_틀리면_쓰임을_내고_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_folder(tmp_path, folder(item("0001", "일", "`a.md`", "1회차")))
    wrong = (["--search"], ["--search", "a", "--rows"], ["--today", "2026-10-01", "--search", "a"])
    for extra in wrong:
        assert main(["--queue", str(tmp_path), *extra]) == 2
        assert "쓰임:" in capsys.readouterr().err
    assert main(["--queue", str(tmp_path), "--search", "("]) == 2
    assert "정규식이 틀렸다: (" in capsys.readouterr().err
    # re.error 가 아닌 것을 던지는 정규식도 트레이스백의 종료 1("라벨 줄이 빠진 항목")이 아니라 2다
    for source in ("a{99999999999}", "(" * 5000 + ")" * 5000):
        assert main(["--queue", str(tmp_path), "--search", source]) == 2
        assert "정규식이 틀렸다:" in capsys.readouterr().err


def test_search를_실제로_불러_한글을_찍는다(tmp_path: Path) -> None:
    write_folder(tmp_path / "q", folder(item("0009", "찾을 일", "`a.md`", "자체 승인, 2회차")))
    done = _run("--queue", str(tmp_path / "q"), "--search", "찾을", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    path = (tmp_path / "q" / "0009.md").as_posix()
    assert f"  {path} 열림 2회차 머리: 찾을 일 / 승인: 자체 승인, 2회차" in done.stdout


def test_이_저장소의_대기열_폴더를_찾기가_읽는다() -> None:
    """실제 폴더를 찾기가 읽는지 보는 스모크다. 닫힌 항목 찾기 자체는 앞의 임시 폴더 시험이
    고정한다. agent-os 는 닫힌 항목 0425 를 찾았다. rag-engine 킥오프(2026-11-09)에는 항목이 하나도
    없어, 폴더가 그 자리에 있고(README 가 있다) 찾기가 오류 없이 돌며 README 를 항목으로 읽지
    않는지만 본다. 첫 항목을 더하는 커밋이 그 항목을 찾는 단언으로 되살린다."""
    folder = ROOT / QUEUE
    assert (folder / "README.md").is_file(), "대기열 폴더의 README 가 없다. 경로가 틀렸다"
    files = read_folder(folder)

    assert "README.md" not in files
    hits = search(files, [re.compile(".")])
    assert [hit.ident for hit in hits if hit.state is HitState.BROKEN] == []
