"""2차 원문 내려받기(1차에서 404였던 것의 대체 경로와 추가 문서).

실행: uv run --no-project python -I .scratch/core/probes/vector-store/fetch_raw2.py <dl-dir>
(표준 라이브러리만 쓴다. 목록은 ITEMS 에 박혀 있다.)

2026-11-09에 돌린 상태 출력이 같은 폴더의 `fetch_raw2.txt`다. 원문(dl/)은 옮기지 않았다(fetch_raw.py
독스트링).
"""

import concurrent.futures
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
ITEMS = {
    "pgroonga.control": "https://raw.githubusercontent.com/pgroonga/pgroonga/main/pgroonga.control",
    "pgroonga_Makefile": "https://raw.githubusercontent.com/pgroonga/pgroonga/main/Makefile",
    "paradedb_tokenizers_overview.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/reference/tokenizers/overview.mdx",
    "paradedb_tokenizers_dir.json": "https://api.github.com/repos/paradedb/paradedb/contents/docs/reference/tokenizers",
    "paradedb_hybrid_overview.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/reference/hybrid/overview.mdx",
    "paradedb_hybrid_dir.json": "https://api.github.com/repos/paradedb/paradedb/contents/docs/reference/hybrid",
    "paradedb_Dockerfile": "https://raw.githubusercontent.com/paradedb/paradedb/main/docker/Dockerfile",
    "pg_tokenizer_docs_dir.json": "https://api.github.com/repos/tensorchord/pg_tokenizer.rs/contents/docs",
    "pg_tokenizer_model.md": "https://raw.githubusercontent.com/tensorchord/pg_tokenizer.rs/main/docs/06-model.md",
    "lance_tokenizer_Cargo.toml": "https://raw.githubusercontent.com/lancedb/lance/main/rust/lance-tokenizer/Cargo.toml",
    "lancedb_py_tree.json": "https://api.github.com/repos/lancedb/lancedb/contents/python/python/lancedb",
    "chroma_py_tree.json": "https://api.github.com/repos/chroma-core/chroma/contents/chromadb",
    "opensearch_plugins_doc.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_install-and-configure/plugins.md",
    "opensearch_analyzers_index.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_analyzers/language-analyzers/index.md",
    "opensearch_nori_plugin_src.json": "https://api.github.com/repos/opensearch-project/OpenSearch/contents/plugins/analysis-nori",
    "opensearch_nori_build.gradle": "https://raw.githubusercontent.com/opensearch-project/OpenSearch/main/plugins/analysis-nori/build.gradle",
    "opensearch_nori_LICENSE": "https://raw.githubusercontent.com/opensearch-project/OpenSearch/main/plugins/analysis-nori/licenses/lucene-LICENSE.txt",
    "lucene_nori_NOTICE": "https://raw.githubusercontent.com/apache/lucene/main/lucene/NOTICE.txt",
    "lucene_root_NOTICE": "https://raw.githubusercontent.com/apache/lucene/main/NOTICE.txt",
    "lucene_nori_dict_README": "https://raw.githubusercontent.com/apache/lucene/main/lucene/analysis/nori/README.md",
    "debian_mecab_ko_dic.html": "https://packages.debian.org/trixie/mecab-ko-dic",
    "debian_groonga_tokenizer_mecab.html": "https://packages.debian.org/trixie/groonga-tokenizer-mecab",
    "debian_mecab.html": "https://packages.debian.org/trixie/mecab",
    "pg_createextension.html": "https://www.postgresql.org/docs/current/sql-createextension.html",
    "pg_extend_extensions.html": "https://www.postgresql.org/docs/current/extend-extensions.html",
    "typesense_tokenizer.cpp": "https://raw.githubusercontent.com/typesense/typesense/v29.0/src/tokenizer.cpp",
    "typesense_tokenizer.h": "https://raw.githubusercontent.com/typesense/typesense/v29.0/include/tokenizer.h",
    "kagome_dict_ko_go.mod": "https://raw.githubusercontent.com/ikawaha/kagome-dict-ko/master/go.mod",
    "kagome_dict_ko_LICENSE_master": "https://raw.githubusercontent.com/ikawaha/kagome-dict-ko/master/LICENSE",
    "kagome_dict_ko_README_master": "https://raw.githubusercontent.com/ikawaha/kagome-dict-ko/master/README.md",
    "lindera_ko_dic_LICENSE_master": "https://raw.githubusercontent.com/lindera/lindera-ko-dic/master/LICENSE",
    "lindera_ko_dic_README_master": "https://raw.githubusercontent.com/lindera/lindera-ko-dic/master/README.md",
    "lindera_repo_tree.json": "https://api.github.com/repos/lindera/lindera/contents/",
    "vchord_images_README.md": "https://raw.githubusercontent.com/tensorchord/VectorChord-images/main/README.md",
    "weaviate_kagome_doc.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/config-refs/collections.mdx",
    "weaviate_env_doc.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/deploy/configuration/env-vars/index.md",
    "weaviate_resources_doc.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/resources.md",
    "qdrant_capacity_doc.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/guides/capacity-planning.md",
    "qdrant_fulltext_doc.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/search/text-search/full-text-search.md",
    "qdrant_filtering_doc.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/concepts/filtering.md",
    "milvus_prereq_doc.md": "https://raw.githubusercontent.com/milvus-io/milvus-docs/v2.6.x/site/en/getstarted/run_milvus_docker/prerequisite-docker.md",
    "milvus_prereq_doc_v3.md": "https://raw.githubusercontent.com/milvus-io/milvus-docs/v3.0.x/site/en/getstarted/run_milvus_docker/prerequisite-docker.md",
    "meilisearch_vector_doc.mdx": "https://raw.githubusercontent.com/meilisearch/documentation/main/learn/ai_powered_search/getting_started_with_ai_search.mdx",
    "meilisearch_embedders_ref.mdx": "https://raw.githubusercontent.com/meilisearch/documentation/main/reference/api/settings.mdx",
    "meilisearch_LICENSE_EE": "https://raw.githubusercontent.com/meilisearch/meilisearch/main/LICENSE-EE",
    "meilisearch_LICENSE_MIT": "https://raw.githubusercontent.com/meilisearch/meilisearch/main/LICENSE-MIT",
    "vespa_lucene_linguistics.html": "https://docs.vespa.ai/en/lucene-linguistics.html",
    "elastic_nori_doc.html": "https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori",
    "groonga_news.html": "https://groonga.org/docs/news.html",
}
for name in [
    "qdrant-client",
    "weaviate-client",
    "pymilvus",
    "opensearch-py",
    "meilisearch",
    "meilisearch-python-sdk",
    "typesense",
    "elasticsearch",
    "kiwipiepy",
]:
    ITEMS[f"pypi_{name}.json"] = f"https://pypi.org/pypi/{name}/json"


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
