# search-eval 17: 리랭커 켬·끔 실험과 리랭커의 기본을 정하는 결정 · 2026-11-17

티켓 `.scratch/search-eval/issues/17-reranker-on-off-experiment.md`를 구현한 기록이다. 브랜치는 `feature/17-reranker-on-off-experiment`이다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `17-reranker-on-off-experiment`에 들어와 이어 갔다. 티켓이 멈추라고 한 지점에서 사용자에게 물었고, 사용자는 리랭커의 기본을 "끄는 기본"으로, 전체 게이트와 최소 점수는 "둘 다 유지"로 골랐다. 그 뒤 ADR 이력 초안을 보여 주자 "승인"이라고 답했다.

## 한 것

- 후보 수 5, 10, 20, 50, 100마다 `run --through fused`와 `run --through rerank`를 GPU로 돌려 보고서를 `.scratch/search-eval/probes/experiments/reranker/`에 모았다. 후보 수 100만 새로 계산이 필요했고 4시간 43분 51초에 15,446쌍을 계산했다. 후보 수 50의 두 보고서는 커밋된 `baseline-fast.json`, `baseline-full.json`과 같은 칸을 냈다(`compare_with_baseline.py`).
- 결과와 core 16의 CPU 지연을 사용자에게 보이고 멈췄다. 고른 길대로 ADR 0010(이력과 본문 포인터), ADR 0017·0018 이력, ADR 0007 본문 포인터, `tech.md`(헌법 1.3.3에서 1.3.4), core 명세 넷, 이 기능의 명세, release-image 계획, 용어집, 티켓 20의 시작 전 확인 문장을 고쳤다. 설정의 코드 기본값(`default_reranker_url`)은 이미 `None`이라 값은 바꾸지 않았고 시험 한 줄과 주석으로 고정했다.
- 새 시험 한 줄은 구현 전부터 초록이었으므로 변이 시험으로 빨강이 나는지 따로 봤다(`settings_reranker_default_mutations.toml`, 기대대로 빨강).

## 검증

- `uv run python tools/run_checks.py`가 모두 초록이다(pytest 568초). 셀프 리뷰 반영 뒤 `uv run ruff check .`과 `uv run ruff format --check .`가 초록이다. 나머지는 커밋의 pre-commit이 갈음한다.

## 셀프 리뷰

`code-review` 두 축(표준 축 Sonnet 5.5 / high, 명세 축은 세션 모델). 기준은 `origin/dev`와의 merge-base `a372cd6`이고 수정 15개와 미추적 22개(`experiments/reranker/` 21개, 변이 파일 1개)를 봤다. 리뷰 시점에 `origin/dev`는 티켓 20(PR #58)이 병합되어 앞서 있었다. 그 병합은 커밋 뒤에 합쳐 충돌을 푼다.

- 고친 것. (1) `.scratch/plan-head.md`(와 생성 파일 `plan.md`)의 "단독 compose(… 리랭커 TEI)"가 옛 결정으로 남았다(두 축이 함께 냈다). plan-head를 고치고 `plan_table.py`로 다시 만들었다. (2) ADR 0010 이력의 "CPU로는 후보 5개, 이 GPU로는 후보 20개까지만 든다"가 잰 후보 수를 넘어 닫았다. 잰 후보 수 가운데로 한정하고 CPU 동시 4건 p95 281초와 GPU 값이 리랭크 호출만이라는 점을 적었다. (3) 한계 절의 "질문 한두 개의 몫"이 사람 질문 목록의 재현율(후보 20개 0.955, 50개 0.974, 질문 셋 차이)과 맞지 않았다. 고쳤다. (4) 사용자의 선택을 따옴표로 "리랭커를 끄는 기본"이라 쓴 것은 보여 준 선택지 이름이 아니었다. "끄는 기본"으로 고쳤다. (5) ADR 0017 새 이력의 "지금처럼"이 아직 구현되지 않은 동작을 있는 것처럼 썼다. 고쳤다. (6) core 명세 272행과 평가 명세 243행·230행의 "기본 구성(리랭커 켬)", "받는 곳이 아직 없어"가 결정 뒤에 낡았다. 당시의 구성이라고 한정하고 결정과 받는 곳을 적었다. (7) ADR 0010 Consequences의 메모리 예산 문장에 포인터를 달았다(이력이 읽는 법을 좁혔다). (8) 프로브: 비교 스크립트가 커밋되지 않았다(커밋하고 출력을 남겼다), compose 머리 주석이 복사 원본의 파일 이름과 포트를 그대로 적었다, README의 "15,000쌍"은 어림이고 실제는 15,476쌍이다, `rerank_latency_gpu.py`에 `__main__` 가드가 없었고 "약 470토큰"을 재지 않고 물려받았다, 프로브 색인 행에 compose가 빠졌다.
- 남긴 것. (a) `compose-gpu-17.yml`이 `tei-gpu/compose-gpu.yml`의 복제본이라는 중복 냄새는 README가 까닭(나란히 도는 세션과 이름·포트가 부딪치지 않게)을 밝혀 두었으므로 판단 항목으로 보류했다. (b) `summarize.py`가 보고서 한 짝이 빠지면 메시지 없이 죽는 점은 한 번 쓰는 프로브라 보류했다. (c) 평가 명세 178행의 "그때까지 제품의 기본은 지금대로다"는 결정 전 서술이다. 바로 뒤에 새로 단 [사용자 선택] 항목이 닫혔다고 적어 두었으므로 고치지 않았다.
- 이 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨냥할 것): ADR 0010 이력의 "잰 후보 수 가운데 CPU는 후보 5개 단건(15.3~17.0초)만 그 안에 들고 … 동시 4건은 p95 281초", "사람 질문 목록의 재현율은 후보 20개 0.955, 후보 50개 0.974라 질문 셋 차이", 평가 명세 230행의 "켜는 설치의 후보 수·시간 제한 안내와 리랭커 TEI의 compose 프로필은 release-image 계획이 받는다", `compare_with_baseline.py`의 비교 칸 목록.
- 다시 돌린 명령. `uv run ruff check .`, `uv run ruff format --check .` 초록. 나머지는 pre-commit으로 갈음했고 커밋(9bffabc)과 `origin/dev` 병합 커밋(f2c2d27)의 pre-commit(검사 러너 포함)이 모두 통과했다. 병합 뒤 `uv run pytest tests/test_plan_status.py`도 13개 통과했다.

## 병합과 충돌

`origin/dev`가 티켓 20(PR #58)으로 앞서 있어 병합 커밋으로 합쳤다. 충돌은 둘이었다. (1) ADR 0017: 티켓 20의 구현 이력과 이 브랜치의 결정 이력이 같은 자리에 들어 둘 다 남겼다(결정이 먼저, 구현이 뒤). (2) core 명세의 `RAG_DEFAULT_*` 항목: 티켓 20이 더한 `RAG_DEFAULT_MIN_SCORE` 설명과 이 브랜치가 고친 `RAG_DEFAULT_RERANKER_URL` 설명을 한 줄로 합쳤다.

푸시한 뒤 봇 회차를 기다리는 동안 티켓 16(PR #59)이 dev에 병합되어 PR이 `CONFLICTING`이 됐고 한 번 더 합쳤다. 충돌은 둘이었다. (3) 프로브 색인 `probes/README.md`: 티켓 16의 `experiments/chunking-candidates/` 행과 이 브랜치의 `experiments/reranker/` 행을 둘 다 남겼다. (4) 대기열 `measured-claim-beyond-probe`: 티켓 16이 10회차를 먼저 더해서 그 판을 바탕으로 이 브랜치의 사건을 11회차로 이었다. 티켓 16의 프로브 행이 같은 시각에 이 브랜치의 GPU 임베딩 TEI를 함께 썼다고 적은 것을 보고, ADR 0010 이력과 프로브 README의 0.91쌍/초 설명에 "GPU를 나눠 쓴 값일 수 있고 겹친 정도는 재지 않았다"를 더했다. 티켓 20은 이미 `done`이고 그 시작 전 확인 문장은 이 브랜치가 결정 뒤의 모양으로 고친 그대로 두었다.

## PR 직전 리뷰

`coderabbit-review` 에이전트가 CodeRabbit CLI 0.7.5로 `--base origin/dev` 범위의 42개 파일을 봤다(`Seat: not assigned`, Plan Free였지만 리뷰는 끝까지 돌았다). 보안 지적은 없고 compose의 포트는 127.0.0.1에만 열린다. 에이전트가 직접 대조한 숫자(CPU 15.3~17.0초와 p95 281초, GPU 29.4초, 재현율 0.955/0.974, 새로 계산한 쌍 15,446, MRR 차 0.004, 비교 칸 목록)는 모두 원천과 맞았다.

- 고친 것. (1) Major: ADR 0010 이력의 "이 GPU는 후보 20개(11.6초)까지 든다"가 합성 글 값 하나로 단정했다. 실제 조각으로 돌린 후보 수 100 실행의 평균은 0.91쌍/초라 후보 20개가 약 22초로 환산된다. ADR 이력, README 지연 절, 평가 명세의 "GPU 29초", 티켓 17 Comments에 두 값을 병기했고 느린 까닭은 재지 않았다고 적었다. 결정(끄는 기본)은 바뀌지 않는다. (2) Minor: README의 "후보 수 5와 10은 … 적중@5와 재현율이 켜도 오르지 않는다"가 후보 10 줄과 어긋났다(후보 10은 적중@5가 오르고 재현율만 오르지 않는다). 후보 5와 10을 나눠 적었다.
- 남긴 것. 없음.
- 이 반영이 새로 쓴 사실 문장: ADR 0010 이력의 "실제 조각으로 후보 수 100을 돌린 평균은 0.91쌍/초이고 … 후보 20개도 약 22초라 20초를 넘긴다", README의 "후보 20개 약 22초, 후보 50개 약 55초"(0.91쌍/초로 나눈 환산이고 재지 않았다), "후보 수 100 실행의 시간은 `run` 전체의 시간이라 … 조금 들어 있을 수 있다".

## PR 봇 회차

PR [60](https://github.com/njh6803/rag-engine/pull/60)의 첫 회차다. 머리 7024f0b에서 검사 7개(claude-review, eval-fast, eval-full, image, python, ticket, verify)가 모두 통과했다. claude-review는 "지적 없음"이었다(코드 변경이 주석 한 줄과 단언 한 줄이고, 헌법 판과 ADR 포인터를 같이 고친 것을 확인했다). CodeRabbit은 무료 오픈소스 리뷰 한도에 걸려 리뷰하지 못했고(`Review rate limited`, 코멘트에 "다음 리뷰는 40분 뒤"), `@coderabbitai review` 요청도 같은 문구로 돌아왔다. 그래서 이 PR의 CodeRabbit 리뷰는 없다. 로컬 CodeRabbit CLI는 PR 직전 리뷰에서 이미 돌았다. 고칠 것이 없어 이 회차에서 푸시한 것은 이 일지뿐이다.

## 회고

후보 5개, 판정은 승인 3, 기각 2, 넘김 0이다. 만료할 항목은 없었다(`uv run python tools/queue_open_rows.py --ref origin/dev`, 열린 항목 56개).

- 승인. `measured-claim-beyond-probe`에 11회차(티켓 16이 먼저 병합되어 10회차를 더했고 이 브랜치가 이어 센다). 사건: ADR 0010 이력이 합성 글에서 잰 11.6초 하나로 "GPU는 후보 20개까지 든다"고 단정했으나 실제 조각으로 돌린 평균(0.91쌍/초)으로 환산하면 약 22초였다. 프로브 README는 커밋하지 않은 스크립트의 `==` 비교를 근거로 삼았고, "15,000쌍"은 어림(실제 15,476쌍), 프로브 독스트링의 "약 470토큰"은 재지 않고 물려받은 문구였다. 표준 축과 PR 직전 리뷰가 잡았다. 이미 지침(`docs/agents/issue-tracker.md` 프로브와 근거 절)이 있는 일이라 회차를 센다. 이미 5회차를 넘어 chore 계기이고 처방은 항목이 든 그대로다.
- 승인. `crlf-from-script-edits`에 8회차. 사건: 프로브 출력 셋이 Windows 리다이렉트로 CRLF가 되어 `git add`의 경고로야 알았다. `sed`로 LF로 되돌렸다.
- 승인. `decision-word-residue`에 5회차. 사건: 리랭커를 기본 설치에서 끄는 결정이 "단독 compose(… 리랭커 TEI)"의 뜻을 바꿨는데 `.scratch/plan-head.md`(와 생성 파일 `plan.md`)까지 옛 표현을 grep하지 않았다. 작업 규약 4를 어긴 사건이고 두 축이 함께 잡았다. 이 항목이 5회차에 이르러 chore 계기가 된다.
- 기각. Git Bash가 `origin/dev:경로`를 경로 목록으로 바꿔 첫 `git show`가 실패한 일. PreToolUse 훅이 그 자리에서 `MSYS_NO_PATHCONV=1`을 알렸고 한 번 다시 쳐서 지나갔다.
- 기각. 병렬 티켓 20(PR #58)이 같은 ADR 0017과 core 명세를 먼저 고쳐 병합에서 충돌한 일. `sibling_overlap.py`가 브랜치를 따는 때부터 겹치는 파일을 알렸고 충돌 자체는 예상한 글자 충돌이었다. 병합 커밋 한 번으로 풀렸고 손상은 없었다.

## 다음

- 주 체크아웃 미갱신: 루트는 dev. 병합 뒤 `tidy-checkouts`가 당기고 병합된 워크트리를 지운다. 이 세션은 새 세션을 열지 않으므로 다음에 새 세션을 열 때 지시문이 다시 적게 한다.
- 이 PR이 병합되면 티켓 17이 `done`이다. 같은 기능의 열린 티켓은 13(첫 판정 실행) 하나다(티켓 16은 PR #59로 먼저 병합됐다). 13은 형제 워크트리 `13-first-judge-run`에서 이미 돈다. 13이 병합되면 마지막 티켓을 닫는 커밋이 기능 계획에 `**끝:**` 줄을 적는다(이 PR은 적지 않았다).
- 형제와의 글자 충돌 후보: `.scratch/search-eval/probes/README.md`(13도 행을 더한다). 나중에 병합하는 쪽이 풀어야 한다.
- 켜는 설치 안내를 쓸 때(release-image): ADR 0010 이력과 프로브 README의 GPU 지연은 합성 글 값(후보 20개 11.6초)과 실제 조각의 평균(0.91쌍/초, 후보 20개 약 22초)이 다르다. 실제 조각으로 자기 하드웨어에서 재라고 안내해야 한다. 후보 수와 검색 시간 제한의 안내, 리랭커 TEI의 compose 프로필은 release-image 계획이 받는다.
- 티켓 20은 이미 `done`이다. 이 PR이 티켓 20 시작 전 확인 문장을 결정 뒤의 모양으로 고쳤다(구현은 결정 전 전제인 리랭커가 있는 지식베이스로 끝났다).
- 대기열의 chore 계기: `mutate-marker-discovery`(11회차), `measured-claim-beyond-probe`(11회차), `crlf-from-script-edits`(8회차), `gate-masked-by-echo-chain`(6회차), `precommit-mutations-after-tests`(5회차), `python-i-utf8`(5회차), `decision-word-residue`(5회차). 기능의 마지막 티켓(13이나 16) 뒤에 chore 배치 줄이 이 항목들을 고른다.
- 실험 환경(GPU compose, 데이터베이스 볼륨)은 내렸다. TEI 모델 캐시 볼륨(`search-eval-tei-probe-data`)은 남겼다. 스크래치 폴더의 임시 기록은 커밋하지 않았다.
