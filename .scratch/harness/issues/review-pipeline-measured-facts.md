# review-pipeline-measured-facts: 헌법 운영 문서의 리뷰 파이프라인 실측 항목을 PR #1~#3의 관찰로 채운다

**What to build:** `docs/constitution/operations.md` 리뷰 파이프라인 절의 빈 문장(첫 PR의 번호, CodeRabbit 좌석, 별 수에 따른 자동 리뷰 여부를 첫 PR 뒤에 채운다)을 PR #1~#3에서 실제로 본 것으로 채우고, 문구 수정이라 헌법 판을 1.1.0에서 1.1.1로 올린다. 회고(일지 `docs/journal/2026-11-10-0118-core-spec.md`의 `## 회고`)가 헌법 문서라 넘긴 것을 사용자가 이 PR에서 채우라고 답한 반영이고, 명세 PR(`docs/core-spec`)에 함께 싣는 harness 티켓이다. 새 ADR은 없다(승인된 문장이 채우라고 정해 둔 것을 실행한다).

**대기열:** 없음

**Status:** done

- [x] 운영 문서의 그 문장이 첫 PR 번호, 좌석 상태, 별 10개 미만의 자동 리뷰 여부와 호출 방법, 포함 한도와 리뷰까지의 시간, Claude Code Review 코멘트 수를 적는다
- [x] `docs/constitution/README.md`의 판이 1.1.1이고 `tools/sibling_overlap.py`가 형제보다 높다고 한다
- [x] 회고 반영: 헌법 운영 문서의 실측 항목 빈칸을 채우고 판을 1.1.1로 올렸다, 일지 2026-11-10-0118-core-spec.md
