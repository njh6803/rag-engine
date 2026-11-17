# cross-repo-wait-on-frontier: 다른 저장소의 일을 기다리는 기능이 전체 계획의 프론티어에 시작할 수 있는 기능으로 올라, 세션이 그 기능의 설계 인터뷰를 열 수 있다고 잘못 답했다

**상태:** 열림
**어디로:** `tools/plan_table.py`(기능 계획 첫 문단의 대기 필드 줄을 읽어, 그 줄이 있는 기능을 프론티어에서 빼고 `.scratch/plan.md`에 기다리는 기능 목록으로 낸다. 독스트링의 프론티어 항목과 못 보는 것, 시험을 함께 고친다), `docs/agents/issue-tracker.md`(전체 계획 절의 기능 계획 모양), `.scratch/release-image/plan.md`(본문 첫 문단의 대기를 그 줄로 옮기고 `.scratch/plan-head.md` 순서 절의 같은 문단을 걷는다)
**승인:** 자체 승인 2026-11-14, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-14-2150-release-image-after-agent-os.md, ADR 불필요

release-image의 설계 인터뷰는 agent-os가 판 내기 워크플로를 지어 첫 판을 낸 뒤 오는 지시문으로 연다(사용자가 2026-11-11 그 저장소의 세션에서 정했다). `tools/plan_table.py`는 다른 저장소의 기능을 Blocked by 줄에 받지 않아, 그 대기가 이 저장소에 적혀 있지 않던 동안 프론티어가 release-image를 시작할 수 있는 기능으로 보였다. `next-session` 결정표의 "다음 프론티어 기능" 줄과 `grill-with-docs`의 호출 조건(명세도 설계 줄도 없음)도 그 표를 따른다. 1회차는 사용자가 바로잡았고, 그 세션은 빠진 사실을 기능 계획 본문과 plan-head 순서 절에 산문으로 적는 고침만 했다(harness 티켓 `.scratch/harness/issues/release-image-after-agent-os.md`). 산문은 프론티어 줄을 바꾸지 못해, 그 기능 계획을 열기 전까지는 같은 판단이 다시 날 수 있다. agent-os는 다른 저장소의 기능을 Blocked by에 `rag-engine:<slug>` 꼴로 적고 따로 목록을 내는데, 이 저장소는 그 꼴을 옮기지 않았다(`tools/plan_table.py` 독스트링의 프론티어 항목). 외부 조건을 기다리는 일이 전체 계획에 보이지 않는다는 같은 뿌리를 하네스 기능 쪽에서 다루는 항목은 대기열 harness-feature-off-plan이고, 대상 파일 `tools/plan_table.py`가 같아 함께 묶는다.
