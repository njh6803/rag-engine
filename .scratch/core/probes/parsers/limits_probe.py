"""파서 셋(pdfplumber, python-docx, python-hwpx)과 pdfminer.six 의 휠 소스에서 자원 한도를 찾는다.

근거로 드는 곳은 명세다. PR #2 직전 리뷰가 짚은 빈칸(신뢰할 수 없는 문서를 파싱할 때의 자원 한도)을
명세가 정하기 위한 입력이다. python-hwpx 6.11.0 의 한도(XMLParser 옵션, ZIP 항목 수·크기·압축비)는
PR #2 세션이 읽었고, 이 프로브는 같은 것을 다시 찍으면서 pdfplumber·pdfminer.six·python-docx 에도
같은 종류의 한도가 있는지 본다. 없는 한도는 우리가 바깥에서 두어야 한다.

보는 패턴: lxml `XMLParser(` 와 그 옵션(`huge_tree`, `resolve_entities`, `no_network`), 기본
`etree.fromstring`/`etree.parse`, ZIP 열기(`ZipFile(`)와 압축비·크기 한도 낱말(`compression_ratio`,
`max_entries`, `MAX_`), 재귀 한도(`setrecursionlimit`, `RecursionError`), 쪽 수·시간 상한 낱말
(`maxpages`, `timeout`).

실행(저장소 루트에서. PyPI JSON 과 휠을 받는다. 표준 라이브러리만):
    uv run python -I -X utf8 .scratch/core/probes/parsers/limits_probe.py <저장소 밖 폴더>
출력은 `limits_probe_out.txt` 로 남겼다(2026-11-10). 판은 출력의 `==` 줄에 있다. PyPI JSON 의 모양은
TypedDict 로 선언해 받는다(원칙 II 를 지키려는 것이지 응답을 검사하려는 것이 아니다).
"""

from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import TypedDict

PINNED: dict[str, str] = {
    "pdfplumber": "0.11.10",
    "python-docx": "1.2.0",
    "python-hwpx": "6.11.0",
}
PATTERNS: list[tuple[str, str]] = [
    ("xmlparser", r"XMLParser\("),
    ("xml_options", r"huge_tree|resolve_entities|no_network|load_dtd"),
    ("xml_default", r"etree\.(fromstring|parse|XML)\("),
    ("zip_open", r"ZipFile\("),
    (
        "zip_limits",
        r"compression_ratio|max_entries|max_total|max_entry|MAX_[A-Z_]*SIZE|MAX_[A-Z_]*COUNT",
    ),
    # 한도 상수의 정의 줄. 위 zip_limits 는 쓰는 자리까지 잡아 15줄에서 잘리므로 값이 안 보인다.
    ("zip_limit_values", r"^MAX_ZIP_[A-Z_]+\s*="),
    ("recursion", r"setrecursionlimit|RecursionError"),
    ("pages_timeout", r"maxpages|timeout"),
]


class PyPIUrl(TypedDict):
    packagetype: str
    url: str


class PyPIInfo(TypedDict):
    version: str
    requires_dist: list[str] | None


class PyPIMeta(TypedDict):
    info: PyPIInfo
    urls: list[PyPIUrl]


def pypi_json(name: str, version: str | None) -> PyPIMeta:
    url = f"https://pypi.org/pypi/{name}/json"
    if version is not None:
        url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url, timeout=60) as resp:
        loaded: PyPIMeta = json.loads(resp.read())
    return loaded


def wheel_url(meta: PyPIMeta) -> str:
    wheels = [entry["url"] for entry in meta["urls"] if entry["packagetype"] == "bdist_wheel"]
    pure = [u for u in wheels if u.endswith("py3-none-any.whl")]
    return (pure or wheels)[0]


def pinned_pdfminer(pdfplumber_meta: PyPIMeta) -> str | None:
    for req in pdfplumber_meta["info"]["requires_dist"] or []:
        match = re.match(r"pdfminer\.six\s*==\s*([0-9.]+)", req)
        if match:
            return match.group(1)
    return None


def download(url: str, dest: Path) -> Path:
    target = dest / url.rsplit("/", 1)[-1]
    if not target.exists():
        with urllib.request.urlopen(url, timeout=120) as resp:
            target.write_bytes(resp.read())
    return target


def scan(wheel: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(wheel.read_bytes())) as zf:
        names = [n for n in zf.namelist() if n.endswith(".py")]
        print(f"  python files: {len(names)}")
        for label, pattern in PATTERNS:
            rx = re.compile(pattern)
            hits: list[str] = []
            for name in names:
                text = zf.read(name).decode("utf-8", "replace")
                for no, line in enumerate(text.splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{name}:{no}: {line.strip()[:150]}")
            print(f"  --- {label} /{pattern}/ hits={len(hits)}")
            for hit in hits[:15]:
                print(f"    {hit}")


def main() -> None:
    dest = Path(sys.argv[1])
    dest.mkdir(parents=True, exist_ok=True)
    targets: list[tuple[str, str]] = list(PINNED.items())
    pdfplumber_meta = pypi_json("pdfplumber", PINNED["pdfplumber"])
    pdfminer_version = pinned_pdfminer(pdfplumber_meta)
    print("pdfplumber requires pdfminer.six ==", pdfminer_version)
    if pdfminer_version is None:
        pdfminer_version = pypi_json("pdfminer.six", None)["info"]["version"]
    targets.append(("pdfminer.six", pdfminer_version))
    for name, version in targets:
        meta = pypi_json(name, version)
        url = wheel_url(meta)
        wheel = download(url, dest)
        print(f"== {name} {version} wheel={wheel.name} bytes={wheel.stat().st_size}")
        scan(wheel)


if __name__ == "__main__":
    main()
