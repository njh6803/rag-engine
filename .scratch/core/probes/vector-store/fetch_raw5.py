"""N·O·P 절 원문 내려받기: 관리형 PostgreSQL 확장 목록, Weaviate·Qdrant·Milvus·Meilisearch·ParadeDB
문서, 라이선스 파일, 제한·텔레메트리 문서.

실행: uv run --no-project python -I -X utf8 .scratch/core/probes/vector-store/fetch_raw5.py
<dl2-dir> (표준 라이브러리만 쓴다. 목록은 ITEMS 에 박혀 있다. 실패분과 추가 원문은 fetch_list.py 로
받았다.)

2026-11-09에 돌린 상태 출력이 같은 폴더의 `fetch_raw5.txt`다. 원문(dl2/)은 저장소 밖 스크래치패드에
있어 세션이 끝나면 사라지며, 비교 문서 N·O·P 절의 "읽음" 근거를 다시 보려면 이 스크립트와
fetch_list.py 로 다시 받는다.
"""

import concurrent.futures
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
ITEMS = {
    # 관리형 PostgreSQL의 pgvector 탑재(공식 문서)
    "managed_aws_rds_ext.html": "https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html",
    "managed_aws_aurora_ext.html": "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html",
    "managed_gcp_cloudsql_ext.html": "https://cloud.google.com/sql/docs/postgres/extensions",
    "managed_gcp_alloydb_ext.html": "https://cloud.google.com/alloydb/docs/reference/extensions",
    "managed_azure_ext.html": "https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions",
    "managed_supabase_pgvector.html": "https://supabase.com/docs/guides/database/extensions/pgvector",
    "managed_supabase_pgroonga.html": "https://supabase.com/docs/guides/database/extensions/pgroonga",
    "managed_neon_pgvector.html": "https://neon.com/docs/extensions/pgvector",
    "managed_neon_ext_list.html": "https://neon.com/docs/extensions/pg-extensions",
    "managed_digitalocean_ext.html": "https://docs.digitalocean.com/products/databases/postgresql/details/supported-extensions/",
    "managed_crunchy_ext.html": "https://docs.crunchybridge.com/extensions-and-languages",
    # Weaviate(문서 저장소 raw)
    "weaviate_replication_arch.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/replication-architecture/index.md",
    "weaviate_cluster.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/cluster.md",
    "weaviate_vector_index.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/indexing/vector-index.md",
    "weaviate_rbac.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/configuration/rbac/index.md",
    "weaviate_collections_limits.mdx": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/starter-guides/managing-collections/collections-scaling-limits.mdx",
    "weaviate_multitenancy.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/data.md",
    "weaviate_wl_dir.json": "https://api.github.com/repos/weaviate/weaviate/contents/wl",
    "weaviate_LICENSE_WEAVIATE": "https://raw.githubusercontent.com/weaviate/weaviate/main/LICENSE-WEAVIATE",
    "weaviate_compression.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/vector-quantization.md",
    # Qdrant(landing_page raw)
    "qdrant_distributed.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/guides/distributed_deployment.md",
    "qdrant_telemetry.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/guides/telemetry.md",
    "qdrant_security.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/guides/security.md",
    "qdrant_storage.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/concepts/storage.md",
    "qdrant_memory_tiers.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/ops-configuration/memory-tiers.md",
    # Milvus
    "milvus_limits.md": "https://raw.githubusercontent.com/milvus-io/milvus-docs/v2.6.x/site/en/reference/limits.md",
    "milvus_architecture.md": "https://raw.githubusercontent.com/milvus-io/milvus-docs/v2.6.x/site/en/reference/architecture/architecture_overview.md",
    "milvus_diskann.md": "https://raw.githubusercontent.com/milvus-io/milvus-docs/v2.6.x/site/en/userGuide/indexes/floating-vector/diskann.md",
    # Meilisearch
    "meilisearch_tree.json": "https://api.github.com/repos/meilisearch/meilisearch/git/trees/main?recursive=1",
    "meilisearch_telemetry.mdx": "https://raw.githubusercontent.com/meilisearch/documentation/main/learn/resources/telemetry.mdx",
    "meilisearch_known_limits.mdx": "https://raw.githubusercontent.com/meilisearch/documentation/main/learn/resources/known_limitations.mdx",
    # ParadeDB
    "paradedb_docs_tree.json": "https://api.github.com/repos/paradedb/paradedb/git/trees/main?recursive=1",
    "paradedb_enterprise.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/operate/deploy/enterprise.mdx",
    # Groonga/PGroonga
    "groonga_limitations.html": "https://groonga.org/docs/limitations.html",
    "pgroonga_replication.html": "https://pgroonga.github.io/reference/streaming-replication.html",
    # 라이선스 원문(변경 이력 근거)
    "pgvecto_rs_LICENSE": "https://raw.githubusercontent.com/tensorchord/pgvecto.rs/main/LICENSE",
    "kiwi_README.md": "https://raw.githubusercontent.com/bab2min/Kiwi/main/README.md",
    # Chroma
    "chroma_telemetry.md": "https://raw.githubusercontent.com/chroma-core/chroma/main/docs/docs.trychroma.com/markdoc/content/docs/overview/telemetry.md",
    # OpenSearch
    "opensearch_disk_based.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_vector-search/optimizing-storage/disk-based-vector-search.md",
    "opensearch_security_plugin_LICENSE": "https://raw.githubusercontent.com/opensearch-project/security/main/LICENSE.txt",
    "opensearch_knn_LICENSE": "https://raw.githubusercontent.com/opensearch-project/k-NN/main/LICENSE.txt",
    # Elasticsearch
    "elastic_x_pack_LICENSE": "https://raw.githubusercontent.com/elastic/elasticsearch/main/licenses/ELASTIC-LICENSE-2.0.txt",
}


def get(item):
    name, url = item
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; curl/8)", "Accept": "*/*"}
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
        (out / name).write_bytes(data)
        return f"OK   {len(data):>8}  {name}"
    except Exception as e:
        return f"FAIL {str(e)[:40]:>8}  {name}  <- {url}"


with concurrent.futures.ThreadPoolExecutor(8) as ex:
    for line in ex.map(get, sorted(ITEMS.items())):
        print(line)
