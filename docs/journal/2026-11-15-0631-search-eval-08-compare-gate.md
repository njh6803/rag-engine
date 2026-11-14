# search-eval 08: `compare --gate fast|full`과 기준 보고서 견줌 · 2026-11-15

티켓 `.scratch/search-eval/issues/08-compare-gate.md`를 구현한 기록이다. 브랜치는 `feature/08-compare-gate`다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `08-compare-gate`에 들어와 이어 갔다. 티켓 12(PR 47)가 `tools/search_eval.py`를 건드릴 수 있다고 지시문이 알려서, 병합 전에 형제 겹침을 본다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 08, 명세 `.scratch/search-eval/spec.md`의 "CI 게이트와 기준 보고서"와 보고서 절, 앞 일지 `2026-11-14-2016-search-eval-07-inference-records.md`의 "다음", 티켓 07의 `## Comments`.
- 실제 TEI(Docker와 GPU)는 띄우지 않았다. 조각 임베딩 해시의 통합 시험은 `TeiStub`와 시험 PostgreSQL로 돈다.

## 한 것

- `app/eval_compare.py`(새 파일): 순수 판정. `Gate`(FAST는 합친 뒤 줄, FULL은 리랭크 뒤 줄), `compare_reports`, `CompareResult`. 하락폭은 상위 5 적중률 2%p, MRR 0.02이고 정확히 경계는 통과한다. 내용 해시, 구성(판정 칸 둘을 뺀 칸), 그 게이트가 읽는 기록 파일의 해시가 다르거나 줄이 없으면 숫자를 견주지 않는다.
- `adapters/eval_compare.py`(새 파일): 보고서와 기준 보고서를 읽어 판정에 넘기고 종료 코드와 표를 낸다. 기준 보고서는 `BundlePaths`(02의 경로 판정)를 지난다. 보고서 자리에 폴더를 주면 그 안의 `report.json`을 읽는다.
- `domain/eval_set.py`: `JUDGE_CONFIG_KEYS`. `tools/search_eval.py`: `compare` 하위 명령. `README.md`, 명세의 보고서 절과 CI 게이트 절.
- `adapters/inference_records.py`와 `app/eval_report.py`: `run` 보고서의 `records.files`가 `run`이 읽지 않는 조각 임베딩 기록 파일(`chunk-embeddings.*`)의 해시도 싣는다. 07이 남긴 한계를 받은 것이다.
- 시험: `tests/app/test_eval_compare.py`(38), `tests/tools/test_search_eval_compare.py`(39), `tests/tools/test_search_eval_compare_records.py`(5. 실제 DB와 TEI 스텁), `tests/domain/test_eval_set.py`(판정 칸 상수와 보고서 칸을 묶는 시험 하나).
- 변이 표 `.scratch/search-eval/probes/eval_compare_mutations.toml`(21).

## 정한 것

- 07의 한계 하나(조각 임베딩 해시)는 `compare`가 묶음 폴더의 기록 파일에서 해시를 직접 계산하는 길 대신, `run` 보고서에 칸을 더하는 길로 받았다. 기록을 손으로 고쳐도 기준 보고서를 만든 때의 `run`이 같은 해시를 싣고 있어 `compare` 혼자 견줄 수 있고, 맵에 열쇠를 더하는 것이라 보고서의 판은 올리지 않았다. `records.json`이 없는 `read`와 `off`는 어느 파일의 해시도 싣지 않는다.
- 07의 다른 한계(요청 지문과 TEI 판의 불일치)는 `compare`가 잡지 않고 `validate`에 맡긴다. 어댑터의 모듈 독스트링에 적고 한계도 같이 적었다. 빠른 게이트의 잡이 `validate`를 `run`보다 앞에 두게 짓는 것은 티켓 11의 몫이다.
- 하락폭은 상수(`HIT_AT_5_DROP`, `MRR_DROP`)로만 두었다. 티켓 11의 흔들림 측정이 값을 확정한다.

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high, 명세 축은 세션 모델이다. 기준은 `6dbb08c`이고 수정 7개와 미추적 6개를 봤다.

- Critical 하나(명세 축): 하락폭 경계가 실제 보고서의 값에서 깨졌다. 보고서의 `hit_at_5`는 `맞힌 수 / 질의 수`인 부동소수점이라 끝자리에 오차가 있고, 처음 판은 소수 글자 그대로 `Decimal`로 뺄 뿐이라 정확히 2%p 떨어진 쌍이 실패로 읽혔다(질의 수 50~1000에서 정확히 2%p 하락 10310쌍 가운데 1712쌍이라고 명세 축이 쟀다). 내 시험은 모두 `0.82`와 `0.80` 같은 짧은 소수라 잡지 못했다. 차를 소수 아홉째 자리로 반올림하게 고쳤고(`_gap` 하나로 모아 `difference`와 판정이 같은 값을 쓴다), 질의 수 50부터 1000까지 모든 맞힌 수에서 정확히 2%p 하락이 통과하는 시험과 질의 하나가 더 틀리면 실패하는 시험을 더했다. 변이 3(반올림을 둘째 자리로 거칠게)과 21(반올림을 뺀다)이 기대한 빨강이다. 구현을 고치기 전에 빨강을 본 것은 아니다.
- 표준 축 Minor: 어댑터가 실패를 `None`으로 돌려주고 `compare_command`가 `is None`마다 반복하던 것을 `_CompareFailed` 예외로 바꿨다(`CODING_STANDARDS.md`의 "실패는 예외로"). 약한 단언(종료 코드만 본 시험, `"보고서"`만 본 시험)에 표와 까닭을 더했다. 조사가 어긋난 문장(`baseline-fast.json를`)을 고쳤다.
- 이번 변경이 거짓으로 만든 문장: `eval_report.py`의 표 머리 "읽은 기록 파일"을 "기록 파일"로, 명세 CI 게이트 절과 시험 절의 "읽은 기록 파일"에 조각 임베딩을 덧붙였다. `RecordsSummary`와 `_chunk_file_hashes`의 독스트링이 말한 "디스크에 있으면 싣는다"는 `records.json`이 없는 `read`에서 거짓이라 그 조건을 적었다. 티켓의 `InferenceRecords`는 없는 클래스라 `RecordsRun`으로 고쳤다. "15분 안팎"은 잰 적 없는 어림이라 잰 값(`test_search_eval_records.py`의 기준선 258초)으로 바꿨다. ADR 0018의 "보고서가 읽은 기록 파일마다 해시를 싣고"는 사실을 더하기만 해 여전히 참이라 이력도 포인터도 달지 않았다.
- 판정 칸의 이름 상수(`JUDGE_CONFIG_KEYS`)가 `config_values`의 리터럴과 따로 놀 수 있어, 두 값을 묶는 시험을 더했다. NaN이 든 보고서는 읽지 못하는 파일로 거절한다(`allow_inf_nan=False`).
- 남긴 것: `MetricRow.stage`와 `MetricChange.metric`이 문자열인 것, `app/eval_compare.py`가 기록 파일 이름을 따로 적는 것(앱 계층은 어댑터의 `record_files`를 부를 수 없다), 전체 게이트의 `rerank.jsonl` 이름을 진짜 전체 `run`과 맞대는 시험이 없는 것(티켓 14·15). 티켓 08 `## Comments`에 이유와 함께 적었다.
- 이 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨냥할 것): `app/eval_compare.py` 모듈 독스트링의 반올림 문단과 `_gap` 독스트링, `adapters/eval_compare.py` 모듈 독스트링의 `validate` 문장과 NaN 문장, `RecordsSummary`·`summary()`·`_chunk_file_hashes`의 독스트링, 명세 CI 게이트 절의 새 문장 셋(반올림, 줄 누락, 폴더 인자), 티켓 08의 `## Comments`.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`, `uv run python tools/run_checks.py`(전부 통과, pytest 437초), 변이 표의 DB 없는 열여덟(1~17, 21)이 모두 기대한 빨강.

## 검증

- 시험 순서를 솔직히 적는다. 앱 시험과 표면 시험은 구현 전에 먼저 썼고 모듈이 없다는 까닭으로 빨강을 봤다. 그 빨강은 구현의 까닭이 아니라서 변이 표가 구현을 틀리게 했을 때 시험이 빨개지는 것으로 다시 확인했다(20개를 한 번에 돌려 모두 기대대로, 반올림 변이 하나를 더해 21개).
- 변이 표의 표지는 처음에 자리 표시(`MARKER`)로 두고 첫 실행의 실패 출력에서 골랐다. 도구가 보여 주는 실패 출력이 서버 로그 꼬리로 채워지는 통합 변이(18~20)는 변이를 손으로 넣어 해당 시험만 돌려 단언 문구를 읽었고, 읽은 뒤 소스를 원문으로 되돌렸다(`if True`·`if False`의 잔존이 없음을 Grep으로 봤다).
- 검사 러너 전체가 두 번 모두 통과했다(첫 판 pytest 437.1초, 셀프 리뷰 반영 뒤 437.4초). 이 세션에서는 시간 단언 시험이 빨갛지 않았다.
- 실제 TEI(Docker와 GPU)를 띄운 실행은 하지 않았다.
- 커밋 전에 `mutate.py --staged`를 먼저 돌렸다(07의 첫 커밋 시도가 이 검사에 막힌 기억에서다). 변이 12, 15, 17의 표지가 pytest의 단언 풀이 줄(`assert 0 == 1`, `where 1 = _compare(…`, `CompareResult(…).passed`)이라 거부되었다. 시험 단언에 값을 실은 메시지를 달고(`assert code == 1, f"하락폭을 넘는 하락의 종료 코드: {code}"` 꼴) 그 문구를 표지로 바꾼 뒤 세 변이를 돌려 기대한 빨강을 봤고, `--staged`가 문제 0으로 지나갔다.

## origin/dev 병합

커밋 `5a9faf6` 뒤 `git fetch origin`으로 보니 `origin/dev`가 티켓 12(#47, `judge` 하위 명령)를 받아 앞서 있었다. `git merge origin/dev`는 `tools/search_eval.py`와 `app/eval_report.py`를 자동으로 합치고 `README.md`의 `tools/` 줄 한 곳에서만 충돌했다. 12의 문장(`judge`가 마지막 단계의 상위 10개를 판정하고 `run`이 그 파일로 `llm` 숫자를 센다)을 기준으로 두고 끝에 이 PR의 `compare` 문장을 이었다. 생성 파일 `.scratch/plan.md`는 `tools/plan_table.py`를 다시 돌려도 달라지지 않았다.

- 확인: 병합 뒤 `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), 겹친 영역의 시험(`test_eval_compare.py`, `test_search_eval_compare.py`, `test_eval_set.py`, `test_eval_report.py`) 88 passed, DB가 필요한 `test_search_eval_judge.py`와 `test_search_eval_compare_records.py` 40 passed. 12의 `judge`가 판정 칸 둘(`judge_model`, `judge_prompt_version`)을 쓰므로 `compare`가 그 둘을 구성 견줌에서 빼는 것이 12와 맞는다.
- 처음 시험을 돌릴 때 `RAG_TEST_DATABASE_URL`을 내보내지 않아 39개가 환경 오류였고, `-p no:logging`을 준 탓에 `caplog` 시험 하나가 오류였다. 둘 다 내 명령의 실수이고 코드와는 무관하다.

## PR 직전 리뷰

`coderabbit-review` 에이전트가 `coderabbit review --agent --committed --base origin/dev`를 돌렸다. CLI 0.7.5, `Seat: not assigned`, 종료 코드 0으로 `review_completed`, 파일 19개, CLI 지적 2건이다(한도 초과나 거절은 없었다). 에이전트가 코드를 읽고 직접 찾은 지적 6건을 더해 8건이고 Critical과 Major는 0건이다. 중점으로 준 항목(하락폭 경계, 판정 칸 제외와 기록 해시 견줌, 기준 보고서 읽기와 `BundlePaths`, `_chunk_file_hashes` 호환)은 문제를 찾지 못했다고 보고했다. 경계는 질의 수 여덟 가지에 모든 맞힌 수로 정확히 2%p 떨어진 5202쌍을 돌려 거짓 양성 0이었다고 한다(에이전트가 돌린 값이고 이 세션에서 다시 돌리지는 않았다).

- 고쳤다. [Minor, 직접 읽은 지적] 기준 보고서와 새 보고서 모두 기록 파일 해시가 없으면(`--records off`로 만든 보고서끼리) `None != None`이 거짓이라 기록 파일 견줌이 조용히 통과했다. `src/rag_engine/app/eval_compare.py`의 `_incomparable`을 코드로 읽어 맞는 것을 확인했고, 기준 쪽 해시가 없으면 새 쪽 값과 무관하게 견줄 수 없다고 내도록 고쳤다(문구는 `기록 파일 <이름>의 해시가 기준 보고서에 없어 견줄 수 없다(기준 없음, 새 …). 기록을 읽거나 쓴 실행(--records read|write)의 보고서로 기준을 갱신한다`, 기존 시험이 기대하는 `기준 없음`은 그대로다). 시험 `test_양쪽_보고서에_기록_파일_해시가_모두_없어도_견줄_수_없다고_낸다`를 더했다.
- 고쳤다. [Minor, CLI 지적을 구현의 한계로 읽은 것] 보고서의 조각 임베딩 해시는 `run`이 도는 때의 디스크 바이트라, 기록을 바꿔 `index`를 돌린 뒤 `run` 전에 되돌리면 통과한다. 코드 변경 없이 `adapters/eval_compare.py` 독스트링의 못 보는 것에 이 틈과 빠른 게이트의 잡에서는 열리지 않는다는 판단을 적었다.
- 남겼다. [Minor, CLI] `_chunk_file_hashes`가 `read_bytes()`로 조각 임베딩 파일 전체를 읽어 해시한다. 같은 함수의 기존 `_file_hashes`도 `read_bytes`이고 묶음에 용량 상한이 있어 새 유형이 아니다. 청크 해시 헬퍼로 두 곳을 함께 바꾸는 일은 이 티켓의 범위 밖이라 일지에만 남긴다.
- 남겼다. [Minor] 구성 견줌이 파이썬 `!=`라 `True == 1`이다. 지금 `search_config_values`의 칸은 문자열, 정수, 중첩 객체뿐이라 나타나지 않는다. 칸이 불리언이나 부동소수점으로 늘면 그때 견줌을 바꾼다.
- 남겼다. [Nit] `JUDGE_CONFIG_KEYS`와 `config_values`의 리터럴이 따로 적힌 것은 `tests/domain/test_eval_set.py`의 묶는 시험이 이미 잡는다. 기준 보고서 자리가 폴더나 특수 파일이면 "기준 보고서가 없다"로 안내하는 문구의 부정확, 새 보고서에 같은 `(질의 목록, 단계)` 줄이 둘이면 뒤의 것이 이기는 것(`run`이 중복을 내지 않는다), 반올림이 half-even이라 5e-10 이내의 초과가 통과하는 것은 실제 하락폭에 비해 무시할 수 있어 두었다.
- 오탐으로 분류한 것은 없다.

반영 뒤 `uv run pytest tests/app/test_eval_compare.py tests/tools/test_search_eval_compare.py` 78 passed, `uv run pyright` 두 파일 0 errors. 전체 검사는 커밋이 부르는 pre-commit이 돌린다.

PR 직전 리뷰가 밀 주장으로 넘기는 새 사실 문장은 둘이다. 하나는 `adapters/eval_compare.py` 독스트링의 "보고서의 조각 임베딩 해시는 `index`가 색인을 만든 때가 아니라 `run`이 도는 때의 디스크 바이트"이고, 다른 하나는 위 문구의 "빠른 게이트의 잡(같은 체크아웃에서 이어 도는 단계)에서는 열리지 않는 틈"이다. 앞의 것은 `inference_records.py`의 `_chunk_file_hashes` 독스트링("디스크의 바이트")과 대 봤고, 뒤의 것은 명세 162행의 빠른 게이트 잡 순서(`validate`, `index`, `validate --indexed`, `run --through fused`, `compare --gate fast`가 한 잡에서 차례로 돈다)에서 읽은 추론이다.

## 회고

낸 후보 여섯. 승인 4, 기각 2, 넘김 없음.

1. 통합 변이 셋(18~20)이 어긋났을 때 도구가 보여 주는 출력이 서버 로그의 꼬리라 단언 문구가 없었다. 표지를 고르려고 변이를 소스에 손으로 넣고 그 시험만 돌려 `E` 줄을 읽은 뒤 되돌렸다. → 승인. 층: 도구(`tools/mutate.py`). 사건: 위 한 바퀴(소스에 변이를 남긴 채 끝날 위험이 있는 손작업이었고 Grep으로 잔존 0을 확인했다). 간 자리: 대기열 `mutate-marker-discovery`의 9회차(5회차 이상이라 chore 배치 조건이다).
2. 티켓 08 `## Comments`에 재지 않은 "전체 한 번에 15분 안팎"과, 없는 클래스 이름(`InferenceRecords`), 코드에 대 보지 않은 "원천"이라는 말을 적었고 두 축이 잡았다. → 승인. 층: 지침(이미 있는 근거 문장 지침을 어긴 사건이라 회차를 센다). 간 자리: 대기열 `measured-claim-beyond-probe`의 7회차.
3. `run` 보고서가 읽지 않는 파일의 해시도 싣게 되었는데 "읽은 기록 파일마다"를 grep하지 않아 명세 두 곳과 `eval_report.py`의 표 머리가 거짓으로 남았다. 두 축이 모두 잡았다. → 승인. 층: 지침(작업 규약 4를 어긴 사건이라 회차를 센다). 간 자리: 대기열 `decision-word-residue`의 4회차.
4. 하락폭 경계 시험을 `0.82`와 `0.80` 같은 손으로 쓴 짧은 소수로만 써서, 실제 보고서의 `맞힌 수 / 질의 수` 값에서 깨지는 판정(정확히 2%p 하락이 실패로 읽혔다)을 놓쳤다. 명세 축이 Critical로 잡았다. → 승인. 층: `CODING_STANDARDS.md` 줄(자동 검사로 옮길 수 없는 판단이다. 리뷰가 잡도록 둔 기준이 아직 없어 회차를 센다). 간 자리: 새 대기열 `boundary-test-generated-values`(1회차).
5. 훅과 가드가 그 자리에서 막거나 알렸다. 중간 문장이 영어로 나갔다고 `hook_midturn_korean`이 알렸고, 파이프 뒤 종료 코드를 `PreToolUse` 훅이 알렸고, 워크트리 가드가 복합 git 명령을 거부했으며, `.env`에 닿는 Grep glob을 훅이 막았다. → 기각. 이미 있는 훅이 그 자리에서 막거나 알렸다(05, 07 회고의 기각과 같은 모양).
6. 편집기의 pyright 진단이 낡은 캐시나 서브에이전트의 스크래치 스크립트를 가리켰고 `uv run pyright`가 0 errors로 판정했다. → 기각. 손으로 친 검사가 판정자이고 사건의 비용이 없었다(07 회고 6과 같은 모양).

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev`가 모두 만료할 항목이 없다고 했다(`git fetch origin` 뒤). 회차 5 이상은 `mutate-marker-discovery`(9회차), `measured-claim-beyond-probe`(7회차), `crlf-from-script-edits`(6회차), `gate-masked-by-echo-chain`(6회차)이다.

## 다음

- 이 PR이 병합되면 티켓 08은 끝이다. 열린 티켓은 10, 11, 12, 13, 14, 15, 16, 17, 18, 19라 기능은 아직 끝나지 않았다(기능 계획의 `**끝:**` 줄을 달지 않았다).
- 11(빠른 게이트의 CI 잡)이 이어받을 것: 잡이 `validate`를 `run`보다 앞에 두어야 한다(`compare`는 요청 지문과 TEI 판의 불일치를 잡지 않는다). 하락폭 상수(`HIT_AT_5_DROP`, `MRR_DROP`)의 값은 11의 흔들림 측정이 확정한다. 값을 바꾸면 변이 4, 5의 값(0.2)과 경계 시험의 숫자를 맞춘다.
- 14와 15가 이어받을 것: 전체 게이트가 읽는 `rerank.jsonl`의 이름을 진짜 전체 `run`의 보고서와 맞대는 시험이 없다(`app/eval_compare.py`가 이름을 따로 적는다).
- 12가 `tools/search_eval.py`를 건드릴 수 있다(지시문이 알렸다). 나중에 병합되는 쪽이 충돌을 푼다.
