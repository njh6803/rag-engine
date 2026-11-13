# scratch-compose-syntax-check: 프로브 폴더에 커밋한 compose 파일의 구문 오류를 아무 검사도 보지 않아 PR 직전 리뷰가 잡았다

**상태:** 열림
**어디로:** `tools/run_checks.py`의 `CHECKS`(저장소가 추적하는 `compose*.yml`과 `.scratch/**/compose*.yml`을 `docker compose -f <파일> config --quiet`로 판정하는 검사. 이 저장소에는 `compose.test.yml`도 있어 같은 검사가 그 파일도 지킨다)
**승인:** 자체 승인 2026-11-13, 1회차(더하는 것이라 다섯 번째에 반영한다. 병합 전에 PR 직전 `bug-perf-review`가 잡았으므로 손상이 아니다), 일지 2026-11-13-0615-search-latency-probe.md, ADR 불필요

`search-latency/compose.yml`의 머리 주석을 고치며 한 줄을 둘로 갈랐는데 둘째 줄에 `#`를 붙이지 않아 YAML이 깨졌다(`docker compose config --quiet`가 종료 코드 1). 셀프 리뷰 두 축과 ruff, pyright, pytest 어느 것도 이 파일을 보지 않아, PR 직전 `bug-perf-review`가 `docker compose config`를 직접 돌려서야 나왔다. 검사 러너에 compose 구문 판정이 없는 것이 빈틈이다. docker가 없는 환경에서 건너뛸지는 반영할 때 정한다(환경 부재로 건너뛴 시험은 초록이 아니라는 원칙 I을 같이 본다).
