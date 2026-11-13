# docs-only-commit-full-pytest: 문서와 프로브 출력만 바꾼 커밋도 pre-commit이 전체 pytest를 돌아 커밋 시도마다 11~16분을 기다렸다

**상태:** 열림
**어디로:** `tools/run_checks.py`(pre-commit의 `parallel-checks`). 스테이징된 파일이 문서 경로뿐이면 `.scratch`와 `docs`를 읽는 저장소 상태 시험(`tests/test_plan_status.py` 등)만 돌게 좁힌다. 게이트를 좁히는 일이라 남길 시험의 목록과 ADR이 필요한지는 반영하는 chore가 정한다(`docs/constitution/operations.md`의 가드레일)
**승인:** 사용자 승인 2026-11-13, 1회차(게이트를 좁히는 것이라 retro가 넘겼고 사용자가 대기열에 두기로 답했다. 더하는 것과 같이 다섯 번째에 반영한다), 일지 2026-11-13-1716-search-eval-tickets.md, ADR 필요 여부는 반영할 때 정한다
