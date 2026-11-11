# precommit-mutations-after-tests: pre-commit이 6분짜리 `parallel-checks`를 돌린 뒤에야 1초 안 걸리는 변이 표 검사가 실패를 알린다

**상태:** 열림
**어디로:** `.pre-commit-config.yaml`(훅 순서. 몇 초 안에 끝나는 `check-mutations`·`markdown tables`·`line separators`를 `parallel-checks` 앞에 둔다)
**승인:** 자체 승인 2026-11-11, 2회차(훅 순서를 바꾸는 더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-11-1530-core-10-ingest-updates-group-requeue.md, 08 일지 2026-11-11-1328-core-08-parsers-isolation.md가 같은 사건을 적었다. ADR 불필요

core 10 구현 세션의 첫 커밋 시도에서 `parallel-checks`(`tools/run_checks.py`의 `CHECKS`, 이 세션에서 361초)가 모두 통과한 뒤에야 `check-mutations`가 변이 표 둘(`first_round_trip_mutations.toml`, `ingest_mutations.toml`)의 원문이 이 커밋에 깨졌다고 알렸다. 고친 뒤 커밋을 다시 시도해 `parallel-checks`가 283초 더 돌았다. 같은 사건이 core 08 일지에도 있다(07의 변이 표 둘). 변이 표 검사는 staged 파일만 읽어 1초 안에 끝나므로 앞에 두면 실패가 6분 일찍 온다. 잃은 데이터는 없고 시간만 썼다.
