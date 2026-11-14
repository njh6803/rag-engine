# serve-startup-test-load-margin: `serve` 시작 시험의 30초 기한이 검사 러너의 전체 실행 부하에서 모자라 pre-commit이 빨갛다

**상태:** 열림
**어디로:** `tests/test_serve_command.py`(`STARTUP_TIMEOUT_SECONDS`를 그 시험만 홀로 돌린 시간의 넉넉한 배수로 올리거나 서버가 뜬 신호를 기다리는 모양으로 바꾼다. `.claude/rules/tests.md`의 시간 단언 규칙이 원천이고, 닫힌 `token-expiry-test-load-margin`과 같은 종류다)
**승인:** 자체 승인 2026-11-14, 1회차(고침이라 문턱 없이 반영한다. 커밋이 만들어지지 않았을 뿐 잃은 작업이 없어 손상이 아니다), 일지 2026-11-14-1917-search-eval-06-miss-causes-and-breakdowns.md, ADR 불필요

search-eval 06의 둘째 커밋을 pre-commit이 돌릴 때 `test_serve가_뜨면_JSON_Lines만_남기고_접근_로그에_쿼리_문자열을_싣지_않는다`가 "serve가 30초 안에 뜨지 않았다"로 실패했다(전체 pytest 1313초, 4139개 가운데 이 하나). 이 변경은 `serve` 경로를 건드리지 않았고 첫 커밋(24ef179)의 같은 시험은 통과했다. `tests/test_serve_command.py`만 홀로 돌리면 두 시험이 14초에 통과한다. 같은 시기에 다른 세션이 같은 PC에서 검사를 돌고 있어 부하가 겹쳤다고 본다(부하는 재지 않았다). 잃은 것은 약 22분이고 데이터는 아니다. 기준 브랜치는 이 시험을 고치지 않은 상태다(브랜치가 `origin/dev` 끝에서 땄다). `stale-branch-base-test-fix`와 달리 뒤처진 브랜치의 사건이 아니다.
