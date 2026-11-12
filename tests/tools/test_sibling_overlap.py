"""tools/sibling_overlap.py 검증. 순수 함수와, 임시 원격·클론·워크트리로 만든 형제를 지나는 main.

임시 원격은 로컬 경로라 github.com 이 아니어서, main 은 `gh` 를 부르지 않고 merge ref 로 열린
PR 을 가린다. `gh api` 의 길은 `gh_listing` 을 바꿔 끼운 테스트 하나와 실제 실행(일지
2026-10-07-10)이 본다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from tools.sibling_overlap import (
    ADR_DIR,
    CONSTITUTION,
    GH_BODY_JQ,
    ON_FAILURE,
    ON_STUCK,
    Move,
    MoveError,
    MovePlan,
    Numbers,
    StuckMoveError,
    Survey,
    Verdict,
    Worktree,
    apply_moves,
    canary_sources,
    clashes,
    closed_heads,
    dangling_cites,
    dangling_files,
    fresh,
    gh_pulls,
    github_repo,
    harness_files,
    highest_version,
    journal_order,
    main,
    moved_bodies,
    moves,
    open_pulls,
    own_pull_bodies,
    plan_moves,
    pull_bodies,
    pull_body_lines,
    read_numbers,
    remote_branches,
    renumber,
    report_own_pulls,
    reserved_version,
    rewrite,
    unbumped,
    uncanaried,
    unshared,
    vacating_first,
    worktrees,
    write_moved_bodies,
)

from tools import sibling_overlap

TOOL = Path(__file__).resolve().parents[2] / "tools" / "sibling_overlap.py"


def _번호(
    journals: frozenset[str] | None = None,
    adrs: dict[str, str] | None = None,
    version: str | None = None,
) -> Numbers:
    return Numbers(journals or frozenset(), adrs or {}, version)


def test_일지_ADR_헌법의_번호를_읽는다() -> None:
    """일지는 번호가 아니라 파일 이름 전체를 든다. 옛 순번 꼴과 새 시각 꼴을 함께 읽는다."""
    numbers = read_numbers(
        ["2026-10-07-09-session-web-deps-hook.md", "2026-11-06-1432-a.md"],
        ["0026-design-system.md", "README.md"],
        "**Version**: 3.0.18 | **Ratified**: 2026-09-19",
    )

    assert numbers.journals == frozenset(
        {"2026-10-07-09-session-web-deps-hook.md", "2026-11-06-1432-a.md"}
    )
    assert numbers.adrs == {"0026": "0026-design-system.md"}
    assert numbers.version == "3.0.18"


def test_규약_밖의_이름은_번호가_아니다() -> None:
    """일지는 날짜 뒤가 두 자리나 네 자리여야 하고, 규약 전의 이름과 세 자리 꼴은 일지가 아니다.
    ADR 은 네 자리 번호로 시작해야 한다."""
    numbers = read_numbers(
        [
            "2026-10-07-x.md",
            "README.md",
            "2026-10-07-09-a.txt",
            "2026-10-07-143-a.md",
            "2026-09-19-kickoff.md",
        ],
        ["README.md", "26-short.md", "001-ticket.md"],
        "버전 없음",
    )

    assert numbers == _번호()


def test_새_번호는_아는_번호_어디에도_없는_것이고_일지는_새_번호가_아니다() -> None:
    theirs = _번호(
        frozenset({"2026-10-07-03-a.md", "2026-10-07-04-b.md"}),
        {"0026": "0026-x.md", "0027": "0027-y.md"},
        "3.0.17",
    )
    base = _번호(frozenset({"2026-10-07-03-a.md"}), {"0026": "0026-x.md"})
    main_ = _번호(frozenset({"2026-10-07-04-b.md"}), version="3.0.17")

    expected = _번호(adrs={"0027": "0027-y.md"})
    assert fresh(theirs, base, main_) == expected
    # 아는 번호가 없어도 일지는 새 번호로 세지 않는다
    assert fresh(theirs).journals == frozenset()


def test_공유한_이력은_같은_번호에_같은_파일이고_헌법_판은_가르지_않는다() -> None:
    ours = _번호(
        frozenset({"2026-10-07-05-a.md", "2026-10-07-06-ours.md"}),
        {"0002": "0002-x.md"},
        "1.0.1",
    )
    main_ = _번호(
        frozenset({"2026-10-07-05-a.md", "2026-10-07-06-main.md"}),
        {"0002": "0002-x.md"},
        "1.0.1",
    )

    expected = _번호(version="1.0.1")
    assert unshared(ours, main_) == expected


def test_같은_번호에_다른_파일이거나_같은_판이면_겹침이다() -> None:
    """같은 분의 일지 둘은 번호가 아니라 겹침이 아니다.

    그 겹침은 `tests/test_journal_names.py` 가 본다.
    """
    ours = _번호(
        frozenset({"2026-11-07-0930-ours.md"}),
        {"0027": "0027-ours.md"},
        "3.0.19",
    )
    theirs = _번호(
        frozenset({"2026-11-07-0930-theirs.md"}),
        {"0027": "0027-theirs.md"},
        "3.0.19",
    )

    assert [(clash.kind, clash.key) for clash in clashes(ours, theirs)] == [
        ("ADR", "0027"),
        ("헌법", "3.0.19"),
    ]


def test_같은_파일과_다른_판은_겹침이_아니다() -> None:
    ours = _번호(adrs={"0027": "0027-same.md"}, version="3.0.19")
    theirs = _번호(adrs={"0027": "0027-same.md"}, version="3.0.20")

    assert clashes(ours, theirs) == []
    assert clashes(ours, _번호()) == []


def test_옮길_번호는_겹친_종류의_이_브랜치_새_번호_전부를_차례대로_형제_뒤에_붙인다() -> None:
    """겹친 번호만 옮기면 이 브랜치의 다른 새 번호와 부딪히거나 차례가 뒤집힌다.

    이 브랜치 0003~0007, 열린 PR 0003, main 0004.
    """
    ours = _번호(
        adrs={f"000{n}": f"000{n}-ours.md" for n in range(3, 8)},
        version="3.0.18",
    )
    taken = [
        _번호(adrs={"0001": "x.md", "0002": "y.md"}),
        _번호(adrs={"0003": "pr.md"}, version="3.0.17"),
        _번호(adrs={"0004": "main.md"}),
    ]
    found = clashes(ours, taken[1]) + clashes(ours, taken[2])

    assert moves(ours, taken, found) == [
        Move("ADR", f"000{old}", f"000{old + 2}") for old in range(3, 8)
    ]


def test_옮길_번호는_자리가_그대로인_것을_빼고_ADR은_네_자리다() -> None:
    ours = _번호(adrs={"0002": "0002-ours.md", "0009": "0009-ours.md"})
    taken = [_번호(adrs={"0001": "a.md", "0002": "main.md", "0007": "b.md"})]

    assert moves(ours, taken, clashes(ours, taken[0])) == [Move("ADR", "0002", "0008")]


def test_GitHub_원격_URL에서_소유자와_저장소를_읽는다() -> None:
    assert github_repo("https://github.com/njh6803/agent-os") == ("njh6803", "agent-os")
    assert github_repo("https://github.com/njh6803/agent-os.git\n") == ("njh6803", "agent-os")
    assert github_repo("git@github.com:njh6803/agent-os.git") == ("njh6803", "agent-os")
    assert github_repo("/tmp/origin.git") is None
    assert github_repo("https://gitlab.com/a/b") is None


def test_gh_api_줄에서_열린_PR의_head를_읽는다() -> None:
    sha = "e358ad4daba191efbb550bf33cfba6018a17acaa"
    assert gh_pulls(f"158 {sha}\n\n잡음\n9 짧다\n") == {158: sha}


def test_열린_PR은_merge_ref가_있는_PR이다() -> None:
    listing = "\n".join(
        [
            "aaa\trefs/pull/157/head",
            "bbb\trefs/pull/158/head",
            "ccc\trefs/pull/158/merge",
            "ddd\trefs/pull/9/merge",
            "eee\trefs/heads/main",
            "fff\trefs/heads/chore/001-x",
        ]
    )

    assert open_pulls(listing) == {158: "bbb"}
    assert remote_branches(listing) == {"main": "eee", "chore/001-x": "fff"}


def test_닫힌_PR은_head_ref가_있고_열린_PR이_아닌_것이다() -> None:
    """열린 PR 의 head 와 같은 커밋은 뺀다. 한 커밋을 head 로 든 닫힌 PR 이 여럿이면 큰 번호다."""
    listing = "\n".join(
        [
            "aaa\trefs/pull/157/head",
            "bbb\trefs/pull/158/head",
            "bbb\trefs/pull/158/merge",
            "bbb\trefs/pull/150/head",
            "ccc\trefs/pull/160/head",
            "ccc\trefs/pull/159/head",
            "ddd\trefs/pull/161/merge",
            "eee\trefs/heads/main",
            # ls-remote 와 gh api 사이에 head 가 움직인 열린 PR. 번호로 뺀다
            "ggg\trefs/pull/162/head",
        ]
    )

    assert closed_heads(listing, {158: "bbb", 162: "fff"}) == {"aaa": 157, "ccc": 160}


def test_가장_높은_헌법_판은_글자가_아니라_수로_견주고_그_판을_쓴_자리를_모두_든다() -> None:
    held = [("origin/main", "3.0.9"), ("PR #5", "3.0.10"), ("워크트리", None), ("PR #6", "3.0.10")]

    assert highest_version(held) == ("3.0.10", ["PR #5", "PR #6"])
    assert highest_version([("origin/main", "3.0.9"), ("PR #5", "2.10.0")]) == (
        "3.0.9",
        ["origin/main"],
    )
    assert highest_version([("PR #5", None)]) is None


def test_판을_올리지_않고_고친_헌법_파일은_원칙_스택_운영의_셋이다() -> None:
    """헌법 README(판 줄과 색인)와 셋 밖의 새 파일은 보지 않는다(못 보는 것)."""
    changed = frozenset(
        {
            "docs/constitution/operations.md",
            "docs/constitution/tech.md",
            "docs/constitution/README.md",
            "docs/constitution/new.md",
            "CLAUDE.md",
        }
    )

    assert unbumped(changed, _번호()) == [
        "docs/constitution/operations.md",
        "docs/constitution/tech.md",
    ]
    assert unbumped(changed, _번호(version="3.0.32")) == []
    principles = frozenset({"docs/constitution/principles.md"})
    assert unbumped(principles, _번호()) == ["docs/constitution/principles.md"]
    # 올림의 종류는 보지 않는다. 원칙을 바꾸고 patch 로 올려도 지나간다(못 보는 것)
    assert unbumped(principles, _번호(version="3.0.32")) == []
    readme_only = frozenset({"docs/constitution/README.md", "docs/constitution/new.md"})
    assert unbumped(readme_only, _번호()) == []


def test_워크트리_목록은_bare와_사라진_것을_빼고_경로와_HEAD를_준다() -> None:
    porcelain = "\n".join(
        [
            "worktree /repo",
            "HEAD 111",
            "branch refs/heads/main",
            "",
            "worktree /repo/.claude/worktrees/a",
            "HEAD 222",
            "detached",
            "",
            "worktree /repo/.claude/worktrees/gone",
            "HEAD 333",
            "branch refs/heads/gone",
            "prunable gitdir file points to non-existent location",
            "",
            "worktree /bare.git",
            "bare",
            "",
        ]
    )

    assert worktrees(porcelain) == [
        Worktree("/repo", "111"),
        Worktree("/repo/.claude/worktrees/a", "222"),
    ]


def test_카나리아로_불러_보는_하네스_파일은_스킬_본문과_규칙과_서브에이전트다() -> None:
    """스킬 본문은 스킬 폴더 바로 아래의 마크다운 전부다. 카나리아의 하위 파일 갈래가 `SKILL.md` 밖
    파일을 원천으로 받는다(harness 027). 그보다 아래 폴더의 파일, `CLAUDE.md`, 훅 설정은 보지 않는다
    (못 보는 것)."""
    changed = [
        ".claude/skills/a/SKILL.md",
        ".claude/skills/a/notes.md",
        ".claude/skills/a/refs/deep.md",
        ".claude/skills/SKILL.md",
        ".claude/rules/tools.md",
        ".claude/agents/r.md",
        ".claude/settings.json",
        "CLAUDE.md",
        "docs/x.md",
    ]

    assert harness_files(changed) == [
        ".claude/agents/r.md",
        ".claude/rules/tools.md",
        ".claude/skills/a/SKILL.md",
        ".claude/skills/a/notes.md",
    ]


def test_원천으로_든_카나리아_명세를_하나도_고치지_않은_하네스_파일만_알린다() -> None:
    """대기열 235. 못 보는 것: 같은 원천의 명세 하나만 고쳐도, 명세를 고친 뒤 하네스를 다시 고쳐도
    지나간다(둘 다 이 입력이다). 읽지 못한 명세는 원천이 없어 그것만 고쳐도 알린다."""
    skill, rule, agent = ".claude/skills/a/SKILL.md", ".claude/rules/r.md", ".claude/agents/b.md"
    specs: dict[str, str | None] = {
        "c/a1.toml": skill,
        "c/a2.toml": skill,
        "c/r.toml": rule,
        "c/broken.toml": None,
    }
    changed = frozenset({skill, rule, agent, "c/a2.toml", "c/broken.toml"})

    assert uncanaried([agent, rule, skill], changed, specs) == [
        (agent, []),
        (rule, ["c/r.toml"]),
    ]


def test_카나리아_명세의_원천을_읽고_읽지_못한_명세는_원천이_없다(tmp_path: Path) -> None:
    rule = ".claude/rules/x.md"
    _쓴다(
        tmp_path,
        {
            ".scratch/harness/probes/canary/a.toml": f'kind = "rule"\nsource = "{rule}"\n',
            ".scratch/design-refresh/probes/canary/b.toml": "source = [\n",
            ".scratch/harness/probes/canary/c.toml": "source = 3\n",
            ".scratch/harness/probes/other/d.toml": f'source = "{rule}"\n',
        },
    )

    assert canary_sources(tmp_path) == {
        ".scratch/design-refresh/probes/canary/b.toml": None,
        ".scratch/harness/probes/canary/a.toml": rule,
        ".scratch/harness/probes/canary/c.toml": None,
    }


# 아래 시험들이 없는 번호로 쓰는 일지 인용은 임시 저장소에는 없고 이 저장소에는 있는 번호다. 이
# 파일의 새 줄도 커밋 전의 이 도구가 대조한다(대기열 254)


def test_없는_일지_번호를_가리킨_인용을_나온_차례로_한_번씩_든다() -> None:
    """대기열 254: 짐작한 일지 번호를 카나리아 명세에 인용해 없는 일지를 가리킨 채 셀프 리뷰까지
    갔다(일지 2026-10-13-67). 목록 꼴(`·`)의 번호도 하나씩 본다."""
    text = (
        "일지 2026-10-07-05를 본다(일지 2026-10-07-01·2026-10-07-04)\r\n"
        "다시 일지 2026-10-07-05, 그리고 새 일지 2026-10-07-02\n"
    )

    # 있는 번호는 뜻이 다른 일지를 가리켜도 지나간다(못 보는 것)
    known = {"2026-10-07-01-a.md", "2026-10-07-02-b.md"}
    assert dangling_cites(text, known) == ["2026-10-07-05", "2026-10-07-04"]


def test_인용_블록과_코드와_merge_base나_main에_있던_줄의_일지_인용은_보지_않는다() -> None:
    """인용 블록은 사용자 프롬프트의 원문이고, 코드 스팬과 펜스는 옮기기 전의 옛 번호를 적은
    기록이나 도구의 출력이다. merge-base 나 main 의 판에 글자 그대로 있는 줄은 이 브랜치가 더한 줄이
    아니다. 펜스는 여는 줄과 같은 글자로 같거나 더 길게 닫고, 닫지 않으면 끝까지 간다."""
    text = (
        '> 사용자: "일지 2026-10-07-03의 다음부터"\n'
        "처음 받은 `일지 2026-10-07-04` 를 옮겼다\r\n"
        "````\n"
        "옮길 번호: 일지 2026-10-07-05 → 2026-10-07-06\n"
        "```\n"
        "일지 2026-10-07-03 은 더 짧은 펜스 줄 뒤에도 펜스 안이다\n"
        "````` 뒤에 글이 붙은 줄은 닫지 않는다\n"
        "~~~~\n"
        "일지 2026-10-07-07 은 아직 펜스 안이다\n"
        "`````\n"
        "옛 줄의 일지 2026-10-07-08\r\n"
        "~~~\n"
        "일지 2026-10-07-09\n"
    )

    assert dangling_cites(text, set(), frozenset({"옛 줄의 일지 2026-10-07-08"})) == []
    # 둘 줄이 아니면 펜스 밖의 같은 줄은 든다
    assert dangling_cites(text, set()) == ["2026-10-07-08"]


def test_낱말_없이_든_번호와_목록의_줄인_꼴은_보지_않고_시험_데이터의_번호는_든다() -> None:
    """못 보는 것. "일지" 낱말 없이 든 번호, 목록의 줄인 꼴(`·05`), 코드 스팬에 넣은 인용은
    지나간다. 거꾸로 일부러 없는 번호를 쓴 시험 데이터(문자열)도 인용으로 읽어 든다."""
    text = (
        "처음 2026-10-07-03 을 받았다. 일지 2026-10-07-01·05 를 본다. `일지 2026-10-07-04`\n"
        '    assert "일지 2026-10-07-06" in out\n'
    )

    assert dangling_cites(text, {"2026-10-07-01-a.md"}) == ["2026-10-07-06"]


def test_지운_파일과_UTF_8로_읽지_못하는_파일의_일지_인용은_보지_않는다(tmp_path: Path) -> None:
    """못 보는 것. 고친 파일 목록에 있어도 디스크에 없거나 글이 아니면 넘어간다. 줄을 가를 판이
    없으면 git 을 부르지 않는다."""
    (tmp_path / "a.md").write_bytes("일지 2026-10-07-05\n".encode("cp949"))
    _쓴다(tmp_path, {"b.md": "일지 2026-10-07-05\n"})

    found = dangling_files(tmp_path, (), ["a.md", "b.md", "gone.md"], {"2026-10-07-01-a.md"})

    assert found == [("b.md", ["2026-10-07-05"])]


RESERVE = "1.0.1은 함께 돌던 형제 브랜치(`topic`)가 먼저 매겨 비워 두었다."


def _이력(version: str, history: str) -> str:
    return _헌법(version) + f"\n{history}\n"


def test_비워_둔_판의_문장을_지웠고_판_줄이_main과_같으면_그_판이다() -> None:
    """비워 둔 판의 새 신호(retro-queue-per-item 06). 대기열 279의 옛 신호는 이력 문단을 더했는지
    봤는데, 헌법 README 에 이력 문단이 없어졌다. 이 브랜치의 판 줄이 main 의 판 줄과 같고 main 에
    있던 이 브랜치 몫의 비워 둔 문장을 이 브랜치가 지웠으면 그 판을 가져간 것이다."""
    main_text = _이력("1.0.2", RESERVE)
    ours = _이력("1.0.2", "")

    assert reserved_version("topic", main_text, ours) == "1.0.1"
    # 다른 브랜치 몫이거나 분리 HEAD 면 올리지 않은 것이다
    assert reserved_version("other", main_text, ours) is None, (
        "다른 브랜치 몫으로 비워 둔 판은 가져간 판이 아니다"
    )
    assert reserved_version(None, main_text, ours) is None
    # 문장을 지우지 않았으면 가져가지 않은 것이다
    assert reserved_version("topic", main_text, main_text) is None, (
        "문장을 지우지 않았으면 가져간 것이 아니다"
    )
    # 판 줄이 main 과 다르면 이 신호가 아니라 판 줄로 본다. main 을 합치기 전의 브랜치는 비워 둔
    # 문장이 아예 없어도 판 줄이 main 의 것이 아니다
    assert reserved_version("topic", main_text, _이력("1.0.3", "")) is None, (
        "판 줄이 main 과 다르면 신호가 아니다"
    )
    assert reserved_version("topic", main_text, _이력("1.0.0", "")) is None
    # 다른 브랜치 몫의 문장을 지운 것은 이 브랜치의 판이 아니다
    other = "1.0.3은 함께 돌던 형제 브랜치(`other`)가 먼저 매겨 비워 두었다."
    both = _이력("1.0.4", f"{RESERVE}\n{other}")
    assert reserved_version("topic", both, _이력("1.0.4", RESERVE)) is None
    assert reserved_version("other", both, _이력("1.0.4", RESERVE)) == "1.0.3"
    # 둘 이상이면 가장 높은 판이다. 지우지 않은 것은 센 것에서 뺀다
    mine = "1.0.3은 함께 돌던 형제 브랜치(`topic`)가 먼저 매겨 비워 두었다."
    twice = _이력("1.0.4", f"{RESERVE}\n{mine}")
    assert reserved_version("topic", twice, _이력("1.0.4", "")) == "1.0.3", (
        "둘 이상이면 가장 높은 판이다"
    )
    assert reserved_version("topic", twice, _이력("1.0.4", mine)) == "1.0.1"


def test_판_줄이_없는_README는_비워_둔_판을_가져가지_않은_것이다() -> None:
    """PR 직전 버그 축: 이 브랜치가 헌법 README 를 지웠거나 비워도 도구가 트레이스백 없이 판정한다.
    지운 README 는 판 줄이 없어 main 의 판 줄과 같지 않다."""
    assert reserved_version("topic", _이력("1.0.2", RESERVE), "") is None
    assert reserved_version("topic", "", "") is None


def test_비워_둔_판은_그_꼴의_문장만_읽고_그_문장을_깨뜨려_고쳐도_가져간_것으로_센다() -> None:
    """못 보는 것. 다른 꼴로 적은 예약은 읽지 않는다. 이 브랜치가 문장을 지우지 않고 그 꼴이
    깨지게 고쳐도 그 판을 가져간 것으로 센다."""
    main_text = _이력("1.0.2", RESERVE)
    reworded = _이력("1.0.2", RESERVE.replace("먼저 매겨", "앞서 매겨"))

    assert reserved_version("topic", main_text, reworded) == "1.0.1"
    loose = _이력("1.0.2", "1.0.1은 형제 `topic` 몫으로 비웠다.")
    assert reserved_version("topic", loose, _이력("1.0.2", "")) is None


def test_옮길_번호대로_인용을_한_번에_바꾼다() -> None:
    """대기열 249. 차례대로 옮기는 사슬(0027→0028, 0028→0029)도 한 번에 바꿔 0027 이 0029 까지
    가지 않는다. 일지는 번호가 아니라 옮기지 않는다."""
    plan = renumber([Move("ADR", "0027", "0028"), Move("ADR", "0028", "0029")])
    text = (
        "# ADR 0027 제목\n"
        "ADR 0027·0028·0026, [0027](0027-x.md), docs/adr/0028-x.md\r\n"
        "일지 2026-11-07-02, docs/journal/2026-11-07-02-retro-queue-one-file-per-item.md\n"
        "(대기열 135·48·136, 대기열 136의 2회차)\n"
        "| 135 | 행 |\n"
    )
    # 일지 인용, 대기열 인용과 행 머리는 번호가 아니라 이름이라 옮기지 않는다
    expected = (
        "# ADR 0028 제목\n"
        "ADR 0028·0029·0026, [0028](0028-x.md), docs/adr/0029-x.md\r\n"
        "일지 2026-11-07-02, docs/journal/2026-11-07-02-retro-queue-one-file-per-item.md\n"
        "(대기열 135·48·136, 대기열 136의 2회차)\n"
        "| 135 | 행 |\n"
    )

    assert rewrite(text, plan) == expected
    # 더 긴 수의 일부는 번호가 아니다
    longer = "2026-10-07-031, 대기열 1350, ADR 00271, 10027-x, v1.0027-x\n"
    assert rewrite(longer, plan) == longer


def test_일지_이름의_시각_네_자리는_ADR_번호가_아니라_옮기지_않는다() -> None:
    """일지 이름이 시각 꼴(`<날짜>-<HHMM>-<슬러그>.md`)이 되며 시각 `0049` 가 ADR 0049 와 같은 네
    자리가 됐다. 옮기지 않는 일지 경로의 시각을 ADR 번호로 읽어 바꾸면 경로가 죽는다. 옛 순번 꼴은
    두 자리라 걸리지 않았다."""
    plan = renumber([Move("ADR", "0049", "0050")])
    path = "docs/journal/2026-11-08-0049-notes.md"
    text = f"{path}, ADR 0049, [0049](0049-x.md)\n"

    assert rewrite(text, plan) == f"{path}, ADR 0050, [0050](0050-x.md)\n", (
        "일지 이름의 시각 네 자리를 ADR 번호로 옮겼다"
    )


def test_인용_블록의_줄은_원문이라_옮기지_않는다() -> None:
    """일지는 사용자 프롬프트를 원문으로 인용한다(`> 사용자:`). 이 브랜치를 옮긴 첫 `--move` 가 그
    원문의 일지 번호를 새 번호로 바꿨다(일지 2026-10-15-15). 못 보는 것: `>` 없이 이어지는 줄은
    인용 블록이어도 옮긴다."""
    plan = renumber([Move("ADR", "0027", "0028")])
    text = (
        '> 사용자: "ADR 0027의 다음부터, 대기열 2를 닫는다"\n'
        "> ADR 0027\n"
        "이어지는 줄 ADR 0027\n"
        "본문의 ADR 0027, 인용 > ADR 0027\n"
    )

    assert rewrite(text, plan) == (
        '> 사용자: "ADR 0027의 다음부터, 대기열 2를 닫는다"\n'
        "> ADR 0027\n"
        "이어지는 줄 ADR 0028\n"
        "본문의 ADR 0028, 인용 > ADR 0028\n"
    )


def test_줄인_인용은_옮기지_않고_같은_꼴이면_다른_뜻도_옮긴다() -> None:
    """못 보는 것. 줄인 꼴("ADR 27"), 낱말 없이 든 번호는 그대로다. 같은 꼴이면 형제의 같은 번호를
    가리킨 인용도 이 브랜치의 번호로 읽어 옮긴다."""
    plan = renumber([Move("ADR", "0027", "0028")])
    text = "ADR 27, 새로 연 것은 27·28다. 대기열 2를 연다. 형제의 ADR 0027 과 겹쳤다\n"

    assert rewrite(text, plan) == (
        "ADR 27, 새로 연 것은 27·28다. 대기열 2를 연다. 형제의 ADR 0028 과 겹쳤다\n"
    )


def test_티켓_꼴의_인용은_옮기지_않는다() -> None:
    """harness 티켓은 번호가 없는 이름이라 옮길 일이 없다. 옛 꼴(`NNN-<slug>`)의 stem 과 머리 줄,
    `chore/` 브랜치는 ADR 번호가 옮겨도 그대로다."""
    plan = renumber([Move("ADR", "0002", "0003")])
    text = (
        "# 002: 이쪽\n"
        "브랜치 `chore/002-ours`, 파일 .scratch/harness/issues/002-ours.md, 002-ours를 본다\n"
        "티켓 002 와 0002 는 ADR 0002 다\n"
    )

    assert rewrite(text, plan) == text.replace("ADR 0002", "ADR 0003")


def test_gh_가_낸_줄에서_열린_PR의_번호와_본문을_읽는다() -> None:
    """대기열 376. 줄마다 `[번호, 본문]` 의 JSON 이다. 본문이 비면 null 이 온다."""
    text = '[7,"일지 2026-10-07-03\\r\\n둘째 줄"]\n\n[9,null]\n'

    assert pull_bodies(text) == {7: "일지 2026-10-07-03\r\n둘째 줄", 9: ""}
    assert pull_bodies("") == {}
    # 풀지 못한 줄이 하나라도 있으면 읽지 못한 것이다. 일부만 보고 다 봤다고 하지 않는다
    assert pull_bodies('[7,"본문"]\n{"number": 9}\n') is None
    assert pull_bodies("잘린 [7,\n") is None
    assert pull_bodies('["7","본문"]\n') is None


def test_본문에_날것으로_든_U0085와_U2028은_줄을_가르지_않는다() -> None:
    """JSON 은 문자열 안의 그 글자를 이스케이프하지 않아도 된다. `splitlines` 는 그 글자에서도 갈라
    한 PR 의 줄을 둘로 쪼갰다(PR 직전 `bug-perf-review`)."""
    body = f"가{chr(0x85)}나{chr(0x2028)}다{chr(0x2029)}라"

    assert pull_bodies(f'[7,"{body}"]\n') == {7: body}


def test_이_브랜치의_PR_본문은_origin_owner의_head로_REST에서_읽는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """못 보는 것: 포크에서 연 PR 은 head 의 owner 가 달라 걸리지 않는다. gh 가 없거나 실패하면
    None."""
    commands: list[list[str]] = []
    answer: list[subprocess.CompletedProcess[str] | None] = []

    def 띄운다(
        command: list[str], cwd: Path, timeout: float
    ) -> subprocess.CompletedProcess[str] | None:
        commands.append(command)
        return answer[0]

    def gh_가_있다(name: str) -> str:
        return "gh"

    monkeypatch.setattr(sibling_overlap, "_run", 띄운다)
    monkeypatch.setattr(sibling_overlap.shutil, "which", gh_가_있다)
    answer.append(subprocess.CompletedProcess([], 0, '[7,"본문"]\n', ""))

    assert own_pull_bodies(tmp_path, "o", "r", "chore/x") == {7: "본문"}
    endpoint = "repos/o/r/pulls?state=open&head=o:chore%2Fx"
    assert commands == [["gh", "api", endpoint, "--jq", GH_BODY_JQ]]
    answer[0] = subprocess.CompletedProcess([], 1, "", "HTTP 404")
    assert own_pull_bodies(tmp_path, "o", "r", "chore/x") is None
    answer[0] = None  # 띄우지 못했거나 시간을 넘겼다
    assert own_pull_bodies(tmp_path, "o", "r", "chore/x") is None


def test_분리_HEAD면_PR_본문을_묻지_않는다(
    저장소: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """못 보는 것: 분리 HEAD 에는 head 로 든 브랜치가 없어 아무것도 찍지 않는다."""
    _, work, _ = 저장소
    asked: list[str] = []

    def 깃허브다(url: str) -> tuple[str, str]:
        return ("o", "r")

    def 본문을_읽는다(root: Path, owner: str, repo: str, branch: str) -> dict[int, str]:
        asked.append(branch)
        return {}

    monkeypatch.setattr(sibling_overlap, "github_repo", 깃허브다)
    monkeypatch.setattr(sibling_overlap, "own_pull_bodies", 본문을_읽는다)
    shifted = [Move("ADR", "0027", "0028")]

    report_own_pulls(work, shifted)
    assert asked == ["topic"]
    _git(work, "checkout", "-q", "--detach")
    report_own_pulls(work, shifted)
    assert asked == ["topic"]
    assert capsys.readouterr().out == ""


def test_옮길_번호대로_인용이_바뀌는_PR_본문만_옮긴_본문으로_낸다() -> None:
    """대기열 376. 인용 블록은 두고, 대기열 인용과 행의 머리 꼴(`| N |`)은 옮기지 않는다."""
    shifted = [Move("ADR", "0027", "0028")]
    bodies = {
        8: "무관한 본문\n",
        7: "ADR 0027, 대기열 135\r\n> ADR 0027\r\n| 135 | 표 |\r\n",
    }

    assert moved_bodies(bodies, shifted) == {
        7: "ADR 0028, 대기열 135\r\n> ADR 0027\r\n| 135 | 표 |\r\n"
    }


def test_옮긴_본문은_바이트_그대로_쓰고_쓰지_못한_PR은_오류로_든다(tmp_path: Path) -> None:
    """대기열 376. 하나를 쓰지 못해도 멈추지 않고 나머지를 쓴다."""
    (tmp_path / "pr-8-body.md").mkdir()
    moved = {7: "일지 2026-10-07-05\r\n", 8: "막힘", 9: "아홉"}

    written = write_moved_bodies(moved, tmp_path)

    assert written[7] == tmp_path / "pr-7-body.md"
    assert written[9] == tmp_path / "pr-9-body.md"
    assert isinstance(written[8], OSError)
    assert (tmp_path / "pr-7-body.md").read_bytes() == moved[7].encode("utf-8")
    assert write_moved_bodies({}, tmp_path) == {}


def test_PR_본문의_줄은_옮긴_본문의_파일과_올리는_명령을_든다(tmp_path: Path) -> None:
    """대기열 376. 명령은 클라우드에서도 도는 REST 다. 쓰지 못한 PR 만 손으로 고치라고 한다. 명령이
    본문 전체를 덮어쓰므로 올리기 전에 지금 본문과 견주라고 명령 앞에 적고, 명령은 줄 끝에 두어
    그 뒤를 그대로 붙여 넣을 수 있게 한다(PR #328 CodeRabbit·셀프 리뷰)."""
    path = tmp_path / "pr-7-body.md"
    bodies = {7: "일지 2026-10-07-03\r\n", 8: "무관\n", 9: "일지 2026-10-07-03\n"}

    lines = pull_body_lines(bodies, {7: path, 9: PermissionError("막혔다")}, ("o", "r"))

    assert lines == [
        f"이 브랜치의 열린 PR #7 본문에 옮기기 전 번호가 있다. 옮긴 본문을 {path.as_posix()} 에"
        " 썼다. 올리는 명령은 본문 전체를 이 파일로 덮어쓴다. 올리기 전에 지금 본문을 다시 읽어"
        " 이 파일과 견주고, 옮긴 번호 밖의 차이(읽은 뒤에 사람·봇·세션이 고친 것)가 있으면 이"
        " 파일에도 넣는다. 올리는 명령: gh api repos/o/r/pulls/7 --method PATCH -F"
        f' "body=@{path.as_posix()}"',
        "이 브랜치의 열린 PR #8 본문에는 옮길 인용이 없다",
        "이 브랜치의 열린 PR #9 본문에 옮기기 전 번호가 있다. 옮긴 본문을 쓰지 못했다(막혔다)."
        " 손으로 고친다",
    ]
    command = f'gh api repos/o/r/pulls/7 --method PATCH -F "body=@{path.as_posix()}"'
    assert lines[0].endswith(f"올리는 명령: {command}")
    assert pull_body_lines({}, {}, ("o", "r")) == []
    assert pull_body_lines(None, {}, ("o", "r")) == [
        "이 브랜치의 열린 PR 본문을 읽지 못했다(gh 가 없거나 `gh api` 가 실패했다). PR 본문에"
        " 옮기기 전 번호가 남았는지 손으로 본다"
    ]


def test_옮기기는_코드_스팬과_펜스_안의_같은_꼴도_옮긴다() -> None:
    """못 보는 것. 파일 이름 인용(`docs/adr/…`)이 대개 코드 스팬 안에 있어 그 자리도 옮긴다."""
    plan = renumber([Move("ADR", "0027", "0028")])
    text = "`docs/adr/0027-a.md`, 처음 `ADR 0027`\n```\n0027-x.md\n```\n"

    assert rewrite(text, plan) == ("`docs/adr/0028-a.md`, 처음 `ADR 0028`\n```\n0028-x.md\n```\n")


def test_옮기기는_이_브랜치가_고친_글만_고치고_이름을_바꾸며_자리가_차_있으면_멈춘다(
    tmp_path: Path,
) -> None:
    adr = "docs/adr/0002-ours.md"
    files = {
        # 줄 끝은 바이트 그대로 둔다(`write_text` 는 윈도에서 줄 끝을 바꿔 바이트로 쓴다)
        adr: "# 이쪽\r\nADR 0002, 대기열 2\r\n",
        # 대기열 인용은 번호가 아니라 항목의 이름이라 옮기지 않는다
        ".scratch/retro-queue/0002.md": "# 0002: 이쪽\n\n대기열 2\n",
        # 둘 줄(`kept`)을 주지 않으면 merge-base 에 있던 줄도 옮긴다. CLI 는 merge-base 와 main 의
        # 줄을 준다
        "docs/notes.md": "merge-base 에 있던 줄의 ADR 0002\n이 브랜치가 더한 줄\n",
        "README.md": "ADR 0002\n",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    binary = b"\xff\xfeADR 0002"  # UTF-8 이 아니라 인용 꼴이 있어도 두는 파일
    (tmp_path / "logo.png").write_bytes(binary)
    ours = _번호(adrs={"0002": "0002-ours.md"})
    shifted = [Move("ADR", "0002", "0003")]
    changed = [
        adr,
        ".scratch/retro-queue/0002.md",
        "docs/notes.md",
        "logo.png",
        "gone.md",
    ]

    plan = plan_moves(tmp_path, ours, shifted, changed)

    assert plan.renames == [(adr, "docs/adr/0003-ours.md")]
    moved_adr = "# 이쪽\r\nADR 0003, 대기열 2\r\n"
    assert plan.texts == {
        adr: moved_adr,
        "docs/notes.md": "merge-base 에 있던 줄의 ADR 0003\n이 브랜치가 더한 줄\n",
    }
    assert plan.originals == {path: files[path].encode() for path in plan.texts}

    apply_moves(tmp_path, plan)

    assert not (tmp_path / adr).exists()
    assert (tmp_path / "docs/adr/0003-ours.md").read_bytes() == moved_adr.encode("utf-8")
    assert (tmp_path / "README.md").read_bytes() == b"ADR 0002\n"
    assert (tmp_path / "logo.png").read_bytes() == binary

    blocked = _번호(adrs={"0003": "0003-ours.md"})
    (tmp_path / "docs/adr/0004-ours.md").mkdir()
    with pytest.raises(MoveError, match="docs/adr/0004-ours.md"):
        plan_moves(tmp_path, blocked, [Move("ADR", "0003", "0004")], ["docs/adr/0003-ours.md"])


def test_옮길_자리가_다른_옮길_파일이면_그_파일을_먼저_옮긴다(tmp_path: Path) -> None:
    """반박 검증(일지 2026-10-15-15): 같은 슬러그의 사슬 02-x, 03-x 를 03, 04 로 옮길 때 03-x 를
    "이미 무엇이 있다" 로 거절했다. 지금은 ADR 0002-x, 0003-x 를 0003, 0004 로 옮긴다."""
    adrs = {f"000{n}": f"000{n}-x.md" for n in (2, 3)}
    for name in adrs.values():
        (tmp_path / ADR_DIR).mkdir(parents=True, exist_ok=True)
        (tmp_path / ADR_DIR / name).write_bytes(f"# {name}\n".encode())
    shifted = [Move("ADR", "0002", "0003"), Move("ADR", "0003", "0004")]

    plan = plan_moves(tmp_path, _번호(adrs=adrs), shifted, [])

    assert plan.renames == [
        (f"{ADR_DIR}/0003-x.md", f"{ADR_DIR}/0004-x.md"),
        (f"{ADR_DIR}/0002-x.md", f"{ADR_DIR}/0003-x.md"),
    ]

    apply_moves(tmp_path, plan)

    assert sorted(path.name for path in (tmp_path / ADR_DIR).iterdir()) == [
        "0003-x.md",
        "0004-x.md",
    ]
    first = (tmp_path / ADR_DIR / "0003-x.md").read_bytes()
    assert first == b"# 0002-x.md\n"
    # 순환은 옮김에서 나오지 않지만, 들어오면 끝나지 않는 대신 멈춘다
    with pytest.raises(MoveError, match="서로 자리를 맞바꾸는"):
        vacating_first([("a.md", "b.md"), ("b.md", "a.md")])


def test_심볼릭_링크는_따라가_쓰지_않는다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """반박 검증(일지 2026-10-15-15): 이 브랜치의 변경에 든 링크를 따라가 저장소 밖의 파일을 고쳤다.

    링크를 만드는 권한이 없는 윈도에서도 돌도록 `is_symlink` 를 바꿔 끼운다.
    """
    (tmp_path / "link.md").write_bytes(b"ADR 0002\n")
    (tmp_path / "plain.md").write_bytes(b"ADR 0002\n")
    real = Path.is_symlink

    def 링크다(self: Path) -> bool:
        return self.name == "link.md" or real(self)

    monkeypatch.setattr(Path, "is_symlink", 링크다)

    shifted = [Move("ADR", "0002", "0003")]
    ours = _번호(adrs={"0002": "0002-x.md"})
    plan = plan_moves(tmp_path, ours, shifted, ["link.md", "plain.md"])

    assert list(plan.texts) == ["plain.md"]


def _옮길_파일들(root: Path) -> MovePlan:
    """옛 글 둘을 고치고 이름 둘을 바꾸는 계획. 둘째 이름은 없는 폴더로 가 바꾸다 멈춘다."""
    for name in ("a.md", "b.md"):
        (root / name).write_bytes(f"{name} 의 옛 글\r\n".encode())
    return MovePlan(
        renames=[("a.md", "a2.md"), ("b.md", "없는-폴더/b2.md")],
        texts={"a.md": "a 의 새 글\n", "b.md": "b 의 새 글\n"},
        originals={name: f"{name} 의 옛 글\r\n".encode() for name in ("a.md", "b.md")},
    )


def test_옮기다_멈추면_고친_것을_거꾸로_되돌린다(tmp_path: Path) -> None:
    """셀프 리뷰 표준 축의 Major: 되돌리지 않고 다시 치면 이미 옮긴 인용이 사슬을 따라 한 번 더
    옮겨진다."""
    plan = _옮길_파일들(tmp_path)

    with pytest.raises(MoveError, match="모두 되돌렸다") as raised:
        apply_moves(tmp_path, plan)

    assert not isinstance(raised.value, StuckMoveError)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a.md", "b.md"]
    for name in ("a.md", "b.md"):
        assert (tmp_path / name).read_bytes() == plan.originals[name]


def test_되돌리지_못하면_남은_것을_든다(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """첫 이름 바꾸기만 되고 그 뒤의 이름 바꾸기(되돌리기 포함)가 모두 실패하는 디스크."""
    plan = _옮길_파일들(tmp_path)
    real = Path.rename
    calls: list[str] = []

    def 처음만_된다(self: Path, target: Path) -> Path:
        calls.append(self.name)
        if len(calls) > 1:
            raise PermissionError(f"{self.name} 을 쥔 프로세스가 있다")
        return real(self, target)

    monkeypatch.setattr(Path, "rename", 처음만_된다)

    with pytest.raises(StuckMoveError) as raised:
        apply_moves(tmp_path, plan)

    # a.md 는 a2.md 에서 돌아오지 못했고 그 글도 되쓰지 않았다(옛 이름에 쓰면 사본이 생긴다)
    assert "a2.md → a.md" in str(raised.value) and ", a.md" in str(raised.value)
    assert not (tmp_path / "a.md").exists()
    assert (tmp_path / "a2.md").read_bytes() == "a 의 새 글\n".encode()
    assert (tmp_path / "b.md").read_bytes() == plan.originals["b.md"]


def test_되돌리지_못한_파일의_옛_자리에_다른_것이_있어도_덮지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """옛 자리가 비었으면 읽기가 실패해 되쓰지 않지만, 같은 슬러그의 사슬에서는 다른 옮길 파일이
    그 자리에 있을 수 있다. 그 위에 옛 바이트를 쓰면 남의 글을 덮는다."""
    plan = _옮길_파일들(tmp_path)
    real = Path.rename
    calls: list[str] = []
    other = "a.md 자리에 든 다른 파일\n".encode()

    def 처음만_되고_옛_자리가_찬다(self: Path, target: Path) -> Path:
        calls.append(self.name)
        if len(calls) > 1:
            if self.name == "a2.md":
                (tmp_path / "a.md").write_bytes(other)
            raise PermissionError(f"{self.name} 을 쥔 프로세스가 있다")
        return real(self, target)

    monkeypatch.setattr(Path, "rename", 처음만_되고_옛_자리가_찬다)

    with pytest.raises(StuckMoveError):
        apply_moves(tmp_path, plan)

    assert (tmp_path / "a.md").read_bytes() == other
    assert (tmp_path / "a2.md").read_bytes() == "a 의 새 글\n".encode()


def test_쓰다_멈춘_파일도_옛_바이트로_되돌린다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR 직전 버그 축의 Major: `write_bytes` 는 파일을 먼저 비우고 쓰는데, 쓰기를 마친 파일만
    되돌려 쓰다 멈춘 파일은 잘린 채 남고 "모두 되돌렸다" 로 끝났다. 미추적 파일이면 git 으로도
    되돌릴 수 없다."""
    plan = _옮길_파일들(tmp_path)
    real = Path.write_bytes
    failed: list[str] = []

    def b_는_쓰다_멈춘다(self: Path, data: bytes) -> int:
        if self.name == "b.md" and not failed:
            failed.append(self.name)
            real(self, data[:2])
            raise OSError(28, "디스크가 찼다")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", b_는_쓰다_멈춘다)

    with pytest.raises(MoveError, match="모두 되돌렸다") as raised:
        apply_moves(tmp_path, plan)

    assert failed == ["b.md"]
    assert not isinstance(raised.value, StuckMoveError)
    for name in ("a.md", "b.md"):
        assert (tmp_path / name).read_bytes() == plan.originals[name]


def test_열지도_못한_파일은_되쓰지_않아_남은_것으로_들지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """쓰기 전에 되돌릴 목록에 올리므로, 열지도 못한 파일(그대로다)을 되쓰다 또 실패해 되돌리지
    못한 것으로 들면 안 된다."""
    plan = _옮길_파일들(tmp_path)
    real = Path.write_bytes

    def b_는_열지_못한다(self: Path, data: bytes) -> int:
        if self.name == "b.md":
            raise PermissionError("b.md 를 쥔 프로세스가 있다")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", b_는_열지_못한다)

    with pytest.raises(MoveError, match="모두 되돌렸다") as raised:
        apply_moves(tmp_path, plan)

    assert not isinstance(raised.value, StuckMoveError)
    for name in ("a.md", "b.md"):
        assert (tmp_path / name).read_bytes() == plan.originals[name]


def test_BOM으로_시작하는_파일도_첫_줄의_인용_블록을_지키고_BOM을_지킨다() -> None:
    """PR 직전 버그 축: BOM 이 `^` 를 막아 첫 줄만 규칙에서 벗어났다. BOM 을 떼고 바꾼 뒤 다시
    붙인다."""
    plan = renumber([Move("ADR", "0027", "0028")])
    bom = chr(0xFEFF)
    text = f"{bom}> 사용자: ADR 0027\r\nADR 0027\r\n"

    assert rewrite(text, plan) == f"{bom}> 사용자: ADR 0027\r\nADR 0028\r\n"


def test_merge_base나_main에_글자_그대로_있는_줄은_옮기지_않는다() -> None:
    """PR 직전 버그 축: main 을 합치다 같은 번호의 줄 둘을 남긴 채 옮기면 main 의 색인 행까지
    옮겨졌다. main 에 이미 있던 같은 번호의 참조는 상대를 가리킨다(`.claude/rules/adr.md`). 그
    줄을 이 브랜치가 고쳤으면 글자가 달라져 옮긴다."""
    plan = renumber([Move("ADR", "0027", "0028")])
    main_index = "- [0027](0027-sibling.md) 형제"
    kept = frozenset({main_index})
    index = f"{main_index}\n- [0027](0027-ours.md) 이쪽\n- [0027](0027-sibling.md) 형제(고침)\n"

    assert rewrite(index, plan, kept) == (
        f"{main_index}\n- [0028](0028-ours.md) 이쪽\n- [0028](0028-sibling.md) 형제(고침)\n"
    )


def test_CRLF_파일의_둘_줄도_줄_끝의_CR을_빼고_견주어_글자가_같으면_옮기지_않는다() -> None:
    """윈도에서 CRLF 로 체크아웃한 파일의 줄은 `\\r` 로 끝나지만 둘 줄 집합(`_kept_lines`)은 CR 을
    뺀 줄이다. CR 을 떼지 않고 견주면 main 의 줄이 둘 줄과 달라 옮겨지고, 줄 끝은 CR 이 남는다."""
    plan = renumber([Move("ADR", "0027", "0028")])
    main_index = "- [0027](0027-sibling.md) 형제"
    kept = frozenset({main_index})
    index = f"{main_index}\r\n- [0027](0027-ours.md) 이쪽\r\n"

    assert rewrite(index, plan, kept) == (f"{main_index}\r\n- [0028](0028-ours.md) 이쪽\r\n")


def test_되돌리지_못하면_move_를_다시_치지_말라고_한다(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def 멈춘다(start: Path) -> tuple[Survey, Verdict]:
        raise StuckMoveError("옮기다 멈췄고 되돌리지 못한 것이 있다: a2.md → a.md")

    monkeypatch.setattr(sibling_overlap, "_move_and_check", 멈춘다)

    code = main(["--move"])

    err = capsys.readouterr().err
    assert code == 2
    assert "a2.md → a.md" in err
    assert ON_STUCK in err and ON_FAILURE not in err


# --- 임시 원격과 클론 ---------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _쓴다(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _커밋한다(root: Path, files: dict[str, str], message: str) -> str:
    _쓴다(root, files)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _헌법(version: str) -> str:
    return f"# 헌법\n\n**Version**: {version} | **Ratified**: 2026-09-19\n"


SEED = {
    "docs/journal/2026-10-07-01-seed.md": "씨앗\n",
    "docs/adr/0001-seed.md": "씨앗\n",
    "docs/adr/README.md": "색인\n",
    "docs/constitution/README.md": _헌법("1.0.0"),
    "docs/constitution/operations.md": "운영\n",
    "README.md": "읽어 보기\n",
    "CLAUDE.md": "지침\n",
}


def _원격과_클론(tmp_path: Path, seed: dict[str, str]) -> tuple[Path, Path, Path]:
    """(원격, 작업 클론, 원격에 밀어 넣는 다른 클론). 작업 클론은 씨앗 커밋의 `topic` 에 있다."""
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    pusher = tmp_path / "pusher"
    _git(tmp_path, "clone", "-q", str(remote), str(pusher))
    _git(pusher, "checkout", "-q", "-b", "main")
    _커밋한다(pusher, seed, "씨앗")
    _git(pusher, "push", "-q", "origin", "main")
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _git(work, "checkout", "-q", "-b", "topic")
    return remote, work, pusher


@pytest.fixture
def 저장소(tmp_path: Path) -> tuple[Path, Path, Path]:
    return _원격과_클론(tmp_path, SEED)


def _PR을_민다(pusher: Path, number: int, files: dict[str, str]) -> str:
    """origin/main 위에 커밋 하나를 지어 `refs/pull/<번호>/head` 로 민다. merge ref 는 없다."""
    _git(pusher, "checkout", "-q", "-b", f"pr{number}", "origin/main")
    sha = _커밋한다(pusher, files, f"PR {number}")
    _git(pusher, "push", "-q", "origin", f"{sha}:refs/pull/{number}/head")
    _git(pusher, "checkout", "-q", "main")
    return sha


def _연다(cwd: Path, number: int, sha: str) -> None:
    """GitHub 이 열린 PR 에 두는 merge ref 를 흉내 낸다. 판정에는 있는지만 쓰인다."""
    _git(cwd, "push", "-q", "origin", f"{sha}:refs/pull/{number}/merge")


def _워크트리의_PR을_민다(work: Path, name: str, number: int, files: dict[str, str]) -> Path:
    """origin/main 위의 형제 워크트리에 커밋해 `refs/pull/<번호>/head` 로 민다. merge ref 없이."""
    path = work.parent / name
    _git(work, "worktree", "add", "-q", "-b", name, str(path), "origin/main")
    sha = _커밋한다(path, files, f"PR {number}")
    _git(path, "push", "-q", "origin", f"{sha}:refs/pull/{number}/head")
    return path


def _CLI를_부른다(work: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), str(work)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_열린_PR과_겹치면_알리고_1로_끝나며_닫힌_PR은_보지_않는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, pusher = 저장소
    pr5 = _PR을_민다(
        pusher,
        5,
        {
            "docs/adr/0003-pr.md": "그쪽\n",
            "docs/constitution/README.md": _헌법("1.0.1"),
            "CLAUDE.md": "그쪽 지침\n",
        },
    )
    _연다(pusher, 5, pr5)
    _PR을_민다(pusher, 4, {"docs/adr/0002-closed.md": "닫힘\n"})
    _쓴다(
        work,
        {
            "docs/adr/0002-ours.md": "이쪽\n",
            "docs/adr/0003-ours.md": "이쪽\n",
            "docs/constitution/README.md": _헌법("1.0.1"),
            "CLAUDE.md": "이쪽 지침\n",
        },
    )

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1
    assert "열린 PR 을 읽은 길: merge ref" in out
    assert "이 브랜치의 새 번호: ADR 0002, ADR 0003, 헌법 1.0.1" in out
    assert "PR #5 ADR 0003: 이 브랜치 0003-ours.md, 그쪽 0003-pr.md" in out
    assert "PR #5 헌법 1.0.1" in out
    assert "PR #4" not in out and "ADR 0002:" not in out
    assert "옮길 번호: ADR 0002 → 0004, ADR 0003 → 0005\n" in out
    assert "PR #5: CLAUDE.md, docs/constitution/README.md" in out


def test_gh_api가_읽은_열린_PR은_merge_ref가_없어도_형제다(
    저장소: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """열 때부터 충돌한 PR 처럼 merge ref 가 없어도, gh 가 열려 있다고 하면 대조한다.

    그 PR 의 head 에 선 형제 워크트리도 닫힌 PR 의 것으로 접지 않는다(대기열 194).
    """
    _, work, pusher = 저장소
    pr6 = _PR을_민다(pusher, 6, {"docs/adr/0002-pr.md": "그쪽\n", "README.md": "그쪽\n"})
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n", "README.md": "이쪽\n"})
    _git(work, "fetch", "-q", "origin", "refs/pull/6/head")
    sibling = work.parent / "pr6"
    _git(work, "worktree", "add", "-q", "-b", "pr6", str(sibling), pr6)

    def 깃허브다(url: str) -> tuple[str, str]:
        return ("o", "r")

    def gh_가_연다(root: Path, owner: str, repo: str) -> str:
        return f"6 {pr6}\n"

    monkeypatch.setattr(sibling_overlap, "github_repo", 깃허브다)
    monkeypatch.setattr(sibling_overlap, "gh_listing", gh_가_연다)

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1
    assert "열린 PR 을 읽은 길: gh api\n" in out
    assert "PR #6 ADR 0002: 이 브랜치 0002-ours.md, 그쪽 0002-pr.md" in out
    assert f"- 워크트리 {sibling.resolve()}: README.md\n" in out
    assert "닫힌 워크트리" not in out


def test_main이_이_브랜치_뒤에_들인_번호와_겹치면_CLI가_알린다(
    저장소: tuple[Path, Path, Path],
) -> None:
    _, work, pusher = 저장소
    _커밋한다(pusher, {"docs/adr/0002-main.md": "main\n"}, "main 이 나아간다")
    _git(pusher, "push", "-q", "origin", "main")
    pr9 = _PR을_민다(pusher, 9, {"docs/notes.md": "새 main 위\n"})
    _연다(pusher, 9, pr9)
    _커밋한다(pusher, {"docs/adr/0003-main.md": "main\n"}, "main 이 PR #9 뒤로 더 나아간다")
    _git(pusher, "push", "-q", "origin", "main")
    _커밋한다(work, {"docs/adr/0002-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 1, result.stderr
    assert "origin/main ADR 0002: 이 브랜치 0002-ours.md, 그쪽 0002-main.md" in result.stdout
    # 새 main 위의 PR #9 는 main 의 번호를 되풀이하지 않는다
    assert result.stdout.count("ADR 0002:") == 1
    assert "옮길 번호: ADR 0002 → 0004\n" in result.stdout
    # CLI 로 부른 출력도 다음 빈 번호를 찍지 않는다. harness 티켓에는 번호가 없다
    assert "다음 빈 번호" not in result.stdout


def test_형제_워크트리의_커밋하지_않은_번호와_겹치면_알린다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, _ = 저장소
    sibling = work.parent / "sibling"
    _git(work, "worktree", "add", "-q", "-b", "other", str(sibling), "origin/main")
    probe = ".scratch/새-프로브.md"  # 미추적이고, git 이 따옴표로 감싸는 이름이다
    _쓴다(sibling, {"docs/adr/0002-sibling.md": "형제\n", probe: "형제\n"})
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n", probe: "이쪽\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1
    assert f"워크트리 {sibling.resolve()} ADR 0002" in out
    assert f"워크트리 {sibling.resolve()}: {probe}\n" in out


def test_PR이_닫힌_형제_워크트리는_커밋하지_않은_변경만_견주고_형제_줄에서_접는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 194: squash 병합 뒤 남은 워크트리가 "함께 고친 파일" 을 채워 열린 PR 의 줄을 묻었다.

    임시 원격은 github.com 이 아니라 열린 PR 을 merge ref 로 가린다. 그래서 merge ref 없이 민 PR 이
    닫힌 PR 이다. 열 때부터 충돌해 merge ref 가 없는 열린 PR 의 워크트리도 접는다(못 보는 것).
    """
    _, work, pusher = 저장소
    _쓴다(work, {"README.md": "이쪽\n", "CLAUDE.md": "이쪽 지침\n"})
    merged = _워크트리의_PR을_민다(work, "merged", 3, {"README.md": "병합\n"})
    dirty = _워크트리의_PR을_민다(work, "dirty", 4, {"CLAUDE.md": "병합\n"})
    _쓴다(dirty, {"README.md": "커밋하지 않았다\n"})
    # 닫힌 PR 의 head 뒤에 커밋을 더한 워크트리는 접지 않는다. HEAD 가 같을 때만 접는다
    later = _워크트리의_PR을_민다(work, "later", 6, {"README.md": "닫힌 뒤\n"})
    _커밋한다(later, {"CLAUDE.md": "더 했다\n"}, "닫힌 뒤의 커밋")
    # head 까지 따라가지 않은 워크트리도 접지 않는다. 병합된 커밋이 나온다(못 보는 것)
    behind = _워크트리의_PR을_민다(work, "behind", 7, {"README.md": "앞 커밋\n"})
    pr7 = _커밋한다(behind, {"CLAUDE.md": "뒤 커밋\n"}, "PR 7 의 둘째 커밋")
    _git(behind, "push", "-q", "origin", f"+{pr7}:refs/pull/7/head")
    _git(behind, "reset", "-q", "--hard", "HEAD~1")
    pr5 = _PR을_민다(pusher, 5, {"README.md": "열림\n"})
    _연다(pusher, 5, pr5)

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert ", PR 이 닫힌 워크트리 2곳(커밋하지 않은 변경만 견준다)\n" in out
    assert str(merged.resolve()) not in out
    assert f"- 워크트리 {dirty.resolve()}(PR #4 닫힘): README.md\n" in out
    assert f"- 워크트리 {later.resolve()}: CLAUDE.md, README.md\n" in out
    assert f"- 워크트리 {behind.resolve()}: README.md\n" in out
    assert "- PR #5: README.md\n" in out


def _gh_가_연다(monkeypatch: pytest.MonkeyPatch, pulls: dict[int, str]) -> None:
    """원격을 github.com 으로 보이게 하고, gh 가 `pulls` 를 열린 PR 로 읽게 한다."""

    def 깃허브다(url: str) -> tuple[str, str]:
        return ("o", "r")

    def gh_가_읽는다(root: Path, owner: str, repo: str) -> str:
        return "".join(f"{number} {sha}\n" for number, sha in pulls.items())

    monkeypatch.setattr(sibling_overlap, "github_repo", 깃허브다)
    monkeypatch.setattr(sibling_overlap, "gh_listing", gh_가_읽는다)


def test_head_ref가_아직_없는_열린_PR은_head_커밋을_받아_대조한다(
    저장소: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """대기열 288: PR 을 연 지 몇 분 안에는 gh 가 열린 PR 을 읽어도 `refs/pull/<N>/head` 가 원격에
    아직 없어, 그 ref 를 받는 fetch 가 128로 끝나 대조 전체가 2로 멈췄다. head 커밋은 브랜치에
    있다."""
    _, work, pusher = 저장소
    _git(pusher, "checkout", "-q", "-b", "pr7", "origin/main")
    pr7 = _커밋한다(pusher, {"docs/adr/0002-pr.md": "그쪽\n"}, "PR 7")
    _git(pusher, "push", "-q", "origin", "pr7")  # 브랜치만 있고 refs/pull/7/head 는 없다
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n"})
    _gh_가_연다(monkeypatch, {7: pr7})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "PR #7 ADR 0002: 이 브랜치 0002-ours.md, 그쪽 0002-pr.md" in out
    assert "받지 못해 대조에서 뺀" not in out


def test_head_커밋을_받지_못한_열린_PR만_형제에서_빼고_알린다(
    저장소: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """head 커밋이 원격 어디에서도 닿지 않으면 그 PR 만 빼고 나머지 형제는 그대로 대조한다."""
    _, work, pusher = 저장소
    _git(pusher, "checkout", "-q", "-b", "pr8", "origin/main")
    pr8 = _커밋한다(pusher, {"docs/adr/0002-pr8.md": "밀지 않았다\n"}, "PR 8")
    _git(pusher, "checkout", "-q", "main")
    pr5 = _PR을_민다(pusher, 5, {"docs/adr/0002-pr5.md": "그쪽\n"})
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n"})
    _gh_가_연다(monkeypatch, {5: pr5, 8: pr8})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "PR #5 ADR 0002: 이 브랜치 0002-ours.md, 그쪽 0002-pr5.md" in out
    assert "PR #8 ADR" not in out and f"PR #8 {pr8[:7]}" not in out
    assert "받지 못해 대조에서 뺀 열린 PR: #8(" in out
    assert "다시 쳐도 같으면 기다리지 않는다" in out  # 포크처럼 기다려도 받아지지 않는 갈래


def test_head_커밋을_받지_못한_열린_PR만_있으면_그_PR과_겹쳐도_0으로_끝난다(
    저장소: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """못 보는 것: 뺀 PR 과의 번호 겹침은 보지 않아, 남은 형제로 0으로 끝난다."""
    _, work, pusher = 저장소
    _git(pusher, "checkout", "-q", "-b", "pr8", "origin/main")
    pr8 = _커밋한다(pusher, {"docs/adr/0002-pr8.md": "밀지 않았다\n"}, "PR 8")
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n"})
    _gh_가_연다(monkeypatch, {8: pr8})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "받지 못해 대조에서 뺀 열린 PR: #8(" in out


def test_head_ref가_gh가_읽은_head보다_옛것인_열린_PR은_head_커밋을_받아_대조한다(
    저장소: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """원격의 `refs/pull/<N>/head` 가 아직 브랜치의 앞 커밋에 머물면 그 ref 로는 head 가 오지
    않는다."""
    _, work, pusher = 저장소
    _PR을_민다(pusher, 9, {"docs/before.md": "앞 커밋\n"})
    _git(pusher, "checkout", "-q", "pr9")
    pr9 = _커밋한다(pusher, {"docs/adr/0002-pr9.md": "그쪽\n"}, "PR 9 의 둘째 커밋")
    _git(pusher, "push", "-q", "origin", "pr9")  # refs/pull/9/head 는 앞 커밋에 머문다
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n"})
    _gh_가_연다(monkeypatch, {9: pr9})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "PR #9 ADR 0002: 이 브랜치 0002-ours.md, 그쪽 0002-pr9.md" in out
    assert "받지 못해 대조에서 뺀" not in out


def test_head_커밋을_sha로_받는_fetch가_시간을_넘기면_대조_전체가_2로_멈춘다(
    저장소: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """못 보는 것: 시간을 넘긴 fetch 는 받지 못한 것으로 세지 않는다."""
    _, work, pusher = 저장소
    _git(pusher, "checkout", "-q", "-b", "pr8", "origin/main")
    pr8 = _커밋한다(pusher, {"docs/adr/0002-pr8.md": "밀지 않았다\n"}, "PR 8")
    _gh_가_연다(monkeypatch, {8: pr8})
    original = subprocess.run

    def sha_받기가_멈춘다(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        encoding: str,
        errors: str,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        """도구의 `subprocess.run` 호출 모양만 받는다. 그 밖의 호출이 오면 TypeError 로 드러난다."""
        if "fetch" in command and command[-1] == pr8:
            raise subprocess.TimeoutExpired(command, timeout)
        return original(
            command,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            encoding=encoding,
            errors=errors,
            timeout=timeout,
            check=check,
        )

    monkeypatch.setattr(subprocess, "run", sha_받기가_멈춘다)

    code = main([str(work)])

    captured = capsys.readouterr()
    assert code == 2, captured.out
    assert "git fetch 을 띄우지 못했거나" in captured.err


def test_원격을_읽은_뒤_head_ref가_사라지면_대조_전체가_2로_멈춘다(
    저장소: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """못 보는 것: `ls-remote` 에 있던 ref 를 받는 fetch 가 실패하면 sha 길로 내려가지 않는다."""
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {"docs/adr/0002-pr5.md": "그쪽\n"})
    _gh_가_연다(monkeypatch, {5: pr5})
    original = sibling_overlap.read_remote

    def 읽은_뒤_ref를_지운다(root: Path) -> sibling_overlap.Remote:
        remote = original(root)
        _git(pusher, "push", "-q", "origin", ":refs/pull/5/head")
        return remote

    monkeypatch.setattr(sibling_overlap, "read_remote", 읽은_뒤_ref를_지운다)

    code = main([str(work)])

    captured = capsys.readouterr()
    assert code == 2, captured.out
    assert "git fetch (종료 128)" in captured.err


def test_main을_합치는_중인_형제_워크트리에서_main과_같은_파일은_함께_고친_파일이_아니다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 294: main 을 합치고 커밋하기 전인 형제의 작업 트리에는 main 의 변경이 보여, 디스크
    사본이 origin/main 과 글자가 같은 파일을 그 형제가 함께 고친 파일로 냈다.

    미추적 파일은 main 과 글자가 같아도 센다(못 보는 것).
    """
    _, work, pusher = 저장소
    sibling = work.parent / "merging"
    _git(work, "worktree", "add", "-q", "-b", "merging", str(sibling), "origin/main")
    _커밋한다(sibling, {"CLAUDE.md": "형제 지침\n"}, "형제의 일")
    _커밋한다(pusher, {"README.md": "main 이 고쳤다\n", "docs/new.md": "main 의 새 파일\n"}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    _git(sibling, "merge", "-q", "--no-commit", "--no-ff", "origin/main")
    # 합친 뒤 main 이 더한 파일을 형제가 손으로 옮겨 두었다(미추적)
    _커밋한다(pusher, {"docs/later.md": "main 이 뒤에 더했다\n"}, "main 이 더 나아간다")
    _git(pusher, "push", "-q", "origin", "main")
    _쓴다(sibling, {"docs/later.md": "main 이 뒤에 더했다\n"})
    _쓴다(
        work,
        {
            "README.md": "이쪽\n",
            "CLAUDE.md": "이쪽 지침\n",
            "docs/new.md": "이쪽 새 파일\n",
            "docs/later.md": "이쪽\n",
        },
    )

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert f"- 워크트리 {sibling.resolve()}: CLAUDE.md, docs/later.md\n" in out


def test_PR이_닫힌_형제_워크트리가_main을_합치는_중이면_main과_같은_파일은_함께_고친_파일이_아니다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 294 의 가름은 PR 이 닫힌 워크트리의 갈래(닫힌 head 뒤에 커밋하지 않은 변경)에도
    쓴다."""
    _, work, pusher = 저장소
    closed = _워크트리의_PR을_민다(work, "closed", 4, {"CLAUDE.md": "병합\n"})
    _커밋한다(pusher, {"README.md": "main 이 고쳤다\n"}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    _git(closed, "merge", "-q", "--no-commit", "--no-ff", "origin/main")
    _쓴다(closed, {"docs/dirty.md": "커밋하지 않았다\n"})
    _쓴다(work, {"README.md": "이쪽\n", "docs/dirty.md": "이쪽\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert f"- 워크트리 {closed.resolve()}(PR #4 닫힘): docs/dirty.md\n" in out


def test_PR이_닫힌_형제_워크트리의_번호는_접지_않고_대조한다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 205 의 길: 받은 번호로 만든 ADR 파일은 PR 이 닫힌 워크트리에 있어도 찬 번호다."""
    _, work, _ = 저장소
    closed = _워크트리의_PR을_민다(work, "closed", 3, {"README.md": "병합\n"})
    _쓴다(closed, {"docs/adr/0002-closed.md": "형제\n"})
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert f"워크트리 {closed.resolve()}(PR #3 닫힘) ADR 0002" in out


def test_형제가_쓴_가장_높은_헌법_판과_그_자리를_찍는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 199: 판을 올리기 전의 대조는 겹침을 못 알려, 올린 뒤에야 형제의 판과 겹친 것을 알았다.

    판은 고르지 않는다. 올림의 종류는 바뀐 내용이 정한다. 형제 워크트리는 커밋하지 않은 판도 본다.
    """
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {"docs/constitution/README.md": _헌법("1.0.10")})
    _연다(pusher, 5, pr5)
    sibling = work.parent / "sibling"
    _git(work, "worktree", "add", "-q", "-b", "other", str(sibling), "origin/main")
    _쓴다(sibling, {"docs/constitution/README.md": _헌법("1.0.9")})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "형제가 쓴 가장 높은 헌법 판: 1.0.10(PR #5). 판을 올리면 이보다 높게 고른다\n" in out

    _쓴다(sibling, {"docs/constitution/README.md": _헌법("1.1.0")})
    # 이 브랜치의 판이 형제의 판보다 낮아도 찍기만 한다(못 보는 것). 같은 판만 겹침이다
    _쓴다(work, {"docs/constitution/README.md": _헌법("1.0.11")})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert f"형제가 쓴 가장 높은 헌법 판: 1.1.0(워크트리 {sibling.resolve()})." in out
    assert "이 브랜치의 새 번호: 헌법 1.0.11" in out


def test_헌법_파일을_고치고_판을_올리지_않으면_1로_끝나고_올리면_0이다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 224: `operations.md` 를 고치고 판을 올리지 않은 것을 셀프 리뷰가 잡았다.

    헌법 파일은 어느 변경이든 판을 올린다(원칙 변경은 major, 절 추가는 minor, 문구 수정은 patch).
    """
    _, work, _ = 저장소
    _쓴다(work, {"docs/constitution/operations.md": "고친 운영\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "번호 겹침 없음" in out
    unbumped_line = "헌법 파일을 고치고 판을 올리지 않았다: docs/constitution/operations.md."
    assert unbumped_line in out
    assert "옮길 번호" not in out

    _쓴다(work, {"docs/constitution/README.md": _헌법("1.0.1")})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "판을 올리지 않았다" not in out

    # 바꿨는지만 본다. merge-base 의 판보다 낮게 고쳐도 지나간다(못 보는 것)
    _쓴다(work, {"docs/constitution/README.md": _헌법("0.9.0")})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "판을 올리지 않았다" not in out


def test_이_브랜치에_새_번호가_없어도_형제가_쓴_가장_높은_헌법_판을_찍는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 199: 판을 올리기 전에도 찍는다. 다음 빈 번호는 찍지 않는다. 일지와 harness 티켓은
    번호가 아니라 이름이라 받지 않는다."""
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {"docs/notes.md": "그쪽\n"})
    _연다(pusher, 5, pr5)
    sibling = work.parent / "sibling"
    _git(work, "worktree", "add", "-q", "-b", "other", str(sibling), "origin/main")
    _쓴다(sibling, {"docs/other.md": "형제\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0
    assert "이 브랜치의 새 번호 없음" in out
    assert "다음 빈 번호" not in out
    # 일지를 쓸 세션이면 번호를 받으라던 안내와 스크래치를 옮기라던 안내는 없어졌다
    assert "일지를 쓸 세션이면" not in out
    assert "스크래치" not in out
    # 판을 올리기 전에도 찍는다. 형제가 판을 올리지 않았으면 main 의 판이다
    assert "형제가 쓴 가장 높은 헌법 판: 1.0.0(origin/main)." in out


def test_main에_같은_파일로_이미_든_ADR은_새_번호가_아니다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """쌓아 올린 아래 PR 이 squash 로 main 에 들어간 뒤 아직 main 을 들이지 않은 브랜치.

    아래 PR 의 ADR 은 merge-base 에 없어 이 브랜치의 새 번호로 읽히지만 main 과 같은 파일이라
    공유한 이력이다. 새 번호로 세면 main 에 이미 있는 ADR 을 옮기라고 한다(PR 직전 버그 축).
    """
    _, work, pusher = 저장소
    below = {"docs/adr/0002-below.md": "아래\n"}
    _커밋한다(work, below, "아래 PR")
    _커밋한다(pusher, below, "아래 PR 을 squash 로 들인다")
    _커밋한다(pusher, {"docs/adr/0003-main.md": "main\n"}, "main 이 나아간다")
    _git(pusher, "push", "-q", "origin", "main")

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "이 브랜치의 새 번호 없음" in out
    assert "번호 겹침 없음" in out
    assert "옮길 번호" not in out


def test_이_브랜치의_PR과_겹치지_않는_PR은_번호_겹침이_아니고_0으로_끝난다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, pusher = 저장소
    own = _커밋한다(work, {"docs/constitution/README.md": _헌법("1.0.1")}, "이쪽 PR")
    _git(work, "push", "-q", "origin", f"{own}:refs/pull/7/head")
    _연다(work, 7, own)
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n", "README.md": "이쪽\n"})
    pr8_files = {"docs/adr/0003-other.md": "그쪽\n", "README.md": "그쪽\n"}
    pr8 = _PR을_민다(pusher, 8, pr8_files)
    _연다(pusher, 8, pr8)

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0
    assert "번호 겹침 없음" in out
    assert "PR #7" not in out
    assert "PR #8: README.md" in out


def test_amend로_밀지_않은_이_브랜치의_PR은_형제가_아니다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """원격 브랜치와 PR head 가 같고, 로컬은 amend 로 그 커밋을 버렸다(아직 강제 푸시 전)."""
    _, work, _ = 저장소
    own = _커밋한다(work, {"docs/constitution/README.md": _헌법("1.0.1")}, "이쪽 PR")
    _git(work, "push", "-q", "origin", "topic", f"{own}:refs/pull/7/head")
    _연다(work, 7, own)
    _git(work, "commit", "-q", "--amend", "-m", "이쪽 PR, 고친 메시지")

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "PR #7" not in out


def test_얕은_클론에서_merge_base가_없는_PR은_고친_파일만_알_수_없다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    remote, work, pusher = 저장소
    pr6 = _PR을_민다(pusher, 6, {"docs/adr/0002-pr.md": "그쪽\n"})
    _연다(pusher, 6, pr6)
    for n in range(3):
        _커밋한다(pusher, {"README.md": f"main {n}\n"}, f"main {n}")
    _git(pusher, "push", "-q", "origin", "main")
    shallow = work.parent / "shallow"
    _git(work.parent, "clone", "-q", "--depth", "1", f"file://{remote}", str(shallow))
    _git(shallow, "checkout", "-q", "-b", "topic")
    _쓴다(shallow, {"docs/adr/0002-ours.md": "이쪽\n"})

    code = main([str(shallow)])

    out = capsys.readouterr().out
    assert code == 1
    assert "PR #6 ADR 0002" in out
    assert "- PR #6: 알 수 없다(merge-base 가 없다." in out


def test_merge_base에서_번호의_자리가_비면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seed = {k: v for k, v in SEED.items() if k != "docs/constitution/README.md"}
    _, work, _ = _원격과_클론(tmp_path, seed)

    code = main([str(work)])

    captured = capsys.readouterr()
    assert code == 2
    assert "번호의 자리가 비었다: docs/constitution/README.md" in captured.err
    assert ON_FAILURE in captured.err


def test_merge_base에_옛_대기열_표가_없어도_2로_끝나지_않는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열이 항목마다 파일 하나인 폴더가 된 뒤에는 `.scratch/retro-queue.md` 가 어느 브랜치의
    merge-base 에도 없다. 빈 자리 검사가 그 표를 보면 분할 뒤에 딴 모든 브랜치에서 대조가 2로
    멈춘다. 씨앗 저장소가 바로 그 모양이다."""
    _, work, _ = 저장소
    assert ".scratch/retro-queue.md" not in SEED
    _쓴다(work, {"docs/notes.md": "이쪽\n"})

    code = main([str(work)])

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "번호의 자리가 비었다" not in captured.err
    assert "번호 겹침 없음\n" in captured.out
    assert "대기열" not in captured.out


def test_대기열_폴더의_항목_파일은_번호로_읽지_않아_같은_이름이어도_겹침이_아니다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """항목은 번호가 아니라 이름이 식별자라 이 도구가 대조하는 번호가 아니다. 두 브랜치가 같은
    이름의 항목을 다른 글로 더해도 함께 고친 파일로 알릴 뿐 번호 겹침으로 세지 않고, 그 파일에서
    `대기열 N` 인용도 옮기지 않는다."""
    item = ".scratch/retro-queue/0582.md"
    seed = {**SEED, ".scratch/retro-queue/0001.md": "# 0001: 씨앗\n"}
    _, work, pusher = _원격과_클론(tmp_path, seed)
    pr5 = _PR을_민다(pusher, 5, {item: "# 0582: 그쪽\n"})
    _연다(pusher, 5, pr5)
    _쓴다(work, {item: "# 0582: 이쪽\n\n대기열 0581을 잇는다\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "이 브랜치의 새 번호 없음\n" in out
    assert "번호 겹침 없음\n" in out
    assert f"- PR #5: {item}\n" in out
    assert "대기열" not in out


def test_원격을_읽지_못하면_2로_끝나고_까닭과_할_일을_알린다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 251: 2일 때 할 일이 번호를 받는 두 스킬 가운데 하나에만 있었다."""
    _, work, _ = 저장소
    _git(work, "remote", "set-url", "origin", str(work.parent / "없는-원격.git"))

    code = main([str(work)])

    captured = capsys.readouterr()
    assert code == 2
    assert "ls-remote" in captured.err
    assert ON_FAILURE in captured.err
    assert "번호(ADR, 헌법 판)를 손으로 고르지" in ON_FAILURE
    assert "티켓" not in ON_FAILURE


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_도움말은_쓰임과_종료_코드를_찍고_0으로_끝난다(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 251: `--help` 를 시작 경로로 읽어 "형제를 대조하지 못했다" 로 2를 냈다."""
    with pytest.raises(SystemExit) as raised:
        main([flag])

    captured = capsys.readouterr()
    assert raised.value.code == 0
    assert "--move" in captured.out and "종료 코드" in captured.out
    assert captured.err == ""


def test_도움말은_CLI에서도_0으로_끝난다() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "uv run python tools/sibling_overlap.py" in result.stdout


def test_인자가_틀리면_2로_끝나고_할_일을_알린다(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--moev"])

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert "--moev" in captured.err
    assert ON_FAILURE in captured.err


CANARY = ".scratch/harness/probes/canary/x.toml"
SKILL = ".claude/skills/x/SKILL.md"


def test_바꾼_스킬의_카나리아_명세를_고치지_않으면_1로_끝나고_고치면_0이다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 235: `next-session` 을 바꾸고 카나리아를 돌리지 않은 채 셀프 리뷰 두 축과 PR 직전
    리뷰를 지났다(일지 2026-10-13-38)."""
    spec = f'kind = "skill"\nsource = "{SKILL}"\n'
    _, work, _ = _원격과_클론(tmp_path, {**SEED, SKILL: "옛 본문\n", CANARY: spec})
    _쓴다(work, {SKILL: "새 본문\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "번호 겹침 없음" in out
    assert "카나리아 명세를 이 브랜치에서 고치지 않고 바꾼 하네스 파일" in out
    assert f"- {SKILL}: x.toml\n" in out
    # 계정 한도로 돌리지 못하는 갈래는 결과 줄을 고칠 수 없어, 이 알림이 남는다고 출력이 말한다
    assert "계정 한도로 돌리지 못하면 그 절의 계정 한도 항목대로 사전 확인만 돌리고" in out

    # 불러 본 뒤 명세의 최신 결과 줄을 고치면(operations.md 환경 규약 상세) 지나간다
    _쓴다(work, {CANARY: "# 최신 결과: 통과 4\n" + spec})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "카나리아 명세를" not in out

    # 지운 하네스 파일은 불러 볼 것이 없다
    _쓴다(work, {CANARY: spec})
    (work / SKILL).unlink()

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "카나리아 명세를" not in out


def test_카나리아_명세가_하나도_없는_저장소에서는_바꾼_스킬을_알리지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """rag-engine 은 카나리아 도구와 명세를 복사하지 않았다(킥오프 7단계). 알림이 시키는 일을 할
    길이 없어, 명세가 하나도 없으면 판정을 끈다. 명세가 있으면 위 시험대로 돈다."""
    _, work, _ = _원격과_클론(tmp_path, {**SEED, SKILL: "옛 본문\n"})
    _쓴다(work, {SKILL: "새 본문\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "카나리아 명세를" not in out


def test_합치기를_커밋하기_전에도_main이_들여온_파일은_이_브랜치의_변경이_아니다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main 을 합치다 충돌을 풀고 커밋하기 전에 친 대조가, merge-base 가 옛 자리라 main 이 고친
    규칙을 이 브랜치의 카나리아 누락으로, main 만 고친 파일을 함께 고친 파일로 알렸다(일지
    2026-10-15-15). 이 브랜치가 고친 스킬은 그대로 센다. 못 보는 것: 이 브랜치가 고쳤어도 main 과
    내용이 같아진 파일은 세지 않는다."""
    rule, same = ".claude/rules/x.md", ".claude/rules/y.md"
    spec = f'kind = "skill"\nsource = "{SKILL}"\n'
    seed = {**SEED, SKILL: "옛 본문\n", rule: "옛 규칙\n", same: "옛\n", CANARY: spec}
    _, work, pusher = _원격과_클론(tmp_path, seed)
    ours = {SKILL: "새 본문\n", "README.md": "이 브랜치\n", same: "같은 고침\n"}
    _커밋한다(work, ours, "이 브랜치")
    theirs = {rule: "main 의 규칙\n", "README.md": "main\n", "CLAUDE.md": "main\n"}
    _커밋한다(pusher, {**theirs, same: "같은 고침\n"}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    with pytest.raises(subprocess.CalledProcessError):
        _git(work, "merge", "-q", "origin/main")  # README.md 가 충돌한다
    _쓴다(work, {"README.md": "둘 다\n"})
    _git(work, "add", "README.md")

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert f"- {SKILL}: x.toml\n" in out
    assert rule not in out
    assert same not in out
    assert "- origin/main: README.md\n" in out


def test_합치기를_커밋하기_전에도_main이_올린_헌법_판은_이_브랜치의_판이_아니다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main 을 합치고 커밋하기 전에 친 대조가 main 이 올린 판을 이 브랜치의 새 판으로 읽어 main 과
    같은 판으로 겹쳤다고 1로 끝났다(일지 2026-10-15-15). 헌법 README 가 main 과 같으면 판은 main
    에서 들어온 것이다."""
    _, work, pusher = _원격과_클론(tmp_path, SEED)
    _커밋한다(work, {"README.md": "이 브랜치\n"}, "이 브랜치")
    _커밋한다(pusher, {"docs/constitution/README.md": _헌법("1.0.1")}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    _git(work, "merge", "-q", "--no-commit", "--no-ff", "origin/main")

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "이 브랜치의 새 번호 없음" in out
    assert "번호 겹침 없음" in out


def test_옮기기를_고르면_옮길_번호대로_옮기고_다시_대조한다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 249: 형제가 더 높은 번호를 들고 먼저 병합해 한 세션에서 번호를 두 번 옮기고, 그때마다
    인용(다섯에서 아홉)을 손으로 고쳤다(일지 2026-10-13-59·2026-10-13-61)."""
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {"docs/adr/0002-pr.md": "ADR 0002 그쪽\n"})
    _연다(pusher, 5, pr5)
    old = "docs/adr/0002-ours.md"
    _커밋한다(work, {old: "ADR 0002 이쪽\n\n대기열 2를 연다.\n"}, "ADR")

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "옮길 번호: ADR 0002 → 0003\n" in out
    assert "`--move` 를 붙여 다시 치면" in out

    # 옮길 자리에 무엇이 있으면 아무것도 고치지 않고 2로 끝난다
    blocker = work / "docs/adr/0003-ours.md"
    blocker.mkdir()

    code = main([str(work), "--move"])

    captured = capsys.readouterr()
    assert code == 2, captured.out
    assert "번호를 옮기지 못했다. 옮길 자리 docs/adr/0003-ours.md" in captured.err
    assert ON_FAILURE in captured.err
    adr_text = (work / old).read_text(encoding="utf-8")
    assert adr_text == "ADR 0002 이쪽\n\n대기열 2를 연다.\n"

    blocker.rmdir()

    code = main([str(work), "--move"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out.startswith("옮겼다: ADR 0002 → 0003.")
    assert f"이름을 바꾼 파일: {old} → docs/adr/0003-ours.md." in out
    assert "인용을 고친 파일: docs/adr/0003-ours.md." in out
    assert "옛 이름의 지움까지 함께 스테이지한다(`git add -A`)" in out
    assert "번호 뒤의 조사는 옮기지 않았으니 손으로 본다" in out
    assert "번호 겹침 없음" in out and "옮길 번호" not in out
    assert "PR 본문" not in out  # origin 이 GitHub 이 아니면 PR 본문을 묻지 않는다
    assert not (work / old).exists()
    moved = (work / "docs/adr/0003-ours.md").read_text(encoding="utf-8")
    # 대기열 인용은 번호가 아니라 항목의 이름이라 옮기지 않는다
    assert moved == "ADR 0003 이쪽\n\n대기열 2를 연다.\n"
    # 인덱스는 건드리지 않는다. 옛 ADR 이 인덱스에 남아도 대조는 작업 트리를 읽어 0이다(못 보는 것)
    assert old in _git(work, "ls-files")

    code = main([str(work), "--move"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out.startswith("옮길 번호가 없어 옮기지 않았다\n")


def test_옮기기는_일지_파일_이름과_머리_줄을_옮기지_않는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """일지는 번호가 아니라 시각이다. ADR 을 옮길 때 이 브랜치의 일지 파일 이름과 `# 날짜 (NN)`
    머리 줄, 일지 인용은 그대로 두고 일지 안의 ADR 인용만 옮긴다."""
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {"docs/adr/0002-pr.md": "그쪽\n"})
    _연다(pusher, 5, pr5)
    journal = "docs/journal/2026-11-07-0930-ours.md"
    stamp = "2026-11-07-0930"  # 인용 꼴을 글자로 적으면 이 도구가 이 파일의 줄을 인용으로 읽는다
    text = f"# 2026-11-07 (03) 이쪽\n\nADR 0002 를 쓴다. 일지 {stamp} 에서 잇는다.\n"
    _커밋한다(work, {"docs/adr/0002-ours.md": "이쪽\n", journal: text}, "ADR 과 일지")

    code = main([str(work), "--move"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert (work / journal).read_text(encoding="utf-8") == text.replace("ADR 0002", "ADR 0003")
    assert "이름을 바꾼 파일: docs/adr/0002-ours.md → docs/adr/0003-ours.md." in out
    assert (work / journal).is_file()


def test_옮기기는_merge_base와_main의_판에_글자_그대로_있는_같은_번호의_줄을_둔다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PR 직전 버그 축: 양쪽이 같은 ADR 번호를 쓰고 충돌을 풀어 세 줄을 남긴 채 `--move` 를 치면
    merge-base 에 있던 줄과 main 이 더한 줄까지 옮겨졌다. 두 판에 글자 그대로 있는 줄은 상대를
    가리키니 둔다. 이 브랜치가 더한 줄만 옮긴다."""
    base_line = "merge-base 의 줄: ADR 0002 를 쓸 예정\n"
    _, work, pusher = _원격과_클론(tmp_path, {**SEED, "docs/notes.md": base_line})
    ours_line, main_line = "이 브랜치의 줄: ADR 0002\n", "main 의 줄: ADR 0002\n"
    ours = {"docs/adr/0002-ours.md": "이쪽\n", "docs/notes.md": base_line + ours_line}
    _커밋한다(work, ours, "이 브랜치")
    main_files = {"docs/adr/0002-main.md": "main\n", "docs/notes.md": base_line + main_line}
    _커밋한다(pusher, main_files, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    with pytest.raises(subprocess.CalledProcessError):
        _git(work, "merge", "-q", "origin/main")  # 둘 다 더한 docs/notes.md 끝이 충돌한다
    _쓴다(work, {"docs/notes.md": base_line + main_line + ours_line})
    _git(work, "add", "docs/notes.md")

    code = main([str(work), "--move"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "옮겼다: ADR 0002 → 0003" in out
    notes = (work / "docs/notes.md").read_text(encoding="utf-8")
    assert notes == base_line + main_line + "이 브랜치의 줄: ADR 0003\n"


def test_옮기기는_이_브랜치가_더한_줄의_번호만_옮기고_나머지_줄은_그대로_둔다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """위 시험의 대조군. 같은 파일에서 이 브랜치가 더한 줄이 옮겨졌는지 따로 본다."""
    _, work, pusher = _원격과_클론(tmp_path, SEED)
    _커밋한다(pusher, {"docs/adr/0002-main.md": "main\n"}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    _쓴다(work, {"docs/adr/0002-ours.md": "이쪽\n", "docs/notes.md": "이 브랜치의 줄: ADR 0002\n"})

    code = main([str(work), "--move"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert (work / "docs/notes.md").read_text(encoding="utf-8") == "이 브랜치의 줄: ADR 0003\n"


def test_옮기기는_이_브랜치의_열린_PR_본문에_남은_옛_번호를_알린다(
    저장소: tuple[Path, Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """대기열 376: 번호를 옮긴 뒤 열린 PR 본문에 옛 경로가 남아 claude-review 가 짚었다(그때는 일지
    경로였고 지금은 ADR 경로다). 본문은 고치지 않고 고친 본문의 파일과 올리는 명령을 낸다."""
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {"docs/adr/0002-pr.md": "그쪽\n"})
    _연다(pusher, 5, pr5)
    _커밋한다(work, {"docs/adr/0002-ours.md": "이쪽\n"}, "ADR")
    asked: list[tuple[str, str, str]] = []

    def 깃허브다(url: str) -> tuple[str, str]:
        return ("o", "r")

    def gh_가_연다(root: Path, owner: str, repo: str) -> str:
        return f"5 {pr5}\n"

    def 본문을_읽는다(root: Path, owner: str, repo: str, branch: str) -> dict[int, str]:
        asked.append((owner, repo, branch))
        return {7: "ADR 는 docs/adr/0002-ours.md 다\n"}

    monkeypatch.setattr(sibling_overlap, "github_repo", 깃허브다)
    monkeypatch.setattr(sibling_overlap, "gh_listing", gh_가_연다)
    monkeypatch.setattr(sibling_overlap, "own_pull_bodies", 본문을_읽는다)
    monkeypatch.setattr(sibling_overlap.tempfile, "tempdir", str(tmp_path))

    code = main([str(work), "--move"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert asked == [("o", "r", "topic")]
    assert "이 브랜치의 열린 PR #7 본문에 옮기기 전 번호가 있다." in out
    assert "올리는 명령: gh api repos/o/r/pulls/7 --method PATCH -F" in out
    [written] = tmp_path.glob("*/pr-7-body.md")
    assert written.read_text(encoding="utf-8") == "ADR 는 docs/adr/0003-ours.md 다\n"
    assert f'"body=@{written.as_posix()}"' in out


def test_이_브랜치가_더한_줄의_일지_인용이_어디에도_없는_번호면_1로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 254: `sibling_overlap.py` 를 치기 전에 짐작한 일지 번호를 인용했고 손으로 고쳤다(일지
    2026-10-13-66). main 에 있던 줄의 없는 번호는 이 브랜치가 더한 것이 아니라 알리지 않는다. 형제의
    일지는 커밋하지 않았어도 있는 번호다. 인용하기 전에 그 일지 파일을 먼저 만들면 지나간다."""
    old = "옛 줄의 일지 2026-10-07-09\n"
    _, work, _ = _원격과_클론(tmp_path, {**SEED, "docs/notes.md": old})
    ours = "docs/journal/2026-10-07-02-ours.md"
    # 커밋 메시지의 인용은 보지 않는다(못 보는 것)
    journal = {ours: "# 2026-10-07 (02) 이쪽\n\n일지 2026-10-07-02를 쓴다\n"}
    _커밋한다(work, journal, "일지 2026-10-07-08 을 본다")
    _쓴다(work, {"docs/notes.md": old + "일지 2026-10-07-05와 일지 2026-10-07-01을 본다\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "번호 겹침 없음" in out
    assert "어디에도 없는 일지를 가리킨 인용" in out
    assert "- docs/notes.md: 2026-10-07-05\n" in out
    assert "- docs/journal/" not in out
    assert "2026-10-07-08" not in out

    sibling = work.parent / "sibling"
    _git(work, "worktree", "add", "-q", "-b", "other", str(sibling), "origin/main")
    _쓴다(sibling, {"docs/journal/2026-10-07-05-sibling.md": "형제\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "어디에도 없는 일지" not in out

    # 아직 만들지 않은 일지를 먼저 인용하면 알리고, 그 일지 파일을 만들면 지나간다
    notes = (work / "docs/notes.md").read_text(encoding="utf-8")
    _쓴다(work, {"docs/notes.md": notes + "다음은 일지 2026-10-07-06에 쓴다\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert "- docs/notes.md: 2026-10-07-06\n" in out

    _쓴다(work, {"docs/journal/2026-10-07-06-next.md": "# 2026-10-07 (06) 다음\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "어디에도 없는 일지" not in out


def test_합치는_도중_main에서_들어온_줄의_일지_인용은_이_브랜치가_더한_줄이_아니다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """셀프 리뷰 명세 축: merge-base 에 없고 main 에만 있는 줄을 빼는 것을 고정한 시험이 없었다.
    main 을 합치다 충돌을 풀고 커밋하기 전에는 merge-base 가 옛 자리라, main 이 더한 줄이 이
    브랜치가 고친 파일에 섞인다."""
    _, work, pusher = _원격과_클론(tmp_path, SEED)
    _커밋한다(work, {"docs/notes.md": "이쪽\n"}, "이 브랜치")
    main_line = "main 이 옮겨 적은 옛 일지 2026-10-07-09\n"
    _커밋한다(pusher, {"docs/notes.md": main_line}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    with pytest.raises(subprocess.CalledProcessError):
        _git(work, "merge", "-q", "origin/main")  # 둘 다 더한 docs/notes.md 가 충돌한다
    assert _git(work, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    _쓴다(work, {"docs/notes.md": main_line + "이쪽\n"})
    _git(work, "add", "docs/notes.md")

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "어디에도 없는 일지" not in out


def test_main이_아닌_브랜치를_합치는_도중에는_그_번호를_이_브랜치_밖의_것으로_센다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """셀프 리뷰 명세 축: 합칠 머리가 main 이 아니면 그 번호를 이 브랜치의 새 번호로 읽었다."""
    _, work, _ = _원격과_클론(tmp_path, SEED)
    _커밋한다(work, {"docs/notes.md": "이쪽\n"}, "이 브랜치")
    _git(work, "checkout", "-q", "-b", "side", "origin/main")
    _커밋한다(work, {"docs/adr/0002-side.md": "# x\n"}, "side")
    _git(work, "checkout", "-q", "-")
    _git(work, "merge", "-q", "--no-ff", "--no-commit", "side")

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "이 브랜치의 새 번호 없음" in out


def test_여러_머리를_합치는_도중에는_머리마다_그_번호를_이_브랜치_밖의_것으로_센다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """셀프 리뷰 표준 축: octopus 합치기(`MERGE_HEAD` 가 여러 줄)를 만드는 시험이 없었다."""
    _, work, _ = _원격과_클론(tmp_path, SEED)
    _커밋한다(work, {"docs/notes.md": "이쪽\n"}, "이 브랜치")
    _git(work, "checkout", "-q", "-b", "side1", "origin/main")
    _커밋한다(work, {"docs/adr/0002-side1.md": "# y\n"}, "side1")
    _git(work, "checkout", "-q", "-b", "side2", "origin/main")
    _커밋한다(work, {"docs/adr/0003-side2.md": "# x\n"}, "side2")
    _git(work, "checkout", "-q", "topic")
    _git(work, "merge", "-q", "--no-ff", "--no-commit", "side1", "side2")
    merge_head = (work / ".git" / "MERGE_HEAD").read_text(encoding="utf-8")
    assert len(merge_head.split()) == 2, merge_head

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "이 브랜치의 새 번호 없음" in out


def test_main이_이_브랜치_몫으로_비워_둔_헌법_판의_문장을_지웠으면_판을_올린_것이다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """대기열 279, retro-queue-per-item 06: #243 이 3.0.35 를 이 브랜치 몫으로 비워 두었는데, 판
    줄을 main 그대로 둔 이 브랜치에 합칠 때마다 "헌법 파일을 고치고 판을 올리지 않았다" 로 1을
    냈다(일지 2026-10-15-19). 헌법 README 의 이력 문단이 없어진 뒤의 신호는 판 줄이 main 과 같고
    main 에 있던 이 브랜치 몫의 비워 둔 문장을 지운 것이다. 합치기를 커밋하기 전(판 줄이 main 과
    같다)과 뒤(판 줄이 merge-base 와 같다)가 모두 그렇다."""
    seed = {**SEED, CONSTITUTION: _이력("1.0.0", "")}
    _, work, pusher = _원격과_클론(tmp_path, seed)
    ours = {
        "docs/constitution/operations.md": "고친 운영\n",
        CONSTITUTION: _이력("1.0.1", ""),
    }
    _커밋한다(work, ours, "이 브랜치")
    _커밋한다(pusher, {CONSTITUTION: _이력("1.0.2", RESERVE)}, "main")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    with pytest.raises(subprocess.CalledProcessError):
        _git(work, "merge", "-q", "origin/main")  # 판 줄이 충돌한다
    assert _git(work, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    _쓴다(work, {CONSTITUTION: _이력("1.0.2", "")})
    _git(work, "add", CONSTITUTION)

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "이 브랜치의 새 번호: 헌법 1.0.1\n" in out
    assert "올린 판으로 센 헌법 1.0.1: origin/main 의 헌법 README 가" in out
    assert "이 브랜치 몫으로 비워 둔 판이고, 이 브랜치가 그 문장을 지웠다" in out
    assert "번호 겹침 없음" in out

    _git(work, "commit", "-q", "--no-edit")
    assert len(_git(work, "rev-list", "--parents", "-n", "1", "HEAD").split()) == 3  # 합치기 커밋

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "판을 올리지 않았다" not in out
    assert "이 브랜치의 새 번호: 헌법 1.0.1\n" in out


# --- harness 티켓은 번호가 아니라 이름이다(retro-queue-per-item 07) -------------------

ISSUES = ".scratch/harness/issues"


def _형제_워크트리(work: Path, files: dict[str, str]) -> Path:
    """origin/main 위의 형제 워크트리에 `files` 를 커밋하지 않고 쓴다."""
    sibling = work.parent / "sibling"
    _git(work, "worktree", "add", "-q", "-b", "other", str(sibling), "origin/main")
    _쓴다(sibling, files)
    return sibling.resolve()


def test_harness_티켓은_번호로_읽지_않아_형제와_같은_번호여도_겹침이_아니고_번호_줄이_없다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """옛 세 자리 번호 꼴(`001-<slug>.md`)도 번호가 아니다. main, 열린 PR, 형제 워크트리가 모두 같은
    번호의 티켓을 들어도 번호 겹침과 옮길 번호가 없고, 다음 빈 티켓 번호도 찍지 않는다. 새 티켓의
    이름(`<slug>.md`)은 번호가 아니라 겹치지 않는다."""
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {f"{ISSUES}/001-pr.md": "# 001: 그쪽\n"})
    _연다(pusher, 5, pr5)
    _커밋한다(pusher, {f"{ISSUES}/001-main.md": "# 001: main\n"}, "main 이 옛 꼴 티켓을 들인다")
    _git(pusher, "push", "-q", "origin", "main")
    _형제_워크트리(work, {f"{ISSUES}/001-sibling.md": "# 001: 형제\n"})
    _쓴다(
        work,
        {
            f"{ISSUES}/001-ours.md": "# 001: 이쪽\n",
            f"{ISSUES}/queue-split.md": "# queue-split: 이쪽\n",
        },
    )

    code = main([str(work)])

    captured = capsys.readouterr()
    out = captured.out
    assert code == 0, out + captured.err
    assert "이 브랜치의 새 번호 없음\n" in out
    assert "번호 겹침 없음\n" in out
    assert "티켓 " not in out  # 형제 줄의 경로에는 시험 이름이 든다. 줄 머리의 낱말만 본다
    assert "다음 빈 번호" not in out
    assert "옮길 번호" not in out


def test_같은_이름의_harness_티켓을_둘이_지으면_함께_고친_파일로만_나온다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """못 보는 것. 이름이 같은 티켓은 번호 겹침이 아니라서 종료 코드를 바꾸지 않는다."""
    _, work, _ = 저장소
    sibling = _형제_워크트리(work, {f"{ISSUES}/queue-split.md": "# queue-split: 형제\n"})
    _쓴다(work, {f"{ISSUES}/queue-split.md": "# queue-split: 이쪽\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "번호 겹침 없음\n" in out
    assert f"- 워크트리 {sibling}: {ISSUES}/queue-split.md\n" in out


def test_옮기기는_ADR만_옮기고_harness_티켓의_이름과_브랜치는_건드리지_않는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """번호가 없는 티켓의 이름을 바꾸거나 브랜치 이름을 바꾸는 명령을 찍지 않는다. 티켓 안의 ADR
    인용은 다른 파일처럼 옮긴다."""
    _, work, pusher = 저장소
    _git(work, "checkout", "-q", "-b", "chore/queue-split")
    _커밋한다(pusher, {"docs/adr/0002-main.md": "main\n"}, "main 이 같은 ADR 번호를 들인다")
    _git(pusher, "push", "-q", "origin", "main")
    ticket = f"{ISSUES}/queue-split.md"
    _커밋한다(
        work,
        {"docs/adr/0002-ours.md": "이쪽\n", ticket: "# queue-split: 이쪽\nADR 0002 를 본다\n"},
        "ADR 과 티켓",
    )

    code = main([str(work), "--move"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out.startswith("옮겼다: ADR 0002 → 0003.")
    assert "이름을 바꾼 파일: docs/adr/0002-ours.md → docs/adr/0003-ours.md." in out
    assert (work / ticket).read_text(encoding="utf-8") == "# queue-split: 이쪽\nADR 0003 를 본다\n"
    assert "git branch -m" not in out and "git push" not in out
    assert "set_session_title" not in out
    assert _git(work, "branch", "--show-current") == "chore/queue-split"


# --- 시각 꼴 일지 이름(ADR 0045 결정 7) -------------------------------------------------


def test_일지_인용은_순번_꼴과_시각_꼴을_파일_이름의_접두로_푼다() -> None:
    names = ["2026-10-19-21-old.md", "2026-11-06-1432-new.md", "2026-09-19-kickoff.md"]

    old, new = "2026-10-19-21", "2026-11-06-1432"
    cited = f"일지 {old}과 일지 {new}, 일지 {old}·{new}"

    assert dangling_cites(cited, names) == []


def test_시각_꼴_파일에_시_두_자리만_든_인용은_맞지_않고_접두_뒤의_하이픈이_가른다() -> None:
    names = ["2026-11-06-1432-new.md", "2026-10-19-21-old.md"]

    hour_only, old_with_minutes, cut = "2026-11-06-14", "2026-10-19-2100", "2026-11-06-143"
    assert dangling_cites(f"일지 {hour_only}를 본다", names) == [hour_only]
    assert dangling_cites(f"일지 {old_with_minutes}을 본다", names) == [old_with_minutes]
    assert dangling_cites(f"일지 {cut}", names) == [cut]


def test_이름순은_옛_꼴과_새_꼴이_섞인_날에도_새_꼴이_늦다() -> None:
    names = ["2026-11-06-12-old.md", "2026-11-06-0930-new.md", "2026-11-05-1800-prev.md"]

    assert sorted(names, key=journal_order)[-1] == "2026-11-06-0930-new.md"
    assert sorted(names, key=journal_order)[0] == "2026-11-05-1800-prev.md"


def test_다음_빈_번호를_찍지_않고_일지_순번을_받지_않는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, _ = 저장소

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "다음 빈 번호" not in out
    assert "일지를 쓸 세션이면" not in out
    assert "일지 20" not in out


def test_merge_base에_순번_일지가_없어도_2로_끝나지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seed = {k: v for k, v in SEED.items() if not k.startswith("docs/journal/")}
    seed["docs/journal/2026-11-06-1432-seed.md"] = "씨앗\n"
    _, work, _ = _원격과_클론(tmp_path, seed)
    _쓴다(work, {"docs/journal/2026-11-07-0930-ours.md": "이쪽\n"})

    code = main([str(work)])

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "번호의 자리가 비었다" not in captured.err
    assert "번호 겹침 없음\n" in captured.out


def test_merge_base에_일지가_하나도_없어도_2로_끝나지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seed = {k: v for k, v in SEED.items() if not k.startswith("docs/journal/")}
    seed["docs/journal/.gitkeep"] = ""
    _, work, _ = _원격과_클론(tmp_path, seed)

    code = main([str(work)])

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "번호의 자리가 비었다" not in captured.err


def test_같은_분의_일지_둘은_번호_겹침이_아니라_일지_이름_시험이_본다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, pusher = 저장소
    pr5 = _PR을_민다(pusher, 5, {"docs/journal/2026-11-07-0930-theirs.md": "그쪽\n"})
    _연다(pusher, 5, pr5)
    _쓴다(work, {"docs/journal/2026-11-07-0930-ours.md": "이쪽\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "번호 겹침 없음\n" in out
    assert "이 브랜치의 새 번호 없음\n" in out


def test_새_꼴_일지_인용도_어디에도_없으면_1로_끝나고_있으면_지나간다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seed = {**SEED, "docs/journal/2026-11-06-1432-seed.md": "씨앗\n"}
    _, work, _ = _원격과_클론(tmp_path, seed)
    stamp, hour_only = "2026-11-06-1432", "2026-11-06-14"
    _쓴다(work, {"docs/notes.md": f"일지 {stamp}를 본다\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "어디에도 없는 일지" not in out

    _쓴다(work, {"docs/notes.md": f"일지 {hour_only}를 본다\n"})

    code = main([str(work)])

    out = capsys.readouterr().out
    assert code == 1, out
    assert f"- docs/notes.md: {hour_only}\n" in out


def test_이_브랜치의_일지는_merge_base_뒤에_더한_것과_커밋하지_않은_새_일지다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, pusher = 저장소
    _커밋한다(pusher, {"docs/journal/2026-11-07-1000-main.md": "main\n"}, "main이 나아간다")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "pull", "-q", "--no-rebase", "origin", "main")
    _커밋한다(work, {"docs/journal/2026-11-07-1100-ours.md": "이쪽\n"}, "이 브랜치")

    code = main([str(work), "--journal"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out.strip() == "docs/journal/2026-11-07-1100-ours.md"

    # 커밋하지 않은 새 일지가 더 늦으면 그것이다. main을 합친 뒤 들어온 남의 일지는 들지 않는다
    _쓴다(work, {"docs/journal/2026-11-07-1200-untracked.md": "미추적\n"})

    code = main([str(work), "--journal"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out.strip() == "docs/journal/2026-11-07-1200-untracked.md"


def test_이_브랜치의_일지는_같은_날_옛_꼴보다_늦게_더한_새_꼴이_걸린다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """이름순이면 `-12-`가 `-0930-`보다 뒤라 옛 일지가 걸린다."""
    _, work, _ = 저장소
    _커밋한다(work, {"docs/journal/2026-11-06-12-old.md": "옛\n"}, "옛 꼴")
    _커밋한다(work, {"docs/journal/2026-11-06-0930-new.md": "새\n"}, "새 꼴")

    code = main([str(work), "--journal"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out.strip() == "docs/journal/2026-11-06-0930-new.md"


def test_이_브랜치의_일지는_날짜로_시작하는_마크다운만_든다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """일지 폴더에 놓인 `.txt`나 `README.md`는 일지가 아니라서 가장 늦은 일지로 걸리지 않는다."""
    _, work, _ = 저장소
    _커밋한다(work, {"docs/journal/2026-11-07-1100-ours.md": "이쪽\n"}, "일지")
    _쓴다(
        work,
        {
            "docs/journal/2026-11-08-1200-notes.txt": "메모\n",
            "docs/journal/README.md": "안내\n",
        },
    )

    code = main([str(work), "--journal"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert out.strip() == "docs/journal/2026-11-07-1100-ours.md"


def test_이_브랜치가_더한_일지가_없으면_1로_끝나고_아무것도_찍지_않는다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, _ = 저장소

    code = main([str(work), "--journal"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "이 브랜치가 더한 일지가 없다" in captured.err


# --- 기준 브랜치 규칙(agent-os ADR 0043, tools/base_rule.py) -----------------------------


def _dev를_딴다(work: Path, pusher: Path, dev: dict[str, str], hotfix: dict[str, str]) -> None:
    """원격에 main 에서 딴 dev 를 두고 dev 에 `dev` 를, main 에 `hotfix` 를 더해 둘이 갈라지게 한다.
    작업 클론은 받아 `origin/dev` 의 추적 ref 를 갖는다. 브랜치는 `topic` 그대로다."""
    _git(pusher, "checkout", "-q", "-b", "dev", "main")
    _커밋한다(pusher, dev, "dev 가 나아간다")
    _git(pusher, "push", "-q", "origin", "dev")
    _git(pusher, "checkout", "-q", "main")
    _커밋한다(pusher, hotfix, "main 에 핫픽스")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")


def test_origin_dev가_있으면_dev를_기준으로_하고_dev에서_딴_브랜치의_번호를_견준다(
    저장소: tuple[Path, Path, Path],
) -> None:
    _, work, pusher = 저장소
    _dev를_딴다(work, pusher, {"docs/adr/0002-dev.md": "dev\n"}, {"docs/adr/0003-hotfix.md": "m\n"})
    _커밋한다(work, {"docs/adr/0002-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    # topic 은 dev 가 나아가기 전에 땄다. dev 가 새로 쥔 0002 와 겹치고 main 에는 0002 가 없다
    assert result.returncode == 1, result.stderr
    assert "origin/dev ADR 0002: 이 브랜치 0002-ours.md, 그쪽 0002-dev.md" in result.stdout
    assert "origin/main ADR 0002" not in result.stdout


def test_dev가_기준이어도_dev에_없는_main의_번호는_main에도_있는_것으로_센다(
    저장소: tuple[Path, Path, Path],
) -> None:
    """dev→main 사이에 hotfix 가 낀 경우다. main 만 쥔 0003 도 이 브랜치 밖의 번호다."""
    _, work, pusher = 저장소
    _dev를_딴다(work, pusher, {"docs/adr/0002-dev.md": "dev\n"}, {"docs/adr/0003-hotfix.md": "m\n"})
    _커밋한다(work, {"docs/adr/0003-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 1, result.stderr
    assert "origin/main ADR 0003: 이 브랜치 0003-ours.md, 그쪽 0003-hotfix.md" in result.stdout
    assert "옮길 번호: ADR 0003 → 0004\n" in result.stdout


def test_dev가_기준일_때_main에서_딴_열린_PR은_main이_쥔_번호를_자기_새_번호로_세지_않는다(
    저장소: tuple[Path, Path, Path],
) -> None:
    """hotfix PR(base 가 main)의 head 는 main 이 쥔 0003 을 품는다. 그 0003 은 PR 이 더한 것이
    아니라 `origin/main` 줄로 이미 알린다. PR 줄에 같은 번호가 이중으로 뜨지 않는다."""
    _, work, pusher = 저장소
    _dev를_딴다(work, pusher, {"docs/adr/0002-dev.md": "dev\n"}, {"docs/adr/0003-hotfix.md": "m\n"})
    pr = _PR을_민다(pusher, 5, {"docs/adr/0004-pr.md": "그쪽\n"})
    _연다(pusher, 5, pr)
    _커밋한다(work, {"docs/adr/0003-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 1, result.stderr
    assert "origin/main ADR 0003: 이 브랜치 0003-ours.md, 그쪽 0003-hotfix.md" in result.stdout
    assert "PR #5 ADR 0003" not in result.stdout


def test_반박_hotfix_브랜치와_열린_PR이_dev가_쥔_번호에_다른_파일을_더하면_서로_겹친다(
    저장소: tuple[Path, Path, Path],
) -> None:
    """PR 봇 첫 회차의 Major. 기준이 아닌 오래 사는 브랜치(dev)와 번호만 같은 PR 의 파일은 PR 이
    새로 매긴 번호다. 번호만 보고 빼면 이 브랜치와 PR 의 겹침이 dev 줄에 가려져 사라진다."""
    _, work, pusher = 저장소
    _dev를_딴다(work, pusher, {"docs/adr/0003-dev.md": "dev\n"}, {"README.md": "m\n"})
    pr = _PR을_민다(pusher, 5, {"docs/adr/0003-pr.md": "그쪽\n"})
    _연다(pusher, 5, pr)
    _git(work, "checkout", "-q", "-B", "hotfix/x", "origin/main")
    _커밋한다(work, {"docs/adr/0003-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 1, result.stderr
    assert "PR #5 ADR 0003: 이 브랜치 0003-ours.md, 그쪽 0003-pr.md" in result.stdout


def test_반박_기준이_아닌_브랜치에서_물려받은_ADR은_옮길_번호에_들지_않는다(
    저장소: tuple[Path, Path, Path],
) -> None:
    """PR 봇 첫 회차의 Major. dev 가 기준이고 main 이 이 브랜치의 조상이면 main 줄은 찍지 않는다.
    그래도 main 에서 물려받은 0002 는 공유한 이력이라 `--move` 가 0003 과 함께 옮기지 않는다."""
    _, work, pusher = 저장소
    _git(pusher, "branch", "dev", "main")
    _git(pusher, "push", "-q", "origin", "dev")
    _커밋한다(pusher, {"docs/adr/0002-main.md": "main\n"}, "main 이 앞선다")
    _git(pusher, "push", "-q", "origin", "main")
    pr = _PR을_민다(pusher, 5, {"docs/adr/0003-pr.md": "그쪽\n"})
    _연다(pusher, 5, pr)
    _git(work, "fetch", "-q", "origin")
    _git(work, "checkout", "-q", "-B", "topic", "origin/main")
    _커밋한다(work, {"docs/adr/0003-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "PR #5 ADR 0003: 이 브랜치 0003-ours.md, 그쪽 0003-pr.md" in result.stdout
    assert "옮길 번호: ADR 0003 → 0004\n" in result.stdout
    assert "0002 →" not in result.stdout


def test_hotfix_브랜치는_dev가_있어도_main을_기준으로_하고_dev의_번호도_견준다(
    저장소: tuple[Path, Path, Path],
) -> None:
    _, work, pusher = 저장소
    _dev를_딴다(work, pusher, {"docs/adr/0002-dev.md": "dev\n"}, {"docs/adr/0003-hotfix.md": "m\n"})
    _git(work, "checkout", "-q", "-B", "hotfix/x", "origin/main")
    _커밋한다(work, {"docs/adr/0002-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 1, result.stderr
    # 기준은 main 이라 dev 는 또 하나의 오래 사는 브랜치로 견준다. hotfix 가 나중에 dev 로 합쳐진다
    assert "origin/dev ADR 0002: 이 브랜치 0002-ours.md, 그쪽 0002-dev.md" in result.stdout


def test_dev의_추적_ref가_없으면_원격에_dev가_있어도_main만_대조한다(
    저장소: tuple[Path, Path, Path],
) -> None:
    """못 보는 것: 원격에 dev 가 있어도 이 클론이 추적 ref 를 받은 적이 없으면 main 으로 돈다."""
    _, work, pusher = 저장소
    _git(pusher, "checkout", "-q", "-b", "dev", "main")
    _커밋한다(pusher, {"docs/adr/0002-dev.md": "dev\n"}, "dev 가 나아간다")
    _git(pusher, "push", "-q", "origin", "dev")
    _git(pusher, "checkout", "-q", "main")
    _커밋한다(work, {"docs/adr/0002-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "origin/dev" not in result.stdout


def test_dev가_기준일_때_일지는_dev와의_merge_base_뒤에_더한_것이다(
    저장소: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, work, pusher = 저장소
    dev_일지 = {"docs/journal/2026-11-05-0900-dev.md": "dev\n"}
    _dev를_딴다(work, pusher, dev_일지, {"README.md": "main\n"})
    _git(work, "checkout", "-q", "-B", "topic", "origin/dev")
    _커밋한다(work, {"docs/journal/2026-11-02-0900-ours.md": "이쪽\n"}, "일지")

    code = main([str(work), "--journal"])

    # main 에 견주면 dev 가 더한 더 늦은 일지가 이 브랜치의 것으로 걸린다
    assert code == 0
    assert capsys.readouterr().out.strip() == "docs/journal/2026-11-02-0900-ours.md"


def test_반박_dev_가_main_보다_뒤처져도_main_에서_딴_브랜치는_main_의_번호와_겹치지_않는다(
    저장소: tuple[Path, Path, Path],
) -> None:
    """dev 를 기준으로 잡아도 merge-base 가 dev 끝이라, main 이 더한 번호가 이 브랜치의 새 번호로
    읽히기 쉽다. 같은 번호에 같은 파일이면 겹침이 아니다."""
    _, work, pusher = 저장소
    _git(pusher, "branch", "dev", "main")
    _git(pusher, "push", "-q", "origin", "dev")
    _커밋한다(pusher, {"docs/adr/0002-main.md": "main\n"}, "main 이 앞선다")
    _git(pusher, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    _git(work, "checkout", "-q", "-B", "topic", "origin/main")
    _커밋한다(work, {"docs/adr/0003-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 0, result.stdout + result.stderr


def test_반박_이력이_갈라진_dev_를_받았어도_조용히_지나가지_않는다(
    저장소: tuple[Path, Path, Path],
) -> None:
    """merge-base 가 없는 dev(고아 브랜치, 얕은 클론)는 이 브랜치와 견줄 수 없다. 겹침 없음으로
    조용히 지나가지 않고 2 로 멈춘다."""
    _, work, pusher = 저장소
    _git(pusher, "checkout", "-q", "--orphan", "dev")
    _git(pusher, "rm", "-rq", "--cached", ".")
    _커밋한다(pusher, {"docs/adr/0001-other.md": "다른 뿌리\n"}, "고아 dev")
    _git(pusher, "push", "-q", "origin", "dev")
    _git(work, "fetch", "-q", "origin")
    _커밋한다(work, {"docs/adr/0002-ours.md": "이쪽\n"}, "이쪽")

    result = _CLI를_부른다(work)

    assert result.returncode == 2, result.stdout + result.stderr


def test_반박_dev_브랜치_자체에서는_새_번호가_없어_겹치지_않는다(
    저장소: tuple[Path, Path, Path],
) -> None:
    _, work, pusher = 저장소
    _dev를_딴다(work, pusher, {"docs/adr/0002-dev.md": "dev\n"}, {"docs/adr/0003-hotfix.md": "m\n"})
    _git(work, "checkout", "-q", "-B", "dev", "origin/dev")

    result = _CLI를_부른다(work)

    assert result.returncode == 0, result.stdout + result.stderr
