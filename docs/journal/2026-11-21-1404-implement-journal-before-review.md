# implement-journal-before-review: implement 스킬이 리뷰 전에 일지 파일을 만들고 보고를 받은 턴에 옮기게 한다 · 2026-11-21

대기열 `review-report-journal-lag`(10회차로 센다) 가운데 `implement` 스킬의 포인터 한 문장만 반영하는 harness 티켓이다. 브랜치는 `chore/implement-journal-before-review`(기준 `origin/dev`, `64bd055`), 작업은 같은 이름의 워크트리에서 했고 모델은 Sonnet 5.5 / high이다. 항목은 다른 처방이 남아 있어 닫지 않고 승인 줄에 반영한 몫만 적었다.

## 셀프 리뷰

`/code-review`를 기준 `64bd055`로 돌렸다. 범위는 수정 파일 둘(`implement/SKILL.md`, 대기열 항목), 미추적 파일 둘(티켓, 이 일지), 커밋 없음이다.

### 명세 축

Critical·Major 없음, Minor 넷. 누락은 없다고 했다. 새 문장이 `code-review/SKILL.md` 132행과 `merge.md` 3의 내용과 맞는 것, 인용 "Once done, use /code-review to review the work."가 원문 그대로인 것, 머리 주석의 "열"이 목록을 센 값과 맞는 것을 대 보았다.

- Minor 1(남김): 문장 끝에 붙은 이유 구절(미루면 컨텍스트 압축 뒤 요약에서 일지를 다시 짓게 된다는 말)이 이유 서술이라 "가리키기만 한다"는 티켓 취지에 가깝게 걸린다. 규칙 본문이 아니라 이유 한 줄이고, 지워도 요구는 서지만 지침을 따르는 쪽이 왜 지켜야 하는지 알게 하는 줄이라 둔다.
- Minor 2(남김): 문장이 "PR 직전 리뷰의 보고"도 말하는데 PR 직전 리뷰는 `implement` 흐름 바깥에서 돈다(대기열 `pre-pr-review-missing-from-implement-path`가 같은 틈). 요구가 "두 리뷰"를 말해서 맞고, 그 틈은 그 항목의 몫이다.
- Minor 3(남김): "이 브랜치의 일지"를 알아보는 법이 없다(일지 이름에 브랜치 이름이 없다). 이 티켓은 티켓 stem을 슬러그로 썼다. 슬러그 규칙을 정하는 것은 `merge.md` 3의 몫이라 이 티켓에서 더하지 않는다.
- Minor 4(고침): 머리 주석에 이 저장소의 대기열 식별자가 들어간 것이 괄호 속 번호는 agent-os의 기록이라는 앞 설명과 어긋나 보인다. 식별자 앞에 "이 저장소 대기열"을 붙였다.
- 사실 메모: 요청문의 9회차와 달리 `tools/queue_open_rows.py`는 이 항목을 10회차로 센다. 이번 변경이 회차를 더하지는 않는다.
- 다시 돌린 것: 보고가 `uv run python tools/check_instructions.py`(종료 0)와 `tools/queue_open_rows.py`(항목 읽힘)를 다시 돌렸다.

### 표준 축

확정 위반 없음, Minor 셋과 Nit 둘(모두 판단 문제). 머리 주석의 "열"이 원본에 더한 항목을 센 값과 맞는 것, 가리킨 두 자리의 내용, 대기열 항목의 모양과 부분 반영 규칙, 티켓 서식, 옛 표현 `아홉을`의 잔존 0을 대 보았다.

- Minor 1(고침): "이 브랜치의 일지가 없으면"에 있는지 알아보는 길이 없다. 기능 일지는 슬러그가 브랜치 stem과 다르고(`core-05-ingest-api` 대 `feature/05-ingest-api`), `git branch -m` 개명 뒤에도 이름으로는 못 찾고, 리뷰 전에 만든 일지는 미추적이라 diff에 안 보인다. 괄호로 `git status --porcelain`과 기준 브랜치 대비 변경에서 `docs/journal/` 파일을 찾아 보라는 길과 까닭을 한 구절로 더했다.
- Minor 2(일부 고침): 새 문장이 이미 있는 지침을 세 번째로 되풀이한다. 규칙 본문은 두 자리로 가리키기만 하고, 까닭 한 구절은 남긴다(지키는 쪽이 왜 지키는지 알게 하는 줄이다). 영어 문장 뒤에 한 줄로 붙은 모양은 `implement`의 다른 추가와 달라 보이지만 원문 줄을 건드리지 않으려고 그대로 둔다.
- Minor 3(남김): "PR 직전 리뷰의 보고"는 `implement` 단계가 아니다. 지침 자체는 맞고 요구가 "두 리뷰"를 말하며, 대기열 8회차는 구현 세션이 직접 `coderabbit-review`를 돌린 사건이다.
- Nit 4(고침): "일지를 다시 짓게 된다"가 대기열 서술(판정을 압축 요약과 PR 본문에서 다시 모았다)보다 셌다. "보고의 판정을 다시 모으게 된다"로 맞췄다.
- Nit 5(고침): 이 일지 첫 줄의 접두 `# chore <슬러그>:`가 다른 일지에 없는 모양이었다. 가까운 harness 일지처럼 `# <슬러그>: …`로 바꿨다.
- 남은 갈래: 압축이 보고 직후에 끼는 갈래와 리뷰 실패 갈래는 이 변경으로 닫히지 않는다. 승인 줄이 이미 "아직 남았다"고 적었다.
- 다시 돌린 것: 보고는 `git diff`와 Grep으로 센 것뿐이다. 검사는 아래에서 돌린다.

## 한 일과 확인한 것

- `.claude/skills/implement/SKILL.md`: "Once done, use /code-review" 줄에 한 문장을 더했다. 일지가 없으면 머리 한 줄 파일로 먼저 만들 것(있는지 알아보는 길 포함), 두 리뷰의 보고를 받은 턴에 옮길 것을 말하고 `merge.md` 3과 `code-review` 6단계 끝을 가리킨다. 머리 주석의 "아홉"을 "열"로 바꾸고 이 포인터를 목록에 더했다.
- `.scratch/retro-queue/review-report-journal-lag.md`: 승인 줄에 일부 반영한 몫과 남은 몫을 적었다. 상태는 `열림`이다.
- 티켓 `.scratch/harness/issues/implement-journal-before-review.md`는 첫 커밋에 `in-progress`로 실렸다가 PR 직전 리뷰의 Major로 잡혀 두 번째 커밋에서 `done`과 체크 완료로 고쳤다(아래 절). 하네스 티켓은 전체 계획 표에 들지 않아 `tools/plan_table.py`가 `.scratch/plan.md`를 바꾸지 않는다.
- 확인: `tools/check_instructions.py` 종료 0, `tools/plan_table.py --check` 종료 0, `ruff check .`와 `ruff format --check .` 초록, `pyright` 오류 0, `lint-imports` 2 kept. 테스트 전체는 커밋의 pre-commit이 갈음한다. 이 변경은 지침 문서뿐이라 `tdd`의 빨강 단계와 변이 도구는 해당이 없다(지침 문장을 지키는 시험이 저장소에 없다).
- 첫 커밋 시도는 제목이 96자라 commit-msg 훅에서 막혔고(72자 제한), 제목을 줄여 다시 커밋했다. 그 사이 pre-commit의 pytest가 두 번 돌아 시간(약 15분씩)이 들었다.

## 커밋과 PR 직전 리뷰

커밋 `0248af9`는 pre-commit을 통과했다. 이어 PR 직전 리뷰를 `bug-perf-review`로 돌렸다(CodeRabbit CLI는 앞 핫픽스에서 권한 분류기가 거절해 쓰지 않았다. 보안 축은 변경이 지침 문서뿐이라 돌리지 않았다). 유효 2건, 오탐 0.

- Major(고침): 티켓이 첫 커밋에서 `Status: in-progress`에 체크박스가 모두 비어 있는데 일지는 `done`으로 두었다고 적었다. 원인은 앞서 `sed`로 상태를 바꾸는 명령을 `plan_table.py`와 한 명령에 묶었더니 도구가 복합 git 형태라며 통째로 거부해 `sed`도 실행되지 않았는데, 거부된 줄을 확인하지 않고 일지에 `done`이라고 쓴 것이다. 분리한 명령으로 `done`과 체크 완료를 하고 `pyright`, `lint-imports`도 이때 돌려 다섯째 체크박스(검사 다섯)를 실제 결과로 채웠다. 일지의 해당 줄도 바로잡았다.
- Minor(고침): 새 문장의 확인 길 "기준 브랜치 대비 변경"에 명령이 없었다. 기준 브랜치와 바로 비교하면 그 사이 병합된 남의 일지가 보일 수 있어 `git diff --name-only $(git merge-base origin/<기준 브랜치> HEAD)`로 병합 기준점과 비교하라고 문장에 적었다.
- 밀 주장 대조: 가리킨 두 자리의 내용, 머리 주석의 열 항목, `queue_open_rows.py`가 읽는 승인 줄(10회차, 열림)은 맞다고 확인했다. 일지가 이미 있는 브랜치와 리뷰 실패 뒤 재시도는 틀린 동작이 없다.
- 남김: 압축이 리뷰 보고를 받은 뒤에 끼는 갈래는 문장이 리뷰를 부르기 전으로 묶여 있어 이미 보고를 받은 뒤 들어온 세션에는 일지를 만들라는 말이 없다. 항목의 남은 몫(10회차 메모)이라 새 지적으로 세지 않는다.
- 다시 돌린 것: 위 `확인` 줄의 검사. 이 고침 커밋의 테스트는 pre-commit이 갈음한다.
