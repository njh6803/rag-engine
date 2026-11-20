# wait-ci-stale-review-state-on-rerequest: 한도에 걸렸던 헤드에 CodeRabbit 리뷰를 다시 요청하면 `wait_ci`가 앞 요청의 한도 표시를 끝난 리뷰로 읽어 리뷰가 시작되기 전에 통과로 끝난다

**상태:** 열림
**어디로:** `tools/wait_ci.py`(같은 헤드에 남은 `Review rate limited` 체크 런을, 대기를 띄운 뒤 요청 유예 동안은 건너뜀처럼 아직 요청이 닿지 않은 상태로 읽는다. 그 입력을 고정하는 시험을 `tests/tools/`의 그 도구 시험에 더하고, 독스트링의 못 보는 것도 함께 고친다)
**승인:** 자체 승인 2026-11-21, 1회차(도구의 버그를 고치는 것이라 사건 하나로 반영한다. 사건이 난 PR은 설계 문서만 담아 그 PR에는 싣지 않았다), 일지 2026-11-20-2034-source-sync-design.md, ADR 불필요

PR 89의 첫 푸시에서 CodeRabbit이 한도에 걸려 그 헤드에 체크 런 `neutral`, `Review rate limited`가 남았다. 다음 날 같은 헤드에 `@coderabbitai review`를 다시 남기고 곧바로 `uv run python tools/wait_ci.py 89`를 띄우자, 도구가 `끝: 모두 통과. CodeRabbit: Review rate limited`(종료 0)로 끝났다. 그 직후 `gh api …/commits/<헤드>/check-runs`로 본 CodeRabbit 체크 런은 `in_progress`, `Review in progress`였다(요청 코멘트 20:00:07, CodeRabbit의 답 20:00:16, 체크 런의 `started_at` 20:00:29, 모두 2026-11-20 UTC).

그 도구의 `_settle`은 진행 중이거나 나타나지 않았거나 요청되지 않은(건너뜀) 검사가 없으면 곧바로 통과로 끝내고, 요청 유예 90초는 건너뜀 상태에만 건다(334~348줄을 읽었다). 한도 표시는 끝난 결과로 읽히므로 유예가 걸리지 않는다. 이 세션은 체크 런을 직접 보고 대기를 다시 띄웠지만, 끝 줄만 믿으면 리뷰 없이 병합하는 길로 이어진다.

같은 세션에서 본 것이 하나 더 있다. 그 독스트링이 못 보는 것에 "세션이 꺼진 뒤의 완료"를 재지 않았다고 적는데, 앱 세션이 끝나자 배경으로 띄운 대기도 끝 줄을 내지 못하고 멈췄고 출력 파일은 비어 있었다. 다시 열린 세션에는 작업이 멈췄다는 알림만 왔다(한 번 본 것이다).
