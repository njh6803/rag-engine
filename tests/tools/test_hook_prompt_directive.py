"""tools/hook_prompt_directive.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tools.hook_prompt_directive import (
    TITLE_CALL,
    TITLE_FALLBACK,
    block_reason_for,
    context_for,
    directive_branch,
    first_turn_context,
    has_assistant_turn,
    is_first_turn,
)

# next-session 의 지시문 형식과 칸마다의 규칙이 든 파일. 그 스킬이 상황마다 나뉜 뒤(harness 027)의
# 자리다.
NEXT_SESSION = Path(__file__).parents[2] / ".claude" / "skills" / "next-session" / "directive.md"
ISSUE_TRACKER = Path(__file__).parents[2] / "docs" / "agents" / "issue-tracker.md"

# 티켓 05 세션이 실제로 받은 첫 메시지(2026-09-23). 앱이 딥링크의 첫 `/` 를 U+FF0F 로 바꿔 넣었고
# 사람이 고치지 않고 보냈다. 시작 프롬프트 줄의 `/` 는 ASCII 그대로다.
DIRECTIVE = """／implement .scratch/admin-api/issues/05-traces-list.md

다음 작업: .scratch/admin-api/issues/05-traces-list.md. GET /traces — 실행 요약 목록과 다음 커서
다음 단계: 구현
어디서: 새 세션
시작 프롬프트: /implement .scratch/admin-api/issues/05-traces-list.md
브랜치: feature/05-traces-list
읽을 것: docs/journal/2026-09-23-03-plugins.md 의 "다음"
이어받을 상태: 없음
확인할 선행 조건: 없음
이번 요청 범위: 구현·리뷰·커밋까지. PR과 병합은 사용자가 말할 때"""


def test_지시문의_브랜치는_다시_풀기_러너도_쓰는_공개_이름으로_읽는다() -> None:
    """`tools/rerun_continue.py`가 이 함수로 인계 지시문을 알아본다(명세 "이어 가기와 끝")."""
    assert directive_branch(DIRECTIVE) == "feature/05-traces-list"
    assert directive_branch(DIRECTIVE.replace("어디서: 새 세션", "어디서: 이 세션")) is None
    assert directive_branch("브랜치: feature/x 만 있는 글") is None


def test_next_session_스킬의_지시문_형식을_채우면_알아본다() -> None:
    """형식의 원천은 next-session 스킬이다.

    거기서 라벨이 바뀌면 훅은 예외 없이 침묵하므로 여기서 잡는다.
    """
    text = NEXT_SESSION.read_text(encoding="utf-8")
    block = text.split("## 형식", 1)[1].split("```", 2)[1]
    filled: list[str] = []
    for line in block.strip().splitlines():
        label, _, placeholder = line.partition(":")
        if label == "어디서":
            assert "새 세션" in placeholder
            filled.append("어디서: 새 세션")
        elif label == "브랜치":
            filled.append("브랜치: chore/x")
        else:
            filled.append(line)

    context = context_for("/implement x\n\n" + "\n".join(filled))

    assert context is not None
    assert "`chore/x`" in context


def test_새_세션_지시문이면_브랜치_이름으로_제목을_바꾸는_계기다() -> None:
    context = context_for(DIRECTIVE.replace("／", "/", 1))

    assert context is not None
    assert "set_session_title" in context
    assert "`self`" in context
    assert "`feature/05-traces-list`" in context
    assert "SKILL.md" not in context


def test_self가_거부되면_세션_ID를_대신_넘기라고_한다() -> None:
    """클라우드 세션의 `set_session_title` 은 `self` 를 거부했다(대기열 81, 일지 2026-10-01-05).

    세 낱말은 지시의 세 갈래를 대신한다. "거부"는 거부될 때의 분기, "세션의 ID"는 ID 로 바꿔
    넘기기, "알린다"는 찾지 못했을 때 사용자에게 알리기다. 어순은 보지 않는다.
    """
    context = context_for(DIRECTIVE.replace("／", "/", 1))

    assert context is not None
    assert "거부" in context
    assert "세션의 ID" in context
    assert "알린다" in context


def test_첫_글자가_전각이면_스킬_파일을_읽어_따르라는_계기가_붙는다() -> None:
    context = context_for(DIRECTIVE)

    assert context is not None
    assert "`feature/05-traces-list`" in context
    assert "`.claude/skills/implement/SKILL.md`" in context


def test_어디서가_새_세션이_아니면_계기가_아니다() -> None:
    """이유 칸에서 결정표를 인용해도 줄 머리가 `이 세션`이면 이 세션이다(next-session 결정표)."""
    this_session = DIRECTIVE.replace("어디서: 새 세션", "어디서: 이 세션")
    quoting = DIRECTIVE.replace(
        "어디서: 새 세션",
        "어디서: 이 세션. 결정표의 `어디서: 새 세션`과 다른 것은 컨텍스트가 자산이라서다",
    )

    assert context_for(this_session) is None
    assert context_for(quoting) is None


def test_어디서_줄의_이유는_새_세션_판정을_바꾸지_않는다() -> None:
    with_reason = DIRECTIVE.replace(
        "어디서: 새 세션", "어디서: 새 세션. 티켓 하나가 컨텍스트 하나다"
    )

    assert context_for(with_reason) is not None


def test_브랜치_줄이_없거나_비었으면_계기가_아니다() -> None:
    without = "\n".join(line for line in DIRECTIVE.splitlines() if not line.startswith("브랜치:"))
    empty = DIRECTIVE.replace("브랜치: feature/05-traces-list", "브랜치: ")

    assert context_for(without) is None
    assert context_for(empty) is None


def test_평범한_프롬프트와_형식을_설명하는_문장은_계기가_아니다() -> None:
    """줄 머리의 `브랜치:`·`어디서:` 만 본다. 문장 속에서 형식을 인용한 것은 지시문이 아니다."""
    for prompt in (
        "테스트를 돌려 줘",
        "／implement .scratch/x.md",
        "지시문이면(`브랜치:` 줄과 `어디서: 새 세션` 줄이 있다) 계기를 넣는다",
    ):
        assert context_for(prompt) is None, prompt


def test_브랜치_값을_감싼_백틱과_CRLF는_벗긴다() -> None:
    wrapped = DIRECTIVE.replace(
        "브랜치: feature/05-traces-list", "브랜치: `feature/05-traces-list`"
    )
    context = context_for(wrapped.replace("\n", "\r\n"))

    assert context is not None
    assert "`feature/05-traces-list`" in context
    assert "``" not in context
    assert "\r" not in context


def test_스킬_이름이_케밥_하나가_아니면_읽을_경로를_만들지_않는다() -> None:
    """이름이 경로가 되므로 `..`·구분자·플러그인 접두어는 받지 않는다."""
    for first_line in ("／../../secrets x", "／plugin:skill x", "／ implement x", "／"):
        context = context_for(DIRECTIVE.replace(DIRECTIVE.splitlines()[0], first_line, 1))

        assert context is not None, first_line
        assert "SKILL.md" not in context, first_line


# open_session.ps1 의 Convert-StartLine 이 옮긴 첫 줄. 스킬 파일을 상대 경로로 가리키고, 연
# 저장소를 표지로 든다. 상대 경로라 저장소가 아닌 폴더에서는 파일을 못 찾아 멈추고, 표지로 훅이
# 폴더를 가른다.
ROOT = "C:\\project\\agent"


def _opened(root: str = ROOT, skill: str = "implement") -> str:
    """Convert-StartLine 이 만드는 모양의 첫 줄로 DIRECTIVE 를 연다. 모양의 원천은 ps1 이고, 그
    함수를 pwsh 로 불러 이 훅에 넘기는 대조는 tests/tools/test_open_session.py 에 있다."""
    first = (
        f".claude/skills/{skill}/SKILL.md 를 읽어 그대로 따른다. "
        f"이 세션을 연 저장소는 `{root}`이고 "
        "작업 폴더가 그곳이 아니면 따르지 말고 알린다. 스킬의 인자는 이 줄의 '인자:' 뒤부터 메시지 "
        "끝까지다. 인자: .scratch/admin-api/issues/05-traces-list.md"
    )
    return DIRECTIVE.replace(DIRECTIVE.splitlines()[0], first, 1)


def test_연_저장소와_작업_폴더가_같으면_막지_않고_이름을_붙인다() -> None:
    assert block_reason_for(_opened(), ROOT) is None
    context = context_for(_opened())
    assert context is not None
    assert "`feature/05-traces-list`" in context


def test_작업_폴더가_연_저장소와_다르면_프롬프트를_막는다() -> None:
    """딥링크는 폴더를 싣지 않고 앱이 마지막 폴더를 쓴다. 그것이 워크트리면 거기에도 같은 스킬
    파일이 있어, 사람이 보내기 전에 폴더를 보던 눈 없이 엉뚱한 곳에서 시작한다(PR #65 의
    CodeRabbit). 모델에게 권하는 것이 아니라 프롬프트를 막는다 — 첫 줄은 "그대로 따른다"라고
    말하므로 권고는 그것과 다툰다."""
    worktree = f"{ROOT}\\.claude\\worktrees\\silly-carson-627e95"

    reason = block_reason_for(_opened(), worktree)

    assert reason is not None
    assert f"`{worktree}`" in reason
    assert f"`{ROOT}`" in reason


def test_작업_폴더를_모르면_막는다() -> None:
    """비교할 수 없으면 막는 쪽이다. 빈 문자열도 모르는 것이다."""
    for cwd in (None, ""):
        reason = block_reason_for(_opened(), cwd)

        assert reason is not None, cwd
        assert "(알 수 없음)" in reason, cwd


def test_폴더_비교는_구분자와_대소문자와_끝의_구분자를_가리지_않는다() -> None:
    """윈도 경로라 대소문자를 가리지 않는다. 운영체제의 정규화에 맡기지 않아 CI 에서도 같은
    답이다."""
    for cwd in ("c:/project/agent", "C:\\project\\agent\\", "C:/Project/Agent/"):
        assert block_reason_for(_opened(), cwd) is None, cwd


def test_연_저장소가_워크트리이거나_공백이_든_경로여도_같은_폴더면_막지_않는다() -> None:
    for root in (f"{ROOT}\\.claude\\worktrees\\wt", "C:\\My Docs\\agent"):
        assert block_reason_for(_opened(root=root), root) is None, root
        assert block_reason_for(_opened(root=root), ROOT + "\\other") is not None, root


def test_옮기지_않은_첫_줄이나_지시문이_아니면_막지_않는다() -> None:
    """슬래시 명령과 전각은 앱이 연 폴더에서 스킬을 찾는다. 가리키는 저장소가 따로 없다. 지시문이
    아닌 프롬프트는 이 훅의 일이 아니다."""
    not_directive = "\n".join(
        line for line in _opened().splitlines() if not line.startswith("브랜치:")
    )
    for prompt in (DIRECTIVE, DIRECTIVE.replace("／", "/", 1), not_directive):
        assert block_reason_for(prompt, "D:\\elsewhere") is None


def test_스킬_파일로_시작하는데_연_저장소_표지를_못_읽으면_막는다() -> None:
    """쏘는 ps1 은 여는 세션의 체크아웃 사본이고 파싱하는 훅은 받는 세션의 주 체크아웃 사본이다.

    두 사본의 문구가 갈리면 표지를 못 읽는다. 그때 지나가면 폴더 가드가 조용히 꺼지므로 막는다
    (2026-10-05 워크트리 감사 13). 작업 폴더가 맞아 보여도 비교할 표지가 없으니 막는다.
    """
    drifted = _opened().replace("이 세션을 연 저장소는 `", "연 저장소: `", 1)

    for cwd in (ROOT, "D:\\elsewhere"):
        reason = block_reason_for(drifted, cwd)

        assert reason is not None, cwd
        assert "표지" in reason, cwd
        assert "open_session.ps1" in reason, cwd


def test_사람이_스킬_경로로_시작해_쓴_지시문은_막지_않는다() -> None:
    """막는 것은 ps1 이 만드는 고정 머리(`<스킬 경로> 를 읽어 그대로 따른다.`)로 시작할 때뿐이다.

    사람이 손으로 쓴 첫 줄이 스킬 경로로 시작해도 그 머리가 아니면 open-session 이 옮긴 줄이 아니다.
    """
    human = DIRECTIVE.replace(
        DIRECTIVE.splitlines()[0], ".claude/skills/implement/SKILL.md 를 참고해 구현한다", 1
    )

    assert block_reason_for(human, ROOT) is None


def test_어디서_줄이_워크트리를_말하면_계기가_그것을_먼저_따르라고_한다() -> None:
    """받는 쪽은 지시문 자체다. implement 밖의 시작 프롬프트(설계·명세·티켓·chore)도 지나는 자리라
    첫 턴 계기가 짚는다(next-session `directive.md`, 2026-10-06 수정 검증)."""
    worktree = DIRECTIVE.replace(
        "어디서: 새 세션",
        "어디서: 새 세션. 나란히 여는 2 중 1. 주 체크아웃에서 브랜치를 따지 않고 "
        "EnterWorktree(name은 브랜치의 마지막 토막)로 새 워크트리에 먼저 들어가 "
        "거기서 브랜치를 바꾼다",
    )

    with_worktree = context_for(worktree)
    plain = context_for(DIRECTIVE)

    assert with_worktree is not None
    assert "워크트리" in with_worktree
    assert "먼저" in with_worktree
    assert plain is not None
    assert "EnterWorktree" not in plain


WORKTREE_SENTENCE = (
    "주 체크아웃에서 브랜치를 따지 않고 EnterWorktree(name은 브랜치의 마지막 토막)로 새 워크트리에 "
    "먼저 들어가 거기서 브랜치를 바꾼다"
)
WORKTREE_WHERE = "어디서: 새 세션. " + WORKTREE_SENTENCE
STALE_ROOT = (
    "확인할 선행 조건: 주 체크아웃 미갱신: 루트는 main. 병합은 이 워크트리 사본의 next-session "
    'merge.md(없으면 SKILL.md)의 "워크트리에서 병합할 때"를 Read로 열어 따른다'
)


def _stale(where: str = WORKTREE_WHERE, condition: str = STALE_ROOT) -> str:
    """워크트리에서 병합한 세션이 낸 지시문(next-session `merge.md` "워크트리에서 병합할 때" 4).

    "어디서" 줄의 tidy-checkouts 머리는 기본으로 넣지 않는다. 쓰는 쪽이 머리를 빠뜨려도 훅은 짚는다.
    """
    return DIRECTIVE.replace("어디서: 새 세션", where).replace("확인할 선행 조건: 없음", condition)


def _bundled(k: str, head: str = "") -> str:
    """나란히 여는 둘 중 k 번째 지시문의 "어디서" 줄. `head` 는 워크트리 문장 앞에 붙는다."""
    return f"어디서: 새 세션. 나란히 여는 2 중 {k}. {head}{WORKTREE_SENTENCE}"


# 계기가 tidy-checkouts 를 돌라고 하는 문구. 문구를 다듬으면 여기 한 곳만 고친다.
RUNS_TIDY = "Skill 도구로 `tidy-checkouts` 를 돈다"


def test_주_체크아웃_미갱신이면_워크트리_전에_tidy_checkouts를_돌라고_한다() -> None:
    """새 세션은 EnterWorktree 전까지 주 체크아웃 세션이라 그 스킬이 루트를 당길 수 있다.

    들어간 뒤에는 그 스킬이 1에서 멈춘다. 그래서 순서를 짚는다(next-session "워크트리에서 병합할
    때" 4). 그 스킬이 사람에게 넘기는 확인을 기다리면 첫 턴이 멈추므로 잇게 한다.
    """
    context = context_for(_stale())

    assert context is not None
    assert "`tidy-checkouts`" in context
    assert "Skill" in context
    assert context.index("set_session_title") < context.index("`tidy-checkouts`")
    assert context.index("`tidy-checkouts`") < context.index("'어디서' 줄이 워크트리")
    assert "`tidy-checkouts` 를 돈 뒤 다른 일보다 먼저" in context
    assert "제목을 바꾼 뒤 다른 일보다 먼저" not in context
    assert "기다리지 않" in context


def test_나란히_여는_묶음이면_첫_세션만_tidy_checkouts를_돈다() -> None:
    """함께 돌면 같은 루트를 당기거나 같은 워크트리를 지우려 할 수 있다. 첫 세션(k=1)만 돈다.

    k 는 글자 그대로 1일 때만 첫 세션이다. 잘못 적은 0 이나 `01` 은 돌지 않는 쪽으로 틀린다.
    """
    first = context_for(_stale(where=_bundled("1")))

    assert first is not None
    assert RUNS_TIDY in first
    for k in ("2", "3", "0", "01"):
        later = context_for(_stale(where=_bundled(k)))
        assert later is not None, k
        assert RUNS_TIDY not in later, k
        assert "돌지 않는다" in later, k
        assert "첫 세션" in later, k


def test_미갱신은_확인할_선행_조건_줄의_머리_라벨로만_알아본다() -> None:
    """다른 줄이 미갱신을 인용하거나 줄 머리가 아닌 데서 라벨을 인용한 것은 세지 않는다.

    같은 줄이라도 형식(`주 체크아웃 미갱신: 루트는 …`)의 콜론이 없는 부정이나 설명은 세지 않는다.
    """
    quoted = _stale(condition="확인할 선행 조건: 없음").replace(
        "이어받을 상태: 없음", "이어받을 상태: 앞 세션 일지에 `주 체크아웃 미갱신` 한 줄이 있다"
    )
    inline = _stale(condition="확인할 선행 조건: 없음").replace(
        "읽을 것:", "읽을 것: 확인할 선행 조건: 주 체크아웃 미갱신: 형식은 next-session 3.", 1
    )
    negated = _stale(condition="확인할 선행 조건: 주 체크아웃 미갱신 아님(이 세션이 당겼다)")
    no_stale = _stale(condition="확인할 선행 조건: 없음")

    for prompt in (quoted, inline, negated, no_stale):
        context = context_for(prompt)
        assert context is not None
        assert "tidy-checkouts" not in context


def test_미갱신인데_워크트리_문장이_없어도_tidy_checkouts를_먼저_돈다() -> None:
    """주 체크아웃에서 끊은 작업을 잇는 지시문이면 워크트리 문장이 없다. 그래도 루트는 낡았다."""
    context = context_for(_stale(where="어디서: 새 세션"))

    assert context is not None
    assert RUNS_TIDY in context
    assert "EnterWorktree" not in context


def test_next_session_스킬이_적으라는_미갱신_문구를_훅이_알아본다() -> None:
    """훅은 글자로 판정한다. 지시문을 쓰는 쪽의 문구가 갈리면 계기가 조용히 빠진다.

    next-session `directive.md` 가 적으라는 것을 그대로 꺼내 지시문을 짓고 훅에 준다. 첫 지시문의
    "어디서" 머리, "확인할 선행 조건"의 두 줄(묶음의 나머지와 그 밖), 형식 블록의 라벨이다. 머리는
    순서와 기다리지 않기를 스스로 말하고 워크트리 문장보다 앞에 와야 한다 — 이 계기를 들인 뒤 주
    체크아웃이 처음 당겨지기 전의 옛 훅과 옛 implement 는 워크트리 문장을 먼저 따르라고만 한다.
    """
    text = NEXT_SESSION.read_text(encoding="utf-8")
    form = text.split("## 형식", 1)[1].split("```", 2)[1]
    assert any(line.startswith("확인할 선행 조건:") for line in form.splitlines())
    assert "`새 세션. 나란히 여는 <N> 중 <k>.`" in text
    assert "`주 체크아웃 미갱신: 루트는 <브랜치>`" in text
    rests = re.findall(r"`(주 체크아웃 미갱신: 루트는 <브랜치>\.[^`]*)`", text)
    heads = re.findall(r"`(주 체크아웃 미갱신이라 [^`]*)`", text)
    assert len(rests) == 1, rests
    assert len(heads) == 1, heads
    rest = rests[0].replace("<브랜치>", "main")
    head = heads[0]
    assert "첫 세션" in rest
    assert "tidy-checkouts" in head
    assert "먼저" in head
    assert "기다리지 않" in head

    first = _stale(
        where=_bundled("1", head + " "),
        condition="확인할 선행 조건: 주 체크아웃 미갱신: 루트는 main",
    )
    where_line = next(line for line in first.splitlines() if line.startswith("어디서:"))
    first_context = context_for(first)
    rest_context = context_for(_stale(where=_bundled("2"), condition=f"확인할 선행 조건: {rest}"))

    assert where_line.index("tidy-checkouts") < where_line.index("EnterWorktree")
    assert first_context is not None
    assert RUNS_TIDY in first_context
    assert rest_context is not None
    assert "돌지 않는다" in rest_context


def test_스킬_파일로_시작해도_지시문이_아니면_막지_않는다() -> None:
    """막는 것은 open-session 이 옮긴 지시문뿐이다.

    사람이 스킬 경로로 시작한 보통 프롬프트는 지나간다.
    """
    plain = ".claude/skills/implement/SKILL.md 를 읽고 요약해 줘"

    assert block_reason_for(plain, ROOT) is None


# 손으로 연 세션에 일지에 적으라는 계기의 표지(대기열 72). 문구를 다듬으면 여기 한 곳만 고친다.
PASTED = "대기열 72"
# 지시문 본문만(시작 프롬프트 줄과 빈 줄을 뺀 것). 사람이 앞 세션의 출력에서 지시문만 옮긴 꼴이다.
BODY = DIRECTIVE.split("\n\n", 1)[1]


def _skill_root(root: Path, skill: str = "implement") -> str:
    """`.claude/skills/<skill>/SKILL.md` 가 있는 작업 폴더. open-session 의 `Convert-StartLine` 이
    첫 줄을 옮기는 조건이 그 파일이다."""
    skill_file = root / ".claude" / "skills" / skill / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("---\nname: x\n---\n", encoding="utf-8")
    return str(root)


def test_반각_슬래시의_이_저장소_스킬로_시작하면_손으로_연_세션이라_일지에_적으라고_한다(
    tmp_path: Path,
) -> None:
    """대기열 72. open-session 은 이 저장소의 스킬 명령을 스킬 파일 문장으로 옮겨 보내므로, 반각
    `/` 원문이 남은 첫 줄은 사람이 붙여 넣은 것이다. 앞 세션의 여는 일이 실패한 것은 앞 세션의
    일지가 병합된 뒤라 거기 적힐 자리가 없다. 반각 `/` 는 진짜 명령이 되어도 훅이 원문을
    받는다(`.scratch/harness/probes/slash_prompt_payload/probe.py`)."""
    context = context_for(DIRECTIVE.replace("／", "/", 1), _skill_root(tmp_path))

    assert context is not None
    assert PASTED in context
    assert "`/implement`" in context
    assert "일지" in context
    assert "`feature/05-traces-list`" in context
    assert context.index("set_session_title") < context.index(PASTED)
    # 계기는 첫 턴에만 와서, 단계를 닫을 때까지 미루면 압축이나 끊김에 사라진다(셀프 리뷰 두 축)
    assert "바로 적는다" in context
    assert "`date +%Y-%m-%d-%H%M`" in context
    assert "`Get-Date -Format yyyy-MM-dd-HHmm`" in context
    assert "docs/journal/<날짜>-<HHMM>-<슬러그>.md" in context


def test_첫_줄이_지시문의_라벨_줄이면_손으로_연_세션이다() -> None:
    """open-session 은 시작 프롬프트를 늘 첫 줄에 둔다(그 스킬 2단계). 첫 줄이 지시문의 라벨 줄이면
    사람이 지시문만 붙여 넣은 것이다. 하네스 chore 처럼 슬래시 명령이 아닌 시작 프롬프트도 이 꼴로
    잡힌다. 스킬 파일을 보지 않으므로 작업 폴더를 몰라도 같다."""
    for prompt in (BODY, "\n  " + BODY, BODY.replace("\n", "\r\n")):
        context = context_for(prompt, None)

        assert context is not None, prompt[:20]
        assert PASTED in context, prompt[:20]
        assert "`다음 작업:`" in context, prompt[:20]


def test_open_session_이_보낸_꼴이면_일지에_적으라고_하지_않는다(tmp_path: Path) -> None:
    """스킬 파일 문장으로 옮긴 첫 줄, 옮기지 못한 채 전각으로 남은 첫 줄(`held=` 뒤 고치지 않고
    보냈다), 슬래시 명령이 아닌 시작 프롬프트."""
    root = _skill_root(tmp_path)
    for prompt in (_opened(), DIRECTIVE, "대기열 1 을 반영한다\n\n" + BODY):
        context = context_for(prompt, root)

        assert context is not None, prompt[:20]
        assert PASTED not in context, prompt[:20]


def test_스킬_파일이_없는_반각_슬래시는_적으라고_하지_않는다(tmp_path: Path) -> None:
    """open-session 은 스킬 파일이 없는 슬래시 명령만 옮기지 못해 `held=` 로 멈추고, 사람이 첫 글자
    `／` 를 `/` 로 고쳐 보낸다(그 스킬 3단계). 손으로 붙여 넣은 것과 글이 같아 가르지 못하므로
    적으라고 하지 않는다. 작업 폴더를 모를 때도 스킬 파일을 볼 수 없어 같다."""
    halfwidth = DIRECTIVE.replace("／", "/", 1)

    for cwd in (str(tmp_path), None):
        context = context_for(halfwidth, cwd)

        assert context is not None, cwd
        assert PASTED not in context, cwd


def test_못_보는_것_사람이_평범한_시작_프롬프트를_첫_줄에_쳐_붙여_넣으면_가르지_못한다(
    tmp_path: Path,
) -> None:
    """거짓 음성이다. 슬래시 명령이 아닌 시작 프롬프트는 open-session 이 옮기지 않아, 사람이 그 줄을
    먼저 치고 지시문을 붙여 넣으면 open-session 이 보낸 글과 같다."""
    by_hand = "대기열 72·293·300 을 chore 한 PR 로 반영한다\n\n" + BODY

    context = context_for(by_hand, _skill_root(tmp_path))

    assert context is not None
    assert PASTED not in context


def test_못_보는_것_스킬이_한쪽에만_있으면_틀린다(tmp_path: Path) -> None:
    """첫 줄을 옮기는 쪽은 여는 쪽 루트의 스킬 파일을, 이 판정은 이 세션의 작업 폴더의 스킬 파일을
    본다. 같은 반각 첫 줄도 작업 폴더에만 스킬이 있으면(여는 쪽은 옮기지 못해 `held=` 뒤 사람이 고쳐
    보냈다) 붙여 넣은 것으로 보고(거짓 양성), 작업 폴더에 없으면(여는 쪽은 옮겼어야 했다)
    놓친다(거짓 음성)."""
    halfwidth = DIRECTIVE.replace("／", "/", 1)
    only_here = context_for(halfwidth, _skill_root(tmp_path / "here"))
    (tmp_path / "missing").mkdir()
    missing_here = context_for(halfwidth, str(tmp_path / "missing"))

    assert only_here is not None
    assert PASTED in only_here
    assert missing_here is not None
    assert PASTED not in missing_here


def test_next_session_지시문_형식의_라벨을_훅이_안다() -> None:
    """첫 줄이 라벨 줄인지는 형식의 라벨로 가른다. 형식에 라벨이 늘면 그 줄로 시작한 붙여 넣기를
    놓친다."""
    text = NEXT_SESSION.read_text(encoding="utf-8")
    form = text.split("## 형식", 1)[1].split("```", 2)[1]
    labels = [line.split(":", 1)[0] + ":" for line in form.strip().splitlines()]

    assert labels
    for label in labels:
        context = context_for(f"{label} x\n\n" + BODY, None)
        assert context is not None, label
        assert PASTED in context, label


def test_모델이_아직_답하지_않은_트랜스크립트는_첫_턴이다() -> None:
    """지시문으로 연 세션은 지시문이 첫 메시지다. 훅이 도는 시점엔 assistant 기록이 없다."""
    first_turn = [
        '{"type":"queue-operation","operation":"enqueue"}',
        '{"type":"attachment","attachment":{"type":"hook_additional_context"}}',
        '{"type":"user","message":{"role":"user","content":"／implement x"}}',
    ]

    assert has_assistant_turn(first_turn) is False
    assert has_assistant_turn([]) is False


def test_모델이_한_번이라도_답했으면_첫_턴이_아니다() -> None:
    """진행 중인 대화에 지시문을 붙여 넣은 것은 새 세션이 아니다(이 훅을 만든 세션에서 실측)."""
    ongoing = [
        '{"type":"user","message":{"role":"user","content":"훅을 만든다"}}',
        '{"type":"assistant","message":{"role":"assistant","content":[]}}',
        '{"type":"user","message":{"role":"user","content":"```\\n브랜치: x\\n```"}}',
    ]

    assert has_assistant_turn(ongoing) is True


def test_기록의_종류는_최상위_type만_보고_깨진_줄은_건너뛴다() -> None:
    """본문 속의 `"type":"assistant"` 는 기록의 종류가 아니다. 최상위 `type` 만 본다.

    잘린 줄은 훅이 읽는 동안 앱이 마지막 줄을 쓰고 있을 때 생긴다.
    """
    lines = [
        "not json",
        "[]",
        '{"type":"user","message":{"content":"잘린',
        '{"type":"user","message":{"content":"{\\"type\\":\\"assistant\\"}"}}',
        '{"type":"attachment","attachment":{"type":"assistant"}}',
    ]

    assert has_assistant_turn(lines) is False
    assert has_assistant_turn([*lines, '{"type":"assistant"}']) is True


def test_트랜스크립트_파일이_아직_없으면_첫_턴이다(tmp_path: Path) -> None:
    """새 세션의 첫 프롬프트에서는 트랜스크립트가 만들어지기 전일 수 있다."""
    assert is_first_turn(str(tmp_path / "없음.jsonl")) is True


def test_트랜스크립트에_assistant_기록이_생기면_첫_턴이_끝난다(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('{"type":"user"}\n', encoding="utf-8")
    assert is_first_turn(str(transcript)) is True

    transcript.write_text('{"type":"user"}\n{"type":"assistant"}\n', encoding="utf-8")
    assert is_first_turn(str(transcript)) is False


def test_트랜스크립트_경로를_모르면_첫_턴이라고_하지_않는다() -> None:
    """잘못 발동하면 엉뚱한 세션의 이름이 조용히 바뀐다. 모를 때는 발동하지 않아야 드러난다."""
    assert is_first_turn(None) is False
    assert is_first_turn("") is False


# 첫 턴 티켓 알림(티켓 ticket-for-every-pr 05). 지시문이 아닌 첫 메시지에 티켓·브랜치·제목의 차례를
# 알린다. 명세는 `.scratch/ticket-for-every-pr/spec.md` 의 "첫 턴 알림"이다.
PLAIN = "끝났어?"
USED = '{"type":"user"}\n{"type":"assistant"}\n'
# 앱의 예약 작업이 연 세션의 첫 메시지 머리. 2026-10-22 의 `morning-report-work` 세션
# 트랜스크립트에서 옮겼다.
SCHEDULED = (
    '<scheduled-task name="morning-report-work" '
    'file="C:\\Users\\User\\.claude\\scheduled-tasks\\morning-report-work\\SKILL.md">\n'
    "This is an automated run of a scheduled task. The user is not present to answer questions."
)


def _notice(
    prompt: str = PLAIN,
    transcript: str | None = None,
    attended: str | None = None,
    marker: str | None = None,
) -> str | None:
    return first_turn_context(prompt, None, transcript, attended, marker)


def test_사람이_보는_세션의_첫_턴_보통_프롬프트에는_티켓_차례를_알린다(tmp_path: Path) -> None:
    """낱말은 차례의 자리를 대신한다. 워크트리 먼저, 두는 다른 티켓의 브랜치, 티켓 자리(기능 밖의
    제품 코드 고침 포함)와 번호 명령과 상태(이미 있는 티켓의 상태 포함), 브랜치 맞추기, 제목,
    따르지 않는 때 셋(면제 일의 회고 티켓 포함), 커밋 검사와 규약 원천이다. 어순은 보지 않는다(다른
    티켓의 브랜치만 아래 시험이 본다)."""
    notice = _notice(transcript=str(tmp_path / "없음.jsonl"))

    assert notice is not None
    for word in (
        "`EnterWorktree`",
        "제품 코드",
        "`.scratch/harness/issues/<slug>.md`",
        "번호 없이",
        "`in-progress`",
        "`ready-for-agent`",
        "`git branch -m",
        "다른 티켓의 브랜치",
        TITLE_CALL,
        "질문",
        "`docs/<slug>`",
        "`retro`",
        "인계",
        "`tools/check_ticket.py`",
        "`docs/agents/issue-tracker.md`",
    ):
        assert word in notice, word
    # harness 티켓은 번호를 받지 않아 번호 도구를 치라는 말과 다시 치라는 말이 없다
    assert "sibling_overlap" not in notice
    assert "티켓 NNN" not in notice
    assert "NNN" not in notice


def test_알림의_규약_낱말은_원천_문서에_있다(tmp_path: Path) -> None:
    """알림은 `docs/agents/issue-tracker.md` 의 규약을 옮긴 사본이다. 원천이 브랜치 모양, 상태 값,
    면제 브랜치, 커밋 검사의 이름을 바꾸면 여기서 빨갛다(PR #354 claude-review). 원천에 다른 말로
    적힌 것(워크트리, 제목 도구)은 대조하지 않는다."""
    notice = _notice(transcript=str(tmp_path / "없음.jsonl"))
    source = ISSUE_TRACKER.read_text(encoding="utf-8")

    assert notice is not None
    for word in (
        "`feature/<NN>-<slug>`",
        "`chore/<slug>`",
        "`.scratch/harness/issues/<slug>.md`",
        "`ready-for-agent`",
        "`in-progress`",
        "`docs/<slug>`",
        "`tools/check_ticket.py`",
    ):
        assert word in notice, word
        assert word in source, word


def test_다른_티켓의_브랜치는_티켓을_쓰기_전에_본다(tmp_path: Path) -> None:
    """다른 티켓의 워크트리에서 연 세션이 다른 일을 받으면, 차례대로 따른 1)이 남의 워크트리에 새
    티켓을 먼저 쓴다. 그래서 그 조건은 1) 앞에 온다(PR 직전 `bug-perf-review`, 일지
    2026-10-22-29)."""
    notice = _notice(transcript=str(tmp_path / "없음.jsonl"))

    assert notice is not None
    assert notice.index("다른 티켓의 브랜치") < notice.index("1) 티켓을 쓴다")


def test_첫_턴이_아니면_보통_프롬프트에_알리지_않는다(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(USED, encoding="utf-8")

    assert _notice(transcript=str(transcript)) is None


def test_헤드리스_표지가_있으면_알리지_않는다(tmp_path: Path) -> None:
    """`claude -p` 는 `CLAUDE_CODE_SESSION_ATTENDED=0` 이고, 카나리아는 표지 변수를 붙인다."""
    new = str(tmp_path / "없음.jsonl")

    assert _notice(transcript=new, attended="0") is None
    assert _notice(transcript=new, marker="1") is None
    assert _notice(transcript=new, attended="1", marker="") is not None


def test_헤드리스와_예약_작업은_트랜스크립트를_열지_않고_거른다(tmp_path: Path) -> None:
    """거르기를 트랜스크립트보다 먼저 본다. 폴더는 열 수 없는 트랜스크립트 자리다."""
    folder = str(tmp_path)

    assert _notice(transcript=folder, attended="0") is None
    assert _notice(transcript=folder, marker="1") is None
    assert _notice(SCHEDULED, transcript=folder) is None
    # 대조: 사람이 보는 세션의 보통 프롬프트는 그 자리를 열려다 실패한다. 위 셋이 열지 않았다는
    # 표지다.
    with pytest.raises(OSError):
        _notice(transcript=folder)


def test_예약_작업이_연_세션의_첫_메시지에는_알리지_않는다(tmp_path: Path) -> None:
    """앱의 예약 작업이 연 세션은 헤드리스 가름으로 헤드리스로 보이지 않는다(명세 "첫 턴 알림"의
    2026-10-21 검토 주석). 첫 메시지의 머리로 거른다. 문장 속에서 그 꼴을 든 것은 거르지 않는다."""
    new = str(tmp_path / "없음.jsonl")

    assert _notice(SCHEDULED, transcript=new) is None
    assert _notice("\n" + SCHEDULED, transcript=new) is None
    assert _notice("`<scheduled-task ` 로 시작하는 세션을 본다", transcript=new) is not None


def test_지시문이면_지금_계기만_있고_티켓_알림은_없다(tmp_path: Path) -> None:
    """지시문의 계기(제목, tidy-checkouts, 폴더 막기)는 헤드리스 가름과 상관없이 그대로다."""
    new = str(tmp_path / "없음.jsonl")
    directive = DIRECTIVE.replace("／", "/", 1)
    notice = _notice(transcript=new)
    assert notice is not None

    for attended in (None, "0"):
        context = _notice(directive, transcript=new, attended=attended)
        assert context == context_for(directive)
        assert context is not None
        assert "`tools/check_ticket.py`" not in context
        assert notice not in context


def test_못_보는_것_질문만_하는_세션에도_알린다(tmp_path: Path) -> None:
    """첫 메시지만으로는 커밋할 세션인지 가르지 못한다. 알림이 질문을 따르지 않는 때로 든다."""
    assert _notice("이 훅은 언제 트랜스크립트를 여나?", str(tmp_path / "없음.jsonl")) is not None


def test_못_보는_것_슬래시_명령으로_연_세션에도_알린다(tmp_path: Path) -> None:
    """지시문이 아닌 첫 메시지라 커밋하지 않는 스킬(`/tidy-checkouts`)로 연 세션도 알림을 받는다.
    알림이 커밋할 일이 없으면 따르지 않는다고 든다."""
    assert _notice("/tidy-checkouts", str(tmp_path / "없음.jsonl")) is not None


def test_못_보는_것_지시문_모양을_붙여_넣고_다른_일을_시키면_알리지_않는다(tmp_path: Path) -> None:
    """지시문으로 보아 지시문 계기만 낸다."""
    pasted = DIRECTIVE.replace("／", "/", 1) + "\n\n이건 무시하고 README 오타만 고쳐 줘"
    context = _notice(pasted, str(tmp_path / "없음.jsonl"))

    assert context is not None
    assert "`tools/check_ticket.py`" not in context


def test_두_계기의_제목_문구가_같다(tmp_path: Path) -> None:
    """제목 문구는 지시문 계기의 것을 그대로 쓴다(티켓 05). 한쪽만 고치면 여기서 빨갛다."""
    directive = context_for(DIRECTIVE.replace("／", "/", 1))
    notice = _notice(transcript=str(tmp_path / "없음.jsonl"))

    for context in (directive, notice):
        assert context is not None
        assert TITLE_CALL in context
        assert TITLE_FALLBACK in context
