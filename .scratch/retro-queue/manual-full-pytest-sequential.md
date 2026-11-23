# manual-full-pytest-sequential: 손으로 친 전체 pytest가 병렬 없이 돌아 47분 53초가 걸렸고, 같은 시험을 바로 뒤 커밋의 pre-commit은 병렬로 623.6초에 마쳤다

**상태:** 열림
**어디로:** `CLAUDE.md` 검증 명령의 테스트 줄(전체 스위트를 손으로 칠 때 `tools/run_checks.py`와 같은 `-n`을 붙이게 하거나, 다음이 커밋이면 pre-commit의 결과로 갈음한다는 `code-review` 6단계 5를 가리킨다). `pyproject.toml`의 pytest `addopts`로 옮길지는 반영하는 chore가 정한다
**승인:** 자체 승인 2026-11-18, 2회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-18-1444-glossary-release-names.md, 2026-11-22-0855-source-sync-02-skipped-documents.md, ADR 필요 여부는 반영할 때 정한다(ADR 0035가 검사 러너의 워커 수를 정했다)

이 세션은 문서와 주석만 바꾼 변경에서 `CLAUDE.md` 검증 명령대로 `uv run pytest -q`를 쳤다. 결과는 `4563 passed in 2873.66s (0:47:53)`이었고, 기다리는 동안 사용자가 끝났는지 물었다. 커밋 `25dfbe1`의 pre-commit에서는 검사 러너가 같은 시험을 xdist로 돌려 623.6초에 마쳤다(`tools/run_checks.py`의 `Check("pytest", …)`가 `-n`을 붙인다). 문서만 바꾼 커밋의 pre-commit이 전체 pytest를 도는 일은 대기열 docs-only-commit-full-pytest가 따로 센다.
