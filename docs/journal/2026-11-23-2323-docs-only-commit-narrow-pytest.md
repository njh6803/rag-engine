# docs-only-commit-narrow-pytest: 문서만 바꾼 커밋은 문서를 읽는 시험만 돈다 · 2026-11-23

`next-session` 지시문으로 연 새 세션의 기록이다(Sonnet 5.5). 브랜치는 `chore/docs-only-commit-narrow-pytest`이고 티켓은 `.scratch/harness/issues/docs-only-commit-narrow-pytest.md`다. 대기열 항목 `docs-only-commit-full-pytest`(열두 회차)를 반영한다. 이 세션은 PR을 열고 병합하는 데까지다.

## 준비

- 주 체크아웃에서 브랜치를 따지 않고 `EnterWorktree`로 워크트리에 들어간 뒤 브랜치 이름을 `chore/docs-only-commit-narrow-pytest`로 바꿨다. `git fetch origin` 뒤 `origin/dev`(`50d15a8`)와 같은 머리였고 `tools/sibling_overlap.py`는 번호와 헌법 버전 겹침이 없다고 답했다.
- 읽은 것: 대기열 항목, `docs/agents/issue-tracker.md`, `docs/constitution/operations.md`의 가드레일 절, `tools/run_checks.py`(독스트링의 "문서만 바뀐 커밋에서도 pytest 를 건너뛰지 않는다(core 01 결정)" 항목), `.pre-commit-config.yaml`, `tests/tools/test_run_checks.py`.

## 사용자에게 받은 승인(코드를 고치기 전)

- 남길 시험 넷과 "ADR 없이"를 고르게 했고 "넷으로 좁히고 ADR 없이"가 답이었다. 남길 시험: `tests/test_plan_status.py`, `tests/tools/test_check_adr_pointers.py`, `tests/tools/test_queue_open_rows.py`, `tests/tools/test_check_quotes.py`의 "이 저장소 전체를 돌려도 끝난다" 한 건.
- 문서의 범위는 "md와 프로브 출력"이 답이었다. 그때는 범위의 파일을 읽는 다른 시험이 없다고 `tests/`를 grep으로 훑어 보고 말했는데, 뒤에 감사 훅으로 확인하니 틀렸다(아래 "감사로 알게 된 것").
- 손으로 쳐 본 것: 남긴 넷은 `uv run pytest -q <넷>`으로 105건이 통과했다(이 PC에서 다섯 번 쟀고 24, 32, 49, 148, 165초다. 다른 세션이 함께 돌수록 느렸다. 스크래치 명령).
- ADR을 쓰지 않은 까닭: "문서만 바뀐 커밋도 건너뛰지 않는다"가 ADR이 아니라 `tools/run_checks.py` 독스트링(core 01 결정)에만 적혀 있었다.

## 지은 것

- `tools/run_checks.py`: `is_doc_path`, `docs_only`, `staged_paths`(`git diff --cached --name-only --no-renames -z`), `checks_for`, `needs_test_database`, 상수 `DOC_STATE_TESTS`와 `DOC_PYTEST_TIMEOUT_SECONDS`(900초). 문서만 바꾼 커밋이면 pytest 검사를 넷으로 바꾸고 `-n`과 시험 데이터베이스 준비를 뺀다. `docs-only` 줄을 한 줄 찍는다. 읽지 못함, 빈 목록, 문서가 아닌 파일이 섞임은 전체 pytest다.
- `tests/tools/test_run_checks.py`: 문서 범위 판정 서른다섯 입력, 빈 목록, 이름을 바꾼 파일, 지운 파일, 저장소가 아님, git이 없음, 남길 시험의 파일과 이름이 실제로 있는지.
- 옛 문장 고침: `tools/run_checks.py` 독스트링, `.pre-commit-config.yaml` 머리 주석, `.claude/skills/next-session/SKILL.md`의 Docker 갈래.
- 반박한 것(손으로 변이를 넣어 시험이 빨개지는지 봤다): `docs_only`에서 `bool(paths)`를 뺐을 때 세 시험이 빨갰고, `--no-renames`를 뺐을 때 이름 바꾸기 시험이 빨갰다. 둘 다 원래대로 되돌렸다.

## 감사로 알게 된 것

- 셀프 리뷰의 두 축이 "문서를 읽는 시험이 넷뿐"이라는 주장의 반례로 `test_hook_prompt_directive`와 `test_hook_grill_design_check`를 찾았다. 그래서 파일을 열 때마다 시험 이름과 경로를 적는 감사 훅(스크래치패드의 `sitecustomize.py`와 pytest 플러그인)을 붙여 전체 pytest를 `-n 6`으로 돌렸다(2026-11-24, 1시간 16분. 테스트 데이터베이스가 없어 오류 480건, 실패 5건. 실패 가운데 줄 구분 문자 시험은 `MemoryError`와 `Invalid argument`로 이 환경의 탓이고 나머지 넷은 데이터베이스를 쓰는 시험이다).
- 문서 범위의 파일을 연 시험: 승인한 넷, 따로 도는 검사가 있는 것(줄 구분 문자, 마크다운 표, 인용 명령줄 둘, 지침 검사), 그리고 목록에도 없고 따로 도는 검사도 없는 둘(`test_hook_prompt_directive`의 규약 낱말 시험은 `docs/agents/issue-tracker.md`를, `test_hook_grill_design_check`의 용어집 시험은 `docs/agents/domain.md`를 연다). 데이터베이스가 필요한 시험은 이 감사에서 보지 못했다.
- 사용자가 승인한 목록은 넷이라 목록은 넷으로 두고, 둘을 독스트링의 "못 보는 것"과 티켓에 적었다. 목록에 더할지는 사용자의 결정으로 남겼다.

## 셀프 리뷰 (`/code-review`, 기준 `50d15a8`, 파일 4개 수정과 미추적 1개, 커밋 0개)

- 고친 것: (1) `docs_only`가 받는 인자 꼴에 `None`을 더했다(`main`이 읽기 실패를 `None`으로 넘긴다). (2) `main`을 시험하는 한 건이 진짜 색인을 읽던 것을 `staged_paths` 대체로 바꿨다. (3) 숫자 둘의 근거를 고쳤다: 전체 pytest는 "11~16분"이 아니라 대기열 기록의 434초~1292초(약 7분에서 21분), 남긴 넷은 "31.55초"가 아니라 명령과 함께 24~165초(다섯 번 잰 범위). (4) "문서를 읽는 시험이 넷뿐"이라는 닫힌 주장을 감사 결과로 고치고 둘을 못 보는 것에 적었다. (5) 900초 주석의 헷갈린 문장을 다시 썼고, 좁힌 pytest가 시간 제한을 넘기면 전체로 넘어가지 않고 실패한다는 것을 독스트링과 티켓에 분명히 적었다. (6) `git commit --amend`에서 스테이징 목록이 비면 전체로 간다는 것을 못 보는 것에 적었다.
- 남긴 것: 목록 밖의 시험 둘은 사용자 결정으로 남겼다(위 감사 절). 옛 `core 01` 문장이 가리키던, 문서 커밋이 저장소 상태 시험을 깰 수 있다는 까닭은 지금도 맞다고 독스트링에 적었다.
- 다시 돌린 명령: 아래 "둘째 커밋의 pre-commit"과 PR 본문에 적는다(pre-commit이 손으로 치는 다섯을 갈음한다).

## 커밋 둘의 pre-commit(손으로 봤다, 명령은 `git commit -F <메시지 파일>`)

- 첫 커밋(`5f37084`, 코드와 문서 열 파일): `docs-only` 줄이 없고 `test-db`가 돌았으며 pytest 검사가 836.6초에 통과했다. 인용 대조가 경고 셋을 냈고(막지 않는다) 원문이 아닌 말에 따옴표를 씌운 것이라 따옴표를 뗐다.
- 둘째 커밋(`6f51930`, 문서 두 파일): `docs-only...pytest 를 문서 시험 넷으로 좁혔다` 줄이 찍혔고 `test-db`가 나오지 않았으며 pytest 검사가 122.3초에 통과했다(검사 러너 전체 122.73초). 같은 pre-commit의 pyright와 run-hooks 등과 동시에 돌아 손으로 돌린 24~165초 범위에 든다. 836.6초에서 122.3초로 줄었다.
- 부분 커밋의 임시 색인으로는 커밋하지 않았다(독스트링의 못 보는 것 (2)).

## PR 직전 리뷰

- 내장 `/security-review`: 지적 없음. 새 git 호출은 인자 목록과 고정 명령이고 스테이징한 파일 이름이 명령줄에 들어가지 않으며, 문서 이름으로 코드를 숨기는 우회는 로컬 게이트만 좁히고 CI가 받친다.
- CodeRabbit CLI(`coderabbit-review` 에이전트): CLI의 `review` 실행을 권한 분류기가 "민감 정보 유출"로 거절했다(미커밋 코드를 외부 서비스로 보내는 일로 본 것으로 보인다). 우회하지 않았다. 에이전트가 코드와 시험을 직접 읽고 돌려서 낸 보고는 Minor 둘이었다. 고친 것: (1) 독스트링과 티켓의 "23~32초"가 재현되지 않았다(이 에이전트가 147.5초와 48.7초를 쟀다). 다섯 번 잰 24, 32, 49, 148, 165초로 고치고 900초를 "165초의 5.5배"로 적었다. (2) `git commit --amend`는 `--cached`가 옛 HEAD와 색인의 차이만 읽어, 코드가 든 커밋에 문서만 스테이징하면 완성되는 커밋에 코드가 있어도 좁혀진다. 독스트링의 "못 보는 것"에 적었고 시험 하나(`test_코드를_커밋한_뒤_문서만_스테이징하면_문서만으로_읽힌다`)로 고정했다. 이 시험은 처음에 루트의 `base.md`를 문서로 잘못 두어 빨갰고, `docs/note.md`로 고쳐 초록이 됐다(코드가 아니라 시험 입력의 잘못이었다). 그 에이전트가 더 찾은 문서 읽는 시험은 독스트링의 둘뿐이고 나머지는 따로 도는 검사거나 문서 범위 밖(`deploy/`, `evals/`, `.github/`, toml)이었다.
- `bug-perf-review`(CLI 대신): Critical·Major 없음, Minor 하나는 유효했다. 고친 것: 방금 고친 숫자가 같은 문장 안에서 다시 어긋났다(괄호의 다섯 값은 24부터인데 "23초에서"라고 적었다). `tools/run_checks.py`와 시험 독스트링을 "24초"로 맞췄다. 보류한 것 하나는 독스트링에 한 줄 적었다: 감사 훅은 시험 프로세스 안의 파일 열기만 적어 시험이 띄운 자식 프로세스의 문서 읽기를 못 본다(그 에이전트가 그런 자식을 찾지는 못했다). 그 밖에 밀 주장 여섯과 좁히는 쪽으로 틀리는 입력(대문자 확장자, 점 파일, 대소문자만 바꾼 이름 변경, 하위 모듈, 심볼릭 링크 등)을 반박해 봤으나 반례가 없었다. 호출 예산(40회)을 한 번 넘겨 멈췄고, 좁힌 pytest를 pre-commit 환경에서 실제로 돌려 보는 일은 아래 실제 커밋으로 봤다.
- 밀 주장으로 넘긴 새 문장(원문은 각 파일에 있다): `tools/run_checks.py` 독스트링의 남긴 넷 시간(105건이 24초에서 165초, 다섯 번 잰 값은 24, 32, 49, 148, 165초), 시험 독스트링의 24~165초, 900초 주석의 가장 느렸던 165초와 그 다섯 배 반쯤이라는 말, 티켓의 같은 다섯 값.

## 회고

후보 여섯, 승인 둘(회차 둘), 기각 넷, 넘김 없음. 읽은 것: 이 일지, 대기열 항목 넷(`tools/queue_open_rows.py --search`로 찾아 같은 일로 보이는 셋을 열었다). 만료 둘을 닫았다.

**승인**
- **선택 화면의 목록을 grep으로 센 채 닫힌 수로 보였다 → `grilling-premise-check` 8회차.** 남길 시험을 사용자에게 보이고 승인받았는데 그 목록은 경로 문자열 grep이라 파일을 헬퍼나 상수로 여는 시험을 놓쳤다. 셀프 리뷰 두 축이 둘을 더 찾았고 감사 훅을 붙인 전체 pytest(1시간 16분)가 문서 범위를 읽는 시험의 모습을 확인했다. 사건은 위 "감사로 알게 된 것"이다. 조건: 사건(있음), 층(지침. 센 방법이 놓치는 꼴은 자동 검사로 옮길 수 없다), 되돌림(PR 하나). 더하는 것이라 반영은 다섯 번째이고 이 항목은 이미 그 수를 넘어 chore 계기에 들어 있다.
- **고쳐 쓴 숫자 문장이 근거의 값 목록과 어긋났다 → `review-fix-sentence-overstates-adr` 2회차.** 셀프 리뷰를 고치며 쓴 시간 범위가 다른 에이전트의 측정으로 틀렸고, 그 값으로 고친 문장도 괄호의 최솟값과 앞의 말이 어긋나 PR 직전 `bug-perf-review`가 잡았다. 처방이 그 항목의 코드 리뷰 6단계 1 한 줄 자리와 같다. 조건: 사건(있음), 층(지침. 문장이 근거와 맞는지는 판단이다), 되돌림(PR 하나). 반영은 다섯 번째다.

**기각**
- 가드와 훅이 그 자리에서 막고 알린 것: Bash의 작업 폴더를 체크아웃 밖으로 옮기는 명령, 복합 git 명령, `.env`에 닿는 Grep의 glob, 72자를 넘긴 커밋 제목, 한국어가 아닌 중간 문장. 사건 비용이 호출 한 번씩이다.
- CodeRabbit CLI 실행을 권한 분류기가 거절했다: 앱의 가드가 그 자리에서 막고 알렸고, 대체 길인 `bug-perf-review`가 같은 축을 봤다. 고칠 자리가 저장소 밖(사용자의 권한 설정)이다. 반복되면 사람 몫 항목으로 올린다.
- 새 시험이 처음에 빨갰다(루트의 임의 파일 이름을 문서로 둔 시험 입력의 잘못): 시험 먼저의 흐름이 그 자리에서 잡았다.
- `review-report-journal-lag`: 보안 리뷰의 보고는 받은 턴이 아니라 다음 턴에 일지로 옮겼다. 컨텍스트가 압축되지 않았고 잃은 판정이 없어 비용이 없다.
- 감사 훅을 붙인 전체 pytest가 1시간 16분 걸렸다: 이 세션에서 한 번 한 선택이고 되풀이 비용이 아니다. 목록 밖의 시험을 더할지는 사용자의 결정이라 회고 후보가 아니다(아래 "다음").

**대기열 처리**
- 만료로 닫은 것: `grilling-one-decision-per-question`, `uv-with-windows-lock`(둘 다 승인 줄의 가장 늦은 날짜가 2026-11-09이고 `origin/dev` 기준으로도 같았다).
- 이 세션이 닫은 것: `docs-only-commit-full-pytest`(티켓 `.scratch/harness/issues/docs-only-commit-narrow-pytest.md`).

## 다음

- 이 브랜치로 PR을 열어 CI의 결과를 본다. 코드를 바꾼 PR이라 CI의 `python` 잡이 전체 pytest를 돈다. 병합은 요청 범위(PR과 병합까지)에 들어 있다.
- 사용자에게 물을 것: 좁힌 길에서 도는 시험 목록에 `test_hook_prompt_directive`의 규약 낱말 시험과 `test_hook_grill_design_check`의 용어집 시험 둘을 더해 여섯으로 할지. 승인한 목록은 넷이라 이 PR은 넷으로 낸다. 더하면 문서 커밋의 pre-commit이 몇 초 늘고 CI 전에 두 시험이 문서 변경에 빨개지는 것을 잡는다.
- 병합 뒤 `tidy-checkouts`로 주 체크아웃을 당기고 이 워크트리를 정리한다.
