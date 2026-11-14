# surface-tests-after-implementation: 느린 표면 시험을 구현 뒤에 써서 시험 먼저(원칙 I)의 순서를 어긴다

**상태:** 열림
**어디로:** `.claude/skills/implement/SKILL.md`(시험을 먼저 쓰는 단계에 DB와 TEI 스텁을 붙이는 표면 시험도 구현 전에 쓰고, 구현이 없어 빨강인 것을 한 번 실행해 본다고 못 박는다. 검사로는 한 커밋 안의 작성 순서를 가를 수 없어 지침이 가장 높은 층이다)
**승인:** 자체 승인 2026-11-14, 3회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-14-1438-search-eval-04-fast-run-report.md(1회차: 회고 5에서 기각했다), 2026-11-14-1723-search-eval-05-full-run-rerank.md(2회차: 셀프 리뷰 표준 축이 Major로, 봇 claude-review가 Minor로 낸 사건이라 회차로 센다), 2026-11-14-1917-search-eval-06-miss-causes-and-breakdowns.md(3회차: `tests/tools/test_search_eval_misses.py`와 `test_search_eval_filter_probe.py`를 구현 뒤에 써 처음부터 초록이었다고 일지 검증 절이 스스로 적었다), ADR 불필요

search-eval 04와 05 모두 앱 시험은 시험을 먼저 썼지만 `tests/tools/test_search_eval_run.py`(테스트 PostgreSQL과 TEI 스텁을 붙이는 표면 시험, 한 번에 2~3분)는 구현 뒤에 써서 처음부터 초록이었다. 두 번 모두 빨강은 변이 표가 구현을 틀리게 했을 때 시험이 실패하는 것으로 대신 확인했다. 시험이 느리고 환경이 무거워 순서가 뒤로 밀리는 것으로 보이고, 잃은 것은 순서의 약속이다. 데이터는 잃지 않았다.
