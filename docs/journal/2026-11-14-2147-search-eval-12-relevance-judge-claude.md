# search-eval 12: Claude 관련성 판정기와 `judge`, 보고서의 LLM 숫자 · 2026-11-14

티켓 `.scratch/search-eval/issues/12-relevance-judge-claude.md`를 구현한 기록이다. 브랜치는 `feature/12-relevance-judge-claude`다. 워크트리 `.claude/worktrees/12-relevance-judge-claude`에서 Sonnet 5.5 / high 세션이 했다. 세션 도중 컨텍스트가 한 번 압축되었다. 이번 요청의 범위는 PR과 병합까지다.

## 준비

- 읽은 것: `implement` 스킬, 티켓 12, 명세 `.scratch/search-eval/spec.md`의 "LLM 관련성 판정"과 "자리와 층", ADR 0019, 앞 일지 `2026-11-14-1723-search-eval-05-full-run-rerank.md`의 `## 다음`, 티켓 06과 07.
- 06이 이 브랜치의 기준(`origin/dev`)에 아직 병합되지 않아 `run`에도 `--config`가 없다. 그래서 `judge`에도 더하지 않았다(티켓 본문의 약속: 06과 12 가운데 나중에 병합하는 쪽이 더한다).
- 티켓 06, 07, 12는 `tools/search_eval.py`, `app/eval_report.py`, `adapters/eval_run.py`를 함께 건드린다. 나중에 병합하는 쪽이 충돌을 푼다.

## 한 것

- 의존성과 경계: `anthropic>=2.8,<3`을 운영 의존성으로 선언하고 `pyproject.toml`의 import-linter forbidden 계약(`app`과 `domain`)에 더해 열일곱으로 만들었다. 계약 이름, 위 주석, `CLAUDE.md` 레이어 절의 "열여섯"을 같이 고쳤다.
- `adapters/claude_judge.py`(새 파일): `RelevanceJudge`의 Claude 구현. Messages API를 한 번 부르고 `output_config`의 JSON 스키마로 관련 여부 하나만 받는다. 지시문의 판 `PROMPT_VERSION`은 1이다. SDK의 자체 재시도는 끄고(`max_retries=0`), 예외는 이 저장소가 쓴 글로만 올리고 원인을 잇지 않는다(`from None`).
- `adapters/judge_settings.py`(새 파일): `RAG_JUDGE_URL`, `RAG_JUDGE_MODEL`, `RAG_JUDGE_API_KEY`. 셋이 모두 있어야 조립하고, 모자라면 빠진 이름만 알린다. 키는 `repr`에도 싣지 않는다.
- `adapters/eval_judgments_file.py`(새 파일): `judgments.jsonl`의 읽기, 덧붙이기, 열쇠 순 정렬해 다시 쓰기, `--prune`. 경로는 묶음의 경로 판정을 지난다.
- `adapters/eval_judge.py`(새 파일)와 `tools/search_eval.py`: `judge --through fused|rerank [--yes] [--prune]`. 건수와 비용 어림을 찍고 `--yes`가 없으면 부르지 않는다. 동시 호출 넷, 일시 실패 재시도 셋.
- `app/eval_judgments.py`(새 파일): 판정할 쌍 고르기, `llm` 숫자 세기, 비용 어림, 동시 호출과 재시도.
- `app/eval_run.py`: `JUDGED_TOP`, `sha256_text`, `TopPassage`, `QueryOutcome.top`, 공개 함수 `top_passages`. `app/eval_report.py`: 보고서 JSON과 `report.md`의 `llm` 칸. `adapters/eval_run.py`: 판정 파일을 읽어 `llm` 숫자를 넘긴다.
- `domain/errors.py`: 새 오류 코드 둘 `JUDGE_UNAVAILABLE`(일시)과 `JUDGE_REJECTED`(영구)와 두 집합. 작업 코드의 집합 `JOB_ERROR_CODES`는 건드리지 않았다.
- 시험: 새 파일 다섯(`tests/app/test_eval_judgments.py`, `tests/adapters/test_claude_judge.py`, `test_judge_settings.py`, `test_eval_judgments_file.py`, `tests/tools/test_search_eval_judge.py`)과 가짜 끝점 `tests/support/claude_stub.py`·`claude_server.py`. 기존 시험은 `test_eval_run.py`(2 추가), `test_errors.py`, `tests/tools/conftest.py`, `test_search_eval_run.py`를 고쳤다.
- 변이 표 `.scratch/search-eval/probes/eval_judge_mutations.toml`(23). 실제 호출 프로브 `.scratch/search-eval/probes/judge-call/`와 `probes/README.md`의 행.
- 문서: 티켓 12를 `done`으로 두고 `## Comments`를 더했다. `README.md`, `compose.eval.yml`의 설정 안내, ADR 0007에 이력 `2026-11-14 RelevanceJudge는 ADR 0003의 넷째 플러그인 자리가 아니다`(사용자가 "적는다"로 답했다).

## 정한 것

- 새 오류 코드 둘을 더하고 작업 코드 집합은 그대로 둔다. 판정기에 작업 대기열의 코드 뜻을 빌리면 뜻이 흐려진다. `TransientFailure`와 `PermanentFailure`가 두 집합의 합집합을 받도록 넓혔다(티켓 01이 넘긴 물음의 답).
- `llm` 숫자의 분모: 앞의 둘(LLM이 관련 있다고 본 비율, 기대 근거에 닿은 조각과의 일치 비율)은 판정이 있는 조합만, 판정 없음의 비율은 상위 10개 조합 전체다. 판정 파일이 없거나 맞는 줄이 하나도 없으면 `llm`은 `null`과 까닭이다.
- 빠진 정답 후보는 기대 근거에 닿지 않았는데 LLM이 관련 있다고 본 조각이고, 질의 목록·근거 식별자·문서·순번으로만 가리킨다(글은 싣지 않는다. 원칙 V).
- 비용 어림은 ADR 0019의 3,000건 약 26달러에 건수를 비례시킨 값이다. 다른 모델이면 맞지 않는다고 출력에 적는다.
- `--prune`은 `--yes`와 관계없이 사람이 고른 명령이라 바로 지운다. 모듈 독스트링에 그렇게 적었다.
- 설치된 SDK(anthropic 2.8.0)는 키를 `Authorization: Bearer`로 보낸다. 가짜 끝점 시험은 그 헤더를 단언한다.

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high다. 커밋 전에 돌았고 Critical은 없었다. 표준 축이 Major 하나, 명세 축이 Minor 이하를 냈다.

- 고친 것
  - Major(표준 축이 원칙 V로 냈고 명세 축도 같은 자리를 Minor로 잡았다): `_QUIET_LOGGERS`가 `httpx`, `httpcore`였다. 설치된 SDK는 `httpx2`, `httpcore2`를 쓴다(`anthropic/_utils/_logs.py`, `httpx2/_client.py`). 그래서 아래 HTTP 라이브러리의 로거를 경고로 되돌린다는 서술이 거짓이었고 `ANTHROPIC_LOG=debug`면 `httpx2`가 열린 채 남았다. 이름을 고쳤고, 시험은 세 로거(`anthropic`, `httpx2`, `httpcore2` 부모와 그 자식)가 경고 이상이 되는지 본다. 먼저 시험을 고쳐 옛 코드에서 빨강을 본 뒤 코드를 고쳤다.
  - `judgments.jsonl.tmp`가 묶음 밖 파일을 가리키는 링크이면 정렬해 다시 쓸 때 링크를 따라가 밖의 파일을 덮었다(시험을 먼저 써서 실제로 덮이는 것을 봤다). 쓰기 전에 임시 파일을 지운다.
  - 공백만 든 설정 값을 "있는 것"으로 세던 것을 없는 것으로 본다(시험의 빈 값 케이스에 공백을 더했다. 변이 표 19번의 원문도 고쳤다).
  - `eval_judge.py` 모듈 독스트링: 점검 순서(경로 판정이 단계 3 뒤)를 코드와 맞추고, `--prune`이 `--yes`와 관계없이 바로 지우며 뒤이은 평가가 실패해도 이미 지운 뒤라는 것을 적었다. `_Job`은 도메인의 "작업"과 겹쳐 `_Inputs`로 바꿨다(변이 표 22번의 원문도 고쳤다). `_judge_and_record`의 `rewrite_sorted` 두 번 호출을 `finally` 하나로 모았다.
  - `EvalReport.llm`과 `build_report`의 `llm`을 필수로 바꾸고 호출자 없는 기본값 `LLM_NOT_READ`를 지웠다(Speculative Generality).
  - 낡은 서술: `tests/support/fake_judge.py`의 미래형, `domain/errors.py` 모듈 독스트링에서 판정기 코드 둘이 빠진 것, `compose.eval.yml`의 "넷과 셋뿐"이라는 닫힌 주장(SDK가 `ANTHROPIC_LOG` 같은 자기 환경 변수를 따로 읽는다)과 README의 짝, 티켓 Comments의 SDK 줄 번호 라벨(521~541줄이 오류 본문을 메시지에 싣는 자리, 2226~2258줄은 비동기 전송의 DEBUG 로그, 재시도는 934줄과 2280줄), 프로브 README와 티켓 Comments의 헤더를 `Authorization: Bearer`로 보냈다는 서술(프로브는 헤더를 찍지 않았다. SDK 소스를 읽은 것과 API가 요청을 받아들인 것만 확인했다).
- 남긴 것(Minor와 Nit, 동작을 바꾸지 않거나 이번 변경의 범위를 넘는다)
  - 키워드 전용 `approved`, `prune`이 `run_judge`에서 `_judge_bundle`로 지나간다(`CODING_STANDARDS.md`의 불리언 플래그). CLI 인자 값을 그대로 넘기는 것이고 고치려면 `judge`의 표면을 다시 짜야 한다.
  - `run_judge`의 `except` 넷이 같은 출력과 `return 1`을 되풀이한다.
  - `app/eval_judgments.py`가 고르기, 숫자 세기, 호출을 한 모듈에서 맡고 모델·판의 필터가 세 곳에 있다(`Judgment`에 묶는 안).
  - 쓰다 죽어 마지막 줄이 개행 없이 잘리면 다음 읽기가 줄 번호를 알리며 1로 끝나고 사람이 손으로 고쳐야 한다(덧붙이기는 한 줄 한 번의 쓰기다).
  - `anthropic.AnthropicError`와 `APIStatusError` 밖의 예외(잘못된 `RAG_JUDGE_URL`의 httpx 오류 따위)는 두 실패로 바뀌지 않는다.
  - `--prune`이 평가보다 앞서 지운다(독스트링에 사실대로 적었다).
  - `prune_judgments`와 `_stage`의 명령·조회 분리, 상수를 고정하는 시험 하나, `del world, claude_url`의 되풀이.
- 다시 돌린 것: 아래 검증에 적었다.

## 검증

- 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`(2 kept), `uv run python tools/check_type_escapes.py`(깨끗), 판정 관련 단위 시험 101 passed(`tests/app/test_eval_judgments.py`, `test_eval_run.py`, `tests/adapters/test_claude_judge.py`, `test_judge_settings.py`, `test_eval_judgments_file.py`, `tests/domain/test_errors.py`). 반영 전에는 전체 `uv run pytest`가 4162 passed였고 부하에서 `ReadTimeout` 둘이 났다가 홀로 돌리니 초록이었다. 전체 시험은 커밋의 pre-commit이 다시 돈다. 첫 커밋 시도에서 pre-commit이 세 가지로 막았다. 티켓 05 변이 표의 `old` 셋이 어긋난 것(`eval_full_run_mutations.toml` 2·7·9번을 고치고 세 변이가 빨강인 것을 다시 확인했다), 일지의 따옴표 경고 둘(인용부호를 지웠다), 계약 시험 둘의 `ReadTimeout`이다. 셋째는 `tests/contract/test_search_complete.py`를 홀로 돌려 19 passed(5분 6초)로 부하 탓임을 확인했다. 두 번째 커밋 시도는 변이 표와 따옴표 훅을 지나 전체 pytest에서 5건이 빨갰고(4165 passed), 그 파일 셋을 홀로 돌리니 19 passed(3분 59초)였다.
- 변이 표: 23개 모두 기대대로 빨강이다. 셀프 리뷰 반영 뒤 전체 실행은 세 번 걸렸다. 첫 번째는 22번의 원문이 `_Job`→`_Inputs` 개명으로 어긋나 아무 파일도 쓰지 않고 멈췄다. 두 번째는 이 셸에 `RAG_TEST_DATABASE_URL`이 없어 표면 시험 셋의 기준선이 error라 변이를 넣지 않았다(컨테이너는 떠 있었다. 환경 변수를 붙여 다시 돌렸다). 세 번째에서 21개가 기대대로였고 12번과 14번은 결과가 빨강이었지만 줄 번호 꼴 표지(`…py:128: AssertionError`, `…py:182: AssertionError`)가 시험 파일의 편집으로 밀려 어긋났다. 표지를 새 줄 번호(143, 189)로 고치고 그 둘만 다시 돌려 기대대로였으며, `--check`로 변이 뒤에 소스의 원문이 한 번씩 있는 것(원상태)을 확인했다.
- 시험 순서를 솔직히 적는다. 앱 시험(`tests/app/`)은 시험을 먼저 쓰고 구현했다. 표면 시험(`tests/tools/test_search_eval_judge.py`)도 구현 전에 썼지만 구현 전에 한 번 실행해 빨강을 보지는 않았다. 빨강은 변이 표가 구현을 틀리게 했을 때 시험이 실패하는 것으로 확인했다. 셀프 리뷰가 낸 세 수정(로거, 임시 파일 링크, 공백 값)은 시험을 먼저 고쳐 옛 코드에서 빨강을 본 뒤 고쳤다.
- 변이 표를 처음 돌렸을 때 두 빈틈이 있었다(길이 한도에서 잘린 응답을 읽어 보는 변이 16번과 상위 조각 수를 다섯으로 줄이는 변이 23번이 초록으로 지나갔다). 16번은 시험을 보강했고 23번은 `top_passages`를 공개 함수로 올려 앱 시험을 더했다. 그 뒤 23개 모두 기대대로 빨강이었다. 셀프 리뷰 반영 뒤 22번의 원문이 `_Job`→`_Inputs` 개명으로 어긋나 표를 고쳤다.
- 실제 Claude API 호출 확인은 했다. 사용자가 건수 7건과 비용 어림 약 0.061달러를 보고 승인했고 자기 터미널에서 프로브를 돌렸다(이 세션의 `.env`를 읽는 명령은 권한 판정이 거부해 우회하지 않았다). 모델 `claude-opus-5-5`, 여섯 쌍이 모두 기대와 일치했고 응답 모양은 어댑터 프로브의 꼴대로였다. 표본이 여섯 쌍이라 정확도는 말하지 않는다. 사람이 고른 40개와의 일치 확인은 티켓 13의 몫이다.
- 프로브 출력이 사용자의 PowerShell 리다이렉션으로 cp949였다. UTF-8·LF로 바꿔 커밋했다.
- `httpx2`와 `httpcore2`의 DEBUG 출력이 본문을 싣는지는 로그를 실제로 켜서 재지 않았다. 소스에서 본문을 싣는 호출을 찾지 못했을 뿐이다.

## 이 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨눌 것)

- `claude_judge.py` 머리 독스트링의 로거 단락(`httpx2`는 메서드·주소·상태 코드를, `httpcore2`는 연결과 전송 단계의 이름을 찍는다는 서술)과 `_QUIET_LOGGERS` 위의 주석.
- `eval_judge.py` 모듈 독스트링의 점검 순서 1~4와 `--prune` 단락.
- `eval_judgments_file.py`의 `_replace` 독스트링(끊긴 실행이 남긴 임시 파일, 링크를 따라 쓰는 것).
- `compose.eval.yml` 4행과 `README.md` 72행의 환경 변수 서술, `domain/errors.py` 모듈 독스트링의 판정기 코드 문장.
- 티켓 12 `## Comments`의 SDK 줄 번호 라벨과 로거 이름 서술, 프로브 README의 judge-call 행.
- 이 일지의 회고 14·15번과 검증 절의 pre-commit 서술(변이 표 05의 2·7·9번 수정, 계약 시험 둘의 부하 flake 판정).

## 회고

낸 후보 열다섯. 승인 5, 기각 10, 넘김 없음.

1. 표면 시험(`tests/tools/test_search_eval_judge.py`)을 구현 전에 썼지만 구현 전에 한 번 실행해 빨강을 보지 않았다(원칙 I). → 승인(회차로 세는 것). 열린 항목 `surface-tests-after-implementation`이 이미 처방한 사건이라 그 승인 줄을 3회차로 고쳤다(1·2회차는 04·05 일지). 이번에는 순서가 아니라 빨강 실행이 빠졌고, 그 항목의 처방(구현 전 빨강을 한 번 실행한다)이 막는 사건이다. 셀프 리뷰 두 축은 이 일을 지적하지 않았고 이 일지가 스스로 밝혔다. 다섯 번째 전이라 반영하지 않는다.
2. 사용자가 자기 터미널에서 돌린 프로브의 출력이 파일로 받자 cp949였다. 커밋 전에 UTF-8·LF로 바꿨다. → 승인(회차로 세는 것). 열린 항목 `python-i-utf8`을 4회차로 고쳤다. 이 항목의 처방은 `-I` 뒤에 `-X utf8`을 붙이는 것이라 이 사건(`-I` 없이 파일 리다이렉트)을 그대로 막지는 못하지만, 윈도 Python이 로케일 인코딩으로 쓰는 같은 뿌리라 센다. 5회차에 반영할 때 어디로 줄을 `-I` 한정에서 리다이렉트 출력 전반으로 넓힐지 정한다.
3. 전체 `uv run pytest`(4162 passed)에서 이 변경이 건드리지 않은 기존 시험 둘(`tests/contract/test_tool_errors.py`의 로그 시험, `tests/server/test_ingest_api.py`의 폼 칸 시험)이 `ReadTimeout`으로 빨갰고 홀로 돌리니 초록이었다. → 승인(새 항목 `load-readtimeout-flake`, 1회차). 고침이라 문턱 없이 반영하지만 이 PR은 기능 PR이라 다른 시험을 고쳐 싣지 않고 대기열에 둔다. 원인은 재지 않았다. `origin/dev`에 그 사이 들어온 커밋이 없어 상류가 이미 고친 것도 아니다. 닫힌 `token-expiry-test-load-margin`과 같은 부하 시험 종류다.
4. Grep 도구로 `.venv/Lib/site-packages/anthropic` 폴더를 검색하자 `httpx2`가 든 파일이 있는데도 일치 없음이 나왔다(같은 파일을 직접 가리키면 나왔다). → 승인(새 항목 `grep-skips-gitignored-venv`, 1회차. 더하는 것이라 다섯 번째에 반영한다). 폴더 검색이 `.gitignore`를 따라 `.venv`를 건너뛰는 것으로 보이지만 원인은 재지 않았다. 호출 몇 번을 잃었다.
5. 판정기 어댑터가 낮출 로거를 `httpx`, `httpcore`로 가정했다(설치된 SDK는 `httpx2`, `httpcore2`). → 기각. 셀프 리뷰 두 축이 잡았고 `code-review`의 주장 검증 목록이 겨눈 사건이라 리뷰가 제 몫을 한 것이다. 검사로 옮길 길도 없다(설치된 판마다 로거 이름이 다르다).
6. `judgments.jsonl.tmp`가 밖을 가리키는 링크이면 정렬해 다시 쓸 때 링크를 따라 밖의 파일을 덮었다. → 기각. 명세 축이 잡은 코드 결함이고 시험을 먼저 써서 빨강을 본 뒤 고쳤다(리뷰가 제 몫을 한 것).
7. 낡은 서술 다섯(`fake_judge.py`의 미래형, `errors.py`의 판정기 코드 누락, `compose.eval.yml`의 "넷과 셋뿐", 티켓 Comments의 SDK 줄 번호 라벨, 프로브 README의 헤더 측정 서술). → 기각. 주장 검증 목록이 겨눈 사건이다.
8. 셀프 리뷰 반영에서 `_Job`을 `_Inputs`로 바꾸자 변이 표 22번의 원문이 어긋났다. → 기각. `tools/mutate.py`가 아무 파일도 쓰기 전에 "변이 파일 오류"로 알렸고 `--check`가 고친 표를 확인했다.
9. 변이 표를 처음 돌렸을 때 약한 시험 둘(16번, 23번)이 드러났다. → 기각. 변이 표가 제 몫을 한 것이고 시험을 보강해 고쳤다.
10. IDE가 편집 직후 낡은 pyright 진단(`Import ... could not be resolved`, `Type of ... is unknown`)을 쏟았다. → 기각. 색인이 늦은 소음이고 `uv run pyright`가 판정자다(03 회고 8, 04 회고 7, 05 회고 6과 같다).
11. 권한 판정이 `.env`를 읽는 프로브 실행 명령을 거부했고, 워크트리 가드가 heredoc 덧붙이기를 거부했다. → 기각. 이미 있는 가드가 그 자리에서 막았고 우회하지 않았다(`.env`는 사용자가 자기 터미널에서 돌렸고 heredoc은 `Edit`으로 대신했다).
12. 변이 표의 줄 번호 꼴 표지 둘(12번, 14번)이 시험 파일을 편집하자 밀려 어긋났고, 전체 실행을 한 번 더 들였다. → 기각. `tools/mutate.py`가 어긋난 변이와 실제 출력을 그 자리에서 알렸다. 열린 `mutate-marker-discovery`는 표지를 처음 고르는 비용을 다루고 이 사건(이미 고른 표지가 편집으로 밀림)은 처방이 달라 회차로 세지 않는다.
13. 새 셸에서 `RAG_TEST_DATABASE_URL` 없이 변이 표를 돌려 표면 시험 셋의 기준선이 error가 났다. → 기각. `tools/mutate.py`가 "기준선이 초록이 아니라 변이를 넣지 않았다"로 알렸고 시험의 오류 문장이 필요한 환경 변수와 값을 그대로 일러 줬다.
14. 첫 커밋 시도에서 pre-commit의 `check-mutations`가 막았다. 티켓 05의 변이 표(`eval_full_run_mutations.toml`)가 가리키는 `src/rag_engine/app/eval_run.py`의 원문 셋(2·7·9번)을 이 변경이 고쳐 `old`가 어긋났기 때문이다. → 기각. 이미 있는 훅이 커밋 전에 그 자리에서 막았다. 표의 `old`와 `new` 셋을 새 원문으로 고쳤고 세 변이를 다시 돌려 모두 기대대로 빨강이었다(`리랭커에 절 경로를 빼고 조각 글만 보낸다` 1 failed, `리랭크 뒤 적중을 합친 뒤 순위로 센다` 1 failed, `합친 뒤의 후보 전부가 아니라 앞의 하나만 리랭크한다` 1 failed).
15. 같은 커밋 시도에서 pre-commit의 전체 pytest가 이 변경이 건드리지 않은 `tests/contract/test_search_complete.py`의 시험 둘에서 `ReadTimeout`으로 빨갰다. 같은 PC에서 다른 세션(다른 워크트리의 xdist 작업자와 `C:/project/agent`의 vitest)이 CPU를 쓰고 있었다. 그 파일을 홀로 다시 돌리니 19 passed(5분 6초)였다. → 승인(회차로 세는 것). 3번과 같은 `ReadTimeout`이지만 시험 파일이 다른 사례다. `load-readtimeout-flake`의 승인 줄을 2회차로 고쳤고, 두 번째 커밋 시도의 같은 종류 사례(아래 다음 절)로 3회차가 됐다. 이 항목은 같은 종류의 결함이 사례마다 다른 시험에서 나오는 끝이 열린 결함 종류라, 세 번째 사례부터는 사례를 고치지 않고 종류 전체를 없애는 고침이나 받아들임 가운데 하나를 정한다. 기능 PR이라 지금은 시험을 고쳐 싣지 않는다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev` 출력 모두 만료할 항목이 없다고 했다. 회차 5 이상은 `measured-claim-beyond-probe`(6회차), `mutate-marker-discovery`(6회차), `crlf-from-script-edits`(5회차)다.

## 다음

- 이 PR이 병합되면 티켓 12는 끝이다. 티켓 06이 병합되지 않은 채라 `judge`에 `--config`가 없다. 06과 12 가운데 나중에 병합하는 쪽이 `judge`에 `--config`를 더한다(티켓 12 `## Comments`의 `--config` 항목). 06이 읽을 것: 이 일지의 "정한 것", `app/eval_report.py`의 `EvalReport.llm`과 `adapters/eval_run.py`의 `_llm_numbers`(06이 놓친 까닭과 나눠 본 숫자를 더할 때 같은 자리를 건드린다).
- 사람이 고른 표본 40개와 LLM 판정의 일치 확인은 이 티켓이 아니라 티켓 13(`.scratch/search-eval/issues/13-first-judge-run.md`)의 몫이다(이번 실제 호출은 여섯 쌍의 응답 모양 확인이었다).
- `judge`를 다음에 건드리는 티켓이 함께 볼 Minor(이번 셀프 리뷰가 남겼다): `approved`와 `prune`이 `run_judge`에서 `_judge_bundle`로 키워드 전용으로 지나가는 것, `run_judge`의 `except` 넷의 되풀이, `app/eval_judgments.py`가 고르기와 숫자 세기와 호출을 한 모듈에서 맡고 모델·판의 필터가 세 곳에 있는 것, 쓰다 죽어 마지막 줄이 잘린 `judgments.jsonl`을 사람이 손으로 고쳐야 하는 것, SDK 밖의 예외(잘못된 `RAG_JUDGE_URL`의 HTTP 오류 따위)가 두 실패로 바뀌지 않는 것.
- 회차 5 이상인 열린 항목이 셋이다(`measured-claim-beyond-probe` 6회차, `mutate-marker-discovery` 6회차, `crlf-from-script-edits` 5회차). search-eval의 마지막 티켓 뒤에 `next-session` 결정표가 chore 배치로 고른다.
- 전체 `uv run pytest`는 커밋의 pre-commit이 돈다. 부하에서 `ReadTimeout`이 다시 나면 `load-readtimeout-flake`의 사건이다(이 PR의 첫 커밋 시도에서 계약 시험 둘이 2회차였다). 두 번째 커밋 시도에서도 pre-commit 전체 pytest가 5건(`tests/test_serve_command.py` 1, `tests/contract/test_delete_restore.py` 2, `tests/contract/test_first_round_trip.py` 2)을 `ReadTimeout`과 서버 기동 30초 초과로 빨갛게 냈고(4165 passed, 20분 31초) 그 파일 셋을 홀로 돌리니 19개 모두 초록이었다(3분 59초). 그래서 항목이 3회차다. 이 항목은 3회차부터 사례를 고치지 않고 종류 전체를 없애거나 받아들인다. 혼자 다시 돌려 지나가면 막지 않기는 게이트를 느슨하게 하는 길이라 넘김이고, 종류 전체를 없애는 고침(서버를 띄우는 시험의 시간 제한을 부하 여유로 한 곳에서 정하기 따위)은 이 PR이 아니라 chore가 정한다.
