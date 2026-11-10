"""`rag-engine bootstrap-token`은 살아 있는 `admin` 토큰이 없을 때만 첫 토큰을 낸다(명세 "인증과
권한", 스토리 30)."""

import hashlib

import psycopg
import pytest

from rag_engine.main import main


def _tokens(database_url: str) -> list[tuple[str, str, str]]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        return connection.execute(
            "SELECT name, role, token_hash FROM tokens ORDER BY id"
        ).fetchall()


def test_첫_관리_토큰을_찍고_그_해시만_저장한다(
    seeded_command_environment: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap-token"])

    raw = capsys.readouterr().out.strip()
    assert raw.startswith("rag_")
    assert _tokens(seeded_command_environment) == [
        ("bootstrap", "admin", hashlib.sha256(raw.encode()).hexdigest())
    ]


def test_이름을_줄_수_있다(
    seeded_command_environment: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap-token", "--name", "운영자"])

    capsys.readouterr()
    assert [(name, role) for name, role, _ in _tokens(seeded_command_environment)] == [
        ("운영자", "admin")
    ]


def test_살아_있는_admin_토큰이_있으면_종료_코드_1과_안내를_내고_토큰을_찍지_않는다(
    seeded_command_environment: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap-token"])
    capsys.readouterr()

    with pytest.raises(SystemExit) as caught:
        main(["bootstrap-token"])

    output = capsys.readouterr()
    assert caught.value.code == 1
    assert "rag_" not in output.out + output.err
    assert "살아 있는 admin 토큰" in output.err
    assert len(_tokens(seeded_command_environment)) == 1


def test_회수된_admin_토큰만_남았으면_다시_발급한다(
    seeded_command_environment: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap-token"])
    capsys.readouterr()
    with psycopg.connect(seeded_command_environment, autocommit=True) as connection:
        connection.execute("UPDATE tokens SET revoked_at = now()")

    main(["bootstrap-token", "--name", "다시"])

    assert capsys.readouterr().out.strip().startswith("rag_")
    assert [name for name, _, _ in _tokens(seeded_command_environment)] == ["bootstrap", "다시"]


def test_필수_설정이_없으면_값을_찍지_않고_종료_코드_1이다(
    seeded_command_environment: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("RAG_ALLOWED_HOSTS")
    monkeypatch.setenv("RAG_DATABASE_URL", "postgresql://user:비밀번호@nowhere/db")

    with pytest.raises(SystemExit) as caught:
        main(["bootstrap-token"])

    error = capsys.readouterr().err
    assert caught.value.code == 1
    assert "RAG_ALLOWED_HOSTS" in error
    assert "비밀번호" not in error
