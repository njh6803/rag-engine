# 01: 포트 둘: 진단용 검색 `diagnose_candidates`와 판정기 `RelevanceJudge`

**What to build:** 평가가 실제 검색과 같은 SQL 뼈대로 단계별 순위를 받을 수 있게 `VectorIndex`에 진단용 메서드를 더하고, LLM 관련성 판정기의 포트를 `domain`에 둔다. 이 기능의 첫 티켓이고 계약(포트)을 세워 다른 티켓을 막는다(명세 Further Notes의 순서 항목, ADR 0007 Consequences). 평가 도구도 Claude 어댑터도 아직 없으므로, PostgreSQL 어댑터의 시험이 이 티켓의 바깥 표면이다. 포트의 이름은 ADR 0007 이력 2026-11-13에 이미 들어 있다.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `domain`에 `SearchDiagnosis`(`is_current`와 줄의 목록)와 그 줄(`SearchHit`에 `ordinal`, `vector_rank`, `keyword_rank`, `fused_rank`를 더한 것)을 두고, `VectorIndex`에 `diagnose_candidates(SearchQuery, exact)`를 더한다(명세 "진단용 검색과 단계"). 줄은 벡터 후보와 키워드 후보의 합집합 전부이고(많아야 후보 수의 두 배), `fused_rank`는 그 합집합 안에서 RRF 점수 순으로 매긴 1부터의 순위다. RRF 점수가 같은 줄의 순서는 `search_candidates`와 같은 규칙으로 끊는다.
- [ ] PostgreSQL 어댑터: 벡터 쪽과 키워드 쪽의 CTE, 필터와 그룹 집합의 조건, RRF 점수의 식을 짓는 함수를 하나로 두고 `search_candidates`와 `diagnose_candidates`가 함께 쓴다. 두 문장이 다른 곳은 합친 뒤의 자르기와 마지막 `SELECT`뿐이다. `SET LOCAL hnsw.ef_search`와 `hnsw.iterative_scan`도 같은 규칙으로 건다. `exact`가 참이면 같은 트랜잭션에서 HNSW 색인을 쓰지 않는 계획(`SET LOCAL enable_indexscan = off` 같은)으로 같은 SQL 글을 돌린다(명세의 `[사용자 선택]` 정확 스캔 항목, ADR 0018 이력 2026-11-13 "평가는 후보를 정확 스캔으로 뽑고, 추론 기록의 해시가 바뀌면 승인을 받는다").
- [ ] 어댑터 대조 시험: 같은 질의에서 `diagnose_candidates`(`exact` 거짓)의 `fused_rank`가 후보 수 이하인 줄이 `search_candidates`의 후보와 순서, 조각, RRF 점수까지 같다. 키워드가 빈 질의, 필터가 있는 질의, 벡터나 키워드 한쪽에만 든 조각이 있는 질의를 모두 본다. 선례는 `tests/adapters/test_vector_index_chunks.py`다.
- [ ] 어댑터 시험: `exact`가 참일 때의 계획에 판의 HNSW 부분 색인이 없고 거짓일 때는 있다(EXPLAIN. 선례는 `tests/adapters/test_vector_index_chunks.py`의 계획 시험이고, 어댑터가 시험용으로 계획을 글로 내는 메서드를 두어 판의 HNSW 부분 색인 이름을 본다. 같은 트랜잭션의 `SET LOCAL`이 계획에 걸리게 짓는다). `exact`가 참인 결과의 `vector_rank`가 거리 순과 같다. 질의한 판이 현재 판이 아니게 되면 `is_current`가 거짓이다.
- [ ] `domain`에 `RelevanceJudge` Protocol을 둔다. 메서드는 `judge(query, text)` 하나이고 관련 있으면 참을 돌려준다. 다시 해 볼 만한 실패는 `TransientFailure`, 그 밖은 `PermanentFailure`로 올린다는 것을 독스트링에 적는다(명세 "LLM 관련성 판정"). 시험 지원에 가짜 판정기를 둔다. Claude 구현은 12다.
- [ ] 검사 넷이 초록이다.
