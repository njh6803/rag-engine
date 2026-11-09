"""dl/의 원문에서 라이선스 머리줄, control 파일, GitHub 최신 릴리스, PyPI 메타데이터를 뽑아 적는다.

실행: uv run --no-project python -I .scratch/core/probes/vector-store/summarize_dl.py <dl-dir>
(표준 라이브러리만 쓴다. <dl-dir>은 fetch_raw.py~fetch_raw4.py 가 원문을 내려받은 곳이다. 그 원문은
저장소 밖 스크래치패드에 있어 세션이 끝나면 사라지니 다시 받아서 돌린다.)

2026-11-09에 돌려 표준 출력을 같은 폴더의 `summarize_dl.txt`로 남겼다(PyPI 절에 각 클라이언트의 판).
"""

import json
import pathlib
import re
import sys

dl = pathlib.Path(sys.argv[1])

print("=== LICENSE heads ===")
for p in sorted(dl.glob("*LICENSE*")) + sorted(dl.glob("*COPYING*")):
    t = p.read_text(encoding="utf-8", errors="replace")
    head = " | ".join(line.strip() for line in t.splitlines() if line.strip())[:260]
    print(f"{p.name}: {len(t)}B :: {head}")

print("\n=== control files ===")
for p in sorted(dl.glob("*.control*")):
    print(f"--- {p.name}\n{p.read_text(encoding='utf-8', errors='replace').strip()}")

print("\n=== GitHub latest releases ===")
for p in sorted(dl.glob("*_release.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        published = str(d.get("published_at"))[:10]
        name = str(d.get("name"))[:60]
        print(f"{p.name}: tag={d.get('tag_name')} published={published} name={name}")
    except Exception as e:
        print(f"{p.name}: ERR {e}")


def pypi_summary(p: pathlib.Path) -> None:
    """PyPI JSON 하나에서 최신 판, 업로드일, 휠 수와 크기, 라이선스, 의존성, extras 를 적는다."""
    d = json.loads(p.read_text(encoding="utf-8"))
    info = d["info"]
    rels = d.get("releases", {})
    ver = info["version"]
    files = rels.get(ver, [])
    upload = min((f["upload_time"] for f in files), default="?")[:10]
    wheels = [f for f in files if f["filename"].endswith(".whl")]
    sizes = sorted({round(f["size"] / 1e6, 1) for f in wheels})
    lic = info.get("license") or ""
    lic_expr = info.get("license_expression") or ""
    classifiers = [
        c for c in info.get("classifiers", []) if c.startswith("License") or c.startswith("Typing")
    ]
    reqs = [r for r in (info.get("requires_dist") or []) if "extra ==" not in r]
    extras = sorted(
        {
            m.group(1)
            for r in (info.get("requires_dist") or [])
            for m in [re.search(r'extra == "([^"]+)"', r)]
            if m
        }
    )
    print(
        f"--- {info['name']} {ver} ({upload}) requires_python={info.get('requires_python')}"
        f" wheels={len(wheels)} wheel_MB={sizes[:4]}"
    )
    print(f"    license={lic[:80]!r} license_expression={lic_expr!r} classifiers={classifiers}")
    print(f"    requires(no extra)={reqs}")
    print(f"    extras={extras}")


print("\n=== PyPI ===")
for p in sorted(dl.glob("pypi_*.json")):
    try:
        pypi_summary(p)
    except Exception as e:
        print(f"{p.name}: ERR {e}")
