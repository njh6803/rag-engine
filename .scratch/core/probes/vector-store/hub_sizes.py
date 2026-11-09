"""Docker Hub v2 API로 후보 이미지의 압축 크기(바이트)를 읽어 MB로 적는다.

실행: uv run --no-project python -I .scratch/core/probes/vector-store/hub_sizes.py > hub_sizes.txt
(표준 라이브러리만 쓴다. Docker Hub 를 부른다. 태그는 TAGS 에 박혀 있다.)

2026-11-09에 돌려 출력을 같은 폴더의 `hub_sizes.txt`로 남겼다(postgres 18-trixie, pgvector
0.8.7-pg18-trixie, pgroonga 4.1.0, qdrant v1.20.0, weaviate 1.40.4, milvus v3.0.5·v2.6.27 등의
amd64·arm64 압축 크기 MB).
"""

import json
import urllib.request

TAGS = [
    ("library/postgres", "18-trixie"),
    ("pgvector/pgvector", "0.8.7-pg18-trixie"),
    ("groonga/pgroonga", "4.1.0-debian-18"),
    ("groonga/pgroonga", "4.1.0-alpine-18"),
    ("cubeplex/postgresql-pgroonga-pgvector", "latest"),
    ("qdrant/qdrant", "v1.20.0"),
    ("semitechnologies/weaviate", "1.40.4"),
    ("milvusdb/milvus", "v3.0.5"),
    ("milvusdb/milvus", "v2.6.27"),
    ("milvusdb/minio", "RELEASE.2024-12-18T13-15-44Z"),
    ("milvusdb/etcd", "3.5.30-r1"),
]
for repo, tag in TAGS:
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "curl/8"}), timeout=60
        ) as r:
            d = json.load(r)
        sizes = {
            i["architecture"]: round(i["size"] / 1e6, 1)
            for i in d["images"]
            if i.get("architecture") in ("amd64", "arm64")
        }
        print(f"{repo}:{tag}\tlast_updated={d['last_updated'][:10]}\tcompressed_MB={sizes}")
    except Exception as e:
        print(f"{repo}:{tag}\tERROR {e}")
