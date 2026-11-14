# gate-masked-by-echo-chain: 게이트 명령 뒤에 `; echo`를 이은 백그라운드 실행이 실패를 종료 코드 0으로 보고했다

**상태:** 열림
**어디로:** `tools/hook_bash_gate_pipe.py`(게이트 명령 뒤에 `;`나 `&&`로 이은 `echo`가 백그라운드 실행의 종료 코드를 가리면 알린다. 원천은 `CLAUDE.md` 환경 함정의 "파이프와 `&&`·`;` 체인 뒤의 `$?`는 마지막 명령의 종료 코드다"이고, 닫힌 `gate-pipe-read-status`가 같은 원리의 `$?` 읽기를 막았다)
**승인:** 자체 승인 2026-11-14, 6회차(`gate-pipe-read-status`의 6회차. 같은 원리의 지침을 어긴 사건이라 회차를 센다. 더하는 것이라 다섯 번째를 넘었으나 이 PR의 범위가 아니라 대기열에 둔다. 커밋이 만들어지지 않았을 뿐 잃은 작업이 없어 손상이 아니다), 일지 2026-11-14-2356-search-eval-09-public-docs-documents.md, ADR 불필요

search-eval 09의 법령 커밋을 `git commit -m ... > /dev/null 2>&1; echo started`로 백그라운드에 띄웠다. pre-commit이 실패해 커밋은 만들어지지 않았는데 앱은 "completed (exit code 0)"를 알렸고, 출력도 버려 실패의 까닭이 없었다. 뒤늦게 `git log`가 HEAD가 그대로임을 보여서야 알았고, 실패한 pytest의 출력을 보려고 커밋을 처음부터 다시 돌렸다(약 26분). 이번 꼴은 `$?`를 읽지 않아 기존 훅이 경고하지 않는다.
