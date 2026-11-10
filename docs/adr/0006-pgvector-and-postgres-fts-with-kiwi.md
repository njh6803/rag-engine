---
status: accepted
date: 2026-11-09
---

# 벡터 저장소는 pgvector와 PostgreSQL 전문 검색으로 하고, 한국어 형태소는 앱의 Kiwi가 맡는다

ADR 0002는 벡터 저장소를 core 설계 인터뷰에 맡겼고, 기준은 접근 그룹과 날짜로 거르는 필터, 한국어 키워드 검색과의 결합, 설치의 단순함이었다. 후보 열다섯을 라이선스, 한국어 토큰화, 이미지 크기, 필터 결합, 하이브리드, 운영, 채택도, 확장성, 무료판 제한의 차원으로 비교했고(`.scratch/core/design/vector-store-comparison.md`), 사용자가 Docker 실측 없이 문서 근거만으로 정하기로 했다. 결정은 결선 C다. 벡터는 pgvector 0.8.x의 `vector` 열에 두고 지식베이스마다 부분 HNSW 색인(`WHERE kb_id = …`)을 만들며, 필터 뒤 후보가 모자라면 `hnsw.iterative_scan`으로 보탠다(바뀜: 이력 2026-11-10 "부분 HNSW 색인은 색인 판 단위이고 벡터 열은 차원 없는 `vector`에 캐스트 표현식으로 색인한다"). 키워드는 PostgreSQL 전문 검색으로 하되 한국어 형태소 분석은 데이터베이스가 아니라 앱(서버와 작업자)의 kiwipiepy가 하고, 그 토큰을 `to_tsvector('simple', …)`에 넣어 GIN 색인을 걸며 질의도 같은 토크나이저로 자른다. 벡터와 키워드는 한 SQL에서 RRF로 합친다. 컨테이너는 공식 `pgvector/pgvector:0.8.7-pg18-trixie`(164MB, 프로브 `vector-store/hub_sizes.py`) 하나다.

고른 까닭은 넷이다. 문서의 조각 교체와 접근 그룹 필터가 데이터베이스 한 트랜잭션과 같은 SQL의 `WHERE`에서 끝나 두 저장소 사이의 일관성 장치가 필요 없다. 컨테이너가 하나이고, 색인이 데이터베이스 안에 있어 덤프 하나에 든다(원본 파일의 볼륨은 ADR 0013이 더한다). 비교한 벡터 저장소 가운데 채택도가 가장 높아(Docker Hub pull 3.07억과 PyPI 월 3,110만은 프로브 `vector-store/pulls_and_pypistats.py`. 관리형 PostgreSQL 아홉 곳 모두에 탑재된 것은 비교 문서 N-3이 각 서비스의 확장 문서를 읽은 것. Elasticsearch·OpenSearch의 더 큰 수치는 벡터 검색이 아닌 쓰임이 대부분이라 같은 줄로 견주지 않았다) 설치처와 리뷰어가 아는 도구다. 라이선스가 PostgreSQL License이고 텔레메트리, 유료판 제한, 라이선스 변경 전력이 없다. PostgreSQL 기본 파서는 한국어를 공백 단위로만 자르므로(지난 조사의 문서 읽음) 형태소 분석을 앱에 두었고, Kiwi는 Apache-2.0에 py.typed가 없어(프로브 `vector-store/wheel_pytyped.py`) 우리 쪽 스텁을 둔다.

## Considered Options

- A. pgvector + PGroonga: 점수가 TF뿐이고("Score is 'how many keywords are included' (TF, Term Frequency) for now", 문서 읽음), 색인이 WAL 밖이라 크래시 뒤 REINDEX가 필요하며, 공식 결합 이미지가 없고 한국어 TokenMecab은 사전을 소스에서 빌드해야 한다.
- B. pgvector + ParadeDB pg_search: BM25와 lindera ko-dic이 들어 있지만 AGPL-3.0이고 Community는 단일 노드, 이미지 374MB에 `shared_preload_libraries` 재시작이 필요하다.
- D. Weaviate: kagome 한국어 토크나이저와 BM25F가 있지만 저장소가 둘이 되고, 텔레메트리가 기본으로 켜지며 2026-08에 상용 분리가 있었다.
- E. pgvector + OpenSearch(또는 Meilisearch): 키워드 엔진이 Apache-2.0이고 nori가 있지만 이미지 1,159MB에 힙 1GB와 `vm.max_map_count`가 필요하고 저장소가 둘이다. 설치처 규모가 커지면 키워드 엔진만 이 길로 바꿀 수 있다.
- F. OpenSearch 단독: 하이브리드가 내장되지만 무게가 같고 PostgreSQL이 어차피 있다.
- G. Qdrant: 가볍고(72.6MB) 분산이 되지만 공식 빌드의 charabia에 `korean` 피처가 없어(v1.20.0 `Cargo.toml` 읽음, 프로브 `facts/qdrant_facts.py`) 한국어 형태소가 없고 저장소가 둘이다.
- 탈락: pg_bigm(형태소 없음), VectorChord·pgvectorscale(pgvector 위의 색인이라 나중에 끼울 수 있어 보류), Milvus(528MB + etcd + MinIO, 단독 구성의 최소 메모리 8GB는 Milvus 문서의 요구 사양 읽음), Elasticsearch(삼중 라이선스), Meilisearch 단독(벡터 저장소로서의 공개 수치 부족), Typesense(GPL), Vespa·LanceDB·Chroma.

## Consequences

- 나중에 다른 벡터 DB로 바꾸는 조건 셋을 지킨다. 응용 층은 벡터와 키워드를 `VectorIndex` 포트(ADR 0007)로만 다루고 pgvector용 SQL은 어댑터 하나에만 둔다. 조각의 본문, 위치, 임베딩 벡터는 엔진과 상관없이 PostgreSQL의 조각 표에 원본으로 남아 엔진을 바꿀 때 다시 파싱하거나 임베딩하지 않고 옮겨 넣기만 한다. 바꿀 때 새로 드는 것은 어댑터, 두 저장소 사이의 outbox 표와 재시도·주기 대조, 결과의 접근 그룹 재검사, 두 번째 백업, compose 항목이고, 잃는 것은 한 트랜잭션이다. 검색 도구 형식과 수집 API의 계약은 바뀌지 않는다.
- `ts_rank`에는 IDF가 없어 BM25가 아니다. 검색 품질은 search-eval의 적중률 보고서가 재고, 모자라면 키워드 엔진만 E의 길로 바꾼다.
- Kiwi 모델(kiwipiepy_model, 88MB)이 서버와 작업자 이미지에 든다. 토크나이저 판은 색인 판의 요소라(ADR 0008) 바뀌면 키워드 열을 다시 만든다.
- 좁은 필터에서 HNSW가 k개를 못 채우는 경우의 반복 스캔과 정확 스캔 분기는 명세가 정한다(어림).
- 샤딩이 없다. 노드 하나의 규모(설치 하나가 조직 하나, `docs/PRD.md`)를 전제한다.

## 이력

### 2026-11-10 부분 HNSW 색인은 색인 판 단위이고 벡터 열은 차원 없는 `vector`에 캐스트 표현식으로 색인한다

명세(`.scratch/core/spec.md`)가 정했다. 본문의 "지식베이스마다 부분 HNSW 색인(`WHERE kb_id = …`)"은 색인 판(ADR 0008) 단위가 된다. 재색인 동안 지식베이스 하나에 옛 판과 새 판의 조각이 나란히 있고 모델이 다르면 차원도 다를 수 있어, 조각 표의 벡터 열은 차원을 적지 않은 `vector`로 두고 색인 판마다 `CREATE INDEX … USING hnsw ((embedding::vector(D)) vector_cosine_ops) WHERE index_version_id = …`로 건다. 질의도 같은 캐스트로 쓴다. pgvector v0.8.7 README가 차원이 다른 벡터를 한 열에 두는 방법으로 적은 문장(842행, 차원 없는 열에 `(embedding::vector(3))` 표현식과 `WHERE (model_id = 123)`을 함께 건 예)을 프로브 `facts/pgvector_readme_facts.py`로 대 봤다. 검색은 현재 판만 보므로 부분 색인의 조건과 질의의 `WHERE`가 같다. 반복 스캔은 필터가 있을 때 `SET LOCAL hnsw.iterative_scan = relaxed_order`로 켜고, `hnsw.ef_search`는 후보 수(기본 50)로 올린다(기본 40이면 결과가 40개로 잘린다. 같은 README 935행). 정확 스캔 분기는 첫 판에 두지 않고, 그 필요는 search-eval의 적중률 보고서가 재고 나서 정한다.
