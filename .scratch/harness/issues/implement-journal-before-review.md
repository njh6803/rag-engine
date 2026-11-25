# implement-journal-before-review: implement 스킬이 리뷰를 부르기 전에 일지 파일부터 만들고 두 리뷰의 보고를 받은 턴에 옮기게 한다

**What to build:** `.claude/skills/implement/SKILL.md`의 "Once done, use /code-review to review the work." 줄에 한 문장을 더한다. 내용은 둘이다. 리뷰를 부르기 전에 이 브랜치의 일지(`docs/journal/<날짜>-<HHMM>-<슬러그>.md`)가 없으면 머리 한 줄만 든 파일을 먼저 만든다. 셀프 리뷰와 PR 직전 리뷰의 보고는 받은 턴에 그 일지로 옮긴다. 같은 지침이 `code-review` 6단계 끝과 `next-session` `merge.md` 3에 이미 있다. 그런데 구현 때 실리는 자리인 `implement`에는 가리키는 줄이 없어서, 구현 세션이 리뷰 보고를 받고도 일지를 만들지 않았다(대기열 항목의 회차 서술이 원천이다). 새 문장은 규칙을 다시 풀어 쓰지 않고, 이름 규칙과 옮기는 때를 그 두 자리로 가리킨다. 지침의 본문을 `implement`에 한 벌 더 두면 한쪽만 고쳐져 어긋나기 때문이다.

이 티켓의 몫은 `implement` 스킬 한 자리다. 대기열 항목에는 다른 자리와 다른 갈래의 처방(`code-review` 4단계의 두 브리프, `spec-reviewer`와 `to-tickets`, 압축이 보고 직후에 끼어드는 갈래)도 적혀 있다. 이 티켓은 그 가운데 `implement`의 포인터만 반영하므로 항목은 닫지 않고 열어 둔다. 반영한 몫은 항목의 승인 줄에 적는다.

**대기열:** review-report-journal-lag

**Status:** done

- [x] `.claude/skills/implement/SKILL.md`의 "Once done, use /code-review" 줄에 한 문장이 있다. 일지가 없으면 머리 한 줄 파일로 먼저 만들 것과 두 리뷰(셀프 리뷰, PR 직전 리뷰)의 보고를 받은 턴에 옮길 것을 말하고, `code-review` 6단계 끝과 `merge.md` 3을 가리킨다
- [x] 새 문장이 이름 규칙과 옮기는 때의 본문을 되풀이하지 않는다(가리키기만 한다)
- [x] 스킬 머리 주석(센티널)의 "더했다" 목록이 이 문장을 담는다
- [x] 대기열 항목 `review-report-journal-lag`의 승인 줄에 이번에 반영한 몫이 적혀 있고 상태는 `열림`이다
- [x] 지침 검사(`tools/check_instructions.py`)와 손으로 치는 검사 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)이 초록이다(테스트는 커밋의 pre-commit이 갈음한다)

## Comments
