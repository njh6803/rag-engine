"""릴리스 워크플로가 단계 사이에서 부르는 판정 도구.

`.github/workflows/release.yml` 이 `python3 tools/release_ci.py <하위 명령>` 으로 부른다. 번호와
노트와 묶음을 짓는 `tools/release.py` 와 달리 이 파일은 워크플로의 단계가 모은 사실을 받아 가르기만
한다. `gh`와 `docker`는 부르지 않는다. 사실을 모으는 것은 워크플로이고, 가르는 것을 여기 두는 까닭은
시험하기 위해서다(워크플로 자체에는 자동 시험이 없다. `.scratch/release-image/spec.md` Testing
Decisions). 표준 라이브러리만 쓴다. agent-os 저장소의 같은 이름 도구(커밋 `1aac0cf`)를 옮겨 이
저장소의 값(이미지 둘, 묶음 이름)으로 고친 것이다.

하위 명령:

- `image-id TAR`: `docker save` 가 만든 파일에서 이미지 설정 파일의 해시(`sha256:...`)를 낸다.
  시험한 이미지와 올린 이미지가 같은지 견주는 값이다.
- `platform-manifest FILE`: 올린 이미지 색인(`docker buildx imagetools inspect --raw` 의 출력)에서
  증명이 아닌 linux/amd64 매니페스트의 해시를 낸다.
- `manifest-config FILE`: 매니페스트의 설정 해시를 낸다.
- `repository TARGET [--bake FILE]`: 짓기 대상 이름(`server`, `worker`)에 대응하는 Docker Hub
  저장소 이름(이름공간 뒤 토막. `rag-engine-server` 등)을 `docker-bake.hcl` 의 `tags` 에서 읽어
  낸다. 둘의 대응을 정하는 유일한 곳이 그 파일이고, 워크플로가 이 명령으로 읽는다.
- `judge --exit-code N --digest D`: 번호 태그 조회의 출력(표준 입력)으로
  `attach`·`keep`·`reject`·`hold` 를 낸다.
- `precheck --published true|false [--tag-commit SHA] [--draft ID=SHA]... --sha SHA`: 둘째 잡의 사전
  확인. `$GITHUB_OUTPUT` 에 붙일 `key=value` 줄을 낸다.
- `verify-files --dir D --number N --sha SHA --digest 이미지=해시...`: 첫째 잡의 아티팩트를 받은
  직후 받은 파일이 다 있고 안의 릴리스 번호와 커밋과 해시가 첫째 잡의 출력과 같은지 본다.

실패는 까닭을 stderr 에 적고 1 로 끝난다.

못 보는 것:

- `image-id` 는 `manifest.json` 하나가 가리키는 설정 파일의 바이트를 읽을 뿐이다. 그 바이트가 두 꼴
  (`<아이디>.json` 과 `blobs/sha256/<해시>`)에서 같은 해시를 낸다는 것은 두 꼴을 만들어 넣어 본
  것이다. 어느 엔진이 어느 꼴을 내는지는 엔진 버전에 따라 갈린다. 이 저장소의 개발 PC(Docker 29.9.2,
  저장 드라이버 overlay2)의 `docker save` 는 `blobs/sha256/<해시>` 꼴을 냈고, 그 값은 `docker image
  inspect` 의 `Id` 와 같았다. `<아이디>.json` 꼴은 agent-os 가 자기 PC와 GitHub 러너의
  `docker save` 에서 읽었다고 적은 것이고 이 저장소에서는 읽어 보지 않았다. 이 저장소의 GitHub
  러너에서 어느 꼴이 나오는지도 아직 재지 못했다.
- 사전 확인은 사실의 수집(어느 릴리스와 태그와 초안이 있는지)이 맞다고 믿는다. 수집이 틀리면 판정도
  틀린다.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeGuard

if __package__ in (None, ""):  # 스크립트로 부르면 저장소 루트가 import 경로에 없다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.release import PREFIX, ReleaseError, judge_number_tag  # noqa: E402

# 짓기 대상 이름(`deploy/images/docker-bake.hcl` 의 `target`)이다. 이미지 파일과 점검 결과 파일의
# 이름이 이 이름을 따른다. Docker Hub 의 저장소 이름은 다르다. 둘의 대응은 `docker-bake.hcl` 의
# `tags` 한 곳이 정하고 `repository` 가 읽는다.
IMAGES = ("server", "worker")
BAKE_FILE = "deploy/images/docker-bake.hcl"
PLATFORM_OS = "linux"
PLATFORM_ARCH = "amd64"
ATTESTATION_KEY = "vnd.docker.reference.type"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_SHA = re.compile(r"[0-9a-f]{40}")
# `target "<대상>" { … }` 한 덩어리. 닫는 중괄호는 줄 맨 앞에 있다(안쪽 블록은 들여 쓴다).
_BAKE_TARGET = re.compile(r'^target\s+"(?P<target>[^"]+)"\s*\{(?P<body>.*?)^\}', re.M | re.S)
_BAKE_TAGS = re.compile(r"^\s*tags\s*=\s*\[(?P<tags>[^\]]*)\]", re.M)
_BAKE_TAG_ARRAY = re.compile(
    r'\s*"\$\{NAMESPACE\}/(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*):\$\{TAG\}"\s*,?\s*'
)


def _is_object(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _json(text: str, what: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ReleaseError(f"{what} 이 JSON 이 아니다: {error}") from error


# ---------- 이미지 설정의 해시 ----------


def image_config_digest(tar_path: Path) -> str:
    """`docker save` 파일의 `manifest.json` 이 가리키는 설정 파일의 sha256.

    엔진 버전에 따라 `<아이디>.json` 이나 `blobs/sha256/<해시>` 를 가리킨다. 둘 다 설정 파일의
    바이트가 이미지 설정 그대로이므로 그 해시는 설정과 레이어(`rootfs.diff_ids`)를
    함께 가리킨다.
    """
    try:
        with tarfile.open(tar_path) as archive:
            data = _config_bytes(archive)
    except (OSError, tarfile.TarError) as error:
        raise ReleaseError(f"{tar_path} 를 읽지 못했다: {error}") from error
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _config_bytes(archive: tarfile.TarFile) -> bytes:
    manifest = _read_member(archive, "manifest.json")
    entries = _json(manifest.decode("utf-8", errors="replace"), "manifest.json")
    if not _is_list(entries) or len(entries) != 1 or not _is_object(entries[0]):
        raise ReleaseError("manifest.json 이 이미지 하나를 가리키지 않는다")
    config = entries[0].get("Config")
    if not isinstance(config, str) or not config:
        raise ReleaseError("manifest.json 에 Config 가 없다")
    return _read_member(archive, config)


def _read_member(archive: tarfile.TarFile, name: str) -> bytes:
    try:
        member = archive.getmember(name)
    except KeyError as error:
        raise ReleaseError(f"저장 파일에 {name} 이 없다") from error
    handle = archive.extractfile(member)
    if handle is None:
        raise ReleaseError(f"저장 파일의 {name} 이 파일이 아니다")
    return handle.read()


# ---------- 올린 이미지 ----------


def platform_manifest_digest(index_text: str) -> str:
    """색인에서 증명이 아닌 linux/amd64 매니페스트의 해시. 하나가 아니면 실패한다."""
    document = _json(index_text, "이미지 색인")
    manifests = document.get("manifests") if _is_object(document) else None
    if not _is_list(manifests):
        raise ReleaseError("이미지 색인이 아니다(manifests 가 없다)")
    found: list[str] = []
    for entry in manifests:
        if not _is_object(entry):
            continue
        platform = entry.get("platform")
        annotations = entry.get("annotations")
        attestation = _is_object(annotations) and ATTESTATION_KEY in annotations
        if (
            _is_object(platform)
            and platform.get("os") == PLATFORM_OS
            and platform.get("architecture") == PLATFORM_ARCH
            and not attestation
        ):
            digest = entry.get("digest")
            if isinstance(digest, str) and _DIGEST.fullmatch(digest):
                found.append(digest)
    if len(found) != 1:
        raise ReleaseError(
            f"색인에서 {PLATFORM_OS}/{PLATFORM_ARCH} 매니페스트가 하나가 아니다"
            f"(찾은 수 {len(found)})"
        )
    return found[0]


def manifest_config_digest(manifest_text: str) -> str:
    document = _json(manifest_text, "이미지 매니페스트")
    config = document.get("config") if _is_object(document) else None
    digest = config.get("digest") if _is_object(config) else None
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        raise ReleaseError("매니페스트에 config.digest 가 없거나 꼴이 틀리다")
    return digest


# ---------- 저장소 이름 ----------


def bake_repositories(text: str) -> dict[str, str]:
    """`docker-bake.hcl` 에서 짓기 대상 이름마다 Docker Hub 저장소 이름(이름공간 뒤 토막)을 읽는다.

    `tags = ["${NAMESPACE}/<저장소>:${TAG}"]` 꼴 한 줄을 가진 대상만 센다(`_web` 처럼 태그가 없는
    바탕 대상은 건너뛴다). 태그가 둘 이상이거나 다른 꼴이면 실패한다. 이 파일이 대응을 정하는 유일한
    곳이다.
    """
    found: dict[str, str] = {}
    for block in _BAKE_TARGET.finditer(text):
        target = block.group("target")
        tags = _BAKE_TAGS.search(block.group("body"))
        if tags is None:
            continue
        # 배열 안 전체가 허용한 태그 글자 하나와 일치해야 한다. 변수(`EXTRA_TAG`)나 둘째 항목이
        # 끼면 bake 가 그 태그도 평가해 올리므로 일부만 맞는 배열은 받지 않는다.
        whole = _BAKE_TAG_ARRAY.fullmatch(tags.group("tags"))
        if whole is None:
            raise ReleaseError(
                f"{target} 의 tags 가 `${{NAMESPACE}}/<저장소>:${{TAG}}` 한 줄이 아니다: "
                f"{tags.group('tags').strip()!r}"
            )
        found[target] = whole.group("name")
    return found


def bake_repository(text: str, target: str) -> str:
    repositories = bake_repositories(text)
    try:
        return repositories[target]
    except KeyError:
        raise ReleaseError(
            f"짓기 대상 {target!r} 의 저장소 이름이 {BAKE_FILE} 에 없다"
            f"(있는 것: {sorted(repositories)})"
        ) from None


# ---------- 둘째 잡의 사전 확인 ----------


class PrecheckAction(Enum):
    DONE = "done"
    PROCEED = "proceed"


@dataclass(frozen=True)
class PrecheckPlan:
    action: PrecheckAction
    delete: tuple[str, ...]

    @property
    def replaced(self) -> bool:
        return bool(self.delete)


def precheck(
    *, published: bool, tag_commit: str, drafts: Sequence[tuple[str, str]], sha: str
) -> PrecheckPlan:
    """그 번호로 이미 있는 것을 보고 할 일을 가른다(명세 "릴리스 워크플로" 사전 확인).

    공개 릴리스가 있으면 그 태그가 이 커밋을 가리킬 때만 더 할 일 없이 끝난다. 공개 릴리스 없이 git
    태그만 있으면 실패한다. 초안은 이 커밋의 것만 지우고 새로 만들고, 다른 커밋의 것이면 실패한다.
    """
    if published:
        if tag_commit == sha:
            return PrecheckPlan(PrecheckAction.DONE, ())
        where = f"{tag_commit}" if tag_commit else "찾지 못한 커밋"
        raise ReleaseError(f"그 번호의 공개 릴리스가 이 커밋이 아닌 다른 커밋({where})을 가리킨다")
    if tag_commit:
        raise ReleaseError(
            f"공개 릴리스 없이 그 번호의 git 태그({tag_commit})만 있다. "
            "앞 실행이 남긴 것이라 사람이 본다"
        )
    for draft_id, target in drafts:
        if target != sha:
            raise ReleaseError(
                f"그 번호의 초안 {draft_id} 이 다른 커밋({target})의 것이다. "
                "앞 실행이 번호 태그를 붙인 릴리스일 수 있어 지우지 않는다"
            )
    return PrecheckPlan(PrecheckAction.PROCEED, tuple(draft_id for draft_id, _ in drafts))


# ---------- 둘째 잡이 받은 아티팩트 ----------


def required_files(number: str) -> list[str]:
    names = [f"rag-engine-{number}.tar.gz", "notes.md", "release.json"]
    for image in IMAGES:
        names += [f"grype-{image}.json", f"sbom-{image}.spdx.json"]
    return names


def verify_files(directory: Path, number: str, sha: str, digests: Mapping[str, str]) -> None:
    missing = [name for name in required_files(number) if not (directory / name).is_file()]
    if missing:
        raise ReleaseError(f"받은 아티팩트에 없는 파일: {', '.join(missing)}")
    try:
        manifest = _json((directory / "release.json").read_text(encoding="utf-8"), "release.json")
    except (OSError, UnicodeDecodeError) as error:
        raise ReleaseError(f"release.json 을 읽지 못했다: {error}") from error
    if not _is_object(manifest):
        raise ReleaseError("release.json 이 객체가 아니다")
    if manifest.get("number") != number:
        raise ReleaseError(
            f"아티팩트의 릴리스 번호 {manifest.get('number')!r} 가 "
            f"첫째 잡의 번호 {number!r} 와 다르다"
        )
    if manifest.get("revision") != sha:
        raise ReleaseError(f"아티팩트의 커밋 {manifest.get('revision')!r} 가 {sha!r} 와 다르다")
    images = manifest.get("images")
    if not _is_object(images):
        raise ReleaseError("release.json 에 images 가 없다")
    for image in IMAGES:
        expected = digests.get(image)
        if not expected:
            raise ReleaseError(f"첫째 잡의 출력에 {image} 의 해시가 없다")
        if images.get(image) != expected:
            raise ReleaseError(
                f"아티팩트의 {image} 해시 {images.get(image)!r} 가 첫째 잡의 {expected!r} 와 다르다"
            )


# ---------- 명령줄 ----------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools/release_ci.py", description="릴리스 단계 판정")
    commands = parser.add_subparsers(dest="command", required=True)
    image_id = commands.add_parser("image-id")
    image_id.add_argument("tar")
    for name in ("platform-manifest", "manifest-config"):
        sub = commands.add_parser(name)
        sub.add_argument("file")
    repository = commands.add_parser("repository")
    repository.add_argument("target")
    repository.add_argument("--bake", default=BAKE_FILE, help="docker-bake.hcl 의 경로")
    judge = commands.add_parser("judge")
    judge.add_argument("--exit-code", type=int, required=True)
    judge.add_argument("--digest", required=True)
    check = commands.add_parser("precheck")
    check.add_argument("--published", choices=("true", "false"), required=True)
    check.add_argument("--tag-commit", default="")
    check.add_argument("--draft", action="append", default=[], help="ID=커밋")
    check.add_argument("--sha", required=True)
    files = commands.add_parser("verify-files")
    files.add_argument("--dir", required=True)
    files.add_argument("--number", required=True)
    files.add_argument("--sha", required=True)
    files.add_argument("--digest", action="append", default=[], help="이미지=해시")
    return parser


def _pairs(specs: Sequence[str], what: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for spec in specs:
        key, separator, value = spec.partition("=")
        if not separator or not key or not value:
            raise ReleaseError(f"{what} 는 이름=값 꼴이다: {spec!r}")
        pairs.append((key, value))
    return pairs


def _read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ReleaseError(f"{path} 를 읽지 못했다: {error}") from error


def _run(args: argparse.Namespace) -> None:
    if args.command in ("precheck", "verify-files") and _SHA.fullmatch(args.sha) is None:
        raise ReleaseError(f"--sha 가 커밋 해시 40자가 아니다: {args.sha!r}")
    if args.command == "image-id":
        print(image_config_digest(Path(args.tar)))
    elif args.command == "platform-manifest":
        print(platform_manifest_digest(_read_file(args.file)))
    elif args.command == "manifest-config":
        print(manifest_config_digest(_read_file(args.file)))
    elif args.command == "repository":
        print(bake_repository(_read_file(args.bake), args.target))
    elif args.command == "judge":
        print(judge_number_tag(args.exit_code, sys.stdin.read(), args.digest).value)
    elif args.command == "precheck":
        if args.tag_commit and _SHA.fullmatch(args.tag_commit) is None:
            raise ReleaseError(f"--tag-commit 이 커밋 해시 40자가 아니다: {args.tag_commit!r}")
        plan = precheck(
            published=args.published == "true",
            tag_commit=args.tag_commit,
            drafts=_pairs(args.draft, "--draft"),
            sha=args.sha,
        )
        print(f"action={plan.action.value}")
        print(f"delete={' '.join(plan.delete)}")
        print(f"replaced={'true' if plan.replaced else 'false'}")
    else:
        verify_files(Path(args.dir), args.number, args.sha, dict(_pairs(args.digest, "--digest")))


def main(argv: Sequence[str]) -> int:
    args = _parser().parse_args(list(argv))
    try:
        _run(args)
    except (ReleaseError, OSError) as error:
        print(f"{PREFIX}{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):  # 윈도 콘솔의 cp949 로 한국어가 깨지지 않게 한다
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
