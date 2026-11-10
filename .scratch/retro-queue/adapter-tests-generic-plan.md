# adapter-tests-generic-plan: 어댑터 시험이 연결을 새로 만들어 써서 준비된 문장의 일반 계획에서만 나는 결함을 PR 직전 리뷰까지 못 잡았다

**상태:** 열림
**어디로:** `tests/conftest.py`의 `engine` 픽스처와 시험용 엔진을 만드는 자리(시험 연결이 `plan_cache_mode=force_generic_plan`으로 열려 첫 실행부터 일반 계획을 밟게 하는 검사. 처방의 효과는 반영할 때 `tests/adapters/test_job_queue.py`의 열다섯 번 넣기 시험이 빨개지는지로 먼저 잰다)
**승인:** 자체 승인 2026-11-11, 2회차(더하는 것이라 다섯 번째에 반영한다. 첫 사건은 PR 직전 `bug-perf-review`가 잡았고 병합 전이라 손상이 아니다), 일지 2026-11-11-0314-core-05-ingest-api.md, 2026-11-11-0615-core-07-first-search-round-trip.md, ADR 불필요

core 05의 `PostgresJobQueue.enqueue`가 `ON CONFLICT`의 색인 추론 술어를 바인드 파라미터로 보냈다. psycopg가 같은 문장을 다섯 번 돌린 뒤 서버에 준비시키고 일반 계획이 부분 색인을 찾지 못해, 한 연결에서 수집이 열 번쯤 성공한 뒤부터 모든 수집이 500이 된다. 어댑터 시험은 시험마다 연결을 새로 만들어 이 결함을 밟지 못했고, 셀프 리뷰 두 축도 지나쳤다. 일지 회고 절에 사건의 경위가 있다. 이 결함은 린터와 타입체커가 판정할 수 없고 시험 설정이 가장 강제력이 높은 층이다.
