"""원문 파일(LICENSE, control, Cargo.toml, 문서 md, GitHub releases, PyPI JSON)을 dl/로 내려받는다.

실행: uv run --no-project python -I .scratch/core/probes/vector-store/fetch_raw.py <dl-dir>
(출력: 각 항목의 상태 한 줄. 표준 라이브러리만 쓴다. 목록은 ITEMS 에 박혀 있다.)

2026-11-09에 돌린 상태 출력이 같은 폴더의 `fetch_raw.txt`다. 내려받은 원문(dl/)은 저장소 밖
스크래치패드에 있어 세션이 끝나면 사라지며, 비교 문서의 "읽음" 근거를 다시 보려면 이 스크립트로 다시
받는다.
"""

import concurrent.futures
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
ITEMS = {
    # ParadeDB
    "paradedb_LICENSE": "https://raw.githubusercontent.com/paradedb/paradedb/main/LICENSE",
    "paradedb_pg_search.control": "https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/pg_search.control",
    "paradedb_README.md": "https://raw.githubusercontent.com/paradedb/paradedb/main/README.md",
    "paradedb_tokenizers.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/documentation/indexing/tokenizers.mdx",
    "paradedb_hybrid.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/documentation/guides/hybrid.mdx",
    "paradedb_release.json": "https://api.github.com/repos/paradedb/paradedb/releases/latest",
    "paradedb_Cargo.toml": "https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/Cargo.toml",
    # VectorChord
    "vchord_LICENSE": "https://raw.githubusercontent.com/tensorchord/VectorChord/main/LICENSE",
    "vchord_README.md": "https://raw.githubusercontent.com/tensorchord/VectorChord/main/README.md",
    "vchord_release.json": "https://api.github.com/repos/tensorchord/VectorChord/releases/latest",
    "vchord_bm25_LICENSE": "https://raw.githubusercontent.com/tensorchord/VectorChord-bm25/main/LICENSE",
    "vchord_bm25_README.md": "https://raw.githubusercontent.com/tensorchord/VectorChord-bm25/main/README.md",
    "pg_tokenizer_README.md": "https://raw.githubusercontent.com/tensorchord/pg_tokenizer.rs/main/README.md",
    "pg_tokenizer_LICENSE": "https://raw.githubusercontent.com/tensorchord/pg_tokenizer.rs/main/LICENSE",
    # pgvectorscale
    "pgvectorscale_LICENSE": "https://raw.githubusercontent.com/timescale/pgvectorscale/main/LICENSE",
    "pgvectorscale_README.md": "https://raw.githubusercontent.com/timescale/pgvectorscale/main/README.md",
    "pgvectorscale_release.json": "https://api.github.com/repos/timescale/pgvectorscale/releases/latest",
    # OpenSearch
    "opensearch_LICENSE.txt": "https://raw.githubusercontent.com/opensearch-project/OpenSearch/main/LICENSE.txt",
    "opensearch_release.json": "https://api.github.com/repos/opensearch-project/OpenSearch/releases/latest",
    "opensearch_doc_additional_plugins.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_install-and-configure/additional-plugins/index.md",
    "opensearch_doc_nori.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_install-and-configure/additional-plugins/analysis-nori-plugin.md",
    "opensearch_doc_docker.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_install-and-configure/install-opensearch/docker.md",
    "opensearch_doc_knn_filter.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_vector-search/filter-search-knn/index.md",
    "opensearch_doc_hybrid.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_vector-search/ai-search/hybrid-search/index.md",
    "opensearch_doc_install_index.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_install-and-configure/install-opensearch/index.md",
    # Elasticsearch
    "elasticsearch_LICENSE.txt": "https://raw.githubusercontent.com/elastic/elasticsearch/main/LICENSE.txt",
    "elasticsearch_release.json": "https://api.github.com/repos/elastic/elasticsearch/releases/latest",
    "lucene_NOTICE.txt": "https://raw.githubusercontent.com/apache/lucene/main/lucene/NOTICE.txt",
    # Meilisearch
    "meilisearch_LICENSE": "https://raw.githubusercontent.com/meilisearch/meilisearch/main/LICENSE",
    "meilisearch_release.json": "https://api.github.com/repos/meilisearch/meilisearch/releases/latest",
    "meilisearch_crate_Cargo.toml": "https://raw.githubusercontent.com/meilisearch/meilisearch/main/crates/meilisearch/Cargo.toml",
    "meilisearch_types_Cargo.toml": "https://raw.githubusercontent.com/meilisearch/meilisearch/main/crates/meilisearch-types/Cargo.toml",
    "meilisearch_milli_Cargo.toml": "https://raw.githubusercontent.com/meilisearch/meilisearch/main/crates/milli/Cargo.toml",
    "charabia_Cargo.toml": "https://raw.githubusercontent.com/meilisearch/charabia/main/charabia/Cargo.toml",
    "charabia_LICENSE": "https://raw.githubusercontent.com/meilisearch/charabia/main/LICENSE",
    # Vespa
    "vespa_LICENSE": "https://raw.githubusercontent.com/vespa-engine/vespa/master/LICENSE",
    "vespa_release.json": "https://api.github.com/repos/vespa-engine/vespa/releases/latest",
    # LanceDB / lance
    "lancedb_LICENSE": "https://raw.githubusercontent.com/lancedb/lancedb/main/LICENSE",
    "lancedb_release.json": "https://api.github.com/repos/lancedb/lancedb/releases/latest",
    "lance_index_Cargo.toml": "https://raw.githubusercontent.com/lancedb/lance/main/rust/lance-index/Cargo.toml",
    "lance_python_Cargo.toml": "https://raw.githubusercontent.com/lancedb/lance/main/python/Cargo.toml",
    "lancedb_python_Cargo.toml": "https://raw.githubusercontent.com/lancedb/lancedb/main/python/Cargo.toml",
    "lancedb_fts_doc.md": "https://raw.githubusercontent.com/lancedb/lancedb/main/docs/src/fts.md",
    # Chroma
    "chroma_LICENSE": "https://raw.githubusercontent.com/chroma-core/chroma/main/LICENSE",
    "chroma_release.json": "https://api.github.com/repos/chroma-core/chroma/releases/latest",
    # Typesense
    "typesense_LICENSE.txt": "https://raw.githubusercontent.com/typesense/typesense/v29.0/LICENSE.txt",
    "typesense_release.json": "https://api.github.com/repos/typesense/typesense/releases/latest",
    # Dictionaries / tokenizers
    "kagome_LICENSE": "https://raw.githubusercontent.com/ikawaha/kagome/v2/LICENSE",
    "kagome_dict_ko_LICENSE": "https://raw.githubusercontent.com/ikawaha/kagome-dict-ko/main/LICENSE",
    "kagome_dict_ko_README.md": "https://raw.githubusercontent.com/ikawaha/kagome-dict-ko/main/README.md",
    "lindera_LICENSE": "https://raw.githubusercontent.com/lindera/lindera/main/LICENSE",
    "lindera_README.md": "https://raw.githubusercontent.com/lindera/lindera/main/README.md",
    "lindera_ko_dic_LICENSE": "https://raw.githubusercontent.com/lindera/lindera-ko-dic/main/LICENSE",
    "lindera_ko_dic_README.md": "https://raw.githubusercontent.com/lindera/lindera-ko-dic/main/README.md",
    "mecab_ko_dic_README": "https://bitbucket.org/eunjeon/mecab-ko-dic/raw/master/README",
    "mecab_ko_dic_COPYING": "https://bitbucket.org/eunjeon/mecab-ko-dic/raw/master/COPYING",
    "mecab_ko_README": "https://bitbucket.org/eunjeon/mecab-ko/raw/master/README.md",
    "mecab_COPYING": "https://raw.githubusercontent.com/taku910/mecab/master/mecab/COPYING",
    "weaviate_go.mod": "https://raw.githubusercontent.com/weaviate/weaviate/main/go.mod",
    "kiwi_LICENSE": "https://raw.githubusercontent.com/bab2min/Kiwi/main/LICENSE",
    "kiwipiepy_release.json": "https://api.github.com/repos/bab2min/kiwipiepy/releases/latest",
    # PostgreSQL extensions control files / version support
    "pgroonga.control.in": "https://raw.githubusercontent.com/pgroonga/pgroonga/main/pgroonga.control.in",
    "pgroonga_README.md": "https://raw.githubusercontent.com/pgroonga/pgroonga/main/README.md",
    "pg_bigm.control": "https://raw.githubusercontent.com/pgbigm/pg_bigm/master/pg_bigm.control",
    "pgvector_vector.control": "https://raw.githubusercontent.com/pgvector/pgvector/master/vector.control",
    "vchord.control": "https://raw.githubusercontent.com/tensorchord/VectorChord/main/vchord.control",
    "pgvectorscale_vectorscale.control": "https://raw.githubusercontent.com/timescale/pgvectorscale/main/pgvectorscale/vectorscale.control",
    "pg_trgm_doc.html": "https://www.postgresql.org/docs/current/pgtrgm.html",
    "pg_textsearch_dict.html": "https://www.postgresql.org/docs/current/textsearch-dictionaries.html",
    "pgroonga_create_index.html": "https://pgroonga.github.io/reference/create-index-using-pgroonga.html",
    "groonga_tokenizers.html": "https://groonga.org/docs/reference/tokenizers.html",
    "groonga_token_mecab.html": "https://groonga.org/docs/reference/tokenizers/token_mecab.html",
    "groonga_scorers.html": "https://groonga.org/docs/reference/scorer.html",
    "pgroonga_score.html": "https://pgroonga.github.io/reference/functions/pgroonga-score.html",
    "pgroonga_query_expand.html": "https://pgroonga.github.io/reference/functions/pgroonga-query-expand.html",
    "pgroonga_install_debian.html": "https://pgroonga.github.io/install/debian.html",
    "pgroonga_docker_README.md": "https://raw.githubusercontent.com/pgroonga/docker/main/README.md",
    # Qdrant
    "qdrant_indexing_doc.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/manage-data/indexing.md",
    "qdrant_hybrid_doc.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/search/hybrid-queries.md",
    "qdrant_Cargo_segment.toml": "https://raw.githubusercontent.com/qdrant/qdrant/master/lib/segment/Cargo.toml",
    "qdrant_Cargo_root.toml": "https://raw.githubusercontent.com/qdrant/qdrant/master/Cargo.toml",
    "qdrant_Dockerfile": "https://raw.githubusercontent.com/qdrant/qdrant/master/Dockerfile",
    # Weaviate docs
    "weaviate_hybrid_doc.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/search/hybrid.md",
    "weaviate_filters_doc.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/filtering.md",
    # Milvus docs memory
    "milvus_doc_prerequisites.md": "https://raw.githubusercontent.com/milvus-io/milvus-docs/v2.6.x/site/en/getstarted/run_milvus_docker/prerequisite-docker.md",
}
for name in [
    "qdrant-client",
    "weaviate-client",
    "pymilvus",
    "opensearch-py",
    "elasticsearch",
    "meilisearch",
    "meilisearch-python-sdk",
    "lancedb",
    "chromadb",
    "typesense",
    "kiwipiepy",
    "psycopg",
    "pgvector",
    "asyncpg",
    "sqlalchemy",
    "python-mecab-ko",
    "mecab-ko",
    "opensearch-dsl",
]:
    ITEMS[f"pypi_{name}.json"] = f"https://pypi.org/pypi/{name}/json"


def get(item):
    name, url = item
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        (out / name).write_bytes(data)
        return f"OK   {len(data):>8}  {name}  <- {url}"
    except Exception as e:
        return f"FAIL {str(e)[:40]:>8}  {name}  <- {url}"


with concurrent.futures.ThreadPoolExecutor(8) as ex:
    for line in ex.map(get, sorted(ITEMS.items())):
        print(line)
