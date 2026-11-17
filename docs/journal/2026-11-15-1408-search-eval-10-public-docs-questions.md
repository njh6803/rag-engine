# search-eval 10: 공공 문서 묶음의 질문과 기대 근거, 임베딩 기록 · 2026-11-15

티켓 `.scratch/search-eval/issues/10-public-docs-questions.md`를 구현한 기록이다. 브랜치는 `feature/10-public-docs-questions`다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `10-public-docs-questions`에 들어와 이어 갔다. 티켓에 사용자의 검수 지점이 있어 질문 초안을 검수표로 보이고 멈췄다.

## 한 것

- 질문 155개와 기대 근거, 사람 질문 목록과 키워드형 목록(질의 310개)을 `evals/public-docs/`의 `evidence.jsonl`, `queries-human.jsonl`, `queries-keyword.jsonl`에 썼다. 서브에이전트 여섯이 문서 묶음별로 초안을 쓰고, 에이전트가 글귀가 본문에 있는지, 공백을 뺀 길이, 질문과 글귀의 연속 겹침(14자 이상이면 베낌으로 봤다), 키워드 낱말 수를 스크립트로 검사했다.
- 사용자가 검수표(id, 표지, 질문, 키워드, 필터, 문서, 글귀)를 보고 "그대로 확정"이라고 답했다(2026-11-15). 그 뒤에 임베딩 기록을 만들었다.
- 표지는 `table` 34, `multi_document` 26, `no_context` 32이고 `figure`는 없다. 필터가 붙은 질의 20개는 모두 사람 질문 목록의 법령 질문이다(2026-01-01 이후 10개, 2023-12-31 이전 5개, 2025년 5개).
- 임베딩 기록 `records/`는 TEI GPU 이미지(`turing-1.9.4`)와 GTX 1660 Ti로 만들었다. `index --records write --tei-device gpu`가 2116초(약 35분), `run --through fused --records write --tei-device gpu`가 49초였다. 조각 기록 2178개와 질의 기록 310개, 합 약 10.4MB다.
- `tests/tools/test_search_eval_public_docs.py`: 지금 통과함을 재는 시험 둘(파일 검사, 비어 있지 않음)과 변이 시험 셋(문서 해시, 목록에 없는 문서, 기록의 TEI 판). `.gitattributes`에 `records/*.f32 binary`를 더했다.
- `README.md`의 `evals/` 설명과 `.scratch/plan-head.md`의 `evals/public-docs/` 설명이 기대 근거와 질의 목록과 기록이 생겼다는 현재형으로 바뀌었다.

## 정한 것

- 필터는 법령에만 걸었다. 법령의 `updated_at`은 공포일이지만 보고서 14개는 대부분 포털의 자료 기준일이라 날짜 필터의 근거가 못 된다(티켓 09 `## Comments`). 균등 간격으로 골랐다.
- 한 문서에 개정 전후 두 판이 함께 실린 조문(근로기준법, 최저임금법, 기간제법의 일부)은 글귀가 겹치지 않게 골랐다. `labr-07`은 구판에만 있는 문장이다.
- 코로나19 보고서의 숫자 표를 묻는 `cult-19`~`cult-22`는 표 블록이 숫자와 칸 구분자뿐이라 `table`과 `no_context`를 함께 달았다.
- 임베딩 기록은 임시 compose(`compose.eval.yml`에서 TEI 이미지, 포트, 모델 캐시 볼륨만 바꾼 것)로 만들었고 커밋하지 않았다. 끝난 뒤 컨테이너와 평가 데이터베이스 볼륨을 내렸다(모델 캐시 외부 볼륨 `search-eval-tei-probe-data`는 남겼다).

## 검증

- `validate evals/public-docs`(파일 검사)와 `validate evals/public-docs --indexed`가 모두 `문제 없음`이다. 같은 데이터베이스에서 `run --through fused --records read`의 보고서가 `--records write`의 보고서와 `stages`, `rows`, `misses`, `miss_counts`, `human_causes`, `filtered`가 같음을 손으로 봤다.
- 첫 커밋 시도는 pre-commit의 pytest가 `tests/test_plan_status.py` 하나로 실패해 막혔다. 티켓을 `done`으로 바꾼 뒤 `plan_table.py`로 `.scratch/plan.md`를 다시 만들고도 스테이징하지 않은 것이 까닭이다. 스테이징한 뒤 다시 커밋해 지났다(pytest 4328개).

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high, 명세 축은 세션 모델이다. 기준은 `48344dd`이고 수정 5개와 미추적 3경로(`records/` 파일 5개, 시험 파일, 검수표)를 봤다. Critical은 없었다.

- 명세 축 Major: `.scratch/plan-head.md`와 생성 파일 `.scratch/plan.md`의 `evals/public-docs/` 줄이 "기대 근거와 질의 목록은 10이 채운다"로 미래형이라 이 변경 뒤에는 거짓이었다. `plan-head.md`를 고치고 `plan_table.py`로 `plan.md`를 다시 만들었다.
- 명세 축 Minor: `README.md`의 `evals/` 줄에 새 파일이 빠졌다. 고쳤다.
- 표준 축 Minor: 시험이 훑는 기록 파일이 셋뿐이라 `records.json`과 `query-embeddings.f32`를 더해 다섯으로 넓혔다. 변이 시험 둘의 단언이 `or`로 느슨해(`"tei" in reason.lower()`, 없는 문서의 이름이 `reason`이나 `where` 어느 쪽에든) 변이 입력이 실제로 내는 문구(`records.json의 tei_version 1.9.3이 config.json의 1.9.4과 다르다`, `where`가 `기대 근거 x-없는문서`이고 `reason`이 `문서 목록에 없는 문서 laws/없는문서.pdf를 가리킨다`)를 `validate_bundle`로 읽은 뒤 그 문구로 좁혔다.
- 표준 축 Minor: 티켓 Comments가 조각 2193개와 기록 2178개의 차이를 "같은 글의 조각 15개가 합쳐졌기 때문"이라고 단정했다. `embedding_key`가 모델 이름과 글의 sha256임은 코드로 읽었으나 15개가 모두 같은 글에서 났는지는 세지 않았으므로(색인 데이터베이스는 정리했다) 추정이라고 고쳤다.
- 남긴 것: 코로나19 숫자 표의 글귀가 파서의 칸 구분자(`|`)와 숫자 열이라 표 직렬화가 바뀌면 조용히 놓친 것으로 센다(명세 축 Minor). 지금 규칙에는 어긋나지 않고 티켓 Comments가 그 선택을 밝혔다. `eval_records_check.py`가 `.f32`의 크기와 `records.json`의 `count`가 맞는지는 보지 않는다(그 독스트링이 밝힌 한계이고 이 변경의 결함이 아니다. 에이전트가 손으로 대 봤고 맞다). 시험이 `tests/tools/`에 있으면서 `adapters`를 부르는 것(Nit)은 저장소 상태 시험의 선례 위치를 따랐다.
- 이 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨냥할 것): 티켓 10의 `## Comments`의 2193 대 2178 문장, `.scratch/plan-head.md`와 `README.md`의 `evals/` 줄, 시험 파일의 두 단언 문구.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`, `uv run python tools/run_checks.py`(전부 통과, pytest 602.6초. 커밋 직전의 pre-commit 판은 418초에 4327개 통과, 계획표 시험 하나만 실패해 고친 뒤 다시 통과했다).

## origin/dev 병합

`git fetch origin`으로 보니 `origin/dev`가 티켓 08(#49, `compare --gate`)을 받아 앞서 있었다. `git merge origin/dev`는 `README.md`의 `evals/`와 `tools/` 두 줄에서만 충돌했다. 두 줄은 서로 다른 쪽이 고친 것이라 `evals/` 줄은 이 PR의 판(기록 파일 설명 포함)을, `tools/` 줄은 08의 판(`compare --gate` 문장 포함)을 남겼다. `.scratch/plan.md`는 `plan_table.py`를 다시 돌려도 달라지지 않았다.

## PR 직전 리뷰

`coderabbit-review` 에이전트가 `coderabbit review --agent --committed --base origin/dev`를 돌렸다. CLI 0.7.5, `Seat: not assigned`, 종료 코드 0으로 `review_completed`, 파일 15개, 지적 1건이다(한도 초과나 거절은 없었다). Critical과 Major는 0건이다. 중점으로 준 항목은 에이전트가 직접 대 봤다. 비밀과 개인 정보가 데이터 파일에 실리지 않았고, 시험이 윈도 전용 가정 없이 임시 복사본에만 쓰며, 기록 파일 크기(2178×1024×4 등)와 시험 단언 문구가 `validate_bundle`의 실제 출력과 글자 그대로 같고, 티켓 Comments의 2193 대 2178 문장이 코드와 맞다는 보고다(에이전트가 돌린 값이고 이 세션에서 다시 돌리지는 않았다).

- 남겼다. [Minor] `labr-01`의 사람 질문이 "수습 중인 근로자에게 수습 후 3개월 동안은"이라 적었는데 기대 근거의 글귀는 "수습을 시작한 날부터 3개월 이내"다. 질문의 "수습 후"는 수습이 끝난 뒤로 읽혀 근거와 어긋난다(두 파일의 79줄을 직접 읽어 맞는 것을 확인했다. 키워드형 질의에는 이 문제가 없다). 사용자가 검수표를 보고 "그대로 확정"한 문구이고, 바꾸면 `records/query-embeddings.*`를 GPU로 다시 만들어야 해서 이 PR에서는 고치지 않는다. 아래 "다음"에 넘겼다.
- 남겼다. [Nit] 시험의 `manifest.write_text`가 윈도에서 `\r\n`으로 쓰는 것과 `iterdir()`의 순서가 파일 시스템마다 다른 것은 임시 복사본에서만 쓰고 어느 파일이든 해시 변조가 잡히므로 결과가 같아 두었다.
- 새로 쓴 사실 문장은 이 절뿐이고, 고친 코드나 파일은 없다.

## 회고

후보 네 개를 냈고 승인 0, 기각 4, 넘김 0이다. 승인된 것이 없어 대기열에 새로 쓴 항목과 회차를 더한 항목은 없다. 만료할 항목도 없었다(`queue_open_rows.py`를 작업 폴더 기준과 `--ref origin/dev` 기준으로 돌렸고 두 출력이 같았다).

- 기각. 티켓을 `done`으로 바꾼 뒤 `plan_table.py`로 다시 만든 `.scratch/plan.md`를 스테이징하지 않고 첫 커밋을 시도해, pre-commit의 pytest가 약 7분(418초)을 돈 끝에 `test_plan_status` 하나로 실패했다. `implement` 스킬이 "티켓을 `done`으로 바꾸거나 기능 계획을 고친 커밋은 `plan_table.py`를 손으로 돌려 `.scratch/plan.md`까지 싣는다"고 이미 적고 있고, 그 누락은 이미 있는 검사가 커밋이 되기 전에 막았다. 이미 있는 검사가 그 자리에서 막은 것이라 기각이다. 7분이 드는 것은 전체 pytest를 도는 게이트 자체의 비용이고 열린 `docs-only-commit-full-pytest`가 그 비용의 다른 사건(문서만 바꾼 커밋)을 다루므로, 처방이 다른 이 사건을 그 항목의 회차로 세지 않았다.
- 기각. 워크트리 세션의 앱 가드가 명령이 복잡해 워크트리 안에 머무는지 확인할 수 없다며 세 번 거부했다(git 호출을 `$(...)`와 `|`로 이은 명령, 환경 변수와 heredoc이 한 줄에 든 스크립트 실행, 괄호가 든 정규식 인자). 앱 가드가 그 자리에서 막았고 명령을 단순하게 쪼개 바로 풀렸다. 이 저장소가 고칠 수 있는 훅이나 지침이 아니다.
- 기각. 시험을 `| tail`로 줄이자 `hook_bash_gate_pipe`가 파이프의 종료 코드가 가려진다고 경고했다. 이미 있는 훅이 그 자리에서 알린 것이고, 출력의 `5 passed`로 판정은 읽혔다. 그 뒤의 게이트는 모두 파일로 돌려 종료 코드를 따로 봤다.
- 기각. 명세 축 서브에이전트가 스크래치패드에 만든 임시 스크립트(`count.py`, `chk2.py` 등)의 pyright 진단이 대화에 새 진단으로 올라왔다. 저장소 밖 파일이라 저장소의 pyright 게이트에 걸리지 않고, 이 세션의 판단을 바꾼 것도 없다. 사건이 아니라 소음이라 기각이다.

## 다음

- 이 PR이 병합되면 티켓 10은 끝이고 `.scratch/search-eval/plan.md`에 `끝` 줄은 아직 없다(열린 티켓이 여럿이다). 티켓 11(빠른 게이트의 CI, `baseline-fast.json`)이 열린다. 선행 조건 08과 10이 모두 병합됐다. 티켓 14(GPU 리랭크 기록)도 10만 기다려 열린다. 둘은 서로 막지 않으므로 나란히 돌 수 있다.
- 티켓 11은 `run --through fused`의 보고서를 기준 보고서로 커밋하고 `compare --gate fast`를 CI 잡에 건다. `records/`의 판이 바뀌면(TEI 판, 구성) 기록을 다시 만들어야 하고, 그때도 GPU 이미지가 필요하다. CPU TEI는 평가 도구의 시간 제한(`tei_timeout_seconds` 60초)에 걸려 `index`가 끝나지 않는다(티켓 09 `## Comments`).
- 기대 근거나 질문을 고치면 `records/`의 질의 기록과 기준 보고서가 함께 어긋난다. 티켓 13이 판정 표본을 보고 기대 근거를 고치면 티켓 11의 `baseline-fast.json`을 함께 갱신한다(티켓 13의 Blocked by).
- `labr-01`의 사람 질문 문구("수습 후 3개월 동안은")가 근거의 "수습을 시작한 날부터 3개월 이내"와 어긋난다(PR 직전 리뷰의 Minor 보류). 티켓 11이 `baseline-fast.json`을 만들기 전에 "수습을 시작한 날부터 3개월 동안은" 꼴로 고치고 `run --through fused --records write --tei-device gpu`로 질의 기록(`query-embeddings.*`)만 다시 만든다(이 세션에서 49초). 문구를 사용자가 확정했으므로 고칠 때 사용자에게 한 줄로 알린다. 티켓 13이 기대 근거를 고칠 때 함께 고치는 길도 있다.
- 이 세션이 만든 임시 compose(`compose-gpu.yml`)는 커밋하지 않았다. 같은 구성으로 기록을 다시 만들 때는 `compose.eval.yml`에서 TEI 이미지를 `turing-1.9.4`와 GPU 예약으로 바꾸고 모델 캐시 볼륨을 이미 받아 둔 것으로 지정한다.
