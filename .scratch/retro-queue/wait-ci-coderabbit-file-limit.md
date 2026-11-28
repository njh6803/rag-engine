# wait-ci-coderabbit-file-limit: CodeRabbit이 파일 수 한도로 리뷰를 건너뛴 PR에서 `wait_ci`가 리뷰를 요청하지 않았다고 끝나 다시 요청하라고 안내한다

**상태:** 열림
**어디로:** `tools/wait_ci.py`(건너뜀의 까닭을 PR의 CodeRabbit 답 코멘트로 가르고, 파일 수 한도로 건너뛰었으면 다시 요청하라고 하지 않고 검사와 다른 봇 리뷰로 판정하라고 안내하며, 못 보는 것의 "파일 수 한도" 항목을 고친다)
**승인:** 자체 승인 2026-11-28, 1회차(도구의 버그를 고치는 것이라 사건 하나로 반영한다. 사건이 난 PR은 화면과 이름 바꾸기를 담아 그 PR에는 싣지 않았다), 일지 2026-11-26-1938-admin-screens.md, ADR 불필요

PR #127에서 `@coderabbitai review`를 남기자, CodeRabbit이 "Review skipped: 114 files exceed the limit of 100."으로 답했다. 머리 커밋의 CodeRabbit 체크 런은 SKIPPED였고, `wait_ci`가 찍은 그 상태의 설명은 "Review skipped: manual review required for this OSS repository"였다. `wait_ci`는 종료 4와 "리뷰가 요청되지 않았다. `@coderabbitai review` 를 남기고 다시 띄운다"로 끝났다. 체크 런은 요청 전의 건너뜀과 같은 꼴이라, 까닭은 PR에 달린 CodeRabbit의 답 코멘트에서 읽어야 한다. 다시 요청해도 파일 수가 그대로라 같은 한도에 걸릴 것으로 어림하고(다시 요청해 보지는 않았다), 그 요청은 시간당 한 번인 리뷰 한도(`docs/constitution/operations.md` 리뷰 파이프라인)를 쓸 것으로 어림한다(건너뛴 요청이 한도를 쓰는지는 재지 않았다). `next-session` `merge.md` 2에 CodeRabbit이 리뷰할 수 없는 PR의 회차를 세는 문장을 더하는 것은 고침이 아니라 더하는 것이라 이 항목에 싣지 않는다. 도구의 안내가 다음 할 일을 알리면 그 문장은 들지 않는다. 같은 도구의 다른 갈래는 `wait-ci-stale-review-state-on-rerequest`다.
