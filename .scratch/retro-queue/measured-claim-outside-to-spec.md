# measured-claim-outside-to-spec: 실측을 옮긴 ADR·명세·계획·일지의 문장이 첫 실행의 값, 출력에 없는 보편 주장, 흉내 낸 조건의 값을 그대로 적어 셀프 리뷰와 PR 직전 리뷰가 잡았다

**상태:** 열림
**어디로:** `docs/agents/issue-tracker.md` 프로브와 근거 절(`.claude/skills/to-spec/SKILL.md` 3단계에 둔 "적기 전에 커밋한 출력에서 값을 글자로 찾는다"를 모든 근거 문장의 자리(ADR, 일지, 기능 계획, 프로브 README, 독스트링)에 닿게 이 절로 옮기고, 같은 프로브를 다시 돌렸으면 판정할 실행을 정해 그 실행의 값만 쓰며, 흉내 낸 조건으로 잰 값이면 그 조건을 문장에 붙인다는 갈래를 더한다)
**승인:** 자체 승인 2026-11-22, 18회차(measured-claim-beyond-probe의 18회차. 닫힌 그 항목이 "그 자리들에서 또 나면 17회차로 세고 넓힐지는 그때 retro가 정한다"고 적었고, 17회차는 처방이 다른 `to-spec-path-rule-vs-evidence-citation`이 이었다. 처방을 넓히는 것이라 그 항목에 더하지 않고 새로 쓴다. 더하는 것이고 5회차를 넘어 chore 배치 조건이다), 일지 2026-11-21-2139-source-sync-stuck-calls-design.md, ADR 불필요

source-sync의 막힌 호출 설계 세션이다. 프로브 `stuck-mount`의 결과를 명세·ADR 0023·db-source 계획·일지로 옮긴 문장을 셀프 리뷰 2회차가 잡았다. 재실행으로 판정한다고 정해 두고 첫 실행의 값(285초)을 썼고, 처리기를 단 SIGTERM과 SIGKILL 8초를 모든 칸의 사실처럼 썼으며, 출력은 4.2초까지인데 "0.1~4초"로 썼고, 커널 헛돎의 원인과 범위를 단정했고, 같은 가상 기계의 컨테이너 파일 서버를 "실제 공유 폴더"로 썼다. PR 직전 리뷰(`coderabbit-review`)는 빈 파이프로 잰 막힌 스레드의 메모리(14.2kB)를 읽던 바이트가 든 경우까지 덮는 값처럼 쓴 것을 잡았다. 닫힌 measured-claim-beyond-probe의 처방은 `to-spec` 3단계에만 닿아, 설계 인터뷰가 고친 명세와 ADR, 기능 계획, 일지에는 실리지 않았다. 같은 닫힌 항목에서 이어진 다른 처방(두 지침이 어긋나는 자리를 고친다)은 `to-spec-path-rule-vs-evidence-citation`이 다룬다.
