"""tools/hook_bash_gate_pipe.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다.

대기열 19 의 네 사건이 이 테스트의 입력이다 — 게이트를 `tail` 에 넘긴 뒤 `$?` 를 읽었다.
"""

from __future__ import annotations

from tools.hook_bash_gate_pipe import is_gate, warnings_for


def test_게이트_명령_자리를_알아본다() -> None:
    assert is_gate("uv run pytest -q")
    assert is_gate("PYTHONUTF8=1 uv run --no-sync python tools/check_instructions.py")
    assert is_gate("uv run --env-file .env pytest -m llm")
    assert is_gate(" uv run ruff check .")
    assert is_gate("uv run lint-imports")
    assert is_gate("python -m pytest tests/tools")
    assert is_gate("py -3 -m pytest -q")
    assert not is_gate("echo pytest")
    assert not is_gate("git log")
    assert not is_gate("grep -rn pyright src")


def test_훅_러너도_게이트다() -> None:
    """CLAUDE.md 가 훅 러너를 게이트로 센다(대기열 95)."""
    assert is_gate("uv run python tools/run_hooks.py")
    assert len(warnings_for("uv run python tools/run_hooks.py 2>&1 | tail -3")) == 1


def test_검사_러너도_게이트다() -> None:
    """pre-commit 의 always_run 검사를 함께 띄우는 러너다(ADR 0005 이력 2026-10-07)."""
    assert is_gate("uv run python tools/run_checks.py")
    assert len(warnings_for("uv run python tools/run_checks.py 2>&1 | tail -3")) == 1


def test_형제_번호_대조도_게이트다() -> None:
    """출력대로 고칠 것이 있으면 1로 끝나는 판정이다. 조건의 원천은 그 도구의 독스트링이다.

    대기열 115·175·224·235.
    """
    assert is_gate("uv run python tools/sibling_overlap.py")
    assert len(warnings_for("uv run python tools/sibling_overlap.py | head -5")) == 1


def test_게이트마다_바로_읽은_dollar_question_은_훅_러너_뒤에서도_조용하다() -> None:
    """2026-10-02-03 세션의 명령에서 뒤의 게이트 쌍 셋을 옮기고 경로를 줄였다(앞의 쌍 넷은
    ruff·ruff format·pyright·lint-imports). 러너를 게이트로 보지 않아 마지막 `$?` 를 앞선
    `check_type_escapes` 의 것으로 읽고 두 번 경고했다(대기열 95)."""
    command = (
        "uv run python tools/check_instructions.py > S/g5.log 2>&1\n"
        'echo "instructions $?"\n'
        "uv run python tools/check_type_escapes.py > S/g6.log 2>&1\n"
        'echo "type escapes $?"\n'
        "uv run python tools/run_hooks.py > S/g7.log 2>&1\n"
        'echo "run_hooks $?"'
    )

    assert warnings_for(command) == []


def test_워크플로_감사도_게이트다() -> None:
    """zizmor 는 rag-engine 의 검증 명령이다(`.github/workflows/ci.yml` 의 python 잡)."""
    command = "uv run zizmor --offline --strict-collection --config .github/zizmor.yml ."

    assert is_gate(command)
    assert len(warnings_for(f"{command} 2>&1 | tail -5")) == 1
    assert warnings_for(f'{command} > S/zz.log 2>&1; echo "zizmor=$?"') == []
    assert not is_gate("echo zizmor")


def test_web_명령은_게이트로_보지_않는다() -> None:
    """agent-os 의 web 검증 명령은 rag-engine 에 없어 목록에서 뺐다(킥오프 7단계)."""
    assert not is_gate("pnpm -C web verify")
    assert not is_gate("pnpm -C web exec playwright test")


def test_경고는_파일로_리다이렉트하는_대안을_함께_준다() -> None:
    """파이프를 친 동기는 출력 줄이기였다(대기열 19). 막기만 하면 다음에도 파이프를 친다."""
    pipe = warnings_for("uv run pytest -q 2>&1 | tail -3")
    chain = warnings_for("uv run ruff check . && echo done; echo $?")

    assert "리다이렉트" in pipe[0]
    assert "리다이렉트" in chain[0]


def test_파이프_마지막이_아닌_게이트를_경고한다() -> None:
    """PR #56 세션: `| tail -3; echo $?` 로 tail 의 종료 코드를 읽었다."""
    warnings = warnings_for("PYTHONUTF8=1 uv run pytest -q 2>&1 | tail -3; echo $?")

    assert len(warnings) == 1
    assert "파이프의 마지막이 아니다" in warnings[0]


def test_서브셸_안의_파이프도_본다() -> None:
    assert len(warnings_for("(uv run pytest -q | tail -3)")) == 1


def test_파이프_경고가_있으면_dollar_question_경고는_겹쳐_내지_않는다() -> None:
    """같은 원인이다. 한 명령에 문장 둘을 넣지 않는다."""
    assert len(warnings_for("uv run pytest -q | tail -3; echo $?")) == 1


def test_체인_뒤의_dollar_question_을_경고한다() -> None:
    """대기열 11: 검사 일곱을 && 로 잇고 `$?` 를 읽었더니 앞 것이 아니라 마지막 것이었다."""
    warnings = warnings_for("uv run ruff check . && echo done; echo $?")

    assert len(warnings) == 1
    assert "$?" in warnings[0]


def test_dollar_question_마다_바로_앞_조각을_본다() -> None:
    """PR #91 리뷰: 첫 `$?` 만 보면 둘째가 echo 의 종료 코드를 읽는 것을 놓친다."""
    warnings = warnings_for("uv run ruff check .; echo $?; uv run pyright; echo done; echo $?")

    assert len(warnings) == 1
    assert "pyright" in warnings[0]


def test_인용된_옵션_값은_자리표시자로_남겨_명령_위치를_지킨다() -> None:
    """PR #91 리뷰: 인용을 지우면 뒤 낱말이 옵션 값 자리로 밀린다."""
    assert len(warnings_for('uv run --project "작업 경로" pytest -q | tail -3')) == 1


def test_게이트_바로_뒤의_dollar_question_은_경고하지_않는다() -> None:
    assert warnings_for("uv run ruff check . && uv run pyright; echo $?") == []
    assert warnings_for('uv run pytest -q; echo "exit=$?"') == []


def test_파이프_없는_게이트와_게이트_아닌_파이프는_경고하지_않는다() -> None:
    assert warnings_for("uv run pytest -q") == []
    assert warnings_for("git log --oneline | head -5") == []
    assert warnings_for("uv run ruff check . && uv run ruff format --check .") == []


def test_인용과_heredoc_안의_게이트_낱말은_보지_않는다() -> None:
    assert warnings_for("echo 'uv run pytest | tail' | cat") == []
    assert warnings_for("cat <<'EOF'\nuv run pytest | tail\nEOF\necho $?") == []
