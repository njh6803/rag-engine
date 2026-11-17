# search-eval 15: 전체 게이트의 CI 잡과 출시 앞 맞추기 절차 · 2026-11-16

티켓 `.scratch/search-eval/issues/15-full-gate-ci.md`를 구현한 기록이다. 브랜치는 `feature/15-full-gate-ci`, PR은 #57(base dev)이다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `15-full-gate-ci`에 들어와 진행했다.

## 한 것

- 판정: `tools/eval_gate_paths.py`에 전체 게이트의 판정 `decide_full`과 환경 변수 `EVAL_GATE`(`fast` 기본, `full`)를 더했다. base가 `main`인 PR과 수동 실행은 평가하고, 푸시와 base가 다른 PR은 평가하지 않는다. base를 읽지 못한 PR과 알지 못하는 이벤트는 평가한다(닫힘 쪽). 알지 못하는 `EVAL_GATE`는 종료 코드 2로 끝나 출력 파일을 쓰지 않는다. 시험은 96개이고, 변이 표는 19개로 이번에 7개(13~19)를 더했다.
- 잡: `ci.yml`에 `eval-full`을 더했다. 잡은 건너뛰지 않고 늘 시작하며 첫 스텝이 평가 여부를 가른다. 나머지 스텝은 `if: steps.paths.outputs.evaluate == 'true'`로 가른다. 차례는 빠른 게이트와 같고 `run --through rerank --records read`와 `compare --gate full`만 다르다. 모델 캐시는 복원만 하고 저장하지 않는다. `verify`의 `needs`에는 이름만 더했다.
- 절차: `.claude/skills/next-session/merge.md`의 출시 PR 절에 전제 확인 3(dev의 머리에서 전체 게이트 초록)과 "기록과 기준 맞추기"를 적었고, `SKILL.md`의 출시 PR 줄에 같은 확인을 더했다.
- 첫 `baseline-full.json`: 커밋 `b700333`의 수동 실행(실행 43766794021)이 올린 `report.json`을 사용자의 승인("승인")을 받아 고치지 않고 복사했다(sha256 `cc2236b8…ab679b`, 티켓 Comments).
- 문서: 사용자의 승인("승인")을 받아 헌법 `operations.md` 9행·24행과 판(1.3.2에서 1.3.3, patch), ADR 0018의 새 이력과 본문 포인터 셋을 고쳤다.

## 정한 것

- 푸시는 평가하지 않는다. main은 PR의 머리를 병합한 내용이라 그 PR에서 이미 쟀다는 것이 `tools/eval_gate_paths.py` 독스트링이 적은 까닭이다.
- 평가를 건너뛰는 일은 잡의 조건이 아니라 스텝의 조건으로 가른다. 잡을 건너뛰면 필수 검사 `verify`가 빨강으로 센다.
- 티켓은 "같은 브랜치에 푸시를 이어 넣어" 앞 실행의 취소를 보라고 적었으나, 이 저장소의 `ci.yml`은 푸시를 main과 dev에서만 받는다. 그래서 같은 `--ref`로 수동 실행을 연달아 두 번 띄워 앞 실행이 취소되는 것을 봤다. 취소된 실행의 `verify`는 빨강으로 끝났다(다른 잡이 성공하지 못해서). 티켓 Comments에 이 차이를 적었다.
- PR의 base를 dev에서 main으로 바꿨을 때 CI가 다시 도는지는 확인하지 않았다(`pull_request`의 기본 types에 `edited`가 없다고 보지만 문서를 읽지 않았다). `edited`를 types에 더하면 제목을 고칠 때마다 CI가 다시 시작되고 앞 실행이 취소되므로 더하지 않고, 독스트링의 "전체 게이트가 못 보는 것"에만 적었다.

## 검증

- 전체 게이트의 수동 실행(실행 43766794021): `python`·`image`·`ticket`·`eval-fast`가 성공, `eval-full`이 `compare`에서 실패(기준 보고서가 없어서, 예상한 실패), `verify`가 실패했다. `eval-full`은 4분 20초에 추론 기록 15,786건을 읽고 새로 계산한 수는 0이었다.
- 연달아 띄운 수동 실행 둘(43768005935, 43768046697)에서 앞 실행이 `cancelled`로 끝났다.

## 셀프 리뷰

- `/code-review`(표준 축과 명세 축, 둘 다 서브에이전트)를 돌려 지적을 코드와 문서에 반영했다. 반영하지 않은 것: `eval-full` 스텝 60줄이 `eval-fast`와 겹치는 것(티켓이 "차례는 빠른 게이트와 같다"고 요구해 같은 차례를 유지했다), `decide`와 `decide_full`의 이름이 비대칭인 것(독스트링이 설명한다), `pull_request`에 `edited`가 없는 것(위 "정한 것").

## PR 직전 리뷰

- `coderabbit-review` 에이전트를 돌렸으나 이 보고에서는 CodeRabbit CLI를 돌리지 않았다고 했고(읽기와 실행 대조만 했다), 실질은 `bug-perf-review`와 같은 축의 대조다. 밀 주장은 에이전트가 `decide_full`을 이벤트 6종과 base 6종으로 불러 보고, `gh run view --json jobs`로 티켓 Comments의 실행 기록을 다시 읽어 맞다고 확인했다. Critical은 없었다.
- Major 하나: `merge.md` 전제 확인 3의 재실행이 같은 브랜치를 다시 띄우면 새 실행이 등록되기 전에 앞 실행(failure나 cancelled)을 새 판정으로 읽는다. → 다시 띄울 때마다 새 시각의 이름으로 새 임시 브랜치를 올리게 고쳤다.
- Minor 넷을 고쳤다. 진행 중인 맞추기 티켓을 어디서 찾는지(`origin/dev`와 base가 dev인 열린 PR의 머리, 첫 줄 `# <번호>: 기록과 기준 맞추기`)와 누가 만드는지, `gh run cancel`이 이미 끝난 실행에서 실패해도 무시하고 임시 브랜치를 지운다, 대기는 foreground `sleep`이 막혀 있어 `Monitor`의 until 루프로 한다, 기다리는 동안 dev가 움직였는지 `origin/dev^{tree}`를 다시 대 본다.
- ADR 0018 새 이력의 "빨강이면 GPU로 다시 만든다"가 `merge.md`보다 단순하다는 지적을 받아, `compare` 메시지로 까닭을 가르고 품질 저하는 조사라는 `merge.md`의 갈래를 그대로 옮겼다. 사용자가 승인한 초안의 한 문장을 `merge.md`와 맞춘 정정이다.
- Nit 둘: `merge.md`의 "20분짜리 실행"을 실측(실행 43766794021의 `python` 잡까지 약 11분)으로 고쳤다. 원격 `scratch/15-gate-drop`은 이 PR이 병합되기 전에 지운다.
- 남긴 것: PR의 base를 dev에서 main으로 바꿨을 때 CI가 다시 도는지 확인하지 않은 위험은 독스트링과 ADR 이력에 이미 적었다(열린 위험).
- `/security-review`: 확신 8 이상의 취약점 0건. 워크플로 주입(`github.base_ref`를 env로 넘기고 `::stop-commands::`로 감쌈), 권한(`contents: read`, `pull_request_target` 없음, 비밀 없음), 캐시 복원만 하는 것, `GITHUB_OUTPUT`에 고정 한 줄만 쓰는 것을 확인했다. 참고로 `eval-fast`와 같은 캐시 키를 복원하므로 그쪽의 캐시 오염 가능성을 상속하지만 새 경로는 아니다.

## 부하 시간 시험의 새 사례 (일지에만 남김)

이 변경은 `tools/`, `tests/tools/`, CI, 문서만 바꾸는데, 커밋의 pre-commit(전체 pytest가 15~26분, 다른 세션이 여럿 돌던 때)에서 서로 다른 시험이 번갈아 빨갰다. 시도마다 다음 시험이 실패했다: `tests/app/test_worker_service.py`의 10초 기한 시험, `tests/test_serve_command.py`의 30초 기동 기한(세 번), `tests/contract/test_search_complete.py`의 MCP 클라이언트 `ReadTimeout`, `tests/app/test_job_lease.py`의 5초 상한(6.53초), `tests/adapters/test_postgres_engine.py`의 연결 상한 시험. `test_serve_command`는 같은 시험이 반복 실패해 작업 규약 6에 따라 진단했고, 홀로 돌리면 통과했다(2 passed, 5분 34초). 사용자가 2026-11-15에 이 종류를 다시 열지 않기로 했으므로 시험을 고치지 않고 같은 커밋을 다시 시도했다(훅은 건너뛰지 않았다).

## 봇 회차

- claude-review 첫 회차(커밋 `c93f17e`): Critical과 Major는 없고 Minor 둘, Nit 하나다. 첫 회차의 Minor와 Nit은 지적마다 판단했다.
- Minor, `tools/eval_gate_paths.py`의 모듈 이름과 독스트링이 두 게이트의 규칙을 한 덩어리로 담는다는 지적: 보류한다. 이름을 바꾸면 `ci.yml`, 시험 파일, 변이 표, ADR 0018 이력, 헌법 문장이 함께 움직이는 별도 정리라 이 티켓의 범위 밖이다. 뒤로 넘기는 일이라 아래 "다음"에 적는다.
- Minor, `decide`와 `decide_full`의 이벤트 분기가 두 곳에 따로 있다는 지적: 보류한다. 이벤트가 둘뿐이고 알지 못하는 이벤트의 닫힘 쪽 처리를 시험이 따로 고정해 어긋나면 잡힌다. 공통 분기를 뽑는 것은 아직 필요가 없는 일반화다.
- Nit, 시험 이름이 함수 이름과 환경 변수 이름을 담는다는 지적: 보류한다. 기존 시험이 같은 꼴이다.
- CodeRabbit은 별이 10개 미만인 저장소라 자동 리뷰를 하지 않아 `@coderabbitai review` 코멘트로 요청했다. 첫 회차(커밋 `c93f17e`, 리뷰 한 건이 달렸다)는 범위 밖 코멘트로 Major 하나, 인라인으로 Minor 하나를 냈다.
- Major, `pull_request`의 `types`에 `edited`를 더해 base 변경에도 CI를 돌리라는 지적: 보류한다. 이 설계는 PR 본문 "검토했으나 택하지 않은 안"과 이 일지 "정한 것"이 이미 가렸다. `edited`를 더하면 제목과 본문을 고칠 때마다 CI가 다시 시작되고 앞 실행이 취소되며, 출시 PR은 처음부터 base가 main으로 열려 `opened` 이벤트에서 평가한다. 남은 위험(열린 PR의 base를 바꾼 경우)은 독스트링과 ADR 0018 이력에 적혀 있다.
- Minor, ADR 0018 이력과 `merge.md`가 기록에 없는 쌍을 `compare` 메시지로 가른다고 적었으나 그 경우는 `run --through rerank` 스텝이 먼저 멈춰 `compare`가 돌지 않는다는 지적: 맞는 지적이라 고쳤다. 두 문서가 이제 "실패한 스텝의 로그로 가른다"고 하고 `run` 스텝의 "기록에 없는 쌍이 있고" 오류와 `compare`의 해시 불일치 거부를 구분한다. 사용자가 승인한 이력 초안의 한 문장을 사실에 맞춘 정정이다(앞의 `merge.md`와 맞춘 정정과 같은 종류).
- base가 dev인 이 PR의 CI(실행 43820193972)에서 `eval-full`은 7초에 성공으로 끝났고 첫 스텝 뒤의 열두 스텝(설치부터 산출물 올리기까지)이 모두 `skipped`였다(`gh run view --json jobs`로 읽었다). 티켓 실행 기록 14번의 남은 한 항목이 이것이다.

## 회고

후보 넷을 내고 승인 1, 기각 3, 넘김 0이다. 만료할 항목은 없었다(`queue_open_rows.py --ref origin/dev`가 만료할 항목 없음).

- 승인. 변이 19의 표지를 시험이 낸 `assert 0 == 2` 풀이 줄로 골라 `check-mutations`가 단언 풀이 줄이라며 거부했다. 사건: 표지를 고치고 변이 19와 `--check`를 다시 돌았다. 층: 열린 항목 `mutate-marker-discovery`가 이미 같은 사건을 처방하고 있어(도구가 어긋난 변이의 출력을 한 번에 보여 주는 길) 새 항목을 쓰지 않았다. 되돌림: PR 하나다. 항목에 10회차를 더했다(`.scratch/retro-queue/mutate-marker-discovery.md`, 9회차에서 10회차). 이미 chore 배치 조건(회차 5 이상)이라 이 세션에서 반영하지 않는다.
- 기각. 상대 경로 리다이렉트가 한 번 실패해 절대 경로로 바꿨다. 열린 항목 `redirect-outside-worktree`의 사건(주 체크아웃에 파일이 만들어짐)과 다르고, 비용은 호출 한 번이며 데이터를 잃지 않았다.
- 기각. 훅이 그 자리에서 막은 셋: 부정 glob을 쓴 Grep이 `.env`에 닿아 거부된 것, `check-ticket`이 브랜치 이름이 티켓을 가리키지 않는 `scratch/15-gate-drop`의 커밋을 막은 것(분리 HEAD에서 커밋해 지났다), 브랜치가 `origin/dev`보다 뒤처져 푸시가 막힌 것(`CLAUDE.md` 환경 함정대로 `git merge origin/dev`로 풀었다). 이미 있는 훅이 막고 알렸다.
- 기각. 티켓 18 세션이 티켓 15 파일에 메모를 넣어 병합에서 티켓 파일이 충돌한 것. 양쪽을 모두 보존해 풀었고 잃은 것이 없으며 사건이 한 번이다.
- 일지에만 남김. 부하 시간 시험 종류의 새 사례(위 절). 사용자가 2026-11-15에 이 종류를 다시 열지 않기로 했다.

## 다음

- 이 PR(#57)이 병합되면 티켓 15는 끝이다. 남은 티켓과 프론티어는 `uv run python tools/plan_table.py`가 만드는 `.scratch/plan.md`로 본다.
- 출시 PR(dev에서 main)이 이 변경의 첫 실제 확인이다. 그 PR에서 `eval-full`이 평가하는지, `github.base_ref`가 짧은 이름(`main`)으로 오는지를 본다. 이 PR은 base가 dev라 이 확인을 하지 못했다. 열린 PR의 base를 dev에서 main으로 바꿨을 때 CI가 다시 도는지도 아직 확인하지 않았다.
- `merge.md`의 새 절차(전제 확인 3의 임시 브랜치와 수동 실행 기다리기, "기록과 기준 맞추기")는 이 저장소에서 밟은 적이 없다. 첫 출시 PR 앞에서 밟다가 어긋나면 그 자리에서 고친다.
- 첫 `baseline-full.json`은 CI 한 번의 실행에서 얻은 값이다. 같은 커밋의 실행을 더 쌓아 흔들림을 재는 일은 아직 없다.
- claude-review가 낸 Minor를 뒤로 넘겼다. `tools/eval_gate_paths.py`의 이름과 독스트링을 게이트별로 나누는 정리(경로로 가르는 `decide`와 이벤트·base로 가르는 `decide_full`)다. 이름을 바꾸면 `ci.yml`, 시험, 변이 표, ADR 0018 이력이 함께 움직이므로 하네스 chore 하나로 한다.
- 대기열 `mutate-marker-discovery`가 10회차다. `next-session` 결정표의 chore 배치가 고를 수 있다.
- 게이트가 빨갛다고 에이전트가 기준 보고서를 스스로 갱신하지 않는다. 멈춰 보고한다(헌법 `operations.md` 9행).
