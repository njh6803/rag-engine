# review-report-to-journal-on-receipt: 셀프 리뷰 두 축과 명세 검토의 보고 끝에 받은 턴에 일지로 옮기라는 줄을 단다

**What to build:** 서브에이전트가 보고를 돌려줄 때 그 끝에 "받은 턴에 일지로 옮긴다"는 줄이 함께 오게 한다. 같은 줄이 이미 `coderabbit-review`(`.claude/agents/coderabbit-review.md`)와 `bug-perf-review`(`.claude/agents/bug-perf-review.md`)의 보고 끝에 달려 온다. 아직 닿지 않은 자리는 셋이다.

- `code-review` 스킬 4단계의 두 브리프(표준 축과 명세 축). 셀프 리뷰 두 축의 보고에는 이 줄이 없어, 보고를 받은 세션이 판정을 일지로 옮기지 못한 채 컨텍스트가 압축되었다(대기열 5회차, 9회차).
- `.claude/agents/spec-reviewer.md`. 명세 검토의 보고도 같다(대기열 7회차, 12회차).
- `to-tickets` 스킬. 명세 검토의 보고를 받는 세션이 이 스킬을 따르는데, 그 보고를 일지로 옮기라는 문장이 없다(대기열 7회차, 12회차).

넣는 문장은 규칙을 다시 풀어 쓰지 않고, 이름 짓기와 옮기는 때를 이미 정한 자리(`next-session`의 `merge.md` 3, `code-review` 6단계 끝)로 가리킨다. 보고 끝 줄은 두 에이전트가 이미 쓰는 글을 글자 그대로 쓴다. 한 곳을 고치면 나머지를 같이 찾아 고칠 수 있게 하기 위해서다.

이 티켓이 맡지 않는 것이 둘이다.

- 보고가 온 바로 그 턴에 컨텍스트 압축이 끼는 갈래(대기열 10회차)는 받은 턴에 옮기라는 문장으로는 닿지 않는다. 나란히 여는 `session-asks-extractor` 티켓이 맡는다.
- `implement` 스킬의 포인터는 `implement-journal-before-review` 티켓이 이미 반영했다.

그래서 대기열 항목은 닫지 않고 승인 줄의 일부 반영 문구만 갱신한다. ADR은 필요 없다(지침 한 줄을 더하는 일이고 계약이나 구조를 바꾸지 않는다).

**대기열:** review-report-journal-lag

**Status:** done

- [x] `code-review` 스킬 4단계가 두 브리프(표준 축, 명세 축) 모두에 보고 끝 줄을 글자 그대로 적게 한다. 합친 보고(5단계)에는 그 줄이 한 번만 남는다는 말이 있다
- [x] `.claude/agents/spec-reviewer.md`의 보고 형식 끝에 같은 줄이 있다
- [x] `to-tickets` 스킬에 명세 검토 보고를 받은 턴에 일지로 옮기라는 문장이 있다. 일지가 없으면 머리 한 줄 파일로 먼저 만들 것과, 이름 짓기와 옮기는 때를 가리키는 곳(`merge.md` 3, `code-review` 6단계 끝)을 말한다. 규칙의 본문은 되풀이하지 않는다
- [x] `code-review`와 `spec-reviewer`의 보고 끝 줄이 `coderabbit-review`, `bug-perf-review`가 쓰는 줄과 글자 그대로 같다(`받는 본 세션에게:`로 찾으면 네 파일이 나온다)
- [x] `code-review`와 `to-tickets` 머리 주석(센티널)의 "더했다" 목록이 이번 문장을 담는다
- [x] 대기열 항목 `review-report-journal-lag`의 승인 줄 일부 반영 문구가 이번에 반영한 몫(`code-review` 4단계 두 브리프, `spec-reviewer`, `to-tickets`)을 적고, 남은 것은 보고 직후에 컨텍스트 압축이 끼는 갈래뿐이라고 적는다. 상태는 `열림`이다
- [x] 지침 검사(`tools/check_instructions.py`)와 손으로 치는 검사 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)이 초록이다(테스트는 커밋의 pre-commit이 갈음한다)

## Comments
