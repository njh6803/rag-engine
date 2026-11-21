# coderabbit-hourly-limit-shared-across-prs: 앞 리뷰에서 77분쯤 지나 낸 `@coderabbitai review`가 한도에 걸려, 첫 리뷰 뒤의 커밋이 CodeRabbit 리뷰 없이 병합됐다

**상태:** 열림
**어디로:** `.claude/skills/next-session/merge.md`(봇 회차의 대기. 요청하기 전에 이 저장소의 다른 PR이 지난 한 시간 안에 리뷰를 받았는지 본다)
**승인:** 자체 승인 2026-11-21, 2회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-21-1358-source-sync-spec.md(1회차는 PR 89, 2회차는 PR 95), ADR 불필요

`docs/constitution/operations.md`의 리뷰 파이프라인은 포함 한도를 시간당 리뷰 1회로 적는다. PR 89에서는 그 PR의 앞 리뷰에서 77분쯤 지나 낸 요청도 `Review rate limited`로 끝났다. PR 95에서는 그 PR이 리뷰를 한 번도 받지 않았는데 연 지 3분 뒤의 첫 요청이 `Review rate limited`로 끝났고, 요약 코멘트는 `Next included review available in 22 minutes.`를 적었다. 그래서 한도는 PR마다가 아니라 더 넓은 단위(저장소나 계정)로 세는 것으로 본다. 어느 단위인지는 재지 않았다. 재어 본 결과로 운영 문서의 한도 문장을 고치게 되면 그 문서는 헌법이라 사용자 승인이 따로 든다. 경과는 PR 89의 본문 "확인 방법"과 마지막 코멘트에 있다.
