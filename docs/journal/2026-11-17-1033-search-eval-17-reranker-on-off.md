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
- 다시 돌린 명령. `uv run ruff check .`, `uv run ruff format --check .` 초록. 나머지는 pre-commit으로 갈음하며 결과는 커밋 뒤에 적는다.
