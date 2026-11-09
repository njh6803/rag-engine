"""PyPI JSON에서 최신 판의 순수 파이썬 휠(또는 첫 휠)을 내려받아 py.typed 유무와 최상위 패키지를
적는다.

실행: uv run --no-project python -I -X utf8 .scratch/core/probes/vector-store/wheel_pytyped.py \\
    <dl-dir> <wheel-dir> <name> [<name> ...]
(표준 라이브러리만 쓴다. <dl-dir>에 fetch_raw.py 가 받은 `pypi_<name>.json`이 있어야 하고, 휠은
<wheel-dir>에 내려받는다.)

2026-11-09에 돌려 출력을 같은 폴더의 `wheel_pytyped.txt`로 남겼다(qdrant-client 1.20.0,
weaviate-client 4.24.1, pymilvus 3.0.2, opensearch-py 3.2.0, meilisearch 0.43.0,
meilisearch-python-sdk 8.1.5, typesense 2.1.1, elasticsearch 9.5.1, kiwipiepy 0.24.1). 휠은 옮기지
않았다.
"""

import json
import pathlib
import sys
import urllib.request
import zipfile

dl, wd = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
for name in sys.argv[3:]:
    d = json.loads((dl / f"pypi_{name}.json").read_text(encoding="utf-8"))
    ver = d["info"]["version"]
    files = [f for f in d["releases"][ver] if f["filename"].endswith(".whl")]
    files.sort(key=lambda f: (0 if "none-any" in f["filename"] else 1, f["size"]))
    if not files:
        print(f"{name} {ver}: no wheel")
        continue
    f = files[0]
    if f["size"] > 30_000_000:
        print(f"{name} {ver}: wheel too big ({f['size'] / 1e6:.1f}MB) skip {f['filename']}")
        continue
    dest = wd / f["filename"]
    if not dest.exists():
        urllib.request.urlretrieve(f["url"], dest)
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
    pytyped = sorted(n for n in names if n.endswith("py.typed"))
    tops = sorted({n.split("/")[0] for n in names if "/" in n and not n.endswith(".dist-info/")})
    print(
        f"{name} {ver}: {f['filename']} {f['size'] / 1e6:.2f}MB py.typed={pytyped} tops={tops[:8]}"
    )
