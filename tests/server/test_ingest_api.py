"""수집 API의 첫 길(명세 "수집 API", "수집 파이프라인과 작업", 스토리 1~4, 11, 40).

`POST /api/v1/ingest/documents`가 원본을 저장하고 문서 행과 작업을 만들어 202와 작업 ID를 낸다. 같은
키에 같은 내용이면 건너뛰고(200) 내용이 바뀌면 갱신하며, 아직 꺼내지지 않은 작업이 있으면 그 작업을
다시 쓴다. 작업자는 아직 돌지 않으므로 이 시험이 보는 상태는 모두 수집 직후의 것이다.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import LiteralString
from uuid import UUID

import httpx
import psycopg
from tests.harness import LogCapture, RunningServer

from rag_engine.adapters.settings import Settings
from rag_engine.domain.media_types import PDF_MIME

PATH = "/api/v1/ingest/documents"
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"
OTHER_PDF = PDF + "%% 바뀐 내용 %%\n".encode()


def _auth(server: RunningServer) -> dict[str, str]:
    return {"Authorization": f"Bearer {server.admin_token}"}


def _post(
    server: RunningServer,
    content: bytes = PDF,
    *,
    filename: str = "규정.pdf",
    data: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.post(
        server.base_url + PATH,
        headers=_auth(server),
        files={"file": (filename, content)},
        data=data or {},
    )


def _query(
    settings: Settings, statement: LiteralString, *params: object
) -> list[tuple[object, ...]]:
    with psycopg.connect(settings.database_url, autocommit=True) as connection:
        return connection.execute(statement, list(params)).fetchall()


def _blobs(settings: Settings) -> list[Path]:
    return sorted(path for path in (settings.data_dir / "blobs").rglob("*") if path.is_file())


def test_새_파일을_넣으면_202와_문서_작업_식별자를_낸다(server: RunningServer) -> None:
    response = _post(server)

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"action", "document_id", "job_id"}
    assert body["action"] == "created"
    UUID(body["document_id"])
    UUID(body["job_id"])


def test_새_문서는_받음_상태로_키와_제목과_기본_그룹과_세대_1을_갖는다(
    server: RunningServer,
) -> None:
    before = datetime.now(UTC)
    body = _post(server, filename="인사 규정.v2.pdf").json()

    ((key, title, mime, size, status, generation, group, source, updated_at),) = _query(
        server.settings,
        "SELECT d.key, d.title, d.mime, d.size_bytes, d.status, d.generation, g.name, s.name,"
        " d.updated_at FROM documents d JOIN groups g ON g.id = d.group_id"
        " JOIN sources s ON s.id = d.source_id WHERE d.id = %s",
        UUID(body["document_id"]),
    )
    assert (key, title, mime, size) == ("인사 규정.v2.pdf", "인사 규정.v2", PDF_MIME, len(PDF))
    assert (status, generation, group, source) == ("received", 1, "default", "default")
    assert isinstance(updated_at, datetime)
    assert before <= updated_at <= datetime.now(UTC)


def test_원본은_문서_UUID_아래_원본_UUID_경로에_그대로_저장된다(server: RunningServer) -> None:
    body = _post(server).json()

    (blob,) = _blobs(server.settings)
    assert blob.parent.name == body["document_id"]
    UUID(blob.name)
    assert blob.read_bytes() == PDF
    ((blob_path,),) = _query(
        server.settings, "SELECT blob_path FROM documents WHERE id = %s", UUID(body["document_id"])
    )
    assert blob_path == f"blobs/{body['document_id']}/{blob.name}"


def test_폼_칸의_키와_그룹과_메타데이터와_갱신일이_문서에_실린다(server: RunningServer) -> None:
    body = _post(
        server,
        filename="upload.pdf",
        data={
            "key": "규정/인사.pdf",
            "group": "default",
            "metadata": json.dumps({"title": "인사 규정", "부서": "기획팀"}, ensure_ascii=False),
            "updated_at": "2026-01-02T03:04:05+09:00",
        },
    ).json()

    ((key, title, metadata, updated_at),) = _query(
        server.settings,
        "SELECT key, title, metadata, updated_at FROM documents WHERE id = %s",
        UUID(body["document_id"]),
    )
    assert key == "규정/인사.pdf"
    assert title == "인사 규정"
    assert metadata == {"title": "인사 규정", "부서": "기획팀"}
    assert updated_at == datetime(2026, 1, 1, 18, 4, 5, tzinfo=UTC)


def test_메타데이터의_제목이_문자열이_아니면_파일_이름에서_제목을_만든다(
    server: RunningServer,
) -> None:
    body = _post(server, filename="규정.pdf", data={"metadata": '{"title": 7}'}).json()

    ((title,),) = _query(
        server.settings, "SELECT title FROM documents WHERE id = %s", UUID(body["document_id"])
    )
    assert title == "규정"


def test_확장자가_없어도_바이트_머리가_PDF면_받는다(server: RunningServer) -> None:
    body = _post(server, filename="규정").json()

    ((mime,),) = _query(
        server.settings, "SELECT mime FROM documents WHERE id = %s", UUID(body["document_id"])
    )
    assert mime == PDF_MIME


def test_작업은_수집_요청의_요청_ID를_들고_문서를_가리킨다(server: RunningServer) -> None:
    response = _post(server)
    body = response.json()

    ((document_id, request_id, status, attempts),) = _query(
        server.settings,
        "SELECT document_id, request_id, status, attempts FROM jobs WHERE id = %s",
        UUID(body["job_id"]),
    )
    assert str(document_id) == body["document_id"]
    assert str(request_id) == response.headers["x-request-id"]
    assert (status, attempts) == ("queued", 0)


def test_같은_키로_같은_내용을_다시_넣으면_200으로_건너뛰고_새_원본도_작업도_남기지_않는다(
    server: RunningServer,
) -> None:
    first = _post(server).json()

    response = _post(server)

    assert response.status_code == 200
    assert response.json() == {
        "action": "unchanged",
        "document_id": first["document_id"],
        "job_id": None,
    }
    assert len(_blobs(server.settings)) == 1
    ((jobs,),) = _query(server.settings, "SELECT count(*) FROM jobs")
    assert jobs == 1


def test_같은_내용이어도_메타데이터와_갱신일이_달라지면_건너뛰되_문서_행을_고친다(
    server: RunningServer,
) -> None:
    first = _post(server, data={"metadata": '{"부서": "기획팀"}'}).json()

    response = _post(
        server,
        data={"metadata": '{"부서": "총무팀"}', "updated_at": "2026-05-06T00:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "unchanged"
    ((metadata, updated_at, generation, status),) = _query(
        server.settings,
        "SELECT metadata, updated_at, generation, status FROM documents WHERE id = %s",
        UUID(first["document_id"]),
    )
    assert metadata == {"부서": "총무팀"}
    assert updated_at == datetime(2026, 5, 6, tzinfo=UTC)
    assert (generation, status) == (1, "received")
    assert len(_blobs(server.settings)) == 1


def test_갱신일을_주지_않은_건너뜀은_문서의_갱신일을_바꾸지_않는다(server: RunningServer) -> None:
    first = _post(server, data={"updated_at": "2026-05-06T00:00:00Z"}).json()

    _post(server, data={"metadata": '{"부서": "총무팀"}'})

    ((updated_at,),) = _query(
        server.settings,
        "SELECT updated_at FROM documents WHERE id = %s",
        UUID(first["document_id"]),
    )
    assert updated_at == datetime(2026, 5, 6, tzinfo=UTC)


def test_같은_키로_내용을_바꿔_넣으면_갱신이고_첫째_작업을_다시_쓴다(server: RunningServer) -> None:
    first = _post(server).json()
    (first_blob,) = _blobs(server.settings)

    response = _post(server, OTHER_PDF)

    assert response.status_code == 202
    second = response.json()
    assert second["action"] == "updated"
    assert second["document_id"] == first["document_id"]
    assert second["job_id"] == first["job_id"]
    ((jobs,),) = _query(server.settings, "SELECT count(*) FROM jobs")
    assert jobs == 1
    ((generation, status, size, request_id),) = _query(
        server.settings,
        "SELECT d.generation, d.status, d.size_bytes, j.request_id FROM documents d"
        " JOIN jobs j ON j.document_id = d.id WHERE d.id = %s",
        UUID(first["document_id"]),
    )
    assert (generation, status, size) == (2, "received", len(OTHER_PDF))
    assert str(request_id) == response.headers["x-request-id"]
    (second_blob,) = _blobs(server.settings)
    assert second_blob != first_blob
    assert second_blob.read_bytes() == OTHER_PDF


def test_갱신한_문서의_갱신일은_준_값_없으면_수집_시각이고_제목은_다시_정해진다(
    server: RunningServer,
) -> None:
    first = _post(server, data={"updated_at": "2020-01-01T00:00:00Z"}).json()
    before = datetime.now(UTC)

    _post(server, OTHER_PDF, filename="규정.pdf", data={"metadata": '{"title": "새 제목"}'})

    ((updated_at, title),) = _query(
        server.settings,
        "SELECT updated_at, title FROM documents WHERE id = %s",
        UUID(first["document_id"]),
    )
    assert isinstance(updated_at, datetime)
    assert before <= updated_at <= datetime.now(UTC)
    assert title == "새 제목"


def test_지원하지_않는_형식은_415이고_작업도_원본도_만들지_않는다(server: RunningServer) -> None:
    response = _post(server, "그냥 글".encode(), filename="메모.txt")

    assert response.status_code == 415
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "unsupported_media_type"
    assert _blobs(server.settings) == []
    assert _query(server.settings, "SELECT count(*) FROM jobs") == [(0,)]
    assert _query(server.settings, "SELECT count(*) FROM documents") == [(0,)]


def test_없는_그룹_이름은_404이고_작업도_원본도_만들지_않는다(server: RunningServer) -> None:
    response = _post(server, data={"group": "없는 그룹"})

    assert response.status_code == 404
    assert response.json()["code"] == "group_not_found"
    assert _blobs(server.settings) == []
    assert _query(server.settings, "SELECT count(*) FROM jobs") == [(0,)]
    assert _query(server.settings, "SELECT count(*) FROM documents") == [(0,)]


def test_업로드_상한을_넘으면_413이고_작업도_원본도_만들지_않는다(
    run_server: Callable[..., RunningServer],
) -> None:
    server = run_server(max_upload_mb=1)

    at_limit = _post(server, b"%PDF-" + b"0" * (1024 * 1024 - 5))
    over_limit = _post(server, b"%PDF-" + b"0" * (1024 * 1024 - 4), filename="큰 파일.pdf")

    assert at_limit.status_code == 202
    assert over_limit.status_code == 413
    assert over_limit.json()["code"] == "upload_too_large"
    assert len(_blobs(server.settings)) == 1
    assert _query(server.settings, "SELECT count(*) FROM jobs") == [(1,)]
    assert _query(server.settings, "SELECT key FROM documents") == [("규정.pdf",)]


def test_입력이_잘못되면_422이고_작업도_원본도_만들지_않는다(server: RunningServer) -> None:
    bad_metadata = _post(server, data={"metadata": "[1, 2]"})
    bad_updated_at = _post(server, data={"updated_at": "내일"})
    no_file = httpx.post(server.base_url + PATH, headers=_auth(server), data={"key": "a.pdf"})

    for response in (bad_metadata, bad_updated_at, no_file):
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
    assert _blobs(server.settings) == []
    assert _query(server.settings, "SELECT count(*) FROM jobs") == [(0,)]


def test_파일_이름이_빈_업로드는_422이고_원본을_남기지_않는다(server: RunningServer) -> None:
    response = _post(server, filename="")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert _blobs(server.settings) == []


def test_토큰이_없으면_401이고_reader_토큰이면_403이다(server: RunningServer) -> None:
    anonymous = httpx.post(server.base_url + PATH, files={"file": ("a.pdf", PDF)})
    reader = httpx.post(
        server.base_url + "/api/v1/admin/tokens",
        headers=_auth(server),
        json={"name": "읽기", "role": "reader"},
    ).json()["token"]
    forbidden = httpx.post(
        server.base_url + PATH,
        headers={"Authorization": f"Bearer {reader}"},
        files={"file": ("a.pdf", PDF)},
    )

    assert anonymous.status_code == 401
    assert forbidden.status_code == 403
    assert _blobs(server.settings) == []


def test_원본을_쓰지_못해_라우트가_실패하면_500_Problem을_내고_작업을_만들지_않는다(
    server: RunningServer, log_capture: LogCapture
) -> None:
    blocker = server.settings.data_dir / "blobs"
    blocker.write_text("폴더가 있어야 할 자리의 파일", encoding="utf-8")

    response = _post(server)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "internal_error"
    assert body["request_id"] == response.headers["x-request-id"]
    assert "detail" not in body
    (failure,) = log_capture.events("request_failed", count=1)
    assert failure["request_id"] == response.headers["x-request-id"]
    assert _query(server.settings, "SELECT count(*) FROM jobs") == [(0,)]
    assert _query(server.settings, "SELECT count(*) FROM documents") == [(0,)]
    assert str(blocker) not in log_capture.text()


def test_로그에는_문서의_키와_제목과_파일_이름이_남지_않는다(
    server: RunningServer, log_capture: LogCapture
) -> None:
    response = _post(
        server,
        filename="비밀 규정 제목.pdf",
        data={"key": "비밀/키.pdf", "metadata": '{"title": "비밀 제목"}'},
    )

    assert response.status_code == 202
    log_capture.events("http_request", count=1)
    text = log_capture.text()
    for secret in ("비밀 규정 제목", "비밀/키", "비밀 제목", server.admin_token):
        assert secret not in text
