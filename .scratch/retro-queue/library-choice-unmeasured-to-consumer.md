# library-choice-unmeasured-to-consumer: 스택에 더할 라이브러리를 PyPI의 메타데이터만 재고 골라, 그것을 쓰는 코드의 타입 검사를 셀프 리뷰 뒤에야 쟀다

**상태:** 열림
**어디로:** `docs/agents/issue-tracker.md` 프로브와 근거 절이 이미 있다. 다섯 번째면 계기 훅 후보(`docs/constitution/tech.md`의 스택 표에 행을 더하는 편집에, 그 라이브러리를 쓰는 코드가 타입 검사와 실행을 지난 프로브가 있는지 묻는 계기를 넣는다. `.claude/skills/grilling/SKILL.md`도 같은 지침을 적는다)
**승인:** 자체 승인 2026-11-12, 1회차(이미 있는 지침을 어긴 사건이라 회차를 센다. 더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-12-2108-search-eval-design.md, ADR 불필요

search-eval 설계 세션이 ADR 0019에서 Anthropic SDK를 고르며 PyPI의 판, 라이선스, `py.typed`만 프로브로 쟀고, 전이 의존의 라이선스 원문과 SDK를 쓰는 코드의 타입 검사는 첫 구현 티켓으로 미뤘다. 셀프 리뷰 표준 축이 Major(판단)로 냈다. 반영에서 전이 의존 셋의 라이선스와 어댑터 꼴의 pyright strict를 프로브로 쟀다. 실제 호출은 키와 비용에 사용자 승인이 필요해 재지 않은 채로 남겼다.
