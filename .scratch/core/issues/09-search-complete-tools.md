# 09: 검색의 완성: 리랭크, 필터, 시간 제한, `get_document`, `list_knowledge_bases`

**What to build:** MCP 클라이언트가 그룹과 갱신일 기간으로 결과를 거르고, 리랭커가 순서를 고친 결과를 받는다. 조각만으로 모자라면 `get_document`로 문서 정보와 전문을 읽고, `list_knowledge_bases`로 어디에서 찾을지 고른다. 도구 셋의 출력과 오류가 계약 시험으로 고정되고, 검색은 지연만 로그에 남긴다.

**Blocked by:** 07 (첫 왕복)

**Status:** ready-for-agent

- [ ] TEI 리랭커 어댑터(`Reranker`): 끝점마다 `/info` 확인(지식베이스 설정의 리랭커 모델), 요청 칸(`query`, `texts`, `truncate: true`, `truncation_direction: "Right"`, `raw_scores: false`, `return_text: false`), `RAG_TEI_BATCH_SIZE`개씩 나눈 묶음(`max_client_batch_size`가 더 작으면 그 값)과 점수 합치기(명세 "임베딩 서버와 리랭커 어댑터" 절). `texts`는 06의 글 짓기 함수가 지은 글이다.
- [ ] `search`의 다섯째 단계: 지식베이스에 리랭커가 있으면 후보 전부를 리랭크해 점수 순으로 바꾸고, 없으면 RRF 점수를 쓴다. 리랭커가 실패하거나 설정 불일치면 RRF로 대체하지 않고 `search_unavailable`이다.
- [ ] 필터: `groups`(없는 그룹 이름은 오류가 아니고 아무 문서에도 맞지 않는다), `updated_after`(포함)·`updated_before`(제외), 오프셋이 없거나 읽을 수 없는 시각과 빈 `query`·범위 밖 `top_k`는 `invalid_argument`. 필터는 벡터·키워드 두 쪽의 `WHERE`에 같이 들고, 필터가 있으면 `SET LOCAL hnsw.iterative_scan = relaxed_order`를 더한다. 지식베이스 그룹 집합의 방어 조건은 필터로 세지 않는다(명세 "검색 흐름" 절).
- [ ] 전체 시간 제한 `RAG_SEARCH_TIMEOUT_SECONDS`를 넘으면 `search_unavailable`. 로그 이벤트 `search`는 임베딩·SQL·리랭크 지연과 전체 지연만 싣는다(질의 글, 지식베이스 이름, `top_k`, 후보 수, 결과 수를 싣지 않는다. ADR 0004).
- [ ] `get_document`(명세 "MCP 도구" 절): 출력 칸 전부, 토큰 범위 안 지식베이스만의 `chunk_counts`, `include_text`면 블록 글을 빈 줄로 이은 `text`(파싱 결과가 없거나 그 내용 해시가 문서의 것과 다르면 null), 지워진 문서와 범위 밖 지식베이스에만 든 문서는 `document_not_found`.
- [ ] `list_knowledge_bases`: `name`, `description`, `document_count`(그 지식베이스 그룹 집합의 지워지지 않은 문서 수. 색인 상태와 상관없다), `is_default`, 토큰 범위 밖은 목록에서 뺀다.
- [ ] 도구 오류는 `isError` 결과의 JSON 글 하나(`type`, `title`, `status`, `code`, `request_id`)이고 코드는 `knowledge_base_not_found`, `document_not_found`, `invalid_argument`, `search_unavailable`, `internal_error` 다섯이다. `detail`에 질의나 문서 내용을 넣지 않는다.
- [ ] 계약 시험(`tests/contract/`): 도구 목록이 셋이고 모두 읽기 전용 표지(읽기 전용, 파괴적이지 않음, 멱등, 열린 세계 아님)가 있으며 outputSchema에 `format_version`이 있다(스토리 23, 42). 세 도구의 결과가 스키마와 `"1.0.0"`에 맞는다.
- [ ] 시험: 스토리 4(메타데이터와 갱신일이 결과의 `metadata`·`updated_at`에 실리고, 메타데이터·갱신일만 바꾼 `unchanged` 수집 뒤의 검색이 새 값을 낸다), 17(필터와 `iterative_scan`), 20(리랭커가 순서를 바꾸고, 실패하면 `search_unavailable`), 21, 22, 26(도구 오류 코드마다 한 사례), 27(범위 밖 지식베이스가 `chunk_counts`와 목록에 없다), 37(수집·검색·작업의 로그에 질의 글, 문서 글·키·제목, 토큰 원문이 없다). 임베딩 끝점 `/info`의 모델 불일치가 검색의 `search_unavailable`을 낸다. 판이 전환되는 사이의 검색이 둘째 단계부터 한 번 다시 하고, 다시 해도 아니면 `search_unavailable`이다(가짜 포트). 지운 문서의 갈래(`get_document`의 `document_not_found`, `document_count`에서 빠짐)는 삭제가 생기는 11이 시험한다.
- [ ] 위 가짜 포트 시험이 쓰는 메모리 안 가짜 포트는 `tests/` 쪽에 두고, 뒤 티켓(10~15)이 넓혀 쓴다. 가짜는 `app`의 동시성 교차와 실패 분류 시험에만 쓴다(명세 "포트 열셋과 그 값" 절, Testing Decisions).
- [ ] 검사 넷이 초록이다.
