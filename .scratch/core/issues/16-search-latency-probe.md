# 16: 대상 사양에서 검색 지연 재기

**What to build:** 실제 TEI(CPU 이미지)와 표본 문서들로 동시 요청 여러 개의 검색 지연을 재서 프로브로 남기고, 그 결과로 어림 기본값(후보 수, TEI 배치 크기)을 정한다. core 계획(`.scratch/core/plan.md`) 수락 줄의 지연 측정이 이 티켓이고, 시험이 아니라 프로브다(명세 Testing Decisions).

**Blocked by:** 14 (재색인과 판 전환), 15 (조회와 `ingest` 명령)

**Status:** done

- [x] Docker에서 테스트 PostgreSQL과 TEI CPU 이미지 둘(임베딩 `BAAI/bge-m3`, 리랭커 `BAAI/bge-reranker-v2-m3`)을 띄우고, 표본 문서들을 `ingest --wait`로 넣는다. 띄우는 방법과 판을 프로브 독스트링에 적는다.
- [x] 동시 요청 여러 개(수와 질의 집합은 프로브가 정하고 적는다)의 `search` 지연을 `/mcp`로 재고, 단계별 지연(임베딩, SQL, 리랭크)은 `search` 로그 이벤트에서 모은다. 기계 사양(CPU, 메모리)을 출력에 적는다.
- [x] 스크립트와 출력을 `.scratch/core/probes/` 아래에 두고 README 표에 행을 더한다(`docs/agents/issue-tracker.md`의 프로브와 근거 절).
- [x] 잰 값으로 `RAG_SEARCH_CANDIDATES`(50)와 `RAG_TEI_BATCH_SIZE`(32)의 기본값을 바꿀지 정하고, 바꾸면 설정의 기본값과 명세의 설정 절을 같이 고친다(기본값은 계약이 아니라 설정이라 ADR이 없다. 명세 "설정" 절). 바꾸지 않아도 그 까닭을 일지에 적는다.
- [x] 표본을 수집하며 파싱 시간과 메모리도 같이 재어 파싱 한도 넷(1000쪽, 300초, 2GiB, 64MiB)이 표본을 막지 않는지 본다. 재지 않은 어림(백오프 밑수 30초 등)은 어림으로 남는다고 프로브 README에 적는다.
- [x] 검사 넷이 초록이다.
