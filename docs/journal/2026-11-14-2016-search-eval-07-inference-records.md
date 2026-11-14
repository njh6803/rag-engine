# search-eval 07: 추론 기록과 `--records read|write|off` · 2026-11-14

티켓 `.scratch/search-eval/issues/07-inference-records.md`를 구현한 기록이다. 브랜치는 `feature/07-inference-records`다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `07-inference-records`에 들어와 이어 갔다. 같은 배치의 06·12 티켓이 `tools/search_eval.py`, `app/eval_report.py`, `adapters/eval_run.py`를 함께 건드리므로 나중에 병합되는 쪽이 충돌을 푼다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 07, 명세 `.scratch/search-eval/spec.md`의 "추론 기록"과 "추론 기록의 시험" 절, 앞 일지 `2026-11-14-1723-search-eval-05-full-run-rerank.md`의 "다음", 티켓 06·12.
- 실제 TEI(Docker와 GPU)는 띄우지 않았다. 시험은 `TeiStub`로 돈다.

## 한 것

- `adapters/inference_records.py`(새 파일): 열쇠(`embedding_key`, `rerank_key`), 감싸는 어댑터 둘(`EmbeddingRecorder`, `RerankRecorder`), 명령 하나의 기록을 맡는 `RecordsRun`, `RecordMode`, `RecordsOptions`, 요청 지문, 다시 돌릴 명령 문구.
- `adapters/inference_record_files.py`(새 파일): `records/`의 파일 형식과 읽기·쓰기. 정렬해 쓰고, 자료 파일을 먼저 쓴 뒤 `records.json`을 마지막에 임시 파일과 `os.replace`로 쓴다.
- `adapters/eval_records_check.py`(새 파일): `validate`의 기록 판정(크기, 판, 요청 지문, TEI 판, `compose.eval.yml`의 이미지 태그).
- `adapters/tei.py`: `InferenceRequestShape`(임베딩과 리랭크의 요청 경로와 칸을 한 자리에 두고 요청을 그것으로 짓는다). `domain/ports.py`: `EmbedderWrapper`. `worker/assembly.py`: 작업자는 기록을 모르고 그 걸이만 연다.
- `adapters/eval_index.py`, `eval_run.py`, `eval_assembly.py`(병합 뒤 기록 배선이 여기로 옮겨 왔다. 아래 "origin/dev 병합"), `eval_validate.py`, `eval_database.py`(`has_documents`), `eval_environment.py`, `app/eval_report.py`(`records` 칸), `tools/search_eval.py`(`--records`, `--tei-device`), `README.md`, `compose.eval.yml`.
- 시험: `tests/tools/test_search_eval_records.py`(표면 시험 30), `tests/adapters/test_inference_records.py`, `test_inference_record_files.py`(새 파일), 어댑터 시험(`test_tei_embedder.py`, `test_tei_reranker.py`), 지원(`tests/support/eval_bundle.py`).
- 변이 표 `.scratch/search-eval/probes/eval_records_mutations.toml`(26).

## 정한 것

- `--records off`의 보고서 `records` 칸은 `{read: 0, computed: 0, files: {}}`이다. off는 기록 계층을 거치지 않으므로 계산 수를 세지 않는다.
- `--tei-device cpu|gpu`는 `write`에서 필수다(없으면 종료 코드 2). 장치를 도구가 알아내는 길은 두지 않았고, TEI `/info`로 알 수 있는지는 재 보지 않았다.
- 상한(새로 계산한 임베딩 100개)은 기록기가 `PermanentFailure`를 올려 멈추고, 명령이 끝난 뒤 `notices()`가 까닭과 다시 돌릴 명령을 낸다. 기록은 종료 코드 0일 때만 커밋한다.
- 05의 `require_reranker_url`은 `--records off`의 전체 실행에만 남았다. 기록을 읽거나 쓰는 전체 실행은 끝점이 없어도 돌고, 기록에 없는 쌍 하나에서 같은 방식으로 실패한다.

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high, 명세 축은 세션 모델이다. 기준은 `a495e80`이고 수정 17개와 미추적 7개를 봤다. Critical은 없었다.

- 고친 것: 기록 파일의 임시 파일(`<이름>.tmp`)이 묶음 밖 링크여도 그 링크로 쓰던 틈(명세 축이 `RecordsRun`을 직접 불러 재현한 것과 표준 축이 코드로 읽은 것이 같은 자리였다). `write`가 종류가 여럿일 때 앞 종류를 쓴 뒤 뒤 종류의 경로에서 거부할 수 있던 순서(시작할 때 주인 파일 전부를 `check_writable`로 본다). 쓰다 끊겨 남은 `.tmp`가 20MB 합에 들던 것. 모듈 독스트링 "읽고 쓰는 모든 경로는 경로 판정을 지난다"와 `eval_records_check.py`의 "다시 만들 기록 파일을 알린다"의 과장. `compose.eval.yml`의 "요청 지문과 응답이 TEI의 판에 묶여 있다"(지문에 TEI 판이 들지 않는다). 재 보지 않은 "TEI `/info`에는 장치가 없다". 05의 변이 표가 가리키던 옛 시험 이름. `_reason` 중복(`failure_reason`으로 모았다). `pytest.raises`의 `match`.
- 남긴 것: 티켓 07 `## Comments`에 이유와 함께 적었다. `index --records read`의 상한 길 시험 없음, 두 실패 까닭이 같은 `EMBEDDING_REJECTED` 코드를 쓰는 것, `RecordKind.RERANK` 분기의 반복, `.keys`와 `.f32` 교체 사이의 실패, 같은 묶음에서 `index`와 `run`을 겹쳐 `write`로 돌릴 때의 `records.json` 덮어쓰기. `run` 보고서에 조각 임베딩의 해시가 없는 것은 받는 쪽인 티켓 08 본문에 적었다.
- 이 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨냥할 것): `inference_record_files.py` 모듈 독스트링의 `.tmp` 서술과 `check_writable`, `records_size`의 독스트링, `eval_records_check.py` 모듈 독스트링의 "못 보는 것" 단락, `compose.eval.yml`의 둘째 주석 줄, `tools/search_eval.py` 모듈 독스트링의 장치 문장, 티켓 07과 08의 새 문단.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`, `uv run python tools/check_type_escapes.py`, 변이 표 `--check`(25), 새 변이 둘(24, 25)의 빨강. 전체 시험은 커밋의 pre-commit이 돈다.

## 검증

- `tests/tools` 전체 2975 passed(표면 시험 30 제외하고 따로, 표면 시험은 별도로 통과). 변이 표 23이 모두 기대한 빨강과 표지로 나왔고, 셀프 리뷰 뒤 둘을 더해 25가 됐다.
- 검사 러너 전체(`tools/run_checks.py`)는 4132 passed에 2 failed였다. 둘은 시간 단언 시험(`test_job_lease`의 5초 한도에 5.27초, `test_hook_push_behind_main`의 시간 제한)이고, 변이 실행과 서브에이전트가 함께 돌던 부하에서 났다. 둘을 단독으로 돌리면 통과한다(2 passed).
- 시험 순서를 솔직히 적는다. 기록기와 파일 형식의 시험은 구현 전에 쓰고 빨강을 봤다. 표면 시험은 구현 전에 먼저 썼다(05 회고가 정한 것). 그 빨강은 인자가 없다는 까닭이라 구현이 틀렸을 때의 빨강은 변이 표로 따로 확인했다.
- 변이 표의 표지를 처음에는 자리 표시로 두고 첫 실행의 실패 출력으로 골랐다. 도구 시험은 캡처된 로그가 끝을 채워 단언 문장이 출력에 없어서, 시험 줄에 `--show-capture=no --tb=short`를 더한 사본으로 한 번 더 돌아 표지를 골랐다(05 회고 1과 같은 모양이라 대기열 회차에 센다).
- 실제 TEI(Docker와 GPU)를 띄운 실행은 하지 않았다.
- 첫 커밋 시도가 둘로 막혔다. 하나는 변이 표 훅(`tools/mutate.py --staged`)이다. 내 표 열둘의 표지가 pytest의 단언 풀이 줄(`assert 0 == 1` 꼴)이라 대기열 517이 알렸고, 03 표의 변이 둘은 내가 `eval_index.py`와 `eval_validate.py`를 고쳐 원문이 사라져 있었다. 나는 `--check`만 돌렸고 `--staged`는 돌리지 않았다. 시험 단언에 값을 실은 메시지(`assert code == 1, f"…종료 코드: {code}"`)를 더하고 그 문구를 표지로 골랐다. 바뀐 변이 열둘을 실제로 돌려 모두 기대대로 빨갰다(`PYTHONUTF8=1 … uv run python tools/mutate.py <표> 5 7 8 …`). 03 표의 두 변이는 원문을 현재 소스에 맞췄고, 변이 둘(4, 5)의 표지는 `DuplicateTable`에서 `데이터베이스를 쓰지 못했다(ProgrammingError)`로 바꿨다. 03 표 전체를 돌려 보니 변이 12(`제품 설정이 작업 폴더의 .env를 읽는다`)가 기대 빨강인데 초록이었다. 설정 객체에 `env_file=None`이 dev에 이미 있어서 `dotenv_settings`를 되살려도 `.env`가 열리지 않는 동치 변이이고, 이 PR이 만든 것이 아니라 손대지 않았다.
- 다른 하나는 pytest 시험 하나(`test_dev의_유무를_조회하다_시간을_넘기면_재지_않는다`)이다. 앞의 손으로 돌린 러너에서도 빨갰다가 단독에서는 통과한 것과 같은 시험이라, 두 번째 빨강에서 추측하지 않고 코드를 읽었다. 시간 제한 0.0001초가 걸리려면 `git`이 끝나기 전에 부모가 `communicate`에 들어가야 하는데, 부하에서 부모가 멈추면 그렇지 못하다(스크래치 스크립트로 재현했다. `Popen` 직후 멈춤이 없으면 5번 모두 `TimeoutExpired`, 0.5초 멈추면 5번 모두 정상 종료). 대기열 `load-time-assertion-margins`의 사례로 더했고 이 PR에서 시험은 고치지 않는다.

첫 병합 커밋 뒤 `git fetch origin`에서 `origin/dev`가 다시 앞서 있어(#46 search-eval 09, #45 harness) 한 번 더 합쳤다. 충돌은 `README.md`의 디렉터리 설명 한 곳뿐이었다. 09의 `evals/` 줄을 더하고 `tools/` 줄은 이 PR의 `--records` 문장이 든 쪽을 유지했다. 생성 파일 `.scratch/plan.md`는 `tools/plan_table.py`를 다시 돌려도 달라지지 않았고, `uv run pytest tests/test_plan_status.py`는 13 passed(184.21초)였다. 09의 평가 재료(`evals/`)를 가리키는 시험은 `tests/`에 없었다.

## 병합 커밋의 pre-commit

`origin/dev`(06) 병합 커밋을 pre-commit이 두 번 돌렸다(둘 다 막혔다). 시도마다 빨간 시험이 달랐고, 이 PR이 건드린 파일의 시험은 하나도 없었다.

- 첫 시도(4207 passed 2 failed, 1356초): `tests/contract/test_reindex_switch.py`의 시험 둘이 MCP 클라이언트의 `ReadTimeout`. 그 파일만 단독으로 돌리면 8건 통과(175.51초).
- 둘째 시도(4207 passed 2 failed, 872.74초): `test_job_lease`의 5초 단언이 5.56초, `test_serve가_뜨면…`이 "serve가 30초 안에 뜨지 않았다".
- 그 사이 CPU 사용률은 100%였고, 다른 저장소의 `tools/run_checks.py`(`-n 8`)와 이 저장소 형제 워크트리의 러너가 번갈아 돌았다(프로세스 목록을 손으로 봤다). 한가해지기를 30분씩 두 번 기다렸으나 오지 않았다. 사례는 대기열 `load-time-assertion-margins`와 `serve-startup-test-load-margin`에 더했다. 시험을 고치지 않았다(끝이 열린 결함 종류라 사례를 고치지 않는다).

## PR 직전 리뷰

`coderabbit-review` 에이전트가 CodeRabbit CLI 0.7.5(`coderabbit review --agent --committed --base origin/dev`)를 돌렸다. `--committed`와 `--include-untracked`는 같이 쓸 수 없어 미추적 파일이 없는 상태에서 뒤의 것을 뺐다. 지적은 7건이고 Critical은 없었다. 좌석은 `not assigned`였는데 리뷰는 끝까지 돌았다.

- 고친 것: 임시 파일 경로가 묶음 안의 다른 자리(최종 파일이나 문서 파일)로 풀리는 링크이면 그 자리에 쓰고 끝의 `unlink`가 지우던 것. 셀프 리뷰의 첫 수정은 묶음 밖 링크만 막았다. 같은 시험(`test_쓰기는_임시_파일이_묶음_안의_다른_자리를_가리키는_링크여도_거부하고_아무것도_쓰지_않는다`)이 고치기 전에 빨갰고(링크가 가리킨 폴더에 쓰려다 `PermissionError`) `_target`이 임시 경로가 최종 경로 바로 옆의 `<이름>.tmp`가 아니면 거부하게 고친 뒤 초록이다. 변이 26(그 판정을 `if False:`로 바꾼다)이 기대한 빨강이다.
- 남긴 것: 교체 중간의 실패로 파일 세트가 서로 다른 세대가 되는 것(셀프 리뷰가 이미 남긴 항목과 같다). `run`이 기록을 읽기 전에 크기 상한을 보지 않는 것과 `records.json` 읽기에 상한이 없는 것(명세 `[정함]` 기록 파일 항목이 20MB를 `validate`의 몫으로 정했다). `write`가 장치가 달라도 옛 값을 옮기고 `device`를 이번 `--tei-device`로 적는 것(티켓 14에 적었다). `run --records read`가 요청 지문과 TEI 판의 불일치를 보지 않는 것(빠른 게이트가 `validate`를 먼저 돌리는 설계이고, 티켓 08에 적었다).
- 이 반영이 새로 쓴 사실 문장(밀 주장): `inference_record_files.py`의 `_target`과 `check_writable` 독스트링, 티켓 07 `## Comments`의 PR 직전 리뷰 문단, 티켓 14의 `## Comments`, 티켓 08의 새 체크박스.

## origin/dev 병합

PR을 열기 전에 `git fetch origin`으로 보니 `origin/dev`가 티켓 06(#44)을 받아 앞서 있었다(`git merge-base --is-ancestor origin/dev HEAD`가 1). `git merge origin/dev`가 파일 여덟에서 충돌했다. 06이 `run`의 공통 조립을 `adapters/eval_assembly.py`로 뽑고(`inspect`와 공유) `--config <파일>`, 놓친 원인, 유형·필터 지표를 더했다.

- 06의 구조를 기준으로 내 `--records`를 얹었다. `prepare_evaluation(..., records=)`가 `RecordsRun`을 열어 `PreparedEvaluation.records_run`에 싣고, `evaluation_deps`가 질의의 임베딩과 리랭크를 그 기록기로 감싸며, `guarded`가 평가가 끝나지 못했을 때 멈춘 기록의 안내를 낸다. `eval_run.py`는 요약과 `commit()`만 맡는다.
- `inspect`는 기록을 쓰지 않는다. `prepare_evaluation`의 `records` 기본값이 `off`라서 `inspect`의 호출은 그대로이고, `off`의 `RecordsRun`은 기록기, 안내, 요약이 모두 비어 있다. 전체 실행을 `reranker is None`으로 가르는 06의 `_evaluate`가 기록 모드에서도 맞다. 빠른 실행은 리랭크 기록기가 없어 `None`이고, 전체 실행은 끝점이 없어도 기록기가 감싼 리랭커가 있다.
- `tools/search_eval.py`는 `inspect` 분기를 `--records` 해석 앞에 둬 `inspect`가 기록 옵션을 받지 않게 했다. `index`는 `records`와 `config_file`을 함께 받는다.
- 보고서는 06의 칸(`by_tag`, `filtered`, `misses`, `miss_counts`, `human_causes`)에 내 `records` 칸이 이어진다. 보고서 판은 칸을 더하는 것이라 올리지 않았다. 시험 쪽 보고서 모델(`tests/support/eval_run_support.py`의 `Report`)에 `records`를 더했다.
- 변이 표: 위치가 옮겨 간 변이 넷(11, 12, 15, 16)의 대상 파일을 `eval_assembly.py`로 바꿨다. 변이 12(빠른 실행의 주인 파일에 리랭크를 넣는다)는 처음에 표지가 나오지 않았다. 처음에는 전체 실행으로 바뀌어 종료 코드가 1이 되리라고 짐작했으나 틀렸고, 손으로 변이를 넣어 시험을 직접 돌려 보니 종료 코드는 0이고 리랭크 기록의 바이트도 그대로였다(리랭크 값이 기록에 이미 있어 기록으로 처리된다). 시험은 마지막 단언(보고서 `files`에 `records/rerank.jsonl`이 실린다)에서 실패한다. 그 단언에 값을 실은 메시지를 달고 표지를 그 문구로 바꿨다.
- 문서 충돌: `compose.eval.yml`과 `README.md`는 두 쪽의 문장을 모두 살렸다. 대기열 `mutate-marker-discovery`의 승인 줄은 06 일지가 7회차, 이 일지가 8회차가 되도록 이었다.
- 확인: 병합 뒤 `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`(2 kept), 관련 시험 736 passed(`tests/tools`의 `search_eval*`, `tests/adapters` 전체, `tests/app`과 `tests/domain`의 평가 시험), 변이 표 `--check` 다섯 표가 모두 원문 한 번씩.

## 회고

낸 후보 여섯. 승인 4, 기각 2, 넘김 없음.

1. 변이 표의 표지를 첫 실행의 실패 출력으로 골라야 했다. 도구 시험(`tests/tools/`)은 캡처된 서버 로그가 출력의 끝 열 줄을 채워 단언 문장이 보이지 않아, 시험 줄에 `--show-capture=no --tb=short`를 더한 사본으로 한 번 더 돌았다. 고른 표지 하나(`query-embeddings.keys`)는 시험 원문에 글자 그대로 있어 도구가 거부했고, 백슬래시가 든 표지는 입력 도구를 지나며 깨져 다시 골랐다. → 승인. 층: 도구(`tools/mutate.py`). 사건: 위 한 바퀴(전체 실행이 두 번 더 들었다). 간 자리: 대기열 `mutate-marker-discovery`의 7회차(5회차 이상이라 chore 배치 조건이다).
2. 손으로 백그라운드로 돌린 `tools/run_checks.py`가 도는 동안 소스를 고쳤다(`inference_record_files.py`, `inference_records.py`). 그 결과(4132 passed, 2 failed)는 고친 뒤의 상태를 재지 못했고, 마지막 확인은 커밋의 pre-commit이 한다. → 승인. 층: 계기 훅(그 항목이 정한 처방과 같다). 간 자리: 대기열 `edit-during-precommit`의 2회차(커밋이 아니라 손으로 돌린 러너라는 차이를 승인 줄에 적었다).
3. 검사 러너의 시험 둘(`test_job_lease`의 5초 한도에 5.27초, `test_hook_push_behind_main`의 시간 제한)이 변이 실행과 서브에이전트가 겹친 부하에서 빨갛고 단독으로는 통과했다(2 passed). → 승인. 끝이 열린 결함 종류의 세 번째 사례(닫힌 `token-expiry-test-load-margin`이 앞의 둘)라 사례를 고치지 않는다. 간 자리: 새 대기열 `load-time-assertion-margins`(`token-expiry-test-load-margin의 3회차`).
4. 05의 시험 이름을 바꾸고 그 시험을 가리키던 05의 변이 표를 고치지 못했고, 셀프 리뷰의 명세 축이 잡았다. 옛 이름을 되살린 사본으로 `mutate.py --check`를 돌리면 종료 0이다(손으로 쟀다). → 승인. 층: 도구(`--check`). 간 자리: 새 대기열 `mutate-check-test-ids`(1회차).
5. 경로 판정을 우회하는 시험을 명령줄로 짜면 묶음 검사가 먼저 링크를 거부해, 겨눈 자리(`RecordsRun`의 시작 검사)에 닿지 못한 채 첫 실행부터 초록이었다. 실패 출력을 뽑아 보고서야 알았다. → 기각. 원칙 I이 그 자리에서 잡았다(빨강을 보지 못한 시험을 이상하게 여겨 확인했다).
6. 훅이 큰 heredoc(40줄 초과)과 파이프 뒤의 종료 코드를 막거나 알렸고, 워크트리 가드가 `git merge-base ... && ...`를 거부했다. 편집기의 낡은 pyright 진단은 `uv run pyright`가 판정했다. → 기각. 이미 있는 훅과 가드가 그 자리에서 막았고(05 회고 5, 6과 같은 모양) 손으로 친 검사가 판정자다.

만료: `uv run python tools/queue_open_rows.py`가 만료할 항목이 없다고 했다(`git fetch origin` 뒤). 회차 5 이상은 `measured-claim-beyond-probe`(6회차), `mutate-marker-discovery`(7회차), `crlf-from-script-edits`(5회차)다.

## 다음

- 이 PR이 병합되면 티켓 07은 끝이다. 08(`compare`)이 이어받을 것: 티켓 08 본문에 적은 `run` 보고서의 `records.files` 한계(조각 임베딩 해시가 없다).
- 10과 14가 `records.json`의 `device`를 읽을 때 `--tei-device`로 받은 값이 들어 있다고 가정해도 된다.
- 06과 12가 `tools/search_eval.py`, `app/eval_report.py`, `adapters/eval_run.py`를 건드릴 때 이 PR과 충돌한다. 나중에 병합되는 쪽이 푼다.
