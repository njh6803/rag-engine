# pre-pr-review-cli-gaps: CodeRabbit CLI가 도는 PR의 PR 직전 리뷰는 셀프 리뷰가 새로 쓴 문장을 넘기지 않고, CLI 리뷰 정의는 `.claude/skills/`의 지적을 오탐으로 거른다

**상태:** 열림
**어디로:** `.claude/agents/coderabbit-review.md`(부르는 명령, "이 저장소에서 오탐으로 분류하는 것"의 `.claude/skills/`), `.claude/skills/code-review/SKILL.md` 6단계 1, `-c`로 주장이 실리지 않으면 `docs/constitution/operations.md` 리뷰 파이프라인(ADR 필요)
**승인:** 사용자 승인 2026-11-28, 1회차(더하는 것이라 다섯 번째에 반영한다. 사용자가 바로잡은 설명으로 다시 골랐다), 일지 2026-11-26-1938-admin-screens.md, ADR은 `-c`로 주장이 실리지 않을 때 필요(운영 문서의 리뷰 파이프라인)

운영 문서의 리뷰 파이프라인은 PR 직전에 CLI가 돌면 CLI로 보고, 못 돌 때만 `bug-perf-review`를 쓰게 한다. `code-review` 6단계 1은 셀프 리뷰를 반영하며 새로 쓴 사실 문장을 `bug-perf-review` 브리프에 밀 주장으로 나열하라고 하면서, CLI가 도는 PR에는 넘기는 길이 아직 없다고 적는다. 넘기지 않는 것은 `coderabbit-review`가 부르는 명령(그 정의 17행의 `coderabbit review --agent --include-untracked`)이다. CLI 0.7.5 자체에는 지시 파일을 받는 `-c, --config <files...>`가 있어(`coderabbit review --help`를 읽었다), 밀 주장을 파일로 넘길 수 있을지 모른다. 그 인자로 주장이 리뷰에 실리는지는 재지 않았다. 실리면 운영 문서를 바꾸지 않고 `coderabbit-review` 정의와 `code-review` 6단계 1만 고쳐도 될 수 있어, 반영하는 세션이 먼저 잰다. 또 `coderabbit-review` 정의는 `.claude/skills/`의 지적을 "남이 쓴 스킬"이라며 오탐으로 거르는데, 이 저장소의 스킬은 PR이 고치는 프로젝트 사본이다. admin 화면 PR은 CLI가 돌았는데도 두 리뷰를 나란히 띄웠고, `bug-perf-review`가 화면 그림 스킬의 웹 편집 확인에서 줄바꿈 대조의 순서 오류(Minor 1)를 찾았다.
