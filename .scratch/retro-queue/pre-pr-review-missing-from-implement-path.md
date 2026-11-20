# pre-pr-review-missing-from-implement-path: 범위가 PR과 병합까지인 구현 세션이 PR 직전 리뷰 없이 푸시하려다 병합 절차를 읽으며 알아챘다

**상태:** 열림
**어디로:** `.claude/skills/implement/SKILL.md`의 "Once done, use /code-review" 줄 뒤에 한 문장(사용자가 PR을 여는 데까지 맡겼으면 푸시하기 전에 PR 직전 리뷰를 돌린다. 그 단계의 원천은 `docs/constitution/operations.md` 리뷰 파이프라인 2이고, 이 스킬에는 그 단계도 그 문서를 가리키는 줄도 없다)
**승인:** 자체 승인 2026-11-20, 1회차(이미 있는 지침을 어긴 사건이라 회차를 센다. 더하는 것이라 다섯 번째에 반영한다. PR을 열기 전에 세션이 스스로 알아챘고 PR 서식의 체크리스트도 그 단계를 묻는 자리라 손상이 아니다), 일지 2026-11-20-0133-release-image-03-standalone-compose-behind-proxy.md, ADR 불필요

release-image 03 구현 세션이 시작 지시문의 범위("PR과 병합까지")대로 셀프 리뷰와 커밋을 마치고 PR을 열려 했으나, 그 사이에 PR 직전 `coderabbit-review`를 돌리지 않았다. 병합 절차(`next-session`의 `merge.md`)와 `operations.md`를 읽다가 그 단계가 빠진 것을 알고 푸시 전에 에이전트를 돌렸다. `implement` 스킬은 끝에서 커밋하고 멈추며 "사용자가 `/git-pr`로 PR을 열면" 훅이 계기를 넣는다고 적을 뿐이라, 범위가 그 너머인 세션이 PR 직전 리뷰를 읽을 길이 스킬 안에는 없다. `Grep`으로 `coderabbit|PR 직전`을 스킬에서 찾으면 일치가 없다. 같은 단계의 다른 건너뜀은 `security-review-skipped-on-docs-pr`가 센다.
