# gate-pipe-read-status: 게이트의 `$?`를 바로 읽은 체인의 뒤쪽 `$?`에 경고하지 않는다 · 2026-11-13

대기열 `gate-pipe-read-status`를 harness 티켓 `.scratch/harness/issues/gate-pipe-read-status.md`로 쓰고 반영한 기록이다. 브랜치는 `chore/gate-pipe-read-status`이고, `next-session` 지시문으로 연 새 세션이 `EnterWorktree`로 새 워크트리(HEAD가 `origin/dev`의 `defc690`과 같았다)에 들어가 했다. 제품 코드는 바꾸지 않았고, 훅 `tools/hook_bash_gate_pipe.py`와 그 시험만 고쳤다.

## 한 것

- `tools/hook_bash_gate_pipe.py`의 `_exit_code_warnings`가 `$?`마다 그 앞 어딘가의 마지막 게이트가 `$?` 바로 앞 조각이 아니면 경고하던 것을, 게이트의 `$?`가 이미 읽혔는지까지 보게 했다. 게이트 바로 다음 조각에 `$?`가 있으면 그 게이트는 읽힌 것이고, 그 뒤 게이트가 아닌 명령 다음의 `$?`는 그 명령의 종료 코드를 읽는 것이라 경고하지 않는다. 사건의 모양은 `ruff check . > 파일; echo ruff=$?; plan_table.py > 파일; echo plan=$?`다.
- 읽히지 않은 게이트(`pytest; echo done; echo $?`, `ruff && echo done; echo $?`)와 게이트 둘 가운데 앞쪽만 읽히지 않은 체인은 계속 경고하고 시험으로 고정했다.
- 게이트와 `&&`로 이어진 읽기(`pytest && echo $?; echo done; echo $?`)는 읽힌 것으로 세지 않는다. 게이트가 실패하면 그 읽기가 건너뛰어지고 이어지는 `echo done`이 종료 코드를 0으로 덮어쓴다. `_SEGMENT`에 캡처 그룹을 둬 조각과 경계를 번갈아 받고, 경계가 `&&`인 읽기는 뺀다(`_is_read`). 아래 "PR 직전 리뷰"가 낸 반례다. `||`로 이어진 읽기는 게이트가 실패해야 실행되므로 읽힌 것으로 센다.
- 독스트링의 판정 문장을 고치고, 못 보는 것에 거짓 음성 하나(`pytest; true $?; other; echo $?`는 조용하다. 게이트 다음 조각의 `$?`를 실제로 쓰는지는 보지 않는다)를 적어 시험으로 고정했다.
- 대기열 항목의 상태 줄을 `닫힘 (티켓 경로, 날짜, 한 것)`으로 고쳤다. 티켓은 `done`이다.
- `uv run python tools/plan_table.py`를 돌렸고 `.scratch/plan.md`는 바뀌지 않았다(harness 티켓은 전체 계획 표에 들지 않는다).
- 실제 실행: 훅 스크립트를 stdin 페이로드로 직접 돌렸다. 사건의 명령은 출력 0바이트(조용), `pytest; echo done; echo $?`와 `&&` 반례는 855바이트(경고)였다. 둘째 고침 뒤에 다시 돌려 같았다.

## 셀프 리뷰

`code-review` 두 축. base `defc690`, 커밋 0, 바뀐 추적 파일 셋과 미추적 하나(티켓). 표준 축은 Sonnet 5.5 / high, 명세 축은 이 세션의 모델로 돌았다.

- 표준 축: 문서화된 표준 위반 없음, Critical·Major 없음. 판단 항목 셋.
  - Mysterious Name(약함). `gates`가 이제 "아직 읽히지 않은 게이트"인데 이름이 그대로다. → 고쳤다. `unread_gates`로 바꿨다.
  - Duplicated Code(약함). `"$?"` 포함 검사가 `_exit_code_warnings`에서 여러 번 나온다. → 남겼다. 한 줄짜리 검사라 헬퍼로 올리면 읽는 비용이 더 든다. (뒤에 `&&` 고침으로 `_is_read` 헬퍼가 생겼고 새로 낸 검사만 그 안에 있다.)
  - Primitive Obsession(약함). 조각을 `str`과 인덱스로만 다룬다. → 남겼다. 이 함수 크기에서는 감수한다.
- 명세 축: Critical·Major 없음, 범위 넘침 없음. Minor 둘. 티켓이 든 `&&` 형태가 시험에 없었고, 시험의 사건 입력이 `plan_table.py` 원문이 아니라 `other_tool`이었다. → 둘 다 고쳤다. 시험에 `&&` 형태를 더하고 `plain` 입력을 `plan_table.py` 원문으로 바꿨다.
- 반영으로 새로 쓴 사실 문장(PR 직전 리뷰와 PR 봇이 겨냥할 것): 독스트링의 판정 문장(게이트 바로 다음 조각의 `$?`를 읽힌 것으로 센다), 못 보는 것의 `true $?` 문장, 뒤에 더한 `&&`·`||` 문장, 티켓의 What to build가 적은 `&&`·`||` 서술.

## 검증

- `uv run python tools/sibling_overlap.py`는 0이었다(새 번호 없음, 번호 겹침 없음, 함께 고친 파일 없음). `origin/dev`를 반영한 뒤에 다시 돌려도 같았다.
- 손으로 친 것: `uv run pytest tests/tools tests/test_plan_status.py`(백그라운드, 종료 0), `uv run pytest tests/tools/test_hook_bash_gate_pipe.py tests/tools/test_run_hooks.py`(고침마다, 종료 0), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `tools/check_type_escapes.py`, `tools/check_instructions.py`(첫 고침 뒤, 모두 0).
- 커밋 시도.
  - 첫 시도(커밋 전, 작업 트리에 스테이징한 상태): pre-commit 검사 러너의 pytest가 `1 failed, 3827 passed in 736.00s`였다. 빨간 것은 `tests/adapters/test_parse_runner.py::test_메시지를_보내다_멈춘_자식이_있어도_수신이_영영_막히지_않는다`(Windows 기대 `parse_failed`에 `parse_timeout`이 왔다)다. 이 변경은 `tools/`와 문서뿐이라 어댑터에 닿지 않는다. 그 시험만 홀로 돌려도 같은 값으로 실패했고(두 번, 이때 이 세션의 다른 시험 묶음이 CPU를 쓰고 있었다), 기준과 같은 트리(`defc690`)의 형제 워크트리 `14-reindex-version-switch`에서도 같았다. 시험은 고치지 않았다(원칙 I). 사용자에게 "별도 진단"과 "훅 우회 커밋" 가운데 물었고 사용자는 별도 진단을 골랐다.
  - 별도 진단은 [세션](#local_46d29bcd-e1d5-4140-ad4a-16d3412ade16)이 맡았다(그 세션의 보고, 이 세션이 코드나 프로브를 다시 읽지는 않았다). 시험의 Windows 기대가 자식 프로세스 기동 시간과 기한 2초의 경쟁에 기대고 있어 부하에서 `parse_timeout`이 나며, 제품 코드와 Python 판은 원인이 아니라고 했다. 시험의 기한을 Windows 30초, 리눅스 2초로 나눠 PR #36을 열었고, 사용자가 "CI 뒤 병합"으로 승인해 그 세션이 `11313d8`로 squash 병합했다(`gh pr view`로 `MERGED`와 병합 커밋을 이 세션이 확인했다). 앞서 이 세션이 "결정적으로 실패한다"고 한 것은 부하 아래에서만 본 값이라 정확하지 않았다.
  - 병합 뒤 `git fetch origin`과 `git merge --ff-only origin/dev`로 `defc690`에서 `11313d8`까지 반영했다(바뀐 30개 파일은 이 브랜치의 파일과 겹치지 않았다). 둘째 시도: pre-commit이 통과했고(종료 0) 커밋 `fa45426`이 만들어졌다. 제목이 73자라 첫 커밋 명령이 PreToolUse 훅(`hook_bash_commit_msg`)에 막혀 pre-commit을 돌기 전에 줄였다.
  - 이 일지와 `&&` 고침을 싣는 커밋은 pre-commit으로 갈음하고 결과는 PR 본문에 적는다.

## PR 직전 리뷰

`coderabbit-review` 서브에이전트(Sonnet)가 CodeRabbit CLI 0.7.5를 한 번 돌렸다. 명령은 `coderabbit review --agent --base-commit 11313d8643c355ea0a49741b2d81f01c5aad9a85`이고 종료 코드 0, 리뷰는 끝까지 돌아(`review_completed`) 지적 1건이었다. 좌석은 `Seat: not assigned`(`Plan: Free`)다. 리뷰한 파일은 넷(훅, 시험, 티켓, 대기열 항목)이다.

- 지적 1(Minor, 유효). 게이트 바로 다음 조각에 `$?`가 있으면 그 조각이 실제로 실행되는지 보지 않고 읽힌 것으로 센다. CodeRabbit이 든 예 `pytest; echo done; echo $?`는 오탐이다(이 입력은 고침 전후 모두 경고하고 시험이 고정한다). 진짜 반례는 `&&` 뒤의 읽기다. `pytest && echo $?; echo done; echo $?`가 새 판에서 조용해졌고 옛 판은 경고했으므로 이 변경이 만든 새 거짓 음성이다. 서브에이전트가 손으로 돌려 확인했고, 이 세션도 고침 전에 새 시험이 빨간 것을 봤다. → 고쳤다. 경계가 `&&`인 읽기는 읽힌 것으로 세지 않는다. 시험 `test_and_뒤의_dollar_question_…`을 더했고 독스트링과 티켓과 대기열 항목의 서술을 맞췄다.
- 서브에이전트가 직접 대 본 입력(손으로 돌림): 새로 조용해진 것 가운데 옳은 것은 `pytest; echo $?; echo $?`, `pytest; x=$?; echo $?`, `pytest; [ $? -ne 0 ] && echo bad; echo $?`, 두 게이트를 각각 바로 읽고 셋째 `$?`로 끝나는 체인 등이다. 거짓 음성으로 문서화된 것은 `pytest; ls $?; echo $?`다.
- CLI가 보지 못한 것은 이 절 뒤의 편집(`&&` 고침, 이 일지)이다. CLI에는 밀 주장을 넘기는 인자가 없어 위 "반영으로 새로 쓴 사실 문장"은 PR 봇이 본다.

## 회고

낸 후보 여섯. 승인 0, 기각 6, 넘김 없음.

1. pre-commit의 전체 pytest가 부하에서 시간 경쟁 시험(`test_parse_runner.py`) 하나로 빨개져 커밋이 막혔고, 사용자 결정과 별도 세션과 PR #36까지 가야 풀렸다. → 기각. 부하에서만 빨간 시간 시험은 닫힌 항목 `token-expiry-test-load-margin`이 받아들여 닫은 종류라 새 항목으로 잇지 않고 일지에만 적는다(`retro` 4단계의 끝이 열린 종류). 이번 사례는 원인이 부하 자체가 아니라 기동 경쟁이었고 시험의 기한을 고쳐 닫혔다. 형제 일지 `2026-11-13-1324-code-review-transition-crossing.md`가 같은 시험이 시도마다 빨간 것을 부하로 어림하고 기각했는데, 이번 진단이 그 어림을 그대로 맞다고 확인하지는 않는다(그 시도의 부하를 이 세션이 보지 않았다).
2. 커밋 제목 73자가 pre-commit을 돌기 전에 `hook_bash_commit_msg`에 막혔다. → 기각. 이미 있는 훅이 그 자리에서 막았다(대기열 `commit-msg-after-slow-checks`가 다루는 일을 그 훅이 막은 쪽으로 풀었다).
3. 새 시험을 기존 시험 한가운데에 끼워 넣은 편집 실수가 Pyright 진단으로 바로 드러났다. → 기각. 검사가 그 자리에서 잡았다.
4. `&&` 뒤 읽기의 거짓 음성을 셀프 리뷰 두 축이 놓치고 PR 직전 CodeRabbit이 잡았다. → 기각. 리뷰가 제 몫을 한 것이고 구현 때 실리는 지침을 어긴 사건이 아니라 새로 쓴 판정의 결함이다(반영으로 고쳤다). 못 보는 것을 시험으로 고정하라는 `.claude/rules/tools.md` 항목은 지켰고(`true $?`), 새 판정이 만든 퇴행은 그 항목의 대상이 아니다.
5. Grep 도구의 glob에 중괄호 부정 패턴(`!{…}`)을 줬다가 `.env`에 닿는다는 `hook_env_read`의 막음을 받았다. → 기각. 이미 있는 훅이 그 자리에서 막았다.
6. 복합 셸 명령(heredoc에 여러 명령)을 워크트리 가드가 거부해 명령을 나눠 다시 쳤다. → 기각. 앱 가드가 그 자리에서 막았고 든 비용은 호출 한 번이다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/main`을 붙인 것 모두 만료할 항목이 없었다. 회차 5 이상의 열린 항목은 `measured-claim-beyond-probe`(5회차)였고 이 브랜치와 닿지 않는다(`--ref` 쪽은 아직 열린 `gate-pipe-read-status`와 `spec-review-transition-crossing`도 5회차 이상으로 셌다. 앞의 것이 이 브랜치가 닫는 항목이고 뒤의 것은 형제 브랜치가 닫는다). 이 세션이 닫은 항목은 `gate-pipe-read-status` 하나다.

## 다음

- 이 PR이 병합되면 `gate-pipe-read-status`의 `&&`·`;` 체인 판정은 끝이다. 남은 한계는 `$?`를 실제로 쓰는지 보지 않는 것(독스트링의 못 보는 것)이고, 같은 꼴의 오경고나 퇴행이 다시 나오면 retro 후보로 올린다. 지금은 사건이 한 번뿐이라 대기열에 넣지 않았다.
- 주 체크아웃 미갱신: 루트는 `main`이다(병합 뒤 `tidy-checkouts`는 다음 새 세션이 돈다).
