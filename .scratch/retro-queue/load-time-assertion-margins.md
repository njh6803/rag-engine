# load-time-assertion-margins: 시간을 재는 시험이 변이 실행·서브에이전트와 겹친 부하에서 빨갛다

**상태:** 열림
**어디로:** 시간 단언의 상한을 시험을 홀로 돌린 시간의 넉넉한 배수로 정하는 보조 함수나, 실제 시간·기한을 재는 단언의 상한을 잡는 검사(`tools/check_*.py`)로 종류 전체를 없앤다. 또는 그 값을 받아들인다고 일지에 적고 닫는다. 게이트를 느슨하게 하는 길(혼자 다시 돌려 지나가면 막지 않기)은 넘김이다
**승인:** 자체 승인 2026-11-14, token-expiry-test-load-margin의 3회차(여러 곳에서 나는 같은 결함의 세 번째 사례라 사례를 고치지 않고 종류를 다룬다), 일지 2026-11-14-2016-search-eval-07-inference-records.md, ADR 불필요

search-eval 07 세션이 손으로 돌린 `tools/run_checks.py`(4132 passed, 2 failed)에서 `tests/app/test_job_lease.py::test_작업_담당_기록을_잃은_것이_드러나면_처리를_멈추고_문서에도_작업_행에도_쓰지_않는다`가 `assert time.monotonic() - started < 5`를 5.27초로 넘겨 빨갛고, `tests/tools/test_hook_push_behind_main.py::test_dev의_유무를_조회하다_시간을_넘기면_재지_않는다`도 빨갰다. 같은 때 변이 실행과 서브에이전트 둘이 돌았다. 두 시험을 단독으로 돌리면 통과했다(2 passed, 16.78초). `.claude/rules/tests.md`가 실제 시간을 재는 단언의 상한을 그 시험만 홀로 돌린 시간의 넉넉한 배수로 두라고 이미 정하지만, 이 둘의 상한이 홀로 돌린 시간의 배수로 정해졌는지는 재 보지 않았다. 잃은 것은 15분의 검사 러너 한 번이 준 거짓 빨강과 그것을 가리는 데 든 확인이다.

같은 세션의 첫 커밋 시도(pre-commit의 pytest, 4135 passed 1 failed)에서 `test_dev의_유무를_조회하다_시간을_넘기면_재지_않는다`가 다시 빨갰다. 까닭은 손으로 재현했다(커밋하지 않은 스크래치 스크립트). `subprocess.run(..., capture_output=True, timeout=0.0001)`은 부모가 `Popen` 직후 멈추지 않으면 `TimeoutExpired`를 내지만(5번 모두), 직후에 0.5초 멈추면 `git`이 이미 끝나 시간 제한이 걸리지 않고 정상으로 돌아왔다(5번 모두). 그 시험의 전제인 시간 제한을 `git`이 뜨기도 전에 넘길 값이라는 가정이 부하에서 부모가 멈추는 순간 깨진다. 시간의 상한이 아니라 시간 제한을 넘기는 쪽의 전제라 상한을 넉넉히 두는 길로는 닿지 않는다.

같은 세션의 둘째 커밋 시도에서는 반대로 `test_dev…`가 통과하고 `test_job_lease`의 같은 시험이 5.42초로 다시 빨갰다(`assert (302472.171 - 302466.75) < 5`). 그때 pre-commit의 pytest가 1426.94초였고(앞 시도는 869.73초) 부하의 까닭은 재 보지 않았다(나란히 도는 다른 세션의 검사가 겹쳤을 수 있다). 부하에 따라 빨간 시험이 바뀌는 모양이라 사례 하나씩 고치는 길이 닿지 않는다는 근거다.

search-eval 07의 `origin/dev` 병합 커밋도 두 시도에서 이 종류로 막혔다. 첫 시도(pre-commit의 pytest, 4207 passed 2 failed, 1356초)는 `tests/contract/test_reindex_switch.py`의 시험 둘이 MCP 클라이언트의 `ReadTimeout`으로 빨갰고, 그 파일만 단독으로 돌리면 8건이 모두 통과했다(175.51초). 둘째 시도(4207 passed 2 failed, 872.74초)는 `test_job_lease`의 같은 시험이 5.56초(`assert (318223.703 - 318218.14) < 5`)로, `test_serve가_뜨면…`이 "serve가 30초 안에 뜨지 않았다"로 빨갰다. 두 시도 사이에 빨간 시험이 모두 바뀌었다. 그때 CPU 사용률이 100%였고 다른 저장소(`C:\project\agent`)와 이 저장소의 형제 워크트리가 `tools/run_checks.py`를 번갈아 돌고 있었다(프로세스 목록을 손으로 봤다). 한가해지기를 30분씩 두 번 기다렸으나 끝내 오지 않았다.

같은 종류를 search-eval 09 세션이 `load-sensitive-time-tests`로도 올렸다(두 세션이 나란히 돌아 서로의 항목을 보지 못했다). 둘은 같은 `test_job_lease`의 5초 단언과 계약 시험의 `ReadTimeout`을 다룬다. chore가 반영할 때 두 항목을 하나로 묶어 종류 전체를 없애는 고침 하나를 정한다.
