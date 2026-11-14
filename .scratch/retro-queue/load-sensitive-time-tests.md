# load-sensitive-time-tests: 시간 단언 시험이 사례마다 다른 자리에서 부하에 빨개져 pre-commit이 매번 길어진다

**상태:** 열림
**어디로:** `tests/app/test_job_lease.py`와 `tests/contract/test_search_complete.py`(두 사례의 시험)와 `.claude/rules/tests.md`(시간 단언 규칙이 원천이다. 사례 하나씩 고치지 않고 종류 전체를 없애는 고침 하나를 정한다. 게이트를 느슨하게 하는 길은 사용자에게 넘긴다)
**승인:** 자체 승인 2026-11-14, 1회차(끝이 열린 결함 종류라 셋째 사례부터는 사례를 고치지 않는다. 사례는 닫힌 `token-expiry-test-load-margin`, 열린 `serve-startup-test-load-margin`, 이 세션의 둘로 넷이다. 커밋이 만들어지지 않았을 뿐 잃은 작업이 없어 손상이 아니다), 일지 2026-11-14-2356-search-eval-09-public-docs-documents.md, ADR 불필요

search-eval 09의 법령 커밋을 pre-commit이 처음 돌릴 때 전체 pytest(25분 41초)가 3,983개 통과, 2개 실패였다. `tests/contract/test_search_complete.py::test_리랭커가_순서를_바꾸고_점수는_리랭크_점수다`는 MCP 호출의 `httpx2.ReadTimeout`으로, `tests/app/test_job_lease.py::test_임대를_잃은_것이_드러나면_처리를_멈추고_문서에도_작업_행에도_쓰지_않는다`는 `time.monotonic() - started < 5`가 7.8초로 실패했다. 이 변경은 코드를 바꾸지 않았고, 두 시험만 따로 돌리면 3분 6초 안에 통과했다(`RAG_TEST_DATABASE_URL`을 주고 `-p no:xdist`). 같은 PC에서 GPU 색인과 다른 세션의 검사가 돌고 있었다(부하는 재지 않았다). 첫 실패 뒤 커밋을 다시 돌려 초록이 되기까지 약 25분을 더 썼다.

같은 종류의 사건이 사례마다 다른 시험에서 나온다. 사례를 하나 더 고치는 것은 다음 사례를 찾는 일이 되므로, 이 항목은 종류를 다룬다. 길은 둘이다. 시간 단언을 신호를 기다리는 모양으로 바꾸거나 상한을 홀로 돌린 시간의 배수로 두는 규칙을 시험 전체에 적용하는 것이 하나이고, 이 값을 받아들인다고 일지에 적고 닫는 것이 다른 하나다. 혼자 다시 돌려 지나가면 막지 않기처럼 게이트를 느슨하게 하는 길은 넘김이다.
