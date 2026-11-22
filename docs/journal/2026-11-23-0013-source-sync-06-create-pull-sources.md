# source-sync 06: 가져오는 원천 만들기와 고치기와 연결 확인 · 2026-11-23

source-sync 티켓을 나눈 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/source-sync/issues/06-create-pull-sources.md`이고, 브랜치는 `feature/06-create-pull-sources`, 작업은 워크트리 `06-create-pull-sources`에서 했다. 요청 범위는 PR과 병합까지다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 06, 명세 `.scratch/source-sync/spec.md`의 "관리 API"와 "서버 경로 커넥터와 원천 폴더", 코드 독스트링이 근거로 드는 ADR(0007, 0012, 0015, 0023), 04 티켓의 구현 메모.
- 시험용 PostgreSQL은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.

## 지은 것

- **도메인.** `Source`에 가져오는 원천의 칸(`connector`, `config`, `exclude_patterns`, `paused`)을 쓰는 길, 오류 코드 `wrong_source_kind`와 `source_folder_overlap`, 폴더 확인의 결과(`FolderLocation`, `FolderTarget`)를 더했다. `ConnectorRegistry` 포트에 `locate_folder`, `survey_folders`, `check_connection`을 더했다. 포트를 새로 만들지 않아 포트가 넷이라는 명세와 ADR 0007의 열거를 지킨다.
- **어댑터.** `server_path.py`에 폴더 확인(`locate_folder`)을 더했다. 부모 폴더를 연 자리에서 토막마다 링크를 따르지 않고 내려가며, 적은 글자 그대로 찾고 없으면 NFC로 맞춰 찾는다. 레지스트리가 세 확인을 커넥터 호출 장치에 태우고 한도는 10초다. 카탈로그에 칸 단위로 쓰는 `update_pull_source`, `set_source_paused`, 자문 잠금 `lock_source_folders`를 더했다.
- **유스케이스.** `app/pull_sources.py`가 만들기, 고치기, 일시 중지와 다시 시작, 연결 확인을 맡는다. 폴더를 정하는 요청은 프로세스 안 잠금, 데이터베이스 연결, 자문 잠금 순으로 차례를 세운다.
- **서버.** 관리 API가 `POST /sources`(`kind: pull`), `PATCH /sources/{name}`, `POST /sources/{name}/check`, `/pause`, `/resume`을 연다. 수집 API는 가져오는 원천의 이름을 받으면 409 `wrong_source_kind`로 답한다.
- **시험.** 새 시험 파일 아홉 개와 시험 도우미 둘(`tests/support/pull_source_http.py`, `tests/support/server_path_faults.py`), 고친 시험 파일 다섯 개. 변이 프로브는 `.scratch/source-sync/probes/pull_sources_mutations.toml`(21개)이다.

## 이 세션이 정한 것

- **겹침 판정은 실제 폴더로 가른다.** 폴더마다 부모 아래 첫 폴더부터 끝 폴더까지 `(장치 번호, 파일 번호)` 열쇠의 사슬을 얻고, 끝 폴더가 상대의 사슬에 들면 겹친다. 대소문자만 다른 이름이나 합쳐 적은 한글과 풀어 적은 한글이 같은 폴더로 가려진다. 폴더가 지금 없거나 10초 안에 답하지 않는 원천과는 저장해 둔 경로를 NFC로 맞춘 토막 단위 앞머리로 견준다.
- **저장하는 폴더 이름.** 글자 그대로 찾은 토막은 사용자가 적은 글자를 저장하고 NFC로 맞춰 찾은 토막만 디스크의 이름을 저장한다(셀프 리뷰가 독스트링의 "디스크의 이름" 표현을 바로잡게 했다).
- **칸 단위 쓰기.** PATCH와 `/pause`가 읽어 둔 값을 통째로 되쓰지 않고 바뀐 칸만 쓴다. 격리 수준이 READ COMMITTED이고 행 잠금이 없어서다.
- **쌍점(`:`).** Windows에서는 폴더 확인도 커넥터와 같은 설정 읽기를 써서 쌍점이 든 폴더를 `invalid_config`로 거절한다. 명세 143행의 거절 목록에는 역슬래시만 있다. 명세 고침은 to-spec의 몫이라 여기에는 적어 두기만 한다.
- **연결 확인의 `peek()`.** 첫 항목의 이름만 읽지 않고 정보까지 읽는다(`scan()`과 같은 호출). 읽기 권한만 있고 탐색 권한이 없는 폴더를 연결 확인이 가려내게 하려는 것이다.
- **union 갈래 오류.** `kind`가 없거나 틀리면 pydantic이 위치를 `body`에서 끝내고 글에 클라이언트가 보낸 값을 되울린다. `validation_issue_of`가 위치 끝에 `kind`를 더하고 틀린 값 대신 받을 수 있는 값을 싣는다(ADR 0015).

## 겪은 것

- 처음 전체 시험에서 셋이 빨갰다. `tests/conftest.py`가 CRLF로 저장돼 있었고(LF로 고쳤다), 오류 위치가 바뀌어 옛 시험 둘이 새 기대와 어긋났다.
- 변이 프로브가 처음 살아남은 둘이 있었다. NFC 갈래를 `scandir`을 바꿔 끼워 재던 시험은 가짜 디렉터리라 아무것도 재지 못했고(실제 폴더 시험으로 바꿨다), 서버 둘 사이의 자문 잠금은 서버 둘을 흉내 낸 시험이 없어서였다(`tests/app/test_pull_sources_two_servers.py`를 더했다).
- Edit 도구가 풀어 적은 한글이 든 줄을 맞추지 못해 `sed`로 줄을 지우고 평범한 글자에 닿은 Edit로 대신했다.
- 폴더를 고치는 요청의 프로세스 안 차례를 지키는 시험을 처음 쓸 때는 1초만 기다렸고, 변이를 걸어도 시험이 초록이었다. 고치기 요청은 확인이 길어 1초 안에 연결 풀이 차지 않았기 때문이다. 기다림을 3초로 늘리자 변이가 빨강으로 잡혔다.
- 변이 프로브의 두 항목이 `_enter_folder`를 단순화하며 없어진 원문(`if missing and ...`)을 가리켜 전체 실행이 도구 오류로 끝났다. 원문을 현재 코드에 맞췄다.
- 첫 커밋 시도는 pre-commit의 변이 표 검사에서 막혔다. 빨강을 기대한 변이는 `expect_output`(그 단언이 빨개질 때만 찍히는 문구)이 있어야 한다. 마지막 실패 출력에서 변이마다 문구를 골라 21개를 더하고 전체를 다시 돌려 모두 맞는 것을 봤다. 같은 pre-commit의 다른 검사(시험 전체 495초 포함)는 통과했다.


## 셀프 리뷰

`/code-review`를 고정점 `origin/dev`(base `2d529ec`)로 돌렸다. 본 범위는 고친 추적 파일 21개, 미추적 파일 11개, 커밋 0이다. 표준 축은 Sonnet(노력 high), 명세 축은 이 세션의 모델로 돌렸고, 두 축에 주장 검증 목록과 밀 주장을 넘겼다. 명세 축에는 상태와 동시 요청이 있어 전이 교차 (d)를 붙였다.

### 보고

- **표준 축.** 하드 위반은 없었다(`Any`, `cast`, `type: ignore`가 없고 import 경계를 지켰다).
  - **Major.** 연결 확인의 `peek()`가 "읽기 권한은 있고 탐색 권한이 없는 폴더"를 가리지 못한다. 일반 사용자로 chmod 444 폴더를 재 보니 `scandir`의 첫 항목 읽기는 통과하고, 실제 `list()`가 하는 `os.stat(dir_fd=)`가 EACCES로 실패했다. 그래서 만들기가 201, 연결 확인이 `ok: true`로 지나가고 `list()`만 `unreadable`로 실패한다. 시험 셋은 `scandir`이 PermissionError를 내게 바꿔 끼운 흉내라 실제 조건을 재지 못한다.
  - **Major.** `update_pull_source`가 `config`, `exclude_patterns`, `paused` 셋을 읽어 둔 값으로 모두 쓴다. 행 잠금이 없고 격리 수준이 READ COMMITTED라 PATCH와 `/pause`가 겹치면 한쪽 갱신이 사라진다.
  - **Minor(냄새).** 시험 도우미 중복(`_request`, `_create`, `_errors`가 `tests/support/pull_source_http.py`와 같다. `refuse_listing`이 세 곳). `_reject_overlap`의 Feature Envy. `check_connection(name, config, source)`와 `FolderTarget`의 Data Clumps.
  - **Nit.** `_check_code`의 `except ConnectorBrokenError`가 기본값과 같다. `_enter_folder`의 `missing and`가 늘 참이다. `ConnectionCheck.ok`가 `code is None`과 겹친다. `set_paused(*, paused: bool)`의 키워드 플래그. `test_check는_…`는 이름에 함수명이 든다. `_issue_location`이 조립 파일 `app.py`에 있다.
  - **주장 검증의 거짓.** (1) `locate_folder` 포트 독스트링과 `_enter_folder`의 "저장 경로는 디스크의 이름": 글자 그대로 찾은 갈래는 사용자가 적은 글자를 낸다(대소문자를 가리지 않는 Windows에서 `Docs` 폴더에 `docs`를 적으면 `docs`가 저장). 디스크 이름이 보장되는 것은 NFC 갈래뿐이다. (2) `domain/connectors.py`의 `ConnectorUnavailableError`가 뒤의 티켓이 원천을 만드는 요청의 422로 옮긴다는 미래형을 쓴다. 만드는 쪽은 이 변경이 닫았다. (3) `registry.py` 머리 설명은 "만들기"만 다룬다. ADR 0007 이력과 명세 95행은 `ConnectorRegistry`의 몫을 "만들고 버전을 판정"으로만 적어 폴더 확인, 살펴보기, 연결 확인이 더해진 것과 어긋난다. (4) 시험 이름 `…검색과_조회가…`는 검색 요청을 보내지 않고 `GET /sources`만 보낸다. (5) `pull_sources.py`의 확인에 걸리는 시간이 잠금을 쥔 시간에 들지 않는다는 문장은 새 폴더에만 맞고, 다른 원천을 살피는 확인(최대 10초)은 프로세스 잠금과 연결을 쥔 채 돈다(명세 149행 "셋째"가 인정한다).
  - **맞게 닫힌 주장.** Problem Details 코드 18개, 새 코드 둘의 상태와 제목, `Source`의 일곱 칸, `_issue_location`이 `body`에서 끝난다는 말, 포트 수 넷, 잠금 시험 둘과 서버 둘 시험이 실제로 붙잡아 가른다.
- **명세 축.**
  - **(a) 빠졌거나 일부.** 겹침 확인의 "실제 폴더로 가른다(대소문자를 가리지 않는 공유 폴더, 합쳐 적은 한글과 풀어 적은 한글)"를 끝까지 보는 시험이 없고, 변이 프로브에도 이 갈래가 없다. 폴더를 고치는 요청(PATCH)이 자문 잠금과 프로세스 안 잠금을 쥐는지 보는 시험과 변이가 없다(동시 시험은 만들기끼리만). 04 티켓 구현 메모의 미래형 두 줄(쌍점은 06이 정한다는 줄, `_descend`를 공개할지 06이 정한다는 줄)이 그대로 남았다.
  - **(b) 범위 넘침.** 제외 패턴이 빈 문자열이면 422인데 명세는 개수 50과 길이 200만 정했다. `union_tag_invalid`의 `msg`가 클라이언트가 보낸 `kind` 값을 그대로 되울린다(`Input tag '비밀값-xyz' found…`로 재서 확인). 주석은 입력 값을 싣지 않는다고 한다(ADR 0015). `PATCH {"config": null}`과 `{"exclude_patterns": null}`은 적지 않은 것으로 조용히 무시된다.
  - **(c) 틀려 보임.** `PullSources` 머리 독스트링이 확인 시간은 잠금을 쥔 시간에 들지 않는다고 적은 것(표준 축 (5)와 같다).
  - **(d) 교차.** 일시 중지·다시 시작과 고치기가 같은 원천에 동시에 오면 갱신이 사라진다. 스크래치 시험에서 pause가 읽은 뒤 config PATCH가 커밋하고 pause가 쓰자 `config`가 `b`에서 `a`로 되돌아갔다. 이때 겹침 확인을 거치지 않은 옛 폴더가 복원되고 PATCH의 `exclude_patterns`도 사라진다. 한도를 넘긴 폴더 확인이 늦게 돌아오는 경우는 안전하다(받을 쪽이 없고 같은 설정의 재요청은 기억 덕에 바로 422이며 중단된 요청이 쥔 잠금은 컨텍스트로 풀린다).
  - **맞게 닫힌 주장.** 오류 코드 "열여덟", "늦게 돌아온 확인은 아무것도 쓰지 못한다".

### 판정과 반영

고친 것(모두 먼저 실패하는 시험을 쓰고 고쳤다).

- 표준 Major 1. `peek()`가 첫 항목의 정보도 읽는다. 읽을 수 있지만 탐색할 수 없는 폴더를 재는 시험은 `tests/support/server_path_faults.py`의 `hide_entry_info`가 `os.stat(dir_fd=)`의 `PermissionError`를 흉내 낸다(권한 비트로 만들지 않는다. root와 Windows에서 같은 결과가 나오지 않는다). 경로 판(`_PathDirectory`)은 변이 16이 지킨다. 파일 서술자 판(`_FdDirectory`, 리눅스)은 CI가 돌린다.
- 표준 Major 2와 명세 (d). `update_pull_source`가 `config`와 `exclude_patterns` 중 적은 칸만, 새 `set_source_paused`가 `paused` 칸만 쓴다. 응답은 쓴 뒤 다시 읽어 낸다(`_report_after_write`). 시험은 `tests/adapters/test_catalog_pull_sources.py`의 셋이고 변이 17이 지킨다.
- 명세 (b) 되울림. `validation_issue_of`로 `union_tag_invalid`의 글이 보낸 값 대신 받을 수 있는 값을 싣고, `_issue_location`은 `problems.py`로 옮겼다. 변이 14와 15가 지킨다.
- 명세 (a) 겹침 판정 두 갈래. `tests/app/test_pull_sources_overlap.py` 넷(같은 폴더·다른 글자, 답하는 원천의 다른 폴더, 답하지 않는 원천과 NFC, 토막 단위 앞머리). 변이 18과 19가 지킨다.
- 명세 (a) 폴더를 고치는 요청의 잠금. 서버 둘 시험(`test_서버_둘에서_폴더를_고치는_요청과_…`)과 차례 기다리는 동안 연결을 쥐지 않는 시험을 더했고 변이 20과 21이 지킨다.
- 표준 주장 검증. `locate_folder`·`FolderLocation`·`_enter_folder` 독스트링(저장 경로의 글자), `ConnectorUnavailableError`의 미래형, `registry.py` 머리, `pull_sources.py` 머리(다른 원천을 살피는 시간은 잠금과 연결을 쥐고 돈다)를 고쳤다. 잠금 시험 이름의 "검색"을 "목록 조회"로 바꿨다.
- 04 티켓의 구현 메모 두 줄을 과거형으로 바꾸고 06이 정한 것을 적었다.
- Nit. `_enter_folder`의 늘 참인 `missing`을 없앴다. 시험 도우미 중복은 `tests/support/pull_source_http.py`와 `server_path_faults.py`로 모았다.

남긴 것과 이유.

- 제외 패턴이 빈 문자열이면 422인 것: 명세가 개수와 길이만 정했고 침묵한다. 빈 패턴은 모든 파일과 맞는지 아무것도 걸러 내지 않는지 뜻이 갈려 거절이 안전하다. 바꿀지는 to-spec이 정한다.
- `PATCH {"config": null}`과 `{"exclude_patterns": null}`을 적지 않은 것으로 무시하는 것: 명세가 침묵한다. 같은 이유로 to-spec 몫이다.
- `ConnectionCheck.ok`가 `code is None`과 겹치는 것: 명세 344행이 응답에 `ok`와 실패했을 때의 `code`를 함께 싣는다고 정했다.
- `_reject_overlap`의 Feature Envy와 `check_connection`·`FolderTarget`의 Data Clumps: 판단 항목이고 고쳐도 읽기가 나아지지 않는다.
- `except ConnectorBrokenError`가 기본값과 같은 것: 연결 확인이 어떤 오류를 어떤 코드로 옮기는지 한 곳에서 보이게 하려고 남겼다.
- ADR 0007 이력과 명세 95행("만들고 버전을 판정"), 명세 143행의 거절 목록(쌍점이 없다)이 이 변경과 어긋난다. ADR과 명세는 승인 없이 고치지 않는다. PR 본문에 적고 to-spec과 ADR 승인으로 넘긴다.

밀 주장(PR 직전 리뷰가 겨냥할 새 사실 문장).

- `peek()` 독스트링: 열거만이 아니라 첫 항목의 정보 읽기까지 해서 탐색 권한이 없는 폴더를 가린다.
- `validation_issue_of` 독스트링(PR 직전 리뷰 뒤의 최신 문장): 갈래 칸이 없거나 틀린 오류는 위치가 `body`에서 끝나 칸 이름을 더하고, 틀린 오류(`union_tag_invalid`)만 글이 보낸 값을 되울려 받을 수 있는 값으로 바꾼다.
- `_report_after_write` 독스트링: 읽어 둔 값에 고친 칸만 덧입히면 동시에 바꾼 다른 요청의 칸이 옛 값으로 보인다.
- `update_pull_source`와 `set_source_paused` 포트 독스트링: 적은 칸만 쓴다.
- `FolderLocation`과 `locate_folder` 독스트링: 글자 그대로 찾은 토막은 적은 글자, NFC로 찾은 토막은 디스크의 이름.
- `registry.py` 머리: 서버가 요청 안에서 부르는 확인 셋이 모두 호출 장치를 지나고 한도가 10초다.
- `pull_sources.py` 머리: 새 폴더의 확인은 차례 앞에서 하고, 다른 원천을 살피는 확인은 차례와 작업 단위 안에서 돈다.

다시 돌린 명령(반영 뒤).

- `uv run ruff format .`(899개 그대로), `uv run ruff check .`, `uv run pyright`(0 errors), `uv run lint-imports`(계약 2개 지켜짐), `uv run python -I -X utf8 tools/check_type_escapes.py`(출력 없음)가 모두 초록이다.
- 이 티켓이 건드린 시험 열두 파일(서버 경로 폴더 확인, 카탈로그, 레지스트리 요청, 서버 둘, 겹침, 관리 API 원천, 잠금, 멈춘 호출, 가짜 커넥터, 원천 공통, 수집 API 원천, 오류 코드)을 한 번에 돌려 202개가 통과했다.
- 전체 시험은 커밋이 부르는 pre-commit의 검사 러너가 돌리므로 그 결과로 갈음한다. 결과는 커밋 뒤 PR 본문에 적는다.

## 검증

- 변이 프로브 21개가 모두 기대한 빨강이었다(`PYTHONUTF8=1 uv run python tools/mutate.py .scratch/source-sync/probes/pull_sources_mutations.toml`). 반영 도중 어긋난 둘은 둘 다 시험을 고쳐 닫았다. 폴더를 고치는 요청의 프로세스 안 차례(21)는 시험의 기다림을 1초에서 3초로 늘린 뒤에야 잡혔다.
- 이 PC는 Windows라 `_FdDirectory`(리눅스의 파일 서술자 판) 경로는 CI가 처음 돌린다. 변이 프로브도 경로 판만 덮는다.

## 회고

- 변이 프로브의 원문이 코드를 단순화하는 순간 죽은 줄을 가리켜 전체 실행이 도구 오류로 끝났다. 도구가 바로 알려 줘서 손해는 없었다. 같은 실수의 첫 사건이다.
- 동시 요청 시험이 변이를 잡으려면 요청이 서버에 닿아 연결을 쥘 시간을 줘야 한다. 만들기는 1초로 충분했고 고치기는 3초가 필요했다. 시간으로 기다리는 시험이라 느린 CI에서는 더 늘어야 할 수 있다. 그때는 변이 21번이 초록으로 살아남는지로 알아챈다.
- 새 규칙이나 훅은 더하지 않았다(`CLAUDE.md` 교정 루프의 다섯 번째나 손상이 아니다).

## 다음

- 06은 끝났다. 07(지금 동기화로 새 파일과 바뀐 파일 넣기)이 06과 02에 막혀 있었고 둘 다 끝나 이제 열린다. 10(일정)도 07 뒤에 열린다.
- 07이 알아야 할 것: 일시 중지는 `paused` 칸만 바꾸고 다음 실행 시각은 일정을 여는 10이 다룬다. 가져오는 원천의 `config.folder`는 저장 경로(NFC로 찾은 토막만 디스크의 이름)이고 커넥터가 그 경로를 부모 폴더 아래에서 다시 연다.
- 12(되살리기)가 알아야 할 것: 원천을 되살릴 때도 겹침 확인(`PullSources._reject_overlap`)을 다시 거쳐야 한다.
- to-spec과 ADR 승인으로 넘길 것: ADR 0007 이력과 명세 95행의 `ConnectorRegistry` 몫("만들고 버전을 판정")에 폴더 확인, 살펴보기, 연결 확인이 빠졌다. 명세 143행의 거절 목록에 쌍점이 없다. 제외 패턴이 빈 문자열일 때와 `PATCH`에 `null`을 줄 때의 뜻이 명세에 없다. 서버 경로 원천의 설정이 `folder` 밖의 칸을 받아 저장하고 응답에 싣는다(명세 143행은 설정이 `folder` 하나라고만 한다).
- 티켓 11(원천 삭제)이 알아야 할 것: 지운 원천을 PATCH, `/pause`, `/resume`, `/check`가 막지 않는다. 명세 172행대로 `source_deleted`를 더해야 한다.

## PR 직전 리뷰

### 보안 리뷰(내장 `/security-review`)

신뢰도 8 이상의 취약점이 없었다. 하위 작업이 본 것과 결론은 아래와 같다.

- 새 경로(`PATCH /sources/{name}`, `/check`, `/pause`, `/resume`, 가져오는 원천을 만드는 `POST /sources`)는 모두 `/api/v1/admin` 아래에 있고, 앞단 인증 미들웨어가 `reader` 토큰을 403으로, 없거나 틀린 토큰을 401로 막는다. 새 경로에는 면제가 없다.
- 폴더 설정은 `..`, 빈 토막, `/`로 시작, 역슬래시, NUL을 거절한다(Windows는 쌍점도). 리눅스에서는 부모 폴더를 연 자리에서 토막마다 `O_NOFOLLOW`와 `dir_fd`로 내려가므로 링크로 부모 밖을 읽는 길이 없다. 읽기와 목록과 확인이 매번 같은 내려가기를 다시 해서 폴더 확인과 읽기 사이에 경로 글자를 다시 여는 틈이 없다.
- NFC로 맞춰 찾는 갈래는 이미 연 폴더의 목록 안에서만 고르고, 고른 이름도 링크를 따르지 않는 열기로 연다.
- 오류 응답과 로그에는 폴더 이름, 설정, 커넥터 예외 글이 실리지 않는다(고정 문장, 예외 종류 이름만).
- 새 SQL은 SQLAlchemy 바인딩이고 자문 잠금 열쇠는 상수다.
- 남는 틈은 Windows의 확인한 뒤 여는 길(개발 기계 한정, 04 티켓이 이미 적어 둔 것)뿐이다.

### CodeRabbit CLI 리뷰(0.7.5, 지적 6건)와 트리아지

CLI는 끝까지 돌았다(종료 코드 0, 인증 오류 없음). 트리아지 서브에이전트가 지적을 코드와 대 보고 겨냥한 주장 일곱을 판정했다. Critical과 Major는 없다. CodeRabbit이 Major로 낸 넷 가운데 둘은 오탐이었고 둘은 Minor로 내렸다.

- **오탐.** `app.py:177`의 "폴더 확인이 종료를 막는다"(폴더 확인은 daemon 스레드에서 돌고 요청마다 10초 한도가 있다). `test_ingest_sources.py`의 "`RAG_SOURCES_DIR` 순서"(`_parent_folder()`가 호출마다 환경 변수를 읽는다).
- **주장 판정.** 일곱 주장 가운데 여섯이 코드와 맞았다. 틀린 하나가 `validation_issue_of`의 독스트링이다. 실제로 재 보니 `kind`가 틀린 오류(`union_tag_invalid`)만 보낸 값을 되울리고, 칸이 없는 오류(`union_tag_not_found`)의 글은 `Unable to extract tag using discriminator 'kind'`라 보낸 값이 없다.

고친 것.

- `validation_issue_of` 독스트링을 위 실측대로 나눠 적었다- `peek()` 독스트링(`_Directory` 프로토콜)에 한계를 적었다. 원천 폴더 바로 아래의 첫 항목 하나만 보고, 권한 오류는 파일 서술자 판(리눅스)에서만 확실하다(경로 판의 `DirEntry.stat()`은 열거 때 얻은 정보를 돌려줄 수 있다는 것은 문서에서 읽은 것이고 이 PC에서 재지 않았다).
- `registry.py` 머리에 커넥터를 만드는 호출은 한도 밖이고 이벤트 루프 위에서 돈다는 것을 적었다.

남긴 것과 이유.

- 새 폴더의 열쇠를 차례를 기다리기 전에 얻는 틈: 앞선 요청이 잠금을 쥔 최대 10초 사이에 운영자가 그 폴더를 지우고 다시 만들면 옛 열쇠로 겹침을 견준다. 운영자가 서버 폴더를 직접 바꾸는 경우뿐이고, 저장한 뒤의 같은 조작은 이 구조로 막지 못한다. 잠금을 잡은 뒤 다시 찾으면 잠금 시간이 최대 10초 늘어서 고치지 않는다.
- 지운 원천(`deleted_at`이 선 원천)을 PATCH, `/pause`, `/resume`, `/check`가 통과하는 것: 원천을 지우는 API가 아직 없어 지금은 일어나지 않는다. 지우는 티켓 11이 `require_pull_source`와 `set_paused`에 `source_deleted`(명세 172행)를 더해야 한다. "다음"에 적는다.
- 서버 경로 원천의 설정이 `folder` 말고 다른 칸도 받아 그대로 저장하고 응답에 싣는 것: 명세 143행은 설정이 `folder` 하나라고 하지만 거절을 정하지 않았다. 응답은 `admin` 토큰만 본다. to-spec으로 넘긴다.
- 서버 둘 시험의 `sleep(1.0)`이 느린 CI에서 "기다렸다"를 증명하지 못할 수 있는 것: 변이 20번과 2번이 잡는 동안은 의미가 있다. 느려지면 변이가 초록으로 살아남는다(위 회고).
- 커넥터 만들기가 이벤트 루프 위에서 돈다: 티켓 05가 정한 설계이고 서버 경로 커넥터는 파일을 부르지 않는다. 서버 경로가 아닌 커넥터를 붙이는 티켓이 스레드로 옮긴다.
