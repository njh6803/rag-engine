# search-eval 11: 빠른 게이트의 CI 잡과 경로 판정 · 2026-11-16

티켓 `.scratch/search-eval/issues/11-fast-gate-ci.md`를 마무리하고 병합한 기록이다. 브랜치는 `feature/11-fast-gate-ci`, PR은 #51이다. 구현과 CI 실행 기록은 앞 세션이 마쳤고, 사용자가 계정을 바꿔 잇기를 원해 끊었다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `11-fast-gate-ci`에 들어와 이어 갔다.

## 한 것

- 앞 세션이 낸 것: 경로 판정 `tools/eval_gate_paths.py`(시험 62개, 변이 12개)와 `ci.yml`의 `eval-fast` 잡, `workflow_dispatch` 계기, `compose.eval.yml`의 모델 볼륨 환경 변수, 첫 기준 보고서 `evals/public-docs/baseline-fast.json`, 프로브 `ci-fast/`와 `probes/README.md` 두 행, 티켓 Comments(실측, 흔들림, 시간, 실행 기록).
- 이 세션이 마친 것: 헌법 `docs/constitution/operations.md` 9행을 사용자가 승인한 문장으로 고친 변경과 판 1.3.1에서 1.3.2로의 상승을 커밋에 싣고, 티켓을 `done`으로 닫았다. 전체 검사 넷을 다시 돌렸다.
- 흔들림은 같은 커밋의 세 번이 299칸 가운데 실행 시각 하나만 달라 지표의 차가 0이었다. 잡 시간은 3분 15초에서 4분 39초로 15분 한도의 약 31% 이하다.

## 정한 것

- 헌법 판을 patch(1.3.2)로 올린 까닭: 새 원칙이나 새 절이 없고, 기존 절(`operations.md` CI 칸)의 한 줄을 "기준치 아래로 떨어질 때 CI가 실패한다"에서 게이트가 선 동작(경로 판정, 하락폭 2%p와 0.02, 기준 보고서는 사용자의 승인으로만 바꾼다)으로 고쳤을 뿐이다. 문구 수정은 patch라는 `docs/constitution/principles.md` 거버넌스를 따랐다. 승인은 사용자가 "승인"이라고 답했고 티켓 Comments의 헌법 개정 항목에 글 그대로 적었다. `Last Amended`는 승인한 날(2026-11-15)로 뒀다.
- 첫 기준 보고서도 사용자가 "승인"이라고 답했고, 승인받은 `report.json`을 고치지 않고 복사했다(sha256은 티켓 Comments).
- 하락폭 2%p(0.02)는 흔들림 0과 기준 보고서의 승인으로 확정됐다. 이 세 번은 한 커밋, 한 종류의 러너에서 얻은 값이라 하락폭을 정당화하는 폭이라기보다 이 구성(추론 기록을 읽는 실행)의 결정성을 보인 것으로 읽어야 한다.
- 문서만 바꾼 커밋의 평가 건너뛰기 기록은 이 PR이 `ci.yml`과 `src/`를 바꿔 이 PR 안에서 낼 수 없어, base가 이 브랜치인 임시 PR(#54, #55)로 냈고 병합하지 않고 닫았다.
- 떨어뜨림 기록은 검색 코드를 망가뜨려 만들지 못했다. 합치기 식을 망가뜨린 커밋은 단위 시험이 막아 pre-commit을 지나지 못했다. 그래서 임시 브랜치에서 기준 보고서의 숫자를 올려 게이트의 하락 판정 동작만 보였고, 실제 검색 품질 저하를 이 게이트가 잡는지는 이 기록으로 보지 못했다고 티켓에 적었다.

## 검증

- 린트, 포맷, pyright, lint-imports가 모두 종료 코드 0이다. 전체 pytest의 결과는 티켓 체크박스 20에 따른다.
- 본 PR의 최신 푸시(`4bfd1b7`)에서 `eval-fast`가 4분 2초에 성공했고 `compare`가 기준과 견주어 통과했다.

## 셀프 리뷰와 PR 직전 리뷰

- 셀프 리뷰는 앞 세션이 첫 커밋 전에 돌렸다. 그 뒤에 더한 것(기준 보고서, 프로브 `ci-fast/`, README 두 행, 티켓 Comments, 헌법 한 줄)을 PR 직전에 봤다.
- `coderabbit-review`(CLI 0.7.5, 지적 0건으로 `review_completed`)와 에이전트의 직접 대조: Critical과 Major는 없었다. 헌법 9행의 숫자와 이름은 `eval_compare.py`의 `HIT_AT_5_DROP`·`MRR_DROP`, `ci.yml`, `eval_gate_paths.py`와 맞았고, 티켓 Comments의 시간과 실행 결과는 `gh api`로 다시 읽은 값과 맞았다.
- 반영한 것(Minor 둘과 Nit 하나): 이 일지가 없던 것(지금 쓴다), 티켓 34행에서 떨어뜨린 커밋의 실행에 `ticket` 잡도 빨강이었다는 구절(`gh run view 43722013203`으로 손으로 봤다. `verify`의 빨강이 `eval-fast` 하나만의 결과라고 가르지 못한다), 티켓 30행에서 보고서의 `meta.commit`이 PR 병합 커밋 `ac9e576`이라는 구절.
- 남긴 것: 추적하지 않는 `.scratch_*.log` 임시 파일은 커밋 전에 지운다. `Last Amended`는 승인일 기준으로 둔다(이 저장소에 어느 날짜를 쓰라는 규칙을 찾지 못했다).
- 오탐으로 가른 것: `actions/*`의 태그 고정(`.github/zizmor.yml`이 허용), 경로 목록에 `tests/`가 없는 것(독스트링의 못 보는 것에 적은 의도), 산출물이 공개 저장소에 30일 남는 것(공공 문서 묶음이라 원칙 V에 걸리지 않는다).
- `/security-review`: 높은 확신의 취약점 0건, 중간 확신 0건. 워크플로 주입(env로 넘기고 `::stop-commands::`로 막음), 권한(`contents: read`, 비밀 없음), 캐시 오염(병합 ref에 묶임), 경로 판정 우회(설계상의 한계), 명령 주입(`subprocess` 인자 목록)을 확인했다.

## 회고

후보 셋을 내고 승인 1, 기각 2, 넘김 0이다. 후보는 앞 세션이 지시문에 남긴 회고 후보 셋이고, 이 세션이 직접 겪은 실수는 없다. 아래 사건 서술은 그 지시문이 원천이다. 만료할 항목은 없었다(`queue_open_rows.py`가 만료할 항목 없음).

- 승인. `python -I`가 `PYTHONUTF8`을 무시한다는 지시문의 후보는 열린 항목 `python-i-utf8`이 이미 같은 사건을 적고 있다. 앞 세션이 CI 실행 기록을 읽는 스크립트를 `-I`로 돌렸더니 출력이 깨져 `-X utf8`로 풀었다. 사건: 읽지 못하는 출력으로 한 번 더 돌았다. 층: 지침(`CLAUDE.md` 환경 함정 한 줄)이 처방이고 검사로 옮길 수 없다. 되돌림: PR 하나다. 항목에 5회차를 더했다(`.scratch/retro-queue/python-i-utf8.md`, 4회차에서 5회차). 5회차에 이르러 `next-session` 결정표의 chore 배치 조건이 됐다. 이 세션은 반영하지 않는다.
- 기각. 검색 코드를 실제로 망가뜨린 커밋은 단위 시험이 막아 pre-commit을 지나지 못해 떨어뜨림 기록을 기준을 올려 만들었다는 후보. 실수가 아니라 게이트가 설계대로 일한 결과이고, 티켓 Comments의 실행 기록 항목이 한계(실제 품질 저하를 이 기록으로 보지 못했다)를 이미 적었다.
- 기각. `tools/wait_ci.py`의 `--head`가 40자 SHA를 요구하고 `--expect verify`가 없으면 CodeRabbit을 15분 기다린다는 후보. `--head`에 짧은 SHA를 주면 도구가 "`--head` 는 40자 SHA 로 준다"를 내고 끝나(`tools/wait_ci.py` 569행) 이미 그 자리에서 알린다. `--expect verify`는 CodeRabbit을 요청하지 않는 출시 PR과 되돌려 합치기 PR의 절차이고 `merge.md`가 거기에 적었다. 티켓 PR은 `@coderabbitai review`를 요청하므로 CodeRabbit을 기다리는 것이 맞다.

- 일지에만 남김. 부하 시간 시험 종류의 새 사례. 이 커밋의 첫 시도에서 pre-commit의 pytest가 3건 빨갰다(`tests/app/test_job_lease.py`의 5초 상한이 5.27초, `tests/contract/test_search_complete.py`와 `tests/contract/test_tool_errors.py`의 MCP 클라이언트 `ReadTimeout`. 2060초에 4479개 가운데 3개). 바로 앞에 같은 작업 트리에서 돌린 전체 pytest는 4479개가 모두 통과했고(4457초), 이 커밋은 문서와 대기열 항목만 바꿔 코드를 건드리지 않는다. 사용자가 2026-11-15에 이 종류를 다시 열지 않기로 했으므로(대기열 `token-expiry-test-load-margin`은 위험을 받아들이며 닫혔다) 시험을 고치지 않고 커밋을 다시 시도했다.

## 다음

- 이 PR이 병합되면 티켓 11은 끝이다. `.scratch/search-eval/plan.md`의 `끝` 줄은 아직 없다. 열린 티켓은 13, 15, 16, 17, 18이다.
- 15(전체 게이트)는 11이 dev에 들어간 뒤에야 `workflow_dispatch` 수동 실행이 뜨는지 실행 기록으로 확인할 수 있다. 이 티켓이 확인하지 못한 것이다(기본 브랜치의 워크플로 파일에 이 계기가 들어가기 전에는 뜨는지 문서가 적지 않는다). 수동 실행에서 다른 잡과 `verify`가 어떻게 끝나는지도 15가 본다.
- 13과 16은 이 티켓의 기준 보고서(`baseline-fast.json`)를 읽는다. 기록(`records/`)을 다시 만들면 기록 해시가 바뀌어 `compare`가 실패하므로 기준 보고서를 사용자의 승인으로 새로 만들어야 한다.
- 대기열 `python-i-utf8`이 5회차가 됐다(회고 절). `CLAUDE.md` 환경 함정에 `-X utf8` 한 줄을 더하는 chore를 `next-session` 결정표가 고를 수 있다.
- 게이트가 빨갛다고 에이전트가 기준 보고서를 스스로 갱신하지 않는다. 멈춰 보고한다(헌법 `operations.md` 9행).
