"""`rag-engine ingest <경로> [--group 이름] [--wait] [--timeout 초]`(명세 "관리 명령", 스토리 9).

파일 하나나 폴더를 서버 없이 수집한다. 폴더면 지원 확장자의 파일을 재귀로 걷고 키는 폴더 기준 상대
경로(POSIX 구분자)다. `--wait`는 넣은 문서마다 작업이 없어질 때까지 기다리고, 색인이 실패한 문서가
있으면 종료 코드 1, `--timeout`이 지나면 2다. 작업자는 따로 떠 있어야 하므로 기다림 시험은 같은
데이터베이스를 도는 작업자를 스레드로 띄운다.
"""

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import LiteralString
from uuid import UUID

import psycopg
import pytest
from tests.support.docx_files import docx_bytes
from tests.support.tei_server import serve_stub
from tests.support.tei_stub import TeiStub

from rag_engine.adapters import ingest_command
from rag_engine.adapters.log_format import request_id_var
from rag_engine.adapters.postgres.engine import run_in_selector_loop
from rag_engine.adapters.settings import load_settings
from rag_engine.app.ingest import IngestRequest, IngestResult
from rag_engine.domain.ports import BlobStore, UnitOfWork
from rag_engine.main import main
from rag_engine.worker.assembly import run_once_with_settings

PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"
휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")
DEFAULT_DIMENSIONS = 1024
WORKER_PAUSE_SECONDS = 0.2
WORKER_STOP_SECONDS = 60
WAIT_ROWS_SECONDS = 60


@pytest.fixture
def ingest_database_url(
    seeded_command_environment: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> str:
    """기본 레코드가 든 데이터베이스의 주소. 원본 저장 폴더는 시험의 임시 폴더로 바꾼다."""
    monkeypatch.setenv("RAG_DATA_DIR", str(tmp_path / "data"))
    return seeded_command_environment


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    """`a.docx`, `sub/b.docx`, `sub/deeper/c.pdf`와 수집하지 않는 `ignored.txt`가 든 폴더."""
    root = tmp_path / "docs"
    (root / "sub" / "deeper").mkdir(parents=True)
    (root / "a.docx").write_bytes(휴가)
    (root / "sub" / "b.docx").write_bytes(출장)
    (root / "sub" / "deeper" / "c.pdf").write_bytes(PDF)
    (root / "ignored.txt").write_text("수집하지 않는다", encoding="utf-8")
    return root


def _query(database_url: str, statement: LiteralString) -> list[tuple[object, ...]]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        return connection.execute(statement).fetchall()


def _actions(out: str) -> list[tuple[str, str]]:
    # 로그 핸들러도 표준 출력에 쓰므로(스텁 서버의 로그가 같은 프로세스에서 섞인다) 동작 줄만
    # 읽는다.
    lines = [line.split("\t") for line in out.splitlines() if "\t" in line]
    return [(action, label) for action, label in lines]


def _run(arguments: list[str]) -> int:
    """종료 코드를 낸다. 정상으로 끝나면 0이다."""
    try:
        main(["ingest", *arguments])
    except SystemExit as exit_:
        code = exit_.code
        assert isinstance(code, int)
        return code
    return 0


def _run_in_thread(arguments: list[str]) -> tuple[threading.Thread, list[int]]:
    """명령을 스레드에서 띄운다. 끝나면 종료 코드가 두 번째 값에 하나 쌓인다."""
    codes: list[int] = []
    thread = threading.Thread(target=lambda: codes.append(_run(arguments)), daemon=True)
    thread.start()
    return thread, codes


def _wait_until(
    database_url: str, statement: LiteralString, expected: list[tuple[object, ...]]
) -> None:
    """질의 결과가 기대와 같아질 때까지 기다린다. 기한을 넘기면 실패한다."""
    deadline = time.monotonic() + WAIT_ROWS_SECONDS
    while _query(database_url, statement) != expected:
        assert time.monotonic() < deadline, f"{statement}가 {expected}가 되지 않았다"
        time.sleep(WORKER_PAUSE_SECONDS)


@contextmanager
def _background_worker() -> Generator[None]:
    """같은 데이터베이스를 도는 작업자를 스레드로 띄운다. 꺼낼 작업을 모두 처리하고 잠깐 쉬기를
    블록이 끝날 때까지 되풀이한다."""
    settings = load_settings()
    stop = threading.Event()

    def work() -> None:
        while not stop.is_set():
            run_in_selector_loop(run_once_with_settings(settings))
            stop.wait(WORKER_PAUSE_SECONDS)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(WORKER_STOP_SECONDS)


@contextmanager
def _embedding_stub(database_url: str) -> Generator[None]:
    """기본 판의 임베딩 끝점을 스텁 주소로 고친다."""
    with serve_stub(TeiStub(dimensions=DEFAULT_DIMENSIONS)) as endpoint:
        with psycopg.connect(database_url, autocommit=True) as connection:
            connection.execute("UPDATE index_versions SET embedding_endpoint = %s", [endpoint])
        yield


def test_폴더를_재귀로_걸어_지원_확장자만_넣고_키는_폴더_기준_상대_경로다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(docs)]) == 0

    assert _actions(capsys.readouterr().out) == [
        ("created", "a.docx"),
        ("created", "sub/b.docx"),
        ("created", "sub/deeper/c.pdf"),
    ]
    keys = _query(ingest_database_url, "SELECT key FROM documents ORDER BY key")
    assert keys == [("a.docx",), ("sub/b.docx",), ("sub/deeper/c.pdf",)]


def test_파일_하나를_주면_파일_이름이_키다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(docs / "sub" / "b.docx")]) == 0

    assert _actions(capsys.readouterr().out) == [("created", "b.docx")]
    assert _query(ingest_database_url, "SELECT key FROM documents") == [("b.docx",)]


def test_같은_폴더를_다시_넣으면_unchanged를_한_줄씩_찍는다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run([str(docs)])
    capsys.readouterr()

    assert _run([str(docs)]) == 0

    assert [action for action, _ in _actions(capsys.readouterr().out)] == ["unchanged"] * 3
    assert _query(ingest_database_url, "SELECT count(*) FROM documents") == [(3,)]


def test_group을_주면_그_그룹의_문서로_넣는다(ingest_database_url: str, docs: Path) -> None:
    with psycopg.connect(ingest_database_url, autocommit=True) as connection:
        connection.execute("INSERT INTO groups (id, name) VALUES (gen_random_uuid(), '팀B')")

    assert _run([str(docs), "--group", "팀B"]) == 0

    groups = _query(
        ingest_database_url,
        "SELECT DISTINCT g.name FROM documents d JOIN groups g ON g.id = d.group_id",
    )
    assert groups == [("팀B",)]


def test_없는_그룹_이름이면_아무_파일도_넣지_않고_종료_코드_1이다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(docs), "--group", "없는그룹"]) == 1

    output = capsys.readouterr()
    assert "없는그룹" in output.err
    assert output.out == ""
    assert _query(ingest_database_url, "SELECT count(*) FROM documents") == [(0,)]
    assert _query(ingest_database_url, "SELECT count(*) FROM jobs") == [(0,)]


def test_없는_경로는_종료_코드_1과_안내를_낸다(
    ingest_database_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(tmp_path / "없는 폴더")]) == 1

    assert "없는 폴더" in capsys.readouterr().err
    assert _query(ingest_database_url, "SELECT count(*) FROM documents") == [(0,)]


def test_수집할_파일이_없는_폴더는_안내만_하고_종료_코드_0이다(
    ingest_database_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "빈 폴더"
    empty.mkdir()
    (empty / "메모.txt").write_text("지원하지 않는 확장자", encoding="utf-8")

    assert _run([str(empty), "--wait"]) == 0

    output = capsys.readouterr()
    assert output.out == ""
    assert "수집할 파일이 없다" in output.err


def test_거부된_파일이_있어도_나머지는_넣고_종료_코드_1과_거부_코드를_낸다(
    ingest_database_url: str,
    docs: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_MAX_UPLOAD_MB", "1")
    (docs / "큼.pdf").write_bytes(PDF + b"0" * (1024 * 1024))

    code = _run([str(docs)])

    assert code == 1, f"종료 코드가 {code}이다(거부된 파일이 있으면 1)"
    output = capsys.readouterr()
    assert [label for _, label in _actions(output.out)] == [
        "a.docx",
        "sub/b.docx",
        "sub/deeper/c.pdf",
    ]
    assert "upload_too_large" in output.err
    assert "큼.pdf" in output.err
    assert _query(ingest_database_url, "SELECT count(*) FROM documents") == [(3,)]


def test_지원하지_않는_형식의_파일_하나는_종료_코드_1과_거부_코드를_낸다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(docs / "ignored.txt")]) == 1

    assert "unsupported_media_type" in capsys.readouterr().err
    assert _query(ingest_database_url, "SELECT count(*) FROM documents") == [(0,)]


def test_한_번의_실행이_넣은_작업은_UUIDv7_요청_ID_하나를_쓰고_실행마다_다르다(
    ingest_database_url: str, docs: Path
) -> None:
    _run([str(docs)])
    first = _query(ingest_database_url, "SELECT DISTINCT request_id::text FROM jobs")
    (docs / "d.docx").write_bytes(docx_bytes("제3조 복무", "복무에 관한 규정"))

    _run([str(docs)])

    ids = _query(ingest_database_url, "SELECT DISTINCT request_id::text FROM jobs ORDER BY 1")
    assert len(first) == 1
    assert len(ids) == 2
    assert {UUID(str(row[0])).version for row in ids} == {7}


def test_wait는_작업자가_색인을_마치면_종료_코드_0이다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (docs / "sub" / "deeper" / "c.pdf").unlink()
    with _embedding_stub(ingest_database_url), _background_worker():
        assert _run([str(docs), "--wait"]) == 0

    output = capsys.readouterr()
    assert "작업자" in output.err
    assert _query(ingest_database_url, "SELECT status FROM documents ORDER BY key") == [
        ("parsed",),
        ("parsed",),
    ]


def test_wait는_색인이_실패한_문서가_있으면_종료_코드_1과_실패_문서를_낸다(
    ingest_database_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "깨짐"
    broken.mkdir()
    (broken / "깨진.docx").write_bytes(b"PK\x03\x04 broken")

    with _background_worker():
        assert _run([str(broken), "--wait"]) == 1

    error = capsys.readouterr().err
    assert "깨진.docx" in error
    assert "parse_failed" in error


def test_timeout이_지나면_종료_코드_2다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    started = time.monotonic()

    code = _run([str(docs), "--wait", "--timeout", "1"])

    assert code == 2, f"종료 코드가 {code}이다(시간 초과는 2)"
    assert time.monotonic() - started < 30
    assert "시간" in capsys.readouterr().err
    assert _query(ingest_database_url, "SELECT count(*) FROM documents") == [(3,)]


def test_wait_없이는_작업이_남아도_기다리지_않고_종료_코드_0이다(
    ingest_database_url: str, docs: Path
) -> None:
    assert _run([str(docs), "--timeout", "1"]) == 0


def test_wait는_앞서_넣은_작업이_도는_문서가_unchanged여도_그_작업을_기다린다(
    ingest_database_url: str, docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (docs / "sub" / "deeper" / "c.pdf").unlink()
    _run([str(docs)])
    capsys.readouterr()

    with _embedding_stub(ingest_database_url), _background_worker():
        code = _run([str(docs), "--wait"])
        # 블록을 나가면 작업자가 남은 작업을 마저 처리하므로, 명령이 돌아온 바로 그때의 상태를
        # 읽는다.
        statuses = _query(ingest_database_url, "SELECT status FROM documents ORDER BY key")

    assert code == 0
    assert [action for action, _ in _actions(capsys.readouterr().out)] == ["unchanged"] * 2
    assert statuses == [("parsed",), ("parsed",)]


def test_wait는_기다리는_사이_뒤_수집이_문서를_깨뜨려_색인이_실패하면_종료_코드_1이다(
    ingest_database_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "한_문서"
    folder.mkdir()
    target = folder / "규정.docx"
    target.write_bytes(휴가)
    waiting, codes = _run_in_thread([str(folder), "--wait"])
    _wait_until(ingest_database_url, "SELECT count(*) FROM jobs", [(1,)])

    target.write_bytes(b"PK\x03\x04 broken")
    assert _run([str(folder)]) == 0
    with _background_worker():
        waiting.join(WORKER_STOP_SECONDS)

    assert codes == [1]
    assert "parse_failed" in capsys.readouterr().err


def test_한_실행의_요청_ID는_로그_문맥과_넣은_작업에_같이_쓰인다(
    ingest_database_url: str, docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[UUID | None, UUID]] = []
    real = ingest_command.ingest_document

    async def spy(
        unit_of_work: UnitOfWork,
        blob_store: BlobStore,
        request: IngestRequest,
        *,
        request_id: UUID,
        now: datetime,
        max_upload_bytes: int,
    ) -> IngestResult:
        seen.append((request_id_var.get(), request_id))
        return await real(
            unit_of_work,
            blob_store,
            request,
            request_id=request_id,
            now=now,
            max_upload_bytes=max_upload_bytes,
        )

    monkeypatch.setattr(ingest_command, "ingest_document", spy)

    assert _run([str(docs)]) == 0

    assert len(seen) == 3
    mismatched = [(in_log, passed) for in_log, passed in seen if in_log != passed]
    assert not mismatched, f"로그 문맥의 요청 ID가 다른 호출이 {len(mismatched)}개다"
    assert request_id_var.get() is None
    job_ids = _query(ingest_database_url, "SELECT DISTINCT request_id::text FROM jobs")
    assert job_ids == [(str(seen[0][1]),)]
