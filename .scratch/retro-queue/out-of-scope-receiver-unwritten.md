# out-of-scope-receiver-unwritten: 명세 Out of Scope가 "source-sync 계획 본문에 적었다"고 한 고아 원본 정리가 그 계획에 없었다

**상태:** 열림
**어디로:** `.claude/skills/to-spec/SKILL.md`의 Out of Scope 단계에 한 줄(받는 계획에 적었다고 쓰기 전에 그 파일을 grep해 그 줄을 보고, 다섯 번째면 명세의 "본문에 적었다" 문장마다 받는 파일에 그 낱말이 있는지 보는 검사)
**승인:** 자체 승인 2026-11-10, 3회차(이미 있는 지침을 어긴 사건이라 회차를 센다), 일지 2026-11-10-1828-core-tickets.md, 2026-11-12-2108-search-eval-design.md(3회차), ADR 불필요

셀프 리뷰 표준 축 Major 2. 명세 80·238행이 받는 쪽에 적었다고 했으나 `.scratch/source-sync/plan.md`의 diff에 없었다. 반영에서 그 계획 본문에 더했다. to-spec의 Out of Scope를 받는 계획 본문에 적고 Blocked by를 확인하라는 지침이 있는 채로 났다.

2회차는 core 티켓 세션이다. 일지가 search-eval 계획의 문단에 빈 결과에 대한 의견을 적었다고 했으나 없었고, 대기 작업 재사용을 15가 쓴다고 했으나 15의 수용 기준이 받지 않았다. 명세 축 Minor 9와 표준 축 Minor 8이 잡았다.

3회차는 search-eval 설계 세션이다. 이번은 적었다고 쓴 문장이 거짓이었던 것이 아니라, 넘길 것을 받는 쪽에 아예 적지 않았다. SDK가 이미지에 실리는 것을 release-image 계획에 넘기지 않았고(표준 축 Minor), `.github/workflows/ci.yml`의 머리 주석이 이 설계에 미룬 판단과 계약 시험의 inputSchema 시험을 어느 티켓이 받는지 적지 않았다(명세 축 Minor). 반영에서 release-image 계획 본문과 ADR 0018 Consequences, ADR 0015 이력에 더했다. 처방이 to-spec의 Out of Scope 단계라 설계 산출물 단계에는 닿지 않는다.
