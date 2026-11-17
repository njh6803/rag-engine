# gate-pipe-read-status: `hook_bash_gate_pipe`가 게이트 바로 뒤에서 `$?`를 이미 읽은 체인에서도 뒤의 다른 명령의 `$?`에 경고한다

**상태:** 닫힘 (.scratch/harness/issues/gate-pipe-read-status.md, 2026-11-13, `_exit_code_warnings`가 게이트 바로 다음 조각에 `$?`가 있으면(`;`·개행·`||`로 이어진 읽기만 센다. `&&` 뒤의 읽기는 게이트가 실패하면 건너뛰어지고 `&` 뒤의 `$?`는 백그라운드 기동의 0이라 뺀다) 그 게이트를 읽힌 것으로 세어 뒤쪽 `$?`의 경고 후보에서 뺐다. 읽히지 않은 게이트(`pytest; echo done; echo $?`)는 계속 경고하고 시험으로 고정했다)
**어디로:** `tools/hook_bash_gate_pipe.py`의 `_exit_code_warnings`와 `tests/tools/test_hook_bash_gate_pipe.py`
**승인:** 사용자 승인 2026-11-09, 5회차(고침이라 문턱 없이 반영한다), 일지 2026-11-09-1221-kickoff.md, 2026-11-09-2125-core-design.md, 2026-11-10-2047-core-01-test-db-runner.md(4·5회차: 같은 세션에서 `ruff check . > 파일; echo ruff=$?; plan_table.py > 파일; echo plan=$?`의 둘째 `$?`에 다시 경고가 떴다), ADR 불필요

`gate; echo "a=$?"; other; echo "b=$?"`처럼 게이트의 `$?`를 바로 뒤에서 읽은 뒤 게이트가 아닌 명령의 `$?`를 읽으면, 판정(`$?` 앞에 게이트가 있고 `$?` 바로 앞 조각이 그 마지막 게이트가 아니면 경고)이 둘째 `$?`를 게이트의 결과로 읽은 것으로 본다. 킥오프 8단계에서 Bash 호출 셋에 경고 네 건이 떴다(세션 기록으로 셌다). 고칠 때 `pytest; echo done; echo $?`처럼 게이트의 `$?`를 읽지 않은 체인은 계속 경고하는지 시험으로 고정한다.
