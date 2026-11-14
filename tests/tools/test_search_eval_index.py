"""평가 도구 `tools/search_eval.py`의 `index`와 `validate --indexed`(티켓 search-eval 03).

뒤에는 실제 테스트 PostgreSQL과 TEI 스텁을 붙이고 도구의 `main(argv)`를 부른다. "아무것도 쓰지
않는다"와 "스키마도 올리지 않는다"는 바깥에서 본다. 표의 행 전체와 스키마의 판 표와 데이터 폴더가
그대로인지 견준다(명세 Testing Decisions). 데이터베이스는 `rag_eval_<난수>`로 짓는다.
"""

import os
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.exc import OperationalError
from tests.support.docx_files import docx_bytes
from tests.support.eval_bundle import (
    INDEX_CONFIG,
    PASSAGE,
    PASSAGE_B,
    passage_evidence,
    write_indexable_bundle,
)
from tests.support.pdf_files import PdfPage, pdf_bytes, text_block
from tests.support.tei_server import serve_stub
from tests.support.tei_stub import TeiStub

from rag_engine.adapters import eval_index
from rag_engine.adapters.ingest_command import ingest_path
from rag_engine.adapters.postgres.migrate import upgrade_to_head
from rag_engine.adapters.settings import Settings
from rag_engine.domain.entities import JsonValue
from tools import search_eval

DOCUMENT_A = docx_bytes("휴가", PASSAGE + ".")
DOCUMENT_B = docx_bytes("출장", PASSAGE_B + ".")
DOCUMENTS = {"a.docx": DOCUMENT_A, "sub/b.docx": DOCUMENT_B}
EVIDENCE = [
    passage_evidence("q1", "a.docx", PASSAGE),
    passage_evidence("q2", "sub/b.docx", PASSAGE_B),
]
DATABASE_ENV = "RAG_EVAL_DATABASE_URL"
DATA_DIR_ENV = "RAG_EVAL_DATA_DIR"
EMBEDDING_ENV = "RAG_EVAL_EMBEDDING_URL"
SECRET = "비밀번호-자리표시자"


@dataclass(frozen=True, slots=True)
class World:
    """평가 도구가 보는 환경. 평가 전용 이름 셋의 값과 시험이 도구를 부르는 작업 폴더다."""

    database_url: str
    data_dir: Path
    tei_url: str
    work_dir: Path


@pytest.fixture
def tei_url() -> Iterator[str]:
    with serve_stub(TeiStub()) as url:
        yield url


@pytest.fixture
def world(
    empty_eval_database_url: str, tei_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> World:
    """개발자 셸의 `RAG_*`를 지우고(시험이 쓰는 `RAG_TEST_DATABASE_URL`은 남긴다) 평가 전용 이름
    셋을 준다. 작업 폴더는 빈 폴더다."""
    for name in [name for name in os.environ if name.startswith("RAG_")]:
        if name != "RAG_TEST_DATABASE_URL":
            monkeypatch.delenv(name)
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    data_dir = tmp_path / "eval-data"
    monkeypatch.chdir(work_dir)
    monkeypatch.setenv(DATABASE_ENV, empty_eval_database_url)
    monkeypatch.setenv(DATA_DIR_ENV, str(data_dir))
    monkeypatch.setenv(EMBEDDING_ENV, tei_url)
    return World(empty_eval_database_url, data_dir, tei_url, work_dir)


def _bundle(
    tmp_path: Path,
    name: str = "bundle",
    documents: dict[str, bytes] | None = None,
    evidence: list[JsonValue] | None = None,
    config: dict[str, JsonValue] | None = None,
) -> Path:
    return write_indexable_bundle(
        tmp_path / name,
        DOCUMENTS if documents is None else documents,
        EVIDENCE if evidence is None else evidence,
        config=INDEX_CONFIG if config is None else config,
    )


def _index(bundle: Path) -> int:
    return search_eval.main(["index", str(bundle)])


def _validate_indexed(bundle: Path) -> int:
    return search_eval.main(["validate", str(bundle), "--indexed"])


type Snapshot = dict[str, list[tuple[object, ...]]]


def _snapshot(database_url: str) -> Snapshot:
    """데이터베이스의 모든 표와 그 행 전체. 스키마의 판 표(`alembic_version`)도 든다."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = current_schema() ORDER BY 1"
            ).fetchall()
        ]
        return {
            name: [
                tuple(row)
                for row in connection.execute(
                    sql.SQL("SELECT * FROM {} ORDER BY 1").format(sql.Identifier(name))
                ).fetchall()
            ]
            for name in names
        }


def _files(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def _indexed_keys(database_url: str) -> list[str]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT d.key FROM documents d JOIN document_index_states s ON s.document_id = d.id"
            " WHERE s.status = 'indexed' ORDER BY d.key"
        ).fetchall()
    return [row[0] for row in rows]


def _write_env_file(work_dir: Path, text: str) -> None:
    (work_dir / ".env").write_text(text, encoding="utf-8")


def test_index는_묶음의_문서를_색인하고_validate_indexed가_초록이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)

    assert _index(bundle) == 0
    assert _indexed_keys(world.database_url) == ["a.docx", "sub/b.docx"]
    assert _validate_indexed(bundle) == 0

    assert "문제 없음" in capsys.readouterr().out


def test_같은_묶음에_index를_다시_치면_이어서_끝나고_문서를_바꾸지_않는다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    capsys.readouterr()
    before = _snapshot(world.database_url)["documents"]

    assert _index(bundle) == 0

    assert "unchanged" in capsys.readouterr().out
    assert _snapshot(world.database_url)["documents"] == before


@pytest.mark.parametrize("missing", [DATABASE_ENV, DATA_DIR_ENV, EMBEDDING_ENV])
@pytest.mark.parametrize("command", ["index", "validate --indexed"])
def test_평가_전용_이름이_없으면_제품의_환경이_있어도_돌지_않고_빠진_이름을_알린다(
    world: World,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing: str,
    command: str,
) -> None:
    bundle = _bundle(tmp_path)
    monkeypatch.delenv(missing)
    # 제품의 이름과 작업 폴더의 `.env`가 같은 자리를 채워도 도구는 읽지 않는다.
    monkeypatch.setenv("RAG_DATABASE_URL", world.database_url)
    monkeypatch.setenv("RAG_DATA_DIR", str(world.data_dir))
    monkeypatch.setenv("RAG_DEFAULT_EMBEDDING_URL", world.tei_url)
    _write_env_file(world.work_dir, f"{missing}=postgresql://u:p@127.0.0.1:1/rag_eval_x\n")

    code = search_eval.main([*command.split(), str(bundle)])

    err = capsys.readouterr().err
    assert code == 1
    assert missing in err
    assert world.database_url not in err
    assert _snapshot(world.database_url) == {}
    assert _files(world.data_dir) == []


def test_리랭커_끝점이_없어도_돈다(
    world: World, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RAG_EVAL_RERANKER_URL", raising=False)

    assert _index(_bundle(tmp_path)) == 0


def test_작업_폴더의_env가_있어도_색인_결과가_같다(world: World, tmp_path: Path) -> None:
    """제품의 설정 객체가 `.env`를 읽으면 `RAG_PARSE_MAX_PAGES=1`이 두 쪽짜리 PDF의 파싱을
    거부한다."""
    two_pages = pdf_bytes(
        [PdfPage(text_block("첫째 쪽의 글이다")), PdfPage(text_block("둘째 쪽의 글이다"))]
    )
    bundle = _bundle(tmp_path, documents={**DOCUMENTS, "two.pdf": two_pages})
    _write_env_file(world.work_dir, "RAG_PARSE_MAX_PAGES=1\nRAG_DEFAULT_CHUNK_TOKENS=64\n")

    assert _index(bundle) == 0
    assert _indexed_keys(world.database_url) == ["a.docx", "sub/b.docx", "two.pdf"]


@pytest.mark.parametrize("command", ["index", "validate --indexed"])
@pytest.mark.parametrize(
    "url",
    [
        f"postgresql://user:{SECRET}@127.0.0.1:1/product",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_test_not_eval",
        f"postgresql://user:{SECRET}@127.0.0.1:1/",
        f"postgresql://user:{SECRET}@127.0.0.1:1",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x?dbname=product",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x?dbname=",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x?DBNAME=product",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x?database=product",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x?host=other.example",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x?service=product",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x#?dbname=product",
        f"postgresql://user:{SECRET}@127.0.0.1:1/rag_eval_x#?host=other.example",
    ],
)
def test_이름이_rag_eval로_시작하지_않는_주소는_연결_오류가_아니라_이름의_규칙이_나온다(
    world: World,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    url: str,
) -> None:
    del world
    bundle = _bundle(tmp_path)
    monkeypatch.setenv(DATABASE_ENV, url)

    code = search_eval.main([*command.split(), str(bundle)])

    err = capsys.readouterr().err
    assert code == 1
    assert "rag_eval" in err
    assert SECRET not in err
    assert "127.0.0.1" not in err


def test_묶음_밖의_문서가_든_데이터베이스에는_아무것도_쓰지_않고_1이다(
    world: World,
    tmp_path: Path,
    make_settings: Callable[..., Settings],
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _bundle(tmp_path)
    assert _index(bundle) == 0
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "other.docx").write_bytes(docx_bytes("다른", "묶음에 없는 문서의 글이다."))
    settings = make_settings(world.database_url)
    assert ingest_path(settings, foreign, group=None, wait_timeout_seconds=None) == 0
    capsys.readouterr()
    before = (_snapshot(world.database_url), _files(world.data_dir))

    assert _index(bundle) == 1

    assert "묶음에 없는 문서" in capsys.readouterr().err
    assert (_snapshot(world.database_url), _files(world.data_dir)) == before


def test_키는_같고_내용_해시가_다른_문서가_든_데이터베이스에는_아무것도_쓰지_않고_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _index(_bundle(tmp_path)) == 0
    changed = docx_bytes("휴가", "같은 이름의 문서지만 내용이 다르다.")
    other = _bundle(tmp_path, "other", documents={"a.docx": changed, "sub/b.docx": DOCUMENT_B})
    capsys.readouterr()
    before = (_snapshot(world.database_url), _files(world.data_dir))

    assert _index(other) == 1

    err = capsys.readouterr().err
    assert "a.docx" in err
    assert "내용 해시" in err
    assert (_snapshot(world.database_url), _files(world.data_dir)) == before


def test_스키마의_판이_이_체크아웃과_다르면_올리지_않고_거부한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    upgrade_to_head(world.database_url)
    with psycopg.connect(world.database_url, autocommit=True) as connection:
        connection.execute("UPDATE alembic_version SET version_num = '0001'")
    before = (_snapshot(world.database_url), _files(world.data_dir))

    assert _index(_bundle(tmp_path)) == 1

    assert "스키마" in capsys.readouterr().err
    assert (_snapshot(world.database_url), _files(world.data_dir)) == before


def test_스키마의_판_표가_없는데_다른_표가_든_데이터베이스는_거부한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with psycopg.connect(world.database_url, autocommit=True) as connection:
        connection.execute("CREATE TABLE somebody_elses_table (id integer)")
    before = _snapshot(world.database_url)

    assert _index(_bundle(tmp_path)) == 1

    assert "스키마" in capsys.readouterr().err
    assert _snapshot(world.database_url) == before


@pytest.mark.parametrize(
    "change",
    [
        {"chunking": {"strategy": "structure_first", "max_tokens": 256, "overlap_tokens": 64}},
        {"embedding_model": "다른/모델"},
        {"embedding_dimensions": 8},
    ],
    ids=["청킹", "임베딩 모델", "차원"],
)
def test_현재_판의_요소가_구성과_다르면_아무것도_쓰지_않고_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str], change: dict[str, JsonValue]
) -> None:
    assert _index(_bundle(tmp_path)) == 0
    other = _bundle(tmp_path, "other", config={**INDEX_CONFIG, **change})
    capsys.readouterr()
    before = (_snapshot(world.database_url), _files(world.data_dir))

    assert _index(other) == 1

    assert "config.json" in capsys.readouterr().err
    assert (_snapshot(world.database_url), _files(world.data_dir)) == before


@pytest.mark.parametrize(
    "change",
    [
        {"embedding_dimensions": 2001},
        {"chunking": {"strategy": "없는_전략", "max_tokens": 512, "overlap_tokens": 64}},
    ],
    ids=["차원 상한 초과", "모르는 청킹 전략"],
)
def test_기본_지식베이스를_만들_수_없는_구성은_스키마를_올리기_전에_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str], change: dict[str, JsonValue]
) -> None:
    bundle = _bundle(tmp_path, config={**INDEX_CONFIG, **change})

    assert _index(bundle) == 1

    assert "config.json" in capsys.readouterr().err
    assert _snapshot(world.database_url) == {}
    assert _files(world.data_dir) == []


def test_목록과_해시가_다른_문서_파일이_있으면_스키마를_올리지_않고_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "documents" / "a.docx").write_bytes(
        docx_bytes("휴가", "목록을 만든 뒤에 바뀐 문서다.")
    )

    assert _index(bundle) == 1

    assert "해시" in capsys.readouterr().err
    assert _snapshot(world.database_url) == {}
    assert _files(world.data_dir) == []


def test_목록에_없는_파일이_documents에_있으면_스키마를_올리지_않고_1이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "documents" / "extra.docx").write_bytes(docx_bytes("끼어든", "목록에 없는 문서다."))

    assert _index(bundle) == 1

    assert "목록에 없는 파일" in capsys.readouterr().err
    assert _snapshot(world.database_url) == {}
    assert _files(world.data_dir) == []


def test_색인에_실패한_문서가_하나라도_있으면_1이고_나머지는_색인한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = DOCUMENT_A[:200]
    bundle = _bundle(tmp_path, documents={**DOCUMENTS, "broken.docx": broken})

    assert _index(bundle) == 1

    assert "broken.docx" in capsys.readouterr().err
    assert _indexed_keys(world.database_url) == ["a.docx", "sub/b.docx"]


def test_스키마를_올리다_데이터베이스_오류가_나면_종류만_알리고_1이다(
    world: World,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del world

    def refuse(settings: Settings) -> None:
        del settings
        raise OperationalError("SELECT 1", None, Exception(f"{SECRET}@db.internal"))

    monkeypatch.setattr(eval_index, "migrate_database", refuse)

    assert _index(_bundle(tmp_path)) == 1

    err = capsys.readouterr().err
    assert "OperationalError" in err
    assert SECRET not in err
    assert "db.internal" not in err


def test_validate_indexed는_색인되지_않은_문서가_있으면_거부한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del world
    assert _index(_bundle(tmp_path)) == 0
    larger = _bundle(
        tmp_path,
        "larger",
        documents={**DOCUMENTS, "c.docx": docx_bytes("셋째", "셋째 문서의 글이다.")},
    )
    capsys.readouterr()

    assert _validate_indexed(larger) == 1

    err = capsys.readouterr().err
    assert "c.docx" in err
    assert "색인되어 있지 않다" in err


def test_validate_indexed는_색인에_실패한_문서를_색인되지_않은_것으로_거부한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del world
    bundle = _bundle(tmp_path, documents={**DOCUMENTS, "broken.docx": DOCUMENT_A[:200]})
    assert _index(bundle) == 1
    capsys.readouterr()

    assert _validate_indexed(bundle) == 1

    err = capsys.readouterr().err
    assert "broken.docx: 색인되어 있지 않다" in err
    assert "a.docx: 색인되어 있지 않다" not in err


def test_validate_indexed는_스키마가_없는_데이터베이스에서_거부한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _validate_indexed(_bundle(tmp_path)) == 1

    assert "색인되어 있지 않다" in capsys.readouterr().err
    assert _snapshot(world.database_url) == {}


def test_validate_indexed는_본문에_없는_글귀를_세트의_오류로_거부한다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del world
    assert _index(_bundle(tmp_path)) == 0
    wrong = _bundle(
        tmp_path,
        "wrong",
        evidence=[passage_evidence("q1", "a.docx", "문서에는 전혀 없는 글귀이다 확인용")],
    )
    capsys.readouterr()

    assert search_eval.main(["validate", str(wrong)]) == 0
    assert _validate_indexed(wrong) == 1

    err = capsys.readouterr().err
    assert "q1" in err
    assert "본문에 없다" in err


def test_validate_indexed는_절을_가르는_제목의_글귀를_본문으로_세지_않는다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del world
    title = "유일한제목입니다"
    bundle = _bundle(
        tmp_path,
        documents={"a.docx": docx_bytes(title, "본문의 문단이다.")},
        evidence=[passage_evidence("q1", "a.docx", title)],
    )
    assert _index(bundle) == 0
    capsys.readouterr()

    assert _validate_indexed(bundle) == 1

    assert "본문에 없다" in capsys.readouterr().err


def test_validate_indexed는_조각_상한의_4분의_1을_넘는_제목을_문단으로_다뤄_본문에_둔다(
    world: World, tmp_path: Path
) -> None:
    del world
    long_title = " ".join(f"항목{number}" for number in range(200))
    passage = " ".join(f"항목{number}" for number in range(10, 25))
    documents = {"long.docx": docx_bytes(long_title, "그 밑의 문단이다.")}
    bundle = _bundle(
        tmp_path, documents=documents, evidence=[passage_evidence("q1", "long.docx", passage)]
    )
    assert _index(bundle) == 0

    assert _validate_indexed(bundle) == 0


def test_validate_indexed는_공백과_NFC가_달라도_글귀를_찾는다(world: World, tmp_path: Path) -> None:
    del world
    decomposed = unicodedata.normalize("NFD", PASSAGE).replace(" ", "\t")
    bundle = _bundle(tmp_path, evidence=[passage_evidence("q1", "a.docx", decomposed)])
    assert _index(bundle) == 0

    assert _validate_indexed(bundle) == 0


def test_validate_indexed는_한_문서_안에서_두_번_나오는_글귀를_경고하고_종료_코드는_0이다(
    world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del world
    twice = docx_bytes("휴가", PASSAGE + ".", "다른 말이다.", PASSAGE + ".")
    bundle = _bundle(
        tmp_path,
        documents={"a.docx": twice},
        evidence=[passage_evidence("q1", "a.docx", PASSAGE)],
    )
    assert _index(bundle) == 0
    capsys.readouterr()

    assert _validate_indexed(bundle) == 0

    captured = capsys.readouterr()
    assert "경고" in captured.err
    assert "q1" in captured.err
    assert "문제 없음" in captured.out
