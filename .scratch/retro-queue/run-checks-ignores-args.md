# run-checks-ignores-args: `tools/run_checks.py`가 `--help` 같은 인자를 읽지 않고 검사 전체를 띄워, 검사 목록만 보려던 세션이 검사를 돌렸다

**상태:** 열림
**어디로:** `tools/run_checks.py`(`--help`나 알 수 없는 인자를 받으면 검사를 띄우지 않고 한 줄 사용법과 검사 목록을 찍고 끝낸다). 인자를 받은 도구가 크게 다르게 반응하는 같은 꼴은 `mutate-usage-dump`가 `tools/mutate.py`에서 다룬다
**승인:** 자체 승인 2026-11-24, 1회차(더하는 것이라 다섯 번째에 반영한다. 띄운 검사를 `TaskStop`으로 멈췄고 남은 프로세스가 없어 손상이 아니다), 일지 2026-11-24-1554-docs-only-six-state-tests.md, ADR 불필요

docs-only-six-state-tests 세션이 `DOC_STATE_TESTS` 목록을 확인하려고 `uv run python tools/run_checks.py --help`를 쳤다. 그 러너는 인자를 읽지 않아 검사 전체(pytest 포함)를 띄웠고, 돌기 시작한 것을 바로 `TaskStop`으로 멈췄다. 멈춘 뒤 남은 프로세스가 없는 것을 확인했다. 잃은 것은 호출 한 번과 확인이고 데이터는 잃지 않았다. 그 세션은 이후 목록을 `python -c`로 상수만 읽어 본다.
