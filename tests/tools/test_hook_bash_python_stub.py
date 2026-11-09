"""tools/hook_bash_python_stub.py 의 순수 함수. stdin 을 읽는 main 은 실제 실행으로 확인한다."""

from __future__ import annotations

from tools.hook_bash_python_stub import bare_python_calls, reason_for


def test_python을_부르지_않으면_비어_있다() -> None:
    assert bare_python_calls("git status && ls -la") == []


def test_명령_첫_자리의_python은_잡는다() -> None:
    assert bare_python_calls("python - <<'EOF'\nprint(1)\nEOF") == ["python"]


def test_uv_run_python과_py는_잡지_않는다() -> None:
    assert bare_python_calls("PYTHONUTF8=1 uv run python tools/x.py") == []
    assert bare_python_calls("py -3 -c 'print(1)'") == []


def test_파이프와_연결_뒤의_python도_잡는다() -> None:
    assert bare_python_calls("git log | python -c 'import sys'") == ["python"]
    assert bare_python_calls("cd x && python3 x.py") == ["python3"]
    assert bare_python_calls("echo $(python -V)") == ["python"]


def test_들여쓰기된_줄의_python도_명령어_자리다() -> None:
    """개행은 그 자체로 명령 구분자다. 앞의 공백이 그 사실을 바꾸지 않는다."""
    assert bare_python_calls("echo hi\n  python x.py") == ["python"]
    assert bare_python_calls("  python x.py") == ["python"]


def test_환경변수_접두는_건너뛰고_명령어를_본다() -> None:
    assert bare_python_calls("PYTHONUTF8=1 python x.py") == ["python"]


def test_인자의_python은_명령이_아니다() -> None:
    assert bare_python_calls("echo python") == []
    assert bare_python_calls("grep -rn python src") == []
    assert bare_python_calls("ls .venv/Scripts/python.exe") == []
    assert bare_python_calls("docker run --rm img python --version") == []


def test_따옴표_안이라도_셸이_실행할_분리자_뒤의_python은_막는다() -> None:
    assert bare_python_calls('bash -c "cd tools; python x.py"') == ["python"]


def test_따옴표_안의_데이터나_컨테이너의_python도_지금은_막는다() -> None:
    """거짓 양성이다. 분리자·키워드 뒤와 줄 머리면 따옴표 안이라도 막는다.

    따옴표를 푸는 판정으로 고치면 이 테스트를 뒤집는다(대기열 82, 일지 2026-10-01-06).
    """
    assert bare_python_calls('echo "a; python x"') == ["python"]
    assert bare_python_calls('git commit -m "fix: if python fails"') == ["python"]
    assert bare_python_calls('git commit -m "a\npython x"') == ["python"]
    docker = 'docker run --rm --entrypoint sh img -c "id -u; python --version"'
    assert bare_python_calls(docker) == ["python"]


def test_문자열_머리의_데이터인_python은_막지_않는다() -> None:
    assert bare_python_calls('echo "python x"') == []


def test_sh_c_문자열_머리에서_실행될_python은_지금은_지나간다() -> None:
    """거짓 음성이다. 따옴표를 푸는 판정으로 고치면 이 테스트를 뒤집는다(대기열 82)."""
    assert bare_python_calls('sh -c "python x.py"') == []


def test_셸_키워드_뒤의_python도_명령어_자리다() -> None:
    assert bare_python_calls("for i in 1; do python x.py; done") == ["python"]
    assert bare_python_calls("if python -c 1; then :; fi") == ["python"]
    assert bare_python_calls("exec python x.py") == ["python"]
    assert bare_python_calls("case $1 in a) python x.py;; esac") == ["python"]


def test_heredoc_본문은_명령이_아니다() -> None:
    """heredoc 훅은 통과시키는 명령을 이 훅이 본문 때문에 막으면 두 훅이 충돌한다."""
    assert bare_python_calls("cat <<'EOF'\npython is great\nEOF\necho done") == []
    assert bare_python_calls("cat <<-EOF\n\tpython x\n\tEOF\npython y") == ["python"]


def test_이유는_대체_명령을_말한다() -> None:
    assert reason_for("uv run python x.py") is None
    reason = reason_for("python x.py")
    assert reason is not None
    assert "uv run python" in reason
