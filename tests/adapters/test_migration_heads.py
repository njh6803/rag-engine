"""마이그레이션 리비전의 끝(alembic 의 head)이 하나인지 보는 저장소 상태 시험.

핫픽스 PR 이 main 에 마이그레이션을 더하는 동안 dev 에도 같은 부모를 가리키는 마이그레이션이 있으면,
운영에서 개발로 합치기 PR 에서 head 가 둘이 된다. 그러면
`migrate`(`command.upgrade(config, "head")`)가 "Multiple head revisions are present" 로 실패해
서버가 뜨지 않는다(명세 `.scratch/release-image/spec.md` "번호와 느낌표"). 이 시험이 그 PR 의 CI 를
막는다.

막지 못하는 것: head 가 하나여도 두 리비전이 서로의 결과를 모르고 같은 열을 만드는 것 같은 내용의
충돌은 보지 않는다. 데이터베이스에 닿지 않으므로 실제로 올라가는지도 보지 않는다(그것은
`test_migrations.py` 와 `test_migrate_command.py` 의 몫이다). 이 시험이 빨개졌을 때의 처리는 실패
문장이 적는다.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from rag_engine.adapters.postgres.migrate import MIGRATIONS_DIRECTORY

TWO_HEADS = "head 가 둘이다"


def head_problem(migrations: Path) -> str | None:
    """마이그레이션 폴더의 head 가 하나가 아니면 실패 문장, 하나면 None."""
    config = Config()
    config.set_main_option("script_location", str(migrations))
    heads = sorted(ScriptDirectory.from_config(config).get_heads())
    if len(heads) == 1:
        return None
    if not heads:
        return f"`{migrations}` 에 마이그레이션 리비전이 하나도 없다."
    return (
        f"마이그레이션 리비전의 {TWO_HEADS}({', '.join(heads)}). 같은 부모를 가리키는"
        " 리비전이 둘 이상 있다. 핫픽스가 main 에 더한 마이그레이션과 dev 에 더한"
        " 마이그레이션이 같은 부모를 가리킬 때 운영에서 개발로 합치기 PR 에서 이렇게 된다."
        " head 가 둘이면 `migrate` 가 실패해 서버가 뜨지 않는다."
        " 어느 리비전의 부모를 바꿀지, 합치는 리비전을 더할지는 짐작하지 말고"
        " 멈추고 사용자에게 묻는다. 운영에서 개발로 합치기 PR 은 머리가 main 이라"
        " 그 PR 에 합치는 리비전을 더할 자리가 없다."
    )


def _revision(directory: Path, name: str, revision: str, parent: str | None) -> None:
    (directory / f"{name}.py").write_text(
        f'revision = "{revision}"\ndown_revision = {parent!r}\n', encoding="utf-8", newline="\n"
    )


def _임시_폴더(tmp_path: Path) -> Path:
    versions = tmp_path / "versions"
    versions.mkdir()
    return versions


def test_이_저장소의_마이그레이션_head는_하나다() -> None:
    versions = MIGRATIONS_DIRECTORY / "versions"
    assert any(versions.glob("*.py")), "마이그레이션 폴더가 비었거나 경로가 틀렸다"
    assert head_problem(MIGRATIONS_DIRECTORY) is None


def test_같은_부모를_가리키는_리비전_둘은_head가_둘이라_잡는다(tmp_path: Path) -> None:
    versions = _임시_폴더(tmp_path)
    _revision(versions, "0001_base", "0001", None)
    _revision(versions, "0002_hotfix", "0002a", "0001")
    _revision(versions, "0002_dev", "0002b", "0001")
    problem = head_problem(tmp_path)
    assert problem is not None
    assert TWO_HEADS in problem
    assert "0002a" in problem and "0002b" in problem


def test_head가_둘이면_실패_문장이_짐작하지_말고_멈추라고_적는다(tmp_path: Path) -> None:
    versions = _임시_폴더(tmp_path)
    _revision(versions, "0001_base", "0001", None)
    _revision(versions, "0002_a", "0002a", "0001")
    _revision(versions, "0002_b", "0002b", "0001")
    problem = head_problem(tmp_path)
    assert problem is not None
    assert "같은 부모" in problem  # 까닭
    assert "멈추고 사용자에게 묻는다" in problem
    # 풀이를 시키지 않는다(합치는 리비전을 더하라는 명령이 아니다)
    assert "더하라" not in problem and "고쳐라" not in problem


def test_한_줄로_이어진_리비전은_head가_하나라_지난다(tmp_path: Path) -> None:
    versions = _임시_폴더(tmp_path)
    _revision(versions, "0001_base", "0001", None)
    _revision(versions, "0002_next", "0002", "0001")
    assert head_problem(tmp_path) is None


def test_리비전이_하나도_없으면_잡는다(tmp_path: Path) -> None:
    _임시_폴더(tmp_path)
    problem = head_problem(tmp_path)
    assert problem is not None and "하나도 없다" in problem
