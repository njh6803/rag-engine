# source-sync 10: 일정과 일정 확인 · 2026-11-23

source-sync 티켓 07을 닫은 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/source-sync/issues/10-schedules-and-schedule-check.md`이고, 브랜치는 `feature/10-schedules-and-schedule-check`, 작업은 워크트리 `10-schedules-and-schedule-check`에서 했다. 요청 범위는 PR과 병합까지다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다. 08(지움 반영과 빈 목록 보호)이 나란히 돈다.

## 준비

- 읽은 것: 티켓 10, 명세 `.scratch/source-sync/spec.md`의 "일정과 일정 확인", "설정", "로그", "규약 문서와 낡은 문장", "Testing Decisions", ADR 0022, 07 일지의 "다음"과 "봇 회차", 프로브 `cron-expr`와 `schedule-once`.
- 시험용 PostgreSQL은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.
- 마이그레이션은 더하지 않았다. `sources`의 `schedule`, `next_run_at`, `paused` 칸과 `ScheduleCalculator` 포트, `InvalidScheduleError`가 앞 티켓에서 이미 있었다.

## 지은 것

- **의존성과 규약 문서.** `cronsim` 2.8을 운영 의존성으로 더하고 import 금지 목록(`pyproject.toml`)에 넣어 열일곱이 열여덟이 됐다. 계약 이름(`eighteen`), 그 위의 주석, `CLAUDE.md` 레이어 절의 수를 같이 고쳤다. `docs/constitution/tech.md`의 작업 대기열 칸에 일정과 그 라이브러리를 적었고 헌법 버전은 1.5.9(문구 수정, patch)로 올렸다. 형제 워크트리가 1.5.8을 쓰고 있어 `tools/sibling_overlap.py`로 비켜 갔다.
- **계산기.** `adapters/schedule.py`의 `CronsimScheduleCalculator`. 공백으로 가른 칸이 다섯이 아니면 라이브러리를 부르기 전에 거부한다(라이브러리는 여섯 칸을 초가 앞선 표현식으로 읽는다). 값이 틀린 표현식과 오지 않는 날짜(2월 31일)는 만들 때 라이브러리가 올리는 예외로 거부하고, 50년을 찾아도 오는 날이 없어 멈추는 `StopIteration`도 같은 거부로 바꾼다. 라이브러리의 예외는 원인이나 맥락으로 달지 않아 글이 응답이나 로그로 나가지 않는다.
- **설정.** `RAG_SCHEDULE_TIMEZONE`(기본 `Asia/Seoul`). 모르는 이름이면 설정을 읽는 자리에서 거부하고, 오류는 칸 이름만 싣는다(원칙 V). 서버와 작업자가 같은 설정을 읽으므로 둘 다 기동을 거부한다.
- **카탈로그 포트 넷.** `set_source_schedule`, `set_next_run_at`, `lock_source`(행을 `FOR UPDATE`로 잠그고 읽는다), `lock_due_sources`(`FOR UPDATE SKIP LOCKED`, 지난 시각 순).
- **일정 확인 유스케이스.** `app/schedule_check.py`의 `check_schedules(unit_of_work, calculator, *, now)`가 작업 단위 하나에서 시각이 지난 원천을 잠그고, 원천마다 `enqueue_source_job`(07이 둔 것)으로 동기화 작업을 넣고, 동기화 기록(`trigger`가 `schedule`, 옵션 없음)을 더하고, 다음 시각을 `now` 다음으로 옮긴다. 놓친 회차가 여럿이어도 한 번만 넣는다. 같은 원천의 동기화가 대기 중이거나 실행 중이면 작업은 넣지 않고 기록을 `not_started`(실패 사유 `sync_in_progress`, 시작 시각 비움, 끝 시각은 만든 시각)로 남긴다. 일정 없이 시각만 남은 원천은 시각을 비운다.
- **작업자.** `worker/schedule_loop.py`의 `run_schedule_loop`가 `RAG_WORKER_POLL_SECONDS`마다 일정 확인을 한 번 부르고, `serve`가 슬롯과 따로 띄운다(`schedules` 인자는 필수다). 일정 확인은 자기 작업 단위를 받는다. 슬롯의 작업 단위를 세어 보는 시험(`WatchedUnitOfWork`, `FlakyUnitOfWork`)이 있고, 슬롯이 모두 긴 작업에 잡혀도 일정이 시작되어야 해서다. 실제 조립(`run_worker`)은 같은 작업 단위 묶음을 쓰고, 연결 풀의 하한에 일정 확인의 연결 하나를 더했다. 확인이 실패하면(`TransientFailure`는 경고, 그 밖의 예외는 오류) 로그만 남기고 다음 주기에 다시 한다. 로그는 `schedule_sync_enqueued`와 `schedule_sync_skipped`만 한 줄씩 남기고 아무 일도 없는 주기는 조용하다. 실은 원천 이름, 기록 ID, 작업 ID, 요청 ID뿐이다.
- **관리 API.** `POST /sources`와 `PATCH /sources/{name}`이 `schedule`을 받는다. 받지 않는 글은 422 `validation_error`(`loc`의 끝이 `schedule`, 종류 `invalid_schedule`)이고 응답에 라이브러리 글이 없다. PATCH는 칸이 없으면 그대로 두고 null이면 일정을 없앤다(`model_fields_set`으로 가른다). 다음 실행 시각은 일정을 적거나 고칠 때, 일시 중지에서 다시 시작할 때 `now` 다음으로 채우고, 일정을 없애거나 일시 중지하면 비운다. 이미 돌고 있는 원천을 다시 시작해도 시각을 건드리지 않는다(이미 지난 시각이 밀리지 않게 한다). 일시 중지한 원천의 일정을 고치면 시각은 빈 채로 둔다. 일정을 고치는 요청과 일시 중지는 원천 행을 잠그고 읽는다.
- **시험.** `tests/adapters/test_schedule_calculator.py`(기대값은 프로브 `cron-expr/probe_out.txt`에서 옮겼다), `tests/app/test_schedule_check.py`, `test_schedule_check_concurrent.py`(연결 여덟, 원천 스물, 다섯 회차), `tests/app/test_worker_schedule_loop.py`, `tests/server/test_admin_source_schedule.py`, 설정과 두 기동 명령의 시험(모르는 시간대면 거부)이다. 도우미는 `tests/support/schedule_sources.py`와 `Pipeline.schedules()`다. 변이 표는 `.scratch/source-sync/probes/schedule_mutations.toml`이다.

## 이 세션이 정한 것

- **일정 확인은 슬롯과 따로 돌고 자기 작업 단위를 받는다.** `serve`의 필수 인자 `schedules`(`ScheduleDeps`: 작업 단위, 계산기, 지금 시각)다. 슬롯과 같은 `deps.unit_of_work`를 쓰면 작업 단위의 `begin()` 횟수를 세어 시점을 정하는 기존 시험이 흔들린다. 조립에서는 같은 어댑터를 넘기므로 운영에는 차이가 없다.
- **시각이 이미 지난 원천을 "다시 시작"해도 시각을 다시 계산하지 않는다.** 이미 돌고 있던 원천에 `resume`을 부르면 다음 실행 시각이 뒤로 밀려 일정 확인이 그 회차를 놓칠 수 있다. 일시 중지에서 돌아올 때만 채운다.
- **일정이 없는데 시각만 남은 원천은 일정 확인이 시각을 비우고 지나간다.** 일정을 없앨 때 시각도 함께 비우므로 보통은 없다. 있으면 같은 행이 매 주기 다시 잡히지 않게 한다.
- **저장한 표현식이 계산기가 받지 않는 글이 된 경우는 작업 단위째 되돌린다.** 저장할 때 확인한 글이라 일어나지 않는 일이다. 일어나면 그 주기의 모든 원천이 서지만, 한 원천의 오류가 나머지를 막는 쪽이 조용히 일정이 사라지는 쪽보다 낫다고 보고 로그(`schedule_check_failed`)로 드러낸다.
- **50년 안에 오는 날이 없는 표현식을 만들지 못했다.** 프로브의 표에 든 표현식과 손으로 불러 본 몇 가지 달력 조합은 모두 28년 안에 시각을 냈다(손으로 해 본 것이고 스크립트로 남기지 않았다). 일 칸과 요일 칸을 둘 다 적으면 하나만 맞아도 돌아서 `0 0 31 2 1` 같은 표현식은 받는다(시험이 본다). 그래서 `StopIteration` 거부는 라이브러리를 바꿔 끼운 시험으로 본다.

## 겪은 것

- 편집기의 진단이 여러 번 낡은 값(없는 import, 모르는 타입)을 띄웠다. 판정은 `uv run pyright`의 종료 코드로만 했다.
- 한글을 폭 2로 세는 줄 길이 검사(`E501`)가 독스트링과 시험 이름에서 여러 번 걸렸다. 주석·독스트링은 `tools/rewrap_comments.py`로 감았다.
- 변이 도구가 `expect_output` 표지가 시험 원문에 그대로 있으면 표 전체를 돌리지 않고 거절한다. 틀린 표지로 한 번 돌려 실패 출력을 모은 뒤 받은 값으로 표지를 골랐다.

## 셀프 리뷰 (`/code-review origin/dev`, 두 축)

표준 축과 명세 축을 서브에이전트로 따로 돌렸다. 둘 다 Critical과 Major는 없었다.

**고친 것**
- 표준 축: 2월 31일은 어떤 경우에도 거부한다는 닫힌 주장이 틀렸다. 일 칸과 요일 칸을 둘 다 적으면 하나만 맞아도 돌아서 `0 0 31 2 1`은 받는다. 어댑터 독스트링과 관리 API 독스트링을 고치고 받는 시험을 더했다.
- 표준 축: 관리 API 독스트링의 422 `invalid_schedule` 표현이 틀렸다(응답은 `validation_error`이고 `invalid_schedule`은 오류 종류다). 스토리 22를 일정 확인 독스트링에 더했다. 손으로 해 본 달력 조합을 "쟀다"고 적은 문장은 손으로 해 본 것이라고 고쳤다. 다음 실행 시각 계산이 세 곳에 되풀이되어 `_next_due` 하나로 모았다.
- 명세 축(교착): 일정 확인이 원천 행을 `FOR UPDATE`로 잡으면, 지금 동기화가 작업 행을 넣을 때 외래 키 확인이 거는 `KEY SHARE`를 기다리게 한다. 이때 일정 확인이 같은 원천에 작업을 넣으려 하면 서로를 기다린다. 코드를 읽고 따진 것이라 실제 교착을 재현하지는 못했다. 문서 저장소가 이미 쓰는 `FOR NO KEY UPDATE`(`with_for_update(key_share=True)`)로 `lock_source`와 `lock_due_sources`를 바꾸었다. 일정 확인끼리와 일정을 고치는 요청과는 계속 서로 기다린다. 티켓 본문은 `FOR UPDATE SKIP LOCKED`라고 적었으나 건너뛰는 성질은 같고 키 잠금만 약해졌다. 시험 둘(`test_schedule_check_locking.py`)과 변이 둘을 더했다.
- 명세 축: 일정 확인의 로그 줄이 `try` 밖에 있어 로그가 예외를 내면 반복이 죽을 수 있었다. 로그를 `try` 안으로 옮겼다.
- 명세 축: `PATCH`에 틀린 일정을 주면 없는 원천이 404가 아니라 422로, 밀어 넣는 원천이 409가 아니라 422로 나왔다. 원천 확인을 일정 확인 앞으로 옮겼다. `POST`는 커넥터 설정 확인과 일정 확인의 순서를 가르는 명세가 없어 그대로 두었다.

**남긴 것**
- 저장된 일정 하나가 계산기에서 예외를 내면 그 주기의 모든 원천이 선다(작업 단위째 되돌린다). 저장할 때 확인한 글이라 일어나지 않는 일이고, 일어나면 `schedule_check_failed`로 드러난다. 원천 하나만 건너뛰는 쪽은 그 원천의 일정이 조용히 사라지는 위험과 맞바꾸므로 정하지 않았다.
- 앞뒤 공백이 있는 표현식(`"0 0 * * *\n"`)은 받아서 원문 그대로 저장한다. 계산에는 지장이 없다.
- `RAG_SCHEDULE_TIMEZONE`을 바꿔 다시 띄워도 저장된 `next_run_at`은 옛 시간대로 계산한 값이다. 그 시각이 한 번 지나가야 새 시간대로 바뀐다. 명세에 이 장면이 없다.
- 표준 축의 작은 지적: 동기화 기록을 만드는 영 값 칸 되풀이(`SyncRecord`), `check_once`의 예외 가지 둘, `lock_*` 이름의 명령과 질의 구분, `lock_source(...) or current`의 시험 없는 대체 경로, `_change_schedule`의 Feature Envy.

## 다음 티켓에 넘기는 것

- 11(원천 지우기): 지울 때 `next_run_at`을 비운다. `PATCH`의 일정, `pause`, `resume`은 `require_pull_source`가 지운 원천도 돌려주므로, 지운 원천의 시각을 다시 채울 수 있다(일정 확인은 `deleted_at`으로 거르니 돌지는 않는다). 11이 이 요청들을 막거나 지운 원천에는 시각을 쓰지 않게 해야 한다.
- 12(되살리기): 지운 원천을 되살릴 때 다음 실행 시각을 다시 계산한다(`PullSources._next_due`가 쓸 만하다).
- 14(정리 작업): 일정 확인이 넣는 작업 종류를 더하는 자리는 `app/schedule_check.py`의 `_start`다.
- 08(병렬): `domain/ports.py`에 포트 넷(`set_source_schedule`, `set_next_run_at`, `lock_source`, `lock_due_sources`)을 더했다. 08이 같은 파일에 더하면 문자 겹침을 손으로 푼다.
- 작업자 `serve`의 `schedules` 인자는 필수다. `PullSources` 생성자와 `create`, `update`, `set_paused`는 `calculator`와 `now`를 받도록 바뀌었다.

## 검증

- 변이 표 `.scratch/source-sync/probes/schedule_mutations.toml`은 변이 20개이고 `uv run python tools/mutate.py` 전체 실행에서 모두 기대대로 빨강이었다. 마지막 둘(잠금 변이)은 가짜 표지로 한 번 돌려 받은 실패 출력(`raise TimeoutError from exc_val`, `AssertionError: assert not {<Task finished`)에서 표지를 골랐다. 셀프 리뷰 반영(`_next_due` 도우미, `FOR NO KEY UPDATE`)으로 원문이 바뀐 변이 넷은 원문을 새 코드에 맞춰 다시 쓰고 `--check`로 20개 모두 원문이 한 번씩 있음을 보았다.
- 첫 커밋 시도는 변이 표 검사(`tools/mutate.py --staged`)가 막았다. 변이 여섯의 표지가 pytest의 단언 풀이 줄이어서다. 넷은 같은 실패 출력의 `AssertionError: assert …` 줄로 골랐고, 둘(`assert False`만 찍히던 시험)은 값이 실리는 단언 메시지(`next_run_at is …`, `next_run_at time is …Z`)를 시험에 더해 그 문구로 골랐다. 그 여섯 변이를 다시 돌려 모두 새 표지로 빨강임을 보았다.
- 손으로 치는 검사: `uv run ruff format .`(931개 그대로), `uv run ruff check .`, `uv run pyright`(오류 0), `uv run lint-imports`(계약 둘 모두 유지, "열여덟"), `uv run python tools/check_type_escapes.py`, `uv run python tools/sibling_overlap.py`(번호 겹침 없음, 헌법 1.5.9)가 모두 종료 코드 0이다.
- 검사 러너 전체(`uv run python tools/run_checks.py`): 시험 앞의 검사 열 개는 통과했고 pytest는 5603개 통과, 4개 실패(729초)였다. 실패는 모두 `tests/server/test_admin_pull_source_stuck_calls.py`의 시간 단언(`elapsed < PROMPT_SECONDS`, 값은 1.016~1.172초)이다. 서버 로그의 같은 요청 처리 시간은 42~81ms이고, 그 파일만 홀로 돌리면 모두 통과한다(종료 코드 0). 이 PC에서 xdist로 전체를 돌릴 때의 부하가 클라이언트 쪽 1초 가까운 지연을 만든 것으로 본다. 그 시험도, 그 경로(`create`)의 동작도 이 티켓이 바꾸지 않았다. 시험은 고치지 않았다(원칙 I). 커밋 사전 검사의 두 번째 전체 실행에서는 같은 pytest가 모두 통과했다(544초).

## 회고

- 잘 맞은 것: 일정 확인을 슬롯과 따로 돌리고 자기 작업 단위를 받게 한 결정. 슬롯의 작업 단위를 세는 기존 시험을 건드리지 않았고, 자리가 모두 잡혀 있어도 일정이 도는 것을 시험으로 바로 볼 수 있었다.
- 놓친 것: 원천 행 잠금을 `FOR UPDATE`로 짠 것. 문서 저장소가 같은 이유로 `FOR NO KEY UPDATE`를 쓴다는 선례(`document_store.py` 머리말)가 코드에 있었는데 처음에 그 선례를 찾지 않았다. 명세 축 리뷰가 잡았다. 외래 키가 걸린 행을 잠글 때는 그 선례를 먼저 본다.
- 겪은 것(되풀이): 한글 줄 길이 `E501`이 독스트링과 시험 이름에서 이번에도 여러 번 걸렸다. 이미 `tools/rewrap_comments.py`가 있어 그것으로 처리했다. 새 후보는 올리지 않는다.

## 다음

- 이 티켓의 PR을 열고 병합한다(요청 범위). 병합 뒤 봇 회차가 있으면 이 일지 끝에 "봇 회차"로 적는다.
- 다음 티켓 후보: 11(원천 지우기. 지울 때 `next_run_at`을 비우고 지운 원천에는 시각을 다시 쓰지 않게 한다), 08(지움 반영과 빈 목록 보호, 나란히 돈다), 14(색인 버전 전환). 넘기는 것의 자세한 내용은 위 "다음 티켓에 넘기는 것"이다.
