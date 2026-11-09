"""PyPI 메타데이터를 받아 판, 라이선스, 분류자, 의존성, 휠 속 py.typed 유무를 적는다.

사용: uv run python -I .scratch/core/probes/db-queue/pypi_meta.py <다운로드 디렉터리> <패키지...>
출력: 표준 출력에 텍스트 보고, 다운로드 디렉터리에 <pkg>.json과 휠 파일.
(저장소 루트에서. 표준 라이브러리만 쓴다. PyPI 를 부른다.)

2026-11-09에 질문 묶음별로 돌려 표준 출력을 같은 폴더의 `report_q1q2.txt`(psycopg, psycopg-binary,
psycopg-pool, asyncpg, sqlalchemy, alembic, yoyo-migrations), `report_q3.txt`(procrastinate,
pgqueuer, pq, pgmq, chancy, dramatiq-pg, taskiq-pg, arq, saq, celery, dramatiq),
`report_q4q5q6.txt`(testcontainers, pytest-postgresql, pgserver, postgresql-wheel, py-pglite, uuid6,
uuid-utils, python-ulid, pydantic-settings, pydantic, fastapi),
`report_embedded_pg.txt`(pg0-embedded, pgembed, pgbox, pgembed-pgvector)로 남겼다. 세 보고는 cp949
로 적혀 있어 옮기며 UTF-8 로 바꿨다. 다운로드 디렉터리(JSON, 휠)는 옮기지 않았다.
"""

import json
import sys
import urllib.request
import zipfile
from pathlib import Path

UA = {"User-Agent": "rag-engine-design-research/0.1 (facts gathering)"}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as f:
        f.write(resp.read())


def pick_wheel(urls: list[dict]) -> dict | None:
    wheels = [u for u in urls if u.get("packagetype") == "bdist_wheel"]
    if not wheels:
        return None
    # 순수 파이썬 휠 > cp312 win_amd64 > cp312 아무거나 > 첫째
    for pred in (
        lambda u: u["filename"].endswith("py3-none-any.whl"),
        lambda u: "cp312" in u["filename"] and "win_amd64" in u["filename"],
        lambda u: "cp312" in u["filename"],
        lambda u: "abi3" in u["filename"] and "win_amd64" in u["filename"],
    ):
        for u in wheels:
            if pred(u):
                return u
    return wheels[0]


def report_wheel(wheel: dict, dest: Path) -> None:
    """휠을 (없으면) 내려받아 py.typed, .pyi 수, 최상위 디렉터리를 적는다."""
    if not dest.exists():
        download(wheel["url"], dest)
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    py_typed = [n for n in names if n.endswith("py.typed")]
    pyi = [n for n in names if n.endswith(".pyi")]
    tops = sorted({n.split("/")[0] for n in names if not n.endswith(".dist-info/") and "/" in n})
    print(f"  휠: {wheel['filename']} ({wheel['size']} bytes)")
    print(f"  휠 속 py.typed: {py_typed if py_typed else '없음'}")
    print(f"  휠 속 .pyi 수: {len(pyi)}")
    print(f"  휠 최상위: {tops[:12]}")


def main() -> None:
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    for pkg in sys.argv[2:]:
        print("=" * 78)
        print(f"[{pkg}]")
        try:
            data = fetch_json(f"https://pypi.org/pypi/{pkg}/json")
        except Exception as e:
            print(f"  !! PyPI JSON 실패: {e!r}")
            continue
        (out_dir / f"{pkg}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
        info = data["info"]
        version = info["version"]
        urls = data["urls"]
        upload = min((u["upload_time"] for u in urls), default="?")
        print(f"  최신 판: {version}  (업로드 {upload})")
        print(f"  requires_python: {info.get('requires_python')!r}")
        print(f"  license 필드: {(info.get('license') or '')[:120]!r}")
        print(f"  license_expression: {info.get('license_expression')!r}")
        print(f"  license_files: {info.get('license_files')!r}")
        lic_cls = [c for c in info.get("classifiers", []) if c.startswith("License ::")]
        print(f"  License 분류자: {lic_cls}")
        py_cls = [
            c
            for c in info.get("classifiers", [])
            if c.startswith("Programming Language :: Python :: 3.")
        ]
        print(f"  Python 분류자: {[c.rsplit(' ', 1)[-1] for c in py_cls]}")
        typed_cls = [c for c in info.get("classifiers", []) if c.startswith("Typing ::")]
        print(f"  Typing 분류자: {typed_cls}")
        print(f"  requires_dist: {info.get('requires_dist')}")
        purls = info.get("project_urls") or {}
        print(f"  project_urls: {purls}")
        # 발표된 판 수와 최근 판 몇 개
        releases = data.get("releases", {})
        recent = sorted(
            ((min(f["upload_time"] for f in files), v) for v, files in releases.items() if files),
            reverse=True,
        )[:5]
        print(f"  최근 판 5개(업로드일, 판): {recent}")
        # 휠 내려받아 py.typed 확인
        wheel = pick_wheel(urls)
        if wheel is None:
            print("  휠 없음(sdist만)")
            continue
        dest = out_dir / wheel["filename"]
        try:
            report_wheel(wheel, dest)
        except Exception as e:
            print(f"  !! 휠 확인 실패: {e!r}")


if __name__ == "__main__":
    main()
