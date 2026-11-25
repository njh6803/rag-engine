"""가져오는 원천(`pull`)을 만들고 고치는 관리 API(source-sync 티켓 06, 명세 "관리 API", "서버 경로
커넥터와 원천 폴더", 스토리 6, 8, 9, 24).

실제 uvicorn 서버와 실제 파일 시스템(시험마다 만드는 임시 부모 폴더, `RAG_SOURCES_DIR`)을 쓴다.
"""

import os
import unicodedata
from pathlib import Path

import httpx
import pytest
from tests.harness import RunningServer
from tests.support.pull_source_http import SOURCES, errors, request
from tests.support.server_path_faults import hide_entry_info, refuse_listing

JOBS = "/api/v1/admin/jobs"
FOLDER = "규정집"
PULL_FIELDS = {
    "name",
    "kind",
    "connector",
    "config",
    "group",
    "schedule",
    "next_run_at",
    "paused",
    "exclude_patterns",
    "created_at",
    "deleted_at",
    "documents",
    "last_sync",
}


@pytest.fixture
def parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """부모 폴더. `RAG_SOURCES_DIR`을 이 폴더로 바꾼다."""
    path = tmp_path / "sources"
    path.mkdir()
    monkeypatch.setenv("RAG_SOURCES_DIR", str(path))
    return path


def _create(server: RunningServer, name: str = "wiki", **body: object) -> httpx.Response:
    fields: dict[str, object] = {
        "kind": "pull",
        "connector": "server_path",
        "config": {"folder": FOLDER},
        **body,
    }
    return request(server, "POST", SOURCES, name=name, **fields)


# ---------- 만들기 ----------


def test_가져오는_원천을_만들면_201과_가져오는_원천의_칸이_채워진_원천을_낸다(
    server: RunningServer, parent: Path
) -> None:
    (parent / FOLDER).mkdir()

    response = _create(server)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == PULL_FIELDS
    assert (body["name"], body["kind"]) == ("wiki", "pull")
    assert (body["connector"], body["config"]) == ("server_path", {"folder": FOLDER})
    assert (body["group"], body["schedule"], body["next_run_at"]) == ("default", None, None)
    assert (body["paused"], body["exclude_patterns"]) == (False, [])
    assert body["documents"] == {"total": 0, "failed": 0, "skipped": 0}
    assert (body["deleted_at"], body["last_sync"]) == (None, None)


def test_목록과_하나_보기가_만든_원천의_칸을_그대로_낸다(
    server: RunningServer, parent: Path
) -> None:
    (parent / FOLDER).mkdir()
    created = _create(server, exclude_patterns=["임시", "*_초안.docx"]).json()

    one = request(server, "GET", f"{SOURCES}/wiki").json()
    listed = request(server, "GET", SOURCES).json()["sources"]

    assert one == created
    assert [found for found in listed if found["name"] == "wiki"] == [created]
    assert created["exclude_patterns"] == ["임시", "*_초안.docx"]


def test_만든_직후에는_동기화를_스스로_시작하지_않는다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER).mkdir()

    assert _create(server).status_code == 201

    assert request(server, "GET", JOBS).json()["jobs"] == []


def test_끝의_슬래시는_떼고_여러_단계의_폴더를_받는다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER / "인사").mkdir(parents=True)

    response = _create(server, config={"folder": f"{FOLDER}/인사/"})

    assert response.status_code == 201
    assert response.json()["config"] == {"folder": f"{FOLDER}/인사"}


def test_그룹을_적지_않으면_기본_그룹이고_없는_그룹이면_404다(
    server: RunningServer, parent: Path
) -> None:
    (parent / FOLDER).mkdir()

    response = _create(server, group="없는그룹")

    assert response.status_code == 404
    assert response.json()["code"] == "group_not_found"
    assert request(server, "GET", f"{SOURCES}/wiki").status_code == 404


def test_이름이_이미_있으면_409_source_already_exists다(
    server: RunningServer, parent: Path
) -> None:
    (parent / FOLDER).mkdir()
    (parent / "다른").mkdir()
    assert _create(server).status_code == 201

    response = _create(server, config={"folder": "다른"})

    assert response.status_code == 409
    assert response.json()["code"] == "source_already_exists"


# ---------- 칸의 규칙 ----------


@pytest.mark.parametrize("field", ["connector", "config"])
def test_가져오는_원천은_커넥터와_설정을_반드시_적는다(
    server: RunningServer, parent: Path, field: str
) -> None:
    fields: dict[str, object] = {"connector": "server_path", "config": {"folder": FOLDER}}
    del fields[field]

    response = request(server, "POST", SOURCES, name="wiki", kind="pull", **fields)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert errors(response) == [(field, "missing")]


@pytest.mark.parametrize(
    "extra",
    [
        {"connector": "server_path"},
        {"config": {"folder": FOLDER}},
        {"group": "default"},
        {"exclude_patterns": ["임시"]},
    ],
)
def test_밀어_넣는_원천은_이름만_받고_가져오는_원천의_칸을_적으면_422다(
    server: RunningServer, extra: dict[str, object]
) -> None:
    response = request(server, "POST", SOURCES, name="groupware", kind="push", **extra)

    assert response.status_code == 422
    assert errors(response) == [(next(iter(extra)), "extra_forbidden")]


def test_제외_패턴은_원천_하나에_50개까지_받는다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER).mkdir()

    too_many = _create(server, exclude_patterns=[f"패턴{number}" for number in range(51)])
    fifty = _create(server, exclude_patterns=[f"패턴{number}" for number in range(50)])

    assert too_many.status_code == 422
    assert errors(too_many)[0][0] == "exclude_patterns"
    assert fifty.status_code == 201


def test_제외_패턴_하나는_200자까지_받는다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER).mkdir()

    too_long = _create(server, exclude_patterns=["가" * 201])
    limit = _create(server, exclude_patterns=["가" * 200])

    assert too_long.status_code == 422
    assert errors(too_long)[0][0] == "exclude_patterns"
    assert limit.status_code == 201


# ---------- 폴더 확인 ----------


@pytest.mark.parametrize("folder", ["../밖", "규정집/../밖", "/절대", "", ".", "규정집\\하위"])
def test_폴더_값의_모양이_틀리면_422와_invalid_config다(
    server: RunningServer, parent: Path, folder: str
) -> None:
    response = _create(server, config={"folder": folder})

    assert response.status_code == 422
    assert errors(response) == [("config", "invalid_config")]


def test_설정에_폴더_칸이_없으면_422와_invalid_config다(
    server: RunningServer, parent: Path
) -> None:
    response = _create(server, config={})

    assert response.status_code == 422
    assert errors(response) == [("config", "invalid_config")]


def test_없는_폴더는_422와_not_found다(server: RunningServer, parent: Path) -> None:
    response = _create(server, config={"folder": "없는폴더"})

    assert response.status_code == 422
    assert errors(response) == [("config", "not_found")]
    assert request(server, "GET", f"{SOURCES}/wiki").status_code == 404


def test_심볼릭_링크인_폴더는_422와_rejected다(
    server: RunningServer, parent: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "밖"
    outside.mkdir()
    (parent / FOLDER).symlink_to(outside, target_is_directory=True)

    response = _create(server)

    assert response.status_code == 422
    assert errors(response) == [("config", "rejected")]


def test_중간_토막이_링크여도_422와_rejected다(
    server: RunningServer, parent: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "밖"
    (outside / "안").mkdir(parents=True)
    (parent / FOLDER).symlink_to(outside, target_is_directory=True)

    response = _create(server, config={"folder": f"{FOLDER}/안"})

    assert response.status_code == 422
    assert errors(response) == [("config", "rejected")]


def test_폴더가_아니라_파일이면_422와_rejected다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER).write_bytes(b"x")

    response = _create(server)

    assert response.status_code == 422
    assert errors(response) == [("config", "rejected")]


def test_폴더_이름을_합쳐_적은_꼴로_적어도_풀어_적은_폴더를_찾아_디스크의_이름으로_저장한다(
    server: RunningServer, parent: Path
) -> None:
    on_disk = unicodedata.normalize("NFD", FOLDER)
    assert on_disk != FOLDER
    (parent / on_disk).mkdir()

    response = _create(server, config={"folder": FOLDER})

    assert response.status_code == 201
    assert response.json()["config"] == {"folder": on_disk}


# ---------- 겹침 ----------


@pytest.mark.parametrize(
    ("first", "second"),
    [("a", "a"), ("a", "a/b"), ("a/b", "a")],
    ids=["같은_폴더", "안에_있는_폴더", "품은_폴더"],
)
def test_다른_원천의_폴더와_같거나_안에_있거나_품으면_409_source_folder_overlap이다(
    server: RunningServer, parent: Path, first: str, second: str
) -> None:
    (parent / "a" / "b").mkdir(parents=True)
    assert _create(server, "first", config={"folder": first}).status_code == 201

    response = _create(server, "second", config={"folder": second})

    assert response.status_code == 409
    assert response.json()["code"] == "source_folder_overlap"
    assert request(server, "GET", f"{SOURCES}/second").status_code == 404


def test_이름이_같은_글자로_시작해도_다른_폴더면_겹치지_않는다(
    server: RunningServer, parent: Path
) -> None:
    (parent / "규정").mkdir()
    (parent / "규정집").mkdir()
    assert _create(server, "first", config={"folder": "규정"}).status_code == 201

    assert _create(server, "second", config={"folder": "규정집"}).status_code == 201


# ---------- 고치기 ----------


def test_고치는_요청은_적은_칸만_고친다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER).mkdir()
    (parent / "새폴더").mkdir()
    _create(server, exclude_patterns=["임시"])

    patterned = request(server, "PATCH", f"{SOURCES}/wiki", exclude_patterns=["*.tmp"])
    moved = request(server, "PATCH", f"{SOURCES}/wiki", config={"folder": "새폴더"})

    assert patterned.status_code == 200
    assert patterned.json()["exclude_patterns"] == ["*.tmp"]
    assert patterned.json()["config"] == {"folder": FOLDER}
    assert moved.status_code == 200
    assert moved.json()["config"] == {"folder": "새폴더"}
    assert moved.json()["exclude_patterns"] == ["*.tmp"]
    assert request(server, "GET", f"{SOURCES}/wiki").json() == moved.json()


def test_설정을_고치면_만들_때와_같은_확인을_다시_한다(
    server: RunningServer, parent: Path, tmp_path: Path
) -> None:
    (parent / FOLDER).mkdir()
    (parent / "다른").mkdir()
    (parent / "링크").symlink_to(tmp_path, target_is_directory=True)
    _create(server, "wiki")
    _create(server, "other", config={"folder": "다른"})

    def patch(folder: str) -> httpx.Response:
        return request(server, "PATCH", f"{SOURCES}/wiki", config={"folder": folder})

    assert (patch("../밖").status_code, errors(patch("../밖"))) == (
        422,
        [("config", "invalid_config")],
    )
    assert errors(patch("없는폴더")) == [("config", "not_found")]
    assert errors(patch("링크")) == [("config", "rejected")]
    overlap = patch("다른")
    assert (overlap.status_code, overlap.json()["code"]) == (409, "source_folder_overlap")
    assert request(server, "GET", f"{SOURCES}/wiki").json()["config"] == {"folder": FOLDER}


def test_자기_자신의_폴더로_고쳐도_겹침이_아니다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER).mkdir()
    _create(server)

    response = request(server, "PATCH", f"{SOURCES}/wiki", config={"folder": FOLDER})

    assert response.status_code == 200


@pytest.mark.parametrize("field", ["name", "kind", "connector", "group", "paused", "next_run_at"])
def test_고치는_요청은_이름_갈래_커넥터_그룹과_일시_중지_다음_실행_시각을_받지_않는다(
    server: RunningServer, parent: Path, field: str
) -> None:
    (parent / FOLDER).mkdir()
    _create(server)

    response = request(server, "PATCH", f"{SOURCES}/wiki", **{field: "x"})

    assert response.status_code == 422
    assert errors(response) == [(field, "extra_forbidden")]


def test_밀어_넣는_원천을_고치려_하면_409_wrong_source_kind다(server: RunningServer) -> None:
    response = request(server, "PATCH", f"{SOURCES}/default", exclude_patterns=["임시"])

    assert response.status_code == 409
    assert response.json()["code"] == "wrong_source_kind"


def test_없는_원천을_고치려_하면_404다(server: RunningServer) -> None:
    response = request(server, "PATCH", f"{SOURCES}/없는원천", exclude_patterns=["임시"])

    assert response.status_code == 404
    assert response.json()["code"] == "source_not_found"


# ---------- 연결 확인 ----------


def test_원천을_만든_뒤_연결_확인은_200과_ok_참이다(server: RunningServer, parent: Path) -> None:
    (parent / FOLDER).mkdir()
    _create(server)

    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "code": None}


def test_폴더를_지운_뒤_연결_확인은_200과_ok_거짓_source_unreadable이다(
    server: RunningServer, parent: Path
) -> None:
    (parent / FOLDER).mkdir()
    _create(server)
    (parent / FOLDER).rmdir()

    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "code": "source_unreadable"}


def test_폴더를_여는_호출이_권한_오류를_내면_연결_확인은_ok_거짓_source_unreadable이다(
    server: RunningServer, parent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (parent / FOLDER).mkdir()
    _create(server)
    real_open, real_lstat = os.open, os.lstat

    def refuse_open(path: str | os.PathLike[str], *args: int, **kwargs: int) -> int:
        if os.fsdecode(path).replace("\\", "/").endswith(FOLDER):
            raise PermissionError(13, "권한 없음")
        return real_open(path, *args, **kwargs)

    def refuse_lstat(path: str | os.PathLike[str], **kwargs: int) -> os.stat_result:
        if os.fsdecode(path).replace("\\", "/").endswith(FOLDER):
            raise PermissionError(13, "권한 없음")
        return real_lstat(path, **kwargs)

    monkeypatch.setattr(os, "open", refuse_open)
    monkeypatch.setattr(os, "lstat", refuse_lstat)

    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "code": "source_unreadable"}


def test_열수는_있지만_열거를_거절하는_폴더는_연결_확인이_ok_거짓이다(
    server: RunningServer, parent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (parent / FOLDER).mkdir()
    _create(server)
    refuse_listing(monkeypatch, FOLDER)

    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "code": "source_unreadable"}


def test_이름은_보이지만_항목의_정보를_읽을_수_없는_폴더는_연결_확인이_ok_거짓이다(
    server: RunningServer, parent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 읽기 권한은 있고 탐색 권한이 없는 폴더다. 열기와 이름 열거는 통과하고 `list()`가 하는
    # 항목 정보 읽기에서 실패한다(PR #103의 지적, 셀프 리뷰가 실제 조건으로 다시 재현했다).
    (parent / FOLDER).mkdir()
    _create(server)
    hide_entry_info(monkeypatch)

    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "code": "source_unreadable"}


def test_링크로_바뀐_폴더는_연결_확인이_source_path_rejected다(
    server: RunningServer, parent: Path, tmp_path: Path
) -> None:
    (parent / FOLDER).mkdir()
    _create(server)
    (parent / FOLDER).rmdir()
    outside = tmp_path / "밖"
    outside.mkdir()
    (parent / FOLDER).symlink_to(outside, target_is_directory=True)

    response = request(server, "POST", f"{SOURCES}/wiki/check")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "code": "source_path_rejected"}


def test_밀어_넣는_원천의_연결_확인은_409_wrong_source_kind다(server: RunningServer) -> None:
    response = request(server, "POST", f"{SOURCES}/default/check")

    assert response.status_code == 409
    assert response.json()["code"] == "wrong_source_kind"


def test_없는_원천의_연결_확인은_404다(server: RunningServer) -> None:
    response = request(server, "POST", f"{SOURCES}/없는원천/check")

    assert response.status_code == 404
    assert response.json()["code"] == "source_not_found"


# ---------- 일시 중지와 다시 시작 ----------


def test_일시_중지와_다시_시작은_일시_중지_칸만_바꾸고_이미_그_상태여도_200이다(
    server: RunningServer, parent: Path
) -> None:
    (parent / FOLDER).mkdir()
    created = _create(server).json()

    paused = request(server, "POST", f"{SOURCES}/wiki/pause")
    paused_again = request(server, "POST", f"{SOURCES}/wiki/pause")
    resumed = request(server, "POST", f"{SOURCES}/wiki/resume")
    resumed_again = request(server, "POST", f"{SOURCES}/wiki/resume")

    assert [paused.status_code, paused_again.status_code] == [200, 200]
    assert paused.json() == paused_again.json() == {**created, "paused": True}
    assert [resumed.status_code, resumed_again.status_code] == [200, 200]
    assert resumed.json() == resumed_again.json() == created


@pytest.mark.parametrize("action", ["pause", "resume"])
def test_밀어_넣는_원천의_일시_중지와_다시_시작은_409_wrong_source_kind다(
    server: RunningServer, action: str
) -> None:
    response = request(server, "POST", f"{SOURCES}/default/{action}")

    assert response.status_code == 409
    assert response.json()["code"] == "wrong_source_kind"


@pytest.mark.parametrize("action", ["pause", "resume"])
def test_없는_원천의_일시_중지와_다시_시작은_404다(server: RunningServer, action: str) -> None:
    response = request(server, "POST", f"{SOURCES}/없는원천/{action}")

    assert response.status_code == 404
