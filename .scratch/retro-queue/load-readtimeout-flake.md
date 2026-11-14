# load-readtimeout-flake: 전체 시험을 병렬로 돌릴 때 기존 서버 시험 둘이 `ReadTimeout`으로 빨갛고 홀로 돌리면 초록이다

**상태:** 열림
**어디로:** `tests/contract/test_tool_errors.py`와 `tests/server/test_ingest_api.py`의 해당 시험(읽기 시간 제한이나 서버 기동 대기를 부하에 여유가 있게 고친다. 어느 시간 제한인지는 아직 재지 않았다. 같은 부하 시험 종류로 닫힌 `token-expiry-test-load-margin`이 있다)
**승인:** 자체 승인 2026-11-14, 3회차(3회차는 같은 PR의 두 번째 커밋 시도에서 pre-commit 전체 pytest가 낸 5건이다. `tests/test_serve_command.py`의 서버 기동 30초 초과 1건, `tests/contract/test_delete_restore.py` 2건, `tests/contract/test_first_round_trip.py` 2건으로, 그 파일 셋을 홀로 돌리니 19개 모두 초록이었다(3분 59초). 이 항목은 끝이 열린 결함 종류라 3회차부터 사례를 더 고치지 않고 종류 전체를 없애는 고침 하나를 하거나 받아들인다고 정한다. 둘 가운데 혼자 다시 돌려 지나가면 막지 않기는 게이트를 느슨하게 하므로 넘김이다. 이 판단은 다음 chore나 사용자에게 간다). 2회차까지의 내역: 2회차는 첫 커밋 시도의 `tests/contract/test_search_complete.py` 시험 둘이고 1회차는 `tests/contract/test_tool_errors.py`와 `tests/server/test_ingest_api.py`, 2회차는 같은 PR의 커밋 시도에서 pre-commit 전체 pytest가 낸 `tests/contract/test_search_complete.py`의 시험 둘이다. 고침이라 문턱 없이 반영한다. 이 PR은 기능 PR이라 다른 시험을 고쳐 싣지 않고 대기열에 둔다. 3회차부터는 사례를 고치지 않고 종류 전체를 없애거나 받아들인다), 일지 2026-11-14-2147-search-eval-12-relevance-judge-claude.md, ADR 불필요

search-eval 12의 변경을 담은 전체 `uv run pytest`(4162 passed)에서 `test_로그에는_질의와_문서의_글_키_제목과_토큰_원문이_없다`(`tests/contract/test_tool_errors.py`)와 `test_폼_칸의_키와_그룹과_메타데이터와_갱신일이_문서에_실린다`(`tests/server/test_ingest_api.py`)가 `ReadTimeout`으로 빨갰다. 둘 다 홀로 돌리니 초록이었다. 두 시험은 이 변경이 건드리지 않은 기존 시험이고, `origin/dev`에도 그 사이 들어온 커밋이 없어 상류가 이미 고친 것도 아니다. 서버를 띄우는 시험이 부하에서 읽기 시간을 넘긴다고 보이지만 원인은 재지 않았다. 잃은 것은 다시 돌린 시간이고 데이터는 아니다.

같은 PR의 첫 커밋 시도에서 pre-commit의 전체 pytest가 `tests/contract/test_search_complete.py`의 시험 둘을 `ReadTimeout`으로 빨갛게 냈다. 같은 PC에서 다른 세션의 xdist 작업자와 vitest가 CPU를 쓰고 있었고, 그 파일을 홀로 다시 돌리니 19개 모두 초록이었다(5분 6초). 시험 파일이 달라 서버를 띄우는 시험 일반이 부하에서 읽기 시간을 넘긴다는 추정이 힘을 얻는다.
