# session-model-fable-5-2: 설계 인터뷰와 명세 지시문의 모델 값을 Fable 5.2로 고친다

**What to build:** `next-session`의 결정표와 `directive.md`가 설계 인터뷰와 명세 지시문의 "모델" 줄에 적는 값 `Fable 5.1 / xhigh`를 `Fable 5.2 / xhigh`로 고친다. PR #27을 병합한 뒤 명세 세션을 열던 `tools/open_session.ps1`이 모델 메뉴에서 그 이름의 항목을 찾지 못하고 `5초 안에 모델 메뉴의 'Fable 5.1' 을(를) 찾지 못했다.`로 멈췄고, 지시문은 사람이 모델을 손으로 골라 보냈다(2026-11-13, 일지 `2026-11-13-0124-session-model-fable-5-2.md`). 스크립트는 지시문의 `모델:` 줄에 적힌 이름으로 메뉴의 항목을 찾고(이름이 같거나 이름 뒤에 공백과 덧붙임이 오는 항목이다. `Test-NameShows`) 모델 이름의 목록을 따로 두지 않으므로, 고칠 자리는 그 값을 적는 문서 네 곳이다. `.claude/skills/next-session/SKILL.md` 결정표의 설계 인터뷰 줄, 명세 줄, "이어서" 줄의 모델 칸과 `.claude/skills/next-session/directive.md` 2의 잇는 지시문 문장이다. 값의 근거를 agent-os ADR 0029로 가리키는 `directive.md` 2의 문장에는 Fable 칸의 판 번호가 메뉴의 이름을 따른다는 것을 덧붙인다(그 ADR은 5.1로 적는다). 값을 5.2로 정한 것은 사용자다(일지의 인용). 코드와 시험은 바꾸지 않는다. 모델 이름을 읽는 시험과 검사가 없다(`tools/`와 `tests/`의 `*.py`를 `Fable`, `Sonnet 5.5`, `Opus 5.5`, `xhigh`로 grep해 손으로 봤다).

**대기열:** 없음

**Status:** done

- [x] 네 자리가 `Fable 5.2 / xhigh`를 적는다
- [x] 일지를 뺀 저장소에서 옛 값이 남은 자리가 이 티켓뿐이다(`git grep -n -I "Fable 5.1" -- . ":(exclude)docs/journal"`. 스테이징한 뒤 돌렸다)
- [x] 스크립트가 모델 메뉴에서 `Fable 5.2`를 찾아 고른다(`pwsh -NoProfile -File tools/open_session.ps1 -Action defaults -Model 'Fable 5.2' -Effort xhigh`를 손으로 돌렸다. 기본값이 `Sonnet 5.5`일 때 돌려 `model=Fable 5.2 원래 Sonnet 5.5`, `effort=xhigh 원래 high`가 나왔고, 끝난 뒤 새 세션 화면의 기본값을 `Sonnet 5.5 / high`로 되돌렸다. 출력 전문은 일지의 실행 확인 절)
- [x] 손으로 치는 검사 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)이 초록이다(이 티켓을 싣는 커밋의 pre-commit이 다섯을 돌린다. 하나라도 빨가면 커밋이 만들어지지 않는다)

## Comments

- 2026-11-13 셀프 리뷰. 남긴 것은 셋이고 판정과 이유는 일지의 셀프 리뷰 절에 있다. 같은 값이 네 곳에 흩어진 구조, 옛 "이어서" 줄로 열린 구현 세션이 옛 값을 다음 지시문으로 잇는 갈래, 수용 기준 둘째 줄의 명령이 커밋 전에는 미추적 파일을 보지 못하는 것이다.
- 병합 뒤에도 주 체크아웃과 먼저 딴 워크트리의 스킬 사본은 당기거나 합치기 전까지 옛 값을 낸다. 그때 사람이 할 일은 일지의 "다음"에 있다.
- 이름이 다시 바뀔 때의 비용은 대기열 `model-menu-name-drift`가 든다.
