# env-traps-crlf-and-utf8: 줄 끝 CRLF는 커밋 전 검사가 잡게 하고, `python -I`의 한글 깨짐은 환경 함정에 한 줄 적는다 · 2026-11-21

`next-session` 지시문으로 연 새 세션(Sonnet 5.5, high)이 대기열 항목 `crlf-from-script-edits`(11회차)와 `python-i-utf8`(7회차)을 한 티켓으로 반영한 기록이다. 티켓은 `.scratch/harness/issues/env-traps-crlf-and-utf8.md`, 브랜치는 `chore/env-traps-crlf-and-utf8`이고 `origin/dev`(`64bd055`)에서 새 워크트리 `env-traps-crlf-and-utf8`로 땄다. 두 항목의 `어디로` 줄이 각각 두 길(지침 한 줄 / 검사)을 열어 두었고, 어느 쪽이 맞는지는 이 세션이 항목을 읽고 정했다.

## 계기

- `crlf-from-script-edits`: 스크래치 스크립트의 `write_text`와 리다이렉트가 Windows에서 저장소 파일을 CRLF로 바꾸고도 아무 검사가 알리지 못해, 열한 번 `git add`의 `CRLF will be replaced by LF` 경고로야 알았다. 11회차는 원인조차 가리지 못했다.
- `python-i-utf8`: `uv run python -I`가 `PYTHONUTF8`을 읽지 않아 한글 출력이 cp949로 깨진다. 일곱 번 났다.

## 한 것

- 결정: CRLF는 검사로, `-I`는 지침 한 줄로 간다. CRLF는 쓴 도구를 알 수 없으니 "스크립트를 쓸 때 LF로 둔다"는 지침으로는 막지 못하고, 사다리에서도 린터·훅이 지침보다 위다(`CLAUDE.md` 교정 루프). `-I`는 판정할 도구가 없는 명령줄 습관이라 지침이 맞다.
- `tools/check_line_separators.py`: 새 함수 `crlf_in`이 텍스트 파일의 CRLF 줄 끝을 파일마다 한 줄(`<줄>:<열>: CRLF 줄 끝 <수>줄`)로 낸다. `problems_in`이 확장자와 상관없이 맨 끝에 붙이고, `main`이 되돌리는 안내(`CRLF_HINT`)를 붙인다. `separators_in`(홀로 선 CR)은 그대로다. 이진(앞 8000바이트에 NUL) 파일은 이미 `is_text`가 걸러 낸다.
- `tests/tools/test_check_line_separators.py`: 순수 함수(줄·열, 922줄 파일이 한 줄, LF뿐이거나 홀로 선 CR뿐이면 아님, 확장자 넷, 이진 파일의 침묵), `main`(안내 갈래), CLI 진입점을 subprocess로 한 번(저장소 밖 픽스처로 종료 1)을 더했다. 모든 코드 포인트를 훑는 시험은 CRLF 항목을 코드 포인트 해석에서 빼도록 고쳤다.
- `tests/tools/test_hook_line_separators.py`, `tools/hook_line_separators.py`: 훅은 이번에 판정을 바꾸지 않았다. 검사와 훅을 견주는 시험이 CRLF 항목 하나(`len == 1`)만 빼고 견주며, 훅 독스트링의 `못 보는 것`에 CRLF가 든다. 훅이 CRLF에 침묵하는 것은 기존 시험이 고정한다.
- `.pre-commit-config.yaml`: `check-line-separators` 훅 이름에 `CRLF 줄 끝`을 더했다(셀프 리뷰 명세 축이 짚었다).
- `CLAUDE.md` 환경 함정: `uv run python -I -X utf8 <파일>` 한 줄.
- 대기열: 두 항목을 닫고, `control-char-from-script-escape`(1회차, 열림) 본문에 어디로 줄의 "한 chore로 묶는다"가 낡았다는 주석 한 줄만 더했다.

## 검증

- 손으로 봤다(커밋하지 않은 스크립트, 2026-11-21): CRLF 바이트가 든 추적 파일은 43개이고 전부 앞 8000바이트 안에 NUL이 있다(PDF 21, HWPX 20, `.f32` 2는 셀프 리뷰 표준 축이 다시 세어 맞다고 했다). 텍스트로 읽히는 추적 파일에는 CRLF가 없어 새 판정이 이 저장소를 초록으로 둔다.
- 손으로 봤다(이 워크트리의 Bash, `sys.flags.utf8_mode`와 `sys.stdout.encoding`): `uv run python -I`는 `0 cp949`, 앞에 `PYTHONUTF8=1`을 붙여도 `0`, `-I -X utf8`을 붙이면 `1 utf-8`이다. `.claude/settings.json`의 `env`에 `PYTHONUTF8`이 들어 있다.
- 빨강에서 시작했다: 시험을 먼저 쓰고 돌리자 `ImportError: cannot import name 'crlf_in'`으로 수집부터 졌다. 구현 뒤 한 시험이 더 졌다(모든 코드 포인트를 훑는 시험이 ` U+` 표지 없는 CRLF 항목에서 `IndexError`). 시험을 고쳐 통과했다.
- 알려진 빨강으로 종료 1을 손으로 봤다: 임시 폴더에 CRLF `.md`와 LF `.md`를 바이트로 써서 검사를 돌리니 CRLF 파일 한 줄(`crlf.md:1:2: CRLF 줄 끝 2줄`)과 안내가 나오고 종료 1이었다. 저장소 전체는 종료 0이다. 임시 폴더는 지웠다.
- `ruff check .`, `ruff format --check .`, `pyright`(오류 0), `lint-imports`(2 kept), `tools/check_type_escapes.py`, `tools/check_instructions.py`, `tools/plan_table.py --check`가 초록이다. 두 시험 파일은 이 PC에서 한 번에 약 6분이 걸렸다(다른 세션이 여럿 돌던 때, 첫 회차 372.37초). 원인은 재지 않았다.

## 셀프 리뷰

`/code-review`를 기준 `64bd055`로 돌렸다. 범위는 수정 파일 8개, 새 파일 1개(티켓), 커밋 0개다. 표준 축은 확실한 위반 0, 판단 항목 Minor 넷과 냄새 둘을, 명세 축은 빠진 것 하나와 작은 범위 넘침·틀려 보이는 것을 냈다.

- 고친 것: ① 원인 단정(`CRLF_HINT`와 훅 독스트링). 대기열을 보면 원인이 적힌 회차는 3·5·6·7·8회차뿐인데 그 사고는 스크립트와 리다이렉트가 냈다고 단정해 썼다. 안내는 흔한 원인이라고 낮추고, 훅 독스트링은 원인이 적힌 회차는 모두 Bash의 스크립트나 리다이렉트였고 열한 번째는 원인을 가리지 못했다고 고쳤다. ② 닫힌 목록. `못 보는 것`이 "PDF·HWPX"만 들어 `.f32`가 빠졌고 "NUL이 든 이진 파일"은 실제 규칙(앞 8000바이트 안의 NUL)보다 넓었다. 둘 다 고쳤고, 8000바이트 뒤에만 NUL이 있는 파일은 git처럼 텍스트로 본다는 말도 적었다. ③ 과거형 문장. 이 검사가 CRLF의 CR을 줄 끝이라 보지 않아 0이었다는 문장에 그때를 붙였다. ④ CLI 시험 독스트링의 "git 이 알려 주지 않는다"는 11회차의 `git add` 경고와 부딪혀 "경고를 한 번 낼 뿐"으로 좁혔다. ⑤ `.pre-commit-config.yaml`의 훅 이름이 옛 판정 목록 그대로였다. ⑥ `control-char-from-script-escape`의 `어디로` 줄이 말하는 "한 chore로 묶는다"가 낡았는데 본문 주석과 앞뒤가 어긋났다. 주석에 낡았음을 분명히 적었다. ⑦ `crlf_in`이 `_spots`와 같은 줄·열 계산을 다시 했다. `_spots`를 쓰도록 합쳤다. ⑧ 쉬운 말. 안내문이 CRLF와 LF를 풀지 않았다. "Windows 식 줄바꿈(CR 문자 뒤에 LF 문자, CRLF)"으로 한 번 풀었고 티켓의 작업 사본·정규화·NUL·계기 훅에도 풀이를 붙였다.
- 남긴 것: 어긋남 종류를 문자열 조각(` U+`, `CRLF 줄 끝`)으로 가르는 Primitive Obsession은 기존 방식의 한 갈래 연장이라 판단 항목으로 둔다. 갈래가 하나 더 생기면 작은 타입으로 바꾼다. 수용 기준의 빨강에서 시작했다는 말과 알려진 빨강으로 종료 1을 손으로 보았다는 말은 코드로 확인되지 않아 위 검증 절에 근거를 적었다.
- 밀 주장(PR 직전 리뷰에 넘길 반영 문장): ① 검사 독스트링 `못 보는 것`의 8000 바이트 뒤에만 NUL이 있는 파일은 git처럼 텍스트로 보고 CRLF를 센다는 말 ② 훅 독스트링의 원인이 적힌 회차는 모두 Bash의 스크립트나 리다이렉트였다는 말 ③ `CRLF_HINT`의 흔한 원인이 스크립트의 write_text나 stdout 리다이렉트가 Windows에서 LF를 CRLF로 바꾼 것이라는 말.
- 다시 돌린 것: `ruff check .`, `ruff format --check .`, `pyright`(오류 0)를 고친 뒤 다시 돌려 초록이다. 두 시험 파일은 고친 뒤 다시 돌려 `44 passed`(296.70초)다. 나머지 검증 명령(전체 `pytest` 포함)은 커밋의 pre-commit이 갈음한다.

## 커밋

첫 커밋 시도의 pre-commit은 `ruff`와 나머지 검사(`check-instructions`, `pyright` 둘, `lint-imports`, `run-hooks` 등)가 통과했고 전체 pytest만 `3 failed, 4950 passed, 1 error in 1095.63s`로 졌다. 진 시험은 `tests/contract/test_tool_errors.py`의 도구 오류, `tests/server/test_mcp_assembly.py`의 기본 SSE 응답, `tests/tools/test_search_eval_index.py`의 차원 매개변수, 오류는 `tests/tools/test_check_notes.py`의 `main과 dev 위의 커밋은 지난다`(setup)다. 로그의 오류는 `RuntimeError: can't start new thread`, `SystemError: <built-in function compile> returned NULL without setting an exception`, 그리고 멀쩡한 pydantic 파일(`_generate_schema.py` 252행)에서 난 `SyntaxError`다. 모두 이 변경이 닿지 않은 곳이다.

- 이 PC의 상태를 손으로 봤다(실패 직후, `Win32_OperatingSystem`): 가상 메모리 여유 13.0GB(전체 127.9GB), 물리 메모리 여유 3.1GB, 파이썬 프로세스 90개. 대기열 항목 `concurrent-checks-exhaust-memory`가 적은 부하(여유 6~16GB)와 같은 모양이다.
- 진 시험 네 개(매개변수 포함 6건)를 따로 돌렸다(`RAG_TEST_DATABASE_URL`을 `compose.test.yml`의 값으로 두고 `-k`로 골랐다). `6 passed, 204 deselected in 289.88s`다. 이 변경과 무관한 부하 실패로 읽고 같은 커밋을 다시 시도했다.
- 둘째 시도: 전체 pytest를 포함한 검사가 모두 통과했다(pytest 994.9초, `run-hooks` 133.7초). 커밋 메시지 검사만 제목 91자가 한도 72자를 넘어 졌다. 인용 대조(경고만 내는 검사)가 이 티켓과 일지의 따옴표 인용 8건을 저장소에 글자 그대로 없다고 알려, 따옴표를 떼고 고친 뒤 제목을 줄여 다시 커밋했다.

## 회고

후보 둘, 승인 0, 기각 2, 넘김 0.

- 두 시험 파일이 한 번에 6분 넘게 걸림(기각): 모든 코드 포인트를 훑는 시험이 느린 것인지 이 PC의 부하인지 재지 않았다. 원인을 가리지 못한 채 처방을 정할 수 없고, 부하에서 느려지는 시간 문제는 사용자가 닫은 종류(2026-11-15)에 가깝다. 일지에만 적는다.
- 대기열 첫 문단만 읽고 훅 독스트링에 원인을 단정함(기각): 셀프 리뷰 두 축이 같이 잡았다. 리뷰가 제 몫을 한 것이라 회차로 세지 않는다.

## 다음

- 이 PR을 `dev`에 병합한다. 병합은 `next-session` `merge.md`의 "워크트리에서 병합할 때"를 따른다.
- `control-char-from-script-escape`는 1회차라 다섯 번째에 반영한다. 그때 `crlf_in` 옆에 더한다.
