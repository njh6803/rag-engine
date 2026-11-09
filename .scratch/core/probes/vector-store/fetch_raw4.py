"""4차 원문 내려받기(ParadeDB 설치·Dockerfile, OpenSearch k-NN 메모리, PostgreSQL 랭킹 문서).

실행: uv run --no-project python -I .scratch/core/probes/vector-store/fetch_raw4.py <dl-dir>
(표준 라이브러리만 쓴다. 목록은 ITEMS 에 박혀 있다.)

2026-11-09에 돌린 상태 출력이 같은 폴더의 `fetch_raw4.txt`다. 원문(dl/)은 옮기지 않았다(fetch_raw.py
독스트링).
"""

import concurrent.futures
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
ITEMS = {
    "paradedb_install_extension.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/operate/deploy/self-hosted/extension.mdx",
    "paradedb_Dockerfile.paradedb-18": "https://raw.githubusercontent.com/paradedb/paradedb/main/docker/Dockerfile.paradedb-18",
    "paradedb_Dockerfile.template": "https://raw.githubusercontent.com/paradedb/paradedb/main/docker/Dockerfile.template",
    "paradedb_docker_README.md": "https://raw.githubusercontent.com/paradedb/paradedb/main/docker/README.md",
    "paradedb_CHANGELOG.md": "https://raw.githubusercontent.com/paradedb/paradedb/main/CHANGELOG.md",
    "opensearch_knn_methods_engines.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_field-types/supported-field-types/knn-methods-engines.md",
    "pg_textsearch_controls.html": "https://www.postgresql.org/docs/current/textsearch-controls.html",
    "pg_textsearch_features.html": "https://www.postgresql.org/docs/current/textsearch-features.html",
}


def get(item):
    name, url = item
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        (out / name).write_bytes(data)
        return f"OK   {len(data):>8}  {name}"
    except Exception as e:
        return f"FAIL {str(e)[:40]:>8}  {name}  <- {url}"


with concurrent.futures.ThreadPoolExecutor(8) as ex:
    for line in ex.map(get, sorted(ITEMS.items())):
        print(line)
