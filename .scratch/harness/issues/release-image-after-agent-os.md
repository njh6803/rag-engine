# release-image-after-agent-os: release-image 기능 계획에 agent-os의 첫 판 뒤로 미룬 설계 인터뷰의 대기를 적는다

**What to build:** release-image의 설계 인터뷰는 agent-os가 판 내기 워크플로를 짓고 첫 판을 낸 뒤 사용자에게 주는 지시문으로 연다. 사용자가 2026-11-11 그 저장소의 세션에서 정한 순서다(그 저장소의 일지 `docs/journal/2026-11-11-1532-release-image-design-round3.md`). 이 순서가 이 저장소에는 적혀 있지 않았고, `tools/plan_table.py`는 다른 저장소의 기능을 Blocked by 줄에 받지 않아 전체 계획의 프론티어가 release-image를 시작할 수 있는 기능으로 보였다. 2026-11-14 세션이 그것을 보고 release-image의 설계 인터뷰를 열 수 있다고 답했고, 사용자가 바로잡았다(일지 `2026-11-14-2150-release-image-after-agent-os.md`). 다음 세션이 같은 판단을 내리지 않게, release-image 기능 계획 본문의 첫 문단과 `.scratch/plan-head.md`의 순서 절에 그 대기를 적고 전체 계획을 다시 만든다. 대기와 어긋나는 `tools/plan_table.py` 독스트링의 프론티어 항목 문장("rag-engine 은 다른 저장소의 기능에 막히지 않는다")을 고친다. 도구의 동작과 시험은 바꾸지 않는다. 대기를 프론티어 계산에 반영하는 검사는 이 티켓에 넣지 않는다(첫 사건이고 손상이 없다, `CLAUDE.md` 교정 루프).

**대기열:** 없음

**Status:** done

- [x] release-image 기능 계획 본문의 첫 문단이 대기, 근거, 그사이 할 일, 문단을 걷는 때를 적는다
- [x] `.scratch/plan-head.md` 순서 절이 같은 대기를 적고 그 문단을 가리킨다
- [x] `tools/plan_table.py` 독스트링의 프론티어 항목이 대기와 어긋나지 않는다
- [x] `uv run python tools/plan_table.py`로 `.scratch/plan.md`를 다시 만들었다
- [x] 손으로 치는 검사 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)이 초록이다(이 티켓을 싣는 커밋의 pre-commit이 다섯을 돌린다. 하나라도 빨가면 커밋이 만들어지지 않는다)
