"""Anthropic 파이썬 SDK(`anthropic`)의 PyPI 메타데이터와 최신 휠의 라이선스 원문을 본다.

보는 것:
1. PyPI JSON 의 최신 판, 배포일, `requires_python`, 라이선스 칸(`license`, `license_expression`),
   라이선스 분류자, `requires_dist`(HTTP 클라이언트가 무엇인지), 프로젝트 주소.
2. 최신 순수 파이썬 휠을 메모리로 받아(디스크에 쓰지 않는다) `py.typed` 가 있는지, 휠 안
   라이선스 파일의 이름과 머리 줄, METADATA 의 License 줄.

설치형으로 재배포하는 이미지에 드는 의존성이라 라이선스를 원문으로 본다
(`docs/constitution/tech.md`, `docs/agents/issue-tracker.md` 의 프로브와 근거 절).

실행: uv run python -X utf8 .scratch/search-eval/probes/llm-sdk/pypi_anthropic.py
(표준 라이브러리만 쓴다. 네트워크는 pypi.org 와 그 JSON 이 가리키는 휠 주소뿐이고, 요청에 싣는
것은 패키지 이름뿐이다.)

2026-11-12에 돌렸다(출력 `pypi_anthropic_out.txt`). 결과 요약은 같은 폴더의 README 표에 있다.
"""

from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from typing import TypedDict

PACKAGE = "anthropic"
USER_AGENT = "pypi-metadata-probe"
LICENSE_HEAD_LINES = 25


class Info(TypedDict, total=False):
    version: str
    license: str | None
    license_expression: str | None
    requires_python: str | None
    requires_dist: list[str] | None
    classifiers: list[str]
    project_urls: dict[str, str] | None


class ReleaseFile(TypedDict, total=False):
    filename: str
    url: str
    size: int
    packagetype: str
    upload_time_iso_8601: str


class Package(TypedDict):
    info: Info
    urls: list[ReleaseFile]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data: bytes = response.read()
    return data


def section(title: str) -> None:
    print(f"\n===== {title} =====")


def print_metadata(info: Info) -> None:
    section("1: PyPI JSON")
    print("version:", info.get("version"))
    print("requires_python:", info.get("requires_python"))
    print("license:", (info.get("license") or "")[:120] or None)
    print("license_expression:", info.get("license_expression"))
    for classifier in info.get("classifiers", []):
        if classifier.startswith("License ::"):
            print("classifier:", classifier)
    print("project_urls:", info.get("project_urls"))
    print("requires_dist:")
    for requirement in info.get("requires_dist") or []:
        print("   ", requirement)


def print_wheel(release: ReleaseFile) -> None:
    section("2: 최신 휠")
    print("filename:", release.get("filename"))
    print("size:", release.get("size"))
    print("upload_time:", release.get("upload_time_iso_8601"))
    url = release.get("url")
    if url is None:
        print("휠 주소가 없다")
        return
    archive = zipfile.ZipFile(io.BytesIO(fetch(url)))
    names = archive.namelist()
    print("files:", len(names))
    print("py.typed:", [name for name in names if name.endswith("py.typed")])
    for name in names:
        lowered = name.lower()
        if name.endswith(".dist-info/METADATA"):
            for line in archive.read(name).decode("utf-8").splitlines():
                if line.startswith(("License", "Requires-Python", "Version")):
                    print("METADATA:", line)
        if "license" in lowered.rsplit("/", 1)[-1] or "/licenses/" in lowered:
            print("라이선스 파일:", name)
            for line in archive.read(name).decode("utf-8").splitlines()[:LICENSE_HEAD_LINES]:
                print("   |", line)


def main() -> None:
    package: Package = json.loads(fetch(f"https://pypi.org/pypi/{PACKAGE}/json"))
    print_metadata(package["info"])
    wheels = [
        release
        for release in package["urls"]
        if release.get("packagetype") == "bdist_wheel"
        and release.get("filename", "").endswith("-none-any.whl")
    ]
    if not wheels:
        print("순수 파이썬 휠이 없다:", [release.get("filename") for release in package["urls"]])
        return
    print_wheel(wheels[0])
    section("끝")


if __name__ == "__main__":
    main()
