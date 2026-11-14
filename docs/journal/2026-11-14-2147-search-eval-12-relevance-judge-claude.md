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

## PR 직전 리뷰

CodeRabbit CLI(0.7.5, 무료 요금제)는 한 번 돌았지만 리뷰 서비스 연결이 끊겨(`Connection failed: WebSocket subscription completed unexpectedly`) 끝나지 못했고 발견은 0건이었다. 한도를 더 쓰지 않으려 다시 돌리지 않았다. 규정대로 `bug-perf-review`가 같은 축을 봤고, `coderabbit-review` 에이전트가 CLI 실패 뒤 직접 읽은 보고도 받았다. 두 보고 모두 Critical은 없었다.

- 직접 읽은 보고(`coderabbit-review`): Major 없음, Minor 일곱.
  - 고친 것
    - `claude_judge.py`의 `_QUIET_LOGGERS` 주석이 `httpx2`를 DEBUG로 찍는다고 적었지만 `httpx2/_client.py`의 1084행과 1922행은 INFO로 찍는다(직접 열어 확인했다). 주석을 INFO나 DEBUG로 고쳤다.
    - 머리 독스트링이 `httpcore2`는 단계 이름만 찍는다고 적었지만 `_trace.py`의 `Trace.trace`(43~45행)는 `key=value`로 호스트·포트·응답 헤더까지 DEBUG로 찍는다. 요청은 메서드만 찍어 헤더 값과 본문은 싣지 않는다는 서술로 고쳤다.
    - 408(요청 시간 초과)과 409(잠금 시간 초과)를 영구 실패로 세던 것. SDK의 `_should_retry`(`_base_client.py` 947~954행)는 둘을 재시도 대상으로 본다. 어댑터가 SDK 재시도를 끄고 호출하는 쪽에 맡기므로 같은 집합(`_RETRYABLE_STATUSES`)을 일시 실패로 센다. 시험을 먼저 고쳐 408·409에서 빨강을 봤다.
    - UTF-8이 아닌 `judgments.jsonl`을 읽으면 `UnicodeDecodeError`가 처리되지 않고 스택으로 나갔다. `JudgmentFileError`(메시지는 인코딩 이름만)로 바꿨다. 시험을 먼저 써서 빨강을 봤다.
  - 도달하지 않는 길로 보고 시험만 고정했다: 판정 파일이 묶음 밖 링크일 때 `BundlePathError`의 까닭을 버리고 형 이름만 낸다는 지적. 실제로는 앞의 점검 단계가 이미 `링크를 풀면 묶음 폴더 밖을 가리킨다`를 찍는다. 기존 시험의 단언을 그 문장으로 바꿔 `run`과 `judge` 둘 다 고정했고, 바꾼 시험은 고치기 전에도 초록이었다.
  - 남긴 것: SDK가 읽는 `ANTHROPIC_CUSTOM_HEADERS`가 개발 셸에 있으면 그 헤더가 `RAG_JUDGE_URL`로 간다(`anthropic/_client.py` 250~255행). `api_key`와 `base_url`은 명시해 `ANTHROPIC_*`의 키와 주소는 쓰이지 않는다. `compose.eval.yml`의 서술(코드가 직접 읽는 환경 변수)은 참이라 두었다. 첫 실제 실행 티켓(13)이 개발 셸을 정리할 때 함께 본다.
  - 원칙 V 점검: 질의, 조각 본문, API 키가 로그·표준 오류·예외 메시지·보고서로 새는 길을 찾지 못했다. 이론상의 길 하나는 SDK의 OpenTelemetry 계측(`records_content`)이 켜지고 OTel SDK가 설정된 경우인데 이 도구는 OTel을 설정하지 않아 noop이다. 판정기를 서버 프로세스에 붙이게 되면 다시 본다.
- 대체 보고(`bug-perf-review`): Major 하나, Minor 셋, 보류 하나.
  - Major: 쌍 하나가 영구 실패(`refusal`, `max_tokens`에서 잘린 응답, 400)를 내면 실행 전체가 멈추고, 판정 대기의 순서가 고정이라 다시 돌려도 같은 쌍에서 멈춘다. 동시 작업자 넷이 3쌍씩만 나아가 3,000건이면 1,000번쯤 다시 쳐야 한다. 명세는 이 경우를 정하지 않았다. 판정기 포트의 두 예외로는 쌍 하나의 거절과 인증 실패를 가를 수 없어 설계 결정이라 사용자에게 물었다.
    > 건너뛰고 계속 (Recommended)
    - 고친 것: 영구 실패는 그 쌍만 건너뛰고(`JudgeOutcome.skipped`와 `skip_reasons`) 나머지를 판정한다. 사이에 판정을 받지 못한 채 영구 실패가 `PERMANENT_STREAK_LIMIT`(5)번 이어지면 쌍이 아니라 판정기의 일로 보고 멈춘다. 판정을 하나도 받지 못하고 끝나면 종료 1이다. 건너뛴 수와 까닭을 표준 오류에 알린다. 건너뛴 쌍은 판정 없음으로 남아 다시 돌리면 다시 부르므로 거절의 비용이 한 번 더 든다.
  - Minor 고침: `judgments.jsonl`이 개행 없이 끝나면 덧붙인 줄이 앞 줄에 붙고 `rewrite_sorted`가 `JudgmentFileError`로 막혔다(시험에서 재현했다). `append_judgment`가 개행을 먼저 쓴다. 시험을 먼저 써서 빨강을 봤다.
  - Minor 남김: 재시도 대기(0.25, 0.5, 1초)가 짧고 `Retry-After`를 읽지 않아 429나 529가 2초쯤 이어지면 실행이 멈춘다. 이어서 돌릴 수 있고 데이터는 잃지 않는다. 대기를 더하는 것은 비용과 시간의 판단이라 첫 실제 실행(티켓 13)의 결과를 본 뒤 정한다. 실패한 실행이 몇 건을 남겼는지 알리지 않는 것(`JudgeRunError`가 받은 건수를 싣지 않는다)도 같은 이유로 남겼다.
  - 보류: 두 프로세스가 같은 묶음에서 동시에 `judge`나 `run`을 돌릴 때의 경합(`os.replace`로 한쪽 줄이 사라지고 임시 파일 이름이 하나라 서로 지운다). 보고가 코드를 읽은 것이라 재현하지 않았고 한 사람이 한 묶음을 돌리는 도구라 남겼다.
  - 성능: 3,000건에서 판정 파일의 읽기와 쓰기, 쌍 고르기, `llm_summary`는 문제가 없다. `judge`는 `--yes` 없이 어림만 볼 때도 평가 전체를 돌아 `--yes`로 다시 치면 평가가 두 번 돈다. 설계상 의도다(건수는 평가의 결과로만 알 수 있다).
- 내장 `/security-review`(식별 하위 작업 하나): 확신 8 이상의 취약점은 발견 없음이라 거르는 하위 작업은 돌리지 않았다. 읽은 것은 어댑터 셋(`claude_judge.py`, `judge_settings.py`, `eval_judgments_file.py`), `eval_judge.py`, `bundle_paths.py`, 앱의 `eval_judgments.py`·`eval_report.py`, `tools/search_eval.py`, 프로브 `judge-call/`와 그 출력이고 `uv.lock`은 열지 않았다. 결론은 키가 repr·예외·표준 오류·프로브 출력으로 새는 길 없음, `judgments.jsonl` 경로는 묶음의 경로 판정을 지나고 임시 파일을 먼저 지워 링크를 따라 쓰지 않음, 보고서에는 질의나 조각 본문이 실리지 않음이다. 코드를 읽어 판정했고 판정기 호출이나 로그 출력을 돌려 재지는 않았다. 건너뛰기 처리와 `_ends_with_newline`을 더한 뒤의 작업 나무(커밋하지 않은 수정 포함)를 읽은 것이다.
- 고친 것의 변이 표: 영구 실패 셋(연이어 한계, 한 쌍에 멈춤, 연속을 끊지 않음)과 종료 1, UTF-8, 개행, 408·409를 새 변이로 더하고 기존 429와 "한 쌍이 실패해도 남은 쌍을 계속 부른다"(옛 동작을 겨눈 것)를 고쳤다(23개에서 29개).

## 병합(2026-11-15, `origin/dev` 합치기)

티켓 06(#44)이 먼저 병합되어 `git merge origin/dev`로 합쳤다. 충돌은 아홉 파일이었고 둘 다 같은 줄을 건드린 곳이다(06과 12가 `tools/search_eval.py`, `app/eval_run.py`, `app/eval_report.py`, `adapters/eval_run.py`를 함께 건드린다는 것은 구현 전에 알고 있었다).

- 구조는 06의 것을 바탕으로 두었다. `Stage`와 단계 튜플은 `app/eval_stages.py`, `check_ready`와 `report_problems`와 평가 실행은 `adapters/eval_assembly.py`, 질의 평가는 `Evaluator`다. 12의 것(`TopPassage`, `JUDGED_TOP`, `sha256_text`, `top_passages`, `QueryOutcome.top`)은 그 위에 얹었고, `Evaluator.outcome`이 마지막 단계의 순위로 `top`을 싣는다.
- `QueryOutcome.scored`는 06의 뜻(빠른 실행은 `None`, 후보가 없던 전체 실행은 빈 튜플)을 따랐다. 12는 빈 튜플을 기본값으로 두었으나 `src`에서 `scored`를 읽는 곳은 점수 분포(`eval_score_distribution.py`, 06의 `None` 구분을 쓴다)뿐이고 `llm_summary`는 읽지 않는다.
- `eval_assembly.py`에 공개 함수 `evaluate(prepared)`를 더했다. 06이 `adapters/eval_run.py`의 비공개 `_evaluate`로 두었던 평가 실행을 `run`과 `judge`가 함께 쓰기 위해서다. `eval_judge.py`는 점검을 `prepare_evaluation`(`run`, `inspect`와 같은 길)에 맡기고, 판정기 설정 읽기와 모델·지시문 판 대조가 그 뒤로 왔다(순서가 판정기 설정이 먼저였던 데서 바뀌었다. 한 쪽만 틀린 입력은 같은 오류를 내고, 둘 다 틀리면 이제 묶음의 오류가 먼저 나온다).
- `judge`가 `--config <파일>`을 받는다(티켓 본문의 약속). 판정 파일의 열쇠(`judge_model`, `judge_prompt_version`)가 준 구성에서 오므로 `run`에도 같은 구성을 줘야 `llm` 칸이 같은 줄을 센다. `tools/search_eval.py`의 독스트링이 그렇게 적는다. 06의 `_stage(through: str)`와 12의 `_stage(command, through: list[str])`가 이름이 겹쳐 `_stage_of`와 `_single_stage`로 갈랐다.
- 변이 표: `eval_full_run_mutations.toml`의 둘(`rankings[Stage.RERANK]`, `rerank_candidates`)은 06이 코드를 옮겨 이미 새 원문이었으므로 그쪽을 취했다. `eval_judge_mutations.toml`의 "데이터베이스 점검을 건너뛴다"는 `ruff format`이 호출을 세 줄로 나눈 새 모양에 맞췄다. 네 표 모두 `--check`가 원문이 한 번씩 있음을 확인했다.
- `tests/app/test_eval_report.py`(06이 새로 쓴 시험) 세 곳이 `build_report`를 `llm` 없이 불러 `llm=LlmUnavailable("판정 파일이 없다")`를 더했다. `tests/support/eval_run_support.py`의 `Report`는 `extra="forbid"`라 `llm`, `llm_unavailable` 칸을 받도록 더했다(전에 `test_search_eval_run.py`에 있던 12의 줄이 06의 이동으로 거기 없다).
- 대기열 `surface-tests-after-implementation`은 양쪽이 같은 줄을 3회차로 올려 합쳐 4회차로 적었고(04, 05, 06, 12), README의 두 목록(어댑터·앱 파일, `tools/` 설명)도 양쪽을 합쳤다.
- 병합 뒤 PR 직전 리뷰: 앞의 PR 직전 리뷰는 06을 합치기 전의 코드를 봤으므로 병합에서 새로 쓴 통합 코드를 `bug-perf-review`로 한 번 더 돌렸다(범위는 `git show --cc 7d14d97`과 기준 대비 diff 24개 파일). Critical·Major·Minor는 없었고 Nit 하나였다. 보안 축(`/security-review`)은 이 병합 뒤에는 다시 돌리지 않았다. 앞서 돈 것이 판정기·파일 쓰기·로그를 이미 겨눴고, 병합에서 새로 쓴 코드는 점검 순서와 단계 연결이라 새 공격면이 아니라고 보았다(코드를 읽어 내린 판단이고 도구로 재지 않았다).
  - Nit(`eval_judge.py`의 `_mismatches`와 `eval_judgments.py`의 `llm_unavailable` 문구가 `--config`를 쓴 경우에도 "config.json의 judge_model"이라고만 적어, `judge --config alt.json`에서 어긋나면 사용자가 묶음의 `config.json`을 열게 된다): 고쳤다. 두 문구가 "쓴 구성(--config 또는 묶음의 config.json)의 …"로 적고, `llm_unavailable`은 판정을 `--config`로 했으면 `run`에도 같은 구성을 주라고 덧붙인다. 이 문구를 단언하는 시험과 변이 표는 없었고(grep), `judge_model`·`판` 관련 시험 28건이 홀로 초록이었다.
  - 이 병합 뒤 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨눌 것): 위 두 문구와 "판정을 `--config`로 했으면 `run`에도 같은 구성을 준다"는 안내(`tools/search_eval.py` 독스트링과 티켓 12 Comments가 같은 말을 한다).

## 봇 회차(PR #47, 첫 회차)

PR #47(헤드 070562b)에 CodeRabbit이 인라인 다섯 건을, claude-review가 코드 리뷰 한 건(Critical·Major 없음, Minor 둘, Nit 둘)을 냈다. 첫 회차라 지적마다 근거를 읽고 판단했다.

- 고친 것
  - CodeRabbit Minor(변이 표 208행): "SDK의 자체 재시도를 켠다" 변이의 `tests`가 이름을 바꾸기 전의 시험(`test_요청_한도와_…`)을 가리켰다. 시험 파일을 grep해 낡은 이름임을 확인했고 현재 이름(`test_시간_초과와_요청_한도와_…`)으로 고쳤다. 이 변이를 돌려 기준선 초록, 변이 뒤 빨강을 확인했다. 시험 파라미터가 여섯이라 첫 실패 파라미터(408)의 줄이 표지의 줄 번호와 달랐고 표지를 104행으로 고쳤다.
  - CodeRabbit Critical(자식 로거): `anthropic._base_client`가 요청 본문을 찍는 로거이고 `anthropic`의 자식이다. 파이썬 로깅은 자식에 수준이 직접 주어져 있으면 부모를 WARNING으로 되돌려도 자식 수준이 이긴다. 그래서 `_QUIET_LOGGERS`에 `anthropic._base_client`를 이름으로 더했다. 시험 매개변수에 이 자식을 더해 고치기 전에 빨강(`assert 10 >= 30`)을 먼저 봤다. 앞의 시험은 자식에 수준을 직접 주는 경우를 보지 않았다.
  - CodeRabbit Major(OpenTelemetry): SDK 2.8.0은 `open_telemetry` 인자가 없으면 환경 변수 `ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE`를 읽어, 값이 `content`이고 추적기가 설정되어 있으면 질의와 조각의 글을 span에 실을 수 있다. 앞의 PR 직전 리뷰는 이것을 "이 도구는 OTel을 설정하지 않아 noop"이라며 이론상의 길로 두었다. 이 저장소가 설정하지 않아도 판정기를 서버 프로세스에 붙이면 열리는 길이라 `open_telemetry=False`를 명시했다. 시험은 생성자에 `open_telemetry=False`가 넘어가는지(고치기 전에 빨강, `KeyError`)와, 같은 환경 변수를 켠 채 실제 클라이언트가 추적을 끄는지(`client.open_telemetry["traces"]["enabled"]`가 False)를 본다. 둘째 단언은 SDK가 `False`를 어떻게 풀어 읽는지를 설치된 판으로 확인한 것이다.
  - 변이 표에 두 변이를 더했다(31번 "SDK의 OpenTelemetry 추적을 끄지 않는다", 32번 "요청 본문을 찍는 자식 로거를 따로 올리지 않는다"). 둘 다 기준선 초록, 변이 뒤 빨강이다. 이 표는 30개에서 32개가 됐다.
- 보류한 것
  - CodeRabbit Minor(JSON `null` 응답이 `_verdict`에서 `AttributeError`): `messages.create`가 `Message`가 아닌 값을 돌려주는 경우다. 막으려면 `isinstance(response, Message)`를 해야 하는데 pyright strict의 `reportUnnecessaryIsInstance`가 걸리고, 원칙 II가 `cast`·`type: ignore`를 금한다. 실제 API가 `null` 본문을 낸다는 증거도 없고 재현하지 않았다. 실행이 멈춰도 이미 받은 판정은 파일에 남는다. 다음 절에 넘긴다.
  - CodeRabbit Major(같은 판정 파일의 추가와 교체를 직렬화): 두 프로세스가 같은 묶음에서 동시에 `judge`나 `run`을 돌리는 경합이다. PR 직전 리뷰(`bug-perf-review`)가 이미 같은 경합을 코드를 읽어 보고했고 한 사람이 한 묶음을 돌리는 도구라 남기기로 했다. 프로세스 간 잠금은 플랫폼마다 달라 이 PR의 범위가 아니다. PR 본문의 "남긴 위험"에 적혀 있다.
  - claude-review Minor 둘(`judge_pairs`의 `nonlocal` 계수기, `approved`와 `prune`의 불리언 인자)과 Nit 둘(`finally: rewrite_sorted`가 `JudgeRunError`를 가리는 것, 어댑터 생성자가 전역 로거 수준을 바꾸는 것): 모두 Minor·Nit이고 동작이 틀린 곳이 아니라 읽기 쉬움의 지적이라 이 PR에서 고치지 않고 "다음" 절에 넘긴다. 불리언 인자는 "다음"에 이미 있던 항목이고, `nonlocal` 계수기와 `finally`가 `JudgeRunError`를 가리는 것은 이번에 더했다. 전역 로거 수준은 어댑터 독스트링이 의도로 적고 있어 서버에 붙이는 시점에 조립 함수로 옮긴다.
- 이 반영이 새로 쓴 사실 문장은 아래 목록에 더했다.

## 병합 2(2026-11-15, 티켓 07의 `origin/dev` 합치기)

봇 첫 회차 반영을 푸시한 뒤 `wait_ci`가 "충돌"로 끝났다(`mergeStateStatus`가 `DIRTY`). 그 사이 티켓 07(#48, 추론 기록)이 `dev`에 병합되어 같은 평가 파일을 건드렸다. `git merge origin/dev`로 합쳤고 충돌은 다섯 파일이었다.

- `app/eval_report.py`: `build_report`가 `llm`과 `records`를 둘 다 받고(`records`는 07의 기본값 `NO_RECORDS`), 보고서의 JSON에 `llm`(`llm_unavailable` 포함)과 `records`가 함께 실린다.
- `adapters/eval_run.py`: 두 쪽의 import를 모두 두었다. `run_evaluation`은 판정 파일을 읽은 뒤 07의 `records_run`으로 `guarded`를 부르고, 보고서에 `llm`과 `records=summary`를 둘 다 넘긴다. 07이 `eval_run.py`에 둔 비공개 `_evaluate`는 지웠다. `evaluate(prepared)`가 `eval_assembly.py`에 하나로 있고(06 병합 때 12가 올린 공개 함수와 07의 `evaluation_deps`가 같은 파일에서 만났다) 12의 `judge`와 `run`이 함께 쓴다.
- `tools/search_eval.py`: 사용법에 `run … [기록 옵션]`과 `judge`가 함께 들어갔고, `main()`은 `validate`, `judge`, `inspect`를 기록 옵션을 읽기 전에 가르며 `run`만 `records`를 받는다.
- `compose.eval.yml`, `README.md`: 07의 리랭커 줄과 12의 판정기 설정 블록, 07의 `--records` 설명과 12의 `judge` 설명을 합쳤다.
- **`judge`는 기록 옵션을 받지 않는다.** 07이 `judge`에 대해 정한 것이 없어 `prepare_evaluation`의 기본(`--records off`와 같다)을 그대로 두었다. 그래서 `judge`는 추론 기록을 읽지도 쓰지도 않고, `judge --through rerank`는 리랭커 끝점 `RAG_EVAL_RERANKER_URL`이 반드시 있어야 한다(끝점 없이 쳐 보니 `평가 전용 환경 변수가 없다: RAG_EVAL_RERANKER_URL`과 종료 1이었다. 손으로 쟀고 시험은 없다). 기록을 읽어 판정을 빠르게 돌리는 것은 `judge`가 `--records`를 받게 하는 별도 결정이라 이 PR에서 하지 않았고, 티켓 13이 첫 실제 실행에서 필요한지 본다.
- 변이 표: 여섯 개(`eval_judge` 32, `eval_run` 11, `eval_full_run` 9, `eval_misses` 13, `eval_index` 23, `eval_records` 26) 모두 `--check`가 원문이 한 번씩 있음을 확인했다.
- 대기열: 07이 연 `mutate-check-test-ids`가 이번 봇 회차의 낡은 선택자 사건과 같은 처방이라 회고 17을 새 항목이 아니라 그 항목의 2회차로 고쳤다.

## 검증

- 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`(2 kept), `uv run python tools/check_type_escapes.py`(깨끗), 판정 관련 단위 시험 101 passed(`tests/app/test_eval_judgments.py`, `test_eval_run.py`, `tests/adapters/test_claude_judge.py`, `test_judge_settings.py`, `test_eval_judgments_file.py`, `tests/domain/test_errors.py`). 반영 전에는 전체 `uv run pytest`가 4162 passed였고 부하에서 `ReadTimeout` 둘이 났다가 홀로 돌리니 초록이었다. 전체 시험은 커밋의 pre-commit이 다시 돈다. 첫 커밋 시도에서 pre-commit이 세 가지로 막았다. 티켓 05 변이 표의 `old` 셋이 어긋난 것(`eval_full_run_mutations.toml` 2·7·9번을 고치고 세 변이가 빨강인 것을 다시 확인했다), 일지의 따옴표 경고 둘(인용부호를 지웠다), 계약 시험 둘의 `ReadTimeout`이다. 셋째는 `tests/contract/test_search_complete.py`를 홀로 돌려 19 passed(5분 6초)로 부하 탓임을 확인했다. 두 번째 커밋 시도는 변이 표와 따옴표 훅을 지나 전체 pytest에서 5건이 빨갰고(4165 passed), 그 파일 셋을 홀로 돌리니 19 passed(3분 59초)였다. 세 번째 시도가 통과해 커밋 fc295e6이 만들어졌다.
- PR 직전 리뷰를 반영한 뒤 손으로 친 것: `uv run ruff check src tests`(통과), `uv run ruff format --check .`(630개 이미 맞음), `uv run pyright`(0 errors), `uv run lint-imports`(2 kept), `uv run python tools/check_type_escapes.py`(깨끗), 바뀐 시험(`tests/app/test_eval_judgments.py`, `tests/tools/test_search_eval_judge.py` 55 passed, `tests/adapters/test_eval_judgments_file.py`와 `test_claude_judge.py` 43 passed). 변이 표는 `--check`로 29개 원문이 한 번씩 있음을 확인했고, 새로 더하거나 고친 변이 여덟(9~14, 20, 21)이 모두 기대대로 빨강이었다(20·21은 처음에 표지가 어긋나 매개변수 하나로 좁혀 다시 돌렸다). 전체 `uv run pytest`는 이 반영을 담은 커밋의 pre-commit이 다시 돈다.
- `origin/dev` 병합 뒤 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`, `uv run python tools/check_type_escapes.py`가 통과했다. 단위 시험(`tests/app`, `tests/adapters`, `tests/domain` 가운데 판정·평가 관련) 91 passed. 표면 시험(`tests/tools/`의 judge·run·misses·search_eval·filter_probe)은 테스트 PostgreSQL을 띄우고 `RAG_TEST_DATABASE_URL`을 붙여 143 passed(11분 28초)였다. 첫 실행은 그 환경 변수가 없어 시험이 모두 setup error였고 코드 결함이 아니었다. 새 시험 `test_config로_준_구성의_판정_모델이_판정_파일의_열쇠가_되고_구성_없이는_어긋난다`는 홀로 1 passed다. 변이 표는 네 개(`eval_judge`, `eval_run`, `eval_full_run`, `eval_misses`) 모두 `--check`로 원문이 한 번씩 있음을 확인했다. 변이 30번("judge가 `--config`를 준비 단계에 넘기지 않는다")은 기준선 초록, 변이 뒤 빨강(1 failed)이었다. 병합 커밋의 첫 시도에서 pre-commit의 전체 pytest가 4249 passed, 2 failed였다. 실패는 `tests/app/test_job_lease.py`(5초 안에 끝나야 하는 단언이 약 8.6초)와 `tests/test_serve_command.py`(서버가 30초 안에 뜨지 않음)이고 둘 다 이 변경이 건드리지 않은 시간 시험이다. 두 파일을 홀로 돌리니 14 passed(47초)였다. 부하 탓의 시간 시험 종류이며 대기열의 `load-sensitive-time-tests`와 `serve-startup-test-load-margin`이 다루는 사례라 새 항목을 쓰지 않는다.
- 봇 첫 회차를 반영한 뒤 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`(656개 이미 맞음), `uv run pyright`(0 errors), `uv run lint-imports`(2 kept), `uv run python tools/check_type_escapes.py`(깨끗), `tests/adapters/test_claude_judge.py` 홀로 28 passed. 변이 표는 `--check`로 32개 원문이 한 번씩 있음을 확인했다. 새 변이 31·32는 기준선 초록, 변이 뒤 빨강(각 1 failed)이었다. 표지나 선택자를 고친 변이 18·19·30은 18의 표지(102행이 아니라 104행)만 어긋나 고쳐 다시 돌렸고 셋 모두 기대대로 빨강이었다. 30번(표면 시험)은 `RAG_TEST_DATABASE_URL`을 붙여야 기준선이 초록이다(처음에 환경 변수 없이 돌려 기준선 error였고 코드 결함이 아니었다).
- 07 병합(병합 2) 뒤 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`(666개 이미 맞음), `uv run pyright`(0 errors), `uv run lint-imports`(2 kept)가 통과했고, 변이 표 여섯 개의 `--check`가 모두 원문이 한 번씩 있음을 확인했다. 12와 07이 만나는 시험(`tests/app`의 report·judgments·run, `tests/adapters`의 claude_judge·judgments_file·inference_records·inference_record_files, `tests/tools`의 judge·run·records)을 테스트 PostgreSQL과 `RAG_TEST_DATABASE_URL`을 붙여 224 passed(6분 10초)로 돌렸다. 병합 커밋의 전체 pytest는 pre-commit이 돈다.
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
- PR 직전 리뷰를 반영해 새로 쓴 것: `claude_judge.py`의 머리 독스트링(일시 실패에 408·409 포함, `httpx2`는 INFO, `httpcore2`는 호스트·포트·응답 헤더까지 DEBUG이고 요청의 헤더 값과 본문은 싣지 않는다는 서술)과 `_RETRYABLE_STATUSES` 위의 주석(SDK의 `_should_retry`와 같은 집합이라는 서술), `eval_judgments_file.py`의 `JudgmentFileError`·`append_judgment` 독스트링, `app/eval_judgments.py`의 `PERMANENT_STREAK_LIMIT` 주석과 `judge_pairs`·`JudgeOutcome` 독스트링, `eval_judge.py`의 `_judge_and_record` 독스트링과 건너뛴 쌍의 표준 오류 문구.

- 07 병합(병합 2)에서 새로 쓴 것: `tools/search_eval.py` 독스트링의 "`inspect`와 `judge`는 기록 옵션을 받지 않는다. `judge`는 기록을 읽지도 쓰지도 않아 `--records off`로 `run`을 돌린 것과 같은 평가를 돈다"와 "기록 옵션이 없는 `judge`의 전체 실행도 리랭커 끝점이 반드시 있어야 한다", 일지 병합 2 절의 같은 서술.
- 봇 첫 회차를 반영해 새로 쓴 것: `claude_judge.py` 머리 독스트링의 "요청의 본문을 찍는 로거는 `anthropic`의 자식 `anthropic._base_client`"와 "SDK는 환경 변수 `ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE=content`와 OpenTelemetry의 추적기가 함께 설정되면 질의와 조각의 글을 span에 실을 수 있다(`_tracing.py`)" 서술, `_QUIET_LOGGERS` 위 주석("자식에 수준이 직접 주어져 있으면 부모를 되돌려도 그 수준이 이긴다"), 생성자의 `open_telemetry=False` 주석. 이 일지 "봇 회차" 절의 "`open_telemetry=False`가 추적을 끈다"는 설치된 SDK 2.8.0의 `client.open_telemetry["traces"]["enabled"]`를 시험이 대 본 것이다(환경 변수를 켠 채로 본다).

## 회고

낸 후보 열아홉. 승인 7, 기각 12, 넘김 없음.

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
16. `origin/dev` 병합 커밋의 pre-commit이 첫 시도에서 `tests/app/test_job_lease.py`(5초 단언이 약 8.6초)와 `tests/test_serve_command.py`(서버가 30초 안에 뜨지 않음)로, 둘째 시도에서 `test_serve_command.py`의 같은 시험 하나로, 셋째 시도에서 `test_job_lease.py`의 같은 시험(약 6.1초) 하나로 빨갰다. 넷째 시도는 통과해 병합 커밋 7d14d97이 만들어졌다. 그 뒤 `origin/dev`의 #45(문서와 `tools/plan_table.py`만 바꿈)를 합치는 커밋의 첫 시도도 `tests/contract/test_delete_restore.py`의 `ReadTimeout` 하나로 빨갰고 그 파일을 홀로 돌리면 9 passed(2분 8초)였다. 모두 이 변경이 건드리지 않은 시간 시험이고 홀로 돌리면 초록이었다(서브 시험 둘 14 passed 47초, serve 시험 8.8초). → 승인(회차로 세는 것). 열린 `serve-startup-test-load-margin`을 2회차로 고쳤다(1회차는 06의 같은 시험). 임대 시험은 부하 시간 시험을 받아들여 닫은 종류의 사례라 일지에만 적고 잇지 않는다. 사건이 이어 두 시도를 막았지만 손상(잃은 작업이나 깨진 main·dev)이 아니라 반영하지 않는다.
17. 시험 이름을 바꾼 뒤 변이 표의 `tests` 선택자(208행)가 옛 이름을 가리켰는데 `tools/mutate.py --check`는 `old` 원문만 보아 알리지 않았고, PR 첫 봇 회차가 지적했다. → 승인(회차로 세는 것). 처음에는 새 항목으로 썼으나 `origin/dev`를 합치니 07이 같은 사건에 같은 처방(`--check`가 시험 이름의 존재를 본다)으로 연 `mutate-check-test-ids`가 있어, 내 항목을 지우고 그 항목의 승인 줄을 2회차로 고쳤다(1회차는 07 일지). 더하는 것이라 다섯 번째에 반영한다. 사건은 이 PR의 일이고, 층은 `--check`가 시험 이름의 존재를 확인하는 검사(자동 검사가 가장 높은 층)이며, PR 하나로 되돌릴 수 있다. 같은 도구의 `mutate-marker-discovery`는 표지를 처음 고르는 비용이고 이 사건은 이미 고른 선택자가 낡는 것이라 처방이 달라 잇지 않는다. 이 변이를 낡은 선택자로 돌리면 어떻게 알려지는지는 재지 않았다.
18. 앞의 PR 직전 리뷰 두 축이 로거를 `anthropic`만 올리고 자식(`anthropic._base_client`)이 수준을 직접 받는 경우, SDK의 OpenTelemetry 환경 변수 경로를 놓쳤고 CodeRabbit이 잡았다. → 기각. 봇 리뷰가 제 몫을 한 것이다. 검사로 옮길 길도 없다(SDK 판마다 본문을 싣는 경로가 다르다). 고친 시험이 자식 로거와 `open_telemetry` 인자를 직접 고정한다.
19. 변이 18의 표지(`test_claude_judge.py:102`)가 시험 파일 편집으로 밀려 어긋났고, 이 셸에 `RAG_TEST_DATABASE_URL`이 없어 표면 시험 변이 30의 기준선이 error였다. → 기각. 둘 다 `tools/mutate.py`가 그 자리에서 알렸다(어긋난 표지와 실제 출력, "기준선이 초록이 아니라 변이를 넣지 않았다"). 12번과 13번의 같은 사건이다. 12번은 열린 `mutate-marker-discovery`의 처방과 달라 회차로 세지 않는다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev` 출력 모두 만료할 항목이 없다고 했다. 회차 5 이상은 `measured-claim-beyond-probe`(6회차), `mutate-marker-discovery`(6회차), `crlf-from-script-edits`(5회차)다.

## 다음

- 이 PR이 병합되면 티켓 12는 끝이다. 06이 먼저 병합되어 `judge`의 `--config`는 이 PR에서 더했다(위 병합 절). 티켓 07이 같은 파일(`tools/search_eval.py`, `app/eval_report.py`, `adapters/eval_run.py`)을 건드리면 `EvalReport.llm`, `adapters/eval_run.py`의 `_llm_numbers`, `eval_judge.py`가 `eval_assembly`의 공용 길을 쓰는 것을 읽는다.
- 사람이 고른 표본 40개와 LLM 판정의 일치 확인은 이 티켓이 아니라 티켓 13(`.scratch/search-eval/issues/13-first-judge-run.md`)의 몫이다(이번 실제 호출은 여섯 쌍의 응답 모양 확인이었다).
- `judge`를 다음에 건드리는 티켓이 함께 볼 Minor(이번 셀프 리뷰가 남겼다): `approved`와 `prune`이 `run_judge`에서 `_judge_bundle`로 키워드 전용으로 지나가는 것, `run_judge`의 `except` 넷의 되풀이, `app/eval_judgments.py`가 고르기와 숫자 세기와 호출을 한 모듈에서 맡고 모델·판의 필터가 세 곳에 있는 것, 쓰다 죽어 마지막 줄이 잘린 `judgments.jsonl`을 사람이 손으로 고쳐야 하는 것, SDK 밖의 예외(잘못된 `RAG_JUDGE_URL`의 HTTP 오류 따위)가 두 실패로 바뀌지 않는 것. 봇 첫 회차가 더한 것: `judge_pairs`의 안쪽 함수가 `nonlocal`로 계수기를 바꾸는 출력 인자 꼴(claude-review Minor), `_judge_and_record`의 `finally: rewrite_sorted`가 예외를 내면 `JudgeRunError`를 가리는 것(Nit), 어댑터 생성자가 프로세스 전역 로거 수준을 바꾸는 것(Nit, 서버에 붙일 때 조립 함수로 옮긴다), `messages.create`가 `Message`가 아닌 값(JSON `null` 본문)을 돌려줄 때 `_verdict`가 `AttributeError`를 내는 것(CodeRabbit Minor, 타입 우회 없이는 막을 수 없어 막는 방법부터 정한다), 같은 묶음에서 `judge` 둘을 동시에 돌릴 때 판정 파일의 읽기와 교체 경합(CodeRabbit Major, 위 보류).
- 회차 5 이상인 열린 항목이 셋이다(`measured-claim-beyond-probe` 6회차, `mutate-marker-discovery` 6회차, `crlf-from-script-edits` 5회차). search-eval의 마지막 티켓 뒤에 `next-session` 결정표가 chore 배치로 고른다.
- 전체 `uv run pytest`는 커밋의 pre-commit이 돈다. 부하에서 `ReadTimeout`이 다시 나면 `load-readtimeout-flake`의 사건이다(이 PR의 첫 커밋 시도에서 계약 시험 둘이 2회차였다). 두 번째 커밋 시도에서도 pre-commit 전체 pytest가 5건(`tests/test_serve_command.py` 1, `tests/contract/test_delete_restore.py` 2, `tests/contract/test_first_round_trip.py` 2)을 `ReadTimeout`과 서버 기동 30초 초과로 빨갛게 냈고(4165 passed, 20분 31초) 그 파일 셋을 홀로 돌리니 19개 모두 초록이었다(3분 59초). 그래서 항목이 3회차다. 이 항목은 3회차부터 사례를 고치지 않고 종류 전체를 없애거나 받아들인다. 혼자 다시 돌려 지나가면 막지 않기는 게이트를 느슨하게 하는 길이라 넘김이고, 종류 전체를 없애는 고침(서버를 띄우는 시험의 시간 제한을 부하 여유로 한 곳에서 정하기 따위)은 이 PR이 아니라 chore가 정한다.
