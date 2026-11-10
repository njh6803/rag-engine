# check-quotes-untracked-scope: `check_quotes.py --all-lines`를 인자 없이 치면 추적되지 않은 .md를 조용히 건너뛰어 미추적 일지의 경고 둘이 0으로 보였다

**상태:** 열림
**어디로:** `tools/check_quotes.py`(인자 없는 호출의 대상에 `git ls-files --others --exclude-standard`의 .md를 더하거나, 독스트링의 못 보는 것에 "추적되지 않은 파일" 항목을 적고 `tests/tools/`의 시험으로 고정한다. `.claude/rules/tools.md`의 못 보는 것 항목)
**승인:** 자체 승인 2026-11-10, 1회차(고침이라 문턱 없이 반영한다), 일지 2026-11-10-0118-core-spec.md, ADR 불필요

명세 세션의 새 파일(명세, 일지)은 커밋 전까지 미추적이라 셀프 리뷰 반영 뒤의 검증 실행 `--all-lines`가 그 둘을 보지 않았고 "경고 없음"이 나왔다. 경로를 넘겨 다시 돌리자 일지의 질문 인용 둘이 경고됐다. 독스트링은 "추적되는 .md 전부"라고 적지만 못 보는 것 목록에는 그 항목이 없다. `check_line_separators.py`는 같은 자리를 못 보는 것에 적어 두었다.
