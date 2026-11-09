"""PyPI 의 sdist 를 내려받아 파일 목록, 라이선스 파일 머리, entry_points(console_scripts) 를 뽑는다.

사용: uv run python -I .scratch/core/probes/parsers/sdist_probe.py <download_dir> pkg
(저장소 루트에서. 표준 라이브러리만 쓴다. PyPI 를 부르고 sdist 를 <download_dir>에 내려받는다.)

2026-11-09에 휠이 없는 파서 후보(pyhwp 계열)에 돌려 표준 출력으로 읽었다. 출력 파일은 남기지 않았고
내려받은 sdist 도 옮기지 않았다.
"""

import json
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
dl_dir = Path(sys.argv[1])
pkg = sys.argv[2]
dl_dir.mkdir(parents=True, exist_ok=True)

req = urllib.request.Request(
    f"https://pypi.org/pypi/{pkg}/json", headers={"User-Agent": "rag-engine-probe/0.1"}
)
with urllib.request.urlopen(req, timeout=60) as r:
    data = json.loads(r.read().decode("utf-8"))
sd = [u for u in data["urls"] if u["packagetype"] == "sdist"]
if not sd:
    print("sdist 없음")
    sys.exit(0)
u = sd[0]
dest = dl_dir / u["filename"]
if not dest.exists():
    req = urllib.request.Request(u["url"], headers={"User-Agent": "rag-engine-probe/0.1"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())
print("sdist:", u["filename"], u["size"], u["upload_time"])


def members(path):
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                yield n, (lambda n=n, z=z: z.read(n))
    else:
        with tarfile.open(path) as t:
            for m in t.getmembers():
                if m.isfile():
                    yield m.name, (lambda m=m, t=t: t.extractfile(m).read())


names = []
interesting = {}
with zipfile.ZipFile(dest) if dest.suffix == ".zip" else tarfile.open(dest) as arc:
    if isinstance(arc, zipfile.ZipFile):
        for n in arc.namelist():
            names.append(n)
            low = n.lower()
            if low.endswith(
                (
                    "setup.py",
                    "setup.cfg",
                    "pyproject.toml",
                    "entry_points.txt",
                    "/license",
                    "/copying",
                    "license.txt",
                    "pkg-info",
                )
            ):
                interesting[n] = arc.read(n).decode("utf-8", "replace")
    else:
        for m in arc.getmembers():
            if not m.isfile():
                continue
            names.append(m.name)
            low = m.name.lower()
            if low.endswith(
                (
                    "setup.py",
                    "setup.cfg",
                    "pyproject.toml",
                    "entry_points.txt",
                    "/license",
                    "/copying",
                    "license.txt",
                    "pkg-info",
                )
            ):
                interesting[m.name] = arc.extractfile(m).read().decode("utf-8", "replace")

print("files:", len(names))
for n in names[:5]:
    print("  ", n)
for n, text in interesting.items():
    print("-----", n, f"({len(text)} chars)")
    lines = text.splitlines()
    if n.lower().endswith(("entry_points.txt", "setup.cfg")):
        print("\n".join(lines[:80]))
    elif n.lower().endswith("setup.py"):
        keep = [
            ln
            for ln in lines
            if any(
                k in ln
                for k in (
                    "console_scripts",
                    "hwp5",
                    "license",
                    "License",
                    "python_requires",
                    "version",
                    "entry_points",
                )
            )
        ]
        print("\n".join(keep[:60]))
    else:
        print("\n".join(lines[:10]))
