# mutate-usage-dump: `tools/mutate.py`가 변이 파일 인자 없이 `--check`를 받으면 독스트링 전체를 찍어 세션이 300줄을 읽었다

**상태:** 열림
**어디로:** `tools/mutate.py`(변이 파일 인자가 없거나 선택 인자만 있을 때 독스트링 전체 대신 `사용:` 줄만 찍는다. `--help`는 이미 한 줄 메시지만 낸다)
**승인:** 자체 승인 2026-11-11, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-11-0314-core-05-ingest-api.md, ADR 불필요

core 05 구현 세션이 `uv run python tools/mutate.py --check --since origin/main`(변이 파일 인자를 빠뜨림)을 쳤고, 종료 코드 2와 함께 독스트링 약 300줄이 출력되어 그 파일을 통째로 읽었다. `--help`는 한 줄 메시지로 끝났으므로 같은 도구의 두 오류 출력의 크기가 다르다. 잃은 데이터는 없고 컨텍스트만 썼다. 같은 비용을 `tools/tidy_checkouts.py --help`로 겪은 사례가 `tidy-checkouts` 스킬에 적혀 있다(agent-os 대기열 271).
