"""Docker Hub v2 API의 pull_count·star_count와 pypistats.org의 최근 월간 다운로드를 적는다.

실행(저장소 루트에서):
    uv run --no-project python -I -X utf8 \\
        .scratch/core/probes/vector-store/pulls_and_pypistats.py <dl2-dir>
(표준 라이브러리만 쓴다. Docker Hub 와 pypistats.org 를 부르고 원문 JSON 을 <dl2-dir>에 둔다.)

2026-11-09에 돌려 출력을 같은 폴더의 `pulls_and_pypistats.txt`로 남겼다(비교 문서 N-2·N-3 표). 원문
JSON(dl2/)은 옮기지 않았다.
"""

import datetime
import json
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
HUB = [
    "pgvector/pgvector",
    "groonga/pgroonga",
    "paradedb/paradedb",
    "semitechnologies/weaviate",
    "qdrant/qdrant",
    "milvusdb/milvus",
    "chromadb/chroma",
    "opensearchproject/opensearch",
    "getmeili/meilisearch",
    "library/postgres",
    "library/elasticsearch",
    "cubeplex/postgresql-pgroonga-pgvector",
    "tensorchord/vchord-postgres",
]
PYPI = [
    "pgvector",
    "psycopg",
    "psycopg2-binary",
    "kiwipiepy",
    "weaviate-client",
    "qdrant-client",
    "pymilvus",
    "chromadb",
    "opensearch-py",
    "meilisearch",
    "elasticsearch",
    "asyncpg",
    "lancedb",
]


def get(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "curl/8", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


print(f"# fetched {datetime.datetime.now(datetime.UTC).astimezone().date().isoformat()}")
print("## Docker Hub: repo\tpull_count\tstar_count\tlast_updated")
for repo in HUB:
    try:
        d = get(f"https://hub.docker.com/v2/repositories/{repo}")
        (out / f"hub_repo_{repo.replace('/', '_')}.json").write_text(
            json.dumps(d), encoding="utf-8"
        )
        print(
            f"{repo}\t{d.get('pull_count'):,}\t{d.get('star_count')}\t{str(d.get('last_updated'))[:10]}"
        )
    except Exception as e:
        print(f"{repo}\tERROR {str(e)[:60]}")

print("\n## pypistats recent: package\tlast_day\tlast_week\tlast_month")
for name in PYPI:
    try:
        d = get(f"https://pypistats.org/api/packages/{name}/recent")
        (out / f"pypistats_{name}.json").write_text(json.dumps(d), encoding="utf-8")
        x = d["data"]
        print(f"{name}\t{x['last_day']:,}\t{x['last_week']:,}\t{x['last_month']:,}")
    except Exception as e:
        print(f"{name}\tERROR {str(e)[:60]}")
