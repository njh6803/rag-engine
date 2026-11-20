"""tools/release_ci.py 의 시험. 릴리스 워크플로가 단계 사이에서 부르는 판정 도구다(release-image
08).

번호와 노트와 묶음은 tools/release.py(test_release.py)가 맡고, 여기는 워크플로의 단계가 넘기는 값을
읽는 순수 판정을 본다. 이미지 아이디는 `docker save` 가 엔진 판에 따라 만드는 두 꼴(`<아이디>.json`
과 `blobs/sha256/<해시>`)을 모두 만들어 넣는다. 올린 이미지 색인의 꼴은
`docker buildx imagetools inspect --raw` 가 내는 OCI 색인이다. agent-os 저장소의 같은 이름 시험(커밋
`1aac0cf`)을 옮기고 이미지를 넷에서 둘로, 이름을 이 저장소의 값으로 고친 것이다.

저장소 상태 시험(아래 "저장소 상태" 절)은 bake 설정이 이미지 이름을 정하는 저장소 이름 둘,
이미지를 짓는 파일과 compose 의 바깥 이미지가 digest 로 고정됐는지, 프록시 설정의 `/mcp` 자리가
`proxy_buffering off` 를 두는지 본다. agent-os 의 시험은 bake 설정을 단독 배포 시험이 쓰는 별도
compose 파일(`compose.fixtures.yaml`)과도 견주는데, 이 저장소의 단독 compose 시험은 묶음의 compose
를 그대로 쓰므로 그 파일이 없다. 그래서 그 견줌은 뺐다. bake 설정의 저장소 이름과 compose 의
`image:` 줄과 설치 안내의 대응표를 맞대는 일은 이미 `tests/tools/test_deploy_guide.py` 의
`대응표_어긋남` 이 한다(release-image 04). 같은 견줌을 여기서 다시 쓰지 않고 이 파일은 bake 설정이
이미지 이름을 정하는 한 곳이라는 것만 본다.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from tools.release import ReleaseError
from tools.release_ci import (
    BAKE_FILE,
    IMAGES,
    PrecheckAction,
    bake_repositories,
    bake_repository,
    image_config_digest,
    main,
    manifest_config_digest,
    platform_manifest_digest,
    precheck,
    verify_files,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
SHA = "1" * 40
OTHER_SHA = "2" * 40
ROOT = Path(__file__).resolve().parents[2]
_TIMEOUT = 120


def _tar(path: Path, members: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


CONFIG = (
    b'{"architecture":"amd64","config":{"Env":["A=1"]},"rootfs":{"type":"layers","diff_ids":[]}}'
)


def test_옛_저장_방식의_저장_파일에서_설정_파일의_해시를_읽는다(tmp_path: Path) -> None:
    tar = _tar(
        tmp_path / "old.tar",
        {
            "manifest.json": json.dumps([{"Config": "abc.json", "Layers": []}]).encode(),
            "abc.json": CONFIG,
        },
    )
    assert image_config_digest(tar) == _digest(CONFIG)


def test_containerd_저장_방식의_저장_파일에서도_같은_해시를_읽는다(tmp_path: Path) -> None:
    hex_ = hashlib.sha256(CONFIG).hexdigest()
    tar = _tar(
        tmp_path / "oci.tar",
        {
            "manifest.json": json.dumps(
                [{"Config": f"blobs/sha256/{hex_}", "Layers": []}]
            ).encode(),
            f"blobs/sha256/{hex_}": CONFIG,
        },
    )
    assert image_config_digest(tar) == _digest(CONFIG)


def test_ENV만_다른_두_이미지는_설정_해시가_다르다(tmp_path: Path) -> None:
    other = CONFIG.replace(b"A=1", b"A=2")
    one = _tar(
        tmp_path / "one.tar",
        {"manifest.json": json.dumps([{"Config": "c.json"}]).encode(), "c.json": CONFIG},
    )
    two = _tar(
        tmp_path / "two.tar",
        {"manifest.json": json.dumps([{"Config": "c.json"}]).encode(), "c.json": other},
    )
    assert image_config_digest(one) != image_config_digest(two)


@pytest.mark.parametrize(
    ("members", "reason"),
    [
        ({}, "저장 파일에 manifest.json 이 없다"),  # 매니페스트가 없다
        ({"manifest.json": b"[]"}, "이미지 하나를 가리키지"),  # 이미지가 없다
        (
            {"manifest.json": json.dumps([{"Config": "a"}, {"Config": "b"}]).encode()},
            "이미지 하나를 가리키지",  # 이미지가 둘
        ),
        (
            {"manifest.json": json.dumps([{"Config": "없는.json"}]).encode()},
            "저장 파일에 없는.json 이 없다",  # 설정 파일이 없다
        ),
        ({"manifest.json": b"not json"}, "JSON 이 아니다"),
    ],
)
def test_저장_파일에서_설정을_하나로_고르지_못하면_실패한다(
    tmp_path: Path, members: dict[str, bytes], reason: str
) -> None:
    with pytest.raises(ReleaseError, match=reason):
        image_config_digest(_tar(tmp_path / "bad.tar", members))


def _index(*manifests: dict[str, object]) -> str:
    return json.dumps({"schemaVersion": 2, "manifests": list(manifests)})


def _entry(digest: str, os: str, arch: str, *, attestation: bool = False) -> dict[str, object]:
    entry: dict[str, object] = {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "digest": digest,
        "platform": {"os": os, "architecture": arch},
    }
    if attestation:
        entry["annotations"] = {"vnd.docker.reference.type": "attestation-manifest"}
    return entry


def test_올린_색인에서_증명이_아닌_리눅스_amd64_매니페스트를_고른다() -> None:
    text = _index(
        _entry(DIGEST_A, "linux", "amd64"),
        _entry(DIGEST_B, "unknown", "unknown", attestation=True),
    )
    assert platform_manifest_digest(text) == DIGEST_A


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (_index(_entry(DIGEST_A, "linux", "arm64")), "하나가 아니다"),  # 플랫폼이 맞지 않는다
        (
            _index(_entry(DIGEST_A, "linux", "amd64"), _entry(DIGEST_B, "linux", "amd64")),
            "하나가 아니다",  # 둘이다
        ),
        (
            _index(_entry(DIGEST_A, "linux", "amd64", attestation=True)),
            "하나가 아니다",  # 증명뿐이다
        ),
        (
            json.dumps({"schemaVersion": 2, "config": {"digest": DIGEST_A}}),
            "manifests 가 없다",  # 색인이 아니다
        ),
        ("not json", "JSON 이 아니다"),
    ],
)
def test_색인에서_매니페스트를_하나로_고르지_못하면_실패한다(text: str, reason: str) -> None:
    with pytest.raises(ReleaseError, match=reason):
        platform_manifest_digest(text)


def test_매니페스트의_설정_해시를_읽는다() -> None:
    text = json.dumps({"schemaVersion": 2, "config": {"digest": DIGEST_A}, "layers": []})
    assert manifest_config_digest(text) == DIGEST_A


@pytest.mark.parametrize("text", ["{}", '{"config": {}}', '{"config": {"digest": "sha256:x"}}'])
def test_매니페스트에_설정_해시가_없거나_꼴이_틀리면_실패한다(text: str) -> None:
    with pytest.raises(ReleaseError, match="config.digest"):
        manifest_config_digest(text)


def test_공개_릴리스가_이_커밋을_가리키면_더_할_일_없이_끝난다() -> None:
    plan = precheck(published=True, tag_commit=SHA, drafts=[], sha=SHA)
    assert plan.action is PrecheckAction.DONE
    assert plan.delete == ()


def test_공개_릴리스가_다른_커밋을_가리키면_실패한다() -> None:
    with pytest.raises(ReleaseError, match="다른 커밋"):
        precheck(published=True, tag_commit=OTHER_SHA, drafts=[], sha=SHA)


def test_공개_릴리스의_태그를_찾지_못해도_실패한다() -> None:
    with pytest.raises(ReleaseError, match="찾지 못한 커밋"):
        precheck(published=True, tag_commit="", drafts=[], sha=SHA)


def test_공개_릴리스_없이_git_태그만_있으면_실패한다() -> None:
    with pytest.raises(ReleaseError, match="git 태그"):
        precheck(published=False, tag_commit=SHA, drafts=[], sha=SHA)


def test_이_커밋의_남은_초안은_지우고_새로_만든다() -> None:
    plan = precheck(published=False, tag_commit="", drafts=[("11", SHA), ("12", SHA)], sha=SHA)
    assert plan.action is PrecheckAction.PROCEED
    assert plan.delete == ("11", "12")
    assert plan.replaced is True


def test_다른_커밋의_초안이_있으면_실패한다() -> None:
    with pytest.raises(ReleaseError, match="초안"):
        precheck(published=False, tag_commit="", drafts=[("11", OTHER_SHA)], sha=SHA)


def test_아무것도_없으면_그대로_진행한다() -> None:
    plan = precheck(published=False, tag_commit="", drafts=[], sha=SHA)
    assert plan.action is PrecheckAction.PROCEED
    assert plan.delete == ()
    assert plan.replaced is False


def _files(directory: Path, number: str, *, skip: str | None = None) -> None:
    names = [f"rag-engine-{number}.tar.gz", "notes.md", "release.json"]
    for image in IMAGES:
        names += [f"grype-{image}.json", f"sbom-{image}.spdx.json"]
    for name in names:
        if name != skip:
            (directory / name).write_text("{}" if name != "notes.md" else "# 노트\n", "utf-8")
    if skip != "release.json":
        manifest = {
            "number": number,
            "revision": SHA,
            "images": {image: DIGEST_A for image in IMAGES},
        }
        (directory / "release.json").write_text(json.dumps(manifest), "utf-8")


def _digests() -> dict[str, str]:
    return dict.fromkeys(IMAGES, DIGEST_A)


def test_이_저장소의_이미지는_서버와_작업자_둘이다() -> None:
    assert IMAGES == ("server", "worker")


def test_받은_파일이_다_있고_번호와_해시가_같으면_지난다(tmp_path: Path) -> None:
    _files(tmp_path, "0.1.0-rc.1")
    verify_files(tmp_path, "0.1.0-rc.1", SHA, _digests())


def test_받은_파일이_하나라도_빠지면_실패한다(tmp_path: Path) -> None:
    _files(tmp_path, "0.1.0-rc.1", skip="grype-worker.json")
    with pytest.raises(ReleaseError, match="grype-worker.json"):
        verify_files(tmp_path, "0.1.0-rc.1", SHA, _digests())


def test_배포_파일_묶음이_빠져도_실패한다(tmp_path: Path) -> None:
    _files(tmp_path, "0.1.0-rc.1", skip="rag-engine-0.1.0-rc.1.tar.gz")
    with pytest.raises(ReleaseError, match="rag-engine-0.1.0-rc.1.tar.gz"):
        verify_files(tmp_path, "0.1.0-rc.1", SHA, _digests())


def test_받은_파일의_판_번호가_다르면_실패한다(tmp_path: Path) -> None:
    _files(tmp_path, "0.1.0-rc.1")
    manifest = {"number": "0.1.0-rc.2", "revision": SHA, "images": _digests()}
    (tmp_path / "release.json").write_text(json.dumps(manifest), "utf-8")
    with pytest.raises(ReleaseError, match="번호"):
        verify_files(tmp_path, "0.1.0-rc.1", SHA, _digests())


def test_받은_파일의_이미지_해시가_다르면_실패한다(tmp_path: Path) -> None:
    _files(tmp_path, "0.1.0-rc.1")
    digests = _digests() | {"worker": DIGEST_B}
    with pytest.raises(ReleaseError, match="worker"):
        verify_files(tmp_path, "0.1.0-rc.1", SHA, digests)


def test_받은_파일의_커밋이_다르면_실패한다(tmp_path: Path) -> None:
    _files(tmp_path, "0.1.0-rc.1")
    with pytest.raises(ReleaseError, match="커밋"):
        verify_files(tmp_path, "0.1.0-rc.1", OTHER_SHA, _digests())


def test_명령줄의_번호_태그_판정은_조회_출력을_표준_입력으로_받는다(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("ERROR: x: not found\n"))
    assert main(["judge", "--exit-code", "1", "--digest", DIGEST_A]) == 0
    assert capsys.readouterr().out.strip() == "attach"


def test_명령줄의_판정은_다른_해시를_거부로_읽는다(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    text = f"Name: x\nMediaType: y\nDigest:    {DIGEST_B}\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert main(["judge", "--exit-code", "0", "--digest", DIGEST_A]) == 0
    assert capsys.readouterr().out.strip() == "reject"


def test_명령줄의_초안_확인은_출력_줄을_내고_실패하면_1로_끝난다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["precheck", "--published", "false", "--sha", SHA, "--draft", f"11={SHA}"]
    assert main(args) == 0
    out = capsys.readouterr().out.splitlines()
    assert "action=proceed" in out
    assert "delete=11" in out
    assert "replaced=true" in out
    bad = ["precheck", "--published", "false", "--sha", SHA, "--tag-commit", SHA]
    assert main(bad) == 1
    assert capsys.readouterr().err.startswith("release: ")


def test_명령줄의_파일_확인은_빠진_파일을_1로_알린다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _files(tmp_path, "0.1.0-rc.1", skip="notes.md")
    args = ["verify-files", "--dir", str(tmp_path), "--number", "0.1.0-rc.1", "--sha", SHA]
    for image in IMAGES:
        args += ["--digest", f"{image}={DIGEST_A}"]
    assert main(args) == 1
    assert "notes.md" in capsys.readouterr().err


def test_명령줄의_이미지_설정_해시는_저장_파일에서_읽어_낸다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tar = _tar(
        tmp_path / "old.tar",
        {"manifest.json": json.dumps([{"Config": "c.json"}]).encode(), "c.json": CONFIG},
    )
    assert main(["image-id", str(tar)]) == 0
    assert capsys.readouterr().out.strip() == _digest(CONFIG)


def test_명령줄의_매니페스트_고르기와_설정_읽기는_파일을_읽어_해시를_낸다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    index = tmp_path / "index.json"
    index.write_text(_index(_entry(DIGEST_A, "linux", "amd64")), "utf-8")
    assert main(["platform-manifest", str(index)]) == 0
    assert capsys.readouterr().out.strip() == DIGEST_A
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"config": {"digest": DIGEST_B}}), "utf-8")
    assert main(["manifest-config", str(manifest)]) == 0
    assert capsys.readouterr().out.strip() == DIGEST_B


def test_명령줄은_읽지_못하는_파일을_1로_알린다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["platform-manifest", str(tmp_path / "없다.json")]) == 1
    assert "읽지 못했다" in capsys.readouterr().err


def test_명령줄은_커밋_해시가_아닌_sha를_받지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["precheck", "--published", "true", "--sha", ""]) == 1
    assert "커밋 해시 40자" in capsys.readouterr().err
    _files(tmp_path, "0.1.0-rc.1")
    args = ["verify-files", "--dir", str(tmp_path), "--number", "0.1.0-rc.1", "--sha", "abc"]
    assert main(args) == 1
    assert "커밋 해시 40자" in capsys.readouterr().err


def test_명령줄은_이름_값_꼴이_아닌_초안과_해시를_받지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad_draft = ["precheck", "--published", "false", "--sha", SHA, "--draft", "11"]
    assert main(bad_draft) == 1
    assert "이름=값" in capsys.readouterr().err
    _files(tmp_path, "0.1.0-rc.1")
    bad_digest = ["verify-files", "--dir", str(tmp_path), "--number", "0.1.0-rc.1", "--sha", SHA]
    assert main([*bad_digest, "--digest", "server"]) == 1
    assert "이름=값" in capsys.readouterr().err


def test_첫째_잡이_이미지_해시를_하나도_넘기지_않으면_실패한다(tmp_path: Path) -> None:
    manifest: dict[str, object] = {"number": "0.1.0-rc.1", "revision": SHA, "images": {}}
    _files(tmp_path, "0.1.0-rc.1")
    (tmp_path / "release.json").write_text(json.dumps(manifest), "utf-8")
    with pytest.raises(ReleaseError, match="해시가 없다"):
        verify_files(tmp_path, "0.1.0-rc.1", SHA, {})


def test_워크플로가_부르는_꼴로_스크립트를_직접_실행해도_저장소_이름을_낸다() -> None:
    # 워크플로는 `python3 tools/release_ci.py repository server` 로 부른다. 패키지로 import 하는
    # 다른 시험은 스크립트로 부를 때만 드러나는 import 경로 문제를 보지 못한다.
    done = subprocess.run(
        [sys.executable, "tools/release_ci.py", "repository", "server"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=_TIMEOUT,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "rag-engine-server"


# ---------- Docker Hub 저장소 이름 ----------

BAKE = ROOT / BAKE_FILE

_BAKE_SAMPLE = """\
target "_common" {
  context = "."
}

target "one" {
  inherits = ["_common"]
  tags     = ["${NAMESPACE}/rag-engine-one:${TAG}"]
}
"""


def _repositories() -> dict[str, str]:
    return bake_repositories(BAKE.read_text("utf-8"))


def test_짓기_목록은_이미지_둘마다_저장소_이름_하나를_정한다() -> None:
    repositories = _repositories()
    assert set(repositories) == set(IMAGES)
    assert len(set(repositories.values())) == len(IMAGES)
    assert repositories == {"server": "rag-engine-server", "worker": "rag-engine-worker"}


def test_짓기_목록의_태그가_없는_바탕_대상은_건너뛴다() -> None:
    assert bake_repositories(_BAKE_SAMPLE) == {"one": "rag-engine-one"}


@pytest.mark.parametrize(
    "tags",
    [
        '["${NAMESPACE}/a:${TAG}", "${NAMESPACE}/b:${TAG}"]',
        '["${NAMESPACE}/a:latest"]',
        '["docker.io/a:${TAG}"]',
        "[]",
        # 둘째 항목이 변수라 따옴표 수가 같아도 bake 는 그 태그도 평가해 올린다.
        '["${NAMESPACE}/a:${TAG}", EXTRA_TAG]',
        '[EXTRA_TAG, "${NAMESPACE}/a:${TAG}"]',
    ],
)
def test_태그가_이름공간_저장소_태그_한_줄이_아니면_실패한다(tags: str) -> None:
    text = f'target "one" {{\n  tags = {tags}\n}}\n'
    with pytest.raises(ReleaseError, match="한 줄이 아니다"):
        bake_repositories(text)


def test_짓기_목록에_없는_대상의_저장소를_물으면_있는_대상을_알리며_실패한다() -> None:
    with pytest.raises(ReleaseError, match="저장소 이름이") as raised:
        bake_repository(_BAKE_SAMPLE, "none")
    assert "'none'" in str(raised.value)
    assert "['one']" in str(raised.value)


def test_명령줄은_짓기_대상의_저장소_이름을_낸다(capsys: pytest.CaptureFixture[str]) -> None:
    for target, repository in _repositories().items():
        assert main(["repository", target, "--bake", str(BAKE)]) == 0
        assert capsys.readouterr().out.strip() == repository


def test_명령줄은_다른_짓기_파일과_없는_대상을_다룬다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bake = tmp_path / "bake.hcl"
    bake.write_text(_BAKE_SAMPLE, "utf-8")
    assert main(["repository", "one", "--bake", str(bake)]) == 0
    assert capsys.readouterr().out.strip() == "rag-engine-one"
    assert main(["repository", "worker", "--bake", str(bake)]) == 1
    assert "저장소 이름이" in capsys.readouterr().err
    assert main(["repository", "one", "--bake", str(tmp_path / "없다.hcl")]) == 1
    assert "읽지 못했다" in capsys.readouterr().err


# ---------- 저장소 상태: 고정과 프록시 ----------

DOCKERFILE = ROOT / "deploy" / "images" / "Dockerfile"
COMPOSE = ROOT / "deploy" / "standalone" / "compose.yaml"
SITE_CONF = ROOT / "deploy" / "standalone" / "proxy" / "site.conf"
_PINNED = re.compile(r"@sha256:[0-9a-f]{64}")
_ARG = re.compile(r"^ARG\s+(?P<name>\w+)=(?P<value>\S+)\s*$", re.M)
_FROM = re.compile(
    r"^FROM\s+(?:--\S+\s+)*(?P<image>\S+)(?:\s+AS\s+(?P<stage>\S+))?\s*$", re.M | re.I
)
_COMPOSE_IMAGE = re.compile(r"^\s+image:\s*(?P<image>\S.*?)\s*$", re.M)
_YAML_COMMENT = re.compile(r"\s+#.*$")
# 우리가 짓는 이미지는 이름공간을 `.env` 에서 받는다. 이 접두의 줄은 바깥 이미지가 아니다.
_OWN_IMAGE = "${RAG_ENGINE_NAMESPACE"


def unpinned_from(dockerfile: str) -> list[str]:
    """이미지를 짓는 파일에서 digest(`@sha256:`)로 고정되지 않은 `FROM` 의 이미지를 모은다.

    `FROM ${이름}` 은 첫 `FROM` 앞의 `ARG 이름=값` 기본값을 읽고(Docker 는 그 앞의 `ARG` 만 `FROM`
    에서 쓰게 한다), 앞 단계의 이름(`FROM runtime AS server`)은 바깥에서 받는 이미지가 아니라
    건너뛴다. `FROM scratch` 도 건너뛴다.

    못 보는 것: `--build-arg` 로 기본값을 덮어쓰는 짓기(CI 와 bake 는 덮어쓰지 않는다), 한 줄에
    여러 `ARG` 를 적는 꼴, 줄 이음(`\\`)으로 나눈 `FROM`.
    """
    first_from = _FROM.search(dockerfile)
    head = dockerfile[: first_from.start()] if first_from is not None else dockerfile
    defaults = {m["name"]: m["value"] for m in _ARG.finditer(head)}
    stages: set[str] = set()
    found: list[str] = []
    for match in _FROM.finditer(dockerfile):
        image = match["image"]
        resolved = defaults.get(image[2:-1], image) if image.startswith("${") else image
        if image != "scratch" and image not in stages and _PINNED.search(resolved) is None:
            found.append(image)
        if match["stage"]:
            stages.add(match["stage"])
    return found


def unpinned_compose_images(compose: str) -> list[str]:
    """compose 에서 digest 로 고정되지 않은 바깥 이미지 줄을 모은다. 우리 이미지 줄은 센다.

    줄 뒤의 YAML 주석(` # …`)은 값이 아니므로 떼고 본다. 주석에만 digest 를 적은 줄은 고정되지 않은
    것이다.
    """
    values = [_YAML_COMMENT.sub("", m["image"]) for m in _COMPOSE_IMAGE.finditer(compose)]
    return [v for v in values if not v.startswith(_OWN_IMAGE) and _PINNED.search(v) is None]


_SERVICE_HEADER = re.compile(r"^  (?P<name>[a-z][a-z0-9_-]*):\s*$")
_OWN_REPOSITORY = re.compile(r"\}/(?P<repository>[a-z0-9-]+):")


def own_repository_by_service(compose: str) -> dict[str, str]:
    """compose 의 서비스마다 우리 이미지의 저장소 이름을 모은다. 바깥 이미지 서비스는 뺀다.

    서비스 머리는 두 칸 들여 쓴 `이름:` 줄이고, 그 아래 `image:` 줄이 우리 이미지 접두로 시작할 때만
    센다. 서비스를 서로 맞바꾸거나 저장소 이름을 틀리게 쓰면 짝이 달라진다.

    못 보는 것: `image:` 가 아닌 곳(`build:`)에서 오는 이미지, 한 서비스에 `image:` 가 둘인 꼴(뒤의
    것이 이긴다), 서비스 머리가 두 칸이 아닌 들여쓰기로 쓰인 꼴(앞 서비스에 붙는다), YAML 앵커로
    이미지 줄을 나누어 쓰는 꼴. 서비스 머리 뒤에 주석을 붙인 꼴(`  a:  # …`), 따옴표를 친 `image:`
    값, 저장소 이름 자리에 변수를 쓴 꼴은 그 서비스를 센 목록에서 조용히 뺀다. 빠지면 기대 맵과
    달라져 시험이 빨개지므로 거짓 음성은 작다.
    """
    found: dict[str, str] = {}
    service = ""
    for line in compose.splitlines():
        header = _SERVICE_HEADER.match(line)
        if header is not None:
            service = header["name"]
            continue
        image = _COMPOSE_IMAGE.match(line)
        if image is not None and image["image"].startswith(_OWN_IMAGE) and service:
            repository = _OWN_REPOSITORY.search(image["image"])
            if repository is not None:
                found[service] = repository["repository"]
    return found


def mcp_buffers(site_conf: str) -> bool:
    """프록시 설정의 `location = /mcp { … }` 한 덩어리가 `proxy_buffering off;` 를 두지 않으면 참.

    못 보는 것: 같은 줄에 여러 지시문을 적은 꼴, `include` 로 가져오는 설정, `location /mcp`
    (`=` 없는 접두 자리)로 바꿔 쓴 꼴(이 경우 `=` 자리가 없다고 읽어 참을 낸다).
    """
    block = re.search(r"^\s*location\s*=\s*/mcp\s*\{(?P<body>.*?)^\s*\}", site_conf, re.M | re.S)
    if block is None:
        return True
    return re.search(r"^\s*proxy_buffering\s+off\s*;", block["body"], re.M) is None


def test_이_저장소의_이미지를_짓는_파일은_바깥_이미지를_digest로_고정한다() -> None:
    text = DOCKERFILE.read_text("utf-8")
    # 범위가 비면 위반 0으로 조용히 초록이다. FROM 줄이 있는 파일을 읽었는지 먼저 본다.
    assert _FROM.search(text) is not None
    assert unpinned_from(text) == []


def test_digest_없는_FROM을_잡는다() -> None:
    text = "ARG PY=python:3.12-slim\nFROM ${PY} AS build\nFROM build AS server\n"
    assert unpinned_from(text) == ["${PY}"]
    assert unpinned_from("FROM python:3.12-slim\n") == ["python:3.12-slim"]
    pinned = "ARG PY=python:3.12-slim@sha256:" + "a" * 64 + "\nFROM ${PY} AS build\n"
    assert unpinned_from(pinned) == []
    # 첫 FROM 뒤에 같은 이름으로 다시 적은 ARG 는 FROM 이 읽지 않는다(Docker 규칙). 앞의 고정된
    # 기본값이 이긴다.
    later = pinned + "ARG PY=python:3.12-slim\n"
    assert unpinned_from(later) == []
    # `--platform=` 같은 옵션이 붙은 FROM 도 옵션 뒤의 이미지를 본다. 옵션 줄을 건너뛰면 고정되지
    # 않은 단계를 하나 더해도 통과한다.
    platform_unpinned = pinned + "FROM --platform=$BUILDPLATFORM python:3.12-slim AS helper\n"
    assert unpinned_from(platform_unpinned) == ["python:3.12-slim"]
    platform_pinned = (
        pinned + f"FROM --platform=$BUILDPLATFORM python@sha256:{'c' * 64} AS helper\n"
    )
    assert unpinned_from(platform_pinned) == []
    # 반대로 고정 값을 첫 FROM 뒤에만 적으면 FROM 은 그 값을 못 읽는다.
    only_after = "FROM ${PY} AS build\nARG PY=python:3.12-slim@sha256:" + "a" * 64 + "\n"
    assert unpinned_from(only_after) == ["${PY}"]


def test_이_저장소의_단독_compose는_바깥_이미지를_digest로_고정한다() -> None:
    text = COMPOSE.read_text("utf-8")
    # 바깥 이미지(프록시, PostgreSQL, 임베딩 서버 둘)와 우리 이미지 줄을 모두 읽었는지 본다.
    assert len(_COMPOSE_IMAGE.findall(text)) >= 7
    assert unpinned_compose_images(text) == []


def test_이_저장소의_단독_compose는_서비스마다_맞는_우리_이미지를_쓴다() -> None:
    # 마이그레이션과 서버는 서버 이미지, 작업자는 작업자 이미지를 쓴다. 저장소 이름은 bake 설정이
    # 정한다.
    repositories = _repositories()
    expected = {
        "migrate": repositories["server"],
        "server": repositories["server"],
        "worker": repositories["worker"],
    }
    assert own_repository_by_service(COMPOSE.read_text("utf-8")) == expected


def test_서비스끼리_맞바꾼_우리_이미지를_잡는다() -> None:
    text = COMPOSE.read_text("utf-8")
    repositories = _repositories()
    server, worker = repositories["server"], repositories["worker"]
    swapped = text.replace(f"/{worker}:", "/@@:").replace(f"/{server}:", f"/{worker}:")
    swapped = swapped.replace("/@@:", f"/{server}:")
    assert swapped != text
    assert own_repository_by_service(swapped) != own_repository_by_service(text)


def test_digest_없는_바깥_이미지_줄을_잡는다() -> None:
    text = (
        "services:\n"
        "  proxy:\n    image: nginx:1.29\n"
        "  server:\n    image: ${RAG_ENGINE_NAMESPACE:?x}/rag-engine-server:${V:?x}\n"
    )
    assert unpinned_compose_images(text) == ["nginx:1.29"]
    pinned = f"  proxy:\n    image: nginx@sha256:{'b' * 64}\n"
    assert unpinned_compose_images(pinned) == []
    # digest 를 주석에만 적은 줄은 고정된 것이 아니다. 값 뒤의 주석은 값이 아니다.
    commented = f"  proxy:\n    image: nginx:1.29  # 고정 예정 @sha256:{'b' * 64}\n"
    assert unpinned_compose_images(commented) == ["nginx:1.29"]
    pinned_with_comment = f"  proxy:\n    image: nginx@sha256:{'b' * 64}  # 1.29\n"
    assert unpinned_compose_images(pinned_with_comment) == []


def test_이_저장소의_프록시_설정은_mcp_자리에서_응답을_모으지_않는다() -> None:
    text = SITE_CONF.read_text("utf-8")
    # 지금의 서버는 응답을 모으지 않게 하는 머리를 싣기 때문에 기능 시험으로는 이 설정의 유무가
    # 갈리지 않는다. 그래서 설정 글을 직접 본다.
    assert "location = /mcp" in text
    assert mcp_buffers(text) is False


def test_mcp_자리가_응답을_모으게_바뀐_프록시_설정을_잡는다() -> None:
    on = (
        "    location = /mcp {\n        proxy_buffering on;\n        proxy_pass http://up;\n    }\n"
    )
    assert mcp_buffers(on) is True
    missing = "    location = /mcp {\n        proxy_pass http://up;\n    }\n"
    assert mcp_buffers(missing) is True
    # 다른 자리의 `proxy_buffering off` 는 /mcp 자리를 지켜 주지 않는다.
    elsewhere = missing + "    location = /health {\n        proxy_buffering off;\n    }\n"
    assert mcp_buffers(elsewhere) is True
    off = "    location = /mcp {\n        proxy_buffering off;\n        proxy_pass http://up;\n"
    off += "    }\n"
    assert mcp_buffers(off) is False
    assert mcp_buffers("    location / {\n    }\n") is True
