# 벡터 저장소와 한국어 키워드 검색 비교 (core 설계 인터뷰 조사)

조사일 2026-11-09. 결정은 설계 인터뷰(사용자)가 내리고, 이 문서는 사실과 근거를 모은다. 설치형(폐쇄망 VM, 단독 compose), PDF·DOCX·HWPX 한국어 문서, 메타데이터는 이 서버의 PostgreSQL(ADR 0002), 임베딩은 별도 컨테이너가 HTTP로 주고 지식베이스마다 차원이 다를 수 있다는 전제에서 봤다.

## 근거 표기

칸마다 괄호로 근거 종류를 적는다(`docs/agents/issue-tracker.md` 프로브와 근거 절).

- **읽음**: 코드·문서 원문을 내려받아 읽었다. 뒤에 파일 이름이나 주소와 판을 적는다. 지난 조사(다른 서브에이전트)가 내려받은 원문도 읽음으로 적고 `S1/`을 붙인다.
- **스크립트**: 스크립트가 낸 값. 뒤에 스크립트 이름을 적는다.
- **웹 요약**: WebFetch가 요약한 것. 원문과 대 보지 않았으므로 수치와 인용은 근거가 아니다. 주소를 적는다.
- **어림**: 재지 않은 수와 해석.

스크립트와 그 출력(`.txt`)은 `.scratch/core/probes/vector-store/`에 커밋했다(2026-11-09에 세션 스크래치패드에서 옮겼다. 프로브 표는 `.scratch/core/probes/README.md`). 원문(`dl/`·`dl2/`)은 저장소 밖 세션 스크래치패드에 있고 세션이 끝나면 사라진다. 다시 받으려면 그 폴더의 `fetch_raw*.py`·`fetch_list.py`를 돌린다.

- `S2/` = `C:\Users\User\AppData\Local\Temp\claude\C--project-rag-engine\56918e8d-294f-44a4-967b-4a576e6fb835\scratchpad\vector-store-2\` (`dl/` 원문, `dl2/` N·O·P 절 원문(관리형 PostgreSQL 확장 표, Weaviate·Qdrant·Milvus·Meilisearch·ParadeDB 문서, 가격 페이지, 라이선스·블로그, GitHub·Docker Hub·pypistats JSON), `wheel/` 휠. `probe/`에 있던 스크립트와 출력은 위 폴더로 옮겼다)
- `S1/` = 같은 상위의 `vector-store\` (지난 조사. `dl/`. `probe/hub_sizes.py`는 위 폴더로 옮겼다)

스크립트: `.scratch/core/probes/vector-store/hub_tags.py`(Docker Hub v2 API로 태그별 amd64 압축 크기, 출력 `hub_tags.txt`), `.scratch/core/probes/vector-store/elastic_size.py`(docker.elastic.co 레지스트리 매니페스트 레이어 합), `.scratch/core/probes/vector-store/wheel_pytyped.py`(PyPI 휠을 받아 `py.typed` 유무, 출력 `wheel_pytyped.txt`), `.scratch/core/probes/vector-store/summarize_dl.py`(LICENSE 머리줄, control 파일, GitHub 최신 릴리스, PyPI 메타데이터, 출력 `summarize_dl.txt`), `.scratch/core/probes/vector-store/fetch_raw.py`·`fetch_raw2.py`·`fetch_raw3.py`·`fetch_raw4.py`(원문 내려받기), `.scratch/core/probes/vector-store/html_text.py`(HTML 태그 벗겨 키워드 주변 읽기), `.scratch/core/probes/vector-store/hub_sizes.py`(지난 조사의 이미지 크기). N·O·P 절(2026-11-09): `.scratch/core/probes/vector-store/github_stats.py`(gh api로 별·포크·이슈·기여자·90일 커밋·릴리스·LICENSE 커밋 이력, 출력 `github_stats.txt`), `.scratch/core/probes/vector-store/pulls_and_pypistats.py`(Docker Hub `pull_count`, pypistats `recent`, 출력 `pulls_and_pypistats.txt`), `.scratch/core/probes/vector-store/fetch_raw5.py`·`fetch_list.py`(+`items6.txt`~`items9.txt`; `dl2/` 원문 내려받기), `.scratch/core/probes/vector-store/pdf_text.py`(pypdf로 PDF 텍스트).

이미지 크기는 모두 Docker Hub v2 API `repositories/<repo>/tags`의 amd64 `size`(압축 크기, MB = 바이트/1e6)다. 이미지를 내려받거나 컨테이너를 띄우지 않았다.

## 0. 전제가 되는 설계 사실

- 메타데이터·작업 기록은 이 서버의 PostgreSQL에 두고 연결 문자열 하나만 받는다. 설치 환경의 기존 PostgreSQL에 붙일 수 있어 "그쪽에 확장이 있어야 하는 비용"이 선택 기준이다(ADR 0002 읽음). 비교 뒤 ADR 0002 이력 2026-11-09가 이 장면을 지원 범위에서 뺐고, 이 축은 비교 당시의 기준으로 남긴다.
- PostgreSQL 확장은 control 파일에 `trusted = true`가 없으면 `CREATE EXTENSION`에 superuser가 필요하다("For many extensions this means superuser privileges are needed. However, if the extension is marked trusted in its control file, then it can be installed by any user who has CREATE privilege on the current database" — 읽음 `S2/dl/pg_createextension.html`, PostgreSQL 18 문서). pgvector `vector.control`, PGroonga `pgroonga.control`, pg_bigm `pg_bigm.control`에는 `trusted` 줄이 없다(읽음 `S2/dl/*.control`). `pg_search.control`은 `superuser = false`, `requires = 'vector'`(읽음). `vchord.control`과 `vectorscale.control`은 `superuser = true`, `requires = 'vector'`(읽음). pg_trgm만 "trusted"(읽음 `S2/dl/pg_trgm_doc.html`).
- 지식베이스마다 벡터 차원이 다를 수 있다. pgvector는 차원 없는 `vector` 컬럼을 허용하되 색인은 같은 차원끼리만 만들 수 있어 표현식·부분 색인을 쓴다("you can only create indexes on rows with the same number of dimensions (using expression and partial indexing)" — 읽음 `S1/dl/pgvector_README.md` 0.8.7, FAQ). `vector` 2,000차원, `halfvec` 4,000차원 상한(읽음, 같은 파일).
- pgvector의 근사 색인은 필터를 색인 스캔 **뒤**에 건다("With approximate indexes, filtering is applied after the index is scanned. If a condition matches 10% of rows, with HNSW and the default hnsw.ef_search of 40, only 4 rows will match on average" — 읽음, 같은 파일). 0.8.0부터 `hnsw.iterative_scan = strict_order | relaxed_order`, `hnsw.max_scan_tuples`(기본 20000), `hnsw.scan_mem_multiplier`(읽음). "If filtering by only a few distinct values, consider partial indexing"(읽음).

## 1단계: 넓은 후보 표

기준 셋(라이선스, 한국어 키워드 검색, 배포 무게)으로 거른다. 라이선스는 LICENSE 원문으로 확인했다. 무게는 압축 이미지 크기와 컨테이너 수다.

| # | 후보 | 라이선스 | 한국어 키워드 검색 | 배포 무게 | 판정 |
|---|---|---|---|---|---|
| 1 | PostgreSQL + pgvector + 기본 전문 검색(tsvector) | pgvector: PostgreSQL License(읽음 `S1/dl/pgvector_LICENSE`) | 기본 파서에 한국어 형태소 분석기 없음(읽음 `S1/dl/pg_textsearch_parsers.html`; 지난 조사). 비ASCII 글은 공백 단위 `word` 토큰이라 조사가 붙은 채 색인된다 | 컨테이너 1, `pgvector/pgvector:0.8.7-pg18-trixie` 164.1MB(스크립트 `.scratch/core/probes/vector-store/hub_sizes.py`) | 그대로는 **탈락**(한국어). 토큰화를 앱(kiwipiepy 등)에서 하고 `to_tsvector('simple', …)`에 넣는 변형(1′)은 확장이 pgvector뿐이라 **결선 C** |
| 2 | PostgreSQL + pgvector + PGroonga | PGroonga: PostgreSQL License(읽음 `S1/dl/pgroonga_COPYING`); Groonga 본체 LGPL-2.1(읽음 `S1/dl/groonga_license_COPYING`) | TokenBigram 기본(비ASCII 2글자, 사전 없음). TokenMecab은 "MeCab doesn't depend on Japanese. You can use MeCab for other languages by creating dictionary"(읽음 `S2/dl/groonga_token_mecab.html` Groonga 16.1.5). 한국어 사전(mecab-ko-dic)은 Debian 패키지가 없고(읽음 `S2/dl/debian_mecab_ko_dic.html`: 패키지 없음 응답) `groonga-tokenizer-mecab`은 일본어 사전(naist-jdic 또는 jumandic)에 의존한다(읽음 `S2/dl/debian_groonga_tokenizer_mecab.html`). 한국어 TokenMecab은 사전을 소스에서 빌드해야 하며, mecab-ko-dic README는 포크 mecab-ko 설치를 전제한다(읽음 `S2/dl/mecab_ko_dic_README_md_api`) → 실측 대상 | 컨테이너 1. 공식 결합 이미지 없음. `groonga/pgroonga:4.1.0-debian-18` 260.9MB(pgvector 없음, `groonga-tokenizer-mecab` 포함: 읽음 `S1/dl/pgroonga_docker_debian18_Dockerfile` 20행), 비공식 `cubeplex/postgresql-pgroonga-pgvector` 196.2MB(mecab 없음)(스크립트 `.scratch/core/probes/vector-store/hub_sizes.py`) | **결선 A** |
| 3 | PostgreSQL + pgvector + pg_bigm | PostgreSQL License(읽음 `S1/dl/pg_bigm_COPYRIGHT`) | 2-gram. 점수 함수가 없고 유사도(`bigm_similarity`)와 LIKE 가속뿐. PGroonga 쪽 설명으로는 Recheck가 필요해 적중이 많으면 느리다(읽음 `S2/dl/pgroonga_overview.html`, 경쟁자의 주장임) | 컨테이너 1이지만 PGDG 패키지 없음(지난 조사), 공식 이미지 없음 → 소스 빌드. PostgreSQL 9.1~19 지원(읽음 `S1/dl/pg_bigm_en_REL1_2.md`) | **탈락**. 같은 라이선스·같은 1컨테이너인 PGroonga가 패키지(apt/yum 저장소), 이미지, 점수, 동의어 확장에서 모두 앞선다 |
| 4 | PostgreSQL + pgvector + ParadeDB pg_search | **AGPL-3.0**(읽음 `S2/dl/paradedb_LICENSE`; README "ParadeDB Community is licensed under the GNU Affero General Public License v3.0", Enterprise는 상용 — 읽음 `S2/dl/paradedb_README.md`) | `pdb.lindera(korean)` — "Korean Lindera uses the KoDic dictionary"(읽음 `S2/dl/paradedb_tok_lindera.mdx`). 사전은 표준 빌드에 내장: `tokenizers/Cargo.toml`에 `lindera = { features = ["embed-cc-cedict", "embed-ipadic", "embed-ko-dic", …] }`(읽음 `S2/dl/paradedb_tokenizers_Cargo.toml`). ICU, ngrams, edge-ngrams, whitespace 등도 있음(읽음 `S2/dl/paradedb_avail_tok_dir.json`). BM25 점수 내장 | 컨테이너 1. `paradedb/paradedb:0.26.6-pg18` 374.4MB(스크립트 `.scratch/core/probes/vector-store/hub_tags.py`). `postgres:18-trixie` 기반에 pg_search deb + PGDG `postgresql-18-pgvector=0.8.6` + PostGIS + pg_cron(읽음 `S2/dl/paradedb_Dockerfile.paradedb-18`). `shared_preload_libraries = 'pg_search,…'` 필요(읽음, 같은 파일 60행) | **결선 B**. 라이선스(AGPL)는 사용자 판단 |
| 5 | PostgreSQL + VectorChord 또는 pgvectorscale | VectorChord: **AGPL-3.0 또는 ELv2 이중**(읽음 `S2/dl/vchord_LICENSE`). pgvectorscale: PostgreSQL License(읽음 `S2/dl/pgvectorscale_LICENSE`) | 한국어와 무관(벡터 색인). VectorChord-bm25 + pg_tokenizer.rs(Apache-2.0, 읽음 `S2/dl/pg_tokenizer_LICENSE`)가 BM25를 주지만, lindera ko-dic은 "compile the extension from source and enable … lindera-ko-dic features"(읽음 `S2/dl/pg_tokenizer_model.md`) | VectorChord `tensorchord/vchord-postgres:pg18-v1.1.1` 161.4MB, 올인원 `vchord-suite:pg18-latest` 176.8MB(스크립트 `.scratch/core/probes/vector-store/hub_tags.py`). pgvectorscale은 `timescale/timescaledb-ha:pg18-all-oss-amd64` 1567.3MB(스크립트) 또는 소스 빌드. 둘 다 `superuser = true`(읽음 control) | **보류(탈락)**. 둘 다 pgvector의 `vector` 타입 위에 얹는 색인이라 pgvector로 시작한 뒤 바꿔 끼울 수 있다. 지금 결정에 넣지 않는다 |
| 6 | Qdrant 1.20 | Apache-2.0(읽음 `S1/dl/qdrant_LICENSE`) | 공식 빌드의 charabia 피처는 `greek, hebrew, thai, chinese-segmentation, chinese-normalization`뿐 — `korean` 없음(읽음 `S2/dl/qdrant_Cargo_segment.toml` = `lib/segment/Cargo.toml` master 2026-11; v1.20.0 태그도 같은 다섯 피처다: 스크립트 `.scratch/core/probes/facts/qdrant_facts.py`, 출력 `qdrant_facts_out.txt`). multilingual 토크나이저 문서도 한국어를 들지 않음(읽음 `S2/dl/qdrant_indexing_doc.md`). 한글은 charabia의 기본 분절(유니코드 단어 경계)로 떨어져 조사가 붙은 어절 단위가 될 것(어림). BM25 서버측 점수는 1.20부터, RRF·DBSF 내장(읽음 `S2/dl/qdrant_indexing_doc.md`, `qdrant_hybrid_doc.md`) | `qdrant/qdrant:v1.20.0` 72.6MB(스크립트 `.scratch/core/probes/vector-store/hub_sizes.py`), 컨테이너 1(+PostgreSQL) | **탈락**(한국어 형태소 없음. 공식 이미지로는 유니코드 단어 경계 수준) |
| 7 | Weaviate 1.40.4 | BSD-3-Clause, `wl` 디렉터리만 Weaviate License(읽음 `S2/dl/weaviate_LICENSE_root`) | `kagome_kr`: "uses the Kagome tokenizer with a Korean MeCab (mecab-ko-dic) dictionary"(읽음 `S2/dl/weaviate_kagome_doc.md`). "not loaded by default … set the environment variable ENABLE_TOKENIZER_KAGOME_KR to true"(읽음, 같은 파일). go.mod에 `github.com/ikawaha/kagome-dict-ko v0.2.1`(읽음 `S2/dl/weaviate_go.mod`). BM25F + 벡터 하이브리드 내장 | `semitechnologies/weaviate:1.40.4` 89.3MB(스크립트 `.scratch/core/probes/vector-store/hub_sizes.py`), 컨테이너 1(+PostgreSQL) | **결선 D**(별도 엔진 대표) |
| 8 | Milvus 3.0.5 | Apache-2.0(읽음 `S1/dl/milvus_LICENSE`) | lindera ko-dic 내장(2.6+ "include all dictionaries pre-compiled" — 읽음 `S1/dl/milvusdoc_lindera-tokenizer.md`), BM25 sparse, 하이브리드 | `milvusdb/milvus:v3.0.5` 528.5MB + compose면 etcd 64.9MB + MinIO 62.6MB(스크립트 `.scratch/core/probes/vector-store/hub_sizes.py`). 단일 컨테이너 스크립트 모드(etcd 내장, 로컬 FS)도 있으나 최소 RAM "Standalone: 8G", 권장 16G(웹 요약 https://milvus.io/docs/prerequisite-docker.md) | **탈락**(무게·메모리) |
| 9 | OpenSearch 3.9.0 | Apache-2.0(읽음 `S2/dl/opensearch_LICENSE.txt`) | `analysis-nori`는 "additional plugin"이라 이미지에 없고 `bin/opensearch-plugin install analysis-nori`로 넣는다(읽음 `S2/dl/opensearch_doc_additional_plugins.md`). 오프라인은 zip을 `file:` 경로로 설치(읽음 `S2/dl/opensearch_plugins_doc.md`). 플러그인 Apache-2.0(읽음 `S2/dl/opensearch_nori_build.gradle`), Lucene nori의 사전은 `mecab-ko-dic-2.1.1-20180720`(읽음 `S2/dl/lucene_root_NOTICE`). 하이브리드(`hybrid` 질의, RRF·min_max·z_score, fusion mode는 파이프라인 없이) 내장(읽음 `S2/dl/opensearch_doc_hybrid.md`) | `opensearchproject/opensearch:3.9.0` 1159.5MB(스크립트 `.scratch/core/probes/vector-store/hub_tags.py`). JVM 힙 기본 `-Xms1g -Xmx1g`, 호스트 `vm.max_map_count=262144` 필요, Docker Desktop은 4GB 이상(읽음 `S2/dl/opensearch_doc_install_index.md`, `opensearch_doc_docker.md`) | 단독 엔진으론 **탈락**(무게). 둘로 가르는 안의 키워드 엔진으로 **결선 E** |
| 10 | Elasticsearch 9.5.6 | AGPL-3.0 only / SSPL-1 / ELv2 **삼중**, x-pack은 ELv2만(읽음 `S2/dl/elasticsearch_LICENSE.txt`) | nori(같은 Lucene 모듈, "uses the mecab-ko-dic dictionary" — 읽음 `S2/dl/elastic_nori_doc.html`). 오프라인 플러그인 설치 가능(읽음) | `docker.elastic.co/elasticsearch/elasticsearch:9.5.6` 916.8MB(스크립트 `.scratch/core/probes/vector-store/elastic_size.py`) | **탈락**. 같은 nori·같은 무게급의 OpenSearch가 Apache-2.0이다 |
| 11 | Meilisearch v1.56.1 | MIT, 단 `enterprise_editions` 폴더의 EE 파일은 BUSL-1.1(읽음 `S2/dl/meilisearch_LICENSE`, `meilisearch_LICENSE_EE`) | charabia `korean = ["lindera/lindera-ko-dic", "lindera/embed-ko-dic"]`이 charabia 기본 피처에 들고(읽음 `S2/dl/charabia_Cargo.toml`), meilisearch 크레이트 기본 피처가 `meilisearch-types/all-tokenizations` → `charabia/default`(읽음 `S2/dl/meilisearch_crate_Cargo.toml`, `meilisearch_types_Cargo.toml`, `meilisearch_milli_Cargo.toml`) → 공식 빌드에 한국어 형태소 내장. 벡터·하이브리드는 v1.13(2025-02-17)에서 안정화("vectorStore is no longer an accepted value for the /experimental-features route" — 읽음 `S2/dl/meilisearch_v1.13.0_release.json`). `userProvided` 임베더는 `dimensions` 필수(웹 요약 https://www.meilisearch.com/docs/reference/api/settings) | `getmeili/meilisearch:v1.56.1` 106.1MB(스크립트 `.scratch/core/probes/vector-store/hub_tags.py`), 단일 바이너리, 호스트 설정 없음 | 둘로 가르는 안의 **가벼운 키워드 엔진 대안**으로 결선 E에 병기. 벡터 저장소로서의 대규모 공개 수치가 없어 벡터 겸용 결선엔 넣지 않았다 |
| 12 | Vespa 8.781.11 | Apache-2.0(읽음 `S2/dl/vespa_LICENSE`) | Lucene linguistics 언어 목록에 Korean 포함(읽음 `S2/dl/vespa_lucene_linguistics.html`) | `vespaengine/vespa:8.781.11` 810.2MB(스크립트). "a single-node Vespa application requires a minimum of 4 GB for the Docker container"(웹 요약 https://docs.vespa.ai/en/operations-selfhosted/docker-containers.html) | **탈락**(무게) |
| 13 | LanceDB 0.41.0 / Chroma 1.5.9 | 둘 다 Apache-2.0(읽음 `S2/dl/lancedb_LICENSE`, `chroma_LICENSE`) | LanceDB: 파이썬 빌드에 `tokenizer-lindera` 피처 포함(읽음 `S2/dl/lance_python_Cargo.toml`)이나 `lindera/ko-dic`은 모델 파일을 `LANCE_LANGUAGE_MODEL_HOME`에 따로 설치해야 한다(웹 요약 https://docs.lancedb.com/search/full-text-search). Chroma: `$contains`/`$regex` 부분 문자열 필터이고 BM25 랭킹이 아니다(웹 요약 https://docs.trychroma.com/docs/querying-collections/full-text-search) | LanceDB는 임베디드(서버 없음), 휠 69~86MB, pydantic·pyarrow 의존, `py.typed` 없음(읽음 PyPI JSON·저장소 트리 `S2/dl/lancedb_py_tree.json`). Chroma 이미지 185.5MB(스크립트), 휠 21.7~23.3MB에 onnxruntime·kubernetes·opentelemetry 의존(읽음 `S2/dl/pypi_chromadb.json`) | **탈락**(한국어 랭킹 검색 부재 또는 사전 수동 설치, 두 저장소, 무거운 클라이언트) |
| 14 | Typesense 30.2 | **GPL-3.0**(읽음 `S2/dl/typesense_LICENSE.txt` v29.0) | `locale == "ko"`면 NFKD 정규화 + ICU `BreakIterator::createWordInstance` 단어 경계(읽음 `S2/dl/typesense_tokenizer.cpp` v29.0 22·85~87·129행) → 사전 기반 형태소 아님. 하이브리드 rank fusion 있음(웹 요약 https://typesense.org/docs/latest/api/vector-search.html) | `typesense/typesense:31.0.rc25` 384.2MB(스크립트) | **탈락**(GPL-3.0, 형태소 없음) |
| 15 | 둘로 가르기: 벡터는 pgvector, 키워드는 별도 엔진(OpenSearch 또는 Meilisearch), RRF는 우리가 | 위 9·11 | 위 9·11 | 컨테이너 2(PostgreSQL+pgvector 164MB, OpenSearch 1159MB 또는 Meilisearch 106MB) | **결선 E** |

결선: **A** pgvector+PGroonga, **B** pgvector+pg_search, **C** pgvector+tsvector(앱 측 한국어 형태소), **D** Weaviate(벡터+BM25 한 엔진, 메타데이터는 PostgreSQL), **E** pgvector+OpenSearch(nori) 또는 Meilisearch.

## 2단계: 결선 비교

### A. 라이선스(서버, 클라이언트, 토크나이저와 사전)

| 결선 | 값(근거) |
|---|---|
| A pgvector+PGroonga | pgvector PostgreSQL License(읽음). PGroonga PostgreSQL License(읽음). Groonga LGPL-2.1(읽음). TokenMecab을 쓰면 MeCab은 GPL/LGPL/BSD 중 택일("released under any of the GPL, the LGPL, or the BSD License" — 읽음 `S2/dl/mecab_COPYING`), mecab-ko-dic Apache-2.0(읽음 `S2/dl/mecab_ko_dic_COPYING`; README "아파치 라이센스 2.0" — 읽음). 클라이언트: psycopg 3.3.8 LGPL-3.0-only(읽음 PyPI), pgvector 0.5.1 MIT(읽음 PyPI) |
| B pgvector+pg_search | pg_search **AGPL-3.0**(읽음). lindera MIT(읽음 `S2/dl/lindera_LICENSE`), lindera-ko-dic은 `mecab-ko-dic-2.1.1-20180720.tar.gz`를 받아 빌드(읽음 `S2/dl/lindera_ko_dic_build.rs`) → 사전 Apache-2.0. 클라이언트: A와 같음(SQL만) |
| C pgvector+tsvector+kiwipiepy | pgvector PostgreSQL License. Kiwi Apache-2.0(읽음 `S2/dl/kiwi_LICENSE`), kiwipiepy 0.24.1 `license_expression = Apache-2.0`(읽음 PyPI), 모델 kiwipiepy_model 0.24.0 Apache-2.0(읽음 `S2/dl/pypi_kiwipiepy_model.json`). 대안 mecab-ko 1.0.3 BSD + mecab-ko-dic 1.0.0(읽음 PyPI) |
| D Weaviate | 서버 BSD-3(`wl` 제외)(읽음). kagome MIT(읽음 `S2/dl/kagome_LICENSE`), kagome-dict-ko 코드 MIT(읽음 `S2/dl/kagome_dict_ko_LICENSE_master`) + 데이터 mecab-ko-dic-2.1.1-20180720(읽음 `S2/dl/kagome_dict_ko_README_master`) Apache-2.0. weaviate-client 4.24.1 BSD 3-clause(읽음 PyPI) |
| E pgvector+OpenSearch(/Meilisearch) | OpenSearch Apache-2.0, analysis-nori Apache-2.0, 사전 mecab-ko-dic 2.1.1 Apache-2.0(읽음). opensearch-py 3.2.0 Apache-2.0(읽음 PyPI). Meilisearch MIT(+EE BUSL-1.1), charabia MIT(읽음 `S2/dl/charabia_LICENSE`), meilisearch 0.43.0 MIT, meilisearch-python-sdk 8.1.5 MIT(읽음 PyPI) |

### B. 배포

| 결선 | 값(근거) |
|---|---|
| A | 컨테이너 1. 공식 결합 이미지 없음 → 셋 중 하나: (i) `groonga/pgroonga:4.1.0-debian-18`(260.9MB, `postgres:18-trixie` 기반 — 읽음 Dockerfile)에 PGDG `postgresql-18-pgvector` apt 추가, (ii) `pgvector/pgvector:0.8.7-pg18-trixie`(164.1MB)에 Groonga apt 저장소로 `postgresql-18-pgdg-pgroonga` 추가(설치 절차 읽음 `S2/dl/pgroonga_install_debian.html`), (iii) 비공식 cubeplex 196.2MB. 폐쇄망 반입 이미지 1개. 메모리 권장 최소치 문서 없음(HNSW 빌드는 `maintenance_work_mem`에 그래프가 들어가야 빠름 — 읽음 README). 기존 PostgreSQL: PGroonga는 PostgreSQL 12~18(읽음 `S1/dl/pgroonga_install_index.html`), pgvector 13+(읽음 README), 둘 다 superuser로 `CREATE EXTENSION`(control에 trusted 없음 — 읽음). PGroonga 패키지는 Groonga 저장소(Debian·Ubuntu·AlmaLinux, 읽음), PGDG 아님. 한국어 TokenMecab은 사전 소스 빌드(1단계 2번) |
| B | 컨테이너 1. `paradedb/paradedb:0.26.6-pg18` 374.4MB(pgvector 0.8.6 포함). pg_search+pgvector만 든 "official" 이미지는 Docker 공식 이미지 승인 대기(읽음 `S2/dl/paradedb_docker_README.md`). 기존 PostgreSQL: "Ensure that you have superuser access", "As of 0.25.0, pg_search relies on pgvector's vector type, making it a required extension", deb(Debian 12/13, Ubuntu)·rpm(EL 9/10) amd64·arm64, `shared_preload_libraries`에 추가(읽음 `S2/dl/paradedb_install_extension.mdx`) → **서버 재시작**이 필요하다. PostgreSQL 15~18(읽음 `S2/dl/paradedb_Cargo.toml` features) |
| C | 컨테이너 1. `pgvector/pgvector:0.8.7-pg18-trixie` 164.1MB 그대로. 기존 PostgreSQL: pgvector만(13+, superuser). 대신 서버(앱) 이미지에 kiwipiepy 휠 3.7~5.9MB + 모델 87.9MB(tar.gz)가 더해진다(읽음 PyPI) |
| D | 컨테이너 2(PostgreSQL 164MB급 + Weaviate 89.3MB). 환경변수 `ENABLE_TOKENIZER_KAGOME_KR=true`(읽음). 메모리: "The HNSW index must be stored in memory", "Smaller projects, less than 1M objects, do not require resource planning"(읽음 `S2/dl/weaviate_resources_doc.md`). 기존 PostgreSQL에 **확장이 필요 없다**(pgvector 불필요). 포트 둘(HTTP, gRPC)(어림) |
| E | 컨테이너 2. OpenSearch 1159.5MB에 nori 플러그인은 **없어서** zip을 함께 반입해 시작 때 설치하거나 자체 이미지를 만든다(읽음). JVM 힙 기본 1GB, 호스트 `vm.max_map_count=262144`(폐쇄망 VM에서 sysctl 권한 필요), Docker Desktop 4GB(읽음). Meilisearch 대안: 106.1MB, 단일 바이너리, 호스트 설정 없음, 한국어 내장(읽음) |

### C. 한국어 키워드 검색

| 결선 | 값(근거) |
|---|---|
| A | 분석: TokenBigram(2-gram, 사전 없음, 재현율 쪽. Groonga 문서의 예: 京都 질의가 東京都에도 맞음 — 읽음 `S2/dl/groonga_token_mecab.html`) 또는 TokenMecab(형태소, 사전 필요, 정밀도 쪽). 영문·숫자: `TokenBigramSplitSymbolAlphaDigit` 등 변형과 `TokenNgram` 옵션(읽음 `S2/dl/pgroonga_create_index.html`; 토크나이저 목록 읽음 `groonga_token_mecab.html` 목차). 정규화: NormalizerNFKC150(읽음). 사용자 사전: TokenMecab이면 MeCab 사전 재빌드, TokenBigram은 해당 없음. 동의어: `pgroonga_query_expand(table, term, synonyms, query)`로 질의 확장(읽음 `S2/dl/pgroonga_query_expand.html`). 부분 일치: n-gram이라 자연 지원. **점수는 TF뿐**: "Score is 'how many keywords are included' (TF, Term Frequency) for now. Groonga supports customizing how to score. But PGroonga doesn't support yet"(읽음 `S2/dl/pgroonga_score.html`). Groonga 자체도 "doesn't provide Okapi BM25 based scorer yet"(읽음 `S2/dl/groonga_scorers.html`) |
| B | 분석: `pdb.lindera(korean)` 형태소(ko-dic), `pdb.icu`, `pdb.ngram(n,n)`, edge-ngrams, whitespace(읽음). 필드 하나에 토크나이저 여러 개(`multiple-per-field.mdx` 존재 — 파일명만 읽음). 영문·숫자: lindera 옵션 `nfkc`, `lowercase`(읽음 lindera.mdx 64행). 점수: BM25(`pdb.score`)(읽음 README·rrf.mdx). 사용자 사전·동의어: **문서에서 확인 못 함**(열린 사실) |
| C | 분석: 앱에서 kiwipiepy로 형태소 → 공백으로 이어 `to_tsvector('simple', …)`. 질의도 같은 토크나이저로. 영문·숫자: Kiwi가 분리(어림). 사용자 사전: Kiwi API(어림, 문서 미확인). 동의어: PostgreSQL synonym 사전은 파일이 `$SHAREDIR/tsearch_data/`에 있어야 해(읽음 `S2/dl/pg_textsearch_dict.html`) 컨테이너 이미지에 굽거나, 앱에서 질의 확장. 부분 일치: 접두 `:*`만. 점수: `ts_rank`/`ts_rank_cd`는 "do not use any global information"(IDF 없음 — 읽음 `S2/dl/pg_textsearch_controls.html`) |
| D | 분석: `kagome_kr` 형태소(mecab-ko-dic)(읽음). 부분 일치·오타: 별도 속성에 `trigram` 토크나이저(읽음 `S2/dl/weaviate_kagome_doc.md`). 점수: BM25F(읽음 `S2/dl/weaviate_hybrid_doc.md`). 사용자 사전·동의어: **문서에서 확인 못 함**(열린 사실). 영문·숫자 혼용: kagome 사전 처리(어림) |
| E | OpenSearch nori: `decompound_mode`(none/discard/mixed, 기본 discard), `user_dictionary`/`user_dictionary_rules`, `discard_punctuation`(웹 요약 https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer — 같은 Lucene 모듈), `nori_part_of_speech` 필터, 동의어는 Lucene synonym 토큰 필터(어림). 점수 BM25. Meilisearch: lindera ko-dic 형태소, 동의어·오타 허용 설정 내장(어림), 점수는 BM25가 아니라 랭킹 규칙(어림) |

### D. 하이브리드

| 결선 | 값(근거) |
|---|---|
| A | 한 SQL. CTE 둘(벡터 `ORDER BY embedding <=> $1 LIMIT n`, 키워드 `WHERE content &@~ $2 ORDER BY pgroonga_score(tableoid, ctid) DESC LIMIT n`)을 `FULL OUTER JOIN`해 RRF `1/(k+rank)`를 SQL로 더한다. 패턴은 pgvector README "Hybrid Search"와 `examples/hybrid_search/rrf.py`(tsvector 판, 읽음 `S1/dl/pgvector_python_rrf.py`). RRF·정규화는 우리가 |
| B | 같은 방식이고 문서에 pg_search용 RRF SQL(`pdb.score(id)` 분기 + `embedding <=>` 분기, 분기 가중치, k=60)이 있다(읽음 `S2/dl/paradedb_hybrid_rrf.mdx`). RRF는 우리가 SQL로 |
| C | pgvector README의 rrf.py 그대로(`ts_rank_cd` + `<=>`)(읽음). RRF는 우리가 |
| D | 서버 내장 `hybrid`(alpha, 서버 기본 0.75 — 웹 요약 https://docs.weaviate.io/weaviate/concepts/search/hybrid-search). 융합: `relativeScoreFusion`(v1.24부터 기본, 점수 정규화 합) 또는 `rankedFusion`(읽음 `S2/dl/weaviate_hybrid_concept.md`). 한 요청 |
| E | 두 저장소에 두 질의를 던져 앱에서 RRF. OpenSearch의 내장 하이브리드는 벡터가 OpenSearch 안에 있어야 해서 해당 없음 |

### E. 필터와 권한(지식베이스·그룹·접근 그룹)

| 결선 | 값(근거) |
|---|---|
| A·B·C(pgvector 공통) | 사후 필터 + 반복 스캔(0단계 인용). 설계: 지식베이스 필터는 **지식베이스마다 부분 HNSW 색인**(`WHERE kb_id = …`)으로 색인 선택에 흡수(README "partial indexing" 권고 읽음). 접근 그룹(`acl && $groups`)·그룹·날짜는 사후 필터이고 `hnsw.iterative_scan = relaxed_order`로 k를 채운다. 한계: `hnsw.max_scan_tuples`(기본 20000)에 닿으면 k 미달 가능 → 아주 좁은 필터(접근 그룹이 가진 조각이 적을 때)는 정확 스캔으로 떨어뜨리는 분기가 설계에 필요(어림). 접근 그룹 수가 적고 고정이면 그룹별 부분 색인도 가능(어림). 키워드 측: PGroonga·pg_search·tsvector 모두 일반 `WHERE`로 거른다 |
| D | 사전 필터: "Filtered vector search in Weaviate is based on the concept of pre-filtering … does not require a brute-force vector search", 역색인으로 allow-list를 만든 뒤 HNSW 탐색, `v1.34`부터 ACORN 기본(읽음 `S2/dl/weaviate_filters_doc.md`) → 좁은 필터에서도 k 보장(문서 주장, 읽음) |
| E | 벡터 측은 pgvector와 같다. 키워드 측(OpenSearch)은 bool filter. **접근 그룹 필터를 두 저장소 모두에 복제**해야 하고 변경 시 둘 다 갱신(어림) |

### F. 다중 모델·차원

| 결선 | 값(근거) |
|---|---|
| A·B·C | `embedding vector`(차원 없음) 컬럼 하나 + 지식베이스마다 `CREATE INDEX … USING hnsw ((embedding::vector(768)) vector_cosine_ops) WHERE kb_id = …`(README FAQ 읽음). 지식베이스 생성 = DDL 1회(부분 색인). 상한 `vector` 2,000, `halfvec` 4,000(읽음). 대안은 kb별 파티션(어림) |
| D | 컬렉션마다 벡터 설정 → 지식베이스 = 컬렉션(API 호출, DDL 아님). 컬렉션 하나에 named vectors로 여러 차원도 가능(어림) |
| E | 벡터 측 A와 같음. 키워드 측은 차원 무관 |

### G. 일관성

| 결선 | 값(근거) |
|---|---|
| A | 메타데이터·벡터·키워드 색인이 **같은 PostgreSQL 트랜잭션**. 문서 교체·삭제가 원자적. 단 PGroonga 색인은 PostgreSQL WAL 밖이다: `pgroonga.enable_wal` 기본 off(켜면 스트리밍 복제 가능, 쓰기 성능 저하 — 읽음 `S2/dl/pgroonga_enable_wal.html`), "PGroonga isn't crash safe. If your PostgreSQL process is crashed while updating, your PGroonga indexes may be broken … REINDEX"(읽음 `S2/dl/pgroonga_overview.html`). 크래시 세이프 모듈(`pgroonga_crash_safer`, `pgroonga.enable_crash_safe`)은 2.3.3부터 "still an experimental feature", 쓰기 성능 페널티(읽음 `S2/dl/pgroonga_crash_safe.html`) |
| B | 같은 트랜잭션. pg_search 색인은 PostgreSQL 블록 스토리지·버퍼 캐시·WAL 위에 있어 크래시 복구와 물리 복제가 된다(웹 요약 https://www.paradedb.com/blog/block_storage_part_one; README "standard SQL and ACID transactions" — 읽음) |
| C | 같은 트랜잭션. tsvector·GIN·pgvector 모두 PostgreSQL 네이티브(WAL) |
| D | 두 저장소. PostgreSQL 커밋과 Weaviate 반영 사이 창 → outbox 표 + 작업자 재시도 + 주기 대조(원천이 진실·"다음 동기화 뒤 검색되지 않는다"는 PRD 문구가 지연을 허용)(어림). 문서 교체는 Weaviate 쪽 삭제+삽입이 한 트랜잭션이 아님(어림) |
| E | 세 자리(PostgreSQL 표·pgvector·OpenSearch). D와 같은 보상에 키워드 색인까지 두 벌(어림) |

### H. 규모와 성능(조각 수백만 어림). 모두 웹 요약이거나 어림

| 항목 | 값(근거) |
|---|---|
| pgvector HNSW | Supabase: dbpedia-openai 1M×1536, m=24·ef_construction=56, 8코어 32GB에서 accuracy@10 0.98은 ef_search 100, 0.99는 250; "Postgres uses about 30-35GB of RAM for optimal performance on this dataset"; 절대 QPS·빌드 시간은 안 적음(웹 요약 https://supabase.com/blog/increase-performance-pgvector-hnsw). README: 그래프가 `maintenance_work_mem`에 들어가야 빠름, `max_parallel_maintenance_workers`로 병렬 빌드(읽음). 색인 메모리 어림 N×(4d + 8·2m)B → 3M×768, m=16이면 원본 9.2GB + 색인 ~10GB(어림) |
| pgvector 반복 스캔 | AWS 블로그: 10M×384(all-MiniLM-L6-v2), 카테고리 9개(5~25%), 특정 질의 패턴에서 0.7.4 대비 최대 5.7배; relaxed_order는 strict 대비 95~99% 품질(웹 요약 https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/; 조건 불충분) |
| pgvectorscale(참고) | 50M×768 Cohere, r6id.4xlarge 128GB, pgvector 0.7.0, Pinecone s1 대비 p95 28배 낮음·QPS 16배(비율만, HNSW 수치 없음)(웹 요약 https://www.tigerdata.com/blog/pgvector-vs-pinecone) |
| Qdrant 벤치(비교군) | 2024-06, 8vCPU 32GB 서버, 1M×1536·10M×96·1M×960·1.2M×100; 수치는 차트, pgvector 없음; Elasticsearch 색인이 10M×96에서 5.5시간 vs 32분(웹 요약 https://qdrant.tech/benchmarks/) |
| VectorDBBench | 케이스 Performance768D1M/10M, 1536D500K/5M, 필터·전문 검색 케이스, pgvector·pgvectorscale·VectorChord·Weaviate·Elasticsearch·OpenSearch 지원, README에 수치 없음(웹 요약 https://github.com/zilliztech/VectorDBBench) |
| OpenSearch k-NN 메모리 | "1.1 * (4 * dimension + 8 * m) bytes/vector", 1M×256 m=16 ≈ 1.267GB, 네이티브 색인은 힙 밖 RAM의 circuit breaker 50%(웹 요약 https://raw.githubusercontent.com/opensearch-project/documentation-website/main/_mappings/supported-field-types/knn-methods-engines.md) |
| Qdrant 용량 공식(참고) | dense = N×d×4B, HNSW = N×m×2×4B×1.2(웹 요약 https://qdrant.tech/documentation/capacity-planning/) |
| Weaviate | HNSW 전부 메모리 상주(읽음). 수치 없음 |
| PGroonga·pg_search 키워드 | 공개 수치 없음(PGroonga overview는 정성적 — 읽음) |

### I. 백업·복원

| 결선 | 값(근거) |
|---|---|
| A·B·C | `pg_dump` 하나. 색인은 정의만 담기고 복원 때 다시 만들어진다(PostgreSQL 일반 동작, 어림) → 복원 시간 = HNSW + 키워드 색인 재빌드. 물리 백업(`pg_basebackup`)은 PGroonga 색인 파일을 포함하나 `enable_wal` off면 복제엔 못 쓴다(읽음 enable-wal). pg_search는 블록 스토리지라 물리 백업·PITR 대상(웹 요약) |
| D | 둘: `pg_dump` + Weaviate `backup-filesystem` 모듈(`ENABLE_MODULES=backup-filesystem`, `BACKUP_FILESYSTEM_PATH`, 단일 노드용 — 읽음 `S2/dl/weaviate_backups_doc.md`). 두 스냅샷의 시점이 달라 복원 뒤 대조가 필요(어림) |
| E | 둘: `pg_dump` + OpenSearch snapshot(fs repository)(어림). Meilisearch면 snapshot/dump(어림) |

### J. 파이썬 클라이언트

| 결선 | 값(근거) |
|---|---|
| A·B·C | psycopg 3.3.8 LGPL-3.0-only, `py.typed`, async 내장, 휠 0.2MB, 의존 typing-extensions뿐(읽음 PyPI; 지난 조사). pgvector 0.5.1 MIT, `py.typed`, 휠 0.03MB, 의존 없음(읽음). C는 kiwipiepy 0.24.1 추가: 휠 3.7~5.9MB(cp39-abi3), 의존 kiwipiepy_model·numpy·tqdm, **`py.typed` 없음**(`_c_api.pyi` 스텁만 — 스크립트 `.scratch/core/probes/vector-store/wheel_pytyped.py`) → 원칙 II 아래서 우리 쪽 스텁이 필요(어림) |
| D | weaviate-client 4.24.1 BSD-3, `py.typed` 있음(스크립트), 휠 0.67MB, 의존 pydantic≥2.12·grpcio·protobuf·authlib·httpx·validators(읽음 PyPI), async 클라이언트 있음(어림) |
| E | opensearch-py 3.2.0 Apache-2.0, `py.typed` 있음(스크립트), 휠 0.39MB, 의존 requests·urllib3·certifi·Events·opensearch-protobufs, async는 extra(읽음 PyPI). meilisearch 0.43.0 MIT `py.typed`, requests+camel-converter[pydantic], 동기만; meilisearch-python-sdk 8.1.5 MIT `py.typed`, pydantic+httpx2, async(읽음 PyPI, 스크립트) |

### K. 성숙도

| 대상 | 최신 판·날짜(근거) | 주기·유지 주체 |
|---|---|---|
| pgvector | 0.8.7(이미지 2026-10-31)(스크립트 S1; 지난 조사) | 개인(ankane) 중심 |
| PGroonga | 4.1.0 2026-10-09; 4.0.9 09-23; 4.0.8 08-03(읽음 `S1/dl/pgroonga_releases.json`). main의 control은 4.1.1(읽음). Groonga 16.1.5 2026-10-29(읽음 `S2/dl/groonga_news.html`) | 월 1회쯤. Groonga Project(ClearCode) |
| pg_search | v0.26.6 2026-11-08, 0.26.5 11-04(읽음 release JSON, 스크립트 hub_tags) | 주 단위. ParadeDB Inc. |
| Kiwi/kiwipiepy | 0.24.1 2026-10-20(읽음 release JSON) | 개인(bab2min) |
| Weaviate | 1.40.4 2026-11-05(스크립트 S1) | Weaviate B.V. |
| OpenSearch | 3.9.0 2026-09-29; 2.19.7 2026-10-26(읽음 release JSON, 스크립트) | 분기 단위. OpenSearch Software Foundation(Linux Foundation) |
| Meilisearch | v1.56.1 2026-11-02(읽음 release JSON) | Meili SAS |

### L. 테스트

GitHub Actions service container는 Ubuntu 러너에서 공개 레지스트리 이미지를 그대로 띄운다("If you are using GitHub-hosted runners, you must use an Ubuntu runner" — 웹 요약 https://docs.github.com/en/actions/using-containerized-services/about-service-containers).

| 결선 | 값(근거) |
|---|---|
| A | service container 가능하나 결합 이미지가 없어 **우리 이미지를 레지스트리에 올리거나** cubeplex(비공식)를 쓴다. 임베디드 대안 없음(PostgreSQL 바이너리 필요) → 로컬도 Docker 또는 외부 DB URL |
| B | `paradedb/paradedb:0.26.6-pg18`을 바로 service container로. 임베디드 없음 |
| C | `pgvector/pgvector:0.8.7-pg18-trixie`를 바로. 임베디드 없음 |
| D | `semitechnologies/weaviate:1.40.4` + `ENABLE_TOKENIZER_KAGOME_KR=true`. 임베디드 Weaviate는 "experimental", "supported on Linux and macOS"(웹 요약 https://docs.weaviate.io/deploy/installation-guides/embedded) → Windows 개발 기계에선 Docker |
| E | OpenSearch는 nori가 이미지에 없어 **커스텀 이미지**가 필요하고 힙 1GB·`vm.max_map_count`가 걸린다(읽음). Meilisearch는 단일 바이너리라 로컬·CI 모두 쉬움(어림) |

### M. 색인 판 올리기(모델 교체·재색인)

| 결선 | 값(근거) |
|---|---|
| A·B·C | 새 임베딩을 새 컬럼(또는 새 kb 부분 색인)에 적재한 뒤 한 트랜잭션에서 교체. HNSW 빌드는 `maintenance_work_mem`·병렬 워커로(읽음). PGroonga 자체 판 올리기: 호환 판은 `ALTER EXTENSION pgroonga UPDATE`, 비호환(3.2.5→4.0.0 같은)은 색인 전부 삭제·재생성(웹 요약 https://pgroonga.github.io/upgrade/). pg_search: 테이블당 색인 하나("Only one ParadeDB index can exist per table" — 웹 요약 https://www.paradedb.com/docs/reference/indexing/create-index) → 토크나이저를 바꾸면 그 테이블 색인 재생성 |
| D | 새 컬렉션에 재적재 후 이름·별칭 교체(어림) |
| E | 벡터 측 A와 같음 + OpenSearch 새 인덱스·alias 교체(어림) |

### N. 채택도(수집 2026-11-09)

수치는 모두 그날 하루의 스냅숏이다. 별·pull·다운로드는 CI·미러·봇이 부풀리고, OpenSearch·Elasticsearch·PostgreSQL 수치는 벡터 검색이 아닌 쓰임이 대부분이므로(어림) 같은 줄끼리만 견준다.

**N-1. GitHub**(스크립트 `github_stats.py`, 원문 `S2/dl2/gh_<owner>_<repo>.json`). 기여자는 anon 포함 Link 마지막 페이지 수, 90일 커밋은 기본 브랜치의 2026-08-11 이후 커밋 수(머지·봇 포함).

| 저장소 | 별 | 포크 | 열린 이슈 | 기여자 | 90일 커밋 | 첫 GitHub 릴리스 | 최신 릴리스 | 저장소 생성 |
|---|---|---|---|---|---|---|---|---|
| pgvector/pgvector | 23,625 | 1,384 | 17 | 27 | 103 | 릴리스 기능 안 씀(첫 태그 v0.1.0 2021-04-20, 읽음 commits API) | – | 2021-04-20 |
| pgroonga/pgroonga | 762 | 33 | 51 | 11 | 17 | 2015-09-29 | 2026-10-09 | 2015-01-12 |
| groonga/groonga | 862 | 124 | 153 | 86 | 160 | 2014-05-14 | 2026-10-29 | 2009-01-14 |
| paradedb/paradedb | 9,498 | 505 | 283 | 157 | 580 | 2024-06-06 | 2026-11-08 | 2023-06-30 |
| bab2min/Kiwi | 804 | 82 | 18 | 16 | 88 | 2017-10-30 | 2026-10-19 | 2017-02-21 |
| bab2min/kiwipiepy | 416 | 39 | 12 | 9 | 53 | 2019-12-01 | 2026-10-20 | 2019-09-06 |
| weaviate/weaviate | 16,944 | 1,434 | 843 | 191 | 3,563 | 2019-05-21 | 2026-11-05 | 2016-03-30 |
| qdrant/qdrant | 35,479 | 2,805 | 781 | 215 | 610 | 2021-04-06 | 2026-10-22 | 2020-05-30 |
| milvus-io/milvus | 46,614 | 4,324 | 1,449 | 398 | 743 | 2019-10-21 | 2026-10-30 | 2019-09-16 |
| chroma-core/chroma | 29,657 | 2,601 | 979 | 197 | 85 | 2022-10-22 | 2025-04-01(릴리스 기능을 그 뒤 안 씀. 최신 커밋 2026-11-07, 읽음 commits API) | 2022-10-05 |
| opensearch-project/OpenSearch | 13,981 | 3,088 | 3,357 | 2,238 | 326 | 2021-04-22 | 2026-10-20 | 2021-01-29 |
| meilisearch/meilisearch | 59,817 | 2,784 | 316 | 261 | 313 | 2019-11-26 | 2026-11-02 | 2018-04-23 |
| elastic/elasticsearch | 78,533 | 26,199 | 6,434 | 2,569 | 4,157 | 2019-06-20(릴리스 기능 기준. 프로젝트는 2010) | 2026-11-02 | 2010-02-08 |

**N-2. 이미지 pull과 파이썬 패키지 다운로드**(스크립트 `pulls_and_pypistats.py`, 원문 `S2/dl2/hub_repo_*.json`·`pypistats_*.json`). pull은 Docker Hub `pull_count` 누적, 다운로드는 pypistats `last_month`.

| 제품 | Docker Hub 이미지 | 누적 pull | 파이썬 패키지 | 최근 30일 다운로드 |
|---|---|---|---|---|
| PostgreSQL(참고) | library/postgres | 12,311,071,653 | psycopg / psycopg2-binary / asyncpg | 133,610,177 / 206,514,204 / 107,296,977 |
| pgvector | pgvector/pgvector | 306,983,100 | pgvector | 31,134,981 |
| PGroonga | groonga/pgroonga (+cubeplex 결합 이미지) | 1,158,648 (+10,317) | –(SQL 함수만) | – |
| pg_search | paradedb/paradedb | 4,312,340 | – | – |
| VectorChord(참고) | tensorchord/vchord-postgres | 635,151 | – | – |
| Kiwi | – | – | kiwipiepy | 323,273 |
| Weaviate | semitechnologies/weaviate | 34,799,413 | weaviate-client | 9,835,248 |
| Qdrant | qdrant/qdrant | 56,204,541 | qdrant-client | 12,034,960 |
| Milvus | milvusdb/milvus | 80,154,738 | pymilvus | 3,698,902 |
| Chroma | chromadb/chroma | 8,852,637 | chromadb | 6,525,454 |
| OpenSearch | opensearchproject/opensearch | 225,305,303 | opensearch-py | 39,088,317 |
| Meilisearch | getmeili/meilisearch | 64,828,752 | meilisearch | 608,387 |
| Elasticsearch | library/elasticsearch(Docker Hub 공식 이미지만. docker.elastic.co 수치는 공개 안 됨) | 988,453,322 | elasticsearch | 34,064,422 |
| LanceDB(참고) | – | – | lancedb | 7,689,981 |

**N-3. 관리형 PostgreSQL의 확장 탑재**(읽음 `S2/dl2/managed_*.html`, 2026-11-09 저장. 판은 확장 표에서 읽은 것, "있음"은 전용 절·행이 있는 것, "없음"은 문서 전체에 이름이 0회). pgvector는 아홉 곳 모두에 있고(받은 문서는 열한 개. Neon과 Supabase는 둘씩이다) PGroonga는 Supabase뿐, pg_search는 Neon에만 나오는데 "Unavailable"·"Deprecated"로 표시된다. 이 축에서 결선 C(pgvector만)가 가장 넓게 붙고, A(PGroonga)와 B(pg_search)는 관리형 PostgreSQL에 붙이려면 Supabase(A)거나 자체 운영이다.

| 서비스 | pgvector | PGroonga | pg_search |
|---|---|---|---|
| AWS RDS for PostgreSQL | 0.8.2(PG 14~18 열) | 없음 | 없음 |
| AWS Aurora PostgreSQL | 0.8.2 | 없음 | 없음 |
| GCP Cloud SQL for PostgreSQL | 0.8.5(PG 13+) | 없음 | 없음 |
| GCP AlloyDB | 있음(판 안 읽음) | 없음 | 없음 |
| Azure Database for PostgreSQL Flexible | 0.8.2(PG 14~18) | 없음 | 없음 |
| Supabase | 있음(전용 문서) | **있음**(전용 문서 "PGroonga: Multilingual Full Text Search") | 없음 |
| Neon | 0.8.0~0.8.6(PG 판별) | 없음 | 목록에 있으나 "**Unavailable.**"·"Deprecated" |
| DigitalOcean Managed PostgreSQL | 있음 | 없음 | 없음 |
| Crunchy Bridge | 있음 | 없음 | 없음 |

**N-4. 설문·순위·고객 페이지**

| 원천 | 값(근거) |
|---|---|
| Stack Overflow Developer Survey 2025, 데이터베이스 | PostgreSQL 55.6%(전체)·58.2%(전문가), Elasticsearch 16.7%·17.8%. Pinecone·Milvus·Qdrant·Chroma·Weaviate는 보기에 없음(읽음 `S2/dl2/so_survey_2025_tech.html`에서 0회) |
| DB-Engines 벡터 DBMS 순위 | 원문을 두 번(WebFetch, urllib) 받지 못함(인증서 검증 오류). 제3자 블로그가 옮긴 2026-03 점수: Pinecone 7.74, Milvus 6.02, Qdrant 4.79, Weaviate 4.52(웹 요약 https://zatoima.github.io/en/db-engines-ranking-march-2026, 원문 https://db-engines.com/en/ranking/vector+dbms). 순위 자체가 검색 빈도·구인 공고 기반 지표라 설치 수가 아니다(어림) |
| Qdrant 고객 페이지 | Kakao("AI-Powered Internal Service Desk"), Deutsche Telekom, Tripadvisor, HubSpot, Flipkart, Sprinklr, Bazaarvoice, Dailymotion 등 50여 사(읽음 `S2/dl2/qdrant_customers.html`에서 이름 확인). 벡터 수·QPS는 없음 |
| Weaviate 사례 페이지 | 이름이 있는 사례 MetaBuddy 하나, 규모 수치 없음(웹 요약 https://weaviate.io/case-studies) |
| pgvector | 공식 고객 페이지 없음. 채택 근거는 N-3의 관리형 탑재와 N-2의 pull·다운로드 |
| ParadeDB·PGroonga·Kiwi 고객 페이지 | 보지 않음 |

### O. 확장성(무료판 기준)

| 결선 | 수직(노드 하나에서) | 수평(복제·HA·샤딩, 무료판에서) | 문서화된 한계 | 공개 규모 사례 |
|---|---|---|---|---|
| A pgvector+PGroonga | pgvector HNSW는 버퍼 캐시·OS 캐시에 올라야 빠르고 공식 상한은 없다(읽음 README). 메모리 어림: 768차원 float32 한 벡터 3KB + 그래프 → 100만 조각 3~4GB, 1,000만 조각 30~40GB(어림. halfvec면 절반). 디스크 기반이 필요하면 pgvectorscale·VectorChord로 색인만 바꾼다(1단계 표). PGroonga는 색인당 Groonga DB 파일 | PostgreSQL 스트리밍 복제·HA(Patroni 등)·읽기 복제본은 모두 무료. pgvector 색인은 표준 AM이라 WAL로 그대로 복제(어림). **PGroonga는 standby에도 설치하고 `pgroonga.enable_wal=on`·`pgroonga.max_wal_size`를 켜야 하며**, 크래시 세이프는 `pgroonga_crash_safer`를 preload하되 "reduces write performance"(읽음 `S2/dl2/pgroonga_replication.html`). 샤딩은 Citus 등 별도 | pgvector 2,000차원(halfvec 4,000)(읽음, F 차원). Groonga 테이블: 레코드 2^30-1(PAT_KEY)·2^28-1(DAT_KEY), 키 총합 4GiB 기본(KEY_LARGE 1TiB)(읽음 `S2/dl2/groonga_limitations.html`, v16.1.5) | 플레인 pgvector의 실무 상한을 5천만 안팎으로 보는 글이 여럿, Timescale의 5천만 벤치는 판매자 자료(웹 요약 https://blog.elest.io/pgvector-vs-qdrant-vs-weaviate-which-vector-database-holds-up-at-100m-vectors/, https://thenewstack.io/why-pgvector-benchmarks-lie/). PGroonga 규모 사례 못 찾음 |
| B pgvector+pg_search | pgvector는 A와 같다. pg_search는 "designed to scale vertically on a single Postgres primary", 1~10TB 운영, 본 최대 10TB(읽음 `S2/dl2/paradedb_limitations.mdx`) | **Community는 단일 노드**: "ParadeDB Community ... supports single-node deployments", HA·failover·읽기 복제본(인덱스 물리 복제)은 Enterprise(읽음 `S2/dl2/paradedb_enterprise.mdx` 표 "High availability ❌/✅", "Read replica support ❌/✅"; `paradedb_high_availability.mdx`). Community에서 되는 것: ParadeDB를 기존 PostgreSQL의 **논리 복제 구독자**로 두기(DDL은 수동)(읽음 `paradedb_logical_replication.mdx`). 샤딩은 Citus·PgDog 언급(읽음 limitations) | 테이블당 색인 하나(M 차원). covering index라 컬럼 추가·삭제는 REINDEX(읽음 limitations) | 10TB(위). 고객 페이지 안 봄 |
| C pgvector+tsvector+kiwipiepy | pgvector는 A와 같다. tsvector GIN은 PostgreSQL 기본. 형태소 분석은 앱 프로세스(모델 88MB, B 차원) | PostgreSQL 그대로 전부 무료. 분석기가 앱에 있어 서버 복제와 무관 | tsvector 1MB 미만, 위치 값 ≤16,383, 어휘소당 위치 256개(읽음 `S2/dl2/pg_textsearch_limitations.html`) | pgvector와 같음. tsvector 한국어 규모 사례 없음 |
| D Weaviate | "HNSW is an in-memory index"(읽음 `S2/dl2/weaviate_vector_index.md`). 메모리 줄이기: flat·dynamic(flat→HNSW 자동 전환)·**HFresh**(디스크 기반, 센트로이드만 메모리), 양자화 PQ·BQ·SQ·RQ(읽음 `weaviate_compression.md`) | **OSS(CE)에서 샤딩(v1.8+)과 복제(replication factor, 리더리스 데이터 복제, 메타데이터는 v1.25부터 Raft) 모두 됨**(읽음 `S2/dl2/weaviate_cluster.md`, `weaviate_replication_arch.md`). 멀티테넌시는 테넌트=샤드(읽음 `weaviate_multitenancy.md`). Cloud 가격표의 "HA / replication ×(Free)"는 Cloud 등급 이야기(읽음 `weaviate_pricing.html`) | `MAXIMUM_ALLOWED_COLLECTIONS_COUNT` 기본 -1(무제한, v1.30~)이지만 컬렉션 수가 늘면 성능 병목이라 멀티테넌시 권고(읽음 `S2/dl/weaviate_env_doc.md`, `S2/dl2/weaviate_collections_limits.mdx`) | 사례 페이지에 규모 수치 없음(N-4) |
| E pgvector+OpenSearch / Meilisearch | OpenSearch k-NN HNSW는 네이티브(off-heap) 메모리(읽음, H 차원). `mode: on_disk`면 기본 32x 압축 + 전정밀 재점수 2단계(읽음 `S2/dl2/opensearch_disk_based.md`). Meilisearch는 단일 프로세스·LMDB | OpenSearch 클러스터 샤딩·복제는 서버 코어이고 security·k-NN 플러그인도 Apache-2.0(읽음 `S2/dl2/opensearch_*_LICENSE`). **Meilisearch는 단일 노드**: 샤딩·네트워크(연합) 코드는 `enterprise_edition` 모듈(BUSL)(읽음 `S2/dl2/meilisearch_tree.json`의 `crates/milli/src/sharding/enterprise_edition.rs`, 그 파일 머리 주석) | Meilisearch: 인덱스당 문서 4,294,967,296, 인덱스 크기 ~80TiB(2TiB 권장), 속성당 위치 65,535, 인덱스당 속성 65,536(읽음 `S2/dl2/meilisearch_known_limits.html`) | 못 찾음(열린 사실 9) |
| 참고: Qdrant | 노드 하나에 "up to about 100 million vectors"(읽음 `S2/dl2/qdrant_vertical_scaling.md`). RAM 공식 `dense_size = base * dimensions * bytes_per_dim`(읽음 `qdrant_capacity_planning.md`). on-disk 벡터·양자화 | OSS에서 샤딩·복제(`shard_number`, `replication_factor`)·Raft 모두 됨. **리샤딩·자동 리밸런싱은 Cloud 전용**("not available in self-hosted Qdrant")(읽음 `S2/dl2/qdrant_distributed.md`) | 리소스 쿼터(v1.19, 기본 꺼짐)(읽음 `qdrant_quotas.md`) | 고객 페이지(N-4) |
| 참고: Milvus | DiskANN(디스크 Vamana + 메모리 PQ)(읽음 `S2/dl2/milvus_diskann.md`) | 분산 구조(코디네이터 active-standby 2.2.3+, 무상태 워커, etcd·오브젝트 스토리지·스트리밍) 전부 Apache-2.0(읽음 `milvus_architecture.md`, `milvus_coordinator_ha.md`) | DB당 컬렉션 65,536, 컬렉션당 파티션 1,024(읽음 `milvus_multi_tenancy.md`, `milvus_quota_limits.md`) | – |

한 줄 판정(어림, 위 표에서): A·C는 PostgreSQL이 주는 만큼(수직 + 복제/HA 무료, 샤딩은 외부)이고 A는 PGroonga WAL 설정이 하나 더 붙는다. B는 벡터 쪽은 같지만 **키워드 색인의 HA가 유료**다. D는 무료판에서 분산이 가장 완전하다(샤딩+복제+Raft). E의 OpenSearch는 무료 분산이 완전하되 무겁고, Meilisearch는 분산이 유료다.

### P. 무료판의 기능 제한·텔레메트리·라이선스 변경 이력

**P-1. 유료·클라우드 전용 기능**(무료판에 없는 것만)

| 제품 | 무료판 라이선스 | 유료·클라우드에만 있는 것(근거) |
|---|---|---|
| pgvector | PostgreSQL License(읽음, A 차원) | 없음. 상용판 없음 |
| PGroonga / Groonga | PostgreSQL License / LGPL-2.1(읽음, A 차원) | 없음. 상용은 지원 계약뿐(어림) |
| pg_search(ParadeDB) | AGPL-3.0(Community) | Enterprise: 상용 라이선스, 지원, **인덱스 물리 복제 → HA·failover·읽기 복제본**(표에서 Community ❌ 두 줄: High availability, Read replica support). Cloud는 private preview(읽음 `S2/dl2/paradedb_enterprise.mdx`, `paradedb_pricing.html`) |
| Kiwi / kiwipiepy | Apache-2.0(0.23.2 이하는 LGPL 유지)(읽음 `S2/dl2/kiwi_README.md`) | 없음 |
| Weaviate | BSD-3(CE = `wl/` 밖 전부) | EE(v1.40~, `LICENSE_KEY`): **Shard Self-Recovery, Namespaces, Deduplicated backups**. 키 없이 켜면 403·빈 샤드(읽음 `S2/dl2/weaviate_enterprise.mdx`, `weaviate_wl_LICENSE`). RBAC는 OSS v1.29 GA(읽음 `weaviate_rbac_config.md`). Cloud 등급표(Free/Flex/Premium/Enterprise): 백업 보존 ×/7/30/45일, HA·복제 ×/✓/✓/✓, SSO·SAML ×/×/✓/✓(읽음 `weaviate_pricing.html`) — Cloud 이야기, 셀프호스트 CE에는 적용 안 됨 |
| OpenSearch | Apache-2.0(서버·security·k-NN 플러그인 LICENSE 읽음) | 없음. 상용은 AWS 관리형뿐(어림) |
| Meilisearch | MIT + EE 부분 BUSL-1.1(`SPDX: MIT AND BUSL-1.1`)(읽음 `S2/dl2/meilisearch_LICENSE`) | EE 코드(`enterprise_edition` 모듈): **샤딩, 네트워크 연합 검색, S3 스냅숏, 동적 검색 규칙**. BUSL은 "non-production purposes only", 상용 사용은 계약, Change Date 공개 4년 뒤 MIT(읽음 `meilisearch_LICENSE_EE`, `meilisearch_tree.json`). Cloud Enterprise: SSO SAML, 분석, 개인화(읽음 `meilisearch_pricing.html`) |
| 참고: Qdrant | Apache-2.0 | 리샤딩·자동 리밸런싱(O 표), Cloud RBAC·백업 자동화·SSO(읽음 `qdrant_pricing.html`, 첫 열 지원 "Discord Only"). OSS에 있는 것: API 키(v1.2), 읽기 전용 키(v1.7), 컬렉션 단위 JWT(v1.9), TLS(읽음 `qdrant_security.md`) |
| 참고: Milvus | Apache-2.0 | Zilliz Cloud: Free 5GB·컬렉션 5개, Enterprise에 SSO·RBAC·감사로그·99.95% SLA(읽음 `S2/dl2/zilliz_pricing.html`). Milvus OSS의 RBAC 유무는 안 봄 |
| 참고: Elasticsearch | AGPL-3.0 / SSPL / ELv2 택일 | Basic(무료)에 TLS·파일/네이티브 인증·RBAC(6.8.0·7.1.0부터). 유료: SSO·LDAP/AD·필드·문서 수준 보안(읽음 `S2/dl2/elastic_security_free_blog.html`). 구독표 PDF는 텍스트 추출에서 등급 열이 사라져 대조 못 함(읽음 `elastic_subscriptions.pdf`→`.txt`) |
| 참고: Chroma | Apache-2.0(읽음 `S2/dl2/chroma_LICENSE`) | Chroma Cloud. 안 봄 |

**P-2. 텔레메트리(전화 걸기) 기본값**

| 제품 | 기본 | 끄기(근거) |
|---|---|---|
| pgvector, PGroonga, Kiwi | 문서에 텔레메트리 언급 없음(어림: PostgreSQL 확장·라이브러리가 바깥에 접속할 통로가 없다) | – |
| pg_search | 저장소에 `telemetry.rs`가 있으나 커스텀 스캔의 EXPLAIN 통계 코드다(읽음 `S2/dl2/paradedb_docs_tree.json` 경로). 전화 걸기 유무는 확인 못 함(열린 사실 12) | – |
| Weaviate | **켬**: 판·OS·객체 수·토폴로지·클라이언트 라이브러리·클라우드 메타데이터, "may use this data to identify potential customers"; v1.39.4부터 시작 배너도 weaviate.io에서 받아 옴 | `DISABLE_TELEMETRY=true`(읽음 `S2/dl2/weaviate_telemetry.md`) |
| OpenSearch | 문서에서 못 봄(어림: 없음) | – |
| Meilisearch | **켬**(시스템·성능·기능 사용) | `--no-analytics` 또는 `MEILI_NO_ANALYTICS=true`(읽음 `S2/dl2/meilisearch_telemetry.html`) |
| 참고: Qdrant | **켬**(OSS 컨테이너, 익명) | `QDRANT__TELEMETRY_DISABLED=true`(읽음 `S2/dl2/qdrant_usage_statistics.md`) |
| 참고: Chroma | 익명 제품 텔레메트리 수집(읽음 `S2/dl2/chroma_telemetry_README.md`) | 끄는 변수는 문서 원문 못 받음(404) |

**P-3. 라이선스 변경 전력**(스크립트 `github_stats.py`의 LICENSE 커밋 이력 `S2/dl2/gh_license_commits_*.json`, Elasticsearch는 `LICENSE.txt` 이력 `elastic_license_commits.txt`)

| 제품 | 전력 |
|---|---|
| pgvector | 없음(PostgreSQL License, 2021~) |
| PGroonga, Groonga, OpenSearch | 이력 안 뽑음. 변경 소문 없음(어림) |
| pg_search(ParadeDB) | 2023-08-30 초기 LICENSE → **2023-10-04 "Convert to APGL"**(스크립트) |
| Kiwi | **LGPL → Apache-2.0, 2026-09-11**(더 관대해짐)(스크립트, 읽음 README) |
| Weaviate | BSD-3 단일 → **2026-08-26 "add Weaviate license and license switch"**(`wl/` 상용 분리), 09-15 `LICENSE_KEY` 검사, 09-30 문구 수정(스크립트, 읽음 `S2/dl/weaviate_LICENSE_root`·`S2/dl2/weaviate_wl_LICENSE` "Date posted: August 26, 2026") |
| Meilisearch | 2019-11-12 MIT 전환 → **2025-08-19 "Add EE license"(BUSL-1.1)** → 2025-10-09 LICENSE-MIT 분리(스크립트, 읽음 LICENSE) |
| Elasticsearch | Apache-2.0 → **2021-02-03 SSPL+Elastic License**(7.11, 발표 2021-01-14) → 2024-09-13 **AGPL-3.0 추가**(읽음 `elastic_license_commits.txt`, `elastic_license_change_blog.html`, `elastic_agpl_blog.html` "we had issues with AWS") |
| 참고: VectorChord(pgvecto.rs 후속) | pgvecto.rs Apache-2.0 → VectorChord 2024-10-31 AGPL → 2024-12-10 AGPL+ELv2 이중(스크립트, 읽음 `pgvecto_rs_LICENSE`) |
| 참고: Qdrant, Milvus, Chroma | 없음(Qdrant 2026-09-03은 저작권자 표기만)(스크립트) |

한 줄 판정(어림): 무료판 제한이 큰 순서는 Meilisearch(분산 전부 BUSL) ≥ pg_search(키워드 색인 HA 유료) > Weaviate(EE 셋은 운영 편의 기능, 핵심 검색·분산·RBAC는 CE) > OpenSearch·pgvector·PGroonga·Kiwi(제한 없음). 라이선스 변경 전력은 Elasticsearch·Meilisearch·Weaviate·ParadeDB·VectorChord가 "상용 쪽으로" 바꿨고 Kiwi만 반대 방향이다. PostgreSQL 확장 둘(pgvector·PGroonga)은 전력이 없다.

## 가장 갈리는 차원 다섯(요약)

1. **한국어 분석 방식과 점수**: A는 2-gram(또는 사전 빌드가 필요한 TokenMecab)에 TF 점수, B·D·E는 mecab-ko-dic 형태소에 BM25(B·E) 또는 BM25F(D), C는 형태소(Kiwi)에 IDF 없는 ts_rank.
2. **라이선스**: A·C 전부 PostgreSQL/MIT/Apache-2.0/LGPL(링크), B는 AGPL-3.0, D는 BSD-3, E는 Apache-2.0(또는 MIT+BUSL).
3. **일관성**: A·B·C는 한 트랜잭션(단 A의 PGroonga 색인은 WAL 밖·크래시 시 REINDEX, 크래시 세이프는 실험적), D·E는 두 저장소라 보상 장치.
4. **기존 PostgreSQL에 붙일 때 요구**: A 확장 2개(superuser, Groonga 저장소), B 확장 2개(superuser + `shared_preload_libraries` 재시작, PG 15+), C pgvector 1개, D·E는 pgvector(E) 또는 없음(D).
5. **배포 무게와 폐쇄망 반입**: A 1컨테이너(결합 이미지는 직접 유지, ~200~260MB), B 1컨테이너 374MB, C 1컨테이너 164MB(+모델 88MB), D 2컨테이너(+89MB), E 2컨테이너(+1159MB와 플러그인 zip, 호스트 sysctl / Meilisearch면 +106MB).

## 열린 사실(확인 못 한 것)

1. **PGroonga TokenMecab + mecab-ko-dic이 실제로 도는지.** mecab-ko-dic README는 포크 mecab-ko를 전제하는데(읽음) Debian `libmecab2`(0.996)로 `mecab-dict-index` 빌드와 Groonga 로드가 되는지, 토큰 품질이 어떤지는 실측 전엔 모른다. 안 되면 A의 한국어는 TokenBigram뿐이다.
2. **pg_search의 한국어 사용자 사전·동의어** 지원 여부(문서 색인에서 못 찾음).
3. **Weaviate kagome_kr의 사용자 사전·동의어** 지원 여부.
4. **pgvector 반복 스캔이 접근 그룹 필터(배열 overlap)에서 k를 채우는지와 지연**(실측 3).
5. **PGroonga 크래시 세이프 모듈을 켠 운영**의 안정성·쓰기 성능(문서가 "experimental").
6. **대상 사양의 메모리 예산.** PRD에 VM 사양이 없다. 조각 수백만×768차원이면 어느 안이든 수십 GB급 RAM 이야기가 된다(어림).
7. **AGPL(pg_search)의 수용 여부**는 사용자 판단이다(설치형 배포에서 AGPL 확장을 번들하는 의무 범위는 이 문서가 판정하지 않는다).
8. OpenSearch nori 플러그인 zip의 판 일치·반입 절차(어림: 플러그인 판은 서버 판과 같아야 한다).
9. Meilisearch를 벡터 저장소로 쓸 때의 규모 수치(공개 벤치 못 찾음).
10. 공식 pgvector+PGroonga 결합 이미지 부재 → 자체 이미지 유지 비용(릴리스마다 재빌드).
11. **DB-Engines 벡터 순위 원문**을 받지 못했다(인증서 검증 오류 두 번). N-4의 점수는 제3자 블로그의 2026-03 옮김이다.
12. **pg_search(ParadeDB)가 바깥으로 사용 통계를 보내는지.** 저장소의 `telemetry.rs`는 EXPLAIN 통계 코드이고, 이미지 환경 변수나 문서는 확인하지 못했다.
13. **OpenSearch·Milvus·Chroma의 텔레메트리 기본값 원문**(Chroma 문서 404). 결선에는 OpenSearch만 걸린다.
14. **pgvector 수천만~억 단위 규모의 독립 사례**가 없다. 있는 것은 판매자 벤치와 블로그뿐(O 표).
15. **Elasticsearch 구독 등급표**는 PDF 텍스트 추출에서 열이 사라져 기능별 등급을 대조하지 못했다(결선 밖 참고).
16. **Weaviate EE 범위가 앞으로 넓어질지**(2026-08 분리 뒤 석 달, 기능 셋). 지금은 CE에 검색·분산·RBAC가 다 있으나 변경 전력이 생겼다(P-3).

## 3단계: 실측 계획(실행하지 않았다. 사용자가 Docker 실측 없이 문서 근거만으로 정했다, ADR 0006)

셋 다 Docker로 이미지를 띄운다. 스크립트와 결과는 `.scratch/core/probes/`에 커밋한다(프로브 규약).

### 실측 1. 한국어 토큰 비교(결선 A·B·D·E의 C 차원을 가른다)

같은 한국어 문장 다섯(조사·복합명사·영문·숫자·띄어쓰기 오류를 하나씩 품은 문장)을 넣어 토큰 열을 표로 받는다.

- PGroonga: `docker run --rm -d --name pgr -e POSTGRES_PASSWORD=x groonga/pgroonga:4.1.0-debian-18` → `CREATE EXTENSION pgroonga; SELECT pgroonga_tokenize('<문장>', 'tokenizer', 'TokenBigram'); SELECT pgroonga_tokenize('<문장>', 'tokenizer', 'TokenMecab');`(이미지의 사전은 일본어 → 한국어는 미등록어로 뭉개질 것으로 기대. 그다음 컨테이너 안에서 `apt install mecab-utils` + mecab-ko-dic 소스 `./configure && make && make install` + `/etc/mecabrc`의 `dicdir`를 바꿔 다시 `TokenMecab`. 열린 사실 1을 판정)
- pg_search: `docker run --rm -d -e POSTGRES_PASSWORD=x paradedb/paradedb:0.26.6-pg18` → `SELECT '<문장>'::pdb.lindera(korean)::text[]; SELECT '<문장>'::pdb.icu::text[];`
- Weaviate: `docker run --rm -d -e ENABLE_TOKENIZER_KAGOME_KR=true -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true semitechnologies/weaviate:1.40.4` → 토큰 API가 없으므로 문장 다섯을 `kagome_kr` 속성으로 넣고 "서울시" vs "서울시는"처럼 조사 유무 질의로 BM25 적중을 비교(간접). 보조로 `kagome` CLI(`go install github.com/ikawaha/kagome/v2@latest`, `-dict ko`)로 직접 토큰.
- OpenSearch(선택): `opensearchproject/opensearch:3.9.0`에 `bin/opensearch-plugin install analysis-nori` 뒤 `_analyze`(tokenizer `nori_tokenizer`, decompound_mode mixed).
- 기대 산출: 문장×엔진 토큰 표, 조사 분리 여부, 복합명사 분해, 영문·숫자 처리, TokenMecab 한국어 가능 여부(예/아니오와 오류 메시지).

### 실측 2. pgvector+PGroonga 하이브리드 질의 하나를 psycopg로 소비 지점까지(결선 A의 D·E·J 차원)

- 이미지: `cubeplex/postgresql-pgroonga-pgvector:18.6-pgroonga4.1.0-pgvector0.8.7`(비공식) 또는 `groonga/pgroonga:4.1.0-debian-18`에 `apt install postgresql-18-pgvector`를 더한 임시 Dockerfile.
- 스키마: `chunks(id bigserial, kb_id int, acl text[], content text, embedding vector)`; `CREATE INDEX ON chunks USING hnsw ((embedding::vector(768)) vector_cosine_ops) WHERE kb_id = 1; CREATE INDEX ON chunks USING pgroonga (content) WITH (tokenizer = 'TokenBigram');`
- 질의: CTE 둘(`ORDER BY embedding::vector(768) <=> %(q)s` / `WHERE kb_id = 1 AND acl && %(groups)s AND content &@~ %(kw)s ORDER BY pgroonga_score(tableoid, ctid) DESC`) + `FULL OUTER JOIN` RRF(k=60) + 조각·경로·쪽·위치·갱신일·점수 컬럼.
- 소비 지점: psycopg 3.3.8 + pgvector 0.5.1 `register_vector`로 `row_factory=class_row(SearchHit)`(dataclass)까지 받아 `uv run pyright`(strict) 통과와 실행 결과 10건, `SET hnsw.iterative_scan = relaxed_order` 전후 결과 수.
- 기대 산출: 타입 검사 통과(Any·cast 없음), 질의 지연 ms(조각 1만 건 표본), RRF 결과 표. 같은 스크립트를 pg_search(`pdb.score`)와 tsvector(`ts_rank_cd`)로 바꿔 B·C도 같은 틀로 잴 수 있게 분기 하나를 둔다.

### 실측 3. 좁은 필터에서 결과가 비는지(pgvector 공통 — 결선 A·B·C 대 D의 E 차원)

- `pgvector/pgvector:0.8.7-pg18-trixie`에 조각 100만 건(랜덤 768차원, `kb_id` 4개, `acl` 접근 그룹 100개에서 1~3개 무작위), kb별 부분 HNSW(m=16, ef_construction=64, `maintenance_work_mem='4GB'`, 빌드 시간 기록).
- 질의: 접근 그룹 선택도 10%·1%·0.1%에서 `LIMIT 10`을 `hnsw.iterative_scan = off | strict_order | relaxed_order`로 각 20회. 결과 수, p50·p95 지연, `EXPLAIN (ANALYZE)`의 스캔 튜플 수, `max_scan_tuples` 도달 여부.
- 기대 산출: 선택도×모드 표. off에서 0.1%는 k 미달, relaxed_order에서 k 충족이지만 지연 상승이 예상(어림). 결과가 D(Weaviate 사전 필터)를 띄워 같은 데이터로 재는 두 번째 단계를 정당화하는지 판단 자료.
