"""3차 원문 내려받기(ParadeDB 토크나이저·하이브리드 문서, PGroonga 크래시/백업 문서, 사전 출처,
기타).

실행: uv run --no-project python -I .scratch/core/probes/vector-store/fetch_raw3.py <dl-dir>
(표준 라이브러리만 쓴다. 목록은 ITEMS 에 박혀 있다.)

2026-11-09에 돌린 상태 출력이 같은 폴더의 `fetch_raw3.txt`다. 원문(dl/)은 옮기지 않았다(fetch_raw.py
독스트링).
"""

import concurrent.futures
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
ITEMS = {
    "paradedb_root_dir.json": "https://api.github.com/repos/paradedb/paradedb/contents/",
    "paradedb_avail_tok_dir.json": "https://api.github.com/repos/paradedb/paradedb/contents/docs/reference/tokenizers/available-tokenizers",
    "paradedb_docker_dir.json": "https://api.github.com/repos/paradedb/paradedb/contents/docker",
    "paradedb_hybrid_rrf.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/reference/hybrid/rrf.mdx",
    "paradedb_tokenizers_Cargo.toml": "https://raw.githubusercontent.com/paradedb/paradedb/main/tokenizers/Cargo.toml",
    "paradedb_tok_lindera.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/reference/tokenizers/available-tokenizers/lindera.mdx",
    "paradedb_tok_icu.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/reference/tokenizers/available-tokenizers/icu.mdx",
    "paradedb_tok_korean.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/reference/tokenizers/available-tokenizers/korean.mdx",
    "paradedb_tok_jieba.mdx": "https://raw.githubusercontent.com/paradedb/paradedb/main/docs/reference/tokenizers/available-tokenizers/jieba.mdx",
    "pgroonga_overview.html": "https://pgroonga.github.io/overview/",
    "pgroonga_enable_wal.html": "https://pgroonga.github.io/reference/parameters/enable-wal.html",
    "pgroonga_crash_safe.html": "https://pgroonga.github.io/reference/crash-safe.html",
    "pgroonga_howto_dir.html": "https://pgroonga.github.io/how-to/",
    "pgroonga_reference_index.html": "https://pgroonga.github.io/reference/",
    "pgroonga_releases.json": "https://api.github.com/repos/pgroonga/pgroonga/releases/latest",
    "pgroonga_news.html": "https://pgroonga.github.io/news/",
    "lindera_ko_dic_README.md": "https://raw.githubusercontent.com/lindera/lindera/main/lindera-ko-dic/README.md",
    "lindera_ko_dic_Cargo.toml": "https://raw.githubusercontent.com/lindera/lindera/main/lindera-ko-dic/Cargo.toml",
    "lindera_ko_dic_build.rs": "https://raw.githubusercontent.com/lindera/lindera/main/lindera-ko-dic/build.rs",
    "mecab_ko_dic_README_api": "https://api.bitbucket.org/2.0/repositories/eunjeon/mecab-ko-dic/src/master/README",
    "mecab_ko_dic_README_md_api": "https://api.bitbucket.org/2.0/repositories/eunjeon/mecab-ko-dic/src/master/README.md",
    "mecab_ko_dic_src_list.json": "https://api.bitbucket.org/2.0/repositories/eunjeon/mecab-ko-dic/src/master/",
    "lance_root_Cargo.toml": "https://raw.githubusercontent.com/lancedb/lance/main/Cargo.toml",
    "meilisearch_v1.13.0_release.json": "https://api.github.com/repos/meilisearch/meilisearch/releases/tags/v1.13.0",
    "pypi_kiwipiepy_model.json": "https://pypi.org/pypi/kiwipiepy_model/json",
    "pypi_mecab-ko-dic.json": "https://pypi.org/pypi/mecab-ko-dic/json",
    "opensearch_knn_memory.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_vector-search/performance-tuning-indexing.md",
    "opensearch_knn_memory2.md": "https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_vector-search/performance-tuning.md",
    "qdrant_capacity.md": "https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/capacity-planning.md",
    "weaviate_hybrid_concept.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/weaviate/concepts/search/hybrid-search.md",
    "weaviate_backups_doc.md": "https://raw.githubusercontent.com/weaviate/docs/main/docs/deploy/configuration/backups.md",
    "weaviate_LICENSE_root": "https://raw.githubusercontent.com/weaviate/weaviate/main/LICENSE",
    "weaviate_LICENSE_BSD": "https://raw.githubusercontent.com/weaviate/weaviate/main/LICENSE-BSD",
    "opensearch_py_README.md": "https://raw.githubusercontent.com/opensearch-project/opensearch-py/main/README.md",
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
