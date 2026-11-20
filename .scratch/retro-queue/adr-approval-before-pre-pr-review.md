# adr-approval-before-pre-pr-review: ADR 초안의 승인을 PR 직전 리뷰보다 먼저 받아, 리뷰가 낸 Major를 고치며 승인받은 글이 병합 전에 바뀌었다

**상태:** 열림
**어디로:** `.claude/skills/grill-with-docs/SKILL.md` 산출물 단계에 한 줄(ADR 초안은 셀프 리뷰와 PR 직전 리뷰를 모두 거친 뒤에 승인 화면에 올린다. PR 직전 리뷰의 원천은 `docs/constitution/operations.md` 리뷰 파이프라인 2다)
**승인:** 자체 승인 2026-11-21, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-20-2034-source-sync-design.md, ADR 불필요

source-sync 설계 세션은 셀프 리뷰(`/code-review`)를 반영한 초안으로 ADR 0021과 0022의 승인을 받았고, PR 직전 리뷰(`coderabbit-review`)는 그 뒤에 돌렸다. 그 리뷰가 ADR 0021의 서버 경로 원천 경계 규칙을 Major로 냈고(적은 글자만 보고 가르면 `..`나 심볼릭 링크로 `/sources` 밖을 읽게 된다), 승인받은 문단에 세 문장을 더했다. 고른 방향을 바꾸지 않는 풀이로 보아 새 질문은 올리지 않고 사용자에게 원문과 함께 알렸다.

결정이 바뀐 것은 없지만 사용자가 승인한 글과 병합되는 글이 달라졌다. 같은 결과를 다른 원인(초안이 고른 선택지의 조건을 빠뜨린 것)으로 다루는 항목이 `adr-draft-drops-option-conditions`다. 반영할 때는 승인 화면에서 사용자가 고칠 곳을 고르면 두 리뷰를 어디까지 다시 돌릴지도 함께 정한다.
