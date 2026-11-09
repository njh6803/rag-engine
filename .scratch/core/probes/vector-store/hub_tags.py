"""Docker Hub v2 API로 후보 이미지의 최근 태그 목록(이름, 갱신일, amd64 압축 크기 MB)을 적는다.

실행: uv run --no-project python -I .scratch/core/probes/vector-store/hub_tags.py > hub_tags.txt
(표준 라이브러리만 쓴다. Docker Hub 를 부른다.)

2026-11-09에 돌려 출력을 같은 폴더의 `hub_tags.txt`로 남겼다(저장소마다 최근 40개 태그).
"""

import json
import urllib.request

REPOS = [
    "paradedb/paradedb",
    "tensorchord/vchord-postgres",
    "tensorchord/vchord-suite",
    "timescale/timescaledb-ha",
    "opensearchproject/opensearch",
    "getmeili/meilisearch",
    "vespaengine/vespa",
    "typesense/typesense",
    "chromadb/chroma",
    "groonga/pgroonga",
    "pgvector/pgvector",
    "library/postgres",
    "qdrant/qdrant",
    "semitechnologies/weaviate",
]


def show_tags(repo: str) -> None:
    """저장소 하나의 최근 태그 40개를 이름, 갱신일, amd64 압축 크기 순으로 적는다."""
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=40&ordering=last_updated"
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "curl/8"}), timeout=60
    ) as r:
        d = json.load(r)
    print(f"## {repo}  (count={d.get('count')})")
    for t in d["results"]:
        amd = [i for i in t["images"] if i.get("architecture") == "amd64"]
        size = round(amd[0]["size"] / 1e6, 1) if amd else None
        print(f"  {t['name']:<48} {t['last_updated'][:10]}  amd64_MB={size}")


for repo in REPOS:
    try:
        show_tags(repo)
    except Exception as e:
        print(f"## {repo} ERROR {e}")
