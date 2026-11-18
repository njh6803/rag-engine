# edit-during-precommit: 커밋의 pre-commit이 도는 동안 스테이징된 파일을 고쳐, 검사가 모두 지난 뒤에 커밋이 실패했다

**상태:** 열림
**어디로:** 검사 러너(`tools/run_checks.py`)가 도는 동안 표지를 두고, 그 표지가 있으면 추적 파일의 Edit·Write에 알리는 계기 훅(커밋이 도는 중이다. 추적 파일의 편집은 커밋이 끝난 뒤에 한다)
**승인:** 자체 승인 2026-11-13, 5회차(더하는 것이라 다섯 번째에 반영한다. 커밋이 만들어지지 않았을 뿐 잃은 작업이 없어 손상이 아니다), 일지 2026-11-13-0453-search-eval-spec.md, 2026-11-14-2016-search-eval-07-inference-records.md(2회차. 커밋이 아니라 손으로 백그라운드로 돌린 `tools/run_checks.py`가 도는 동안 소스를 고쳐, 그 결과가 고친 뒤의 상태를 재지 못했다), 2026-11-17-0304-search-eval-20-min-score-argument.md(3회차. 백그라운드로 돌리던 `tools/run_checks.py`가 도는 동안 시험 파일을 고쳐, 그 실행을 멈추고 처음부터 다시 돌렸다), 2026-11-19-0123-release-docs-and-merge-procedure.md(4회차. 백그라운드로 돌린 `tools/run_checks.py`가 도는 동안 셀프 리뷰의 반영으로 헌법 문서와 병합 절차를 고쳐, 그 결과가 고친 뒤의 상태를 재지 못했다. 고침을 모두 끝낸 뒤 처음부터 다시 돌렸다), 2026-11-19-0515-release-image-01-images-show-release-number.md(5회차. 백그라운드로 돌린 `tools/run_checks.py`가 도는 동안 셀프 리뷰의 반영으로 문서와 시험 파일을 고쳐, 그 실행을 멈추고 처음부터 다시 돌렸다. 회차가 5에 이르러 chore 배치의 계기가 된다), ADR 불필요

search-eval 명세 세션이 `git commit`을 백그라운드로 돌려 두고, 그 사이에 PR 직전 리뷰의 반영을 스테이징된 파일에 덧썼다. 검사 러너의 열은 모두 Passed였는데(pytest 406.7초) 훅이 `files were modified by this hook`으로 끝나 커밋이 만들어지지 않았고, 반영분을 스테이징해 다시 돌렸다(pytest 572.6초). 표지를 어디에 두고 훅이 어떻게 읽을지는 이 항목을 반영하는 chore가 정한다.
