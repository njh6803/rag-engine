"""`anthropic` 을 운영 의존성에 더할 때 새로 드는 전이 의존 셋의 라이선스를 원문으로 본다.

보는 것: `uv pip install --dry-run "anthropic>=2.8,<3"` 이 새로 설치한다고 낸 판(docstring-parser
0.18.0, jiter 0.19.0, sniffio 1.3.1)마다
1. PyPI JSON 의 라이선스 칸(`license`, `license_expression`)과 라이선스 분류자.
2. 그 판의 휠 하나를 메모리로 받아(디스크에 쓰지 않는다) METADATA 의 License 줄과 휠 안 라이선스
   파일의 이름, 머리 줄.

설치형으로 재배포하는 이미지에 드는 의존성이라 라이선스를 원문으로 본다
(`docs/agents/issue-tracker.md` 의 프로브와 근거 절).

실행: uv run python -X utf8 .scratch/search-eval/probes/llm-sdk/pypi_transitive_licenses.py
(표준 라이브러리만 쓴다. 네트워크는 pypi.org 와 그 JSON 이 가리키는 휠 주소뿐이고, 요청에 싣는
것은 패키지 이름과 판뿐이다.)

2026-11-12에 돌렸다(출력 `pypi_transitive_licenses_out.txt`). 결과 요약은 같은 폴더의 README 표에
있다.
"""

from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from typing import TypedDict

PACKAGES = [("docstring-parser", "0.18.0"), ("jiter", "0.19.0"), ("sniffio", "1.3.1")]
USER_AGENT = "pypi-metadata-probe"
LICENSE_HEAD_LINES = 6


class Info(TypedDict, total=False):
    version: str
    license: str | None
    license_expression: str | None
    classifiers: list[str]


class ReleaseFile(TypedDict, total=False):
    filename: str
    url: str
    packagetype: str


class Package(TypedDict):
    info: Info
    urls: list[ReleaseFile]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data: bytes = response.read()
    return data


def print_wheel_licenses(release: ReleaseFile) -> None:
    print("wheel:", release.get("filename"))
    url = release.get("url")
    if url is None:
        print("휠 주소가 없다")
        return
    archive = zipfile.ZipFile(io.BytesIO(fetch(url)))
    for name in archive.namelist():
        lowered = name.lower()
        if name.endswith(".dist-info/METADATA"):
            for line in archive.read(name).decode("utf-8").splitlines():
                if line.startswith(("License", "Version")):
                    print("METADATA:", line)
        base = lowered.rsplit("/", 1)[-1]
        if "license" in base or "copying" in base or "/licenses/" in lowered:
            print("라이선스 파일:", name)
            text = archive.read(name).decode("utf-8", errors="replace")
            for line in text.splitlines()[:LICENSE_HEAD_LINES]:
                print("   |", line)


def main() -> None:
    for name, wanted in PACKAGES:
        print(f"\n===== {name} {wanted} =====")
        package: Package = json.loads(fetch(f"https://pypi.org/pypi/{name}/{wanted}/json"))
        info = package["info"]
        print("version:", info.get("version"))
        print("license:", (info.get("license") or "")[:120] or None)
        print("license_expression:", info.get("license_expression"))
        for classifier in info.get("classifiers", []):
            if classifier.startswith("License ::"):
                print("classifier:", classifier)
        wheels = [r for r in package["urls"] if r.get("packagetype") == "bdist_wheel"]
        if not wheels:
            print("휠이 없다:", [r.get("filename") for r in package["urls"]])
            continue
        print_wheel_licenses(wheels[0])
    print("\n===== 끝 =====")


if __name__ == "__main__":
    main()
