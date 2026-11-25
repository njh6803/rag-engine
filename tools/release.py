"""릴리스 도구. 릴리스 번호, 릴리스 노트, 배포 파일 묶음을 짓고 이미지의 번호 태그를 판정한다.

릴리스 워크플로가 부른다(`.scratch/release-image/spec.md` 의 "저장소의 자리", "번호와 느낌표",
"릴리스 노트", "배포 파일 묶음"). agent-os 저장소의 같은 이름 도구(커밋 `1aac0cf`)를 옮겨 이
저장소의 값으로 고친 것이다. 표준 라이브러리만 쓴다. 의존성을 깔지 않은 CI 잡에서
`python3 tools/release.py` 로 돌기 때문이다(ci.yml 의 ticket 잡이
`python3 tools/check_ticket.py --ci` 로 도는 것과 같은 길이다).

밖에서 부르는 입구는 하위 명령 셋과 함수 하나다(`classify` 처럼 시험과 다른 티켓이 가져다 쓰는 순수
함수가 더 있다).

- `number [--repo DIR] [--head REV]`: 릴리스할지, 다음 릴리스 번호, 그 버전 태그, 지난 릴리스로 고른
  태그를 `key=value` 줄로 낸다(`$GITHUB_OUTPUT` 에 그대로 붙인다). 버전 태그가 하나도 없으면
  `previous_tag=` 는 빈 값이다. 제품 변경이 없으면 `release=false` 로 성공이고, 구성 오류는 까닭을
  stderr 에 적고 1 로 끝난다.
- `notes --number N --contract-versions PATH [--repo DIR] [--head REV] [--grype NAME=PATH]...`:
  릴리스 노트의 글을 stdout 에 낸다. `--grype` 는 이미지마다의 Grype 결과(거르지 않은 JSON)이고
  이미지마다 한 번씩 거듭 쓴다. `--contract-versions` 는 "계약 버전" 절에 실을 글의 파일이다.
  릴리스 워크플로가 지은 서버 이미지에서 `rag-engine --version` 을 돌려, 첫 줄을 뺀 둘째 줄부터를
  이 파일에 그대로 담아 넘긴다(필수다. 없으면 노트를 짓지 않는다). 도구는 앞뒤의 빈 줄을 덜고
  줄바꿈 꼴(CRLF 등)만 LF 로 맞춘 줄을 코드 울타리(백틱 셋으로 연 `text` 블록) 안에 실어 줄바꿈이
  노트에서 접히지 않게 한다. 파일이 없거나 읽지 못하거나 공백이 아닌 문자가 든 줄이 하나도 없거나
  백틱 셋으로 시작하는 줄이 있으면 노트를 짓지 않고 실패한다. 계약 버전이 빠진 노트가
  나가면 운영자가 자기 클라이언트와 맞는 릴리스인지 알 길이 없다(명세 "릴리스 노트").
- `bundle --number N --namespace NS [--source DIR] [--out DIR]`: `rag-engine-<N>.tar.gz` 를 짓고
  그 경로를 낸다.
- `judge_number_tag(종료 코드, 출력, digest)`: 번호 태그 조회의 결과로 붙인다·그대로 둔다·거부한다·
  붙이지 않는다를 가른다. 워크플로는 `tools/release_ci.py judge` 를 거쳐 부른다(그 도구는
  release-image 의 08 이 들인다).

`PRODUCT_PATHS` 가 제품 변경의 경로 목록의 원천이다. 제품 변경은 릴리스에 실릴 변경으로 세는 경로를
고친 변경이다. 넷은 `src/`, `pyproject.toml`, `uv.lock`, `deploy/` 이고 `pyproject.toml` 은 칸을
가리지 않고 통째로 센다(까닭은 명세 "제품 변경의 경로"). `README.md`, `docs/`(릴리스 노트 원고
포함), 테스트용 `compose.test.yml`, 평가용 `compose.eval.yml` 은 세지 않는다. 노트
검사(`tools/check_notes.py`)가 같은 것을 가져다 쓴다.

번호의 규칙과 커밋을 고르는 길은 명세 "번호와 느낌표"가 원천이다. 제목은 커밋 검사의 `PATTERN`
하나로 읽는다(길이와 끝 마침표는 보지 않는다). 커밋은 병합 커밋을 빼고, 지난 릴리스의 버전 태그에서
닿지 않으며 제품 경로를 고친 것이다. 첫 부모만 따라가는 길(`--first-parent`)과 경로로 거른 이력의
기본 단순화는 쓰지 않는다(`--full-history`. agent-os 의 프로브 `release_mechanics` README 7번이
안전한 쪽이라고 어림해 적은 것이고 이 저장소에서는 다시 재지 않았다).

배포 파일 묶음의 틀에는 자리 표지 둘을 쓴다. `@RAG_ENGINE_VERSION@` 는 릴리스 번호(`v` 없음)로,
`@RAG_ENGINE_NAMESPACE@` 는 이미지 이름공간으로 바뀐다. compose 의 `${...}` 와 프록시 설정의 `$` 와
겹치지 않게 `@` 로 감싼 이름이다. `@RAG_ENGINE_` 으로 시작하는 다른 표지가 남으면 묶음을 짓지
않는다. 묶음은 풀면 `rag-engine-<N>/` 하나가 나오고 그 안에 틀의 파일이 있다(틀의
`deploy/standalone/` 경로는 담지 않는다). 같은 입력이면 바이트가 같다(시각·소유자·gzip 이름을
고정한다).

못 보는 것:

- 버전 태그는 이 저장소의 로컬 `git tag` 만 본다. 원격에만 있는 태그는 CI 가 `git fetch --tags` 로
  가져온 뒤에야 보인다. 얕은 체크아웃은 이력이 모자라 번호도 노트도 짓지 않고 실패한다(전체 이력과
  태그를 받아야 한다). 명세의 "계산한 태그가 이미 있다" 규칙은 로컬 태그로는 닿을 길이 없다. 가장
  큰 태그가 언제나 지난 릴리스라 계산한 번호는 그것보다 크기 때문이다. 그래서 `ensure_untaken` 은
  방어이고 그 판정만 따로 시험한다.
- 릴리스 설정 파일은 작업 트리의 것을 읽는다. 릴리스하는 커밋을 체크아웃한 CI 에서는 같다.
- 묶음의 파일은 UTF-8 글로 읽는다. 읽지 못하는 파일은 자리 표지를 보지 않고 그대로 담는다.
  심볼릭 링크와 윈도의 junction 은 틀 폴더 자체든 그 아래든 담지 않고 실패한다. 출력 폴더가 틀 폴더
  안이면 묶음이 묶음을 다시 담으므로 실패한다.
- 업그레이드 원고와 기능 원고를 이름 바꾸기로 따라가지 못한다. 범위 안에서 업그레이드 원고를 다른
  이름으로 옮기며 고치면 원고를 더한 커밋 시점의 글이 실리고, 지난 릴리스에 있던 다른 폴더의 원고를
  내용 그대로 `features/` 로 옮기면 새 원고로 읽는다. 같은 모양이 agent-os 원본에 있다. 이
  저장소에서 고칠지는 실제 릴리스에서 나는지 본 뒤에 정한다.
- 번호 태그 판정이 읽는 `Digest:` 줄의 꼴은 `docker buildx imagetools inspect` 의 출력이다. agent-os
  저장소가 2026-11-16 에 로컬 레지스트리로 조회해 적어 둔 꼴을 옮긴 것이고, 이 저장소에서는 조회해
  보지 않았다. 조회 실패의 종료 코드와 `: not found` 꼴도 같은 저장소의 프로브 기록을 옮긴 것이다.
- 묶음은 파일만 담는다. 틀의 빈 하위 폴더는 담지 않고, 파일 권한은 모두 0644 라 실행 권한이 필요한
  파일은 지원하지 않는다.
- "계약 버전" 절은 받은 줄이 `rag-engine --version` 의 둘째 줄부터인지 보지 않는다. 첫 줄까지 담아
  넘겨도 그대로 싣는다.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import subprocess
import sys
import tarfile
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeGuard

if __package__ in (None, ""):  # 스크립트로 부르면 저장소 루트가 import 경로에 없다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.check_commit_msg import PATTERN  # noqa: E402

PRODUCT_PATHS = ("src", "pyproject.toml", "uv.lock", "deploy")
CONFIG_PATH = "deploy/release.toml"
CONFIG_KEY = "candidate_for"
NOTES_ROOT = "docs/release-notes"
FEATURES = f"{NOTES_ROOT}/features"
UPGRADE = f"{NOTES_ROOT}/upgrade"
INTRO = f"{NOTES_ROOT}/intro"
DEFAULT_SOURCE = "deploy/standalone"
GIT_TIMEOUT = 60.0
PREFIX = "release: "
BUNDLE_ROOT = "rag-engine"
VERSION_MARKER = "@RAG_ENGINE_VERSION@"
NAMESPACE_MARKER = "@RAG_ENGINE_NAMESPACE@"
FENCE = "```"

_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-rc\.([1-9][0-9]*))?")
_NAMESPACE = re.compile(r"[a-z0-9]+(?:(?:_|__|-+)[a-z0-9]+)*")  # 점 없는 Docker 경로 한 토막
_MARKER = re.compile(r"@RAG_ENGINE_[^@\s]*@?")  # 닫는 `@` 가 빠진 오타도 잡는다
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_DIGEST_LINE = re.compile(r"Digest:\s+(\S+)")
_NOT_FOUND = ": not found"


class ReleaseError(Exception):
    """구성 오류나 입력 오류. 까닭을 사람이 읽는 글로 담는다."""


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    candidate: int | None = None

    @property
    def key(self) -> tuple[int, int, int, int, int]:
        """유의적 버전의 차례. 출시 후보는 같은 번호의 정식 릴리스보다 작다."""
        final = 1 if self.candidate is None else 0
        return (self.major, self.minor, self.patch, final, self.candidate or 0)

    @property
    def final(self) -> bool:
        return self.candidate is None

    @property
    def base(self) -> Version:
        return Version(self.major, self.minor, self.patch)

    @property
    def tag(self) -> str:
        return f"v{self}"

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        return core if self.candidate is None else f"{core}-rc.{self.candidate}"


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


@dataclass(frozen=True)
class Plan:
    release: bool
    number: str | None
    previous_tag: str | None
    commits: tuple[Commit, ...]

    @property
    def tag(self) -> str | None:
        return None if self.number is None else f"v{self.number}"


class TagVerdict(Enum):
    ATTACH = "attach"
    KEEP = "keep"
    REJECT = "reject"
    HOLD = "hold"


def _is_object(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _mapping(value: object) -> dict[str, object]:
    return value if _is_object(value) else {}


def _items(value: object) -> list[object]:
    return list(value) if _is_list(value) else []


def parse_version(text: str) -> Version | None:
    found = _VERSION.fullmatch(text)
    if found is None:
        return None
    candidate = found.group(4)
    return Version(
        int(found.group(1)),
        int(found.group(2)),
        int(found.group(3)),
        None if candidate is None else int(candidate),
    )


def parse_tag(tag: str) -> Version | None:
    return parse_version(tag[1:]) if tag.startswith("v") else None


def classify(subject: str) -> tuple[str | None, bool]:
    """제목의 접두와 느낌표. 커밋 검사의 `PATTERN` 에 맞지 않으면 `(None, False)` 다."""
    found = PATTERN.match(subject)
    if found is None:
        return (None, False)
    end = found.end(1) if found.group(2) is None else found.end(2)
    return (found.group(1), subject[end : end + 1] == "!")


def display_title(subject: str) -> str:
    """접두와 범위와 느낌표를 뗀다. 끝의 ` (#번호)` 는 남긴다."""
    if PATTERN.match(subject) is None:
        return subject
    return subject.split(": ", 1)[1]


# ---------- git ----------


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        message = f"git {args[0]} 을 띄우지 못했거나 {GIT_TIMEOUT:.0f}초를 넘겼다: {error}"
        raise ReleaseError(message) from error


def _stderr(done: subprocess.CompletedProcess[bytes]) -> str:
    return done.stderr.decode("utf-8", errors="replace").strip()


def _git(repo: Path, *args: str) -> str:
    done = _run(repo, *args)
    if done.returncode != 0:
        raise ReleaseError(f"git {args[0]} 이 {done.returncode} 로 끝났다: {_stderr(done)}")
    return done.stdout.decode("utf-8", errors="replace")


def _tags(repo: Path) -> list[str]:
    return [line for line in _git(repo, "tag", "--list").split("\n") if line]


def _version_tags(tags: Sequence[str]) -> dict[str, Version]:
    found: dict[str, Version] = {}
    for tag in tags:
        version = parse_tag(tag)
        if version is not None:
            found[tag] = version
    return found


def _largest(versions: Mapping[str, Version]) -> str | None:
    return max(versions, key=lambda tag: versions[tag].key, default=None)


def _check_revision(head: str) -> None:
    """`-` 로 시작하는 리비전은 git 이 옵션으로 읽는다(`--output=파일` 은 로그를 그 파일에 쓴다)."""
    if head.startswith("-"):
        raise ReleaseError(f"리비전은 - 로 시작할 수 없다: {head!r}")


def _check_full_history(repo: Path) -> None:
    """얕은 체크아웃은 머리를 루트처럼 다룬다. 지난 커밋이 빠지고 옛 파일이 새 파일이 된다."""
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise ReleaseError(
            "얕은 체크아웃이라 이력이 모자라다. 전체 이력과 태그를 받은 뒤 "
            "(`git fetch --unshallow --tags`) 다시 돌린다"
        )


def _ensure_ancestor(repo: Path, tag: str, head: str) -> None:
    done = _run(repo, "merge-base", "--is-ancestor", f"refs/tags/{tag}", head)
    if done.returncode == 1:
        raise ReleaseError(
            f"지난 릴리스 {tag} 가 {head} 의 조상이 아니다. 버전 태그가 다른 가지에 있다"
        )
    if done.returncode != 0:
        raise ReleaseError(f"{tag} 와 {head} 의 조상 관계를 보지 못했다: {_stderr(done)}")


def _log(repo: Path, since: str | None, head: str, paths: Sequence[str], *options: str) -> str:
    """범위의 병합 아닌 커밋을 오래된 것부터 낸다.

    첫 부모만 따르지 않고(`--first-parent` 없음) 경로로 거른 이력의 기본 단순화도 쓰지 않는다.
    """
    span = head if since is None else f"refs/tags/{since}..{head}"
    return _git(
        repo,
        "log",
        "--no-merges",
        "--full-history",
        "--topo-order",
        "--reverse",
        *options,
        span,
        "--",
        *paths,
    )


def product_commits(repo: Path, since: str | None, head: str) -> list[Commit]:
    """`since` 태그에서 닿지 않고 제품 경로를 고친 커밋. 병합 커밋은 뺀다. 오래된 것부터."""
    output = _log(repo, since, head, PRODUCT_PATHS, "--format=%H%x00%s")
    commits: list[Commit] = []
    for line in output.split("\n"):
        if line:
            sha, _, subject = line.partition("\x00")
            commits.append(Commit(sha, subject))
    return commits


def _added(repo: Path, since: str | None, head: str, folder: str) -> list[str]:
    """범위 안의 커밋이 더한 `folder` 아래 파일. 더해진 커밋의 차례로, 같은 경로는 한 번만."""
    # 이름 바꾸기 찾기를 끈다. 켜 두면 옮긴 파일이 더해진 것이 아니라 바뀐 것(R)으로 나와 놓친다.
    output = _log(
        repo,
        since,
        head,
        [folder],
        "--no-renames",
        "--diff-filter=A",
        "--name-only",
        "--format=%x01%H",
    )
    moved: set[str] = set() if since is None else _moved_in(repo, since, head, folder)
    paths: list[str] = []
    for line in output.split("\n"):
        if line and not line.startswith("\x01") and line not in moved and line not in paths:
            paths.append(line)
    return paths


def _moved_in(repo: Path, since: str, head: str, folder: str) -> set[str]:
    """지난 릴리스에 이미 있던 파일을 범위 안에서 `folder` 아래로 옮긴 새 경로.

    지난 릴리스와 머리의 순 변경에서만 이름 바꾸기를 찾는다. 범위 안에서 더해진 뒤 옮긴 파일은 옛
    경로가 지난 릴리스에 없어 여기 들지 않는다. 내용을 절반 넘게 고치며 옮긴 파일은 이름 바꾸기로
    읽히지 않아 놓친다.
    """
    output = _git(
        repo,
        "diff",
        "-M",
        "--name-status",
        "--diff-filter=R",
        f"refs/tags/{since}",
        head,
        "--",
        folder,
    )
    columns = (line.split("\t") for line in output.split("\n") if line)
    return {one[2] for one in columns if len(one) == 3}


def _read_at(repo: Path, revision: str, path: str) -> str | None:
    """`revision` 의 `path` 글. 그 리비전에 경로가 없으면 None 이고, 있는데 읽지 못하면 실패한다."""
    listed = _git(repo, "ls-tree", "--full-tree", "--name-only", revision, "--", path)
    if not listed.strip():
        return None
    done = _run(repo, "show", f"{revision}:{path}")
    if done.returncode != 0:
        raise ReleaseError(f"{revision} 의 {path} 를 읽지 못했다: {_stderr(done)}")
    return done.stdout.decode("utf-8", errors="replace").rstrip("\n")


# ---------- 번호 ----------


def read_candidate(repo: Path) -> Version | None:
    """`deploy/release.toml` 의 `candidate_for`. 파일이 없거나 칸이 없으면 None 이다."""
    path = repo / CONFIG_PATH
    if not path.is_file():
        return None
    try:
        data = _mapping(tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ReleaseError(f"{CONFIG_PATH} 를 읽지 못했다: {error}") from error
    extra = sorted(set(data) - {CONFIG_KEY})
    if extra:
        raise ReleaseError(f"{CONFIG_PATH} 는 {CONFIG_KEY} 칸 하나만 받는다. 다른 칸: {extra}")
    if CONFIG_KEY not in data:
        return None
    value = data[CONFIG_KEY]
    version = parse_version(value) if isinstance(value, str) else None
    if version is None or not version.final:
        raise ReleaseError(
            f'{CONFIG_PATH} 의 {CONFIG_KEY} 는 앞에 0 이 없는 "X.Y.Z" 꼴이어야 한다: {value!r}'
        )
    return version


def ensure_untaken(tag: str, tags: Sequence[str]) -> None:
    if tag in tags:
        raise ReleaseError(f"계산한 태그 {tag} 가 이미 있다")


def _next_number(
    versions: Mapping[str, Version],
    previous: str | None,
    candidate: Version | None,
    commits: Sequence[Commit],
) -> Version:
    if candidate is not None:
        finals = [version for version in versions.values() if version.final]
        last_final = max(finals, key=lambda version: version.key, default=None)
        if last_final is not None and candidate.key <= last_final.key:
            raise ReleaseError(
                f"{CONFIG_PATH} 의 {CONFIG_KEY} {candidate} 가 지난 정식 릴리스 {last_final} "
                "보다 크지 않다"
            )
        used = [
            version.candidate
            for version in versions.values()
            if version.candidate is not None and version.base == candidate
        ]
        number = Version(
            candidate.major, candidate.minor, candidate.patch, max(used, default=0) + 1
        )
        if previous is not None and number.key <= versions[previous].key:
            raise ReleaseError(
                f"{CONFIG_KEY} {candidate} 로 계산한 {number} 가 지난 릴리스보다 크지 않다"
                f"({previous}). 이미 낸 변경의 범위가 엉킨다"
            )
        return number
    if previous is None:
        raise ReleaseError(
            f"출시 후보 칸({CONFIG_PATH} 의 {CONFIG_KEY})도 버전 태그도 없어 "
            "첫 릴리스의 번호를 정할 수 없다"
        )
    last = versions[previous]
    if last.candidate is not None:
        return last.base
    bumps = [classify(commit.subject) for commit in commits]
    if any(prefix == "feat" or breaking for prefix, breaking in bumps):
        return Version(last.major, last.minor + 1, 0)
    return Version(last.major, last.minor, last.patch + 1)


def plan_release(repo: Path, head: str = "HEAD") -> Plan:
    _check_revision(head)
    _check_full_history(repo)
    tags = _tags(repo)
    versions = _version_tags(tags)
    candidate = read_candidate(repo)
    previous = _largest(versions)
    if previous is not None:
        _ensure_ancestor(repo, previous, head)
    commits = product_commits(repo, previous, head)
    if not commits:
        return Plan(release=False, number=None, previous_tag=previous, commits=())
    number = _next_number(versions, previous, candidate, commits)
    ensure_untaken(number.tag, tags)
    return Plan(release=True, number=str(number), previous_tag=previous, commits=tuple(commits))


# ---------- 노트 ----------


def _warning_lines(grype: Mapping[str, str]) -> list[str]:
    found: set[tuple[str, str, str, str, tuple[str, ...]]] = set()
    for image, text in grype.items():
        try:
            document = _mapping(json.loads(text))
        except json.JSONDecodeError:
            document = {}
        if not _is_list(document.get("matches")) or "descriptor" not in document:
            raise ReleaseError(f"{image} 의 grype 결과가 거르지 않은 JSON 이 아니다")
        for entry in _items(document["matches"]):
            match = _mapping(entry)
            vulnerability = _mapping(match.get("vulnerability"))
            fix = _mapping(vulnerability.get("fix"))
            if str(vulnerability.get("severity", "")).upper() != "CRITICAL":
                continue
            if fix.get("state") != "fixed":
                continue
            identifier = str(vulnerability.get("id"))
            if not identifier.startswith("CVE-"):
                related = [
                    str(_mapping(one).get("id"))
                    for one in _items(match.get("relatedVulnerabilities"))
                ]
                identifier = next((one for one in related if one.startswith("CVE-")), identifier)
            artifact = _mapping(match.get("artifact"))
            found.add(
                (
                    image,
                    identifier,
                    str(artifact.get("name")),
                    str(artifact.get("version")),
                    tuple(str(one) for one in _items(fix.get("versions"))),
                )
            )
    lines: list[str] = []
    for image, identifier, name, version, fixes in sorted(found):
        fixed = f"고친 번호는 {', '.join(fixes)}이다." if fixes else "고친 번호가 나와 있다."
        lines.append(f"- {identifier}: {image} 이미지의 {name} {version}에 있다. {fixed}")
    return lines


def _section(heading: str, body: Sequence[str], *, joiner: str) -> str | None:
    return f"## {heading}\n\n{joiner.join(body)}" if body else None


def _contract_section(contract: str) -> str:
    """ "계약 버전" 절. 받은 줄의 앞뒤 빈 줄을 덜고 줄바꿈 꼴만 맞춰 코드 울타리 안에 싣는다."""
    lines = contract.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ReleaseError(
            "계약 버전 줄이 비었다. `rag-engine --version` 의 둘째 줄부터를 받아야 노트를 짓는다"
        )
    if any(line.strip().startswith(FENCE) for line in lines):
        raise ReleaseError(f"계약 버전 줄에 코드 울타리({FENCE})가 들어 있어 노트 꼴이 깨진다")
    return "## 계약 버전\n\n" + f"{FENCE}text\n" + "\n".join(lines) + f"\n{FENCE}"


def render_notes(
    repo: Path,
    number: str,
    contract: str,
    grype: Mapping[str, str] | None = None,
    head: str = "HEAD",
) -> str:
    _check_revision(head)
    _check_full_history(repo)
    version = parse_version(number)
    if version is None:
        raise ReleaseError(f"릴리스 번호가 X.Y.Z 나 X.Y.Z-rc.N 꼴이 아니다: {number!r}")
    contract_section = _contract_section(contract)
    older = {
        tag: found
        for tag, found in _version_tags(_tags(repo)).items()
        if found.key < version.key and (version.candidate is not None or found.final)
    }
    since = _largest(older)
    if since is not None:
        _ensure_ancestor(repo, since, head)
    commits = product_commits(repo, since, head)

    intro = _read_at(repo, head, f"{INTRO}/{version.base}.md")
    features = [
        text
        for path in _added(repo, since, head, FEATURES)
        if (text := _read_at(repo, head, path)) is not None
    ]
    upgrade: list[str] = []
    new_features: list[str] = []
    fixes: list[str] = []
    others: list[str] = []
    for commit in commits:
        prefix, breaking = classify(commit.subject)
        title = display_title(commit.subject)
        if breaking:
            upgrade.append(_upgrade_entry(repo, commit, title, since, head))
        elif prefix == "feat":
            new_features.append(f"- {title}")
        elif prefix == "fix":
            fixes.append(f"- {title}")
        else:
            others.append(f"- {title}")

    sections = [
        _section("경고", _warning_lines(grype or {}), joiner="\n"),
        None if intro is None else f"## 소개\n\n{intro}",
        _section("기능 소개", features, joiner="\n\n"),
        _section("업그레이드할 때 할 일", upgrade, joiner="\n\n"),
        contract_section,
        _section("새 기능", new_features, joiner="\n"),
        _section("고친 것", fixes, joiner="\n"),
        _section("그 밖의 변경", others, joiner="\n"),
    ]
    present = [section for section in sections if section is not None]
    return "\n\n".join(present) + "\n"


def _last_adder(repo: Path, since: str | None, head: str, path: str) -> str | None:
    """범위 안에서 `path` 를 마지막으로 더한 커밋. 지운 뒤 같은 경로에 다시 더하면 둘 이상이다."""
    output = _log(repo, since, head, [path], "--no-renames", "--diff-filter=A", "--format=%H")
    shas = [line for line in output.split("\n") if line]
    return shas[-1] if shas else None


def _upgrade_entry(repo: Path, commit: Commit, title: str, since: str | None, head: str) -> str:
    added = _git(
        repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "--diff-filter=A", "-r",
        "--no-renames", commit.sha, "--", UPGRADE,
    )  # fmt: skip
    texts: list[str] = []
    for path in (line for line in added.split("\n") if line):
        # 머리의 글은 그 경로를 마지막으로 더한 커밋의 것이다. 앞서 더한 커밋은 그때의 글을 싣는다.
        text = None
        if _last_adder(repo, since, head, path) == commit.sha:
            text = _read_at(repo, head, path)
        if text is None:
            text = _read_at(repo, commit.sha, path)
        if text is not None:
            texts.append(text)
    return "\n\n".join([f"### {title}", *texts])


# ---------- 배포 파일 묶음 ----------


def _fill(data: bytes, replacements: Mapping[str, str], where: str) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    left = _MARKER.search(text)
    if left is not None:
        raise ReleaseError(f"{where} 에 모르는 자리 표지 {left.group(0)} 가 남았다")
    return text.encode("utf-8")


def _is_link(path: Path) -> bool:
    """심볼릭 링크이거나 윈도의 junction 이다. 둘 다 대상을 따라가면 틀 밖으로 나간다."""
    return path.is_symlink() or path.is_junction()


def _template_files(source: Path) -> list[Path]:
    """틀 폴더 아래 파일을 이름순으로 낸다. 링크는 따라가지 않고 만나면 실패한다."""
    files: list[Path] = []
    pending = [source]
    while pending:
        for entry in sorted(pending.pop().iterdir()):
            if _is_link(entry):
                raise ReleaseError(f"심볼릭 링크나 junction 은 묶음에 담지 않는다: {entry}")
            if entry.is_dir():
                pending.append(entry)
            elif entry.is_file():
                files.append(entry)
    return sorted(files)


def _collect(
    source: Path, root: str, replacements: Mapping[str, str]
) -> tuple[set[str], dict[str, bytes]]:
    """틀 폴더의 파일을 자리 표지를 채워 읽고, 묶음 안의 폴더 이름과 파일 내용을 낸다."""
    if not source.is_dir():
        raise ReleaseError(f"배포 파일의 틀 폴더가 없다: {source}")
    if _is_link(source):  # 링크의 대상을 따라가면 틀 밖의 파일이 묶음에 실린다
        raise ReleaseError(f"배포 파일의 틀 폴더가 심볼릭 링크나 junction 이다: {source}")
    paths = _template_files(source)
    if not paths:
        raise ReleaseError(f"배포 파일의 틀 폴더가 비었다: {source}")
    names = {root}
    contents: dict[str, bytes] = {}
    for path in paths:
        relative = path.relative_to(source).as_posix()
        contents[f"{root}/{relative}"] = _fill(path.read_bytes(), replacements, relative)
        parent = relative.rpartition("/")[0]
        while parent:
            names.add(f"{root}/{parent}")
            parent = parent.rpartition("/")[0]
    return names, contents


def _pack(names: set[str], contents: Mapping[str, bytes]) -> bytes:
    """이름순으로, 시각과 소유자 없이 묶어 같은 입력이 같은 바이트가 되게 한다."""
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name in sorted([*names, *contents]):
                info = tarfile.TarInfo(name)
                info.mtime = 0
                if name in contents:
                    info.size = len(contents[name])
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(contents[name]))
                else:
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    archive.addfile(info)
    return raw.getvalue()


def build_bundle(source: Path, out_dir: Path, number: str, namespace: str) -> Path:
    if parse_version(number) is None:
        raise ReleaseError(f"릴리스 번호가 X.Y.Z 나 X.Y.Z-rc.N 꼴이 아니다: {number!r}")
    if _NAMESPACE.fullmatch(namespace) is None:
        raise ReleaseError(
            f"이미지 이름공간이 소문자·숫자·`_-` 로 된 점 없는 이름 하나가 아니다: {namespace!r}"
        )
    source_root = source.resolve()
    out_root = out_dir.resolve()
    if out_root == source_root or source_root in out_root.parents:
        raise ReleaseError(f"출력 폴더가 틀 폴더 안이면 묶음이 묶음을 다시 담는다: {out_dir}")
    root = f"{BUNDLE_ROOT}-{number}"
    names, contents = _collect(source, root, {VERSION_MARKER: number, NAMESPACE_MARKER: namespace})
    packed = _pack(names, contents)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{root}.tar.gz"
    target.write_bytes(packed)
    return target


# ---------- 번호 태그 판정 ----------


def judge_number_tag(exit_code: int, output: str, pushed_digest: str) -> TagVerdict:
    """번호 태그 조회(`docker buildx imagetools inspect`)의 결과로 할 일을 가른다.

    "없다" 는 종료 코드가 1 이고 마지막 줄이 `: not found` 로 끝날 때뿐이다. 종료 코드는 없음과
    실패가 모두 1 이라 가르지 못하지만, 1 이 아니면(셸이 docker 를 못 찾은 127 등) 조회 자체가
    돌지 못한 것이라 없다고 읽지 않는다. 같은 digest 면 그대로 두고, 다른 digest 면 거부하고,
    읽지 못하면 붙이지 않는다.
    """
    if _DIGEST.fullmatch(pushed_digest) is None:
        raise ReleaseError(
            f"올린 digest 가 sha256:<소문자 16진 64자> 꼴이 아니다: {pushed_digest!r}"
        )
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if exit_code == 0:
        for line in lines:
            found = _DIGEST_LINE.match(line)
            if found is not None:
                seen = found.group(1)
                if _DIGEST.fullmatch(seen) is None:  # 읽지 못한 값은 다른 digest 가 아니다
                    return TagVerdict.HOLD
                return TagVerdict.KEEP if seen == pushed_digest else TagVerdict.REJECT
        return TagVerdict.HOLD
    if exit_code == 1 and lines and lines[-1].endswith(_NOT_FOUND):
        return TagVerdict.ATTACH
    return TagVerdict.HOLD


# ---------- 명령줄 ----------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools/release.py", description="릴리스 도구")
    commands = parser.add_subparsers(dest="command", required=True)
    number = commands.add_parser("number", help="릴리스할지와 다음 릴리스 번호를 낸다")
    number.add_argument("--repo", default=".")
    number.add_argument("--head", default="HEAD")
    notes = commands.add_parser("notes", help="릴리스 노트의 글을 낸다")
    notes.add_argument("--number", required=True)
    notes.add_argument("--repo", default=".")
    notes.add_argument("--head", default="HEAD")
    notes.add_argument("--grype", action="append", default=[], help="이미지 이름=Grype JSON 경로")
    notes.add_argument(
        "--contract-versions",
        help="필수. `rag-engine --version` 의 둘째 줄부터를 담은 파일(계약 버전 절에 싣는다)",
    )
    bundle = commands.add_parser("bundle", help="배포 파일 묶음을 짓는다")
    bundle.add_argument("--number", required=True)
    bundle.add_argument("--namespace", required=True)
    bundle.add_argument("--source", default=DEFAULT_SOURCE)
    bundle.add_argument("--out", default=".")
    return parser


def _grype_reports(specs: Sequence[str]) -> dict[str, str]:
    reports: dict[str, str] = {}
    for spec in specs:
        name, separator, path = spec.partition("=")
        if not separator or not name or not path:
            raise ReleaseError(f"--grype 는 NAME=PATH 꼴이다: {spec!r}")
        if name in reports:  # 뒤의 보고서가 앞의 것을 덮으면 앞의 경고가 조용히 빠진다
            raise ReleaseError(f"--grype {name} 이 두 번 나왔다. 이미지마다 한 번씩만 쓴다")
        try:
            reports[name] = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ReleaseError(f"{name} 의 grype 결과를 읽지 못했다: {error}") from error
    return reports


def _contract_text(path: str | None) -> str:
    if path is None:
        raise ReleaseError("--contract-versions 가 없다. 계약 버전 줄을 받아야 노트를 짓는다")
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ReleaseError(f"계약 버전 줄의 파일을 읽지 못했다: {error}") from error


def _number_command(repo: Path, head: str) -> int:
    plan = plan_release(repo, head)
    lines = {
        "release": "true" if plan.release else "false",
        "number": plan.number or "",
        "tag": plan.tag or "",
        "previous_tag": plan.previous_tag or "",
    }
    for key, value in lines.items():
        print(f"{key}={value}")
    return 0


def main(argv: Sequence[str]) -> int:
    args = _parser().parse_args(list(argv))
    try:
        if args.command == "number":
            return _number_command(Path(args.repo), args.head)
        if args.command == "notes":
            text = render_notes(
                Path(args.repo),
                args.number,
                _contract_text(args.contract_versions),
                _grype_reports(args.grype),
                args.head,
            )
            sys.stdout.write(text)
            return 0
        print(build_bundle(Path(args.source), Path(args.out), args.number, args.namespace))
        return 0
    except (ReleaseError, OSError) as error:  # OSError: 묶음을 쓰다 나는 파일 오류
        print(f"{PREFIX}{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):  # 윈도 콘솔의 cp949 로 한국어가 깨지지 않게 한다
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
