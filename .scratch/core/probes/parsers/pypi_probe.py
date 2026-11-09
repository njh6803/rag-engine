"""PyPI JSON API로 패키지 메타데이터(라이선스, 최신 판, requires_python, 분류자, 배포 날짜)를 받고,
최신 판의 wheel 하나를 내려받아 py.typed 유무를 zip 목록으로 확인한다.

사용: uv run python -I .scratch/core/probes/parsers/pypi_probe.py <out_dir> <download_dir> pkg1 pkg2
... (저장소 루트에서. 표준 라이브러리만 쓴다. PyPI 를 부르고 휠을 <download_dir>에 내려받는다.)

2026-11-09에 파서 후보 패키지로 두 번 돌렸다. 둘째 실행의 출력이 같은 폴더의 `out2/pypi_probe.json`
(docling-slim, docling-core, docling-parse, pymupdf-layout, pymupdf4llm, surya-ocr, pdftext, pyhwpx,
hwp-extract, olefile)이다. 첫째 실행의 출력(pypdfium2, pdfplumber, pdfminer.six, pypdf, pymupdf,
docling, unstructured, marker-pdf, python-docx, docx2python, mammoth, python-hwpx, hwpx, pyhwp,
hwp5, kordoc)은 41KB 라 옮기지 않았고, 다시 받으려면 그 이름들로 돌린다. 내려받은 휠도 옮기지
않았다.
"""

import json
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
out_dir = Path(sys.argv[1])
dl_dir = Path(sys.argv[2])
pkgs = sys.argv[3:]
out_dir.mkdir(parents=True, exist_ok=True)
dl_dir.mkdir(parents=True, exist_ok=True)


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rag-engine-probe/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def pick_wheel(urls):
    # 우선 py3-none-any, 다음 cp312 win_amd64, 다음 아무 wheel
    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    prefs = (
        "py3-none-any",
        "cp312-cp312-win_amd64",
        "cp312-abi3-win_amd64",
        "cp39-abi3-win_amd64",
        "cp38-abi3-win_amd64",
        "abi3-win_amd64",
        "win_amd64",
    )
    for pref in prefs:
        for w in wheels:
            if pref in w["filename"]:
                return w
    return wheels[0] if wheels else None


def inspect_wheel(w, dest, rec):
    """휠을 (없으면) 내려받아 py.typed·.pyi·라이선스 파일·METADATA 의 라이선스 줄을 rec 에
    적는다."""
    if not dest.exists():
        req = urllib.request.Request(w["url"], headers={"User-Agent": "rag-engine-probe/0.1"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
        rec["py_typed_files"] = [n for n in names if n.endswith("py.typed")]
        rec["pyi_count"] = sum(1 for n in names if n.endswith(".pyi"))
        rec["py_typed"] = bool(rec["py_typed_files"])
        rec["license_files_in_wheel"] = [
            n for n in names if "LICEN" in n.upper() or "COPYING" in n.upper()
        ]
        meta = [n for n in names if n.endswith(".dist-info/METADATA")]
        if meta:
            text = z.read(meta[0]).decode("utf-8", "replace")
            rec["metadata_license_lines"] = [
                line
                for line in text.splitlines()[:300]
                if line.startswith(
                    ("License", "Classifier: License", "License-File", "License-Expression")
                )
            ]


results = {}
for pkg in pkgs:
    rec = {"package": pkg}
    try:
        data = fetch_json(f"https://pypi.org/pypi/{pkg}/json")
    except Exception as e:
        rec["error"] = repr(e)
        results[pkg] = rec
        print(pkg, "ERROR", e, flush=True)
        continue
    info = data["info"]
    rec["version"] = info["version"]
    rec["requires_python"] = info.get("requires_python")
    lic = info.get("license") or ""
    rec["license_field"] = lic if len(lic) < 300 else lic[:300] + "...(truncated)"
    rec["license_expression"] = info.get("license_expression")
    rec["license_classifiers"] = [
        c for c in info.get("classifiers", []) if c.startswith("License ::")
    ]
    rec["python_classifiers"] = [
        c
        for c in info.get("classifiers", [])
        if c.startswith("Programming Language :: Python :: 3.")
    ]
    rec["typing_classifier"] = [c for c in info.get("classifiers", []) if "Typing" in c]
    rec["home_page"] = info.get("home_page")
    rec["project_urls"] = info.get("project_urls")
    rec["summary"] = info.get("summary")
    rec["requires_dist_count"] = len(info.get("requires_dist") or [])
    rec["requires_dist"] = (info.get("requires_dist") or [])[:80]
    urls = data["urls"]
    rec["release_upload_time"] = urls[0]["upload_time"] if urls else None
    rels = data["releases"]

    def rel_time(v, rels=rels):
        files = rels.get(v) or []
        return files[0]["upload_time"] if files else ""

    recent = sorted(rels.keys(), key=rel_time, reverse=True)[:5]
    rec["recent_releases"] = [(v, rel_time(v)) for v in recent]
    rec["release_count"] = len(rels)
    w = pick_wheel(urls)
    if w is None:
        rec["wheel"] = None
        rec["py_typed"] = "wheel 없음(sdist만)"
    else:
        rec["wheel"] = w["filename"]
        rec["wheel_size"] = w["size"]
        dest = dl_dir / w["filename"]
        try:
            inspect_wheel(w, dest, rec)
        except Exception as e:
            rec["py_typed"] = f"확인 실패: {e!r}"
    results[pkg] = rec
    print(
        pkg,
        rec["version"],
        "py.typed=",
        rec.get("py_typed"),
        "lic=",
        rec["license_expression"] or rec["license_field"][:60],
        rec["license_classifiers"],
        flush=True,
    )

(out_dir / "pypi_probe.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("written", out_dir / "pypi_probe.json")
