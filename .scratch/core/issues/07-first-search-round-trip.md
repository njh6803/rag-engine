# 07: 첫 왕복: DOCX 수집, 작업자 한 번 돌기, MCP `search`

**What to build:** 문서 담당자가 DOCX 문서를 수집 API로 넣고 작업자가 한 번 돌면, MCP 클라이언트가 같은 서버의 `/mcp`로 `search`를 불러 근거 위치·갱신일·점수가 붙은 조각을 받는다. 수집이 도는 동안의 검색은 옛 조각을 그대로 본다. core의 첫 끝에서 끝까지 길이다.

**Blocked by:** 05 (수집 API), 06 (TEI·Kiwi·청킹)

**Status:** ready-for-agent

**03이 넘긴 것:** `PostgresVectorIndex`에 판의 HNSW 부분 색인 만들기(`create_version_index`, 색인 이름은 `version_index_name`)만 있고 조각 쓰기(`replace_chunks`)와 검색 질의는 없다. 색인 상태는 05, `delete_chunks`는 10·11, `archive_chunks`는 11이 처음 부를 때 구현한다(05의 메모). 질의는 색인과 같은 캐스트 `embedding::vector(D)`를 써야 그 색인을 탄다(명세 "데이터 모델과 스키마"). 첫 판의 색인이 카탈로그에 있음은 03이 시험했고, 벡터 질의가 그것을 쓰는지(EXPLAIN)는 이 티켓이 본다.

**06이 넘긴 것:** 조각 글은 `ChunkDraft`의 두 칸이 가른다. `text`는 조각 글이고 검색 결과와 `chunks.text`에 들어간다. `index_text`는 임베딩과 키워드에 넣을 글(절 경로 줄, 빈 줄, 조각 글)이고 청커가 `compose_index_text`로 이미 지었다(06이 요구한 "이 함수만 쓴다"는 이 경로로 지킨다). 절 경로가 상한의 4분의 1을 넘으면 줄인 경로로 지은 글이라 `location.section`으로 다시 지으면 다를 수 있으니, 다시 부르지 말고 그대로 쓴다. 이 글을 `chunks`에 남길지, 14의 키워드 재생성과 09의 리랭크가 어떻게 되짓는지는 07이 정해 14와 09 티켓에 적는다. `token_count`는 `index_text`의 토큰 수에 특수 토큰 수를 더한 값이다. 임베딩은 `Embedder.embed(index_texts)`, 키워드는 `adapters.kiwi.tokenize_keywords(index_text)`(포트 쪽 이름은 `KeywordTokenizer`)에 `index_text`를 넣고, 질의도 같은 함수로 센다. 청커는 `chunker_for(config.strategy)`로 고르고 `Chunker.chunk(blocks, config, tokens)`의 `tokens`에는 `Embedder`를 그대로 넘긴다(`Embedder`가 `TokenMeter`를 겸한다). `TeiEmbedder`는 끝점마다 하나이고 첫 호출에서 `/info`를 확인하므로 작업자가 판마다 하나를 만들어 재사용한다. 기존 `TokenCounter` 포트는 `TokenMeter`로 바뀌었다.

- [ ] 작업자의 한 번 돌기 입구와 작업 꺼내기(`FOR UPDATE SKIP LOCKED`, `queued`이고 `run_after`가 지난 것 또는 임대가 끝난 `running`, 시도 횟수 +1, 올린 세대 비움, `leased_until`). 임대 연장·인수의 완성은 13이다.
- [ ] `index_document`의 네 단계(명세 "수집 파이프라인과 작업" 절): 첫째(지워진 문서는 성공, 세대 올림, 작업 행 조건), 둘째(파싱 필요 판정과 파싱 결과 행, 문서 상태 `parsed`), 셋째(살아 있는 판을 대상 판으로 읽어 판마다 청킹·임베딩·키워드, 세대 대조, 옛 조각을 지우고 새 조각과 복사 칸, 색인 상태 `indexed`), 넷째(`succeeded`). 셋째 단계가 문서 단위 원자 교체를 보장한다(ADR 0008). 전환 검사는 여기서 부르는 자리만 두고 14가 채운다.
- [ ] 파서 레지스트리가 entry point 그룹 `rag_engine.parsers`에서 파서를 로드하고(ADR 0012), 파싱은 spawn한 자식 프로세스에서 한다(파서 이름, 원본 경로, 한도를 넘긴다). 한도와 실패 분류의 완성은 08이다.
- [ ] DOCX 파서(python-docx): 제목 스타일은 제목 블록(수준), 문단, 표 블록(행마다 한 줄, 칸은 ` | `). 픽스처 DOCX는 시험이 만든다.
- [ ] MCP `search`(명세 "검색 흐름"·"MCP 도구" 절. 리랭크와 필터는 09): 지식베이스 고르기(없거나 토큰 범위 밖이면 `knowledge_base_not_found`), 현재 판이 없으면 빈 결과, 판에 적힌 끝점·모델로 질의 임베딩, SQL 하나의 벡터·키워드 후보와 RRF, 같은 문장에서 판이 아직 `current`인지 보고 아니면 둘째 단계부터 한 번 다시, `SET LOCAL hnsw.ef_search`, 결과 칸 전부와 `format_version`.
- [ ] 벡터 질의가 03이 만든 첫 판의 HNSW 부분 색인을 쓰는 것을 EXPLAIN으로 본다(같은 캐스트 `embedding::vector(D)`). 준비문의 일반 계획도 본다. psycopg는 한 연결에서 같은 질의를 `prepare_threshold`(기본 5)번 넘게 돌리면 준비문으로 만들고(psycopg 3 문서의 Prepared statements 절과 connections API), PostgreSQL은 `plan_cache_mode`가 `auto`면 준비문의 처음 다섯 번을 사용자 지정 계획으로 돌린 뒤 일반 계획을 고를 수 있다(PostgreSQL 18 문서 PREPARE). 그래서 몇 번 돌린 EXPLAIN에는 일반 계획이 보이지 않으므로 `EXPLAIN (GENERIC_PLAN)`이나 `plan_cache_mode = force_generic_plan`으로 직접 본다. PostgreSQL 18 문서의 부분 색인 절(11.8)은 술어를 계획 시점에 맞추므로 매개변수 조건은 부분 색인을 쓰지 못한다고 적는다. 일반 계획이 `index_version_id = $1` 조건으로 부분 색인을 쓰지 못하면, 검색 질의가 일반 계획으로 돌지 않게 하는 길(그 질의를 준비문으로 만들지 않거나 검색 트랜잭션에서 사용자 지정 계획을 강제한다)을 골라 어댑터 시험으로 고정하고, 고른 길과 근거를 일지와 명세 검색 흐름 절에 적는다. 명세 검토가 재지 못한 것이다(일지 `docs/journal/2026-11-10-1828-core-tickets.md`).
- [ ] 시험: 수집 → 작업자 한 번 → `search`의 왕복(DOCX), 작업 전에는 옛 글·작업 뒤에는 새 글(스토리 24, 25), 스토리 12~16, 18, 19. 계약 시험에 `search` 결과가 출력 스키마와 `"1.0.0"`에 맞음과 범위 밖 지식베이스의 `knowledge_base_not_found`를 더한다(`tests/contract/`).
- [ ] 어댑터 시험: RRF SQL의 순위(벡터와 키워드 한쪽에만 든 후보도 합쳐진다).
- [ ] 수집 요청 ID가 작업자 로그의 `request_id`로 이어진다(스토리 38). 작업자의 로그 이벤트 `job_started`·`job_finished`는 명세 "로그, 요청 ID, 지연 기록" 절의 칸(파싱·임베딩·쓰기 지연 포함)을 싣고, 문서의 키와 제목은 싣지 않는다.
- [ ] 검사 넷이 초록이다.
